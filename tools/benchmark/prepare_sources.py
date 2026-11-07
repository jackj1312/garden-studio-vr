#!/usr/bin/env python3
"""Prepare a benchmark's original sources for a run: check every file is readable, fetch iCloud placeholders, read
capture dates, extract video frames at a fixed rate with timestamps, and write a dated source register.

  python3 prepare_sources.py [--manifest source-manifest.json] [--out prepared/] [--fps 1] [--max-px 1280]
                             [--quality 0.75] [--wait 600] [--no-frames] [--no-hash]

Works for any property: it only reads the files listed in the manifest (no folder traversal) and never uploads
anything. iCloud placeholders are requested with `brctl download` and waited for. Capture dates come from EXIF
(photos), the MP4/MOV `mvhd` atom (videos, UTC), the PDF `/CreationDate` and dates in file names (drawings, letters);
`date_basis` says which. Frames are extracted with AVFoundation via `extract_frames.swift` (compiled once into
~/Library/Caches/garden-studio-benchmark), falling back to ffmpeg if installed. Preview frames are JPEGs at a modest
size; for camera solves extract full resolution at the recorded timestamp from the original video (max-px 0).

Output: <out>/source-register.json and <out>/frames/<video>/<video>_t<seconds>.jpg"""
import argparse, datetime, hashlib, json, os, re, shutil, struct, subprocess, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MANIFEST = os.path.expanduser("~/Desktop/Garden Studio Benchmark/source-manifest.json")
_REPO_DOCS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "docs", "benchmark")
# In the publishing checkout: docs/benchmark/inputs/prepared (published by publish.py). Elsewhere: ./prepared
DEFAULT_OUT = os.path.join(_REPO_DOCS, "inputs", "prepared") if os.path.isdir(_REPO_DOCS) else os.path.join(os.getcwd(), "prepared")
DATALESS = 0x40000000
CACHE = os.path.expanduser("~/Library/Caches/garden-studio-benchmark")
PHOTO = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff"}
VIDEO = {".mp4", ".mov", ".m4v"}


def is_placeholder(p):
    try:
        return bool(os.stat(p).st_flags & DATALESS)
    except (OSError, AttributeError):
        return False


def readable(p):
    try:
        with open(p, "rb") as f:
            f.read(4096)
        return True
    except OSError:
        return False


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def hydrate(paths, wait_s):
    """Ask iCloud for every placeholder, then wait until they have bytes (or time runs out)."""
    todo = [p for p in paths if is_placeholder(p)]
    if not todo:
        return []
    if not shutil.which("brctl"):
        return todo
    print("Requesting %d iCloud placeholder(s) with brctl download ..." % len(todo))
    for p in todo:
        try:
            subprocess.run(["brctl", "download", p], capture_output=True, timeout=60)
        except Exception as e:
            print("  brctl failed for %s: %s" % (p, e))
    t0 = time.time()
    while time.time() - t0 < wait_s:
        todo = [p for p in todo if is_placeholder(p)]
        if not todo:
            break
        print("  waiting for %d file(s) ... (%.0fs)" % (len(todo), time.time() - t0))
        time.sleep(10)
    return [p for p in todo if is_placeholder(p)]


# ---------------------------------------------------------------- metadata readers
def exif_info(p):
    try:
        from PIL import Image
    except ImportError:
        return {}
    try:
        im = Image.open(p); ex = im.getexif(); sub = ex.get_ifd(0x8769) if ex else {}
        w, h = im.size
        if ex.get(274) in (5, 6, 7, 8):
            w, h = h, w  # displayed orientation
        out = {"width_px": w, "height_px": h}
        dto = sub.get(36867) or ex.get(306)
        if dto:
            d = dto.strip().replace(":", "-", 2)
            out["capture_local"] = d
            off = sub.get(36881) or sub.get(36880)
            out["capture_date"] = d[:10]; out["date_basis"] = "EXIF DateTimeOriginal" + (" (offset %s)" % off if off else "")
            if off:
                out["capture_offset"] = off
        make, model = ex.get(271), ex.get(272)
        if make or model:
            out["device"] = " ".join(x for x in (make, model) if x).strip()
        return out
    except Exception as e:
        return {"metadata_error": str(e)}


def _boxes(f, end):
    while f.tell() < end:
        h = f.read(8)
        if len(h) < 8:
            return
        size, typ = struct.unpack(">I4s", h); hdr = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]; hdr = 16
        elif size == 0:
            size = end - f.tell() + 8
        start = f.tell() - hdr
        yield typ, start, size, hdr
        f.seek(start + size)


def mp4_info(p):
    out = {}
    try:
        end = os.path.getsize(p)
        with open(p, "rb") as f:
            top = list(_boxes(f, end))
            if not any(t == b"moov" for t, _, _, _ in top):
                declared = sum(sz for _, _, sz, _ in top)
                out["video_error"] = ("no moov atom: truncated or incomplete video (boxes declare %.0f MB, file is %.0f MB); not playable"
                                      % (declared / 1e6, end / 1e6))
            for typ, s, sz, h in top:
                if typ != b"moov":
                    continue
                f.seek(s + h)
                for t2, s2, sz2, h2 in _boxes(f, s + sz):
                    if t2 == b"mvhd":
                        f.seek(s2 + h2); ver = f.read(1)[0]; f.read(3)
                        if ver == 1:
                            c, m, ts, d = struct.unpack(">QQIQ", f.read(28))
                        else:
                            c, m, ts, d = struct.unpack(">IIII", f.read(16))
                        if c:
                            dt = datetime.datetime(1904, 1, 1) + datetime.timedelta(seconds=c)
                            out["capture_utc"] = dt.isoformat() + "Z"; out["capture_date"] = dt.date().isoformat()
                            out["date_basis"] = "MP4 mvhd creation_time (UTC)"
                        if ts:
                            out["duration_s"] = round(d / ts, 3)
                break
    except Exception as e:
        out["metadata_error"] = str(e)
    return out


def pdf_info(p):
    out = {}
    try:
        with open(p, "rb") as f:
            data = f.read()
        m = re.search(rb"/CreationDate\s*\(D:(\d{4})(\d{2})(\d{2})", data)
        if m:
            out["file_created"] = "%s-%s-%s" % tuple(x.decode() for x in m.groups())
        out["pages"] = len(re.findall(rb"/Type\s*/Page[^s]", data)) or None
    except Exception as e:
        out["metadata_error"] = str(e)
    return out


def name_date(name):
    m = re.search(r"(20\d{2})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})", name)
    if m:
        return "%s-%s-%s" % m.groups()[:3], "file name (camera timestamp)"
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{2})(?!\d)", name)
    if m:
        d, mo, y = m.groups()
        return "20%s-%s-%s" % (y, mo, d), "date in file name (dd.mm.yy)"
    return None, None


def drawing_meta(name):
    m = re.match(r"^(\d{3,6})\.(\w+?)\s", name)
    if not m:
        return {}
    num, rev = m.groups()
    sheet = re.match(r"(\d+|[A-Z]+)([A-Z]?)$", rev)
    return {"drawing": "%s.%s" % (num, rev), "sheet": sheet.group(1) if sheet else rev, "revision": (sheet.group(2) or "-") if sheet else None}


# ---------------------------------------------------------------- frames
def extractor():
    src = os.path.join(HERE, "extract_frames.swift")
    if not os.path.exists(src):
        return None
    tag = hashlib.sha256(open(src, "rb").read()).hexdigest()[:12]
    exe = os.path.join(CACHE, "extract_frames-" + tag)
    if os.path.exists(exe):
        return exe
    if shutil.which("swiftc"):
        os.makedirs(CACHE, exist_ok=True)
        r = subprocess.run(["swiftc", "-O", src, "-o", exe], capture_output=True, text=True)
        if r.returncode == 0:
            return exe
        print("swiftc failed:", r.stderr[-400:])
    return None


def extract(video, outdir, prefix, fps, max_px, quality):
    exe = extractor()
    frames, header = [], {}
    if exe:
        r = subprocess.run([exe, video, outdir, prefix, str(fps), str(max_px), str(quality)], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if "duration" in j:
                header = j
            elif j.get("file"):
                frames.append({"t_s": j["t"], "file": j["file"]})
        return frames, header, "AVFoundation (extract_frames.swift)"
    if shutil.which("ffmpeg"):
        os.makedirs(outdir, exist_ok=True)
        scale = [] if not max_px else ["-vf", "fps=%s,scale='if(gt(iw,ih),min(%d,iw),-2)':'if(gt(iw,ih),-2,min(%d,ih))'" % (fps, max_px, max_px)]
        subprocess.run(["ffmpeg", "-loglevel", "error", "-i", video] + (scale or ["-vf", "fps=%s" % fps]) + ["-q:v", "4", os.path.join(outdir, prefix + "_%06d.jpg")])
        for i, n in enumerate(sorted(x for x in os.listdir(outdir) if x.startswith(prefix + "_"))):
            new = "%s_t%07.2f.jpg" % (prefix, i / fps); os.replace(os.path.join(outdir, n), os.path.join(outdir, new))
            frames.append({"t_s": round(i / fps, 3), "file": new})
        return frames, header, "ffmpeg"
    return [], {}, "no extractor (needs macOS swiftc or ffmpeg)"


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST); ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--fps", type=float, default=1.0); ap.add_argument("--max-px", type=int, default=1280)
    ap.add_argument("--quality", type=float, default=0.75); ap.add_argument("--wait", type=float, default=600)
    ap.add_argument("--no-frames", action="store_true"); ap.add_argument("--no-hash", action="store_true")
    a = ap.parse_args(argv)
    man = json.load(open(a.manifest))
    rows = man.get("files", [])
    paths = [r["path"] for r in rows]
    os.makedirs(a.out, exist_ok=True)
    still = hydrate([p for p in paths if os.path.exists(p)], a.wait)
    files, unreadable = [], []
    for r in rows:
        p = r["path"]; name = os.path.basename(p); ext = os.path.splitext(name)[1].lower()
        e = {"id": os.path.splitext(name)[0], "name": name, "path": p, "kind": r.get("kind"),
             "type": "photo" if ext in PHOTO else "video" if ext in VIDEO else "drawing" if ext == ".pdf" else "scan" if ext in {".usdz", ".ply", ".obj"} else "other"}
        if "frame" in (r.get("kind") or ""):
            e["type"] = "frame"
        if not os.path.exists(p):
            e["status"] = "missing"; unreadable.append({"path": p, "reason": "missing"}); files.append(e); continue
        if p in still or is_placeholder(p):
            e["status"] = "icloud-placeholder"; unreadable.append({"path": p, "reason": "iCloud placeholder: bytes not downloaded"}); files.append(e); continue
        if not readable(p):
            e["status"] = "unreadable"; unreadable.append({"path": p, "reason": "cannot be read"}); files.append(e); continue
        st = os.stat(p); e["status"] = "ok"; e["bytes"] = st.st_size
        if not a.no_hash:
            e["sha256"] = sha256(p)
        nd, nb = name_date(name)
        if e["type"] in ("photo", "frame"):
            e.update(exif_info(p))
        elif e["type"] == "video":
            e.update(mp4_info(p))
            if e.get("video_error"):
                e["status"] = "unplayable"; unreadable.append({"path": p, "reason": e["video_error"]})
        elif ext == ".pdf":
            e.update(pdf_info(p)); e.update(drawing_meta(name))
            if not e.get("drawing"):
                e["type"] = "document"
        elif ext == ".usdz":
            try:
                with zipfile.ZipFile(p) as z:
                    dts = [i.date_time for i in z.infolist()]
                if dts:
                    e["capture_date"] = "%04d-%02d-%02d" % min(dts)[:3]; e["date_basis"] = "USDZ archive entry date"
            except Exception as x:
                e["metadata_error"] = str(x)
        if not e.get("capture_date") and nd:
            e["capture_date"], e["date_basis"] = nd, nb
        if not e.get("capture_date") and e.get("file_created"):
            e["capture_date"], e["date_basis"] = e["file_created"], "PDF CreationDate (issue/print date, check the title block)"
        if nd and e.get("capture_date") and nd != e["capture_date"] and e["type"] in ("photo", "video"):
            e["name_date"] = nd
        if not e.get("capture_date"):
            e["capture_date"] = None
            e["date_basis"] = "unknown: no capture metadata (file modified %s)" % datetime.date.fromtimestamp(st.st_mtime).isoformat()
            if e["type"] == "frame":
                e["note"] = "previously extracted frame; parent video and timestamp not recorded with it (name prefix %r)" % name.split("_")[0]
        if e["type"] == "video" and not a.no_frames and e["status"] == "ok":
            stem = os.path.splitext(name)[0]
            outdir = os.path.join(a.out, "frames", stem)
            print("Extracting %s at %g fps ..." % (name, a.fps))
            fr, header, how = extract(p, outdir, stem, a.fps, a.max_px, a.quality)
            if header:
                e["width_px"], e["height_px"] = int(header.get("width") or 0), int(header.get("height") or 0)
                e["fps_nominal"] = header.get("fps_nominal")
                e.setdefault("duration_s", header.get("duration"))
            e["frames"] = [{"id": "%s@%.2fs" % (stem, f["t_s"]), "t_s": f["t_s"], "file": "frames/%s/%s" % (stem, f["file"])} for f in fr]
            e["frame_extraction"] = {"method": how, "fps": a.fps, "max_px": a.max_px, "jpeg_quality": a.quality,
                                     "note": "preview frames; extract full resolution at t_s from the original for camera solves"}
        files.append(e)
    def fsize(d):
        tot = 0
        for root, _, names in os.walk(d):
            tot += sum(os.path.getsize(os.path.join(root, n)) for n in names)
        return tot
    reg = {"schema": "garden-studio/source-register/1", "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "manifest": os.path.abspath(a.manifest), "policy": "originals stay where they are (private); only small preview frames are copied here",
           "files": sorted(files, key=lambda e: (e.get("capture_date") or "9999", e["name"])),
           "unreadable": unreadable}
    counts = {}
    for e in files:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    reg["totals"] = {"files": len(files), "by_type": counts, "unreadable": len(unreadable),
                     "frames_extracted": sum(len(e.get("frames", [])) for e in files),
                     "prepared_bytes": fsize(os.path.join(a.out, "frames")) if os.path.isdir(os.path.join(a.out, "frames")) else 0}
    with open(os.path.join(a.out, "source-register.json"), "w") as f:
        json.dump(reg, f, indent=1)
    print("Register: %s" % os.path.join(a.out, "source-register.json"))
    print("Files %d %s; unreadable %d; frames %d (%.1f MB)" % (len(files), counts, len(unreadable), reg["totals"]["frames_extracted"], reg["totals"]["prepared_bytes"] / 1e6))
    for u in unreadable:
        print("  UNREADABLE:", u["reason"], "-", u["path"])
    return 0 if not unreadable else 3


if __name__ == "__main__":
    sys.exit(main())

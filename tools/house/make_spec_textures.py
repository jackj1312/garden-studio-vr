"""Finish textures for a signed spec (WORKFLOW G2b): every finish in spec.finishes becomes a texture set at true scale whose
mean albedo IS the finish's colour_srgb (the spec's chosen colour), so the build never improvises a colour.

    uv run --offline --with numpy --with pillow python tools/house/make_spec_textures.py assets/sites/house/spec/spec_v1.json \
        [--ph master/polyhaven/tex] [--out master/phototex/spec]

Per finish:
  - asset.source "polyhaven": the Poly Haven set (1k diffuse / normal GL / roughness), diffuse gained per channel in linear
    light to the target mean (each fibre / grain keeps its own variation), tile = the set's real dimensions, or the spec
    note's scale (boards "190 x 1900" -> scale so the boards are 190 wide; "micro-texture at 1.5 m tile").
  - an asset that does not show what the finish says (ASSET_MISMATCH below, checked by eye against the set's own preview)
    is NOT used: the finish is built from its own notes (tile size, joint, grout) or as its flat colour, and reported.
  - asset.source "parametric" with tile notes ("300 x 600 mm ... 2 mm joints grout #D9D3C8"): drawn tiles at true size.
  - everything else: a flat colour (no texture), roughness/metalness from the finish type.
Writes <out>/<FINISH>_col.jpg, _nrm.jpg, _rough.jpg and <out>/spec_tex_meta.json {finish: {tile_m, files, rough, metal, source}}."""
import sys, os, json, re, argparse
import numpy as np
from PIL import Image, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("spec"); ap.add_argument("--ph", default="master/polyhaven/tex"); ap.add_argument("--out", default="master/phototex/spec")
ap.add_argument("--px", type=int, default=1024)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
S = json.load(open(a.spec))
FETCHED = json.load(open(os.path.join(os.path.dirname(a.ph.rstrip("/")), "fetched.json"))) if os.path.exists(os.path.join(os.path.dirname(a.ph.rstrip("/")), "fetched.json")) else {}

# the named set does not show the finish (seen on the set's own diffuse, 1 Nov 2026) -> build from the notes / flat, and ask Jack
ASSET_MISMATCH = {
    "grey_cartago_02": "a dark herringbone marble mosaic, not a 600 x 600 warm grey stone-look tile (fallback floor_tiles_06 is a "
                       "black/grey checkerboard): built from the finish notes (600 x 600, 3 mm joints, grout #A39B90) in the finish colour",
    "marble_01": "beige limestone wall blocks with joints, not a white quartz worktop with soft grey vein: built as the flat finish colour",
}
METAL = {"METAL-BLACK": (0.55, 0.6), "BRASS": (0.35, 1.0), "STEEL-BRUSHED": (0.3, 1.0)}
ROUGH = {"TV-BLACK": 0.08, "GLASS-CLEAR": 0.02, "SAN-WHITE": 0.12, "RAL9016": 0.35, "CER-CREAM": 0.7, "KIT-FRONT": 0.6, "KITB-FRONT": 0.35,
         "FIN-SKIRT": 0.4, "FIN-DOOR": 0.4, "FIN-WBOARD": 0.4, "FIN-STAIR": 0.5, "TILE-METRO-WHITE": 0.15, "FIN-TILE-WALL": 0.4,
         "FIN-FLR-TILE": 0.55, "FIN-FLR-OAK": 0.52, "FIN-CEIL": 0.95, "FIN-WALL": 0.9, "FIN-WALL-CLAY": 0.9, "KIT-TOP": 0.25, "KITB-TOP": 0.45}


def hex2rgb(h): h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float64) / 255.0
def lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def srgb(c): c = np.clip(c, 0, 1); return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def recolour(rgb_srgb01, target_hex, keep=1.0):
    """per-channel gain in linear light so the mean equals the target; keep < 1 flattens the variation toward the mean"""
    L = lin(rgb_srgb01); t = lin(hex2rgb(target_hex))
    m = L.reshape(-1, 3).mean(0) + 1e-6
    g = L * (t / m)
    g = t + (g - t) * keep
    # the gain can push a channel past 1 where the source was bright: clip, then re-centre once
    g = np.clip(g, 0, 1); g *= (t / (g.reshape(-1, 3).mean(0) + 1e-6))
    g = np.clip(g, 0, 1)
    if np.abs(srgb(g).reshape(-1, 3).mean(0) - np.asarray(hex2rgb(target_hex))).max() > 8 / 255:      # judged as seen (sRGB mean)
        # a strongly tinted source (a yellow waffle weave) cannot be re-tinted per channel without clipping: take its
        # luminance only and lay the target colour over it (CORRECTIONS-LOG: bed linen came out mint/yellow)
        Y = (L * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
        Y = Y / (Y.mean() + 1e-6); Y = 1 + (Y - 1) * keep
        g = np.clip(t * Y, 0, 1); g *= (t / (g.reshape(-1, 3).mean(0) + 1e-6)); g = np.clip(g, 0, 1)
    return srgb(g)


def load(p, mode="RGB"): return np.asarray(Image.open(p).convert(mode).resize((a.px, a.px), Image.LANCZOS), np.float64) / 255.0
def save(arr, name): Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(a.out, name), quality=90)


def tiles(size_m, tw, th, joint, base_hex, grout_hex, bond="stack", var=None, seed=1):
    """drawn tiles over a size_m square repeat: tw x th (m), joint (m); var = luminance variation image (0..1) or None"""
    n = a.px; rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n] * (size_m / n)
    row = np.floor(yy / th).astype(int)
    off = np.where((row % 2 == 1) & (bond == "brick"), tw / 2, 0.0)
    u = (xx + off) % tw; v = yy % th
    col_i = np.floor((xx + off) / tw).astype(int)
    in_joint = (u < joint) | (v < joint)
    base = lin(hex2rgb(base_hex)); grout = lin(hex2rgb(grout_hex))
    img = np.ones((n, n, 3)) * base
    # per-tile tone +-3 % and the source micro-variation
    tone = 1 + 0.03 * np.sin(col_i * 12.9898 + row * 78.233) * np.cos(col_i * 4.1 + row * 1.3)
    img *= tone[..., None]
    if var is not None: img *= (0.94 + 0.12 * var)[..., None]
    img[in_joint] = grout
    img *= (lin(hex2rgb(base_hex)) / (img[~in_joint].reshape(-1, 3).mean(0) + 1e-6))
    img[in_joint] = grout
    h = np.where(in_joint, 0.0, 1.0)
    h = np.asarray(Image.fromarray((h * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float64) / 255
    gy, gx = np.gradient(h)
    nrm = np.stack([-gx * 2.5, -gy * 2.5, np.ones_like(h)], -1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    return srgb(img), nrm * 0.5 + 0.5, in_joint


def smooth_noise(n, scale_px, seed):
    """tileable value noise: random grid of (n / scale_px) cells, bicubic-upsampled (wraps because the grid wraps)"""
    rng = np.random.default_rng(seed); g = max(2, int(round(n / scale_px)))
    base = rng.standard_normal((g, g))
    big = np.tile(base, (3, 3))
    im = Image.fromarray(((big - big.min()) / (np.ptp(big) + 1e-9) * 255).astype(np.uint8)).resize((3 * n, 3 * n), Image.BICUBIC)
    out = np.asarray(im, np.float64)[n:2 * n, n:2 * n] / 255.0
    return (out - out.mean()) / (out.std() + 1e-9)


def paint(col, fid, rough):
    """matt emulsion on a plastered wall (row 188, Jack: walls looked like concrete): the finish colour, a barely visible
    low-frequency tone drift (+-0.6 % luminance, no blotches), a fine roller stipple in the normal map only, roughness
    rough +- 0.03. Tiles seamlessly (noise grids wrap)."""
    n = a.px; t = lin(hex2rgb(col))
    low = 0.6 * smooth_noise(n, 256, 11) + 0.4 * smooth_noise(n, 96, 12)
    img = t[None, None, :] * (1 + 0.006 * low[..., None])
    img *= t / img.reshape(-1, 3).mean(0)
    # roller stipple: isotropic (blurred white noise, wraps) - never a grid (a value-noise grid read as woven fabric on ceilings)
    rng = np.random.default_rng(13); wn = rng.standard_normal((n, n))
    big = np.tile(wn, (3, 3))
    hb = np.asarray(Image.fromarray(((big - big.min()) / np.ptp(big) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.4)), np.float64)[n:2 * n, n:2 * n] / 255
    h = (hb - hb.mean()) / (hb.std() + 1e-9) * 0.02
    gy, gx = np.gradient(h)
    nrm = np.stack([-gx * 1.5, -gy * 1.5, np.ones_like(h)], -1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)   # barely there: a painted wall reads flat
    r = np.clip(rough + 0.03 * smooth_noise(n, 128, 15), 0.02, 1.0)
    save(srgb(img), f"{fid}_col.jpg"); save(nrm * 0.5 + 0.5, f"{fid}_nrm.jpg"); save(np.stack([r] * 3, -1), f"{fid}_rough.jpg")


PAINT = {"FIN-WALL", "FIN-WALL-CLAY", "FIN-CEIL"}
ACG = os.path.join(os.path.dirname(a.ph.rstrip("/")), "..", "ambientcg")      # master/ambientcg/<id>/<id>_1K-JPG_*.jpg


def acg(aid, kind):
    d = os.path.join(ACG, aid)
    return next((os.path.join(d, x) for x in sorted(os.listdir(d)) if x.endswith(f"_{kind}.jpg")), None) if os.path.isdir(d) else None


meta = {}
notes_out = []
for f in S["finishes"]:
    fid, col = f["id"], f["colour_srgb"]
    src = f["asset"].get("source"); aid = f["asset"].get("id", "")
    notes = f.get("notes", "")
    rough, metal = ROUGH.get(fid, 0.6), 0.0
    if fid in METAL: rough, metal = METAL[fid]
    entry = dict(colour_srgb=col, rough=rough, metal=metal, tile_m=[1.0, 1.0], files={}, source="flat colour")
    if fid in PAINT:
        paint(col, fid, rough)
        tile = 1.5
        entry.update(tile_m=[tile, tile], files=dict(col=f"{fid}_col.jpg", nrm=f"{fid}_nrm.jpg", rough=f"{fid}_rough.jpg"), rough_map=True,
                     source=f"procedural matt emulsion (tools/house/make_spec_textures.py paint): {col}, +-0.6 % tone drift, roller stipple normal, roughness {rough}+-0.03")
        meta[fid] = entry; continue
    if src == "ambientcg" and acg(aid, "Color"):
        c = load(acg(aid, "Color"))
        if "desaturate" in f["asset"]:                                   # quartz look: the stone's veins kept at a fraction of their colour
            k = float(f["asset"]["desaturate"]); L_ = c.mean(-1, keepdims=True); c = L_ + (c - L_) * k
        if "vein_contrast" in f["asset"]:
            k = float(f["asset"]["vein_contrast"]); m_ = c.reshape(-1, 3).mean(0); c = m_ + (c - m_) * k
        save(recolour(c, col), f"{fid}_col.jpg")
        if acg(aid, "NormalGL"): Image.open(acg(aid, "NormalGL")).convert("RGB").resize((a.px, a.px)).save(os.path.join(a.out, f"{fid}_nrm.jpg"), quality=90)
        tile = float(f["asset"].get("tile_m", 2.0))
        entry.update(tile_m=[tile, tile], files=dict(col=f"{fid}_col.jpg", nrm=f"{fid}_nrm.jpg" if acg(aid, "NormalGL") else None, rough=None),
                     source=f"ambientCG {aid} (CC0), recoloured to {col}" + (f", veins at {f['asset'].get('desaturate')} saturation" if "desaturate" in f["asset"] else ""))
        meta[fid] = entry; continue
    if src == "polyhaven" and aid and aid not in ASSET_MISMATCH and os.path.isdir(os.path.join(a.ph, aid)):
        d = os.path.join(a.ph, aid)
        fn = {k: next((os.path.join(d, x) for x in os.listdir(d) if k in x), None) for k in ("diff", "nor_gl", "rough")}
        dims = (FETCHED.get(aid, {}).get("dimensions_mm") or [1000, 1000])
        tile = [dims[0] / 1000.0, dims[1] / 1000.0]
        m_tile = re.search(r"at ([\d.]+) m tile", notes)
        m_as = re.match(r"as (FIN-[A-Z-]+)", notes)                    # "as FIN-WALL, tinted": the same scale as that finish
        if m_as and not m_tile:
            m_tile = re.search(r"at ([\d.]+) m tile", next((g.get("notes", "") for g in S["finishes"] if g["id"] == m_as.group(1)), ""))
        if m_tile: tile = [float(m_tile.group(1))] * 2
        m_board = re.search(r"boards (\d+) x (\d+) mm", notes)
        BOARD_MM = {"plank_flooring_02": 1980 / 14, "oak_wood_planks": 1200 / 13}      # each set's own board width (boards counted on its diffuse)
        if m_board and aid in BOARD_MM:
            tile = [tile[0] * (int(m_board.group(1)) / BOARD_MM[aid])] * 2
        rot = bool(f["asset"].get("rotate_90"))                              # boards along the image's v (floor UV v = plan -z: front to back)
        keep = 0.8 if fid.startswith(("FIN-WALL", "FIN-CEIL")) else 1.0      # paint: the plaster's relief, a quieter tone
        R90 = (lambda arr: np.rot90(arr).copy()) if rot else (lambda arr: arr)
        save(R90(recolour(load(fn["diff"]), col, keep)), f"{fid}_col.jpg")
        if fn["nor_gl"]:
            nm_ = load(fn["nor_gl"])
            if rot:                                                           # rotating a normal map turns its x/y vectors too
                nm_ = np.rot90(nm_).copy(); x_, y_ = nm_[..., 0].copy(), nm_[..., 1].copy(); nm_[..., 0] = 1 - y_; nm_[..., 1] = x_
            save(nm_, f"{fid}_nrm.jpg")
        if fn["rough"]:
            r = load(fn["rough"], "L"); r = np.clip(r - r.mean() + rough, 0.02, 1.0)
            save(R90(np.stack([r] * 3, -1)), f"{fid}_rough.jpg")
        entry.update(tile_m=tile, files=dict(col=f"{fid}_col.jpg", nrm=f"{fid}_nrm.jpg" if fn["nor_gl"] else None,
                                             rough=f"{fid}_rough.jpg" if fn["rough"] else None), source=f"Poly Haven {aid} (CC0), recoloured to {col}")
    elif (src == "parametric" and f["asset"].get("kind") in ("tile_wall", "tile_floor")) or aid == "grey_cartago_02":
        m = re.search(r"(\d+) x (\d+)(?: mm)?", notes + " " + f["name"])
        jm = re.search(r"(\d+) mm joints?", notes)
        gm = re.search(r"grout (#[0-9A-Fa-f]{6})", notes)
        tw, th = (int(m.group(1)) / 1000.0, int(m.group(2)) / 1000.0) if m else (0.3, 0.6)
        if "horizontal" in notes and th > tw: tw, th = th, tw
        joint = (int(jm.group(1)) if jm else 2) / 1000.0
        grout = gm.group(1) if gm else "#D9D3C8"
        bond = "brick" if "brick" in notes or fid == "TILE-METRO-WHITE" else "stack"
        if bond == "brick" and th > tw: tw, th = th, tw                 # brick-bond (metro) tiles are laid long side horizontal
        size = max(tw, th) * 2 if max(tw, th) >= 0.3 else 0.6
        var = None
        pl = os.path.join(a.ph, "white_plaster_02")
        vs_ = f["asset"].get("variation")                                     # e.g. "ambientcg Marble019": stone-look tile faces
        if vs_ and vs_.startswith("ambientcg ") and acg(vs_.split()[1], "Color"):
            v_ = load(acg(vs_.split()[1], "Color"), "L")
            v_ = np.asarray(Image.fromarray((v_ * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.0)), np.float64) / 255   # mottling, not speckle
            lo_, hi_ = np.percentile(v_, 2), np.percentile(v_, 98); var = np.clip((v_ - lo_) / (hi_ - lo_ + 1e-6), 0, 1) * 1.6 - 0.3
        elif os.path.isdir(pl):
            v_ = load(next(os.path.join(pl, x) for x in os.listdir(pl) if "diff" in x), "L"); var = (v_ - v_.min()) / (np.ptp(v_) + 1e-6)
        c, n, _ = tiles(size, tw, th, joint, col, grout, bond, var)
        save(c, f"{fid}_col.jpg"); save(n, f"{fid}_nrm.jpg")
        entry.update(tile_m=[size, size], files=dict(col=f"{fid}_col.jpg", nrm=f"{fid}_nrm.jpg", rough=None),
                     source=f"parametric tiles {int(tw * 1000)} x {int(th * 1000)} mm, {int(joint * 1000)} mm joints, grout {grout} ({bond} bond)"
                            + (f", faces from {vs_} (CC0)" if vs_ else ""))
        if aid in ASSET_MISMATCH: entry["asset_mismatch"] = ASSET_MISMATCH[aid]; notes_out.append(f"{fid}: {ASSET_MISMATCH[aid]}")
    else:
        if aid in ASSET_MISMATCH: entry["asset_mismatch"] = ASSET_MISMATCH[aid]; notes_out.append(f"{fid}: {ASSET_MISMATCH[aid]}")
    meta[fid] = entry
json.dump(dict(spec=os.path.basename(a.spec), finishes=meta, asset_mismatch=notes_out), open(os.path.join(a.out, "spec_tex_meta.json"), "w"), indent=1)
for k, v in meta.items(): print(f"{k:18s} {v['source'][:90]}  tile {v['tile_m'][0]:.2f} m")
for n in notes_out: print("ASSET MISMATCH:", n)

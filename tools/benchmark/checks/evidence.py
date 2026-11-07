"""EVIDENCE checks: every built element cites a dated source; nothing is built from no source.

Check ids (per version):
  evidence.cited       every wall, opening, room, stair, slab and object has `source` and `source_date` (YYYY-MM-DD);
                       a source of "assumed", "estimate", "typical" etc. is not a source
  evidence.register    cited sources resolve to the plan's `sources[]` register (or a prepared source register) and
                       the cited date matches the register's capture date
  evidence.assumed     elements marked `assumed: true` are listed (WARN: each must be named as an assumption)
  evidence.superseded  a Before element cites only captures older than the latest capture of the same `area`
                       (WARN: check the latest capture still shows it)
"""
import datetime, json, os
from plandata import Result, DATE_RE, all_elements

C = "evidence"
NOT_A_SOURCE = {"", "assumed", "assumption", "estimate", "estimated", "guess", "guessed", "invented", "typical",
                "default", "none", "n/a", "na", "unknown", "tbc", "todo", "eyeballed", "by eye", "placeholder"}


def _as_list(x):
    if x is None: return []
    return list(x) if isinstance(x, (list, tuple)) else [x]


def load_register(path):
    """Read a prepared source-register.json (tools/benchmark/prepare_sources.py) into {key: date}."""
    with open(path) as f:
        reg = json.load(f)
    out = {}
    for e in reg.get("files", []):
        d = (e.get("capture_date") or "")[:10] or None
        for k in (e.get("id"), e.get("name"), os.path.basename(e.get("path", "") or "")):
            if k: out[k] = d
        for fr in e.get("frames", []) or []:
            for k in (fr.get("id"), fr.get("file"), os.path.basename(fr.get("file", "") or "")):
                if k: out[k] = d
    return out


def run(v, extra_register=None, today=None):
    data = v.data or {}
    reg = {}
    for s in data.get("sources", []) or []:
        for k in (s.get("id"), s.get("file"), os.path.basename(str(s.get("file", "")))):
            if k: reg[k] = s.get("date")
    if extra_register:
        for k, d in extra_register.items():
            reg.setdefault(k, d)
    today = today or datetime.date.today().isoformat()
    res = []
    missing, bad_date, not_src, unresolved, mismatch, assumed = [], [], [], [], [], []
    count = 0
    for key, e in all_elements(v):
        count += 1
        eid = e["id"]
        srcs = [str(s).strip() for s in _as_list(e.get("source"))]
        dates = [str(d).strip() for d in _as_list(e.get("source_date"))]
        if e.get("assumed"):
            assumed.append(eid)
        if not srcs or all(not s for s in srcs):
            missing.append("%s (%s)" % (eid, key)); continue
        if any(s.lower() in NOT_A_SOURCE for s in srcs):
            not_src.append("%s cites %r" % (eid, srcs)); continue
        if not dates or any(not DATE_RE.match(d) for d in dates) or (len(dates) not in (1, len(srcs))):
            bad_date.append("%s (%r)" % (eid, e.get("source_date"))); continue
        try:
            for d in dates:
                datetime.date.fromisoformat(d)
        except ValueError:
            bad_date.append("%s (%r)" % (eid, e.get("source_date"))); continue
        if any(d > today for d in dates):
            bad_date.append("%s dated in the future (%r)" % (eid, dates)); continue
        if reg:
            for i, s in enumerate(srcs):
                if s not in reg:
                    unresolved.append("%s -> %s" % (eid, s)); continue
                rd = reg[s]; d = dates[i] if len(dates) == len(srcs) else dates[0]
                if rd and d != rd[:10]:
                    mismatch.append("%s cites %s dated %s, register says %s" % (eid, s, d, rd[:10]))
    if missing:
        res.append(Result(C + ".cited", "FAIL", "-", "%d element(s) cite no source: %s" % (len(missing), ", ".join(missing[:20])), v.name))
    if not_src:
        res.append(Result(C + ".cited", "FAIL", "-", "%d element(s) cite a non-source: %s" % (len(not_src), "; ".join(not_src[:12])), v.name))
    if bad_date:
        res.append(Result(C + ".cited", "FAIL", "-", "%d element(s) without a valid source_date: %s" % (len(bad_date), ", ".join(bad_date[:20])), v.name))
    if not (missing or not_src or bad_date):
        res.append(Result(C + ".cited", "PASS", "-", "all %d elements cite a dated source" % count, v.name))
    if reg:
        if unresolved or mismatch:
            res.append(Result(C + ".register", "FAIL", "-", "; ".join((["unknown source: " + ", ".join(unresolved[:15])] if unresolved else []) +
                                                                 (["date mismatch: " + "; ".join(mismatch[:10])] if mismatch else [])), v.name))
        else:
            res.append(Result(C + ".register", "PASS", "-", "every citation resolves to the source register with its date", v.name))
    else:
        res.append(Result(C + ".register", "WARN", "-", "no sources[] register in the plan data: citations not cross-checked", v.name))
    if assumed:
        res.append(Result(C + ".assumed", "WARN", "-", "%d element(s) marked assumed (name each as an assumption when presenting): %s" % (len(assumed), ", ".join(assumed[:20])), v.name))
    # superseded captures, only where areas are tagged
    areas = {}
    for s in data.get("sources", []) or []:
        for a in _as_list(s.get("areas")):
            if s.get("date") and (a not in areas or s["date"] > areas[a][0]):
                areas[a] = (s["date"], s.get("id"))
    if areas and v.name.lower() in ("before", "today", "existing"):
        old = []
        for key, e in all_elements(v):
            a = e.get("area"); dates = [str(d) for d in _as_list(e.get("source_date"))]
            if a in areas and dates and max(dates) < areas[a][0]:
                old.append("%s (%s, latest capture of %s is %s %s)" % (e["id"], max(dates), a, areas[a][1], areas[a][0]))
        if old:
            res.append(Result(C + ".superseded", "WARN", "-", "%d element(s) rest on captures older than the latest of their area: %s" % (len(old), "; ".join(old[:10])), v.name))
    return res

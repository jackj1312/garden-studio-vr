"""Every finding becomes a lesson before it is fixed, and the lessons are what every reviewer reads first.

Jack, 1 Nov 2026: "every mark i make needs to be added to the list of things to check before showing me because they
probably have a root cause that can be avoided in the future ... and those fixes or fixes for anything need to go into
a document the reviewer reads constantly so all fixes get made on a first pass" and "even include the fixes it's made
on this round so we learn what we have done wrong in the past".

A finding is anything that had to be fixed: one of Jack's headset marks (a correction mark in marks.json), or a fault
the build, a check, the audit or a judge found and fixed itself in a round. Each one gets:
  - a row in CORRECTIONS-LOG.md (what went wrong, who caught it, root cause, rule now, gate), written BEFORE the fix;
  - a line in DETAIL-CHECKLIST.md (the check that catches it next time, "(row N)"), unless a tool check covers it;
  - evidence that it is fixed, from the same view it was found in.
FIRST-PASS.md is regenerated from all of that: what is open on each site, the lessons of the latest rounds, and every
rule we have learned, grouped by gate. Builders, fixers, auditors and judges read it at the start of every round and
again before every fix.

Findings live in assets/sites/<site>/review/findings.json (one list per site; the studio software keeps it per client).

    python3 tools/review/lessons.py intake  --site house-wip            # Jack's new correction marks -> findings + log rows
    python3 tools/review/lessons.py add     --site house-wip --round shell-1 --source self --caught-by "Shell walk" \
            --what "..." --root-cause "..." --rule "..." --gate G5b [--check "checklist line" | --tool tools/house/check_shell.py] \
            [--fixed --evidence renders/...png]
    python3 tools/review/lessons.py resolve --site house-wip --id F12 --root-cause ... --rule ... --gate G5b --check "..." | --tool ...
    python3 tools/review/lessons.py fixed   --site house-wip --id F12 --evidence renders/.../after.png
    python3 tools/review/lessons.py brief                                # rewrite FIRST-PASS.md
    python3 tools/review/lessons.py gate    --site house-wip            # exit 1 unless every finding is logged, ruled, checked and fixed
"""
import argparse, json, os, re, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "CORRECTIONS-LOG.md")
CHECKLIST = os.path.join(ROOT, "DETAIL-CHECKLIST.md")
BRIEF = os.path.join(ROOT, "FIRST-PASS.md")
SITES = os.path.join(ROOT, "assets", "sites")
CHECK_HEAD = "## Learned from review findings (tools/review/lessons.py; check on every project)"
TODO = "TO FIND"
ROW_RE = re.compile(r"^\| (\d+) \|")
# the marking tool's preset reasons (src/notes.js PRESETS) and the gate each one points at
PRESETS = {"Visual bug": "G7", "Missing item": "G5c", "Hole in wall": "G5b", "Missing texture": "G5c", "Clipping": "G5c",
           "Wrong way round": "G2b", "Don't like item": "G2b"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cell(t):
    return " ".join(str(t or "").replace("|", "/").split())


def findings_path(site):
    return os.path.join(SITES, site, "review", "findings.json")


def load(site):
    p = findings_path(site)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"site": site, "findings": []}


def save(site, data):
    p = findings_path(site)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, p)


def log_lines():
    with open(LOG, encoding="utf-8") as f:
        return f.read().split("\n")


def log_rows():
    """{row number: [cells]} for every table row in CORRECTIONS-LOG.md."""
    out = {}
    for ln in log_lines():
        m = ROW_RE.match(ln)
        if m:
            out[int(m.group(1))] = [c.strip() for c in ln.strip().strip("|").split("|")]
    return out


def row_text(n, f):
    return (f"| {n} | {cell(f['what'])} | {cell(f['caught_by'])} | {cell(f.get('root_cause') or TODO)} | "
            f"{cell(f.get('rule') or TODO)} | {cell(f.get('gate') or TODO)} |")


def write_row(f):
    """Add the finding's row to the log (new number after the last row) or rewrite its existing row."""
    lines = log_lines()
    idx = [i for i, ln in enumerate(lines) if ROW_RE.match(ln)]
    if f.get("row"):
        for i in idx:
            if int(ROW_RE.match(lines[i]).group(1)) == f["row"]:
                lines[i] = row_text(f["row"], f)
                break
        else:
            sys.exit(f"row {f['row']} not found in CORRECTIONS-LOG.md")
    else:
        f["row"] = max(int(ROW_RE.match(lines[i]).group(1)) for i in idx) + 1
        lines.insert(idx[-1] + 1, row_text(f["row"], f))
    with open(LOG, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def add_check(f):
    """The finding's checklist line goes under one heading in DETAIL-CHECKLIST.md, tagged with its row."""
    if not f.get("check"):
        return
    with open(CHECKLIST, encoding="utf-8") as fh:
        s = fh.read()
    tag = f"(row {f['row']})"
    if tag in s:
        return
    line = f"- {cell(f['check'])} {tag}"
    if CHECK_HEAD not in s:
        s = s.rstrip("\n") + f"\n\n{CHECK_HEAD}\n"
    s = s.rstrip("\n") + "\n" + line + "\n"
    with open(CHECKLIST, "w", encoding="utf-8") as fh:
        fh.write(s)


def next_id(data):
    return "F%d" % (max([int(x["id"][1:]) for x in data["findings"]] or [0]) + 1)


def where(stroke):
    bits = [stroke.get(k) for k in ("version", "view", "stage") if stroke.get(k) not in (None, "")]
    tags = [k for k in stroke if k.endswith("_tags") or k == "parts"]
    for k in tags:
        v = stroke[k]
        if isinstance(v, list) and v:
            bits.append("on " + ", ".join(str(x) for x in v[:3]))
    if stroke.get("surface"):
        bits.append(f"surface {stroke['surface']}")
    return "; ".join(str(b) for b in bits)


# ---------------------------------------------------------------- commands

def cmd_intake(a):
    data = load(a.site)
    p = os.path.join(SITES, a.site, "marks.json")
    if not os.path.isfile(p):
        print(f"{a.site}: no marks.json yet"); return
    with open(p, encoding="utf-8") as fh:
        strokes = json.load(fh).get("strokes", [])
    have = {x.get("mark") for x in data["findings"]}
    new = 0
    for s in strokes:
        if s.get("kind") != "correction" or s["id"] in have:
            continue                                  # proposals are design changes: they go to the spec change list
        note = s.get("note") or ("(voice note transcribing)" if s.get("note_status") else "(no note)")
        preset = s.get("preset") or next((q for q in PRESETS if note.startswith(q)), None)
        tag = f" [{preset}]" if preset else ""
        if preset == "Don't like item": tag += " (design change: goes to the spec, not a fault)"
        f = {"id": next_id(data), "source": "mark", "mark": s["id"], "round": a.round or "headset review", "preset": preset,
             "what": f"Jack's mark{tag}: {note} [{where(s)}]", "caught_by": f"Jack, headset ({(s.get('created') or '')[:10]})",
             "root_cause": None, "rule": None, "gate": PRESETS.get(preset), "check": None, "tool": None,
             "status": "open", "evidence": None, "created": now()}
        write_row(f)
        data["findings"].append(f); new += 1
        print(f"{f['id']}  row {f['row']}  {note[:80]}")
    save(a.site, data)
    print(f"{a.site}: {new} new mark(s) taken in; {len(strokes)} stroke(s) in marks.json")
    brief()


def fill(f, a):
    for k in ("root_cause", "rule", "gate", "check", "tool"):
        v = getattr(a, k, None)
        if v:
            f[k] = v
    if f.get("root_cause") and f.get("rule") and f.get("gate") and (f.get("check") or f.get("tool")):
        if f["status"] == "open":
            f["status"] = "ruled"


def cmd_add(a):
    data = load(a.site)
    f = {"id": next_id(data), "source": a.source, "mark": None, "round": a.round, "what": a.what,
         "caught_by": a.caught_by, "root_cause": None, "rule": None, "gate": None, "check": None, "tool": None,
         "status": "open", "evidence": None, "created": now()}
    fill(f, a)
    write_row(f); add_check(f)
    if a.fixed:
        mark_fixed(f, a.evidence)
    data["findings"].append(f)
    save(a.site, data)
    print(f"{f['id']}  row {f['row']}  {f['status']}")
    brief()


def find(data, fid):
    for f in data["findings"]:
        if f["id"] == fid:
            return f
    sys.exit(f"no finding {fid}")


def cmd_resolve(a):
    data = load(a.site); f = find(data, a.id)
    fill(f, a); write_row(f); add_check(f)
    save(a.site, data)
    print(f"{f['id']}  row {f['row']}  {f['status']}")
    brief()


def mark_fixed(f, evidence):
    if f["status"] == "open":
        sys.exit(f"{f['id']}: give the root cause, rule, gate and a check before calling it fixed (the lesson comes first)")
    if not evidence or not os.path.exists(os.path.join(ROOT, evidence)):
        sys.exit(f"{f['id']}: --evidence must be an existing file (the same view, after the fix)")
    f["status"], f["evidence"], f["fixed"] = "fixed", evidence, now()


def cmd_fixed(a):
    data = load(a.site); f = find(data, a.id)
    mark_fixed(f, a.evidence)
    save(a.site, data)
    print(f"{f['id']}  fixed")
    brief()


def all_sites():
    return sorted(d for d in os.listdir(SITES) if os.path.isfile(findings_path(d)))


def brief():
    rows = log_rows()
    out = ["# FIRST PASS: read this before every round and before every fix",
           "",
           "Jack, 1 Nov 2026: every mark he makes, and every fix we make ourselves, becomes a lesson so that \"all fixes get",
           "made on a first pass\". This file is generated by `python3 tools/review/lessons.py brief` from CORRECTIONS-LOG.md,",
           "DETAIL-CHECKLIST.md and each site's review/findings.json. Do not edit it by hand.",
           "",
           "**Who reads it:** every builder, fixer, auditor and judge, at the start of every round, again before each fix, and",
           "before anything is shown to Jack. **How to use it:** build so that none of the rules below is broken; when a new",
           "fault turns up, log it with `lessons.py add` (or `intake` for Jack's marks) with its root cause and rule BEFORE",
           "fixing it, then fix it and record the evidence with `lessons.py fixed`. `lessons.py gate --site <site>` must pass",
           "before Jack sees the build.",
           ""]
    out.append("## Open on each site")
    any_open = False
    for site in all_sites():
        fs = load(site)["findings"]
        op = [f for f in fs if f["status"] != "fixed"]
        if not op:
            continue
        any_open = True
        out.append(f"### {site}")
        for f in op:
            out.append(f"- **{f['id']} (row {f['row']}, {f['status']})** {cell(f['what'])}"
                       + (f" Rule: {cell(f['rule'])}" if f.get("rule") else " Root cause and rule still to find."))
    if not any_open:
        out.append("Nothing open.")
    out.append("")
    out.append("## Lessons from the latest rounds (newest first)")
    recent = []
    for site in all_sites():
        for f in load(site)["findings"]:
            recent.append((f.get("created") or "", site, f))
    recent.sort(key=lambda t: t[0], reverse=True)
    if not recent:
        out.append("None yet.")
    for _, site, f in recent[:60]:
        out.append(f"- {site} · {f.get('round') or ''} · row {f['row']}: {cell(f['what'])} → **{cell(f.get('rule') or TODO)}**"
                   + (f" (check: {cell(f['check'])})" if f.get("check") else "") + (f" (tool: {f['tool']})" if f.get("tool") else ""))
    out.append("")
    out.append("## Every rule we have learned, by gate (CORRECTIONS-LOG.md)")
    by_gate = {}
    for n, c in rows.items():
        if len(c) < 6 or c[4] in ("", TODO):
            continue
        gates = re.findall(r"G\d+[a-z]?", c[5]) or ["other"]
        by_gate.setdefault(gates[0], []).append((n, c))
    key = lambda g: (int(re.sub(r"\D", "", g) or 99), g)
    for g in sorted(by_gate, key=key):
        out.append(f"### {g}")
        for n, c in by_gate[g]:
            out.append(f"- ({n}) {c[4]}  _[{c[1]}]_")
        out.append("")
    out.append("## Then the detail checklist")
    out.append("DETAIL-CHECKLIST.md, line by line, at G3 and G6 (and G5b/G5c for a house). Every line came from a past mistake.")
    with open(BRIEF, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"FIRST-PASS.md: {len(rows)} log rows, {len(recent)} findings")


def cmd_gate(a):
    data = load(a.site)
    faults = []
    p = os.path.join(SITES, a.site, "marks.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            strokes = json.load(fh).get("strokes", [])
        have = {f.get("mark") for f in data["findings"]}
        for s in strokes:
            if s.get("kind") == "correction" and s["id"] not in have:
                faults.append(f"mark {s['id']} not taken in (run intake)")
    rows = log_rows()
    for f in data["findings"]:
        c = rows.get(f.get("row"))
        if not c:
            faults.append(f"{f['id']}: its log row {f.get('row')} is missing")
        elif TODO in (c[3], c[4], c[5]):
            faults.append(f"{f['id']} (row {f['row']}): root cause, rule or gate still to find")
        if not (f.get("check") or f.get("tool")):
            faults.append(f"{f['id']}: no checklist line or tool check, so it can happen again")
        if f["status"] != "fixed":
            faults.append(f"{f['id']}: not fixed with evidence")
    newest = max(os.path.getmtime(x) for x in (LOG, CHECKLIST, findings_path(a.site)) if os.path.exists(x))
    if not os.path.exists(BRIEF) or os.path.getmtime(BRIEF) < newest:
        faults.append("FIRST-PASS.md is older than the log or findings (run brief)")
    for x in faults:
        print("FAIL", x)
    print(f"{a.site}: {'PASS' if not faults else 'FAIL'} · {len(data['findings'])} finding(s), {len(faults)} fault(s)")
    sys.exit(1 if faults else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lesson = argparse.ArgumentParser(add_help=False)
    for k in ("root-cause", "rule", "gate", "check", "tool"):
        lesson.add_argument("--" + k)
    p = sub.add_parser("intake"); p.add_argument("--site", required=True); p.add_argument("--round")
    p = sub.add_parser("add", parents=[lesson]); p.add_argument("--site", required=True); p.add_argument("--round", required=True)
    p.add_argument("--source", default="self", choices=["self", "check", "audit", "judge", "jack"])
    p.add_argument("--caught-by", required=True); p.add_argument("--what", required=True)
    p.add_argument("--fixed", action="store_true"); p.add_argument("--evidence")
    p = sub.add_parser("resolve", parents=[lesson]); p.add_argument("--site", required=True); p.add_argument("--id", required=True)
    p = sub.add_parser("fixed"); p.add_argument("--site", required=True); p.add_argument("--id", required=True); p.add_argument("--evidence", required=True)
    sub.add_parser("brief")
    p = sub.add_parser("gate"); p.add_argument("--site", required=True)
    a = ap.parse_args()
    {"intake": cmd_intake, "add": cmd_add, "resolve": cmd_resolve, "fixed": cmd_fixed,
     "brief": lambda _: brief(), "gate": cmd_gate}[a.cmd](a)


if __name__ == "__main__":
    main()

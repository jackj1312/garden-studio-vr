#!/usr/bin/env python3
"""Run every shared plan-data check and print PASS / FAIL with details.

  python3 run_checks.py plan-data.json [--gate 1A|1B] [--version before|after]
                        [--overlays residuals.json ...] [--register inputs/prepared/source-register.json]
                        [--json report.json] [--tol 0.03] [--landing 0.6] [--quiet]

Exit code 0 = no FAIL, 1 = at least one FAIL, 2 = the file could not be read or is not valid plan data.
Pure Python 3 (no numpy, no Blender). Schema: docs/benchmark/PLAN-DATA-SCHEMA.md (published as PLAN-DATA-SCHEMA.md)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plandata, closure, circulation, evidence, overlays  # noqa: E402


def run_all(data, gate="1B", only=None, overlay_files=(), register=None, tol=0.03, landing=0.6, today=None):
    results = []
    errs = plandata.validate(data)
    if errs:
        for e in errs:
            results.append(plandata.Result("schema", "FAIL", "-", e))
        return results
    results.append(plandata.Result("schema", "PASS", "-", "valid plan data (%s)" % ", ".join(data["versions"])))
    reg = evidence.load_register(register) if register else None
    for v in plandata.versions(data, only):
        results += closure.run(v, tol=tol, gate=gate)
        results += circulation.run(v, landing_depth=landing, tol=tol, gate=gate)
        results += evidence.run(v, extra_register=reg, today=today)
    if gate == "1B" and not overlay_files:
        results.append(plandata.Result("overlay.coverage", "FAIL", "-", "GATE 1B needs overlay residuals (--overlays) for the drawings and the solved photos/frames"))
    for f in overlay_files:
        results += overlays.run(overlays.load(f), label=os.path.basename(f))
    return results


def summary(results):
    groups = {}
    for r in results:
        g = r.check.split(".")[0]
        s = groups.setdefault(g, {"PASS": 0, "WARN": 0, "FAIL": 0})
        s[r.status] = s.get(r.status, 0) + 1
    return groups


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan"); ap.add_argument("--gate", choices=["1A", "1B"], default="1B")
    ap.add_argument("--version"); ap.add_argument("--overlays", nargs="*", default=[])
    ap.add_argument("--register"); ap.add_argument("--json"); ap.add_argument("--tol", type=float, default=0.03)
    ap.add_argument("--landing", type=float, default=0.6); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    try:
        data = plandata.load(a.plan)
    except Exception as e:
        print("ERROR: cannot read %s: %s" % (a.plan, e)); return 2
    results = run_all(data, a.gate, a.version, a.overlays, a.register, a.tol, a.landing)
    if any(r.check == "schema" and r.status == "FAIL" for r in results):
        for r in results: print("FAIL schema:", r.detail)
        return 2
    for r in results:
        if a.quiet and r.status == "PASS":
            continue
        print("%-4s %-28s %-7s %-34s %s" % (r.status, r.check, r.version or "", r.subject, r.detail))
    groups = summary(results)
    print()
    for g, s in groups.items():
        print("%-12s %s  (%d pass, %d warn, %d fail)" % (g.upper(), "FAIL" if s["FAIL"] else "PASS", s["PASS"], s["WARN"], s["FAIL"]))
    overall = "FAIL" if any(s["FAIL"] for s in groups.values()) else "PASS"
    print("OVERALL %s (gate %s)" % (overall, a.gate))
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"plan": os.path.abspath(a.plan), "gate": a.gate, "overall": overall, "groups": groups,
                       "results": [r.as_dict() for r in results]}, f, indent=1)
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

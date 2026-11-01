#!/usr/bin/env python3
"""Regulations for the house viewer: the research dataset -> assets/sites/<site>/regs.json + regs_map.json.

    python3 tools/house/build_regs.py <site> <REGS-DATASET.json> [<REGS-REPORT.md>]

regs.json      every rule of the dataset, unchanged except an added `inspection_ids` (["IP-FOUND", …]); the dataset's meta;
               the product liability wording (REGS-REPORT.md §5, verbatim); and the inspection points, each with the
               DATASET stages its own rules are tagged with (no hand-typed stage list — CORRECTIONS-LOG 123).
regs_map.json  which rules attach to which parts, hand-curated below (MAP) and reviewable as data
               (CORRECTIONS-LOG 120: test what each part IS, not its group label). Entries:
                 { id, when, rules: [ids], why, prompt? }
               `when` keys (all must hold; a list is any-of; a key starting "not_" negates):
                 type, group, category, storey, material (the part's material name),
                 element / label (regex on the element id / the part's spec label),
                 room (regex on the name of the room the picked point is in),
                 near_boundary (true/false: the part within 1.0 m of a boundary line, measured in the viewer),
                 low_glazing (true: a glazed opening whose sill is < 800 mm above its floor).
               `prompt` is shown above the rules: what to check on THIS part.
               "not_applicable" lists rules that do not apply to this house, with the reason; "unmapped" lists rules no
               entry uses (should be empty, or explained).
Nothing here decides compliance: it only says which rules to look at on which part."""
import collections, json, os, re, sys

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
WALL_LEAVES = ["wall_outer", "wall_inner"]
NEW = ["new", "finish"]
EXT_WALL = r"^(G|F)-ext|^F-ashlar|^G-kitR~infill|^F-rear~infill"
INTERNAL_NEW = r"^G-utilKit|^G-cloakPart|^G-utilCloak|^F-ens|^F-rearC|^G-hallKit~infill"
PROC_ALTER = ["PROC-R3-2"]

# names that say what the inspector actually looks at (the dataset's are the authority's terms; IP-COMPLEX's rules are
# ties, closers, barriers and flue clearances on walls going up, not "complex structure")
POINT_NAMES = {
    "IP-PLANS": "Plans check (before that work starts)",
    "IP-START": "Notice before starting (2 days)",
    "IP-COMMENCE": "Commencement: foundations and ground-floor structure done",
    "IP-FOUND": "Foundation excavations, before concrete",
    "IP-DRAIN": "Drains, before covering (with test)",
    "IP-DPC": "Damp-proof course and membrane, before covering",
    "IP-REINF": "Slab reinforcement, before concrete (on request)",
    "IP-STRUCT": "Structural members: lintels, steels, joists, rafters (on request)",
    "IP-INSUL": "Insulation, before covering (on request)",
    "IP-COMPLEX": "Walls going up: cavities, ties, closers, barriers, flue clearances (on request)",
    "IP-COMPLETE": "Completion: final inspection and certificate",
}

MAP = [
    # ---- substructure
    dict(id="foundations_new", when={"group": "foundation", "category": NEW},
         rules=["A-S1-A1", "A-S1-A2", "A-2E4-depth", "A-2E2c-thick", "A-2E2d-steps", "A-2E2a-central", "A-2E3-width",
                "A-2E1-ground", "C-S1-C1", "H-2.25", "H-S1-H4", "PROC-ESBCP-3", "PROC-R46A-1"],
         why="new trench-fill foundations"),
    dict(id="foundations_existing", when={"group": "foundation", "category": "existing"}, rules=["PROC-R4-3", "A-S1-A1"],
         why="existing foundations: not new work",
         prompt="Existing foundation: the drawings say 'to be exposed & inspected'. Its size here is assumed until then."),
    dict(id="slab_build_up", when={"group": "slab_layer", "category": NEW, "material": ["concrete", "hardcore", "rebar", "screed"]},
         rules=["C-4.7", "C-2.39", "PROC-R46A-1", "B-5.3"], why="ground-bearing slab"),
    dict(id="slab_dpm", when={"group": "slab_layer", "category": NEW, "material": ["dpm", "vcl"]}, rules=["C-4.8", "C-4.7c"],
         why="damp-proof membrane",
         prompt="The DPM must lap and bond to the wall DPC: the DPC is laid with the substructure walls, before the slab."),
    dict(id="slab_insulation", when={"group": "slab_layer", "category": NEW, "material": ["pir", "mineral_wool"]},
         rules=["L-T4.2-floor"], why="floor insulation"),
    dict(id="slab_existing", when={"group": "slab_layer", "category": "existing"}, rules=["PROC-R4-3"],
         why="existing floor: not new work", prompt="Existing floor: the drawings say 'not known, assumed solid'."),
    # ---- walls
    dict(id="ext_walls_structure", when={"group": WALL_LEAVES, "category": NEW, "element": EXT_WALL},
         rules=["A-S1-A1", "A-2C8-cavity", "A-T5-ties", "A-2C23-span", "A-2C24c-load", "A-2E2a-central", "B-5.1-TB2", "B-5.2",
                "B-5.18", "B-5.20-21", "L-T4.2-wall", "PROC-R7-1"], why="new external cavity walls"),
    dict(id="ext_walls_dpc", when={"group": "wall_outer", "category": NEW, "element": EXT_WALL, "storey": "ground"},
         rules=["C-5.5b", "C-5.5c", "C-4.7c"], why="the DPC is in the ground-storey leaves",
         prompt="DPC at least 150 mm above the ground outside; check the low spots (side passage by the utility door)."),
    dict(id="ext_walls_insulation", when={"group": "wall_insulation", "category": NEW}, rules=["C-5.13", "C-5.15", "L-T4.2-wall"],
         why="partial-fill cavity insulation"),
    dict(id="cavity_below_dpc", when={"group": "wall_cavity", "category": NEW}, rules=["C-5.5c"], why="cavity fill below the DPC"),
    dict(id="boundary_walls", when={"group": "wall_outer", "category": NEW, "near_boundary": True}, rules=["B-11.8"],
         why="a new wall within 1 m of a boundary",
         prompt="Within 1 m of the boundary: this wall needs fire resistance from both sides, and only small openings."),
    dict(id="internal_new_walls", when={"group": ["wall_inner", "wall_lining"], "category": NEW, "element": INTERNAL_NEW},
         rules=["E-S1-E2", "E-T0.2"], why="new internal walls to bedrooms / WCs"),
    dict(id="internal_block", when={"group": "wall_inner", "category": NEW, "element": INTERNAL_NEW, "material": "block"},
         rules=["E-5.19-20"], why="blockwork partition"),
    dict(id="internal_stud", when={"group": ["wall_inner", "wall_lining"], "category": NEW, "element": INTERNAL_NEW,
                                   "material": ["timber", "existing_partition", "plasterboard", "mineral_wool"]},
         rules=["E-5.18"], why="stud partition"),
    dict(id="party_wall", when={"element": "party"}, rules=["B-5.5", "B-9.24", "E-S1-E2"],
         why="the semi-detached party wall with No.21 (condition holds: the house is semi-detached)",
         prompt="Party wall: a compartment wall. Any new pipe, cable or joist into it must be fire-stopped."),
    dict(id="existing_walls_altered", when={"group": WALL_LEAVES, "category": "existing", "element": r"^(G|F)-rear|^G-kitR|^F-wingR"},
         rules=["L-10.7e-T4.3", "PROC-R4-3"], why="existing walls the extension encloses or alters"),
    dict(id="removed_walls", when={"category": "demolition", "group": WALL_LEAVES}, rules=PROC_ALTER + ["A-S1-A1"],
         why="walls taken out: a material alteration if load-bearing",
         prompt="Coming out: if it carries anything (see Build: Carries), this needs the engineer's design first."),
    # ---- openings and support
    dict(id="lintels", when={"group": "lintel", "label": r"lintel", "not_label": r"padstone|dry pack|shim"},
         rules=["A-2C24-lintel", "A-S1-A1", "B-5.18", "C-5.5c", "PROC-ESBCP-3"], why="lintels over openings"),
    dict(id="padstones", when={"label": r"padstone", "not_label": r"dry pack|shim", "not_group": ["steel", "timber_beam"]}, rules=["A-S1-A1", "B-5.2", "PROC-ESBCP-3"],
         why="padstones under the steels",
         prompt="Padstone: size, bearing length and the masonry under it come from the engineer's calcs (A1). Check them on site; "
                "the lintel bearing rule does not apply to a padstone."),
    dict(id="dry_packs", when={"label": r"dry pack|shim", "not_group": ["steel", "timber_beam"]}, rules=["A-S1-A1", "PROC-R7-1"],
         why="dry pack / shims between padstone and steel (typical, not drawn)",
         prompt="Dry pack: fully packed, no voids, hard non-shrink mortar or steel shims; typical, not from the drawings."),
    dict(id="steels", when={"group": "steel", "category": NEW},
         rules=["A-S1-A1", "B-5.1-TB2", "B-5.2", "PROC-ESBCP-3", "PROC-R3-2", "K-1.11"],
         why="new steel beams; they replace load-bearing leaves (a material alteration)",
         prompt="Check the padstones it bears on (Build tab: Bears on): size, bearing and dry pack against the calcs. "
                "Fire protection to the steel (R30) unless the engineer says otherwise."),
    dict(id="timber_beams_new", when={"group": "timber_beam", "category": NEW}, rules=["A-S1-A1", "B-5.1-TB2", "PROC-ESBCP-3"],
         why="new timber / flitch beams"),
    dict(id="joists", when={"group": ["joist", "deck"], "category": NEW}, rules=["A-2C23-span", "B-5.1-TB2", "E-5.23", "A-S1-A1"],
         why="the new first floor"),
    # ---- roof
    dict(id="roof_structure", when={"group": ["rafter", "hip", "valley", "ridge", "wall_plate", "ceiling_joist"], "category": NEW},
         rules=["A-S1-A1", "B-5.3", "L-T4.2-roof"], why="the new roof structure (roof-only structure: B-5.3)"),
    dict(id="roof_insulation", when={"group": "roof_layer", "category": NEW, "material": ["pir", "mineral_wool"]},
         rules=["L-T4.2-roof", "C-6.14"], why="roof insulation"),
    dict(id="roof_membranes", when={"group": "roof_layer", "category": NEW, "not_material": ["pir", "mineral_wool"]},
         rules=["C-6.10"], why="roof membranes, battens and ventilation",
         prompt="The drawings call for eaves ventilation (10,000 mm²/m): the dataset has the condensation rule (C-6.10) "
                "but no separate eaves-vent or abutment-flashing rule yet."),
    dict(id="roof_cover", when={"group": "roof_cover", "category": NEW}, rules=[],
         why="roof covering",
         prompt="Roof covering: external fire spread (AD B, B4) and abutment trays and flashings are not in the regulations "
                "dataset yet. Check them against the drawings' notes."),
    dict(id="ashlar", when={"element": r"ashlar"}, rules=["L-T4.2-wall"], why="ashlar walls in the roof"),
    # ---- windows, doors, rooflights
    dict(id="new_windows", when={"group": "window", "category": NEW},
         rules=["L-T4.2-window", "L-10.3", "L-10.4", "L-10.7d", "F-T1.4", "F-1.52", "F-T1.7", "F-1.16"],
         why="new windows: energy, purge and background ventilation"),
    dict(id="windows_far", when={"group": ["window", "door"], "category": NEW, "near_boundary": False}, rules=["B-D11.7"],
         why="openings 1 m or more from the boundary: unprotected-area limits"),
    dict(id="openings_near_boundary", when={"group": ["window", "door"], "category": NEW, "near_boundary": True},
         rules=["B-11.8", "B-D11.5"], why="openings within 1 m of a boundary"),
    dict(id="escape_window", when={"element": r"-EE$"}, rules=["B-2.10a", "B-2.10cd", "B-2.10b", "B-2.2", "B-2.3", "B-S1-B1"],
         why="the bedroom 3 escape (EE) window",
         prompt="Escape window: clear opening ≥ 0.33 m² and ≥ 450 x 450 mm; bottom of the opening ≤ 1100 mm above the floor "
                "(see the live check)."),
    dict(id="upper_low_windows", when={"group": "window", "category": NEW, "storey": "first", "low_glazing": True},
         rules=["K-D3.1-window"], why="low first-floor windows: guarding"),
    dict(id="critical_glazing", when={"group": ["door", "window"], "category": NEW, "low_glazing": True},
         rules=["K-D5.1", "K-5.4", "K-5.7", "K-5.8"], why="glazing in critical locations (low or in doors)"),
    dict(id="new_external_doors", when={"group": "door", "category": NEW, "label": r"bi-fold|external"},
         rules=["L-T4.2-doors", "L-10.3", "L-10.4", "L-10.7d", "F-T1.4"], why="new external doors"),
    dict(id="new_internal_doors", when={"group": "door", "category": NEW, "not_label": r"bi-fold|external"}, rules=["F-1.25"],
         why="new internal doors: undercut for air"),
    dict(id="rooflights", when={"group": "rooflight", "category": NEW}, rules=["L-T4.2-window", "L-10.7d"], why="new rooflights"),
    dict(id="flue_rooflight", when={"element": r"^RL-porch"}, rules=["J-D34"],
         why="the boiler flue drawn beside this rooflight on section D-D",
         prompt="Section D-D draws the boiler flue terminal beside this rooflight (the flue is not modelled): check the "
                "terminal clearances."),
    dict(id="porch", when={"element": r"porch", "group": ["wall_outer", "door", "roof_cover", "rooflight"]}, rules=["L-0.14"],
         why="the front porch",
         prompt="Porch: at ground level and about 4 m² inside (model), far under 30 m². It stays exempt from the energy rules "
                "only while the door between house and porch is kept and the heating is not extended into it. Whether the "
                "whole porch is exempt building work (Schedule 2) is for building control to confirm."),
    # ---- stair (existing)
    dict(id="stair", when={"type": "stair"},
         rules=["K-T1.1", "K-T1.1-pitch", "K-2RG", "K-1.5", "K-1.11", "K-1.20", "K-1.24", "K-1.34", "K-D3.1", "K-1.39", "K-3.2c", "K-1.9",
                "B-2.5"],
         why="the stair",
         prompt="Existing stair: Part K applies where the work alters it or what is over it (headroom under new beams)."),
    # ---- drains
    dict(id="drains", when={"group": "drain", "category": NEW},
         rules=["H-2.24", "H-2.25", "H-2.33", "H-T6", "H-2.60", "H-3.14-15", "PROC-ESBCP-1"], why="new below-ground drains"),
    dict(id="soakaway", when={"label": r"soakaway"}, rules=["H-3.25", "H-3.27-28"], why="soakaway"),
    dict(id="svp", when={"label": r"soil vent|svp"}, rules=["H-1.31"], why="soil vent pipe"),
    # ---- temporary works
    dict(id="temporary", when={"category": "temporary"}, rules=[],
         why="temporary works",
         prompt="Temporary works are not Building Regulations: they fall under CDM 2015 and site safety. Props, needles and "
                "scaffold need a temporary works design by others; the ones shown are typical, not from the drawings."),
    # ---- rooms (shown when the picked point is in that room)
    dict(id="room_kitchen", when={"room": r"kitchen"}, rules=["F-1.17", "F-T1.1", "F-1.21", "F-1.55", "G-S1-G6", "G-S1-G1", "F-1.26", "F-3.17"],
         why="kitchen"),
    dict(id="room_wet", when={"room": r"en-suite|bath|wc|cloak|utility"},
         rules=["F-1.17", "F-T1.1", "F-1.20", "F-1.51", "F-3.25", "G-4.10", "G-4.11", "G-S1-G1", "H-T1", "H-T2-D3", "H-1.20", "P-2.5"],
         why="wet rooms"),
    dict(id="room_bedroom3", when={"room": r"bedroom 3"}, rules=["B-2.2", "F-1.26", "B-2.11", "E-S1-E2"], why="the new bedroom"),
    dict(id="room_circulation", when={"room": r"hall|landing"}, rules=["B-1.9", "B-1.8", "B-1.1", "B-1.2-1.4", "B-1.14"],
         why="smoke alarms in the hall and landing"),
    dict(id="room_habitable", when={"room": r"living|sitting|dining"}, rules=["B-2.1", "F-1.26", "L-6.58"], why="ground-floor rooms"),
]
PROJECT = ["PROC-R3-1", "PROC-R4-1", "PROC-R7-1", "REG7-AD7-1.2", "PROC-R16-1", "PROC-R16-2", "PROC-R16-3C", "PROC-BA32-NEW",
           "PROC-BA32-OLD", "PROC-SI993-5", "PROC-SI911-22", "PROC-2A-11C", "PROC-2A-11D", "PROC-2A-11F", "PROC-2A-11L",
           "PROC-2A-11O", "PROC-R16-4", "PROC-R17-1", "PROC-R20-1", "PROC-ESBCP-1", "PROC-ESBCP-2", "PROC-RBI-1",
           "PROC-TRANS-L21", "PROC-TRANS-FHS", "PROC-TRANS-B25", "L-10.9-10", "L-6.60", "L-10.8", "L-5.10", "L-5.20",
           "L-8.4", "P-1.7", "P-2.5", "F-4.1", "J-3.43", "J-S1-J5", "G-3.42", "D-1", "L-4.10", "B-1.8"]
NOT_APPLICABLE = {
    "B-5.6": "no garage at 23 Battle Road", "PROC-LEVY-1": "not triggered by a house extension",
    "M-0.2": "M4(1) does not apply to extensions", "O-0.3": "overheating: new dwellings only", "Q-0.2": "security: new dwellings only",
    "R-1.2": "gigabit ducts: new dwellings only", "S-scope": "EV charging: not triggered by this extension",
    "G-S1-G3-4": "new dwellings only", "G-S1-G2": "new dwellings only", "K-1.13": "loft conversions only",
    "P-1.4": "socket heights: new dwellings only",
}


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    site, src = sys.argv[1], sys.argv[2]
    report = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(src), "REGS-REPORT.md")
    data = json.load(open(src))
    meta, rules = data["meta"], data["rules"]
    by_id = {r["id"]: r for r in rules}
    for r in rules:
        r["inspection_ids"] = [(re.match(r"(IP-[A-Z]+)", ip) or [None, "NONE"])[1] if ip.startswith("IP-") else "NONE"
                               for ip in r.get("inspection_point") or []]

    # liability wording, verbatim from the report's §5 quote
    wording = None
    if os.path.isfile(report):
        m = re.search(r"^> (\*\*Guidance, not approval\.\*\*.+)$", open(report).read(), re.M)
        if m:
            wording = m.group(1).replace("**", "")
    meta = dict(meta)
    meta["product_liability"] = wording or meta.get("liability")
    meta["not_for_construction"] = ("Not for construction. This model is drawn from the planning and building-regulations "
                                    "drawings for explanation only: do not set out, order or build from it. Dimensions "
                                    "marked scaled or assumed are not on the drawings.")

    # inspection points: the stages their OWN rules are tagged with (dataset numbering, meta.stages)
    points = []
    for key, text in meta["inspection_points"].items():
        if not text.startswith("IP-"):
            continue
        pid = text.split(":")[0]
        tagged = [r for r in rules if pid in r["inspection_ids"]]
        # each rule votes for its stages, weighted down when it is tagged to many stages or many points (the generic
        # procedure rules), and stage 1 (the house before: desk checks) only counts for the plans check
        count = collections.Counter()
        for r in tagged:
            st = [s for s in r.get("stage") or [] if s != 1 or pid == "IP-PLANS"] or (r.get("stage") or [])
            for s in st:
                count[s] += 1.0 / (len(st) * max(1, len(set(r["inspection_ids"]))))
        top = max(count.values()) if count else 0
        stages = sorted(s for s, c in count.items() if c >= 0.5 * top)
        if pid == "IP-PLANS":
            stages = [1]          # a desk check before work on each element starts, not a site visit at a stage
        points.append({"id": pid, "name": POINT_NAMES.get(pid, text.split(":")[1].strip()), "description": text,
                       "dataset_stages": stages, "stage_weights": {k: round(v, 2) for k, v in sorted(count.items())}, "rules": len(tagged)})
    points.sort(key=lambda p: (p["dataset_stages"] or [99])[0])

    out_dir = os.path.join(ROOT, "assets", "sites", site)
    json.dump({"contract": 2, "source": os.path.basename(src), "meta": meta, "inspection_points": points, "rules": rules},
              open(os.path.join(out_dir, "regs.json"), "w"), indent=1, ensure_ascii=False)

    used = set(PROJECT) | set(NOT_APPLICABLE)
    for e in MAP:
        for rid in e["rules"]:
            if rid not in by_id:
                sys.exit(f"build_regs: MAP entry {e['id']} names unknown rule {rid}")
            used.add(rid)
    unmapped = [r["id"] for r in rules if r["id"] not in used]
    for e in MAP:            # the owner's loft conversion (LOFT-*) is not on the drawings: it never takes a regs mapping
        e.setdefault("when", {})["not_element"] = "^LOFT-|-owner$|^AB-X-porch|^AB-S-porch"   # owner / as-built items
    rmap = {"contract": 2, "note": __doc__.split("regs_map.json", 1)[1].split("Nothing here")[0].strip(),
            "entries": MAP, "project": PROJECT,
            "not_applicable": [{"id": k, "reason": v} for k, v in NOT_APPLICABLE.items()], "unmapped": unmapped}
    json.dump(rmap, open(os.path.join(out_dir, "regs_map.json"), "w"), indent=1, ensure_ascii=False)
    print(f"build_regs: {len(rules)} rules, {len(MAP)} map entries, project {len(PROJECT)}, n/a {len(NOT_APPLICABLE)}, "
          f"unmapped {unmapped}; liability from {'report' if wording else 'dataset meta'}")
    for p in points:
        print(f"  {p['id']:12} dataset stages {p['dataset_stages']}  ({p['rules']} rules)")


if __name__ == "__main__":
    main()

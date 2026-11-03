"""A sweep plan: the standing points of one space of one version (PLAN S8).

    python3 tools/review/sweep_plan.py --space kitchen-diner --version approved_2b --room R-g-kitchen-living-dining-open-plan \
        --spec-version after --door 2.15,-4.55,opening --door 3.3,-7.7,bifolds
    python3 tools/review/sweep_plan.py --space front-garden --version approved_2b --garden 1.5,7.5,4,20,3.5 --door 0.2,21.0,street

A grid about 1 m apart (--spacing) inset from the walls (--inset), plus the doorways given with --door x,z,tag, written to
renders/house-build/first-build/round-1/sweep/<space>/<version>/plan.json. Rooms come from the signed spec (spec_v1.json
versions.<before|after>.rooms: floor_y, polygon); a garden is a rectangle x0,x1,z0,z1,spacing in the house frame. Nothing
here is specific to one house: the spec is the input."""
import argparse, json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def inside(x, z, poly):
    c = False
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % len(poly)]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            c = not c
    return c


def edge_dist(x, z, poly):
    best = 1e9
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % len(poly)]
        dx, dz = x2 - x1, z2 - z1
        t = 0 if dx == dz == 0 else max(0, min(1, ((x - x1) * dx + (z - z1) * dz) / (dx * dx + dz * dz)))
        best = min(best, math.hypot(x - (x1 + t * dx), z - (z1 + t * dz)))
    return best


def centroid(poly):
    return sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)


def room_grid(poly, spacing, inset):
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    nx = int((max(xs) - min(xs) - 2 * inset) // spacing) + 1
    nz = int((max(zs) - min(zs) - 2 * inset) // spacing) + 1
    x0 = (min(xs) + max(xs)) / 2 - (nx - 1) * spacing / 2
    z0 = (min(zs) + max(zs)) / 2 - (nz - 1) * spacing / 2
    out = []
    for i in range(nx):
        for j in range(nz):
            x, z = x0 + i * spacing, z0 + j * spacing
            if inside(x, z, poly) and edge_dist(x, z, poly) >= inset:
                out.append((round(x, 2), round(z, 2)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", required=True); ap.add_argument("--version", required=True)
    ap.add_argument("--room", help="room id in the spec"); ap.add_argument("--spec-version", default="after", choices=["before", "after"])
    ap.add_argument("--garden", help="x0,x1,z0,z1,spacing (house frame)")
    ap.add_argument("--spacing", type=float, default=1.0); ap.add_argument("--inset", type=float, default=0.4)
    ap.add_argument("--door", action="append", default=[], help="x,z,tag: a doorway (0.1 m inside the room)")
    ap.add_argument("--eyes", default="1.22,1.6"); ap.add_argument("--site", default="house-wip")
    ap.add_argument("--out-root", default="renders/house-build/first-build/round-1/sweep")
    a = ap.parse_args()
    spec = json.load(open(os.path.join(ROOT, "assets/sites/house/spec/spec_v1.json")))
    plan = {"space": a.space, "version": a.version, "site": a.site, "eyes": [float(e) for e in a.eyes.split(",")],
            "yaws": list(range(0, 360, 30)), "up_deg": 35, "down_deg": -35, "w": 480, "h": 270, "fov": 60}
    pts = []
    if a.room:
        room = next(r for r in spec["versions"][a.spec_version]["rooms"] if r["id"] == a.room)
        poly = room["polygon"]; fy = room["floor_y"]
        plan.update(kind="room", room=a.room, polygon=poly, floor_y=fy, ceiling_y=room["ceiling_y"] if isinstance(room["ceiling_y"], (int, float)) else 2.43)
        for x, z in room_grid(poly, a.spacing, a.inset):
            pts.append({"x": x, "z": z, "y": fy, "tag": "grid"})
        for d in a.door:
            x, z, tag = d.split(",")
            assert inside(float(x), float(z), poly), f"doorway {d} is outside the room polygon"
            pts.append({"x": float(x), "z": float(z), "y": fy, "tag": "door:" + tag})
        cx, cz = centroid(poly)
    else:
        x0, x1, z0, z1, sp = [float(v) for v in a.garden.split(",")]
        nx, nz = int(round((x1 - x0) / sp)) + 1, int(round((z1 - z0) / sp)) + 1
        for i in range(nx):
            for j in range(nz):
                pts.append({"x": round(x0 + i * (x1 - x0) / max(1, nx - 1), 2), "z": round(z0 + j * (z1 - z0) / max(1, nz - 1), 2), "y": None, "tag": "grid"})
        for d in a.door:
            x, z, tag = d.split(",")
            pts.append({"x": float(x), "z": float(z), "y": None, "tag": "gate:" + tag})
        sj = json.load(open(os.path.join(ROOT, "assets/sites/front-garden-model/site.json")))["bounds"]
        # garden frame -> house frame: x + 4.63, z + 3.09 (spec garden.frame_transform)
        plan.update(kind="garden", bounds=[sj["x0"] + 4.63, sj["x1"] + 4.63, sj["z0"] + 3.09, sj["z1"] + 3.09])
        cx, cz = 3.0, 0.0                          # looked at for the up / down frames: the house front
    for i, p in enumerate(pts):
        p["id"] = f"p{i + 1:02d}"
        p["look"] = round(math.degrees(math.atan2(-(cx - p["x"]), -(cz - p["z"]))) % 360, 0) if (abs(cx - p["x"]) + abs(cz - p["z"])) > 0.3 else 0
    plan["points"] = pts
    out = os.path.join(ROOT, a.out_root, a.space, a.version)
    os.makedirs(out, exist_ok=True)
    json.dump(plan, open(os.path.join(out, "plan.json"), "w"), indent=1)
    print(f"{a.space}/{a.version}: {len(pts)} points -> {os.path.relpath(out, ROOT)}/plan.json")


if __name__ == "__main__":
    main()

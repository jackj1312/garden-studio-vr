"""Verify the exported open threshold between the Battle Road living and kitchen floors."""
import json
import sys

from check_setting_marks import Setting
from hb_geom import area, ccw, clip_half, sub


def top_faces(model, name):
    height = model.bounds(name)[1][1]
    return [ccw([(p[0], p[2]) for p in face]) for _, face in model.triangles(name)
            if all(abs(p[1] - height) < .00001 for p in face)]


def overlap(first, second):
    polygon = first
    for p, q in zip(second, second[1:] + second[:1]):
        dx, dy = sub(q, p)
        polygon = clip_half(polygon, (dy, -dx, dx*p[1] - dy*p[0]))
        if len(polygon) < 3:
            return 0
    return abs(area(polygon))


def check(path):
    model = Setting(path)
    living = 'SPEC-FLR-R-g-living'
    kitchen = 'SPEC-FLR-R-g-kitchen-living-dining-open-plan'
    first, second = [top_faces(model, name) for name in (living, kitchen)]
    assert first and second
    overlap_m2 = sum(overlap(a, b) for a in first for b in second)
    assert overlap_m2 < .000001, ('overlapping floor finishes', overlap_m2)
    skirts = [name for name in model.nodes if name.startswith(('SPEC-SKIRT-R-g-living', 'SPEC-SKIRT-R-g-kitchen'))]
    for x in (2.75, 3.0, 3.25):
        heights = [model.top(living, x, -4.30), model.top(kitchen, x, -4.41)]
        assert all(heights) and abs(heights[0][0]-heights[1][0]) < .001, (x, heights)
        for z in (-4.32, -4.33):
            for skirt in skirts:
                hit = model.top(skirt, x, z)
                assert hit is None or hit[0] <= heights[0][0]+.001, (skirt, x, z, hit)
    return {'overlap_m2': overlap_m2, 'clear_stations': 3}


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1]), indent=2))

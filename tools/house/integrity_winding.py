"""Classify the gate's winding jump without a quadratic temporary on detailed meshes."""
import numpy as np

EPSILON = 2e-4
THRESHOLD = -.5


def winding_at(points, triangles):
    """Original double-precision Van Oosterom/Strackee solid-angle sum."""
    if not len(triangles):
        return np.zeros(len(points))
    q = points[:, None, :]
    a, b, c = (triangles[:, i] - q for i in range(3))
    la, lb, lc = (np.linalg.norm(x, axis=2) for x in (a, b, c))
    dot = lambda x, y: np.einsum("ijk,ijk->ij", x, y)
    det = dot(a, np.cross(b, c))
    den = la * lb * lc + dot(a, b) * lc + dot(a, c) * lb + dot(b, c) * la
    return (2 * np.arctan2(det, den)).sum(axis=1) / (4 * np.pi)


def inward_mask(triangles, accelerated=True):
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    twice_areas = np.linalg.norm(normals, axis=1)
    valid = twice_areas > 1e-12
    normals[valid] /= twice_areas[valid, None]
    centres = triangles.mean(axis=1)
    lower, upper = triangles.min(axis=1), triangles.max(axis=1)
    behind, ahead = centres - normals * EPSILON, centres + normals * EPSILON
    result = np.zeros(len(triangles), dtype=bool)

    def jump(ids, nearby):
        return winding_at(behind[ids], nearby) - winding_at(ahead[ids], nearby)

    def batch(ids):
        if accelerated and len(ids) > 32:
            # Query faces in spatial groups so they can share candidate triangles.
            span = np.ptp(centres[ids], axis=0)
            ordered = ids[np.argsort(centres[ids, int(np.argmax(span))])]
            mid = len(ordered) // 2
            batch(ordered[:mid])
            batch(ordered[mid:])
            return
        if not accelerated or len(triangles) < 160:
            result[ids] = jump(ids, triangles) < THRESHOLD
            return
        lo, hi = centres[ids].min(axis=0), centres[ids].max(axis=0)
        separation = np.maximum(0., np.maximum(lower - hi, lo - upper))
        dist = np.maximum(0., np.linalg.norm(separation, axis=1) - EPSILON)
        near = dist < .012
        radius = .012
        # The solid-angle integrand is n·r / |r|^3. Its gradient has
        # norm <= 2/|r|^3. Across 2*eps, the omitted winding change from
        # a triangle is <= eps*area/(pi*distance^3), including open surfaces.
        bound = EPSILON / (2*np.pi) * twice_areas / np.maximum(dist, 1e-10)**3
        while (uncertainty := bound[~near].sum()) > .30:
            radius *= 2
            near = dist < radius
        value = jump(ids, triangles[near])
        result[ids] = value < THRESHOLD
        unsure = ids[np.abs(value - THRESHOLD) <= uncertainty + 1e-10]
        if len(unsure):
            # Decisions straddling the original threshold use every triangle.
            result[unsure] = jump(unsure, triangles) < THRESHOLD

    ids = np.flatnonzero(valid)
    for block in np.array_split(ids, max(1, (len(ids) + 127)//128)) if not accelerated else [ids]:
        if len(block):
            batch(block)
    return result

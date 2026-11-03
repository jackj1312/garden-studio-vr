"""Measured edge boards of a lean-to porch, in the drawing's XYZ frame."""
import json
import os

from hb_geom import ccw, prism
from hb_roof import COVER


def _board(outline, left, right):
    """Extrude a closed Y/Z cutting profile between the two X stations."""
    vertices, faces = prism(ccw(outline), left, right)
    return [(x, y, z) for y, z, x in vertices], faces


def porch_trim(spec, plane, low_edge, soffit):
    """A surveyed left verge, its boxed end and the front fascia/level return.

    The traced roof supplies the pitch, projection and soffit height. The photo
    survey establishes which side has a free verge, its bargeboard depth and
    the wall arris. The opposite side is an abutment against the higher wing.
    """
    survey = spec.get('as_built', {})
    source = os.path.expanduser(survey.get('survey', ''))
    if not source or not os.path.isfile(source):
        return None
    with open(source) as stream:
        porch = json.load(stream).get('porch', {})
    verge = porch.get('verge')
    if not verge or 'verge_outer_x' not in porch.get('roof', {}):
        return None

    a, b = low_edge
    left, right = sorted((a[0], b[0]))
    wall = survey['shift'][0] + porch['side_wall_outer_x']
    if abs(left - (survey['shift'][0] + porch['roof']['verge_outer_x'])) > .02 or not left < wall < right:
        return None
    board = .018
    skin = .012
    front = a[1] + .050             # behind the tile nose, inside the gutter
    wall_front = a[1] + plane.wing.spec['overhang']
    back = max(p[1] for p in plane.wing.footprint)
    depth = verge['bargeboard_depth']
    zroof = lambda y: plane.z((left, y)) - COVER['tiles'] / plane.cos
    bottom = lambda y: plane.z((left, y)) - depth

    # The front box runs level back to the wall. From that station the
    # underside follows the roof, with a vertical closure at the change.
    lower = [(front, soffit), (wall_front, soffit),
             (wall_front, bottom(wall_front)), (back, bottom(back))]
    barge = lower + [(back, zroof(back)), (front, zroof(front))]
    lining = lower + [(back, bottom(back) + skin),
                      (wall_front - board, bottom(wall_front - board) + skin),
                      (wall_front - board, soffit + skin), (front + board, soffit + skin),
                      (front + board, zroof(front + board)), (front, zroof(front))]
    front_board = [(front, soffit), (wall_front, soffit),
                   (wall_front, soffit + skin), (front + board, soffit + skin),
                   (front + board, zroof(front + board)), (front, zroof(front))]
    return [('', _board(front_board, wall, right)),
            ('-barge', _board(barge, left, left + board)),
            ('-boxed-return', _board(lining, left + board, wall))]

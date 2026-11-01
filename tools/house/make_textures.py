"""True-scale PBR texture sets for the house generator: base colour (sRGB), normal (OpenGL / glTF +Y), and ORM
(R = ambient occlusion, G = roughness, B = metallic, the glTF packing).

    uv run --with numpy --with pillow python tools/house/make_textures.py <out_dir> [--only name,name]

Sources, in order of preference (CREDITS.md):
  1. the client's own surfaces: unit-built photo sheets (tools/blender/bake_unit_sheets.py -> master/phototex/sheets)
     and close-up tiles (master/phototex/*.jpg, scales in scales.json) - brick, paving, lawn, gravel;
  2. colours SAMPLED from the client's frames (renders/front-garden/audit-3: roof (156,138,120), mortars);
  3. CC0 Poly Haven sets already in master/polyhaven/tex (concrete_pavement, gravel_floor, brown_mud_leaves_01);
  4. procedural products at their real unit sizes (440x215 block, 1200x450 PIR boards, 265x165 plain tiles at
     100 gauge, 1200 plasterboard with tapered edges, sawn C24 with grain and grade stamps, ...).
Every set is written with its real-world tile size in tex_meta.json; the generator maps UVs in metres / tile.
Max 1024 px a side (CONTRACT.md: Quest budget); the GLB export converts to WebP."""
import sys, os, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = sys.argv[1]
ONLY = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
os.makedirs(OUT, exist_ok=True)
PH = os.path.join(ROOT, "master", "polyhaven", "tex")
PT = os.path.join(ROOT, "master", "phototex")
META = {}
RNG = np.random.default_rng(23)


# ---------------------------------------------------------------- helpers
def srgb_to_lin(a): return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
def lin_to_srgb(a): return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(np.clip(a, 0, None), 1 / 2.4) - 0.055)


def noise(h, w, scale, seed=0, octaves=4, wrap=True):
    """tileable fractal value noise in [0,1]"""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32); amp = 1.0; tot = 0.0
    for o in range(octaves):
        gh, gw = max(2, int(h / scale * 2 ** o)), max(2, int(w / scale * 2 ** o))
        g = rng.random((gh, gw)).astype(np.float32)
        im = Image.fromarray((g * 255).astype(np.uint8))
        if wrap:
            big = np.tile(g, (3, 3)); im = Image.fromarray((big * 255).astype(np.uint8)).resize((w * 3, h * 3), Image.BICUBIC)
            a = np.asarray(im, np.float32)[h:2 * h, w:2 * w] / 255
        else:
            a = np.asarray(im.resize((w, h), Image.BICUBIC), np.float32) / 255
        out += a * amp; tot += amp; amp *= 0.5
    return out / tot


def streaks(h, w, sx, sy, seed=0, octaves=3):
    """tileable noise stretched along x (wood fibre): feature size sx px along, sy px across"""
    rng = np.random.default_rng(seed); out = np.zeros((h, w), np.float32); amp = 1; tot = 0
    for o in range(octaves):
        gh, gw = max(2, int(h / sy * 2 ** o)), max(2, int(w / sx * 2 ** o))
        g = rng.random((gh, gw)).astype(np.float32)
        big = np.tile(g, (3, 3)); im = Image.fromarray((big * 255).astype(np.uint8)).resize((w * 3, h * 3), Image.BICUBIC)
        out += np.asarray(im, np.float32)[h:2 * h, w:2 * w] / 255 * amp; tot += amp; amp *= 0.55
    return out / tot


def blur(a, r):
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255


def normal_from_height(hgt, strength, wrap=True):
    """OpenGL (+Y up) tangent-space normal map from a height field (strength = slope gain)"""
    if wrap:
        dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5
        dy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5
    else:
        dx = np.gradient(hgt, axis=1); dy = np.gradient(hgt, axis=0)
    nx, ny = -dx * strength, dy * strength          # image rows go down; +Y (green) is up the texture
    nz = np.ones_like(hgt)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / L, ny / L, nz / L], -1)
    return (n * 0.5 + 0.5)


def save(name, col_srgb, nrm=None, ao=None, rough=None, metal=None, tile=(1.0, 1.0), alpha=None, extra=None):
    if ONLY and name not in ONLY: return
    h, w = col_srgb.shape[:2]
    c = np.clip(col_srgb, 0, 1)
    if alpha is not None:
        Image.fromarray((np.dstack([c, np.clip(alpha, 0, 1)]) * 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, f"{name}_col.png"))
        colf = f"{name}_col.png"
    else:
        Image.fromarray((c * 255).astype(np.uint8)).save(os.path.join(OUT, f"{name}_col.jpg"), quality=90)
        colf = f"{name}_col.jpg"
    files = dict(col=colf)
    if nrm is not None:
        Image.fromarray((np.clip(nrm, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, f"{name}_nrm.png"))
        files["nrm"] = f"{name}_nrm.png"
    if rough is not None:
        ao_ = np.ones((h, w), np.float32) if ao is None else ao
        mt = np.zeros((h, w), np.float32) if metal is None else (metal if np.ndim(metal) else np.full((h, w), metal, np.float32))
        rg = rough if np.ndim(rough) else np.full((h, w), rough, np.float32)
        Image.fromarray((np.dstack([ao_, rg, mt]) * 255).astype(np.uint8)).save(os.path.join(OUT, f"{name}_orm.jpg"), quality=92)
        files["orm"] = f"{name}_orm.jpg"
    META[name] = dict(files=files, tile=list(tile), alpha=alpha is not None, **(extra or {}))
    print(name, w, "x", h, "tile", tile)


def load(path, size=None):
    im = Image.open(path).convert("RGB")
    if size: im = im.resize(size, Image.LANCZOS)
    return np.asarray(im, np.float32) / 255


def font(px):
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"):
        if os.path.exists(f):
            try: return ImageFont.truetype(f, px)
            except Exception: pass
    return ImageFont.load_default()


def text_layer(h, w, rows, fill_frac=1.0):
    """[(y_frac, text, px, colour, x_step)] -> RGBA float layer"""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for (yf, txt, px, col, step) in rows:
        f = font(px)
        x = 0
        while x < w:
            d.text((x, int(yf * h)), txt, fill=col, font=f); x += step
    return np.asarray(im, np.float32) / 255


# ---------------------------------------------------------------- 1. the client's brick (unit-built sheets, 4.05 x 4.8 m)
def brick_sheet(src, name, clean=0.0, gain=(1, 1, 1), mortar=1.0):
    S = 4.05, 4.8
    W, H = 864, 1024                           # 4.7 mm/px
    rgba = Image.open(src).convert("RGB").resize((W, H), Image.LANCZOS)
    col = np.asarray(rgba, np.float32) / 255
    r, g, b = col[..., 0], col[..., 1], col[..., 2]
    red = (r - b)
    thr = np.percentile(red, 30)
    brick = blur((red > thr).astype(np.float32), 0.6)
    lum = col.mean(-1)
    if clean:                                  # a new brick 'to match': same units, less weathering
        mean = col.reshape(-1, 3)[brick.reshape(-1) > 0.5].mean(0)
        col = col * (1 - clean) + (col * 0.6 + mean * 0.4) * clean
    # warmed to the brick as Jack's photos show it in daylight (the scanned sheets read cool and dull), and the joints
    # darkened so the bond reads at headset distance (judges, CORRECTIONS-LOG 121)
    col = col * np.array(gain, np.float32)
    col = col * (brick[..., None] + (1 - brick[..., None]) * mortar)
    col = np.clip(col, 0, 1)
    # bed joints: rows where mortar dominates -> course phase for the UVs (a bed joint lands on the dpc)
    rowm = 1 - brick.mean(1)
    course_px = 0.075 / S[1] * H
    phase = np.array([rowm[np.arange(int(k), H, course_px).astype(int) % H].mean() for k in np.linspace(0, course_px, 24, endpoint=False)])
    k0 = np.linspace(0, course_px, 24, endpoint=False)[int(np.argmax(phase))]
    v_joint = 1 - (k0 / H)                     # v of a bed-joint centre (v up)
    hgt = brick * 0.8 + (lum - lum.mean()) * 0.6 + noise(H, W, 6, 3) * 0.08
    nrm = normal_from_height(hgt, 6.0)
    ao = 0.62 + 0.38 * blur(brick, 1.5)
    rough = 0.84 * brick + 0.95 * (1 - brick)
    save(name, col, nrm, ao, rough, 0.0, S, extra=dict(v_joint=round(float(v_joint), 4), source=os.path.relpath(src, ROOT)))


# ---------------------------------------------------------------- 2. roof tiles: plain concrete tiles, 265x165 at 100 gauge
def plain_tiles(name, base_rgb, moss=0.0, seed=1):
    S = (1.325, 1.0)                            # 5 tiles across (265 mm), 10 courses (100 mm gauge)
    W, H = 1024, 773
    ppm_x, ppm_y = W / S[0], H / S[1]
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ym = yy / ppm_y; xm = xx / ppm_x
    course = np.floor(ym / 0.1).astype(int)
    off = (course % 2) * 0.1325
    tx = np.floor(((xm + off) % S[0]) / 0.265).astype(int)
    fy = (ym % 0.1) / 0.1                        # 0 at the top of the exposed course (under the course above), 1 at the tail
    fx = (((xm + off) % S[0]) % 0.265) / 0.265
    tid = course * 7 + tx
    var = (np.sin(tid * 12.9898 + seed) * 43758.5453) % 1.0
    var2 = (np.sin(tid * 78.233 + seed * 3) * 12345.678) % 1.0
    base = srgb_to_lin(np.array(base_rgb, np.float32) / 255)
    col = base[None, None, :] * (0.72 + 0.5 * var[..., None]) * np.array([1.0, 0.98 + 0.04 * var2.mean(), 1.0])[None, None, :]
    grain = noise(H, W, 10, seed + 5, 5)
    col = col * (0.88 + 0.24 * grain[..., None])
    gap = (fx < 0.012) | (fx > 0.988)
    shadow = np.clip((fy - 0.86) / 0.14, 0, 1) ** 2           # the course below is shaded by this tile's tail
    lip = np.clip(1 - fy / 0.22, 0, 1) ** 1.3                 # top of the course: in the shadow of the tail above
    col = col * (1 - 0.85 * lip[..., None]) * (1 - 0.75 * gap[..., None]) * (1 - 0.2 * shadow[..., None])
    if moss > 0:
        m = noise(H, W, 40, seed + 11, 4)
        lichen = (noise(H, W, 1.5, seed + 12, 2) > 0.80) & (m > 0.45)
        moss_m = np.clip((m - 0.62) * 3 * moss, 0, 0.75) * np.clip(1 - fy / 0.3, 0, 1) + 0.25 * gap * (m > 0.55)
        moss_col = srgb_to_lin(np.array([70, 74, 44], np.float32) / 255)
        lich_col = srgb_to_lin(np.array([176, 170, 120], np.float32) / 255)
        col = col * (1 - moss_m[..., None]) + moss_col * moss_m[..., None]
        col = np.where(lichen[..., None], col * 0.4 + lich_col * 0.6, col)
    col_s = lin_to_srgb(np.clip(col, 0, 1))
    hgt = fy * 0.9 - lip * 0.6 - gap * 0.5 + grain * 0.1          # each tile slopes out towards its tail
    nrm = normal_from_height(hgt, 5.0)
    ao = 1 - 0.45 * lip - 0.3 * gap - 0.25 * shadow
    rough = 0.78 + 0.1 * grain - (0 if moss else 0.05)
    save(name, col_s, nrm, ao, rough, 0.0, S)


# ---------------------------------------------------------------- 3. dense concrete block 440x215 + 10 joints
def blocks(name):
    S = (0.9, 0.9); W = H = 1024
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ym = yy / H * S[1]; xm = xx / W * S[0]
    row = np.floor(ym / 0.225).astype(int); off = (row % 2) * 0.225
    xr = (xm + off) % 0.45; yr = ym % 0.225
    joint = (xr < 0.010) | (yr < 0.010)
    bid = np.floor((xm + off) / 0.45).astype(int) * 31 + row * 7
    var = (np.sin(bid * 12.9898) * 43758.5453) % 1.0
    base = np.array([0.56, 0.56, 0.54], np.float32)
    agg = noise(H, W, 2, 7, 2); pits = (noise(H, W, 1.2, 8, 1) > 0.82).astype(np.float32)
    col = base[None, None] * (0.9 + 0.12 * var[..., None]) * (0.86 + 0.28 * agg[..., None]) * (1 - 0.25 * pits[..., None])
    mortar = np.array([0.66, 0.65, 0.62], np.float32) * (0.92 + 0.12 * noise(H, W, 3, 9, 2))[..., None]
    col = np.where(joint[..., None], mortar, col)
    hgt = (~joint) * 1.0 - pits * 0.3 + agg * 0.15
    save(name, col, normal_from_height(blur(hgt, 0.7), 5), 1 - 0.3 * joint - 0.2 * pits, 0.9, 0.0, S)


# ---------------------------------------------------------------- 4. foil-faced PIR boards (1200 x 450), printed
def pir_foil(name, label):
    S = (2.4, 0.9); W, H = 1024, 384
    crinkle = noise(H, W, 5, 21, 5)
    col = np.full((H, W, 3), 0.80, np.float32) * (0.92 + 0.1 * crinkle[..., None])
    xm = np.arange(W) / W * S[0]; ym = np.arange(H) / H * S[1]
    jx = (np.abs(((xm + 0.6) % 1.2) - 0.6) > 0.597)
    jy = (np.abs(((ym + 0.225) % 0.45) - 0.225) > 0.223)
    joint = jx[None, :] | jy[:, None]
    txt = text_layer(H, W, [(0.12, label, 13, (40, 70, 150, 230), 512), (0.62, label, 13, (40, 70, 150, 230), 512)])
    a = txt[..., 3:4]
    col = col * (1 - a) + txt[..., :3] * a
    col = np.where(joint[..., None], col * 0.5, col)
    rough = 0.22 + 0.15 * crinkle + 0.5 * a[..., 0]
    metal = np.clip(1 - a[..., 0] * 1.2, 0, 1) * 0.95
    save(name, col, normal_from_height(crinkle * 0.6 - joint * 0.5, 3), 1 - 0.3 * joint, rough, metal, S)


# ---------------------------------------------------------------- 5. timber: sawn C24 with grain, knots and grade stamps
def timber(name, base_rgb, stamp=True, treated=False, aged=False, seed=4):
    S = (2.4, 0.3); W, H = 1024, 128
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    fibre = streaks(H, W, 120, 1.5, seed, 4)                       # long fibres along the member
    late = streaks(H, W, 300, 5, seed + 1, 3)                      # latewood bands, wandering slowly
    bands = np.clip((np.sin((yy / H * 2 * np.pi * 7) + (late - 0.5) * 9) * 0.5 + 0.5), 0, 1) ** 4
    base = np.array(base_rgb, np.float32) / 255
    col = base[None, None] * (0.9 + 0.14 * fibre[..., None] - 0.16 * bands[..., None])
    rng = np.random.default_rng(seed)
    for k in range(2):                                             # knots, with grain flowing round them
        cx, cy, r = rng.uniform(0, W), rng.uniform(10, H - 10), rng.uniform(4, 8)
        d = np.sqrt(((xx - cx) * 0.5) ** 2 + (yy - cy) ** 2)
        col *= (1 - 0.5 * np.clip(1 - d / r, 0, 1) ** 0.6)[..., None]
        col *= (1 - 0.08 * np.clip(1 - d / (r * 3), 0, 1))[..., None]
    if treated: col = col * np.array([0.84, 0.95, 0.80], np.float32)
    if aged: col = col * 0.8 + 0.02
    if stamp:
        t = text_layer(H, W, [(0.30, "C24  KD  TR26  UKCA", 17, (95, 45, 120, 200), 1024)])
        a = t[..., 3:4]; col = col * (1 - a) + t[..., :3] * a
    hgt = fibre * 0.5 - bands * 0.2
    save(name, col, normal_from_height(hgt, 3.0), 0.92 + 0.08 * fibre, 0.8 if not aged else 0.9, 0.0, S)


# ---------------------------------------------------------------- 6. sheets and membranes
def plasterboard(name, existing=False):
    S = (2.4, 2.4); W = H = 1024
    paper = noise(H, W, 2, 31, 3)
    base = np.array([0.90, 0.89, 0.86] if not existing else [0.88, 0.86, 0.82], np.float32)
    col = base[None, None] * (0.97 + 0.05 * paper[..., None])
    hgt = paper * 0.1
    if not existing:
        xm = np.arange(W) / W * S[0]
        d = np.abs(((xm + 0.6) % 1.2) - 0.6)             # tapered edge every 1200
        taper = np.clip(1 - (0.6 - d) / 0.05, 0, 1)
        col = col * (1 - 0.06 * taper)[None, :, None]
        hgt = hgt - taper[None, :] * 0.5
    save(name, col, normal_from_height(blur(hgt, 1), 2), None, 0.9, 0.0, S)


def membrane(name):
    S = (1.5, 1.5); W = H = 768
    fl = noise(H, W, 1.5, 41, 3); sp = noise(H, W, 8, 42, 2)
    col = np.full((H, W, 3), 0.93, np.float32) * (0.95 + 0.06 * fl[..., None] + 0.03 * sp[..., None])
    t = text_layer(H, W, [(0.2, "BREATHER MEMBRANE · VAPOUR PERMEABLE · THIS SIDE UP", 16, (70, 90, 130, 200), 760),
                          (0.7, "BREATHER MEMBRANE · VAPOUR PERMEABLE · THIS SIDE UP", 16, (70, 90, 130, 200), 760)])
    a = t[..., 3:4]; col = col * (1 - a) + t[..., :3] * a
    save(name, col, normal_from_height(fl * 0.4 + sp * 0.4, 2), None, 0.65, 0.0, S)


def dpm(name):
    S = (2.0, 2.0); W = H = 768
    folds = np.abs(noise(H, W, 60, 51, 4) - 0.5) * 2
    col = np.full((H, W, 3), 0.055, np.float32) * (0.9 + 0.4 * folds[..., None])
    save(name, col, normal_from_height(folds, 8), None, 0.35, 0.0, S)


def rebar_mesh(name):
    S = (0.4, 0.4); W = H = 256                          # A393: 10 mm bars at 200 mm both ways
    xm = np.arange(W) / W * S[0]
    bar = (np.abs(((xm + 0.1) % 0.2) - 0.1) < 0.005).astype(np.float32)
    alpha = np.clip(bar[None, :] + bar[:, None], 0, 1)
    rust = noise(H, W, 4, 61, 3)
    col = np.array([0.30, 0.16, 0.10], np.float32)[None, None] * (0.8 + 0.4 * rust[..., None])
    rib = (np.sin(np.arange(W) / W * S[0] / 0.008 * 2 * np.pi) * 0.5 + 0.5)
    hgt = alpha * (0.8 + 0.2 * rib[None, :])
    save(name, col, normal_from_height(blur(hgt, 0.8), 4), None, 0.7, 0.4, S, alpha=alpha)


def mineral_wool(name):
    S = (1.0, 1.0); W = H = 512
    fib = noise(H, W, 0.8, 71, 3); clump = noise(H, W, 20, 72, 3)
    col = np.array([0.88, 0.72, 0.30], np.float32)[None, None] * (0.75 + 0.3 * fib[..., None] + 0.15 * clump[..., None])
    save(name, col, normal_from_height(fib * 0.7 + clump * 0.5, 4), 0.75 + 0.25 * clump, 1.0, 0.0, S)


def chipboard(name):
    S = (1.2, 1.2); W = H = 768
    chips = noise(H, W, 0.7, 81, 2); big = noise(H, W, 3, 82, 2)
    col = np.array([0.76, 0.62, 0.42], np.float32)[None, None] * (0.78 + 0.25 * chips[..., None] + 0.12 * big[..., None])
    t = text_layer(H, W, [(0.45, "P5  T&G  22mm  MOISTURE RESISTANT", 16, (40, 90, 50, 200), 768)])
    a = t[..., 3:4]; col = col * (1 - a) + t[..., :3] * a
    save(name, col, normal_from_height(chips, 2), None, 0.8, 0.0, S)


def steel(name, rgb, rough=0.55, metal=0.25, spangle=False):
    S = (1.0, 1.0); W = H = 512
    mott = noise(H, W, 6, 91, 4)
    col = np.array(rgb, np.float32)[None, None] * (0.85 + 0.25 * mott[..., None])
    hgt = mott * 0.2
    if spangle:                                          # galvanising crystals (Voronoi-ish)
        pts = RNG.uniform(0, W, (900, 2))
        yy, xx = np.mgrid[0:H, 0:W]
        dmin = np.full((H, W), 1e9); idx = np.zeros((H, W), int)
        for k, (px, py) in enumerate(pts):
            dx = np.minimum(np.abs(xx - px), W - np.abs(xx - px)); dy = np.minimum(np.abs(yy - py), H - np.abs(yy - py))
            d = dx * dx + dy * dy; m = d < dmin; dmin[m] = d[m]; idx[m] = k
        sh = (np.sin(idx * 12.9898) * 43758.5453) % 1.0
        col = col * (0.93 + 0.12 * sh[..., None])
        hgt = hgt + sh * 0.05
    save(name, col, normal_from_height(hgt, 2), None, rough + 0.1 * mott, metal, S)


def plain(name, rgb, rough, metal=0.0, nscale=4, amp=0.04, S=(1.0, 1.0), W=256):
    n = noise(W, W, nscale, hash(name) % 1000, 3)
    col = np.array(rgb, np.float32)[None, None] * (1 - amp + 2 * amp * n[..., None])
    save(name, col, normal_from_height(n, 1.0), None, rough, metal, S)


# ---------------------------------------------------------------- 7. CC0 sets and the client's ground photos
def cc0(name, folder, tile, tint=(1, 1, 1), size=1024):
    d = os.path.join(PH, folder)
    col = load(os.path.join(d, "diff.jpg"), (size, size)) * np.array(tint, np.float32)
    nrm = load(os.path.join(d, "nor.jpg"), (size, size))      # Poly Haven 'nor' is OpenGL (glTF) convention
    arm = load(os.path.join(d, "arm.jpg"), (size, size))
    save(name, col, nrm, arm[..., 0], arm[..., 1], arm[..., 2], (tile, tile), extra=dict(source=f"Poly Haven {folder} (CC0)"))


def photo(name, file, tile, tint=(1, 1, 1), rough=0.9, strength=3.0, size=1024, desat=0.0):
    im = Image.open(os.path.join(PT, file)).convert("RGB")
    w, h = im.size; s = size / max(w, h)
    col = np.asarray(im.resize((int(w * s), int(h * s)), Image.LANCZOS), np.float32) / 255 * np.array(tint, np.float32)
    if desat:
        g = col.mean(-1, keepdims=True); col = np.clip(col * (1 - desat) + g * desat, 0, 1)
    lum = col.mean(-1)
    save(name, col, normal_from_height(blur(lum, 1.0), strength), 0.8 + 0.2 * blur(lum, 2) / max(1e-3, lum.mean()) * 0.5, rough, 0.0, tile,
         extra=dict(source=f"client close-up {file}"))


def closeboard(name, base_rgb=(128, 104, 80), seed=21):
    """vertical feather-edge boards (125 wide lapped to 100), weathered softwood: u along the fence, v up"""
    S = (1.0, 1.8); W, H = 512, 922
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    um = xx / W * S[0]
    fb = (um % 0.1) / 0.1                                  # 0 at the thick edge, 1 at the feather edge under the next board
    bid = np.floor(um / 0.1).astype(int)
    var = (np.sin(bid * 12.9898 + seed) * 43758.5453) % 1.0
    grain = streaks(W, H, 160, 2.0, seed, 4).T                 # fibres run up the board
    base = np.array(base_rgb, np.float32) / 255
    col = base[None, None] * (0.82 + 0.28 * var[..., None]) * (0.86 + 0.24 * grain[..., None])
    col = col * (1 - 0.45 * (fb > 0.965)[..., None])        # shadow line at each lap
    weather = noise(H, W, 6, seed + 2, 3)
    col = col * 0.85 + col.mean(-1, keepdims=True) * 0.15 * (0.6 + weather[..., None])
    hgt = fb * 0.6 + grain * 0.2
    save(name, np.clip(col, 0, 1), normal_from_height(hgt, 5.0), 0.85 + 0.15 * (1 - (fb > 0.965)), 0.9, 0.0, S)


def heras(name):
    """Heras panel mesh: 4 mm galvanised wires at 75 mm (vertical wires) x 225 mm (horizontal), alpha cut-out"""
    S = (0.45, 0.45); W = H = 512
    xm = np.arange(W) / W * S[0]; ym = np.arange(H) / H * S[1]
    vx = (np.abs(((xm + 0.0375) % 0.075) - 0.0375) < 0.0022).astype(np.float32)
    hy = (np.abs(((ym + 0.1125) % 0.225) - 0.1125) < 0.0022).astype(np.float32)
    alpha = np.clip(vx[None, :] + hy[:, None], 0, 1)
    col = np.full((H, W, 3), 0.66, np.float32) * (0.9 + 0.2 * noise(H, W, 8, 71, 2)[..., None])
    save(name, col, normal_from_height(blur(alpha, 0.8), 3), None, 0.45, 0.85, S, alpha=alpha)


def tarp(name, rgb=(0.10, 0.26, 0.58)):
    S = (1.5, 1.5); W = H = 512
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    weave = 0.5 + 0.25 * np.sin(xx / W * S[0] / 0.004 * np.pi) * np.sin(yy / H * S[1] / 0.004 * np.pi)
    folds = noise(H, W, 3, 81, 3)
    col = np.array(rgb, np.float32)[None, None] * (0.8 + 0.3 * folds[..., None]) * (0.95 + 0.1 * weave[..., None])
    save(name, np.clip(col, 0, 1), normal_from_height(folds * 2 + weave * 0.1, 6), None, 0.55, 0.0, S)


def band(name, file, S, size=(1024, 128)):
    """a straightened course band cut from a close-up (the soldier course over the front windows, close-up 20504)"""
    col = load(file, size)
    lum = col.mean(-1)
    mortar = np.clip((lum - np.percentile(lum, 70)) * 6, 0, 1)
    save(name, col, normal_from_height(blur(1 - mortar, 1.0) * 0.8 + lum * 0.3, 5.0), 0.7 + 0.3 * (1 - mortar), 0.85, 0.0, S,
         extra=dict(source=os.path.relpath(file, ROOT)))



# ---------------------------------------------------------------- 8. scanned CC0 PBR (ambientCG, master/ambientcg/<id>, 1K-JPG)
ACG = os.path.join(ROOT, "master", "ambientcg")
ACG_URL = "https://ambientcg.com/view?id={}"


def acg_maps(aid, size=1024):
    d = os.path.join(ACG, aid)
    f = lambda k: os.path.join(d, f"{aid}_1K-JPG_{k}.jpg")
    col = load(f("Color"), (size, size))
    nrm = load(f("NormalGL"), (size, size))
    rough = load(f("Roughness"), (size, size)).mean(-1)
    ao = load(f("AmbientOcclusion"), (size, size)).mean(-1) if os.path.exists(f("AmbientOcclusion")) else np.ones((size, size), np.float32)
    metal = load(f("Metalness"), (size, size)).mean(-1) if os.path.exists(f("Metalness")) else np.zeros((size, size), np.float32)
    return col, nrm, rough, ao, metal


def recolour(col, target_rgb, keep=0.85):
    """the scan's own light/dark detail on a measured colour: luminance ratio x target (sRGB 0-255)"""
    lum = col.mean(-1, keepdims=True); m = max(1e-3, float(lum.mean()))
    t = np.array(target_rgb, np.float32)[None, None] / 255
    return np.clip(t * (1 - keep + keep * lum / m), 0, 1)


def acg(name, aid, tile, target=None, keep=0.85, rough_gain=1.0, metal=None, size=1024, extra=None, nrm_k=1.0):
    col, nrm, rough, ao, mt = acg_maps(aid, size)
    if nrm_k != 1.0:                       # a flatter face (skimmed plaster): the scan's relief scaled down
        n = nrm * 2 - 1; n[..., :2] *= nrm_k; n /= np.linalg.norm(n, axis=-1, keepdims=True); nrm = n * 0.5 + 0.5; ao = 1 - (1 - ao) * nrm_k
    if target is not None: col = recolour(col, target, keep)
    mt = mt if metal is None else np.full_like(rough, metal)
    save(name, col, nrm, ao, np.clip(rough * rough_gain, 0.03, 1), mt, (tile, tile) if np.ndim(tile) == 0 else tile,
         extra=dict(source=f"ambientCG {aid} (CC0) {ACG_URL.format(aid)}", **(extra or {})))


def acg_blocks(name, aid="Concrete030"):
    """dense concrete blocks 440x215 laid with 10 mm joints: every block's face is its own window into the scan
    (no two neighbours alike), on the measured block grey; true module (CORRECTIONS-LOG 133)"""
    S = (0.9, 0.9); W = H = 1024
    col0, nrm0, rough0, ao0, _ = acg_maps(aid, 1024)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ym = yy / H * S[1]; xm = xx / W * S[0]
    row = np.floor(ym / 0.225).astype(int); off = (row % 2) * 0.225
    xr = (xm + off) % 0.45; yr = ym % 0.225
    joint = (xr < 0.010) | (yr < 0.010)
    bid = (np.floor(((xm + off) % S[0]) / 0.45).astype(int) * 31 + row * 7) % 97
    sx = ((bid * 389) % 1024); sy = ((bid * 211) % 1024)
    ix = ((xx + sx) % 1024).astype(int); iy = ((yy + sy) % 1024).astype(int)
    col = recolour(col0[iy, ix], (150, 150, 145), 0.9)
    var = (np.sin(bid * 12.9898) * 43758.5453) % 1.0
    col = col * (0.93 + 0.1 * var[..., None])
    mortar = np.array([0.62, 0.61, 0.58], np.float32) * (0.92 + 0.12 * noise(H, W, 3, 9, 2))[..., None]
    col = np.where(joint[..., None], mortar, col)
    hj = blur((~joint).astype(np.float32), 0.8)
    nj = normal_from_height(hj, 5.0)
    n = nrm0[iy, ix] * 2 - 1; nj2 = nj * 2 - 1
    nn = n + np.concatenate([nj2[..., :2], np.zeros_like(nj2[..., :1])], -1); nn /= np.linalg.norm(nn, axis=-1, keepdims=True)
    save(name, col, nn * 0.5 + 0.5, np.where(joint, 0.7, ao0[iy, ix]), np.where(joint, 0.95, rough0[iy, ix]), 0.0, S,
         extra=dict(source=f"ambientCG {aid} (CC0) {ACG_URL.format(aid)}, laid as 440x215 blocks"))


def acg_timber(name, base_rgb, aid="Wood058", stamp=True, treated=False, aged=False, seed=4):
    """sawn softwood from a scanned wood face, grain along the member (u), recoloured to C24 whitewood, grade stamps"""
    S = (2.4, 0.3); W, H = 1024, 128
    col0, nrm0, rough0, ao0, _ = acg_maps(aid, 1024)
    col0 = np.rot90(col0); nrm0 = np.rot90(nrm0)[..., [1, 0, 2]] * np.array([-1, 1, 1]) + np.array([1, 0, 0])
    rough0 = np.rot90(rough0)
    y0 = (seed * 137) % (1024 - H)
    col = recolour(col0[y0:y0 + H], base_rgb, 0.9); nrm = nrm0[y0:y0 + H]; rough = rough0[y0:y0 + H]
    if treated: col = col * np.array([0.84, 0.95, 0.80], np.float32)
    if aged: col = col * 0.82 + 0.02
    if stamp:
        t = text_layer(H, W, [(0.30, "C24  KD  TR26  UKCA", 17, (95, 45, 120, 200), 1024)])
        a = t[..., 3:4]; col = col * (1 - a) + t[..., :3] * a
    save(name, np.clip(col, 0, 1), np.clip(nrm, 0, 1), None, np.clip(0.75 + 0.2 * rough, 0, 1), 0.0, S,
         extra=dict(source=f"ambientCG {aid} (CC0) {ACG_URL.format(aid)}, recoloured to C24 whitewood"))


def acg_galv(name, aid="Metal038", base=(170, 174, 178)):
    """galvanised steel: a scanned steel face lightened to zinc grey, with spangle"""
    col, nrm, rough, ao, mt = acg_maps(aid, 512)
    col = recolour(col, base, 0.6)
    pts = RNG.uniform(0, 512, (700, 2)); yy, xx = np.mgrid[0:512, 0:512]
    dmin = np.full((512, 512), 1e9); idx = np.zeros((512, 512), int)
    for k, (px, py) in enumerate(pts):
        dx = np.minimum(np.abs(xx - px), 512 - np.abs(xx - px)); dy = np.minimum(np.abs(yy - py), 512 - np.abs(yy - py))
        d = dx * dx + dy * dy; m = d < dmin; dmin[m] = d[m]; idx[m] = k
    sh = (np.sin(idx * 12.9898) * 43758.5453) % 1.0
    col = col * (0.92 + 0.12 * sh[..., None])
    save(name, np.clip(col, 0, 1), nrm, ao, np.clip(0.28 + 0.25 * rough + 0.08 * sh, 0, 1), 0.9, (1.0, 1.0),
         extra=dict(source=f"ambientCG {aid} (CC0) {ACG_URL.format(aid)}, zinc spangle added"))

# ---------------------------------------------------------------- the set
# brick: the sheet's brick mean (142,111,105) against the daylight close-up brick.jpg (167,134,120) and the house front in
# 20260719_102925 (166,129,111) -> gain about (1.16, 1.12, 1.03); joints darkened to 0.82 so the bond reads
brick_sheet(os.path.join(PT, "sheets", "brick_house.png"), "brick_existing", gain=(1.16, 1.12, 1.03), mortar=0.82)
brick_sheet(os.path.join(PT, "sheets", "brick_porch.png"), "brick_porch", gain=(1.10, 1.07, 1.02), mortar=0.85)
brick_sheet(os.path.join(PT, "sheets", "brick_house.png"), "brick_new", clean=0.35, gain=(1.19, 1.14, 1.04), mortar=0.85)
# roof: sampled on Jack's photo 20260719_102925 (main slope, sun) median sRGB (153,126,109), p10 (77,55,44), p90 (214,177,158);
# shade frame walk_0017 (107,88,82); the garden model's flat (156,138,120) is greyer than the photos. Base set so the
# textured mean (course shadows included) lands on the sunlit median; moss/lichen kept lighter than before.
# round 6 judge (log 165): the roof read pale salmon; walk_0011 sunlit roof median sRGB (107,87,79), 20260719_102925 darker
# in shade: dark chocolate / red-brown plain clay tiles with strong course lines. (ambientCG's roof sets are interlocking or
# pantiles, not UK plain tiles, so the true 265x165 module stays generated, coloured from the photos.)
# measured against the photos (row 176): the render roof read L 54 against the photos' L 46 (x0.68 linear)
plain_tiles("tile_existing", (81, 55, 46), moss=0.5, seed=1)
plain_tiles("tile_new", (79, 54, 45), moss=0.0, seed=2)
closeboard("closeboard")
if os.path.exists(os.path.join(ROOT, "master/phototex/units/soldier/band.jpg")):
    band("brick_soldier", os.path.join(ROOT, "master/phototex/units/soldier/band.jpg"), (1.8, 0.225))
plain("anthracite_upvc", (0.21, 0.23, 0.25), 0.4, nscale=8, amp=0.015)
plain("cream_stone", (0.66, 0.62, 0.56), 0.85, nscale=3, amp=0.06)
plain("buff_concrete", (0.58, 0.57, 0.53), 0.9, nscale=2, amp=0.08)
plain("packer", (0.45, 0.33, 0.26), 0.7, amp=0.03)
plain("black_metal", (0.05, 0.05, 0.055), 0.45, 0.5, amp=0.02)
plain("dish", (0.74, 0.75, 0.76), 0.4, 0.2, amp=0.02)
plain("slate", (0.52, 0.53, 0.53), 0.3, amp=0.02)
heras("heras")
tarp("tarp")
plain("skip_steel", (0.80, 0.56, 0.06), 0.55, 0.3, nscale=6, amp=0.10)
plain("pallet", (0.70, 0.58, 0.40), 0.85, amp=0.08)
plain("tote", (0.86, 0.85, 0.80), 0.8, nscale=10, amp=0.05)
plain("cabin", (0.80, 0.81, 0.80), 0.5, 0.2, amp=0.02)
plain("pvc_drain", (0.70, 0.36, 0.17), 0.5, amp=0.02)
blocks("block")
pir_foil("pir", "PIR INSULATION  ·  FOIL FACED  ·  λ 0.022  ·  85mm")
mineral_wool("mineral_wool")
timber("timber", (214, 178, 124))
timber("timber_existing", (176, 140, 96), stamp=False, aged=True, seed=7)
timber("batten", (190, 170, 120), stamp=False, treated=True, seed=9)
timber("timber_temp", (222, 190, 130), stamp=False, seed=11)
chipboard("chipboard")
plasterboard("plasterboard")
plasterboard("plaster", existing=True)
membrane("membrane")
dpm("dpm")
rebar_mesh("rebar")
steel("steel", (0.36, 0.11, 0.07), rough=0.6, metal=0.15)
steel("lintel_galv", (0.66, 0.68, 0.70), rough=0.35, metal=0.95, spangle=True)
steel("lead", (0.40, 0.42, 0.43), rough=0.55, metal=0.6)
steel("scaffold", (0.62, 0.64, 0.66), rough=0.4, metal=0.9, spangle=True)
cc0("concrete", "concrete_pavement", 2.0, tint=(0.95, 0.95, 0.95))
cc0("screed", "concrete_pavement", 1.2, tint=(1.08, 1.06, 1.02))
cc0("hardcore", "gravel_floor", 1.0, tint=(0.82, 0.82, 0.85))
cc0("earth", "brown_mud_leaves_01", 2.0, tint=(0.95, 0.9, 0.85))
photo("ground_paving", "paving_blocks.jpg", (1.14, 0.8), rough=0.85)
photo("ground_lawn", "lawn_noleaf.jpg" if os.path.exists(os.path.join(PT, "lawn_noleaf.jpg")) else "lawn.jpg", (0.8, 0.8), rough=0.95, desat=0.15,
      tint=(0.97, 0.95, 0.92))
photo("ground_gravel", "gravel.jpg", (0.5, 0.5), rough=0.9)
photo("fence_board", "fence.jpg", (1.0, 0.668), tint=(1.08, 0.97, 0.86), rough=0.9, strength=2.0)
cc0("road", "asphalt_02", 3.0, tint=(0.9, 0.9, 0.9))
plain("upvc_white", (0.93, 0.93, 0.92), 0.32, nscale=8, amp=0.01)
plain("black_upvc", (0.05, 0.05, 0.055), 0.4, nscale=8, amp=0.02)
plain("aluminium", (0.22, 0.23, 0.25), 0.35, 0.7, amp=0.02)
plain("sanitary", (0.96, 0.96, 0.96), 0.12, amp=0.005)
plain("joinery", (0.92, 0.91, 0.88), 0.45, amp=0.01)
plain("door_leaf", (0.93, 0.92, 0.89), 0.45, amp=0.01)
plain("velux", (0.22, 0.24, 0.25), 0.4, 0.3)
plain("felt", (0.10, 0.10, 0.11), 0.85, nscale=2, amp=0.08)
plain("prop_steel", (0.85, 0.42, 0.06), 0.5, 0.3, amp=0.06)
plain("existing_floor", (0.66, 0.58, 0.48), 0.75, amp=0.05)
plain("floor_finish", (0.70, 0.60, 0.46), 0.6, amp=0.05)
plain("stair", (0.62, 0.48, 0.32), 0.6, amp=0.06)
plain("vcl", (0.80, 0.84, 0.86), 0.25, amp=0.03)
plain("existing_partition", (0.88, 0.86, 0.82), 0.85, amp=0.03)

# ---------------------------------------------------------------- new works from scanned CC0 PBR (round 6, Jack: 'not a cartoon')
if os.path.isdir(ACG):
    acg_blocks("block", "Concrete047A")
    acg_timber("timber", (214, 182, 132))
    acg_timber("timber_existing", (176, 140, 96), stamp=False, aged=True, seed=7)
    acg_timber("batten", (196, 176, 124), stamp=False, treated=True, seed=9)
    acg_timber("timber_temp", (222, 192, 136), stamp=False, seed=11)
    acg("concrete", "Concrete047A", 2.0, target=(160, 158, 150), keep=0.8)
    acg("screed", "Concrete047A", 1.6, target=(178, 174, 164), keep=0.6)
    acg("hardcore", "Ground111", 1.0, keep=0.9, target=(132, 118, 104))
    acg("chipboard", "Chipboard005", 1.2, target=(196, 168, 120), keep=0.9)
    acg("steel", "PaintedMetal004", 1.0, target=(122, 48, 34), keep=0.22, rough_gain=1.2, metal=0.15)    # red-oxide primer
    acg("prop_steel", "PaintedMetal004", 1.0, target=(214, 110, 24), keep=0.25, metal=0.2)              # Acrow props, powder coat
    acg("plasterboard", "Plaster001", 2.4, target=(232, 229, 222), keep=0.15, nrm_k=0.2)
    acg("plaster", "Plaster001", 2.0, target=(226, 221, 212), keep=0.25, nrm_k=0.3)
    acg("dpm", "Plastic012A", 2.0, target=(22, 23, 25), keep=0.6)
    acg("tarp", "Plastic015A", 1.5, target=(38, 82, 150), keep=0.6)
    acg_galv("lintel_galv"); acg_galv("scaffold", base=(160, 164, 168))
mp = os.path.join(OUT, "tex_meta.json")
old = json.load(open(mp)) if (ONLY and os.path.exists(mp)) else {}
old.update(META)
json.dump(old, open(mp, "w"), indent=1)
print("textures:", len(META))

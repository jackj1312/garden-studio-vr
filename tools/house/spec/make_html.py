import pickle, json, math, os, io, base64, html, sys
sys.path.insert(0, os.path.dirname(__file__))
from build_spec import lab2hex, EL, footprint
from PIL import Image
SCR = os.path.dirname(os.path.abspath(__file__))
D = pickle.load(open(SCR + "/spec.pkl", "rb")); S = D["spec"]; C = D["counts"]
REPO = "/Users/Jack/Library/Application Support/Claude/scratch-workspaces/cd50e9e5-31ba-4912-8a12-2cd5e6840a09/26acb63f-ba00-4d05-8613-053726bb4022/scratch-2026-10-30-84369f"
REFS = REPO + "/assets/sites/front-garden-model/refs"
OUT = os.path.expanduser("~/Desktop/23 Battle Road - First Build Spec")
os.makedirs(OUT, exist_ok=True)
E = html.escape
FINHEX = {f["id"]: f["colour_srgb"] for f in S["finishes"]}
FINNAME = {f["id"]: f["name"] for f in S["finishes"]}

def b64img(im, q=78):
    buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=q); return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
def crop(photo, box, h=110):
    P = Image.open(f"{REFS}/{photo}.jpg"); x0, y0, x1, y1 = box
    c = P.crop((int(x0 * P.width), int(y0 * P.height), int(x1 * P.width), int(y1 * P.height)))
    s = h / max(1, c.height); w = max(24, min(220, int(c.width * s)))
    return b64img(c.resize((w, h)))
def thumb(photo, box, w=150):
    P = Image.open(f"{REFS}/{photo}.jpg").convert("RGB"); from PIL import ImageDraw
    d = ImageDraw.Draw(P); x0, y0, x1, y1 = box
    d.rectangle((int(x0 * P.width), int(y0 * P.height), int(x1 * P.width), int(y1 * P.height)), outline=(255, 0, 200), width=6)
    P.thumbnail((w, int(w * 1.4))); return b64img(P, 70)

def sw(h, title=""):
    return f'<span class="sw" style="background:{h}" title="{E(title)}"></span>' if h else ""

# ------------------------------------------------------------------ SVG plans
SC = 58; X0, X1, Z0, Z1 = -0.6, 9.5, -8.75, 3.0
def P(x, z): return (round((x - X0) * SC, 1), round((z - Z0) * SC, 1))   # road (z+) at the bottom
CATCOL = {"furniture": "var(--it-furn)", "joinery": "var(--it-join)", "sanitary": "var(--it-san)", "appliance": "var(--it-app)", "soft_furnishing": "var(--it-soft)",
          "decor": "var(--it-dec)", "plant": "var(--it-plant)", "lighting": "var(--it-light)", "radiator": "var(--it-rad)", "fixture": "var(--it-join)", "fitting": "var(--it-join)"}
def plan_svg(v, storey, numbering):
    floor = 0.0 if storey == "ground" else 2.6755
    W = (X1 - X0) * SC; H = (Z1 - Z0) * SC
    o = [f'<svg viewBox="0 0 {W:.0f} {H:.0f}" class="plan" role="img" aria-label="{E(v)} {E(storey)} plan">']
    o.append(f'<rect x="0" y="0" width="{W:.0f}" height="{H:.0f}" class="pbg"/>')
    rooms = [r for r in S["versions"][v]["rooms"] if r["storey"] == storey]
    for r in rooms:
        pts = " ".join("%s,%s" % P(x, z) for x, z in r["polygon"])
        cls = "room new" if r.get("change") in ("new",) else "room"
        o.append(f'<polygon points="{pts}" class="{cls}"/>')
    # walls
    st = storey
    for e in EL[v]:
        if e["type"] != "wall" or e["meta"].get("storey") != st or e["meta"].get("stage_out") or e["id"].startswith("N21") or e["id"].startswith("AB-"): continue
        p = e["params"]; (sx, sz), (ex, ez) = p["start"], p["end"]
        th = sum(l["thickness"] for l in p["layers"]); L = math.hypot(ex - sx, ez - sz) or 1e-6
        ux, uz = (ex - sx) / L, (ez - sz) / L; nx, nz = -uz, ux
        quad = [(sx + nx * th / 2, sz + nz * th / 2), (ex + nx * th / 2, ez + nz * th / 2), (ex - nx * th / 2, ez - nz * th / 2), (sx - nx * th / 2, sz - nz * th / 2)]
        above = p["base"] > floor + 1.0
        o.append(f'<polygon points="{" ".join("%s,%s" % P(*q) for q in quad)}" class="{"wall above" if above else "wall"}"/>')
        for oid in e.get("openings", []):
            op = next((q for q in EL[v] if q["id"] == oid), None)
            if not op or op["meta"].get("stage_out"): continue
            a = op["params"]["offset"]; w = op["params"]["width"]
            g = [(sx + ux * a + nx * th / 2, sz + uz * a + nz * th / 2), (sx + ux * (a + w) + nx * th / 2, sz + uz * (a + w) + nz * th / 2),
                 (sx + ux * (a + w) - nx * th / 2, sz + uz * (a + w) - nz * th / 2), (sx + ux * a - nx * th / 2, sz + uz * a - nz * th / 2)]
            win = "window" in oid
            o.append(f'<polygon points="{" ".join("%s,%s" % P(*q) for q in g)}" class="{"opw" if win else "opd"}"/>')
            if win:
                m1 = P(sx + ux * a, sz + uz * a); m2 = P(sx + ux * (a + w), sz + uz * (a + w))
                o.append(f'<line x1="{m1[0]}" y1="{m1[1]}" x2="{m2[0]}" y2="{m2[1]}" class="winl"/>')
    # drawn fixtures (stair, breasts)
    for f in S["versions"][v]["drawn_fixtures"]:
        lo, hi = f["box_min"], f["box_max"]
        if not (lo[1] < floor + 2.0 and hi[1] > floor + 0.05): continue
        if f["element"] == "CH-stack": continue
        a = P(lo[0], lo[2]); b = P(hi[0], hi[2])
        o.append(f'<rect x="{a[0]}" y="{a[1]}" width="{b[0]-a[0]:.1f}" height="{b[1]-a[1]:.1f}" class="drawnfx"/>')
        if f["element"] == "ST-stair":
            for k in range(14):
                pass
    # exterior items on the ground floor
    if storey == "ground":
        for x in S["exterior"]["items"]:
            if v not in x["versions"]: continue
            lo, hi = x["box_min"], x["box_max"]
            if lo[1] > 1.6 or x["id"] in ("X-REAR-GARDEN", "X-NO21-WINDOWS", "X-NO21-PORCH") or hi[0] - lo[0] > 5: continue
            if not (X0 < lo[0] < X1 and Z0 < lo[2] < Z1): continue
            a = P(lo[0], lo[2]); b = P(hi[0], hi[2])
            o.append(f'<rect x="{a[0]}" y="{a[1]}" width="{max(2,b[0]-a[0]):.1f}" height="{max(2,b[1]-a[1]):.1f}" class="extit"><title>{E(x["id"])}: {E(x["name"])}</title></rect>')
    # items (rugs first so nothing hides under them; throws are drapes, numbered only)
    order = sorted(S["versions"][v]["items"], key=lambda d: 0 if any(k in d["type"] for k in ("rug", "mat", "runner")) else 1)
    for d in order:
        r = next(rr for rr in S["versions"][v]["rooms"] if rr["id"] == d["room"])
        if r["storey"] != storey or not any(d["size_mm"]) or "throw" in d["type"]: continue
        fp = footprint(d); n = numbering[d["id"]]
        col = CATCOL.get(d["category"], "var(--it-furn)")
        o.append(f'<polygon points="{" ".join("%s,%s" % P(*q) for q in fp)}" class="item" style="fill:{col}"><title>{n}. {E(d["type"])}</title></polygon>')
    for d in S["versions"][v]["items"]:
        r = next(rr for rr in S["versions"][v]["rooms"] if rr["id"] == d["room"])
        if r["storey"] != storey or not any(d["size_mm"]): continue
        n = numbering[d["id"]]; cx, cz = d["position_m"][0], d["position_m"][2]; q = P(cx, cz)
        small = d["category"] in ("decor", "lighting") or "cushion" in d["type"]
        rr_ = 5.2 if small else 7.2
        o.append(f'<circle cx="{q[0]}" cy="{q[1]}" r="{rr_}" class="{"num s" if small else "num"}"/><text x="{q[0]}" y="{q[1]+ (2.2 if small else 2.9)}" class="{"nt s" if small else "nt"}">{n}</text>')
    for r in rooms:
        xs = [p[0] for p in r["polygon"]]; zs = [p[1] for p in r["polygon"]]
        cx, cz = sum(xs) / len(xs), sum(zs) / len(zs)
        if r["id"] == "R-g-hall": cx, cz = 5.07, -2.6
        if r["id"] == "R-g-kitchen-living-dining-open-plan": cx, cz = 4.2, -7.55
        if r["id"] == "R-f-landing": cx, cz = 4.6, -1.5
        if r["id"] == "R-f-bedroom-3-rear-new": cx, cz = 5.4, -7.55
        q = P(cx, cz)
        nm = r["name"].split(" (")[0]
        if r["area_m2"] >= 2.0:
            o.append(f'<text x="{q[0]}" y="{q[1]-14}" class="rl">{E(nm)}</text><text x="{q[0]}" y="{q[1]-3}" class="ra">{r["area_m2"]} m²</text>')
    # compass + scale
    o.append(f'<g transform="translate({W-46},{H-58})"><circle r="18" class="cmp"/><path d="M 18 0 L -6 -5 L -6 5 Z" class="cmpn"/><text x="24" y="4" class="cl">N</text></g>')
    a = P(0, Z1 - 0.25); b = P(2, Z1 - 0.25)
    o.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" class="sbar"/><text x="{(a[0]+b[0])/2}" y="{a[1]-5}" class="cl" text-anchor="middle">2 m</text>')
    road = P(4.5, Z1 - 0.08)
    o.append(f'<text x="{road[0]}" y="{road[1]}" class="cl" text-anchor="middle">towards Battle Road (east) ↓</text>')
    gar = P(4.5, Z0 + 0.2)
    o.append(f'<text x="{gar[0]}" y="{gar[1]}" class="cl" text-anchor="middle">↑ back garden (west)</text>')
    o.append("</svg>")
    return "\n".join(o)

def mats_cell(m):
    out = []
    for k, val in m.items():
        if not val: continue
        h = FINHEX.get(val.split(" ")[0])
        out.append(f'{sw(h, FINNAME.get(val.split(" ")[0], val))}<span class="mk">{E(k)}:</span> {E(val)}')
    return "<br>".join(out) or "—"
def src_cell(a):
    if a["source"] == "polyhaven": return f'Poly Haven <code>{E(a["id"])}</code> (CC0)'
    if a["source"] == "elements": return f'drawn element <code>{E(a["element"][:34])}</code>'
    k = a.get("kind", ""); extra = {kk: vv for kk, vv in a.items() if kk not in ("source", "kind")}
    s = ", ".join(f"{kk} {vv}" for kk, vv in list(extra.items())[:4])
    return f'parametric <code>{E(k)}</code><span class="dim"> {E(s[:150])}</span>'

def item_table(v, storey, numbering):
    rows = []
    for d in S["versions"][v]["items"]:
        r = next(rr for rr in S["versions"][v]["rooms"] if rr["id"] == d["room"])
        if r["storey"] != storey: continue
        st = d["status"]; flag = ' <span class="tag p">to confirm</span>' if "Jack to confirm" in st else (' <span class="tag t">typical existing</span>' if "existing" in st else "")
        both = '' if d["in_both_versions"] else ' <span class="tag n">' + ("After only" if v == "after" else "Before only") + '</span>'
        x, y, z = d["position_m"]
        rows.append(f'<tr><td class="n">{numbering[d["id"]]}</td><td>{E(r["name"].split(" (")[0])}</td><td><b>{E(d["type"])}</b>{both}{flag}<div class="dim">{E(d["id"])} · x {x} z {z} y {y} · faces {d["yaw_deg"]}°</div></td>'
                    f'<td class="nw">{d["size_mm"][0]}×{d["size_mm"][1]}×{d["size_mm"][2]}</td><td>{mats_cell(d["materials"])}</td><td>{src_cell(d["asset"])}</td><td>{E(d["provenance"])}<div class="dim">{E(d["evidence"][:160])}</div></td></tr>')
    return ('<div class="scroll"><table class="t"><thead><tr><th>#</th><th>Room</th><th>Item</th><th>W×D×H mm</th><th>Finish / colour</th><th>Source</th><th>Provenance / why</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>")

numbering = {}
plans = {}
for v in ("before", "after"):
    numbering[v] = {}; n = 0
    for storey in ("ground", "first"):
        for d in S["versions"][v]["items"]:
            r = next(rr for rr in S["versions"][v]["rooms"] if rr["id"] == d["room"])
            if r["storey"] == storey:
                n += 1; numbering[v][d["id"]] = n
    for storey in ("ground", "first"):
        plans[(v, storey)] = (plan_svg(v, storey, numbering[v]), item_table(v, storey, numbering[v]))

# ------------------------------------------------------------------ room boards
def room_boards():
    seen = {}; out = []
    for v in ("before", "after"):
        for r in S["versions"][v]["rooms"]:
            seen.setdefault(r["id"], {"r": r, "v": []})["v"].append(v)
    for rid, info in seen.items():
        r = info["r"]; f = r["finishes"]
        tag = "Before + After" if len(info["v"]) == 2 else ("Before only" if info["v"] == ["before"] else "After only")
        fabrics = set()
        for v in info["v"]:
            for d in S["versions"][v]["items"]:
                if d["room"] == rid:
                    for val in d["materials"].values():
                        k = (val or "").split(" ")[0]
                        if k in FINHEX: fabrics.add(k)
        chips = "".join(f'<div class="chip">{sw(FINHEX.get(f[k].split(" ")[0]), "")}<div><div class="ck">{k}</div><div>{E(FINNAME.get(f[k].split(" ")[0], f[k]))}{(" · " + FINHEX[f[k].split(" ")[0]]) if f[k].split(" ")[0] in FINHEX else ""}</div><div class="dim">{E(f[k])}</div></div></div>' for k in ("floor", "walls", "ceiling", "skirting") if f.get(k))
        fab = "".join(f'<span class="mini">{sw(FINHEX[k])}{E(FINNAME[k].split(":")[0])}</span>' for k in sorted(fabrics) if not k.startswith("FIN-"))
        ceil = r["ceiling_y"] if isinstance(r["ceiling_y"], str) else f'{round(r["ceiling_y"] - r["floor_y"], 3)} m floor to ceiling'
        out.append(f'<div class="board"><div class="bh"><b>{E(r["name"])}</b><span class="tag">{tag}</span></div><div class="dim">{r["area_m2"]} m² · {E(r["storey"])} · {E(str(ceil))}</div>{chips}<div class="fabs">{fab}</div></div>')
    return "".join(out)

# ------------------------------------------------------------------ exterior
def ext_table():
    rows = []
    for m in S["exterior"]["materials"]:
        L, a, b = m["target_lab"]; h = lab2hex(L, a, b)
        wb = m.get("white_balanced_lab") or (m.get("secondary") or {}).get("white_balanced_lab")
        wbs = f'<div class="dim">white-balanced: {sw(lab2hex(*wb))} L {wb[0]} a {wb[1]} b {wb[2]}</div>' if wb else ""
        img = crop(m["target_photo"], m["region_frac"]); th = thumb(m["target_photo"], m["region_frac"])
        rows.append(f'<tr><td><b>{E(m["name"])}</b><div class="dim">{E(m["id"])}</div></td><td class="nw"><img src="{th}" class="th" alt="photo {E(m["target_photo"])} with the region marked"><img src="{img}" class="cr" alt="measured region"></td>'
                    f'<td>{sw(h)} <b>L {L} a {a} b {b}</b><div class="dim">L p10–p90 {m["target_L_spread_p10_p90"][0]}–{m["target_L_spread_p10_p90"][1]}</div>{wbs}</td><td>{E(m["target_photo"])}<div class="dim">{E(m["light"])}</div></td>'
                    f'<td class="dim">{E(m.get("asset", ""))} {E(m.get("unit_mm", ""))} {E(m.get("macro_variation", ""))} {E(m.get("reference", ""))}</td></tr>')
    return '<div class="scroll"><table class="t"><thead><tr><th>Material</th><th>Photo · region</th><th>Target (median Lab)</th><th>Photo · light</th><th>Asset / scale</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
def ext_items():
    rows = []
    for x in S["exterior"]["items"]:
        vv = "Before + After" if len(x["versions"]) == 2 else x["versions"][0].title() + " only"
        flag = ' <span class="tag p">to confirm</span>' if "confirm" in x["status"] else ""
        rows.append(f'<tr><td><b>{E(x["id"])}</b><div class="dim">{vv}</div></td><td>{E(x["name"])}{flag}</td><td class="nw">x {x["box_min"][0]}…{x["box_max"][0]}<br>y {x["box_min"][1]}…{x["box_max"][1]}<br>z {x["box_min"][2]}…{x["box_max"][2]}</td><td>{E(x["finish"])}</td><td>{E(x["provenance"])}<div class="dim">{E(x["evidence"][:200])}</div></td></tr>')
    return '<div class="scroll"><table class="t"><thead><tr><th>Item</th><th>What it is</th><th>Box (m)</th><th>Finish</th><th>Provenance</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
def dw_table(v):
    rows = []
    for o in S["versions"][v]["doors_windows"]:
        rows.append(f'<tr><td><b>{E(o["kind"])}</b>{" · external" if o["external"] else ""}<div class="dim">{E(o["id"][:44])}</div></td><td class="nw">{o["width_mm"]} wide<br>sill {o["sill_y"]} · head {o["head_y"]}</td><td>{E(o["frame_outside"])}</td><td>{E(o["frame_inside"])}</td><td>{E(o["glazing"])}<div class="dim">{E(o["ironmongery"])}</div><div class="dim">{E(o["surround"])}</div></td><td class="dim">{E(o["provenance"])}</td></tr>')
    return '<div class="scroll"><table class="t"><thead><tr><th>Opening</th><th>Size (m)</th><th>Outside</th><th>Inside</th><th>Glazing · ironmongery · surround</th><th>Provenance</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"

# ------------------------------------------------------------------ our Unreal still (ours, local)
ue = Image.open(REPO + "/renders/unreal/20261101-r10/S_20260719_102925.png"); ue.thumbnail((360, 480)); ue_b64 = b64img(ue, 75)
ph = Image.open(REFS + "/20260719_102925.jpg"); ph.thumbnail((360, 480)); ph_b64 = b64img(ph, 75)

fin_rows = "".join(f'<tr><td>{sw(f["colour_srgb"])}</td><td><b>{E(f["name"])}</b><div class="dim">{E(f["id"])} · {E(f["use"])}</div></td><td class="nw">{f["colour_srgb"]}<br>L {f["colour_lab"][0]} a {f["colour_lab"][1]} b {f["colour_lab"][2]}</td><td>{E(f["asset"].get("source",""))} <code>{E(str(f["asset"].get("id", f["asset"].get("kind",""))))}</code>{(" · fallback <code>"+E(f["asset"]["fallback"])+"</code>") if f["asset"].get("fallback") else ""}<div class="dim">{E(f["notes"])}</div></td><td>{E(f["status"])}</td></tr>' for f in S["finishes"])
gap_rows = "".join(f'<tr><td class="n">{g["id"]}</td><td>{E(g["gap"])}</td><td>{E(g["closes_it"])}</td><td><b>{E(g["target"])}</b></td></tr>' for g in S["unreal_look"]["gaps"])
tgt_rows = "".join(f'<li><b>{t["id"]}</b> <span class="dim">{E(t["area"])}</span> — {E(t["target"])}</li>' for t in S["unreal_look"]["targets"])
obs = "".join(f"<li>{E(x)}</li>" for x in S["unreal_look"]["benchmark"]["observed"])
dec = "".join(f'<div class="dec"><div class="dh"><span class="did">{d["id"]}</span><b>{E(d["title"])}</b></div><p>{E(d["question"])}</p><p class="rec">Recommended: {E(d["recommendation"])}</p></div>' for d in S["open_decisions"])
cams = "".join(f'<tr><td><b>{E(c["name"])}</b><div class="dim">{E(c["id"])} · {", ".join(c["versions"])}</div></td><td class="nw">{E(str(c["eye_m"]))}</td><td class="nw">{E(str(c["target_m"]))}</td><td>{E(str(c["lens_mm"]))}</td><td>{E(c["sun"])}</td><td class="dim">{E(c["purpose"])}</td></tr>' for c in S["cameras"])
faults = "".join(f'<li><b>{g["id"]}</b> {E(g["fault"])} <span class="dim">({E(g["photos"])})</span><br>→ {"<b>fix in the first build</b>" if g["fix_in_first_build"] else "leave as-is"}: {E(g["fix"])}</li>' for g in S["garden"]["known_faults"])
fac = lambda v: "".join(f"<li>{E(x)}</li>" for x in S["exterior"]["facades"][v])
paid = "".join(f'<li><b>{E(p["name"])}</b> — {E(p["what"])}; {E(p["price"])}. <span class="dim">{E(p["why"])}</span></li>' for p in S["paid_alternatives_not_used"])
walk = lambda v: " → ".join(f'{E(w[0])} <span class="dim">({w[1][0]}, {w[1][2]})</span>' for w in S["walkthrough"][v])

legend = "".join(f'<span class="lg"><span class="sw" style="background:{c}"></span>{E(k.replace("_"," "))}</span>' for k, c in [("furniture", "var(--it-furn)"), ("joinery / fixtures", "var(--it-join)"), ("sanitary", "var(--it-san)"), ("appliances", "var(--it-app)"), ("soft furnishings", "var(--it-soft)"), ("decor", "var(--it-dec)"), ("plants", "var(--it-plant)"), ("lighting", "var(--it-light)"), ("radiators", "var(--it-rad)")])

doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>First Build Spec</title>
<style>
:root{{--bg:#f7f5f1;--fg:#1f1d1a;--dim:#6d675f;--card:#ffffff;--line:#e2ddd5;--acc:#9a5b3c;--acc2:#5f7357;--room:#f3efe7;--roomnew:#e8f0e2;--wall:#4a4540;--pbg:#fbfaf7;
--it-furn:#c9a77c;--it-join:#b9b2a6;--it-san:#a9c7d6;--it-app:#9aa3ad;--it-soft:#e3cfb8;--it-dec:#d9b7a6;--it-plant:#8fb07c;--it-light:#f0d27a;--it-rad:#d8d8d8;--tagp:#f4e2c8;--tagn:#dfe9d6;--tagt:#e6e2f0}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#171614;--fg:#ece7df;--dim:#a39c91;--card:#211f1c;--line:#36322d;--acc:#e0946c;--acc2:#9fbd92;--room:#2a2723;--roomnew:#28331f;--wall:#d8d0c4;--pbg:#1d1b19;
--it-furn:#8a6e4b;--it-join:#6e685f;--it-san:#4f7385;--it-app:#5d6670;--it-soft:#8a7660;--it-dec:#8a6a5c;--it-plant:#557a45;--it-light:#a88d3c;--it-rad:#777;--tagp:#5a4527;--tagn:#3a4a30;--tagt:#3d3850}}}}
:root[data-theme="dark"]{{--bg:#171614;--fg:#ece7df;--dim:#a39c91;--card:#211f1c;--line:#36322d;--acc:#e0946c;--acc2:#9fbd92;--room:#2a2723;--roomnew:#28331f;--wall:#d8d0c4;--pbg:#1d1b19;
--it-furn:#8a6e4b;--it-join:#6e685f;--it-san:#4f7385;--it-app:#5d6670;--it-soft:#8a7660;--it-dec:#8a6a5c;--it-plant:#557a45;--it-light:#a88d3c;--it-rad:#777;--tagp:#5a4527;--tagn:#3a4a30;--tagt:#3d3850}}
*{{box-sizing:border-box}} html,body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:24px 16px 80px}} h1{{font-size:30px;line-height:1.15;margin:8px 0 4px}} h2{{font-size:22px;margin:44px 0 10px;padding-top:12px;border-top:1px solid var(--line)}} h3{{font-size:17px;margin:24px 0 8px}}
.dim{{color:var(--dim);font-size:13px}} code{{font:12px ui-monospace,Menlo,monospace;background:var(--line);padding:1px 4px;border-radius:4px}}
nav{{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0}} nav a{{font-size:13px;padding:4px 10px;border:1px solid var(--line);border-radius:999px;color:var(--fg);text-decoration:none;background:var(--card)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}} .kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}} .kpi b{{font-size:24px;display:block}}
.rules li{{margin:6px 0}} .scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:10px;background:var(--card)}}
table.t{{border-collapse:collapse;width:100%;font-size:13.5px;min-width:820px}} .t th{{text-align:left;font-weight:600;background:var(--room);position:sticky;top:0}} .t td,.t th{{padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}}
.n{{font-weight:700;text-align:center}} .nw{{white-space:nowrap}} .mk{{color:var(--dim)}}
.sw{{display:inline-block;width:16px;height:16px;border-radius:4px;border:1px solid rgba(0,0,0,.25);vertical-align:-3px;margin-right:5px}}
.tag{{font-size:11px;padding:1px 7px;border-radius:999px;background:var(--line);margin-left:6px;white-space:nowrap}} .tag.p{{background:var(--tagp)}} .tag.n{{background:var(--tagn)}} .tag.t{{background:var(--tagt)}}
.planwrap{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px;margin:10px 0}} svg.plan{{width:100%;height:auto;display:block}}
.pbg{{fill:var(--pbg)}} .room{{fill:var(--room);stroke:none}} .room.new{{fill:var(--roomnew)}} .wall{{fill:var(--wall)}} .wall.above{{fill:none;stroke:var(--wall);stroke-dasharray:4 3;stroke-width:1}}
.opd{{fill:var(--pbg)}} .opw{{fill:var(--pbg)}} .winl{{stroke:#5a8fb0;stroke-width:2}} .drawnfx{{fill:none;stroke:var(--dim);stroke-width:1;stroke-dasharray:2 2}} .extit{{fill:none;stroke:var(--acc);stroke-width:1.2;stroke-dasharray:3 2}}
.item{{stroke:rgba(0,0,0,.45);stroke-width:.8;opacity:.92}} .num{{fill:var(--fg);}} .num.s{{fill:var(--dim)}} .nt{{fill:var(--bg);font:700 8.5px sans-serif;text-anchor:middle}} .nt.s{{font-size:6.5px}}
.rl{{fill:var(--fg);font:600 11px sans-serif;text-anchor:middle;opacity:.8}} .ra{{fill:var(--dim);font:10px sans-serif;text-anchor:middle}} .cl{{fill:var(--dim);font:11px sans-serif}} .cmp{{fill:none;stroke:var(--dim)}} .cmpn{{fill:var(--acc)}} .sbar{{stroke:var(--fg);stroke-width:3}}
.lg{{font-size:12.5px;margin-right:12px;white-space:nowrap;display:inline-block}}
.boards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}} .board{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}} .bh{{display:flex;justify-content:space-between;gap:6px;align-items:baseline}}
.chip{{display:flex;gap:8px;align-items:flex-start;margin-top:8px;font-size:13px}} .chip .sw{{width:30px;height:30px;flex:none}} .ck{{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.04em}} .fabs{{margin-top:8px}} .mini{{font-size:12px;display:inline-block;margin:3px 8px 0 0}}
img.th{{width:64px;height:auto;border-radius:4px;vertical-align:top;margin-right:6px}} img.cr{{height:72px;width:auto;border-radius:4px;vertical-align:top;max-width:150px;object-fit:cover}}
.dec{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:10px 0}} .dh{{display:flex;gap:10px;align-items:baseline}} .did{{font-weight:700;color:var(--acc)}} .rec{{color:var(--acc2);font-weight:600;margin:4px 0 0}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:740px}} .pair img{{width:100%;border-radius:8px;display:block}} .pair figcaption{{font-size:12px;color:var(--dim)}}
.note{{background:var(--card);border-left:4px solid var(--acc);padding:10px 14px;border-radius:6px;margin:12px 0}}
@media (max-width:640px){{h1{{font-size:24px}} .pair{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="dim">23 Battle Road, Hailsham · WORKFLOW gate G2b · spec v1.0 · 1 Nov 2026</div>
<h1>First Build Spec</h1>
<p>Everything the first build must contain, for the homeowner view: <b>Before</b> (the house today) and <b>After</b> (approved scheme 4915.2B finished, porch as built), in your real front garden. The same schedule drives the browser/Quest viewer and the furnished Unreal render. The machine-readable copy is <code>assets/sites/house/spec/spec_v1.json</code> (format: <code>SCHEMA.md</code> beside it).</p>
<div class="note"><b>Status: draft for your sign-off.</b> Ten decisions are at the bottom, each with a recommendation. Once you sign off, the build follows this exactly; nothing changes except through your change request.</div>
<nav><a href="#waste">How this stops waste</a><a href="#plans-before">Plans · Before</a><a href="#plans-after">Plans · After</a><a href="#boards">Room finishes</a><a href="#finishes">Finish table</a><a href="#doors">Doors &amp; windows</a><a href="#exterior">Exterior &amp; garden</a><a href="#light">Light &amp; cameras</a><a href="#unreal">Unreal look</a><a href="#accept">Acceptance</a><a href="#decisions">Decisions</a></nav>
<div class="cards">
<div class="kpi"><b>{C["before"]["rooms"]} / {C["after"]["rooms"]}</b><span class="dim">rooms Before / After</span></div>
<div class="kpi"><b>{C["before"]["items"]} / {C["after"]["items"]}</b><span class="dim">items placed Before / After ({C["unique_item_ids"]} unique)</span></div>
<div class="kpi"><b>{C["finishes"]}</b><span class="dim">finishes with colour values</span></div>
<div class="kpi"><b>{C["exterior_materials"]}</b><span class="dim">exterior colours measured from your photos</span></div>
<div class="kpi"><b>{C["exterior_items"]}</b><span class="dim">exterior items placed</span></div>
<div class="kpi"><b>{C["before"]["openings"]} / {C["after"]["openings"]}</b><span class="dim">doors &amp; windows specified</span></div>
</div>

<h2 id="waste">How this stops waste</h2>
<ol class="rules">
<li><b>Spec before build.</b> Every room, fixture, fitting, piece of furniture, finish and colour is written down here first, with its size, exact position, facing and source. You sign it off through the questions form before anything is built or rented (CORRECTIONS 177).</li>
<li><b>The build never improvises.</b> If something is not in this spec, the build stops and asks you, instead of guessing and fixing it later.</li>
<li><b>Colours are measured, not judged by eye.</b> Every existing surface has a target taken from a marked region of one of your photos; the render must land within ΔE 5 of it (CORRECTIONS 165, 176).</li>
<li><b>An automatic check runs before any judge.</b> Every item present, within 20 mm, the right asset and finish; nothing floating, clashing or in a door's swing. This spec already passes its own layout check: 0 overlaps, 0 items outside their room, 0 items in a door swing.</li>
<li><b>Two rounds, then you.</b> One judge round and one fix round per deliverable. A result that misses the spec goes back to the spec, not into trial and error. Cloud runs only against a signed-off spec, with a cost cap.</li>
<li><b>Unchanged rooms are identical in Before and After</b>, so the comparison shows the building work and nothing else.</li>
</ol>

<h2 id="plans-before">Plans · Before (the house today)</h2>
<p class="dim">Drawn from the elements' own coordinates (x along the front, 0 = party wall; road at the bottom). Every numbered shape is an item at its true size and position; the dashed orange boxes are outside items, the dotted outlines drawn fixtures (stair, chimney breasts). {legend}</p>
<h3>Ground floor</h3><div class="planwrap">{plans[("before","ground")][0]}</div>{plans[("before","ground")][1]}
<h3>First floor</h3><div class="planwrap">{plans[("before","first")][0]}</div>{plans[("before","first")][1]}
<h2 id="plans-after">Plans · After (approved 4915.2B finished)</h2>
<p class="dim">New rooms are tinted green. The living room's rear wall is open below the beam (2.288 m), so the living room and the kitchen-diner are one space.</p>
<h3>Ground floor</h3><div class="planwrap">{plans[("after","ground")][0]}</div>{plans[("after","ground")][1]}
<h3>First floor</h3><div class="planwrap">{plans[("after","first")][0]}</div>{plans[("after","first")][1]}

<h2 id="boards">Room-by-room finish boards</h2>
<p>Style: modern warm. Oak floors, warm-white walls, linen and boucle, terracotta and sage accents, black and brushed-brass metalwork.</p>
<div class="boards">{room_boards()}</div>
<h2 id="finishes">Finish table</h2>
<div class="scroll"><table class="t"><thead><tr><th></th><th>Finish</th><th>Colour</th><th>Texture / asset</th><th>Status</th></tr></thead><tbody>{fin_rows}</tbody></table></div>

<h2 id="doors">Doors &amp; windows</h2>
<p class="dim">Before: your five owner windows anthracite (front four plus the north bathroom), everything else white, as the photos show. After: decision D3. The utility door opens into the utility (handing override; the model's derived swing crossed the island stools).</p>
<h3>Before</h3>{dw_table("before")}<h3>After</h3>{dw_table("after")}

<h2 id="exterior">Exterior &amp; garden</h2>
<h3>Measured colour targets (from your photos)</h3>
<p class="dim">Median CIE Lab of the marked region (the pink box on the small photo). Photos taken in shade carry a blue cast; where a white object in the same photo allowed it, a white-balanced value is given too. The check compares the render through the same camera.</p>
{ext_table()}
<h3>Façades</h3><p><b>Before</b></p><ul>{fac("before")}</ul><p><b>After</b></p><ul>{fac("after")}</ul>
<h3>Exterior items</h3>{ext_items()}
<h3>Front garden</h3>
<p>Taken from the garden model as it is ({E(S["garden"]["source"])}). Frame: {E(S["garden"]["frame_transform"])}.</p>
<p class="dim">Kept: {E("; ".join(S["garden"]["keep_as_is"]))}. Left out: {E("; ".join(S["garden"]["exclude"]))}.</p>
<h3>Known garden faults</h3><ul>{faults}</ul>

<h2 id="light">Light, cameras and the walk</h2>
<ul><li><b>Filmed sun</b> (front stills, matched checks): bearing 138° (SE), 22° up, about 10:00 BST in late September, 100,000 lux, 5600 K.</li>
<li><b>Afternoon sun</b> (rear and interior stills, your “sunny afternoon”): bearing 234° (SW), 25° up, 16:00 BST, 5000 K. It shines straight into the new kitchen-diner through the bi-folds.</li>
<li>{E(S["lighting"]["sky"])}</li><li>Colour check light: {E(S["lighting"]["check_light"])}</li><li>Lamps: {E(S["lighting"]["lamps"]["day_stills"])}; interactive: {E(S["lighting"]["lamps"]["interactive"])}</li></ul>
<div class="scroll"><table class="t"><thead><tr><th>Camera</th><th>Eye (x, y, z)</th><th>Looks at</th><th>Lens mm</th><th>Sun</th><th>Purpose</th></tr></thead><tbody>{cams}</tbody></table></div>
<p><b>Walk, Before:</b> {walk("before")}</p><p><b>Walk, After:</b> {walk("after")}</p>
<p class="dim">Eye height 1.60 m, 18 mm lens, 0.9 m/s, turns ≤ 25°/s, 1 s ease in and out, motion blur 0.5. Upstairs is a separate shot.</p>

<h2 id="unreal">Unreal look specification: closing the Airbnb gap</h2>
<p><b>What the benchmark is, from the primary source.</b> Simba's walkable Airbnb (post of 11 Oct 2026, 39.75 s, 1918×1080) was modelled by Claude in Blender from a floor plan and two photos, then lit in Unreal Engine 5.8. I read the post data and the full-resolution poster frame. The author's article needs a login (it returns HTTP 402 here), so its points come from BENCHMARKS.md section 1, written from the 31 Oct reading. I didn't download the video itself, because a download needs your permission; it was stepped through on 31 Oct. {E(S["unreal_look"]["benchmark"]["hud"])}</p>
<h3>What makes it look the way it does</h3><ul>{obs}</ul>
<h3>Our latest Unreal still next to your photo</h3>
<figure class="pair"><div><img src="{ph_b64}" alt="Jack's photo 20260719_102925"><figcaption>Your photo 20260719_102925</figcaption></div><div><img src="{ue_b64}" alt="Unreal r10 render, same camera"><figcaption>Unreal r10, same camera (r9 sheet: renders/unreal/20261101-r9/sheet.jpg)</figcaption></div></figure>
<p class="dim">{E(S["unreal_look"]["current"])}</p>
<h3>Each gap and what closes it</h3>
<div class="scroll"><table class="t"><thead><tr><th>#</th><th>Gap seen in our r9/r10 renders</th><th>Setting or asset that closes it</th><th>Testable target</th></tr></thead><tbody>{gap_rows}</tbody></table></div>
<h3>Numbered look targets</h3><ul class="rules">{tgt_rows}</ul>
<h3>Paid alternatives (not used; free assets only)</h3><ul>{paid}</ul>

<h2 id="accept">Acceptance (checked automatically before any judge)</h2>
<ul><li>Every item in the schedule is present once (GLB extra <code>spec_id</code>), none extra.</li><li>Position within <b>20 mm</b>, rotation within 2°, size ±10 mm (parametric) or ±3 % (library, fitted uniformly).</li>
<li>Exterior colours within <b>ΔE 5</b> of their photo target after one exposure offset per photo; L spread ratio 0.7–1.3. Interior finishes ΔE 5 to the swatch under the neutral check light.</li>
<li>Nothing floats (gap ≤ 3 mm), nothing clashes (clash check 0), every door opens fully without hitting an item.</li><li>Styling counts per room pass (targets T-S1 to T-S5).</li></ul>

<h2 id="decisions">Open decisions for you</h2>
<p>These are the only choices the evidence couldn't make. Everything else is decided. They'll come to you as one questions form.</p>
{dec}
<p class="dim" style="margin-top:40px">Your photos are embedded here for your own use only; this page is local and was not uploaded anywhere. Generated from spec_v1.json.</p>
</main></body></html>"""
open(OUT + "/First Build Spec.html", "w").write(doc)
print("html", len(doc) // 1024, "KB")

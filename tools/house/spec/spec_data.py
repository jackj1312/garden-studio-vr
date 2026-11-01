# Hand-authored design data for 23 Battle Road spec v1 (frame: elements' "viewer" frame).
# x = along the front towards the north flank (0 = party-wall centre line), z = minus depth into the house
# (0 = outside face of the main front wall; negative = towards the back garden; positive = towards the road),
# y = up from ground-floor FFL. First-floor FFL = 2.6755. Yaw (deg) about +Y, the direction the item's FRONT faces:
# 0 -> -z (back garden, west), 90 -> -x (party wall, south), 180 -> +z (road, east), -90 -> +x (north flank).
# Positions are the centre of the item's footprint at its base (floor items: y = floor; wall items: y = bottom).
GF, FF = 0.0, 2.6755
B, A, BA = ["before"], ["after"], ["before", "after"]

ITEMS = []
def it(id, ver, room, cat, typ, asset, size, pos, yaw, mats, prov, why, status="fixed"):
    ITEMS.append(dict(id=id, versions=ver, room=room, category=cat, type=typ, asset=asset,
                      size_mm=[int(round(s)) for s in size], position_m=[round(p, 3) for p in pos],
                      yaw_deg=yaw, materials=mats, provenance=prov, evidence=why, status=status))

def ph(i, fit="uniform", **k):        # Poly Haven model (CC0), fitted to the box
    d = {"source": "polyhaven", "id": i, "url": f"https://polyhaven.com/a/{i}", "licence": "CC0", "fit": fit}
    d.update(k); return d
def par(kind, **k):                    # parametric: built by the build script from these numbers
    d = {"source": "parametric", "kind": kind}; d.update(k); return d
def drawn(el, **k):
    d = {"source": "elements", "element": el, "note": "geometry and position as in the elements/GLB; finish from this spec"}
    d.update(k); return d

P = "proposed — Jack to confirm"
TYP = "typical (not surveyed): placed by the design rules in this spec"

# ----------------------------------------------------------------- shared parametric definitions
CUSH = lambda fab: par("cushion", corner_bulge_mm=25, seam="piped", fabric=fab)
CURT = lambda w: par("curtain_pair", pole="matt black 25 mm, finials", pole_width_mm=w, heading="double pinch pleat",
                     fullness=2.0, stacked_each_side_mm=300, drop_to_mm_above_floor=10, lining="blackout off-white",
                     fabric="FAB-CURTAIN")
RAD = lambda w: par("radiator_panel", type="single panel convector K1, flat front", colour="RAL 9016 satin",
                    valves="matt black TRV left + lockshield right", wall_gap_mm=50, width_mm=w)
PEND_DRUM = par("pendant_drum", shade="FAB-CURTAIN linen drum 450 dia x 250", flex="black braided", rose="matt black 100 dia",
                lamp="2700 K LED 806 lm", drop_mm=600)
FLOORLAMP = par("floor_lamp", base="matt black tripod", shade="linen drum 400 dia x 300", height_mm=1550, lamp="2700 K 806 lm")
TABLELAMP = par("table_lamp", base="matt ceramic CER-CREAM 160 dia", shade="linen 300 dia x 220", height_mm=480, lamp="2700 K 470 lm")
ART = lambda motif: par("framed_print", frame="oak 20 mm, white mount 50 mm", glazing="non-reflective acrylic", motif=motif)

# ================================================================= GROUND FLOOR, both versions
# ---- Porch (as built; identical in Before and After)
it("POR-BENCH", BA, "R-g-porch-vaulted", "furniture", "shoe bench", par("bench_box", top="WOOD-OAK-FURN 30 mm", body="slatted oak shelf"),
   [900, 350, 450], [5.16, GF, 0.85], 90, {"all": "WOOD-OAK-FURN"}, "typical", TYP + "; clear of the door sweep (hinge 3.119, 1.306).")
it("POR-HOOKS", BA, "R-g-porch-vaulted", "fitting", "coat hook rail (4 hooks) with 2 coats", par("hook_rail", rail="oak 600x90x20", hooks="matt black", coats=2),
   [600, 60, 90], [5.31, 1.60, 0.85], 90, {"rail": "WOOD-OAK-FURN", "hooks": "METAL-BLACK"}, "typical", TYP)
it("POR-MAT", BA, "R-g-porch-vaulted", "soft_furnishing", "coir door mat", par("rug", pile="coir", edge="none"),
   [600, 900, 15], [3.70, GF, 0.94], 0, {"all": "RUG-JUTE"}, "typical", TYP)
it("POR-LIGHT", BA, "R-g-porch-vaulted", "lighting", "flush ceiling light on the vault", par("flush_disc", dia_mm=300, diffuser="opal", lamp="2700 K 1000 lm", place="ray-cast up to the vault soffit at this x,z"),
   [300, 300, 60], [4.33, 2.40, 0.35], 0, {"all": "METAL-BLACK"}, "typical", TYP)
# ---- Hall (identical)
it("HAL-RUNNER", BA, "R-g-hall", "soft_furnishing", "runner rug", par("rug", pile="flat-weave wool, cream with charcoal border stripe"),
   [700, 2200, 10], [5.07, GF, -3.20], 0, {"all": "RUG-WOOL"}, "typical", TYP)
it("HAL-PEND", BA, "R-g-hall", "lighting", "pendant", PEND_DRUM, [450, 450, 250], [4.45, 2.43, -0.70], 0, {"shade": "FAB-CURTAIN"}, "typical", TYP)
it("HAL-RAD", BA, "R-g-hall", "radiator", "radiator", RAD(450), [450, 50, 600], [5.08, 0.15, -0.35], 0, {"all": "RAL9016"}, "typical", TYP + "; east of the front door hinge (4.766, -0.158).")
it("HAL-ART-1", BA, "R-g-hall", "decor", "framed print", ART("botanical line drawing"), [500, 25, 700], [5.48, 1.15, -3.10], 90, {"frame": "WOOD-OAK-FURN"}, "typical", TYP)
it("HAL-ART-2", BA, "R-g-hall", "decor", "framed print", ART("abstract landscape, warm neutrals"), [500, 25, 700], [5.48, 1.15, -3.85], 90, {"frame": "WOOD-OAK-FURN"}, "typical", TYP)

# ---- Living (front left) — identical furniture in Before and After (After: the rear wall is opened below 2.288)
it("LIV-SOFA", BA, "R-g-living", "furniture", "3-seat sofa", par("sofa", seats=3, arms="square 150", legs="oak 120 tapered", back_cushions=3, seat_cushions=3, upholstery="FAB-SOFA"),
   [1990, 900, 780], [3.085, GF, -2.55], 90, {"upholstery": "FAB-SOFA", "legs": "WOOD-OAK-FURN"}, "typical",
   TYP + "; against the hall wall facing the chimney breast; clear of the living door leaf (hinge 3.605, -1.286, opens along z -1.286).")
for n, (dz, fab) in enumerate([(-1.95, "FAB-CUSH-SAGE"), (-2.35, "FAB-CUSH-TERRA"), (-2.75, "FAB-CUSH-CREAM"), (-3.15, "FAB-CUSH-SAGE")], 1):
    it(f"LIV-CUSH-{n}", BA, "R-g-living", "soft_furnishing", "cushion 450", CUSH(fab), [450, 150, 450], [3.38, 0.45, dz], 90, {"all": fab}, "typical", "styling rule S1 (sofa: 3+ cushions)")
it("LIV-THROW", BA, "R-g-living", "soft_furnishing", "knitted throw over the south arm", par("throw_drape", drape="over arm and seat front"), [1300, 1700, 8], [3.10, 0.45, -3.40], 90, {"all": "FAB-THROW"}, "typical", "styling rule S1")
it("LIV-COFFEE", BA, "R-g-living", "furniture", "coffee table", ph("modern_coffee_table_01"), [1202, 600, 390], [1.80, GF, -2.35], 90, {"all": "as asset"}, "typical", TYP)
it("LIV-RUG", BA, "R-g-living", "soft_furnishing", "rug", par("rug", pile="low wool, cream with fine charcoal border"), [1700, 2400, 12], [1.85, GF, -2.45], 0, {"all": "RUG-WOOL"}, "typical", "styling rule S1 (rug)")
it("LIV-STOVE", BA, "R-g-living", "fitting", "wood-burning stove in the fireplace recess", par("stove", body="matt black steel", door="glass with log glow off by day", flue="into the recess (hidden)"),
   [450, 380, 600], [0.36, 0.02, -2.31], -90, {"all": "METAL-BLACK"}, "typical", "recess drawn x 0.15-0.56, z -2.04..-2.58, open to 0.835 (4915.2B); stove type " + P, status=P)
it("LIV-HEARTH", BA, "R-g-living", "fitting", "slate hearth", par("slab", edge="eased"), [1100, 850, 20], [0.575, GF, -2.31], -90, {"all": "STONE-SLATE"}, "typical", TYP)
it("LIV-TV", BA, "R-g-living", "appliance", "55-inch TV, wall-mounted on the chimney breast", par("tv", screen="black glass, off, reflective", bezel="6 mm dark aluminium"),
   [1230, 30, 710], [0.575, 1.10, -2.31], -90, {"all": "TV-BLACK"}, "typical", TYP)
it("LIV-SHELF", BA, "R-g-living", "joinery", "alcove cupboard with 4 oak shelves (rear alcove)", par("alcove_unit", cupboard_h_mm=900, cupboard="putty painted shaker doors x2", shelves_y_m=[1.25, 1.60, 1.95], shelf_t_mm=30, shelf_d_mm=300),
   [1300, 380, 2000], [0.355, GF, -3.68], -90, {"cupboard": "KIT-FRONT", "shelves": "WOOD-OAK-FURN", "top": "WOOD-OAK-FURN"}, "typical", "alcove drawn z -2.995..-4.36 (4915.2B)")
it("LIV-ARM", BA, "R-g-living", "furniture", "armchair", par("armchair", frame="oak", upholstery="FAB-SOFA", style="low lounge, rounded back"),
   [760, 820, 760], [1.25, GF, -3.70], -135, {"upholstery": "FAB-SOFA", "frame": "WOOD-OAK-FURN"}, "typical", TYP)
it("LIV-FLAMP", BA, "R-g-living", "lighting", "floor lamp", FLOORLAMP, [400, 400, 1550], [3.25, GF, -3.85], 0, {"base": "METAL-BLACK", "shade": "FAB-CURTAIN"}, "typical", "styling rule S1 (2 lamps)")
it("LIV-TLAMP", BA, "R-g-living", "lighting", "table lamp on the alcove cupboard", TABLELAMP, [300, 300, 480], [0.355, 0.93, -4.05], -90, {"base": "CER-CREAM", "shade": "FAB-CURTAIN"}, "typical", "styling rule S1 (2 lamps)")
it("LIV-PEND", BA, "R-g-living", "lighting", "pendant", PEND_DRUM, [450, 450, 250], [1.86, 2.43, -2.33], 0, {"shade": "FAB-CURTAIN"}, "typical", TYP)
it("LIV-CURT", BA, "R-g-living", "soft_furnishing", "curtains on the front window", CURT(2000), [2000, 120, 2240], [1.888, 0.01, -0.36], 0, {"fabric": "FAB-CURTAIN", "pole": "METAL-BLACK"}, "typical", "styling rule S1 (window dressing); window O-G-front-living-front-window x 1.155-2.62")
it("LIV-RAD", BA, "R-g-living", "radiator", "radiator under the front window", RAD(1200), [1200, 50, 600], [1.888, 0.15, -0.375], 0, {"all": "RAL9016"}, "typical", TYP)
it("LIV-ART-1", BA, "R-g-living", "decor", "framed print above sofa", ART("large leaf study, sage on cream"), [500, 25, 700], [3.545, 1.20, -2.05], 90, {"frame": "WOOD-OAK-FURN"}, "typical", "styling rule S1 (2 artworks)")
it("LIV-ART-2", BA, "R-g-living", "decor", "framed print above sofa", ph("hanging_picture_frame_02", fit="scale_to_box"), [500, 25, 700], [3.545, 1.20, -3.05], 90, {"frame": "WOOD-OAK-FURN"}, "typical", "styling rule S1")
it("LIV-PLANT-1", BA, "R-g-living", "plant", "tall potted plant (front alcove)", ph("potted_plant_01"), [589, 637, 1351], [0.50, GF, -0.95], 0, {"pot": "CER-CREAM"}, "typical", "styling rule S1 (plant >= 0.6 m)")
it("LIV-PLANT-2", BA, "R-g-living", "plant", "small succulent on shelf", ph("potted_plant_04"), [170, 186, 268], [0.36, 1.28, -3.40], -90, {}, "typical", "styling")
it("LIV-DEC-1", BA, "R-g-living", "decor", "book stack on coffee table", ph("book_encyclopedia_set_01", fit="uniform", scale_note="lay 3 books flat"), [300, 220, 90], [1.80, 0.39, -2.10], 90, {}, "typical", "styling rule S1 (5 decor items)")
it("LIV-DEC-2", BA, "R-g-living", "decor", "ceramic vase with dried stems", ph("ceramic_vase_02"), [220, 221, 309], [1.80, 0.39, -2.62], 90, {"glaze": "CER-CREAM"}, "typical", "styling")
it("LIV-DEC-3", BA, "R-g-living", "decor", "wooden bowl", ph("wooden_bowl_01"), [313, 309, 94], [0.36, 1.28, -3.05], -90, {}, "typical", "styling")
it("LIV-DEC-4", BA, "R-g-living", "decor", "books on shelf (row of 14)", ph("decorative_book_set_01", fit="scale_to_box"), [700, 220, 260], [0.36, 1.63, -3.60], -90, {}, "typical", "styling")
it("LIV-DEC-5", BA, "R-g-living", "decor", "candlestick", ph("wooden_candlestick"), [98, 100, 220], [0.36, 1.98, -3.20], -90, {}, "typical", "styling")
it("LIV-DEC-6", BA, "R-g-living", "decor", "standing photo frame", ph("standing_picture_frame_01"), [201, 100, 250], [0.36, 1.98, -4.00], -90, {}, "typical", "styling")

# ---- Sitting room / snug (front right, bay) — identical in Before and After
it("SIT-SOFA", BA, "R-g-sitting", "furniture", "2-seat sofa (loveseat)", par("sofa", seats=2, arms="square 150", legs="oak 120 tapered", upholstery="FAB-SOFA"),
   [1600, 900, 780], [7.15, GF, -0.65], 180, {"upholstery": "FAB-SOFA", "legs": "WOOD-OAK-FURN"}, "typical", TYP + "; clear of the door leaf (hinge 5.492, -1.035, opens along z -1.035 to x 6.23).")
for n, (dx, fab) in enumerate([(6.70, "FAB-CUSH-TERRA"), (7.15, "FAB-CUSH-CREAM"), (7.60, "FAB-CUSH-SAGE")], 1):
    it(f"SIT-CUSH-{n}", BA, "R-g-sitting", "soft_furnishing", "cushion 450", CUSH(fab), [450, 150, 450], [dx, 0.45, -0.95], 180, {"all": fab}, "typical", "styling rule S1")
it("SIT-THROW", BA, "R-g-sitting", "soft_furnishing", "knitted throw", par("throw_drape", drape="over east arm"), [1300, 1700, 8], [7.85, 0.45, -0.65], 180, {"all": "FAB-THROW"}, "typical", "styling rule S1")
it("SIT-BOOKCASE", BA, "R-g-sitting", "joinery", "bookcase in the 1045 recess", par("bookcase", shelves=5, carcass="painted", back="painted"),
   [1000, 330, 1800], [8.49, GF, -0.485], 90, {"all": "KIT-FRONT"}, "typical", "recess drawn z -0.993..0.023, back face x 8.655 (4915.1/2B)")
it("SIT-ARM", BA, "R-g-sitting", "furniture", "armchair in the bay corner", par("armchair", frame="oak", upholstery="FAB-CUSH-SAGE", style="low lounge"),
   [760, 820, 760], [6.45, GF, 1.55], -45, {"upholstery": "FAB-CUSH-SAGE", "frame": "WOOD-OAK-FURN"}, "typical", TYP)
it("SIT-SIDE", BA, "R-g-sitting", "furniture", "side table", ph("side_table_01"), [550, 450, 551], [7.20, GF, 2.05], 180, {}, "typical", TYP)
it("SIT-STOOL", BA, "R-g-sitting", "furniture", "small round wooden table", ph("WoodenTable_02"), [301, 301, 418], [7.15, GF, 0.20], 0, {}, "typical", TYP)
it("SIT-RUG", BA, "R-g-sitting", "soft_furnishing", "rug", par("rug", pile="jute-wool blend"), [1600, 2000, 12], [7.15, GF, 0.55], 0, {"all": "RUG-JUTE"}, "typical", "styling rule S1")
it("SIT-FLAMP", BA, "R-g-sitting", "lighting", "floor lamp", FLOORLAMP, [400, 400, 1550], [5.85, GF, 2.20], 0, {"base": "METAL-BLACK"}, "typical", "styling rule S1 (2 lamps)")
it("SIT-TLAMP", BA, "R-g-sitting", "lighting", "table lamp on side table", TABLELAMP, [300, 300, 480], [7.20, 0.551, 2.05], 180, {"base": "CER-CREAM"}, "typical", "styling rule S1 (2 lamps)")
it("SIT-PEND", BA, "R-g-sitting", "lighting", "pendant", PEND_DRUM, [450, 450, 250], [7.145, 2.43, 0.62], 0, {"shade": "FAB-CURTAIN"}, "typical", TYP)
it("SIT-CURT", BA, "R-g-sitting", "soft_furnishing", "curtains on the bay window", CURT(2000), [2000, 120, 2240], [7.158, 0.01, 2.30], 180, {"fabric": "FAB-CURTAIN"}, "typical", "window O-G-bayfront-sitting-front-window x 6.44-7.875")
it("SIT-RAD", BA, "R-g-sitting", "radiator", "radiator under the window", RAD(1200), [1200, 50, 600], [7.158, 0.15, 2.285], 180, {"all": "RAL9016"}, "typical", TYP)
it("SIT-PLANT", BA, "R-g-sitting", "plant", "tall potted plant", ph("potted_plant_01"), [589, 637, 1351], [8.35, GF, 2.00], 180, {}, "typical", "styling rule S1")
it("SIT-ART-1", BA, "R-g-sitting", "decor", "framed print", ART("coastal abstract, warm grey"), [500, 25, 700], [6.75, 1.20, -1.11], 180, {"frame": "WOOD-OAK-FURN"}, "typical", "styling rule S1")
it("SIT-ART-2", BA, "R-g-sitting", "decor", "framed print", ph("hanging_picture_frame_03", fit="scale_to_box"), [385, 32, 502], [7.55, 1.30, -1.11], 180, {}, "typical", "styling rule S1")
it("SIT-DEC-1", BA, "R-g-sitting", "decor", "books on bookcase", ph("decorative_book_set_01", fit="scale_to_box"), [800, 220, 260], [8.49, 1.10, -0.485], 90, {}, "typical", "styling")
it("SIT-DEC-2", BA, "R-g-sitting", "decor", "vase", ph("ceramic_vase_01"), [205, 206, 401], [8.49, 1.46, -0.20], 90, {}, "typical", "styling")
it("SIT-DEC-3", BA, "R-g-sitting", "decor", "wicker basket", ph("wicker_basket_02"), [375, 271, 218], [8.49, 0.02, -0.80], 90, {}, "typical", "styling")
it("SIT-DEC-4", BA, "R-g-sitting", "decor", "small plant on side table", ph("potted_plant_04"), [170, 186, 268], [7.32, 0.551, 1.95], 180, {}, "typical", "styling")
it("SIT-DEC-5", BA, "R-g-sitting", "decor", "book stack", ph("book_encyclopedia_set_01"), [300, 220, 90], [7.15, 0.418, 0.20], 0, {}, "typical", "styling")

# ================================================================= BEFORE-only ground floor
KB = "R-g-kitchen"
def kunit(id, ver, room, typ, size, pos, yaw, front, why, extra=None, cat="joinery"):
    a = par("kitchen_unit", unit=typ, plinth_mm=150, worktop_top_y=0.91, front=front, **(extra or {}))
    it(id, ver, room, cat, typ, a, size, pos, yaw, {"front": front, "worktop": "KITB-TOP" if room == KB else "KIT-TOP"}, "typical", why,
       status="typical existing (not surveyed)" if room == KB else P)
# Run A (flank, back face x 8.665) facing -x (yaw 90); run B (back wall z -1.27) facing -z (yaw 0)
kunit("KB-A1", B, KB, "tall fridge-freezer housing", [600, 600, 2100], [8.365, GF, -1.57], 90, "KITB-FRONT", "existing kitchen, layout typical (no interior photos)")
kunit("KB-A2", B, KB, "base unit 800, drawers", [800, 600, 910], [8.365, GF, -2.27], 90, "KITB-FRONT", "typical")
kunit("KB-A3", B, KB, "sink base 1000, inset stainless 1.5 bowl, chrome mixer", [1000, 600, 910], [8.365, GF, -3.17], 90, "KITB-FRONT", "sink centred on kitchen window 1 (z -2.415..-3.875)")
kunit("KB-A4", B, KB, "integrated dishwasher 600", [600, 600, 910], [8.365, GF, -3.97], 90, "KITB-FRONT", "typical")
kunit("KB-A5", B, KB, "base unit 600", [600, 600, 910], [8.365, GF, -4.57], 90, "KITB-FRONT", "typical")
kunit("KB-A6", B, KB, "base unit 625", [625, 600, 910], [8.365, GF, -5.1825], 90, "KITB-FRONT", "typical")
kunit("KB-B1", B, KB, "base unit 600", [600, 600, 910], [5.935, GF, -1.57], 0, "KITB-FRONT", "typical")
kunit("KB-B2", B, KB, "oven base 600, built-in single oven, 4-zone ceramic hob", [600, 600, 910], [6.535, GF, -1.57], 0, "KITB-FRONT", "hob on the back wall, not under a window", cat="appliance")
kunit("KB-B3", B, KB, "base unit 600", [600, 600, 910], [7.135, GF, -1.57], 0, "KITB-FRONT", "typical")
kunit("KB-B4", B, KB, "corner base 630", [630, 600, 910], [7.75, GF, -1.57], 0, "KITB-FRONT", "typical")
it("KB-HOOD", B, KB, "appliance", "chimney cooker hood 600, stainless", par("cooker_hood", style="chimney", finish="brushed stainless"), [600, 500, 880], [6.535, 1.55, -1.52], 0, {"all": "STEEL-BRUSHED"}, "typical", "over the hob", status="typical existing (not surveyed)")
it("KB-WALL", B, KB, "joinery", "wall units 720 high (x 5.635-6.235 and 6.835-8.065)", par("wall_units", segments_x=[[5.635, 6.235], [6.835, 8.065]], depth_mm=330, bottom_y=1.45, front="KITB-FRONT"),
   [2430, 330, 720], [6.85, 1.45, -1.435], 0, {"front": "KITB-FRONT"}, "typical", "typical", status="typical existing (not surveyed)")
it("KB-SPLASH", B, KB, "fitting", "metro tile splashback 75x150, worktop to wall units", par("tile_band", tile_mm=[150, 75], bond="brick", grout="#D9D3C8", height_mm=540),
   [2430, 8, 540], [6.85, 0.91, -1.274], 0, {"all": "TILE-METRO-WHITE"}, "typical", "typical", status="typical existing (not surveyed)")
it("KB-TABLE", B, KB, "furniture", "round bistro table", ph("round_wooden_table_02", fit="uniform"), [796, 796, 746], [6.85, GF, -4.40], 0, {}, "typical", "clear of the lobby door sweep (hinge 5.699, -5.593)", status="typical existing (not surveyed)")
it("KB-CHAIR-1", B, KB, "furniture", "dining chair", ph("dining_chair_02"), [434, 576, 973], [6.85, GF, -3.75], 0, {}, "typical", "typical")
it("KB-CHAIR-2", B, KB, "furniture", "dining chair", ph("dining_chair_02"), [434, 576, 973], [6.85, GF, -5.05], 180, {}, "typical", "typical")
it("KB-PEND", B, KB, "lighting", "ceiling light", par("flush_disc", dia_mm=400, diffuser="opal", lamp="3000 K 2000 lm"), [400, 400, 80], [7.15, 2.35, -3.38], 0, {}, "typical", "typical")
for n, (nm, a, s, p) in enumerate([("kettle", par("kettle", finish="cream enamel"), [220, 160, 250], [8.35, 0.91, -2.05]),
                                    ("toaster", par("toaster", finish="cream enamel"), [300, 180, 200], [8.35, 0.91, -2.50]),
                                    ("utensil jar", ph("jug_01"), [275, 168, 211], [6.00, 0.91, -1.45]),
                                    ("chopping board", par("board", wood="oak", size="450x300x25", leaning=True), [450, 25, 300], [7.20, 0.91, -1.30]),
                                    ("fruit bowl", ph("wooden_bowl_01"), [313, 309, 94], [6.85, 0.746, -4.40]),
                                    ("herb pot on sill", ph("planter_pot_clay", fit="uniform"), [180, 180, 150], [8.62, 1.083, -3.40])], 1):
    it(f"KB-DEC-{n}", B, KB, "decor", nm, a, s, p, 90, {}, "typical", "styling rule S3 (kitchen counters)")

# Under-stairs cupboard, store, lobby, cloaks, conservatory (Before)
it("STO-SHELF", B, "R-g-store", "furniture", "steel shelving unit", ph("steel_frame_shelves_01"), [1097, 502, 2140], [3.416, GF, -5.60], -90, {}, "typical", TYP)
it("STO-WM", B, "R-g-store", "appliance", "washing machine", par("washing_machine", finish="white"), [600, 600, 850], [4.95, GF, -6.17], 0, {}, "typical", TYP)
it("LOB-HOOKS", B, "R-g-lobby", "fitting", "coat hook rail with 2 coats", par("hook_rail", rail="oak 600x90x20", hooks="matt black", coats=2), [600, 60, 90], [5.67, 1.60, -6.17], -90, {}, "typical", TYP)
it("CLB-WC", B, "R-g-cloaks", "sanitary", "close-coupled WC", drawn("FT-G-WC-cloaks-8-0-6-010000000000001", parametric="wc_close_coupled, white vitreous china, cistern 800 high"),
   [320, 630, 800], [8.315, GF, -6.17], 90, {"all": "SAN-WHITE"}, "drawn", "4915.1 sanitary arcs (WC x 7.97-8.66, y 5.98-6.36 drawn)")
it("CLB-BASIN", B, "R-g-cloaks", "sanitary", "corner/compact basin", drawn("FT-G-basin-cloaks-7-21-5-83", parametric="wall-hung basin 330x330, chrome pillar tap"),
   [270, 270, 850], [7.345, GF, -5.965], 0, {"all": "SAN-WHITE"}, "drawn", "4915.1")
CONS = "R-g-conservatory-uPVC-polycarbonate-roof"
it("CON-SOFA", B, CONS, "furniture", "rattan 2-seat sofa with cushions", par("sofa", seats=2, frame="natural rattan weave", upholstery="FAB-SOFA"), [1400, 750, 800], [0.555, GF, -6.40], -90, {"frame": "RATTAN", "cushions": "FAB-SOFA"}, "typical", TYP)
it("CON-ARM", B, CONS, "furniture", "rattan armchair", par("armchair", frame="natural rattan weave", upholstery="FAB-SOFA"), [750, 750, 800], [2.35, GF, -6.40], 90, {"frame": "RATTAN"}, "typical", TYP)
it("CON-TABLE", B, CONS, "furniture", "rattan coffee table, glass top", par("table_low", frame="rattan", top="6 mm clear glass"), [900, 500, 420], [1.45, GF, -6.40], 90, {"frame": "RATTAN"}, "typical", TYP)
it("CON-RUG", B, CONS, "soft_furnishing", "jute rug", par("rug", pile="jute"), [1400, 2000, 10], [1.45, GF, -6.40], 0, {"all": "RUG-JUTE"}, "typical", TYP)
it("CON-PLANT-1", B, CONS, "plant", "potted plant", ph("potted_plant_02"), [701, 657, 841], [2.55, GF, -5.15], 0, {}, "typical", "styling")
it("CON-PLANT-2", B, CONS, "plant", "succulent on table", ph("potted_plant_04"), [170, 186, 268], [1.45, 0.42, -6.20], 0, {}, "typical", "styling")
it("CON-FLAMP", B, CONS, "lighting", "floor lamp", FLOORLAMP, [400, 400, 1550], [0.45, GF, -7.60], 0, {}, "typical", "styling")
for n, (fab, dz) in enumerate([("FAB-CUSH-SAGE", -6.05), ("FAB-CUSH-TERRA", -6.75)], 1):
    it(f"CON-CUSH-{n}", B, CONS, "soft_furnishing", "cushion", CUSH(fab), [450, 150, 450], [0.30, 0.45, dz], -90, {"all": fab}, "typical", "styling")

# ================================================================= AFTER-only ground floor
KLD = "R-g-kitchen-living-dining-open-plan"
# Run A: back line x 8.59 (extension flank inner face; 75 mm filler behind the fridge where the old flank face is 8.665)
kunit("KA-A1", A, KLD, "tall integrated fridge-freezer housing", [600, 600, 2200], [8.29, GF, -4.82], 90, "KIT-FRONT", "kitchen layout " + P)
kunit("KA-A2", A, KLD, "base unit 400, 3 drawers", [400, 600, 910], [8.29, GF, -5.32], 90, "KIT-FRONT", "kitchen layout " + P)
kunit("KA-A3", A, KLD, "hob base 800: built-in single oven under 780 induction hob", [800, 600, 910], [8.29, GF, -5.92], 90, "KIT-FRONT",
      "hob centred z -5.92 on the drawn 'mv (cooker hood extract)' (4915.2B, drawn x 8.05-8.17, z -5.86..-5.98)", cat="appliance")
kunit("KA-A4", A, KLD, "base unit 600, pan drawers", [600, 600, 910], [8.29, GF, -6.62], 90, "KIT-FRONT", "kitchen layout " + P)
kunit("KA-A5", A, KLD, "blind corner base 975", [975, 600, 910], [8.29, GF, -7.4075], 90, "KIT-FRONT", "kitchen layout " + P)
kunit("KA-B1", A, KLD, "base unit 520", [520, 600, 910], [5.56, GF, -7.595], 0, "KIT-FRONT", "kitchen layout " + P)
kunit("KA-B2", A, KLD, "integrated dishwasher 600", [600, 600, 910], [6.12, GF, -7.595], 0, "KIT-FRONT", "kitchen layout " + P)
kunit("KA-B3", A, KLD, "sink base 800: undermount stainless single bowl, brushed brass swan-neck tap", [800, 600, 910], [6.82, GF, -7.595], 0, "KIT-FRONT",
      "sink centred on the kitchen rear window (x 5.915-7.725, sill 1.018; 4915.2B)")
kunit("KA-B4", A, KLD, "base unit 770 (to the corner)", [770, 600, 910], [7.605, GF, -7.595], 0, "KIT-FRONT", "kitchen layout " + P)
it("KA-WALL", A, KLD, "joinery", "wall units 720 high on run A (z -5.12..-7.32) with integrated extractor 800 over the hob", par("wall_units", segments_z=[[-5.12, -7.32]], depth_mm=330, bottom_y=1.45, front="KIT-FRONT", extractor={"z": [-5.52, -6.32], "type": "integrated canopy 800, ducted to the drawn mv point"}),
   [2200, 330, 720], [8.425, 1.45, -6.22], 90, {"front": "KIT-FRONT"}, "typical", "kitchen layout " + P, status=P)
it("KA-ISLAND", A, KLD, "joinery", "island 1300 x 900, oak slab fronts, quartz top with 250 overhang on the north side", par("island", carcass_d_mm=650, overhang_side="north (+z)", top_t_mm=30, front="KIT-ISLAND"),
   [1300, 900, 910], [6.35, GF, -5.95], 0, {"front": "KIT-ISLAND", "top": "KIT-TOP"}, "typical",
   "aisles: 0.99 to run A, 0.895 to run B, 1.0 to the utility wall; clear of the utility door sweep (hinge 6.308, -4.441)", status=P)
for n, xx in enumerate([6.05, 6.65], 1):
    it(f"KA-STOOL-{n}", A, KLD, "furniture", "counter stool", ph("bar_chair_round_01"), [483, 486, 750], [xx, GF, -5.25], 0, {}, "typical", "kitchen layout " + P, status=P)
for n, xx in enumerate([6.025, 6.675], 1):
    it(f"KA-PEND-{n}", A, KLD, "lighting", "pendant over island", ph("modern_ceiling_lamp_01", drop_to_bottom_y=1.65), [432, 432, 951], [xx, 2.43, -5.95], 0, {}, "typical", "1 pendant per 650 mm of island; bottom 0.74 m above the top", status=P)
it("KA-SPLASH", A, KLD, "fitting", "quartz upstand 100 mm on both runs + full-height quartz splash behind the hob", par("upstand", height_mm=100, hob_splash={"z": [-5.52, -6.32], "height_mm": 540}),
   [2690, 20, 100], [6.645, 0.94, -7.885], 0, {"all": "KIT-TOP"}, "typical", "kitchen layout " + P, status=P)
it("KA-BLIND", A, KLD, "soft_furnishing", "linen roman blind on the kitchen rear window", par("roman_blind", fabric="FAB-CURTAIN", folds=5, mount="inside recess"), [1810, 60, 1060], [6.82, 1.018, -7.88], 0, {"all": "FAB-CURTAIN"}, "typical", "styling rule S1 (window dressing)")
it("KA-TABLE", A, KLD, "furniture", "oak dining table for 6", par("dining_table", top="solid oak 40 mm, rounded corners r 20", legs="4 square oak 70, inset 100"),
   [1800, 900, 750], [3.85, GF, -6.20], 90, {"all": "WOOD-OAK-FURN"}, "typical", "dining band x 2.66-4.74 between the snug and the island; 0.8 m clear to the bi-folds", status=P)
for n, (xx, zz, yw) in enumerate([(3.25, -5.65, -90), (3.25, -6.20, -90), (3.25, -6.75, -90), (4.45, -5.65, 90), (4.45, -6.20, 90), (4.45, -6.75, 90)], 1):
    it(f"KA-CHAIR-{n}", A, KLD, "furniture", "dining chair", ph("dining_chair_02"), [434, 576, 973], [xx, GF, zz], yw, {}, "typical", "dining layout " + P, status=P)
it("KA-LINEAR", A, KLD, "lighting", "linear pendant over the table", par("linear_pendant", length_mm=1200, body="matt black, opal diffuser", lamp="2700 K 2400 lm", bottom_y=1.60),
   [1200, 80, 60], [3.85, 2.43, -6.20], 90, {"all": "METAL-BLACK"}, "typical", "dining layout " + P, status=P)
it("KA-DOWN", A, KLD, "lighting", "6 recessed downlights over the kitchen (x 5.9/7.1/8.2 at z -4.95 and -6.95)", par("downlight_set", positions_xz=[[5.9, -4.95], [7.1, -4.95], [8.2, -4.95], [5.9, -6.95], [7.1, -6.95], [8.2, -6.95]], trim="white 85 dia", lamp="2700 K 550 lm"),
   [85, 85, 10], [7.05, 2.43, -5.95], 0, {}, "typical", "typical")
it("KA-SOFA", A, KLD, "furniture", "2-seat sofa (snug zone, catslide side)", par("sofa", seats=2, arms="square 150", legs="oak", upholstery="FAB-SOFA"),
   [1700, 900, 780], [1.335, GF, -6.10], -90, {"upholstery": "FAB-SOFA"}, "typical", "snug zone x 0.865-2.66 under the catslide; 0.9 m walkway to the dining chairs; route living -> bi-folds at x 1.8-2.96", status=P)
for n, (zz, fab) in enumerate([(-5.60, "FAB-CUSH-SAGE"), (-6.10, "FAB-CUSH-CREAM"), (-6.60, "FAB-CUSH-TERRA")], 1):
    it(f"KA-CUSH-{n}", A, KLD, "soft_furnishing", "cushion 450", CUSH(fab), [450, 150, 450], [1.05, 0.45, zz], -90, {"all": fab}, "typical", "styling rule S1")
it("KA-THROW", A, KLD, "soft_furnishing", "knitted throw", par("throw_drape", drape="over south arm"), [1300, 1700, 8], [1.30, 0.45, -6.80], -90, {"all": "FAB-THROW"}, "typical", "styling rule S1")
it("KA-RUG", A, KLD, "soft_furnishing", "rug under the snug", par("rug", pile="low wool, oatmeal"), [1600, 2300, 12], [1.90, GF, -6.10], 0, {"all": "RUG-WOOL"}, "typical", "styling rule S1")
it("KA-SIDE", A, KLD, "furniture", "small round table", ph("WoodenTable_02"), [301, 301, 418], [2.15, GF, -6.10], 0, {}, "typical", "styling")
it("KA-STABLE", A, KLD, "furniture", "side table at the sofa's north end", ph("side_table_01"), [550, 450, 551], [1.20, GF, -4.95], -90, {}, "typical", "styling")
it("KA-TLAMP", A, KLD, "lighting", "table lamp", TABLELAMP, [300, 300, 480], [1.20, 0.551, -4.95], -90, {}, "typical", "styling rule S1 (2 lamps)")
it("KA-FLAMP", A, KLD, "lighting", "floor lamp", FLOORLAMP, [400, 400, 1550], [1.10, GF, -7.30], 0, {}, "typical", "styling rule S1 (2 lamps)")
it("KA-PLANT-1", A, KLD, "plant", "tall potted plant", ph("potted_plant_01"), [589, 637, 1351], [2.35, GF, -4.85], 0, {}, "typical", "styling rule S1; leaves 0.9 m of the 2.8 m living opening clear at x 2.65-3.555")
it("KA-PLANT-2", A, KLD, "plant", "herb pot on worktop", ph("planter_pot_clay"), [180, 180, 150], [7.45, 0.94, -7.70], 0, {}, "typical", "styling rule S3")
it("KA-ART-1", A, KLD, "decor", "large framed print on the G-rearC wall", ART("warm abstract, terracotta and cream"), [700, 25, 1000], [4.60, 1.10, -4.69], 0, {"frame": "WOOD-OAK-FURN"}, "typical", "styling rule S1 (2 artworks)")
it("KA-ART-2", A, KLD, "decor", "framed print above the snug sofa", ART("botanical, sage"), [500, 25, 700], [0.875, 1.25, -6.10], -90, {"frame": "WOOD-OAK-FURN"}, "typical", "styling rule S1")
for n, (nm, a, s, p) in enumerate([("kettle", par("kettle", finish="matt cream"), [220, 160, 250], [8.30, 0.94, -6.85]),
                                    ("coffee machine", par("coffee_machine", finish="brushed steel"), [250, 400, 350], [8.30, 0.94, -7.30]),
                                    ("utensil crock with utensils", ph("jug_01"), [275, 168, 211], [8.35, 0.94, -5.30]),
                                    ("oak chopping board leaning on the splash", par("board", wood="oak", size="450x300x25", leaning=True), [450, 25, 300], [8.55, 0.94, -6.55]),
                                    ("fruit bowl on island", ph("wooden_bowl_01"), [313, 309, 94], [6.10, 0.94, -6.05]),
                                    ("vase with eucalyptus on island", ph("ceramic_vase_03"), [112, 112, 414], [6.70, 0.94, -6.10]),
                                    ("oil and vinegar bottles on a tray", par("bottle_pair_tray", tray="oak 300x150"), [300, 150, 260], [5.60, 0.94, -7.70]),
                                    ("tea towel on the oven handle", par("tea_towel", fabric="striped cotton, cream/sage"), [500, 10, 700], [7.99, 0.45, -5.92]),
                                    ("table centrepiece: low bowl", ph("wooden_bowl_02"), [131, 125, 73], [3.85, 0.75, -6.20]),
                                    ("candles on table (2)", ph("brass_candleholders", fit="uniform"), [300, 100, 240], [3.85, 0.75, -6.60])], 1):
    it(f"KA-DEC-{n}", A, KLD, "decor", nm, a, s, p, 0, {}, "typical", "styling rule S3 (>= 8 kitchen items)")
it("KA-UFH", A, KLD, "fitting", "underfloor heating under the oak floor (no radiators in the kitchen-diner)", par("note_only"), [0, 0, 0], [4.7, GF, -6.2], 0, {}, "typical", "keeps the bi-fold wall and runs clear; " + P, status=P)

# Utility (ex-kitchen), cloaks lobby, cloaks WC (After)
U = "R-g-utility-ex-kitchen"
kunit("UT-1", A, U, "washing machine (integrated look, white)", [600, 600, 850], [5.95, GF, -2.855], 180, "KIT-FRONT", "utility run on the cloaks partition (face z -2.555)", cat="appliance")
kunit("UT-2", A, U, "tumble dryer", [600, 600, 850], [6.55, GF, -2.855], 180, "KIT-FRONT", "utility", cat="appliance")
kunit("UT-3", A, U, "sink base 600, stainless single bowl, brushed brass tap", [600, 600, 910], [7.15, GF, -2.855], 180, "KIT-FRONT", "utility")
kunit("UT-4", A, U, "base unit 1255", [1255, 600, 910], [8.0775, GF, -2.855], 180, "KIT-FRONT", "utility")
kunit("UT-5", A, U, "tall broom cupboard", [600, 600, 2100], [5.95, GF, -4.07], 0, "KIT-FRONT", "west of the kitchen door (x 6.275-7.185)")
it("UT-DOWN", A, U, "lighting", "2 downlights", par("downlight_set", positions_xz=[[6.6, -3.45], [7.9, -3.45]]), [85, 85, 10], [7.25, 2.43, -3.45], 0, {}, "typical", "typical")
it("CLL-MIRROR", A, "R-g-cloaks-lobby", "decor", "round mirror, oak frame, 600 dia", par("mirror_round", frame="oak 20 mm"), [600, 25, 600], [6.06, 1.25, -2.43], 180, {"frame": "WOOD-OAK-FURN"}, "typical", "the lobby is the cloaks door's sweep (hinge 6.515, -1.377): wall items only")
it("CLL-LIGHT", A, "R-g-cloaks-lobby", "lighting", "downlight", par("downlight_set", positions_xz=[[6.06, -1.86]]), [85, 85, 10], [6.06, 2.43, -1.86], 0, {}, "typical", "typical")
it("CLA-WC", A, "R-g-cloaks-WC", "sanitary", "close-coupled WC", drawn("FT-G-WC-cloaks-8-01-1-7", parametric="wc_close_coupled, white vitreous china, cistern 800 high, matt black flush plate"),
   [370, 665, 800], [8.3425, GF, -1.855], 90, {"all": "SAN-WHITE"}, "drawn", "4915.2B sanitary arcs (x 7.98-8.705, y 1.67-2.04 drawn)")
it("CLA-BASIN", A, "R-g-cloaks-WC", "sanitary", "compact vanity unit with basin", drawn("FT-G-basin-cloaks-7-063000000000001-2-03", parametric="vanity 390x400, oak front, white ceramic basin, brushed brass mono tap"),
   [390, 400, 850], [7.2575, GF, -2.2285], 180, {"vanity": "WOOD-OAK-FURN", "basin": "SAN-WHITE"}, "drawn", "4915.2B (x 7.033-7.482, y 2.0-2.457 drawn)")
it("CLA-MIRROR", A, "R-g-cloaks-WC", "decor", "mirror over basin", par("mirror_rect", frame="thin black", size="400x600"), [400, 20, 600], [7.2575, 1.15, -2.43], 180, {}, "typical", "styling rule S4")
it("CLA-TOWEL", A, "R-g-cloaks-WC", "soft_furnishing", "hand towel on black ring", par("towel_ring", towel="cream waffle"), [250, 80, 350], [7.75, 1.00, -2.43], 180, {}, "typical", "styling rule S4")
it("CLA-PLANT", A, "R-g-cloaks-WC", "plant", "small plant on cistern", ph("potted_plant_04"), [170, 186, 268], [8.55, 0.80, -1.855], 90, {}, "typical", "styling rule S4")
it("CLA-LIGHT", A, "R-g-cloaks-WC", "lighting", "downlight IP65", par("downlight_set", positions_xz=[[7.6, -1.86]]), [85, 85, 10], [7.6, 2.43, -1.86], 0, {}, "typical", "typical")

# ================================================================= FIRST FLOOR — Bedroom 1, Bedroom 2, Bathroom identical in both
R1 = "R-f-bedroom-1-front-left"
it("BD1-BED", BA, R1, "furniture", "king bed 1500x2000 mattress, upholstered headboard", par("bed", mattress_mm=[1500, 2000, 250], frame="upholstered FAB-SOFA, plinth base 300 high", headboard_h_mm=1200, linen="BED-LINEN", pillows=4, throw="THROW-BED across the foot"),
   [1600, 2100, 1200], [1.555, FF, -2.38], -90, {"frame": "FAB-SOFA", "linen": "BED-LINEN", "throw": "THROW-BED"}, "typical",
   "headboard on the chimney breast face (x 0.505, breast z -1.679..-3.088; 4915.2B FF); door leaf (hinge 3.605, -2.075) opens along z -2.075 to x 2.835, clear of the bed foot (2.605)")
it("BD1-BS-1", BA, R1, "furniture", "bedside table (front alcove)", par("bedside", drawers=1, body="WOOD-OAK-FURN"), [400, 400, 550], [0.40, FF, -1.36], -90, {"all": "WOOD-OAK-FURN"}, "typical", "alcove z -0.3..-1.679")
it("BD1-BS-2", BA, R1, "furniture", "bedside table (rear alcove)", par("bedside", drawers=1, body="WOOD-OAK-FURN"), [400, 400, 550], [0.40, FF, -3.40], -90, {"all": "WOOD-OAK-FURN"}, "typical", "alcove z -3.088..-4.36")
it("BD1-LAMP-1", BA, R1, "lighting", "bedside lamp", TABLELAMP, [300, 300, 480], [0.40, FF + 0.55, -1.36], -90, {}, "typical", "styling rule S2")
it("BD1-LAMP-2", BA, R1, "lighting", "bedside lamp", TABLELAMP, [300, 300, 480], [0.40, FF + 0.55, -3.40], -90, {}, "typical", "styling rule S2")
it("BD1-WARD", BA, R1, "furniture", "2-door wardrobe", par("wardrobe", doors=2, front="painted shaker KIT-FRONT", handles="brushed brass knobs"), [900, 600, 2000], [3.095, FF, -0.60], 0, {"all": "KIT-FRONT"}, "typical", "front-right corner x 2.645-3.545 beside the window (x 1.17-2.63)")
it("BD1-DRESSER", BA, R1, "furniture", "chest of drawers", par("chest", drawers=3, body="WOOD-OAK-FURN"), [1000, 450, 800], [1.70, FF, -4.135], 180, {"all": "WOOD-OAK-FURN"}, "typical", "on the rear wall; 0.73 m to the bed side")
it("BD1-RUG", BA, R1, "soft_furnishing", "rug, half under the bed", par("rug", pile="wool, cream"), [1400, 2000, 12], [2.10, FF, -2.38], 0, {"all": "RUG-WOOL"}, "typical", "styling rule S2")
it("BD1-CURT", BA, R1, "soft_furnishing", "curtains", CURT(2000), [2000, 120, 2215], [1.90, FF + 0.01, -0.36], 0, {"fabric": "FAB-CURTAIN"}, "typical", "window x 1.17-2.63")
it("BD1-RAD", BA, R1, "radiator", "radiator under window", RAD(1200), [1200, 50, 600], [1.90, FF + 0.15, -0.375], 0, {}, "typical", TYP)
it("BD1-PEND", BA, R1, "lighting", "pendant", PEND_DRUM, [450, 450, 250], [1.85, FF + 2.405, -2.33], 0, {}, "typical", TYP)
it("BD1-ART", BA, R1, "decor", "framed print above the bed", ART("soft abstract, clay and cream"), [900, 25, 600], [0.52, FF + 1.40, -2.38], -90, {}, "typical", "styling rule S2")
it("BD1-PLANT", BA, R1, "plant", "potted plant", ph("potted_plant_02"), [701, 657, 841], [3.10, FF, -4.00], 90, {}, "typical", "styling rule S2")
it("BD1-DEC-1", BA, R1, "decor", "books + vase on dresser", ph("ceramic_vase_04"), [183, 182, 342], [1.45, FF + 0.80, -4.15], 180, {}, "typical", "styling")
it("BD1-DEC-2", BA, R1, "decor", "book on bedside", ph("book_encyclopedia_set_01"), [180, 220, 40], [0.40, FF + 0.55, -3.25], -90, {}, "typical", "styling")

R2 = "R-f-bedroom-2-front-bay"
it("BD2-BED", BA, R2, "furniture", "double bed 1350x1900 mattress, oak frame", par("bed", mattress_mm=[1350, 1900, 220], frame="oak slatted, headboard panel", headboard_h_mm=1000, linen="BED-LINEN", pillows=4, throw="THROW-BED"),
   [1450, 2000, 1000], [7.655, FF, 1.075], 90, {"frame": "WOOD-OAK-FURN", "linen": "BED-LINEN"}, "typical",
   "headboard on the flank (x 8.655), clear of the duct pier (z -1.125..-0.435)")
it("BD2-BS-1", BA, R2, "furniture", "bedside table", par("bedside", drawers=1), [400, 400, 550], [8.455, FF, 0.15], 90, {"all": "WOOD-OAK-FURN"}, "typical", TYP)
it("BD2-BS-2", BA, R2, "furniture", "bedside table", par("bedside", drawers=1), [400, 400, 550], [8.455, FF, 2.00], 90, {"all": "WOOD-OAK-FURN"}, "typical", TYP)
it("BD2-LAMP-1", BA, R2, "lighting", "bedside lamp", TABLELAMP, [300, 300, 480], [8.455, FF + 0.55, 0.15], 90, {}, "typical", "styling rule S2")
it("BD2-LAMP-2", BA, R2, "lighting", "bedside lamp", TABLELAMP, [300, 300, 480], [8.455, FF + 0.55, 2.00], 90, {}, "typical", "styling rule S2")
it("BD2-WARD", BA, R2, "furniture", "wardrobe", par("wardrobe", doors=2, front="painted shaker KIT-FRONT"), [1200, 600, 2000], [7.20, FF, -0.825], 180, {"all": "KIT-FRONT"}, "typical", "on the landing wall from x 6.6; door leaf (hinge 6.412, -1.173) opens along x 6.412")
it("BD2-DESK", BA, R2, "furniture", "dressing table/desk by the window", par("desk", top="oak 25 mm", legs="oak", drawers=1), [900, 450, 750], [6.15, FF, 2.125], 0, {"all": "WOOD-OAK-FURN"}, "typical", TYP)
it("BD2-CHAIR", BA, R2, "furniture", "chair", ph("dining_chair_02"), [434, 576, 973], [6.15, FF, 1.55], 180, {}, "typical", TYP)
it("BD2-RUG", BA, R2, "soft_furnishing", "rug", par("rug", pile="jute-wool"), [1400, 2000, 12], [6.95, FF, 1.075], 0, {"all": "RUG-JUTE"}, "typical", "styling rule S2")
it("BD2-CURT", BA, R2, "soft_furnishing", "curtains", CURT(2000), [2000, 120, 2215], [7.148, FF + 0.01, 2.30], 180, {}, "typical", "window x 6.42-7.875")
it("BD2-RAD", BA, R2, "radiator", "radiator under window", RAD(1200), [1200, 50, 600], [7.148, FF + 0.15, 2.285], 180, {}, "typical", TYP)
it("BD2-PEND", BA, R2, "lighting", "pendant", PEND_DRUM, [450, 450, 250], [7.15, FF + 2.405, 0.62], 0, {}, "typical", TYP)
it("BD2-ART", BA, R2, "decor", "framed print above bed", ART("line drawing, figures"), [700, 25, 500], [8.645, FF + 1.30, 1.075], 90, {}, "typical", "styling rule S2")
it("BD2-PLANT", BA, R2, "plant", "small potted plant on desk", ph("potted_plant_04"), [170, 186, 268], [5.85, FF + 0.75, 2.20], 0, {}, "typical", "styling rule S2")

BT = "R-f-bathroom"
it("BTH-TRAY", BA, BT, "sanitary", "shower tray + 2-sided glass enclosure, matt black frame, thermostatic bar valve and 250 rain head",
   drawn("FT-F-shower-tray-bathroom-6-571000000000001-2-1679999999999997", parametric="tray 940x840 white stone resin; screens 8 mm on the x 7.51 and z -2.168 sides, 1950 high; hinged door on the z side"),
   [940, 840, 1950], [7.04, FF, -2.5875], 0, {"tray": "SAN-WHITE", "frame": "METAL-BLACK", "glass": "GLASS-CLEAR"}, "drawn", "4915.1/2B sanitary (x 6.541-7.54, y 2.138-3.037 drawn)")
it("BTH-BASIN", BA, BT, "sanitary", "semi-pedestal basin 400", drawn("FT-F-basin-bathroom-7-896-2-63", parametric="basin 390x380 white, brushed brass mono tap"),
   [390, 380, 850], [8.09, FF, -2.8185], 180, {"all": "SAN-WHITE"}, "drawn", "4915.2B (x 7.866-8.315, y 2.6-3.037)")
it("BTH-WC", BA, BT, "sanitary", "close-coupled WC", drawn("FT-F-WC-bathroom-7-99-1-47", parametric="wc_close_coupled white, cistern 800"),
   [310, 620, 800], [8.30, FF, -1.625], 90, {"all": "SAN-WHITE"}, "drawn", "4915.2B (x 7.96-8.64, y 1.44-1.81)")
it("BTH-CAB", BA, BT, "fitting", "mirror cabinet over basin", par("mirror_cabinet", size="450x600x120", body="white"), [450, 120, 600], [8.09, FF + 1.20, -2.977], 180, {}, "typical", "styling rule S4")
it("BTH-TOWELRAD", BA, BT, "radiator", "towel radiator 500x1200, matt black", par("towel_rail", finish="matt black"), [500, 60, 1200], [7.60, FF + 0.15, -1.29], 180, {"all": "METAL-BLACK"}, "typical", "on the bedroom-2 wall, outside the door sweep (radius 0.78 from 6.51, -1.286)")
it("BTH-TOWELS", BA, BT, "soft_furnishing", "2 folded towels on the rail", par("towels", colour="cream + sage"), [450, 80, 500], [7.60, FF + 0.70, -1.33], 180, {}, "typical", "styling rule S4")
it("BTH-MAT", BA, BT, "soft_furnishing", "bath mat", par("rug", pile="cotton waffle"), [500, 800, 10], [7.70, FF, -2.05], 0, {}, "typical", "styling rule S4")
it("BTH-PLANT", BA, BT, "plant", "small plant on window board", ph("potted_plant_04"), [170, 186, 268], [8.54, FF + 0.97, -2.60], 90, {}, "typical", "styling rule S4")
it("BTH-LIGHT", BA, BT, "lighting", "3 downlights IP65", par("downlight_set", positions_xz=[[7.0, -1.75], [7.6, -2.6], [8.2, -2.2]]), [85, 85, 10], [7.6, FF + 2.405, -2.2], 0, {}, "typical", "typical")

# Landing (Before: hall/landing; After: extended landing) and cupboards
it("LAN-PEND", BA, "R-f-hall-landing", "lighting", "pendant over the landing", PEND_DRUM, [450, 450, 250], [4.40, FF + 2.405, -1.75], 0, {}, "typical", TYP)
it("LAN-ART", BA, "R-f-hall-landing", "decor", "framed print on bedroom-1 wall", ART("abstract, sage"), [500, 25, 700], [3.70, FF + 1.20, -1.55], -90, {}, "typical", "styling")
it("LAN2-RUNNER", A, "R-f-landing", "soft_furnishing", "runner along the new corridor", par("rug", pile="flat-weave wool"), [700, 1800, 10], [6.03, FF, -3.40], 0, {"all": "RUG-WOOL"}, "typical", TYP)
it("LAN2-ART-1", A, "R-f-landing", "decor", "framed print on the en-suite wall", ART("botanical"), [500, 25, 700], [6.4475, FF + 1.20, -3.60], 90, {}, "typical", "styling")
it("LAN2-ART-2", A, "R-f-landing", "decor", "framed print on the en-suite wall", ART("landscape"), [500, 25, 700], [6.4475, FF + 1.20, -4.20], 90, {}, "typical", "styling")
it("LAN2-PEND", A, "R-f-landing", "lighting", "pendant over the corridor", PEND_DRUM, [450, 450, 250], [6.03, FF + 2.405, -3.30], 0, {}, "typical", TYP)

# ================================================================= BEFORE bedroom 3 (rear wing)
R3B = "R-f-bedroom-3-rear-wing"
it("B3B-BED", B, R3B, "furniture", "single bed 900x1900, oak frame", par("bed", mattress_mm=[900, 1900, 200], frame="oak", headboard_h_mm=900, linen="BED-LINEN", pillows=2, throw="THROW-BED"),
   [1000, 2000, 900], [8.14, FF, -4.235], 0, {"frame": "WOOD-OAK-FURN"}, "typical", "headboard on the bathroom wall (z -3.185), along the flank")
it("B3B-DESK", B, R3B, "furniture", "desk under the window", par("desk", top="oak 25", legs="oak"), [1100, 550, 750], [7.10, FF, -5.215], 180, {"all": "WOOD-OAK-FURN"}, "typical", "window x 6.395-7.86 (sill +0.968)")
it("B3B-CHAIR", B, R3B, "furniture", "desk chair", ph("dining_chair_02"), [434, 576, 973], [7.10, FF, -4.65], 0, {}, "typical", TYP)
it("B3B-WARD", B, R3B, "furniture", "wardrobe", par("wardrobe", doors=2, front="KIT-FRONT"), [1000, 600, 2000], [5.91, FF, -3.80], -90, {"all": "KIT-FRONT"}, "typical", "on the stair wall (x 5.61), clear of the door leaf (opens along x 6.367 to z -3.05)")
it("B3B-RUG", B, R3B, "soft_furnishing", "rug", par("rug", pile="wool"), [1200, 1700, 12], [7.10, FF, -4.10], 0, {"all": "RUG-WOOL"}, "typical", "styling rule S2")
it("B3B-LAMP", B, R3B, "lighting", "desk lamp", ph("desk_lamp_arm_01"), [617, 408, 879], [7.45, FF + 0.75, -5.30], 180, {}, "typical", "styling rule S2")
it("B3B-CURT", B, R3B, "soft_furnishing", "curtains", CURT(1700), [1700, 120, 2215], [7.128, FF + 0.01, -5.43], 0, {}, "typical", "window x 6.395-7.86")
it("B3B-PEND", B, R3B, "lighting", "pendant", PEND_DRUM, [450, 450, 250], [7.10, FF + 2.405, -4.30], 0, {}, "typical", TYP)
it("B3B-ART", B, R3B, "decor", "framed print", ART("map print"), [500, 25, 700], [8.63, FF + 1.20, -4.80], 90, {}, "typical", "styling rule S2")
it("B3B-PLANT", B, R3B, "plant", "plant on desk", ph("potted_plant_04"), [170, 186, 268], [6.70, FF + 0.75, -5.30], 0, {}, "typical", "styling rule S2")

# ================================================================= AFTER bedroom 3 (new, over the kitchen) and en-suite
R3A = "R-f-bedroom-3-rear-new"
it("B3A-BED", A, R3A, "furniture", "king bed 1500x2000, upholstered headboard on the low (ashlar) wall", par("bed", mattress_mm=[1500, 2000, 250], frame="upholstered FAB-SOFA", headboard_h_mm=1100, linen="BED-LINEN", pillows=4, throw="THROW-BED"),
   [1700, 2150, 1100], [3.8675, FF, -6.20], -90, {"frame": "FAB-SOFA", "linen": "BED-LINEN"}, "typical",
   "ashlar wall face x 2.7925 (1.55 high, 4915.3A); standing height over the bed from x ~3.58")
it("B3A-BS-1", A, R3A, "furniture", "bedside table", par("bedside", drawers=1), [400, 400, 550], [3.00, FF, -5.05], -90, {"all": "WOOD-OAK-FURN"}, "typical", TYP)
it("B3A-BS-2", A, R3A, "furniture", "bedside table", par("bedside", drawers=1), [400, 400, 550], [3.00, FF, -7.35], -90, {"all": "WOOD-OAK-FURN"}, "typical", TYP)
it("B3A-LAMP-1", A, R3A, "lighting", "bedside lamp", TABLELAMP, [300, 300, 480], [3.00, FF + 0.55, -5.05], -90, {}, "typical", "styling rule S2")
it("B3A-LAMP-2", A, R3A, "lighting", "bedside lamp", TABLELAMP, [300, 300, 480], [3.00, FF + 0.55, -7.35], -90, {}, "typical", "styling rule S2")
it("B3A-WARD", A, R3A, "joinery", "built-in wardrobe 'wd.' (as drawn), painted shaker doors on the x 7.36 face",
   drawn("FT-F-wardrobe-wd-7-36-5-65", parametric="carcass to the drawn box, 4 doors, brass knobs"), [2240, 1225, 2100], [7.9725, FF, -6.77], 90, {"front": "KIT-FRONT"}, "drawn", "4915.2B 'wd.', dims 1285 / 2303")
it("B3A-ARM", A, R3A, "furniture", "reading armchair by the EE window", par("armchair", frame="oak", upholstery="FAB-CUSH-SAGE"), [760, 820, 760], [6.20, FF, -7.20], 90, {}, "typical", "the escape window stays openable (not blocked)")
it("B3A-FLAMP", A, R3A, "lighting", "floor lamp", FLOORLAMP, [400, 400, 1550], [6.95, FF, -7.55], 0, {}, "typical", "styling rule S2")
it("B3A-RUG", A, R3A, "soft_furnishing", "rug under the bed", par("rug", pile="wool, oatmeal"), [2000, 2800, 12], [4.30, FF, -6.20], 0, {"all": "RUG-WOOL"}, "typical", "styling rule S2")
it("B3A-CURT-1", A, R3A, "soft_furnishing", "curtains, left rear window", CURT(1700), [1700, 120, 1950], [4.2675, FF + 0.01, -7.83], 0, {}, "typical", "window x 3.645-4.89")
it("B3A-CURT-2", A, R3A, "soft_furnishing", "curtains, EE rear window", CURT(2300), [2300, 120, 1950], [6.82, FF + 0.01, -7.83], 0, {}, "typical", "window x 5.915-7.725")
it("B3A-RAD-1", A, R3A, "radiator", "radiator under left window", RAD(1100), [1100, 50, 600], [4.2675, FF + 0.15, -7.82], 0, {}, "typical", TYP)
it("B3A-RAD-2", A, R3A, "radiator", "radiator under EE window", RAD(1200), [1200, 50, 600], [6.82, FF + 0.15, -7.82], 0, {}, "typical", TYP)
it("B3A-PEND", A, R3A, "lighting", "pendant (flat part of the ceiling)", PEND_DRUM, [450, 450, 250], [5.00, FF + 2.405, -6.20], 0, {}, "typical", TYP)
it("B3A-ART-1", A, R3A, "decor", "framed print on the north wall", ART("abstract, clay"), [500, 25, 700], [4.00, FF + 1.20, -4.495], 0, {}, "typical", "styling rule S2")
it("B3A-ART-2", A, R3A, "decor", "framed print on the north wall", ART("botanical"), [500, 25, 700], [4.80, FF + 1.20, -4.495], 0, {}, "typical", "styling rule S2")
it("B3A-PLANT", A, R3A, "plant", "potted plant", ph("potted_plant_02"), [701, 657, 841], [6.85, FF, -5.95], 0, {}, "typical", "styling rule S2")
ES = "R-f-en-suite"
it("ENS-SHOWER", A, ES, "sanitary", "1800x900 walk-in shower: low tray, 1200 fixed glass screen (matt black frame) from x 7.14, rain head + handset, thermostatic bar valve",
   drawn("FT-F-shower-1800x900-en-suite-6-6000000000000005-3-215", parametric="tray 1800x900x40 white stone resin; screen 1200x2000, 8 mm"), [1740, 838, 2000], [7.47, FF, -3.634], 0, {"tray": "SAN-WHITE", "frame": "METAL-BLACK"}, "drawn", "4915.2B '1800x900 shower', '2100'")
it("ENS-BASIN", A, ES, "sanitary", "wall-hung vanity 500 with basin, oak front", drawn("FT-F-basin-en-suite-8-186-4-208", parametric="vanity 500x400, oak front, white basin, brushed brass tap"), [500, 400, 850], [8.3855, FF, -4.4585], 90, {"vanity": "WOOD-OAK-FURN"}, "drawn", "4915.2B")
it("ENS-WC", A, ES, "sanitary", "wall-hung WC with concealed cistern, matt black flush plate", drawn("FT-F-WC-en-suite-7-87-4-95", parametric="wc_wall_hung white, boxing 1000 high tiled"), [370, 715, 1000], [8.2275, FF, -5.105], 90, {"all": "SAN-WHITE"}, "drawn", "4915.2B")
it("ENS-MIRROR", A, ES, "decor", "mirror over the vanity", par("mirror_rect", frame="thin black", size="500x700"), [500, 20, 700], [8.58, FF + 1.20, -4.4585], 90, {}, "typical", "styling rule S4")
it("ENS-TOWELRAD", A, ES, "radiator", "towel radiator 500x1200, matt black", par("towel_rail", finish="matt black"), [500, 60, 1200], [6.60, FF + 0.15, -4.45], -90, {}, "typical", "on the landing-side partition, outside the door sweep")
it("ENS-TOWELS", A, ES, "soft_furnishing", "towels", par("towels", colour="cream + sage"), [450, 80, 500], [6.64, FF + 0.70, -4.45], -90, {}, "typical", "styling rule S4")
it("ENS-PLANT", A, ES, "plant", "small plant", ph("potted_plant_04"), [170, 186, 268], [8.40, FF + 0.85, -4.30], 90, {}, "typical", "styling rule S4")
it("ENS-LIGHT", A, ES, "lighting", "3 downlights IP65 (one in the shower)", par("downlight_set", positions_xz=[[7.5, -3.65], [7.6, -4.6], [8.2, -5.1]]), [85, 85, 10], [7.6, FF + 2.405, -4.4], 0, {}, "typical", "typical")

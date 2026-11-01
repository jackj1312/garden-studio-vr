#!/usr/bin/env python3
"""Room-planner catalogue: every item the planner can swap to or add, grouped Modern / Contemporary / Country / Scandi.

    python3 tools/planner/make_catalogue.py --site house [--spec spec_v1.json]

Writes assets/sites/<site>/spec/catalogue_v1.json (never touches the spec). Two kinds of entry:
  * seeded from the spec: one entry per distinct object the signed-off spec uses (same kind/asset and size), so the
    planner can always swap back to what was signed off; `from_spec` lists the item ids;
  * alternatives: free Poly Haven CC0 models (ids and real dimensions read from api.polyhaven.com, 1 Nov 2026) and
    parametric pieces (proportioned shapes the build makes itself).
Each entry says whether a real 3D model is on disk for the planner (`model`), only available free online
(`model_status: "free, not downloaded"`), or does not exist (`placeholder: true`: the build would make it as a
parametric shape). Style tags on Poly Haven entries are read from the asset's name, category and size, not from its
preview; check the linked page before relying on them (`style_basis`).
Also holds the room-level option lists: wall palettes, floor finishes, kitchen fronts and worktops.

Parameterised by site: the spec gives the seeds; the alternative lists are the studio's general catalogue.
"""
import argparse, json, os
from datetime import datetime, timezone

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
STYLES = ["Modern", "Contemporary", "Country", "Scandi"]

# ---- colour options per part (name, hex) --------------------------------------------------------------------------
UPH = [("Oatmeal boucle", "#D8CEBF"), ("Cream boucle", "#EFE8DA"), ("Stone linen", "#CFC6B4"), ("Sage linen", "#9BA58B"),
       ("Terracotta linen", "#B5694B"), ("Dove grey wool", "#B9B7B1"), ("Charcoal wool", "#4A4C4E"), ("Navy velvet", "#2E3A55"),
       ("Forest velvet", "#2F4A3A"), ("Ochre velvet", "#C99A3B"), ("Rust cord", "#A0522D"), ("Cognac leather", "#8B5A2B")]
WOOD = [("Natural oak", "#B8936A"), ("Pale oak", "#D7BE98"), ("Smoked oak", "#6E5440"), ("Walnut", "#5C4033"),
        ("Birch ply", "#E0CDA9"), ("Pine", "#C9A06B"), ("Black-stained ash", "#2B2B2B"), ("White painted", "#F2F0EA"),
        ("Painted sage", "#A3AE95"), ("Painted heritage blue", "#5D7380")]
METAL = [("Matt black", "#1E1E1E"), ("Brushed brass", "#B08D57"), ("Polished chrome", "#C8CCCF"), ("Antique bronze", "#6B5236"),
         ("Matt white", "#F2F2F0")]
FABRIC = [("Natural linen", "#E2D9C9"), ("White voile", "#F4F2EC"), ("Stone linen", "#CFC6B4"), ("Sage linen", "#9BA58B"),
          ("Terracotta linen", "#B5694B"), ("Ochre cotton", "#C99A3B"), ("Charcoal wool", "#4A4C4E"), ("Navy velvet", "#2E3A55"),
          ("Ticking stripe (blue)", "#C9D2DA"), ("Small floral (cream)", "#EADFCF")]
CERAMIC = [("Cream", "#E9E2D6"), ("White", "#F5F5F2"), ("Sage", "#A3AE95"), ("Terracotta", "#B5694B"), ("Charcoal", "#3C3C3C"),
           ("Speckled stone", "#CFC7BA")]
BEDDING = [("White cotton", "#F3F1EC"), ("Natural linen", "#E2D9C9"), ("Sage waffle", "#9BA58B"), ("Grey linen", "#B9B7B1"),
           ("Terracotta linen", "#B5694B")]
RUG = [("Cream wool", "#E6DFD3"), ("Jute", "#C4B190"), ("Grey wool", "#A9A7A2"), ("Charcoal wool", "#4A4C4E"),
       ("Rust kilim", "#A65A3A"), ("Blue-grey flatweave", "#8F9CA6"), ("Sage wool", "#A9B39C")]
OPTS = {"upholstery": UPH, "seat": UPH, "body": WOOD, "frame": WOOD, "top": WOOD, "legs": WOOD + METAL[:3], "wood": WOOD,
        "metal": METAL, "shade": FABRIC[:3] + [("Black", "#1E1E1E"), ("Brass", "#B08D57")], "fabric": FABRIC,
        "ceramic": CERAMIC, "bedding": BEDDING, "throw": BEDDING + UPH[:4], "rug": RUG, "all": None}

# ---- room-level option lists ---------------------------------------------------------------------------------------
WALL_PALETTES = {
    "Modern": [("Brilliant white", "#F7F7F4"), ("Cool grey", "#C9CCCB"), ("Concrete", "#A7A8A5"), ("Warm putty", "#D8CFC0"),
               ("Ink blue", "#2C3A4A"), ("Black olive", "#3B3F36"), ("Charcoal", "#3E4245")],
    "Contemporary": [("Warm white (signed off)", "#ECE6DC"), ("Soft clay (signed off accent)", "#CDB8A3"), ("Greige", "#CFC6B8"),
                     ("Mushroom", "#B9AA98"), ("Sage", "#A9B39C"), ("Plaster pink", "#E3C9B8"), ("Stone", "#D9D2C4")],
    "Country": [("Old white", "#ECE6D6"), ("Cream", "#F0E6CC"), ("Duck egg", "#B9CBC4"), ("Sage green", "#9EA88E"),
                ("Ochre", "#D2A94F"), ("Heritage red", "#8E3B2F"), ("Deep teal blue", "#33475B"), ("Mouse brown", "#8A7B68")],
    "Scandi": [("Pure white", "#F8F8F6"), ("Soft white", "#F2F0EB"), ("Pale grey", "#DAD9D5"), ("Light greige", "#D9D2C6"),
               ("Dusty pink", "#D9B8AE"), ("Pale sage", "#C5CCBC"), ("Fog blue", "#BCC7CC")],
}
FLOORS = [  # id, name, styles, hex, pattern, plank/tile size mm, rooms
    ("FIN-FLR-OAK", "Engineered oak, natural matt (signed off)", ["Contemporary", "Scandi"], "#B48C64", "planks", [190, 1900], "any"),
    ("FLR-OAK-HB", "Oak herringbone, natural oiled", ["Contemporary", "Country"], "#B08760", "herringbone", [90, 450], "any"),
    ("FLR-OAK-SMOKED", "Smoked oak, wide plank", ["Modern", "Contemporary"], "#6E5440", "planks", [240, 2200], "any"),
    ("FLR-OAK-PALE", "Pale white oak, wide plank", ["Scandi"], "#D2BC98", "planks", [220, 2200], "any"),
    ("FLR-PINE-PAINTED", "Painted pine boards, soft white", ["Scandi", "Country"], "#EDEAE2", "planks", [150, 3000], "any"),
    ("FLR-PINE", "Reclaimed pine boards", ["Country"], "#B98C5A", "planks", [175, 3000], "any"),
    ("FLR-WALNUT", "Walnut, narrow plank", ["Modern"], "#5C4033", "planks", [120, 1200], "any"),
    ("FIN-FLR-TILE", "Porcelain tile, warm grey stone look (signed off)", ["Contemporary", "Modern"], "#B9B1A6", "tiles", [600, 600], "wet"),
    ("FLR-TERRACOTTA", "Terracotta quarry tile", ["Country"], "#B0603F", "tiles", [300, 300], "wet"),
    ("FLR-ENCAUSTIC", "Patterned encaustic-look tile", ["Country", "Contemporary"], "#C9C1B2", "pattern", [200, 200], "wet"),
    ("FLR-SLATE", "Riven slate", ["Country", "Modern"], "#4A4B4E", "tiles", [400, 600], "wet"),
    ("FLR-CONCRETE", "Polished concrete / microcement", ["Modern"], "#A9A7A2", "concrete", [0, 0], "any"),
    ("FLR-TERRAZZO", "Terrazzo tile, pale", ["Modern", "Scandi"], "#E3DED6", "tiles", [600, 600], "wet"),
    ("FLR-CARPET-OAT", "Wool carpet, oatmeal", ["Contemporary", "Country"], "#D3C8B6", "carpet", [0, 0], "dry"),
    ("FLR-CARPET-GREY", "Wool carpet, pale grey", ["Scandi", "Modern"], "#C4C2BD", "carpet", [0, 0], "dry"),
    ("FLR-SISAL", "Sisal fitted carpet", ["Country", "Scandi"], "#C9B78F", "carpet", [0, 0], "dry"),
]
FRONTS = [  # id, name, styles, hex, door style
    ("KIT-FRONT", "Shaker, painted putty (signed off)", ["Contemporary", "Country"], "#C8BCAA", "shaker"),
    ("FR-SHAKER-SAGE", "Shaker, painted sage", ["Country", "Contemporary"], "#A3AE95", "shaker"),
    ("FR-SHAKER-NAVY", "Shaker, painted navy", ["Contemporary", "Country"], "#2E3A55", "shaker"),
    ("FR-INFRAME-CREAM", "In-frame, painted cream", ["Country"], "#EDE5D2", "inframe"),
    ("FR-INFRAME-BLUE", "In-frame, heritage blue", ["Country"], "#5D7380", "inframe"),
    ("FR-SLAB-WHITE", "Handleless slab, matt white", ["Modern", "Scandi"], "#F2F1EC", "slab"),
    ("FR-SLAB-GRAPHITE", "Handleless slab, graphite", ["Modern"], "#3A3C3E", "slab"),
    ("FR-SLAB-GREIGE", "Slab, soft greige", ["Modern", "Contemporary"], "#BDB4A6", "slab"),
    ("KIT-ISLAND", "Flat oak veneer (signed off on the island)", ["Scandi", "Contemporary"], "#B8936A", "slab"),
    ("FR-FLUTED-OAK", "Fluted oak", ["Contemporary", "Modern"], "#A98258", "fluted"),
    ("FR-BIRCH-PLY", "Birch ply, exposed edge", ["Scandi"], "#E0CDA9", "slab"),
    ("FR-PALE-GREY", "Slab, pale grey with oak pulls", ["Scandi"], "#D5D4CF", "slab"),
    ("KITB-FRONT", "Shaker, white satin (the kitchen today)", ["Country", "Contemporary"], "#F1EFEA", "shaker"),
]
TOPS = [  # id, name, styles, hex
    ("KIT-TOP", "White quartz, soft grey vein, 30 mm (signed off)", ["Contemporary", "Modern", "Scandi"], "#EEECE8"),
    ("TOP-CALACATTA", "Calacatta-look quartz, bold vein", ["Contemporary", "Modern"], "#F1EFEA"),
    ("TOP-MARBLE-HONED", "Honed Carrara marble", ["Country", "Contemporary"], "#E9E7E2"),
    ("TOP-OAK", "Solid oak stave, 40 mm", ["Country", "Scandi"], "#B8936A"),
    ("TOP-WALNUT", "Walnut stave, 40 mm", ["Modern", "Contemporary"], "#5C4033"),
    ("TOP-GRANITE-BLACK", "Black granite, honed", ["Modern", "Country"], "#262729"),
    ("TOP-CONCRETE", "Concrete-look composite", ["Modern"], "#9E9C97"),
    ("TOP-TERRAZZO", "Terrazzo, pale with grey chips", ["Modern", "Scandi"], "#E3DED6"),
    ("TOP-STEEL", "Brushed stainless steel", ["Modern"], "#B7B9BA"),
    ("TOP-LAMINATE-WHITE", "Matt white laminate (budget)", ["Scandi"], "#F2F1EC"),
    ("KITB-TOP", "Oak-effect laminate (the kitchen today)", ["Country"], "#A9845E"),
]

# ---- spec kind -> slot -------------------------------------------------------------------------------------------
SLOT = {
    "sofa": "sofa", "armchair": "armchair", "bed": "bed", "bedside": "bedside", "chest": "chest", "wardrobe": "wardrobe",
    "desk": "desk", "dining_table": "dining_table", "modern_coffee_table_01": "coffee_table", "table_low": "coffee_table",
    "side_table_01": "side_table", "WoodenTable_02": "side_table", "round_wooden_table_02": "dining_table",
    "dining_chair_02": "dining_chair", "bar_chair_round_01": "counter_stool", "bench_box": "bench",
    "steel_frame_shelves_01": "shelving", "alcove_unit": "bookcase", "bookcase": "bookcase", "island": "island",
    "kitchen_unit": "kitchen_unit", "wall_units": "kitchen_wall_units", "cooker_hood": "appliance",
    "washing_machine": "appliance", "tv": "tv",
    "pendant_drum": "pendant", "modern_ceiling_lamp_01": "pendant", "linear_pendant": "pendant", "flush_disc": "ceiling_light",
    "downlight_set": "downlights", "floor_lamp": "floor_lamp", "table_lamp": "table_lamp", "desk_lamp_arm_01": "table_lamp",
    "potted_plant_01": "plant_floor", "potted_plant_02": "plant_floor", "potted_plant_04": "plant_small",
    "planter_pot_clay": "plant_small",
    "framed_print": "art", "hanging_picture_frame_02": "art", "hanging_picture_frame_03": "art",
    "mirror_rect": "mirror", "mirror_round": "mirror", "ceramic_vase_01": "vase", "ceramic_vase_02": "vase",
    "ceramic_vase_03": "vase", "ceramic_vase_04": "vase", "wooden_bowl_01": "bowl", "wooden_bowl_02": "bowl",
    "book_encyclopedia_set_01": "books", "decorative_book_set_01": "books", "brass_candleholders": "candles",
    "wooden_candlestick": "candles", "wicker_basket_02": "basket", "standing_picture_frame_01": "photo_frame",
    "kettle": "kitchen_small", "toaster": "kitchen_small", "coffee_machine": "kitchen_small", "jug_01": "kitchen_small",
    "board": "kitchen_small", "bottle_pair_tray": "kitchen_small", "tea_towel": "kitchen_small",
    "rug": "rug", "cushion": "cushion", "throw_drape": "throw", "curtain_pair": "window_dressing",
    "roman_blind": "window_dressing", "towels": "towels", "towel_ring": "towels",
    "radiator_panel": "radiator", "towel_rail": "towel_rail",
    "hook_rail": "hooks", "mirror_cabinet": "mirror_cabinet",
    "slab": "fixed", "stove": "fixed", "tile_band": "fixed", "upstand": "fixed", "note_only": "fixed",
}
# the 2D/3D shape each slot is drawn with (the planner's builders)
SHAPE = {"plant_floor": "plant", "plant_small": "plant", "pendant": "pendant", "ceiling_light": "flush", "downlights": "downlights",
         "kitchen_small": "small", "vase": "small", "bowl": "small", "books": "books", "candles": "small", "basket": "small",
         "photo_frame": "small", "counter_stool": "stool", "dining_chair": "chair", "desk_chair": "chair", "bookcase": "cabinet",
         "shelving": "shelving", "chest": "cabinet", "bedside": "cabinet", "wardrobe": "tall_cabinet", "kitchen_unit": "kitchen_unit",
         "kitchen_wall_units": "wall_cabinet", "tv_unit": "cabinet", "sideboard": "cabinet", "coffee_table": "table",
         "side_table": "table", "dining_table": "table", "desk": "table", "console": "table", "art": "frame", "mirror": "mirror",
         "window_dressing": "curtains", "towels": "small", "towel_rail": "radiator", "hooks": "small", "mirror_cabinet": "wall_cabinet",
         "wc": "wc", "basin": "basin", "shower": "shower", "bath": "bath", "appliance": "cabinet", "fixed": "box", "bench": "bench",
         "ottoman": "ottoman", "rug": "rug", "cushion": "cushion", "throw": "throw", "tv": "tv", "radiator": "radiator",
         "island": "kitchen_unit", "floor_lamp": "floor_lamp", "table_lamp": "table_lamp", "wall_light": "wall_light",
         "sofa": "sofa", "armchair": "armchair", "bed": "bed", "clock": "small", "planter": "plant"}
MOUNT = {"pendant": "ceiling", "ceiling_light": "ceiling", "downlights": "ceiling", "art": "wall", "mirror": "wall",
         "window_dressing": "window", "wall_light": "wall", "kitchen_wall_units": "wall", "mirror_cabinet": "wall",
         "towel_rail": "wall", "radiator": "wall", "hooks": "wall", "tv": "wall"}
SURFACE = {"table_lamp", "plant_small", "vase", "bowl", "books", "candles", "photo_frame", "kitchen_small", "cushion", "throw",
           "towels", "clock"}
SLOT_NAMES = {
    "sofa": "Sofas", "armchair": "Armchairs", "ottoman": "Footstools and ottomans", "coffee_table": "Coffee tables",
    "side_table": "Side tables", "console": "Console tables", "dining_table": "Dining tables", "dining_chair": "Dining chairs",
    "counter_stool": "Counter stools", "bench": "Benches", "desk": "Desks and dressing tables", "desk_chair": "Desk chairs",
    "bed": "Beds", "bedside": "Bedside tables", "chest": "Chests of drawers", "wardrobe": "Wardrobes", "bookcase": "Bookcases and cupboards",
    "shelving": "Open shelving", "sideboard": "Sideboards and TV units", "tv": "TVs", "rug": "Rugs and mats", "cushion": "Cushions",
    "throw": "Throws", "window_dressing": "Curtains and blinds", "pendant": "Pendants", "ceiling_light": "Ceiling lights",
    "downlights": "Downlights", "wall_light": "Wall lights", "floor_lamp": "Floor lamps", "table_lamp": "Table and desk lamps",
    "plant_floor": "Floor plants", "plant_small": "Small plants and pots", "art": "Pictures", "mirror": "Mirrors", "vase": "Vases",
    "bowl": "Bowls", "books": "Books", "candles": "Candles", "basket": "Baskets", "photo_frame": "Photo frames", "clock": "Clocks",
    "kitchen_small": "Kitchen worktop things", "towels": "Towels", "radiator": "Radiators", "towel_rail": "Towel radiators",
    "wc": "WCs", "basin": "Basins", "shower": "Showers", "bath": "Baths", "hooks": "Hooks", "mirror_cabinet": "Mirror cabinets",
    "kitchen_unit": "Kitchen units", "kitchen_wall_units": "Kitchen wall units", "island": "Kitchen islands", "appliance": "Appliances",
    "fixed": "Fixed parts",
}
GROUPS = [  # catalogue browser: group -> slots
    ("Seating", ["sofa", "armchair", "ottoman", "dining_chair", "counter_stool", "bench", "desk_chair"]),
    ("Tables", ["coffee_table", "side_table", "console", "dining_table", "desk"]),
    ("Bedroom", ["bed", "bedside", "chest", "wardrobe"]),
    ("Storage", ["bookcase", "shelving", "sideboard", "hooks"]),
    ("Lighting", ["pendant", "ceiling_light", "downlights", "wall_light", "floor_lamp", "table_lamp"]),
    ("Soft furnishings", ["rug", "cushion", "throw", "window_dressing", "towels"]),
    ("Plants", ["plant_floor", "plant_small"]),
    ("Decor", ["art", "mirror", "vase", "bowl", "books", "candles", "basket", "photo_frame", "clock", "kitchen_small"]),
    ("Bathroom", ["wc", "basin", "shower", "bath", "mirror_cabinet", "towel_rail"]),
    ("Heating and tech", ["radiator", "tv"]),
    ("Kitchen", ["kitchen_unit", "kitchen_wall_units", "island", "appliance"]),
]

# spec seeds: style tags for the signed-off "modern-warm" board (oak, boucle, linen, white shaker)
SEED_STYLES = {"default": ["Contemporary"], "WoodenTable_02": ["Scandi", "Contemporary"], "round_wooden_table_02": ["Scandi", "Country"],
               "dining_chair_02": ["Contemporary", "Scandi"], "steel_frame_shelves_01": ["Modern"], "modern_coffee_table_01": ["Modern", "Contemporary"],
               "modern_ceiling_lamp_01": ["Modern", "Contemporary"], "desk_lamp_arm_01": ["Modern"], "wicker_basket_02": ["Country", "Scandi"],
               "table_low": ["Contemporary", "Country"], "bench_box": ["Scandi", "Country"], "linear_pendant": ["Modern"],
               "planter_pot_clay": ["Country", "Contemporary"], "potted_plant_01": STYLES, "potted_plant_02": STYLES, "potted_plant_04": STYLES}

PH = "polyhaven"


def ph(aid):
    return {"source": "polyhaven", "id": aid, "url": f"https://polyhaven.com/a/{aid}", "licence": "CC0"}


# ---- alternatives: (slot, name, styles, [W,D,H] mm, polyhaven id or None, parts {part: default hex/finish}, description)
ALT = [
    # sofas
    ("sofa", "Poly Haven 'Sofa 01', 3-seat", ["Contemporary"], [1571, 658, 796], "Sofa_01", {"upholstery": "#9AA39A"}, "compact 3-seat fabric sofa (1.57 m)"),
    ("sofa", "Poly Haven 'Sofa 02', 3-seat", ["Contemporary", "Modern"], [1807, 817, 709], "sofa_02", {"upholstery": "#B9B7B1"}, "low 3-seat fabric sofa (1.81 m)"),
    ("sofa", "Poly Haven 'Sofa 03', large", ["Modern"], [2731, 925, 1118], "sofa_03", {"upholstery": "#4A4C4E"}, "large sofa (2.73 m): needs a big wall"),
    ("sofa", "Low modular 3-seat, boucle", ["Modern"], [2200, 1000, 700], None, {"upholstery": "#EFE8DA", "legs": "#1E1E1E"}, "deep low seat, square arms, hidden plinth"),
    ("sofa", "Track-arm 3-seat, charcoal wool", ["Modern"], [2100, 920, 760], None, {"upholstery": "#4A4C4E", "legs": "#1E1E1E"}, "slim track arms, black metal legs"),
    ("sofa", "Curved 3-seat, oatmeal boucle", ["Contemporary"], [2150, 950, 740], None, {"upholstery": "#D8CEBF", "legs": "#B8936A"}, "soft curved back, oak plinth"),
    ("sofa", "2-seat loveseat, sage linen", ["Contemporary", "Scandi"], [1550, 880, 780], None, {"upholstery": "#9BA58B", "legs": "#B8936A"}, "two seats, loose linen cover"),
    ("sofa", "Rolled-arm 3-seat, linen loose cover", ["Country"], [2050, 950, 860], None, {"upholstery": "#E2D9C9", "legs": "#6E5440"}, "classic rolled arms, turned legs, skirt optional"),
    ("sofa", "Chesterfield-style 3-seat, cognac leather", ["Country"], [2050, 900, 760], None, {"upholstery": "#8B5A2B", "legs": "#5C4033"}, "buttoned back and arms"),
    ("sofa", "Wooden-frame 3-seat, oak + wool cushions", ["Scandi"], [1950, 820, 780], None, {"upholstery": "#B9B7B1", "frame": "#D7BE98"}, "exposed oak frame, loose cushions"),
    ("sofa", "Slim 3-seat on tapered legs, pale grey", ["Scandi"], [2000, 860, 780], None, {"upholstery": "#C9CCCB", "legs": "#D7BE98"}, "light, raised on legs"),
    ("sofa", "Corner sofa (L), stone linen", ["Contemporary", "Modern"], [2600, 1700, 760], None, {"upholstery": "#CFC6B4", "legs": "#1E1E1E"}, "L-shaped: only fits a big room"),
    # armchairs
    ("armchair", "Poly Haven 'Arm Chair 01'", ["Country"], [848, 766, 1065], "ArmChair_01", {"upholstery": "#B5694B"}, "upholstered wing-back style armchair"),
    ("armchair", "Poly Haven 'Modern Arm Chair 01'", ["Modern"], [820, 986, 1022], "modern_arm_chair_01", {"upholstery": "#4A4C4E"}, "modern lounge armchair"),
    ("armchair", "Poly Haven 'Mid Century Lounge Chair'", ["Scandi", "Contemporary"], [1008, 1190, 1169], "mid_century_lounge_chair", {"upholstery": "#8B5A2B", "frame": "#5C4033"}, "mid-century lounge chair: deep footprint"),
    ("armchair", "Poly Haven 'Green Chair 01'", ["Contemporary"], [673, 664, 1058], "GreenChair_01", {"upholstery": "#2F4A3A"}, "compact upholstered chair"),
    ("armchair", "Poly Haven 'Rocking Chair 01'", ["Country"], [708, 833, 994], "Rockingchair_01", {"frame": "#6E5440"}, "wooden rocking chair"),
    ("armchair", "Poly Haven 'Gallinera Chair'", ["Scandi"], [580, 603, 1033], "gallinera_chair", {"frame": "#B8936A"}, "light wooden chair"),
    ("armchair", "Tub chair, boucle", ["Contemporary", "Modern"], [760, 760, 720], None, {"upholstery": "#EFE8DA"}, "rounded tub, swivel base"),
    ("armchair", "Lounge chair, oak frame + sheepskin", ["Scandi"], [700, 780, 760], None, {"upholstery": "#EFE8DA", "frame": "#D7BE98"}, "low lounge chair"),
    ("armchair", "Wingback, ticking stripe", ["Country"], [800, 860, 1080], None, {"upholstery": "#C9D2DA", "legs": "#5C4033"}, "tall wingback"),
    ("ottoman", "Poly Haven 'Ottoman 01'", ["Contemporary", "Country"], [884, 621, 624], "Ottoman_01", {"upholstery": "#B9B7B1"}, "upholstered ottoman"),
    ("ottoman", "Round pouffe, wool", ["Scandi", "Modern"], [500, 500, 400], None, {"upholstery": "#B9B7B1"}, "knitted pouffe"),
    ("ottoman", "Footstool, velvet, turned legs", ["Country"], [700, 450, 420], None, {"upholstery": "#2F4A3A", "legs": "#5C4033"}, "small footstool"),
    # coffee / side / console
    ("coffee_table", "Poly Haven 'Modern Coffee Table 02', square", ["Modern"], [1199, 1199, 369], "modern_coffee_table_02", {"top": "#3C3C3C"}, "large square low table"),
    ("coffee_table", "Poly Haven 'Coffee Table Round 01'", ["Contemporary", "Scandi"], [1301, 1301, 491], "coffee_table_round_01", {"top": "#B8936A"}, "large round coffee table (1.3 m)"),
    ("coffee_table", "Poly Haven 'Coffee Table 01'", ["Country"], [1540, 972, 523], "CoffeeTable_01", {"top": "#6E5440"}, "big wooden coffee table"),
    ("coffee_table", "Poly Haven 'Industrial Coffee Table'", ["Modern"], [778, 757, 638], "industrial_coffee_table", {"top": "#6E5440", "legs": "#1E1E1E"}, "metal and wood"),
    ("coffee_table", "Poly Haven 'Chinese Tea Table'", ["Country"], [841, 835, 498], "chinese_tea_table", {"top": "#5C4033"}, "low square tea table"),
    ("coffee_table", "Oval oak coffee table", ["Scandi"], [1200, 650, 400], None, {"top": "#D7BE98"}, "soft oval, splayed legs"),
    ("coffee_table", "Travertine-look plinth table", ["Contemporary"], [1100, 600, 350], None, {"top": "#D9CDB8"}, "solid plinth"),
    ("coffee_table", "Glass and black steel coffee table", ["Modern"], [1100, 550, 380], None, {"top": "#BFC7C8", "legs": "#1E1E1E"}, "slim frame"),
    ("coffee_table", "Pine farmhouse coffee table", ["Country"], [1100, 600, 450], None, {"top": "#C9A06B"}, "turned legs, shelf under"),
    ("side_table", "Poly Haven 'Side Table Tall 01'", ["Modern", "Contemporary"], [383, 383, 761], "side_table_tall_01", {"top": "#3C3C3C"}, "tall round side table"),
    ("side_table", "Poly Haven 'Small Wooden Table 01'", ["Scandi", "Country"], [916, 439, 533], "small_wooden_table_01", {"top": "#B8936A"}, "small long table"),
    ("side_table", "Poly Haven 'Gallinera Table'", ["Scandi"], [830, 518, 487], "gallinera_table", {"top": "#B8936A"}, "low wooden table"),
    ("side_table", "Poly Haven 'Painted Wooden Nightstand'", ["Country"], [504, 508, 615], "painted_wooden_nightstand", {"body": "#A3AE95"}, "painted nightstand"),
    ("side_table", "Round marble side table", ["Contemporary", "Modern"], [450, 450, 520], None, {"top": "#E9E7E2", "legs": "#B08D57"}, "marble top, brass base"),
    ("side_table", "Nesting tables (2), oak", ["Scandi"], [500, 400, 500], None, {"top": "#D7BE98"}, "two tables that nest"),
    ("console", "Poly Haven 'Classic Console 01'", ["Country"], [1543, 589, 949], "ClassicConsole_01", {"body": "#5C4033"}, "classic console table"),
    ("console", "Poly Haven 'Chinese Console Table'", ["Country", "Contemporary"], [1719, 338, 660], "chinese_console_table", {"body": "#3C2A1E"}, "long narrow console"),
    ("console", "Slim oak console", ["Scandi", "Contemporary"], [1000, 300, 800], None, {"top": "#B8936A"}, "narrow hall console"),
    ("console", "Black steel console", ["Modern"], [1100, 320, 780], None, {"top": "#1E1E1E"}, "thin frame and shelf"),
    # dining
    ("dining_table", "Poly Haven 'Round Wooden Table 01', 1.4 m", ["Country", "Scandi"], [1399, 1399, 1005], "round_wooden_table_01", {"top": "#B8936A"}, "large round table (high: check the height)"),
    ("dining_table", "Poly Haven 'Painted Wooden Table', 2.4 m", ["Country"], [2405, 1136, 958], "painted_wooden_table", {"top": "#C9A06B", "legs": "#A3AE95"}, "long farmhouse table"),
    ("dining_table", "Poly Haven 'Wooden Table 01'", ["Country"], [1799, 657, 548], "WoodenTable_01", {"top": "#6E5440"}, "long low wooden table"),
    ("dining_table", "Oak table for 6, pedestal legs", ["Contemporary"], [1800, 950, 750], None, {"top": "#B8936A"}, "two pedestal bases"),
    ("dining_table", "Round oak table for 4", ["Scandi", "Contemporary"], [1200, 1200, 750], None, {"top": "#D7BE98"}, "1.2 m round, central leg"),
    ("dining_table", "Black ash table for 6", ["Modern"], [1800, 900, 750], None, {"top": "#2B2B2B"}, "slim black frame"),
    ("dining_table", "Concrete-top table, steel legs", ["Modern"], [2000, 950, 750], None, {"top": "#9E9C97", "legs": "#1E1E1E"}, "heavy slab top"),
    ("dining_table", "Extending farmhouse table, pine", ["Country"], [1600, 900, 760], None, {"top": "#C9A06B", "legs": "#F2F0EA"}, "extends to 2.2 m"),
    ("dining_table", "Pale oak table for 6, splayed legs", ["Scandi"], [1800, 900, 740], None, {"top": "#D7BE98"}, "light and simple"),
    ("dining_chair", "Poly Haven 'Painted Wooden Chair 01'", ["Country"], [431, 539, 956], "painted_wooden_chair_01", {"frame": "#A3AE95"}, "painted wooden chair"),
    ("dining_chair", "Poly Haven 'Painted Wooden Chair 02'", ["Country"], [639, 662, 1263], "painted_wooden_chair_02", {"frame": "#5D7380"}, "tall painted chair"),
    ("dining_chair", "Poly Haven 'School Chair 01'", ["Modern", "Scandi"], [565, 675, 1006], "SchoolChair_01", {"frame": "#B8936A", "metal": "#1E1E1E"}, "wood and steel chair"),
    ("dining_chair", "Poly Haven 'Gallinera Chair'", ["Scandi"], [580, 603, 1033], "gallinera_chair", {"frame": "#B8936A"}, "light wooden chair"),
    ("dining_chair", "Wishbone-style oak chair, paper cord", ["Scandi"], [550, 510, 760], None, {"frame": "#D7BE98", "seat": "#D2C29C"}, "curved back, woven seat"),
    ("dining_chair", "Upholstered dining chair, boucle", ["Contemporary"], [480, 560, 820], None, {"seat": "#EFE8DA", "legs": "#B8936A"}, "curved upholstered back"),
    ("dining_chair", "Moulded chair, black", ["Modern"], [460, 530, 810], None, {"seat": "#1E1E1E", "legs": "#1E1E1E"}, "one-piece shell"),
    ("dining_chair", "Ladder-back chair, rush seat", ["Country"], [470, 480, 980], None, {"frame": "#6E5440", "seat": "#C4B190"}, "rush seat, ladder back"),
    ("counter_stool", "Poly Haven 'Metal Stool 01'", ["Modern"], [351, 354, 882], "metal_stool_01", {"metal": "#1E1E1E"}, "tall metal stool"),
    ("counter_stool", "Poly Haven 'Metal Stool 03' with back", ["Modern"], [460, 470, 1023], "metal_stool_03", {"metal": "#1E1E1E"}, "metal stool with back"),
    ("counter_stool", "Oak counter stool, woven seat", ["Scandi", "Country"], [420, 420, 650], None, {"frame": "#D7BE98", "seat": "#D2C29C"}, "low back"),
    ("counter_stool", "Upholstered counter stool, sage", ["Contemporary"], [450, 480, 900], None, {"seat": "#9BA58B", "legs": "#B08D57"}, "padded seat and back"),
    ("counter_stool", "Poly Haven 'Painted Wooden Stool'", ["Country"], [384, 406, 578], "painted_wooden_stool", {"frame": "#A3AE95"}, "low painted stool (too low for a 910 counter)"),
    ("bench", "Poly Haven 'Painted Wooden Bench'", ["Country"], [1164, 496, 889], "painted_wooden_bench", {"frame": "#A3AE95"}, "painted bench with back"),
    ("bench", "Poly Haven 'Folding Wooden Stool'", ["Country", "Scandi"], [527, 547, 441], "folding_wooden_stool", {"frame": "#B8936A"}, "folding stool"),
    ("bench", "Upholstered bench, linen", ["Contemporary"], [1200, 400, 450], None, {"upholstery": "#CFC6B4", "legs": "#B8936A"}, "end-of-bed or hall bench"),
    ("bench", "Black steel shoe bench, oak top", ["Modern"], [1000, 350, 450], None, {"top": "#B8936A", "metal": "#1E1E1E"}, "two shelves under"),
    ("bench", "Pale oak slatted bench", ["Scandi"], [1000, 360, 450], None, {"top": "#D7BE98"}, "slatted top"),
    ("desk", "Poly Haven 'School Desk 01'", ["Country"], [711, 545, 882], "SchoolDesk_01", {"top": "#B8936A"}, "small old school desk"),
    ("desk", "Oak desk, two drawers", ["Scandi", "Contemporary"], [1100, 550, 750], None, {"top": "#B8936A"}, "simple writing desk"),
    ("desk", "Black steel desk, walnut top", ["Modern"], [1200, 600, 740], None, {"top": "#5C4033", "legs": "#1E1E1E"}, "slim frame"),
    ("desk", "Painted dressing table", ["Country"], [1000, 480, 760], None, {"body": "#EDE5D2"}, "three drawers, turned legs"),
    ("desk", "Wall-hung desk shelf, oak", ["Scandi", "Modern"], [900, 400, 750], None, {"top": "#D7BE98"}, "floating desk (fixed to the wall)"),
    ("desk_chair", "Poly Haven 'Dining Chair 02'", ["Contemporary", "Scandi"], [433, 576, 973], "dining_chair_02", {"frame": "#B8936A"}, "the signed-off dining chair"),
    ("desk_chair", "Task chair, grey fabric", ["Modern"], [600, 600, 950], None, {"seat": "#7D7F80", "metal": "#1E1E1E"}, "swivel, castors"),
    ("desk_chair", "Bentwood chair", ["Country", "Scandi"], [430, 500, 860], None, {"frame": "#6E5440"}, "classic bentwood"),
    # bedroom
    ("bed", "Platform bed, oak, king", ["Scandi"], [1650, 2100, 900], None, {"frame": "#D7BE98", "bedding": "#F3F1EC"}, "low oak frame"),
    ("bed", "Low bed, walnut + black, king", ["Modern"], [1700, 2150, 850], None, {"frame": "#5C4033", "bedding": "#B9B7B1"}, "low, wide headboard"),
    ("bed", "Upholstered bed, linen, king", ["Contemporary"], [1650, 2150, 1250], None, {"frame": "#CFC6B4", "bedding": "#F3F1EC"}, "tall padded headboard"),
    ("bed", "Upholstered bed, linen, double", ["Contemporary"], [1500, 2100, 1200], None, {"frame": "#CFC6B4", "bedding": "#F3F1EC"}, "padded headboard, 1350 mattress"),
    ("bed", "Painted panel bed, double", ["Country"], [1500, 2100, 1150], None, {"frame": "#EDE5D2", "bedding": "#EADFCF"}, "wooden panelled head and foot"),
    ("bed", "Iron bedstead, double", ["Country"], [1450, 2050, 1200], None, {"frame": "#1E1E1E", "bedding": "#F3F1EC"}, "black iron frame"),
    ("bed", "Poly Haven 'Gothic Bed 01', double", ["Country"], [1493, 2039, 1533], "GothicBed_01", {"frame": "#5C4033"}, "ornate carved bed (heavy look)"),
    ("bed", "Poly Haven 'Vintage Day Bed'", ["Country"], [1972, 854, 1127], "vintage_day_bed", {"frame": "#6E5440"}, "single day bed"),
    ("bed", "Single bed, oak", ["Scandi"], [1000, 2050, 850], None, {"frame": "#D7BE98", "bedding": "#F3F1EC"}, "single, 900 mattress"),
    ("bedside", "Poly Haven 'Classic Nightstand 01'", ["Country"], [567, 424, 699], "ClassicNightstand_01", {"body": "#6E5440"}, "classic nightstand"),
    ("bedside", "Poly Haven 'Painted Wooden Nightstand'", ["Country"], [504, 508, 615], "painted_wooden_nightstand", {"body": "#A3AE95"}, "painted nightstand"),
    ("bedside", "Floating bedside shelf, oak", ["Scandi", "Modern"], [450, 300, 150], None, {"body": "#D7BE98"}, "wall-hung drawer"),
    ("bedside", "Round bedside table, black", ["Modern"], [400, 400, 500], None, {"body": "#1E1E1E"}, "one drawer"),
    ("bedside", "Rattan bedside, two drawers", ["Contemporary", "Country"], [450, 400, 550], None, {"body": "#B89668"}, "cane fronts"),
    ("bedside", "Pale oak bedside, one drawer", ["Scandi"], [420, 380, 520], None, {"body": "#D7BE98"}, "open shelf under"),
    ("chest", "Poly Haven 'Gothic Commode 01'", ["Country"], [1201, 580, 1212], "GothicCommode_01", {"body": "#5C4033"}, "carved commode"),
    ("chest", "Poly Haven 'Vintage Wooden Drawer 01'", ["Country"], [1715, 1006, 1090], "vintage_wooden_drawer_01", {"body": "#6E5440"}, "big old chest (1 m deep)"),
    ("chest", "Poly Haven 'Drawer Cabinet'", ["Modern", "Scandi"], [1141, 488, 1881], "drawer_cabinet", {"body": "#B8936A"}, "tall drawer cabinet"),
    ("chest", "Oak chest, 6 drawers", ["Scandi", "Contemporary"], [1200, 450, 800], None, {"body": "#B8936A"}, "wide low chest"),
    ("chest", "Painted chest, 3+2 drawers", ["Country"], [950, 480, 900], None, {"body": "#EDE5D2"}, "classic painted"),
    ("chest", "Black lacquer chest, handleless", ["Modern"], [1100, 450, 750], None, {"body": "#2B2B2B"}, "push-to-open"),
    ("wardrobe", "Poly Haven 'Vintage Cabinet 01'", ["Country"], [2021, 669, 2235], "vintage_cabinet_01", {"body": "#6E5440"}, "big vintage cabinet"),
    ("wardrobe", "Poly Haven 'Painted Wooden Cabinet 02'", ["Country"], [996, 729, 2568], "painted_wooden_cabinet_02", {"body": "#5D7380"}, "tall painted cupboard (2.57 m high)"),
    ("wardrobe", "2-door wardrobe, oak", ["Scandi", "Contemporary"], [1000, 600, 2000], None, {"body": "#B8936A"}, "two doors, rail and shelf"),
    ("wardrobe", "2-door wardrobe, white shaker", ["Contemporary", "Country"], [1000, 600, 2100], None, {"body": "#F2EFEA"}, "shaker doors"),
    ("wardrobe", "Sliding wardrobe, smoked glass", ["Modern"], [1800, 650, 2200], None, {"body": "#3A3C3E"}, "sliding doors: no swing space needed"),
    ("wardrobe", "Open clothes rail, black steel", ["Modern", "Scandi"], [1000, 450, 1700], None, {"body": "#1E1E1E"}, "open rail with shelf"),
    # storage
    ("bookcase", "Poly Haven 'Shelf 01'", ["Country", "Scandi"], [1003, 256, 2080], "Shelf_01", {"body": "#B8936A"}, "tall shallow shelf"),
    ("bookcase", "Poly Haven 'Wooden Bookshelf Worn'", ["Country"], [1373, 581, 2063], "wooden_bookshelf_worn", {"body": "#6E5440"}, "worn wooden bookshelf"),
    ("bookcase", "Poly Haven 'Painted Wooden Shelves'", ["Country"], [511, 367, 1125], "painted_wooden_shelves", {"body": "#A3AE95"}, "small painted shelves"),
    ("bookcase", "Poly Haven 'Painted Wooden Cabinet'", ["Country"], [1194, 616, 1181], "painted_wooden_cabinet", {"body": "#5D7380"}, "painted cupboard"),
    ("bookcase", "Poly Haven 'Chinese Cabinet'", ["Country"], [1262, 545, 2872], "chinese_cabinet", {"body": "#3C2A1E"}, "tall cabinet (2.87 m: too tall for 2.43 ceilings)"),
    ("bookcase", "Oak bookcase, 5 shelves", ["Scandi", "Contemporary"], [900, 320, 1900], None, {"body": "#B8936A"}, "simple"),
    ("bookcase", "Black steel and glass cabinet", ["Modern"], [900, 400, 1800], None, {"body": "#1E1E1E"}, "glazed doors"),
    ("bookcase", "Built-in alcove cupboard + shelves, painted", ["Country", "Contemporary"], [1000, 380, 2000], None, {"body": "#ECE6DC"}, "cupboard under, open shelves over"),
    ("shelving", "Poly Haven 'Steel Frame Shelves 02'", ["Modern"], [593, 502, 2141], "steel_frame_shelves_02", {"body": "#1E1E1E"}, "narrow steel shelving"),
    ("shelving", "Poly Haven 'Steel Frame Shelves 03'", ["Modern"], [2351, 721, 2311], "steel_frame_shelves_03", {"body": "#1E1E1E"}, "wide steel shelving"),
    ("shelving", "Wall shelves (3), oak", ["Scandi", "Contemporary"], [900, 220, 900], None, {"body": "#B8936A"}, "floating shelves"),
    ("sideboard", "Poly Haven 'Modern Wooden Cabinet', 2.4 m", ["Scandi", "Contemporary"], [2440, 520, 680], "modern_wooden_cabinet", {"body": "#B8936A"}, "long low cabinet"),
    ("sideboard", "Low TV unit, oak", ["Scandi", "Contemporary"], [1600, 420, 500], None, {"body": "#B8936A"}, "two doors, open shelf"),
    ("sideboard", "Fluted sideboard, walnut", ["Modern", "Contemporary"], [1600, 450, 750], None, {"body": "#5C4033"}, "fluted doors"),
    ("sideboard", "Painted dresser base", ["Country"], [1400, 480, 900], None, {"body": "#A3AE95"}, "drawers over cupboards"),
    ("hooks", "Oak hook rail, 4 hooks", ["Scandi", "Contemporary"], [600, 60, 90], None, {"wood": "#B8936A", "metal": "#1E1E1E"}, "the signed-off rail"),
    ("hooks", "Shaker peg rail, 6 pegs, painted", ["Country"], [900, 60, 90], None, {"wood": "#ECE6DC"}, "peg rail"),
    ("hooks", "Black steel hooks, 5", ["Modern"], [600, 60, 60], None, {"metal": "#1E1E1E"}, "slim hooks"),
    # lighting
    ("pendant", "Poly Haven 'Modern Ceiling Lamp 01'", ["Modern", "Contemporary"], [431, 431, 951], "modern_ceiling_lamp_01", {"shade": "#1E1E1E"}, "the signed-off island pendant"),
    ("pendant", "Poly Haven 'Hanging Industrial Lamp'", ["Modern"], [549, 549, 1355], "hanging_industrial_lamp", {"shade": "#1E1E1E"}, "industrial dome pendant"),
    ("pendant", "Poly Haven 'Lantern Chandelier 01'", ["Country"], [579, 574, 877], "lantern_chandelier_01", {"metal": "#1E1E1E"}, "lantern pendant"),
    ("pendant", "Poly Haven 'Chandelier 02'", ["Country"], [679, 619, 848], "Chandelier_02", {"metal": "#B08D57"}, "chandelier"),
    ("pendant", "Linen drum pendant 450", ["Contemporary"], [450, 450, 250], None, {"shade": "#E2D9C9"}, "the signed-off drum"),
    ("pendant", "Paper globe pendant 500", ["Scandi"], [500, 500, 500], None, {"shade": "#F4F2EC"}, "paper lantern"),
    ("pendant", "Pleated fabric pendant", ["Scandi", "Contemporary"], [400, 400, 300], None, {"shade": "#E2D9C9"}, "pleated shade"),
    ("pendant", "Opal glass globe, brass", ["Contemporary", "Modern"], [300, 300, 400], None, {"shade": "#F4F2EC", "metal": "#B08D57"}, "glass globe"),
    ("pendant", "Rattan pendant", ["Country", "Contemporary"], [450, 450, 350], None, {"shade": "#B89668"}, "woven rattan"),
    ("pendant", "Enamel dome pendant, cream", ["Country"], [350, 350, 250], None, {"shade": "#EDE5D2"}, "enamel dome"),
    ("pendant", "Linear LED bar pendant, black", ["Modern"], [1200, 80, 60], None, {"metal": "#1E1E1E"}, "the signed-off table pendant"),
    ("pendant", "Three-drop cluster, smoked glass", ["Modern"], [800, 250, 400], None, {"shade": "#5A5550"}, "three small globes on a bar"),
    ("ceiling_light", "Flush disc, opal", ["Modern", "Scandi"], [300, 300, 60], None, {"shade": "#F4F2EC"}, "the signed-off flush light"),
    ("ceiling_light", "Semi-flush linen", ["Contemporary"], [400, 400, 220], None, {"shade": "#E2D9C9"}, "semi-flush"),
    ("ceiling_light", "Ribbed glass flush, brass", ["Country", "Contemporary"], [300, 300, 150], None, {"shade": "#F4F2EC", "metal": "#B08D57"}, "ribbed glass"),
    ("ceiling_light", "Spot bar, 3 spots, black", ["Modern"], [800, 80, 120], None, {"metal": "#1E1E1E"}, "three adjustable spots"),
    ("downlights", "Recessed downlights, white", ["Modern", "Scandi", "Contemporary"], [85, 85, 10], None, {"metal": "#F2F2F0"}, "fire-rated LED downlights"),
    ("downlights", "Recessed downlights, black", ["Modern"], [85, 85, 10], None, {"metal": "#1E1E1E"}, "black bezels"),
    ("downlights", "Recessed downlights, brass", ["Contemporary"], [85, 85, 10], None, {"metal": "#B08D57"}, "brass bezels"),
    ("wall_light", "Poly Haven 'Industrial Wall Lamp'", ["Modern"], [273, 140, 429], "industrial_wall_lamp", {"metal": "#1E1E1E"}, "industrial arm lamp"),
    ("wall_light", "Poly Haven 'Industrial Wall Sconce'", ["Modern", "Country"], [150, 251, 341], "industrial_wall_sconce", {"metal": "#6B5236"}, "sconce"),
    ("wall_light", "Swing-arm wall light, brass", ["Contemporary", "Country"], [180, 500, 300], None, {"metal": "#B08D57", "shade": "#E2D9C9"}, "reading light"),
    ("wall_light", "Up-down wall light, white", ["Scandi", "Modern"], [100, 100, 200], None, {"metal": "#F2F2F0"}, "plaster up-down"),
    ("wall_light", "Picture light, brass", ["Country", "Contemporary"], [400, 120, 80], None, {"metal": "#B08D57"}, "over a picture"),
    ("floor_lamp", "Linen drum floor lamp", ["Contemporary"], [400, 400, 1550], None, {"shade": "#E2D9C9", "metal": "#1E1E1E"}, "the signed-off floor lamp"),
    ("floor_lamp", "Arc floor lamp, black", ["Modern"], [400, 1500, 1900], None, {"metal": "#1E1E1E", "shade": "#1E1E1E"}, "arcs over a sofa"),
    ("floor_lamp", "Tripod floor lamp, oak", ["Scandi", "Country"], [550, 550, 1550], None, {"wood": "#B8936A", "shade": "#F4F2EC"}, "tripod legs"),
    ("floor_lamp", "Paper column floor lamp", ["Scandi"], [300, 300, 1200], None, {"shade": "#F4F2EC"}, "paper column"),
    ("floor_lamp", "Brass reading lamp", ["Country", "Contemporary"], [300, 400, 1400], None, {"metal": "#B08D57", "shade": "#E2D9C9"}, "angled head"),
    ("table_lamp", "Ceramic table lamp, linen shade", ["Contemporary"], [300, 300, 480], None, {"ceramic": "#E9E2D6", "shade": "#E2D9C9"}, "the signed-off lamp"),
    ("table_lamp", "Poly Haven 'Desk Lamp Arm 01'", ["Modern"], [617, 408, 879], "desk_lamp_arm_01", {"metal": "#1E1E1E"}, "anglepoise-type desk lamp"),
    ("table_lamp", "Poly Haven 'Vintage Oil Lamp'", ["Country"], [219, 219, 801], "vintage_oil_lamp", {"metal": "#B08D57"}, "oil-lamp style"),
    ("table_lamp", "Poly Haven 'Lantern 01'", ["Country"], [122, 97, 294], "Lantern_01", {"metal": "#1E1E1E"}, "small lantern"),
    ("table_lamp", "Mushroom lamp, opal glass", ["Modern", "Scandi"], [300, 300, 350], None, {"shade": "#F4F2EC"}, "mushroom shape"),
    ("table_lamp", "Oak base lamp, pleated shade", ["Scandi"], [280, 280, 450], None, {"wood": "#D7BE98", "shade": "#F4F2EC"}, "pleated shade"),
    ("table_lamp", "Stoneware gourd lamp", ["Country", "Contemporary"], [320, 320, 550], None, {"ceramic": "#A3AE95", "shade": "#E2D9C9"}, "glazed gourd base"),
    # soft furnishings
    ("rug", "Wool rug, cream with border, 2.0 x 2.9", ["Contemporary"], [2000, 2900, 12], None, {"rug": "#E6DFD3"}, "large low-pile"),
    ("rug", "Wool rug, cream, 1.6 x 2.3", ["Contemporary", "Scandi"], [1600, 2300, 12], None, {"rug": "#E6DFD3"}, "medium"),
    ("rug", "Jute rug, 1.6 x 2.3", ["Country", "Scandi"], [1600, 2300, 12], None, {"rug": "#C4B190"}, "natural jute"),
    ("rug", "Flatweave, charcoal, 1.7 x 2.4", ["Modern"], [1700, 2400, 8], None, {"rug": "#4A4C4E"}, "flatweave"),
    ("rug", "Kilim, rust, 1.4 x 2.0", ["Country"], [1400, 2000, 8], None, {"rug": "#A65A3A"}, "patterned kilim"),
    ("rug", "Round wool rug, 1.6", ["Scandi", "Contemporary"], [1600, 1600, 12], None, {"rug": "#E6DFD3"}, "round"),
    ("rug", "Hall runner, 0.7 x 2.4", ["Contemporary", "Country", "Scandi", "Modern"], [700, 2400, 10], None, {"rug": "#C4B190"}, "runner"),
    ("rug", "Coir door mat", ["Country", "Scandi"], [600, 900, 15], None, {"rug": "#C4B190"}, "door mat"),
    ("rug", "Bath mat, cotton", ["Contemporary", "Scandi"], [500, 800, 10], None, {"rug": "#F3F1EC"}, "bath mat"),
    ("cushion", "Poly Haven 'Throw Pillows 01' (set)", ["Contemporary"], [1021, 627, 450], "throw_pillows_01", {"fabric": "#E2D9C9"}, "a set of throw pillows"),
    ("cushion", "Cushion 450, boucle", ["Contemporary", "Modern"], [450, 150, 450], None, {"fabric": "#EFE8DA"}, "square"),
    ("cushion", "Cushion 450, linen", ["Contemporary", "Scandi", "Country"], [450, 150, 450], None, {"fabric": "#9BA58B"}, "square"),
    ("cushion", "Lumbar cushion 300 x 600", ["Contemporary", "Modern"], [600, 150, 300], None, {"fabric": "#B5694B"}, "long"),
    ("cushion", "Floral cushion 450", ["Country"], [450, 150, 450], None, {"fabric": "#EADFCF"}, "printed"),
    ("throw", "Chunky knit throw", ["Contemporary", "Scandi"], [1300, 1700, 8], None, {"throw": "#EAE2D2"}, "knitted"),
    ("throw", "Wool tartan throw", ["Country"], [1300, 1700, 8], None, {"throw": "#8E3B2F"}, "tartan"),
    ("throw", "Waffle bed throw", ["Scandi", "Contemporary"], [2200, 600, 10], None, {"throw": "#9BA58B"}, "bed runner"),
    ("window_dressing", "Linen curtains, pair, pole", ["Contemporary", "Scandi"], [2000, 120, 2240], None, {"fabric": "#E2D9C9", "metal": "#1E1E1E"}, "the signed-off curtains (width follows the window)"),
    ("window_dressing", "Sheer voile curtains, pair", ["Scandi", "Modern"], [2000, 100, 2240], None, {"fabric": "#F4F2EC", "metal": "#F2F2F0"}, "light filtering"),
    ("window_dressing", "Velvet curtains, pair, blackout", ["Modern", "Contemporary"], [2000, 140, 2240], None, {"fabric": "#2E3A55", "metal": "#B08D57"}, "lined, blackout"),
    ("window_dressing", "Floral cotton curtains, pair", ["Country"], [2000, 130, 2240], None, {"fabric": "#EADFCF", "wood": "#6E5440"}, "printed, wooden pole"),
    ("window_dressing", "Linen roman blind", ["Contemporary", "Country"], [1200, 60, 1060], None, {"fabric": "#E2D9C9"}, "the signed-off blind (inside the reveal)"),
    ("window_dressing", "Roller blind, white", ["Modern", "Scandi"], [1200, 50, 1060], None, {"fabric": "#F4F2EC"}, "simple roller"),
    ("window_dressing", "Wooden venetian blind", ["Country", "Scandi"], [1200, 50, 1060], None, {"wood": "#B8936A"}, "50 mm slats"),
    ("window_dressing", "Aluminium venetian, black", ["Modern"], [1200, 40, 1060], None, {"metal": "#1E1E1E"}, "25 mm slats"),
    ("window_dressing", "Café shutters, painted", ["Country"], [1200, 60, 600], None, {"wood": "#F2F0EA"}, "lower half only"),
    ("window_dressing", "Full-height shutters, white", ["Contemporary", "Modern"], [1200, 60, 1200], None, {"wood": "#F2F0EA"}, "tier-on-tier"),
    ("towels", "Folded towels, white", STYLES, [450, 80, 500], None, {"fabric": "#F3F1EC"}, "two towels"),
    ("towels", "Folded towels, sage", ["Contemporary", "Scandi"], [450, 80, 500], None, {"fabric": "#9BA58B"}, "two towels"),
    ("towels", "Hand towel on ring", STYLES, [250, 80, 350], None, {"fabric": "#F3F1EC", "metal": "#1E1E1E"}, "hand towel"),
    # plants
    ("plant_floor", "Poly Haven 'Potted Plant 01', tall", STYLES, [588, 636, 1350], "potted_plant_01", {"ceramic": "#E9E2D6"}, "the signed-off tall plant"),
    ("plant_floor", "Poly Haven 'Potted Plant 02'", STYLES, [701, 657, 841], "potted_plant_02", {"ceramic": "#E9E2D6"}, "medium potted plant"),
    ("plant_floor", "Poly Haven 'Planter Box 01'", ["Country"], [912, 413, 424], "planter_box_01", {"wood": "#6E5440"}, "wooden planter box"),
    ("plant_floor", "Olive tree in terracotta", ["Country", "Contemporary"], [600, 600, 1600], None, {"ceramic": "#B5694B"}, "small olive tree"),
    ("plant_floor", "Fiddle-leaf fig in black pot", ["Modern"], [600, 600, 1700], None, {"ceramic": "#262626"}, "tall fig"),
    ("plant_floor", "Monstera in woven basket", ["Scandi", "Contemporary"], [800, 800, 1100], None, {"ceramic": "#C4B190"}, "wide monstera"),
    ("plant_small", "Poly Haven 'Potted Plant 04', succulent", STYLES, [170, 185, 267], "potted_plant_04", {"ceramic": "#E9E2D6"}, "small succulent"),
    ("plant_small", "Poly Haven 'Planter Pot Clay', herbs", ["Country", "Contemporary"], [265, 263, 221], "planter_pot_clay", {"ceramic": "#B5694B"}, "clay pot"),
    ("plant_small", "Trailing pothos in a stoneware pot", ["Scandi", "Contemporary"], [250, 250, 300], None, {"ceramic": "#CFC7BA"}, "trailing"),
    ("plant_small", "Snake plant, matt black pot", ["Modern"], [220, 220, 600], None, {"ceramic": "#262626"}, "upright"),
    # decor
    ("art", "Framed print 500 x 700, oak frame", ["Contemporary", "Scandi"], [500, 25, 700], None, {"frame": "#B8936A"}, "the signed-off print"),
    ("art", "Large framed print 700 x 1000, oak", ["Contemporary", "Scandi"], [700, 25, 1000], None, {"frame": "#B8936A"}, "large print"),
    ("art", "Black-framed print 600 x 800", ["Modern"], [600, 25, 800], None, {"frame": "#1E1E1E"}, "black frame"),
    ("art", "Gallery wall (5 frames)", ["Contemporary", "Country"], [1400, 25, 900], None, {"frame": "#B8936A"}, "mixed frames"),
    ("art", "Canvas, abstract 900 x 900", ["Modern", "Contemporary"], [900, 40, 900], None, {"frame": "#F2F0EA"}, "unframed canvas"),
    ("art", "Poly Haven 'Hanging Picture Frame 01'", ["Contemporary"], [593, 15, 840], "hanging_picture_frame_01", {"frame": "#B8936A"}, "picture frame"),
    ("art", "Poly Haven 'Hanging Picture Frame 02'", ["Contemporary"], [751, 33, 499], "hanging_picture_frame_02", {"frame": "#B8936A"}, "landscape frame"),
    ("art", "Poly Haven 'Hanging Picture Frame 03'", ["Contemporary"], [385, 31, 502], "hanging_picture_frame_03", {"frame": "#B8936A"}, "small frame"),
    ("art", "Poly Haven 'Fancy Picture Frame 01'", ["Country"], [603, 19, 464], "fancy_picture_frame_01", {"frame": "#B08D57"}, "ornate frame"),
    ("art", "Poly Haven 'Fancy Picture Frame 02'", ["Country"], [660, 89, 771], "fancy_picture_frame_02", {"frame": "#B08D57"}, "ornate frame"),
    ("mirror", "Round mirror 600, oak frame", ["Scandi", "Contemporary"], [600, 25, 600], None, {"frame": "#B8936A"}, "round"),
    ("mirror", "Rectangular mirror 400 x 600", ["Modern", "Contemporary"], [400, 20, 600], None, {"frame": "#1E1E1E"}, "slim frame"),
    ("mirror", "Arched mirror 600 x 1000, brass", ["Contemporary", "Modern"], [600, 25, 1000], None, {"frame": "#B08D57"}, "arched top"),
    ("mirror", "Overmantel mirror, gilt", ["Country"], [900, 40, 1100], None, {"frame": "#B08D57"}, "large period mirror"),
    ("mirror", "Poly Haven 'Ornate Mirror 01'", ["Country"], [486, 25, 744], "ornate_mirror_01", {"frame": "#B08D57"}, "ornate mirror"),
    ("vase", "Poly Haven 'Ceramic Vase 01'", ["Contemporary", "Scandi"], [204, 206, 401], "ceramic_vase_01", {"ceramic": "#E9E2D6"}, "vase"),
    ("vase", "Poly Haven 'Ceramic Vase 02'", ["Contemporary", "Scandi"], [219, 221, 309], "ceramic_vase_02", {"ceramic": "#E9E2D6"}, "vase"),
    ("vase", "Poly Haven 'Ceramic Vase 03'", ["Contemporary", "Modern"], [112, 112, 414], "ceramic_vase_03", {"ceramic": "#E9E2D6"}, "slim vase"),
    ("vase", "Poly Haven 'Ceramic Vase 04'", ["Contemporary"], [183, 181, 342], "ceramic_vase_04", {"ceramic": "#E9E2D6"}, "vase"),
    ("vase", "Poly Haven 'Antique Ceramic Vase 01'", ["Country"], [255, 255, 439], "antique_ceramic_vase_01", {"ceramic": "#CFC7BA"}, "antique vase"),
    ("vase", "Poly Haven 'Brass Vase 01'", ["Country", "Contemporary"], [227, 227, 692], "brass_vase_01", {"metal": "#B08D57"}, "tall brass vase"),
    ("vase", "Poly Haven 'Brass Vase 02'", ["Country"], [210, 210, 528], "brass_vase_02", {"metal": "#B08D57"}, "brass vase"),
    ("vase", "Poly Haven 'Metal Jug'", ["Country", "Modern"], [196, 195, 287], "metal_jug", {"metal": "#B7B9BA"}, "metal jug"),
    ("bowl", "Poly Haven 'Wooden Bowl 01'", ["Scandi", "Country"], [313, 309, 93], "wooden_bowl_01", {"wood": "#B8936A"}, "wooden bowl"),
    ("bowl", "Poly Haven 'Wooden Bowl 02'", ["Scandi", "Country"], [130, 124, 73], "wooden_bowl_02", {"wood": "#B8936A"}, "small bowl"),
    ("bowl", "Poly Haven 'Carved Wooden Plate'", ["Country"], [271, 268, 38], "carved_wooden_plate", {"wood": "#6E5440"}, "carved plate"),
    ("bowl", "Poly Haven 'Brass Pot 02'", ["Country", "Contemporary"], [366, 302, 108], "brass_pot_02", {"metal": "#B08D57"}, "brass bowl"),
    ("bowl", "Stoneware fruit bowl", ["Contemporary", "Modern"], [300, 300, 100], None, {"ceramic": "#CFC7BA"}, "stoneware"),
    ("books", "Poly Haven 'Book Encyclopedia Set 01'", STYLES, [551, 163, 237], "book_encyclopedia_set_01", {}, "book set"),
    ("books", "Poly Haven 'Decorative Book Set 01'", STYLES, [2505, 321, 285], "decorative_book_set_01", {}, "a long row of books"),
    ("books", "Book stack (3)", STYLES, [300, 220, 90], None, {}, "coffee-table books"),
    ("candles", "Poly Haven 'Brass Candleholders'", ["Country", "Contemporary"], [1052, 364, 835], "brass_candleholders", {"metal": "#B08D57"}, "a set of brass candleholders"),
    ("candles", "Poly Haven 'Brass Diya Lantern'", ["Country"], [123, 123, 380], "brass_diya_lantern", {"metal": "#B08D57"}, "brass lantern"),
    ("candles", "Wooden candlestick", ["Scandi", "Country"], [100, 100, 220], None, {"wood": "#B8936A"}, "candlestick"),
    ("candles", "Pillar candles on a tray", ["Modern", "Contemporary"], [300, 150, 200], None, {"ceramic": "#F5F5F2"}, "three pillars"),
    ("basket", "Poly Haven 'Wicker Basket 01'", ["Country", "Scandi"], [383, 295, 117], "wicker_basket_01", {}, "shallow basket"),
    ("basket", "Poly Haven 'Wicker Basket 02'", ["Country", "Scandi"], [374, 270, 218], "wicker_basket_02", {}, "basket"),
    ("basket", "Seagrass log basket", ["Country", "Contemporary"], [450, 450, 400], None, {}, "log or blanket basket"),
    ("photo_frame", "Poly Haven 'Standing Picture Frame 01'", STYLES, [200, 100, 249], "standing_picture_frame_01", {}, "photo frame"),
    ("photo_frame", "Poly Haven 'Standing Picture Frame 02'", STYLES, [216, 102, 266], "standing_picture_frame_02", {}, "photo frame"),
    ("clock", "Poly Haven 'Mantel Clock 01'", ["Country"], [483, 250, 160], "mantel_clock_01", {"wood": "#5C4033"}, "mantel clock"),
    ("clock", "Poly Haven 'Wall Clock'", ["Modern", "Scandi"], [320, 47, 320], "wall_clock", {}, "wall clock"),
    ("clock", "Poly Haven 'Vintage Grandfather Clock 01'", ["Country"], [996, 795, 2190], "vintage_grandfather_clock_01", {"wood": "#5C4033"}, "grandfather clock (floor)"),
    ("kitchen_small", "Poly Haven 'Vintage Electric Kettle'", ["Country"], [320, 248, 304], "vintage_electric_kettle", {}, "retro kettle"),
    ("kitchen_small", "Poly Haven 'Jug 01'", ["Country", "Contemporary"], [275, 167, 211], "jug_01", {"ceramic": "#E9E2D6"}, "jug"),
    ("kitchen_small", "Poly Haven 'Pot Enamel 01'", ["Country"], [262, 180, 178], "pot_enamel_01", {}, "enamel pot"),
    ("kitchen_small", "Poly Haven 'Tea Set 01'", ["Country"], [918, 483, 164], "tea_set_01", {}, "tea set on tray"),
    ("kitchen_small", "Poly Haven 'Wine Bottles 01'", STYLES, [676, 80, 331], "wine_bottles_01", {}, "row of bottles"),
    # bathroom
    ("wc", "Close-coupled WC", ["Contemporary", "Country"], [370, 665, 800], None, {"ceramic": "#F5F5F2"}, "standard"),
    ("wc", "Back-to-wall WC + unit", ["Contemporary", "Modern"], [500, 600, 900], None, {"ceramic": "#F5F5F2", "body": "#C8BCAA"}, "cistern hidden in a unit"),
    ("wc", "Wall-hung WC, concealed cistern", ["Modern", "Scandi"], [370, 530, 1000], None, {"ceramic": "#F5F5F2"}, "frame in the wall, black plate"),
    ("wc", "High-level cistern WC", ["Country"], [420, 700, 2000], None, {"ceramic": "#F5F5F2", "wood": "#5C4033"}, "traditional"),
    ("basin", "Semi-pedestal basin 400", ["Contemporary", "Scandi"], [390, 380, 850], None, {"ceramic": "#F5F5F2"}, "small"),
    ("basin", "Vanity 600, oak, basin over", ["Scandi", "Contemporary"], [600, 450, 850], None, {"body": "#B8936A", "ceramic": "#F5F5F2"}, "drawers under"),
    ("basin", "Wall-hung vanity 500, oak", ["Modern", "Contemporary"], [500, 400, 850], None, {"body": "#B8936A", "ceramic": "#F5F5F2"}, "the signed-off en-suite vanity"),
    ("basin", "Washstand, painted, Belfast-style basin", ["Country"], [800, 500, 850], None, {"body": "#A3AE95", "ceramic": "#F5F5F2"}, "open shelf"),
    ("basin", "Pedestal basin 550", ["Country"], [550, 450, 850], None, {"ceramic": "#F5F5F2"}, "classic pedestal"),
    ("shower", "Shower tray + 2-sided glass, black", ["Modern", "Contemporary"], [940, 840, 1950], None, {"metal": "#1E1E1E"}, "the signed-off enclosure"),
    ("shower", "Walk-in shower 1800 x 900", ["Modern", "Contemporary"], [1740, 838, 2000], None, {"metal": "#1E1E1E"}, "fixed glass panel"),
    ("shower", "Quadrant enclosure 900, chrome", ["Contemporary"], [900, 900, 1950], None, {"metal": "#C8CCCF"}, "curved door"),
    ("bath", "Bath 1700 x 700, panelled", ["Contemporary", "Scandi"], [1700, 700, 560], None, {"ceramic": "#F5F5F2", "body": "#ECE6DC"}, "standard bath"),
    ("bath", "Roll-top bath, painted", ["Country"], [1700, 750, 650], None, {"ceramic": "#F5F5F2", "body": "#2E3A55"}, "freestanding"),
    ("bath", "Freestanding oval bath, stone resin", ["Modern"], [1600, 750, 580], None, {"ceramic": "#F5F5F2"}, "freestanding"),
    ("mirror_cabinet", "Mirror cabinet 450", ["Contemporary", "Modern"], [450, 120, 600], None, {"body": "#F5F5F2"}, "the signed-off cabinet"),
    ("mirror_cabinet", "Mirror cabinet 600, oak", ["Scandi"], [600, 140, 700], None, {"body": "#B8936A"}, "oak frame"),
    ("mirror_cabinet", "Painted bathroom cabinet", ["Country"], [500, 150, 650], None, {"body": "#A3AE95"}, "painted"),
    ("towel_rail", "Towel radiator 500 x 1200, matt black", ["Modern", "Contemporary"], [500, 60, 1200], None, {"metal": "#1E1E1E"}, "the signed-off towel rail"),
    ("towel_rail", "Towel radiator 500 x 1200, chrome", ["Contemporary", "Scandi"], [500, 60, 1200], None, {"metal": "#C8CCCF"}, "chrome ladder"),
    ("towel_rail", "Traditional towel rail, brass", ["Country"], [600, 120, 950], None, {"metal": "#B08D57"}, "traditional"),
    # heating and tech
    ("radiator", "Panel radiator, white", ["Modern", "Contemporary", "Scandi"], [800, 100, 600], None, {"metal": "#F1F0EA"}, "type 22 panel"),
    ("radiator", "Column radiator, 2-column, white", ["Country", "Contemporary"], [800, 100, 600], None, {"metal": "#F1F0EA"}, "column"),
    ("radiator", "Column radiator, anthracite", ["Modern", "Country"], [800, 100, 600], None, {"metal": "#3A3C3E"}, "column, dark"),
    ("radiator", "Vertical designer radiator, black", ["Modern"], [450, 90, 1800], None, {"metal": "#1E1E1E"}, "vertical"),
    ("radiator", "Cast-iron radiator, painted", ["Country"], [900, 160, 650], None, {"metal": "#5D7380"}, "period cast iron"),
    ("tv", "55-inch TV", ["Modern", "Contemporary", "Scandi", "Country"], [1230, 30, 710], None, {}, "wall-mounted"),
    ("tv", "65-inch TV", ["Modern", "Contemporary"], [1450, 30, 830], None, {}, "wall-mounted"),
    ("tv", "Frame-style TV 55, oak frame", ["Contemporary", "Scandi"], [1240, 30, 715], None, {"frame": "#B8936A"}, "looks like a picture when off"),
    ("tv", "Poly Haven 'Television 01' (vintage)", ["Country"], [599, 470, 456], "Television_01", {}, "vintage TV (decor)"),
]


def finish_hex(spec):
    return {f["id"]: f["colour_srgb"] for f in spec["finishes"]}


def opts_for(parts):
    out = {}
    for p in parts:
        o = OPTS.get(p)
        if o:
            out[p] = [{"name": n, "hex": h} for n, h in o]
    return out


def slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--spec", default=None)
    a = ap.parse_args()
    spec_dir = os.path.join(ROOT, "assets", "sites", a.site, "spec")
    spec_name = a.spec or sorted(f for f in os.listdir(spec_dir) if f.startswith("spec_v") and f.endswith(".json"))[-1]
    spec = json.load(open(os.path.join(spec_dir, spec_name), encoding="utf-8"))
    fin = finish_hex(spec)
    lib_root = os.path.join(ROOT, "assets", "library")
    entries, by_key, spec_map = [], {}, {"before": {}, "after": {}}
    used_ids = set()

    def model_for(aid):
        if not aid:
            return None
        p = os.path.join(lib_root, "polyhaven", aid, aid + ".gltf")
        return os.path.relpath(p, ROOT) if os.path.isfile(p) else None

    def add(e):
        base = e["id"]
        k = 2
        while e["id"] in used_ids:
            e["id"] = f"{base}-{k}"; k += 1
        used_ids.add(e["id"])
        entries.append(e)
        return e

    # 1. seeds from the spec
    for vkey in ("after", "before"):
        for it in spec["versions"][vkey]["items"]:
            asset = it["asset"]
            kind = asset.get("kind") or asset.get("id") or ""
            if asset.get("source") == "elements":
                t = it["type"].lower()
                slot = "wc" if "wc" in t else "basin" if "basin" in t or "vanity" in t else "shower" if "shower" in t else \
                    "wardrobe" if "wardrobe" in t else "fixed"
                kind = slot
            else:
                slot = SLOT.get(kind, "fixed")
            key = (kind, tuple(it["size_mm"]), asset.get("element") or "", it["type"] if slot in ("fixed", "kitchen_unit", "appliance") else "")
            if key in by_key:
                e = by_key[key]
                if it["id"] not in e["from_spec"]:
                    e["from_spec"].append(it["id"])
                spec_map[vkey][it["id"]] = e["id"]
                continue
            parts = {}
            for p, f in (it.get("materials") or {}).items():
                parts[p] = f if isinstance(f, str) else f
            src = ph(asset["id"]) if asset.get("source") == "polyhaven" else (
                {"source": "elements", "element": asset.get("element"), "note": "drawn on the architect's plans"}
                if asset.get("source") == "elements" else {"source": "parametric", "kind": kind})
            mdl = model_for(asset.get("id")) if asset.get("source") == "polyhaven" else None
            e = {
                "id": "spec-" + slug(f"{it['type']}-{it['size_mm'][0]}"),
                "name": it["type"][:1].upper() + it["type"][1:],
                "slot": slot, "category": it["category"], "shape": SHAPE.get(slot, "box"),
                "styles": SEED_STYLES.get(kind, SEED_STYLES["default"]),
                "style_basis": "the signed-off style board (spec v1)",
                "size_mm": it["size_mm"],
                "mount": MOUNT.get(slot, "surface" if slot in SURFACE else "floor"),
                "parts": parts,
                "part_hex": {p: fin.get(f, None) for p, f in parts.items() if isinstance(f, str)},
                "options": opts_for([p for p in parts if p != "all"]) if slot not in ("kitchen_unit", "kitchen_wall_units", "island", "fixed") else {},
                "source": src, "model": mdl,
                "model_status": "on disk" if mdl else ("free, not downloaded" if asset.get("source") == "polyhaven" else
                                                      "drawn (from the house model)" if asset.get("source") == "elements" else "none"),
                "placeholder": not mdl,
                "from_spec": [it["id"]],
                "signed_off": True,
                "description": it["type"],
                "asset": asset,
            }
            by_key[key] = add(e)
            spec_map[vkey][it["id"]] = e["id"]

    # 2. alternatives (a Poly Haven model the spec already uses in that slot is not listed twice)
    seeded = {(e["slot"], e["source"].get("id")) for e in entries if e["source"].get("source") == "polyhaven"}
    for slot, name, styles, size, aid, parts, desc in ALT:
        if aid and (slot, aid) in seeded:
            continue
        mdl = model_for(aid)
        e = {
            "id": ("ph-" + slug(aid) if aid else "pm-" + slug(name)) + "-" + slot.replace("_", "-"),
            "name": name, "slot": slot, "category": {"plant_floor": "plant", "plant_small": "plant", "pendant": "lighting",
                                                      "ceiling_light": "lighting", "downlights": "lighting", "wall_light": "lighting",
                                                      "floor_lamp": "lighting", "table_lamp": "lighting", "rug": "soft_furnishing",
                                                      "cushion": "soft_furnishing", "throw": "soft_furnishing", "towels": "soft_furnishing",
                                                      "window_dressing": "soft_furnishing", "radiator": "radiator", "towel_rail": "radiator",
                                                      "wc": "sanitary", "basin": "sanitary", "shower": "sanitary", "bath": "sanitary",
                                                      "tv": "appliance", "bookcase": "joinery", "hooks": "fitting",
                                                      "mirror_cabinet": "fitting"}.get(slot, "decor" if slot in (
                                                          "art", "mirror", "vase", "bowl", "books", "candles", "basket", "photo_frame",
                                                          "clock", "kitchen_small") else "furniture"),
            "shape": SHAPE.get(slot, "box"), "styles": styles,
            "style_basis": "Poly Haven name, category and size (preview not checked)" if aid else "studio parametric piece",
            "size_mm": size, "mount": MOUNT.get(slot, "surface" if slot in SURFACE else "floor"),
            "parts": {p: h for p, h in parts.items()}, "part_hex": dict(parts),
            "options": opts_for(list(parts)),
            "source": ph(aid) if aid else {"source": "parametric", "kind": SHAPE.get(slot, "box")},
            "model": mdl,
            "model_status": "on disk" if mdl else ("free, not downloaded" if aid else "none"),
            "placeholder": not mdl,
            "from_spec": [], "signed_off": False, "description": desc,
        }
        if slot == "window_dressing":
            e["fits_window"] = True
        add(e)

    from collections import Counter
    by_style = Counter(s for e in entries for s in e["styles"])
    by_group = Counter(next((g for g, ss in GROUPS if e["slot"] in ss), "Other") for e in entries)
    out = {
        "catalogue": "room planner catalogue", "version": 1, "site": a.site, "spec": spec_name,
        "made": datetime.now(timezone.utc).isoformat(timespec="seconds"), "made_by": "tools/planner/make_catalogue.py",
        "styles": STYLES, "groups": [{"name": g, "slots": s} for g, s in GROUPS], "slot_names": SLOT_NAMES,
        "notes": ["Poly Haven models are CC0. 'free, not downloaded' = a real model exists online; fetch it with "
                  "tools/unreal/fetch_assets.py into assets/library/polyhaven/<id>/ and re-run this script to show it in the planner.",
                  "placeholder = drawn as a proportioned shape; the build makes it parametrically.",
                  "Style tags on Poly Haven entries come from the asset's name, category and size; check the preview."],
        "counts": {"entries": len(entries), "by_style": by_style, "by_group": by_group,
                   "real_models_on_disk": sum(1 for e in entries if e["model"]),
                   "free_models_not_downloaded": sum(1 for e in entries if e["model_status"] == "free, not downloaded"),
                   "placeholders": sum(1 for e in entries if e["placeholder"])},
        "spec_items": spec_map,
        "wall_palettes": {k: [{"name": n, "hex": h} for n, h in v] for k, v in WALL_PALETTES.items()},
        "floors": [{"id": i, "name": n, "styles": s, "hex": h, "pattern": p, "unit_mm": u, "rooms": r} for i, n, s, h, p, u, r in FLOORS],
        "kitchen_fronts": [{"id": i, "name": n, "styles": s, "hex": h, "door": d} for i, n, s, h, d in FRONTS],
        "worktops": [{"id": i, "name": n, "styles": s, "hex": h} for i, n, s, h in TOPS],
        "entries": entries,
    }
    dest = os.path.join(spec_dir, "catalogue_v1.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(json.dumps(out["counts"], indent=1))
    print("->", os.path.relpath(dest, ROOT))


if __name__ == "__main__":
    main()

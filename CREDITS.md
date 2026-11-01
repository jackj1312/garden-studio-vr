# Credits and licensing

This is intended to become a commercial service, so everything here is chosen to be
safe to sell. Check this file before adding any dependency or asset.

## In use

| What | Source | Licence | Commercial use |
|------|--------|---------|----------------|
| three.js r185 | mrdoob/three.js | MIT | Yes, attribution in source only |
| Textures (7 sets) | Poly Haven | CC0 | Yes, no attribution required |
| HDRI skies (5) | Poly Haven | CC0 | Yes, no attribution required |
| Typefaces | System stack | n/a | Yes |

Poly Haven assets are CC0, which is a genuine public-domain dedication rather than a
"free for personal use" licence. Nothing here needs crediting, and this file exists as a
record rather than an obligation.

House build textures (tools/house/make_textures.py): concrete_pavement, gravel_floor and brown_mud_leaves_01 (Poly Haven, CC0, already in master/polyhaven/tex), used for concrete, hardcore and soil; every other construction material is generated procedurally, and the brick, paving, lawn and gravel come from the client's own photographs. Look renders light with kloofendal_48d_partly_cloudy_puresky (Poly Haven, CC0).

House build textures, round 6 (1 Nov 2026): scanned CC0 PBR from ambientCG (CC0 1.0, commercial use, no attribution
required), 1K-JPG sets kept in master/ambientcg/<id>/ and recoloured / laid at true scale by tools/house/make_textures.py:

| Used for | ambientCG set | Source |
|---|---|---|
| dense concrete block faces (laid as 440x215 blocks), concrete trench fill, slab, padstones, screed | Concrete047A | https://ambientcg.com/view?id=Concrete047A |
| (downloaded, not used: streaky formwork look) | Concrete030 | https://ambientcg.com/view?id=Concrete030 |
| hardcore | Ground111 | https://ambientcg.com/view?id=Ground111 |
| C24 timber, existing timber, battens, temporary timber (grain along the member, grade stamp added) | Wood058 | https://ambientcg.com/view?id=Wood058 |
| chipboard / OSB deck | Chipboard005 | https://ambientcg.com/view?id=Chipboard005 |
| red-oxide primed steel, Acrow props (recoloured) | PaintedMetal004 | https://ambientcg.com/view?id=PaintedMetal004 |
| galvanised lintels, straps, hangers, scaffold tube (zinc spangle added) | Metal038 | https://ambientcg.com/view?id=Metal038 |
| plasterboard and skim (relief flattened) | Plaster001 | https://ambientcg.com/view?id=Plaster001 |
| DPM / DPC | Plastic012A | https://ambientcg.com/view?id=Plastic012A |
| tarpaulins | Plastic015A | https://ambientcg.com/view?id=Plastic015A |
| (downloaded, not used) | PaintedMetal013 | https://ambientcg.com/view?id=PaintedMetal013 |

The existing house keeps the client's own surfaces (brick from Jack's photographed unit sheets, the soldier course from his
close-up, roof tiles at the colour sampled from his photos, anthracite frames as surveyed).

Texture sets: exterior_wall_cladding_03, wood_floor_deck, brushed_concrete, grass_ground,
red_brick, square_brick_paving, weathered_plank_siding.
Skies: kloofendal_misty_morning_puresky (morning), kloofendal_43d_clear_puresky (midday), qwantani_sunset_puresky (golden hour), evening_road_01_puresky (dusk), dikhololo_night (night). Each is served as a 2k EXR for light and a 4k tone-mapped JPEG for the eye.

## Cleared for later use

| What | Licence | Note |
|------|---------|------|
| Meta Immersive Web SDK | MIT | WebXR locomotion, interactions, spatial UI |
| Pascal Editor | MIT | Architectural authoring, drivable over MCP |
| IfcOpenShell / Bonsai | LGPL | Fine as an authoring tool; do not link into shipped code |

## Ruled out

**xeokit-sdk — AGPL-3.0.** Capable BIM viewer, but AGPL reaches through a network service:
offering a hosted viewer built on it would oblige you to publish your own source. Not
compatible with selling this.

**"Royalty-free" music libraries.** Many licences cover your own projects but exclude work
delivered to a client, which is exactly what this would be. Any music must be CC0, or
carry a licence that explicitly permits client deliverables, and the licence gets filed here.

## Client data

Scans, addresses, drawings and anything identifying a client's property must never go into
a public repository. This repo is public because it holds the engine and a placeholder
garden. Per-client sites belong in private repos or private hosting, with only the shared
engine in the open.

## Master model

`master/studio.blend` is the source of truth for the studio. `assets/models/studio.glb`
is exported from it: geometry only, with the bevel and array modifiers applied and UVs
unwrapped. glTF cannot carry Blender's procedural materials, so the master supplies the
shapes and `src/studio.js` supplies the surfaces. The UV set is already in place for the
lightmap bake, which will arrive as a texture on these same meshes.

## Scanned vegetation (Poly Haven, CC0)
island_tree_01, island_tree_02 (Rob Tuytel, Rico Cilliers), shrub_01–04, fern_02,
grass_medium_01, grass_medium_02, periwinkle_plant, celandine_01, moss_01. Photogrammetry
models, CC0, no attribution required; credited here anyway. Sources are refetched with
`tools/fetch-polyhaven.py` and are not committed; the Quest/desktop GLBs under
assets/models/veg are derived from them. Nothing CC-BY appears in any render.

## Unreal rebuild of the front garden (1 Nov 2026) — free scanned assets, all CC0
Fetched by tools/unreal/fetch_assets.py into the studio asset library (~/Desktop/garden-scans/asset-library, outside the
repo, reused for every client; its LIBRARY.md lists each file's URL). CC0 1.0 = public domain, safe for paid client work, no
attribution required. No paid assets, no Fab/Epic login used.

| Used for | Asset | Source | Licence |
|---|---|---|---|
| House brick (tinted to Jack's brick close-up) | brick_4 | https://polyhaven.com/a/brick_4 | CC0 |
| Roof plain tiles, ridge | roof_tiles | https://polyhaven.com/a/roof_tiles | CC0 |
| Block-paved path, step, neighbour's drive | short_bricks_floor | https://polyhaven.com/a/short_bricks_floor | CC0 |
| Pea-shingle drive (with displacement) | dry_river_pebbles | https://polyhaven.com/a/dry_river_pebbles | CC0 |
| Lawn base, neighbour turf | leafy_grass | https://polyhaven.com/a/leafy_grass | CC0 |
| Bed soil | brown_mud_leaves_01 | https://polyhaven.com/a/brown_mud_leaves_01 | CC0 |
| Edging setts | granular_concrete | https://polyhaven.com/a/granular_concrete | CC0 |
| Kerb, concrete, stone bench | concrete_pavement | https://polyhaven.com/a/concrete_pavement | CC0 |
| Road, pavement, shed felt | asphalt_02 | https://polyhaven.com/a/asphalt_02 | CC0 |
| Pergola and bench pine | coated_pine_02 | https://polyhaven.com/a/coated_pine_02 | CC0 |
| Slatted fence | raw_plank_wall | https://polyhaven.com/a/raw_plank_wall | CC0 |
| Shed cladding | weathered_brown_planks | https://polyhaven.com/a/weathered_brown_planks | CC0 |
| Bench cushions | waffle_pique_cotton | https://polyhaven.com/a/waffle_pique_cotton | CC0 |
| Apple tree bark, branches, leaves (our measured tree shape) | island_tree_02 | https://polyhaven.com/a/island_tree_02 | CC0 |
| Box balls, hedge leaf balls | celandine_01 | https://polyhaven.com/a/celandine_01 | CC0 |
| Stipa (ornamental grass) | grass_medium_01 | https://polyhaven.com/a/grass_medium_01 | CC0 |
| Salvia and lavender stand-ins | periwinkle_plant | https://polyhaven.com/a/periwinkle_plant | CC0 |
| Background trees over the road | island_tree_01 | https://polyhaven.com/a/island_tree_01 | CC0 |
| Fallback sky | kloofendal_43d_clear_puresky | https://polyhaven.com/a/kloofendal_43d_clear_puresky | CC0 |
Grass blades on the lawn are generated geometry (tools/unreal/export_ue.py), coloured from Jack's lawn photo.

## Room planner (planner.html, 1 Nov 2026) — catalogue references, nothing downloaded
The planner draws every piece as a proportioned shape in its colours; it ships no third-party models or textures. Its catalogue
(`assets/sites/house/spec/catalogue_v1.json`, made by `tools/planner/make_catalogue.py`) names 112 Poly Haven models (CC0 1.0) as
free alternatives, with their real dimensions read from api.polyhaven.com on 1 Nov 2026; each entry links its page
(https://polyhaven.com/a/<id>). None is downloaded yet; if fetched later into `assets/library/polyhaven/<id>/` the catalogue marks
them "on disk" (the planner itself stays with simple shapes, by Jack's choice). Library code: three.js r185 (MIT) from jsDelivr, loaded only when the 3D preview is switched on.


## First build to spec_v1 (1 Nov 2026): Poly Haven models and texture sets (all CC0, commercial and web use, no attribution required)
Fetched by tools/house/fetch_spec_assets.py into master/polyhaven/ (models) and master/polyhaven/tex/ (textures); finishes recoloured to the spec's colours by tools/house/make_spec_textures.py. floor_tiles_06 and laminate_floor_02 (the spec's fallbacks) were downloaded to check them and are not used.

| asset | kind | source | licence | format |
|---|---|---|---|---|
| WoodenTable_02 | model | https://polyhaven.com/a/WoodenTable_02 | CC0 | gltf |
| bar_chair_round_01 | model | https://polyhaven.com/a/bar_chair_round_01 | CC0 | gltf |
| book_encyclopedia_set_01 | model | https://polyhaven.com/a/book_encyclopedia_set_01 | CC0 | gltf |
| brass_candleholders | model | https://polyhaven.com/a/brass_candleholders | CC0 | gltf |
| caban | texture | https://polyhaven.com/a/caban | CC0 | 1k jpg |
| ceramic_vase_01 | model | https://polyhaven.com/a/ceramic_vase_01 | CC0 | gltf |
| ceramic_vase_02 | model | https://polyhaven.com/a/ceramic_vase_02 | CC0 | gltf |
| ceramic_vase_03 | model | https://polyhaven.com/a/ceramic_vase_03 | CC0 | gltf |
| ceramic_vase_04 | model | https://polyhaven.com/a/ceramic_vase_04 | CC0 | gltf |
| curly_teddy_natural | texture | https://polyhaven.com/a/curly_teddy_natural | CC0 | 1k jpg |
| decorative_book_set_01 | model | https://polyhaven.com/a/decorative_book_set_01 | CC0 | blend |
| desk_lamp_arm_01 | model | https://polyhaven.com/a/desk_lamp_arm_01 | CC0 | gltf |
| dining_chair_02 | model | https://polyhaven.com/a/dining_chair_02 | CC0 | gltf |
| grey_cartago_02 | texture | https://polyhaven.com/a/grey_cartago_02 | CC0 | 1k jpg |
| hanging_picture_frame_02 | model | https://polyhaven.com/a/hanging_picture_frame_02 | CC0 | gltf |
| hanging_picture_frame_03 | model | https://polyhaven.com/a/hanging_picture_frame_03 | CC0 | gltf |
| hessian_380 | texture | https://polyhaven.com/a/hessian_380 | CC0 | 1k jpg |
| jug_01 | model | https://polyhaven.com/a/jug_01 | CC0 | gltf |
| knitted_fleece | texture | https://polyhaven.com/a/knitted_fleece | CC0 | 1k jpg |
| long_white_tiles | texture | https://polyhaven.com/a/long_white_tiles | CC0 | 1k jpg |
| marble_01 | texture | https://polyhaven.com/a/marble_01 | CC0 | 1k jpg |
| modern_ceiling_lamp_01 | model | https://polyhaven.com/a/modern_ceiling_lamp_01 | CC0 | gltf |
| modern_coffee_table_01 | model | https://polyhaven.com/a/modern_coffee_table_01 | CC0 | gltf |
| oak_veneer_01 | texture | https://polyhaven.com/a/oak_veneer_01 | CC0 | 1k jpg |
| oak_veneer_02 | texture | https://polyhaven.com/a/oak_veneer_02 | CC0 | 1k jpg |
| plank_flooring_02 | texture | https://polyhaven.com/a/plank_flooring_02 | CC0 | 1k jpg |
| planter_pot_clay | model | https://polyhaven.com/a/planter_pot_clay | CC0 | gltf |
| potted_plant_01 | model | https://polyhaven.com/a/potted_plant_01 | CC0 | gltf |
| potted_plant_02 | model | https://polyhaven.com/a/potted_plant_02 | CC0 | gltf |
| potted_plant_04 | model | https://polyhaven.com/a/potted_plant_04 | CC0 | gltf |
| rough_linen | texture | https://polyhaven.com/a/rough_linen | CC0 | 1k jpg |
| round_wooden_table_02 | model | https://polyhaven.com/a/round_wooden_table_02 | CC0 | gltf |
| side_table_01 | model | https://polyhaven.com/a/side_table_01 | CC0 | gltf |
| slate_floor | texture | https://polyhaven.com/a/slate_floor | CC0 | 1k jpg |
| standing_picture_frame_01 | model | https://polyhaven.com/a/standing_picture_frame_01 | CC0 | gltf |
| steel_frame_shelves_01 | model | https://polyhaven.com/a/steel_frame_shelves_01 | CC0 | gltf |
| tatami_mat | texture | https://polyhaven.com/a/tatami_mat | CC0 | 1k jpg |
| waffle_pique_cotton | texture | https://polyhaven.com/a/waffle_pique_cotton | CC0 | 1k jpg |
| white_plaster_02 | texture | https://polyhaven.com/a/white_plaster_02 | CC0 | 1k jpg |
| wicker_basket_02 | model | https://polyhaven.com/a/wicker_basket_02 | CC0 | gltf |
| wooden_bowl_01 | model | https://polyhaven.com/a/wooden_bowl_01 | CC0 | gltf |
| wooden_bowl_02 | model | https://polyhaven.com/a/wooden_bowl_02 | CC0 | gltf |
| wooden_candlestick | model | https://polyhaven.com/a/wooden_candlestick | CC0 | gltf |

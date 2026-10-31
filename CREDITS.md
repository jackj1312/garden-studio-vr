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

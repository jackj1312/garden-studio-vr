# Shared tools, MCPs and skills

These are available resources in the benchmark, not things Jack must explain again or compulsory methods. Choose alternatives when better; no MCP, application or existing implementation is mandatory. `tool-manifest.json` inventories the copied common baseline, with source path and hash. It includes source code, not previous house outputs. Scripts may depend on installed Python/Node/Blender libraries and need an isolated site's config; this is a toolbox, not a prebuilt finished house. Adapt integration to the independently measured site.

| Capability | Existing tool family / method to reuse | Preflight |
|---|---|---|
| House/browser/VR | `src/house`, `src/marks.js`, `src/notes.js`, shared UI/scene modules, viewer pages and vendor three.js | New site route, walk test, room portals, controllers, no default house-wip data leakage. |
| Furniture/finish/planner | `src/furnish`, `src/planner`, `src/studio-layout-service.js`, `tools/layout_store.py`, `tools/planner`, HTTPS server | Build own room/wall/host metadata; shared saved layout and advisory checks. |
| Garden | `src/garden`, terrain, geometry/drawing/history/wrist/plan, device/render controls | Source-specific frontage and studio overlay modules are excluded; reconstruct them from originals/owner base if needed. Adapt imports rather than loading old measurements. |
| Kit | `tools/library/kit` generator, dimensions, materials, catalogue, eligible models/maps/thumbs/records | Licences and hash availability; these generic items are common inputs, not old house placements. |
| Reconstruction | `tools/house`, `tools/plan`, `tools/blender`, `tools/photogrammetry`, `tools/phototex` | Run against own data only. Old hard-coded stations, sample files and regression expectations are not architectural authority. |
| Review/packaging | `tools/review`, export/compression/texture repair, local capture and preview tools | Adapt measured assertions to own source spec; inspect served GLBs as well as source. Never open historical evidence linked in tests. |
| Unreal/cloud | `tools/unreal`, `tools/cloud`, native Python/Sequencer/MRQ, import/material/foliage tools | Verify installed engine/permissions. Existing saved Unreal scenes/caches/output volumes are sealed prior results. No spend under old authorisation. |
| Blender MCP | `skills/blender-mcp-workflow/SKILL.md` | Discover tools, read current scene/file safely; existing localhost protocol if supported; preserve unsaved work. MCP not exposed in this packaging session, so availability is UNVERIFIED, not missing by assumption. CLI/Python fallback is allowed and reported. |
| Images/video | Image generation tool/skill, original-render staging, ffmpeg, camera rehearsal, native Eevee/Unreal | Original-image rule and approval gates; Higgsfield MCP/subscription not verified and not purchased. |
| UI/PDF/research | Browser/computer use, PDF inspection/rendering, public authoritative web/map sources | Use available connector first; no logins/permissions invented, no private uploads or screenshots passed to third parties without authority. |

Only applicable project skills are carried. Their current original locations are recorded; snapshot instructions are in `skills/`. Some supporting scripts may need the installed skill package. Do not browse other clients' samples or prior benchmark results linked by a skill. The clean benchmark boundary takes priority over those links. Follow user approvals and current tool documentation, never guessed MCP schemas.

At each run discover the actual available integrations by name/description; record available / configured-but-unverified / unavailable, version, safe smoke test, fallback and remaining dependency. A saved inventory is not proof of a live connection. Do not copy MCP config values, tokens, cookies, keys or provider secrets into this pack. No installation, subscription or cloud session is started just to populate an inventory.

The retained generic source also includes builder/architect/inspector roles, construction sequence, slice/x-ray, measurement/heights, structural edit operations, change requests/inspections, rule hooks, capture/splat utilities, environment ambience/wind and VR presence. Read R33–R36 so these older capabilities are not lost behind the newer editors.

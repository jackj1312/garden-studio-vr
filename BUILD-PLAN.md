# Garden studio in VR — build plan

A walkable 3D recreation of the property, in which Lauren's tattoo studio builds itself
through six stages, viewed in a Meta Quest 3 at real scale.

Decided 30 Oct 2026. Stylised real, roughly to scale, pre-set variants, no in-headset editing.

## The approach

Nothing in the final scene is photogrammetry. The camera scan exists only as a tracing
reference — it tells us where every wall, fence, tree and door actually is, so the
recreation is measured rather than guessed. The scene itself is clean, named geometry,
which is what makes stages, variants and animation possible at all.

Everything is built at true metric scale. That is not cosmetic: at real scale the Quest's
own floor tracking means walking two steps in the room walks two steps in the garden, and
that 1:1 correspondence is what makes it feel like being there.

## Visual style — "stylised real"

- Real materials and real proportions. Brick reads as brick, cedar as cedar.
- Simplified detail. No individual leaves, no mortar courses, no door furniture.
- Lighting baked into the textures where possible, one real-time sun for shadows.
- Trees and planting as low-poly massing with a good silhouette, not scanned foliage.
- The test: recognisable as *this* garden from the doorway, without pretending to be a photo.

## The six stages

| # | Stage | What appears |
|---|-------|--------------|
| 1 | As it is today | The garden as scanned. Nothing proposed. |
| 2 | Cleared | Hedge, slabs and anything in the footprint removed. Bare ground. |
| 3 | Base | Groundworks, slab or pile foundation, service trench to the house. |
| 4 | Frame | Timber frame, joists, roof structure. Open and skeletal. |
| 5 | Clad and roofed | Cladding, roof covering, windows, door. Weathertight. |
| 6 | Finished | Interior fit-out, deck and path, planting, lighting, furniture. |

Stage 1 is the control. Every other stage is a diff against it, so "what does this cost me
in garden" is always answerable by scrubbing back.

## Scene structure

Naming is load-bearing — the viewer drives the scene entirely by object names, so the
model and the app stay decoupled and either can be rebuilt without the other.

```
EXISTING/            always present unless a stage removes it
  ground, boundary_fence, boundary_wall, house_exterior,
  hedge, patio_slabs, shed, tree_01..n, path
HOUSE_INTERIOR/      only the rooms a structural change opens up
STAGE_02_CLEARED/ ... STAGE_06_FINISHED/
REMOVED_AT_STAGE_02/ objects that disappear, parented for one-line hiding
VARIANT_A/, VARIANT_B/   alternative studio positions and finishes
```

Rules: no object in two stage groups; anything that moves between stages is one object with
keyframes, not two copies; every stage group is self-contained so hiding it is always safe.

## What gets modelled

In this order, because each one unblocks a milestone.

1. **Ground plane and levels** — the single most important piece. Gets the slopes right.
2. **Boundaries** — fences, walls, gates. Defines the envelope the studio has to live in.
3. **House exterior** — full, all elevations.
4. **Garden features** — patio, path, shed, trees, planting beds.
5. **The studio, six times** — one model, six states.
6. **Affected interior rooms** — only where a structural change opens one up.
7. **Variants** — alternative studio positions, orientations and finishes.

## Capture shoot

Looser than a splat capture, because we only need geometry and positions.

- Overcast, still day. Manual exposure locked, f/8, low ISO, JPEG.
- A walk-around of the whole property at chest height, plus a second pass angled down.
- Every boundary corner, every door and window, from two directions.
- Tape-measure checks written down: house frontage, garden length and width, door height,
  fence height, distance from house to rear boundary. Six numbers is enough to lock scale.
- Offload immediately. The MacBook Air has ~23 GB free.

Processing: Luma AI's free tier, or a rented GPU hour if it disappoints. The output is a
reference mesh, not a deliverable, so "good enough to trace" is the bar.

## The viewer

three.js with WebXR, hosted as a URL. Opens in the Quest 3 browser, works on a laptop for
anyone you show it to, nothing to install.

**Movement** — the part that decides whether it feels real:

- Floor-level reference space, so eye height comes from the headset and 1:1 walking works.
- Thumbstick for distance, capped at walking pace (~1.4 m/s), head-relative direction.
- Snap turn by default, smooth turn as an option.
- A soft vignette during stick movement. Costs nothing, removes most of the nausea.
- Collision against walls and the studio shell, so you can't walk through the building.
- No flying, no scaling, no teleport arcs. You are a person in a garden.

**Stage controls** — all three, since they stack:

- A scrubber on a wrist panel, draggable with the other controller.
- Six snapshot buttons for jumping straight to a stage.
- A play button that runs the whole build as an animation, roughly 30 seconds.

Transitions animate rather than cut: walls rise, roof lands, planting scales in. That's
what makes it read as "building itself".

**Variant switch** — a separate control, independent of the stage, so any variant can be
seen at any stage.

## Performance budget (Quest 3, 90 Hz)

- 150–250k triangles for the whole scene.
- Under ~60 draw calls. Merge by material, atlas the textures.
- Baked lighting, one real-time directional light, shadows on the studio only.
- KTX2 compressed textures, meshopt-compressed GLB. Target under 15 MB total.
- Instance the repeats: fence panels, slabs, joists, planting.

## Milestones

**M1 — viewer skeleton.** Grey boxes for the garden, locomotion, scrubber, six empty stages,
running on the Quest. Proves the hard part and needs no scan or modelling.
**M2 — capture.** Shoot, process, import the reference, lock the scale.
**M3 — existing scene.** Ground, boundaries, house exterior, garden features.
**M4 — the studio.** Six stages, animated transitions.
**M5 — structural changes.** Affected rooms, variants.
**M6 — polish.** Materials, baked lighting, compression, a shareable link.

M1 first is deliberate: if the movement doesn't feel right in the headset, that's worth
knowing before a week of modelling, and the fix is in the app rather than the geometry.


## Three dials, not one

The scene is controlled by three independent axes. Any combination is valid, which is what
makes it worth walking rather than looking at.

| Dial | Values | What it answers |
|------|--------|-----------------|
| Stage | 1-6, scrubbable | How built is it? |
| Placement | Corner, along fence | Where does it sit? |
| Setting | Time of day x occasion | What is it like to be there? |

**Setting** was added 30 Oct 2026. It splits in two:

- *Time of day* — discrete baked presets (morning, midday, golden hour, dusk, night) that
  cross-fade. Baked rather than a continuous sun, because lightmaps are what buy the
  fidelity at 90 Hz and a moving sun throws them away. Dusk and night switch the practical
  lights on: studio interior, porch, festoon, path markers.
- *Occasion* — a props and lighting layer: everyday, barbecue, evening party, quiet winter
  evening. Each is a named collection that drops in furniture, people, and accent lights.

An empty model shows a building. A lit garden with a table laid and people in it shows what
the building is for, which is the thing that actually persuades a planner, a builder, or
anyone else being asked to imagine it.

Occasion layers are stage-6 only by default. Time of day applies at every stage, and the
cinematic uses it as a shot device.

## Cinematic mode

One button, two behaviours, because they have to be different:

- **Flat screens** — a real filmic flyby, around 60 seconds, choreographed so camera moves
  and build stages land together. Dolly, crane, rack focus, the lot.
- **In VR** — a guided tour. The viewer stays planted, the build animates in front of them,
  and the scene cuts to the next vantage point. Cuts are comfortable; glides cause sickness.
  The choreography lives in the build, not in the camera.

A properly rendered film (ray tracing, depth of field, motion blur) is a separate deliverable
out of Blender once the model is worth filming.

## Quality tiers are the price points

Decided 30 Oct 2026. The basic version is not a stepping stone to be thrown away — it is
the entry product. So quality is a switch in one codebase, never a second codebase.

`?q=basic` · `?q=standard` (default) · `?q=premium`

| | Basic | Standard | Premium |
|---|---|---|---|
| Shadow map | 1024 | 2048 | 4096 |
| Grass instances | 2,500 | 14,000 | 30,000 |
| Anisotropy | 4 | 8 | 16 |
| Bloom | no | yes | yes |
| Ambient occlusion | no | no | yes |
| Pixel ratio cap | 1.25 | 1.75 | 1.25 |

Measured on the M1 Air at 2048 x 1536: standard holds 60 fps. Screen-space ambient
occlusion costs about three quarters of the frame rate on integrated graphics, which is
why it sits in premium alone and why premium drops its pixel ratio to pay for it. It is
also temporary — baked lighting does the same job better and costs nothing at runtime, so
when the bake lands, AO comes out and premium spends that budget on something else.

A VR profile is applied over whichever tier is active: 1024 shadows, no post-processing,
a third of the grass. Holding 90 Hz in the headset outranks every tier, because dropped
frames make people ill and nobody buys a walkthrough that made them ill.

## Selling this

Decided 30 Oct 2026: this becomes a service sold to other people, which changes three
things about how it gets built.

- **Licence discipline.** Every dependency and asset is checked before use and recorded in
  `CREDITS.md`. Everything currently in the project is MIT or CC0. AGPL libraries are out.
- **One engine, many sites.** `src/config.js` holds everything site-specific, and nothing
  else does. A new client is a new config plus their own assets, not a fork.
- **Client data stays private.** Scans, addresses and drawings never enter a public repo.
  The engine is public; each client's site is not.

## Open items

- The architectural drawing of the property, when it turns up — upgrades everything.
- Moasure for real measurements, if this becomes a repeatable service.
- A call to the council's duty planner. A tattoo studio in a garden is a change-of-use
  question as much as an outbuilding question, and it's cheaper to ask before designing.
- Optional later: a splat of the existing garden as an "as it really looks" overlay on
  stage 1 only, where the performance cost is affordable.

# Judge: homeowner, round 6 — 23 Battle Road (1 Nov 2026)

Matched views (Eevee, camera solved from refs.json, as_built_now stage 1, as-built layer on): `renders/house-build/judge-r6/`
sheets `matched_sheet_A.jpg`, `matched_sheet_B.jpg`, `sheet_<photo>.jpg` (photo left, model right). Photos: 20260719_102925,
walk_0011/0019/0027/0035/0041, 20260506_190234, 20260425_183009. Street hedge checked against walk_0001/0133/0143/0153/0157/0175.
Not run: the approved scheme's stage 15 (no matched render; judged from look6 renders only). Viewer feel is from stills, not a headset.

## Verdict: 5/10 for "I'd show this to my family as our house"
The geometry is genuinely right: path, lawn, drive edge, apple tree, chimney, hips, window positions all land on the photos.
The surfaces are not: the roof, gravel, paving and brick are the wrong colour and the hedge at the road is wrong. A family would say
"that's the shape of our house, painted by someone who has not seen it."

## Findings, most severe first

1. **Roof tile colour (all views, worst in 20260719_102925, walk_0011, 20260506_190234). CONFIRMED.** Real: dark chocolate/red-brown
   plain tiles, strong course lines, mossy ridges. Model: pale salmon-beige, soft, plastic. Largest surface; it alone makes the house
   look like someone else's. The porch pent roof (190234, 183009) has the same fault: real is dark purple-brown. Fix: re-sample the
   tile from walk_0011/0019 in sun, darken ~35 %, add per-tile value variation and a darker course shadow line.
2. **Continuous 1.8 m street hedge. CONFIRMED wrong.** Photos walk_0001, 0133, 0143, 0153 show only separate clipped hedge masses at
   the pavement: one each side of the path gap and one at the drive's edge. Between and beyond them the frontage is open (walk_0157,
   0175, 20260719_102925: no hedge anywhere between camera and house). The model's wall across the whole plot (persp_road_s15,
   persp_pavement) hides the lower house; from the pavement the real house is fully visible. Fix: three hedge blocks, ~2 m long,
   irregular tops, with the path gap and drive opening left open. Also the road-view renders in look6 root (persp_road_s15,
   persp_street_asbuilt) still show horizontal strips through the hedge and lawn: the ground-fix is only in after_ground_fix/.
3. **Gravel drive (20260719_102925, walk_0011). CONFIRMED.** Real: warm gold/cream rounded flint chips, high contrast, shadow-flecked.
   Model: flat grey-pink noise, no gold. Fix: sample the gravel from walk_0157; warm it, add larger pebble normal and value variation.
4. **Block paving, front court and path (walk_0027/0035/0041, 190234). CONFIRMED.** Real: deep red/brown/charcoal mix, dark joints,
   grey edging. Model: pale peach, low contrast, uniform; big translucent shadow bands across the court look like light leaks.
   Fix: darker, more saturated blends; check the shadow bands (probably a sun shadow-map artefact).
5. **Brick (all close views). CONFIRMED in Eevee; the viewer screenshot (r6_scale_figure_front) is much closer.** Real: orange-red with
   blue-black headers and light mortar; model in Eevee: pink-salmon, flat. Soldier course over the lower window is correct.
   Fix: make the viewer's brick the reference and match the Eevee/sheet export to it.
6. **Cartoon props. CONFIRMED.** Tall hedge beside the door (walk_0035/0041/190234): a perfectly square, uniformly hairy green box
   with a spike; real is an irregular clipped hedge with leaf detail. Satellite dish: flat white ellipse (real: dark mesh dish with
   arm). Meter box: grey two-block stack (real: small white box). Bench: dark slab (real: stone bench, curved top). Fix: break the
   hedge silhouette, rebuild dish, box and bench.
7. **Porch mirror. CONFIRMED.** 183009, 190234: real is arch-topped with a thin black frame and glazing bars; the model's is a plain
   rectangle with grid (r6_scale_figure_front, sheet B). Fix: arched top.
8. **No.21's porch (left of house) in walk_0011, 20260719_102925. CONFIRMED.** Real: gabled dark hood, white door with side lights.
   Model: lean-to over a plain pale-blue panel, no door. It is the first thing you see on the left from the drive. Fix: model the
   white door, side lights and gable hood (neighbour, lower precision is fine).
9. **Chimney. CONFIRMED.** Real has pots and a TV aerial (walk_0011, 0019, 20260719). Model is a plain brick box. Position is right.
10. **Dark slab on the brick beside the porch (r6_scale_figure_front, 183009 sheet). PLAUSIBLE.** A black upright panel ~0.4 x 1.2 m
    floats between the white porch strip and the window; the photos show plain brick there and a small wall light. Identify the
    element (door leaf seen edge-on? letterbox?) and remove or fix it.
11. **Glazing bars (walk_0035/0041). PLAUSIBLE.** Model windows read as a heavy 3x2 grid; real anthracite windows are thinner with
    top-hung lights and two large lower panes in places. Sizes, positions, stone cills/surrounds match. Anthracite on the five
    replaced windows and white elsewhere agrees with the photos (the owner's "anthracite today" is only true of those five).
12. **Planting in as_built_now (183009 sheet B). PLAUSIBLE.** Model has a deep lavender bed with black balls, curved edging and a teal
    double bench in front of the pergola; the April photo shows a shallow border, straight paving edge, bare lawn patch, and an
    olive slatted bench. If that is the designed scheme, keep it out of "today". Real pergola timber is greener than the cream model.
13. **Front door. PLAUSIBLE.** Photo shows grey composite door with a narrow glazed light; model is a plain dark leaf. Threshold
    is modelled flush (sill 0.000 above FFL; CORRECTIONS row 44 was "no step"): confirm there is one visible step from the court.
14. **Sky and light: dull grey haze in every render, versus hard blue-sky sun in the photos. CONFIRMED** (reads as overcast).
15. **Apple tree: bare, sparse branches in 20260719 / walk_0011 match view; real is a full-leaf dome. CONFIRMED.** No car, no neighbouring
    fence in the model (real timber horizontal-slat fence right of the drive).

## In VR at true scale
- Interior doors 1.95-2.01 m high, 0.80-0.90 m wide: correct. Front door 2.03 m. Under-stair cupboard 1.25 m: plausible.
- Spawn on the path at standing height is fine, but the hedge wall means the first look at the house from the road is blocked.
- Pergola posts and the figure in r6_scale_figure_front look right against the 1.8 m marker.
- Loft: only the front rooflight exists; back ones are missing (known).

## What is genuinely good
Camera-registered match of path, lawn island, drive curve and tree position; hip and eaves lines; chimney position; window
positions and stone surrounds; downpipe and cable runs; the porch's massing, rooflight and black fascia; correct door/storey heights.

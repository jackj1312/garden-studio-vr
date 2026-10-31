# Survey method — a true-scale plan for every property

The plan is the set of facts everything is built from. Nothing gets modelled until the
plan is measured and signed off. (Jack's own garden, 31 Oct 2026: the house front was
measured from a scan and came out right; everything I estimated from photos came out
wrong. The same will happen at every customer's house unless the plan is measured.)

## Target
- Positions within about 2–3 cm over a typical front or back garden (up to ~20 m).
- Levels (slopes, steps) to the nearest couple of cm.
- Every line on the plan says where it came from: a measuring device, tape, or scan.

## Before the visit (desk, 15 min)
- **Land Registry title plan** (a few pounds): legal boundary shape, roughly. Good for the
  quote. It isn't accurate enough to build from.
- **Aerial view** for orientation and the overall shape only. Google's terms restrict
  commercial reuse, so keep it internal and out of anything the customer receives.
- **Compass bearing** of the house front: this sets where the sun really is.

## On site (45–60 min)
1. **Measure the plan: a Moasure 2 / 2 PRO.** This is the measuring device UK landscapers use.
   Walk it along each line: house face, boundaries, path edges, lawn and bed edges, kerbs,
   trees (trunk centre and spread), posts, bins, gates, manholes. It draws the plan and the
   levels as you go and exports **DXF/DWG**, which I read straight in. Moasure quotes about
   ±0.3% on distances (≈3 cm over 10 m) and depends on technique. Alternative: a laser
   measure and tape triangulation (slower, same result if careful).
2. **Lay 4–6 printed targets** (A4 checkerboards) around the garden and record them in the
   same survey. They lock the photo scan to the measured plan to the centimetre. Research
   on photo surveys finds a model with no control points can be out by metres, and one
   with four or five control points by millimetres.
3. **Photo capture**: a slow loop of the whole site (stills or 4K video, overcast if
   possible, your own shadow out of shot) and straight-on close-ups of each material
   (brick, paving, gravel, roof, fence, lawn). This gives the heights, the house front
   detail and the true textures. CAPTURE.md has the walking method.
4. **Optional drone** (under 250 g, e.g. DJI Mini): a true top-down photo, which is the best
   customer-facing plan and gives the film's aerial shots. UK, from Jan 2026: Flyer ID and
   Operator ID for camera drones from 100 g; commercial work needs insurance and may need
   an A2 CofC; neighbours' privacy applies. Check the CAA before the first paid job.

## Measuring from photos and a walk video (no device) — proven on Jack's garden, 31 Oct
1. A slow walk-round video (2 min, 4K, normal lens, house → street → round every edge → back)
   plus any stills. Frames at 1 per ~1 m of walking.
2. `tools/photogrammetry/sfm_walk.py` solves where every frame and photo was taken.
3. Lock it to real size through **known points** seen in two photos: window corners, a door,
   the arch, a measured path (`tools/photogrammetry/measure.py` + the anchor step). Never by
   shape-fitting alone: on this site that drifted by 40% while looking plausible.
4. Checks before trusting it: camera heights ≈ 1.4–1.7 m; a known width (the 900 mm path)
   measures right; posts or furniture land on the scan; two separate solves agree.
5. `tools/photogrammetry/ortho.py` builds a true-scale **top-down photo** of the ground from every
   solved frame (2 cm per pixel). Lawn edges are traced from it by colour
   (`trace_lawn.py`); kerbs are read off 1 cm enlargements; `tools/plan/smooth.py` turns them
   into smooth curves (a point every 8 cm), so curves are drawn and modelled as curves.
   Fences and walls come from the triangulated 3D points on their faces, never from the
   top-down photo (anything tall smears outward in it). Never measure ground points from a
   single far photo: at 8 m, a 1 degree tilt error moves a point by about 0.7 m.
   Photos give point features (tree trunks, posts) by sight-lines from 2+ views.
6. `tools/plan/draw_plan.py` draws the plan, every line marked by how it was measured.
Result on Jack's garden: path 0.87 m against a 0.90 m tape; posts within 5–12 cm of the scan;
two independent solves within 10 cm.

## Back at the desk
1. DXF + scan + targets → **plan drawing** (as plan v0, but every line measured).
2. You (and later the customer) sign it off. Corrections go on the plan, not the model.
3. Only then: the model (Blender), then the walkthrough, film and headset versions.

## Why not just photos or a scan
- Photos alone: sizes have to be guessed, and they were wrong.
- A phone scan alone: good where the photos overlapped (the house front), missing or
  warped elsewhere, and its scale is only as good as the reference in it.
- A measured plan plus a scan locked to it gives right sizes and real textures. That is
  what the Airbnb benchmark started from: the builder's dimensioned floor plan.

Sources: [Moasure accuracy](https://moasure.com/pages/accuracy),
[Moasure 2 PRO](https://moasure.com/products/moasure-2-pro),
[CAA: drone rules](https://caa.co.uk/drones/rules-and-categories-of-drone-flying/introduction-to-drone-flying-and-the-uk-rules),
[Heliguy: sub-250 g drones, 2026](https://www.heliguy.com/blogs/posts/sub-250g-drones-uk-drone-laws/).

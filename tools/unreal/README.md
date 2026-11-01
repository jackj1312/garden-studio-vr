# Unreal step (WORKFLOW G8/G9) — the Airbnb method

Blender holds the measured model; Unreal adds Lumen lighting, scanned materials and the camera, exactly as the
Airbnb walkthrough was made (Blender -> Unreal 5.8). Runs on a rented Linux GPU (RunPod), never on the Mac.

## One-time access (Jack only: accounts and secrets)
1. Link GitHub to the Epic account: epicgames.com -> Account -> Apps and Accounts -> GitHub -> Connect, then accept
   the invite email from GitHub ("Epic Games" organisation). Without this the engine images are not visible.
2. Create a GitHub personal access token (classic) with only `read:packages`.
3. In RunPod -> Settings -> Container Registry Auth, add `ghcr.io` with your GitHub username and that token, named
   `ghcr-epic`. (Claude never sees the token; pods pull the engine image with it.)

## Pipeline v2: native rebuild (Jack, 1 Nov 2026: "look incredible, not an uprated version of ours"; CORRECTIONS-LOG 147)
The skeleton (positions, sizes, levels) is the measured model; every surface and object is re-made from free scanned CC0
libraries (Poly Haven, ambientCG) in Unreal itself. Site-specific choices live in `sites/<site>.json`; the scripts are generic.
1. `~/splat/bin/python tools/unreal/fetch_assets.py tools/unreal/sites/front-garden.json` -> the shared asset library
   (~/Desktop/garden-scans/asset-library, by source, LIBRARY.md lists URL + licence). Then, once per model asset:
   `Blender -b --factory-startup --python tools/unreal/export_ue.py -- --prep-models ~/Desktop/garden-scans/asset-library <ids>`.
2. `Blender -b master/front-garden.blend --python master/front-garden-v2.py -- --ue out/unreal-ue/front-garden` (about 30 s, 0.7 GB):
   one FBX per Unreal material with metre UVs (planar per face, timber along the grain, random offset per unit), plants listed
   under "replace" become placements, hedges become leaf-ball scatters with an inset core, lawns get real grass blades.
3. `~/splat/bin/python tools/unreal/prepare_ue.py tools/unreal/sites/front-garden.json out/unreal-ue/front-garden`: tints from the
   client's photo colours, tiling from real unit sizes (course period found in each scan), cameras from the photo solve -> bundle.tar.
4. Cloud: `cloud_ue.py up --max-gbp <cap>`, `put` project.tar + bundle.tar + garden_ue2.py, run the editor with
   `-ExecCmds="py /tmp/job/garden_ue2.py --bundle /tmp/job/bundle --out /tmp/job/out --cams check"` (ONE matched camera
   first), `get` the PNGs, `tools/unreal/sheet.py` (prints the EV offset to the photos), then `--cams all`; always `down`.

## Pipeline v1 (superseded: our USD in a UsdStageActor gave untextured grey, CORRECTIONS-LOG 147)
1. `blender -b master/front-garden.blend --python master/front-garden-v2.py -- --usd out/garden.usdc`
   exports the measured model (one USD, true metres, real unit geometry for brick and paving).
2. `tools/unreal/garden_ue.py` (Unreal Python, run headless in the editor): new level, import the USD, sun from the
   site's filmed angle, sky atmosphere + volumetric clouds, Lumen GI and reflections, exponential height fog,
   post-process (neutral tonemap, slight vignette, auto-exposure locked), cameras at the client's matched walk-frame
   poses, a walk sequence along the path; Movie Render Queue to PNG stills and an MP4 walk.
3. `tools/unreal/cloud_ue.py` rents one RTX 4090/L40, pulls `ghcr.io/epicgames/unreal-engine:dev-slim-5.8`, runs
   step 2 with `-RenderOffscreen`, downloads the frames, deletes the pod (money cap, as cloud_blender.py).

## Cost (RunPod, measured rates Oct 2026)
- First setup run: image pull ~25 GB (~10-15 min) + shader compile (~15-25 min) + renders (~10 min): about
  1 hour on an L40/4090 = £0.55-£0.75. Capped at £5.
- Each later look-dev round (stills + a 30 s walk): ~20-30 min = £0.30-£0.40.
- Full-quality VR streaming (Unreal + CloudXR to the Quest): ~£0.55-£0.75 per hour of use.

## Jack's requirements for the Unreal render (1 Nov 2026)
- Reflections: Lumen reflections at high quality, hardware ray tracing on (glass, the porch mirror, wet/glossy surfaces, gutters).
- A fictional character, correctly scaled (1.75-1.80 m) in the world, as a scale cue.
- Switch between first person and third person while walking (a key / controller button), same in the streamed VR build.
- Everything marked in the headset (marks.json) fixed and the matched-view audit passed BEFORE the first Unreal render.

## Changing things in Unreal without full re-renders (Jack, 1 Nov 2026)
- Unreal is real-time: moving a bed, swapping a plant, changing paving or the time of day shows instantly in the editor and
  in the streamed walkthrough. Only final films/stills are "rendered", and each re-render is minutes, not a rebuild.
- Keep the scene in layers: the measured base (house, ground) imported once; proposals as separate swappable sub-levels
  ("today", "clean", "option A", "option B"), switched live.
- Edits flow both ways: the headset marking tool's proposal shapes (marks.json, plan coordinates) can be read straight into
  Unreal as new beds/paths, so a change drawn in VR appears in the Unreal scene without going back through Blender.

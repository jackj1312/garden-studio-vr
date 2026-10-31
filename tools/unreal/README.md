# Unreal step (WORKFLOW G8/G9) — the Airbnb method

Blender holds the measured model; Unreal adds Lumen lighting, scanned materials and the camera, exactly as the
Airbnb walkthrough was made (Blender -> Unreal 5.8). Runs on a rented Linux GPU (RunPod), never on the Mac.

## One-time access (Jack only: accounts and secrets)
1. Link GitHub to the Epic account: epicgames.com -> Account -> Apps and Accounts -> GitHub -> Connect, then accept
   the invite email from GitHub ("Epic Games" organisation). Without this the engine images are not visible.
2. Create a GitHub personal access token (classic) with only `read:packages`.
3. In RunPod -> Settings -> Container Registry Auth, add `ghcr.io` with your GitHub username and that token, named
   `ghcr-epic`. (Claude never sees the token; pods pull the engine image with it.)

## Pipeline
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

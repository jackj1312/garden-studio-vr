# Morning report — overnight 31 Oct 2026

Stopped at ~02:30 when my usage limit was reached. Everything below is on disk in this
folder. **Whether it reached the live link depends on the final commit — see "Live or not".**

## What changed overnight (all tested on desktop, none yet in a headset)

**Presence**
- Procedural ambient audio: wind bed, leaf hiss on gusts, birds; muffled inside the studio;
  footsteps every 0.72 m of travel with a haptic tick on the controllers.
- Wind sway on grass, tree foliage, hedge and shrubs.
- Real Touch controller models; hand-tracking meshes when you put the controllers down.
- Fade from black on arrival; contact shadow blobs under you and under each hand.
- Foveation dropped from maximum to 0.4 (three.js defaults to maximum — it smeared the periphery).
- Shadow camera follows you, so the shadow at your feet is sharp.
- Wrist panel now hides until you turn your wrist to look at it (X pins it); laser only shows
  when it lands on the panel. Face buttons: **A next stage, B previous, Y play/pause, X pin**.

**Fixes found by the judges**
- Passthrough mode crashed on entry (undefined `hemi`) — fixed.
- You could not walk into the finished studio — collision was a solid footprint. Now four
  walls with a door gap, and it never ejects you if you walked in physically.
- In passthrough the sticks now move and rotate the *building*, never you.
- You step up onto the slab/deck (120 mm) instead of standing in the floor.
- Studs no longer run across the glazing; headers and trimmers added; flat roof (the sloped
  one cut through the rear wall); ceiling lining; frame hides once clad.
- Glass is now dark and reflective instead of milky; lighting no longer counted twice.
- Vignette moved from 0.32 m to 1 m from the eyes and only runs in VR.

**Look**
- Geometry merged per material: 351 draw calls → ~60–100. Frame cost 68 ms → ~2 ms on the M1.
- 4k tone-mapped sky on a sphere (369 KB / 662 KB); lighting from 2k EXR; both skies preload.
- Sun direction now derived from the brightest point of each sky, so shadows match it.
- Trees, shrubs and hedge rebuilt as leaf cards (sprig texture) — the icosphere "rocks" are gone.
- Lawn undulation, bare-soil borders, per-tuft tint, drier blades; dark joint plane under paving.
- Neighbour houses either side and across the back, trees over the fence — the fence is no
  longer the edge of the world.
- Deck tint corrected from salmon.

## Live or not
The permission classifier refused several `git add`/`commit` commands overnight ("sensitive
source provenance"). If the last attempt also failed, **the live link is still at build
837d187 (lightmap only)** and everything above is uncommitted here. To publish:
```bash
python3 tools/stamp-build.py && git add -A && git commit -m "Overnight presence pass" && git push
```

## Known problems left
- **Interior is too dark** (over-corrected). Raise `envMapIntensity` on `inner/fitout/worktop`
  in `src/studio.js` to ~0.9 and rebake with more samples.
- Tree cards are a first pass — texture, density and size want an hour of tuning in-headset.
- Lightmap is 2048 JPEG; darks are crushed. Rebake to 4096 and store as PNG/KTX2.
- Local splat pipeline: toolchain installed (`~/splat` venv: pycolmap 4.2.1, msplat, ffmpeg;
  Brush v0.3.0 verified at `~/splat-tools`). 126 lounge frames extracted. The pose solve
  failed on pycolmap's call signature — needs `pycolmap.extract_features(db, images)` with
  options objects; ~30 min of work.
- Nothing measured in the headset yet. Desktop GPU is fine; Quest is unverified.

## Judges' findings that are YOUR decisions, not mine
1. **Quality tiers as price points** — the buyer judge would drop them ("nobody buying a
   garden room chooses between 14,000 and 30,000 grass blades"), and price on survey,
   sightlines, sun study and film instead.
2. **Occasion layers** (barbecue, party) — "a week of work that changes no decision".
3. **The six builder's stages** — buyer wants: Today / Marked out (string lines on the lawn) /
   What you lose (quantified) / Shell / Finished day one / Finished year three.
4. **Sun path with true north** (date + time → shadows on the lawn and kitchen windows) was
   every judge's top product feature. Not built yet.
5. **The "Along fence" variant** rotates the north clerestory to face east — the design
   rationale breaks. Either re-orient it or label it the worse option.
6. **Presenter mode** — client wears the headset and only walks; you drive from the laptop.
7. **Openable door**, scale-reference figures and furniture, sightline presets ("from the
   kitchen window"), a change-of-use caveat for business studios.

Research reports (Spark for splats at ~300–500k on Quest; Brush/msplat local training;
presence techniques) are in the conversation; the key numbers are in BUILD-PLAN.md.

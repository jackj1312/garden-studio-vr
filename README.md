# Garden studio walkthrough

A walkable 3D recreation of the property in which a garden studio builds itself across six
stages, viewed at true scale in a Meta Quest 3 or on a laptop.

**M1 — viewer skeleton.** Grey-box stand-in geometry with placeholder dimensions, so the
movement and the stage mechanism can be tested before any modelling or scanning happens.
Every dimension in `SITE` at the top of `index.html` is a placeholder to be replaced once
the survey scan is in.

## Running it

Any static server works — no build step, no dependencies beyond three.js from a CDN:

```
python3 -m http.server 8765
```

Then open `http://localhost:8765`. WebXR needs a secure context, so VR requires https
(or localhost on the headset itself) — a plain LAN address will not offer Enter VR.

## Controls

**Desktop** — click to capture the cursor, `W A S D` to walk, mouse to look, `Esc` to release.

**VR** — left thumbstick walks at 1.4 m/s in the direction you are facing, right thumbstick
snap-turns 30°, and a panel on the left wrist carries the scrubber, the six stage buttons,
play and the variant switch. Point at it with the right controller and pull the trigger.
Physical walking maps 1:1, so the garden is explored on foot as much as on the stick.

## The six stages

1. As it is today
2. Cleared
3. Base
4. Frame
5. Clad and roofed
6. Finished

The scrubber interpolates between them, so stopping half way through a stage leaves it
half built. See `BUILD-PLAN.md` for the full project plan.

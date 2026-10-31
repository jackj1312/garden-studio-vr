# Plan: Jack's front garden to the Airbnb standard (31 Oct 2026)

## What the Airbnb actually is
Modelled, not scanned. Claude wrote Python that built every object in Blender from a floor
plan and two photos, then lit it in Unreal Engine 5 on an RTX 4090. The realism is the
lighting (bounced light, sunbeams, depth of field, motion blur), not photo textures.
(BENCHMARKS.md has the full reading of the author's article.)

## Why our scan looks bad
Photogrammetry stretched one texture over the whole house from 22 photos taken months apart,
with the day's light baked in. It gets the shape right and the surfaces soft, and thin things
(pergola posts) smear. It can never relight for dusk or night.

## The plan
1. **Use the scan as the tape measure, not the picture.** It already gives the layout and
   proportions at true scale (set from brick courses). Six tape measurements confirm it.
2. **Model the garden in Blender, the Airbnb way.** Python builds the house front (brick
   bond, windows with real glass, the arched window, door, porch roof, pergola), block paving,
   gravel drive, edging, lawn, the bed and its planting, the tree, the boundary and a simple
   street beyond. Clean CC0 materials matched to straight-on photos of your actual surfaces.
3. **Light it properly and compare against your own photos** — same camera position as each
   photo, side by side. Your garden is the benchmark you can judge.
   - Blender Cycles on this Mac for stills (slow but right).
   - Unreal Engine 5 for the live, playable, Airbnb-grade version: needs an NVIDIA PC. The
     Air is under Epic's 16 GB minimum. Route: a rented cloud gaming PC (Shadow), which can
     also stream full Unreal quality to the Quest 3 over wifi (Virtual Desktop).
   - Quest standalone (the web link): bake the Cycles light into the textures.
4. **Then the proposal** on top: planting, lighting, any build — the SE Landscapes layer.
5. Iterate "ultrarealistic" with the three judges and side-by-side photo checks each round.

## What I need from you
- Six tape measurements (house front width, front door width and height, path width,
  lawn length and width, tree trunk to house).
- Straight-on close photos (about 1 m away, overcast if possible) of: brick, block paving,
  gravel, the grey edging, roof tiles, the pergola timber, the lawn.
- The site plan / drawing if you can find it.

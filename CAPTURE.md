# How to record a space

This is the method, and later the instruction sheet a client gets sent.

## The one rule that matters

**Do not stand in one place and spin.** It is the obvious thing to do and it is the one
capture that cannot work.

Reconstruction works by *parallax*: the same surface seen from two different positions,
so the software can triangulate how far away it is. Spinning on the spot gives every
frame the same viewpoint, so there is no parallax and nothing to triangulate. You get a
panorama — a flat picture wrapped around a sphere. Walk six feet to the left and the whole
thing falls apart, which is exactly what VR asks it to do.

**The camera has to travel.** Walking is what produces the 3D.

## Recording a room

Three slow loops, each a complete circuit, each at a different height.

1. **Chest height, about 1.4 m.** Walk the perimeter of the room facing *inward*, towards
   the middle. Keep roughly a metre or two off the walls so you can see along them.
2. **Low, about 0.8 m.** Same loop, camera angled slightly up. This catches undersides —
   sofa fronts, table tops, skirting.
3. **High, about 2 m, angled down.** Catches floor, upper walls and the tops of furniture.

Then a fourth pass: walk into each corner and slowly pan across it. Corners are where
reconstructions fail first, because they are seen least.

**Pace.** A slow, deliberate walk — think of carrying a full cup of tea. Each loop should
take sixty to ninety seconds. Rushing produces motion blur, and blurred frames are worse
than no frames.

**Keep turning gently as you walk** so the camera always faces roughly into the room,
rather than along your direction of travel. Overlap between consecutive frames should be
high — around 70%, which a slow walk gives you naturally at video frame rates.

## Settings

- 4K video if your phone offers it, 30 fps is fine.
- **Lock exposure, focus and white balance** before you start. On an iPhone, press and
  hold on a mid-tone part of the room until AE/AF LOCK appears. Auto exposure hunting
  between frames is one of the most common causes of a failed reconstruction.
- Clean the lens. Genuinely — a smeared lens softens every frame.

## What breaks it

- **Mirrors and glass.** They show a reflection that moves differently from the room, and
  the solver tries to reconstruct a space behind the mirror. Cover large mirrors, or
  accept a mess in that area.
- **Windows with bright daylight.** The camera exposes for the window and the room goes
  black, or vice versa. Shoot on an overcast day, or close the curtains and put the lights
  on and keep it consistent.
- **Anything that moves.** People, pets, curtains in a draught, a TV that is on. Turn the
  television off.
- **Blank surfaces.** A plain white wall has no features to match. It will reconstruct
  poorly and there is not much to be done about it indoors, beyond making sure the wall is
  seen from several angles.
- **Changing the lighting mid-shoot.** Pick a lighting state and leave it alone.

## Scale

Put something of known length in the shot and leave it there — a tape measure extended to
one metre on the floor is ideal. Reconstructions come out unscaled, and one known
dimension fixes the whole scene.

Also write down three real measurements before you start: room length, room width, and
ceiling height. Thirty seconds that saves an hour.

## After recording

Upload the video to Luma AI's free tier, which takes video directly and returns both a
Gaussian splat and a mesh. Processing is cloud-side and takes a while.

For a first test, one room and one good set of loops is plenty. The thing being tested is
the method, not the room.

## Reconstructing it locally

`tools/photogrammetry/scan` is a small Swift tool built against Apple's `PhotogrammetrySession`,
which ships with macOS and runs on the Apple Silicon GPU. Nothing to install, and the
client's video never leaves the machine — which matters once this is a paid service.

```
cd tools/photogrammetry
swiftc -O -o scan main.swift        # once
./scan ~/Desktop/garden-scans/clip.mov ~/Desktop/garden-scans/out.usdz medium 160
```

It takes a video (pulling evenly spaced frames itself) or a folder of stills, and writes a
USDZ you can import straight into Blender. Detail levels run preview, reduced, medium,
full, raw — start at medium.

**It suits outside-in capture**: walking around a garden studio, a house, an extension.
It is the wrong tool for the inside of a room, which is the opposite geometry and what
Gaussian splatting handles well.

## Which route for which job

| Subject | Best route | Why |
|---|---|---|
| Garden, building exterior, extension | `./scan` locally | Outside-in, private, free, no upload |
| Inside of a room | Gaussian splat | Inside-out reconstruction, far better results |
| Fast first test of your technique | Luma AI free tier | Minutes, no setup, handles both |

Local splat training on this Mac is possible with Brush, which runs on Apple Silicon via
Metal. Not set up yet.

## First real test — 31 Oct 2026

Lounge, 91 s of 4K60, lamp-lit, portrait, one pass through four rooms, tape measure down.

- 60 frames spread across the whole clip: **failed at registration in 31 s.** One frame every
  1.5 s is too big a jump between views to match. That was the test design, not the capture.
- 120 frames from one continuous 36 s stretch of the lounge: **reconstructed in 30 s**, 6,200
  triangles, a textured lump the size of half the room. Carpet, sofa and radiator are
  recognisable in the texture; the shape is not a room.

So: the pipeline works end to end — phone to Mac over wifi, frames out, reconstruction, USDZ
into Blender — and Apple's engine does what it was built for. It was built for walking around
an object. Pointed at the inside of a room it produces a blob, as expected.

**Decision:** local photogrammetry for gardens, buildings and exteriors. Gaussian splatting for
interiors. Feed it 300+ frames, never 60.

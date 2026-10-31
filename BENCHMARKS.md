# Benchmarks — what this has to be judged against

Jack, 31 Oct 2026: "The Airbnb quality is still worth start but this video gives a good
example of the quality too." Both are standing references. Every judge pass compares
against them; nothing ships that is obviously below either in its own area.

## 1. The Airbnb walkthrough (modelled, lit in Unreal Engine 5)
Repost: https://x.com/CodeByPoonam/status/2115425204289827065
Original: https://x.com/SimbasJungles/status/2109095401273938072 (Simba, 11 Oct 2026)
Author's write-up: https://x.com/SimbasJungles/status/2109295930021208144

**It is not a scan.** Read from the author's own article (31 Oct):
- Inputs: the builder's floor plan, two phone photos of the empty flat, a few reference
  images (ChatGPT concepts, Pinterest) and a shopping list of real furniture.
- Claude Code (Opus 5.5) wrote Python that modelled every object in Blender 5.2 and
  exported it to Unreal Engine 5.8. No external 3D models; textures Poly Haven CC0 or
  generated in Python.
- Quality came from lighting, not geometry: Lumen global illumination, sunbeams through
  local fog volumes, dust that glows only in the beams, motion blur, depth of field,
  dynamic vignette. "Leveraging UE's lighting and shadows to compensate for the lack of
  polygons."
- Iterated "ultrarealistic" 4–5 times; Claude took 849 screenshots over about two days
  to check its own work. About 3 hours of the author's time.
- Runs as a desktop game on an RTX 4090 at 5120×1440, 64 fps after Claude optimised it.
  Four times of day, every lamp switchable. Not VR.

Judge the real garden against it on: soft bounced light everywhere, warm grade, clean
crisp materials (no smeared photo texture), believable scale, film-camera effects.

## 2. SE Landscapes garden design walkthrough (designed garden, rendered)
https://youtu.be/eJ3wgs7NJkU — "Garden Design Essex 3D Walkthrough Video", 1:22.
Lumion-style film of a bespoke garden. **This is the bar for everything we design in**:
the studio, new planting, fencing, lighting and the film itself. What makes it work:
- **Planting density**: every bed is full — perennials, grasses, alliums, lavender,
  ferns, climbers on the fence; nothing is bare soil. Real species, varied heights.
- **Mature trees** with full canopies that cast dappled light, not sticks with cards.
- **Light**: bright, slightly hazy, high-key daylight; soft shadows; a touch of bloom
  and lens softness; aerial haze on anything far away. Never dark or contrasty.
- **Night shot**: warm uplighters in the beds, path lights, a lit garden building;
  the sky nearly black, the garden glowing.
- **Materials**: horizontal-slat cedar fencing, timber pergola posts, stone paving
  with real joints, circular lawn with a crisp steel edge.
- **Camera**: slow drone-height arcs, low tracking shots through planting, a reveal of
  the garden building, a day→night cut. 1:22 with music.

### What the film actually is, shot by shot (stepped through 31 Oct)
- 0:00–0:03 logo card on olive green; 1:19–1:22 end card "Award-Winning Garden Design".
- 0:04–0:17 low tracking shots at about 1 m height, moving slowly through the beds:
  slender multi-stem trees (birch / amelanchier type, airy canopies, pale trunks), perennial
  beds of white umbels, ornamental grasses, lavender and salvia purples, cedar fence panels
  with **horizontal slats**, square timber pergola posts, neighbour houses beyond the fence.
  Bright, hazy, high-key light; soft shadows; a faint bloom on the brightest leaves.
- 0:22–0:34 a Victorian-style glasshouse on a cedar base with potted plants inside, lavender
  beds, gravel with stepping stones, the slatted fence behind.
- 0:28 the client's house: white render over brick, slate roof, balcony — modelled, not a
  photograph, but to scale with real window proportions.
- 0:40–0:46 drone shots from 10–15 m: a **circular lawn with a crisp edge**, curved beds of
  perennials and grasses, gravel paths, glasshouse at the far end; nothing is bare soil.
- 0:52 the camera flies *through* a canopy — real leaf textures, close.
- 0:57 cut to night: the same drone angles; uplighters on every tree and in the beds, path
  lights, house and glasshouse lit from inside, sky deep blue-black, haze catches the light.
- Camera grammar: slow dollies, slow drone arcs, one crane-down, one day→night cut; music.

## How to use these
- Before any judge pass, open both and look at them again. Then look at ours.
- "Does it feel like the SE Landscapes garden?" is the question for planting and light.
- "Does it feel like the Airbnb capture?" is the question for the existing garden.
- The first real test is Jack's own garden: captured to the Airbnb bar, designed to the
  SE Landscapes bar, walked in the Quest 3.

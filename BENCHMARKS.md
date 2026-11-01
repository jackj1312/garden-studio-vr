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

## 3. kogu's AI-built bedroom (Codex + Blender, rendered) — added 31 Oct 2026
https://x.com/koguGameDev/status/2116450061853057368 — "Codex GPT 6.1 Terra + Blender", 30 s,
1080×1920 vertical. Jack: "hard to distinguish from reality". Stepped through 31 Oct.
- An AI agent modelled and rendered it in Blender, unattended; iteration 8 (the author says the
  quality was starting to plateau and he will distil what was learned).
- **Offline path-traced render (Cycles), not real-time and not VR.**
- Why it reads as real: soft overcast window light with bounce everywhere and no dark
  corners; dense believable imperfection (rumpled duvet, phone and cable on the bed, tissue
  box, laundry drying in the window, cluttered shelves, photos pinned to the wall); true scale
  of a small Japanese flat; a handheld phone camera (wide vertical lens, slight wobble,
  neutral grade).
- For us: the bar for the **rendered film** tier, and proof that Blender path tracing gets
  there. The headset gets the same light baked into light maps.

## 4. THE TARGET: a real house as a Gaussian splat in the browser (Jack, 1 Nov 2026: "this is the actual thing im trying to eventually produce")
https://x.com/rosemoni18/status/2116486864471527912 — 70 s screen recording, 1110×720. Post text and frames read 1 Nov.
- What it is: one person walked through a real house with a phone; the footage became a **3D Gaussian Splat**, viewed in a
  normal browser tab (built on **PlayCanvas**, open source). Photoreal because it IS the captured house, not a model.
- Frames: a modern house exterior (timber cladding, render, large windows, planting) and interiors (bathroom with tiles,
  vanity, shower); free walk-through with smooth camera motion; every surface and shadow is real.
- Claims in the post (unverified): ~$200 per scan, freelancers charge $300–800, file size small, loads on a phone.
- What it means for us: "as it is today" = capture and splat the real garden (we already have the walk video and a
  camera solve; ~/splat has the msplat trainer). Measured modelling stays for the clean base, proposals and edits; the
  proposed changes are placed into the splat scene. Viewer: our three.js viewer can load splats (or PlayCanvas/SuperSplat).

## 5. "Architecture & Design" (Steam Early Access): plan-to-3D design tool (Jack, 1 Nov 2026)
https://x.com/luqman_talks/status/2115382375899447678 — post text read 1 Nov; the product is on Steam ("Architecture & Design").
- An architect's tool: draw accurate 2D plans, the 3D building appears instantly; walk it in first person or VR; multi-storey,
  stairs, custom roofs, doors/windows, furniture and kitchens, materials, terrain sculpting, landscaping, ponds, time of day,
  weather, growing ivy; PDF vector plan export; import own models; Steam Workshop.
- What it means for us: the reference for the DESIGN side of the studio software — plan-first editing that stays accurate in
  3D, live first-person/VR, landscaping tools. Our plan JSON + build script already work this way; the gap is an interactive
  editor. Not verified hands-on (Windows game; not run here).

## How to use these
- Before any judge pass, open both and look at them again. Then look at ours.
- "Does it feel like the SE Landscapes garden?" is the question for planting and light.
- "Does it feel like the Airbnb capture?" is the question for the existing garden.
- The first real test is Jack's own garden: captured to the Airbnb bar, designed to the
  SE Landscapes bar, walked in the Quest 3.

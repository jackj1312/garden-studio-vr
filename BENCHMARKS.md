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

- **Frame study 1 Nov 2026** (video downloaded with Jack's permission; author's caption confirms "Blender and Unreal
  Engine 5"): see ~/Desktop/23 Battle Road - First Build Spec/references/airbnb-walkthrough/STUDY.md. The look is the
  light: raking warm sun, dappled leaf shadows on walls, backlit sheer curtains, time-of-day presets, switchable emissive
  lamps, dense styling, eye-height wide lens with motion blur. Geometry simple and clean, never broken.

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
Jack's link: https://x.com/rosemoni18/status/2116486864471527912 (31 Oct 2026). **This is an uncredited repost**, as was
ToolFolio's of 8 May 2026 (https://x.com/toolfolio/status/2052716015713202644, same 70 s clip). Both posts' replies are bot spam.
Its claims ("one guy… his phone", "~$200 per scan", "$300–800 freelancers") are the reposter's, not the maker's.

**Primary source (traced 1 Nov 2026 via the SuperSplat logo in every frame and the house number 2508 on the porch):**
"2508 Paramount House" by **Cameron Cone** (@cameroncone), https://superspl.at/scene/91c1e47e, published 6 May 2026,
54.7K views. It is 7.4M Gaussians, 94 MB SOG with spherical-harmonics band 1, and walk mode with collision. The video is a
screen recording of his authored camera tour in the SuperSplat viewer (named stops such as "1 Kitchen", with a timeline).
- **Maker:** a broadcast director of photography (Olympics, NFL, HBO) in Austin, TX. His business is Spatial Intelligence
  Group (https://sig-data.com). It sells exactly our product: scans of homes, a to-scale floor plan generated from the scan,
  "scan what's there, design what's next" for architects, a Revit model landed on the real site, and Unreal Engine
  pipelines for VR/AR. He now captures with **XGRIDS LCC + PortalCam LiDAR**.
- **His method, in his own words (scene comment):**
  - Cameras: Canon 5D Mark IV with 14 mm and 35 mm lenses, plus a DJI Pocket gimbal camera.
  - Software: RealityCapture to align, Postshot to train, SuperSplat to edit, and "a little bit of C4D for object cleanup".
  - "I separately captured each area, rebuilt them in Super Splat to compress the files, and finally combined them all
    into one massive splat."
  - Months of work over "multiple versions of this house" to make the pipeline reliable. Walk-mode collision was the
    feature he cared about most.
- **Unanswered in the thread:** total photo count, time taken, and how he solved the white walls (a commenter says
  RealityCapture and Postshot fail on them).
- **What actually makes it look real:** sharp full-frame DSLR stills (not phone video), a wide 14 mm for coverage, 35 mm for
  detail, each room shot densely as its own job, and hand cleanup.

**A second house the search results mixed up with this one:** "Private Residence Interior" by Tony Rose (eraser851),
https://superspl.at/scene/9d09ab82 (20 Sept 2026, 15M Gaussians, 524 MB). Will Eastcott of PlayCanvas promoted it as
"$500 Insta360 X5". It is the 360-camera route, and Tony's own write-up gives these numbers:
- ~1000 Insta360 X5 interval photos, about one every 3 ft, on a selfie stick held at eye height ~1 m ahead. Some shots
  were taken low on hands and knees, others held high. 4 h inside, plus 2 h outside (drone and 360 video).
- RealityScan and Postshot alignment failed after days of trying. Spirula Studio worked once a script split each photo
  into its two fisheye halves (cam0/cam1). Depth and normal maps were generated "to help fill in the walls".
- Alignment took ~15 h and training ~20 h on an RTX 3090 / 128 GB RAM machine; final edit in SuperSplat. A commenter says
  the whole thing took at least 60 hours.
- Delivered on his own branded PlayCanvas viewer (https://view.promediaproductions.com/residence-exterior/). The exterior
  is a separate 18.9M-Gaussian splat with 7 streamed LOD levels (splat-transform), a mobile file, voxel collision, a 360
  sky backdrop and portals at each door into the interior. He also built a "blueprint" cut-away viewer.
- LinkedIn critics on Will's post: visible artifacts and blur, 360 lens distortion makes rooms feel bigger, and a 15M
  non-streamed scene lags on ordinary machines.

**What it means for us:**
- "As it is today" = a splat of the real garden, and the bar is Cameron's sharpness, not a phone video.
- Capture: shoot each zone separately and densely in stills (wide plus a detail lens, gimbal video for joins), then align,
  train, clean and merge. A 360 camera is the cheaper, faster fallback.
- Deliver: streamed LOD plus a mobile/Quest file, voxel collision for walk mode, an authored camera tour, and portals
  between zones.
- Measured modelling stays for the clean base, the proposals and collision. Proposals sit inside the splat scene.
- Our current walk video is phone-grade input, so expect a splat below Cameron's bar. A proper stills capture is the
  likely next step.

## 5. "Architecture & Design" (Steam Early Access): plan-to-3D design tool (Jack, 1 Nov 2026)
https://x.com/luqman_talks/status/2115382375899447678 — post text read 1 Nov; the product is on Steam ("Architecture & Design").
- An architect's tool: draw accurate 2D plans, the 3D building appears instantly; walk it in first person or VR; multi-storey,
  stairs, custom roofs, doors/windows, furniture and kitchens, materials, terrain sculpting, landscaping, ponds, time of day,
  weather, growing ivy; PDF vector plan export; import own models; Steam Workshop.
- What it means for us: the reference for the DESIGN side of the studio software — plan-first editing that stays accurate in
  3D, live first-person/VR, landscaping tools. Our plan JSON + build script already work this way; the gap is an interactive
  editor. Not verified hands-on (Windows game; not run here).

- **Studied from the primary source, 1 Nov 2026 (Jack: "this is what I have in mind… this is what I want to be able to do"):**
  Steam app 5032750 by Crispytecture Games (solo; YouTube "Chris 3D ArchViz"), Early Access 21 Aug 2026, £15.99, Windows,
  Unreal Engine with hardware ray tracing (min RTX 2060 6 GB), on GeForce NOW from 19 Oct. DWG/DXF/PDF plan import,
  OBJ/PDF/DXF export, PCVR (OpenXR), kitchen configurator, terrain and scatter, sun/weather, roofs and dormers. Closed source.
  Every feature read frame by frame from an 82 s promo (via @Arcane_Aii). Full study, plan and references:
  ~/Desktop/Plan-to-3D Studio Plan/ (HTML + references/primary-source.md, video, all frames).

## 6. Build-sequence cutaway (future addition; Jack, 1 Nov 2026)
https://x.com/Solvaix/status/2116239616025968832 — post text read 1 Nov: Claude modelled a whole house in code, cut it in half to
show the services (every pipe and wire), animated it with sound, all running in the browser.
- Jack's addition: for PROPOSED changes, show the whole build from start to finished so clients see exactly what goes in,
  including groundworks: setting out, dig, footings, concrete, sub-base, membranes, walls, roof, landscaping, planting.
- How: each proposal is built as ordered construction stages (the viewer already has a 6-stage build slider from the demo
  studio, src/app.js STAGES); add cross-section/cutaway views and per-stage labels, quantities and costs.

## How to use these
- Before any judge pass, open both and look at them again. Then look at ours.
- "Does it feel like the SE Landscapes garden?" is the question for planting and light.
- "Does it feel like the Airbnb capture?" is the question for the existing garden.
- The first real test is Jack's own garden: captured to the Airbnb bar, designed to the
  SE Landscapes bar, walked in the Quest 3.

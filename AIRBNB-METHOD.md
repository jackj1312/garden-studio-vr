# How the Airbnb walkthrough was made: every step and nuance

Studied 2 Nov 2026 from the primary sources: the author's full write-up "How I modeled my entire Airbnb with Opus 5.5"
(Simba, @SimbasJungles, X article 2109286119401492480, 11 Oct 2026, text plus all 11 images), the original video
(x.com/SimbasJungles/status/2109095401273938072, 39.75 s, 1918×1080, downloaded 1 Nov with Jack's permission) stepped
through at 1 fps and 2 fps with full-size crops, and the author's caption. Where the author doesn't say, this says so.

## 1. The facts
- One person, about **3 hours of their own time**, ~15 % of a weekly Claude Max 20× allowance. Claude Code with Opus 5.5 did
  the work over **about 2 days**, taking **849 screenshots and preview renders** to check itself.
- Stack: **Blender 5.2** (modelled by Python that Claude wrote) → **Unreal Engine 5.8** (lighting, effects, the playable
  build). **RTX 4090** desktop at 5120×1440. **Not VR.** Not a scan.
- **No external 3D models.** Textures: a few Poly Haven CC0 scans, the rest generated in Python.
- A one-bedroom beachfront flat about **8 m wide**: living/dining with a kitchen run, bedroom, bathroom, balcony.
- **4–5 small iterations**, six versions of the same bedroom camera (v1 → v6).

## 2. What the author gave Claude (the inputs)
1. **The builder's floor plan**: a furnished 2D plan (a sales-brochure plan, with furniture drawn on).
2. **Two photos of the empty flat**: the glass doors to the balcony and the sea beyond. That is all the survey there was.
3. **Reference images**: concepts the author made in ChatGPT (a warm, oak-and-linen look) plus some Pinterest.
4. **Screenshots of their Mercado Livre shopping cart** (Brazil's Amazon).
   - **The one rule: every piece of furniture and decor had to be something in stock that could actually be bought.**
   - Nuance: a cart gives real products, with real dimensions, materials and product photos. That is why nothing in the
     flat is a generic shape at a guessed size, and why the styling reads as a real shop's palette.
Nothing was measured on site. Scale came from the plan and the product dimensions.

## 3. The prompts (verbatim, the author's translation from Portuguese)
Main prompt, sent after the plan, photos, cart and concept images:
> "i want you to create the apartment in blender using unreal engine 5. i want it to be realistic, well put together and
> well lit, based on the info i gave you. models the apartment in Blender and turns it into a walkable scene in Unreal
> Engine 5, helping designers and clients explore the layout and experience the space before it's built. do this for me"

The author: "You would probably be surprised by how simple my prompts are. I didn't specify anything besides the
Blender + UE5 workflow." The first result came **about an hour** later: correct layout, flat white, untextured, basic.

Feedback between versions (excerpts, verbatim):
> "The sofa pillows are terrible. The two in the back are actually inside the sofa. (…) The rug is terrible. Its rounded
> edge looks like a cylinder. It's not realistic, it's not triple A like I expected."

> "the pillows are really ugly, way too artificial. (…) I also want some texture on everything. The bedroom wardrobe is
> basically solid white. (…) i want everything in great AAA quality, very impressive."

> "i want to make everything in the apartment even more triple A. (…) i want ultra realism in EVERYTHING. including
> leaves. i also want small particles flying around the apartment lit by beautiful godrays. i want very cinematic lighting."

Then "ultrarealistic", again and again. The author's own summary of the first result: "good enough, but lacked polygons
and texture on most of the furniture."

Performance prompt:
> "i want it to run at 60fps without compromising anything in the graphics. the particles should move more. and i want
> motion blur, better godrays and more cinematic light."

Nuances of how the feedback worked:
- It is blunt, specific and visual: a named object, what is wrong with it, and the standard expected ("triple A").
- It never says how to fix anything. It names the fault and the bar.
- Each round was judged on **the same room from the same camera** (the v1–v6 ladder), so progress was visible.

## 4. What Claude did, step by step (as the write-up states it, with what the images show)
1. **Built the whole flat in Blender by Python**: rooms from the plan, walls, floor, ceiling, the balcony, door frames,
   the kitchen run, the bathroom; then every furniture piece and decor item modelled procedurally (sofa, cushions, bed with
   layered bedding, headboard, bedsides, lamps, round glass coffee table, rug, sideboard, dining table and chairs, arched
   mirror, framed prints, plants, vases with dried grass, books, the rattan pendants). No downloaded models.
2. **Textured it**: a few Poly Haven CC0 scans (wood, plaster, fabric) plus textures generated in Python (the rug, the
   cushion weaves, the rattan). Later rounds added "texture on everything" after the "solid white wardrobe" complaint.
3. **Exported to Unreal 5.8 by script** (format not stated; the author says "Python builds the whole apartment in
   Blender and exports it to Unreal", and that Claude "drove everything through scripts").
4. **Lit and dressed it in Unreal**, where the look was made (section 6).
5. **Checked its own work**: "it screenshots every room, spots what looks off and fixes it." 849 screenshots and preview
   renders over about two days: the contact sheet in the write-up shows hundreds of room views from eye height, every room,
   many angles, day and night, plus close-ups of single objects.
6. **Took the owner's feedback** in 4–5 rounds (section 3), each judged on the same camera.
7. **Profiled for 60 fps** (section 7).
8. **Built a separate 2D planner**: move the furniture in it, press F5 in the game and the layout reloads. So the layout
   is data read at runtime, not baked into the level.

## 5. What the two comparison images prove
- **Blender quick preview vs Unreal real-time, same models, same camera** (sideboard with vase and books; coffee table with
  a plant): in Blender the objects look flat, grey and ordinary. In Unreal, with a low warm sun throwing hard shadows of the
  plant across the wall and the book, the same geometry looks real. The author: "if you take each piece of furniture at
  face value, it's no better than any free kit you can find online. The real secret here was leveraging UE's lighting and
  shadows to compensate for the lack of polygons."
- **v1 → v6, same bedroom camera**: v1 flat white, no textures, even light; v2 textures and a warm sun; v3 headboard and
  cushions; v4 better bedding and bedsides; v5 warm grade, sun lower; v6 hard plant shadows across the bed and wall, warm
  everywhere. Geometry barely changed after v3. **Almost all of the gain is light, texture and styling.**

## 6. The look, piece by piece (from the video, with timestamps)
**Light (the main thing)**
- A **low warm sun** from the sea side, raking across the floor and up the walls; bright patches on the planks, the sofa
  arm, the bed. In the morning preset (0–12 s, 30–40 s) the sun is low and golden; at 36 s it is high and white with a
  visible disc, flare and bloom.
- **Hard shadows from plants**: the potted tree and the balcony plants throw sharp leaf shadows onto the sofa, the wall and
  the floor (1–12 s, 26 s, 36 s). This single device does more for realism than anything else in the film.
- **God rays with dust**: visible volumetric beams through the balcony doors in the first seconds; small bright particles
  drift and **only glow inside the beams**, like real dust. Nuance from the write-up: UE 5.8 local fog volumes don't render
  within 10 m of the camera by default, and the flat is ~8 m wide, so the beams never showed until Claude found and changed
  that setting.
- **Soft bounce** filling every corner: no black corners, no flat grey; ceilings are lit by the floor's bounce and carry a
  faint warm gradient.
- **Four times of day** on keys 1–4 (Manhã, Tarde, Pôr do sol, Noite). Switching shows a toast with the preset's name
  (13 s "Pôr do sol", 31 s "Manhã"). Sunset (13–29 s) turns the sky pink-orange and the whole interior amber; night (write-up
  image) is lamp-lit with the sea dark.
- **Every lamp has a switch**: the flat round ceiling light ("plafon"), the floor lamp, the bedside lamps, the rattan
  pendants, the kitchen under-cabinet strip and the mirror's LED strip. Looking at a fitting shows a prompt (20 s:
  "E Acender Plafon da sala"). Shades are emissive and glow; the rattan pendant throws its lattice pattern onto the ceiling
  (28 s). L toggles all lights.
- **A warm grade throughout**: whites are cream, shadows are amber, never blue-grey.

**Materials and scale**
- Plaster walls with subtle tonal variation (limewash look), not flat colour. Oak-look wood floor with planks at a true
  width and visible grain. Black granite kitchen and bathroom counters with a glossy reflection. White slab kitchen units.
  Small square mosaic tiles on the balcony wall. Linen lampshades that glow. Woven rattan. Jute rug with a soft edge (after
  the "cylinder edge" complaint). Sheer **pleated voile curtains** on every sunlit opening, backlit so they glow.
- Textures are at real scale: tile size, plank width, weave. Nothing stretched, nothing tiled visibly.
- Geometry is **simple and clean**: boxes with softened edges, door frames, a glass balustrade with a black top rail. Nothing
  is broken, nothing floats, nothing clips, no raw surface anywhere.

**Styling density (every view is dressed)**
- Living: cream sofa with 4 cushions and a throw; jute rug; round glass coffee table with a trailing plant; oak sideboard
  with stacked books; TV; floor lamp; a trio of leaf prints in oak frames; a surfboard-shaped arched mirror; dried grasses in
  a vase; a plant by the door; a round dining table with light oak chairs under a rattan pendant.
- Bedroom: white layered bedding, a throw, 3 sage cushions and a patterned one, an upholstered headboard, bedside lamps,
  two framed sea prints, a sheer curtain, a potted tree on the balcony outside.
- Bathroom: oak vanity with black granite top and a round basin, black tap, mirror with an LED strip, soap and bottles.
- Kitchen: open oak shelf with jars and plants, a washing machine under the counter, a fridge, a lit niche.
- Balcony: mosaic wall, potted tree, plants, two chairs; beyond it a beach, sea, palms, a road and the neighbouring facade
  with balconies (7 s). The outside context is built, not a backdrop photo.

**Camera and effects**
- Eye height, wide lens (about 20–24 mm equivalent), slow glide. **Motion blur** on every turn (menu default 50 %); fast
  turns smear (29 s). **Depth of field** ("Foco cinematográfico", off in the menu screenshot but visible as softness on
  near objects in some shots), **lens effects** (bloom, flare) at 100 %, a **dynamic vignette**, and **god rays** and
  **dust** at 100 %. Quality preset "Cinema (máximo)", render resolution "Automática" (dynamic, TSR upscaling).

**The playable build (the on-screen help, verbatim)**
`Horário: Manhã · 1 Manhã 2 Tarde 3 Pôr do sol 4 Noite · E acender/apagar a luminária ou o interruptor mirado · WASD
andar · Shift correr · L todas as luzes · V câmera 1ª/3ª pessoa · R rack madeira / pintura branca · Esc menu e
configurações · P foto · F FPS · F5 recarregar a planta · H ocultar ajuda`
- So: time of day, look-at lamp/switch toggle, walk/run, all lights, first/third person, **a material variant toggle on the
  TV rack (wood or white paint)**, an Esc menu (tabs Tela / Gráficos / Controles / Ambiente with quality, render resolution,
  motion blur, sun rays, dust, lens effects, cinematic focus, visual grade), photo mode, FPS counter, reload the plan, hide
  help. The UI is in the owner's language.

## 7. The performance pass (why it runs)
Asked for 60 fps "without compromising anything", Claude profiled the frame and found the GPU spending up to **15 ms on a
glass reflection that doesn't even show during the day**; it now only turns on in the late afternoon and at night. Shadows
were using more rays than anyone can perceive; cut. **Dynamic resolution (TSR upscaling)** holds 60. Result on the RTX 4090
at 5120×1440: 27–43 fps → 64–65 fps, every view, day and night. Nuance: nothing visible was removed; costs were moved to
when they matter.

## 8. Why it reads as real: the short list
1. Light does the work: low warm sun, hard plant shadows, god rays with dust, soft bounce, emissive lamps, warm grade.
2. Every surface has a texture at true scale; plaster and fabric have variation.
3. Every view is dressed to a shop's density, with real products at real sizes.
4. Geometry is simple but never wrong: no gaps, nothing floating, nothing raw.
5. A film camera: wide, eye height, motion blur, vignette, bloom, DOF.
6. Hundreds of self-check screenshots and five rounds of blunt owner feedback on fixed cameras.
7. The outside is built too (sea, sand, palms, the neighbouring facade), so windows show a world.

## 9. What it is not (so we don't copy the wrong thing)
- Not VR and not a headset budget: a 4090 at 60 fps with dynamic resolution. Our Quest build needs the same look from baked
  light; the live look needs a cloud GPU or a PC.
- Not measured: the plan was a brochure plan and two photos. Ours comes from architect's drawings and photos, which is
  an advantage for accuracy, not a reason for a different look.
- Small: one bedroom, ~8 m wide, no stairs, no roof, no second storey, no garden. A whole house has ten times the rooms
  and the self-check loop has to scale with it.
- Not stated: the Blender→Unreal export format, the UE lighting features by name (Lumen is UE5's default GI but the article
  doesn't name it), the Python texture generators, or the planner's file format.

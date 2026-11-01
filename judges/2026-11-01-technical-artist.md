# Technical artist / surveyor judge: audit-2 fix pass, 1 Nov 2026

Read from the 12 sheets (BEFORE and AFTER rows), the v2-mockup pairs, the AUDIT.md claims, DETAIL-CHECKLIST.md and the CORRECTIONS-LOG. Estimates are read off the sheet pixels against known object sizes, so treat them as +/- 10 cm.

## Faults, worst first

1. **Apple tree (sheet_04 walk_0059, sheet_12 walk_0017, sheet_11).** The real crown fills the top half of the frame and arches over the lawn. In the model it is a small crown at the frame edge, or only a black twisted trunk, with empty sky above. The AUDIT lists this as unresolved, but it is the biggest visual miss in every garden-facing view. The correct value is a vase crown of about 6 m, six limbs and a trunk split at about 0.8 m.
2. **Planting is wrong everywhere (sheets 04, 05, 06, 09, 11, 12).** The model has stiff violet spikes and faceted dark ball topiary. The balls are visibly low-poly chunks. The real beds have silver santolina and lavender, pink hydrangea, orange and red heuchera, begonias, grasses and a gazing ball. In walk_0071 the real speckled planter is a grey trough in the model. The mockup mix is still the plant model.
3. **Boundary hedge position and shape (sheets 01, 08, 12).**
   - In walk_0035 the outline and model hedge sit about 70 px left of the real hedge, roughly 0.5 m toward the neighbour. In walk_0039 the model's face is about 0.3 to 0.5 m short of the real leaf face.
   - It is a smooth rounded capsule. The real one is a squared block with a thin spire.
   - The model top is about 0.5 m above the real clipped mass.
   - No leaf structure, and a flat dark-green slab in walk_0039 (confirms log row 79).
   - A stray dark quad lies on the grass under it in walk_0035.
4. **Orange conifer and green conifer (sheets 01, 02, 03, 08, 11).** The model cone is bright saturated orange. The real one is a muted rust spiral topiary. It is about 25 cm too tall, with a base too wide, and its pot is a plain black cylinder. The real pot is a speckled urn. The green one is a plain cone; the real one is a slim olive spiral.
5. **Stone bench (sheets 01, 03, 08).** Positioned correctly, but it is about 25% too narrow (80 px against 105 px, about 25 cm short) and flat-topped. The real top is curved with carved cherub end supports. It is pale white-grey instead of weathered, and the pumpkins are missing.
6. **Lower window surround (sheets 01, 03, 08).** The model has a thick cream stone surround on all four sides, about 15 to 17 px wide. The real window has no cream surround; it has a galvanised steel lintel and a slim reveal. The upper window surround is also about twice too thick and too pale. This breaks checklist "Windows: surround, lintel".
7. **Dark crack lines in the paving (walk_0039, 0049, 0071, 0035).** They are identical before and after, run along the same kerb lines, and appear in no real photo. G14 was closed as a mockup-sun shadow without proof. They look like gaps between the cut ground surfaces.
8. **Street and horizon (sheets 09, 05, 12; v2-mockup walk_0095).** Beyond the lawn the model is a flat green plane to the horizon. There is no road, kerb, parked cars, opposite houses or street hedge. The neighbour's beige buildings behind the shed are also missing, so there is bare sky in walk_0079.
9. **Bins (sheet_06, v2-mockup pairs2).** Tapered plain boxes. There is no "23", no lid line, no wheels or handle, and no logo sticker. The left bin is a bright orange-brown where the real one is dark brown.
10. **House number plaque (sheets 01, 02).** A blank pale grey slab. The real plaque is dark slate with a white "23".
11. **Bed and path-edging junction (sheet_04 walk_0059 AFTER).** At the bed's front-left corner, loose odd blocks stick out and a dark gap sits between the last bed unit and the path edging. It does not read as one continuous run, where the real edging curves continuously.
12. **Shed (sheet_07 walk_0079).**
    - The fascia is orange.
    - The roof reads as a thin slab with no felt visible.
    - The high end sits about 40 px (about 14 cm) low.
    - The lamp is a dark box where the real one is white.
    - Not rendered at all: the black ornate wall panel (the outline has it) and the bird table.
13. **Missing movable clutter (today build).** The balance bike, the blue scooter, the boots by the step, the pumpkins and the lizard ornament are all in the photos and not modelled. The pergola festoon lights and lanterns are also missing. This breaks the checklist line on movable things.
14. **Mirror (sheets 02, 11).** The arch reads as a dark window with glazing bars. The real item is a garden mirror reflecting green, and the inventory says "reflective".
15. **Lighting and colour (every sheet).**
    - The sky is dark navy against a real pale blue.
    - Pergola timber is darker brown and washed-out yellow-tan in different views, where the real timber is honey-orange.
    - The lawn is yellow-olive with large repeated autumn leaves; the real one is vivid green with few small leaves.
    - The mockup sun gives wall shadows that don't match the real ones.

## Claimed fixed but not fixed

- Note 1, hedge "to the house": the length is right, but shape, position and material are not. The checklist hedge line ("clipped or loose, top shape") fails.
- G8, bench and conifers "modelled": placeholders only (log rows 77, 78).
- Note 3 / G6, shed fascia and light: the shed fascia is the wrong colour, and the light is dark where the real one is white.
- Note 12 / G14, paving seams: "not a fault" is unproven (item 7).
- Note 9 / H3, "no sett through sett": a visible gap and odd stub blocks remain at the bed to path-edging junction.
- Inventory ticks for the metal wall panel, bins "23, lids, wheels" and the plaque "modelled with its photo": none are visible in the matched views.
- The log has a numbering clash: rows 77 and 78 are used twice (audit, then splat run).

## Now right

- Pergola post positions and section: the outline sits on the real posts in walk_0071, 0091 and 0203, and the beam and rafter height now clears the porch.
- House walls, the roof, chimney, roof windows, dish and downpipes outline-match the photos in walk_0017, 0035 and 0045. The door sits on the true wall plane, and the door and step positions match.
- Bed outline, border-inside-bed and the path and lawn kerbs follow the real curves. Edging unit family, colour and the 6 to 8 cm upstand read correctly, apart from the junction in item 11.
- Fence height and board rhythm match walk_0071 (top at the real line), and bin positions are right.
- Brick on the neighbour now matches the client's brick, and the shed's pent slope is the right pitch.

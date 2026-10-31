# Corrections log — every place we went wrong, and the rule that stops it happening again

Jack, 31 Oct 2026: "we need to have a mapped workflow and mark every place we went wrong and where ive made
corrections so they never happen again." Every entry: what went wrong, who caught it, the root cause, the rule
now in force, and where in WORKFLOW.md the rule is checked. New mistakes are added here the moment they are
found, before the fix. Test site: Jack's own front garden (Oct 2026).

| # | What went wrong | Caught by | Root cause | Rule now | Gate |
|---|---|---|---|---|---|
| 1 | First model was "a very bad representation": sizes, house, distances and bins all wrong | Jack | Built from a loose description and sizes estimated by eye | Nothing is modelled until a measured scale plan is signed off; never estimate a size | G2 |
| 2 | Path placed 0.8 m off | Me, on re-measure | Position read by eye from a zoomed crop | Positions come from solved cameras (sight-lines, triangulation, orthophoto), never from eyeballing a crop | G1 |
| 3 | Photo solve shrank the garden to 40 % (cameras 0.65 m off the ground) | Me | Free-scale shape fitting (ICP) | Scale is locked by known points seen in two photos; check camera heights 1.4–1.7 m and one known width | G1 |
| 4 | Lawn's front edge 1.1 m too far out | Me, from the walk video | Ground measured from one photo 6–9 m away (1° tilt = 0.7 m) | Ground edges come from the orthophoto of close frames and are cross-checked with 3D points | G1 |
| 5 | Plan curves drawn as kinked straight lines | Jack | Too few measured points | Edges are traced densely (a point every 8 cm) and smoothed | G1 |
| 6 | Bed end drawn as paving; side paving placed wrong | Me, on the orthophoto | Surface identified from an oblique photo | Every surface type is read from the true-colour orthophoto | G1 |
| 7 | Fence drawn parallel to the house at 7.2 m; it runs 5.9 → 7.2 m | Me | Assumed geometry | Boundaries are fitted to 3D points on their faces | G1 |
| 8 | Van and car modelled / van misplaced | Jack | Treated parked vehicles as the site | Vehicles are never built | G3 |
| 9 | West lawn cut short; paving to the shed missing | Jack (review notes) | Stopped where the data thinned out | Plan page with the review bar; every client note answered before modelling | G2 |
| 10 | "Hedge" was one upright shrub; the street hedge was missing | Me, on the matched views | Plan item marked rough and never checked | Every rough item is checked against matched real views before the build | G3 |
| 11 | Roofs and paths exported white | Me, in the viewer | Stale export copies of regenerated materials | Export rebuilds any material copy whose images changed | G6 |
| 12 | Hedge exported white | Me | Procedural material with no image | Every material must have an image or a flat colour that survives export | G6 |
| 13 | Viewer showed the demo's "tattoo studio" text on a real garden | Me | Site mode reused demo UI | Site mode shows the site's own name and hides demo controls | G7 |
| 14 | Viewer grey and washed out next to the real photos; sun from the wrong side | Judges + me | AgX tone mapping; a guessed sun | Neutral tone mapping for real sites; sun direction and height read from the client's own shadows | G5 |
| 15 | Jack's Mac crashed | Jack | A full light bake run on the 8 GB Mac | Bakes and renders only on RunPod, cost approved first; the Mac does light work only | G8 |
| 16 | First cloud run stuck 15 min with the GPU idle (money wasted) | Me | Slow Python light-map packer | Fast C packing (unwrap, average scale, pack); watch the remote log early | G8 |
| 17 | "Everything looks rubbish… nothing has any realism" | Jack | Generated textures and simple boxes; I treated the Airbnb as "lighting only" | Every surface comes from the client's own close-ups; every object is modelled to its real shape | G4, G5 |
| 18 | Mortar made dark grey; the real mortar is cream | Me, on Jack's close-up | Followed a judge's guess over the photo | The client's photos outrank judges and my assumptions; judges are checked against the photos | G4 |
| 19 | Bed shown as a purple lavender/allium block; the real bed is mixed | Judges, Jack's close-ups | Built from a plant list, not the photos | Planting is matched plant by plant to close-ups | G3 |
| 20 | Upstairs window went through the roof | Jack | Eaves built 0.3 m too low (4.6 m, real ~4.9 m) | House heights are measured from wall elevations (straight-on photos) before modelling | G1, G2 |
| 21 | Porch roof built with a hipped end; real is a lean-to with a verge | Jack (and judges earlier) | Roof form guessed from one oblique photo | Each roof's form is confirmed in two views (front and side elevation) | G3 |
| 22 | The arched mirror on the porch was modelled as a window | Jack | Read its shape, not what it is | The element inventory records what each thing IS, confirmed in a close-up | G3 |
| 23 | Party wall at −6.6 m (real ~−5.0); neighbour's house mirrored instead of observed; chimney missing | Me, on the wall elevation | Assumed a symmetrical semi | Neighbouring houses are modelled from what the photos show, never mirrored | G1, G3 |
| 24 | Kerbs were stretched bands with messy curves | Jack | Offset strip along a dense curve (spikes at corners) | Kerbs and edgings are built as their real units (block setts) laid along the curve | G5 |
| 25 | Windows clashed into the brickwork | Jack | Surrounds and heads placed by formula, not from the elevation | Window, surround, lintel and sill sizes come from the measured elevation | G2, G5 |
| 26 | Cloud rendering started before the model was right | Jack | Rushed to spend before checking | No cloud spend until the model passes the matched-view check and Jack signs off | G6 |
| 27 | Answered "lighting is the Airbnb secret" | Jack | Half-read the reference | Study every reference fully from the primary source; say back what it is before building | G0 |

## How to use this
- Before each stage of WORKFLOW.md, read the rows that point at its gate.
- When Jack (or a judge, or a check) finds a new mistake: add a row first, then fix it.
- A row is only closed when the rule is built into a tool or a gate check, not just remembered.

/* ------------------------------------------------------------------ *
 *  Role modes: one viewer, one set of data, four audiences.
 *  ?mode=customer | review | builder | inspector | architect   (default builder)
 *  review = Jack's studio review: exactly the homeowner walkthrough
 *  (as: "customer") plus the marking tool (src/marks.js) for fixes.
 *  A mode only decides what is shown and how you start; it never
 *  forks the code. Every flag is read where the UI is built.
 * ------------------------------------------------------------------ */

export const MODES = {
  customer: {
    label: "Homeowner",
    stageList: true,          // the 12 stages front and centre, plain-English notes
    stageText: "customer",    // customer_note (falls back to note)
    infoText: "plain",        // plain_label / room first; "Show builder's spec" one tap deeper
    section: false,           // no slice
    xray: "simple",           // offered as "See inside"
    hide: "simple",           // "Lift the roof", "Lift the first floor"
    measure: true,            // a simple tape stays
    edit: false, rules: false,
    temporary: true,          // props still show in the stages (they explain the steels)
    start: { stage: "last", walk: true, spawn: "Front door" },
    vr: { locomotion: "teleport", speed: 0.9, seatedOption: true },
    tabs: ["about", "build", "plans", "notes", "tools"],
  },
  /* Jack's studio review (1 Nov): the homeowner walkthrough unchanged (Before / After, walk, teleport, snap turn, fly,
     Height check, No doors, doors open) PLUS the marking tool: draw corrections / proposals on any surface, a note on
     each (voice or typed), saved to assets/sites/<site>/marks.json with the version and Before / After of each mark */
  review: {
    label: "Studio review",
    as: "customer",           // looks and behaves as the homeowner mode everywhere it is not about marking
    marks: true,
    stageList: true, stageText: "customer", infoText: "plain",
    section: false, xray: "simple", hide: "simple", measure: true,
    edit: false, rules: false, temporary: true,
    start: { stage: "last", walk: true, spawn: "Front door" },
    vr: { locomotion: "teleport", speed: 0.9, seatedOption: true },
    tabs: ["about", "build", "plans", "notes", "tools"],
  },
  builder: {
    label: "Builder",
    stageList: false, stageText: "builder", infoText: "spec",
    section: true, xray: "full", hide: "full", measure: true,
    edit: false, rules: true, temporary: true,              // live checks show on the Regs tab
    start: { stage: 1, walk: false, spawn: null },
    vr: { locomotion: "smooth", speed: 1.4, seatedOption: true },
    tabs: ["spec", "build", "regs", "plans", "notes", "tools"],
  },
  inspector: {
    label: "Building inspector",
    stageList: "inspection",  // stages grouped by building-control inspection point, each with its checklist
    stageText: "builder", infoText: "spec",
    section: true, xray: "full", hide: "full", measure: true,
    edit: false, rules: true, inspect: true, temporary: true,
    start: { stage: 3, walk: false, spawn: null },
    vr: { locomotion: "smooth", speed: 1.4, seatedOption: true },
    tabs: ["regs", "spec", "build", "plans", "notes", "tools"],
  },
  architect: {
    label: "Architect",
    stageList: false, stageText: "builder", infoText: "spec",
    section: true, xray: "full", hide: "full", measure: true,
    edit: true, rules: true, temporary: true,
    start: { stage: "last", walk: false, spawn: null },
    vr: { locomotion: "smooth", speed: 1.4, seatedOption: true },
    tabs: ["spec", "regs", "build", "plans", "notes", "tools"],
  },
};
export const TAB_LABEL = { about: "About", spec: "Spec", regs: "Regs", build: "Build", plans: "Plans", notes: "Notes", tools: "Tools" };

export function modeFromURL() {
  const m = new URLSearchParams(location.search).get("mode");
  const key = MODES[m] ? m : "builder";
  return { key, as: key, ...MODES[key] };
}

/* plain words for a part when its element has no plain_label */
export const PLAIN_GROUP = {
  foundation: "Concrete foundation", slab_layer: "Part of the ground floor", wall_outer: "Outer brick wall",
  wall_cavity: "Wall cavity", wall_insulation: "Wall insulation", wall_inner: "Inner wall", wall_lining: "Plastered wall",
  lintel: "Lintel (a beam over an opening)", steel: "Steel beam", timber_beam: "Timber beam", joist: "Floor joist",
  deck: "Floor boards", wall_plate: "Wall plate (the roof sits on this)", rafter: "Roof rafter", hip: "Hip rafter (roof corner)",
  valley: "Valley rafter", ridge: "Ridge (top of the roof)", ceiling_joist: "Ceiling joist", roof_layer: "Roof membrane",
  roof_cover: "Roof tiles", window: "Window", door: "Door", rooflight: "Rooflight", fitting: "Fitting", drain: "Drain",
  prop: "Temporary support", scaffold: "Scaffolding", spoil: "Dug-out soil", ground: "Ground",
};
export const PLAIN_CATEGORY = {
  existing: "Part of the house as it is now.", demolition: "This comes out during the works.",
  temporary: "Temporary — only there while the work is done.", new: "New work.", finish: "Finishing work.",
};

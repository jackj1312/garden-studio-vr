/* Keyboard and screen-reader accessible instructions, shared by the studio's editors. */
const pages = {
  planner: ["Room planner", [
    ["Choose a room", "Choose Before or After and the storey, then click or tap a room. Use Floor to return. Scroll or pinch to zoom. Drag empty space to pan."],
    ["Place furniture", "Use + Add and filter by room type, kind and style. Drag a piece on the plan. A red footprint cannot be dropped. Snap uses a 50 mm grid, walls and nearby furniture. Hold Shift or Alt to move freely."],
    ["Turn and edit", "Drag the rotation handle on screen or touch. Q/E or bracket keys turn 15°. R turns a quarter turn. Arrow keys move 50 mm, or 10 mm with Shift. D duplicates and Delete removes the selected piece."],
    ["Review changes", "Use Undo or Redo, or Ctrl/⌘ Z and Ctrl/⌘ Shift Z. Show 3D preview to inspect the actual furniture. Choose a wall face to repaint, or a covering for the room floor. Save layout shares these changes with the walkthrough. Changes and Send to build record architectural requests for the next build."],
  ]],
  site: ["Garden and site review", [
    ["Walk", "On this screen use W A S D or the arrow keys to move. Click the view for mouse look. Escape releases the pointer for the toolbar. The ? key opens these controls while walking."],
    ["Mark on screen", "M enters Mark mode. Drag on a surface to draw. K changes between a correction and a proposal, Z removes the last visible mark. Select a mark label to edit its note."],
    ["Mark in Quest", "In the surveyed garden, B toggles Mark. Point the right controller at a surface and hold the trigger to draw. A changes kind, the right grip undoes, and holding A with a note open records speech."],
    ["Reference photos", "R opens or closes the site reference view on screen. In Quest, point at a reference picture and pull the trigger to enlarge it."],
    ["Design the garden", "Open Garden design for measured shapes, materials, levels and planting. It has its own How to use panel on screen and on the left wrist."],
  ]],
  house: ["House walkthrough and editing", [
    ["Walk and inspect", "Choose a location with Go to. In Walk, use W A S D and move the mouse to look. Escape frees the pointer. Phones use the on-screen controls. In orbit view, drag to orbit and scroll or pinch to zoom."],
    ["Room lighting", "While walking, aim at a lamp and press E to switch it. With no lamp in view, E switches the lamps in your room. L switches lamps throughout the house. On a phone, open Tools and choose Room lamps or All lamps. The room name appears briefly when you cross its doorway."],
    ["Inspect the building", "Choose a stage and select a part to read its details. In Architect mode the selected element’s board contains its editable dimensions. Undo and Redo step through changes. Save edits keeps the current revision."],
    ["Doors and views", "Select an operable door to use it. In the homeowner controls choose Before or After and Furnished or Unfurnished. In Quest, the left stick walks, the right stick turns, and pushing the right stick forward and releasing teleports."],
    ["Review marks", "In Studio review, click Mark or press M. Draw on a surface with the mouse or right trigger. In Quest, X changes mark kind and Y undoes. Select its label to edit a note."],
  ]],
  furnish: ["Furnish a room", [
    ["Choose a piece", "Choose a room. Filter the catalogue by room type, kind or style and click a thumbnail. Point at the floor, wall, ceiling or compatible supporting piece. Place with a click or tap."],
    ["Move and turn", "Select and drag a piece. A green outline can be placed. A red outline shows why the position is blocked and releasing keeps the original placement. Use Q/E, the two rotation buttons, or twist with two fingers. Hold Shift or Alt to bypass snapping."],
    ["Change a finish", "Choose one measured wall face and a colour. Choose a floor covering for the current room. Original wall colour or Original covering restores its signed finish."],
    ["Walking and overhead", "Bird’s-eye shows this room from directly above. Switch to Walking or select another room to inspect the same layout. Copy, Delete, Undo and Redo act on the selected version. Save layout to share it with the planner and other devices."],
    ["Quest", "Choose tools and thumbnails on the left wrist. Point the right ray and hold the trigger to move furniture, then release to place it. Push the right stick sideways to turn a selected piece. Bird’s-eye brings the measured room plan into reach."],
  ]],
  garden: ["Garden design", [
    ["Draw in metres", "Pick a feature and a drawing method. Drag from the centre for a circle or square, or between opposite corners for a rectangle. Sweep an outline for a smooth curve. Complete the loop to fill an area."],
    ["Adjust the drawing", "Choose Select. Drag the feature to move it, or drag a point, tangent or edge handle. Use the size and angle fields for exact dimensions. Copy, delete, undo and redo act on the current design."],
    ["Levels and planting", "A positive level raises a shape and a negative level sinks it. Add steps to connect the two levels. Choose a material, paving pattern or bed palette. Place each tree or plant with its own click."],
    ["iPad and Apple Pencil", "Use Apple Pencil to draw, select and drag handles. After the first Pencil stroke, a finger pans the plan; two fingers pinch to zoom. Without a Pencil, one finger draws and two fingers navigate."],
    ["Outbuilding base", "Choose Outbuilding base, click each corner and finish, or choose a circle, rectangle or smooth outline. Read edge or curved lengths, area and perimeter in metres. Set slab thickness and top level. Save, then Copy base reference for a later design session."],
    ["Plan and walkthrough", "Bird’s-eye looks straight down on the plot. Standing returns to the house and garden. Save writes the design for this house version. Open the same site and version on your other device."],
    ["Quest", "Aim the right ray at the left wrist to choose a tool. Hold the right trigger and sweep, or drag out a perfect shape. In Select, grab a point or the shape. Push the right stick up or down to change the selected level. The wrist switches between Bird’s-eye and Standing."],
  ]],
  scan: ["Room scan", [
    ["Choose and scan a room", "Pick the room and start the scan. Press B in the headset for room setup. Look around the walls, floor and ceiling."],
    ["Save and finish", "Check the coloured outlines, then pull the right trigger to save. Wait for Saved. Press Y or the Meta button to finish."],
  ]],
};
export const helpPage = key => pages[key] || pages.house;
export function showEditorHelp(key, button = document.activeElement) {
  let box = document.querySelector("#studio-help-dialog");
  if (!box) {
    box = document.createElement("dialog"); box.id = "studio-help-dialog";
    box.setAttribute("aria-labelledby", "studio-help-title");
    box.addEventListener("click", e => { if (e.target === box) box.close(); });
    document.body.append(box);
  }
  const [title, rows] = helpPage(key);
  const article = document.createElement("article");
  const head = document.createElement("header"), name = document.createElement("h2"), close = document.createElement("button");
  name.id = "studio-help-title"; name.textContent = "How to use · " + title;
  close.textContent = "Close"; close.type = "button"; close.onclick = () => box.close(); head.append(name, close); article.append(head);
  for (const [label, detail] of rows) { const h = document.createElement("h3"), p = document.createElement("p"); h.textContent = label; p.textContent = detail; article.append(h, p); }
  box.replaceChildren(article); if (document.pointerLockElement) document.exitPointerLock();
  box.onclose = () => button?.focus?.({preventScroll:true});
  if (!box.open) box.showModal(); close.focus();
}
document.addEventListener("click", e => { const b = e.target.closest?.("[data-editor-help]"); if (b) showEditorHelp(b.dataset.editorHelp, b); });
window.addEventListener("keydown", e => { const box = document.querySelector("#studio-help-dialog[open]");
  if (!box) {
    if(e.key==='?' && !e.target.closest?.('input,textarea,select,[contenteditable]')){
      const trigger=[...document.querySelectorAll('[data-editor-help]')].find(b=>b.offsetWidth&&b.offsetHeight);
      if(trigger){e.preventDefault();e.stopImmediatePropagation();showEditorHelp(trigger.dataset.editorHelp,trigger);}
    }
    return;
  }
  if (e.key === "Escape") { e.preventDefault(); box.close(); }
  if (e.key !== "Tab" && e.key !== "Enter" && e.key !== " ") e.stopImmediatePropagation();
}, true);


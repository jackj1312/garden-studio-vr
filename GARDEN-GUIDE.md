# Garden design

Open [Garden design on this Mac](https://127.0.0.1:8450/garden/) or [Garden design on the studio Wi-Fi](https://192.168.1.118:8450/garden/). **Garden design** in the original surveyed garden and the house walkthrough opens the same editor. The client room planner remains at [/plan/](https://127.0.0.1:8450/plan/).

If port 8450 is down, double-click `tools/start_garden.command` in Garden Studio VR. Keep its window open. It prints the current Wi-Fi address for iPad and Quest. On the Quest, open that address in Meta Quest Browser and press **Enter VR** in the garden tools.

### Draw and edit

1. Open **How to use** at the top of the tool panel. Choose **Bird’s-eye** to see the entire surveyed property. Choose an object type and drawing method.
2. For a circle or square, drag from the centre. For a rectangle, drag between opposite corners. Sweep a curve, returning to the starting point for a closed patio or bed. With **Corner points**, click each corner and press **Finish shape**. **Straight runs** draws between the two chosen ends.
3. Choose **Select**. Drag the body to move it, a corner or radius handle to resize, and the control points or tangent handles to reshape a curve. Type the radius, dimensions, centre coordinates or angle when a measurement matters. The selected object's fields also change its material, pattern and planting palette.
4. Set **Level** in metres. Negative values excavate. Positive values raise the surface. **Add steps** on screen or **Fit steps** on the wrist adds a flight to a levelled area. Adjust its position around the perimeter, width and count. Raised beds and walls can have coping. Each plant or tree is its own selectable object and can be moved, copied and removed independently.
5. **Minimise** takes you to standing height and gives the mouse to the walkthrough. Move the mouse to turn and use **WASD** or the arrow keys to walk. **Esc** releases the pointer. Click the garden to lock it again. **Tab** or **Show tools** returns to your previous drawing view.
6. **Standing** returns to the garden and house. Right-drag to look while designing. The ordinary house walk controls still work. **Save garden** writes this site and house version. Undo and redo are available for individual drawing and editing actions.

### An outbuilding base

Choose **Outbuilding base**. Click corners to make any simple closed footprint, or choose a circle, rectangle or smooth curve. The readout follows the drawing and shows the selected side or curve lengths, width, depth, area and perimeter. A circle also shows its diameter. The footprint becomes concrete when you finish it. The starting slab thickness is 150 mm and its top is 100 mm above the local ground. Both are editable in metres.

**Save garden**, then **Copy base reference**. That gives our next design session the base ID, versioned file path, exact contour and slab levels. The building above it can be designed together later.

### iPad and phone

Apple Pencil uses the same geometry and handles as the mouse. After drawing with the Pencil, one finger pans the plan. Two fingers pan and pinch to zoom. Finger contact during a Pencil stroke leaves the Pencil in control. Without a Pencil, a single finger draws and two fingers navigate. Minimise the dock for more drawing space.

### Quest

Raise the **left wrist** and aim the **right ray** at a button. The wrist contains **How to use**, tools, features, materials, numeric fields, level, steps, undo/redo and save. In standing view, point at the ground and hold the right trigger to draw. In Bird’s-eye, aim at the measured plan in front of you. Trigger-drag a radius or corner for a perfect shape. Use **Select** to grab an existing handle. Push the right stick up or down to change the selected level in 50 mm increments. Lower the wrist to see the plan clearly. The left stick still walks in standing view.

### Saved designs

The file is `assets/sites/<site>/layout/<version>.json`. For the approved Battle Road design it is `assets/sites/house-wip/layout/approved_2b.json`. The garden section stores each object's real geometry in metres. The previous copy and revision receipts sit beside the file. A conflicting save keeps the local draft on screen. Reopen the same site and version to continue on another device. The example pictures are from a separate test layout.

### Device checks

The mouse, mobile touch, simulated Pencil and simulated Quest controller all created and reopened test designs on port 8450. A measured 4 × 3 m concave slab had 10 m² of concrete footprint and 14 m of perimeter. The same standing camera in simulated Quest mode submitted 607 draw calls and 1,537,108 triangles with full interior detail, and 135 calls and 535,638 triangles with the garden detail setting. Median frame intervals were 16.7 ms for both in desktop Chrome. Physical iPad and Quest performance has not been measured.

![Measured plan and drawing tools](docs/pipeline/img/26-garden-plan.jpg)

![A 600 mm sunken area with steps on the existing garden](docs/pipeline/img/27-garden-steps.jpg)

![A concave outbuilding footprint with its measured edges](docs/pipeline/img/29-outbuilding-base.jpg)

![The garden drawing tools on the simulated left wrist](docs/pipeline/img/28-garden-wrist.jpg)


![Garden tools minimised with the walkthrough active](renders/garden-tool/garden-walk-mac.jpg)

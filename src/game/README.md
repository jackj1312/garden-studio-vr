# House Blaster (`game.html`, `src/game/`)

A foam-dart target game set inside 23 Battle Road, for the Quest 3 (and playable on a laptop). A personal side
project, **not** part of the studio pipeline: it only reads the house and changes nothing.

## Play

**Quest:** open **https://192.168.1.131:8443/game.html** in the Quest browser (served by `tools/https-serve.py`;
Advanced → Proceed if warned), wait for the house, press **Play in VR**, aim at **START** and pull the trigger.

| Headset | |
|---|---|
| Trigger | fire (hold to keep firing); press menu buttons |
| Left stick | walk |
| Right stick ← → | snap turn 30° (fine sitting down) |
| Right stick forward, let go | aim a jump (green arc), jump there |
| B / Y | pause menu |

**Screen:** click to fire (the mouse then looks around), WASD to walk, arrows / Q E to turn, Esc to pause.

## The game

- 60-second rounds. Balloons (10), spinning discs (15), robots peeking round door frames or springing up on the
  sofa, worktops and beds (25), and a gold star that zips across the room (50 and **+3 seconds**).
- Hits within 3 s build a combo: x2 at 3, x3 at 5, x4 at 8, x5 at 12. Targets come faster as the round goes on, and
  each "Next room" adds a little speed.
- Rooms: Hall, Living room, Kitchen, Upstairs, Front garden, Whole house.
- **🧸 Toy mode:** you shrink to about 20 cm tall. The sofa towers over you, you can walk under the tables, the stairs
  are cliffs (use the jump to hop up), and the targets shrink to toys your size.
- **Two players:** tick "take turns" (or "2 players" on the headset menu). Player 1 plays, passes the headset,
  Player 2 plays, the results say who won.
- High scores per room are kept on the device (localStorage). Settings: speed (Easy / Normal / Hard), aim help,
  blaster hand, height ±5 cm, seated (+45 cm), sound.

## How it's built

- `house.js` loads `assets/sites/house-preview/` (`versions.json` → as built now, falling back to the approved
  scheme), shows it as built, swings the doors open, and merges it to one mesh per material (~64 draw calls).
- `props.js` adds chunky toy furniture (the model has none) inside the room outlines, clear of the door swings.
- Collision and floors use the viewer's own `src/house/bvh.js` and `walk.js`, imported unchanged. Toy mode runs the
  same walker inside a world scaled up 1/0.13 (a thin wrapper round the BVH), so a toy-sized body falls out of the
  same code.
- `spots.js` finds where targets may appear by dropping rays from the ceiling onto real surfaces (floors, the sofa,
  worktops, stair treads, sills), checking clearance, plus doorways and windows from the elements file. Every target
  is checked for line of sight from your head when it appears; robots peek from the far side of a doorway.
- Sounds are made live with WebAudio (`audio.js`); no files to download.

Tests: `game.html?xrsim=1` is a simulated headset on the desktop (fake controllers drive the VR code;
`__game.sim` in the console). Also `?toy=1`, `?room=kitchen`, `?nolock=1` (no pointer lock), `?autostart=1`.
Screenshots: `renders/game/`.

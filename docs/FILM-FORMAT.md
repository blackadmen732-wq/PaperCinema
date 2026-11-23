# Film file format (`film/<name>.json`): complete reference

One JSON file describes a whole film. `npm run validate` checks every rule below and explains mistakes.
Use `film/ganryujima.json` as the working example.

```json
{
  "title": "…", "fps": 24, "width": 1280, "height": 720, "letterbox": 2.39, "duration": 36,
  "shots":        [ … ],   // camera: docs/CAMERA.md
  "shakes":       [ … ],   // camera shake on hits
  "events":       { … },   // named story moments (seconds)
  "performances": { … },   // character motion: docs/ANIMATION.md
  "titles":       [ … ],   // on-screen text
  "sounds":       [ … ]    // sound cues: find → check → place
}
```

| Section | Item fields | Rules |
|---|---|---|
| top level | `fps` (24), `width`, `height` (1280×720 or 1920×1080), `letterbox` (2.39 = cinema bars), `duration` (s) | all positive numbers |
| `shots[]` | `id`, `name`, `mode` (`dawn` / `studio`), `start`, `end`, `ease` (`inOut` / `linear`), `camera[]` | shots touch end to end; ≥ 2 camera keys inside the shot, in time order |
| `shots[].camera[]` | `t`, `pos` [x,y,z], `look` [x,y,z], `fov` (10–90) | metres, y up, ground 0 |
| `shakes[]` | `t`, `dur`, `amp` (0.005 subtle … 0.015 strong … 0.03 huge), `note` | |
| `events` | `studio-blade-draw`, `boat-arrives`, `kojiro-draw`, `kojiro-throws-scabbard`, `scabbard-splash`, `headband-cut`, `impact` | seconds; the engine times props and effects from these |
| `performances.<id>` | `character`, `keys[]`, `twoHand[]`, `walk[]`, `rideBoatUntil`, `boatPose` | keys strictly increasing; poses must exist in `library/poses.json` |
| `titles[]` | `start`, `end`, `style` (`hero` / `left` / `bottom`), `jp`, `en`, `sub` | fades 0.5 s in and out |
| `sounds[]` | `id`, `t`, `query`, `min`, `max` (ms length window), `len` (s used), `gain` (0–2), `bed` (true = loop) | unique ids; stays inside the film |

## Golden path for a new film

```bash
cp film/ganryujima.json film/my-film.json      # start from the working example
# edit shots, performances, titles, sounds
node engine/validate.mjs film/my-film.json     # fix every ✗
node engine/render.mjs --film film/my-film.json --still auto   # look at output/stills/
node engine/make.mjs film/my-film.json         # full pipeline: render → sound → playbook
```

**Today's limit:** the world (island, sea, studio) and the props' special effects (boat, thrown scabbard,
headband) are built in `engine/world.js` and `engine/main.js` for Ganryūjima. A film in a new location
needs a new set builder there; the camera, motion, titles and sound already come from the file.

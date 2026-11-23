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
  "duels":        [ … ],   // reaction layer: who watches and reacts to whom, when
  "titles":       [ … ],   // on-screen text
  "sounds":       [ … ]    // sound cues: find → check → place
}
```

| Section | Item fields | Rules |
|---|---|---|
| top level | `format` (`vertical` = 9:16 Shorts/TikTok/Reels, the default for new films; `horizontal` = 16:9), `fps` (24), `width`, `height` (1280×720 or 1920×1080), `letterbox` (2.39 = cinema bars), `duration` (s) | all positive numbers |
| `shots[]` | `id`, `name`, `mode` (`dawn` / `studio`), `start`, `end`, `ease` (`inOut` / `linear`), `camera[]` | shots touch end to end; ≥ 2 camera keys inside the shot, in time order |
| `shots[].rig` | KUROKO automatic camera (instead of `camera`): `type`, `subjects`, `feel`, `behaviours`, … | see `docs/CAMERA.md` section 7 |
| `shots[].camera[]` | `t`, `pos` [x,y,z], `look` [x,y,z], `fov` (10–90) | metres, y up, ground 0 |
| `shakes[]` | `t`, `dur`, `amp` (0.005 subtle … 0.015 strong … 0.03 huge), `note` | |
| `events` | (negative = happened before the film starts, e.g. `kojiro-draw: -3` means the sword is already drawn) `studio-blade-draw`, `boat-arrives`, `kojiro-draw`, `kojiro-throws-scabbard`, `scabbard-splash`, `headband-cut`, `impact` | seconds; the engine times props and effects from these |
| `performances.<id>` | `character`, `keys[]` (`{t, pose}` or `{t, move, speed, dist}`), `twoHand[]`, `walk[]`, `rideBoatUntil`, `boatPose` | keys strictly increasing; poses must exist in `library/poses.json` |
| `duels[]` | `a`, `b` (performance ids), `from`, `to`, `note` | head tracking + threat response between a and b |
| `titles[]` | `start`, `end`, `style` (`hero` / `left` / `bottom` / `endcard`), `jp`, `en`, `sub` | fades 0.5 s in and out |
| `sounds[]` | `id`, `t`, `query`, `min`, `max` (ms length window), `len` (s used), `gain` (0–2), `bed` (true = loop), `body` (true = timed to the action: moves later with the hit-stops) | unique ids; stays inside the film |
| `motion` | `{ "overlap": true }` = anime layer (lag, snap, settle) | docs/ANIMATION.md §10 |
| `cast.<id>` | `face` (`"eyes"` = glowing eye slits with lids), `eyes` (colour), `weapon` (`bokken` / `katana`, Musashi in `main.js`) | ids are performers |
| `performances.<id>` | `eyes` [[t, glow], …] (idle 0.9 · focus 1.4 · anticipation 2.2 · decide 3.5 · struck 0.4), `blinks` [s, …] | body time; without `eyes`, states come from the contacts |
| `clashes[]` | `t`, `until`, `attacker`, `defender`, `s` (where on the attacker's blade), `ramp`, `maxDeg` | the defender's blade is turned to meet the cut; contacts are then detected (engine/combat.js) |
| `effects` | `hitStop` {min, max} frames or false, `ribbon` {minSpeed, frames}, `impactFrame` (true / false / {minIntensity, max, at: [body s]}), `contactMinSpeed` (m/s), `contactGap` (s), `sparkLight` | `combat: false` turns the whole combat layer off |
| `autoSounds` | `whoosh` {sfx[], on, rearm, maxPerSec}, `clash` {sfx, light, wood {sfx, rate, light}}, `scrape` {sfx} | without it `main.js` writes no automatic cues |
| `fxBase`, `fx[]` | post FX base look and timed events (`docs/EFFECTS-CATALOG.md`); `fx[].body: true` = timed to the action | no `fxBase`/`fx` = no post stack (as before) |

**Time in `main.js`:** a blade contact inserts a hit-stop (3–4 frames). Shots, rigs, performances, `shakes`,
`events` and `clashes` are in *body time* (the action), so they all move later together; titles and fades stay on
the film clock. Check `output/<film>.events.json` (`stops`) for the shifts.

## Golden path for a new film

```bash
node engine/new-film.mjs my-film --jp 一騎打ち --en "ICHIKI-UCHI" --sub "…" --next "Next: …"   # signature opening + fight body + end card
# edit shots, performances, titles, sounds
node engine/validate.mjs film/my-film.json     # fix every ✗
node engine/render.mjs --film film/my-film.json --still auto   # look at output/stills/
node engine/make.mjs film/my-film.json         # full pipeline: render → sound → playbook
```

**Today's limit:** the world (island, sea, studio) and the props' special effects (boat, thrown scabbard,
headband) are built in `engine/world.js` and `engine/main.js` for Ganryūjima. A film in a new location
needs a new set builder there; the camera, motion, titles and sound already come from the file.

## Motion-page extras (films with `"page": "engine/motion.html"`)
| Field | What |
|---|---|
| `cameraOpts.solver: 2`, `camera[]` beats with `rig: "compose"`, `cut`, `act` | the cinematographer camera (`CAMERA.md` §8) |
| `ramps: [{ t, rate, in, hold, out }]` | speed ramps; `t` in action time, the rest in screen seconds (`STUDIO-STANDARD.md` §4) |
| `fade: { in, out }` | fade from / to black in seconds (default 0.6 / 0.6; a Short uses `in: 0`) |
| `light: { sun, hemi, fill, ground }` | multiplies the dawn lights, sets the shadow tint (`STUDIO-STANDARD.md` §8) |
| `props.trees[]` `{ id, x, z, height, crown, color, cut { t, y, tilt, delay, dir, fall }, split { t, world, side, speed, up } }` | a tree that can be cut and split (times in action time) |
| `impacts[]` `{ t, at, intensity, light, shards, colors, life, ring, ink, sparks, fx }` | hits that are not blade-on-blade (action time) |
| `effects` `ribbon`, `afterimage`, `ground`, `contactShadow`, `speedLines`, `glints`, `contactFx`, `sparkLight`, `inkProps` | `EFFECTS-CATALOG.md`, last section |
| `sounds[].body: true`, `sounds[].layer` | the cue follows hit-stops and speed ramps; `layer` names the cue it belongs to (same hit) |
| `audit.waive: [{ check, from, to, why }]` | a deliberate exception for the studio audit (`AUDIT.md`) |

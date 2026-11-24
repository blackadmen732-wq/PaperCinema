# TIMELINE: the one canonical animation timeline

`output/<film>.timeline.json` is the **single interchange format** between the preview engine and every renderer
(three.js preview, Blender, and whatever comes next: Unreal, a GPU farm, a critic tool). It is written by
`tools/timeline.mjs` from what the engine really did — nothing is re-implemented, so no renderer can drift from the
preview.

```bash
node tools/timeline.mjs film/<name>.json           # → output/<name>.timeline.json
node tools/timeline.mjs --all                      # every film in film/
node tools/timeline.mjs film/<name>.json --sub 8 --pretty --step 2
```

**Who reads it:** `blender/film_blender.py` (`--timeline`, the default), `tools/camera_check.mjs`,
`tools/paper_damage.mjs`, `tools/render_supervisor.mjs`. **Who writes it:** `tools/timeline.mjs` only.

---

## 1. Why one format
Before this, each renderer asked the engine its own question (`tools/export_motion.mjs` for Blender, `window.AUDIT`
for the audit, `engine/resolve-camera.mjs` for the playbook). Three readers meant three chances to drift and three
coordinate conversions. One timeline means: export once, render anywhere, and a camera/quality tool can judge a film
without opening a browser.

The hard requirements (from the owner's research plan) and where each one lives:

| Requirement | Where it is met |
|---|---|
| Precise coordinate conversion | `coords` (§3): one conversion, written down once, used by every reader |
| A consistent 24 fps clock | `clock` (§4): frame = film time; `tb` is the body clock, `rate` the ramp rate |
| Root-motion preservation | `bones.order[0] === "root"`, world-space transforms (§5) |
| Matching bone mappings | `bones.order` + `bones.standard` (ours ↔ Mixamo-style humanoid) |
| Correct behaviour scrubbed backward | `scrub` (§9): frames are re-sampled in reverse and compared |

---

## 2. Top level

| Key | What |
|---|---|
| `format`, `version` | `"paper-cinema-timeline"`, `1` |
| `generated` | tool, time, page and engine kind (`motion` / `main` / `simple`) |
| `film` | name, title, source path, page, `fps`, `duration`, `frames`, `format` (vertical/horizontal), `width`, `height`, `letterbox` |
| `clock` | §4 |
| `coords` | §3 |
| `scrub` | §9 |
| `actors` | §5 (who is in the film, their weapon, how their animation is carried) |
| `bones` | bone order, standard names, space, root index |
| `shots` | §6 |
| `cuts` | frame numbers where a new shot starts |
| `lights` | §7 |
| `effects` | film `effects`, `fxBase`, `fx`, speed `ramps`, the film↔body `warp` table, `autoSounds` |
| `assets` | §8 |
| `events` | §10 |
| `frames` | §5: one row per film frame |
| `subframes` | weapon transforms between frames (`clock.sub` per frame) for motion blur, slash trails and contact tests |

## 3. Coordinates (the only conversion in the project)
The engine is **three.js: +y up, right-handed, metres, the figure faces +z**. Rotations are quaternions
`[x, y, z, w]`. A transform is always 7 numbers: `[px, py, pz, qx, qy, qz, qw]`, in **world space**.

Blender is Z-up. The conversion, and the only one anyone may use:

```
position    (x, y, z)     ->  (x, -z, y)
quaternion  (x, y, z, w)  ->  (w, x, -z, y)          # Blender quaternions are (w, x, y, z)
basis       [[1,0,0],[0,0,-1],[0,1,0]]               # three.js vector -> Blender vector
```

It is carried in `timeline.coords.toBlender` so a reader never has to guess, and it is implemented once in
`blender/character/rig_trellis.py` (`v3()`, `q3()`, `C3`). Unreal (Z-up, left-handed, centimetres) takes the Blender
vector and then negates Y and scales by 100 — write that conversion **here** when it is first needed, not in a tool.

Angles are degrees. `camera.fov` is the **vertical** field of view (three.js convention). One film back for the whole
project: full frame, 36 × 24 mm, fit vertical, so

```
focal_mm = (24 / 2) / tan(fov / 2)
```

`focal_mm` is written on every frame beside `fov`, so a renderer with a physical camera needs no trigonometry.
`focus_m` is the distance from the lens to the nearest visible actor's chest; `aperture` is an f-stop (default 2.8).

## 4. The clock
* **Film time** is the clock of the viewer, the camera, the sound and the post FX. Frame `f` is film time `f / fps`,
  `fps` is 24 everywhere. `frames[]` has one row per film frame, in order, `f` from 0.
* **Body time** (`frames[].tb`) is the clock of the pose keys: film time with the hit-stops and the speed ramps taken
  out. A renderer that replays bone transforms never needs it; a renderer that re-evaluates the keys does.
* `frames[].rate` is the speed-ramp rate of the frame (1 = real time). `effects.warp` holds the film↔body table when
  the film has ramps or hit-stops.
* **Sub-frames:** `subframes[]` holds the weapon transform `clock.sub` times per frame (default 4, i.e. 96 Hz) for
  motion blur, the swept slash and sub-frame blade trajectory checks.

## 5. Actors, bones and root motion
`actors[]`: `{ id, character, demonic, hidden, rootMotion, weapon: { kind, bladeLen, handle, grip, leftGrip, frame }, animation }`.
`animation.source` is `"sampled"` (per-frame transforms in this file) or, when a renderer stores clips itself, a
reference `{ source: "clip", clip, start }` — readers must handle both.

`bones.order` is the fixed bone order (23 bones, the `engine/figure.js` rig); `bones.standard` maps each to the
standard humanoid name (`hips → Hips`, `shoulder.L → LeftArm`, …) so a retarget tool or a game engine can read it
without a table of its own.

Per frame, per actor:

```json
{ "hidden": false, "root": [7], "ry": 0.41, "bones": [[7], …], "weapon": [7], "eyes": 1.2, "pose": { "rsx": 0.2, … } }
```

* `bones[0]` is `root`: the **root motion** (travel and turn) lives there and nowhere else.
* Every bone is in **world space**, so root motion is never applied twice. A renderer that wants local transforms
  multiplies by the inverse of the parent's transform (the parent order is `bones.order`, depth-first).
* `pose` is the engine's pose channels for that frame (handy for debugging and for re-driving a different rig).
* `weapon` is the sword/bokken transform: blade along **+x** from the guard (x = 0), edge toward −y, handle along −x.

## 6. Shots
`shots[]`: `{ id, name, start, end, f0, f1, mode, camera, cutIn }`.
`camera.kind` is `"rig"` (a KUROKO rig: the rig object follows, e.g. `type: "orbit"`), `"keyframes"`
(`{ ease, keys: [{ t, pos, look, fov }] }`) or `"beat"` (a motion-page camera beat). `cutIn: true` means the shot
starts on a hard cut; `cuts[]` is the same information as frame numbers. The camera **transforms** are already baked
per frame in `frames[].camera` — `shots[].camera` is the *intent*, which is what `tools/camera_check.mjs` scores.

## 7. Lights
`lights` = `{ preset, perShot: [{ shot, preset }], overrides, note }`. The preset name (`dawn`, `studio`, a set's
lighting preset) is resolved by the renderer (`engine/world.js setMode/setLight`, `blender/sets/`), so the timeline
stays small and a look change does not invalidate every timeline. `overrides` is the film's `light` block verbatim.

## 8. Assets
`assets[]`: `{ role, id, path }` for every file a renderer needs: `character`, `poses`, `moves`, `prop`, `sfx`,
`voice`, `set`, `model`. Paths are repo-relative.

## 9. Scrubbing backward
A timeline must be the same whether the viewer plays forward or drags backwards, which is only true if every page
function is a pure function of time. The exporter checks it: after the forward pass it re-samples seven frames **in
reverse order** and compares the camera and every bone.

```json
"scrub": { "checked": true, "frames": [0, 31, 63, …], "maxCameraDrift": 0, "maxBoneDrift": 0, "stable": true }
```

`stable: false` (drift above 1 mm) means some page state leaks between frames: fix the engine, do not render.
`--no-scrub` skips the check (CI speed only).

## 10. Events (stable ids)
`events[]`, sorted by time, each `{ id, type, t, f, … }`. The **id** is `"<type>.<NN>"` numbered within the type in
time order (`blade-contact.00`, `blade-contact.01`, `paper-cut.00`), so a sound cue, a camera note, a damage event
and a critic finding can all point at the same moment and keep pointing at it after a re-export.

| `type` | Fields | Source |
|---|---|---|
| `attack-start` | `actor`, `peak`, `speed` (m/s) | derived: the weapon tip crosses 9 m/s (same test as the whoosh cue) |
| `blade-contact` | `tb`, `point`, `intensity`, `speed`, `verified` | `engine/combat.js` contact detection at 240 Hz |
| `hit-stop` | `tb`, `duration` | `engine/combat.js` |
| `paper-cut` | `target`, `part`, `height`, `tilt`, `dir` | film `props.trees[].cut/split`, `impacts[].at`, `events.*-cut` |
| `footstep` | `actor`, `side`, `point`, `speed` | ground events, or derived from the foot bones |
| `ground` | `kind` (dash/skid/wake), `actor` | `engine/groundfx.js` |
| `impact` | `intensity`, `point`, `ink` | authored `film.impacts` |
| `cue` | `sfx`, `gain`, `len`, `rate`, `why`, `source` | `window.EVENTS.cues` + authored `film.sounds` |
| `voice` | `actor`, `line` | `film.voice` |
| `title` | `until`, `style`, `text` | `film.titles` |
| `beat` | `name` | named story times in `film.events` (a negative time means the beat is off in that film) |

**One verified event drives everything.** A blade contact is found once, in the engine; the timeline carries it; the
sound cue, the camera punch, the damage bridge and the critic all read the same `blade-contact.NN`. Nobody re-detects
a hit.

## 11. Coverage
| Film kind | Example | What is exported |
|---|---|---|
| Motion page (camera beats) | `dash-test`, `motion-test`, `voice-test`, `moves-gallery`, `mocap-*` | everything |
| Main engine (shot list + KUROKO rigs) | `ganryujima`, `kuroko-duel` | everything |
| Gallery pages with no cast | `lineup`, `lookdev`, `fx-demo` | camera, shots, events, assets (no actors) |

The exporter adds **one line** to the copy of the engine module the browser receives (`window.PCX ??= …`), so the
files on disk are untouched and the pages render exactly as before. A new page needs one entry in `HOOK` in
`tools/timeline.mjs` (or it publishes `window.PCX` itself and needs nothing).

## 12. Changing the format
Add fields; do not rename or re-order existing ones. `bones.order` is frozen (a change invalidates every cached
render): a new bone goes at the end. Bump `version` only for a breaking change, and then update, in one commit:
`tools/timeline.mjs`, this file, `blender/film_blender.py`, `tools/camera_check.mjs`, `tools/paper_damage.mjs`,
`tools/render_supervisor.mjs`.

# Camera guide: how the camera is controlled

**The camera is data, not AI guesswork.** Every camera move is written as numbers in a film file
(`film/<name>.json`). The engine (`engine/main.js → placeCamera`) reads those numbers and moves
the camera the same way every time. Any person or AI that can edit JSON can direct the camera.

---

## 1. Coordinates (the "stage")

- Units are **metres**. **y is up.** The ground (beach) is at `y = 0`.
- Eye height of a standing person ≈ `1.5`. Chest ≈ `1.2`. Knee ≈ `0.5`.
- Ganryūjima set: island centre about `(0, 0, -4.5)`, sea toward `+z`, sunrise toward `-z`.
  - Kojirō stands at `(0, 0, -0.8)` facing `+z`. Musashi ends at `(0, 0, 0.85)` facing `-z`.
  - The fighters' line runs along the **z axis**. Keep the camera on one side (`x > 0` or `x < 0`) to respect the 180° rule.
- Sword "studio" set (dark, glowing paper backdrop) is far away at `x = 200`.

## 2. A shot

```json
{
  "id": "S5", "name": "One strike", "mode": "dawn",
  "start": 24, "end": 29.5, "ease": "linear",
  "camera": [
    { "t": 24.0, "pos": [-3.2, 1.05, 0.5], "look": [0, 1.25, 0.3], "fov": 36 },
    { "t": 25.7, "pos": [-1.7, 1.2,  0.4], "look": [0, 1.45, 0.1], "fov": 28 },
    { "t": 29.5, "pos": [-2.6, 2.7,  3.8], "look": [0, 0.7,  0  ], "fov": 36 }
  ]
}
```

| Field | Meaning |
|---|---|
| `start`, `end` | Seconds in the film. A new shot = a **cut**. |
| `mode` | `dawn` (island world) or `studio` (dark sword set, with fade-through-black around it) |
| `ease` | `inOut`: starts slow, moves, ends slow (smooth, cinematic). `linear`: constant speed (good when keys must hit exact moments, like an impact). |
| `camera[].t` | Time of this keyframe (seconds) |
| `camera[].pos` | Where the camera **is** `[x, y, z]` |
| `camera[].look` | The point the camera **looks at** `[x, y, z]` |
| `camera[].fov` | Lens. Smaller = more zoomed in (see the lens table) |

**How the engine moves between keyframes:** it draws a **smooth curve (Catmull-Rom spline)** through all
`pos` points and another through all `look` points, so 3+ keyframes give a flowing curve rather than straight
lines with corners. The `fov` blends between keyframes. The shot's `ease` controls speed along the curve.

### Lens table (`fov`, vertical degrees)
| fov | Feels like | Use for |
|---|---|---|
| 24–28 | Telephoto | Faces, sword hilts, the moment of impact |
| 30–36 | Normal | Most fight coverage |
| 38–45 | Wide | Establishing shots, landscapes, cranes |

## 3. Shake (impacts)

```json
"shakes": [ { "t": 25.6, "dur": 0.5, "amp": 0.015, "note": "impact of the decisive blow" } ]
```
`t` = moment of the hit, `dur` = seconds it lasts (fades out), `amp` = strength in metres
(0.005 subtle, 0.015 strong hit, 0.03 explosion).

## 4. Camera recipes (copy, then change the numbers)

`S` = the subject point you care about (for example a fighter's chest `[0, 1.2, -0.8]`).

| Move | Keyframes (start → end) | Tips |
|---|---|---|
| **Establishing fly-over** | `pos` far + high `[0, 5, 60]` → near + low `[1, 2.4, 13]`; `look` stays on the island | `ease: inOut`, fov 42 → 36, 5–7 s |
| **Push-in** (tension) | `pos` = S + `[2.5, 0.2, 2.5]` → S + `[1.0, 0.1, 1.0]`; `look` = S | fov 36 → 30, 3–4 s |
| **Orbit** (standoff) | 3–4 keys around S on a circle, e.g. S + `[3,0.3,0]`, S + `[2.1,0.3,2.1]`, S + `[0,0.3,3]` | Same height and distance each key; `linear` for constant speed |
| **Over-the-shoulder** | `pos` = behind fighter A's shoulder (A + `[0.4, 1.55, -0.9]` relative to the way A faces); `look` = fighter B's chest | fov 32–36 |
| **Low hero angle** | `pos` y ≈ 0.4–0.7, close; `look` at chest/face (y ≈ 1.3–1.5) | Makes a fighter look powerful |
| **Impact close-up** | Key exactly at the hit time, `pos` ~1.6 m from the contact point, fov 28; add a `shakes` entry at the same `t` | Use `ease: linear` so the key lands on the frame |
| **Crane up** (ending) | `pos` rises from y≈2 to y≈9 while moving back; `look` lifts to the horizon/sun | `ease: inOut`, fov 36 → 42 |
| **Cut** | End one shot and start another at the same second | Cut on action (mid-swing) to hide the cut |

## 5. Workflow (any AI or person)

1. Edit the shot's `camera` keys in `film/<name>.json`.
2. **Check stills first** (seconds, not an hour):
   `node engine/render.mjs --still 24,25.7,27`, then look at `output/stills/t*.png`.
3. Adjust: a subject out of frame → change `look`; too far → move `pos` closer or lower the `fov`.
4. Render the section: `node engine/render.mjs --from 24 --to 30 --out output/test.mp4`
5. Full film: `npm run render`, then `node engine/sound.mjs` to add sound.

## 6. What is data vs. code today (honest status)

| Thing | Where it lives |
|---|---|
| Camera paths, lenses, cuts, easing, shakes, events, titles, sounds | **Data** (`film/*.json`) |
| Swords, characters, outfits, patterns | **Data** (`library/`) |
| Character choreography (poses over time) | **Data** (`film/*.json → performances`, poses in `library/poses.json`). See `docs/ANIMATION.md`. |
| Blade-follow, face close-up, torpedo track, orbit, one-take anchor, motion-reactive framing | **Built: KUROKO rigs** (section 7). Still to come: focus pulls / depth of field and motion blur (Blender), 180° auto-check, body-collision push-out. |

---

## 7. KUROKO (黒衣): the automatic camera operator

Named after kabuki's black-clad stagehands, who move everything and are never seen. Instead of typed coordinates,
a shot gets a **rig** that frames **characters by name**, **reacts to their motion**, and moves with a **feel**.
It is deterministic (a spring integrated at 240 Hz from the start of the shot, with a 1 s pre-roll so shots open settled).
Code: `engine/kuroko.js`. Numbers come from a fight-camera research review (game-camera talks such as John Nesky's
"50 Game Camera Mistakes", plus film grammar: the 180° rule, the 30° rule and cutting on action).

```json
{ "id": "S2", "start": 3.0, "end": 4.6, "mode": "dawn",
  "rig": { "type": "frame", "subjects": ["kojiro", "musashi"], "angle": 22, "elevation": 3, "fov": 34, "feel": "dolly" } }
```

### Subjects
`kojiro`, or a body part: `kojiro.head`, `.chest` (default), `.hips`, `.hand`, `.root`. Any performer id in the film works.

### Rig types
| Type | Fields | Use for |
|---|---|---|
| `frame` | `subjects` (1–2), `size` (wide/full/medium/close/extreme), `angle` (−70…70°, 0 = profile), `elevation` (°), `height`, `dist` (×), `fov` | Two-shots and singles. Distance is worked out from the fighters' separation and the lens (frame-fill rule). |
| `orbit` | `subjects` or `target`, `radius`, `height`, `deg0` → `deg1`, `fov` | Standoffs. Keep the arc on one side of the fighters' line. |
| `track` | `subject`, `offset` [right, up, back(−)/front(+)], `lookAhead`, `fov` | **Torpedo / chase**: rides with a fast-moving fighter |
| `face` | `subject`, `angle`, `dist`, `fov` (24) | Face close-ups |
| `anchor` | `beats`: [{ `t`, `type`, …rig fields }] | **One continuous take**: the spring carries the camera from beat to beat without cuts |
| `blade` | `offset` (blade space), `lookAlong`, `fov` | Rides the drawn blade (always locked feel) |

### Feels (camera weight)
| Feel | Character | Spring |
|---|---|---|
| `locked` | Stiff and mechanical: snaps, no overshoot | 6 Hz, damping 1.0 |
| `dolly` | Smooth track, slight lag | 1.8 Hz, 1.0 |
| `crane` | Heavy, slow, graceful | 0.7 Hz, 1.1, tiny drift |
| `handheld` | Loose and nervous, ~5% overshoot, seeded wobble | 2.5 Hz, 0.7 |
| `torpedo` | Fast attack, ~8% overshoot, speed buzz | 4 Hz, 0.62 |

The look point is 1.5× stiffer than the camera body, so the subject never slides out of frame. Fov and roll never overshoot.

### Behaviours (react to motion; default: `reveal`, `push`, `jump`, `dutch`, `lead`)
| Behaviour | Trigger | Camera does |
|---|---|---|
| `reveal` | A fighter retreats or jumps back (speed away from the opponent > 0.6 m/s) | Pulls back up to +38% and widens 4° to show the space |
| `push` | A fighter lunges (> 0.8 m/s toward the opponent) | Pushes in up to −20%, tightens 3° |
| `jump` | Hips rise fast | Camera rises 0.45 m with the body |
| `dutch` | Stagger (weight thrown back, torso reeling) | Rolls up to 7° |
| `whip` | Very fast sword arm | Look leans toward the swing |
| `lead` | Anyone moving | Frames ahead of the movement (lead room) |

All triggers **look ahead 3 frames**: the operator knows the choreography and starts moving just before the action.

**Always on:**
- **Impact punch.** On every `shakes` time and `events.impact`: 7° punch-in over 2 frames, a recoil, then a settle over about 10 frames. It's added after the spring so it lands frame-exact.
- **Guards.** At least 0.8 m from bodies (0.3 m for face/blade rigs), camera above 0.15 m. Clamps: distance 0.6–1.6×, fov ±8°, roll ±10°.

### Which feel for which move
| Move | Feel | Notes |
|---|---|---|
| Standoff | crane | `orbit` |
| Lunge, cut | dolly | `frame` |
| Thrust, dash | torpedo | `track` |
| Parry, bind | handheld | `frame` close |
| Jump-back | dolly or crane | `frame` with `reveal` |
| Stagger | handheld | `frame` with `dutch` |
| Decisive exchange | dolly | `anchor` |

Working example of every rig: `film/kuroko-duel.json`. Check rigs with stills (`--still auto`); see their resolved
paths in the playbook (`python3 docs/build_playbook.py film/kuroko-duel.json` → `docs/playbook-kuroko-duel.html`).

## 8. Motion-page camera beats, the `compose` framing solver and speed ramps
Films on the motion page (`"page": "engine/motion.html"`) direct the camera with `film.camera`: a list of beats.
Which camera for which beat, and the limits of each move: `STUDIO-STANDARD.md` §3. Working example of everything
below: `film/dash-test.json`.

```json
"cameraOpts": { "solver": 2 },
"camera": [
  { "act": 0,    "rig": "compose", "subjects": ["hero"], "basis": "target", "target": "sakura",
    "az0": 196, "az1": 189, "elev": -3, "size0": 0.62, "size1": 0.7, "screen": [0.36, 0.55], "fov": 34, "feel": "dolly" },
  { "act": 0.72, "cut": true, "rig": "compose", "subjects": ["hero"], "az0": 186, "az1": 152, "elev": -4,
    "size": 0.56, "lead": 0.17, "fov": 40, "feel": "torpedo", "lag": 0.018, "untilAct": 1.2 }
]
```

| Field | Meaning |
|---|---|
| `t` or `act` | when the beat starts: film seconds, or **action time** (`act`, follows the speed ramps: "when the blade lands") |
| `until` / `untilAct` | when its 0 → 1 moves finish (default: the next beat) |
| `rig` | `compose` (below), or the older `frame`, `orbit`, `face`, `slide` |
| `feel` | the spring: `locked`, `dolly`, `crane`, `handheld`, `torpedo`, `whip` (3–6 frame move) |
| `cut` | `true` = hard cut (needs `cameraOpts.solver: 2`); without it the camera travels to the new beat |
| `lag` | seconds the camera trails the subject (0.02; a dash can use 0.015–0.03) |

**`cameraOpts.solver: 2`** = the cinematographer's spring: it works on the camera's offset from the subject, so a
21 m/s dash cannot out-run it; a guard keeps the subject inside the frame (`keep: [0.72, 0.8]`), the lens 0.12 m
above the sand (dunes included) and out of trees and rocks. Without it, a film renders with the old world-space
spring, exactly as before.

**`compose`: say what the frame should look like.**
| Field | Meaning |
|---|---|
| `subjects` | `[who]` (first = the framed subject; a tree id also works) |
| `size` | share of the frame height filled by `span` metres (default 1.8 = the whole figure): 0.45 wide, 0.6 full, 1.2 medium, 2.5 close |
| `screen` | `[sx, sy]` where the middle of the subject sits (0.5, 0.5 = centre; 0.36 = left third) |
| `lead` | automatic lead room instead of `screen`: 0.16 puts the subject off-centre with space in front of its motion (or its gaze when still) |
| `az`, `elev` | degrees around the subject (0 = the +z side, 90 = +x) and up (negative = low angle) |
| `basis` | `world` (default) · `facing` (az 0 = in front of the subject, frozen at the beat's start) · `target` (az 180 = over the shoulder towards `target`) |
| `aim`, `span` | a joint instead of the whole body (`eyes`, `head`, `chest`, `wrist`, `tsuba`, `tip`, `hips`) and how many metres `size` measures |
| `fov`, `roll` | lens (22–45) and dutch tilt |
| pairs | every number takes `…0` / `…1`: `az0 → az1` orbit, `elev0 → elev1` crane, `size0 → size1` push-in / pull-back, `fov0 → fov1` with a fixed size = dolly-zoom; `ease`: `inOut` (default), `in`, `out`, `linear` |
| `guard` | `false` = no prop avoidance (a deliberate over-the-prop shot) |

**Speed ramps** (`film.ramps`): the body slows, the camera keeps moving in real time.
```json
"ramps": [ { "t": 1.06, "rate": 0.2, "in": 0.04, "hold": 0.5, "out": 0.16 } ]
```
`t` = action time where the slow-down starts; `rate` 0.2–0.35 (key moment) or 0.45–0.6 (a breath); `in`, `hold`,
`out` = screen seconds. Three clocks: film time (camera, sound, post FX) → world time (sparks, dust, props, impacts)
→ body time (keys; hit-stops). Authored `impacts`, `props` and sounds marked `"body": true` are in action time and
move with the ramps (`output/<film>.events.json` carries the table as `warp`).

Check every camera with `node tools/audit.mjs film/<name>.json` (`AUDIT.md`): it measures visibility, size, lead
room, blockers, lens-in-geometry, pops and the share of slow motion.

## 9. Camera moves on events, lens effects in Blender, impact effects on the frames (27 Nov 2026)
**What reaches the final Blender video** (measured on `film/dash-test.json` and `film/kojiro-exchange-cams.json`):
the timeline exports the live three.js camera AFTER every move below, and `blender/film_modular.py` keys it every
frame through `qcam`, so the path, cuts, the impact punch (zoom kick, shake, roll) and every `cameraMoves` entry are
in the render with the same numbers (f31 of dash-test: 38.4 mm, +2.16° roll in both). Effects drawn only in the
browser (bloom, speed lines, CA flash, glints, ink impact frame, white flash, sparks, ribbons, dust) are NOT; the
ink frame, flash, CA and speed lines are put back on the Blender frames by `tools/post_fx.py`.

**Correction (27 Nov pm): the same focal length was not the same picture.** The timeline's lens is defined on a 24 mm
sensor fitted vertically (`tools/timeline.mjs` SENSOR); `film_modular.py` keyed that focal length on Blender's default
36 mm AUTO sensor, which in a portrait frame fits the HEIGHT, so every film rendered 1.5x wider than designed (beach
f31: Kojiro filled 27-79% of the frame height; the design and `tools/shot_framing.py` assume 15-94%). The film camera
now has `sensor_fit VERTICAL`, `sensor_height 24`. Films rendered before that commit are wider than their design.

**Hit-stop** (`film.effects.hitStop`, frames): `tools/post_fx.py` holds the contact (ink / negative strobe), moves the
frames after it and writes the stop into the bake events, every later cue shifted with it. **Landings** bump the
picture for 5 frames. **Sound in the picture**: every bake cue is panned by its source's place across the rendered
frame and softened with distance (`tools/bake_events.py` Ears; steps, skids and landings come from the bake's ankles).

**`film.cameraMoves`** (`engine/camfx.js`, applied in `placeCamera` after the spring and the punch):
```json
"cameraMoves": [
  { "move": "rack",   "t": 0.9,  "dur": 0.35, "from": "target", "to": "hero" },
  { "move": "whip",   "t": 1.4,  "dur": 0.14, "deg": 40, "dir": 1 },
  { "move": "crash",  "t": 1.44, "zoom": 1.35, "in": 0.06, "hold": 0.18, "out": 0.3 },
  { "move": "dutch",  "t": 1.46, "deg": 7, "in": 0.08, "hold": 0.3, "out": 0.25 },
  { "move": "breath", "t": 1.95, "until": 3.0, "amp": 0.35 },
  { "move": "shake",  "t": 2.4,  "amp": 1.2, "dur": 0.35 }
]
```
| move | what it does |
|---|---|
| `crash` | crash zoom: the lens snaps in by `zoom` over `in` s, holds, eases back over `out` (0 = stays until the cut) |
| `whip` | whip pan THROUGH a cut: swings `deg` away in the last `dur`/2 before `t`, arrives from the other side after. Put `t` on a beat with `"cut": true` |
| `dutch` | roll to `deg`, hold, back |
| `breath` | a breathing handheld operator between `t` and `until` (`amp` degrees) |
| `shake` | a sharp decaying shake on a frame that is not a blade contact (contacts already shake) |
| `rack` | rack focus from actor `from` to actor `to` over `dur` (exported as `frames[].camera.focus_m` / `focus_on`) |

Time: `t` (film s), `act` (action time, follows the ramps) or `"at": "contact"` (the ENGINE's first blade contact; when
only the final bake has the contact, copy its `t` from `output/<film>.bake-events.json`). A move ends at the next hard
cut (whip and rack excepted; `"across": true` keeps it). `node engine/validate.mjs` checks every entry.

**Lens in Blender** (`film.effects`): `"dof": 4.0` (f-stop; `true` = the timeline's aperture, `cameraOpts.aperture`)
keys the focus distance every frame; `"motionBlur": 0.5` (shutter in frames, 180°). Motion blur opens ON the frame
(`START`) and the camera key before each cut is CONSTANT, so a cut never smears two set-ups together. `--no-dof` /
`--no-blur` turn them off for a run. The cut frame is the first frame at or after the beat time (`tools/timeline.mjs`;
it used to round, which put cuts one frame early).

**Impact effects on the frames** (`tools/post_fx.py`, step 5b of `tools/film.sh` when `film.effects.postFx` is true):
the hit frames are the final bake's contact plus every timeline `impactFrame`. Hit frame = one ink frame (black ink on
washi); then a white flash over 3 frames, a red/blue split over 2, speed lines for 4 frames after the hit and on any
frame where the lens zooms faster than 2.5 mm/frame; a soft vignette (`effects.vignette`, 0.25). It writes
`fx.json` (what landed where).

**Multi-camera = beats with `"cut": true`.** There is one Blender camera; each beat is a set-up and the cut switches the
key, so only the live camera ever renders. Proof: `film/kojiro-exchange-cams.json` (wide → medium with a rack focus →
whip pan into the impact close-up with crash zoom + Dutch on the contact → breathing wide recovery).

**KUROKO on the camera bench** (`tools/camera_bench.py solve`, via `tools/camera_bench_kuroko.mjs`): `engine/kuroko.js`
films the bench ball and is scored with the other operators. The look point now has feed-forward (`rig.feedForward`,
1 by default, 0 = the old lag) and lead room scales with the shot: kuroko-frame went 67.8 → 82.4 (operator 81.2).

**Check the framing before rendering** (`tools/shot_framing.py output/<film>.timeline.json [--single B2]`): per shot,
the share of frames where every fighter's chest is inside the frame AND the fighters are at least 0.30 frame widths
apart (so the foreground fighter never covers the other); `--single` marks a shot framed on one fighter. Exit 1
when a shot passes on under 80% of its frames. It costs seconds; a render costs half an hour. On
`kojiro-exchange-cams` it found the over-the-shoulder impact and recovery shots hiding Kojiro behind Musashi; the
angles were then chosen by sweeping `az` / `screen` against it (B1 100%, B2 94%, B3 94%, B4 100%).

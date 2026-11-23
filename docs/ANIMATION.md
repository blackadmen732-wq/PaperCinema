# Animation guide: skeleton, poses, smooth motion, two-hand grip

Characters move from **data** in the film file. You write *when* and *which pose*; the engine
makes the motion smooth, adds breathing and cloth follow-through, and keeps both hands on the sword.

---

## 1. The skeleton (every paper character shares it)

```
root (position x/y/z, facing ry, tilt rx/rz)
├─ right leg: thigh → knee (shin) → foot   ┐ solved by leg IK every frame: feet planted from `stance`,
├─ left leg:  thigh → knee (shin) → foot   ┘ hips height from `crouch`, knees bend forward automatically
└─ hips (drops with crouch, shifts over the loaded foot with weight)
   ├─ hakama (upper skirt: swings with sway / swayx; each leg also wears a split, flared trouser leg)
   └─ torso (tx lean forward, ty turn, tz side-bend)
      ├─ head (hx nod, hy turn)
      ├─ right shoulder (rsx forward/up, rsz sideways)
      │  └─ right elbow (rex, negative = bend)
      │     └─ right hand (rwx wrist) ── holds the sword
      └─ left shoulder (lsx, lsz)
         └─ left elbow (lex)
            └─ left hand (lwx) ── placed on the handle automatically (two-hand grip)
```

- The figure faces **+z** when `ry = 0`. Its right side is **−x**. `ry = 3.14159` faces −z.
- Lower body: `stance` = feet apart front-to-back in metres (right foot forward, kenjutsu style),
  `crouch` = hip drop in metres, `weight` = -1 (back foot) … +1 (front foot). Strikes lunge onto the
  front foot (fumikomi); wind-ups load the back foot.
- Angles are radians. Arm lift guide: `rsx = 0` hangs down, `-1.57` points forward, `-2.8` is overhead.
- Built in `engine/figure.js → makeFigure`. Outfits only change colours and patterns, never the skeleton,
  so **every pose and move works on every character.**

## 2. Poses (`library/poses.json`)

A pose is a named set of joint angles: stances (`chudan`, `jodan`, `hasso`), cuts (`shomen-strike`,
`kesa-giri-finish`, `tsuki-thrust`), the draw (`iai-draw`), reactions (`struck-reel`, `kneel-collapse`, `fallen`).
Add a new pose by copying one and changing angles, then check it with a still render.

## 3. A performance (in the film file)

```json
"performances": {
  "kojiro": {
    "character": "kojiro",
    "twoHand": [[21.0, 26.2]],
    "keys": [
      { "t": 0,     "pose": "rest-hand-on-hilt", "x": 0, "z": -0.8, "ry": 0 },
      { "t": 21.8,  "pose": "jodan" },
      { "t": 24.8,  "pose": "jodan", "z": -0.35, "tx": 0 },
      { "t": 25.05, "pose": "jodan-wind-up" },
      { "t": 25.45, "pose": "shomen-cut-finish", "z": -0.25, "y": -0.14 }
    ]
  }
}
```

| Field | Meaning |
|---|---|
| `keys[].t` | Second when the body reaches this pose. Strictly increasing. |
| `keys[].pose` | A name from `library/poses.json` |
| any joint (`tx`, `rsx`, …) | Overrides that joint for this key only |
| `x`, `z`, `ry` | Where the body stands and faces. **Carry over** to later keys until changed. |
| `y`, `rx`, `rz` | Crouch / tilt. Reset to 0 unless given on each key. |
| `twoHand` | Time windows when the left hand grips the handle (fades in and out over 0.15 s) |
| `walk` | Time windows with a walking bob and arm swing |
| `rideBoatUntil`, `boatPose` | Rides the boat until that second (Ganryūjima only) |

**To hold a pose**, repeat it at a later time: `{t: 21.8, pose: "jodan"}`, `{t: 24.0, pose: "jodan"}`.

## 4. Why the motion is smooth

1. **Curves through all keys.** Each joint follows a *monotone cubic* curve. Speed is continuous
   through every key (no robotic stop at each pose), and the curve never overshoots a key (no wobble).
   Consecutive keys with the same pose hold perfectly still.
2. **Timing makes the drama.** Big moves get short gaps (a cut in 0.3–0.4 s), stances get long holds.
   Use the Strike Grammar timing: Ready (hold) → Wind-up (0.2–0.4 s) → Slash (0.15–0.4 s) → Hit-stop
   (repeat the same pose ~0.15 s) → Follow-through → Reaction.
3. **Life on top** (automatic): breathing when standing still, and the hakama trailing behind
   steps and turns (`addLife` in `engine/main.js`).
4. **The camera is smooth too**: a centripetal Catmull-Rom path with shot easing (see `docs/CAMERA.md`).

## 5. Sword holding and the draw (how "hold" works)

- **The draw is one continuous blade.** Before the draw the right hand rests on the handle (hand IK).
  On `kojiro-draw`: a 3 cm thumb push, then the blade slides out along the scabbard while the scabbard
  stays on the hip, then the blade's frame blends from "in the scabbard" to "in the grip" over ~6 frames.
  No hidden swap, no jump.

- After the draw, the sword is attached to the **right hand** bone (`holdInHand`), so it follows every arm move exactly.
- Inside `twoHand` windows, the engine finds the end of the handle each frame and bends the left shoulder
  and elbow until the left hand lands on it (`reachLeftHand`, a small inverse-kinematics search).
  It starts from the keyed pose every frame, so renders are identical every time.

## 5b. Fight moves (`library/moves.json`)

Instead of writing every pose, call a named move. It expands into timed poses with footwork:

```json
{ "t": 3.0, "move": "lunge-shomen" },
{ "t": 3.1, "move": "jump-back", "speed": 1.2, "dist": 1.0 }
```

| Move | Length | What happens |
|---|---|---|
| `step-in`, `step-back` | 0.28 s | Sliding step (okuri-ashi), 0.4 m |
| `jump-back` | 0.85 s | Load, leap back 1.1 m (0.34 m high), land low |
| `dodge-left` | 0.6 s | Lean and slip 0.45 m to the side |
| `parry-high` | 0.85 s | Rising block (uke), then back to guard |
| `lunge-shomen` | 1.0 s | Wind-up, stamping step 0.65 m, vertical head cut, hold |
| `kesa-giri` | 0.9 s | Hasso to a diagonal cut, stepping 0.5 m |
| `tsuki` | 0.85 s | Load, thrust with a 0.7 m step |
| `bind` | 1.2 s | Blade-lock push (tsubazeriai) |
| `stagger-back` | 0.9 s | Knocked back 0.6 m, reeling |

- `speed` (2 = twice as fast) and `dist` (× distance) adapt any move.
- Positions are relative to where the fighter stands and faces when the move starts.
- The next key must start after the move ends (the checker says so if it doesn't).

## 6. Reaction layer (fighters respond to each other)

Inside a `duels` window (`{"a": "kojiro", "b": "musashi", "from": 17, "to": 27}`), automatically:
1. **Eyes on the opponent**: each head turns and tilts toward the other fighter.
2. **Threat response**: when the opponent's sword arm moves fast, the fighter sinks a little and shifts
   weight back ~0.12 s later (human reaction time), then relaxes.
Explicit reactions (a parry, a step back) are still written as keys.

## 7. Pose gallery (check poses side-on)

```bash
node engine/render.mjs --page engine/lineup.html --film film/lineup.json --query "show=poses&poses=chudan,jodan,shomen-strike" --still 1 --prefix poses-
```
Shows the chosen poses side-on with the two-hand grip, so knees, balance and blade angle are easy to judge.

## 8. Recipe: add a new attack

1. Pick or create the poses (for example `chudan` → `jodan-wind-up` → `kesa-giri-finish`).
2. Add keys with Strike Grammar timing, plus a `shakes` entry and sound cues at the hit second.
3. `npm run validate`, then check stills at the wind-up, the hit and the reaction.
4. Adjust angles or timing, render the section with `--from/--to`, then render the film.

## 9. 3D models from images (status)

The TRELLIS models in `assets/models/` are **static meshes: they have no skeleton yet.** Next step:
rig them in Blender (auto-weights after a clean remesh) using the **same bone names and layout as above**,
so every pose in `library/poses.json` drives them too. The full plan is in `docs/BLENDER-PLAN.md`.

## 10. Anime motion layer and the new joints (motion test)
**New joints** (all default 0, so old poses look the same): `cx/cy/cz` chest above the waist, `nx/ny` neck,
`hz` head roll, `rcy/rcz` (`lcy/lcz`) clavicle forward/shrug, `rsy/lsy` shoulder twist, `rfy/lfy` forearm twist,
`rwz/lwz` wrist side-bend (the cutting snap), `rax/lax` ankles, `lid` eyelids. `face: "eyes"` in a cast entry adds two
amber-glowing eye slits with lids and a brow (default stays faceless, the owner's design).

**Motion layer** (turn on with `"motion": { "overlap": true }` in the film):
| Key field | Effect |
|---|---|
| (always) | Follow-through: head and feet lead 2 frames, hips 1, chest +1, shoulder +1.5, elbow +2, forearm +2.5, wrist and cloth +3 |
| `"drag": 0` | Contact key: every joint arrives together on this frame (the far joints whip to catch up) |
| `"ease": "snap"` / `"antic"` / `"out"` / `"in"` or `[x1,y1,x2,y2]` | Shape of the segment arriving at this key. End slopes are finite (no infinite speed) |
| `"settle": true` (or a strength) | Each joint overshoots the pose a little and settles (closed-form damped spring) |

**Clash** (`film.clashes`): `{ t, until, attacker, defender, s }` turns the defender's blade (up to `maxDeg`) so it lies
across the attacker's blade at fraction `s`; the blades meet on frame `t` and stay crossed through a bind. Contact is then
*detected* (not assumed) and drives hit-stop, sparks, the impact frame and the clash sound.

**Camera beats** (`film.camera` on the motion page): `face` (eyes), `slide` (along `path` joints: elbow → wrist → tsuba),
`frame` (both fighters, `angle` 0 = side-on), `orbit`. Each aims at real joints; a spring smooths the path at 240 Hz.

Check: `node engine/render.mjs --film film/motion-test.json --still 0.7,2.2,3.16,3.7` then look at the stills.

## 11. Cut system and move list (`library/cuts.json`, `film/moves-gallery.json`)

**The cut system** is data in `library/cuts.json`:
- `directions`: the 8 cut directions of the owner's clock sheet. Each has a wind-up, contact and follow-through pose
  (names in `library/poses.json`), the target line on the opponent's body, a tip-path note, timing in frames and the wrist snap.
- `kata`: the 12 ZNKR seitei iaido kata (Mae … Nuki-uchi) as sequences of those cuts, with poses per step.
- `confidence`: what is documented (names, order, cut sequence: from the ZNKR manual, written from memory, so check a detail
  before quoting it), what is tradition (the eight-cut clock chart, school naming), and what is ours (every metre and frame).

| Clock | Direction | Poses (wind-up → contact → finish) | Line on the opponent | Move |
|---|---|---|---|---|
| 1 | kiri-oroshi (straight down) | `furikaburi` → `kiri-oroshi-contact` → `kiri-oroshi-finish` | head top → navel | `kiri-oroshi`, `lunge-shomen`, `nuki-uchi` |
| 2 | kesa (from the upper right) | `kesa-windup` → `kesa-contact` → `kesa-finish` | left neck → right hip | `kesa-giri` |
| 3 | gyaku-kesa (from the upper left) | `gyaku-kesa-windup` → `-contact` → `-finish` | right neck → left hip | poses only |
| 4 | yoko, right to left | `waki-right` → `yoko-contact` → `yoko-finish` | left flank → right flank | `yoko-giri`, `spin-cut` |
| 5 | yoko, left to right (draw-cut) | `iai-ready` → `nukitsuke-contact` → `nukitsuke-finish` (two hands: `waki-left` → `yoko-l-*`) | right temple → left temple | `nukitsuke` |
| 6 | kiri-age from the lower right | `waki-right` → `kiri-age-contact` → `kiri-age-finish` | left hip → right shoulder | `rising-cut` |
| 7 | kiri-age from the lower left | `waki-left` → `kiri-age-l-contact` → `kiri-age-l-finish` | right hip → left shoulder | poses only |
| 8 | tsuki | `tsuki-load` → `tsuki-contact` (`tsuki-high`, `tsuki-low`) → `tsuki-load` | solar plexus (a point) | `tsuki`, `rapid-thrusts`, `linear-drive` |

- **Target lines** are in the opponent's own frame (metres; +x = the opponent's left, +y up, +z = the way they face). The file gives the formula to world space.
- **Wrist:** `rwx` is the snap (it swings the blade toward its edge); `rwz` and `rfy` keep the edge on the cut plane. `snap` in the file lists wind-up and contact values.
- **Aiming a new pose:** the sword sits at 45° in the hand, and its edge is always on the side the forearm points to. So a straight-down cut needs the forearm
  pointing forward-down, a right-to-left cut needs the elbow to the right of the hand, and a blade pointing behind the hand needs the elbow out to the side.
  The cut poses were solved numerically for hand position, blade direction and edge direction inside the joint limits, then checked on stills.

**New moves** (all use `ease` / `drag` / `settle`; frames at 24 fps):

| Move | Length | Beats (anticipation / snap / follow-through) | Notes |
|---|---|---|---|
| `kiri-oroshi` | 1.5 s | 10 / 4 / 2, hold 9 | Feet and weight go first (frames 10–12), the blade in the last 2 frames |
| `lunge-shomen` (improved) | 1.0 s | 5 / 5 / 2 | Same contact time (0.42 s) and 0.65 m step as before; now ends level, not in the ground |
| `kesa-giri` (improved) | 0.9 s | 4 / 3 / 2 | Same contact time (0.30 s) and 0.5 m step as before |
| `yoko-giri` | 1.55 s | 11 / 4 / 2 | From waki-gamae; hips turn before the chest (`cy` held back) |
| `rising-cut` | 1.6 s | 12 / 4 / 3 | Sinks low, ends at full extension on a straight back leg |
| `rapid-thrusts` | 1.85 s | 7, then 3 thrusts of 3 frames (high, low, middle) | 3-frame recoils; the third has a 2-frame extra load and the deepest step |
| `linear-drive` | 1.8 s | 14 / 4 / 2 | 1.6 m lunge; back leg straight, body and blade on one diagonal. Start 3.3 m from the opponent |
| `spin-cut` | 1.7 s | 7 / 11 (the spin) / 2 | Head turns 3 frames before the hips. Uses absolute `ry` 0 → 2π: for a fighter facing +z only; put `"ry": 6.28319` on the next key |
| `low-dodge` | 1.2 s | 4-frame drop, hold 10, rise 15 | Slips 0.45 m left, head at 0.7 m, left hand on the ground. One-handed: no `twoHand` window here |
| `calm-low-stance` | 3.0 s | sinks over 14 frames, then a breathing hold | Ends in `calm-low`; follow with any attack |
| `nukitsuke` | 1.35 s | 12 / 4 / 2 | Horizontal draw-cut from `iai-ready`. One-handed |
| `nuki-uchi` | 1.35 s | 8 / 10 (draw up + cut down) / 2 | Seitei no. 12. One-handed until 0.58 s, then open a `twoHand` window |
| `chiburi` | 1.1 s | 8 + 3 hold / 3 / settle | Large chiburi: fist to the temple, flick down to the right |
| `noto` | 2.85 s | slow, uneven | One-handed. The motion page has no scabbard, so the blade is only laid along the left hip |

A move's first beat is its starting pose, so the key before it should be about 0.25 s earlier in a guard.
`twoHand` windows belong to the performance, not the move: leave the one-handed moves out of them.

**Gallery:** `film/moves-gallery.json` performs every move against a standing target (horizontal, 47 s; it is a test page, not a Short).
Its `index` lists each move's start time and the still times used for review:

```bash
node engine/validate.mjs film/moves-gallery.json
nice -n 10 node engine/render.mjs --film film/moves-gallery.json --still 5.833,8.5,14.209 --prefix mv-
```
Loading takes about 2 minutes (the page samples the whole film at 240 Hz first).

**Checker:** `validate.mjs` now warns when a key, a pose or a move beat goes past a joint limit, and fails on a move beat that names a missing pose.

**Known weak spots:** `noto` (no scabbard on the motion page; the edge lies flat, not up); `calm-low-stance` (legs only bend in the
forward plane, so the stance is long, not wide); `spin-cut` (absolute `ry`); directions 3 and 7 and the kata extras
(`tsuka-ate`, `katate-tsuki`, `soete-tsuki`) are poses checked by numbers only, with no move yet.

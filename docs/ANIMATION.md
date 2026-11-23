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

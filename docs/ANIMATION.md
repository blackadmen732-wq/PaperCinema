# Animation guide: skeleton, poses, smooth motion, two-hand grip

Characters move from **data** in the film file. You write *when* and *which pose*; the engine
makes the motion smooth, adds breathing and cloth follow-through, and keeps both hands on the sword.

---

## 1. The skeleton (every paper character shares it)

```
root (position x/y/z, facing ry, tilt rx/rz)
└─ hips
   ├─ hakama (skirt: swings with sway / swayx)
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

## 5. Two-hand grip (how "hold" works)

- The sword is attached to the **right hand** bone (`holdInHand`), so it follows every arm move exactly.
- Inside `twoHand` windows, the engine finds the end of the handle each frame and bends the left shoulder
  and elbow until the left hand lands on it (`reachLeftHand`, a small inverse-kinematics search).
  It starts from the keyed pose every frame, so renders are identical every time.

## 6. Recipe: add a new attack

1. Pick or create the poses (for example `chudan` → `jodan-wind-up` → `kesa-giri-finish`).
2. Add keys with Strike Grammar timing, plus a `shakes` entry and sound cues at the hit second.
3. `npm run validate`, then check stills at the wind-up, the hit and the reaction.
4. Adjust angles or timing, render the section with `--from/--to`, then render the film.

## 7. 3D models from images (status)

The TRELLIS models in `assets/models/` are **static meshes: they have no skeleton yet.** Next step:
rig them in Blender (auto-weights after a clean remesh) using the **same bone names and layout as above**,
so every pose in `library/poses.json` drives them too.

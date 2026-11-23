# Blender upgrade plan (from the Fable planning review)

Planning document. Render times are **estimates** (scaled from Blender Open Data benchmark ratios) until
milestone M1 measures real ones.

## A. Architecture: one evaluator, two renderers
- **Resolver** `engine/resolve.mjs` (Node, no browser) turns `film/*.json` into `output/<film>.timeline.json`.
  Per frame it stores the camera (position, quaternion, fov, focus distance, f-stop), every bone rotation, the
  root of each character, prop attach states, event frames and environment parameters. The maths (monotone
  cubic, Catmull-Rom, IK, springs) lives in shared modules, never re-written in Python.
- **Previs**: three.js plays the timeline (fast blocking).
- **Final**: `blender/build_film.py` (`blender -b -P build_film.py -- film.timeline.json`) links library
  `.blend` assets, writes keys, saves one `.blend` per shot. `render_shot.py` renders frame ranges. ffmpeg and
  sound stay as they are.
- **Conversions**:
  - Axes: three.js (x, y, z) → Blender (x, −z, y).
  - Lens: `sensor_fit='VERTICAL'`, `angle_y = radians(fov)`.
  - Rotations: quaternion bone keys.
  - Poses: `library/rig-map.json` maps pose fields to bone, axis and sign.
- **Sync test**: the resolver emits about 12 landmarks (hands, head, blade tip, camera). Blender must match within 1 cm.
- **Pin one Blender LTS** everywhere (the bpy API differs between 4.x and 5.x).

## B. Camera system: **KUROKO** (黒衣)
Named after kabuki's black-clad stagehands, who move everything and are never seen. Each shot gets a `"rig"`:

| Rig | Parameters |
|---|---|
| `keys` | today's keyframes |
| `dolly` | `from`, `to`, `target` |
| `crane` | `pivot`, `arm`, `boom` and `swing` curves |
| `orbit` | `target`, `radius`, `height`, `deg0`, `deg1` (a true circle) |
| `handheld` | `amp`, `freq`, `seed` (seeded noise, scales with distance) |
| `blade-follow` | `sword`, `offset`, `lag` (spring-smoothed socket behind the tip) |
| `face-snap` | `character`, `dist`, `side`, `snapFrames` 3–5 (settle overshoot under 2%) |
| `anchor` (one-take) | `"midpoint"` / `"blade:kojiro"` / `"head:musashi"`, `beats[]` of `{t, offset, fov, stiffness}`. Critically damped spring at fixed 240 Hz substeps, so it is deterministic. |

- **Targets**: symbolic, for example `"look": "kojiro.head"`.
- **Guards**: 180° line check, capsule collision with push-out, and maximum angular velocity outside whip pans.
- **Focus**: `"focus": "kojiro.eyeR"`, `"fstop"`, `"focusPull"`. In Blender the focus target is an Empty parented to a bone.
- **Motion blur**: shutter 0.5 normally, 0.25 for macro and hit-stop frames.
- **Macro look**: f/0.4–0.8 for close-ups (scale effect), fov 10–18 (85–135 mm), `clip_start=0.01`. No handheld noise under 0.6 m, camera speed capped at 2% of frame width per frame, breathing near zero.

## C. Characters
- **The TRELLIS meshes are fused statues** (sleeves, sword and glow baked in). Use **rigid paper parts, not skinning**:
  1. Clean: separate loose parts, delete artefacts.
  2. Facet: voxel remesh about 1 cm, Decimate Collapse to 4–8k triangles, then Decimate Planar 8–12°. Shade flat, Bevel 0.5 mm.
  3. Texture: bake the albedo onto the new UVs (Selected to Active).
  4. Split by bone: `bmesh.ops.bisect_plane` at the neck, shoulders, elbows, wrists, waist, hips, knees and ankles. Parent pieces with no weights.
  5. Joints: pleated "bellows" sleeves are the only skinned parts.
  6. Cloth: hakama and sleeve tails as 6–10 rigid panels on chained bones, driven by the follow-through maths.
- **Expect** the hero scan to yield a head, hat and torso; arms are likely procedural. Later: regenerate in an A-pose, with the hat and sword as separate images.
- **Skeleton**: custom, about 26 bones. Today's names plus thigh, shin and foot (left and right), a `saya` bone and hand sockets. Leg IK with poles; arms FK with an IK switch. No Rigify.
- **Paper shader**:
  - `Mix(Diffuse, Translucent, 0.3–0.45)` plus faint sheen. No subsurface on thin sheets.
  - Washi fibre texture (CC0) drives colour, bump 0.1–0.2, and the translucency factor.
  - Edges slightly lighter and rougher.
- **Interior glow**:
  - 2–3 amber lights at 2200–2700 K inside the shell (crimson for demonic).
  - Backface emission masked by a thickness or AO map.
  - Real gaps at the seams so light leaks.
- **Macro checklist**: fibre bump, bevelled creases, 0.3–1 mm warp per facet, double layers at overlaps, dust in the volume, shallow depth of field, warm rim light, dark backdrop.

## D. Swords
- **Metal**:
  - Principled: metallic 1, roughness 0.12–0.2, anisotropic 0.6 along the blade.
  - Hamon: a wave mask (Noise-distorted Wave) that shifts roughness from 0.15 to 0.35 and adds a milky tint.
  - Reflections: a studio HDRI visible to glossy rays only.
- **Demonic**: black paper blade, seam emission driven by `power` 0–1, interior crimson light, Glare (Fog Glow).
- **Correct draw**: **one blade object** with two Child Of constraints (`saya.mouth` → `hand.R.socket`).

| Frame from `kojiro-draw` | What happens |
|---|---|
| f−6 → f0 | The hand IK reaches the handle |
| f0 → f2 | Thumb push: the blade slides 3 cm |
| f2 → f9 | Slide out; the scabbard pulls back 10–15° (saya-biki); the left hand is on the scabbard |
| f9 → f10 | Switch with world matrix preserved; the arm switches IK → FK; jump under 2 mm |

  The thrown scabbard uses the same switch. In three.js use `Object3D.attach()`.
- **Two-hand grip**: sockets `grip.R` and `grip.L`; the left arm is IK with a pole, influence keyed by the `twoHand` windows.

## E. Fight animation library
- **Primary**: a keyframed move library in JSON.
- **Mixamo**: for legs, footwork and jumps (free, manual download, retarget, keep legs, overwrite arms).
- **Avoid as data**:
  - Video mocap (GVHMR, WHAM, 4D-Humans): built on SMPL, which is **non-commercial**. Use for timing reference only, or MediaPipe (Apache 2.0).
  - Text-to-motion (MDM, MoMask): non-commercial training data, and weak at swordwork.
- **Move file** `library/moves/<name>.json`: poses per beat (ready, windup, slash, contact, follow, recover), durations, root motion, blade-tip path, contact point.
  Usage: `{"t": 24.8, "move": "kesa-giri", "speed": 1.2, "target": "musashi", "result": "parried"}`
- **First 12 moves**:
  1. Chūdan idle
  2. Step-in / step-back (okuri-ashi)
  3. Circling side-step
  4. Iai draw-cut
  5. Shōmen-uchi
  6. Kesa-giri
  7. Kiri-age
  8. Yoko-giri
  9. Tsuki
  10. High parry + clash (uke)
  11. Bind (tsubazeriai)
  12. Struck-reel → kneel → fall

  Then: jump-cut, dodge-back, the crimson power attack, and chiburi / nōtō.
- **Clash event**: both wrists are IK-adjusted so the blades meet within 5 mm, then hold.
- **Hit-stop and speed ramps**: a `timewarp` track (film time → performance time). Characters freeze while the camera and particles keep moving.
- **Sparks**: 30–80 seeded paper-confetti quads, emissive flecks and a 2-frame flash.
- **Baked actions**, one per character per shot. No live NLA blending, so the previs and the final can't diverge.

## F. Paint instead of blood
- **Split**:
  - Evaluate the posed mesh at the cut frame, then run `bisect_plane` twice and fill the caps with stacked red paper and wet gloss.
  - Swap in the halves inside the hit-stop.
  - Key the halves: slide 2–4 cm along the plane over 12 frames, then tip. Add a torn-fibre fringe along the cut.
- **Paint, cheapest first**:
  1. A glossy vermilion (shu-iro) ribbon swept along the blade-tip path (doubles as the slash trail).
  2. Red paper streamers and confetti.
  3. A ground paint pool as a keyed shader mask.
  4. Hero close-ups only: Geometry Nodes metaball blobs.

  No fluid simulation.
- **Taste rules**: opaque poster-red, after the hit-stop. Props and clothing are cut more often than bodies; at most one body cut per film.

## G. Environments and sky
- **Keep the diorama.** The sky is a light source only; the camera sees a curved paper cyclorama and a backlit paper sun or moon.
- **Fog**: one volume box, density 0.01–0.03, anisotropy 0.6–0.8, with gobo god rays (costs 1.5–2.5×, so enable per shot).
- **Water**: Geometry Nodes paper wave strips. **Backdrops**: 5–8 kirigami layers with emissive gaps.
- **Presets** in `library/environments/`:
  - `dawn-island`
  - `bamboo-forest`
  - `snow-temple`
  - `burning-castle-night`
  - `sakura-courtyard`

  Shots use `"env": "<preset>"`.

## H. Signature opening: `library/openings/lantern-wave.json` (6.0 s)

| Time | Element |
|---|---|
| 0–0.8 s | Black; sea and wind fade in |
| 0.8 s | Taiko hit, fade from black |
| 0–6 s | Skim the paper waves toward `target`: from 62 m out at 5.2 m height to 13 m out at 2.4 m, fov 42 → 36 |
| 0.8–5.4 s | Kanji title as a real backlit cut-paper object |
| 5.6–6 s | Cut or whip into the film |

Films add `"opening": {"use": "lantern-wave", "jp", "en", "sub", "target", "env"}`. The waves change with the environment. Fixed signature sounds: taiko plus a 3-note shakuhachi or koto motif.

## I. Rendering (estimates)
- **Size**: render 1920×804 (true 2.39:1), which is 26% fewer pixels than 1080 with bars.
- **Cycles settings**:
  - 96–128 samples, adaptive 0.02, OIDN with albedo and normal passes.
  - Light Tree on, Persistent Data on.
  - Bounces: 6 total, diffuse 3, glossy 3, transmission 6, volume 1. Clamp indirect at 5.
  - Motion blur on, AgX view transform.

| Machine | Mode | Per frame | 36 s film |
|---|---|---|---|
| Container, 4 CPU | Cycles 1280×536, 48 samples | 2–5 min | 30–70 h (stills and tests only) |
| Kaggle T4 | EEVEE 1080p | 1–3 s | 30–60 min (headless EGL untested) |
| Kaggle T4 | Cycles OptiX, 96 samples | 25–45 s (60–90 s with fog) | 6–11 h, or 3–6 h on 2 GPUs |
| RunPod 4090 | Cycles | 3–6 s | 1–1.5 h, about $0.40–0.60 (only with owner approval) |

Recommended: three.js for blocking, container Cycles for stills, Kaggle T4 Cycles for finals (per shot, resumable).

## J. Milestones
1. **M1** Lookdev stills: paper shader, glow, faceted hero, metal katana, macro depth of field. Measures real render times.
2. **M2** Resolver + Blender builder (camera only) + the signature opening on Kaggle.
3. **M3** The correct draw in both engines.
4. **M4** Rigged hero with legs; the sync test passes; idle and shōmen.
5. **M5** KUROKO rigs.
6. **M6** Moves 1–12, clash, timewarp; a 10 s exchange.
7. **M7** Cut and paint.
8. **M8** Environment presets and a full re-render.

**Not yet:** cloth or fluid simulation, video mocap, text-to-motion, AI restyle, faces and lip-sync, crowds, 4K, live Blender MCP control.

## K. Risks
- **Photoreal**: realistic for stills and slow shots. Fast AI-keyed fights read as well-directed stop-motion.
- **TRELLIS scans**: may only yield a shell; budget for procedural limbs.
- **SMPL licensing**: blocks the mocap shortcut under the commercial-safe rule.
- **Interior-light noise**: can double the sample count.
- **Kaggle**: session limits; renders must be chunked and resumable.
- **CPU-only container**: minutes per still.
- **Two engines**: the resolver and sync test keep this bounded.
- **Macro shots**: expose every flaw, so plan fewer of them.

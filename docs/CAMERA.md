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

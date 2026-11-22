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
| Camera paths, lenses, cuts, easing, shakes, titles, sounds | **Data** (`film/*.json`) |
| Swords, characters, outfits, patterns | **Data** (`library/`) |
| Character choreography (poses over time) | **Code** (`engine/main.js`, `kojiroKeys` / `musashiKeys`). Next step: move it to data too. |
| Planned camera modes from `docs/STYLE-AND-FIGHT-SYSTEM.md` (blade-follow, face-snap, continuous one-take anchor) | **Not built yet.** Today they're made by hand with keyframes as above. |

# SHIMI (染み): the slash sequence and the stain simulator

`engine/shimi.py` is our own wet-paper stain simulator. This document has two parts: the full frame-by-frame
sequence of a slash, and the upgrade path for SHIMI. It comes from a VFX design review (Fable), and the prior work it cites
was recalled from memory: verify it before publishing any claims.

## 1. The slash, frame by frame (24 fps, f0 = blade contact)
Paper answers in a fixed order: **light → fibre → liquid → shape.**

| Frames | What you see | Driven by |
|---|---|---|
| −3…−1 | Blade smear, 1-frame anticipation hold | 3D + camera (motion blur 0.8) |
| 0 | Contact: the paper dents 2–3 mm. No paint yet | 3D shape key |
| 0…2 | **Flash**: the slit glows raw amber as the inner light escapes through the cut | Emission strip, impact frame, 2–3 frame hit-stop |
| 1…4 | **Fibre tear**: washi fibres pull out instead of snapping. A fuzzy white fringe, motes floating off | Curve strip on the cut edge, 10–20 motes, fibres 2–8 mm |
| 2…6 | **The gap opens** 0 → 3 mm, the lips curl, red inner paper layers show | 3D bisect + displacement |
| 4…10 | **Welling**: glossy paint beads on the lower lip, deepest part first, then merging | Metaballs, 5–9 beads, radius → 4–6 mm |
| 6…9 | **Spurt (optional)**: 3–5 short arcs along the blade, stretched for 3 frames, then round. Opaque and bright | Keyed particles, at most 40, none toward the lens |
| 5…30 | **Fast wicking**: a hairy front races along the fibres, with a pale wet halo ahead of the red | SHIMI |
| 12…72 | **Gravity runs**: a bead lets go and runs in stick-slip, thinning until the paper drinks it | 3D bead, then SHIMI surface layer |
| 14…20 | Spurt drops land and make small secondary stains | SHIMI point sources |
| 12…120 | **Translucency**: the wet halo glows amber; the stain core glows deep red from inside | Shader from the wetness map (0.38 → 0.75) |
| 18…120 | **Cockling**: wet paper puckers in ridges along the fibres, about 0.5 s behind the wetness | Displacement from SHIMI (1–1.5 mm) |
| 24…120 | The beads shrink as the stain grows (the paper drinks the paint) | SHIMI drives the metaball radius |
| 72…240 | **Drying**: gloss to matte, rims darken, a faint tide line stays, about 40% of the cockle stays | SHIMI + shader (compressed to 4–8 s) |

**Sound:**
- f0: a dry paper "shhk" with a low thump
- f0–2: near-silence (hit-stop)
- f2: fibre crackle
- f5: a soft wet tick
- f8: a short spatter
- f12 onward: a faint fizz of soaking paper
- each run: a quiet slide
- each landed drop: a "pat"

**Guardrails:** opaque, bright, slightly thick paint. No pulsing rhythm (it reads as a heartbeat). Always show paper layers in the gap.

## 1b. Presets (call by name: `python3 engine/shimi.py --preset <name> --out output/shimi/<name>`)
| Preset | Fight event | Ready for |
|---|---|---|
| `kesa-cut` | Diagonal cut on a standing body | Mid and wide shots |
| `heavy-drip` | Deep cut, paint runs down in drips with beads | Mid shots |
| `x-cut` | Two crossing cuts | Mid shots |
| `tsuki-stab` | Thrust: a point wound with a halo and drips | Mid shots (after the review fixes) |
| `table-flat` | Paper lying flat, no gravity | Wide shots |
| `ink-wound` | Black sumi ink (cursed blade) | Mid and wide shots |
| `graze` | A light graze, short welling | Wide shots |

Options: `--cut "x0,y0,x1,y1;…"`, `--stab "x,y,r;…"`, `--gravity`, `--bleed`, `--drips`, `--paint vermilion|crimson|ink`, `--seed`, `--size`.

**Review** (Fable, first gallery): about 6/10 on a phone, 4.5/10 against real paint on washi. Fixed after the review:
- pigment lags the water (damp halo)
- ragged cut edges, unblurred fibres, visible fibre texture
- pigment saturation (no black cores) and clamped overlapping cuts
- fat, straight drips ending in beads
- a ragged stab, and a short graze

Still to do before macro close-ups: two water layers, √t wicking, edge-driven evaporation (proper tide lines), granulation, 1024² with every constant scaled to the resolution, and a side-by-side check against photos of real paint on washi.

## 1c. KIZU (傷, "wound"): the wound-flow layer on top of SHIMI (built)
KIZU decides **how paint leaves a cut**; SHIMI decides how the paper drinks it. It's informed by how minor cuts really bleed
(a research review: Plateau–Rayleigh bead break-up, Lucas–Washburn wicking, drop retention, standard first-aid descriptions).
It's stylised as paint and stays non-graphic. Turn it on with `--wound graze|shallow-cut|deep-cut|stab --region face|hand|torso|limb --depth 0..1`.

| Behaviour | Model |
|---|---|
| **Onset delay** | `t_on(s) = s·T_blade + τ0·(1 − 0.7·d)·(0.7 + 0.6·sharpness)/R`. The deepest point shows first; a shallow cut shows nothing for a moment |
| **Depth along the cut** | `d(s) = depth·1.9·s^0.6·(1−s)^1.2`. The blade bites in fast and trails out |
| **Welling** | `q = Q·R·d^1.5·[(1−e^(−τ/t_r))·e^(−τ/t_d)/peak + o·e^(−τ/t_o)]`. Deeper is faster and longer; monotone, no rhythm |
| **Beads → line** | Beads seeded every λ mm along the cut, merging into a line over the merge time. A graze is a 2-D scatter of dots that never merge |
| **Surface vs soaked** | A share of each wound's paint goes to the glossy surface film (graze 15% … deep cut 75%) |
| **Brush swipe** | f0–f3: the blade drags a matte, streaky dry-brush stamp along its path, overshooting the exit (forensic "swipe") |
| **Drips** | A bead lets go only after it grows heavy (time from onset ∝ 1/flow). Max drips per wound and per region (face: 1) |
| **Regions** | Face ×1.6 rate, ×1.3 duration · hand ×1.3 · torso ×1.0 · limb ×0.8 |

**Wound types:**

| Type | τ0 | Rise | Decay | Q | Bead spacing | Merge | Smear | Max drips |
|---|---|---|---|---|---|---|---|---|
| graze | 0.9 s | 0.5 s | 0.4 s | 0.25 | 7 mm (dots) | never | 1.0 | 0 |
| shallow-cut | 0.5 s | 0.25 s | 0.9 s | 0.6 | 5 mm | 1.1 s | 0.6 | 1 |
| deep-cut | 0.12 s | 0.12 s | 2.0 s | 1.1 | 8 mm | 0.3 s | 0.8 | 3 |
| stab | 0.3 s | 0.2 s | 1.5 s | 1.0 | one bead | n/a | 0.2 | 1 |

**Presets:** `face-cut`, `deep-kesa`, `arm-graze`, `stab-wound`. A timing sheet is written to `output/kizu-timing.png`.
Verified sequence for `face-cut`: a pale swipe at 0.08 s → separate beads at 0.5 s → merged line at 1 s → one run by 3 s.

**Guardrails:** opaque bright vermilion, no flesh tones, no rhythm, no spurt for face or stab wounds,
at most 3 drips (face 1), welling done within about 5 s, no neck or wrist wounds, no wound close-up longer than about 1.5 s.
Check the current platform rules before release.

## 1d. SHIMI v2 core (built)
- **Two water layers:** a surface film S (glossy; beads, runs, drips) and capillary water W inside the paper (darkens it, lets light through). S soaks into W up to the paper's capacity.
- **Saturation-limited wicking:** fast at first, then slowing (measured front 8 → 12 → 14.5 → 16.6 → 18.4 px at equal steps).
- **Edge-driven evaporation:** pigment is carried outward, giving real tide lines.
- **A gravity direction field** (`--gravity-dir`, `--gravity-map`) for UV space on 3D parts.
- **New `film_*` map** (glossy surface paint) for the 3D shader. 3D integration design: `docs/SHIMI-3D.md`.

## 2. SHIMI upgrades (ranked by payoff per effort)
1. ✅ **Data maps:** `wet_*`, `pigment_*`, `everwet_*` (16-bit) are exported next to the colour frames.
2. ✅ **No wrap-around:** stains no longer re-enter from the opposite border.
3. **Two water layers:** a surface film S (glossy, moved by gravity) and capillary water C inside the paper (capped).
   Soak-in `S → C` at `k·perm·(Cmax − C)`. Gravity acts only on S. Gloss = S; darkening and translucency = C.
4. **Washburn calibration:** real wicking grows as √t. Use conductivity `D0·(C/Cmax)^3` for a self-limiting front, and define time in seconds (not steps).
5. **True coffee ring:** edges evaporate faster (`evap = e0·(1 + 2.5·(1 − blur(wetmask)))`). The centre refills the edge and carries pigment out.
6. **Granulation:** pigment settles in fibre valleys (height map from the fibres; Curtis-style deposit and lift).
7. **Multi-scale fibres:** long fibres, cloudy density, faint screen lines, bark flecks.
8. **Backruns:** "cauliflower" edges when new water reaches damp paint (comes on its own once 3 and 6 exist).
9. **Cockle and normal maps:** from delayed wetness × ridge noise along the fibres, plus paint height.
10. **GPU version (optional):** every rule is a 3×3 neighbourhood, so it ports to a WebGL shader for real-time preview.
11. **Kubelka–Munk colour:** only needed when red overlaps black ink.

Resolution: 1024² per stained part for close-ups, 512² for mid shots. Speed now: about 0.5 s per frame at 512², about 2 s at 1024² (CPU).

## 3. Into 3D
- **Simulate in the UV space** of the cut part, masked to its UV island.
- **The cut** comes from the 3D bisect: the cut edges' UVs become a polyline, each point with a depth and a start time.
- **Gravity** is world "down" projected into UV, baked per texel and rebaked when the character moves.
- **Shared fibre seed** for the sim and the shader bump, so the stain feathers along the fibres you can see.
- **Contact stains** (`touch` events): raycast from the fingertips. If the wound is wet, add a point source on the fingertip UVs and remove the same amount from the wound.
- **Events JSON** per shot (`cut`, `touch`, `drop-landed`), seeded, so the result is the same every render.

**Paper shader:**

| Map | Use |
|---|---|
| Pigment | Base and translucent colour (inner light turns red through the stain) |
| Wetness | Translucency 0.38 → 0.75, base colour about 15% darker |
| Surface film | Roughness 0.85 → 0.15, coat up to 1 |
| Height | Bump about 0.3 mm |
| Cockle | Displacement 1–1.5 mm |
| Ever-wet | The tide line |

## 4. Honest positioning
- **The method is not new.** SHIMI is a simplified member of a well-known family:
  - Curtis et al. 1997, "Computer-Generated Watercolor"
  - Chu & Tai 2005, "MoXi" (and the Expresii app)
  - Earlier ink-diffusion work by Small, Guo & Kunii, Zhang, and Lee
  - Physics: Lucas–Washburn wicking, and Deegan et al. 1997 on the coffee ring
- **Similar tools exist:** Rebelle, Corel Painter, Adobe Fresco, Houdini wet maps, Blender Dynamic Paint.
- **What's distinctive** is the application:
  - paint wounds on animated paper characters, driven by fight events
  - seeded and deterministic
  - in the character's UV space, feeding a paper that glows from inside
  - a platform-safe paint-not-blood rule

  Say "we have not found an equivalent", not "first".

**Build order:** two water layers + Washburn calibration → UV cut polyline → shader maps in Blender.

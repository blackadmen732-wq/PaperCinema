# Effects plan: SHIMI stains, the face-touch scene, anime effects

## 1. SHIMI (染み): our own stain simulator (`engine/shimi.py`, built)
Paint bleeding into paper, simulated rather than drawn:
- **Fibres:** a random fibre map gives each pixel a permeability and a direction.
- **Wicking:** liquid flows to neighbours faster along fibres, which makes hairy, feathered edges.
- **Pinning:** sized (water-resistant) patches stop the wet front, so edges come out jagged.
- **Gravity rivulets:** on standing paper, pooled paint runs straight down.
- **Drying:** thin water dries first, so pigment piles up at the edges (dark rims). The wet sheen fades to matte.
- **Colour:** subtractive, like real paint. Choose vermilion, crimson or ink.
- **Output:** a seeded, deterministic RGBA frame sequence (`--cut`, `--gravity`, `--bleed`, `--paint`, `--seed`).

**Next steps:**
1. **Wet-paper darkening:** wet paper turns slightly translucent, so the body's interior light glows through the stain. A second map drives the paper shader's translucency.
2. **Stain as a texture on the body:** project the frames onto the cut paper part, in UV space, starting at the cut event. In three.js this is a texture swapped per frame; in Blender an image sequence.
3. **Contact stains:** any paper that touches wet paint (a hand, a sleeve, the ground) gets its own SHIMI source at the contact point. A hand that touched the wound leaves red fingertip blooms.
4. **3D paint on top:** glossy paint beads (metaballs) well out of the cut first, then soak in. The 3D paint shrinks as the SHIMI stain grows, so it looks like the paper is drinking it.

## 2. Blender slash, version 2 (feedback on the first test)
- **A bigger, splashier paint burst:** 3–5 large arcs of droplets thrown along the blade's path (keyed ballistic arcs), stretched along their motion for the first 3 frames (anime smear), then round. Plus a splash on the ground.
- **A sharper, more ink-like stroke:** a hard dry-brush edge mask (high-contrast noise, threshold instead of a soft ramp), bristle streaks along the stroke direction, and ink "splatter" dots off the stroke's start.
- **The stroke appears and dies over about 6 frames** (draw-on along the blade path), with a 2-frame bright flash at the hit.

## 3. The face-touch scene (millimetre control)

**The beat:** the cut lands → paint wells out → the fighter slowly raises a hand and **touches the wound on his face** → the camera follows the hand to the face → the fingers come away red → he **looks up** at his opponent.

| # | Time from hit | Body | Camera (KUROKO) | Stain / paint |
|---|---|---|---|---|
| 1 | 0–0.2 s | Hit-stop, head snapped back | Impact punch, then hold | SHIMI starts at the cut line on the face plate |
| 2 | 0.2–1.0 s | Stunned, eyes (head) lowered | Slow push-in, `dolly` | Paint beads well out of the cut (3D) |
| 3 | 1.0–2.0 s | **Left hand rises to the cheek**: hand IK to a point on the face (`kojiro.face.cut`) | `anchor` beat: **look target = the hand**, drifting with it | |
| 4 | 2.0–2.6 s | Fingertips touch and hold | Close-up, focus locked on the fingertips | **Contact stains**: SHIMI sources at the 2–3 fingertip points on the hand |
| 5 | 2.6–3.4 s | Hand lowers in front of the eyes, he looks at his red fingers | Look target slides hand → eyes, `crane` feel | |
| 6 | 3.4–4.2 s | **Looks up** at the opponent (head rises, slight stance shift) | Camera tilts up with the eyes, then pushes past the shoulder to frame the opponent | The stain keeps spreading and drying on the face |

**What's needed to build it** (all with the systems we already have):
- **Face points:** named points on the head (`face.cut`, `cheek.L`, `eyes`) in the skeleton, so the hand IK can reach a millimetre-exact spot. The engine already does this for the left hand on the sword handle (`reachHand`).
- **Hand IK as data:** a performance key like `{ "t": 1.0, "reach": { "hand": "l", "to": "kojiro.face.cut", "until": 2.6 } }`.
- **KUROKO look targets on any point:** `"look": "kojiro.hand.l"`, then `"kojiro.eyes"`, then `"musashi.head"` (anchor beats). Subjects already resolve by name; this adds hand and face points.
- **SHIMI on the face plate, plus contact stains on the fingertips**, triggered by events (`cut`, `touch`).

## 4. Anime effects pack (planned)
Called by time in the film file, for example `{ "t": 9.2, "effect": "flash-step" }`:
- **`flash-step`:** the fighter folds flat, bursts into confetti, a light streak crosses the screen, and he unfolds behind the target. The camera whips with it.
- **`shadow-vanish`:** the shadow slides away first, then the body dissolves into ink.
- **`speed-lines`:** manga ink lines across the screen during dashes.
- **`impact-frame`:** a 2–3 frame black-and-white sumi-e flash on the decisive hit.
- **`afterimage`:** 2–4 fading paper copies trailing a fast swing.
- **`power-up`:** crimson light leaking through the paper seams, with rising sparks.
- **`hit-stop` / `slow-mo`:** a time-warp track. The fighters freeze while the camera and particles keep moving.
- **Shorts opening:** a 3-second version of the signature opening (hook first, title second).

# CHARACTER FACTORY: modular origami characters

**One skeleton. Interchangeable validated paper parts. One material family.** A character is a JSON recipe;
the factory builds it, binds it to the shared rig and hands back something that poses from `library/poses.json`
and renders with `blender/film_blender.py`.

## Why it exists

The TRELLIS models (`blender/character/rig_trellis.py`, still the external-mesh path) are **one fused shell**:
the arms are glued to the chest, there are no legs — only a skirt blob to the floor — the sleeves merge into
the torso, and nothing can bend. Render them under flat studio light and it is obvious
(`output/character/all-models-neutral.png`). The owner's reference
(`research/ref-origami-samurai-standing.jpg`) is the opposite: **separate sheets of paper**, folded, layered
and joined, with crisp planes, deliberate overlaps, visible thickness and narrow shadows between sheets.

So: build the character the way the reference was built. Out of parts.

## The pieces

| File | What it is |
|---|---|
| `blender/character/part_registry.py` | the library of parts, with their slot, socket, bone, size range, layer and sheet. `python3 blender/character/part_registry.py` prints the whole table |
| `blender/character/modular_builder.py` | builds a recipe: rig → parts → sockets → materials → binding → pose → render |
| `blender/character/part_validator.py` | the gate: a part may not enter the library until it passes, across a pose sweep. Exits non-zero |
| `library/paper-materials/*.json` | the sheets (washi, card, seam shadow): colour, fibre, thickness, fold darkening, translucency, inner light |
| `library/character-recipes/*.json` | the characters |
| `blender/world/paper_materials.py` | `PC_Washi_Master()` turns a sheet into a Cycles material |

## Commands

```bash
B=blender
python3 blender/character/part_registry.py                    # every part, slot, socket and bind
python3 blender/character/part_registry.py --slots            # the slot table only

# build, pose, render
nice -n 10 $B -b -t 2 --python-exit-code 1 -P blender/character/modular_builder.py -- \
  --recipe library/character-recipes/ronin-reference.json --out output/character/ronin.blend
... -- --recipe <r> --turnaround output/character/t.png --light neutral      # front/3-4/side/back
... -- --recipe <r> --turnaround output/character/t.png --light cinematic
... -- --recipe <r> --pose chudan --still output/character/s.png
... -- --recipe <r> --portrait --light neutral --still output/character/material-check.png
... -- --recipe <r> --poses furikaburi,kiri-oroshi-contact,kiri-oroshi-finish,zanshin \
       --poses_out output/character/slash.png --still x                      # prove it animates

# the gate
nice -n 10 $B -b -t 2 --python-exit-code 1 -P blender/character/part_validator.py -- \
  --recipe library/character-recipes/ronin-reference.json --report output/character/validate.json
```

## The skeleton

The same joints and the same names as `engine/figure.js` and `blender/character/rig_trellis.py`, so
`library/poses.json` drives it directly:

```
root → hips → torso → upper → neck → head
upper → {r,l}C → {r,l}S → {r,l}E → {r,l}T → {r,l}H        (clavicle, shoulder, elbow, twist, hand)
root  → {r,l}thigh → {r,l}shin → {r,l}foot
hips  → hakama
```

Empties carry the kinematics (an exact port of `applyPose` + `solveLegs`, including the two-bone leg IK). A
deform armature follows them. **Rigid parts follow the joint empties and flexible parts skin across 2–3 bones.**
A bone's rest orientation has nothing to do with its empty's, so the bones are driven by the empty's *delta*
from rest (`Rig.sync_bones`), never by a Copy Transforms constraint — a constraint shears every skinned part.

## Slots and layer order

A higher layer sits over a lower one. `part_registry.py --slots` prints this table live.

| layer | slot | what goes there |
|---:|---|---|
| 15 | `hand` | folded fingers |
| 18 | `foot` | tabi + zori, war boots |
| 20 | `torso` | the kimono body: the sheets everything else layers onto |
| 22 | `thigh` / `shin` | the hakama legs — **two real legs**, one per bone |
| 25 | `sleeve_upper` / `forearm` | arm sleeves, kote |
| 30 | `neck` | the column between collar and mask |
| 35 | `hair` | folded hair, topknot |
| 40 | `face` | the mask: nose ridge, eye slits, chin |
| 45 | `collar` | eri: the crossed lapels, **left over right** |
| 50 | `obi` | the sash, its knot and cord |
| 55 | `sleeve_hanging` | tamoto: the wide sleeve as a separate folded bag |
| 60 | `armor` | sode, do, the hakama apron and koshiita |
| 70 | `accessory` | katana, cords, tassels |
| 90 | `hat` | kasa, hachigane |

## Adding a part

1. Write a builder in `part_registry.py` and register it:

```python
@part('kasa_wide', slot='hat', socket='head_top', bone='head', size=(0.85, 1.15),
      material='washi_hat', ribs=22, radius=0.40)       # extra kwargs = its documented parameters
def kasa_wide(ctx, P, rnd):
    """One line saying what it is: this shows up in the table."""
    S = ctx.socket                      # where it clips on, in the rig's rest pose
    ...
    return ctx.add('kasa', bm, [ctx.mat('washi_hat'), ctx.mat('washi_shade')], thickness=0.0075)
```

2. Build it as a **folded shell**, not a solid: flat facets, thickness from `ctx.add(thickness=…)` (the rim
   gets the second material, so the cut edge of the sheet reads), an **overlap** with its neighbours at the
   joint, and a `ctx.gap(...)` dark slot wherever two sheets meet.
3. Flexible parts (sleeves, hakama) declare `rigid=False` and `bones=['lE','lS','lT']` — written for the LEFT
   side; the builder mirrors them for the right.
4. Add it to a recipe and run the validator. It is not in the library until that exits 0.
5. Important slots carry **2-3 variants** (kasa wide/narrow, mask angular/long, sleeve wide/narrow, hakama
   pleated/plain). `part_registry.py` warns when a slot drops below two.

## Recipe format

```jsonc
{
  "id": "ronin-reference",
  "proportion": "standard",            // which cut of part the recipe wants
  "glow": [1.0, 0.55, 0.18],           // amber = human, crimson = demonic (AGENTS.md rule 4)
  "glow_strength": 3.0,
  "pose": "neutral",                   // default pose, from library/poses.json
  "pose_overrides": {"stance": 0.34},
  "paper": {"washi_natural": "card_indigo"},   // re-dye the whole character by remapping sheets
  "parts": [
    {"part": "kasa_wide", "scale": 1.0, "params": {"radius": 0.45}},
    {"part": "katana_sheathed", "sockets": ["hip_side.L"]}   // one side only
  ]
}
```

Existing parts build a new character entirely from a recipe.

```jsonc
{ "id": "armoured-warrior", "extends": "ronin-reference.json",
  "swap": [{"part": "hachigane"}, {"part": "kimono_plain"}],   // by slot
  "add":  [{"part": "sode_lamellar"}, {"part": "do_plates"}],  // stack distinct armor pieces
  "drop": ["tassels"],
  "paper": {"washi_natural": "card_indigo"} }
```

A swap takes over its part's slot on the specified sockets. Omit `sockets` to replace all the normal
mounts for that part. Set `"sockets": ["elbow.R"]` to swap only the right sleeve, as the
[Wayfarer](../library/character-recipes/wayfarer.json) does. Armor and accessories use the part name as well as
the socket, so distinct plates can stack. A recipe inherits the parent's paper palette and overrides individual
sheet names. The builder rejects incompatible sockets, duplicate mounts, invalid scale, unknown parameter names
and circular inheritance.

## Materials and folds

Each sheet lives in `library/paper-materials/`. The master material uses two crossing fiber fields and finer
pulp grain to give the surface a woven finish. The mesh stores this grain in rest-pose `PaperGrain` UVs. The continuous garment wraps carry their grain across folds. The closed wraps have one marked seam.
When the sleeves bend, the surface pattern moves with them. Planar garment UVs use one UV unit per metre.
The kasa uses an angular coordinate around the brim with the radius in metres. Add a sheet by copying and
renaming a material JSON, then use `paper` in a recipe to map an existing sheet to it.

The hat's ribs and rim, sleeve creases and mask opening are geometry. A narrow amber layer sits behind the
eye opening and the paper around it carries a low glow. Indigo and charcoal remain available for armour.

## Cast a Blender film

```bash
npm ci
npx playwright install chromium
node tools/export_motion.mjs film/motion-test.json

blender -b --python-exit-code 1 -P blender/film_blender.py -- \
  --film film/motion-test.json \
  --times 0.5,2.0 --out output/blender/modular-proof
```

The Blender film uses the existing world-space performance and camera export. The catalog chooses the modular
recipe from the film cast. Use `--recipes hero=ronin-reference,foe=gold-armour` to override a film cast.
Use `--model ronin_base` when comparing the original generated mesh. The film carries the performance's animated sword prop outside the body rig.
The motion export currently accepts films using `engine/motion.html`. To use an installed copy of Chromium,
set `PAPERCINEMA_CHROMIUM` to its executable path. Use `--no-denoise` in the Blender commands on builds
without Cycles denoising support.

## Render the catalogue shot

```bash
blender -b --python-exit-code 1 -P blender/character/character_shot.py -- \
  --recipe ronin-reference --frames 1-12 --out output/character/shot
```

The Kaggle render job runs this entry point and encodes the PNG sequence only after it verifies the frame range.
Use `bash gpu/kaggle_blender/run.sh pack` to package the current recipes and paper sheets, then `push` to
start the job and `get` to retrieve the result.

## Export a character to Unreal

```bash
blender -b --python-exit-code 1 -P blender/character/export_character.py -- \
  --recipe library/character-recipes/ronin-reference.json --out output/unreal/ronin.fbx
```

For the standalone kasa, add `--part kasa_wide` to the same command.

The export writes the bind-pose skeletal mesh, its `PC_Rig_v1` bone hierarchy, weights, paper edge geometry,
UVs and a `.materials.json` sidecar. Every visible rigid sheet has one bone at full weight. Flexible sleeves
and trousers keep their blended weights. Internal Blender light sources stay in Blender.

Import the first FBX as a **Skeletal Mesh** to create the shared skeleton. On subsequent variants select that
skeleton. Check that the character is upright, faces forward in your stage, and measures approximately 180 cm.
Use the accompanying sheet values and grain UVs to build material instances in Unreal. Keep the angular hat
mapping and the eye emission separate from the body paper. The bind-pose export carries geometry and shader
inputs. The Cycles shading graph, camera animation and final film live in their respective tools.
[Unreal's Skeletal Mesh FBX guide](https://dev.epicgames.com/documentation/unreal-engine/fbx-skeletal-mesh-pipeline-in-unreal-engine)

## Validation rules (the gate)

`part_validator.py` runs every check on every object, then sweeps the poses
`neutral, jodan, crouch-load, airborne-guard, kesa-finish` (standing, arms overhead, deep crouch, jump tuck,
full slash — all real poses from `library/poses.json`).

| check | fails when |
|---|---|
| `material` | a mesh has an empty material slot |
| `paper_uv` | a part is missing rest-pose grain UVs |
| `continuous_grain` | authored grain jumps across a shared garment edge with no marked seam |
| `scale` | object scale is not 1 (the fibre-size failure) |
| `fibre` | the sheet's density is outside `WASHI_FIBRE_RANGE` |
| `pivot` | the part has no rigid parent or skin binding |
| `socket` | the geometry is more than 35 cm (60 cm for armour/accessories) from the socket it declared |
| `self_intersect` | more than 1.2 overlapping face pairs per face — a sheet passing through itself |
| `spike` | modifiers grow the part by over 35 % of its own size (the classic solidify blow-up at a sharp crease) |
| `joint_gap` | two neighbouring parts open more than **4.5 cm** apart *in any pose in the sweep* |
| `silhouette` | the figure breaks into more than 2 pieces, or fills under 16 % / over 88 % of its own box, from the front or the side |

## The quality target

`library/character-recipes/ronin-reference.json` is the locked target, built to match
`research/ref-origami-samurai-standing.jpg`. What has to be true of it, and of anything that replaces it:

- a **pleated kasa**: radial ribs that fold up *and* in, a rolled rim, and a dark cave under the brim;
- an **angular mask** with a nose ridge, cut cheek planes and eye slits the lantern burns through;
- **big flat shoulder planes** running from the neck out to the shoulder and down to the sternum;
- **crossed lapels, left over right**, with a dark seam slot behind the overlap;
- a wrapped **obi** that reads as two passes of one strip, with a knot and a cord;
- **wide hanging sleeves** that are separate folded bags, open and lit inside;
- **two real pleated hakama legs** down to pointed tabi — the single biggest failure of the fused models;
- paper thickness visible at every cut edge, and a dark gap wherever two sheets meet.

Verify it the way a studio does: `--turnaround` under **both** `--light neutral` and `--light cinematic`,
plus a pose sweep, and look at every still. `python3 tools/ai.py review <png> "compare to a folded-paper
samurai: what is wrong?"` is a free second opinion (AGENTS.md rule 02) and costs nothing.

## Known weak spots

- The pose sweep proves the parts stay joined; it does not prove the *cloth* reads — skinned sleeves and
  hakama interpolate linearly across 2-3 bones, so a deep crouch pinches the hakama a little.
- The builder preserves overlapping sheet geometry. Some hidden faces remain under armor plates.
- The katana is a folded paper prop here; `rig_trellis.make_katana()` is the real-metal blade.
- No hair or cloth simulation: everything is folded sheets, by choice.

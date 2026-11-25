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
and joined, with crisp planes, deliberate overlaps, visible thickness and dark seams between sheets.

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
B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
python3 blender/character/part_registry.py                    # every part, slot, socket and bind
python3 blender/character/part_registry.py --slots            # the slot table only

# build, pose, render
nice -n 10 $B -b -t 2 -P blender/character/modular_builder.py -- \
  --recipe library/character-recipes/ronin-reference.json --out output/character/ronin.blend
... -- --recipe <r> --turnaround output/character/t.png --light neutral      # front/3-4/side/back
... -- --recipe <r> --turnaround output/character/t.png --light cinematic
... -- --recipe <r> --pose chudan --still output/character/s.png
... -- --recipe <r> --poses furikaburi,kiri-oroshi-contact,kiri-oroshi-finish,zanshin \
       --poses_out output/character/slash.png --still x                      # prove it animates

# the gate
nice -n 10 $B -b -t 2 -P blender/character/part_validator.py -- \
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
deform armature follows them, so **rigid parts parent to a bone and flexible parts skin across 2-3 bones**.
A bone's rest orientation has nothing to do with its empty's, so the bones are driven by the empty's *delta*
from rest (`Rig.sync_bones`), never by a Copy Transforms constraint — a constraint shears every skinned part.

**Cloth bones.** Two of the 25 bones are not body: `lSleeve` / `rSleeve` hang off the forearm and are aimed at
the ground every frame by `Rig._hang_sleeves()`, the port of `engine/figure.js` `hangCloth()`. Without them a
wide sleeve follows the arm rigidly and an overhead cut buries the face in its own tamoto. A bone with no
child states its own tail in `part_registry.TAIL`, otherwise it gets a stub tail pointing up and the skin
weights — inverse distance to the bone's rest segment — hand its cloth to the arm instead.

A part can also ask for `skin='hang'` (see `tamoto_wide`), which weights it between the body it is **sewn** to
and its own cloth bone by height, smoothstepped. Inverse distance cannot express that: a kimono sleeve's top
sits right on the shoulder bone, so by distance the shoulder wins everywhere and the whole bag swings over the
head. Use it only for cloth that is meant to leave the limb — `tamoto_narrow`, the tight fighting sleeve,
measured *worse* when hung and stays skinned to the arm. `blender/check_sleeve.py` measures the result.

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

A second character is made by **swapping parts only**, never by touching `blender/`:

```jsonc
{ "id": "armoured-warrior", "extends": "ronin-reference.json",
  "swap": [{"part": "hachigane"}, {"part": "kimono_plain"}],   // by slot
  "add":  [{"part": "sode_lamellar"}, {"part": "do_plates"}],  // armor/accessory slots hold several
  "drop": ["tassels"],
  "paper": {"washi_natural": "card_indigo"} }
```

`scale` must stay inside the part's approved `size` range or the build fails loudly. Scaling transforms the
**mesh**, never the object: object scale stays 1 so the washi fibre stays world-size.

## Materials: one family, world-scale fibre

Every sheet is a JSON file in `library/paper-materials/`: paper type, base colour, fibre density and
**direction** (`lengthwise` on sleeves, `radial` on the kasa, `vertical` along the folds of a hakama),
roughness, thickness, fold darkening, edge wear, translucency, inner-light response and the SHIMI stain hook.
`pm.PC_Washi_Master(key, scale=…)` builds it.

**The rule that keeps breaking and must not:** the fibre field is read in *object* space, so a part scaled by
`s` must ask for `fibre_scale = WASHI_FIBRE * s`. Get it wrong and the fibres look like rope on the hat and
vanish on the sleeves. The builder keeps every object at scale 1 and the validator checks both the scale and
the per-sheet density against `pm.WASHI_FIBRE_RANGE`.

Sheets today: `washi_natural`, `washi_bleached`, `washi_hat`, `washi_shade`, `card_indigo`, `card_charcoal`,
and `seam_shadow` — which is not a sheet at all but the dark slot that goes **behind** every overlap.

## Validation rules (the gate)

`part_validator.py` runs every check on every object, then sweeps the poses
`neutral, jodan, crouch-load, airborne-guard, kesa-finish` (standing, arms overhead, deep crouch, jump tuck,
full slash — all real poses from `library/poses.json`).

| check | fails when |
|---|---|
| `material` | a mesh has an empty material slot |
| `scale` | object scale is not 1 (the fibre-size failure) |
| `fibre` | the sheet's density is outside `WASHI_FIBRE_RANGE` |
| `pivot` | the part is not bound to a bone (parented or skinned) |
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
- a **wrapped kimono of few, big sheets**: ONE diagonal sheet (left over right) across the chest, a second sheet
  crossing under it a full step behind, both folded over the shoulder into flat shoulder planes and a back yoke,
  both tucked under the obi; a folded lapel band rides proud along each diagonal;
- a **standing collar in two steps** (outer collar + inner juban collar) rising from the lapels to the nape, with a
  real slot between it and the neck;
- a proud **obi** the sheets tuck under: band, second pass, keeper-loop knot with two tails, cord, koshiita behind;
- **wide sleeve bags in two tiers** cut from one cone (`SLV_TOP` → `SLV_MOUTH`): the upper tier fans out from under
  the shoulder lip and is cut on a diagonal, the hanging bag steps out beneath it to a big slanted OPEN mouth with a
  turned-back cuff; valley creases between the ridges, like the kasa;
- a **diagonal robe skirt** below the obi that continues the lapel's line, then **two real knife-pleated hakama legs**
  with an open front split, and a flared lower tier stepping out from under the long pleated sheet;
- silhouette: sleeves ≈ 2.2× the waist, hem ≈ 1.6× the waist — never a column;
- paper thickness visible at every cut edge, and a dark gap wherever two sheets meet.

Verify it the way a studio does: `--turnaround` under **both** `--light neutral` and `--light cinematic`,
plus a pose sweep, and look at every still. `python3 tools/ai.py review <png> "compare to a folded-paper
samurai: what is wrong?"` is a free second opinion (AGENTS.md rule 02) and costs nothing.

## Judge the geometry in clay first

Materials and light hide weak form. Strip them: a Workbench render with no lights and no materials (cavity
shading only) shows whether the SHEETS read. Torso and lapels share `kimono_sheet()`, both sleeve parts share
`sleeve_ring()`, both leg parts share `leg_ring()` — change the frame, not one part, or the layers stop lining up.
Outer sheets take no inner glow (`ctx.lit(0)`); only sheets seen from inside (sleeve bag, lower hem tier, juban)
take a little, or the cinematic render washes the folds out.

## Known weak spots

- In the library's `neutral` pose the arms swing 7° inward, so the hands sit behind the hip; the recipe's own
  `pose_overrides` hang them straight so they show below the sleeve mouths.
- Arms overhead (jodan) push the wide sleeves through the kasa brim.

- The pose sweep proves the parts stay joined; it does not prove the *cloth* reads — skinned sleeves and
  hakama interpolate linearly across 2-3 bones, so a deep crouch pinches the hakama a little.
- `hide_internal_faces` only removes faces sealed inside another **rigid** part on the **same** bone, so
  there is still hidden geometry under the armour plates.
- The katana is a folded paper prop here; `rig_trellis.make_katana()` is the real-metal blade.
- No hair or cloth simulation: everything is folded sheets, by choice.

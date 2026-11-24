# UNREAL EXPORT: our rigged origami character → a verified Unreal-ready FBX

There is no Unreal Engine and no GPU on this machine. This page is the **bridge for the day there is one**:
the exact recipe, the script that runs it, and the round-trip checks that prove the file is right before anyone
opens Unreal. Everything here was run and verified on this machine (Blender 4.5.16 LTS, 4 CPU cores).

```bash
B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
# 1. the Skeletal Mesh: mesh + skeleton, no animation
nice -n 10 $B -b -t 2 -P blender/character/export_unreal.py -- \
    --model ronin_base --names ue5 --out output/unreal/ronin_skeletal.fbx
# 2. an Animation Sequence on the SAME skeleton, with root motion
nice -n 10 $B -b -t 2 -P blender/character/export_unreal.py -- \
    --model ronin_base --names ue5 --motion output/dash-test.motion.json --cid hero --f0 0 --f1 48 \
    --out output/unreal/ronin_dash.fbx
# 3. an A-pose retarget source (mesh only; a DIFFERENT rest pose, never pair it with 2)
nice -n 10 $B -b -t 2 -P blender/character/export_unreal.py -- \
    --model ronin_base --names ue5 --a-pose --out output/unreal/ronin_apose.fbx
# verify any FBX (re-imports it into a clean file and checks everything below)
nice -n 10 $B -b -t 2 -P blender/character/export_unreal.py -- --verify output/unreal/ronin_dash.fbx
```
`--motion` takes an `output/<film>.motion.json` from `tools/export_motion.mjs`. `--names ue5|humanoid|ours`.
`--report path.json` writes the verification. The script exits after printing `VERIFY PASS` or `VERIFY FAIL`.

## 1. Where the settings come from

Epic's **Send to Unreal** add-on (github.com/EpicGames/BlenderTools, **MIT**, installed here in
`~/.config/blender/4.5/scripts/addons/send2ue` and `ue2rigify`) carries Epic's own FBX export settings in
`send2ue/resources/settings.json` under `blender/export_method/fbx/*`. Those are copied verbatim into
`EPIC_FBX` in `blender/character/export_unreal.py`:

| Group | Setting | Value | Why |
|---|---|---|---|
| transform | `global_scale` / `apply_scale_options` | `1.0` / `FBX_SCALE_NONE` | 1 Blender unit = 1 m; the FBX header carries the cm factor |
| transform | `axis_forward` / `axis_up` | `Y` / `Z` | Blender Z-up, Y-forward → Unreal Z-up, X-forward |
| transform | `apply_unit_scale` / `bake_space_transform` | `True` / `False` | baking the space transform is what twists bind poses |
| armature | `primary_bone_axis` / `secondary_bone_axis` | `Y` / `X` | Unreal's bone convention |
| armature | `add_leaf_bones` | `False` | leaf bones become junk `*_end` bones in the UE skeleton |
| armature | `use_armature_deform_only` | `False` | keeps `root` (a non-deform bone) in the file — **root motion needs it** |
| geometry | `mesh_smooth_type` | `FACE` | faceted paper; smoothing groups, not edges |
| animation | `bake_anim_use_all_bones`, `bake_anim_force_startend_keying` | `True` | every bone keyed on every frame; first and last frame always keyed |
| animation | `bake_anim_simplify_factor` | `0.0` | no curve simplification: the engine already shaped the motion |

## 2. Which exporter actually writes the file

`--exporter blender` (the default) uses **Blender 4.5's own `io_scene_fbx`** driven with the settings above.
`--exporter epic` uses send2ue's patched copy of it. Use the default. Measured here:

* send2ue monkey-patches `io_scene_fbx` to write the armature, the bind pose and the animation at FBX scale
  100 with the object origin applied. That patch dates from the Blender 2.8 era. On **Blender 4.5 the plain
  settings already round-trip exactly right** (175 cm, Z up, root at the origin, root motion at 1:1 metres),
  so the patch buys nothing.
* send2ue's patched animation writer is **broken on Blender 4.5**: its vendored `fbx_animations_do` calls the
  pre-4.0 curve API `AnimationCurveNodeWrapper.add_keyframe()`, which Blender 4.0 replaced with the vectorised
  `set_keyframes()`. Any export with `bake_anim` on dies with
  `'AnimationCurveNodeWrapper' object has no attribute 'add_keyframe'`. Giving the class the old method back
  makes the export finish but writes **one keyframe per curve**. So `--exporter epic` is mesh-only.

Keep the add-on installed anyway: the day an Unreal machine exists, **Pipeline > Send to Unreal** pushes
straight into a running editor over Epic's remote-execution link, and `ue2rigify` is the Unreal-side retarget
tool. The file route above is for everything before that.

## 3. Bone names

`--names ue5` writes the UE5 Mannequin spelling, which gives the best automatic chain detection in Unreal's
IK Retargeter. `--names humanoid` writes the Mixamo spelling (`rig_trellis.HUMANOID`). The map lives in
`UE5` in `export_unreal.py`:

| ours | UE5 | ours | UE5 |
|---|---|---|---|
| `root` | `root` | `clavicle.L/R` | `clavicle_l/r` |
| `hips` | `pelvis` | `shoulder.L/R` | `upperarm_l/r` |
| `waist` | `spine_01` | `elbow.L/R` | `lowerarm_l/r` |
| `chest` | `spine_03` | `twist.L/R` | `lowerarm_twist_01_l/r` |
| `neck` | `neck_01` | `hand.L/R` | `hand_l/r` |
| `head` | `head` | `thigh/shin/foot.L/R` | `thigh_l/r`, `calf_l/r`, `foot_l/r` |
| | | `sleeve.L/R` | `sleeve_l/r` (ours; no Mannequin equivalent) |

**Rename the bones, never the vertex groups.** Blender renames a bone's vertex group with it; renaming the
groups first makes every bone rename collide ("New bone name collides with an existing vertex group name") and
the sync is silently skipped. `rig_trellis.export_names()` renames groups first and then bones, so it hits
this; `export_unreal.rename()` renames bones only.

## 4. The three files, and why they are three

| File | Contents | Becomes in Unreal |
|---|---|---|
| `ronin_skeletal.fbx` | mesh + skeleton, the model's own rest pose, no animation | Skeletal Mesh + Skeleton |
| `ronin_dash.fbx` | the same skeleton, one baked action with root motion | Animation Sequence (**Import Animations** on, same Skeleton asset) |
| `ronin_apose.fbx` | mesh only, A-pose **rest** | an IK Retarget source only |

The A-pose file has a **different rest pose** (`rig_trellis.a_pose()` applies the pose as the new rest, which
also invalidates the measurements the rig_trellis driver uses, so no animation can be baked after it). Never
import it onto the skeleton the animation uses: Unreal will accept it and every bone will be 45° out.

**The katana is not in any of them.** It is not skinned; `build_character(..., katana=False)` leaves it out.
In Unreal it is a separate Static Mesh attached to a socket on `hand_r`. Same for the second sword.

## 5. What `--verify` proves

It re-imports the FBX into a factory-fresh Blender file and asserts (`verify()` in `export_unreal.py`):

| Check | Measured on `ronin_dash.fbx` |
|---|---|
| `scale` | imported height **1.750 units = 175 cm in Unreal** (the engine's figure is 1.75 m) |
| `on_the_floor` | lowest vertex z = 0.000 |
| `z_up` | head z 1.360 > hips z 0.700 |
| `root_bone` | a bone called `root`, at (0, 0, 0), with no parent |
| `root_is_the_top` | children of root: `pelvis`, `thigh_l`, `thigh_r` |
| `unit_scale` | scene `scale_length` = 1.0 |
| `skin_weights` | 19 vertex groups, every one matching a bone |
| `armature_modifier` | every mesh has an Armature modifier |
| `root_motion` | the root bone travels **7.58 m** over the clip (source motion: 7.48 m — the extra is the curve's own run-up) |
| `baked_curves` | 249 f-curves over 75 data paths, frames 2..50 (49 frames at 24 fps) |
| `bone_names` | all 24 expected UE5 names present |

Re-import with `ignore_leaf_bones=False`, or the five terminal bones (`head`, `hand_l/r`, `foot_l/r`) are
dropped by Blender's importer and the check reports them missing when they are in fact in the file.

## 6. On the Unreal side (for the day it exists)

1. Import `ronin_skeletal.fbx`: Skeletal Mesh, **Import Mesh** on, **Import Animations** off, Import Uniform
   Scale 1.0, **Convert Scene** on, **Force Front XAxis** off.
2. Import `ronin_dash.fbx` with **Skeleton** set to the asset from step 1 and **Import Animations** on.
3. On the Animation Sequence enable **Enable Root Motion** and set **Root Motion Root Lock** to *Ref Pose*.
   The travel is already on the `root` bone, in metres; no scaling.
4. Sockets: `hand_r` → `katana`, `head` → `kasa`. The inner lantern is an Unreal point light on `spine_03`,
   not geometry.
5. Retarget to the Mannequin with an IK Rig per skeleton + an IK Retargeter; use `ronin_apose.fbx` as the
   source pose if the chains do not line up. `ue2rigify` (installed, MIT) does the Blender half.
6. Render with Movie Render Queue; `chisio23/Unreal_Tools` (MIT) has a 73-line MRQ job script and a
   Level-Sequence/CineCamera builder worth copying when the KUROKO camera is exported — see
   `docs/TOOLS-EVALUATED.md`.

## 7. Files

| File | What |
|---|---|
| `blender/character/export_unreal.py` | the exporter + the verifier (this page is its guide) |
| `~/.config/blender/4.5/scripts/addons/send2ue`, `ue2rigify` | Epic's add-ons, MIT, installed |
| `output/unreal/*.fbx`, `output/unreal/verify-*.json` | the exported files and their verification reports |

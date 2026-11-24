"""EXPORT_UNREAL: our rigged origami character → a VERIFIED Unreal-ready FBX, through Epic's own
Send to Unreal exporter (github.com/EpicGames/BlenderTools, MIT). Recipe: docs/UNREAL-EXPORT.md.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  # the Skeletal Mesh (mesh + skeleton, the model's own rest pose, no animation)
  nice -n 10 $B -b -P blender/character/export_unreal.py -- --model ronin_base --out output/unreal/ronin_skeletal.fbx
  # an Animation Sequence on the SAME skeleton, with root motion
  nice -n 10 $B -b -P blender/character/export_unreal.py -- --model ronin_base \
      --motion output/dash-test.motion.json --cid hero --f0 0 --f1 48 --out output/unreal/ronin_dash.fbx
  # an A-pose retarget source (mesh only -- a different rest pose, so never pair it with the anim above)
  ... --model ronin_base --a-pose --out output/unreal/ronin_apose.fbx
  # verify any FBX we made (re-imports it into a clean file and checks scale, axis, bones, root motion)
  nice -n 10 $B -b -P blender/character/export_unreal.py -- --verify output/unreal/ronin_dash.fbx

  --names ue5       pelvis/spine_01/upperarm_l...  (UE5 Mannequin spelling, best auto-retarget chains)
  --names humanoid  Hips/Spine/LeftArm...          (Mixamo spelling, rig_trellis.HUMANOID; the default)
  --names ours      root/hips/shoulder.L...        (no renaming)

  --exporter blender  (default) Blender 4.5's own io_scene_fbx, driven with Epic's settings
  --exporter epic     send2ue's patched copy of io_scene_fbx -- MESH ONLY, it cannot write animation on
                      Blender 4.5 (its vendored `fbx_animations_do` calls the pre-4.0 `add_keyframe` API)

The settings in EPIC_FBX below are read straight out of send2ue/resources/settings.json
(`blender/export_method/fbx/*`), i.e. they are the ones Epic's own Send to Unreal pushes to Unreal. On
Blender 4.5 those settings alone already round-trip correctly (175 cm tall, Z up, root at the origin,
root motion at 1:1 metres); send2ue's extra monkey-patching of io_scene_fbx fixed Blender-2.8-era scale
bugs and is no longer needed. Keep the addon installed for the live "Pipeline > Send to Unreal" push the
day an Unreal machine exists; use `--exporter blender` for files.
"""
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import rig_trellis as rt                                     # noqa: E402

# UE5 Mannequin bone spelling, keyed by OUR bone names (rig_trellis.BONES).
UE5 = {
    'root': 'root', 'hips': 'pelvis', 'waist': 'spine_01', 'chest': 'spine_03', 'neck': 'neck_01', 'head': 'head',
    'clavicle.L': 'clavicle_l', 'shoulder.L': 'upperarm_l', 'elbow.L': 'lowerarm_l', 'twist.L': 'lowerarm_twist_01_l', 'hand.L': 'hand_l',
    'clavicle.R': 'clavicle_r', 'shoulder.R': 'upperarm_r', 'elbow.R': 'lowerarm_r', 'twist.R': 'lowerarm_twist_01_r', 'hand.R': 'hand_r',
    'thigh.L': 'thigh_l', 'shin.L': 'calf_l', 'foot.L': 'foot_l',
    'thigh.R': 'thigh_r', 'shin.R': 'calf_r', 'foot.R': 'foot_r',
    'sleeve.L': 'sleeve_l', 'sleeve.R': 'sleeve_r',
}

# Epic's own FBX export defaults, read out of send2ue/resources/settings.json (blender/export_method/fbx/*).
EPIC_FBX = dict(
    use_custom_props=False,
    global_scale=1.0, apply_scale_options='FBX_SCALE_NONE', axis_forward='Y', axis_up='Z',
    apply_unit_scale=True, bake_space_transform=False,
    mesh_smooth_type='FACE', use_subsurf=False, use_mesh_modifiers=True, use_mesh_modifiers_render=True,
    use_mesh_edges=False, use_tspace=False,
    primary_bone_axis='Y', secondary_bone_axis='X', armature_nodetype='NULL',
    use_armature_deform_only=False, add_leaf_bones=False,
    bake_anim=True, bake_anim_use_all_bones=True, bake_anim_force_startend_keying=True,
    bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
    use_metadata=True,
)
# the rest of what io_scene_fbx's save() wants, with send2ue's values
SAVE_REST = dict(
    use_selection=True, use_visible=False, use_active_collection=False,
    object_types={'ARMATURE', 'MESH', 'EMPTY'},
    use_triangles=False, colors_type='SRGB', prioritize_active_color=False,
    use_batch_own_dir=False, batch_mode='OFF',
    bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
    path_mode='AUTO', embed_textures=False, use_space_transform=True,
)


def rename(ch, style):
    """Rename the BONES only: Blender renames the matching vertex groups with them, so renaming the groups
    first (as rig_trellis.export_names does) makes every bone rename collide and the sync is skipped."""
    table = {'ue5': UE5, 'humanoid': rt.HUMANOID}.get(style)
    if not table:
        return
    for b in ch['rig'].data.bones:
        if b.name in table:
            b.name = table[b.name]


def need_send2ue():
    import addon_utils
    if not hasattr(bpy.context.scene, 'send2ue'):
        addon_utils.enable('send2ue', default_set=False, persistent=True)
    assert hasattr(bpy.context.scene, 'send2ue'), 'send2ue addon is not installed (see docs/UNREAL-EXPORT.md)'


def export(objects, path, scene_start=None, scene_end=None, anim=True, exporter='blender'):
    """Write an FBX with Epic's settings. exporter='blender' (default) uses Blender 4.5's own io_scene_fbx;
    exporter='epic' uses send2ue's patched copy of it (mesh only -- see docs/UNREAL-EXPORT.md)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    sc = bpy.context.scene
    if scene_start is not None:
        sc.frame_start, sc.frame_end = scene_start, scene_end
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    kw = dict(EPIC_FBX, **SAVE_REST)
    kw['bake_anim'] = bool(anim)
    kw['filepath'] = os.path.abspath(path)
    if exporter == 'epic':
        need_send2ue()
        from send2ue.core.io import fbx
        fbx.export(**kw)
    else:
        kw.pop('use_space_transform', None)
        bpy.ops.export_scene.fbx(**kw)
    return os.path.abspath(path)


# --------------------------------------------------------------------------------------------- verification
def verify(path, expect_names=None):
    """Re-import the FBX into a clean scene and check everything Unreal cares about."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.abspath(path), automatic_bone_orientation=False,
                             ignore_leaf_bones=False, force_connect_children=False)
    rigs = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    r = {'file': path, 'size_kb': round(os.path.getsize(path) / 1024, 1),
         'armatures': len(rigs), 'meshes': len(meshes), 'checks': {}, 'fail': []}
    if not rigs:
        r['fail'].append('no armature in the FBX')
        return r
    rig = rigs[0]
    bones = {b.name: b for b in rig.data.bones}
    r['bones'] = len(bones)
    r['bone_names'] = sorted(bones)

    def ck(name, ok, detail):
        r['checks'][name] = {'ok': bool(ok), 'detail': detail}
        if not ok:
            r['fail'].append(f'{name}: {detail}')

    # --- scale: the mesh must come back about 1.7 m tall in Blender units (so 170 cm in Unreal)
    zs = []
    for m in meshes:
        for v in m.data.vertices:
            zs.append((m.matrix_world @ v.co).z)
    if zs:
        h = max(zs) - min(zs)
        ck('scale', 1.4 < h < 2.1, f'imported height {h:.3f} Blender units (= {h * 100:.0f} cm in Unreal)')
        ck('on_the_floor', abs(min(zs)) < 0.06, f'lowest vertex z = {min(zs):.3f}')
    # --- axis: Z up (the head above the hips), Y forward in Blender == Unreal's +X
    root = next((b for n, b in bones.items() if n.lower() in ('root', 'Root'.lower())), None)
    hips = next((b for n, b in bones.items() if n.lower() in ('pelvis', 'hips')), None)
    head = next((b for n, b in bones.items() if n.lower() == 'head'), None)
    if hips and head:
        ck('z_up', head.head_local.z > hips.head_local.z + 0.3,
           f'head z {head.head_local.z:.3f} > hips z {hips.head_local.z:.3f}')
    # --- a root bone at the origin, which is what Unreal needs for root motion
    if root is None:
        ck('root_bone', False, 'no bone called root')
    else:
        d = root.head_local.length
        ck('root_bone', d < 0.01 and root.parent is None, f'root at {tuple(round(c, 4) for c in root.head_local)}, parent={root.parent}')
        kids = [b.name for b in bones.values() if b.parent and b.parent.name == root.name]
        ck('root_is_the_top', bool(kids), f'children of root: {kids}')
    # --- unit scale of the imported scene
    ck('unit_scale', abs(bpy.context.scene.unit_settings.scale_length - 1.0) < 1e-6,
       f'scale_length={bpy.context.scene.unit_settings.scale_length}')
    # --- skinning survived
    if meshes:
        groups = set()
        for m in meshes:
            groups |= {g.name for g in m.vertex_groups}
        unknown = sorted(groups - set(bones))
        ck('skin_weights', bool(groups) and not unknown,
           f'{len(groups)} vertex groups, all matching bones' if not unknown else f'groups with no bone: {unknown[:5]}')
        ck('armature_modifier', all(any(md.type == 'ARMATURE' for md in m.modifiers) for m in meshes),
           'every mesh has an Armature modifier')
    # --- animation + root motion
    ad = rig.animation_data
    if ad and ad.action:
        act = ad.action
        fcs = list(rt._fcurves(act))
        r['action'] = act.name
        r['frame_range'] = [round(x, 1) for x in act.frame_range]
        paths = {fc.data_path for fc in fcs}
        rootloc = [fc for fc in fcs if root is not None and f'"{root.name}"' in fc.data_path and fc.data_path.endswith('location')]
        if root is not None:
            trav = 0.0
            for fc in rootloc:
                vals = [kp.co[1] for kp in fc.keyframe_points]
                if vals:
                    trav = max(trav, max(vals) - min(vals))
            ck('root_motion', trav > 0.05,
               f'root bone travels {trav:.3f} units ({trav * 100:.0f} cm) over the clip')
        ck('baked_curves', len(fcs) > 40, f'{len(fcs)} f-curves over {len(paths)} data paths')
        ck('frame_count', act.frame_range[1] - act.frame_range[0] > 1,
           f'frames {act.frame_range[0]:.0f}..{act.frame_range[1]:.0f}')
    else:
        r['action'] = None
    if expect_names:
        missing = [n for n in expect_names if n not in bones]
        ck('bone_names', not missing, f'missing: {missing}' if missing else f'all {len(expect_names)} expected names present')
    r['ok'] = not r['fail']
    return r


def _main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='ronin_base')
    ap.add_argument('--mode', default='heat')
    ap.add_argument('--names', default='humanoid', choices=['ue5', 'humanoid', 'ours'])
    ap.add_argument('--motion')
    ap.add_argument('--cid', default='hero')
    ap.add_argument('--f0', type=int, default=0)
    ap.add_argument('--f1', type=int, default=48)
    ap.add_argument('--pose')
    ap.add_argument('--a-pose', action='store_true')
    ap.add_argument('--out', default='output/unreal/character.fbx')
    ap.add_argument('--verify')
    ap.add_argument('--exporter', default='blender', choices=['blender', 'epic'])
    ap.add_argument('--report')
    a = ap.parse_args(argv)

    if a.verify:
        r = verify(a.verify)
        print(json.dumps(r, indent=1))
        if a.report:
            os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
            json.dump(r, open(a.report, 'w'), indent=1)
        print('VERIFY', 'PASS' if r['ok'] else 'FAIL')
        return

    ch = rt.build_character(a.model, mode=a.mode, katana=False)   # the sword is a separate static mesh on a socket
    anim = False
    if a.motion:
        motion = rt.load_motion(os.path.join(REPO, a.motion) if not os.path.isabs(a.motion) else a.motion)
        rt.bake(ch, motion, a.cid, a.f0, a.f1)
        anim = True
    elif a.pose:
        rt.apply_frame(ch, rt.pose_frame(a.pose))
    if a.a_pose:
        rt.a_pose(ch)
    rename(ch, a.names)
    skins = [ch['mesh'], *ch['feet'], *ch['fists'], *([ch['core']] if ch.get('core') else [])]
    objs = [ch['rig'], *skins]
    f0 = a.f0 + 1 if anim else None
    f1 = a.f1 + 1 if anim else None
    path = export(objs, os.path.join(REPO, a.out) if not os.path.isabs(a.out) else a.out,
                  scene_start=f0, scene_end=f1, anim=anim, exporter=a.exporter)
    print('WROTE', path, os.path.getsize(path), 'bytes')
    names = {'ue5': UE5, 'humanoid': rt.HUMANOID}.get(a.names)
    expect = sorted(set(names.values())) if names else None
    r = verify(path, expect_names=expect)
    print(json.dumps(r, indent=1))
    if a.report:
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        json.dump(r, open(a.report, 'w'), indent=1)
    print('VERIFY', 'PASS' if r['ok'] else 'FAIL')


if __name__ == '__main__':
    _main()

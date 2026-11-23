"""RIG_TRELLIS: turn a TRELLIS model (one static mesh from the owner's reference image) into a character that
fights. Guide: docs/CHARACTER-BLENDER.md.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  # a library pose (library/poses.json), still
  nice -n 10 $B -b -t 2 -P blender/character/rig_trellis.py -- --model ronin_base --pose jodan --out output/character/rig-jodan.png
  # one moment of a film (needs output/<film>.motion.json from tools/export_motion.mjs)
  nice -n 10 $B -b -t 2 -P blender/character/rig_trellis.py -- --motion output/dash-test.motion.json --t 1.11 --out output/character/rig-cut.png
  options: --mode heat|panels|cloak|rigid (how the mesh follows the bones; heat is the default)
  # motion capture: any BVH file, one moment of it
  ... rig_trellis.py -- --bvh take.bvh --t 2.0 --out output/character/rig-bvh.png
  # hand the rig to another tool: A-pose rest + standard humanoid bone names (Hips, Spine, LeftArm, …)
  ... rig_trellis.py -- --a-pose --names humanoid --save output/character/ronin_rig.blend · --view front|q|side|back · --save file.blend

From another Blender script:
  import sys; sys.path.insert(0, 'blender/character'); import rig_trellis as rt
  ch = rt.build_character('ronin_base')                  # mesh + armature + katana + inner lantern
  rt.apply_frame(ch, rt.pose_frame('chudan'))            # a library pose
  motion = rt.load_motion('output/dash-test.motion.json'); rt.bake(ch, motion, 'hero', 20, 40)   # a film

How it works
  * The skeleton has OUR joint names (root, hips, waist, chest, neck, head, clavicle, shoulder, elbow, twist, hand,
    thigh, shin, foot, .L/.R) plus two sleeve bones. Its rest pose is the model's own pose (arms folded in front).
  * The driver takes the WORLD transform of every engine joint (from the film export, or from a Python port of
    figure.js applyPose for library poses) and re-targets it: spine and head take the engine's rotations; the sword
    takes the engine's rotation and a position relative to the shoulders (scaled to this model's arm length); both arms
    are then solved by two-bone IK onto the handle (elbows point where the engine's elbows point), so the two-hand grip
    is exact; legs are two-bone IK to the engine's foot placement, scaled to this model's shorter legs.
  * Axis conversion three.js → Blender: position (x, y, z) → (x, -z, y); quaternion (x, y, z, w) → (w, x, -z, y)
    (the same thing as Euler (rx, ry, rz) → (rx, -rz, ry) in mode 'YZX').
  * Skin. TRELLIS gives ONE fused shell (robe + sleeves + folded arms are a single surface; there is no body under
    it), so the robe is skinned as cloth. Four ways were tried on stills (output/character/rig/attempts-sheet.png):
      "heat"   (default) weld the ~370 loose patches, Blender's automatic bone-heat weights, then a scripted cleanup
               (rigid head + kasa, 4 bones per vertex). The robe drapes from the arms as one cloth. Cleanest.
      "panels" the shell is knife-cut along the collar V, between the hands and under the sleeves; our own region
               weights; an under-robe core glows in the gaps. More origami, but the cut edges look torn.
      "cloak"  our own smooth region weights with no cuts (also the fallback when bone heat fails on a mesh).
      "rigid"  one bone per vertex (hard panels; the faces between panels are removed, so it opens holes).
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
FPS = 24

# ----------------------------------------------------------------------------------------------- axis conversion
C3 = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))            # three.js vector → Blender vector


def v3(p):
    """three.js position → Blender"""
    return Vector((p[0], -p[2], p[1]))


def q3(q):
    """three.js quaternion (x, y, z, w) → Blender 3x3 rotation"""
    return Quaternion((q[3], q[0], -q[2], q[1])).to_matrix()


def TR(pos, rot3):
    m = rot3.to_4x4()
    m.translation = pos
    return m


def swing(a, b):
    """smallest rotation that turns direction a into direction b (3x3)"""
    a, b = Vector(a), Vector(b)
    if a.length < 1e-9 or b.length < 1e-9:
        return Matrix.Identity(3)
    return a.normalized().rotation_difference(b.normalized()).to_matrix()


def ss(a, b, v):
    """smoothstep on numpy arrays (a > b gives a falling step)"""
    t = np.clip((v - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------------------------------------- model specs
# Landmarks in metres for a model scaled to `height` 1.75 (hat included), facing -Y, left side = +x.
# A new TRELLIS model starts from DEFAULT; measure its landmarks once (see the guide, "A new model") and add it here.
DEFAULT = {
    'height': 1.75, 'face': 0,
    'hips': (0, 0.08, 0.70), 'waist_top': (0, 0.09, 0.95), 'chest_top': (0, 0.06, 1.28), 'neck_top': (0, 0.03, 1.36),
    'head_top': (0, -0.02, 1.75),
    'shoulder': (0.25, 0.08, 1.20), 'elbow': (0.42, 0.03, 0.93), 'wrist': (0.07, -0.25, 0.86), 'hand_tip': (0.025, -0.31, 0.85),
    'hip_joint': (0.09, 0.08, 0.66), 'knee': (0.10, 0.03, 0.36), 'ankle': (0.10, 0.08, 0.06), 'toe': (0.10, -0.12, 0.02),
    'sleeve_top': (0.40, -0.06, 0.78), 'sleeve_tip': (0.38, -0.14, 0.26),
    # skin regions (cloak mode)
    'shell_floor': 0.76,                                   # below this height the sleeves hang free of the body column
    'chin': 1.33, 'column_x': 0.27,
    'column_front': [(0.0, -0.27), (0.2, -0.23), (0.4, -0.21), (0.6, -0.17), (0.76, -0.14)],   # (height, front y) of the skirt
    'lantern': [('chest', (0, -0.06, 1.02), 14.0), ('head', (0, -0.02, 1.47), 3.0)],
}
MODELS = {
    'ronin_base': {},                                       # the hero: measured (the DEFAULT values are his)
}
# engine proportions (engine/figure.js) the driver re-targets from
ENGINE = {'hipY': 0.92, 'arm': 0.30 + 0.29, 'leg': 0.46 + 0.44}

BONES = ['root', 'hips', 'waist', 'chest', 'neck', 'head',
         'clavicle.L', 'shoulder.L', 'elbow.L', 'twist.L', 'hand.L', 'sleeve.L',
         'clavicle.R', 'shoulder.R', 'elbow.R', 'twist.R', 'hand.R', 'sleeve.R',
         'thigh.L', 'shin.L', 'foot.L', 'thigh.R', 'shin.R', 'foot.R']
PARENT = {'hips': 'root', 'waist': 'hips', 'chest': 'waist', 'neck': 'chest', 'head': 'neck',
          'thigh.L': 'root', 'shin.L': 'thigh.L', 'foot.L': 'shin.L', 'thigh.R': 'root', 'shin.R': 'thigh.R', 'foot.R': 'shin.R'}
for _s in 'LR':
    PARENT.update({f'clavicle.{_s}': 'chest', f'shoulder.{_s}': f'clavicle.{_s}', f'elbow.{_s}': f'shoulder.{_s}',
                   f'twist.{_s}': f'elbow.{_s}', f'hand.{_s}': f'twist.{_s}', f'sleeve.{_s}': f'elbow.{_s}'})


def model_spec(model, height=None):
    sp = {**DEFAULT, **MODELS.get(model, {})}
    k = (height or sp['height']) / 1.75
    out = {}
    for key, val in sp.items():
        if key == 'lantern':
            out[key] = [(b, tuple(c * k for c in p), e) for b, p, e in val]
        elif key == 'column_front':
            out[key] = [(a * k, b * k) for a, b in val]
        elif isinstance(val, tuple):
            out[key] = tuple(c * k for c in val)
        elif key in ('shell_floor', 'chin', 'column_x'):
            out[key] = val * k
        else:
            out[key] = val
    out['height'] = height or sp['height']
    out['k'] = k
    return out


def side(p, s):
    """mirror a landmark: s = 'L' (+x) or 'R' (-x)"""
    return Vector((p[0] if s == 'L' else -p[0], p[1], p[2]))


# ----------------------------------------------------------------------------------------------- import + material
def import_trellis(model, spec):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(REPO, 'assets', 'models', model + '.glb'))
    new = [o for o in bpy.data.objects if o not in before]
    mesh = [o for o in new if o.type == 'MESH'][0]
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in new:
        if o is not mesh:
            bpy.data.objects.remove(o)
    co = np.array([v.co[:] for v in mesh.data.vertices])
    mn, mx = co.min(0), co.max(0)
    s = spec['height'] / (mx[2] - mn[2])
    co = (co - [(mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, mn[2]]) * s
    a = math.radians(spec.get('face', 0))
    if a:
        x, y = co[:, 0].copy(), co[:, 1].copy()
        co[:, 0], co[:, 1] = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
    mesh.data.vertices.foreach_set('co', co.ravel())
    mesh.data.update()
    mesh.name = 'CHAR_' + model
    return mesh


def paper_material(mesh, glow=1.6, translucency=0.07, demonic=False, relight=0.85):
    """Keep the TRELLIS texture; make it washi: rough, a little light passes through (so the inner lantern shows),
    and the warm areas the reference painted (the lit collar, the sleeve mouths) really emit light."""
    m = mesh.data.materials[0]
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = next((n for n in nt.nodes if n.type == 'TEX_IMAGE'), None)
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    bsdf.inputs['Roughness'].default_value = 0.82
    bsdf.inputs['Metallic'].default_value = 0.0
    if tex is None:
        return m
    hsv = nt.nodes.new('ShaderNodeSeparateColor'); hsv.mode = 'HSV'
    nt.links.new(tex.outputs['Color'], hsv.inputs['Color'])
    # RELIGHT: TRELLIS bakes the reference image's light and shadow into the texture (the unseen back and everything
    # that was hidden behind the sleeves is brown or black). Keep the texture only as soft fold shading on clean
    # paper, so OUR lights decide what is bright and what is dark.
    shade = nt.nodes.new('ShaderNodeMapRange'); shade.inputs['To Min'].default_value = 1.0 - relight * 0.55; shade.inputs['To Max'].default_value = 1.0
    nt.links.new(hsv.outputs['Blue'], shade.inputs['Value'])
    pap = nt.nodes.new('ShaderNodeMixRGB'); pap.blend_type = 'MIX'; pap.inputs['Fac'].default_value = relight
    pap.inputs['Color2'].default_value = (0.86, 0.82, 0.74, 1)
    nt.links.new(tex.outputs['Color'], pap.inputs['Color1'])
    mul = nt.nodes.new('ShaderNodeMixRGB'); mul.blend_type = 'MULTIPLY'; mul.inputs['Fac'].default_value = 1.0
    nt.links.new(pap.outputs[0], mul.inputs['Color1']); nt.links.new(shade.outputs[0], mul.inputs['Color2'])
    nt.links.new(mul.outputs[0], bsdf.inputs['Base Color'])
    # mask = saturated AND bright (the painted orange light); white paper and dark folds stay out
    sat = nt.nodes.new('ShaderNodeMapRange'); sat.inputs['From Min'].default_value = 0.50; sat.inputs['From Max'].default_value = 0.80
    val = nt.nodes.new('ShaderNodeMapRange'); val.inputs['From Min'].default_value = 0.45; val.inputs['From Max'].default_value = 0.85
    nt.links.new(hsv.outputs['Green'], sat.inputs['Value']); nt.links.new(hsv.outputs['Blue'], val.inputs['Value'])
    mask = nt.nodes.new('ShaderNodeMath'); mask.operation = 'MULTIPLY'
    nt.links.new(sat.outputs['Result'], mask.inputs[0]); nt.links.new(val.outputs['Result'], mask.inputs[1])
    amp = nt.nodes.new('ShaderNodeMath'); amp.operation = 'MULTIPLY'; amp.name = amp.label = 'GLOW'
    amp.inputs[1].default_value = glow
    nt.links.new(mask.outputs[0], amp.inputs[0])
    bsdf.inputs['Emission Color'].default_value = (1.0, 0.13, 0.06, 1) if demonic else (1.0, 0.5, 0.16, 1)
    nt.links.new(amp.outputs[0], bsdf.inputs['Emission Strength'])
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
    warm = nt.nodes.new('ShaderNodeMixRGB'); warm.blend_type = 'MULTIPLY'; warm.inputs['Fac'].default_value = 1.0
    warm.inputs['Color2'].default_value = (1.0, 0.72, 0.5, 1)
    nt.links.new(mul.outputs[0], warm.inputs['Color1']); nt.links.new(warm.outputs[0], tr.inputs['Color'])
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs['Fac'].default_value = translucency
    nt.links.new(bsdf.outputs[0], mix.inputs[1]); nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


def set_glow(ch, glow, frame=None):
    """inner glow strength (pulse it with the voice or a hit); keyframes it when frame is given"""
    n = ch['material'].node_tree.nodes.get('GLOW')
    if n:
        n.inputs[1].default_value = glow
        if frame is not None:
            n.inputs[1].keyframe_insert('default_value', frame=frame)
    for L, e in ch['lanterns']:
        L.data.energy = e * glow / 1.6
        if frame is not None:
            L.data.keyframe_insert('energy', frame=frame)


# ----------------------------------------------------------------------------------------------- armature
def build_armature(spec, name='RIG'):
    P = {}                                                  # bone → (head, tail)
    hips = Vector(spec['hips'])
    P['root'] = (Vector((0, 0, 0)), Vector((0, -0.2 * spec['k'], 0)))
    P['hips'] = (hips, hips + Vector((0, 0, -0.10 * spec['k'])))
    P['waist'] = (hips, Vector(spec['waist_top']))
    P['chest'] = (Vector(spec['waist_top']), Vector(spec['chest_top']))
    P['neck'] = (Vector(spec['chest_top']), Vector(spec['neck_top']))
    P['head'] = (Vector(spec['neck_top']), Vector(spec['head_top']))
    for s in 'LR':
        sh, el, wr, ht = (side(spec[k], s) for k in ('shoulder', 'elbow', 'wrist', 'hand_tip'))
        P[f'clavicle.{s}'] = (Vector((sh.x * 0.25, sh.y, sh.z)), sh)
        P[f'shoulder.{s}'] = (sh, el)
        P[f'elbow.{s}'] = (el, wr)
        P[f'twist.{s}'] = ((el + wr) / 2, wr)
        P[f'hand.{s}'] = (wr, ht)
        P[f'sleeve.{s}'] = (side(spec['sleeve_top'], s), side(spec['sleeve_tip'], s))
        hj, kn, an, toe = (side(spec[k], s) for k in ('hip_joint', 'knee', 'ankle', 'toe'))
        P[f'thigh.{s}'] = (hj, kn)
        P[f'shin.{s}'] = (kn, an)
        P[f'foot.{s}'] = (an, toe)
    arm = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for b in BONES:
        eb = arm.edit_bones.new(b)
        eb.head, eb.tail = P[b]
    for b, p in PARENT.items():
        arm.edit_bones[b].parent = arm.edit_bones[p]
        arm.edit_bones[b].use_connect = False
    for b in ('root', 'clavicle.L', 'clavicle.R', 'twist.L', 'twist.R'):
        arm.edit_bones[b].use_deform = False
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    rest = {b: arm.bones[b].matrix_local.copy() for b in BONES}
    return rig, rest, P


def arm_refs(spec, s):
    """The engine's shoulder and elbow frames (as Blender world rotations) when the engine arm is in THIS model's
    rest pose. Engine arm: upper arm along local -y, the elbow hinges about local x, a bent forearm goes to local +z."""
    sh, el, wr = (side(spec[k], s) for k in ('shoulder', 'elbow', 'wrist'))
    du, df = (el - sh).normalized(), (wr - el).normalized()
    y = -du
    z = (df - y * df.dot(y)).normalized()
    x = y.cross(z)
    Ms = Matrix((x, y, z)).transposed()                    # columns x, y, z
    y2 = -df
    z2 = x.cross(y2)
    Me = Matrix((x, y2, z2)).transposed()
    return Ms @ C3.transposed(), Me @ C3.transposed()


# ----------------------------------------------------------------------------------------------- skin weights
def cut_panels(mesh, spec):
    """Open the fused shell where real cloth is not joined: along the collar V (sleeve front | chest), between the two
    sleeves in front (the joined hands), and under the sleeves (sleeve | waist). The back and the shoulder tops stay
    joined, like a kimono's shoulder seam. Returns per-vertex flags (is_arm, is_front_torso)."""
    import bmesh
    k = spec['k']
    floor, chin, colx = spec['shell_floor'], spec['chin'], spec['column_x']
    cf = spec['column_front']
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    v0 = 0.93 * k                                           # where the collar V closes (the joined hands)

    def knife(co, no, keep):
        """score the paper along a plane (only the faces `keep` accepts), so the cut edge is straight, not saw-toothed"""
        fs = [f for f in bm.faces if keep(f.calc_center_median())]
        geom = set(fs)
        for f in fs:
            geom.update(f.edges); geom.update(f.verts)
        bmesh.ops.bisect_plane(bm, geom=list(geom), dist=1e-5, plane_co=co, plane_no=no, clear_inner=False, clear_outer=False)
    front = 0.14 * k
    knife((0, 0, 0), (1, 0, 0), lambda c: c.y < front and 0.15 * k < c.z < v0 + 0.08 * k and abs(c.x) < 0.1 * k)
    knife((0, 0, v0), (-1, 0, 0.5), lambda c: c.y < front and v0 - 0.03 * k < c.z < chin + 0.04 * k and c.x > -0.02 * k)
    knife((0, 0, v0), (1, 0, 0.5), lambda c: c.y < front and v0 - 0.03 * k < c.z < chin + 0.04 * k and c.x < 0.02 * k)
    bm.faces.ensure_lookup_table(); bm.faces.index_update()

    def label(c):
        if c.z > chin:
            return 0
        if c.z < floor - 0.02 * k:
            yf = float(np.interp(c.z, [a for a, _ in cf], [b for _, b in cf]))
            drape = c.z > 0.19 * k and (abs(c.x) > colx or c.y < yf - 0.03 * k)
            return (1 if c.x > 0 else 2) if drape else 0
        xb_front = max(0.0, 0.5 * (c.z - v0))
        t = min(1.0, max(0.0, (c.y - 0.10 * k) / (0.10 * k)))
        xb = xb_front + (0.24 * k - xb_front) * t
        return 0 if abs(c.x) < xb else (1 if c.x > 0 else 2)
    # the flat membrane TRELLIS closes the shell with (under the sleeves, around the waist) tears into shreds when a
    # sleeve lifts: remove it. The opening it leaves is the sleeve mouth; the under-robe core shows inside.
    axis_y = spec['hips'][1]
    shreds = [f for f in bm.faces if abs(f.normal.z) > 0.55 and abs(f.calc_center_median().z - floor) < 0.07 * k
              and math.hypot(f.calc_center_median().x, f.calc_center_median().y - axis_y) > 0.17 * k]
    bmesh.ops.delete(bm, geom=shreds, context='FACES')
    bm.faces.ensure_lookup_table(); bm.faces.index_update()
    lab = {f.index: label(f.calc_center_median()) for f in bm.faces}
    cut = []
    for e in bm.edges:
        ls = {lab[f.index] for f in e.link_faces}
        if len(ls) < 2:
            continue
        m = (e.verts[0].co + e.verts[1].co) / 2
        if ls == {1, 2} or m.y < 0.12 * k or m.z < floor + 0.10 * k:
            cut.append(e)
    bmesh.ops.split_edges(bm, edges=cut)
    bm.verts.ensure_lookup_table()
    n = len(bm.verts)
    is_arm, front_torso = np.zeros(n, bool), np.zeros(n, bool)
    for v in bm.verts:
        ls = {lab[f.index] for f in v.link_faces}
        is_arm[v.index] = bool(ls & {1, 2})
        front_torso[v.index] = ls == {0}
    bm.to_mesh(mesh.data); bm.free()
    mesh.data.update()
    return is_arm, front_torso


def cloak_weights(mesh, spec, P, labels=None, power=4):
    """Our own region weights: returns {bone: array of per-vertex weights} (see the module docstring).
    labels = (is_arm, front_torso) from cut_panels: torso vertices in front ignore the arms (they were cut free)."""
    n = len(mesh.data.vertices)
    co = np.empty(n * 3)
    mesh.data.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    k = spec['k']
    W = {b: np.zeros(n) for b in BONES}

    def seg_d(a, b):
        a, b = np.array(a), np.array(b)
        ab = b - a
        t = np.clip(((co - a) @ ab) / (ab @ ab), 0, 1)
        return np.linalg.norm(co - (a + t[:, None] * ab), axis=1)

    # --- head and neck: above the chin, inside the collar
    chin = spec['chin']
    inside = np.maximum(ss(chin + 0.05 * k, chin + 0.10 * k, z), ss(0.19 * k, 0.13 * k, np.abs(x)))
    head = ss(chin, chin + 0.06 * k, z) * inside
    neck = ss(chin - 0.06 * k, chin, z) * (1 - ss(chin, chin + 0.06 * k, z)) * inside
    body = 1 - head - neck

    # --- upper shell: chest, waist and both arms by distance; arms do not pull the back
    floor = spec['shell_floor']
    inv = lambda d: 1.0 / (d + 0.02 * k) ** power
    arms_ok = ss(0.30 * k, 0.10 * k, y)
    chest_ok = np.ones(n)
    if labels is not None:
        is_arm, front_torso = labels
        arms_ok = np.where(front_torso, arms_ok * ss(0.10 * k, 0.20 * k, y), arms_ok)
        # a sleeve panel in front belongs to its arm alone (it was cut free of the chest)
        chest_ok = np.where(is_arm, 0.02 + 0.98 * ss(-0.02 * k, 0.16 * k, y), 1.0)
    shell = {
        'chest': inv(seg_d(P['chest'][0], P['chest'][1])) * 1.6 * chest_ok,
        'waist': inv(seg_d(P['waist'][0], P['waist'][1])) * 1.6 * chest_ok,
    }
    for s in 'LR':
        mine = (x > 0) if s == 'L' else (x < 0)
        own = np.where(mine, 1.0, 0.0) if labels is not None else 1.0     # cut panels: a sleeve never follows the other arm
        shell[f'shoulder.{s}'] = inv(seg_d(P[f'shoulder.{s}'][0], P[f'shoulder.{s}'][1])) * arms_ok * own
        shell[f'elbow.{s}'] = inv(seg_d(P[f'elbow.{s}'][0], P[f'elbow.{s}'][1])) * arms_ok * own
        shell[f'hand.{s}'] = inv(seg_d(P[f'hand.{s}'][0], P[f'hand.{s}'][1])) * arms_ok * 0.8 * own
    tot = sum(shell.values())
    shell = {b: w / np.maximum(tot, 1e-12) for b, w in shell.items()}

    # --- below the shell floor: the skirt column (hakama → legs) or the free sleeve ends (→ sleeve bones)
    cf = np.array(spec['column_front'])
    yfront = np.interp(z, cf[:, 0], cf[:, 1])
    drape = (z > 0.19 * k) & ((np.abs(x) > spec['column_x']) | (y < yfront - 0.03 * k))
    if labels is not None:
        drape = labels[0] & (z < floor + 0.04 * k)
    left = ss(-0.10 * k, 0.10 * k, x)
    up_h = ss(0.50 * k, 0.66 * k, z)
    up_t = ss(0.26 * k, 0.40 * k, z)
    col = {'hips': up_h, 'thigh.L': (1 - up_h) * up_t * left, 'thigh.R': (1 - up_h) * up_t * (1 - left),
           'shin.L': (1 - up_h) * (1 - up_t) * left, 'shin.R': (1 - up_h) * (1 - up_t) * (1 - left)}
    leftd = ss(-0.03 * k, 0.03 * k, x) if labels is None else (x > 0).astype(float)
    drp = {'sleeve.L': leftd, 'sleeve.R': 1 - leftd}

    upper = ss(floor - 0.04 * k, floor + 0.04 * k, z)      # 1 in the shell, 0 below
    if labels is not None:
        upper = np.where(labels[0], upper, ss(floor - 0.06 * k, floor + 0.02 * k, z))
    for b, w in shell.items():
        W[b] += body * upper * w
    for b, w in col.items():
        W[b] += body * (1 - upper) * (~drape) * w
    # the top of a sleeve end blends into the forearm it hangs from
    hang = ss(floor - 0.10 * k, floor + 0.02 * k, z)
    for s in 'LR':
        W[f'sleeve.{s}'] += body * (1 - upper) * drape * drp[f'sleeve.{s}'] * (1 - 0.5 * hang)
        W[f'elbow.{s}'] += body * (1 - upper) * drape * drp[f'sleeve.{s}'] * 0.5 * hang
    W['head'] += head
    W['neck'] += neck
    tot = sum(W.values())
    lost = tot < 1e-6
    if lost.any():                                          # anything the regions missed follows the chest
        W['chest'][lost] = 1.0
        tot = sum(W.values())
    return {b: w / np.maximum(tot, 1e-9) for b, w in W.items()}


def make_core(rig, spec):
    """The under-robe: a faceted paper body inside the shell. When a sleeve panel swings away from the chest, this is
    what shows in the gap, lit warm by the inner lantern (so the gaps glow instead of showing a hole)."""
    import bmesh
    k = spec['k']
    cy = spec['hips'][1]
    rings = [(0.66, 0.15, 0.115), (0.80, 0.15, 0.105), (0.98, 0.18, 0.115), (1.16, 0.215, 0.12), (1.25, 0.20, 0.11), (1.33, 0.07, 0.065)]
    bm = bmesh.new()
    N = 8
    vs = [[bm.verts.new((rx * k * math.cos(a + 0.39), cy + 0.01 * k + ry * k * math.sin(a + 0.39), zz * k)) for a in (i * math.tau / N for i in range(N))]
          for zz, rx, ry in rings]
    for a, b in zip(vs, vs[1:]):
        for j in range(N):
            bm.faces.new((a[j], a[(j + 1) % N], b[(j + 1) % N], b[j]))
    bm.faces.new(vs[0][::-1]); bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('CORE'); bm.to_mesh(me); bm.free()
    me.materials.append(_mat('CORE_underrobe', (0.42, 0.33, 0.25), 0.9))
    ob = bpy.data.objects.new('CORE', me)
    bpy.context.scene.collection.objects.link(ob)
    wz, cz = spec['waist_top'][2], spec['chest_top'][2]
    gw, gc, gh = ob.vertex_groups.new(name='waist'), ob.vertex_groups.new(name='chest'), ob.vertex_groups.new(name='hips')
    for v in me.vertices:
        t = min(1.0, max(0.0, (v.co.z - (wz - 0.12 * k)) / (0.24 * k)))
        h = min(1.0, max(0.0, (0.74 * k - v.co.z) / (0.1 * k)))
        gh.add([v.index], h, 'REPLACE'); gw.add([v.index], (1 - h) * (1 - t), 'REPLACE'); gc.add([v.index], (1 - h) * t, 'REPLACE')
    ob.parent = rig
    md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = rig
    return ob


def make_fists(rig, spec, P):
    """Two folded-paper fists on the handle (the TRELLIS hands are only the joined sleeve mouths)."""
    import bmesh
    k = spec['k']
    out = []
    for s in 'LR':
        wr = P[f'hand.{s}'][0]
        bm = bmesh.new()
        r = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.046 * k)
        for v in r['verts']:
            v.co = Vector((v.co.x * 0.85, v.co.y * 1.05, v.co.z * 0.95)) + wr
        me = bpy.data.meshes.new(f'FIST.{s}'); bm.to_mesh(me); bm.free()
        me.materials.append(_mat('FIST_paper', (0.74, 0.66, 0.55), 0.85))
        ob = bpy.data.objects.new(f'FIST.{s}', me)
        bpy.context.scene.collection.objects.link(ob)
        ob.vertex_groups.new(name=f'hand.{s}').add(list(range(len(me.vertices))), 1.0, 'REPLACE')
        ob.parent = rig
        md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = rig
        out.append(ob)
    return out


def _clean_heat(mesh, spec):
    """Weight cleanup after bone heat (the "manual" pass, written down so it repeats on every model):
    the kasa and the head are one rigid folded piece (head bone only), the collar blends over a short band,
    and every vertex keeps its 4 strongest bones."""
    k, chin = spec['k'], spec['chin']
    vg = {g.name: g for g in mesh.vertex_groups}
    if 'head' not in vg:
        vg['head'] = mesh.vertex_groups.new(name='head')
    hi = vg['head'].index
    for v in mesh.data.vertices:
        z, ax = v.co.z, abs(v.co.x)
        t = min(1.0, max(0.0, (z - (chin + 0.01 * k)) / (0.07 * k)))
        if z < chin + 0.10 * k and ax > 0.19 * k:           # the collar wings beside the neck stay with the robe
            t = 0.0
        if t <= 0:
            continue
        t = t * t * (3 - 2 * t)
        for g in v.groups:
            if g.group != hi:
                g.weight *= (1 - t)
        vg['head'].add([v.index], max(t, next((g.weight for g in v.groups if g.group == hi), 0.0)), 'REPLACE')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)


def skin(mesh, rig, spec, P, mode='heat'):
    bpy.ops.object.select_all(action='DESELECT')
    if mode == 'heat':
        # Blender's automatic (bone heat) weights; the mesh is welded first because TRELLIS exports ~370 loose patches
        bpy.context.view_layer.objects.active = mesh
        mesh.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.0008)
        bpy.ops.object.mode_set(mode='OBJECT')
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        try:
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
            ok = any(len(v.groups) for v in mesh.data.vertices)
        except Exception as e:                              # noqa: BLE001
            print('[rig_trellis] bone heat failed:', e)
            ok = False
        if ok:
            _clean_heat(mesh, spec)
            return 'heat'
        print('[rig_trellis] bone heat gave no weights: using our own cloak weights instead')
        mesh.parent = None
        for md in list(mesh.modifiers):
            mesh.modifiers.remove(md)
        mesh.vertex_groups.clear()
        mode = 'cloak'
    labels = cut_panels(mesh, spec) if mode == 'panels' else None
    W = cloak_weights(mesh, spec, P, labels, power=6 if mode == 'panels' else 4)
    if mode == 'rigid':
        names = list(W)
        stack = np.stack([W[b] for b in names])
        best = stack.argmax(0)
        W = {b: (best == i).astype(float) for i, b in enumerate(names)}
        # faces that span two panels would stretch: remove them (the gaps are the honest cost of rigid panels)
        me = mesh.data
        drop = [p.index for p in me.polygons if len({int(best[v]) for v in p.vertices}) > 1]
        import bmesh
        bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in drop], context='FACES_ONLY')
        bm.to_mesh(me); bm.free()
        n = len(me.vertices)
        if n != len(best):
            raise RuntimeError('vertex count changed while cutting rigid panels')
    for b, w in W.items():
        idx = np.nonzero(w > 0.004)[0]
        if not len(idx):
            continue
        vg = mesh.vertex_groups.new(name=b)
        for i in idx:
            vg.add([int(i)], float(w[i]), 'REPLACE')
    mesh.parent = rig
    md = mesh.modifiers.new('Armature', 'ARMATURE')
    md.object = rig
    return mode


# ----------------------------------------------------------------------------------------------- props: katana, feet
def _mat(name, rgb, rough=0.5, metal=0.0, **kw):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*rgb, 1); p.inputs['Roughness'].default_value = rough; p.inputs['Metallic'].default_value = metal
    for key, val in kw.items():
        p.inputs[key].default_value = val
    return m


def make_katana(name='KATANA', length=0.91, sori=0.027, tsuka=0.33, demonic=False):
    """A real-metal katana in the ENGINE's sword frame (blade along +x from the guard, edge toward -y, handle along -x;
    engine/props.js makeKatana), converted to Blender axes, so the engine's sword transform drives it directly.
    Polished steel blade with a frosted hamon band, copper habaki, iron tsuba, ray-skin handle with a crossed silk wrap."""
    import bmesh
    w0, w1, th = 0.033, 0.024, 0.0068
    yc = lambda u: -4 * sori * u * (1 - u)
    wd = lambda u: w0 + (w1 - w0) * u
    steel = _mat('KATANA_steel', (0.80, 0.82, 0.85), 0.14, 1.0)
    hamon = _mat('KATANA_hamon', (0.93, 0.93, 0.91), 0.36, 1.0)
    copper = _mat('KATANA_habaki', (0.85, 0.48, 0.25), 0.3, 1.0)
    iron = _mat('KATANA_tsuba', (0.045, 0.04, 0.04), 0.42, 0.9)
    silk = bpy.data.materials.get('KATANA_ito')
    if not silk:
        # tsuka-ito: dark silk crossing over pale ray skin (diamonds), from two crossed wave bands
        silk = bpy.data.materials.new('KATANA_ito'); silk.use_nodes = True
        nt = silk.node_tree; p = nt.nodes['Principled BSDF']; p.inputs['Roughness'].default_value = 0.85
        tc = nt.nodes.new('ShaderNodeTexCoord')
        bands = []
        for sgn in (1, -1):
            mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value = (0, 0, sgn * math.radians(52))
            mp.inputs['Scale'].default_value = (1, 1, 1)
            wv = nt.nodes.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = 26.0; wv.wave_profile = 'SIN'
            nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs[0], wv.inputs['Vector'])
            bands.append(wv)
        mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'
        nt.links.new(bands[0].outputs['Fac'], mx.inputs[0]); nt.links.new(bands[1].outputs['Fac'], mx.inputs[1])
        ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.interpolation = 'CONSTANT'
        ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (0.75, 0.70, 0.58, 1)   # samegawa in the diamonds
        ramp.color_ramp.elements[1].position = 0.62; ramp.color_ramp.elements[1].color = ((0.10, 0.004, 0.006, 1) if demonic else (0.012, 0.012, 0.016, 1))
        nt.links.new(mx.outputs[0], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
        bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.6; bump.inputs['Distance'].default_value = 0.002
        nt.links.new(mx.outputs[0], bump.inputs['Height']); nt.links.new(bump.outputs[0], p.inputs['Normal'])
    mats = [steel, hamon, copper, iron, silk]
    bm = bmesh.new()
    B = lambda p: Vector((p[0], -p[2], p[1]))               # three → Blender
    N = 40
    # blade cross-section: spine (mune) flat, a ridge (shinogi) at 40% of the width, down to a sharp edge
    rows = []
    for i in range(N + 1):
        u = i / N
        tip = max(0.0, (u - 0.93) / 0.07)                   # kissaki: the edge curves up to the spine
        xx = u * length
        top = yc(u)
        bot = top - wd(u) * (1 - tip ** 1.6)
        mid = top - wd(u) * 0.4 * (1 - tip ** 1.6)
        ham = top - wd(u) * 0.72 * (1 - tip ** 1.6)
        t = th * (1 - 0.25 * u) * (1 - tip)
        rows.append([bm.verts.new(B(p)) for p in ((xx, top, t * 0.42), (xx, mid, t / 2), (xx, ham, t * 0.3), (xx, bot, 0), (xx, ham, -t * 0.3), (xx, mid, -t / 2), (xx, top, -t * 0.42))])
    for a, b in zip(rows, rows[1:]):
        for j in range(6):
            f = bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
            f.material_index = 1 if j in (2, 3) else 0     # the hamon band next to the edge
        bm.faces.new((a[6], a[0], b[0], b[6]))
    bm.faces.new(rows[0])

    def box(x0, x1, hy, hz, cy, mat, seg=1, bulge=0.0):
        """a box along x, centred on y = cy; `seg` rings, `bulge` swells the middle (the handle's shape)"""
        ring = []
        for i in range(seg + 1):
            u = i / seg
            g = 1 + bulge * math.sin(math.pi * u)
            xx = x0 + (x1 - x0) * u
            ring.append([bm.verts.new(B((xx, cy + sy * hy * g * cyy, sz * hz * g * czz)))
                         for sy, sz, cyy, czz in ((1, 0.5, 1, 1), (0.5, 1, 1, 1), (-0.5, 1, 1, 1), (-1, 0.5, 1, 1), (-1, -0.5, 1, 1), (-0.5, -1, 1, 1), (0.5, -1, 1, 1), (1, -0.5, 1, 1))])
        for a, b in zip(ring, ring[1:]):
            for j in range(8):
                f = bm.faces.new((a[j], a[(j + 1) % 8], b[(j + 1) % 8], b[j])); f.material_index = mat
        for cap in (ring[0], ring[-1]):
            f = bm.faces.new(cap); f.material_index = mat
    box(0.0, 0.028, w0 / 2 + 0.003, 0.0052, -w0 / 2, 2)                   # habaki
    box(-0.012, -tsuka, 0.0185, 0.0135, -w0 / 2, 4, seg=6, bulge=0.06)    # tsuka
    box(-0.008, -0.014, 0.021, 0.0155, -w0 / 2, 3)                        # fuchi
    box(-tsuka, -tsuka - 0.014, 0.0195, 0.0145, -w0 / 2, 3)               # kashira
    ts = [bm.verts.new(B((xx, -w0 / 2 + 0.043 * math.cos(a) * (0.97 + 0.03 * math.cos(3 * a)), 0.040 * math.sin(a))))
          for xx in (-0.008, -0.002) for a in (i * math.tau / 20 for i in range(20))]
    for j in range(20):
        f = bm.faces.new((ts[j], ts[(j + 1) % 20], ts[20 + (j + 1) % 20], ts[20 + j])); f.material_index = 3
    for cap in (ts[:20], ts[20:]):
        f = bm.faces.new(cap); f.material_index = 3
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_mode = 'QUATERNION'
    ob['bladeLen'] = length
    return ob


def make_feet(rig, spec, P):
    """Folded paper tabi + zori under the hem (the TRELLIS robe hides the legs, so a long stride needs feet)."""
    import bmesh
    k = spec['k']
    paper = _mat('FOOT_tabi', (0.78, 0.74, 0.66), 0.85)
    sole = _mat('FOOT_zori', (0.03, 0.025, 0.02), 0.7)
    feet = []
    for s in 'LR':
        an = P[f'foot.{s}'][0]
        bm = bmesh.new()
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r['verts']:
            fwd = 0.5 - v.co.y                               # 0 at the heel … 1 at the toe (the foot points to -Y)
            v.co = Vector((an.x + v.co.x * 0.085 * k, an.y - (fwd - 0.28) * 0.24 * k, (0.02 + (v.co.z + 0.5) * (0.075 - 0.045 * fwd)) * k))
        r2 = bmesh.ops.create_cube(bm, size=1.0)
        for v in r2['verts']:
            v.co = Vector((an.x + v.co.x * 0.10 * k, an.y - (0.5 - v.co.y - 0.26) * 0.26 * k, (0.01 + v.co.z * 0.02) * k))
        for f in bm.faces:
            f.material_index = 1 if all(v in r2['verts'] for v in f.verts) else 0
        me = bpy.data.meshes.new(f'FOOT.{s}')
        bm.to_mesh(me); bm.free()
        me.materials.append(paper); me.materials.append(sole)
        ob = bpy.data.objects.new(f'FOOT.{s}', me)
        bpy.context.scene.collection.objects.link(ob)
        ob.vertex_groups.new(name=f'foot.{s}').add(list(range(len(me.vertices))), 1.0, 'REPLACE')
        ob.parent = rig
        md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = rig
        feet.append(ob)
    return feet


# ----------------------------------------------------------------------------------------------- the character
def build_character(model='ronin_base', mode='heat', height=None, name=None, demonic=False, glow=1.6, katana=True):
    spec = model_spec(model, height)
    mesh = import_trellis(model, spec)
    mat = paper_material(mesh, glow=glow, demonic=demonic)
    rig, rest, P = build_armature(spec, name=(name or 'RIG_' + model))
    mode = skin(mesh, rig, spec, P, mode)
    feet = make_feet(rig, spec, P)
    core = make_core(rig, spec) if mode in ('panels', 'rigid') else None
    fists = make_fists(rig, spec, P) if katana else []
    lanterns = []
    for bone, pos, energy in spec['lantern']:
        L = bpy.data.lights.new('LANTERN_' + bone, 'POINT')
        L.color = (1.0, 0.13, 0.06) if demonic else (1.0, 0.55, 0.2)
        L.energy = energy; L.shadow_soft_size = 0.05 * spec['k']
        lo = bpy.data.objects.new('LANTERN_' + bone, L)
        bpy.context.scene.collection.objects.link(lo)
        lo.parent = rig; lo.parent_type = 'BONE'; lo.parent_bone = bone
        bpy.context.view_layer.update()
        lo.matrix_world = Matrix.Translation(pos)           # Blender works out the offset from the bone
        lanterns.append((lo, energy))
    sword = make_katana(demonic=demonic) if katana else None
    refs = {s: arm_refs(spec, s) for s in 'LR'}
    L1 = (Vector(spec['elbow']) - Vector(spec['shoulder'])).length
    L2 = (Vector(spec['wrist']) - Vector(spec['elbow'])).length
    T1 = (Vector(spec['knee']) - Vector(spec['hip_joint'])).length
    T2 = (Vector(spec['ankle']) - Vector(spec['knee'])).length
    return {'model': model, 'spec': spec, 'mesh': mesh, 'rig': rig, 'rest': rest, 'P': P, 'feet': feet, 'core': core, 'fists': fists, 'lanterns': lanterns,
            'material': mat, 'sword': sword, 'refs': refs, 'L': (L1, L2), 'T': (T1, T2), 'mode': mode, 'hist': {}}


# ----------------------------------------------------------------------------------------------- frames (engine truth)
JOINTS = ['root', 'hips', 'waist', 'chest', 'neck', 'head', 'clavicle.R', 'shoulder.R', 'elbow.R', 'twist.R', 'hand.R',
          'clavicle.L', 'shoulder.L', 'elbow.L', 'twist.L', 'hand.L', 'thigh.R', 'shin.R', 'foot.R', 'thigh.L', 'shin.L', 'foot.L']


def load_motion(path):
    """output/<film>.motion.json (tools/export_motion.mjs) → frames in Blender axes."""
    d = json.load(open(path))
    names = d['joints']
    sub = d['sub']
    out = {'meta': d, 'sub': sub, 'fps': d['film']['fps'], 'frames': [], 'samples': d['frames']}
    for i in range(0, len(d['frames']), sub):
        F = d['frames'][i]
        fr = {'t': F['t'], 'tb': F['tb'], 'cam': F['cam'], 'trees': F.get('trees', []), 'cast': {}}
        for cid, c in F['cast'].items():
            J = {n: (v3(j[:3]), q3(j[3:])) for n, j in zip(names, c['joints'])}
            fr['cast'][cid] = {'J': J, 'sword': (v3(c['sword'][:3]), q3(c['sword'][3:])), 'twoHand': c.get('twoHand', 1.0),
                               'pose': c.get('pose', {}), 'eyes': c.get('eyes')}
        out['frames'].append(fr)
    return out


def sample_sword(sample, cid):
    """the sword of one sub-frame sample → (position, quaternion) in Blender axes (film export or BVH)"""
    c = sample['cast'][cid]
    if 'swordB' in c:
        return c['swordB'][0].copy(), c['swordB'][1].to_quaternion()
    return v3(c['sword'][:3]), q3(c['sword'][3:]).to_quaternion()


def sword_samples(motion, cid, f0, f1):
    """sub-frame sword transforms (Blender axes) between two frames, newest last: [(t, pos, rot3)]"""
    sub = motion['sub']
    S = motion['samples']
    out = []
    for i in range(max(0, int(round(f0 * sub))), min(len(S) - 1, int(round(f1 * sub))) + 1):
        c = S[i]['cast'].get(cid)
        if c:
            out.append((S[i]['t'], v3(c['sword'][:3]), q3(c['sword'][3:])))
    return out


# --- a Python port of engine/figure.js applyPose + solveLegs + holdInHand, for library poses (stills, pose sheets)
POSES = None
BASE_POSE = dict(x=0, y=0, z=0, ry=0, rx=0, rz=0, tx=0, ty=0, tz=0, hx=0, hy=0, rsx=0.05, rsz=0.12, rex=-0.15, lsx=0.05, lsz=-0.12,
                 lex=-0.15, rwx=0, lwx=0, sway=0, swayx=0, cx=0, cy=0, cz=0, nx=0, ny=0, hz=0, rcy=0, rcz=0, lcy=0, lcz=0, rsy=0, lsy=0,
                 rfy=0, lfy=0, rwz=0, lwz=0, rax=0, lax=0, lid=0, stance=0.12, crouch=0, weight=0, stride=0, phase=0)


def _R(x=0.0, y=0.0, z=0.0, order='XYZ'):
    m = {'X': Matrix.Rotation(x, 4, 'X'), 'Y': Matrix.Rotation(y, 4, 'Y'), 'Z': Matrix.Rotation(z, 4, 'Z')}
    out = Matrix.Identity(4)
    for ax in order:                                        # three.js 'XYZ' = Rx · Ry · Rz
        out = out @ m[ax]
    return out


def engine_fk(p):
    """pose channels → world matrices of every engine joint + the sword, in three.js axes (figure.js, line by line)."""
    p = {**BASE_POSE, **p}
    T = Matrix.Translation
    M = {}
    M['root'] = T((p['x'], p['y'], p['z'])) @ _R(p['rx'], p['ry'], p['rz'], 'YXZ')
    M['hips'] = M['root'] @ T((0, 0.92 - p['crouch'], p['weight'] * p['stance'] * 0.35))
    M['waist'] = M['hips'] @ _R(p['tx'] + p['weight'] * 0.05, p['ty'], p['tz'])
    M['chest'] = M['waist'] @ T((0, 0.26, 0)) @ _R(p['cx'], p['cy'], p['cz'])
    M['neck'] = M['chest'] @ T((0, 0.29, 0)) @ _R(p['nx'], p['ny'], 0)
    M['head'] = M['neck'] @ T((0, 0.06, 0)) @ _R(p['hx'], p['hy'], p['hz'])
    for s, sg, a in (('R', -1, 'r'), ('L', 1, 'l')):
        cl = _R(0, p[a + 'cy'], -p[a + 'cz']) if s == 'R' else _R(0, -p[a + 'cy'], p[a + 'cz'])
        M[f'clavicle.{s}'] = M['chest'] @ T((sg * 0.07, 0.21, 0)) @ cl
        M[f'shoulder.{s}'] = M[f'clavicle.{s}'] @ T((sg * 0.16, 0, 0)) @ _R(p[a + 'sx'], p[a + 'sy'], p[a + 'sz'])
        M[f'elbow.{s}'] = M[f'shoulder.{s}'] @ T((0, -0.3, 0)) @ _R(p[a + 'ex'])
        M[f'twist.{s}'] = M[f'elbow.{s}'] @ _R(0, p[a + 'fy'], 0)
        M[f'hand.{s}'] = M[f'twist.{s}'] @ T((0, -0.29, 0)) @ _R(p[a + 'wx'], 0, p[a + 'wz'])
    L1, L2 = 0.46, 0.44
    hipY, hipZ = 0.92 - p['crouch'] - 0.02, p['weight'] * p['stance'] * 0.35
    for s, sg, front, ank in (('R', -1, True, p['rax']), ('L', 1, False, p['lax'])):
        fz, fy = (1 if front else -1) * p['stance'] / 2, 0.04
        dz, dy = fz - hipZ, fy - hipY
        d = math.hypot(dz, dy)
        mx = (L1 + L2) * 0.999
        if d > mx:
            dz, dy, d = dz * mx / d, dy * mx / d, mx
        phi = math.atan2(dz, -dy)
        a = math.acos(max(-1, min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
        th = phi + a
        kz, ky = hipZ + L1 * math.sin(th), hipY - L1 * math.cos(th)
        sh = math.atan2(hipZ + dz - kz, -(hipY + dy - ky))
        M[f'thigh.{s}'] = M['root'] @ T((sg * 0.1, hipY, hipZ)) @ _R(-th, 0, sg * 0.04)
        M[f'shin.{s}'] = M[f'thigh.{s}'] @ T((0, -L1, 0)) @ _R(-(sh - th))
        M[f'foot.{s}'] = M[f'shin.{s}'] @ T((0, -L2, 0)) @ _R(sh + ank)
    a = math.sqrt(0.5)
    xa, ya = Vector((0, -a, a)), Vector((0, a, a))
    hold = Matrix((xa, ya, xa.cross(ya))).transposed().to_4x4()
    hold.translation = xa * 0.06 + Vector((0, -0.01, 0))
    M['sword'] = M['hand.R'] @ hold
    return M


def pose_frame(pose='chudan', two_hand=True, **over):
    """a library pose (name or dict of channels) → one frame for apply_frame()"""
    global POSES
    if POSES is None:
        POSES = json.load(open(os.path.join(REPO, 'library', 'poses.json')))
    ch = dict(POSES[pose]) if isinstance(pose, str) else dict(pose)
    ch.update(over)
    M = engine_fk(ch)
    conv = lambda m: (v3(m.translation), C3 @ m.to_3x3() @ C3.transposed())
    return {'J': {n: conv(M[n]) for n in JOINTS}, 'sword': conv(M['sword']), 'twoHand': 1.0 if two_hand else 0.0, 'pose': ch}


# ----------------------------------------------------------------------------------------------- the driver
def ik2(S, T, L1, L2, pole):
    """two-bone IK: returns (elbow, reachable target)"""
    d = T - S
    dist = max(abs(L1 - L2) + 1e-3, min(d.length, (L1 + L2) * 0.999))
    dr = d.normalized() if d.length > 1e-9 else Vector((0, 0, -1))
    a = (L1 * L1 - L2 * L2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(L1 * L1 - a * a, 0.0))
    pp = pole - dr * pole.dot(dr)
    if pp.length < 1e-6:
        pp = Vector((0, 0, -1)) - dr * Vector((0, 0, -1)).dot(dr)
        if pp.length < 1e-6:
            pp = Vector((0, 1, 0))
    return S + dr * a + pp.normalized() * h, S + dr * dist


def solve(ch, fr):
    """one engine frame → {bone: 4x4 armature-space matrix}, plus the sword's world matrix under 'SWORD'."""
    spec, rest, P, k = ch['spec'], ch['rest'], ch['P'], ch['spec']['k']
    J = fr['J']
    R3 = {b: rest[b].to_3x3() for b in BONES}
    out = {}
    pr, Rr = J['root']
    out['root'] = TR(pr, Rr @ R3['root'])
    # hips: the engine's hip travel in the root's frame, scaled to this model's legs
    leg_k = (ch['T'][0] + ch['T'][1]) / ENGINE['leg']
    loc = Rr.transposed() @ (J['hips'][0] - pr)             # Blender axes: x side, y back(+)/front(-), z up
    hips = pr + Rr @ (Vector(spec['hips']) + Vector((loc.x * leg_k, loc.y * leg_k, (loc.z - ENGINE['hipY']) * leg_k * 0.9)))
    out['hips'] = TR(hips, J['hips'][1] @ R3['hips'])

    def fk(b, rot_world):
        """place bone b at its rest offset from its (already solved) parent, with a world rotation delta"""
        par = PARENT[b]
        head = out[par] @ (rest[par].inverted() @ rest[b].translation)
        out[b] = TR(head, rot_world @ R3[b])
    for b in ('waist', 'chest', 'neck', 'head'):
        fk(b, J[b][1])
    sm_e = (J['shoulder.L'][0] + J['shoulder.R'][0]) / 2
    arm_k = (ch['L'][0] + ch['L'][1]) / ENGINE['arm']
    for s in 'LR':
        fk(f'clavicle.{s}', J[f'clavicle.{s}'][1])
    # the sword: the engine's rotation; position = where the engine's right hand is, seen from its shoulder, at this arm length
    Ps, Rs = fr['sword']
    grip_e = J['hand.R'][0]
    SR = out['clavicle.R'] @ (rest['clavicle.R'].inverted() @ rest['shoulder.R'].translation)
    grip = SR + (grip_e - J['shoulder.R'][0]) * arm_k
    sword_pos = grip + (Ps - grip_e)
    out['SWORD'] = TR(sword_pos, Rs)
    two = fr.get('twoHand', 1.0)
    for s in 'LR':
        Sref, Eref = ch['refs'][s]
        S = out[f'clavicle.{s}'] @ (rest[f'clavicle.{s}'].inverted() @ rest[f'shoulder.{s}'].translation)
        fkT = S + (J[f'hand.{s}'][0] - J[f'shoulder.{s}'][0]) * arm_k
        if s == 'R':
            Tg = grip
        else:
            on_handle = sword_pos + Rs @ Vector((-0.25, 0.0, -0.018))    # sword-local (-0.25, -0.018, 0) in three axes
            Tg = fkT.lerp(on_handle, two)
        pole = (J[f'elbow.{s}'][0] - J[f'shoulder.{s}'][0]) - (J[f'hand.{s}'][0] - J[f'shoulder.{s}'][0]) * 0.5
        E, Tg = ik2(S, Tg, ch['L'][0], ch['L'][1], pole + Vector((0.25 if s == 'L' else -0.25, 0.05, -0.2)) * 0.15)
        Ru = J[f'shoulder.{s}'][1] @ Sref.transposed() @ R3[f'shoulder.{s}']
        Ru = swing(Ru @ Vector((0, 1, 0)), E - S) @ Ru
        out[f'shoulder.{s}'] = TR(S, Ru)
        Rf = J[f'elbow.{s}'][1] @ Eref.transposed() @ R3[f'elbow.{s}']
        Rf = swing(Rf @ Vector((0, 1, 0)), Tg - E) @ Rf
        out[f'elbow.{s}'] = TR(E, Rf)
        Rt = J[f'twist.{s}'][1] @ Eref.transposed() @ R3[f'twist.{s}']
        Rt = swing(Rt @ Vector((0, 1, 0)), Tg - E) @ Rt
        out[f'twist.{s}'] = TR((E + Tg) / 2, Rt)
        out[f'hand.{s}'] = TR(Tg, J[f'hand.{s}'][1] @ Eref.transposed() @ R3[f'hand.{s}'])
    # legs: the engine's foot placement in the root's frame, scaled; knees bend forward
    fwd = Rr @ Vector((0, -1, 0))
    for s in 'LR':
        hj = hips + Rr @ (Vector(side(spec['hip_joint'], s)) - Vector(spec['hips']))
        fl = Rr.transposed() @ (J[f'foot.{s}'][0] - pr)
        an = side(spec['ankle'], s)
        foot = pr + Rr @ Vector((an.x + (fl.x - (0.1 if s == 'L' else -0.1)) * leg_k, fl.y * leg_k * 1.1 + an.y, max(0.0, fl.z - 0.04) * leg_k + an.z))
        K, foot = ik2(hj, foot, ch['T'][0], ch['T'][1], fwd + Rr @ Vector((0.25 if s == 'L' else -0.25, 0, 0)))
        base = Rr @ R3[f'thigh.{s}']
        out[f'thigh.{s}'] = TR(hj, swing(base @ Vector((0, 1, 0)), K - hj) @ base)
        base = Rr @ R3[f'shin.{s}']
        out[f'shin.{s}'] = TR(K, swing(base @ Vector((0, 1, 0)), foot - K) @ base)
        out[f'foot.{s}'] = TR(foot, J[f'foot.{s}'][1] @ R3[f'foot.{s}'])
    return out


def sleeves(ch, out, prev=None, dt=1 / FPS):
    """The free sleeve ends: they hang from the elbow, stay 70% vertical whatever the arm does, and swing against the
    elbow's motion (prev = the solved matrices of an earlier frame, 2 frames back works well)."""
    rest = ch['rest']
    for s in 'LR':
        b, par = f'sleeve.{s}', f'elbow.{s}'
        head = out[par] @ (rest[par].inverted() @ rest[b].translation)
        delta = out[par].to_3x3() @ rest[par].to_3x3().inverted()
        follow = Quaternion().slerp(delta.to_quaternion(), 0.3).to_matrix()
        R = follow @ rest[b].to_3x3()
        if prev is not None and b in prev:
            v = (head - prev[b].translation) / dt
            v.z *= 0.5
            if v.length > 0.05:
                hang = Vector((0, 0, -1)) - v * 0.07
                lean = swing(Vector((0, 0, -1)), hang)
                ang = lean.to_quaternion().angle
                if ang > 1.0:
                    lean = Quaternion(lean.to_quaternion().axis, 1.0).to_matrix()
                R = lean @ R
        out[b] = TR(head, R)
    return out


def set_pose(ch, out, frame=None):
    """write solved matrices to the pose bones (and keyframe them when frame is given)"""
    rig, rest = ch['rig'], ch['rest']
    for b in BONES:
        pb = rig.pose.bones[b]
        par = PARENT.get(b)
        if par:
            basis = (out[par] @ rest[par].inverted() @ rest[b]).inverted() @ out[b]
        else:
            basis = rest[b].inverted() @ out[b]
        loc, rot, _ = basis.decompose()
        last = ch['hist'].get(b)
        if last is not None and last.dot(rot) < 0:           # keep quaternions on one side: no flips between keys
            rot.negate()
        ch['hist'][b] = rot.copy()
        pb.location, pb.rotation_quaternion, pb.scale = loc, rot, (1, 1, 1)
        if frame is not None:
            pb.keyframe_insert('location', frame=frame)
            pb.keyframe_insert('rotation_quaternion', frame=frame)
    sw = ch['sword']
    if sw is not None:
        loc, rot, _ = out['SWORD'].decompose()
        last = ch['hist'].get('SWORD')
        if last is not None and last.dot(rot) < 0:
            rot.negate()
        ch['hist']['SWORD'] = rot.copy()
        sw.location, sw.rotation_quaternion = loc, rot
        if frame is not None:
            sw.keyframe_insert('location', frame=frame)
            sw.keyframe_insert('rotation_quaternion', frame=frame)


def apply_frame(ch, fr, frame=None, prev=None):
    out = sleeves(ch, solve(ch, fr), prev)
    set_pose(ch, out, frame)
    return out


def bake(ch, motion, cid, f0, f1, offset=0):
    """Keyframe the character over film frames f0..f1 (Blender frame = film frame + offset + 1). Returns the solved
    matrices per film frame. Keys are linear between frames: the engine already shaped the motion."""
    frames = motion['frames']
    f0, f1 = max(0, f0), min(len(frames) - 1, f1)
    solved = {}
    for f in range(max(0, f0 - 3), f1 + 1):                 # 3 frames of run-up for the sleeve swing
        out = solve(ch, frames[f]['cast'][cid])
        sleeves(ch, out, solved.get(f - 2), dt=2 / motion['fps'])
        solved[f] = out
        if f >= f0:
            set_pose(ch, out, frame=f + offset + 1)
    for ob in (ch['rig'], ch['sword']):
        ad = ob.animation_data if ob else None
        if ad and ad.action:
            for fc in _fcurves(ad.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    return solved


def _fcurves(action):
    """fcurves of an action in Blender 4.4+ (slotted actions) and older versions"""
    try:
        if action.fcurves:
            return list(action.fcurves)
    except Exception:                                       # noqa: BLE001
        pass
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                out.extend(bag.fcurves)
    return out


# ----------------------------------------------------------------------------------------------- mocap (BVH) + standard names
# Our joint → the standard humanoid name (Mixamo / most BVH and FBX exporters). export_names() renames the rig to
# these for other tools; bvh_motion() uses the same table (plus aliases) to read any BVH.
HUMANOID = {
    'root': 'Root', 'hips': 'Hips', 'waist': 'Spine', 'chest': 'Spine1', 'neck': 'Neck', 'head': 'Head',
    'clavicle.L': 'LeftShoulder', 'shoulder.L': 'LeftArm', 'elbow.L': 'LeftForeArm', 'twist.L': 'LeftForeArmRoll', 'hand.L': 'LeftHand',
    'clavicle.R': 'RightShoulder', 'shoulder.R': 'RightArm', 'elbow.R': 'RightForeArm', 'twist.R': 'RightForeArmRoll', 'hand.R': 'RightHand',
    'thigh.L': 'LeftUpLeg', 'shin.L': 'LeftLeg', 'foot.L': 'LeftFoot', 'thigh.R': 'RightUpLeg', 'shin.R': 'RightLeg', 'foot.R': 'RightFoot',
    'sleeve.L': 'LeftSleeve', 'sleeve.R': 'RightSleeve',
}
# other spellings seen in BVH files (lower case, side written as {s} = left/right or l/r): first match wins
BVH_ALIASES = {
    'hips': ['hips', 'hip', 'pelvis', 'root'], 'waist': ['spine', 'abdomen', 'lowerback', 'chest'], 'chest': ['spine2', 'spine1', 'chest2', 'chest', 'upperchest', 'thorax'],
    'neck': ['neck', 'neck1'], 'head': ['head'],
    'clavicle': ['{s}shoulder', '{s}collar', '{s}clavicle'], 'shoulder': ['{s}arm', '{s}upperarm', '{s}shldr', '{s}uparm'],
    'elbow': ['{s}forearm', '{s}lowerarm', '{s}elbow', '{s}lowarm'], 'hand': ['{s}hand', '{s}wrist'],
    'thigh': ['{s}upleg', '{s}upperleg', '{s}thigh', '{s}hip'], 'shin': ['{s}leg', '{s}lowerleg', '{s}shin', '{s}knee', '{s}lowleg'], 'foot': ['{s}foot', '{s}ankle'],
}


def export_names(ch, style='humanoid'):
    """Rename the bones (and the vertex groups) to the standard humanoid names, for retarget tools and game engines.
    Do this LAST (before saving a .blend or exporting FBX): the driver in this file uses our own names."""
    if style != 'humanoid':
        return
    for ob in [ch['mesh'], *ch['feet'], *ch['fists'], *([ch['core']] if ch.get('core') else [])]:
        for g in ob.vertex_groups:
            if g.name in HUMANOID:
                g.name = HUMANOID[g.name]
    for b in ch['rig'].data.bones:
        if b.name in HUMANOID:
            b.name = HUMANOID[b.name]


def a_pose(ch, arm_out=0.75):
    """Make the REST pose an A-pose (arms out and down, about 45°), the bind pose retarget tools expect. The model's own
    rest is "arms folded"; this poses it, bakes the mesh there and makes that the new rest. Run it LAST, like
    export_names(): after it the folded-pose measurements this file's driver uses no longer describe the rig."""
    apply_frame(ch, pose_frame({'rsz': arm_out, 'lsz': -arm_out, 'rsx': 0.0, 'lsx': 0.0, 'rex': -0.08, 'lex': -0.08, 'stance': 0.0}, two_hand=False))
    bpy.context.view_layer.update()
    for ob in [ch['mesh'], *ch['feet'], *ch['fists'], *([ch['core']] if ch.get('core') else [])]:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = ob; ob.select_set(True)
        for md in [m for m in ob.modifiers if m.type == 'ARMATURE']:
            bpy.ops.object.modifier_apply(modifier=md.name)
        md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = ch['rig']
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = ch['rig']; ch['rig'].select_set(True)
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def bvh_motion(path, scale=None, two_hand=False, forward='-Y'):
    """A BVH file (any mocap app or tool) → the same frames load_motion() gives, so bake() plays it on the character.
    Uses Blender's own BVH importer. The retarget is by WORLD rotation change from the BVH rest pose (so a T-pose or an
    A-pose file both work) for the spine, head, hands and feet, and by limb DIRECTIONS for arms and legs, re-scaled to the
    engine's limb lengths; solve() then fits them to the character with IK, exactly as it does for film motion.
    The BVH figure should face `forward` in Blender after import (the importer turns Y-up files to Z-up)."""
    before = set(bpy.data.objects)
    bpy.ops.import_anim.bvh(filepath=path, axis_forward='-Z', axis_up='Y', rotate_mode='NATIVE', update_scene_fps=False, update_scene_duration=False)
    src = [o for o in bpy.data.objects if o not in before and o.type == 'ARMATURE'][0]
    names = {b.name.lower().replace('_', '').replace(' ', '').replace('.', '').split(':')[-1]: b.name for b in src.data.bones}

    def find(joint, s=None):
        base = joint.split('.')[0]
        for al in BVH_ALIASES[base]:
            for sd in ((('left', 'l') if s == 'L' else ('right', 'r')) if s else ('',)):
                key = al.format(s=sd)
                if key in names:
                    return names[key]
        return None
    M = {j: find(j) for j in ('hips', 'waist', 'chest', 'neck', 'head')}
    for s in 'LR':
        for j in ('clavicle', 'shoulder', 'elbow', 'hand', 'thigh', 'shin', 'foot'):
            M[f'{j}.{s}'] = find(j, s)
    if M['chest'] == M['waist']:                              # a one-bone spine: the chest takes it, the waist stays with the hips
        M['waist'] = None
    need = ['hips', 'head'] + [f'{j}.{s}' for s in 'LR' for j in ('shoulder', 'elbow', 'hand', 'thigh', 'shin', 'foot')]
    missing = [j for j in need if not M[j]]
    if missing:
        raise RuntimeError(f'bvh_motion: no bone found for {missing} in {os.path.basename(path)} (bones: {sorted(names.values())[:40]}). Add the spelling to BVH_ALIASES in rig_trellis.py.')
    yaw_fix = {'-Y': 0.0, 'Y': math.pi, 'X': math.pi / 2, '-X': -math.pi / 2}[forward]
    G = Matrix.Rotation(yaw_fix, 3, 'Z')
    rest = {j: (src.matrix_world @ src.data.bones[b].matrix_local) for j, b in M.items() if b}
    h0 = rest['hips'].translation.z - min(rest['foot.L'].translation.z, rest['foot.R'].translation.z)
    sc = scale or (0.90 / max(h0, 1e-6))                     # engine hips are 0.92 m up; feet joints sit 0.04 m above the ground
    floor = min(rest['foot.L'].translation.z, rest['foot.R'].translation.z)
    act = src.animation_data.action if src.animation_data else None
    f0, f1 = (int(act.frame_range[0]), int(act.frame_range[1])) if act else (1, 1)
    scene = bpy.context.scene
    # frame time of the BVH: resample to 24 fps
    dt = 1 / FPS
    try:
        with open(path) as fh:
            for line in fh:
                if line.strip().lower().startswith('frame time'):
                    dt = float(line.split(':')[1]); break
    except Exception:                                       # noqa: BLE001
        pass
    dur = (f1 - f0) * dt
    frames = []
    eng_rest = engine_fk({})
    conv = lambda m: (v3(m.translation), C3 @ m.to_3x3() @ C3.transposed())
    E0 = {n: conv(eng_rest[n]) for n in JOINTS}
    down = Vector((0, 0, -1))
    for i in range(int(dur * FPS) + 1):
        ff = f0 + i / FPS / dt
        scene.frame_set(int(ff), subframe=ff - int(ff))
        W = {j: (src.matrix_world @ src.pose.bones[b].matrix) for j, b in M.items() if b}
        D = {j: G @ (W[j].to_3x3() @ rest[j].to_3x3().inverted()) for j in W}     # world rotation change from the rest pose
        P = {j: G @ ((W[j].translation - Vector((rest['hips'].translation.x, rest['hips'].translation.y, floor))) * sc) for j in W}
        J = {}
        hips = P['hips']
        fw = D['hips'] @ Vector((0, -1, 0)); yaw = math.atan2(fw.x, -fw.y)
        Rroot = Matrix.Rotation(yaw, 3, 'Z')
        proot = Vector((hips.x, hips.y, 0))
        J['root'] = (proot, Rroot)
        J['hips'] = (Vector((hips.x, hips.y, hips.z + 0.04)), D['hips'])
        J['waist'] = (J['hips'][0], D.get('waist', D['hips']))
        J['chest'] = (J['waist'][0] + J['waist'][1] @ Vector((0, 0, 0.26)), D.get('chest', J['waist'][1]))
        J['neck'] = (J['chest'][0] + J['chest'][1] @ Vector((0, 0, 0.29)), D.get('neck', J['chest'][1]))
        J['head'] = (J['neck'][0] + J['neck'][1] @ Vector((0, 0, 0.06)), D['head'])
        for s, sg in (('L', 1), ('R', -1)):
            J[f'clavicle.{s}'] = (J['chest'][0] + J['chest'][1] @ Vector((sg * 0.07, 0, 0.21)), D.get(f'clavicle.{s}', J['chest'][1]))
            sh = J[f'clavicle.{s}'][0] + J[f'clavicle.{s}'][1] @ Vector((sg * 0.16, 0, 0))
            du = (W[f'elbow.{s}'].translation - W[f'shoulder.{s}'].translation); df = (W[f'hand.{s}'].translation - W[f'elbow.{s}'].translation)
            du, df = (G @ du).normalized(), (G @ df).normalized()
            el = sh + du * 0.30; hd = el + df * 0.29
            J[f'shoulder.{s}'] = (sh, swing(down, du))
            J[f'elbow.{s}'] = (el, swing(down, df)); J[f'twist.{s}'] = (el, swing(down, df))
            J[f'hand.{s}'] = (hd, swing(down, df))             # the hand follows the forearm (mocap wrists are noisy)
            # legs: the foot seen from the hip joint, at the engine's leg length
            leg = (W[f'foot.{s}'].translation - W[f'thigh.{s}'].translation)
            leg0 = (rest[f'foot.{s}'].translation - rest[f'thigh.{s}'].translation).length
            hj = proot + Rroot @ Vector((sg * 0.1, 0, 0)) + Vector((0, 0, J['hips'][0].z - 0.02))
            ft = hj + (G @ leg) * (0.90 / max(leg0, 1e-6))
            ft.z = max(0.04, 0.04 + (P[f'foot.{s}'].z - (rest[f'foot.{s}'].translation.z - floor) * sc))
            fyaw = D[f'foot.{s}'] @ Vector((0, -1, 0))
            J[f'thigh.{s}'] = (hj, Rroot); J[f'shin.{s}'] = ((hj + ft) / 2, Rroot)
            J[f'foot.{s}'] = (ft, Matrix.Rotation(math.atan2(fyaw.x, -fyaw.y), 3, 'Z'))
        # the katana rides in the right hand the way the engine holds it (handle along the hand's diagonal)
        a = math.sqrt(0.5)
        xa, ya = Vector((0, -a, a)), Vector((0, a, a))
        hold = C3 @ Matrix((xa, ya, xa.cross(ya))).transposed() @ C3.transposed()
        Rh = J['hand.R'][1]
        sword = (J['hand.R'][0] + Rh @ (C3 @ (xa * 0.06 + Vector((0, -0.01, 0)))), Rh @ hold)
        frames.append({'t': i / FPS, 'tb': i / FPS, 'cam': None, 'trees': [], 'cast': {'hero': {'J': J, 'sword': sword, 'twoHand': 1.0 if two_hand else 0.0, 'pose': {}, 'eyes': None}}})
    bpy.data.objects.remove(src)
    samples = [{'t': fr['t'], 'tb': fr['tb'], 'cast': {'hero': {'swordB': fr['cast']['hero']['sword']}}} for fr in frames]
    meta = {'film': {'fps': FPS, 'duration': dur}, 'sword': {'bladeLen': 0.91}, 'cast': {'hero': {}}, 'trees': [], 'camera': {'cuts': []}, 'events': {}}
    return {'meta': meta, 'sub': 1, 'fps': FPS, 'frames': frames, 'samples': samples, 'bvh': True}



# ----------------------------------------------------------------------------------------------- stage + render
def stage_dark(scene, fog=0.0, floor=True, world=(0.004, 0.005, 0.008)):
    """The owner's reference look (research/reference-videos.md): 70% darkness, dark ground that catches the glow."""
    w = bpy.data.worlds.new('WORLD_dark'); scene.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (*world, 1)
    obs = []
    if floor:
        bpy.ops.mesh.primitive_plane_add(size=120)
        fl = bpy.context.object; fl.name = 'STAGE_floor'
        m = bpy.data.materials.new('STAGE_floor'); m.use_nodes = True
        nt = m.node_tree; p = nt.nodes['Principled BSDF']
        p.inputs['Base Color'].default_value = (0.016, 0.015, 0.014, 1); p.inputs['Roughness'].default_value = 0.62
        tc = nt.nodes.new('ShaderNodeTexCoord')
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.4; nz.inputs['Detail'].default_value = 8.0
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.35; bp.inputs['Distance'].default_value = 0.05
        nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], p.inputs['Normal'])
        rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.45; rr.inputs['To Max'].default_value = 0.8
        nt.links.new(nz.outputs['Fac'], rr.inputs['Value']); nt.links.new(rr.outputs[0], p.inputs['Roughness'])
        fl.data.materials.append(m)
        obs.append(fl)
    if fog > 0:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 4))
        fg = bpy.context.object; fg.name = 'STAGE_fog'; fg.scale = (60, 60, 8)
        fm = bpy.data.materials.new('STAGE_fog'); fm.use_nodes = True
        nt = fm.node_tree; nt.nodes.remove(nt.nodes['Principled BSDF'])
        vol = nt.nodes.new('ShaderNodeVolumePrincipled'); vol.inputs['Density'].default_value = fog
        nt.links.new(vol.outputs[0], nt.nodes['Material Output'].inputs['Volume'])
        fg.data.materials.append(fm)
        obs.append(fg)
    return obs


def spot(name, loc, target, energy, color, size_deg=30, blend=0.4, radius=0.2):
    L = bpy.data.lights.get(name) or bpy.data.lights.new(name, 'SPOT')
    L.energy = energy; L.color = color; L.spot_size = math.radians(size_deg); L.spot_blend = blend; L.shadow_soft_size = radius
    o = bpy.data.objects.get(name)
    if o is None:
        o = bpy.data.objects.new(name, L); bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def render_settings(scene, res='432x768', samples=16, blur=True, threads=2):
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = int(samples)
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 5
    scene.cycles.volume_bounces = 1
    scene.cycles.caustics_reflective = scene.cycles.caustics_refractive = False
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = threads
    scene.render.resolution_x, scene.render.resolution_y = [int(v) for v in str(res).split('x')]
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.use_motion_blur = bool(blur)
    scene.render.motion_blur_shutter = 0.5
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:                                       # noqa: BLE001
        pass


# ----------------------------------------------------------------------------------------------- command line
def _main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    arg = lambda n, d=None: argv[argv.index('--' + n) + 1] if '--' + n in argv else d
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    ch = build_character(arg('model', 'ronin_base'), mode=arg('mode', 'heat'), demonic='--demonic' in argv)
    centre = Vector((0, 0, 0.95))
    if arg('motion') or arg('bvh'):
        mo = bvh_motion(arg('bvh')) if arg('bvh') else load_motion(arg('motion'))
        cid = arg('who') or next(iter(mo['frames'][0]['cast']))
        f = int(round(float(arg('t', 0)) * mo['fps']))
        bake(ch, mo, cid, f - 1, f + 1)
        sc.frame_set(f + 1)
        centre = mo['frames'][f]['cast'][cid]['J']['root'][0] + Vector((0, 0, 0.95))
        fwd = mo['frames'][f]['cast'][cid]['J']['root'][1] @ Vector((0, -1, 0))
    elif arg('pose', 'rest') != 'rest':
        apply_frame(ch, pose_frame(arg('pose'), two_hand='--one-hand' not in argv))
        fwd = Vector((0, -1, 0))
    else:
        fwd = Vector((0, -1, 0))
        if ch['sword']:
            ch['sword'].hide_render = True
    stage_dark(sc, fog=float(arg('fog', 0)))
    az = {'front': 0, 'q': 38, 'side': 90, 'back': 180, 'q2': -38, 'bq': 140}[arg('view', 'q')]
    a = math.atan2(fwd.x, -fwd.y) + math.radians(az)
    dist = float(arg('dist', 5.2))
    cd = bpy.data.cameras.new('cam'); cd.lens = 50; cd.sensor_fit = 'VERTICAL'
    cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = centre + Vector((math.sin(a) * dist, -math.cos(a) * dist, 0.15))
    cam.rotation_euler = (centre - cam.location).to_track_quat('-Z', 'Y').to_euler()
    right = Vector((math.cos(a), math.sin(a), 0))
    back = Vector((-math.sin(a), math.cos(a), 0))
    spot('key', centre - back * 2.8 - right * 2.4 + Vector((0, 0, 2.9)), centre, 1300, (1.0, 0.86, 0.68), 40)
    spot('rim', centre + back * 3.0 + right * 2.4 + Vector((0, 0, 1.8)), centre + Vector((0, 0, 0.2)), 2200, (0.62, 0.75, 1.0), 34, 0.3)
    spot('fill', centre - back * 3.5 + right * 3.0 + Vector((0, 0, 0.6)), centre, 160, (0.5, 0.6, 1.0), 50)
    render_settings(sc, arg('res', '432x768'), arg('samples', 16), blur=bool(arg('motion') or arg('bvh')))
    out = arg('out', 'output/character/rig-test.png')
    sc.render.filepath = os.path.abspath(out)
    bpy.ops.render.render(write_still=True)
    if '--a-pose' in argv:
        a_pose(ch)
    if arg('names'):
        export_names(ch, arg('names'))
    if arg('save'):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(arg('save')))


if __name__ == '__main__':
    _main()

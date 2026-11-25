"""MODULAR BUILDER: assemble a rigged paper character from a recipe of parts.

    B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
    nice -n 10 $B -b -t 2 -P blender/character/modular_builder.py -- \
        --recipe library/character-recipes/ronin-reference.json --out output/character/ronin.blend
    ... -- --recipe <r> --pose chudan --still output/character/ronin.png
    ... -- --recipe <r> --turnaround output/character/ronin-turn.png --light neutral

What it does, in order:
  1. builds the shared humanoid rig: the SAME joint names as engine/figure.js and rig_trellis.py
     (root hips torso upper neck head, rC rS rE rT rH + l…, r/l thigh shin foot, hakama), as empties
     driving a deform armature, so library/poses.json poses it and film_blender.py can drive it;
  2. loads the recipe's parts from blender/character/part_registry.py, snaps each one to its socket in the
     rest pose, scales it INSIDE its approved range (scaling the mesh, never the object, so the washi fibre
     stays world-size on every part), and assigns its sheet from library/paper-materials/;
  3. hides faces that are sealed inside another part of the same bone;
  4. parents rigid parts to their bone and skins flexible ones (sleeves, hakama legs) across 2-3 bones;
  5. poses it and hands back {'rig', 'joints', 'objects', 'collection'}.

Recipe format: see library/character-recipes/ronin-reference.json and docs/CHARACTER-FACTORY.md.
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'world'))
import paper_materials as pm            # noqa: E402
import part_registry as reg             # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d


def flag(n):
    return '--' + n in ARGV


# =========================================================================== poses (port of engine/figure.js)
POSES = json.load(open(os.path.join(REPO, 'library', 'poses.json')))
BASE = dict(x=0, y=0, z=0, ry=0, rx=0, rz=0, tx=0, ty=0, tz=0, hx=0, hy=0, hz=0, rsx=0.05, rsz=0.12, rex=-0.15,
            lsx=0.05, lsz=-0.12, lex=-0.15, rwx=0, lwx=0, rwz=0, lwz=0, sway=0, swayx=0, stance=0.12, crouch=0,
            weight=0, cx=0, cy=0, cz=0, nx=0, ny=0, rcy=0, rcz=0, lcy=0, lcz=0, rsy=0, lsy=0, rfy=0, lfy=0,
            rax=0, lax=0)
POSES.setdefault('standing', {'tx': 0.06, 'hx': 0.22, 'nx': 0.1, 'rsx': -0.55, 'rsz': 0.35, 'rex': -1.4,
                              'lsx': -0.5, 'lsz': -0.4, 'lex': -1.45, 'stance': 0.18})


def T(x, y, z):
    """three.js (figure.js) coordinates → Blender."""
    return Vector((x, -z, y))


# =========================================================================== the shared rig
class Rig:
    """Empties (the exact figure.js kinematics) with a deform armature constrained to them."""

    def __init__(self, coll, name='PC'):
        self.coll = coll
        self.J = {}
        self.name = name
        self._build_joints()
        self._build_armature()

    def _joint(self, n, parent, local_three):
        e = bpy.data.objects.new('J_' + n + '_' + self.name, None)
        e.empty_display_size = 0.04
        e.rotation_mode = 'YZX'
        self.coll.objects.link(e)
        if parent:
            e.parent = self.J[parent]
        e.location = T(*local_three)
        self.J[n] = e
        return e

    def _build_joints(self):
        self._joint('root', None, (0, 0, 0))
        self._joint('hips', 'root', (0, 0.92, 0))
        self._joint('torso', 'hips', (0, 0, 0))
        self._joint('upper', 'torso', (0, 0.26, 0))
        self._joint('neck', 'upper', (0, 0.29, 0))
        self._joint('head', 'neck', (0, 0.06, 0))
        self._joint('hakama', 'hips', (0, 0, 0))
        for s, sgn in (('r', -1), ('l', 1)):
            self._joint(s + 'C', 'upper', (sgn * 0.07, 0.21, 0))
            self._joint(s + 'S', s + 'C', (sgn * 0.16, 0, 0))
            self._joint(s + 'E', s + 'S', (0, -0.30, 0))
            self._joint(s + 'T', s + 'E', (0, 0, 0))
            self._joint(s + 'H', s + 'T', (0, -0.29, 0))
            # SLEEVE BONE. The tamoto is cloth, not part of the arm: it hangs from the forearm but
            # keeps falling toward the ground when the arm lifts, instead of swinging over the head
            # with it. It needs a joint of its own for that; _hang_sleeves() aims it every frame.
            # Same place as engine/figure.js hangs its tamoto group (tamoto.position.y = -0.1).
            self._joint(s + 'Sleeve', s + 'T', (0, -0.10, 0))
            self._joint(s + 'thigh', 'root', (sgn * 0.1, 0.92, 0))
            self._joint(s + 'shin', s + 'thigh', (0, -0.46, 0))
            self._joint(s + 'foot', s + 'shin', (0, -0.44, 0))
        bpy.context.view_layer.update()

    def _build_armature(self):
        """One deform bone per joint, each constrained to its empty: rigid parts parent, soft parts skin."""
        arm = bpy.data.armatures.new('ARM_' + self.name)
        rig = bpy.data.objects.new('RIG_' + self.name, arm)
        self.coll.objects.link(rig)
        self.rig = rig
        prev = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode='EDIT')
        kids = {}
        for b, p in reg.PARENT.items():
            kids.setdefault(p, []).append(b)
        for b, head in reg.REST.items():
            eb = arm.edit_bones.new(b)
            eb.head = Vector(head)
            ch = [k for k in kids.get(b, []) if Vector(reg.REST[k]) != Vector(head)]
            if b in getattr(reg, 'TAIL', {}):
                eb.tail = Vector(reg.TAIL[b])
            else:
                eb.tail = Vector(reg.REST[ch[0]]) if ch else Vector(head) + Vector((0, 0, 0.09))
            if (eb.tail - eb.head).length < 1e-4:
                eb.tail = eb.head + Vector((0, 0, 0.09))
        for b, p in reg.PARENT.items():
            arm.edit_bones[b].parent = arm.edit_bones[p]
            arm.edit_bones[b].use_connect = False
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.objects.active = prev
        self.rest_bone = {b: arm.bones[b].matrix_local.copy() for b in reg.REST}
        # Bone order parent-first: setting pose_bone.matrix reads the parent's current pose.
        self.order = []
        todo = [b for b in reg.REST if b not in reg.PARENT]
        while todo:
            b = todo.pop(0)
            self.order.append(b)
            todo += [k for k, p in reg.PARENT.items() if p == b]
        bpy.context.view_layer.update()

    def sync_bones(self):
        """Drive the deform bones from the empties.

        A bone's rest orientation has nothing to do with its empty's (bones point along their own Y), so a
        Copy Transforms constraint would shear every skinned part. What a skin wants is the empty's DELTA
        from rest applied to the bone's own rest matrix: D = empty_now @ empty_rest^-1 (the empties are pure
        translations at rest, so empty_rest is just Translation(REST[b]))."""
        for b in self.order:
            D = self.J[b].matrix_world @ Matrix.Translation(-Vector(reg.REST[b]))
            self.rig.pose.bones[b].matrix = D @ self.rest_bone[b]
            bpy.context.view_layer.update()

    # ---- the pose solver, ported from engine/figure.js applyPose + solveLegs
    def rot(self, j, rx, ry, rz):
        self.J[j].rotation_euler = (rx, -rz, ry)

    def pose(self, name='standing', **over):
        p = dict(BASE)
        p.update(POSES.get(name, {}) if isinstance(name, str) else (name or {}))
        p.update(over)
        J = self.J
        J['root'].location = T(p['x'], p['y'], p['z'])
        self.rot('root', p['rx'], p['ry'], p['rz'])
        hipY = 0.92 - p['crouch']
        hipZ = p['weight'] * p['stance'] * 0.35
        J['hips'].location = T(0, hipY, hipZ)
        self.rot('torso', p['tx'] + p['weight'] * 0.05, p['ty'], p['tz'])
        self.rot('upper', p['cx'], p['cy'], p['cz'])
        self.rot('neck', p['nx'], p['ny'], 0)
        self.rot('head', p['hx'], p['hy'], p['hz'])
        self.rot('rC', 0, p['rcy'], -p['rcz']); self.rot('lC', 0, -p['lcy'], p['lcz'])
        self.rot('rS', p['rsx'], p['rsy'], p['rsz']); self.rot('lS', p['lsx'], p['lsy'], p['lsz'])
        self.rot('rE', p['rex'], 0, 0); self.rot('lE', p['lex'], 0, 0)
        self.rot('rT', 0, p['rfy'], 0); self.rot('lT', 0, p['lfy'], 0)
        self.rot('rH', p['rwx'], 0, p['rwz']); self.rot('lH', p['lwx'], 0, p['lwz'])
        self.rot('hakama', p['swayx'], 0, p['sway'])
        L1, L2 = 0.46, 0.44
        hy, hzz = hipY - 0.02, hipZ
        for s, side in (('r', -1), ('l', 1)):
            front = side < 0
            fz, fy = (1 if front else -1) * p['stance'] / 2, 0.04
            dz, dy = fz - hzz, fy - hy
            d = math.hypot(dz, dy)
            mx = (L1 + L2) * 0.999
            if d > mx:
                dz *= mx / d; dy *= mx / d; d = mx
            phi = math.atan2(dz, -dy)
            a = math.acos(max(-1, min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
            th = phi + a
            kz, ky = hzz + L1 * math.sin(th), hy - L1 * math.cos(th)
            sh = math.atan2(hzz + dz - kz, -(hy + dy - ky))
            J[s + 'thigh'].location = T(side * 0.1, hy, hzz)
            self.rot(s + 'thigh', -th, 0, side * 0.04)
            self.rot(s + 'shin', -(sh - th), 0, 0)
            self.rot(s + 'foot', sh + (p['rax'] if front else p['lax']), 0, 0)
        bpy.context.view_layer.update()
        self._hang_sleeves(p)
        bpy.context.view_layer.update()
        self.sync_bones()
        return p

    def _hang_sleeves(self, p):
        """Aim each sleeve bone at the ground, pushed outward as the arm rises.

        This is the port of engine/figure.js hangCloth(). A sleeve skinned to the arm alone follows
        the arm rigidly, so an overhead cut swings the tamoto over the head and the face disappears
        into its own cloth. Real fabric does not do that: it keeps hanging down, and what the lifted
        arm does is pull it OUT to the side, away from the head.

        `raise` is how far the forearm points up, read off the forearm's own axis (down-the-limb is
        the joint's local -Z here, because T() maps three.js (0,-1,0) to Blender (0,0,-1)): 0 with the
        arm hanging, 1 with it overhead. The outward push scales with it, and the small blend back
        toward the forearm - which is what tips the hem over the face - fades out as the arm lifts."""
        sway = p.get('sway', 0.0)
        rootq = self.J['root'].matrix_world.to_quaternion()
        down = Vector((0.0, 0.0, -1.0))
        for s, lat in (('r', -1.0), ('l', 1.0)):
            e = self.J[s + 'Sleeve']
            e.rotation_euler = (0.0, 0.0, 0.0)
            bpy.context.view_layer.update()
            pq = e.parent.matrix_world.to_quaternion()
            up = (pq @ down).z                              # +1 forearm overhead, -1 hanging
            rise = max(0.0, min(1.0, up))
            d = rootq @ Vector((sway * 0.4 + 2.2 * rise * lat, 0.0, -1.0))
            q = down.rotation_difference((pq.inverted() @ d).normalized())
            e.rotation_euler = q.slerp(Quaternion(), 0.2 * (1.0 - rise)).to_euler('YZX')


# =========================================================================== binding
def _mirror(bone, side):
    return bone if side > 0 else ('r' + bone[1:] if bone[0] == 'l' else bone)


def _seg_dist(p, a, b):
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-9 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


def skin_object(ob, rig, bones, power=3.0, keep=3):
    """Weight a flexible part across 2-3 bones by inverse distance to their rest segments."""
    child = {}
    for b, p in reg.PARENT.items():
        child.setdefault(p, []).append(b)
    segs = {}
    for b in bones:
        a = Vector(reg.REST[b])
        ch = [k for k in child.get(b, []) if Vector(reg.REST[k]) != a]
        if b in getattr(reg, 'TAIL', {}):              # a childless bone states its own tail
            segs[b] = (a, Vector(reg.TAIL[b]))
        else:
            segs[b] = (a, Vector(reg.REST[ch[0]]) if ch else a + Vector((0, 0, 0.09)))
    groups = {b: ob.vertex_groups.new(name=b) for b in bones}
    M = ob.matrix_world
    for v in ob.data.vertices:
        p = M @ v.co
        w = {b: 1.0 / (max(_seg_dist(p, *segs[b]), 0.012) ** power) for b in bones}
        top = sorted(w.items(), key=lambda kv: -kv[1])[:keep]
        tot = sum(x for _, x in top)
        for b, x in top:
            groups[b].add([v.index], x / tot, 'REPLACE')
    mod = ob.modifiers.new('skin', 'ARMATURE')
    mod.object = rig
    ob['pc_bind'] = 'skin:' + ','.join(bones)
    return ob


def skin_hang(ob, rig, sewn, hang):
    """Weight a HANGING part between the body it is sewn to and its own cloth bone, by height.

    Inverse distance cannot do this job. A kimono sleeve is sewn to the body at the shoulder and
    hangs free below, so its top must stay with the shoulder and its bottom must obey gravity - but
    the top of the bag sits right on the shoulder bone, so by distance the shoulder wins everywhere
    and the whole bag swings over the head on an overhead cut. That is the bug this fixes.

    `sewn` keeps the seam; `hang` is the sleeve bone that engine-side hangCloth() aims at the ground.
    The blend is smoothstepped over the part's own height, so there is no crease where it changes."""
    gs = {b: ob.vertex_groups.new(name=b) for b in (sewn, hang)}
    M = ob.matrix_world
    zs = [(M @ v.co).z for v in ob.data.vertices]
    hi, lo = max(zs), min(zs)
    span = max(hi - lo, 1e-4)
    for v in ob.data.vertices:
        t = min(1.0, max(0.0, (hi - (M @ v.co).z) / span))
        t = t * t * (3.0 - 2.0 * t)                    # smoothstep: no crease at the seam
        gs[hang].add([v.index], t, 'REPLACE')
        gs[sewn].add([v.index], 1.0 - t, 'REPLACE')
    mod = ob.modifiers.new('skin', 'ARMATURE')
    mod.object = rig
    ob['pc_bind'] = f'hang:{sewn},{hang}'
    return ob


def parent_rigid(ob, joint):
    ob.parent = joint
    ob.matrix_parent_inverse = joint.matrix_world.inverted()
    ob['pc_bind'] = 'rigid'
    return ob


# =========================================================================== internal faces
def hide_internal_faces(objs, bind):
    """Delete faces sealed inside another RIGID part on the same bone: they never show and cost samples."""
    removed = 0
    rigid = [o for o in objs if bind.get(o.name, ('rigid', None))[0] == 'rigid' and o.type == 'MESH'
             and len(o.data.polygons) < 3000]
    trees = {}
    for o in rigid:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(o.matrix_world)
        trees[o.name] = (BVHTree.FromBMesh(bm), [v.co.copy() for v in bm.verts])
        bm.free()
    for a in rigid:
        for b in rigid:
            if a is b or bind[a.name][1] != bind[b.name][1]:
                continue
            if reg.PARTS.get(b.get('pc_part', ''), {}).get('layer', 0) <= \
               reg.PARTS.get(a.get('pc_part', ''), {}).get('layer', 0):
                continue
            tree = trees[b.name][0]
            bm = bmesh.new()
            bm.from_mesh(a.data)
            bm.transform(a.matrix_world)
            kill = []
            for f in bm.faces:
                c = f.calc_center_median()
                hits, o2 = 0, c
                for _ in range(6):                      # odd number of crossings = inside
                    r = tree.ray_cast(o2 + Vector((0, 0, 1e-4)), Vector((0.31, 0.47, 0.83)))
                    if r[0] is None:
                        break
                    hits += 1
                    o2 = r[0] + Vector((0.31, 0.47, 0.83)) * 1e-4
                if hits % 2 == 1:
                    kill.append(f)
            if kill and len(kill) < len(bm.faces):
                bm.transform(a.matrix_world.inverted())
                bmesh.ops.delete(bm, geom=kill, context='FACES')
                bm.to_mesh(a.data)
                removed += len(kill)
            bm.free()
    return removed


# =========================================================================== build
def build(recipe, *, pose='standing', location=(0, 0, 0), yaw=0.0, collection=None, name=None,
          seed=None, pose_overrides=None):
    """Build one character from a recipe dict. Returns {'rig','joints','objects','collection','recipe'}."""
    name = name or recipe.get('id', 'CHARACTER')
    scene = bpy.context.scene
    if collection is None:
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
    rig = Rig(collection, name=name)
    glow = tuple(recipe.get('glow', (1.0, 0.55, 0.18)))
    glow_str = float(recipe.get('glow_strength', 3.0))
    ctx = reg.PartCtx(collection, seed=int(recipe.get('seed', 3) if seed is None else seed),
                      materials=recipe.get('paper', {}), glow=(glow, glow_str),
                      suffix='' if name == 'CHARACTER' else '_' + name,
                      proportion=recipe.get('proportion', 'standard'))
    bind, built, report = {}, [], []
    entries = sorted(recipe['parts'], key=lambda e: reg.PARTS[e['part']]['layer'])
    for entry in entries:
        key = entry['part']
        if key not in reg.PARTS:
            raise KeyError(f'recipe {name}: no such part {key!r} (see part_registry.py)')
        spec = reg.PARTS[key]
        scale = float(entry.get('scale', 1.0))
        lo, hi = spec['size']
        if not (lo - 1e-6 <= scale <= hi + 1e-6):
            raise ValueError(f'{key}: scale {scale} outside the approved range {lo}-{hi}')
        socks = entry.get('sockets') or spec['socket']
        for sock in socks:
            S = reg.SOCKETS[sock]
            ctx.socket = Vector(S['pos'])
            ctx.sock = sock
            ctx.side = S['side'] if S['side'] else 1
            before = set(ctx.objects)
            P = dict(spec['defaults'])
            P.update(entry.get('params', {}))
            spec['fn'](ctx, P, ctx.rnd)
            made = [o for o in ctx.objects if o not in before]
            bone = entry.get('bone') or spec['bone'] or S['bone']
            bones = [_mirror(b, ctx.side) for b in (entry.get('bones') or spec['bones'])] or [bone]
            for ob in made:
                ob['pc_recipe'] = key
                ob['pc_socket'] = sock
                if scale != 1.0:                       # scale the MESH about the socket: object scale stays 1
                    ob.data.transform(Matrix.Translation(ctx.socket) @ Matrix.Scale(scale, 4)
                                      @ Matrix.Translation(-ctx.socket))
                kind = 'rigid' if spec['rigid'] else (spec.get('skin') or 'skin')
                bind[ob.name] = (kind, bone, bones)
                built.append(ob)
            report.append(f'{key:<22}{sock:<14}{len(made)} objects  scale {scale:.2f}')
    bpy.context.view_layer.update()
    hidden = hide_internal_faces(built, {k: (v[0], v[1]) for k, v in bind.items()})
    for ob in built:
        kind, bone, bones = bind[ob.name]
        if kind == 'hang' and len(ob.data.vertices) and len(bones) >= 2:
            skin_hang(ob, rig.rig, bones[0], bones[1])   # bones = [sewn, cloth]
            ob.parent = rig.rig
        elif kind in ('skin', 'hang') and len(ob.data.vertices):
            skin_object(ob, rig.rig, bones)
            ob.parent = rig.rig
        else:
            parent_rigid(ob, rig.J[bone])
    rig.pose(pose, **(pose_overrides or {}))
    rig.J['root'].location = Vector(location) + rig.J['root'].location
    rig.J['root'].rotation_euler.rotate_axis('Z', yaw)
    bpy.context.view_layer.update()
    rig.sync_bones()
    # the inner lantern: the character is lit from inside, not only by the key light
    for nm, j, off, pw in (('chest', 'upper', (0, 0, 0.10), 3.2), ('belly', 'torso', (0, 0, 0.08), 0.5),
                           ('head', 'head', (0, 0, 0.08), 0.5)):
        L = bpy.data.lights.new(f'PC_lamp_{nm}_{name}', 'POINT')
        L.color = glow
        L.energy = pw * float(recipe.get('lamp_scale', 1.0))
        L.shadow_soft_size = 0.03
        lo = bpy.data.objects.new(L.name, L)
        collection.objects.link(lo)
        lo.parent = rig.J[j]
        lo.location = Vector(off)
    bpy.context.view_layer.update()
    print('\n'.join(report))
    print(f'[builder] {name}: {len(built)} objects, {hidden} internal faces removed, '
          f'{sum(len(o.data.polygons) for o in built)} faces')
    return {'rig': rig, 'joints': rig.J, 'objects': built, 'collection': collection, 'recipe': recipe,
            'armature': rig.rig, 'bind': bind}


def load_recipe(path):
    with open(path) as fh:
        r = json.load(fh)
    base = r.get('extends')
    if base:
        p = base if os.path.isabs(base) else os.path.join(os.path.dirname(os.path.abspath(path)), base)
        parent = load_recipe(p if p.endswith('.json') else p + '.json')
        merged = dict(parent)
        merged.update({k: v for k, v in r.items() if k != 'extends'})
        if 'swap' in r or 'add' in r or 'drop' in r:
            # Swap by SLOT (one kasa, one torso, one obi…), except the slots that legitimately hold several
            # parts at once — there armour and accessories are swapped, added and dropped BY NAME.
            multi = {'armor', 'accessory'}

            def k(e):
                sl = reg.PARTS[e['part']]['slot']
                return e['part'] if sl in multi else sl
            kit = {k(e): e for e in merged['parts']}
            for e in r.get('swap', []):
                kit[k(e)] = e
            for name in r.get('drop', []):
                kit.pop(name, None)
                for key, e in list(kit.items()):
                    if e['part'] == name or reg.PARTS[e['part']]['slot'] == name:
                        kit.pop(key, None)
            for e in r.get('add', []):
                kit[k(e)] = e
            merged['parts'] = list(kit.values())
        r = merged
    return r


# =========================================================================== lighting + render
def studio(scene, kind='neutral', coll=None):
    """neutral = the flat studio that hides nothing (the one the models were audited under);
       cinematic = the dark Lantern Origami key, where the paper glows from inside."""
    coll = coll or scene.collection
    w = bpy.data.worlds.new('PC_World')
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    if kind == 'neutral':
        bg.inputs[0].default_value = (0.55, 0.56, 0.58, 1)
        bg.inputs[1].default_value = 1.4
        rig = (((-2.5, -3, 3.2), 400, 2.5, (1, 1, 1)), ((3, -1.5, 2), 160, 2, (1, 1, 1)),
               ((0, 3.5, 2.5), 200, 3, (1, 1, 1)))
        exposure = 0.0
    else:
        bg.inputs[0].default_value = (0.010, 0.012, 0.020, 1)
        bg.inputs[1].default_value = 0.35
        rig = (((-2.2, -2.4, 2.9), 160, 1.2, (1.0, 0.95, 0.88)),
               ((2.6, 1.9, 2.4), 110, 1.0, (0.70, 0.80, 1.0)),
               ((0.4, -3.4, 0.5), 14, 1.5, (1.0, 0.72, 0.42)))
        exposure = -0.35
    for loc, e, sz, col in rig:
        L = bpy.data.lights.new('L', 'AREA')
        L.energy, L.size, L.color = e, sz, col
        o = bpy.data.objects.new('L', L)
        # Not visible to camera rays. An area lamp renders as a bright rectangle if it ever lands in
        # shot; in an empty studio it never does, which is how one reached a finished frame.
        o.visible_camera = False
        o.location = loc
        o.rotation_euler = (Vector((0, 0, 1.0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        coll.objects.link(o)
    try:
        scene.view_settings.view_transform = 'AgX'
    except Exception:
        pass
    scene.view_settings.exposure = exposure
    return scene


def render_settings(scene, res='420x740', samples=24):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = int(samples)
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    x, y = res.split('x')
    scene.render.resolution_x, scene.render.resolution_y = int(x), int(y)
    scene.render.resolution_percentage = 100
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2


def camera(scene, pos, look, lens=70, coll=None):
    cd = bpy.data.cameras.new('PC_cam')
    cd.lens = lens
    c = bpy.data.objects.new('PC_cam', cd)
    (coll or scene.collection).objects.link(c)
    c.location = pos
    c.rotation_euler = (Vector(look) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = c
    return c


def render(scene, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    scene.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)
    print('wrote', path)
    return path


def frame(objs):
    """Centre and height of what was actually built, so a turnaround always fills the frame."""
    lo = Vector((9e9, 9e9, 9e9))
    hi = Vector((-9e9, -9e9, -9e9))
    for o in objs:
        if o.type != 'MESH' or not len(o.data.vertices):
            continue
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    return (0.0, 0.0, (lo.z + hi.z) / 2), max(hi.z - lo.z, 0.5)


VIEWS = (('front', 0), ('three-quarter', 40), ('side', 90), ('back', 180))


def turnaround(scene, out, center=(0, 0, 0.95), dist=4.3, lens=70, views=VIEWS, eye=None):
    files = []
    for nm, deg in views:
        a = math.radians(deg)
        camera(scene, (-math.sin(a) * dist, -math.cos(a) * dist,
                       center[2] + 0.12 if eye is None else eye), center, lens)
        # A path without .png used to have nothing to replace, so every view wrote to the SAME
        # file and four renders silently became one. Build the name instead of patching it.
        base = out[:-4] if out.lower().endswith('.png') else out.rstrip('/') + '/view'
        files.append(render(scene, f'{base}-{nm}.png'))
    return files


# =========================================================================== CLI
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    rpath = arg('recipe')
    if not rpath:
        print('usage: --recipe library/character-recipes/<id>.json [--out x.blend] [--pose p] '
              '[--still p.png | --turnaround p.png] [--light neutral|cinematic]')
        return
    recipe = load_recipe(os.path.abspath(rpath))
    ch = build(recipe, pose=arg('pose', recipe.get('pose', 'neutral')),
               pose_overrides=None if arg('pose') else recipe.get('pose_overrides'), yaw=math.radians(float(arg('ry', 0))))
    if arg('still') or arg('turnaround'):
        studio(scene, arg('light', 'neutral'))
        render_settings(scene, arg('res', '420x740'), arg('samples', 24))
        center, height = frame(ch['objects'])
        if arg('poses'):
            # a pose sweep (or a slash): one still per pose, same camera, so motion is the only variable
            a = math.radians(float(arg('angle', 34)))
            d = float(arg('dist', 0) or height * 2.55)
            camera(scene, (-math.sin(a) * d, -math.cos(a) * d, center[2] + 0.12), center,
                   float(arg('lens', 70)))
            out = arg('poses_out') or arg('still') or 'output/character/pose.png'
            for nm in arg('poses').split(','):
                ch['rig'].pose(nm, **(recipe.get('pose_overrides', {}) if nm == 'neutral' else {}))
                c2, h2 = frame(ch['objects'])      # re-frame: the pose is the subject, not the framing
                d2 = float(arg('dist', 0) or h2 * 2.55)
                camera(scene, (-math.sin(a) * d2, -math.cos(a) * d2, c2[2] + 0.12), c2,
                       float(arg('lens', 70)))
                render(scene, out.replace('.png', f'-{nm}.png'))
        elif arg('turnaround'):
            turnaround(scene, arg('turnaround'), center=center,
                       dist=float(arg('dist', 0) or height * 2.55), lens=float(arg('lens', 70)))
        else:
            a = math.radians(float(arg('angle', 28)))
            d = float(arg('dist', 0) or height * 2.55)
            camera(scene, (-math.sin(a) * d, -math.cos(a) * d, center[2] + 0.12), center,
                   float(arg('lens', 70)))
            render(scene, arg('still'))
    if arg('out'):
        os.makedirs(os.path.dirname(os.path.abspath(arg('out'))), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(arg('out')))
        print('saved', arg('out'))


if __name__ == '__main__':
    main()

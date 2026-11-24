"""BLENDERFILM: render a film's performance and camera in Blender with the TRELLIS hero. Guide: docs/CHARACTER-BLENDER.md.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  node tools/export_motion.mjs film/dash-test.json                      # once per film change → output/dash-test.motion.json
  # stills at film seconds (check these before any sequence)
  nice -n 10 $B -b -t 2 -P blender/film_blender.py -- --film film/dash-test.json --out output/blender/dash-test/ --times 0.3,1.1,3.1
  # a short sequence (frames are film frames at 24 fps)
  nice -n 10 $B -b -t 2 -P blender/film_blender.py -- --film film/dash-test.json --out output/blender/dash-test/ --frames 24-35

  --cam film        the film's own camera (KUROKO beats, exported frame by frame)                       [default]
  --cam plan        the Blender camera plan for this film in library/blender-cameras.json (falls back to film)
  --cam <move>      one named move for every frame: circle, come-back, go-front, low-hero, high-crane, top-down,
                    side-track, over-shoulder, blade-close (library/blender-cameras.json → "moves")
  --bvh take.bvh    motion capture instead of a film: any BVH (Blender's importer), retargeted onto the character;
                    --cam defaults to circle; --two-hand puts the left hand on the handle; --bvh-forward -Y|Y|X|-X
  --model ronin_base   which TRELLIS model plays the first fighter       --mode heat|panels|cloak|rigid
  --res 432x768 --samples 16 --fog 0.012 --no-blur --no-slash --no-dust --no-glare
  --set output/sets/dojo.blend [--at x,y,z,yawDeg]   stage the film inside a built set (blender/sets/); default: dark stage
  --save file.blend    keep the scene

What it builds
  * the character (blender/character/rig_trellis.py) baked from output/<film>.motion.json: the engine's real joints
  * the katana in a two-hand grip, the inner lantern, the film's tree props
  * dark cinematic light (research/reference-videos.md): about 70% darkness, a warm key from the camera's side, a strong
    cool rim from behind that follows the camera, a low fill; the glow is the brightest thing on screen
  * the slash as LIGHT: a ribbon swept by the real blade over the last sub-frames (white-hot at the leading edge, amber
    human / crimson demonic behind it, fading out), plus a flare light that lights the paper while the blade is fast
  * ground dust on dash / skid / take-off / landing (the engine's ground events), motion blur, a soft glare
"""
import json
import math
import os
import random
import subprocess
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(HERE, 'character'))
sys.path.insert(0, os.path.join(HERE, 'world'))
import rig_trellis as rt  # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
arg = lambda n, d=None: ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d
flag = lambda n: '--' + n in ARGV
FPS = 24
# colour code (AGENTS.md rule 4, same values as blender/world/slash_fx.py): amber = human, crimson = demonic
PALETTE = {'amber': ((1.0, 0.62, 0.22), (0.95, 0.30, 0.03)), 'crimson': ((1.0, 0.30, 0.22), (0.85, 0.02, 0.01))}


# ----------------------------------------------------------------------------------------------- small helpers
def smooth(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


EASE = {'linear': lambda k: k, 'smooth': smooth, 'out': lambda k: 1 - (1 - k) ** 3, 'in': lambda k: k ** 3,
        'inout': lambda k: smooth(smooth(k))}


def new_obj(name, me, parent=None):
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if parent:
        ob.parent = parent
    return ob


def mat_paper(name, rgb, rough=0.85, emit=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*rgb, 1); p.inputs['Roughness'].default_value = rough
    if emit:
        p.inputs['Emission Color'].default_value = (*rgb, 1); p.inputs['Emission Strength'].default_value = emit
    return m


def hex_rgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v ** 2.2 for v in c)                        # sRGB → linear


# ----------------------------------------------------------------------------------------------- tree prop (film.props.trees)
def build_tree(tr, parent):
    """The engine's paper tree (engine/motion.js makeTree): a stump, and a top in two halves that the export moves."""
    H, cy, R = tr.get('height', 3.2), tr.get('cut', {}).get('y', 1.1), 0.16
    sc = tr.get('crown', 0.7)
    bark, blossom = mat_paper('TREE_bark', (0.07, 0.04, 0.025)), mat_paper('TREE_crown', hex_rgb(tr.get('color', '#e9a3b4')), 0.8, 0.02)
    B = lambda p: Vector((p[0], -p[2], p[1]))

    def frustum(bm, r0, r1, y0, y1, th0, th1, n, mat):
        ring = lambda r, y: [bm.verts.new(B((r * math.sin(th0 + (th1 - th0) * i / n), y, r * math.cos(th0 + (th1 - th0) * i / n)))) for i in range(n + 1)]
        a, b = ring(r0, y0), ring(max(r1, 1e-4), y1)
        for i in range(n):
            f = bm.faces.new((a[i], a[i + 1], b[i + 1], b[i])); f.material_index = mat
        if th1 - th0 < math.tau - 1e-3:                       # a half: close the flat cut face
            f = bm.faces.new((a[0], b[0], b[-1], a[-1])); f.material_index = mat
        for rg in (a, b):
            if len({tuple(v.co) for v in rg}) > 2:
                try:
                    f = bm.faces.new(rg); f.material_index = mat
                except ValueError:
                    pass
    bm = bmesh.new()
    frustum(bm, R * 1.2, R * 0.95, 0, cy, 0, math.tau, 6, 0)
    me = bpy.data.meshes.new('TREE_stump'); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    me.materials.append(bark)
    stump = new_obj('TREE_stump', me, parent)
    base = tr.get('base', [tr['x'], 0, tr['z']])
    stump.location = rt.v3(base)
    halves = []
    tiers = [(0.5, 1.15, 0.9), (0.95, 0.95, 0.85), (1.35, 0.72, 0.75), (1.7, 0.45, 0.6)]
    for kk in (0, 1):
        bm = bmesh.new()
        frustum(bm, R * 0.95, R * 0.7, 0, H - cy, kk * math.pi, kk * math.pi + math.pi, 3, 0)
        for y, r, hh in tiers:
            yc = y + (H - cy - 2.0)
            frustum(bm, r * sc, 0.0, yc - hh * sc / 2, yc + hh * sc / 2, kk * math.pi, kk * math.pi + math.pi, 5, 1)
        me = bpy.data.meshes.new(f'TREE_top{kk}'); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
        me.materials.append(bark); me.materials.append(blossom)
        ob = new_obj(f'TREE_top{kk}', me, parent)
        ob.rotation_mode = 'QUATERNION'
        halves.append(ob)
    return {'stump': stump, 'halves': halves}


def key_tree(tree, T, frame):
    for ob, h in zip(tree['halves'], T['halves']):
        ob.location = rt.v3(h[:3])
        ob.rotation_quaternion = rt.q3(h[3:]).to_quaternion()
        ob.keyframe_insert('location', frame=frame); ob.keyframe_insert('rotation_quaternion', frame=frame)


# ----------------------------------------------------------------------------------------------- slash of light
def slash_material(colour='amber', strength=26.0):
    hot, body = PALETTE[colour]
    m = bpy.data.materials.new('SLASH_light'); m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes['Principled BSDF'])
    out = nt.nodes['Material Output']
    uv = nt.nodes.new('ShaderNodeUVMap')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uv.outputs['UV'], sep.inputs[0])            # u = age (0 new … 1 old), v = along the blade (0 base … 1 tip)
    # colour: white-hot where the blade is now, amber/crimson behind it
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (1.0, 0.93, 0.80, 1)
    ramp.color_ramp.elements[1].position = 0.45; ramp.color_ramp.elements[1].color = (*body, 1)
    mid = ramp.color_ramp.elements.new(0.14); mid.color = (*hot, 1)
    nt.links.new(sep.outputs['X'], ramp.inputs['Fac'])
    # brightness: falls with age; strongest in the outer half of the blade; soft at the base and at the very tip
    age = nt.nodes.new('ShaderNodeMath'); age.operation = 'POWER'
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(sep.outputs['X'], inv.inputs[1]); nt.links.new(inv.outputs[0], age.inputs[0]); age.inputs[1].default_value = 2.2
    prof = nt.nodes.new('ShaderNodeValToRGB')
    prof.color_ramp.elements[0].position = 0.0; prof.color_ramp.elements[0].color = (0, 0, 0, 1)
    prof.color_ramp.elements[1].position = 1.0; prof.color_ramp.elements[1].color = (0.25, 0.25, 0.25, 1)
    e = prof.color_ramp.elements.new(0.55); e.color = (0.55, 0.55, 0.55, 1)
    e = prof.color_ramp.elements.new(0.9); e.color = (1, 1, 1, 1)
    nt.links.new(sep.outputs['Y'], prof.inputs['Fac'])
    # torn-paper streaks along the sweep, so the light is not a flat sheet
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.0; nz.inputs['Detail'].default_value = 3.0
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (0.6, 14.0, 1.0)
    nt.links.new(uv.outputs['UV'], mp.inputs['Vector']); nt.links.new(mp.outputs[0], nz.inputs['Vector'])
    st = nt.nodes.new('ShaderNodeMapRange'); st.inputs['From Min'].default_value = 0.35; st.inputs['From Max'].default_value = 0.7
    st.inputs['To Min'].default_value = 0.35; st.inputs['To Max'].default_value = 1.0
    nt.links.new(nz.outputs['Fac'], st.inputs['Value'])
    a1 = nt.nodes.new('ShaderNodeMath'); a1.operation = 'MULTIPLY'
    a2 = nt.nodes.new('ShaderNodeMath'); a2.operation = 'MULTIPLY'
    nt.links.new(age.outputs[0], a1.inputs[0]); nt.links.new(prof.outputs['Color'], a1.inputs[1])
    nt.links.new(a1.outputs[0], a2.inputs[0]); nt.links.new(st.outputs[0], a2.inputs[1])
    em = nt.nodes.new('ShaderNodeEmission'); em.name = 'EMIT'; em.inputs['Strength'].default_value = strength
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(a2.outputs[0], mix.inputs['Fac']); nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m.blend_method = 'BLEND'
    return m


class Slash:
    """The blade's own sweep as a ribbon of light. Rebuilt for the frame being rendered (nothing is keyframed)."""

    def __init__(self, motion, cid, solved, parent, colour='amber', min_speed=7.0, life=0.06):
        self.mo, self.cid, self.solved = motion, cid, solved
        self.min_speed, self.life = min_speed, life
        self.me = bpy.data.meshes.new('SLASH')
        self.me.materials.append(slash_material(colour))
        self.ob = new_obj('SLASH', self.me, parent)
        self.ob.visible_shadow = False
        L = bpy.data.lights.new('SLASH_flare', 'POINT'); L.color = PALETTE[colour][0]; L.shadow_soft_size = 0.25; L.energy = 0
        self.flare = new_obj('SLASH_flare', L, parent)
        self.len = motion['meta']['sword'].get('bladeLen', 0.91)

    def _rebase(self, i):
        """engine sword position → this character's sword position at sub-sample i (the offset is known on whole frames)"""
        sub = self.mo['sub']
        f = i / sub
        f0 = int(math.floor(f)); f1 = min(f0 + 1, len(self.mo['frames']) - 1)
        off = []
        for ff in (f0, f1):
            ff = min(max(ff, min(self.solved)), max(self.solved))
            eng = self.mo['frames'][ff]['cast'][self.cid]['sword'][0]
            off.append(self.solved[ff]['SWORD'].translation - eng)
        return off[0].lerp(off[1], f - f0)

    def update(self, frame):
        S = self.mo['samples']; sub = self.mo['sub']
        i1 = min(frame * sub, len(S) - 1)
        tb1 = S[i1]['tb']
        pts = []
        i = i1
        while i >= 0 and tb1 - S[i]['tb'] <= self.life + 1e-6 and len(pts) < 80:
            sp, sq = rt.sample_sword(S[i], self.cid)
            pts.append((S[i]['tb'], sp + self._rebase(i), sq))
            i -= 1
        pts.reverse()                                        # oldest first
        speed = 0.0
        if len(pts) >= 2:
            (ta, pa, qa), (tb, pb, qb) = pts[-2], pts[-1]
            tip = lambda p, q: p + q @ Vector((self.len, 0, 0))
            speed = (tip(pb, qb) - tip(pa, qa)).length / max(tb - ta, 1e-4)
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new('UVMap')
        peak = 0.0
        if len(pts) >= 2:
            rows = []
            for seg, ((ta, pa, qa), (tb, pb, qb)) in enumerate(zip(pts, pts[1:])):
                tipv = ((pb + qb @ Vector((self.len, 0, 0))) - (pa + qa @ Vector((self.len, 0, 0)))).length / max(tb - ta, 1e-4)
                peak = max(peak, tipv)
                n = 4
                for j in range(n + (1 if seg == len(pts) - 2 else 0)):
                    u = j / n
                    p = pa.lerp(pb, u); q = qa.slerp(qb, u); t = ta + (tb - ta) * u
                    rows.append((t, p + q @ Vector((self.len * 0.12, 0, -0.012)), p + q @ Vector((self.len * 1.03, 0, -0.012)), tipv))
            if peak >= self.min_speed:
                gain = smooth((peak - self.min_speed) / self.min_speed)
                vs = []
                for t, a, b, tv in rows:
                    age = min(1.0, (tb1 - t) / self.life)
                    # slow parts of the sweep show no light: push their age to 1
                    age = max(age, 1.0 - smooth(tv / self.min_speed) * gain)
                    cols = [a.lerp(b, v) for v in (0.0, 0.5, 0.8, 1.0)]
                    vs.append((age, [bm.verts.new(c) for c in cols]))
                for (g0, r0), (g1, r1) in zip(vs, vs[1:]):
                    for j, (v0, v1) in enumerate(((0.0, 0.5), (0.5, 0.8), (0.8, 1.0))):
                        f = bm.faces.new((r0[j], r0[j + 1], r1[j + 1], r1[j]))
                        for lp, (uu, vv) in zip(f.loops, ((g0, v0), (g0, v1), (g1, v1), (g1, v0))):
                            lp[uvl].uv = (uu, vv)
        bm.to_mesh(self.me); bm.free()
        self.me.update()
        k = smooth((peak - self.min_speed) / (2 * self.min_speed)) if peak > self.min_speed else 0.0
        if pts:
            _, p, q = pts[-1]
            self.flare.location = p + q @ Vector((self.len * 0.6, 0, 0))
        self.flare.data.energy = 260.0 * k
        return peak


# ----------------------------------------------------------------------------------------------- ground dust
def dust_material():
    m = bpy.data.materials.new('DUST'); m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (0.55, 0.47, 0.38, 1); p.inputs['Roughness'].default_value = 1.0
    uv = nt.nodes.new('ShaderNodeUVMap')
    grad = nt.nodes.new('ShaderNodeTexGradient'); grad.gradient_type = 'SPHERICAL'
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Location'].default_value = (-1, -1, 0); mp.inputs['Scale'].default_value = (2, 2, 1)
    nt.links.new(uv.outputs['UV'], mp.inputs['Vector']); nt.links.new(mp.outputs[0], grad.inputs['Vector'])
    col = nt.nodes.new('ShaderNodeVertexColor'); col.layer_name = 'a'
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    nt.links.new(grad.outputs['Fac'], mul.inputs[0]); nt.links.new(col.outputs['Color'], mul.inputs[1])
    nt.links.new(mul.outputs[0], p.inputs['Alpha'])
    m.blend_method = 'BLEND'
    return m


class Dust:
    """Paper-dust puffs for the engine's ground events (dash, skid, take-off, landing): camera-facing soft cards,
    a deterministic burst per event, rebuilt for the frame being rendered."""

    def __init__(self, events, parent, life=1.1):
        self.events, self.life = events or [], life
        self.me = bpy.data.meshes.new('DUST'); self.me.materials.append(dust_material())
        self.ob = new_obj('DUST', self.me, parent)
        self.ob.visible_shadow = False

    def update(self, t, cam_matrix):
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new('UVMap'); cl = bm.loops.layers.color.new('a')
        R = cam_matrix.to_3x3()
        cx, cy = R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0))
        for n, ev in enumerate(self.events):
            a = t - ev['t']
            if a < 0 or a > self.life:
                continue
            rnd = random.Random(1000 + n)
            p0 = Vector((ev['pos'][0], -ev['pos'][1], 0.0))
            d = Vector((ev['dir'][0], -ev['dir'][1], 0.0))
            power = min(1.0, 0.35 + ev.get('speed', 3) / 14)
            count = {'skid': 34, 'land': 30, 'dash': 22, 'takeoff': 18}.get(ev['kind'], 18)
            for _ in range(count):
                ang = rnd.uniform(-math.pi, math.pi)
                side = Vector((math.cos(ang), math.sin(ang), 0))
                if ev['kind'] == 'skid':                     # thrown forward along the slide, low
                    v = d * rnd.uniform(1.2, 3.4) * power + side * rnd.uniform(0, 0.7); up = rnd.uniform(0.25, 0.9)
                elif ev['kind'] == 'dash':                   # kicked out behind the runner
                    v = -d * rnd.uniform(0.8, 2.6) * power + side * rnd.uniform(0, 0.6); up = rnd.uniform(0.3, 1.1)
                else:                                        # a ring: landing and take-off
                    v = side * rnd.uniform(0.7, 2.2) * power; up = rnd.uniform(0.15, 0.7)
                drag = 3.2
                travel = (1 - math.exp(-drag * a)) / drag
                pos = p0 + v * travel + Vector((0, 0, 0.05 + up * travel * 0.9 - 0.12 * a * a))
                size = (0.07 + rnd.uniform(0.10, 0.34) * (1 - math.exp(-3 * a))) * (0.7 + 0.5 * power)
                alpha = rnd.uniform(0.35, 0.8) * (1 - smooth(a / self.life)) * smooth(a / 0.05)
                vs = [bm.verts.new(pos + cx * sx * size + cy * sy * size) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                f = bm.faces.new(vs)
                for lp, uvv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                    lp[uvl].uv = uvv; lp[cl] = (alpha, alpha, alpha, 1)
        bm.to_mesh(self.me); bm.free()
        self.me.update()


# ----------------------------------------------------------------------------------------------- camera
class Camera:
    """--cam film: the engine's camera, frame by frame. Otherwise named moves (library/blender-cameras.json): every
    move is an arc around the hero given by azimuth / distance / heights / lens at its start and end."""

    def __init__(self, motion, cid, solved_ref, parent, plan, lib):
        self.mo, self.cid, self.plan, self.lib = motion, cid, plan, lib
        cd = bpy.data.cameras.new('CAM_film'); cd.sensor_fit = 'VERTICAL'; cd.clip_start = 0.02; cd.clip_end = 800
        cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.8
        self.cam = new_obj('CAM_film', cd, parent)
        self.cam.rotation_mode = 'QUATERNION'
        bpy.context.scene.camera = self.cam
        self.last = None

    def hero(self, f):
        J = self.mo['frames'][min(max(f, 0), len(self.mo['frames']) - 1)]['cast'][self.cid]['J']
        return J['root'][0], J['root'][1] @ Vector((0, -1, 0)), J['chest'][0]

    def film_cam(self, f):
        c = self.mo['frames'][f]['cam']
        R = rt.C3 @ Quaternion((c[6], c[3], c[4], c[5])).to_matrix()     # camera local axes are the same in three.js and Blender
        return rt.v3(c[:3]), R.to_quaternion(), c[7]

    def beat(self, t):
        b = None
        for x in self.plan:
            if t >= x['t'] - 1e-6:
                b = x
        return b or self.plan[0]

    def at(self, f):
        t = self.mo['frames'][f]['t']
        b = self.beat(t) if self.plan else {'move': 'film'}
        if b.get('move', 'film') == 'film':
            return self.film_cam(f)
        mv = {**self.lib['moves'][b['move']], **{k: v for k, v in b.items() if k not in ('t', 'move', 'until', 'note')}}
        nxt = [x['t'] for x in self.plan if x['t'] > b['t'] + 1e-6]
        t0 = b['t'] if self.plan and len(self.plan) > 1 else 0.0
        t1 = b.get('until', nxt[0] if nxt else self.mo['meta']['film']['duration'])
        k = EASE[mv.get('ease', 'smooth')]((t - t0) / max(t1 - t0, 1e-3))
        pair = lambda key, d: (mv.get(key, d) if isinstance(mv.get(key, d), (list, tuple)) else [mv.get(key, d)] * 2)
        lerp = lambda key, d: pair(key, d)[0] + (pair(key, d)[1] - pair(key, d)[0]) * k
        # the subject: the hero's chest, smoothed over a few frames so a snap of the body does not shake the lens
        n = int(mv.get('smooth', 4))
        root = sum((self.hero(ff)[0] for ff in range(f - n, f + n + 1)), Vector()) / (2 * n + 1)
        chest = sum((self.hero(ff)[2] for ff in range(f - n, f + n + 1)), Vector()) / (2 * n + 1)
        f_beat = int(round(t0 * self.mo['fps']))
        basis = mv.get('basis', 'hero0')
        if basis == 'world':
            base = 0.0
        else:                                                # 'hero' = follows his facing; 'hero0' = his facing when the beat starts
            fw = self.hero(f if basis == 'hero' else f_beat)[1]
            base = math.atan2(fw.x, -fw.y)
        az = base + math.radians(lerp('az', 30))
        dist, h, lz = lerp('dist', 4.0), lerp('height', 1.2), lerp('look', 1.0)
        if mv.get('breathe'):                                # "coming back, going front": the lens breathes with the blade
            sp = self.blade_speed(f)
            dist *= 1.0 - mv['breathe'] * smooth(sp / 30.0)
        pos = Vector((root.x + math.sin(az) * dist, root.y - math.cos(az) * dist, max(0.06, h + (chest.z - 1.1) * mv.get('follow_y', 0.5))))
        look = Vector((chest.x, chest.y, lz + (chest.z - 1.1) * mv.get('follow_look', 1.0)))
        lead = mv.get('lead', 0.0)
        if lead:
            v = (self.hero(f + 2)[0] - self.hero(f - 2)[0])
            look += Vector((v.x, v.y, 0)) * lead
        q = (look - pos).to_track_quat('-Z', 'Y')
        if mv.get('roll'):
            q = q @ Quaternion((0, 0, 1), math.radians(lerp('roll', 0)))
        return pos, q, lerp('fov', 34)

    def blade_speed(self, f):
        S = self.mo['samples']; sub = self.mo['sub']; L = 0.91
        i = min(f * sub, len(S) - 1); j = max(0, i - sub)
        tip = lambda s: rt.sample_sword(s, self.cid)[0] + rt.sample_sword(s, self.cid)[1] @ Vector((L, 0, 0))
        return (tip(S[i]) - tip(S[j])).length / max(S[i]['tb'] - S[j]['tb'], 1e-3)

    def key(self, f, frame):
        pos, q, fov = self.at(f)
        if self.last is not None and self.last.dot(q) < 0:
            q.negate()
        self.last = q.copy()
        cam = self.cam
        cam.location, cam.rotation_quaternion = pos, q
        cam.data.angle = math.radians(fov)
        cam.keyframe_insert('location', frame=frame); cam.keyframe_insert('rotation_quaternion', frame=frame)
        cam.data.keyframe_insert('lens', frame=frame)
        return pos, q


# ----------------------------------------------------------------------------------------------- main
def main():
    film_path = arg('film', 'film/dash-test.json')
    name = os.path.splitext(os.path.basename(film_path))[0]
    film = json.load(open(os.path.join(REPO, film_path) if not os.path.isabs(film_path) else film_path))
    motion_path = arg('motion', os.path.join(REPO, 'output', name + '.motion.json'))
    if arg('bvh'):
        pass                                                 # motion capture: the BVH is read after the scene is reset (below)
    elif not os.path.exists(motion_path) or os.path.getmtime(motion_path) < os.path.getmtime(os.path.join(REPO, film_path)):
        print('[film_blender] exporting the motion from the preview engine…')
        subprocess.run(['node', 'tools/export_motion.mjs', film_path, '--out', motion_path], cwd=REPO, check=True)
    mo = None if arg('bvh') else rt.load_motion(motion_path)
    if arg('set'):
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(arg('set')))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    if arg('bvh'):
        mo = rt.bvh_motion(os.path.abspath(arg('bvh')), two_hand=flag('two-hand'), forward=arg('bvh-forward', '-Y'))
        name = os.path.splitext(os.path.basename(arg('bvh')))[0]
    NF = len(mo['frames'])
    if arg('times'):
        frames = [min(NF - 1, int(round(float(t) * mo['fps']))) for t in arg('times').split(',')]
    elif arg('frames'):
        a, b = [int(v) for v in arg('frames').split('-')]
        frames = list(range(a, min(b, NF - 1) + 1))
    else:
        frames = [0]
    out_dir = os.path.abspath(arg('out', os.path.join(REPO, 'output', 'blender', name)))
    os.makedirs(out_dir, exist_ok=True)

    sc = bpy.context.scene
    root = bpy.data.objects.new('FILM_ROOT', None); sc.collection.objects.link(root)
    if arg('at'):
        x, y, z, yaw = [float(v) for v in arg('at').split(',')]
        root.matrix_world = Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(yaw), 4, 'Z')

    # ----- cast
    cids = [c for c in mo['frames'][0]['cast']]
    models = (arg('model', 'ronin_base')).split(',')
    f_lo, f_hi = min(frames) - 1, max(frames) + 1
    chars, solved = {}, {}
    for n, cid in enumerate(cids):
        demonic = mo['meta']['cast'].get(cid, {}).get('demonic', False)
        ch = rt.build_character(models[min(n, len(models) - 1)], mode=arg('mode', 'heat'), name='RIG_' + cid, demonic=demonic)
        ch['rig'].parent = root
        ch['sword'].parent = root
        solved[cid] = rt.bake(ch, mo, cid, f_lo, f_hi)
        chars[cid] = ch
    hero = cids[0]

    # ----- props
    trees = [build_tree(tr, root) for tr in mo['meta'].get('trees', [])]
    for f in range(max(0, f_lo), min(NF - 1, f_hi) + 1):
        for tree, T in zip(trees, mo['frames'][f]['trees']):
            key_tree(tree, T, f + 1)

    # ----- stage and light
    if not arg('set'):
        rt.stage_dark(sc, fog=float(arg('fog', 0.0)))
        backdrop(root, mo)
    lib = json.load(open(os.path.join(REPO, 'library', 'blender-cameras.json')))
    cam_arg = arg('cam', 'circle' if arg('bvh') else 'film')
    if arg('bvh') and cam_arg == 'film':
        raise SystemExit('a BVH has no film camera: use --cam <move> (for example circle, low-hero, push-pull)')
    if cam_arg == 'film':
        plan = None
    elif cam_arg == 'plan':
        plan = lib.get('plans', {}).get(name)
        if not plan:
            print(f'[film_blender] no camera plan for "{name}" in library/blender-cameras.json: using the film camera')
    else:
        if cam_arg not in lib['moves']:
            raise SystemExit(f'unknown camera move "{cam_arg}". Known: film, plan, ' + ', '.join(lib['moves']))
        plan = [{'t': 0, 'move': cam_arg}]
    camera = Camera(mo, hero, solved[hero], root, plan, lib)
    for f in range(max(0, f_lo), min(NF - 1, f_hi) + 1):
        camera.key(f, f + 1)
    for ob in (camera.cam, camera.cam.data):
        if ob.animation_data and ob.animation_data.action:
            for fc in rt._fcurves(ob.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    colour = 'crimson' if mo['meta']['cast'].get(hero, {}).get('demonic') else 'amber'
    slash = None if flag('no-slash') else Slash(mo, hero, solved[hero], root, colour)
    ground = (mo['meta'].get('events') or {}).get('ground', [])
    dust = None if flag('no-dust') else Dust(ground, root)

    rt.render_settings(sc, arg('res', '432x768'), arg('samples', 16), blur=not flag('no-blur'), threads=int(arg('threads', 2)))
    if not flag('no-glare'):
        glare(sc)
    power = float(arg('light', 1.0))
    cuts = set(int(round(c * mo['fps'])) for c in (mo['meta']['camera'].get('cuts') or [])) if plan is None else \
        set(int(round(b['t'] * mo['fps'])) for b in plan if b.get('cut', True))

    for f in frames:
        sc.frame_set(f + 1)
        t = mo['frames'][f]['t']
        cpos, cq = camera.cam.location.copy(), camera.cam.rotation_quaternion.copy()
        chest = solved[hero][f]['chest'].translation
        light_rig(sc, root, cpos, chest, power, with_set=bool(arg('set')))
        camera.cam.data.dof.focus_distance = max(0.3, (chest - cpos).length)
        camera.cam.data.dof.aperture_fstop = 2.0 if (chest - cpos).length < 2.5 else 3.2
        peak = slash.update(f) if slash else 0.0
        if dust:
            dust.update(t, camera.cam.matrix_world)
        # no motion blur across a hard cut (the camera jumps between this frame and its neighbours)
        sc.render.use_motion_blur = (not flag('no-blur')) and not ({f, f + 1} & cuts)
        sc.render.filepath = os.path.join(out_dir, (f't{t:06.3f}' if arg('times') else f'f{f:04d}') + '.png')
        bpy.ops.render.render(write_still=True)
        print(f'[film_blender] frame {f} t={t:.3f}s blade {peak:.0f} m/s → {sc.render.filepath}')
    if arg('save'):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(arg('save')))


def backdrop(root, mo):
    """2.5D depth for the dark stage (reference: layered paper cut-outs with a camera moving through them): three rows
    of torn-paper ridge silhouettes far behind the action, each a little lighter and hazier than the one in front."""
    xs = [fr['cast'][c]['J']['root'][0].x for fr in mo['frames'] for c in fr['cast']]
    cx = (min(xs) + max(xs)) / 2
    rnd = random.Random(7)
    for n, (dist, hgt, tone) in enumerate(((16, 3.2, 0.010), (26, 6.0, 0.018), (40, 10.0, 0.03))):
        bm = bmesh.new()
        N, W = 44, 150.0
        top = []
        y = 0.0
        for i in range(N + 1):
            y = 0.6 * y + rnd.uniform(-1, 1) * 0.5
            peak = math.exp(-((i / N - (0.3 + 0.2 * n)) ** 2) / 0.02) * 0.9
            top.append(hgt * (0.45 + 0.28 * y + peak * 0.6))
        for side in (1, -1):                                  # a ridge behind (+y) and one in front (-y) of the action line
            vb = [bm.verts.new((cx - W / 2 + W * i / N, side * dist, -0.5)) for i in range(N + 1)]
            vt = [bm.verts.new((cx - W / 2 + W * i / N, side * dist, top[i if side > 0 else N - i])) for i in range(N + 1)]
            for i in range(N):
                bm.faces.new((vb[i], vb[i + 1], vt[i + 1], vt[i]))
        me = bpy.data.meshes.new(f'BACKDROP_{n}'); bm.to_mesh(me); bm.free()
        m = mat_paper(f'BACKDROP_{n}', (tone, tone * 1.1, tone * 1.5), 1.0, emit=0.55)
        me.materials.append(m)
        ob = new_obj(f'BACKDROP_{n}', me, root)
        ob.visible_shadow = False


def light_rig(sc, root, cam, subject, power=1.0, with_set=False):
    """Light that is re-set for every frame from where the camera stands, like a film crew does per shot:
    a strong cool rim from behind the subject (far side from the lens), a warm key from the lens's left, a faint fill."""
    to_cam = Vector((cam.x - subject.x, cam.y - subject.y, 0))
    to_cam = to_cam.normalized() if to_cam.length > 1e-3 else Vector((0, -1, 0))
    right = Vector((-to_cam.y, to_cam.x, 0))
    aim = Vector((subject.x, subject.y, max(0.9, subject.z)))
    k = power * (0.45 if with_set else 1.0)
    obs = [
        rt.spot('LIGHT_rim', aim - to_cam * 3.4 + right * 2.2 + Vector((0, 0, 2.2)), aim + Vector((0, 0, 0.1)), 1900 * k, (0.55, 0.70, 1.0), 30, 0.5, 0.12),
        rt.spot('LIGHT_rim2', aim - to_cam * 3.0 - right * 2.8 + Vector((0, 0, 1.0)), aim, 700 * k, (0.60, 0.72, 1.0), 32, 0.5, 0.2),
        rt.spot('LIGHT_key', aim + to_cam * 2.6 - right * 2.6 + Vector((0, 0, 2.7)), aim, 800 * k, (1.0, 0.84, 0.66), 30, 0.6, 0.35),
        rt.spot('LIGHT_fill', aim + to_cam * 3.5 + right * 2.5 + Vector((0, 0, 0.5)), aim, 70 * k, (0.45, 0.55, 1.0), 40, 0.6, 0.5),
    ]
    for o in obs:
        if o.parent is not root:
            o.parent = root
    return obs


def glare(sc):
    """a soft bloom on the brightest things (the slash, the lantern) — the compositor's Glare node"""
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new('CompositorNodeRLayers')
    gl = nt.nodes.new('CompositorNodeGlare')
    try:
        gl.glare_type = 'BLOOM'
    except TypeError:
        gl.glare_type = 'FOG_GLOW'
    for key, val in (('threshold', 1.6), ('size', 7), ('quality', 'MEDIUM'), ('mix', -0.55)):
        try:
            setattr(gl, key, val)                            # Blender up to 4.3: node properties
        except Exception:                                    # noqa: BLE001
            pass
    for key, val in (('Threshold', 1.6), ('Strength', 0.45), ('Size', 0.55)):
        if key in gl.inputs:                                 # Blender 4.4+: the same settings are sockets
            gl.inputs[key].default_value = val
    comp = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(rl.outputs['Image'], gl.inputs['Image'])
    nt.links.new(gl.outputs['Image'], comp.inputs['Image'])


if __name__ == '__main__':
    main()

"""PRODUCTION BAKE: the one place the body, the props and the paper are solved, for every render.

Why (review, 26 Nov): the draw test ran the grip, the scabbard draw, the body boundary and the cloth springs,
but the episode renderer (film_modular.py) keyed the timeline's pose and sword separately and never called
them, so a good test clip said nothing about Episode 1. And those passes carry STATE from frame to frame
(spring speed, the scabbard's turn, the sword's turn in the hand), so a render worker that starts at frame
900 must not re-simulate from frame 900.

So: the whole timeline is solved ONCE, in order, from frame 0, and saved to output/<film>.bake.json with a
stamp (a hash of the timeline, the film file and the Blender code). Every render process - one or many,
any chunk, any order - loads that bake and keys exactly the same joints, bones, sword, scabbard and hands.

  bake = production_bake.solve(...)          # or load() when the stamp matches
  production_bake.apply(bake, frame, ...)    # key one frame from the bake
The checks the review asked for are measured on the FINAL solved pose of every frame and printed.
"""
import hashlib
import json
import math
import os

import bpy
from mathutils import Matrix, Quaternion, Vector


def stamp(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        if os.path.isfile(p):
            h.update(p.encode())
            with open(p, 'rb') as fh:
                h.update(fh.read())
    return h.hexdigest()[:16]


def _code_files(repo):
    out = [os.path.join(repo, 'blender', 'film_modular.py'), os.path.join(repo, 'blender', 'production_bake.py')]
    for sub in ('props', 'character'):
        d = os.path.join(repo, 'blender', sub)
        out += [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.py')]
    return out


def bake_stamp(repo, film):
    return stamp([os.path.join(repo, 'output', film + '.timeline.json'),
                  os.path.join(repo, 'film', film + '.json')] + _code_files(repo))


def check_pose_channels(TL, f0, f1, film):
    """Every visible actor must carry the 46 pose channels on every frame asked for: the paper rig is driven by
    them. Films on engine/index.html export bones only (docs/EPISODE-1.md blocker 1)."""
    bad = []
    for i in range(f0, f1 + 1):
        for aid, act in TL['frames'][i]['actors'].items():
            if act.get('hidden'):
                continue
            p = act.get('pose')
            if not isinstance(p, dict) or len(p) < 40:
                bad.append((i, aid))
                if len(bad) > 3:
                    break
        if len(bad) > 3:
            break
    if bad:
        raise SystemExit(
            f"[bake] {film}: no pose channels for {', '.join(f'{a} at frame {i}' for i, a in bad)}. The paper rig needs "
            "the 46 channels engine/motion.html exports; this film's timeline has bones only (its page is probably "
            "engine/index.html). Put the film on engine/motion.html (page) and run tools/timeline.mjs again.")


# --------------------------------------------------------------------------- solve (once, in order)
class Actor:
    def __init__(self, aid, rig, ch_objects, draw=None, springs=None):
        self.aid, self.rig, self.objects, self.draw, self.springs = aid, rig, ch_objects, draw, springs


def solve(TL, actors, fps, checks=True, body_shrink=0.035):
    """Run every frame of the timeline in order through the passes; return the bake dict."""
    import body_capsules as BC
    import sword_draw as SD
    sc = bpy.context.scene
    frames = TL['frames']
    out = {'fps': fps, 'n': len(frames), 'actors': {}, 'checks': {}}
    body = {a.aid: BC.BodyCapsules(a.rig, shrink=body_shrink) for a in actors}
    garment = {a.aid: BC.BodyCapsules(a.rig) for a in actors}
    sleeves = {a.aid: [o for o in a.objects if o.get('pc_recipe') == 'tamoto_wide'] for a in actors}
    rec = {a.aid: {'J': [], 'sword': [], 'saya': [], 'grip': [], 'segs': []} for a in actors}
    chk = {a.aid: {'blade/body': [], 'blade/garment': [], 'arm.R/body': [], 'arm.L/body': [],
                   'sleeve-paper.R/body': [], 'sleeve-paper.L/body': [], 'grip_rel': [], 'phase': []}
           for a in actors}
    for i, fr in enumerate(frames):
        f = i + 1
        sc.frame_set(f)
        for a in actors:
            act = fr['actors'].get(a.aid)
            if not act or act.get('hidden') or not isinstance(act.get('pose'), dict):
                rec[a.aid]['J'].append(None)
                continue
            if a.draw:
                phase = a.draw.step(f, dict(act['pose']))
            else:
                a.rig.pose(act['pose'])
                phase = None
            if a.springs:
                a.springs.step()
            bpy.context.view_layer.update()
            J = a.rig.J
            rec[a.aid]['J'].append({n: [*e.location, *e.rotation_euler] for n, e in J.items()})
            body[a.aid].update()
            rec[a.aid]['segs'].append([(n, list(p), list(q), r) for n, p, q, r in body[a.aid].segs] +
                                      [('hand.' + s, list(J[s + 'H'].matrix_world.translation),
                                        list((J[s + 'H'].matrix_world @ (a.draw.H if a.draw else SD.hand_holder())).translation), 0.035)
                                       for s in ('r', 'l')])
            if a.draw:
                for key, ob in (('sword', a.draw.sword), ('saya', a.draw.saya)):
                    loc, rot, _ = ob.matrix_world.decompose()
                    rec[a.aid][key].append([*loc, *rot])
                vis = {s: (not grip.hide_render) for s, (_o, grip) in a.draw.hands.items()}
                rec[a.aid]['grip'].append(vis)
                chk[a.aid]['phase'].append(phase)
            if checks:
                _check_frame(a, f, phase, body[a.aid], garment[a.aid], sleeves[a.aid], chk[a.aid])
    for a in actors:
        out['actors'][a.aid] = rec[a.aid]
        out['checks'][a.aid] = chk[a.aid]
        if a.draw is not None:
            chk[a.aid]['blade_turned_out'] = {str(k): v for k, v in sorted(a.draw.pushed.items())}
            print('[bake] %s blade turned out of the body on frames %s' % (a.aid, chk[a.aid]['blade_turned_out']))
    return out


def _check_frame(a, f, phase, body, garment, sleeves, chk):
    rig, d = a.rig, a.draw
    garment.update()
    if d is not None and phase in ('drawing', 'drawn'):
        # the blade along its REAL curve (katana_real's circle), edge and back too, against person and garment
        R, L = d.R, d.L
        for i in range(1, 25):
            s = L * i / 24
            for off in (-0.015, 0.0, 0.015):              # edge, centre line, back (the blade is ~3 cm wide)
                if R:
                    a_ = s / R                            # a point `off` from the centre line, on the circle
                    p = Vector(((R - off) * math.sin(a_), R - (R - off) * math.cos(a_), 0.0))
                else:
                    p = Vector((s, off, 0.0))
                w = d.sword.matrix_world @ p
                for key, cc in (('blade/body', body), ('blade/garment', garment)):
                    dd, who = cc.depth(w, skip=('forearm.R', 'forearm.L'))
                    if dd > 0:
                        chk[key].append((f, round(dd * 100, 1), who))
    for sd, ar in (('r', 'R'), ('l', 'L')):
        J = rig.J
        chain = [J[sd + j].matrix_world.translation for j in ('S', 'E', 'H')]
        worst = (0, '')
        for (p0, p1), rad in zip(zip(chain, chain[1:]), (0.035, 0.03)):
            for t in (0.5, 0.75, 1.0):
                dd, who = body.depth(p0.lerp(p1, t), skip=('upperarm.' + ar, 'forearm.' + ar))
                if dd + rad > worst[0]:
                    worst = (dd + rad, who)
        if worst[0] > 0:
            chk['arm.' + ar + '/body'].append((f, round(worst[0] * 100, 1), worst[1]))
    if sleeves:
        rig.sync_bones()
        dg = bpy.context.evaluated_depsgraph_get()
        for ob in sleeves:
            ar = 'R' if ob.get('pc_socket', '').endswith('.R') else 'L'
            me = ob.evaluated_get(dg).to_mesh()
            mw = ob.matrix_world
            worst = (0.0, '')
            for v in me.vertices:
                dd, who = body.depth(mw @ v.co, skip=('upperarm.' + ar, 'forearm.' + ar))
                if dd > worst[0]:
                    worst = (dd, who)
            ob.evaluated_get(dg).to_mesh_clear()
            if worst[0] > 0:
                chk['sleeve-paper.' + ar + '/body'].append((f, round(worst[0] * 100, 1), worst[1]))
    if d is not None and phase in ('grab', 'drawing', 'drawn'):
        rel = d.sword.matrix_world.inverted() @ (rig.J['rH'].matrix_world @ d.H)
        loc, rot, _ = rel.decompose()
        chk['grip_rel'].append((f, phase, [*loc], [*rot]))


def report(bake, F):
    lines = []
    for aid, c in bake['checks'].items():
        for key in ('blade/body', 'blade/garment', 'arm.R/body', 'arm.L/body', 'sleeve-paper.R/body', 'sleeve-paper.L/body'):
            rows = c.get(key, [])
            if rows:
                fr = sorted({r[0] for r in rows})
                mx = max(rows, key=lambda r: r[1])
                lines.append('[check] %s %-20s on %2d of %d frames, deepest %.1f cm (frame %d, %s)' % (
                    aid, key, len(fr), F, mx[1], mx[0], mx[2]))
            else:
                lines.append('[check] %s %-20s never' % (aid, key))
        held = [g for g in c.get('grip_rel', []) if g[1] in ('drawing', 'drawn')]
        if held:
            b_l, b_r = Vector(held[0][2]), Quaternion(held[0][3])
            dl = max(((Vector(g[2]) - b_l).length * 100, g[0]) for g in held)
            dr = max((math.degrees(Quaternion(g[3]).rotation_difference(b_r).angle), g[0]) for g in held)
            st = max((math.degrees(Quaternion(held[k][3]).rotation_difference(Quaternion(held[k - 1][3])).angle), held[k][0])
                     for k in range(1, len(held)))
            sl = max(((Vector(held[k][2]) - Vector(held[k - 1][2])).length * 100, held[k][0]) for k in range(1, len(held)))
            lines.append('[check] %s grip vs hilt (slide to end): drift %.1f cm (f%d), %.1f deg (f%d); one-frame %.1f cm (f%d), %.1f deg (f%d)'
                         % (aid, dl[0], dl[1], dr[0], dr[1], sl[0], sl[1], st[0], st[1]))
    return lines


# --------------------------------------------------------------------------- save / load / apply
def save(bake, path, stamp_):
    bake = dict(bake, stamp=stamp_)
    with open(path, 'w') as fh:
        json.dump(bake, fh, separators=(',', ':'))


def load(path, stamp_):
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        b = json.load(fh)
    return b if b.get('stamp') == stamp_ else None


def apply(bake, i, actors):
    """Key frame index i (0-based; Blender frame i+1) for every actor from the bake."""
    f = i + 1
    for a in actors:
        r = bake['actors'].get(a.aid)
        if not r or i >= len(r['J']) or r['J'][i] is None:
            continue
        for n, v in r['J'][i].items():
            e = a.rig.J[n]
            e.location = v[:3]
            e.rotation_euler = v[3:6]
            e.keyframe_insert('location', frame=f)
            e.keyframe_insert('rotation_euler', frame=f)
        bpy.context.view_layer.update()
        a.rig.sync_bones()
        a.rig.key_bones(f)
        if a.draw:
            k = sum(1 for x in r['J'][:i + 1] if x is not None) - 1
            for key, ob in (('sword', a.draw.sword), ('saya', a.draw.saya)):
                v = r[key][k]
                ob.location = v[:3]
                ob.rotation_mode = 'QUATERNION'
                ob.rotation_quaternion = v[3:7]
                ob.keyframe_insert('location', frame=f)
                ob.keyframe_insert('rotation_quaternion', frame=f)
            import sword_draw as SD
            for s, (opens, grip) in a.draw.hands.items():
                on = r['grip'][k].get(s, False)
                for o in opens:
                    SD.key_visible(o, f, not on)
                SD.key_visible(grip, f, on)


def build_mannequin(bake, actors, frames, sc, mat_fn):
    """The diagnostic mannequin: simple shapes on the baked joints (same motion, same camera), the paper hidden."""
    import bmesh
    clay = mat_fn('mannequin_clay', (0.62, 0.60, 0.57, 1), 0.6)
    joint = mat_fn('mannequin_joint', (0.85, 0.35, 0.15, 1), 0.5)
    handm = mat_fn('mannequin_hand', (0.95, 0.85, 0.30, 1), 0.5)
    for a in actors:
        for o in a.objects:
            if o.type == 'MESH':
                o.hide_render = True
                ad = o.animation_data
                if ad and ad.action:
                    for fc in [fc for fc in ad.action.fcurves if fc.data_path == 'hide_render']:
                        ad.action.fcurves.remove(fc)
        if a.draw:
            for _o, grip in a.draw.hands.values():
                grip.hide_render = True
                ad = grip.animation_data
                if ad and ad.action:
                    for fc in [fc for fc in ad.action.fcurves if fc.data_path == 'hide_render']:
                        ad.action.fcurves.remove(fc)
        segs_all = bake['actors'][a.aid]['segs']
        if not segs_all:
            continue
        for si, (name, _p, _q, r) in enumerate(segs_all[0]):
            me = bpy.data.meshes.new('MQ_%s_%s' % (a.aid, name))
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=r, depth=1.0)
            bm.to_mesh(me)
            bm.free()
            cyl = bpy.data.objects.new(me.name, me)
            me.materials.append(handm if name.startswith('hand') else clay)
            sc.collection.objects.link(cyl)
            cyl.rotation_mode = 'QUATERNION'
            ends = []
            for e in (0, 1):
                ms = bpy.data.meshes.new('MQJ_%s_%s_%d' % (a.aid, name, e))
                bm = bmesh.new()
                bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=r)
                bm.to_mesh(ms)
                bm.free()
                so = bpy.data.objects.new(ms.name, ms)
                ms.materials.append(handm if name.startswith('hand') else (joint if e == 0 else clay))
                sc.collection.objects.link(so)
                ends.append(so)
            for k, segs in enumerate(segs_all):
                f = frames[k] + 1 if frames else k + 1
                _n, p, q, _r = segs[si]
                p, q = Vector(p), Vector(q)
                dvec = q - p
                cyl.location = (p + q) / 2
                cyl.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(
                    dvec.normalized() if dvec.length > 1e-6 else Vector((0, 0, 1)))
                cyl.scale = (1, 1, max(dvec.length, 1e-4))
                for kk in ('location', 'rotation_quaternion', 'scale'):
                    cyl.keyframe_insert(kk, frame=f)
                for so, pt in zip(ends, (p, q)):
                    so.location = pt
                    so.keyframe_insert('location', frame=f)

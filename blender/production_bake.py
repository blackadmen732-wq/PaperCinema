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


def bake_stamp(repo, film, extra=()):
    """The bake's cache key: only what it solves. From the film file: cast, performances (not `drop`: that falls at
    render time), stage, motion and the clock; from the timeline: the actors and the body clock of every frame and
    sub-frame (not the camera, titles or sounds: changing a shot no longer re-bakes 60 s of motion); the bake code; and
    `extra` (the set file: the terrain the bodies stand on)."""
    h = hashlib.sha256()
    try:
        F = json.load(open(os.path.join(repo, 'film', film + '.json')))
        perf = {k: {kk: vv for kk, vv in (v or {}).items() if kk != 'drop'} for k, v in (F.get('performances') or {}).items()}
        key = {k: F.get(k) for k in ('cast', 'stage', 'motion', 'fps', 'duration')}
        key['performances'] = perf
        h.update(json.dumps(key, sort_keys=True).encode())
    except (OSError, ValueError):
        h.update(b'no film file')
    try:
        TL = json.load(open(os.path.join(repo, 'output', film + '.timeline.json')))
        h.update(json.dumps([(fr.get('actors'), fr.get('tb'), fr.get('rate')) for fr in TL['frames']], sort_keys=True).encode())
        h.update(json.dumps([sf.get('actors') for sf in TL.get('subframes') or []], sort_keys=True).encode())
        h.update(json.dumps(TL.get('actors'), sort_keys=True).encode())
    except (OSError, ValueError, KeyError):
        h.update(b'no timeline')
    h.update(stamp(_code_files(repo) + [p for p in extra if p]).encode())
    return h.hexdigest()[:16]


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
    def __init__(self, aid, rig, ch_objects, draw=None, springs=None, caps=None):
        self.aid, self.rig, self.objects, self.draw, self.springs = aid, rig, ch_objects, draw, springs
        self.caps, self.corr = caps, {}


def ground_sampler(sc, skip):
    """The walkable surface under a point, world metres: the highest UP-facing hit of a ray cast down from z_from onto
    every visible mesh that is not a character, a weapon, the sea or the sky (the same meshes tools' ground report
    measures against). None when nothing is under it. Without a set there is nothing: the film's own ground, z 0."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    obs = [o for o in sc.objects if o.type == 'MESH' and o not in skip and o.visible_get() and len(o.data.polygons)
           and not o.name.startswith(('SEA', 'SKY', 'PC_', 'MARK_', 'KATANA_', 'BOKKEN_')) and not o.get('pc_internal')
           and not (o.parent and o.parent.name.startswith(('KATANA_', 'BOKKEN_')))]
    trees = [(o.matrix_world.copy(), o.matrix_world.inverted(), BVHTree.FromObject(o, dg)) for o in obs]
    if not trees:
        return None

    def at(x, y, z_from):
        best = None
        for M, Mi, t in trees:
            hit = t.ray_cast(Mi @ Vector((x, y, z_from)), (Mi.to_3x3() @ Vector((0, 0, -1))).normalized(), 50.0)
            if hit[0] is not None and (M.to_3x3() @ hit[1]).normalized().z > 0.5:
                z = (M @ hit[0]).z
                if best is None or z > best:
                    best = z
        return best
    return at


def sea_sampler(sc, live=False):
    """The sea surface over a point (the highest hit on a SEA mesh from above), world metres; None where there is no
    sea. The ground sampler ignores the sea (a fighter stands on the sand under it), so this is how a body that was
    staged into the water is found: 27 Nov, the shore film put Musashi in the shallows and every foot check passed.
    The near sea is an Ocean modifier that GENERATES its mesh (the base mesh has no faces), so the evaluated mesh is
    what counts; live=True rebuilds it on each new frame (the waves move: a low camera needs the surface of ITS frame)."""
    from mathutils.bvhtree import BVHTree
    obs = [o for o in sc.objects if o.type == 'MESH' and o.name.startswith('SEA') and o.visible_get()]
    if not obs:
        return None
    cache = {}

    def trees_now():
        f = sc.frame_current if live else None
        if cache.get('f', 'none') != f:
            dg = bpy.context.evaluated_depsgraph_get()
            cache['f'] = f
            cache['t'] = [(o.matrix_world.copy(), o.matrix_world.inverted(), BVHTree.FromObject(o, dg)) for o in obs]
        return cache['t']

    def at(x, y):
        best = None
        for M, Mi, t in trees_now():
            hit = t.ray_cast(Mi @ Vector((x, y, 60.0)), (Mi.to_3x3() @ Vector((0, 0, -1))).normalized(), 200.0)
            if hit[0] is not None:
                z = (M @ hit[0]).z
                if best is None or z > best:
                    best = z
        return best
    return at


def solve(TL, actors, fps, checks=True, body_shrink=0.035):
    """Run every frame of the timeline in order through the passes; return the bake dict."""
    import body_capsules as BC
    import sword_draw as SD
    sc = bpy.context.scene
    ground_at = ground_sampler(sc, {o for a in actors for o in a.objects})
    sea_at = sea_sampler(sc)
    last_g = {a.aid: 0.0 for a in actors}             # each body casts from 1 m above ITS last ground (a hillside)
    for a in actors:
        if a.draw is not None:                        # a thrown scabbard lands on the set (sand or sea)
            a.draw.surface = (ground_at, sea_at)
            a.draw.fps = float(fps)
    frames = TL['frames']
    out = {'fps': fps, 'n': len(frames), 'actors': {}, 'checks': {}}
    body = {a.aid: BC.BodyCapsules(a.rig, shrink=body_shrink) for a in actors}
    garment = {a.aid: BC.BodyCapsules(a.rig) for a in actors}
    sleeves = {a.aid: [o for o in a.objects if o.get('pc_recipe') == 'tamoto_wide'] for a in actors}
    aprons = {a.aid: [o for o in a.objects if o.get('pc_recipe') == 'hakama_apron'] for a in actors}
    rec = {a.aid: {'J': [], 'sword': [], 'saya': [], 'grip': [], 'segs': [], 'ground': [], 'base': []} for a in actors}
    chk = {a.aid: {'blade/body': [], 'blade/garment': [], 'arm.R/body': [], 'arm.L/body': [],
                   'sleeve-paper.R/body': [], 'sleeve-paper.L/body': [], 'hakama-apron/legs': [], 'grip_rel': [], 'phase': []}
           for a in actors}
    for i, fr in enumerate(frames):
        f = i + 1
        sc.frame_set(f)
        for a in actors:
            act = fr['actors'].get(a.aid)
            if not act or act.get('hidden') or not isinstance(act.get('pose'), dict):
                rec[a.aid]['J'].append(None)
                rec[a.aid]['ground'].append(None)
                rec[a.aid]['base'].append(None)
                continue
            # the body follows the terrain under it (a film is blocked on flat ground at z 0): the pose's height is
            # raised or lowered to the set's ground under the character's centre, cast from 1 m up so an eave or a
            # counter above is never taken for the floor; the feet settle on their own ground below
            base = 0.0
            if ground_at is not None:
                _p = act['pose']
                _g = ground_at(float(_p.get('x', 0.0)), -float(_p.get('z', 0.0)), last_g[a.aid] + 1.0)
                if _g is not None:
                    last_g[a.aid] = _g
                if _g is not None and abs(_g) > 0.003:
                    base = _g
                    act = dict(act, pose=dict(_p, y=float(_p.get('y', 0.0)) + _g))
                    chk[a.aid].setdefault('terrain', []).append((f, round(_g, 3)))
                if sea_at is not None:
                    _s = sea_at(float(_p.get('x', 0.0)), -float(_p.get('z', 0.0)))
                    if _s is not None and _s > base + 0.05:     # standing in the water (the ground is under the sea)
                        chk[a.aid].setdefault('wet', []).append((f, round(_s - base, 3)))
            if a.draw:
                a.draw.rate = float(fr.get('rate', 1.0) or 1.0)
                phase = a.draw.step(f, dict(act['pose']))
            else:
                a.rig.pose(act['pose'])
                phase = None
                if a.caps is not None:
                    # every actor's arms keep out of the body: each hand stays exactly where the animation put
                    # it (on the sword), only the shoulder/elbow/wrist angles change, rate-limited per frame
                    pose = dict(act['pose'])
                    bpy.context.view_layer.update()
                    a.caps.update()
                    for side in ('r', 'l'):
                        hold = a.rig.J[side + 'H'].matrix_world @ SD.hand_holder()
                        fixed, b_, _a = SD.arm_keep_out(a.rig, pose, a.caps, side, hold=hold)
                        prev = a.corr.get(side, {})
                        corr = {}
                        for k in SD.arm_keys(side):
                            want, was = fixed[k] - pose[k], prev.get(k, 0.0)
                            corr[k] = was + max(-0.25, min(0.25, want - was))
                        a.corr[side] = corr
                        for k, v in corr.items():
                            pose[k] += v
                    a.rig.pose(pose)
            # feet on the ground: the pose's leg solver works in the character's own frame (see Rig.ground_feet)
            lifted = a.rig.ground_feet(ground=ground_at or 0.0, base=base)
            rec[a.aid]['ground'].append(dict(getattr(a.rig, 'foot_ground', {})))   # per foot: the ground it stands on
            rec[a.aid]['base'].append(round(base, 4))       # the terrain under the body: its weapon and the camera follow
            if lifted:
                chk[a.aid].setdefault('feet_lifted', []).append((f, lifted))
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
                _check_frame(a, f, phase, body[a.aid], garment[a.aid], sleeves[a.aid], chk[a.aid], aprons[a.aid])
    out['props'] = []                                  # things that leave a body: a thrown scabbard's splash / landing
    for a in actors:
        out['actors'][a.aid] = rec[a.aid]
        out['checks'][a.aid] = chk[a.aid]
        if a.draw is not None and getattr(a.draw, 'events', None):
            for e in a.draw.events:
                out['props'].append(dict(e, actor=a.aid, what='saya', t=round((e['frame'] - 1) / fps, 4)))
                print('[bake] %s scabbard %s at frame %d, %s' % (a.aid, e['kind'], e['frame'], e['pos']))
        if a.springs is not None:
            chk[a.aid]['cloth_lag'] = {j: [r[0] for r in rows] for j, rows in a.springs.log.items()}
        if chk[a.aid].get('terrain'):
            _t = [g for _f, g in chk[a.aid]['terrain']]
            print('[bake] %s body on the terrain on %d frames: ground %.3f..%.3f m' % (a.aid, len(_t), min(_t), max(_t)))
        if chk[a.aid].get('wet'):
            _w = chk[a.aid]['wet']
            print('[bake] WARNING %s stands IN THE SEA on %d frames (f%d-f%d, water up to %.2f m deep): restage the film '
                  '(film.stage mark / offset / turn) unless it is a wading shot' % (
                      a.aid, len(_w), _w[0][0], _w[-1][0], max(d for _f, d in _w)))
        if chk[a.aid].get('feet_lifted'):
            print('[bake] %s feet put back on the ground on %d frames (cm): %s' % (
                a.aid, len(chk[a.aid]['feet_lifted']), chk[a.aid]['feet_lifted'][:8]))
        if a.draw is not None:
            chk[a.aid]['blade_turned_out'] = {str(k): v for k, v in sorted(a.draw.pushed.items())}
            print('[bake] %s blade turned out of the body on frames %s' % (a.aid, chk[a.aid]['blade_turned_out']))
    return out


def _check_frame(a, f, phase, body, garment, sleeves, chk, aprons=()):
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
    if aprons:
        # the hakama's front/back apron panels (moved by the hakama spring) against the LEGS of the person
        rig.sync_bones()
        dg = bpy.context.evaluated_depsgraph_get()
        legs = ('thigh.R', 'thigh.L', 'shin.R', 'shin.L')
        skip = tuple(n for n, *_ in body.segs if n not in legs)
        worst = (0.0, '')
        for ob in aprons:
            me = ob.evaluated_get(dg).to_mesh()
            mw = ob.matrix_world
            for v in me.vertices:
                dd, who = body.depth(mw @ v.co, skip=skip)
                if dd > worst[0]:
                    worst = (dd, who)
            ob.evaluated_get(dg).to_mesh_clear()
        if worst[0] > 0:
            chk['hakama-apron/legs'].append((f, round(worst[0] * 100, 1), worst[1]))
    # the LEFT hand on the scabbard while it holds it (final pose), and both elbows for pops
    J = rig.J
    chk.setdefault('elbows', []).append((f, [*J['rE'].matrix_world.translation], [*J['lE'].matrix_world.translation]))
    if d is not None and d.hands and not d.hands['l'][1].hide_render:
        import sword_draw as SD
        want = (d.saya.matrix_world @ Vector((SD.LEFT_AT, 0, 0)))
        got = (J['lH'].matrix_world @ d.H).translation
        chk.setdefault('left_on_saya', []).append((f, round((want - got).length * 100, 2)))
    if d is not None and phase in ('grab', 'drawing', 'drawn'):
        rel = d.sword.matrix_world.inverted() @ (rig.J['rH'].matrix_world @ d.H)
        loc, rot, _ = rel.decompose()
        chk['grip_rel'].append((f, phase, [*loc], [*rot]))


def report(bake, F):
    lines = []
    for aid, c in bake['checks'].items():
        for key in ('blade/body', 'blade/garment', 'arm.R/body', 'arm.L/body', 'sleeve-paper.R/body', 'sleeve-paper.L/body',
                    'hakama-apron/legs'):
            rows = c.get(key, [])
            if rows:
                fr = sorted({r[0] for r in rows})
                mx = max(rows, key=lambda r: r[1])
                lines.append('[check] %s %-20s on %2d of %d frames, deepest %.1f cm (frame %d, %s)' % (
                    aid, key, len(fr), F, mx[1], mx[0], mx[2]))
            else:
                lines.append('[check] %s %-20s never' % (aid, key))
        ls = c.get('left_on_saya', [])
        if ls:
            mx = max(ls, key=lambda r: r[1])
            lines.append('[check] %s left hand on the scabbard while holding: %d frames, off by at most %.1f cm (frame %d)'
                         % (aid, len(ls), mx[1], mx[0]))
        el = c.get('elbows', [])
        for k, side in ((1, 'R'), (2, 'L')):
            if len(el) > 2:
                acc = [((Vector(el[i + 1][k]) - Vector(el[i][k])) - (Vector(el[i][k]) - Vector(el[i - 1][k]))).length * 100
                       for i in range(1, len(el) - 1)]
                top = sorted(((v, el[i + 1][0]) for i, v in enumerate(acc)), reverse=True)[:3]
                lines.append('[check] %s elbow.%s jolt (cm/frame^2): median %.1f, top %s' % (
                    aid, side, sorted(acc)[len(acc) // 2], ', '.join('f%d %.1f' % (fr_, v) for v, fr_ in top)))
        for j, lag in sorted(c.get('cloth_lag', {}).items()):
            if lag:
                lines.append('[check] %s cloth %-8s swings from its rest aim: median %.0f, max %.0f deg' % (
                    aid, j, sorted(lag)[len(lag) // 2], max(lag)))
        held = [g for g in c.get('grip_rel', []) if g[1] in ('drawing', 'drawn')]
        if held:
            b_l, b_r = Vector(held[0][2]), Quaternion(held[0][3])
            dl = max(((Vector(g[2]) - b_l).length * 100, g[0]) for g in held)
            dr = max((math.degrees(Quaternion(g[3]).rotation_difference(b_r).angle), g[0]) for g in held)
            # one held frame has no frame-to-frame change (max() of nothing used to crash the report)
            st = max(((math.degrees(Quaternion(held[k][3]).rotation_difference(Quaternion(held[k - 1][3])).angle), held[k][0])
                      for k in range(1, len(held))), default=(0.0, held[0][0]))
            sl = max((((Vector(held[k][2]) - Vector(held[k - 1][2])).length * 100, held[k][0]) for k in range(1, len(held))),
                     default=(0.0, held[0][0]))
            lines.append('[check] %s grip vs hilt (slide to end): drift %.1f cm (f%d), %.1f deg (f%d); one-frame %.1f cm (f%d), %.1f deg (f%d)'
                         % (aid, dl[0], dl[1], dr[0], dr[1], sl[0], sl[1], st[0], st[1]))
    return lines


# --------------------------------------------------------------------------- save / load / apply
def save(bake, path, stamp_):
    """Write atomically: a render worker reading the bake must never see a half-written file."""
    bake = dict(bake, stamp=stamp_)
    tmp = '%s.%d.tmp' % (path, os.getpid())
    with open(tmp, 'w') as fh:
        json.dump(bake, fh, separators=(',', ':'))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


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

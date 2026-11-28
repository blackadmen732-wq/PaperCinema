"""NATIVE perception: read what a source environment already knows, with no pixels involved.

Paper Cinema writes output/<film>.timeline.json (tools/timeline.mjs, docs/TIMELINE-FORMAT.md): every bone of every
actor in world space, the weapon, the camera, the cuts and the verified events. VYRN reads that file and fills the
same store the video path fills, with confidence 1, so an agent asks the same questions of both and the native
answers can grade the video answers.

Other environments plug in by writing the same timeline shape (that is the whole adapter contract):
  * Blender: a bpy script that samples pose bones (matrix_world) and the scene camera per frame and writes
    frames[].actors[id].bones + frames[].camera, converting Z-up to +y up with the inverse of timeline.coords.toBlender.
  * Unreal: a Sequencer/Python export of skeletal-mesh component transforms and the CineCamera, centimetres to metres,
    left-handed to right-handed (docs/TIMELINE-FORMAT.md §3 says where that conversion is written down).
Neither adapter is built yet; the reader below only needs `film`, `frames`, `bones.order`, `cuts` and `events`.
"""
import json, math
from vyrn.geom import project, qrot

BODY_RADIUS = 0.12     # m: joints are centre lines, a body has volume; pad the screen box by this much
FOOT_BONES = ('foot.L', 'foot.R')


def ingest_timeline(path, store, media_id, sha):
    tl = json.load(open(path))
    film = tl['film']
    fps, W, H = film['fps'], film.get('width', 720), film.get('height', 1280)
    aspect = W / H
    order = tl['bones']['order']
    frames = tl['frames']
    actors = [a['id'] for a in tl.get('actors', [])] or list(frames[0]['actors'])
    blade = {a['id']: (a.get('weapon') or {}).get('bladeLen', 0.9) for a in tl.get('actors', [])}
    store.put_media(id=media_id, kind='native', source=path, sha256=sha, fps=fps, duration=film.get('duration'),
                    frames=len(frames), width=W, height=H,
                    processors={'native': 'paper-cinema-timeline/1', 'vyrn': 1},
                    stats={'film': film.get('name'), 'actors': actors, 'events': len(tl.get('events', []))})
    store.put_entity('camera', 'camera', source='native', method='timeline', first_f=0, last_f=len(frames) - 1)
    for a in actors:
        store.put_entity(a, 'actor', source='native', method='timeline', first_f=0, last_f=len(frames) - 1,
                         info={'joints': order})
        store.put_entity(a + '.weapon', 'weapon', parent=a, source='native', method='timeline',
                         first_f=0, last_f=len(frames) - 1, info={'bladeLen': blade.get(a, 0.9)})

    samples, joints = [], []
    prev = {}
    cam_prev = None
    cam_speed = []
    foc = None
    for F in frames:
        f, t = F['f'], F['t']
        cam = F['camera']
        cp, cq, fov = cam['pos'], cam['rot'], cam['fov']
        foc = (H / 2) / math.tan(math.radians(fov) / 2)
        cs = 0.0 if cam_prev is None else math.dist(cp, cam_prev) * fps
        cam_speed.append(cs); cam_prev = cp
        samples.append(('camera', f, t, None, None, None, None, cp[0], cp[1], cp[2], None, None, cs, 1, 1.0))
        for a in actors:
            A = F['actors'].get(a)
            if not A:
                continue
            xs, ys, vis = [], [], 0
            for j, b in enumerate(A['bones']):
                p = project(cp, cq, fov, aspect, b[:3])
                if p:
                    pad = BODY_RADIUS * foc / p[2]
                    xs += [p[0] - pad / W, p[0] + pad / W]; ys += [p[1] - pad / H, p[1] + pad / H]
                    vis += 0 <= p[0] <= 1 and 0 <= p[1] <= 1
                joints.append((a, order[j], f, p[0] if p else None, p[1] if p else None, b[0], b[1], b[2], 1.0))
            hips = A['bones'][order.index('hips')][:3] if 'hips' in order else A['bones'][0][:3]
            if xs:
                x0, x1, y0, y1 = max(0, min(xs)), min(1, max(xs)), max(0, min(ys)), min(1, max(ys))
                box = (x0, y0, x1 - x0, y1 - y0)
            else:
                box = (None,) * 4
            pv = prev.get(a)
            vx = vy = None; sp = 0.0
            if pv and box[0] is not None and pv[1][0] is not None:
                vx = ((box[0] + box[2] / 2) - (pv[1][0] + pv[1][2] / 2)) * fps
                vy = ((box[1] + box[3] / 2) - (pv[1][1] + pv[1][3] / 2)) * fps
            if pv:
                sp = math.dist(hips, pv[0]) * fps
            prev[a] = (hips, box)
            visible = int(vis > len(A['bones']) // 2) if not A.get('hidden') else 0
            samples.append((a, f, t, *box, *hips, vx, vy, sp, visible, 1.0))
            w = A.get('weapon')
            if w:
                tip = tuple(w[i] + v for i, v in enumerate(qrot(w[3:7], (blade.get(a, 0.9), 0, 0))))
                p0, p1 = project(cp, cq, fov, aspect, w[:3]), project(cp, cq, fov, aspect, tip)
                if p0 and p1:
                    x0, x1 = sorted((p0[0], p1[0])); y0, y1 = sorted((p0[1], p1[1]))
                    samples.append((a + '.weapon', f, t, x0, y0, x1 - x0, y1 - y0, tip[0], tip[1], tip[2],
                                    None, None, None, 1, 1.0))
    store.put_samples(samples)
    store.put_joints(joints)
    store.put_signal('camera.speed', fps, cam_speed, 'm/s', 'timeline')

    # ---- events: copied with their stable ids (one verified event drives everything) ----
    for e in tl.get('events', []):
        ents = [x for x in (e.get('actor'), e.get('target')) if x]
        if e['type'] == 'blade-contact':
            ents = actors[:]
        data = {k: v for k, v in e.items() if k not in ('id', 'type', 't', 'f', 't1', 'until')}
        t1 = e.get('t1') or e.get('until') or (e['t'] + e['duration'] if 'duration' in e else None)
        store.put_event(e['id'], e['type'], e['t'], t1, e.get('f'), ents, data, 1.0, 'timeline', 'engine')
    for i, cf in enumerate(tl.get('cuts', [])):
        if cf > 0:
            store.put_event(f'cut.{i:02d}', 'cut', cf / fps, None, cf, [], {}, 1.0, 'timeline', 'engine')

    # ---- derived: planted-foot intervals (tools/footslide.mjs definition: root on the ground, foot low) ----
    n = 0
    ri = order.index('root') if 'root' in order else 0
    for a in actors:
        for fb in FOOT_BONES:
            if fb not in order:
                continue
            fi = order.index(fb)
            start = None
            for F in frames + [None]:
                A = F and F['actors'].get(a)
                planted = bool(A) and A['bones'][ri][1] <= 0.03 and A['bones'][fi][1] <= 0.12
                if planted and start is None:
                    start = F
                elif not planted and start is not None:
                    end = prev_F
                    store.put_event(f'plant.{n:03d}', 'contact.foot-ground', start['t'], end['t'], start['f'], [a],
                                    {'foot': fb}, 1.0, 'timeline:footslide-rule', 'vyrn.native')
                    n += 1; start = None
                prev_F = F

    # ---- relations: actor-to-actor distance (world), as a signal and as 'near' intervals ----
    hi = order.index('hips') if 'hips' in order else 0
    for i, a in enumerate(actors):
        for b in actors[i + 1:]:
            d = [math.dist(F['actors'][a]['bones'][hi][:3], F['actors'][b]['bones'][hi][:3]) for F in frames]
            store.put_signal(f'dist.{a}~{b}', fps, d, 'm', 'timeline')
            _intervals(store, a, b, 'near', [x < 1.8 for x in d], d, frames, fps, 'timeline')
    store.commit()
    return {'frames': len(frames), 'actors': actors, 'events': len(tl.get('events', []))}


def _intervals(store, a, b, kind, mask, vals, frames, fps, method, conf=1.0):
    s = None
    for i, m in enumerate(mask + [False]):
        if m and s is None:
            s = i
        elif not m and s is not None:
            store.put_relation(a, b, kind, s / fps, (i - 1) / fps, s, i - 1, min(vals[s:i]), conf, method)
            s = None

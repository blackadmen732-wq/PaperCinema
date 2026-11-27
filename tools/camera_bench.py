#!/usr/bin/env python3
"""CAMERA BENCH: how good is a camera operator? (Mark, 27 Nov: "a ball floating around and flying around ... boxes
... a boom sound when you do the dash ... multiple different views ... to see how good your camera system is")

A folded-paper ball floats, then DASHES between paper boxes (four dashes, each with a boom), passing behind tall
boxes on purpose. Four camera operators film the SAME flight:
  locked   one fixed wide camera (the baseline: never moves)
  naive    a fixed position that aims EXACTLY at the ball every frame (rigid look-at: no lag, no lead)
  chase    follows behind the ball with a short spring lag, aims at it
  operator the "skilled" one: critically damped follow, LEAD ROOM in the direction of travel, ANTICIPATES each dash
           (it knows the cue sheet: widens and leads a few frames early), and climbs/slides to keep the ball out
           from behind boxes (it checks its own line of sight)
Every camera is scored on the same per-frame measurements (pure maths, no renderer needed):
  in frame (ball centre inside the 5% safe margin) · visible (of 9 rays from the camera to the ball, how many are
  not blocked by a box) · size (ball height on screen within a readable band) · smooth (camera turn acceleration)
  · lead room (during motion, the ball sits on the side it comes FROM).

  python3 tools/camera_bench.py solve      -> output/camera-bench/bench.json + metrics.csv + scores
  (render: blender -b -P blender/bench/camera_bench_render.py -- --cam <name>)
  python3 tools/camera_bench.py compose    -> output/camera-bench/camera-bench.mp4 (2x2 grid, booms mixed)
"""
import csv
import json
import math
import os
import subprocess
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'output', 'camera-bench')
FPS, DUR = 24, 8.0
N = int(FPS * DUR)
BALL_R = 0.28
W, H = 540, 960                               # each view; the grid is 1080 x 1920
SENSOR_H = 36.0                               # sensor fit VERTICAL, so the lens maps to the frame HEIGHT

# ------------------------------------------------------------------ the arena: paper boxes (centre, size) in metres
BOXES = [((-3.0, 1.0, 1.25), (1.4, 1.4, 2.5)), ((0.5, 2.5, 0.6), (1.2, 1.2, 1.2)), ((3.2, 0.5, 1.6), (1.0, 1.6, 3.2)),
         ((-1.2, -2.0, 0.45), (0.9, 0.9, 0.9)), ((2.0, -2.6, 0.9), (1.8, 0.8, 1.8)), ((-4.2, -2.8, 0.7), (1.0, 1.0, 1.4)),
         ((0.0, 0.0, 0.35), (0.7, 0.7, 0.7)), ((4.6, 3.4, 1.0), (1.2, 1.2, 2.0)), ((-2.2, 3.8, 1.9), (1.0, 1.0, 3.8)),
         ((1.6, 5.0, 0.5), (2.2, 1.0, 1.0)), ((-5.0, 1.6, 0.5), (1.0, 2.2, 1.0)), ((5.4, -1.0, 0.6), (0.8, 0.8, 1.2))]

# ------------------------------------------------------------------ the flight: floats and dashes
ANCHORS = [(-4.2, -0.6, 1.4), (1.6, -1.3, 1.2), (0.9, 3.9, 3.0), (-3.4, 2.6, 0.9), (4.0, 1.9, 2.2)]
DASHES = [(1.5, 0.52), (3.2, 0.48), (4.6, 0.50), (6.2, 0.46)]   # (start s, duration s) between the anchors
ANTIC = 0.10                                                  # a little pull back before each dash


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def ball_at(t):
    """Ball centre at film time t (s)."""
    A = [np.array(a, float) for a in ANCHORS]
    seg = 0
    for i, (ts, d) in enumerate(DASHES):
        if t >= ts:
            seg = i + 1
    # where it hovers (float): a slow lissajous around the current anchor, drifting toward the next one
    def hover(k, t):
        a = A[k]
        return a + np.array([0.35 * math.sin(1.3 * t + k), 0.30 * math.sin(0.9 * t + 2 * k), 0.22 * math.sin(2.1 * t + k)])
    for i, (ts, d) in enumerate(DASHES):
        if ts - ANTIC <= t < ts + d:
            p0, p1 = hover(i, ts - ANTIC), hover(i + 1, ts + d)
            dirn = (p1 - p0) / (np.linalg.norm(p1 - p0) + 1e-9)
            if t < ts:                                        # anticipation: ease back 0.35 m
                u = (t - (ts - ANTIC)) / ANTIC
                return p0 - dirn * 0.35 * math.sin(u * math.pi / 2)
            u = (t - ts) / d
            back = p0 - dirn * 0.35
            p = back + (p1 - back) * smooth(u)
            return p + np.array([0, 0, 0.6 * math.sin(math.pi * u)]) * (1 if i % 2 else -0.4)   # a slight arc
    return hover(seg, t)


def path():
    return np.array([ball_at(i / FPS) for i in range(N)])


# ------------------------------------------------------------------ geometry helpers
def ray_box(o, d, c, s):
    """Distance along a unit ray to an axis-aligned box, or None."""
    lo, hi = np.array(c) - np.array(s) / 2, np.array(c) + np.array(s) / 2
    with np.errstate(divide='ignore', invalid='ignore'):
        t1, t2 = (lo - o) / d, (hi - o) / d
    tmin, tmax = np.nanmax(np.minimum(t1, t2)), np.nanmin(np.maximum(t1, t2))
    if tmax >= max(tmin, 0.0):
        return max(tmin, 0.0)
    return None


def blocked(o, p):
    d = p - o
    L = np.linalg.norm(d)
    d = d / L
    for c, s in BOXES:
        t = ray_box(o, d, c, s)
        if t is not None and t < L - 1e-3:
            return True
    return False


def look_basis(pos, target):
    f = target - pos
    f = f / np.linalg.norm(f)
    r = np.cross(f, np.array([0, 0, 1.0]))
    r = r / (np.linalg.norm(r) + 1e-12)
    u = np.cross(r, f)
    return r, u, f


def project(pos, target, lens, p):
    """Screen (x, y in 0..1, y up) and depth of world point p for a camera at pos looking at target."""
    r, u, f = look_basis(pos, target)
    v = p - pos
    z = v @ f
    if z <= 1e-3:
        return None
    fy = lens / SENSOR_H                          # half-height normalised: y_ndc = fy * (v.u / z) * 2 ... see below
    y = 0.5 + (v @ u) / z * lens / SENSOR_H
    x = 0.5 + (v @ r) / z * lens / SENSOR_H * (H / W)
    return x, y, z


def quat_from_basis(r, u, f):
    """Blender camera rotation: columns X = right, Y = up, Z = -forward."""
    m = np.column_stack([r, u, -f])
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    i = int(np.argmax([m[0, 0], m[1, 1], m[2, 2]]))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1.0 + m[i, i] - m[j, j] - m[k, k]) * 2
    q = [0.0] * 4
    q[0] = (m[k, j] - m[j, k]) / s
    q[1 + i] = 0.25 * s
    q[1 + j] = (m[j, i] + m[i, j]) / s
    q[1 + k] = (m[k, i] + m[i, k]) / s
    return q


def spring(x, target, v, half_life, dt):
    """Critically damped spring step (no overshoot)."""
    w = 4 * math.log(2) / max(1e-4, half_life) / 2
    e = math.exp(-w * dt)
    j0 = x - target
    j1 = v + j0 * w
    x = target + (j0 + j1 * dt) * e
    v = (v - j1 * w * dt) * e
    return x, v


# ------------------------------------------------------------------ the four operators
def operators(P):
    dt = 1 / FPS
    V = np.gradient(P, axis=0) * FPS
    cams = {}
    # locked: one wide camera that sees the whole arena
    lp, lt = np.array([0.0, -15.5, 7.0]), np.array([0.0, 1.0, 1.4])
    cams['locked'] = [(lp, lt, 22.0) for _ in range(N)]
    # naive: fixed position, aims exactly at the ball every frame
    npos = np.array([8.0, -9.5, 4.5])
    cams['naive'] = [(npos, P[i].copy(), 32.0) for i in range(N)]
    # chase: 3.2 m behind the ball along its (smoothed) travel, 1.2 m up, short lag
    out, x, v, d_s, dv = [], None, np.zeros(3), np.array([0, 1.0, 0]), np.zeros(3)
    for i in range(N):
        sp = np.linalg.norm(V[i])
        dirn = V[i] / sp if sp > 0.5 else d_s
        d_s, dv = spring(d_s, dirn, dv, 0.25, dt)
        d_s = d_s / (np.linalg.norm(d_s) + 1e-9)
        want = P[i] - d_s * 3.2 + np.array([0, 0, 1.2])
        x = want.copy() if x is None else x
        x, v = spring(x, want, v, 0.12, dt)
        out.append((x.copy(), P[i].copy(), 30.0))
    cams['chase'] = out
    # operator: picks its viewpoint like a person would. Every frame it scores 12 candidate positions around the ball
    # (4 directions x 3 heights, 7 m away) by line of sight NOW and 0.3 s AHEAD (it knows the flight is coming),
    # keeps its current one unless another is clearly better (no flip-flopping), and glides there on a damped spring.
    # It aims AHEAD of the ball by its velocity (lead room), widens before and during each dash (cue sheet).
    out = []
    x, v = None, np.zeros(3)
    aim, av = P[0].copy(), np.zeros(3)
    lens, lv = 30.0, 0.0
    cand_i = None
    cands = [(az, h) for az in (-60, -20, 20, 60) for h in (2.2, 3.6, 5.2)]

    def cand_pos(c, p):
        az, h = c
        a_ = math.radians(az)
        return p + np.array([7.0 * math.sin(a_), -7.0 * math.cos(a_), h])

    def vis(o, p):
        r_, u_, f_ = look_basis(o, p)
        pts = [p] + [p + (r_ * math.cos(a) + u_ * math.sin(a)) * BALL_R * 0.85 for a in [k * math.pi / 4 for k in range(8)]]
        return sum(0 if blocked(o, q) else 1 for q in pts)

    for i in range(N):
        t = i / FPS
        k3 = min(N - 1, i + int(0.3 * FPS))
        centre = P[i] * 0.6 + P[k3] * 0.4                       # frame where the ball IS and where it is GOING
        scored = []
        for ci, c in enumerate(cands):
            o = cand_pos(c, centre)
            sc_ = vis(o, P[i]) + vis(o, P[k3]) - 0.15 * abs(c[0]) / 60 - 0.1 * (c[1] > 4)
            scored.append((sc_, ci))
        best = max(scored)
        if cand_i is None or best[0] > dict((ci, s_) for s_, ci in scored)[cand_i] + 1.5:
            cand_i = best[1]
        want = cand_pos(cands[cand_i], centre)
        x = want.copy() if x is None else x
        x, v = spring(x, want, v, 0.28, dt)
        nxt = [ts for ts, d in DASHES if 0 <= ts - t <= 0.30]
        inn = [ts for ts, d in DASHES if ts <= t <= ts + d + 0.25]
        lead_pt = P[i] + V[i] * (0.16 if inn else 0.10)          # aim ahead of the ball by its speed
        aim, av = spring(aim, lead_pt, av, 0.09 if inn else 0.12, dt)
        want_lens = 22.0 if (nxt or inn) else 28.0
        lens, lv = spring(np.array([lens]), np.array([want_lens]), np.array([lv]), 0.18, dt)
        lens, lv = float(lens[0]), float(lv[0])
        out.append((x.copy(), aim.copy(), lens))
    cams['operator'] = out
    return cams


def kuroko_cams(P):
    """The production camera module (engine/kuroko.js) on the same flight, run in Node (tools/camera_bench_kuroko.mjs)."""
    src = os.path.join(OUT, 'ball-for-kuroko.json')
    dst = os.path.join(OUT, 'kuroko-cams.json')
    json.dump({'fps': FPS, 'ball': P.tolist(), 'dashes': [{'start_s': ts, 'dur_s': d} for ts, d in DASHES]}, open(src, 'w'))
    subprocess.run(['node', os.path.join(REPO, 'tools', 'camera_bench_kuroko.mjs'), src, dst], check=True, cwd=REPO)
    return {k: [(np.array(c['pos']), np.array(c['target']), float(c['lens'])) for c in seq]
            for k, seq in json.load(open(dst)).items()}


# ------------------------------------------------------------------ measure
def measure(P, cams):
    V = np.gradient(P, axis=0) * FPS
    rows, scores = [], {}
    for name, seq in cams.items():
        fwd_prev, turn_prev = None, None
        acc_list, inf, vis_ok, size_ok, lead_ok, lead_n = [], 0, 0, 0, 0, 0
        for i, (pos, tgt, lens) in enumerate(seq):
            pr = project(pos, tgt, lens, P[i])
            r, u, f = look_basis(pos, tgt)
            # ball size on screen (height fraction)
            dist = np.linalg.norm(P[i] - pos)
            size = 2 * BALL_R / dist * lens / SENSOR_H
            # 9 rays: centre + 8 points on the silhouette
            pts = [P[i]] + [P[i] + (r * math.cos(a) + u * math.sin(a)) * BALL_R * 0.85 for a in [k * math.pi / 4 for k in range(8)]]
            seen = sum(0 if blocked(pos, q) else 1 for q in pts)
            # turn acceleration (deg / frame^2) of the camera's forward direction
            turn = 0.0
            if fwd_prev is not None:
                turn = math.degrees(math.acos(max(-1, min(1, float(f @ fwd_prev)))))
            acc = abs(turn - turn_prev) if turn_prev is not None else 0.0
            fwd_prev, turn_prev = f, turn
            acc_list.append(acc)
            x, y = (pr[0], pr[1]) if pr else (-1, -1)
            inside = pr is not None and 0.05 <= x <= 0.95 and 0.05 <= y <= 0.95
            margin = min(x, 1 - x, y, 1 - y) if pr else -1
            # lead room: when the ball moves fast, its screen position should sit BEHIND centre along its screen motion
            lead = ''
            if np.linalg.norm(V[i]) > 2.0 and pr is not None:
                pn = project(pos, tgt, lens, P[i] + V[i] * 0.1)
                if pn:
                    dx, dy = pn[0] - x, pn[1] - y
                    off = (x - 0.5) * dx + (y - 0.5) * dy                   # < 0: ball sits on the side it comes from
                    lead = round(off / (math.hypot(dx, dy) + 1e-9), 4)
                    lead_n += 1
                    lead_ok += off <= 0.0
            inf += inside
            vis_ok += seen >= 5
            size_ok += 0.025 <= size <= 0.12
            rows.append({'frame': i + 1, 'camera': name, 'screen_x': round(x, 4), 'screen_y': round(y, 4),
                         'in_frame': int(inside), 'edge_margin': round(margin, 4), 'rays_visible_of_9': seen,
                         'ball_screen_height': round(size, 4), 'turn_deg_per_frame': round(turn, 3),
                         'turn_accel_deg': round(acc, 3), 'lead_offset': lead, 'lens_mm': round(lens, 1)})
        n = len(seq)
        smooth_pen = float(np.percentile(acc_list, 95))
        s = {'in_frame_pct': 100 * inf / n, 'visible_pct': 100 * vis_ok / n, 'readable_size_pct': 100 * size_ok / n,
             'turn_accel_p95_deg': smooth_pen, 'lead_room_pct': 100 * lead_ok / max(1, lead_n)}
        # weights: what separates a good operator from a bad one. Every camera kept the ball IN frame, so in-frame
        # alone told them apart by nothing; losing it behind a box is the worst failure, then lead room and jerk.
        s['score'] = round(0.15 * s['in_frame_pct'] + 0.30 * s['visible_pct'] + 0.15 * s['readable_size_pct'] +
                           0.20 * max(0.0, 100 - 40 * smooth_pen) + 0.20 * s['lead_room_pct'], 1)
        scores[name] = {k: round(v, 2) for k, v in s.items()}
    return rows, scores


def solve():
    os.makedirs(OUT, exist_ok=True)
    P = path()
    cams = operators(P)
    cams.update(kuroko_cams(P))
    rows, scores = measure(P, cams)
    bench = {'fps': FPS, 'n': N, 'ball_r': BALL_R, 'boxes': BOXES, 'ball': P.tolist(),
             'dashes': [{'start_s': ts, 'dur_s': d, 'start_frame': ts * FPS + 1} for ts, d in DASHES],
             'cams': {k: [{'pos': list(map(float, p)), 'rot': quat_from_basis(*look_basis(p, t)), 'lens': float(l)}
                          for p, t, l in seq] for k, seq in cams.items()},
             'scores': scores, 'view': [W, H], 'sensor_h': SENSOR_H}
    json.dump(bench, open(os.path.join(OUT, 'bench.json'), 'w'))
    with open(os.path.join(OUT, 'metrics.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    speeds = np.linalg.norm(np.gradient(P, axis=0) * FPS, axis=1)
    inside = [i + 1 for i in range(N) if any(all(abs(P[i][j] - c[j]) < s_[j] / 2 + BALL_R for j in range(3)) for c, s_ in BOXES)]
    print('[bench] ball inside a box on frames:', inside or 'never')
    print('[bench] %d frames; ball top speed %.1f m/s; dashes start at frames %s' % (
        N, speeds.max(), [round(ts * FPS + 1, 1) for ts, d in DASHES]))
    print('[bench] %-9s %6s %8s %8s %8s %10s %8s' % ('camera', 'score', 'inframe', 'visible', 'size', 'turnacc95', 'lead'))
    for k, s in sorted(scores.items(), key=lambda kv: -kv[1]['score']):
        print('[bench] %-9s %6.1f %7.1f%% %7.1f%% %7.1f%% %9.2f° %7.1f%%' % (
            k, s['score'], s['in_frame_pct'], s['visible_pct'], s['readable_size_pct'], s['turn_accel_p95_deg'], s['lead_room_pct']))


# ------------------------------------------------------------------ compose the grid + the booms
def compose():
    from PIL import Image, ImageDraw, ImageFont
    B = json.load(open(os.path.join(OUT, 'bench.json')))
    rows = {}
    for r in csv.DictReader(open(os.path.join(OUT, 'metrics.csv'))):
        rows[(r['camera'], int(r['frame']))] = r
    order = ['locked', 'naive', 'chase', 'operator']
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
    gdir = os.path.join(OUT, 'grid')
    os.makedirs(gdir, exist_ok=True)
    dash_frames = [d['start_frame'] for d in B['dashes']]
    for f in range(1, B['n'] + 1):
        g = Image.new('RGB', (2 * W, 2 * H), (12, 12, 12))
        d = ImageDraw.Draw(g)
        for k, name in enumerate(order):
            im = Image.open(os.path.join(OUT, name, 'f%04d.png' % f)).convert('RGB').resize((W, H))
            x0, y0 = (k % 2) * W, (k // 2) * H
            g.paste(im, (x0, y0))
            r = rows[(name, f)]
            sc = B['scores'][name]['score']
            d.rectangle([x0, y0, x0 + W, y0 + 56], fill=(0, 0, 0))
            d.text((x0 + 12, y0 + 6), '%s   score %.0f' % (name.upper(), sc), font=font, fill=(255, 214, 120))
            ok = r['in_frame'] == '1'
            d.text((x0 + 12, y0 + 33), '%s  rays %s/9  margin %.2f' % ('IN FRAME' if ok else 'LOST', r['rays_visible_of_9'],
                   float(r['edge_margin'])), font=small, fill=(150, 230, 150) if ok else (255, 110, 90))
            if any(0 <= f - df < 4 for df in dash_frames):
                d.text((x0 + W - 110, y0 + 8), 'DASH!', font=font, fill=(255, 90, 60))
        g.save(os.path.join(gdir, 'f%04d.png' % f))
    silent = os.path.join(OUT, 'camera-bench-muted.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(gdir, 'f%04d.png'),
                    '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', silent], check=True)
    # the sound: a BOOM on every dash (impact drum, onset on the dash's first frame) + the dash burst whoosh
    lib = os.path.join(REPO, 'assets', 'sfx')
    sys.path.insert(0, os.path.join(REPO, 'tools'))
    import bake_events as E
    boom_on = E.onset(os.path.join(lib, 'impact-drum.mp3'))
    wh_on = E.onset(os.path.join(lib, 'dash-burst.mp3'))
    inputs, filt, labels = [], [], []
    for j, dsh in enumerate(B['dashes']):
        t = dsh['start_s']
        for name, src, on, gain, ln in (('boom', 'impact-drum.mp3', boom_on, 1.0, 1.6), ('whoosh', 'dash-burst.mp3', wh_on, 0.7, 0.6)):
            inputs += ['-i', os.path.join(lib, src)]
            n = len(inputs) // 2 - 1 + 1
            ms = int(round(t * 1000))
            filt.append('[%d:a]atrim=%.4f:%.4f,asetpts=PTS-STARTPTS,afade=t=out:st=%.2f:d=0.4,volume=%.2f,adelay=%d|%d[a%d]'
                        % (n, on, on + ln, ln - 0.4, gain, ms, ms, n))
            labels.append('[a%d]' % n)
    filt.append('%samix=inputs=%d:normalize=0,alimiter=limit=0.9[mix]' % (''.join(labels), len(labels)))
    out = os.path.join(OUT, 'camera-bench.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent] + inputs +
                   ['-filter_complex', ';'.join(filt), '-map', '0:v', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac',
                    '-b:a', '192k', '-t', '%.3f' % (B['n'] / FPS), out], check=True)
    # sync: each boom checked ALONE (a boom-only stem placed by the same trim/delay), because the previous boom's ring
    # overlaps the next dash in the full mix and fooled an onset detector (it read -150 ms on dashes 3-4)
    for dsh in B['dashes']:
        t = dsh['start_s']
        ms = int(round(t * 1000))
        stem = os.path.join(OUT, 'boom-stem.m4a')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(lib, 'impact-drum.mp3'), '-filter_complex',
                        '[0:a]atrim=%.4f:%.4f,asetpts=PTS-STARTPTS,afade=t=out:st=1.2:d=0.4,adelay=%d|%d,apad=whole_dur=%.2f[a]'
                        % (boom_on, boom_on + 1.6, ms, ms, B['n'] / FPS), '-map', '[a]', '-c:a', 'aac', stem], check=True)
        a, sr = E.pcm(stem)
        a = np.abs(np.asarray(a, dtype=np.float64))
        idx = np.where(a > a.max() * 10 ** (-30 / 20))[0]
        on = idx[0] / sr
        print('[bench] dash at frame %.1f (%.3f s): boom onset %.4f s -> %+.1f ms (%+.2f frames)' % (
            dsh['start_frame'], t, on, (on - t) * 1000, (on - t) * FPS))
    print('[bench] ->', out)


if __name__ == '__main__':
    {'solve': solve, 'compose': compose}[sys.argv[1] if len(sys.argv) > 1 else 'solve']()

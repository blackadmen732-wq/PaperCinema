#!/usr/bin/env python3
"""SYNTH: a test duel with exact ground truth, for measuring VYRN's external (video-file) perception.

  python3 -m vyrn.bench.synth --out output/vyrn-bench/duel

Writes, from ONE simulation:
  duel.timeline.json   the scene as Paper Cinema timeline data (docs/TIMELINE-FORMAT.md, the 23-bone rig, world
                       transforms, camera per frame, cuts, events with stable ids). This is what the native adapter
                       reads, exactly as it would read output/<film>.timeline.json from tools/timeline.mjs.
  duel.mp4             the same scene drawn as pixels (two paper fighters in profile, swords, a set, sensor noise,
                       one hard cut to a panning camera) with a sound track: footstep thumps, steel clashes from
                       assets/sfx, a hit, soft whooshes that must NOT count as hits, room noise. One clash sound is
                       deliberately 83 ms (2 frames) late so the sync check has a real fault to find.

Why a synthetic scene: a real Paper Cinema timeline needs the browser engine (npm install for three.js), and
an ordinary video has no ground truth at all. Here every footstep, contact, cut and sound is known to the frame,
so the numbers in vyrn/bench/RESULTS.md are measured, not guessed.
"""
import argparse, json, math, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw

from vyrn.geom import project, look_quat, quat_mul, quat_from_axis

BONES = ['root', 'hips', 'waist', 'chest', 'neck', 'head',
         'clavicle.R', 'shoulder.R', 'elbow.R', 'twist.R', 'hand.R',
         'clavicle.L', 'shoulder.L', 'elbow.L', 'twist.L', 'hand.L',
         'thigh.R', 'shin.R', 'foot.R', 'thigh.L', 'shin.L', 'foot.L', 'hakama']
FPS, DUR, W, H = 24, 6.5, 360, 640
CUT_T = 4.2
BLADE = 0.9
ANKLE = 0.04


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def keys(t, ks):
    """piecewise smoothstep through [(t, v), ...]"""
    if t <= ks[0][0]:
        return ks[0][1]
    for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * smooth((t - t0) / (t1 - t0))
    return ks[-1][1]


# ---- the choreography (body time) ----
CAST = {
    'hero': dict(side=1, colour=(232, 150, 60),
                 root=[(0, -2.3), (2.3, -0.85), (4.6, -0.85), (5.25, -0.25), (5.5, -0.2)],
                 arm=[(0, -60), (2.45, -60), (2.85, 100), (3.08, -15), (3.5, -40), (3.9, 35), (4.6, -55),
                      (5.1, 60), (5.32, 5), (5.6, -55), (6.5, -60)]),
    'villain': dict(side=-1, colour=(170, 32, 44),
                    root=[(0, 2.3), (0.2, 2.3), (2.4, 0.85), (5.38, 0.85), (6.05, 1.75), (6.5, 1.75)],
                    arm=[(0, -60), (2.55, -60), (2.9, 55), (3.3, 55), (3.45, 105), (3.82, -5), (4.3, -55),
                         (5.3, -55), (5.45, 40), (6.5, -50)]),
}


class Fighter:
    def __init__(self, cid, spec):
        self.id, self.s = cid, spec['side']
        self.spec = spec
        x0 = keys(0, spec['root'])
        self.feet = {'R': [x0 + 0.12 * self.s, ANKLE], 'L': [x0 - 0.12 * self.s, ANKLE]}
        self.swing = {}          # foot -> (t0, x_from, x_to)

    def step_feet(self, tb, dt):
        x = keys(tb, self.spec['root'])
        v = (keys(tb + 0.05, self.spec['root']) - keys(tb - 0.05, self.spec['root'])) / 0.1
        for side, (t0, xa, xb) in list(self.swing.items()):
            u = (tb - t0) / 0.3
            if u >= 1:
                self.feet[side] = [xb, ANKLE]; del self.swing[side]
            else:
                self.feet[side] = [xa + (xb - xa) * smooth(u), ANKLE + 0.16 * math.sin(math.pi * u)]
        if abs(v) > 0.15 and not self.swing:
            d = 1 if v > 0 else -1
            # the foot furthest behind the direction of travel steps past the root
            back = min(self.feet, key=lambda k: self.feet[k][0] * d)
            if (x - self.feet[back][0]) * d > 0.18:
                self.swing[back] = (tb, self.feet[back][0], x + 0.24 * d)
        return x

    def pose(self, tb):
        s = self.s
        x = keys(tb, self.spec['root'])
        bob = 0.03 * (1 if self.swing else 0)
        th = math.radians(keys(tb, self.spec['arm']))
        P = {}
        P['root'] = (x, 0.0, 0.0)
        P['hips'] = (x, 0.95 + bob, 0.0)
        P['waist'] = (x + 0.01 * s, 1.1 + bob, 0.0)
        P['chest'] = (x + 0.03 * s, 1.3 + bob, 0.0)
        P['neck'] = (x + 0.04 * s, 1.47 + bob, 0.0)
        P['head'] = (x + 0.05 * s, 1.62 + bob, 0.0)
        sh = (x + 0.02 * s, 1.42 + bob)
        for side, z in (('R', 0.18), ('L', -0.18)):
            P['clavicle.' + side] = (sh[0], sh[1], z * 0.45)
            P['shoulder.' + side] = (sh[0], sh[1], z)
        hand = (sh[0] + 0.55 * math.cos(th) * s, sh[1] + 0.55 * math.sin(th))
        el = (sh[0] + 0.3 * math.cos(th - 0.5) * s, sh[1] + 0.3 * math.sin(th - 0.5) - 0.02)
        phi = th + math.radians(20)
        bd = (math.cos(phi) * s, math.sin(phi))
        P['elbow.R'] = (el[0], el[1], 0.15); P['twist.R'] = ((el[0] + hand[0]) / 2, (el[1] + hand[1]) / 2, 0.1)
        P['hand.R'] = (hand[0], hand[1], 0.05)
        hl = (hand[0] - 0.09 * bd[0], hand[1] - 0.09 * bd[1])
        P['elbow.L'] = (el[0] - 0.03 * s, el[1] - 0.03, -0.15); P['twist.L'] = ((el[0] + hl[0]) / 2, (el[1] + hl[1]) / 2, -0.1)
        P['hand.L'] = (hl[0], hl[1], -0.05)
        for side, z in (('R', 0.1), ('L', -0.1)):
            fx, fy = self.feet[side]
            P['thigh.' + side] = (x, 0.92 + bob, z)
            P['shin.' + side] = ((x + fx) / 2 + 0.07 * s, (0.92 + bob + fy) / 2 + 0.02, z)
            P['foot.' + side] = (fx, fy, z)
        P['hakama'] = (x, 0.6 + bob, 0.0)
        q = quat_mul(quat_from_axis((0, 1, 0), 0 if s > 0 else math.pi), quat_from_axis((0, 0, 1), phi))
        weapon = (hand[0], hand[1], 0.05) + tuple(q)
        tip = (hand[0] + BLADE * bd[0], hand[1] + BLADE * bd[1])
        return P, weapon, tip, hand


def seg_dist(p, q, r, s):
    """shortest distance between 2-D segments pq and rs"""
    def pt_seg(a, b, c):
        bx, by = b[0] - a[0], b[1] - a[1]
        L = bx * bx + by * by
        u = 0 if L == 0 else max(0, min(1, ((c[0] - a[0]) * bx + (c[1] - a[1]) * by) / L))
        return math.hypot(a[0] + u * bx - c[0], a[1] + u * by - c[1])

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1, d2, d3, d4 = cross(r, s, p), cross(r, s, q), cross(p, q, r), cross(p, q, s)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return 0.0
    return min(pt_seg(p, q, r), pt_seg(p, q, s), pt_seg(r, s, p), pt_seg(r, s, q))


def camera_at(t):
    if t < CUT_T:
        pos, tgt, fov = (0.0, 1.3, 7.5), (0.0, 1.1, 0.0), 60.0
    else:
        u = (t - CUT_T) / (DUR - CUT_T)
        cx = -0.6 + 1.2 * u
        pos, tgt, fov = (cx, 1.25, 4.4), (cx * 0.5 + 0.2, 1.15, 0.0), 58.0
    return pos, look_quat(pos, tgt), fov


def simulate():
    n = int(round(DUR * FPS))
    F = {c: Fighter(c, CAST[c]) for c in CAST}
    frames, events, tb, stop_until, prev_d, prev_hit = [], [], 0.0, -1, 9.0, 9.0
    ev_n = {}

    def add(type, t, **kw):
        k = ev_n.get(type, 0); ev_n[type] = k + 1
        events.append(dict(id=f'{type}.{k:02d}', type=type, t=round(t, 4), f=int(round(t * FPS)), **kw))

    prev_feet = {}
    for f in range(n):
        t = f / FPS
        in_stop = f < stop_until
        dt = 0 if in_stop else 1 / FPS
        if f > 0:
            tb += dt
        poses = {}
        for c, ft in F.items():
            if not in_stop:
                ft.step_feet(tb, dt)
            poses[c] = ft.pose(tb)
        h, v = poses['hero'], poses['villain']
        d = seg_dist(h[3], h[2], v[3], v[2])
        if d < 0.05 <= prev_d and not in_stop:
            mid = ((h[2][0] + v[2][0]) / 2, (h[2][1] + v[2][1]) / 2, 0.0)
            add('blade-contact', t, tb=round(tb, 4), point=[round(c, 3) for c in mid], intensity=1.0, verified=True)
            add('hit-stop', t, tb=round(tb, 4), duration=0.125)
            stop_until = f + 3
        prev_d = d
        # the final thrust: hero's blade tip reaches the villain's chest
        vc = v[0]['chest']
        hd = math.hypot(h[2][0] - vc[0], h[2][1] - vc[1])
        if hd < 0.12 <= prev_hit and t > 5:
            add('impact', t, intensity=1.0, point=[round(h[2][0], 3), round(h[2][1], 3), 0.0], target='villain')
        prev_hit = hd
        pos, q, fov = camera_at(t)
        row = dict(f=f, t=round(t, 5), tb=round(tb, 5), rate=1, shot='A' if t < CUT_T else 'B',
                   cut=(f == int(math.ceil(CUT_T * FPS))),
                   camera=dict(pos=list(pos), rot=list(q), fov=fov), actors={})
        for c, (P, wpn, tip, hand) in poses.items():
            row['actors'][c] = dict(hidden=False, root=list(P['root']) + [0, 0, 0, 1], ry=0 if F[c].s > 0 else math.pi,
                                    bones=[list(P[b]) + [0, 0, 0, 1] for b in BONES], weapon=list(wpn))
        frames.append(row)
    # footsteps exactly as tools/timeline.mjs footEvents(): y crosses 0.055 falling after having been above 0.1
    iR, iL = BONES.index('foot.R'), BONES.index('foot.L')
    for c in F:
        for side, idx in (('R', iR), ('L', iL)):
            up = False
            for i in range(1, n):
                y, py = frames[i]['actors'][c]['bones'][idx][1], frames[i - 1]['actors'][c]['bones'][idx][1]
                if y > 0.1:
                    up = True
                elif up and y <= 0.055 and y < py:
                    up = False
                    add('footstep', frames[i]['t'], actor=c, side=side,
                        point=frames[i]['actors'][c]['bones'][idx][:3])
    events.sort(key=lambda e: e['t'])
    # re-number per type in time order (stable ids, as the format requires)
    cnt = {}
    for e in events:
        k = cnt.get(e['type'], 0); cnt[e['type']] = k + 1
        e['id'] = f"{e['type']}.{k:02d}"
    return frames, events


SOUND_LATE = ('blade-contact.01', 2 / FPS)   # the deliberate sync fault


def cue_list(events):
    cues = []
    for e in events:
        if e['type'] == 'footstep':
            cues.append(dict(sfx='thump', t=e['t'], why=e['id']))
        elif e['type'] == 'blade-contact':
            late = SOUND_LATE[1] if e['id'] == SOUND_LATE[0] else 0.0
            cues.append(dict(sfx='clash-steel', t=round(e['t'] + late, 4), why=e['id'], offset=late))
        elif e['type'] == 'impact':
            cues.append(dict(sfx='blade-clash', t=e['t'], why=e['id']))
    # whooshes before the strikes: soft attack, should not be detected as hits
    for t in (2.7, 3.6, 5.15):
        cues.append(dict(sfx='whoosh', t=t, why='decoy'))
    return sorted(cues, key=lambda c: c['t'])


def decode(path, sr):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def make_audio(cues, path, repo):
    sr = 48000
    rng = np.random.default_rng(7)
    out = (rng.standard_normal(int(DUR * sr)) * 0.004).astype(np.float32)          # room noise
    sfx = {k: decode(os.path.join(repo, 'assets/sfx', f'{k}.mp3'), sr) for k in ('clash-steel', 'blade-clash')}
    tt = np.arange(int(0.12 * sr)) / sr
    sfx['thump'] = (np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 40) * 0.35).astype(np.float32)
    tw = np.arange(int(0.35 * sr)) / sr
    env = np.sin(np.pi * tw / tw[-1]) ** 2
    sfx['whoosh'] = (rng.standard_normal(tw.size) * env * 0.05).astype(np.float32)
    for c in cues:
        s = sfx[c['sfx']]
        # a sound file may start with silence: align its first loud sample (the attack) to the cue time
        lead = int(np.argmax(np.abs(s) > 0.1 * np.abs(s).max())) if c['sfx'] != 'whoosh' else 0
        i0 = int(c['t'] * sr) - lead
        a, b = max(0, i0), min(out.size, i0 + s.size)
        out[a:b] += s[a - i0:b - i0] * (0.8 if c['sfx'] != 'thump' else 1.0)
    out = np.clip(out, -1, 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype('<i2').tobytes())


def draw_frame(row, rng, bg_cache):
    pos, q, fov = row['camera']['pos'], row['camera']['rot'], row['camera']['fov']
    aspect = W / H
    key = (tuple(round(c, 3) for c in pos), row['shot'])
    img = Image.new('RGB', (W, H), (226, 214, 190))
    d = ImageDraw.Draw(img)
    # set: sky gradient, ground, three paper pillars and a lantern (static scenery the detector must ignore)
    for yy in range(0, H, 8):
        c = int(200 + 30 * yy / H)
        d.rectangle([0, yy, W, yy + 8], fill=(c, c - 12, c - 40))
    g = project(pos, q, fov, aspect, (0, 0, -0.01))
    gy = int(g[1] * H) if g else H
    d.rectangle([0, gy, W, H], fill=(120, 96, 70))
    for px in (-3.0, -1.6, 2.4):
        a = project(pos, q, fov, aspect, (px, 3.2, -2.5)); b = project(pos, q, fov, aspect, (px, 0, -2.5))
        if a and b:
            wpx = max(3, int(0.35 / a[2] * (H / 2) / math.tan(math.radians(fov) / 2)))
            d.rectangle([a[0] * W - wpx / 2, a[1] * H, a[0] * W + wpx / 2, b[1] * H], fill=(92, 60, 48))
    lan = project(pos, q, fov, aspect, (0.5, 2.6, -2.0))
    if lan:
        d.ellipse([lan[0] * W - 7, lan[1] * H - 9, lan[0] * W + 7, lan[1] * H + 9], fill=(250, 210, 120))
    foc = (H / 2) / math.tan(math.radians(fov) / 2)

    def S(p):
        r = project(pos, q, fov, aspect, p)
        return (r[0] * W, r[1] * H, r[2]) if r else None
    limbs = [('hips', 'chest'), ('chest', 'neck'), ('shoulder.L', 'elbow.L'), ('elbow.L', 'hand.L'),
             ('thigh.L', 'shin.L'), ('shin.L', 'foot.L'), ('thigh.R', 'shin.R'), ('shin.R', 'foot.R'),
             ('shoulder.R', 'elbow.R'), ('elbow.R', 'hand.R')]
    for cid in ('villain', 'hero'):
        A = row['actors'][cid]
        B = {b: A['bones'][i][:3] for i, b in enumerate(BONES)}
        col = CAST[cid]['colour']
        for a, b in limbs:
            pa, pb = S(B[a]), S(B[b])
            if pa and pb:
                wpx = max(2, int(0.11 * foc / pa[2]))
                d.line([pa[:2], pb[:2]], fill=col, width=wpx)
        hp = S(B['hips']); hk = S(B['hakama'])
        if hp and hk:
            r = 0.16 * foc / hp[2]
            d.polygon([(hp[0] - r, hp[1]), (hp[0] + r, hp[1]), (hk[0] + r * 1.3, hk[1]), (hk[0] - r * 1.3, hk[1])],
                      fill=tuple(int(c * 0.8) for c in col))
        hd = S(B['head'])
        if hd:
            r = 0.11 * foc / hd[2]
            d.ellipse([hd[0] - r, hd[1] - r, hd[0] + r, hd[1] + r], fill=col)
        w = A['weapon']
        from vyrn.geom import qrot
        tipw = tuple(w[i] + v for i, v in enumerate(qrot(w[3:7], (BLADE, 0, 0))))
        g0, g1 = S(w[:3]), S(tipw)
        if g0 and g1:
            d.line([g0[:2], g1[:2]], fill=(235, 238, 245), width=max(2, int(0.035 * foc / g0[2])))
    a = np.asarray(img, np.int16)
    a = a + rng.normal(0, 3.0, a.shape).astype(np.int16)                      # sensor noise
    return np.clip(a, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='output/vyrn-bench/duel')
    a = ap.parse_args()
    repo = os.getcwd()
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    frames, events = simulate()
    cues = cue_list(events)
    for c in cues:
        if c['sfx'] != 'whoosh':
            events.append(dict(id='', type='cue', t=c['t'], f=int(round(c['t'] * FPS)), sfx=c['sfx'], why=c['why'],
                               offset=c.get('offset', 0.0), source='synth'))
    events.sort(key=lambda e: (e['t'], e['type']))
    k = 0
    for e in events:
        if e['type'] == 'cue':
            e['id'] = f'cue.{k:02d}'; k += 1
    cut_f = [r['f'] for r in frames if r['cut']]
    tl = dict(format='paper-cinema-timeline', version=1,
              generated=dict(tool='vyrn/bench/synth.py', kind='synthetic'),
              film=dict(name='vyrn-duel', title='VYRN synthetic duel', fps=FPS, duration=DUR, frames=len(frames),
                        format='vertical', width=W, height=H),
              clock=dict(fps=FPS, base='film'),
              actors=[dict(id=c, character='synthetic', weapon=dict(kind='katana', bladeLen=BLADE),
                           animation=dict(source='sampled')) for c in CAST],
              bones=dict(order=BONES, space='world', rootIndex=0),
              shots=[dict(id='A', start=0, end=CUT_T, f0=0, f1=cut_f[0] - 1),
                     dict(id='B', start=CUT_T, end=DUR, f0=cut_f[0], f1=len(frames) - 1, cutIn=True)],
              cuts=cut_f, events=events, frames=frames,
              truth=dict(sound_late=dict(event=SOUND_LATE[0], seconds=SOUND_LATE[1]), decoys=[2.7, 3.6, 5.15]))
    json.dump(tl, open(a.out + '.timeline.json', 'w'))
    wav = a.out + '.wav'
    make_audio(cues, wav, repo)
    rng = np.random.default_rng(1)
    p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
                          '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-shortest', a.out + '.mp4'],
                         stdin=subprocess.PIPE)
    for row in frames:
        p.stdin.write(draw_frame(row, rng, None).tobytes())
    p.stdin.close(); p.wait()
    os.remove(wav)
    kinds = {}
    for e in events:
        kinds[e['type']] = kinds.get(e['type'], 0) + 1
    print(f'wrote {a.out}.mp4 and {a.out}.timeline.json: {len(frames)} frames, cut at frame {cut_f}, events {kinds}')


if __name__ == '__main__':
    main()

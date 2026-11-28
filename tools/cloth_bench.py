#!/usr/bin/env python3
"""CLOTH BENCH: today's spring sleeve against the paper cloth (tools/paper_cloth.py), on the SAME motion: an arm of a
baked film (output/<film>.bake.json: every body capsule, every frame, world space). Autopilot item 15 (Mark, 27 Nov:
"what simulation... to make the clothes like real sleeves and paper, like real clothes that can move").

    python3 tools/cloth_bench.py <film> [--actor hero] [--side R] [--from 31.5] [--to 35.0] [--out output/bench/cloth]

Both sleeves are the same paper panel (a kimono sleeve: its top edge on the arm, shoulder to wrist, hanging `hang` m):
  SPRING (today, blender/character/cloth_springs.py): the panel is RIGID, hinged on the arm; one spring bone swings
         it (tip pulled toward the rule's aim, damping, a little gravity, the wind, a max swing, pushed out of the
         body capsules at the tip only)
  PAPER  (tools/paper_cloth.py): position-based dynamics on the panel's point grid: no stretch, stiff to bend except
         along its creases, gravity and air (by how squarely each facet meets the wind), every point kept out of
         the body capsules
Measured per frame and in total: how deep any point of the panel sinks into the body (the arm it hangs from not
counted), the paper's stretch, how far the hem trails the arm. Writes frames (both side by side, seen from the
side of the actor), an mp4 when ffmpeg is there, and <out>/report.json. Pure numpy + PIL: runs beside a render.
"""
import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import paper_cloth as PC                                         # noqa: E402

G = 9.8


def seg_depth(P, a, b, r):
    """Depth of points P (n, 3) inside the capsule a-b of radius r (negative = outside)."""
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    c = a + t[:, None] * ab
    return r - np.linalg.norm(P - c, axis=1)


def push_out(p, caps, margin):
    for a, b, r in caps:
        ab = b - a
        t = min(1.0, max(0.0, float((p - a) @ ab) / max(float(ab @ ab), 1e-12)))
        c = a + t * ab
        d = p - c
        L = float(np.linalg.norm(d))
        if L < r + margin:
            p = c + (d / L if L > 1e-9 else np.array([0.0, 0.0, 1.0])) * (r + margin)
    return p


def rotate_toward(want, d, max_rad):
    """d turned toward want until the angle between them is max_rad."""
    axis = np.cross(want, d)
    n = np.linalg.norm(axis)
    if n < 1e-9:
        return want.copy()
    axis /= n
    # Rodrigues: rotate want about axis by max_rad
    return want * math.cos(max_rad) + np.cross(axis, want) * math.sin(max_rad) + axis * (axis @ want) * (1 - math.cos(max_rad))


def wind_at(W, t):
    """cloth_springs.ClothSprings.wind_at, the same gusts (m/s^2 for the spring)."""
    if not W:
        return np.zeros(3)
    d = np.array([float(W['to'][0]), float(W['to'][1]), 0.0])
    d /= max(np.linalg.norm(d), 1e-9)
    g = float(W.get('gust', 0.5))
    ph = float(W.get('seed', 0)) * 1.7
    gust = 0.55 + 0.45 * math.sin(2 * math.pi * t / 4.3 + ph) * math.sin(2 * math.pi * t / 1.7 + 0.6 * ph)
    flutter = 0.12 * math.sin(2 * math.pi * t * 5.3 + ph) + 0.08 * math.sin(2 * math.pi * t * 8.9 + 2 * ph)
    side = np.array([-d[1], d[0], 0.0]) * (0.25 * math.sin(2 * math.pi * t / 2.9 + ph))
    return (d * ((1 - g) + g * gust + flutter) + side) * float(W.get('strength', 3.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('film')
    ap.add_argument('--actor', default='hero')
    ap.add_argument('--side', default='R')
    ap.add_argument('--from', dest='t0', type=float, default=31.5)
    ap.add_argument('--to', dest='t1', type=float, default=35.0)
    ap.add_argument('--hang', type=float, default=0.30, help='how far the sleeve hangs below the arm (m)')
    ap.add_argument('--cols', type=int, default=10)
    ap.add_argument('--rows', type=int, default=7)
    ap.add_argument('--density', type=float, default=0.25)
    ap.add_argument('--out')
    a = ap.parse_args()
    B = json.load(open(os.path.join(REPO, 'output', a.film + '.bake.json')))
    F = json.load(open(os.path.join(REPO, 'film', a.film + '.json')))
    fps = float(B.get('fps', 30))
    W = F.get('wind')
    if W:          # the film's wind is in film x/z: the bake's world is (x, -z) (film_modular passes it the same way)
        W = dict(W, to=[float(W['to'][0]), -float(W['to'][1])])
    segs = B['actors'][a.actor]['segs']
    f0, f1 = int(round(a.t0 * fps)), min(len(segs) - 1, int(round(a.t1 * fps)))
    s = a.side.upper()
    own = {'upperarm.' + s, 'forearm.' + s, 'hand.' + s.lower()}

    def frame(f):
        d = {n: (np.array(p, float), np.array(q, float), float(r)) for n, p, q, r in segs[f]}
        S, E = d['upperarm.' + s][0], d['upperarm.' + s][1]
        Wr = d['forearm.' + s][1]
        caps = [v for n, v in d.items() if n not in own]
        return S, E, Wr, caps, d

    nu, nv = a.cols, a.rows
    k_elbow = nu // 2                                  # columns 0..k on the upper arm, k..nu-1 on the forearm

    def top_edge(S, E, Wr):
        """The sleeve's top edge on the arm (from a tenth down the upper arm to just before the wrist), lifted onto the
        top of the arm (4 cm above its axis)."""
        pts = []
        for i in range(nu):
            if i <= k_elbow:
                u = 0.1 + 0.9 * i / k_elbow
                p = S + (E - S) * u
            else:
                u = (i - k_elbow) / (nu - 1 - k_elbow) * 0.9
                p = E + (Wr - E) * u
            pts.append(p + np.array([0.0, 0.0, 0.04]))
        return np.array(pts)

    def hang_dir(S, E, Wr):
        """The rule's aim: straight down, square to the forearm (the sleeve hangs under the arm)."""
        ax = Wr - S
        ax /= max(np.linalg.norm(ax), 1e-9)
        dn = np.array([0.0, 0.0, -1.0])
        h = dn - ax * (dn @ ax)
        n = np.linalg.norm(h)
        return h / n if n > 0.2 else dn

    S, E, Wr, caps, _ = frame(f0)
    top0 = top_edge(S, E, Wr)
    h0 = hang_dir(S, E, Wr)
    X0 = np.array([top0[i] + h0 * a.hang * j / (nv - 1) for j in range(nv) for i in range(nu)])
    _, T = PC.grid(nu, nv, (0, 0, 0), (1, 0, 0), (0, 0, -1))    # the triangles of an nu x nv grid
    # creases: one AT THE ELBOW (where the arm forces the fold; without it the stiff paper fought the fold and stretched
    # 14.5% on Kojiro's strike) and one either side; plastic: the paper keeps a fold once it is made
    creases = PC.crease_lines(nu, nv, columns=(k_elbow - 2, k_elbow, k_elbow + 2), rows=(nv - 3,))
    cloth = PC.PaperCloth(X0, T, pins=range(nu), creases=creases, density=a.density, plastic=0.05, iterations=16, substeps=8)
    # settle the paper on the first pose for a second before the clock starts (both methods start at rest)
    for _ in range(30):
        cloth.step(1 / fps, pin_targets=top0, capsules=[(p, q, r + 0.01) for p, q, r in caps])

    # the spring bone: its root in the middle of the top edge, its tip `hang` below
    spr_p, spr_v = None, np.zeros(3)
    L, K, C, MAXD = a.hang * 0.8, 55.0, 7.0, math.radians(75.0)

    out = a.out or os.path.join(REPO, 'output', 'bench', 'cloth', '%s-%s-%s' % (a.film, a.actor, s))
    os.makedirs(out, exist_ok=True)
    for fn in os.listdir(out):
        if fn.endswith('.png'):
            os.remove(os.path.join(out, fn))
    # the view: from the actor's side (along the shoulder line), centred on the chest over the whole stretch
    _, _, _, _, d0 = frame(f0)
    sh = d0['upperarm.L'][0] - d0['upperarm.R'][0]
    view = np.array([sh[0], sh[1], 0.0]) / max(np.hypot(sh[0], sh[1]), 1e-9)       # looking from the right side
    if s == 'L':
        view = -view
    right = np.cross(view, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    up = np.array([0.0, 0.0, 1.0])
    # a three-quarter view (the sleeve face-on, not edge-on), following the shoulder (the cloth's motion RELATIVE to
    # the body is what is compared; a charge would carry it out of a fixed frame)
    fwd = np.cross([0.0, 0.0, 1.0], view)
    view = view * math.cos(math.radians(40)) + fwd * math.sin(math.radians(40))
    view /= np.linalg.norm(view)
    right = np.cross(view, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    PW, PH, SCALE = 540, 720, 560.0
    cen = {'c': None}

    def follow(Sh):
        cen['c'] = Sh.copy() if cen['c'] is None else cen['c'] + (Sh - cen['c']) * 0.35     # a soft follow

    def scr(P, ox):
        q = P - cen['c']
        return np.stack([ox + PW / 2 + (q @ right) * SCALE, PH * 0.42 - (q @ up) * SCALE], axis=-1)

    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
        fontb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 19)
    except OSError:
        font = fontb = ImageFont.load_default()
    light = np.array([-0.4, 0.3, 0.85])
    light /= np.linalg.norm(light)
    rep = {'film': a.film, 'actor': a.actor, 'side': s, 'from': a.t0, 'to': a.t1, 'frames': f1 - f0 + 1,
           'spring': {'depth_cm': [], 'hang_deg': []}, 'paper': {'depth_cm': [], 'hang_deg': [], 'stretch_pct': []}}
    prev_hem = {}
    for f in range(f0, f1 + 1):
        t = f / fps
        S, E, Wr, caps, d = frame(f)
        follow(S)
        top = top_edge(S, E, Wr)
        want = hang_dir(S, E, Wr)
        wind = wind_at(W, t)
        caps_m = [(p, q, r + 0.01) for p, q, r in caps]
        # ---- SPRING (cloth_springs.step for one joint, 4 sub-steps)
        root = top[k_elbow]
        goal = root + want * L
        if spr_p is None:
            spr_p = goal.copy()
        p, v = spr_p, spr_v
        for _ in range(4):
            h = (1 / fps) / 4
            acc = (goal - p) * K - v * C + np.array([0, 0, -G]) * 0.15 + wind
            v = v + acc * h
            p = p + v * h
            dd = p - root
            p = root + dd / max(np.linalg.norm(dd), 1e-9) * L
        dd = (p - root) / max(np.linalg.norm(p - root), 1e-9)
        if math.acos(max(-1.0, min(1.0, float(dd @ want)))) > MAXD:
            dd = rotate_toward(want, dd, MAXD)
            p = root + dd * L
        for _ in range(6):
            q = push_out(p, caps, 0.015)
            if np.linalg.norm(q - p) < 1e-5:
                break
            v = v - (q - p) * fps * 0.5
            p = root + (q - root) / max(np.linalg.norm(q - root), 1e-9) * L
        spr_p, spr_v = p, v
        hd = (p - root) / L
        Xs = np.array([top[i] + hd * a.hang * j / (nv - 1) for j in range(nv) for i in range(nu)])
        # ---- PAPER (PBD). Wind as AIR SPEED, calibrated to the lean the film asks for: paper_cloth's air pushes a sheet
        # facing it with rho*v per m^2 (rho 0.6), its weight is density*g, so a steady breeze leans a hanging sheet by
        # atan(0.6 v / (density g)). The film's wind strength 3 (m/s^2 for the spring: ~15 deg of lean) is v = 1.1 m/s on
        # 0.25 kg/m^2: x0.36. (The first bench used x1.33: a 4 m/s gale that blew the sleeve flat, 26 cm off its hang.)
        cloth.step(1 / fps, pin_targets=top, capsules=caps_m, wind=tuple(wind * 0.36 * (a.density / 0.25)))
        Xp = cloth.X.copy()
        # ---- measure: depth into the body (not the arm it hangs from), how far the hem trails the arm
        for key, X in (('spring', Xs), ('paper', Xp)):
            dep = max([float(seg_depth(X[nu:], p_, q_, r_).max()) for p_, q_, r_ in caps] + [0.0])
            rep[key]['depth_cm'].append(round(100 * max(0.0, dep), 2))
            # how the sleeve hangs against GRAVITY: each column's top-to-hem line against straight down made square to
            # the arm there (what a free sheet does at rest in still air: 0). A column where the arm itself points up or
            # down has no such line (the sheet hangs alongside the arm) and is skipped; "angle from vertical" read 88
            # deg for a sleeve hanging correctly from a lowered arm.
            angs = []
            for i in range(nu):
                tt = top[min(nu - 1, i + 1)] - top[max(0, i - 1)]
                tt /= max(np.linalg.norm(tt), 1e-9)
                gp = np.array([0.0, 0.0, -1.0]) - tt * (-tt[2])
                if np.linalg.norm(gp) < 0.3:
                    continue
                gp /= np.linalg.norm(gp)
                cv = X[(nv - 1) * nu + i] - X[i]
                angs.append(math.degrees(math.acos(max(-1.0, min(1.0, float(cv @ gp) / max(np.linalg.norm(cv), 1e-9))))))
            rep[key]['hang_deg'].append(round(float(np.mean(angs)), 1) if angs else None)
        rep['paper']['stretch_pct'].append(round(100 * cloth.log['stretch'][-1], 2))
        # ---- draw
        img = Image.new('RGB', (2 * PW + 20, PH + 70), (24, 22, 20))
        dr = ImageDraw.Draw(img)
        for k, (key, X, title) in enumerate((('spring', Xs, 'TODAY: spring sleeve (rigid panel, one bone)'),
                                             ('paper', Xp, 'PAPER CLOTH: PBD, creases, collision'))):
            ox = k * (PW + 20)
            dr.rectangle((ox, 0, ox + PW, PH), fill=(38, 35, 32))
            # body capsules, far to near
            items = []
            for n, (p_, q_, r_) in d.items():
                items.append(((((p_ + q_) / 2) @ view), 'cap', (p_, q_, r_, n in own)))
            tri_depth = X[T].mean(1) @ view
            for ti, tri in enumerate(T):
                items.append((float(tri_depth[ti]), 'tri', tri))
            items.sort(key=lambda it: it[0])
            for _, kind, obj in items:
                if kind == 'cap':
                    p_, q_, r_, arm = obj
                    a2, b2 = scr(p_, ox), scr(q_, ox)
                    col = (150, 146, 140) if arm else (96, 92, 88)
                    w = max(2, int(2 * r_ * SCALE))
                    dr.line((a2[0], a2[1], b2[0], b2[1]), fill=col, width=w)
                    for c_ in (a2, b2):
                        dr.ellipse((c_[0] - w / 2, c_[1] - w / 2, c_[0] + w / 2, c_[1] + w / 2), fill=col)
                else:
                    P3 = X[obj]
                    n_ = np.cross(P3[1] - P3[0], P3[2] - P3[0])
                    n_ /= max(np.linalg.norm(n_), 1e-9)
                    sh_ = 0.45 + 0.55 * abs(float(n_ @ light))
                    col = tuple(int(c * sh_) for c in (196, 52, 44))
                    pts = [tuple(v) for v in scr(P3, ox)]
                    dr.polygon(pts, fill=col)
            # crease lines in ink
            for i_, j_ in creases:
                p1, p2 = scr(X[i_], ox), scr(X[j_], ox)
                dr.line((p1[0], p1[1], p2[0], p2[1]), fill=(40, 12, 10), width=2)
            dr.text((ox + 10, PH + 6), title, font=fontb, fill=(240, 225, 190))
            dep, hang = rep[key]['depth_cm'][-1], rep[key]['hang_deg'][-1]
            txt = 'into the body %.1f cm   off its gravity line %s' % (dep, ('%.0f deg' % hang) if hang is not None else '-')
            if key == 'paper':
                txt += '   stretch %.1f%%' % rep['paper']['stretch_pct'][-1]
            dr.text((ox + 10, PH + 36), txt, font=font, fill=(230, 90, 80) if dep > 0.5 else (200, 200, 200))
        dr.text((10, 8), '%s  %s %s arm  t %.2f s  (f%d)' % (a.film, a.actor, s, t, f + 1), font=font, fill=(200, 200, 200))
        img.save(os.path.join(out, 'f%04d.png' % (f - f0 + 1)))
    for key in ('spring', 'paper'):
        dps = rep[key]['depth_cm']
        rep[key]['summary'] = {'frames_inside': sum(1 for x in dps if x > 0.5), 'deepest_cm': max(dps),
                               'hang_median_deg': float(np.median([h for h in rep[key]['hang_deg'] if h is not None])),
                               'hang_max_deg': max(h for h in rep[key]['hang_deg'] if h is not None)}
    rep['paper']['summary']['stretch_max_pct'] = max(rep['paper']['stretch_pct'])
    rep['paper']['summary']['stretch_median_pct'] = float(np.median(rep['paper']['stretch_pct']))
    json.dump(rep, open(os.path.join(out, 'report.json'), 'w'), indent=1)
    mp4 = out.rstrip('/') + '.mp4'
    try:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(int(fps)), '-i', os.path.join(out, 'f%04d.png'),
                        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', mp4],
                       check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print('[bench] no mp4:', e)
        mp4 = None
    print('[bench] %s %s %s arm, %.2f-%.2f s, %d frames -> %s' % (a.film, a.actor, s, a.t0, a.t1, f1 - f0 + 1, mp4 or out))
    for key in ('spring', 'paper'):
        sm = rep[key]['summary']
        print('  %-6s inside the body on %d frames (deepest %.1f cm); off its gravity line %.0f deg (median), %.0f (max)%s'
              % (key, sm['frames_inside'], sm['deepest_cm'], sm['hang_median_deg'], sm['hang_max_deg'],
                 ('; stretch median %.2f%%, max %.2f%%' % (sm['stretch_median_pct'], sm['stretch_max_pct'])) if key == 'paper' else ''))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""BODY PLAN: where to cut a generated full-body model into the sections our skeleton wears (head, torso, two
sleeves, hakama/skirt, two legs, two feet), measured from the model itself. Autopilot item 14 (the board's cast).

    python3 tools/body_plan.py output/tripo/cast/ronin-model-1.pbr.glb [--facing +x] [--shoulder-z 1.40] [--out DIR]

Reads the GLB with numpy alone (no Blender: it runs beside a render), puts the figure upright (glTF is Y-up; Tripo
bodies face +X), and slices it every 1% of its height. From the width profile (side to side) and the depth profile
(front to back) it finds:
  shoulders  the widest slice in the top 35% (the arms hang there in a rest pose)
  neck       the narrowest slice between the shoulders and the top
  armpit     where the arms separate from the torso (the side-to-side gap below the shoulders opens)
  hips/crotch the slice below which the figure splits into two legs (two clusters across)
  knees, ankles  fractions of the leg (0.52 and 0.92 of crotch -> floor), checked against the leg width minimum
and scales everything so the shoulder line sits at --shoulder-z metres (the same fit as kojiro_*_t1: 1.40 m).
Writes <out>/<name>.plan.json (every number) and <out>/<name>.plan.png (front and side silhouettes, the cut lines).
These are PROPOSALS for library/ai-parts.json keep boxes: the prepared sections are still judged on a render.
"""
import argparse
import json
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read_glb(path):
    """All mesh positions of a .glb in world space (node transforms applied), as an (n, 3) array."""
    data = open(path, 'rb').read()
    magic, _ver, _len = struct.unpack_from('<III', data, 0)
    if magic != 0x46546C67:
        raise SystemExit('%s: not a GLB file' % path)
    off, J, BIN = 12, None, None
    while off < len(data):
        clen, ctype = struct.unpack_from('<II', data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            J = json.loads(chunk)
        elif ctype == 0x004E4942:
            BIN = chunk
        off += 8 + clen

    def accessor(i):
        a = J['accessors'][i]
        bv = J['bufferViews'][a['bufferView']]
        dt, k, n = np.dtype(COMP[a['componentType']]), NCOMP[a['type']], a['count']
        start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = bv.get('byteStride') or dt.itemsize * k
        if stride == dt.itemsize * k:                       # tightly packed (the usual case)
            return np.frombuffer(BIN, dtype=dt, count=n * k, offset=start).reshape(n, k).astype(np.float64)
        rows = np.frombuffer(BIN, dtype=np.uint8, count=stride * (n - 1) + dt.itemsize * k, offset=start)
        rows = np.concatenate([rows, np.zeros(stride * n - len(rows), np.uint8)]).reshape(n, stride)
        return rows[:, :dt.itemsize * k].copy().view(dt).reshape(n, k).astype(np.float64)

    def node_matrix(nd):
        if 'matrix' in nd:
            return np.array(nd['matrix'], float).reshape(4, 4).T
        T = np.eye(4)
        if 'translation' in nd:
            T[:3, 3] = nd['translation']
        R = np.eye(4)
        if 'rotation' in nd:
            x, y, z, w = nd['rotation']
            R[:3, :3] = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
        S = np.diag(list(nd.get('scale', [1, 1, 1])) + [1])
        return T @ R @ S

    pts = []

    def visit(ni, M):
        nd = J['nodes'][ni]
        M2 = M @ node_matrix(nd)
        if 'mesh' in nd:
            for prim in J['meshes'][nd['mesh']]['primitives']:
                P = accessor(prim['attributes']['POSITION'])
                pts.append((np.c_[P, np.ones(len(P))] @ M2.T)[:, :3])
        for c in nd.get('children', []):
            visit(c, M2)

    scene = J['scenes'][J.get('scene', 0)]
    for ni in scene['nodes']:
        visit(ni, np.eye(4))
    return np.vstack(pts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('glb')
    ap.add_argument('--facing', default='+x', help='where the figure faces in the file (Tripo: +x)')
    ap.add_argument('--shoulder-z', type=float, default=1.40)
    ap.add_argument('--out', default=os.path.join(REPO, 'output', 'body-plans'))
    a = ap.parse_args()
    P = read_glb(a.glb)
    # upright: glTF Y-up -> Z-up; front -> -Y (the rig's facing), side to side -> X
    sgn = -1.0 if a.facing.startswith('-') else 1.0
    ax = {'x': 0, 'y': 1, 'z': 2}[a.facing[-1]]
    fwd = P[:, ax] * sgn
    up = P[:, 1]
    side_axis = 2 if ax == 0 else 0
    side = P[:, side_axis] * (1.0 if ax == 0 else -1.0) * sgn
    z0, z1 = up.min(), up.max()
    H = z1 - z0
    u = (up - z0) / H                                      # 0 = soles, 1 = top of the head
    bins = np.linspace(0, 1, 101)
    width, depth, gap, cx = [], [], [], []
    for b0, b1 in zip(bins[:-1], bins[1:]):
        m = (u >= b0) & (u < b1)
        if m.sum() < 5:
            width.append(0.0)
            depth.append(0.0)
            gap.append(0.0)
            cx.append(0.0)
            continue
        s, f = side[m], fwd[m]
        width.append(float(np.percentile(s, 99) - np.percentile(s, 1)))
        depth.append(float(np.percentile(f, 99) - np.percentile(f, 1)))
        # the widest empty gap across the middle third of the slice (legs apart, arms off the torso)
        hs, _ = np.histogram(s, bins=60, range=(np.percentile(s, 1), np.percentile(s, 99)))
        empty = (hs == 0).astype(int)
        best = run = 0
        for v in empty[10:50]:
            run = run + 1 if v else 0
            best = max(best, run)
        gap.append(best / 60.0 * width[-1])
        cx.append(float(np.median(s)))
    width, depth, gap = np.array(width), np.array(depth), np.array(gap)
    sl = lambda i: (i + 0.5) / 100.0                                  # noqa: E731  slice index -> height fraction
    # NECK: the narrowest slice between 70% and 95% of the height (below the head, above the shoulders).
    # SHOULDER LINE: going down from the neck, the first slice at least 1.8x the neck's width. (In a rest A-pose the
    # widest slice up top is where the hands hang, ~52%: "the widest slice in the top 35%" sat on its lower bound for
    # every body. Checked on Kojiro, whose fit is known: 74%.)
    band = [i for i in range(70, 96) if width[i] > 0]
    i_neck = min(band, key=lambda i: width[i])
    i_sh = next((i for i in range(i_neck - 1, 50, -1) if width[i] >= 1.8 * width[i_neck]), i_neck - 4)
    scale = a.shoulder_z / (sl(i_sh) * H)
    m = lambda i: round(sl(i) * H * scale, 3)                       # noqa: E731  slice -> metres on the rig
    # the other cuts: Kojiro's validated section boxes (kojiro_*_t1, shoulders at 1.40 m), which the fit carries over
    # to any figure of the same build; a long skirt, wide sleeves or a hood are adjusted on the render, not here
    plan = {'glb': os.path.relpath(a.glb, REPO), 'vertices': int(len(P)), 'height_file_units': round(float(H), 4),
            'shoulder_frac': round(sl(i_sh), 3), 'neck_frac': round(sl(i_neck), 3),
            'scale_to_rig': round(float(scale), 4), 'height_m': round(float(H * scale), 3),
            'heights_m': {'neck': m(i_neck), 'shoulders': m(i_sh)},
            'widths_m': {'shoulders': round(float(width[i_sh] * scale), 3), 'neck': round(float(width[i_neck] * scale), 3)},
            'head_m': round(float(H * scale) - m(i_neck), 3),
            'fit': {'mode': 'body', 'shoulder_frac': round(sl(i_sh), 3), 'shoulder_z': a.shoulder_z}}
    i_pit = i_crotch = i_knee = i_ankle = None
    os.makedirs(a.out, exist_ok=True)
    name = os.path.basename(a.glb).split('.')[0]
    json.dump(plan, open(os.path.join(a.out, name + '.plan.json'), 'w'), indent=1)
    # the picture: front (side to side) and side (front to back) silhouettes with the cut lines
    S = 520
    img = Image.new('RGB', (2 * S + 30, S + 40), (24, 22, 20))
    dr = ImageDraw.Draw(img)
    for k, (hx, title) in enumerate(((side, 'front'), (fwd, 'side'))):
        ox = k * (S + 30)
        c0 = np.median(hx)
        px = ox + S / 2 + (hx - c0) / H * S * 0.9
        py = S + 10 - u * S * 0.9 - 0.05 * S
        idx = np.random.default_rng(0).choice(len(px), size=min(len(px), 60000), replace=False)
        for x_, y_ in zip(px[idx], py[idx]):
            dr.point((x_, y_), fill=(200, 190, 170))
        for nm, i, col in (('neck', i_neck, (240, 200, 90)), ('shoulders', i_sh, (240, 120, 90))):
            yy = S + 10 - sl(i) * S * 0.9 - 0.05 * S
            dr.line((ox, yy, ox + S, yy), fill=col, width=1)
            dr.text((ox + 4, yy - 12), '%s %.2f m (%.0f%%)' % (nm, m(i), 100 * sl(i)), fill=col)
        dr.text((ox + 4, S + 18), '%s  %s' % (name, title), fill=(230, 230, 230))
    img.save(os.path.join(a.out, name + '.plan.png'))
    print('[plan] %s: %d vertices; neck at %.0f%%, shoulder line at %.0f%% of the figure -> %.2f m tall on the rig, '
          'head %.2f m (neck to top), shoulders %.2f m wide -> %s' % (
              name, len(P), 100 * sl(i_neck), 100 * sl(i_sh), H * scale, plan['head_m'], width[i_sh] * scale,
              os.path.relpath(os.path.join(a.out, name + '.plan.png'), REPO)))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Side-by-side contact sheet for a capture: source video frame (with the detected landmarks) | our figure.

    python3 tools/mocap_sheet.py film/mocap-test.json <video> --times 0.5,2,3.5,5 --out output/stills/mocap-sheet.png

Times are capture time (0 = the first captured frame). Renders the film stills itself (nice -n 10) unless
--no-render, using the prefix mocap-test-. The film must come from tools/mocap_film.py (it carries "mocap").
"""
import argparse
import json
import os
import subprocess

import cv2
import numpy as np

BONES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (27, 31),
         (24, 26), (26, 28), (28, 32), (7, 0), (8, 0)]
LEFT = {11, 13, 15, 23, 25, 27, 31, 7}


def overlay(img, lm):
    h, w = img.shape[:2]
    pts = [(int(x * w), int(y * h)) for x, y, _ in lm]
    for a, b in BONES:
        col = (60, 200, 255) if a in LEFT and b in LEFT else (255, 120, 60) if a not in LEFT and b not in LEFT else (230, 230, 230)
        cv2.line(img, pts[a], pts[b], col, 2, cv2.LINE_AA)
    for i, p in enumerate(pts):
        if i in (0, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28):
            cv2.circle(img, p, 3, (255, 255, 255), -1, cv2.LINE_AA)
    return img


def label(img, text):
    cv2.putText(img, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('film')
    ap.add_argument('video')
    ap.add_argument('--times', required=True)
    ap.add_argument('--out', default='output/stills/mocap-sheet.png')
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--height', type=int, default=360)
    args = ap.parse_args()
    film = json.load(open(args.film))
    mc = film['mocap']
    cap = json.load(open(mc['capture']))
    raw = cap['raw']
    rt = np.array(raw['t'])
    times = [float(x) for x in args.times.split(',')]
    ftimes = [round(t + mc['lead'], 3) for t in times]
    if not args.no_render:
        subprocess.run(['nice', '-n', '10', 'node', 'engine/render.mjs', '--film', args.film, '--still', ','.join(map(str, ftimes)),
                        '--prefix', 'mocap-test-'], check=True)
    v = cv2.VideoCapture(args.video)
    fps = v.get(cv2.CAP_PROP_FPS)
    rows = []
    for t, ft in zip(times, ftimes):
        v.set(cv2.CAP_PROP_POS_FRAMES, int(round((mc['sourceStart'] + t) * fps)))
        ok, fr = v.read()
        if not ok:
            continue
        if cap['source'].get('mirror'):
            fr = cv2.flip(fr, 1)
        i = int(np.argmin(np.abs(rt - t)))
        fr = overlay(fr, raw['image'][i])
        still = cv2.imread(f'output/stills/mocap-test-t{ft:g}.png')     # render.mjs names stills like JS numbers (t1, t2.5)
        H = args.height
        a = cv2.resize(fr, (int(fr.shape[1] * H / fr.shape[0]), H))
        b = cv2.resize(still, (int(still.shape[1] * H / still.shape[0]), H)) if still is not None else np.zeros_like(a)
        rows.append(np.hstack([label(a, f'source t={t:.2f}s'), np.full((H, 6, 3), 255, np.uint8), label(b, f'ours t={ft:.2f}s')]))
    w = max(r.shape[1] for r in rows)
    rows = [np.hstack([r, np.zeros((r.shape[0], w - r.shape[1], 3), np.uint8)]) for r in rows]
    sheet = np.vstack([np.vstack([r, np.full((6, w, 3), 255, np.uint8)]) for r in rows])
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    cv2.imwrite(args.out, sheet)
    print('wrote', args.out)


if __name__ == '__main__':
    main()

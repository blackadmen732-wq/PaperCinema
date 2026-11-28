#!/usr/bin/env python3
"""Side-by-side video + contact sheet for blender/bench/layered_sleeve_bench.py (AUTOPILOT item 17).

    python3 tools/layered_bench_video.py [output/bench/layered]

Reads <dir>/frames/{today,layered}_NNNN.png and <dir>/report.json; writes <dir>/side/NNNN.png (labelled, with the
frame's measured numbers), <dir>.mp4 and <dir>/contact.png (every 4th frame) for watching frame by frame.
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    d = os.path.join(REPO, sys.argv[1] if len(sys.argv) > 1 else 'output/bench/layered')
    rep = json.load(open(os.path.join(d, 'report.json')))
    rows = rep['per_frame']
    side = os.path.join(d, 'side')
    os.makedirs(side, exist_ok=True)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
        fontb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
    except OSError:
        font = fontb = ImageFont.load_default()
    outs = []
    for i, r in enumerate(rows, 1):
        a = Image.open(os.path.join(d, 'frames', 'today_%04d.png' % i)).convert('RGB')
        b = Image.open(os.path.join(d, 'frames', 'layered_%04d.png' % i)).convert('RGB')
        W, H = a.size
        img = Image.new('RGB', (2 * W + 10, H + 64), (24, 22, 20))
        img.paste(a, (0, 0))
        img.paste(b, (W + 10, 0))
        dr = ImageDraw.Draw(img)
        t = r['f'] / rep['fps']
        dr.text((8, 6), '%s  t %.2f s  f%d' % (rep['film'], t, r['f'] + 1), font=font, fill=(30, 30, 30))
        ins_t = max(r['inside_cm_today'].values() or [0])
        ins_l = max(r['inside_cm_layered'].values() or [0])
        dr.text((8, H + 6), 'TODAY: sleeve skinned to the arm', font=fontb, fill=(240, 225, 190))
        dr.text((8, H + 34), 'into the body %.1f cm' % ins_t, font=font,
                fill=(230, 90, 80) if ins_t > 0.5 else (200, 200, 200))
        dr.text((W + 18, H + 6), 'LAYERED: 4 paper plates on springs', font=fontb, fill=(240, 225, 190))
        pR = r.get('plate_deg_R', [])
        dr.text((W + 18, H + 34), 'into the body %.1f cm   R plates %s deg   ripple %.0f deg' % (
            ins_l, '/'.join('%.0f' % x for x in pR), r.get('ripple_deg_R', 0)), font=font,
            fill=(230, 90, 80) if ins_l > 0.5 else (200, 200, 200))
        p = os.path.join(side, '%04d.png' % i)
        img.save(p)
        outs.append(p)
    mp4 = d.rstrip('/') + '.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(int(rep['fps'])), '-i',
                    os.path.join(side, '%04d.png'), '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', '-crf', '20', mp4], check=True)
    # contact sheet: every 4th frame, 4 per row, at half size
    pick = outs[::4]
    th = [Image.open(p) for p in pick]
    w, h = th[0].size[0] // 2, th[0].size[1] // 2
    cols = 4
    sheet = Image.new('RGB', (cols * w, ((len(th) + cols - 1) // cols) * h), (0, 0, 0))
    for k, im in enumerate(th):
        sheet.paste(im.resize((w, h)), ((k % cols) * w, (k // cols) * h))
    sheet.save(os.path.join(d, 'contact.png'))
    print('wrote', mp4, 'and', os.path.join(d, 'contact.png'), '(%d frames, %d on the sheet)' % (len(outs), len(pick)))


if __name__ == '__main__':
    main()

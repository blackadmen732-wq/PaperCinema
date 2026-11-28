#!/usr/bin/env python3
"""TEST: tools/paperize_model.py converts the Poly Haven bucket (assets/polyhaven/wooden_bucket_01, CC0) to paper and
the result is what the library needs. Runs Blender twice: paperize (paper.glb, preview.png, paper.json), then
re-import paper.glb (--check) and measure what came back.

    python3 tools/test_paperize_model.py [--keep]        # exit 0 = PASS; output in output/library/test/

Checks: facets reduced (<= 1500 tris, >= 300) and every face flat; size kept to 1 % of the source (metres, from the
source model's own bounding box measured here too); base at z = 0; 2..8 paper sheets in the model's own colours (the
wood sheet brown: red > green > blue, not the grey of an unsampled default); the glb round-trips with the same faces,
size and sheet materials; preview.png exists and is not blank.
"""
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
B = os.environ.get('BLENDER', '/opt/blender-dl/blender-4.5.16-linux-x64/blender')
SRC = os.path.join(REPO, 'assets/polyhaven/wooden_bucket_01/wooden_bucket_01_1k.gltf')
OUT = os.path.join(REPO, 'output/library/test/wooden_bucket_01')


def blender(*args):
    r = subprocess.run([B, '-b', '-P', os.path.join(REPO, 'tools/paperize_model.py'), '--'] + list(args),
                       capture_output=True, text=True, cwd=REPO)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit('FAIL: blender exited %d' % r.returncode)
    return r.stdout


def main():
    if not os.path.exists(SRC):
        sys.exit('FAIL: %s missing (python3 tools/polyhaven.py sync)' % SRC)
    fails = []

    def ok(cond, what):
        print(('  ok   ' if cond else '  FAIL ') + what)
        if not cond:
            fails.append(what)

    src = json.loads(blender('--check', SRC).split('PC_CHECK ')[1].splitlines()[0])
    blender('--in', SRC, '--out', OUT, '--samples', '16', '--res', '256')
    st = json.load(open(os.path.join(OUT, 'paper.json')))
    back = json.loads(blender('--check', os.path.join(OUT, 'paper.glb')).split('PC_CHECK ')[1].splitlines()[0])
    print('source  ', src)
    print('paper   ', {k: st[k] for k in ('faces', 'tris', 'size_m', 'materials', 'flat')})
    print('glb back', back)
    ok(300 <= st['tris'] <= 1500 and st['tris'] < src['tris'], 'facets reduced: %d -> %d tris' % (src['tris'], st['tris']))
    ok(st['flat'] and back['smooth_faces'] == 0, 'every face flat (paper.json flat, %d smooth faces in the glb)' % back['smooth_faces'])
    err = max(abs(a - b) / max(b, 1e-6) for a, b in zip(st['size_m'], src['size_m']))
    ok(err < 0.01, 'size kept: %s m vs source %s m (worst %.2f %%)' % (st['size_m'], src['size_m'], err * 100))
    ok(abs(back['min_z']) < 1e-3, 'base at z = 0 (min z %.4f)' % back['min_z'])
    sh = st['sheets']
    ok(2 <= len(sh) <= 8, '%d paper sheets' % len(sh))
    wood = max(sh, key=lambda s: s['share'])['srgb']
    ok(wood[0] > wood[1] > wood[2] and wood[0] - wood[2] > 0.08, 'largest sheet is wood-brown, sampled from the texture: sRGB %s' % wood)
    ok(any(max(s['srgb']) - min(s['srgb']) < 0.08 for s in sh), 'a grey (iron band) sheet found: %s' % [s['srgb'] for s in sh])
    ok(back['faces'] >= st['faces'] * 0.95 and back['sheets'] == len(sh), 'glb round trip: %d faces, %d sheet materials' % (back['faces'], back['sheets']))
    berr = max(abs(a - b) for a, b in zip(back['size_m'], st['size_m']))
    ok(berr < 1e-3, 'glb size matches (%.4f m)' % berr)
    png = os.path.join(OUT, 'preview.png')
    ok(os.path.exists(png) and os.path.getsize(png) > 20000, 'preview.png written (%d bytes)' % (os.path.getsize(png) if os.path.exists(png) else 0))
    print('PASS' if not fails else 'FAIL: %d check(s)' % len(fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()

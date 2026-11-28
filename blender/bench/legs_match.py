"""LEGS MATCH: does Blender's leg solver put the legs where the engine does? (28 Nov: it did not: the port ignored the
foot plan `_feet`, so every 'planted' foot of a lockFeet film glided with the body in the render.)

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  $B -b --python-exit-code 1 -P blender/bench/legs_match.py -- --film ganryujima-ep1 [--who target] [--frames 1440-1480]

Poses the shared rig (blender/character/modular_builder.Rig) with the TIMELINE pose of each frame (what the bake
uses) and compares the hip, knee and ankle joints with the engine's own world joints of the same frame
(output/<film>.motion.json, figure.js through three.js). Prints the worst and median distance per joint and exits 1
when any ankle is more than 1 cm from the engine's (the feet are the point).
"""
import json
import math
import os
import statistics
import sys

import bpy
from mathutils import Vector

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for d in ('blender', 'blender/character'):
    sys.path.insert(0, os.path.join(REPO, d))
import modular_builder as MB  # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d


FILM = arg('film', 'ganryujima-ep1')
WHO = arg('who', 'target')
fr0, fr1 = (int(v) for v in arg('frames', '1440-1480').split('-'))
T = json.load(open(os.path.join(REPO, 'output', FILM + '.timeline.json')))
M = json.load(open(os.path.join(REPO, 'output', FILM + '.motion.json')))
per = len(M['frames']) // max(1, len(T['frames']))       # motion samples per film frame
names = M['joints']
coll = bpy.data.collections.new('LM')
bpy.context.scene.collection.children.link(coll)
rig = MB.Rig(coll, 'LM')
PAIRS = {'thigh.R': 'rthigh', 'shin.R': 'rshin', 'foot.R': 'rfoot', 'thigh.L': 'lthigh', 'shin.L': 'lshin',
         'foot.L': 'lfoot', 'hips': 'hips', 'root': 'root'}
err = {k: [] for k in PAIRS}
feet_seen = 0
for f in range(fr0, fr1 + 1):
    act = T['frames'][f]['actors'].get(WHO)
    if not act or not isinstance(act.get('pose'), dict):
        continue
    feet_seen += 1 if act['pose'].get('_feet') else 0
    pose = dict(act['pose'])
    if '--no-feet' in ARGV:                                 # the old port: the foot plan ignored (the test must fail)
        pose.pop('_feet', None)
    rig.pose(pose)
    bpy.context.view_layer.update()
    js = M['frames'][f * per]['cast'][WHO]['joints']
    for jn, bn in PAIRS.items():
        x, y, z = js[names.index(jn)][:3]
        want = Vector((x, -z, y))                           # three.js -> Blender
        got = rig.J[bn].matrix_world.translation
        err[jn].append((got - want).length)
bad = False
print('[legs] %s %s frames %d-%d (%d with a foot plan): Blender joint vs engine joint, cm' % (FILM, WHO, fr0, fr1, feet_seen))
for jn, e in err.items():
    if not e:
        continue
    print('  %-8s median %6.2f  worst %6.2f' % (jn, statistics.median(e) * 100, max(e) * 100))
    if jn.startswith('foot') and max(e) > 0.01:
        bad = True
print('[legs] %s' % ('FAIL: an ankle is more than 1 cm from the engine' if bad else 'PASS: every ankle within 1 cm'))
sys.exit(1 if bad else 0)

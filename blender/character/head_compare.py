"""HEAD COMPARE: the same three cameras on any recipe, so a new head part is judged side by side with the old.

    B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
    $B -b -P blender/character/head_compare.py -- --recipe library/character-recipes/kojiro.json \
        --out output/heads/kojiro [--light neutral|cinematic] [--res 480] [--samples 32]

Writes <out>-full.png (whole figure, 3/4 front), <out>-head.png (head and shoulders, 3/4 front),
<out>-profile.png (head, side) and <out>-front.png (head, straight on), plus <out>-head.json with the measured
head: the bounding box of every part bound to the head bone, in metres, so the size of a new head is a
number, not an impression. Same lens, same distances, same light for every recipe.
--poses a,b,c renders the head close-up and in profile in each pose instead (<out>-pose-<name>-head/profile.png).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modular_builder as MB  # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d


def head_box(objs, head_joint):
    """World bounding box of every rigid part parented to the head joint (mask, hair, hat, a bought head)."""
    lo, hi, names = Vector((9, 9, 9)), Vector((-9, -9, -9)), []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type != 'MESH' or o.parent is not head_joint:
            continue
        ev = o.evaluated_get(dg)
        for v in ev.data.vertices:
            w = ev.matrix_world @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
        names.append(o.name)
    return lo, hi, names


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    recipe = MB.load_recipe(os.path.abspath(arg('recipe')))
    ch = MB.build(recipe, pose=arg('pose', 'neutral'), pose_overrides=recipe.get('pose_overrides'))
    MB.studio(sc, arg('light', 'neutral'))
    r = int(arg('res', 480))
    MB.render_settings(sc, f'{r}x{int(r * 1.25)}', int(arg('samples', 32)))
    out = arg('out')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    lo, hi, names = head_box(ch['objects'], ch['joints']['head'])
    if not names:                                  # builder without bone tags: fall back to the rest head socket
        lo, hi = Vector((-0.12, -0.15, 1.47)), Vector((0.12, 0.12, 1.78))
    hc = (lo + hi) / 2
    json.dump({'recipe': recipe.get('id'), 'head_parts': names, 'min': list(lo), 'max': list(hi),
               'size_m': list(hi - lo), 'centre': list(hc)}, open(out + '-head.json', 'w'), indent=1)
    print('[head] %s parts %s size %.3f x %.3f x %.3f m, top at z %.3f' % (recipe.get('id'), names, *(hi - lo), hi.z))
    if arg('poses'):
        # the head in motion: each pose, the same head-and-shoulders camera re-aimed at the head (collar clipping,
        # the chin in the collar, hair through the shoulders show here before they show in a film)
        for nm in arg('poses').split(','):
            ch['rig'].pose(nm)
            bpy.context.view_layer.update()
            lo2, hi2, _ = head_box(ch['objects'], ch['joints']['head'])
            c2 = (lo2 + hi2) / 2
            for shot, ang in (('head', 32), ('profile', 90)):
                a = math.radians(ang)
                MB.camera(sc, (c2.x - math.sin(a) * 1.25, c2.y - math.cos(a) * 1.25, c2.z + 0.02), (c2.x, c2.y, c2.z - 0.08), 85)
                MB.render(sc, f'{out}-pose-{nm}-{shot}.png')
        return
    center, height = MB.frame(ch['objects'])
    shots = [('full', 30, height * 2.55, center[2] + 0.12, center, 70),
             ('head', 32, 1.25, hc.z + 0.02, (0, 0, hc.z - 0.06), 85),
             ('profile', 90, 1.05, hc.z, (0, 0, hc.z - 0.03), 85),
             ('front', 0, 1.05, hc.z, (0, 0, hc.z - 0.03), 85)]
    for nm, ang, d, z, look, lens in shots:
        a = math.radians(ang)
        MB.camera(sc, (-math.sin(a) * d, -math.cos(a) * d, z), look, lens)
        MB.render(sc, f'{out}-{nm}.png')


main()

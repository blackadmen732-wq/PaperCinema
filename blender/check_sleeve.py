# SLEEVE CLEARANCE on the Blender character - the one that actually renders.
#
#   blender -b -P blender/check_sleeve.py -- --recipe library/character-recipes/ronin-reference.json
#
# Prints the smallest gap between the tamoto's evaluated mesh and the head, for a set of poses that
# raise the arms, and exits 1 if any of them puts cloth inside the head. Measured on the DEFORMED
# mesh (depsgraph-evaluated, so the armature modifier has run), not on the rest geometry, because the
# question is where the cloth ends up after the skin moves it.
#
# Why a Blender script and not the node checker: tools/sleeve_check.mjs measures engine/figure.js,
# the preview engine. The films render this character, and it has its own sleeve and its own rig.
# A fix proved on one is not proved on the other.
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'character'))
import modular_builder as MB            # noqa: E402

CLEAR = 0.0            # cloth may pass beside the head; never inside it
POSES = {
    'neutral': {},
    'jodan-raise': {'rsx': -2.8, 'lsx': -2.8, 'rex': -0.9, 'lex': -0.9},
    'both-up-in': {'rsx': -2.6, 'lsx': -2.6, 'rcz': 0.4, 'lcz': 0.4, 'rex': -1.4, 'lex': -1.4},
    'guard-high': {'rsx': -2.0, 'lsx': -1.6, 'rex': -1.6, 'lex': -1.6},
    'overhead-twist': {'rsx': -2.9, 'lsx': -2.7, 'rsy': 0.5, 'lsy': -0.5, 'rex': -1.2, 'lex': -1.2},
}


def world_verts(dg, ob):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    M = ev.matrix_world
    pts = [M @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return pts


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rpath = MB.arg('recipe', 'library/character-recipes/ronin-reference.json')
    recipe = MB.load_recipe(os.path.abspath(rpath))
    ch = MB.build(recipe, pose='neutral')
    objs = ch['objects']
    sleeves = [o for o in objs if o.name.startswith('tamoto') and 'glow' not in o.name]
    # The FACE is what must stay visible. The kasa is deliberately a wide disc and its bounding box
    # covers both shoulders, so measuring against it would call every arm pose a failure and tell us
    # nothing. Hair hangs behind the head and is cloth itself. So: head, face and mask only.
    heads = [o for o in objs if any(o.name.startswith(p) for p in ('head', 'face', 'mask'))]
    if not sleeves:
        print('  no tamoto in this recipe - nothing to check')
        return 0
    if not heads:
        print('  FAIL: no head mesh found, cannot measure')
        return 1
    dg = bpy.context.evaluated_depsgraph_get()
    worst = ('', 1e9)
    for name, over in POSES.items():
        ch['rig'].pose('neutral', **over)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        hp = [p for o in heads for p in world_verts(dg, o)]
        lo = Vector((min(p.x for p in hp), min(p.y for p in hp), min(p.z for p in hp)))
        hi = Vector((max(p.x for p in hp), max(p.y for p in hp), max(p.z for p in hp)))
        # SIGNED distance to the head's box, so the number says HOW FAR in, not just whether. A flag
        # cannot tell a sleeve grazing the jaw from a sleeve swallowing the face, and those are the
        # two cases this check exists to separate.
        gap, inside = 1e9, 0
        for o in sleeves:
            for p in world_verts(dg, o):
                if all(lo[i] <= p[i] <= hi[i] for i in range(3)):
                    inside += 1
                    d = -min(min(p[i] - lo[i], hi[i] - p[i]) for i in range(3))
                else:
                    d = Vector((max(lo.x - p.x, 0, p.x - hi.x), max(lo.y - p.y, 0, p.y - hi.y),
                                max(lo.z - p.z, 0, p.z - hi.z))).length
                gap = min(gap, d)
        print('  %-16s sleeve-to-head %6.1f cm  (%d vert(s) inside the face)' % (name, gap * 100, inside))
        if gap < worst[1]:
            worst = (name, gap)
    ok = worst[1] >= CLEAR
    print('  %s worst: %s at %.1f cm' % ('OK' if ok else 'FAIL', worst[0], worst[1] * 100))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

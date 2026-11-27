"""PARTS CATALOGUE: every part in the library as a picture, and a character pulled apart into its parts.

    B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
    $B -b -P blender/character/parts_catalog.py -- --tiles output/character/catalog          (one image per part)
    $B -b -P blender/character/parts_catalog.py -- --explode library/character-recipes/kojiro-ai.json \
        --out output/character/exploded-kojiro                                               (exploded view)
    python3 blender/character/parts_catalog.py --sheet output/character/catalog               (the labelled grid)

Tiles: each part is built ALONE on the shared rig (its own socket, its own sheet), framed and rendered on the
neutral studio grey. Exploded: the whole character is built and posed, each part is frozen to a mesh and pushed
away from the body along the line from the body's centre to its socket, and its name is written next to it.
"""
import json
import math
import os
import sys

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]


def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d


HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))


def sheet(folder):
    """Outside Blender: tiles -> one labelled grid, grouped by slot in layer order."""
    from PIL import Image, ImageDraw, ImageFont
    meta = json.load(open(os.path.join(folder, 'tiles.json')))
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15)
    small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
    T, cols = 260, 6
    rows = (len(meta) + cols - 1) // cols
    img = Image.new('RGB', (cols * T, rows * (T + 40)), (40, 40, 44))
    d = ImageDraw.Draw(img)
    meta = [m for m in meta if m.get('file')]
    for i, m in enumerate(meta):
        x, y = (i % cols) * T, (i // cols) * (T + 40)
        tile = Image.open(os.path.join(folder, m['file'])).convert('RGB').resize((T, T))
        img.paste(tile, (x, y))
        d.text((x + 6, y + T + 2), m['part'], fill=(255, 225, 120), font=font)
        d.text((x + 6, y + T + 20), m['slot'] + (' · AI' if 'ai' in m['tags'] else ''), fill=(200, 200, 205), font=small)
    out = folder.rstrip('/') + '-sheet.png'
    img.save(out)
    print('[catalog] sheet', out, img.size)


if __name__ == '__main__' and arg('sheet'):
    sheet(arg('sheet'))
    sys.exit(0)

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

sys.path.insert(0, HERE)
import modular_builder as MB  # noqa: E402
import part_registry as reg  # noqa: E402


def bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = Vector((9, 9, 9)), Vector((-9, -9, -9))
    for o in objs:
        if o.type != 'MESH':
            continue
        ev = o.evaluated_get(dg)
        for v in ev.data.vertices:
            w = ev.matrix_world @ v.co
            lo, hi = Vector(map(min, lo, w)), Vector(map(max, hi, w))
    return lo, hi


def tiles(folder):
    os.makedirs(folder, exist_ok=True)
    meta = []
    names = sorted(reg.PARTS, key=lambda n: (reg.PARTS[n]['layer'], n))
    if arg('only'):          # --only armored_,fan_t1: (re)render just these (name prefixes), keep the other tiles
        pre = tuple(arg('only').split(','))
        names = [n for n in names if n.startswith(pre)]
        old = os.path.join(folder, 'tiles.json')
        meta = [m for m in (json.load(open(old)) if os.path.exists(old) else []) if m['part'] not in names]
    for nm in names:
        spec = reg.PARTS[nm]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        try:                                        # a part's own sheet, as a recipe would pass it
            ch = MB.build({'id': 'cat', 'parts': [{'part': nm, 'params': {'material': spec['material']}}], 'seed': 3},
                          pose='neutral')
        except Exception as e:                      # one broken part must not hide the rest of the library
            print('[catalog] FAILED', nm, repr(e), flush=True)
            meta.append({'part': nm, 'slot': spec['slot'], 'layer': spec['layer'], 'file': None,
                         'tags': list(spec['tags']), 'error': repr(e)})
            continue
        MB.studio(sc, 'neutral')
        MB.render_settings(sc, '320x320', int(arg('samples', 12)))
        lo, hi = bbox(ch['objects'])
        c, size = (lo + hi) / 2, max((hi - lo).length, 0.05)
        a = math.radians(30)
        d = size * 2.1
        MB.camera(sc, (c.x - math.sin(a) * d, c.y - math.cos(a) * d, c.z + size * 0.35), c, 50)
        f = f'{spec["layer"]:02d}_{spec["slot"]}__{nm}.png'
        MB.render(sc, os.path.join(folder, f))
        meta.append({'part': nm, 'slot': spec['slot'], 'layer': spec['layer'], 'file': f, 'tags': list(spec['tags']),
                     'size_m': [round(x, 3) for x in (hi - lo)]})
        json.dump(meta, open(os.path.join(folder, 'tiles.json'), 'w'), indent=1)
        print('[catalog]', nm, flush=True)


def explode(recipe_path, out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    recipe = MB.load_recipe(os.path.abspath(recipe_path))
    ch = MB.build(recipe, pose='neutral', pose_overrides=recipe.get('pose_overrides'))
    dg = bpy.context.evaluated_depsgraph_get()
    centre = Vector((0, 0, 1.05))
    groups = {}
    for o in ch['objects']:                       # freeze each posed part to a plain mesh in world space
        if o.type != 'MESH' or not len(o.data.vertices):
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        me.transform(o.matrix_world)
        f = bpy.data.objects.new(o.name + '_x', me)
        sc.collection.objects.link(f)
        key = (o.get('pc_recipe', o.name), o.get('pc_socket', ''))
        groups.setdefault(key, []).append(f)
        o.hide_render = True
    labels = []
    k = float(arg('spread', 0.75))
    for (part, sock), objs in groups.items():
        sp = Vector(reg.SOCKETS[sock]['pos']) if sock in reg.SOCKETS else centre
        push = (sp - centre) * k
        push.y = push.y * 0.4 - 0.05 * abs(push.x)         # mostly sideways and up/down, a little back
        push.x *= 1.35
        push.z *= 1.2
        for f in objs:
            f.location += push
        lo, hi = bbox(objs)
        side = reg.SOCKETS.get(sock, {}).get('side', 0)
        if side >= 0:                                     # one label per part (the left copy of a pair)
            labels.append({'part': part, 'slot': reg.PARTS[part]['slot'] if part in reg.PARTS else '',
                           'at': list((lo + hi) / 2), 'right': list(Vector((hi.x, (lo.y + hi.y) / 2, (lo.z + hi.z) / 2)))})
    MB.studio(sc, arg('light', 'neutral'))
    MB.render_settings(sc, '900x1200', int(arg('samples', 24)))
    allo = [f for g in groups.values() for f in g]
    lo, hi = bbox(allo)
    c = (lo + hi) / 2
    h = max(hi.z - lo.z, (hi.x - lo.x) * 1.33)
    cam = MB.camera(sc, (c.x - 0.35, c.y - h * 1.55, c.z + 0.1), Vector((c.x + 0.18, c.y, c.z)), 50)
    bpy.context.view_layer.update()
    for L in labels:
        p = world_to_camera_view(sc, cam, Vector(L['right']))
        L['screen'] = [p.x, 1 - p.y]
    MB.render(sc, out + '.png')
    json.dump(labels, open(out + '.labels.json', 'w'), indent=1)
    print('[catalog] exploded', out, len(groups), 'parts')


if arg('tiles'):
    tiles(arg('tiles'))
if arg('explode'):
    explode(arg('explode'), arg('out', 'output/character/exploded'))

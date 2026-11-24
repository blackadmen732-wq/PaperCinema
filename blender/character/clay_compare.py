"""CLAY_COMPARE: neutral-light clay turnarounds of any TRELLIS .glb, for comparing generations
(TRELLIS v1 vs TRELLIS.2). Guide: docs/TOOLS-EVALUATED.md §5. No paper shader, no inner lantern, no
coloured key: one grey clay material under flat white light, so only the GEOMETRY is being judged.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  nice -n 10 $B -b -t 2 -P blender/character/clay_compare.py -- \
      --models origami_samurai_s7,origami_samurai_t2_s7 --out output/character/clay-trellis-compare.png
  options: --views front,q,side,back  --res 420x640  --samples 24
"""
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import rig_trellis as rt                                     # noqa: E402

VIEWS = {'front': 0.0, 'q': 0.75, 'side': 1.5708, 'back': 3.1416}


def clay(obj):
    m = bpy.data.materials.new('CLAY')
    m.use_nodes = True
    bsdf = m.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.62, 0.60, 0.57, 1)
    bsdf.inputs['Roughness'].default_value = 0.62
    for inp in ('Metallic', 'Specular IOR Level'):
        if inp in bsdf.inputs:
            bsdf.inputs[inp].default_value = 0.0 if inp == 'Metallic' else 0.3
    obj.data.materials.clear()
    obj.data.materials.append(m)


def neutral_light(scene):
    scene.world = scene.world or bpy.data.worlds.new('W')
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes['Background']
    bg.inputs[0].default_value = (0.55, 0.55, 0.56, 1)       # even dome: no direction, no colour
    bg.inputs[1].default_value = 1.0
    for name, loc, energy in (('key', (2.2, -3.0, 3.0), 500), ('fill', (-2.6, -2.0, 1.6), 220)):
        la = bpy.data.lights.new(name, 'AREA')
        la.energy, la.size = energy, 3.0
        ob = bpy.data.objects.new(name, la)
        scene.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = Vector((0, 0, -1)).rotation_difference((Vector((0, 0, 1.0)) - Vector(loc)).normalized())


def shot(path, res, samples):
    sc = bpy.context.scene
    cam = bpy.data.objects.new('CAM', bpy.data.cameras.new('CAM'))
    sc.collection.objects.link(cam)
    cam.location, cam.rotation_euler = (0, -4.4, 1.0), (1.50, 0, 0)
    cam.data.lens = 75
    sc.camera = cam
    rt.render_settings(sc, res=res, samples=samples, blur=False, threads=2)
    sc.render.film_transparent = False
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', required=True, help='comma separated model names (assets/models/<name>.glb)')
    ap.add_argument('--views', default='front,q,side')
    ap.add_argument('--res', default='420x640')
    ap.add_argument('--samples', type=int, default=24)
    ap.add_argument('--out', default='output/character/clay-trellis-compare.png')
    a = ap.parse_args(argv)
    out = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tiles = []
    for model in a.models.split(','):
        for view in a.views.split(','):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            spec = rt.model_spec(model)
            mesh = rt.import_trellis(model, spec)
            mesh.rotation_mode = 'XYZ'
            mesh.rotation_euler[2] += VIEWS.get(view, 0.0)
            clay(mesh)
            neutral_light(bpy.context.scene)
            p = f'{os.path.splitext(out)[0]}-{model}-{view}.png'
            shot(p, a.res, a.samples)
            tiles.append((model, view, p))
            print('TILE', model, view, p, 'verts', len(mesh.data.vertices), 'faces', len(mesh.data.polygons), flush=True)
    print('TILES ' + ';'.join(f'{m}|{v}|{p}' for m, v, p in tiles))


if __name__ == '__main__':
    main()

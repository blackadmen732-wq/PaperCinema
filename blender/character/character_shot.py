"""Render a short turn of a production paper character for the Blender render job."""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import modular_builder as mb
from gpu_setup import use_gpu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', default=mb.CATALOG['default_hero'])
    parser.add_argument('--frames', default='1-12')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--res', default='720x1280')
    parser.add_argument('--samples', type=int, default=48)
    parser.add_argument('--light', choices=('neutral', 'cinematic'), default='cinematic')
    parser.add_argument('--no-denoise', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    first, last = (int(n) for n in args.frames.split('-', 1))
    if first < 1 or last < first:
        parser.error('--frames must be a positive inclusive range, for example 1-12')

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    recipe = mb.cast_recipe(args.recipe)
    base = dict(mb.POSES[recipe.get('pose', 'neutral')], **recipe.get('pose_overrides', {}))
    character = mb.build(recipe, pose=base)
    center, height = mb.frame(character['objects'])
    target = Vector(center) + Vector((0, 0, height * .08))
    camera = mb.camera(scene, (0, -height * 2.5, target.z), target, 66)
    mb.studio(scene, args.light)
    mb.render_settings(scene, args.res, args.samples, denoise=not args.no_denoise)
    use_gpu(scene)
    args.out.mkdir(parents=True, exist_ok=True)

    for frame in range(first, last + 1):
        scene.frame_set(frame)
        t = (frame - first) / max(last - first, 1)
        phase = math.tau * (frame - 1) / 72
        pose = dict(base, hx=base.get('hx', 0) - .10 * t,
                    hy=base.get('hy', 0) + .13 * t,
                    tx=base.get('tx', 0) + .018 * math.sin(phase))
        character['rig'].pose(pose)
        angle = math.radians(44 - 24 * t)
        distance = height * (2.53 - .13 * t)
        camera.location = target + Vector((-math.sin(angle) * distance, -math.cos(angle) * distance, .11))
        camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
        mb.render(scene, args.out / f'f{frame:04d}.png')


if __name__ == '__main__':
    main()

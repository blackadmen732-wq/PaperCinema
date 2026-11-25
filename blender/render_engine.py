"""Pick the render engine. EEVEE by default, Cycles only when a shot needs real light transport.

Why EEVEE is the default: Paper Cinema is stylized, not photoreal. A path tracer spends its whole
budget simulating light bounces that the washi look then flattens away. Measured on this machine
(blender/character/trellis_shot.py, one 540x960 frame of ronin_base, fog and a light shaft):
see docs/RENDER-ENGINE.md for the numbers and the side-by-side stills.

  from render_engine import setup_render
  setup_render(scene)                      # EEVEE (default)
  setup_render(scene, 'cycles')            # force the path tracer
  PC_ENGINE=cycles blender -b -P ...       # force it from the shell, no code change

Samples mean different things in the two engines, so pass `quality` (draft|check|final) instead of a
raw number and let each engine pick its own: EEVEE's TAA samples are cheap, Cycles' paths are not.
"""
import os

import bpy

# quality -> (eevee taa samples, cycles samples)
QUALITY = {
    'draft': (8, 8),
    'check': (32, 24),
    'final': (128, 96),
}


def _eevee(scene, samples):
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    ee = scene.eevee
    ee.taa_render_samples = samples
    ee.use_shadows = True
    ee.shadow_ray_count = 2                 # soft shadow edges; 1 is blocky on paper folds
    ee.shadow_step_count = 6
    ee.use_volumetric_shadows = True        # the light shaft has to read through the fog
    ee.use_raytracing = True                # screen-space GI/reflections, so the lantern glow spills
    ee.use_fast_gi = True
    ee.fast_gi_resolution = '2'
    print(f'[engine] EEVEE Next, {samples} TAA samples')
    return 'EEVEE'


def _cycles(scene, samples):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.volume_bounces = 1
    try:                                    # gpu_setup lives next to this file
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from gpu_setup import use_gpu
        use_gpu(scene)
    except Exception as e:                  # noqa: BLE001
        print('[engine] no GPU setup:', e)
    print(f'[engine] Cycles, {samples} samples')
    return 'CYCLES'


def setup_render(scene, engine=None, quality='check', samples=None):
    """Set the engine and its sampling. Returns the engine name actually used."""
    engine = (engine or os.environ.get('PC_ENGINE', 'eevee')).strip().lower()
    ee_n, cy_n = QUALITY.get(quality, QUALITY['check'])
    if engine in ('cycles', 'path', 'cpu'):
        return _cycles(scene, samples or cy_n)
    return _eevee(scene, samples or ee_n)

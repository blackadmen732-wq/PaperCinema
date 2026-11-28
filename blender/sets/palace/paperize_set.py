"""PAPERIZE A SET: the characters' paper surface (paper_materials.add_fold_lines + paper_surface: ink in the valleys of
every fold, a light edge on the ridges, a printed mottle, soft occlusion in the folds) on every building mesh of a
built set, at ARCHITECTURE scale, then render its camera anchors. Mark, 28 Nov: the palace "with the texture", the
look of his paper-craft boards; with photo textures or plain paper materials alone it read as a realistic 3D castle.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  nice -n 15 $B -b -t 2 -P blender/sets/palace/paperize_set.py -- --blend output/sets/dev/palace-island.blend \
      --out output/sets/dev/palace-island-folded --cams CAM_sea,CAM_texture [--width 0.06] [--angle 30] [--res 540x960]

Why other numbers than the characters': a character's ink line is 3.5 mm wide because it is seen from 1-3 m; a keep
seen from 50 m with a 35 mm lens has about 5 cm per pixel at 540 px, so the line is `width` 6 cm and the mottle is
coarser. The sea, the sky, the paper sun and the far mountain cards are left alone (their look is their own).
Lives in blender/sets/palace/ (outside the Episode 1 render stamp, which covers blender/*.py and blender/*/*.py).
"""
import os
import sys

import bpy

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
for d in ('blender', 'blender/world', 'blender/character', 'blender/sets'):
    p = os.path.join(REPO, d)
    if p not in sys.path:
        sys.path.insert(0, p)
import paper_materials as pm  # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default=None):
    k = '--' + name
    return ARGV[ARGV.index(k) + 1] if k in ARGV else default


BLEND = arg('blend')
OUT = arg('out')
CAMS = [c for c in (arg('cams') or '').split(',') if c]
WIDTH, ANGLE = float(arg('width', 0.06)), float(arg('angle', 30))
RES = arg('res', '540x960')
SAMPLES = int(arg('samples', 16))
SKIP = ('SEA', 'SKY', 'LO_Mount', 'MOUNT', 'CLOUD', 'LAYER', 'FOG', 'ocean', 'sea', 'sky', 'mountain', 'cloud')

CRAFT = '--craft' in ARGV
# --craft: every kit material becomes a SHEET of paper of its colour (washi plaster, grey kraft stone, dark card roofs,
# brown card wood, red card lacquer...), each facet its own tone (facet_rand), fibres; the glows (windows, lanterns)
# stay. The kit's own procedural stone/plaster/wood read as a realistic castle (28 Nov, the first palace stills).
SHEETS = [   # (name contains, colour (linear RGB), facet_var, fibre_scale)
    ('window_glow', None, 0, 0), ('lantern_paper', None, 0, 0),
    ('plaster', (0.80, 0.74, 0.62), 0.07, 6.0), ('tile', (0.105, 0.11, 0.125), 0.10, 8.0),
    ('gold', (0.62, 0.42, 0.13), 0.08, 10.0), ('window_dark', (0.035, 0.03, 0.03), 0.05, 8.0),
    ('wood_dark', (0.12, 0.075, 0.05), 0.08, 8.0), ('wood_aged', (0.28, 0.19, 0.12), 0.08, 8.0),
    ('lacquer_red', (0.50, 0.07, 0.04), 0.06, 8.0), ('stone_dressed', (0.46, 0.44, 0.40), 0.12, 5.0),
    ('stone_mossy', (0.27, 0.30, 0.22), 0.12, 5.0), ('stone_dark', (0.17, 0.16, 0.15), 0.10, 5.0),
    # the stones light, the gaps between them near-black: a cut-paper wall reads by its dark gaps (with both in tan
    # paper the stone pattern vanished, 28 Nov)
    ('stone_lantern', (0.42, 0.40, 0.37), 0.10, 6.0), ('stone', (0.50, 0.48, 0.44), 0.16, 5.0),
    ('backfill', (0.045, 0.04, 0.035), 0.05, 5.0), ('earth', (0.33, 0.25, 0.17), 0.10, 4.0),
    ('iron', (0.07, 0.07, 0.075), 0.06, 8.0), ('pine_needle', (0.05, 0.10, 0.06), 0.10, 10.0),
    ('bark', (0.13, 0.085, 0.06), 0.10, 8.0)]
_made = {}


def sheet_for(m):
    if not m or not m.name.startswith('SET_'):
        return m
    key = m.name[4:]
    for k, col, fv, fs in SHEETS:
        if k in key:
            if col is None:
                return m                        # a glow stays as it is
            if key not in _made:
                _made[key] = pm.paper_material('PC_sheet_' + key, col, translucency=0.0, fibre_scale=fs,
                                               fibre_strength=0.10, facet_var=fv, flat=True, seed=len(_made))
            return _made[key]
    return m


bpy.ops.wm.open_mainfile(filepath=os.path.abspath(BLEND))
sc = bpy.context.scene
folds, done, mats = 0, 0, []
for ob in sc.objects:
    if ob.type != 'MESH' or not len(ob.data.polygons) or ob.name.startswith(SKIP) or any(s in ob.name for s in SKIP[6:]):
        continue
    if any(m_ and m_.name.startswith(('LO_Sea', 'LO_PaperSun', 'LO_Mount', 'LO_Cloud')) for m_ in ob.data.materials):
        continue
    if ob.data.users > 1:                      # shared mesh data (instances): fold it once
        if ob.data.get('pc_folded'):
            mats += [m_ for m_ in ob.data.materials if m_ and m_ not in mats]
            continue
    if CRAFT:
        for i_, m_ in enumerate(ob.data.materials):
            ob.data.materials[i_] = sheet_for(m_)
        pm.add_facet_attribute(ob, seed=done)
    folds += pm.add_fold_lines(ob, ANGLE)
    ob.data['pc_folded'] = 1
    done += 1
    mats += [m_ for m_ in ob.data.materials if m_ and m_ not in mats]
up = sum(1 for m_ in mats if pm.paper_surface(m_, ink=0.85, width=WIDTH, light=0.45, mottle=0.14, mottle_scale=0.8, ao=0.4))
print('[paperize] %d meshes, %d folds sharper than %.0f deg, paper surface on %d of %d materials (ink line %.0f cm)'
      % (done, folds, ANGLE, up, len(mats), WIDTH * 100))
w, h = (int(v) for v in RES.split('x'))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
if sc.render.engine == 'CYCLES':
    sc.cycles.samples = SAMPLES
else:
    try:
        sc.eevee.taa_render_samples = SAMPLES
    except AttributeError:
        pass
# the set's camera anchors are empties carrying lens_mm / fstop / focus_m; one real camera (KUROKO) is moved onto
# each of them, as blender/sets/build_set.py put_camera does
cam = bpy.data.objects.get('KUROKO') or next((o for o in sc.objects if o.type == 'CAMERA'), None)
sc.camera = cam
for i, name in enumerate(CAMS):
    a = bpy.data.objects.get(name)
    if a is None:
        print('[paperize] no camera anchor', name)
        continue
    cam.matrix_world = a.matrix_world.copy()
    cam.data.lens = a.get('lens_mm', cam.data.lens)
    cam.data.dof.use_dof = bool(a.get('fstop', 0) > 0)
    if cam.data.dof.use_dof:
        cam.data.dof.aperture_fstop, cam.data.dof.focus_distance = a['fstop'], a['focus_m']
    sc.render.filepath = os.path.abspath(OUT + ('' if i == 0 else '-' + name) + '.png')
    bpy.ops.render.render(write_still=True)
    print('[paperize] ->', sc.render.filepath)

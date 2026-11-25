"""Anime shading for paper: a two-tone ramp and an ink outline, in both engines.

Why this exists: until now every shot lit folded washi *realistically*. A path tracer spends its
whole budget on soft bounce light, and soft light is exactly what flattens a paper crease. Anime
throws that away on purpose: few tones, a hard terminator, a drawn line round the silhouette.

  from toon import toon_shade, ink_outline, stylize
  stylize(obj)                      # both, with the Paper Cinema defaults
  toon_shade(obj, tones=2)          # shading only
  ink_outline(obj, width=0.004)     # outline only

Engine note. The usual trick (Shader to RGB) is EEVEE-only: Cycles has no screen-space shading to
convert. So this uses each engine's own route and the look matches:
  * Cycles  -> Toon BSDF, which is a real toon closure, with `size` as the terminator position
  * EEVEE   -> Diffuse into Shader to RGB into a stepped ColorRamp

The outline is one method in both: an inverted hull. A Solidify modifier pushes a shell outward with
flipped normals, and the shell's material is transparent on front faces and ink on back faces, so all
you ever see is a line round the silhouette. No compositor pass, so it survives motion blur and it
works per object, which means the sword can take a thinner line than the robe.
"""
import bpy

INK = (0.03, 0.025, 0.03, 1.0)          # not pure black: pure black reads as a hole, not a line
OUTLINE_MAT = 'PC_Ink_Outline'


def _is_eevee(scene):
    return scene.render.engine.startswith('BLENDER_EEVEE')


def _base_source(nt):
    """What currently drives Base Color: ('link', socket) or ('value', rgba).

    The TRELLIS meshes are textured — the washi colour is a baked image, not a flat value. Reading
    only the default and deleting the tree threw that texture away and rendered the figure near
    black. So keep whatever feeds Base Color and re-route it into the toon shader.
    """
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return ('value', (0.85, 0.82, 0.75, 1.0))
    inp = bsdf.inputs['Base Color']
    if inp.is_linked:
        return ('link', inp.links[0].from_socket)
    return ('value', tuple(inp.default_value))


def toon_shade(obj, tones=2, terminator=0.55, smooth=0.03, scene=None):
    """Step each material's shading into flat tones, keeping whatever drives its base colour."""
    scene = scene or bpy.context.scene
    eevee = _is_eevee(scene)
    done = 0
    for slot in obj.material_slots:
        mat = slot.material
        if not mat or mat.name == OUTLINE_MAT:
            continue
        mat.use_nodes = True
        nt = mat.node_tree
        kind, src = _base_source(nt)

        # Remove ONLY the Principled node. Everything upstream of it (image textures, UV maps,
        # colour tweaks) is the look the owner already built and must survive. Removing a node
        # invalidates held references, so re-fetch the output node afterwards.
        for n in [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED']:
            nt.nodes.remove(n)
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if out is None:
            out = nt.nodes.new('ShaderNodeOutputMaterial')

        if eevee:
            # EEVEE route: Diffuse -> Shader to RGB -> stepped ramp -> multiply by the base colour.
            dif = nt.nodes.new('ShaderNodeBsdfDiffuse')
            dif.inputs['Color'].default_value = (1, 1, 1, 1)
            s2rgb = nt.nodes.new('ShaderNodeShaderToRGB')
            ramp = nt.nodes.new('ShaderNodeValToRGB')
            els = ramp.color_ramp.elements
            while len(els) > 1:
                els.remove(els[-1])
            els[0].position = 0.0
            els[0].color = (0.42, 0.42, 0.42, 1)          # the shadow tone, as a multiplier
            for i in range(1, tones):
                p = terminator + (i - 1) * (1 - terminator) / max(tones - 1, 1)
                shade = 0.42 + 0.58 * (i / max(tones - 1, 1))
                e = els.new(min(p, 0.999))
                e.color = (shade, shade, shade, 1)
                if smooth > 0:
                    els.new(min(p + smooth, 1.0)).color = e.color
            mul = nt.nodes.new('ShaderNodeMixRGB')
            mul.blend_type = 'MULTIPLY'
            mul.inputs['Fac'].default_value = 1.0
            emi = nt.nodes.new('ShaderNodeEmission')
            nt.links.new(dif.outputs[0], s2rgb.inputs[0])
            nt.links.new(s2rgb.outputs[0], ramp.inputs['Fac'])
            nt.links.new(ramp.outputs['Color'], mul.inputs[2])
            if kind == 'link':
                nt.links.new(src, mul.inputs[1])
            else:
                mul.inputs[1].default_value = src
            nt.links.new(mul.outputs['Color'], emi.inputs['Color'])
            nt.links.new(emi.outputs[0], out.inputs['Surface'])
        else:
            # Cycles route: the Toon BSDF is a real toon closure, so the texture feeds it directly.
            toon = nt.nodes.new('ShaderNodeBsdfToon')
            toon.component = 'DIFFUSE'
            toon.inputs['Size'].default_value = terminator
            toon.inputs['Smooth'].default_value = smooth
            if kind == 'link':
                nt.links.new(src, toon.inputs['Color'])
            else:
                toon.inputs['Color'].default_value = src
            nt.links.new(toon.outputs[0], out.inputs['Surface'])
        done += 1
    return done


def _ink_material():
    mat = bpy.data.materials.get(OUTLINE_MAT)
    if mat:
        return mat
    mat = bpy.data.materials.new(OUTLINE_MAT)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputMaterial')
    geo = nt.nodes.new('ShaderNodeNewGeometry')          # Backfacing: 0 front, 1 back
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    ink = nt.nodes.new('ShaderNodeEmission')
    ink.inputs['Color'].default_value = INK
    mix = nt.nodes.new('ShaderNodeMixShader')
    # Polarity matters and it is the opposite of the obvious guess. The Solidify modifier flips
    # the shell's normals, so the part of the shell nearest the camera is BACKfacing and must
    # vanish; what remains visible past the silhouette is frontfacing and is the line. Getting
    # this backwards paints the whole shell with ink and hides the character behind it.
    nt.links.new(geo.outputs['Backfacing'], mix.inputs['Fac'])
    nt.links.new(ink.outputs[0], mix.inputs[1])          # Fac=0, frontfacing -> the line
    nt.links.new(clear.outputs[0], mix.inputs[2])        # Fac=1, backfacing  -> vanish
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    mat.use_backface_culling = False
    mat.blend_method = 'BLEND'
    return mat


def ink_outline(obj, width=0.004):
    """Inverted-hull outline. width is in metres, so it is the same line at any camera distance."""
    if obj.type != 'MESH':
        return False
    mat = _ink_material()
    if mat.name not in [s.name for s in obj.data.materials]:
        obj.data.materials.append(mat)
    idx = list(obj.data.materials).index(mat)
    for m in list(obj.modifiers):
        if m.name == 'PC_Outline':
            obj.modifiers.remove(m)
    sol = obj.modifiers.new('PC_Outline', 'SOLIDIFY')
    sol.thickness = width
    sol.offset = 1.0
    sol.use_flip_normals = True
    sol.use_rim = False                  # a rim fill closes the shell and hides the silhouette
    sol.material_offset = idx
    sol.material_offset_rim = idx
    return True


def stylize(obj, tones=2, terminator=0.55, smooth=0.03, width=0.004, scene=None):
    """Both, with the defaults this project uses."""
    n = toon_shade(obj, tones=tones, terminator=terminator, smooth=smooth, scene=scene)
    ink_outline(obj, width=width)
    return n

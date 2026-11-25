---
name: tool-trellis2
description: Turn one image into a textured 3D model (GLB) with Microsoft TRELLIS.2. Use for PROPS and set dressing - a lantern, a bridge post, a boat, a rock - from a drawing or photo. Needs an NVIDIA GPU. Not for the characters.
---

# TRELLIS.2 — a picture becomes a prop

MIT (the model too; `nvdiffrast` carries its own terms). Pinned in `vendor/MANIFEST.json`;
fetch with `node tools/vendor.mjs trellis2`. Upstream: https://github.com/microsoft/TRELLIS.2 ·
weights: `microsoft/TRELLIS.2-4B` on Hugging Face (a separate download, several GB).

## Read this before you use it

**It is for props, not for the cast.** This project already has a character, built part by part in
`blender/character/` — folded paper sheets with a real rig, pleats that fold, a sleeve with its own
bone, parts that can be swapped per recipe. TRELLIS.2 returns one fused mesh with baked texture: no
rig, no parts, no edit. It was tried on the cast once and the result could not be posed. Using it on
a character is how you end up back where this project started.

Props are the opposite case. A lantern does not need a rig; it needs to look folded and sit in the
frame, and a drawing of one turning into a mesh in a minute is a real win.

## It needs a GPU, and this container has none

4 cores, no `/dev/dri`. Running it here will fail, slowly. Run it where there is an NVIDIA card:
Mark's own machine if it has one, or a rented GPU — and a rented GPU needs Mark's approval, a cost
estimate and a self-destruct timer first (AGENTS.md rule 1).

## Install (on the GPU machine)

```bash
cd vendor/trellis2 && . ./setup.sh --new-env --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm
```

Long. On a card without flash-attn (V100 and older), install `xformers` and set
`ATTN_BACKEND=xformers` instead. `. ./setup.sh --help` lists every flag.

## Use

`vendor/trellis2/example.py` is the minimal path: load `Trellis2ImageTo3DPipeline.from_pretrained(
"microsoft/TRELLIS.2-4B")`, run it on one image, export a GLB. `app.py` is a web demo if you want to
try images by hand before committing to one.

## Bringing a prop into this project

1. Generate the GLB on the GPU machine; keep the source image beside it.
2. The GLB exports in `OPAQUE` blend mode, so any transparency is set up by hand afterwards.
3. Import into Blender, then **make it match the paper look** — it will arrive smooth-shaded and
   photographic, which is the wrong world. Flat-shade it, cut the polygon count, and give it the
   project's washi material (`blender/world/paper_materials.py`). A prop that does not read as folded
   paper is worse than no prop.
4. Put it in `library/props/` with its licence and its source image recorded beside it.

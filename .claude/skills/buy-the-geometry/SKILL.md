---
name: buy-the-geometry
description: Turn a bought or AI-generated mesh (Tripo, Meshy, Rodin, Hunyuan3D-Part, or any GLB/FBX/OBJ) into a Paper Cinema character part - on a socket, on a bone, made of washi paper. Use when adding geometry from outside instead of folding it by hand.
---

# Buy the geometry, keep the skeleton

The division of labour that makes outside 3D generation useful here:

| | who does it | why |
|---|---|---|
| **Geometry that does not fold** — hats, masks, helmets, armour plates, weapons, props, buildings | **buy or generate it** | a hat does not bend, so a fused shell is fine. This is where a generation service is worth money |
| **Cloth that must deform** — kimono, hakama, sleeves | **fold it here**, in `part_registry.py` | it has to bend at a joint and hold a crease. A generated version cannot |
| **The skeleton, the poses, the fight, the camera** | **here, always** | 25 bones, 46 pose channels, 72 named poses, CMU retargeting, one canonical timeline every renderer reads. This is the asset. Nobody sells it and no service should own it |

A whole generated CHARACTER is one fused shell whose arms cannot bend — that is why
`rig_trellis.py` was abandoned (`docs/CHARACTER-BLENDER.md`). A generated **part** is a legitimate
fused shell, because it is one rigid thing on one bone.

## Adding one

```python
reg.asset_part('kasa_bought', slot='hat', socket='head_top', bone='head',
               file='assets/models/kasa_hat.glb', height=0.22, material='washi_hat')
```

Then it is a part like any other: a recipe names it, the validator checks it, the rig drives it. No
code in `blender/` changes when a new one arrives.

What `asset_bmesh()` does to it, and why each step is the style and not a compromise:

1. **Imports** GLB, glTF, FBX or OBJ, joins every mesh in the file, bakes world transforms.
2. **Decimates hard** — planar dissolve first (free; merges coplanar faces), then a collapse to
   `target_faces`, default 900. A generated mesh arrives at 30–80k smooth triangles; a folded paper
   part is a few hundred flat ones. **The planes have to be big enough to read as folds.** Measured:
   `kasa_hat.glb` 60,042 faces → 917.
3. **Normalises** — drops it on its own origin, scales to `height` metres, moves it to the socket.
4. **Hands it to `ctx.add()`** — the same call every hand-folded part goes through. So it gets flat
   facets, per-facet tone, cut-paper thickness and the washi material automatically. **A bought mesh
   becomes paper on the way in.**

## Which service

Check current docs before paying; this moved fast in 2026.

- **Meshy** — the most mature API. Rigging and animation retargeting endpoints are documented
  (`POST /openapi/v1/rigging`, max 380k triangles). **Use it for meshes, not for rigging**: its rig
  is its skeleton, and ours is the thing worth keeping.
- **Tripo** — documents part-aware generation and a mesh segmentation endpoint (geometric v1,
  semantic v2 beta). The clearest path to *separate parts* rather than one shell.
- **Hunyuan3D-Part** (Tencent, open, self-host) — P3-SAM segments a whole mesh into parts, X-Part
  regenerates each one complete. Needs a GPU, costs nothing per call.
- **TRELLIS.2** — already vendored (`vendor/MANIFEST.json`). Props only; it has no part output.

## Connecting one

Keys never go in a file (AGENTS.md rule 7). The environment's proxy injects them per host: ask with
`request_credential` for the service's host, the user fills a form, and any code here can then call
the API. `openrouter.ai`, `api.groq.com`, `api.cerebras.ai`, `generativelanguage.googleapis.com`,
`integrate.api.nvidia.com` and `api.runpod.io` are already connected and need no key at all.

A consumer **chat subscription** (Grok, ChatGPT Plus) has no API and cannot be connected to
anything. Only a key with per-call billing can.

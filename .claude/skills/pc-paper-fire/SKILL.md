---
name: pc-paper-fire
description: Build layered cut-paper flames, embers and burn reveals for Paper Cinema Blender scenes.
---

Read pc-shot-production and pc-effects. Use the existing paper shader in blender/world/paper_materials.py. Build depth with opaque folded dark-red outer silhouettes, warm orange mid sheets, narrow ivory cores, and drifting cut-paper embers. Use restrained emission for the core and a warm light on nearby paper; keep the fiber texture and folded edges visible. For a first preview, key layers with offset scale/lean curves at 24 fps, stagger silhouettes across 2–4 frame accents, and use seeded motion evaluated from film time. Add a darker paper edge for readability. Use one clear ignition or reveal cue and let embers/catchlights decay across body holds. Keep source and nearby paper in frame. Compare a dark preview, a moving-camera preview and a still with emission reduced. Check that a monochrome silhouette still reads as fire and highlights retain detail. Start with a lantern or supernatural light source isolated from the episode.

## Where this lives in the repo (checked 27 Nov 2026)

- First isolated preview: `blender/bench/paper_fire_preview.py` (outputs in `output/paper-fire/`). Not in any shot until it
  has been looked at and approved.

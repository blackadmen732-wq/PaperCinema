---
name: pc-animated-camera
description: Stage and verify KUROKO or Blender camera movement on Paper Cinema's final baked motion.
---

Read pc-shot-production and pc-camera. Reuse the existing shot library and tools/camera_check.mjs. Lock a wide diagnostic camera first. Keep actor and prop readable through setup and release. For the moving version, ease aim toward a weighted body/prop target, add lead room as the prop moves, and use a brief accent only at a verified beat. Keep the target visible through action and recovery. Use the same bake and timing for both cameras. Check screen margins, apparent subject size, visibility, orientation continuity and unwanted acceleration. Reference notes: blue edit at 6.55–7.57 s uses darkness and graphics between lit action; two-fighter edit near 8.42 s establishes both subjects before the accent; prop edit near 8.45–9.48 s follows a clear silhouette before the graphic hold. Adapt the staging and contrast to original shots.

## Where this lives in the repo (checked 27 Nov 2026)

- Scoring cameras on the same flight: `tools/camera_bench.py` (in frame, 9-ray visibility vs the set, readable size, turn
  jerk, lead room; locked / naive / chase / operator) + `blender/bench/camera_bench_render.py`. KUROKO is not in the bench
  yet: add it as a fifth operator before trusting a KUROKO shot on these numbers.
- Locked vs eased tracking on one bake: `blender/bench/toss_bench.py` (`--cam locked|tracking`).

---
name: pc-motion-import
description: Retarget video motion or RGB MoCap exports into Paper Cinema without replacing its skeleton or tracker.
---

Run pc-shot-production and use paper-cinema-skeleton-animation for the socket contract. Keep tools/mocap.py as the current video estimator/solver and tools/mocap_cmu.py for ASF/AMC. Add RGB MoCap as a separate input path. Start with one real Generic/Blender BVH export from https://github.com/toyxyz/toyxyz_RGBMocap and use Blender's importer to evaluate joint transforms. Record frame time, export options, and whether a rest sample is explicitly present. Map axes and scale once. Resolve left/right by names, verify with an asymmetric pose, and feed normalized landmarks into the shared solve/post stage or explicitly bake a mapped Action. Preserve prop contacts as authored animation. Never average the two captures across contact. Compare the two providers on the same cleared walk or turn for planted-foot drift, root displacement, hand slip and joint continuity. Reject missing core joints with a useful error. A synthetic BVH verifies plumbing; a real export verifies compatibility.

## Status in the repo (checked 27 Nov 2026)

- RGB MoCap read at commit a97c8c1 (MIT). Its Generic BVH (`mocap/source_bvh.py` `write_bvh`): 52 joints, a per-joint Euler
  order chosen to avoid singularities, `Frame Time` = 1/fps, an optional leading T-pose (`prepend_tpose`) that is NOT marked
  inside the BVH (so the export options must be recorded with the file).
- NO real export fixture yet: the repo ships no sample BVH and the app is a Windows GPU tool. Do not call the adapter working
  until a real Generic export has been imported and checked frame by frame.

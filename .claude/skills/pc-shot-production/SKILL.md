---
name: pc-shot-production
description: Turn Paper Cinema references into original baked Blender shots with a shared rig, camera, paper effects and synchronized sound.
---

Read AGENTS.md and the five connected skills: paper-cinema-skeleton-animation, pc-motion-import, pc-animated-camera, pc-paper-fire, and pc-foley. Use pc-measure for evidence. Start with one short shot.

1. List the reference and its intended lesson. Inspect at native rate and use a 40 Hz review grid if useful. Repeated samples are not new source frames. Annotate original timestamps for anticipation, acceleration, contact, hold, camera cut and recovery. Treat scene cuts and brightness peaks as candidates for inspection, not measured contacts.
2. Drive the existing skeleton and verify named sockets before clothing. Use one bake for bare/staged variants. Record release, catch, landing or reaction on the evaluated rig.
3. Put the events, camera, fire and sound on the same presentation clock. Preserve source time and body time separately. A held body pose can coexist with moving embers, a camera move and a decaying sound tail. Apply the body-to-film mapping once.
4. Export a locked and a moving camera preview from the same animation. Inspect frames around events, then watch at delivery speed. Verify an isolated render matches the sequential bake.
5. For folklore, use an attributed source and label the original interpretation. For an original foxfire reveal, let a small distant light establish direction, track the actor's eyeline, then reveal layered paper flame behind a screen. Use quiet ambience, a paper flutter and a low accent at the reveal. The source motif is kitsunebi; the scene and timing are original.

## Where this lives in the repo (checked 27 Nov 2026)

- One bake for every render: `blender/production_bake.py` (stamped `output/<film>.bake.json`; `film_modular.py --bake-only`,
  `--mannequin` for the bare variant). Events from the final bake: `tools/bake_events.py` -> `output/<film>.bake-events.json`
  (contact sub-frame, film time; read by `engine/sound.mjs --events` and the slash).
- Delivery checks: `tools/av_sync_check.py` (audio vs the contact frame), `film_modular.py --probe` (skinned vs rigid parts).
- Proven production shots: `film/kojiro-draw.json`, `film/kojiro-exchange.json`. Benchmarks (isolated): `blender/bench/toss_bench.py`,
  `tools/camera_bench.py`, `blender/bench/paper_fire_preview.py`.

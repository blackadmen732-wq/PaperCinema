---
name: pc-foley
description: Select, clear, spot, and verify Paper Cinema footfalls, entrances, paper movement, blade Foley, ambience and voice.
---

Read pc-shot-production. Inspect assets/sfx/credits.json and reuse existing material-specific and ambience samples. Start with steps-in, steps-out, wood-creak, petal-rustle, steel-scrape, draw-shing, whoosh-a/b/c, clash-light, clash-steel, and sea-bed. Use engine/sound.mjs, the pinned Earshot bank and tools/bake_events.py. Use Kokoro scratch voice through tools/voice.py, and keep dialogue, effects and ambience as distinct tracks during review.

For gaps, search https://freesound.org/ for exact surface/prop terms and https://sonniss.com/gameaudiogdc for alternatives. Check the specific asset's terms and record source, author, license and edits in credits before importing. Route footsteps to planted contact and the right surface; put the draw scrape on visible motion and the swing whoosh apex on speed. Place the dry contact transient at the final baked event once. Build energy with separate material and decay layers. Keep hold duration out of the tail timing. Export muted and mixed variants; use tools/av_sync_check.py and review at normal speed. Target one output frame or less of offset, and inspect the actual mixed wave around the event.

## Where this lives in the repo (checked 27 Nov 2026)

- Every sample named above is in `assets/sfx/` (checked). The `earshot` command is NOT installed in this environment; its
  cached renders in `assets/sfx/earshot/` are used as files.
- The four-layer contact recipe (scrape, apex whoosh, dry transient, material tail; each trimmed to its onset, one trigger):
  `tools/bake_events.py`. Measured on kojiro-exchange: transient +4.9 ms from the bake contact (transient-only stem).

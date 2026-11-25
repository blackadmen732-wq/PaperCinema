# What Paper Cinema needs, end to end

Every stage a finished Short passes through, what we have, what is missing, and what it costs.
Written 2026-11-25 against the repo as it stands. Status is measured, not assumed.

**Legend** — ✅ have and working · ⚠️ have but weak · ❌ missing · 💲 costs money · 🖥️ needs hardware we lack

---

## The machine we are on

| | |
|---|---|
| CPU | Intel Xeon 2.10 GHz, **4 cores** |
| GPU | **none** — no `/dev/dri`, no `nvidia-smi` |
| Blender | 4.5.16 LTS at `/opt/blender-dl/blender-4.5.16-linux-x64/blender` |
| Free GPU | Kaggle 2x T4 — TRELLIS works, Blender render cancels (`docs/KAGGLE-RENDER.md`) |

This one table explains most of what follows. We are rendering films on a 4-core CPU with no
graphics card. It is not a software problem and no coding assistant fixes it.

---

## 1. Story and shot plan ✅

`film/*.json` is the whole film as data: cast, performances, camera, sounds, clashes, voice.
15 films exist. `docs/TIMELINE-FORMAT.md` is the reference, `engine/validate.mjs` the checker.

**Missing: nothing.**

## 2. Character geometry ✅ / ⚠️

- ✅ Modular part factory: 32 parts across 15–17 slots, pose-sweep validated (ronin 427/427,
  warrior 856/856), 36,864 combinations. `docs/CHARACTER-FACTORY.md`.
- ⚠️ TRELLIS meshes (`assets/models/*.glb`, 7 of them) are **one solid piece**. The arms are
  sculpted into the robe, so they cannot be posed. Good for a standing hero shot, useless for a duel.

**Missing:** nothing we must buy. The factory already builds posable characters.

## 3. Character rig ⚠️ → fixable free

- ⚠️ Blender side: a hand-built 5-bone spine chain (`trellis_shot.py`). Auto-weighting fails:
  *"Bone Heat Weighting: failed to find solution for one or more bones"*.
- ✅ three.js side: a proper articulated skeleton with 2-bone analytic IK (`engine/figure.js`).

**Missing: Rigify.** Verified present in this Blender install and it enables cleanly. Free, ships
with Blender, never used. It gives real IK, foot roll and pole targets instead of a bone chain.
**Also present and unused:** `io_anim_bvh` (motion import), `io_scene_fbx`, `node_wrangler`.

**Action: free. Nothing to buy.**

## 4. Motion ⚠️ → the biggest quality gap

- ✅ Anime timing layer: follow-through lag, cubic-bezier snap, damped-spring settle, hang time.
- ✅ `engine/footlock.js` exists (foot locking).
- ⚠️ **The poses themselves are joint angles typed by hand into JSON.** This is why movement reads
  stiff. No amount of timing polish fixes a hand-typed pose.

**Missing: real motion data.**

| Source | Licence | Usable |
|---|---|---|
| **CMU Graphics Lab Motion Capture Database** | *"free for all uses... you may include this data in commercially-sold products"* | ✅ yes, confirmed |
| Mixamo | free, but needs an Adobe login | ⚠️ you would have to download; I cannot log in |
| AMASS | research only | ❌ fails rule 6 |
| Rokoko suit | 💲 hardware | ❌ |

**Action: free (CMU). Retargeting it to our skeleton is real work, not a download.**

## 5. Look and shading ❌ → fixable free

- ✅ `PC_Washi_Master` paper material, Poly Haven CC0 texture layer.
- ❌ **No toon shader. No outlines.** This is the single clearest reason renders look "flat" —
  we are lighting paper realistically instead of stylising it.

**Missing:** inverted-hull outlines and a two-tone ramp shader. Both are standard, both are free,
both are code I write. **Goo Engine** (DillonGoo's anime Blender fork) is free but EEVEE-focused,
so it does little for us until there is a GPU.

**Action: free.**

## 6. Sets ✅

5 sets, 28 kit pieces, Poly Haven CC0 textures. `docs/SETS.md`.
Free expansion available: ambientCG (CC0), Sketchfab CC0 filter, Poly Haven.

**Missing: nothing blocking.**

## 7. Camera ✅

KUROKO rigs (frame/orbit/track/face/anchor/blade/slide/compose), 12 Blender camera moves, and
`tools/camera_check.mjs` which measures every frame and rejects bad shots before a render.

**Missing: nothing.**

## 8. Sound effects ✅

38 clips, freesound integration, automatic cues driven by blade contact detection at 240 Hz,
`earshot` distance cues, ducking. `engine/sound.mjs`.

**Missing: nothing blocking.** More library depth is nice, not required.

## 9. Voice ✅ 💲

ElevenLabs is **connected and live** — verified. `film/*.json` already has a `voice` block and
`sound.mjs` ducks under it. This is a real asset we have barely used.

💲 **Generation spends your ElevenLabs credits.** Not free.

## 10. Music ❌

**Nothing at all.** No music system, no tracks, no bed. A sword-duel Short with no score is
noticeably empty.

| Option | Cost |
|---|---|
| CC0 / public-domain libraries | free |
| ElevenLabs music | 💲 your credits |
| Epidemic Sound, Artlist | 💲 subscription |

**Action: free route exists.**

## 11. Render compute 🖥️ — the real blocker

| Path | State |
|---|---|
| This container, Cycles CPU | works, ~17 s/frame at 480x854 — a 10 s Short is ~70 min |
| This container, EEVEE | **slower and worse** without a GPU (`docs/RENDER-ENGINE.md`) |
| Kaggle free T4 | TRELLIS ✅, Blender render ❌ cancels |
| Your own computer | **unknown — does it have a graphics card?** |
| Paid GPU (RunPod) | 💲 ~$0.20/hr, $3.83 balance left |

**This is the one gap money or hardware solves and software does not.**

## 12. Assembly and delivery ✅

Frame-by-frame headless Chromium render → ffmpeg → mux with the mixed audio. Produces real
vertical Shorts: `output/dash-test-final.mp4` is 720x1280, 8 s, with sound.

**Missing: nothing.**

## 13. Quality control ✅

`tools/audit.mjs` (studio standard gate), `engine/validate.mjs`, `tools/camera_check.mjs`,
graphify knowledge graph. Stronger than most solo setups.

**Missing: nothing.**

---

## Summary

**Free, available now, not yet used:**

1. **Rigify** — real rig with IK (in Blender, verified)
2. **Toon shader + inverted-hull outlines** — the flat look fix
3. **CMU mocap** — commercial-safe motion data
4. **BVH / FBX import** — in Blender, verified
5. **CC0 music**

**Needs your decision:**

| | What | Cost |
|---|---|---|
| 💲 | ElevenLabs voice and music | your credits |
| 💲 | Paid GPU render (RunPod) | ~$0.20/hr, $3.83 left |
| 🖥️ | **Your own computer, if it has a graphics card** | free, and the best option |

**Not needed:** another AI model. We have 403 through OmniRoute plus free NVIDIA, Cerebras and
Groq. Models are not the constraint at any stage above.

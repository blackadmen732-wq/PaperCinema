---
name: pc-animation
description: Motion for Paper Cinema - the 46-channel pose system, the 26-move library, capture from video and CMU, cleaning the tremble out of it, and how a cinematic fight is actually built. Use for anything about how the cast moves or fights.
---

# Motion

## Motion is data, not animation files

**71 named poses** (`library/poses.json`), each **46 channels**. **26 moves** (`library/moves.json`).
A fight is a list: `[kamae, kesa-giri, block, kiri-age, hit]`. Between keys the engine does the work
— monotone-cubic interpolation, eases, **overlap/lag** so the hand arrives after the shoulder, a
**damped-spring settle** that overshoots and returns, parabolic arcs for jumps. That is why it reads
as animation and not as pose-popping.

**Geometry never affects this.** Swap every part and not one frame of motion changes.

All seven real cuts already exist: `kesa-giri`, `lunge-shomen`/`kiri-oroshi`, `spin-cut`,
`rising-cut`, `yoko-giri`, `tsuki`/`rapid-thrusts`, `nukitsuke`/`nuki-uchi`. Plus `step-in`,
`jump-back`, `dodge-left`, `parry-high`, `bind`, `stagger-back`, `sword-engage`, `sword-press`.

**The gap is that films barely use them.** Counted: `ganryujima` **0 moves / 29 raw poses**,
`kuroko-duel` 9/28. A film built from raw poses gets no benefit from any improvement to any move.
Converting a fight to a move list is the highest-value animation work available.

## Capture

```bash
python3 tools/mocap.py clip.mp4 --out library/mocap/<name>.json --fps 24 [--start 1.2 --end 3.4]
python3 tools/mocap_cmu.py assets/mocap/cmu/02_07.amc --out library/mocap/<name>.json [--smooth 0.25]
```

Video → MediaPipe Pose (Apache-2.0, CPU, no GPU). CMU ASF/AMC → forward kinematics → the same solver.
Both end at the same 46 channels, so a film never cares which.

**Licences decide this, and most of the field is closed to commercial work.** SMPL and AMASS are
non-commercial, so GVHMR, WHAM, 4D-Humans, MoMask and anything trained on HumanML3D are
experiment-only. Clean: **CMU** (*"may include this data in commercially-sold products"*),
**MediaPipe** (Apache-2.0), **Mixamo** (free, royalty-free, commercial explicit — and not yet wired
up), and **NVIDIA Kimodo on a SOMA checkpoint** (NVIDIA Open Model; the SMPL-X checkpoint is R&D-only).
Full table: `docs/ANIMATION-SOURCES.md`.

## Taking the tremble out — measured, not guessed

Start from `node tools/jitter.mjs <film>`. Baseline: hand-keyed `ganryujima` is **8%**.

Three real bugs, each worth knowing because each took a measurement to find:

1. **Decimating without filtering.** 120 Hz CMU → 24 fps by taking every 5th frame and binning the
   rest. Textbook aliasing: clean lab data arrived trembling. Now every source frame is solved,
   low-passed (Hann, ~2 output frames, edge-replicated), then sampled on the same instants.
2. **The finishing pass was never called.** `mocap.post()` — small-window Savitzky-Golay, then joint
   limits — ran on the video path and never on the CMU path. Worst channel 52% → 31%.
   Together: sword-mocap **31% → 14%**, 19 shaky joints → 0.
3. **The knee.** Knee angle comes from `acos()`, whose slope runs to infinity as the leg straightens;
   29% of samples sat above 0.97 extension. Soft IK alone made it *worse* (calmer knees, wandering
   feet). Soft IK **plus a limb stretch** that absorbs the shortfall: worst joint 35% → 28%, no feet
   in the list.

Dead ends, so nobody re-runs them: the overlap layer correlates with tremble but is not causal
(8% → 7% when switched on for the clean film); smoothing the `drag` time-warp is correct and changed
nothing. What remains is **key density** — capture carries 24 keys a second and hand-keying carries
one, so capture reproduces noise hand-keying never had. The lever is `--smooth` (0.25 default:
a point better than 0.15 at **no** cost in peak blade speed).

## A cinematic fight

Six beats per attack, with frame counts, at 24 fps:

| beat | frames | camera |
|---|---|---|
| ready | 12–24 | wide or medium: show the distance |
| wind-up | 6–10 | slow push-in, the glow brightens |
| **slash** | **3–5** | blade-follow or whip pan |
| **hit-stop** | **3–6 frozen** | flash, paper burst, small shake |
| follow-through | 8–12 | camera travels past |
| reaction | 12–24 | face-snap to whoever matters now |

**Cinematic is three timelines landing on ONE frame**: the blade, the defender's reaction, the camera.
`engine/combat.js` already finds that frame — both tips at 240 Hz — and flags `reaction-late` past 3
frames, `out-of-reach`, `sub-frame-tunnel`, `tip-teleport`.

KUROKO is the camera: rigs `frame`, `orbit`, `track`, `face`, `anchor`, **`blade`**; feels `locked`,
`dolly`, `crane`, `handheld`, `torpedo`. **`ganryujima` uses 0 rigs and 6 hand-typed cameras.**

## The thing to hold on to

**Capture and anime are opposites, and this project needs both.** Capture gives weight, balance and
recovery. Anime gives a three-frame slash and a six-frame freeze, which no human body does. Use
capture for the movement *between* the cuts and hand-keyed extremes for the cuts themselves. Watch
list: `docs/WATCH-LIST.md`.

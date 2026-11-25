# Cinematic fight research — what exists, what to take, what to build

Researched 25 Nov against a production blueprint Mark supplied. Every licence read on the owner's
page. The blueprint is a good checklist; this file is the part of it that is **true of this repo**.

## 1. The blueprint's "missing features" — most of them are already here

It lists 17 things the project supposedly needs. Checked by grep, not by memory:

| blueprint says you need | in this repo |
|---|---|
| Foot locking | **yes** — `engine/figure.js`, `motion.js`, checked by `validate.mjs` |
| Weapon grip correction | **yes** — `gripHand()` in `figure.js` |
| Focus tracking / DoF | **yes** — `focus_m` and `aperture` ride the canonical timeline |
| Damage persistence | **yes** — SHIMI (`engine/shimi.py`), `tools/paper_damage.mjs` |
| Aspect-ratio safety | **yes** — vertical handling in `kuroko.js`, `motion.js`, `new-film.mjs` |
| Contact / impact events | **yes** — `engine/combat.js` samples both blade tips at 240 Hz |
| Speed ramps | **yes** — `ramps` in `motion.js`, validated |
| Fight-axis (180° rule) | **yes** — scored by `tools/audit.mjs`, and `tools/camera_check.mjs` rejects shots |
| Camera obstruction detection | **NO** — the only genuine gap on the list |

So the blueprint's gap analysis is mostly wrong about this project, in the project's favour. What it
gets right is the central claim, which is the same conclusion everything else reached today:
**the fight, the camera and the effects must be designed together**, and here they are authored
separately, so they do not land on the same frame.

## 2. The Unreal recommendation

The blueprint is Unreal-shaped: Sequencer, Chaos Destruction, Niagara, Motion Warping, Control Rig
FBIK, Cine Camera. All of that is real and good. Taking it would mean rebuilding this project,
because the thing that makes this pipeline work — **every frame is a pure function of time**, so
frames render in any order on any machine — is not how a realtime engine thinks.

Every capability it names has a counterpart here already: Sequencer → the canonical timeline;
Cine Camera + rigs → KUROKO (`frame`, `orbit`, `track`, `face`, `anchor`, `blade` rigs; `locked`,
`dolly`, `crane`, `handheld`, `torpedo` feels); camera shake → `shake()`/`traumaAt()` in `fx.js`;
Niagara → `fx.js` + `groundfx.js`; Chaos → SHIMI/KIZU. Unreal is a decision to make later, from
strength, not a fix for anything broken now.

## 3. NVIDIA's motion system — real, Apache-2.0, and expensive

**[NVlabs/ProtoMotions](https://github.com/NVlabs/ProtoMotions)** is the thing worth knowing about.
GPU-accelerated framework for training physically simulated humans. Implements **AMP** (Adversarial
Motion Priors), **ASE**, **MaskedMimic** and PPO. Physics backends: Newton, IsaacGym, IsaacLab,
Genesis.

- **Licence: ProtoMotions3 source is Apache-2.0.** Clean.
- **But NVIDIA's pretrained models are under the NVIDIA Open Model License**, per model card — read
  each one before shipping anything it produced.
- It needs a real GPU and real training time. It is a research framework, not a plugin.

What it would buy: motion that is *physically* plausible — weight, balance, momentum, recovery —
learned from reference clips, rather than interpolated between poses. Trained on **CMU** data
(commercially clean, already in this repo) it would stay licence-safe.

Honest verdict: this is the single most powerful thing on the list and the furthest from useful
today. It is weeks of GPU work, and this project does not yet put the 26 moves it already has into
its flagship film. Park it; revisit when a GPU is rented anyway.

## 4. The paper slash — six layers, and which ones exist

A slash that reads is six things on one frame, not one effect:

| layer | status here |
|---|---|
| 1. Weapon arc | **yes** — the sword is tracked at 240 Hz, sub-frame sampled into the timeline |
| 2. **Paper ribbon trail** (a thin strip of paper swept through space) | **NO — the real gap** |
| 3. Ink accent | **yes** — `ink-impact` in `fx.js` |
| 4. Contact flash | **yes** — `flash`, `ca-flash`, `glint` |
| 5. **Paper fragments** flying off | **NO** — `groundfx.js` does dust and ground marks, not torn paper |
| 6. Surface damage | **yes** — SHIMI pigment diffusion, KIZU cuts |

So four of six exist. The two that do not are the two that would make it *paper* rather than a
generic anime slash, and both are 3D mesh work, not post effects.

**The ribbon must not be a neon streak.** It is a thin strip of washi with thickness, a taper, and
a tear at its trailing edge, lit by the scene. Prior art, all Blender geometry nodes:

| tool | what | licence |
|---|---|---|
| [jva15/Blender-TrailEffects](https://github.com/jva15/Blender-TrailEffects) | armature-based trail, method from Pierrick Picaut | public repo, licence not stated — **check before use** |
| SimpleTrail (itch.io) | one `.py`, geometry-nodes trail, free | licence not stated |
| Sword Trail (Artistic Asset) | free, Blender 5.0+, bows the trail to follow a curved blade | free, terms unstated |
| Mesh Trail Generator (BlendKit) | node group for slashes | "royalty free", not an OSI licence |

None is clearly licensed for commercial use, so **read the method, write our own**. The method is
not secret: sample the blade's two tip positions over the last N frames, skin a ribbon between them,
taper the width along its length, fade the oldest end. This project already has the hard half —
the blade is sampled at 240 Hz and stored in the timeline, so the ribbon is a geometry-nodes job
over data that already exists.

No "paper tear shader" exists to copy. That one is ours to make, and SHIMI is the start of it.

## 5. What to build, in order

1. **Put the fight through the systems it already has.** `ganryujima` uses zero moves and zero
   KUROKO rigs. Nothing below matters until that is fixed.
2. **The paper ribbon trail** — geometry nodes over the blade path already in the timeline.
3. **Paper fragments on contact** — the contact event already fires; give it torn-washi shards.
4. **Camera obstruction detection** — the one genuine gap in the blueprint's list, and cheap: cast a
   ray from the camera to each subject per frame, fail the shot when a contact frame is hidden.
5. **ProtoMotions**, if and when there is a GPU.

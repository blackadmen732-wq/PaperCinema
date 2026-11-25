# Tools worth having

Found 2026-11-25. Filtered on the two things that actually decide it for this project:

1. **Does it run without a GPU?** This container has none (4 CPU cores, no `/dev/dri`).
2. **Can we sell what it makes?** AGENTS.md rule 6: commercial-safe licences only.

A tool that fails (2) is listed as a warning, not an option.

---

## A licence note that saves worry

**A GPL Blender add-on does not make your films GPL.** Blender itself is GPL; the images it renders
are yours. The licence covers the add-on's own code, which matters only if we redistribute it.
So GPL add-ons below are safe to use and safe to sell the output of.

**Model weights are different.** A CC-BY-NC weight file means you may not sell what it generates.
That is why two well-known music models are in the "avoid" list.

---

## Anime look — Blender

| Tool | Licence | Engine | Why it matters here |
|---|---|---|---|
| **CyclesTooner** | GPL-3.0 | **Cycles** | The best fit: Cycles-first, and Cycles is what wins on this machine (`docs/RENDER-ENGINE.md`). Toon shading, outlines, volumetric light. Blender 4.5 LTS+ — our version. |
| **AniBlend** | GPL-3.0 | EEVEE **and** Cycles | Multi-light cel with per-light shadow tints, screentone, inverted-hull ink outlines, pencil strokes. Much more complete than what I hand-built in `blender/world/toon.py`. |
| **Anime-Tools** (AtomaHuro) | see repo | EEVEE Next | Built for Blender 4.5 LTS. Notable for **Step Keys — hold on 2s/3s/4s**, which is anime timing as a button. |
| **Malt** | MIT | own | A whole NPR rendering framework. Heavier; only if the add-ons are not enough. |
| **awesome-blender** | index | — | The catalogue to search before building anything else. |

**Honest note:** I wrote `blender/world/toon.py` by hand today. CyclesTooner and AniBlend both do it
better and have screentone, which we do not. Rule 00 says use what exists — worth swapping to.

## Motion from video

| Tool | Licence | Needs | Why |
|---|---|---|---|
| **mixamo-llm-mocap** | MIT | **~8 GB VRAM** | Any locked-camera video to clean animation. **Two performers fighting in one pass.** Badged "operable by AI agents". Its own QA gates check foot skate, pops and limb angles — the same things `tools/footslide.mjs` checks. |
| **RGB MoCap** (toyxyz) | free | GPU | One ordinary video to FBX, foot locks, multiple people. |
| **GVHMR** | research | GPU | The estimator inside mixamo-llm-mocap. |
| **`tools/mocap.py`** (ours) | — | **CPU** | Already here. MediaPipe. Lower quality than GVHMR but it runs on this machine today. |

## Music — the project has none at all

| Tool | Licence | Sell the output? | VRAM |
|---|---|---|---|
| **ACE-Step 1.5** | **MIT**, code *and* weights | **Yes** | under 4 GB, and it supports CPU |
| DiffRhythm | Apache 2.0 | Yes | ~8 GB |
| ⚠️ MusicGen | weights CC-BY-NC | **No** | — |
| ⚠️ YuE2 | weights CC-BY-NC | **No** by default | 24 GB |

**ACE-Step is the pick:** MIT on the weights too, which is rare, and the only one that claims CPU
support. 10 seconds to 10 minutes, instrumental or with vocals.

## Sound effects, free and commercial-safe

Openverse, BigSoundBank and SoundBible are all reachable as data providers from this session, so
searching them needs no account. `assets/sfx/CREDITS.md` records what we use.

## Running AI without a GPU

**awesome-ai-cpu** — a curated list of open-source AI that runs on CPU. Directly aimed at our
constraint, and worth checking first whenever a tool seems to need hardware we do not have.

---

## What this list says, taken together

Of everything above, **only the toon add-ons, ACE-Step and our own `mocap.py` run on this machine.**
Every video-to-motion tool wants about 8 GB of VRAM.

That is not a reason to buy any of them. It is the same wall as Kaggle and EEVEE: a rented RTX 3090
has 24 GB at 7-18 cents an hour, and the free Kaggle T4 has 16 GB. The tools are free; the hardware
is the only cost, and most of it is already paid for.

---

## Installed, 2026-11-25

| What | Where | State |
|---|---|---|
| **Blender 5.2.5 LTS** | `/opt/blender-dl/blender-5.2.5-linux-x64/blender` | installed beside 4.5.16, both usable |
| **AniBlend 1.2.0** | `~/.config/blender/5.2/extensions/user_default/aniblend` | enabled; `bpy.ops.anime.*` |
| **CyclesTooner 1.29.0** | `~/.config/blender/5.2/extensions/user_default/cycles_tooner` | enabled; `bpy.ops.object.add_toon_outline` |
| Anime-Tools | — | **not installed.** No release zip, and this session's proxy blocks third-party GitHub source archives. Download it by hand if the Step Keys feature is wanted. |

`blender/character/trellis_shot.py --aniblend 1` renders with AniBlend instead of our own
`blender/world/toon.py`, so the two can be compared on the same frame at any time.

### The comparison, and the verdict

`output/engine-ab/toon2.png` (ours) against `output/engine-ab/aniblend.png` (AniBlend), same model,
same lighting, same engine, same samples.

**AniBlend wins on the outline, clearly.** It draws a crisp black ink line round the whole
silhouette and along every crease. Ours tilts a shell outward and hopes; theirs reads as drawn.
They also have screentone, per-light shadow tints and a hand-tremor option, none of which we have.

Keep `blender/world/toon.py` for one reason only: it runs on Blender 4.5, and the three.js engine
that renders the films is not Blender at all. For Blender stills and Blender films, use AniBlend.

### Blender 5.x broke our code, and it is worth knowing why

Blender 4.4 introduced slotted actions and 5.x removed the legacy `Action.fcurves` shortcut, so
every script that walked an action's curves raised `AttributeError: 'Action' object has no attribute
'fcurves'`. `blender/bl_compat.py` now holds `fcurves_of()` and `object_fcurves()`, which work on
both versions, and `trellis_shot.py`, `kit.py` and `rig_trellis.py` go through them.

---

## 3D OS by Scenario — nine Blender expert skills, installed 2026-11-25

`scenario-labs/skills` (MIT, ~3.7k stars) is 173 agent skills in six departments. The generation
skills call a paid service, but **the expert-tool skills drive Blender on this machine and need no
account** — checked: nothing under `skills/dcc/blender/` references an API key or the hosted server.
Their test suites pass headless on Blender 5.2.1, which is why 5.2.5 was the version installed here.

Installed into `.claude/skills/` (1.5 MB, 52 files, MIT licence kept beside them):

| Skill | The gap it answers |
|---|---|
| `scenario-blender-rigging` | Its description names **"Bone Heat Weighting failed"** and **"clothes that do not follow"** — the two errors that actually blocked us. Rigify fitting, weight fixes, IK/FK, twist bones. Ships `bx_rig.py`, tested on 5.2.1 headless. |
| `scenario-blender-animation` | Stepped blocking to spline, timing and spacing, arcs, overlap — anime timing by name. Also slotted actions, the 5.x API that broke our scripts. |
| `scenario-blender-lighting-rendering` | "flat or muddy renders", "subject not standing out", toon/NPR looks, AgX. Our toon render was too dark because the scene was lit for a realistic shader; this is that problem's manual. |
| `scenario-blender-grease-pencil` | Drawn 2D effects inside a 3D scene. This is how anime actually makes impact frames and speed lines, and it is the right way to build sand and splashes. |
| `scenario-blender-geometry-nodes` | Procedural scattering and simulation zones: the world builder and ground reactions. |
| `scenario-blender-previs-storyboard` | Beats to shot list, 180-degree rule, screen direction, shot sizes. Our camera evaluator checks these; this plans them. |
| `scenario-blender-hard-surface` | Booleans, bevels, weighted normals for set pieces. |
| `scenario-blender-export` | FBX/glTF scale, rotation, leaf bones, re-import checks. |
| `scenario-blender-expert` | The lead skill the others expect: execution channel, review loop, 5.x API changes. |

**Why this matters more than the add-ons.** AniBlend and CyclesTooner are buttons. These are written
for an agent to drive Blender through Python, headless, with their own test suites — which is exactly
how this project renders. Six skills here cover problems this repo has hit and solved badly or not at
all, and one of them names our exact error message.

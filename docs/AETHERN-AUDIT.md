# Aethern audit: what Paper Cinema can share, what it should keep

28 Nov 2026. Branch `claude/shared-core`. Everything below was measured or read in this repository;
nothing is projected.

## The short version

- Of 67 catalogued systems (66 before this branch), **3 are generic enough to share today** and now live in
  `packages/aethern/`: the free model router (`AIROUTER`), the free worker (`WORKER`) and the resume
  state of the Render Supervisor (`RENDERSUP`). Four uncatalogued tools moved with them: the
  systems-map builder, the skills-map builder, the vendor pinner and the promise ledger, plus the
  canvas stub that lets the rig be measured in Node.
- **41 systems are Paper Cinema itself** (film format, engine, rig, Blender, look) and stay.
- **12 are generic in idea but tied to our rig or our look**; they are listed below with the work
  that would free them. Four of those belong to the Sonic task now in progress.
- Paper Cinema runs on the core with **byte-identical output**: `systems.json` (before the new row),
  `SKILLS.md`, the promise ledger run, `vendor --check` and `--list`, and the render plan's shot
  hashes all match the old code exactly.
- The core's main saving is **reading less**: an agent asking about one system reads about 120 tokens
  instead of about 7,600. Against a careful agent that greps instead of reading, the saving is
  smaller (about 210 → 120 tokens) but the answer also carries line counts and links grep cannot.

## What moved, and what changed on the way

| was | now | changed |
|---|---|---|
| `tools/ai.py` | `aethern/router.py` | Models, order, system prompt and paths come from `aethern.json`. **New:** a 7-day result cache for identical prompts (`--fresh` skips it); cached answers are logged and counted by `budget`. |
| `tools/worker.py` | `aethern/worker.py` | Project line, protected files and log folder from config. **New:** a `map` tool, so a worker orients in one call. **Safer:** also refuses `find -delete`, `git clean`, `git reset --hard`, `git checkout -- ` and `git push`, which the old deny list let through. A failed vision call no longer crashes the loop. |
| `tools/build_systems.py` | `aethern/catalog.py` | The table markers and the connections are config. **New:** `map show / find / deps / owner / list / ask`. |
| `tools/build_skills.py` | `aethern/skillmap.py` | Groups were Python lambdas; now data (`prefix`, `suffix`, `names`). |
| `tools/vendor.mjs` | `js/vendor.mjs` | Root, manifest, command name are parameters. |
| `tools/promises.mjs` (ledger part) | `js/ledger.mjs` | The two film checks (`--check-limits`, `--check-character`) stay in Paper Cinema. |
| `tools/headless_dom.mjs` | `js/dom-stub.mjs` | Unchanged. |
| `tools/render_supervisor.mjs` (state part) | `js/state.mjs` | `hashOf`, `loadState`, `isFresh`, `stateWriter`. The writer now writes a temp file and renames it, so a crash mid-save keeps the old state. |
| (nothing) | `aethern/index.py` | **New:** `changed`, `impact`, `snapshot`. |
| (nothing) | `aethern/memory.py` | **New:** `mem add / get / topics / drop`, in `.aethern/memory.jsonl`. |

Every old command still works with the same arguments; the old files are now thin wrappers.

## Verdict for every catalogued system

| system | verdict | why |
|---|---|---|
| `STYLE` Lantern Origami | keep | Paper Cinema's taste, story and rules. Not code. |
| `STRIKE` Strike Grammar | keep | Paper Cinema's taste, story and rules. Not code. |
| `FILM` Film file | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `CHECK` Checker | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `MAKE` One-command pipeline | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `FILMONE` One-command film (Blender + sound) | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `KAGGLEFARM` Free Kaggle Blender farm | extract later | Render-job-as-data and pod control are generic. GPU costs money, so it stays behind the ask-first rule. |
| `NEWFILM` New-film scaffolder | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `ENGINE` Preview engine | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `WORLD` Sets + paper | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `SKELETON` Skeleton + balance | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `MOTION` Motion system | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `MOVES` Fight moves | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `FOOTLOCK` Planted feet + weight | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `MOCAP` Motion capture from video | keep | MediaPipe smoothing is generic, but its output is our rig's channels. |
| `REACT` Reaction layer | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `DRAW` Sword draw | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `KUROKO` KUROKO camera | Cinevora later | The frameworks are generic (camera operator, shot scoring, one interchange timeline, rule-based QA) but they read Paper Cinema joint and rig names. Decoupling those names is real work and was not done. |
| `KEYCAM` Keyframe camera | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `LIBRARY` Library | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `RENDER` Renderer | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `SOUND` Sound pipeline | Sonic (other thread) | Owned by the Sonic sound-tagging task right now. Planned as the core's Sonic module once that lands. |
| `CLASH` Blade contact + hit-stop | Sonic (other thread) | Owned by the Sonic sound-tagging task right now. Planned as the core's Sonic module once that lands. |
| `COMBAT` Combat layer (shared) | keep (Sonic thread editing) | The fight layer of both engines; fight-specific, and the Sonic task is editing it. |
| `AUDIT` Studio audit (automated QA) | Cinevora later | The frameworks are generic (camera operator, shot scoring, one interchange timeline, rule-based QA) but they read Paper Cinema joint and rig names. Decoupling those names is real work and was not done. |
| `STANDARD` Studio standard | keep | Paper Cinema's taste, story and rules. Not code. |
| `GROUNDFX` Ground FX + afterimages | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `CINECAM` Cinematographer camera (motion page) | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `SYNTHSFX` Synthesised sword sounds | Sonic (other thread) | Owned by the Sonic sound-tagging task right now. Planned as the core's Sonic module once that lands. |
| `EARSHOT` Earshot sound bank (existing tool) | Sonic (other thread) | Owned by the Sonic sound-tagging task right now. Planned as the core's Sonic module once that lands. |
| `AIROUTER` Free model router | **extracted** | Generic once the prompt, models and paths moved to config. Now `aethern ai` / `aethern worker`. |
| `WORKER` Free agent worker | **extracted** | Generic once the prompt, models and paths moved to config. Now `aethern ai` / `aethern worker`. |
| `OMNI` OmniRoute gateway | extract later | A 10-line wrapper around an outside gateway; only its key path is Paper Cinema. Not worth moving alone. |
| `BLENDERSKILLS` Blender Skills pack (existing tool) | skip | Third-party skill packs, already pinned outside our code. |
| `VOICE` Voice (spoken lines) | extract later | Kokoro TTS plus an ffmpeg voice chain, cached by a hash of the line: generic. Needs numpy and soundfile, so it goes in as an optional module. |
| `THUMB` Thumbnails | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `PLAYBOOK` Playbook page | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `SHIMI` SHIMI (染み) stain sim | Cinevora later | Paint soaking into paper is a general 2D stain simulation, but it is the studio look. Belongs in a creative (Cinevora) layer, not the agent core. |
| `KIZU` KIZU (傷) wound layer | Cinevora later | Paint soaking into paper is a general 2D stain simulation, but it is the studio look. Belongs in a creative (Cinevora) layer, not the agent core. |
| `LOOKDEV` Lookdev stages | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `BLENDER` Blender (realistic) | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `BWORLD` Blender world set (Ganryūjima) | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `PAPERMAT` Paper materials (Blender) | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `SLASHFX` Slash effects (Blender) | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `SETS` Sets (modular, data-driven, Blender) | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `POLYHAVEN` Poly Haven layer (CC0 photo textures + HDRI ambient) | extract later | A generic CC0 texture/HDRI fetcher with a cache. Only its manifest path is ours. Next candidate. |
| `CHARFACTORY` Modular origami character factory | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `BLENDERFILM` Blender film render (TRELLIS hero) | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `GPU` GPU jobs | extract later | Render-job-as-data and pod control are generic. GPU costs money, so it stays behind the ask-first rule. |
| `MODELS` 3D models | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `ANATOMY` Anatomy (third-party skill) | skip | Third-party skill packs, already pinned outside our code. |
| `STORY` Story bible | keep | Paper Cinema's taste, story and rules. Not code. |
| `SCENE` Scene writing | keep | Paper Cinema's taste, story and rules. Not code. |
| `DIRECTION` Scene direction | keep | Paper Cinema's taste, story and rules. Not code. |
| `RESEARCH` Research | keep | Paper Cinema's taste, story and rules. Not code. |
| `EFFECTS` Effects plan | skip | Plans and records, not code. |
| `FX` FX post-processing (three.js preview) | Cinevora later | A deterministic three.js effect stack any page can import. Generic for three.js, not for agents. |
| `ARCH` Architecture (the six modules) | skip | Plans and records, not code. |
| `TIMELINE` Canonical animation timeline | Cinevora later | The frameworks are generic (camera operator, shot scoring, one interchange timeline, rule-based QA) but they read Paper Cinema joint and rig names. Decoupling those names is real work and was not done. |
| `FIGHTDIR` Fight Director | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `CAMCHECK` Camera evaluator (Camera Director) | Cinevora later | The frameworks are generic (camera operator, shot scoring, one interchange timeline, rule-based QA) but they read Paper Cinema joint and rig names. Decoupling those names is real work and was not done. |
| `DAMAGE` Paper Damage Bridge | keep | The film pipeline itself: film format, engine, rig, motion and renderer. |
| `RENDERSUP` Render Supervisor | **partly extracted** | Its hash-keyed resume state is now `js/state.mjs`. The shot planner and the render commands are Paper Cinema renderers; the cost estimator is generic and is the next piece to move. |
| `UEEXPORT` Unreal export (verified FBX) | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `TOOLSEVAL` Outside-tool evaluation | skip | Plans and records, not code. |
| `TRELLIS2` TRELLIS.2 Kaggle job | keep | Blender scenes, paper materials, characters and models made for this studio. |
| `AETHERN` Aethern shared core | new | This branch. |

## Weaknesses and duplicates found

1. **The free-labour path does not work where Claude Code runs in the cloud.** Every free endpoint
   (Cerebras, Groq, NVIDIA) answers *403, no rule allows this host* from this session's network
   proxy. So `tools/ai.py` and `tools/worker.py` only save Claude usage on your own machine. The
   usage saving that `docs/COST.md` describes has never been measured for cloud sessions, and there
   it is zero.
2. **The map's connections are hand-typed and incomplete.** 27 of 66 systems had no connection at all
   (among them FILMONE, CLASH, VOICE, AIROUTER, WORKER), so "what does this feed?" was unanswerable
   for them. The list also lived inside the builder's code, not in `SYSTEMS.md`. It is now data in
   `aethern.json`; filling the gaps is still to do.
3. **Three separate change-and-resume caches.** The Render Supervisor (hash of frames), the voice
   tool (hash of line settings) and the timeline export (file times) each invented their own. The
   first now uses the shared `state.mjs`; the voice tool is the next to move.
4. **The worker's deny list missed destructive commands** (fixed, see the table above).
5. **The graphify rules in `CLAUDE.md` assume a tool that is not installed in cloud sessions.** Its
   hooks and `graphify query` simply fail there, so agents fall back to reading files.
6. **`docs/COST.md` contained an unchecked line** ("Rule 01: not in excerpt; see AGENTS.md"), a sign it
   was written by a model and not reviewed. Left as is; flagged here.
7. **This repository is public**: it clones without signing in. The new private-repo plan is in
   `packages/aethern/EXPORT.md`; nothing about this repository's visibility was changed.

## Capabilities that are genuinely missing

Checked against everything above, so none of these exists under another name:

1. **Claude's own usage, recorded per task.** `ai.py budget` counts free-model tokens only. The
   token-usage plugin can read one Claude Code session's usage afterwards (this extraction session:
   86.9k output tokens, 21.5M cached input read, about $16 at API prices), but nothing in the repo
   records it per task, so "fewer resources" cannot be tracked over time yet.
2. **Free models reachable from cloud sessions** (a proxy rule, or an OmniRoute gateway the cloud
   session can reach). Until then the offload saving exists only on your machine.
3. **Connections inferred from the code.** Imports between files already say which systems talk to
   which; nothing turns that into the map, so it drifts.
4. **File ownership between agents.** Two tasks are editing this repo at once tonight; the only
   guard is a sentence in a brief. A small claim/lease file would stop two agents editing one file.
5. **A blind side-by-side for human scoring.** The audit measures defects in numbers, but nothing
   presents two renders unlabelled for you to rate, which quality claims need.

## Benchmarks (measured 28 Nov on this repository, 856 files)

Raw numbers: `docs/aethern-bench.json`. Re-run: `python3 packages/aethern/bench/bench.py --root . --ids SOUND,COMBAT,KUROKO,AIROUTER,TIMELINE`.
Token figures are characters ÷ 4, the usual rough estimate (no tokenizer ships with the standard library).

| question an agent asks | read before | grep before | Aethern | 
|---|---|---|---|
| "What is system X, its files and command?" (median of 5 systems) | SYSTEMS.md whole: ~7,595 tokens | `grep -w X SYSTEMS.md`: ~213 tokens | `map show X`: ~118 tokens, with line counts and links |
| "What does X feed?" | systems.json: ~9,872 tokens | not answerable by grep | `map deps X --depth 3`: ~8 tokens |
| "Which system owns this file?" | systems.json: ~9,872 tokens | possible, noisy | `map owner F`: ~7 tokens |
| "How do I use the tools?" | AGENTS.md: ~3,800 tokens | | `aethern help`: ~337 tokens |

| speed | before | after |
|---|---|---|
| Rebuild systems.json | 20.5 ms (old builder) | 31.0 ms. **Slower by 10 ms**: the shared CLI's start-up. Output identical. |
| Change check, 856 files, nothing changed | `git status`: 4.0 ms (since last commit only) | `aethern changed`: 6.8 ms, 0 files re-hashed (since your last look) |
| Change check after a touch with no content change | | 6.5 ms, 1 file re-hashed, 0 reported as changed |
| First scan (no snapshot yet) | | 91 ms |
| Repeated identical model call (local stub server) | 1 request, 18 ms | 0 requests, 0.11 ms |

What these numbers do **not** show: the cache test used a local stub, so it measures the cache's own
cost, not a real model's latency (seconds, on your machine). And reading less only saves usage if
agents use these commands instead of opening files, which the head-to-head test has to show.

## How to check it yourself

```
python3 packages/aethern/bin/aethern help
python3 packages/aethern/bin/aethern map show SOUND
python3 tools/build_systems.py && git diff --stat systems.json      # no change
python3 tools/build_skills.py --check                               # SKILLS.md is current
cd packages/aethern && python3 -m unittest discover -s tests && node --test tests/js.test.mjs
```

## Next

The three-way head-to-head (plain Claude Code, Paper Cinema as it was, Paper Cinema on the core) is
planned in `docs/HEAD-TO-HEAD-PLAN.md` and waits for your yes, because it spends your usage.

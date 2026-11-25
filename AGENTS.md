# AGENTS.md: start here (every AI assistant and new teammate)

**Paper Cinema** makes short, cinematic Japanese sword-duel films (YouTube Shorts / TikTok / Reels, vertical by
default) in the **Lantern Origami** style: folded washi-paper characters lit from inside, real-metal or demonic
swords, paint instead of blood. **Everything in a film is data**; the engine renders it.

## 1. Orient yourself (in this order)
1. **This file**: the rules and commands.
2. **`SYSTEMS.md`**: every system (KUROKO, SHIMI, the skeleton, moves, sound…) with its files, guide, command and
   how it connects to the others. Machine-readable copy: `systems.json`.
3. **`docs/ARCHITECTURE.md`**: the shape of the project — one canonical timeline (`docs/TIMELINE-FORMAT.md`) and the six
   modules around it (Timeline Exporter, Fight Director, Camera Director, Paper Damage Bridge, Render Supervisor, Visual Critic).
4. **`.claude/skills/paper-cinema-film/SKILL.md`**: the step-by-step procedure for making a film (Claude Code loads it automatically).
5. **`docs/README.md`**: which guide to read for which task.
6. **`SKILLS.md`**: every skill in this repo, grouped by the job it does, with the one command that
   proves each one works. That file is the map; nothing here is meant to be found by browsing.

## 2. Folder map
| Folder | Contains |
|---|---|
| `film/` | One JSON per film (`ganryujima.json` = history film, `kuroko-duel.json` = every camera rig and move) |
| `library/` | Reusable data: `poses.json`, `moves.json`, `swords/`, `characters/`, `outfits/`, `parts.json`, `openings/`, `endcards/` |
| `engine/` | The code: engine, camera (KUROKO), skeleton, renderer, sound, checker, SHIMI, tools |
| `docs/` | The guides (index: `docs/README.md`) and the playbook page |
| `blender/` | Headless Blender scripts (realistic renders) |
| `gpu/` | RunPod GPU control + TRELLIS image → 3D |
| `assets/` | 3D models, sounds (+ credits) |
| `research/` | History with confidence marks |
| `tools/` | Repo tools (`build_systems.py`) |
| `output/` | Everything generated (videos, frames, stills). **Not committed** |

## 3. Commands
```bash
npm install                                              # once
node engine/new-film.mjs <name> --jp 漢字 --en TITLE      # new film: signature opening + fight + end card (vertical)
node engine/validate.mjs film/<name>.json                # checker: fix every ✗
node engine/render.mjs --film film/<name>.json --still auto   # one still per shot → output/stills/ (LOOK at them)
bash tools/shotsheet.sh film/<name>.json --set bamboo-forest   # 6 frames from the REAL path, one page.
                                                         # LOOK AT THIS before rendering a film. A model
                                                         # turnaround on grey hides everything that matters.
bash tools/film.sh film/<name>.json                      # MAKE THE FILM: the modular paper character, through
                                                         # Blender, with sound → output/<name>-final.mp4
node engine/render.mjs --film film/<name>.json           # fast BOX pass: a storyboard, never the deliverable
node tools/promises.mjs                                  # every promise, with the command that proves it
node tools/promises.mjs --check-character                # was the last film made with the real character?
node tools/vendor.mjs --list                             # the outside tools in vendor/, and what each is for
node tools/vendor.mjs                                    # fetch them all at their pinned commits
python3 tools/build_skills.py                            # rebuild SKILLS.md, the map of every skill
node engine/render.mjs --film film/<name>.json --vertical | --horizontal   # force a format
python3 engine/thumbnail.py film/<name>.json             # 16:9 + 9:16 thumbnails
python3 engine/shimi.py --preset kesa-cut --out output/shimi/kesa-cut     # SHIMI stain (presets in the file)
python3 docs/build_playbook.py film/<name>.json          # refresh the playbook page
node tools/audit.mjs film/<name>.json                    # studio QA: visibility, camera, pops, smear, sound… (docs/AUDIT.md)
bash tools/film.sh film/<name>.json [--set <name>]       # ONE COMMAND → output/<name>-final.mp4 (Blender + sound,
                                                         # validate → motion → events → audit → render → mix → report)
bash tools/film.sh film/<name>.json --from 96 --to 191   # one stretch; frames already rendered are kept (--fresh redoes them)
bash tools/film.sh film/<name>.json --full               # 720x1280 / 48 samples instead of the 360x640 preview
node tools/timeline.mjs film/<name>.json                  # THE canonical timeline for every renderer (docs/TIMELINE-FORMAT.md)
node tools/camera_check.mjs film/<name>.json             # score every shot; exit 1 on a rejected camera (docs/ARCHITECTURE.md)
/opt/blender-dl/blender-4.5.16-linux-x64/blender -b -P blender/check_sight.py -- \
  --film <name> --set output/sets/<set>.blend            # does the audience SEE it? blocked by the set,
                                                         # off-frame, or too small to read. CRITICAL on a
                                                         # contact frame: the shot exists for that frame
node tools/paper_damage.mjs film/<name>.json             # every cut → a SHIMI/KIZU wound contract
node tools/render_supervisor.mjs film/<name>.json --plan  # shot-by-shot render plan (quality presets, resume)
python3 tools/build_systems.py                           # refresh systems.json after editing SYSTEMS.md
/opt/blender-dl/blender-4.5.16-linux-x64/blender -b -P blender/demon_slash_test.py -- --state impact   # Blender test
npm run preview                                          # live preview in a browser
```
(Blender lives outside the repo. On a fresh machine, download Blender 4.5 LTS from download.blender.org.)

## 4. Rules (must follow)
00. **Use what already exists and works first.** Before building a system, search for a proven tool, skill, library, plugin or technique (GitHub, Blender add-ons/skills, open-source AI tools) and use or adapt it; build our own only for what nothing covers (or what must stay ours, e.g. SHIMI, KUROKO). Check the licence (rule 6). Learn from the owner's reference videos and images (`research/reference-*.md`) instead of guessing taste.
02c. **OmniRoute is the safety net.** `bash tools/omni.sh start` runs a local gateway over 400+ models; `tools/ai.py` falls through to it when the direct free endpoints are rate-limited. Adding more provider accounts (`omniroute keys add <provider> <key>`) widens the free capacity.
02b. **Free workers do the heavy lifting.** `python3 tools/worker.py "<task>"` gives the free NVIDIA models
    real tools (read, write, patch, search, run, look at images) in a loop, so they do multi-step work with
    NO usage cost. Use it for: installing and testing, wiring scripts, docs, repetitive fixes, investigations,
    running checkers and reading their output. Add `--model kimi` for harder reasoning, `--dry` to preview.
    Claude writes the brief and verifies the result; the free worker does the steps.
02a. **Use the cheapest worker that can do the job.** Agents cost the owner's usage, and the tiers differ a lot.
    - **Director** (Opus, the main session): decide what is good, verify, assemble, talk to the owner.
    - **Advisor** (Fable): hard design judgement only — how a fold should wrap, how a fight should read, an audit. Not implementation.
    - **Workers** (`model: haiku`, or `sonnet` when it needs more care): installing, testing, wiring, docs, repetitive fixes, anything with a clear spec. Default to haiku; promote only if it fails.
    - **Free labour** (`tools/ai.py`): writing, code drafts, and LOOKING at frames. Costs nothing.
    Never spawn an Opus or Fable agent for work a haiku agent can do from a clear brief.
02. **Send heavy text work to the free models** (`tools/ai.py`, rule 00): writing scenes, monologues, routine code, and LOOKING at stills/frames (free vision models) go to Cerebras / NVIDIA / Groq, not to Claude. `python3 tools/ai.py list` shows what is up; `review <png|frames dir>` has a model critique the picture; `write` / `code` / `think` for text. Claude directs, decides and verifies; the free models do the volume. Check `tools/ai.py budget` to see what was saved.
01. **Fable reviews and plans the detail work.** For movement, camera, ideas, look, fixes and audits, send the work to a Fable agent (model `fable`, currently Fable 5.2) as studio auditor / director, then build what it finds. Every film gets a Fable review of its stills and audit report before the final render.
00a. **Say the owner's name, Mark, in every reply.** It is a liveness check: it costs one word and it
proves the reply was written for this project and this person, not produced from a template. An
assistant that stops saying it has stopped reading, and Mark has said he will read it that way.

00b. **Set a goal, work it, report, continue.** Never finish a turn with nothing to do next. Before
the turn ends, the next goal is written down - in `library/promises.json` if it was promised out
loud, in the task list if it is in flight, in `docs/FIX-EVERYTHING.md` if it is owed. "What now?" is
a question this project should never have to ask.

0a. **A stated fix is a promise, and an unkept promise is a bug.** Saying "I'll fix that next" creates
an obligation that does not need re-approval: the owner may be distracted or may forget, and an
agreement reached once must not quietly expire. Write it into `library/promises.json` the moment it
is said, with a command that proves it, and run `node tools/promises.mjs` before claiming any work is
finished. Never ask whether to keep a promise already made - keep it. The failure this rule exists
for: on 25 Nov the films were rendered with the box character, after that exact problem had been
written down as item one of docs/FIX-EVERYTHING.md the same morning.

0. **Work autonomously.** When a fix or an improvement is clear, build it, verify it (stills, checker, audit) and report what changed. Do not wait for permission. Ask only for: spending money (rule 1), publishing anything publicly, deleting the owner's work, or a choice that changes the owner's design rules (rule 4).
1. **Paid GPUs: ask the owner first, with the expected cost.** Default to the cheapest *community* GPU. Every pod gets
   the self-destruct timer (`sleep 3600; runpodctl remove pod $RUNPOD_POD_ID`) and is stopped (`python3 gpu/pod.py stop`)
   before any long wait. An idle pod once cost $3 by mistake.
2. **Free compute first:** this machine, then Kaggle (free GPU, phone-verified account). The Kaggle **GPU**
   render is broken (every kernel is cancelled 11–18 s into a Blender render; `docs/KAGGLE-RENDER.md` has the
   eight measured runs that rule out quota, memory, disk and the rest), so `tools/film.sh --gpu` refuses and
   says so. Render here, or on Kaggle's CPU session (`bash gpu/kaggle_blender/run.sh push --cpu`).
3. **Validate, then look at stills, before any full render.** A 36 s render takes about 55 min on CPU.
3b. **Every video passes the studio standard:** read `docs/STUDIO-STANDARD.md` before directing, and run
   `node tools/audit.mjs film/<name>.json` before any full render (no critical finding; fix or waive every major) and
   again with `--frames` after it. Characters and world are paper; **effects are light**.
4. **Keep the owner's design decisions:** the style, amber = human / crimson = demonic, paint and paper shards
   instead of blood, vertical-first, the signature opening and end card.
5. **History:** claims go in `research/` with a confidence mark. Never present tradition as documented fact.
6. **Licences:** only commercial-safe models and assets (MIT, Apache, CC0, CC-BY). Credit CC-BY sounds.
7. **No secrets in files.** API keys are injected by the environment's network proxy.
8. **Keep it connected:** a new system gets a row in `SYSTEMS.md` (then run `python3 tools/build_systems.py`), a
   guide in `docs/` (listed in `docs/README.md`), and a mention in the skill if it changes the procedure.

## 5. Status
- **Built:**
  - preview engine; KUROKO camera; skeleton with legs, balance and the correct draw; moves; reactions
  - library; sound; checker; one-command pipeline; new-film scaffolder; vertical format; thumbnails
  - SHIMI stain sim (2D); 5 TRELLIS models (static); Blender slash test; playbook
  - articulated skeleton (spine, neck, clavicles, twists, wrists, ankles, glowing eyes) + anime motion layer (lag, snap, settle, jump arcs)
  - motion-test page (`engine/motion.js`): blade-contact detection, clash aim, hit-stop, smear ribbon, ink impact frame, auto sound cues, eye-to-blade camera
  - our own synthesised sword sounds (`tools/synth_sfx.sh`); Blender world set + slash FX (`blender/world/`, v1)
  - studio standard + automated audit (`docs/STUDIO-STANDARD.md`, `tools/audit.mjs`); cinematographer camera (`compose` solver, speed ramps); light smear, shock ring, glints; dust, contact shadows, afterimages (`engine/groundfx.js`)
  - one-command film: `bash tools/film.sh film/<name>.json` → `output/<name>-final.mp4` (checker → motion → cue
    events → audit gate → Blender on four niced cores, resumable → mix at -14 LUFS with a pre-hit dip → report)
  - Blender SETS: data-driven locations from a kit (`library/sets/*.json`, `blender/sets/`, guide `docs/SETS.md`): castle courtyard, dojo, bamboo forest, Ganryūjima beach, a 2.5D paper-cut skyline; origami samurai on the marks
- **Next** (see `docs/EFFECTS-PLAN.md`, `docs/SHIMI.md`, `docs/BLENDER-PLAN.md`):
  - the face-touch scene; SHIMI on the 3D body
  - the anime effects pack; a 3-second Shorts opening; Blender slash v2
  - rigging the TRELLIS models
- **Next first:** re-render the duel (`film/kuroko-duel.json` now uses the shared combat layer `engine/combat.js`: clashes, hit-stop, eyes, auto sounds, FX); then the items marked next in `docs/FIX-LIST.md`.
- **Blender hero:** `docs/CHARACTER-BLENDER.md` (the TRELLIS character rigged, film and BVH drivers, `blender/film_blender.py`).
- **Limits:** the browser preview's set is still code in `engine/world.js`; Blender sets (`blender/sets/build_set.py`) place posed characters on marks but do not yet play a film timeline.

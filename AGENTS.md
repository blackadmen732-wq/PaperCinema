# AGENTS.md: start here (every AI assistant and new teammate)

**Paper Cinema** makes short, cinematic Japanese sword-duel films (YouTube Shorts / TikTok / Reels, vertical by
default) in the **Lantern Origami** style: folded washi-paper characters lit from inside, real-metal or demonic
swords, paint instead of blood. **Everything in a film is data**; the engine renders it.

## 1. Orient yourself (in this order)
1. **This file**: the rules and commands.
2. **`SYSTEMS.md`**: every system (KUROKO, SHIMI, the skeleton, moves, sound…) with its files, guide, command and
   how it connects to the others. Machine-readable copy: `systems.json`.
3. **`.claude/skills/paper-cinema-film/SKILL.md`**: the step-by-step procedure for making a film (Claude Code loads it automatically).
4. **`docs/README.md`**: which guide to read for which task.

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
node engine/make.mjs film/<name>.json                    # whole pipeline: check → stills → render → sound → playbook
node engine/render.mjs --film film/<name>.json --vertical | --horizontal   # force a format
python3 engine/thumbnail.py film/<name>.json             # 16:9 + 9:16 thumbnails
python3 engine/shimi.py --preset kesa-cut --out output/shimi/kesa-cut     # SHIMI stain (presets in the file)
python3 docs/build_playbook.py film/<name>.json          # refresh the playbook page
python3 tools/build_systems.py                           # refresh systems.json after editing SYSTEMS.md
/opt/blender-dl/blender-4.5.16-linux-x64/blender -b -P blender/demon_slash_test.py -- --state impact   # Blender test
npm run preview                                          # live preview in a browser
```
(Blender lives outside the repo. On a fresh machine, download Blender 4.5 LTS from download.blender.org.)

## 4. Rules (must follow)
0. **Work autonomously.** When a fix or an improvement is clear, build it, verify it (stills, checker, audit) and report what changed. Do not wait for permission. Ask only for: spending money (rule 1), publishing anything publicly, deleting the owner's work, or a choice that changes the owner's design rules (rule 4).
1. **Paid GPUs: ask the owner first, with the expected cost.** Default to the cheapest *community* GPU. Every pod gets
   the self-destruct timer (`sleep 3600; runpodctl remove pod $RUNPOD_POD_ID`) and is stopped (`python3 gpu/pod.py stop`)
   before any long wait. An idle pod once cost $3 by mistake.
2. **Free compute first:** this machine, then Kaggle (free GPU, phone-verified account).
3. **Validate, then look at stills, before any full render.** A 36 s render takes about 55 min on CPU.
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
- **Next** (see `docs/EFFECTS-PLAN.md`, `docs/SHIMI.md`, `docs/BLENDER-PLAN.md`):
  - the face-touch scene; SHIMI on the 3D body
  - the anime effects pack; a 3-second Shorts opening; Blender slash v2
  - rigging the TRELLIS models
- **Next first:** re-render the duel (`film/kuroko-duel.json` now uses the shared combat layer `engine/combat.js`: clashes, hit-stop, eyes, auto sounds, FX); then the items marked next in `docs/FIX-LIST.md`.
- **Limits:** the browser preview's set is still code in `engine/world.js`; the Blender set (`blender/world/build_world.py`) does not yet import characters or a film timeline.

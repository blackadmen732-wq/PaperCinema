# SKILLS.md — the map

Every skill in this repository, grouped by the job it does. Written for **any** agent: Claude Code
loads `.claude/skills/` by itself, and Codex, Grok, Cursor and anything else can read this page and
then read the one file it points at. Nothing here needs a particular product to be useful.

Read `AGENTS.md` first — it has the rules. This page is where you find the procedure.

## The order of work

A film goes through these, in this order. Each line is a command you can run now; if a step fails it
says so and stops, and nothing further is worth doing until it passes.

| # | Step | Command | Skill |
|---|---|---|---|
| 1 | Write the film | `node engine/new-film.mjs <name> --jp 漢字 --en TITLE` | [`paper-cinema-film`](.claude/skills/paper-cinema-film/SKILL.md) |
| 2 | Check the file | `node engine/validate.mjs film/<name>.json` | same |
| 3 | Block it out, fast and wrong | `node engine/render.mjs --film film/<name>.json` | same — **boxes, a storyboard, never the deliverable** |
| 4 | Look at the stills | `node engine/render.mjs --film film/<name>.json --still auto` | [`qa-review`](.claude/skills/qa-review/SKILL.md) |
| 5 | **Make the film** | `bash tools/film.sh film/<name>.json` | [`paper-cinema-film`](.claude/skills/paper-cinema-film/SKILL.md) |
| 6 | Prove it was the real character | `node tools/promises.mjs --check-character` | — |
| 7 | Keep every promise | `node tools/promises.mjs` | — |

Step 5 is the one that matters. It validates, exports the motion and the canonical timeline, finds
the sound cues, runs the studio audit, renders in Blender **with the modular paper character**,
encodes, adds voice and sound, and reports. It writes `output/<name>.render.json` saying what made
the frames, which is what step 6 reads.

## What is where

| | |
|---|---|
| Rules, every agent, read once a session | `AGENTS.md` |
| Every system and how it connects | `SYSTEMS.md` · machine-readable `systems.json` |
| The shape of the project | `docs/ARCHITECTURE.md` |
| The one timeline format every renderer reads | `docs/TIMELINE-FORMAT.md` |
| Promises made out loud, each with a command that proves it | `library/promises.json` · `node tools/promises.mjs` |
| Outside tools, pinned to a commit | `vendor/MANIFEST.json` · `node tools/vendor.mjs --list` |
| Which guide for which task | `docs/README.md` |
| This page | `python3 tools/build_skills.py` |

## Three rules that cost people time here

1. **Boxes are not the character.** `engine/figure.js` is a preview. The character is built part by
   part in `blender/character/` and rendered by `blender/film_modular.py`. If what you are looking at
   has rectangular arms, you are looking at a storyboard.
2. **Every frame is a pure function of time.** `window.renderAt(t)` must draw the same image for the
   same `t`, asked in any order, on any machine. Nothing may accumulate between frames. This is what
   lets frames render in parallel and a still match frame 77.
3. **A stated fix is a promise.** It goes in `library/promises.json` with a command that proves it,
   the moment it is said. Checks that grep for a filename do not count — one of those passed while
   three films went out with the wrong character.

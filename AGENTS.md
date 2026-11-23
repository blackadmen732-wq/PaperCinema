# AGENTS.md: start here (for any AI assistant or new teammate)

**Paper Cinema** makes cinematic Japanese sword-fight films in the **Lantern Origami** style:
folded/cut paper characters lit from inside, real-metal or demonic swords, data-driven camera and sound.

## Claude skill
`.claude/skills/paper-cinema-film/SKILL.md` is the step-by-step procedure for making or changing a film (Claude Code loads it automatically).

## Read these first
0. `docs/playbook.html`: **visual playbook**: the 9-step pipeline, live camera-path plot, fight beats, sound cues, new-chat prompt (rebuild with `python3 docs/build_playbook.py`)
1. `docs/STYLE-AND-FIGHT-SYSTEM.md`: the look, the 6-beat Strike Grammar, camera modes, lighting rules
2. `docs/FILM-FORMAT.md`: **every field of a film file** + the golden path for a new film
3. `docs/CAMERA.md`: **how to control the camera** (all camera moves are JSON data)
4. `docs/ANIMATION.md`: **skeleton (with legs), poses, balance, smooth motion, the draw, two-hand grip, reactions** (all motion is JSON data)
5. `docs/BLENDER-PLAN.md`: the plan for realistic Blender renders: KUROKO camera rigs, paper/metal shaders, move library, paint-not-blood cuts, environments, signature opening
6. `research/`: historical facts, each marked *documented* / *tradition* / *our choice*

## Project map
| Path | What |
|---|---|
| `film/*.json` | A film: shots (camera), shakes, events, performances (motion), titles, sound cues |
| `library/poses.json` | Named poses for the shared skeleton (stances, cuts, reactions) |
| `library/moves.json` | Named fight moves (jump-back, parry, lunge-shomen, tsuki, bind…) that expand into timed poses |
| `library/openings/`, `library/endcards/` | Signature opening (lantern-wave) and end card templates |
| `engine/kuroko.js` | **KUROKO** camera operator: rigs (frame/orbit/track/face/anchor/blade), feels, motion-reactive behaviours |
| `engine/new-film.mjs` | Scaffold a new film: signature opening + fight body + end card |
| `engine/resolve-camera.mjs` | Resolves KUROKO cameras per frame (used by the playbook) |
| `engine/thumbnail.py` | 16:9 and 9:16 thumbnails from the decisive-blow frame |
| `blender/` | Blender scripts (headless). `demon_slash_test.py` = paint-not-blood slash lookdev |
| `engine/shimi.py` | **SHIMI** stain simulator: paint bleeding into paper fibres (wicking, gravity rivulets, dark drying rims) |
| `docs/EFFECTS-PLAN.md` | SHIMI integration, the face-touch scene design, Blender slash v2, anime effects pack |
| `docs/STORY-BIBLE.md` | Series world rules, characters, cursed swords (fiction), episode ideas |
| `engine/validate.mjs` | Checks a film file and explains every mistake (run before rendering) |
| `engine/make.mjs` | Whole pipeline in one command: check → stills → render → sound → playbook |
| `engine/main.js` | Film engine: world, cast, choreography, camera, overlays; exposes `window.renderAt(t)` |
| `engine/world.js` | Layered paper sea, island, coasts, sun, dark sword studio |
| `engine/figure.js` | Shared rigged paper body + pose system (`track`, `applyPose`, `holdInHand`) |
| `engine/props.js` | Sword builder (`makeKatana`), bokken, boat, oar |
| `engine/paper.js`, `engine/patterns.js` | Washi paper materials; 10 procedural Japanese textile patterns |
| `engine/library.js` | Builds swords/characters from `library/` presets |
| `engine/render.mjs` | Headless Chrome frame-by-frame renderer → MP4 (also `--still`) |
| `engine/sound.mjs` | Sound pipeline: find (Openverse) → check (ffmpeg) → place (cue times) → mix |
| `engine/lookdev.*`, `engine/lineup.*` | Test stages: sword materials (metal/demonic/ink) and library lineups |
| `library/` | `parts.json`, `swords/`, `characters/`, `outfits/`: swap by editing data |
| `assets/models/` | 3D models generated from reference images (TRELLIS, MIT) |
| `assets/sfx/` | Downloaded sounds + `CREDITS.md` (CC-BY sounds need credit in the video description) |
| `gpu/` | Rent/drive/stop a RunPod GPU (`pod.py`), on-pod job agent, TRELLIS generator |

## Commands
```bash
npm install                                        # once
npm run validate                                   # check film/ganryujima.json (explains mistakes)
npm run check                                      # validate + one still per shot → output/stills/
node engine/render.mjs --still 25.7                # one frame
node engine/render.mjs --from 24 --to 30 --out output/clip.mp4   # a section
npm run film                                       # whole pipeline → output/ganryujima-sound.mp4
node engine/make.mjs film/<name>.json              # whole pipeline for another film
node engine/new-film.mjs <name> --jp 漢字 --en TITLE   # start a new film with the signature opening + end card
node engine/render.mjs --film film/<name>.json --vertical   # 9:16 version (KUROKO reframes automatically)
python3 engine/thumbnail.py film/<name>.json        # 16:9 + 9:16 thumbnails
/opt/blender-dl/blender-4.5.16-linux-x64/blender -b -P blender/demon_slash_test.py -- --state impact   # Blender test
npm run preview                                    # live preview in a browser
```

## Rules (must follow)
1. **Paid GPUs: ask the owner first, with the expected cost.** Default to the cheapest *community* GPU.
   Every pod must have the self-destruct timer (`sleep 3600; runpodctl remove pod $RUNPOD_POD_ID`) and must be
   stopped (`python3 gpu/pod.py stop`) before any long wait. An idle pod once cost $3 by mistake.
2. Prefer free compute: this machine, then Kaggle (free GPU, phone-verified account).
3. **Validate, then check stills, before full renders.** A full 36 s render takes ~55 min on CPU.
4. Keep the owner's design decisions (style, amber = human / crimson = demonic glow, paper shards instead of blood).
5. Historical claims go in `research/` with a confidence mark. Never present tradition as documented fact.
6. Licences: only commercial-safe models and assets (MIT/Apache/CC0/CC-BY). Credit CC-BY sounds.
7. Never commit secrets. API keys are injected by the environment's network proxy, never written in files.

## Status / next steps
- Done: preview engine; camera, motion (poses + smooth curves + two-hand grip), events, titles and sound all from data;
  libraries (swords, characters, outfits, patterns, poses); checker; one-command pipeline; 5 TRELLIS models; visual playbook.
- Next (see docs/BLENDER-PLAN.md milestones M1–M8): Blender lookdev stills, resolver + Blender builder, rig `assets/models/*.glb` with the same skeleton layout (Blender), real motion capture (Kaggle), Blender render, AI restyle (Wan VACE).
- Sets (island, sea, studio) and prop effects (boat, thrown scabbard) are still built in code for Ganryūjima.

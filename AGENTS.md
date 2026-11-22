# AGENTS.md: start here (for any AI assistant or new teammate)

**Paper Cinema** makes cinematic Japanese sword-fight films in the **Lantern Origami** style:
folded/cut paper characters lit from inside, real-metal or demonic swords, data-driven camera and sound.

## Read these first
1. `docs/STYLE-AND-FIGHT-SYSTEM.md`: the look, the 6-beat Strike Grammar, camera modes, lighting rules
2. `docs/CAMERA.md`: **how to control the camera** (all camera moves are JSON data)
3. `research/`: historical facts, each marked *documented* / *tradition* / *our choice*

## Project map
| Path | What |
|---|---|
| `film/*.json` | A film: shots (camera keyframes), shakes, titles, sound cues |
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
npm install                                   # once
node engine/render.mjs --still 2,11.5,25.7    # quick check → output/stills/
npm run render                                # full film → output/ganryujima.mp4
node engine/sound.mjs                         # add sound → output/ganryujima-sound.mp4
npm run preview                               # live preview in a browser
```

## Rules (must follow)
1. **Paid GPUs: ask the owner first, with the expected cost.** Default to the cheapest *community* GPU.
   Every pod must have the self-destruct timer (`sleep 3600; runpodctl remove pod $RUNPOD_POD_ID`) and must be
   stopped (`python3 gpu/pod.py stop`) before any long wait. An idle pod once cost $3 by mistake.
2. Prefer free compute: this machine, then Kaggle (free GPU, phone-verified account).
3. **Check stills before full renders.** A full 36 s render takes ~55 min on CPU.
4. Keep the owner's design decisions (style, amber = human / crimson = demonic glow, paper shards instead of blood).
5. Historical claims go in `research/` with a confidence mark. Never present tradition as documented fact.
6. Licences: only commercial-safe models and assets (MIT/Apache/CC0/CC-BY). Credit CC-BY sounds.
7. Never commit secrets. API keys are injected by the environment's network proxy, never written in files.

## Status / next steps
- Done: preview engine, camera-from-data, libraries (swords, characters, outfits, patterns), sound pipeline, 5 TRELLIS models.
- Next: rig `assets/models/ronin_base.glb`, generate sword motion (Kaggle), Blender render, AI restyle (Wan VACE).
- Choreography still lives in code (`engine/main.js`). Moving it into `film/*.json` is planned.

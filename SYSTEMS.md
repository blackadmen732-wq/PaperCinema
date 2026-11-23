# SYSTEMS: everything in Paper Cinema, and how it connects

Every named system lives in one place, has one guide, and has one command. A machine-readable copy of this list
is in `systems.json` (same IDs). If you add a system, add it here **and** in `systems.json`.

## How the pieces connect (one film, start to finish)

```mermaid
flowchart LR
  R[research/*.md<br/>history, marked] --> F
  T[new-film.mjs<br/>OPENING + ENDCARD templates] --> F
  L[LIBRARY<br/>characters · outfits · swords · poses · moves] --> F
  F[film/&lt;name&gt;.json<br/>shots · performances · events · sounds] --> V[CHECKER<br/>validate.mjs]
  V --> E[ENGINE main.js]
  E --> SK[SKELETON + MOTION<br/>figure.js · moves.js]
  E --> K[KUROKO camera<br/>kuroko.js]
  E --> W[WORLD + PAPER<br/>world.js · paper.js · patterns.js]
  E --> RN[RENDER render.mjs<br/>16:9 / 9:16 → MP4]
  RN --> SD[SOUND sound.mjs<br/>find → check → place]
  SD --> OUT[(output/&lt;name&gt;-sound.mp4)]
  F --> TH[THUMBNAIL thumbnail.py]
  F --> PB[PLAYBOOK<br/>build_playbook.py + resolve-camera.mjs]
  F -. cut / touch events .-> KZ[KIZU wound layer]
  KZ --> SH[SHIMI stain sim<br/>shimi.py]
  SH -. maps .-> BL[BLENDER blender/*.py]
  G[GPU gpu/*.py<br/>TRELLIS models] --> A[(assets/models)]
  A -. rig, planned .-> BL
```

One command runs the solid path: `node engine/make.mjs film/<name>.json` (check → stills → render → sound → playbook).

## The catalogue

| ID | System | What it does | Files | Guide | Command | Status |
|---|---|---|---|---|---|---|
| `STYLE` | **Lantern Origami** | The look: faceted washi paper lit from inside; amber = human, crimson = demonic; paint not blood | (rules) | `docs/STYLE-AND-FIGHT-SYSTEM.md` | | ✅ |
| `STRIKE` | **Strike Grammar** | Every attack in 6 beats: ready → wind-up → slash → hit-stop → follow-through → reaction | (rules) | `docs/STYLE-AND-FIGHT-SYSTEM.md` §2 | | ✅ |
| `FILM` | **Film file** | One JSON per film: shots, camera, performances, duels, events, shakes, titles, sounds, format | `film/*.json` | `docs/FILM-FORMAT.md` | | ✅ |
| `CHECK` | **Checker** | Validates a film and explains every mistake in plain words | `engine/validate.mjs` | `docs/FILM-FORMAT.md` | `npm run validate` | ✅ |
| `MAKE` | **One-command pipeline** | check → stills → render → sound → playbook | `engine/make.mjs` | `AGENTS.md` | `node engine/make.mjs film/x.json` | ✅ |
| `NEWFILM` | **New-film scaffolder** | Signature opening + fight body + end card, vertical by default | `engine/new-film.mjs`, `library/openings/`, `library/endcards/` | `docs/FILM-FORMAT.md` | `node engine/new-film.mjs x --jp 漢字 --en TITLE` | ✅ |
| `ENGINE` | **Preview engine** | Builds the 3D paper world per frame (`window.renderAt(t)`), deterministic | `engine/main.js`, `engine/index.html` | `AGENTS.md` | `npm run preview` | ✅ |
| `WORLD` | **Sets + paper** | Layered paper sea, island, coasts, sword studio; washi materials; 10 textile patterns | `engine/world.js`, `engine/paper.js`, `engine/patterns.js` | `docs/STYLE-AND-FIGHT-SYSTEM.md` | | ✅ (sets in code) |
| `SKELETON` | **Skeleton + balance** | Shared rig: two-part spine, neck, clavicles, shoulder/forearm twist, 2-axis wrists, ankles, optional glowing eyes with lids; leg IK, stance/crouch/weight, analytic arm IK (`solveArm`) | `engine/figure.js` | `docs/ANIMATION.md` | | ✅ |
| `MOTION` | **Motion system** | Keys of "second + pose", smooth monotone curves, breathing, cloth follow-through, walk cycle; anime layer: per-joint follow-through lag, `ease` snap curves, `settle` overshoot, `drag:0` contacts | `engine/figure.js`, `library/poses.json` | `docs/ANIMATION.md` | pose gallery: see guide §7 | ✅ |
| `MOVES` | **Fight moves** | Named moves (jump-back, parry, lunge-shomen, kesa-giri, tsuki, bind, dodge, stagger…) expanded into poses | `engine/moves.js`, `library/moves.json` | `docs/ANIMATION.md` §5b | | ✅ |
| `REACT` | **Reaction layer** | Fighters watch each other; delayed threat response (function react) | `engine/main.js` | `docs/ANIMATION.md` §6 | | ✅ |
| `DRAW` | **Sword draw** | One blade slides out of the scabbard into the grip, hand on the hilt | `engine/main.js` | `docs/ANIMATION.md` §5 | | ✅ |
| `KUROKO` | **KUROKO camera** | Automatic operator: rigs (frame/orbit/track/face/anchor/blade), feels (locked/dolly/crane/handheld/torpedo), motion-reactive behaviours, look-ahead, impact punch, guards | `engine/kuroko.js`, `engine/resolve-camera.mjs` | `docs/CAMERA.md` §7 | | ✅ |
| `KEYCAM` | **Keyframe camera** | Hand-made camera paths (pos/look/fov) on smooth curves + shakes | `engine/main.js` | `docs/CAMERA.md` §1–6 | | ✅ |
| `LIBRARY` | **Library** | Swords from parts, characters on one body, outfits, patterns | `library/`, `engine/library.js` | `library/*` + `docs/ANIMATION.md` | lineup: `engine/lineup.html` | ✅ |
| `RENDER` | **Renderer** | Headless Chrome, frame by frame → MP4; `--still`, `--vertical`, `--from/--to` | `engine/render.mjs`, `engine/serve.mjs` | `AGENTS.md` | `npm run render` | ✅ |
| `SOUND` | **Sound pipeline** | Find (Openverse) → check (ffmpeg) → place at cue times → mix; credits | `engine/sound.mjs`, `assets/sfx/` | `docs/playbook.html` | `npm run sound` | ✅ |
| `CLASH` | **Blade contact + hit-stop** | Finds blade-to-blade contact (segment distance, 240 Hz), clash aim so blocks meet the cut, hit-stop body time, sparks, smear ribbon, ink impact frame, auto sound cues (whoosh/clash/scrape) → `output/<film>.events.json` | `engine/motion.js`, `engine/motion.html`, `film/motion-test.json` | `docs/ANIMATION.md` | `node engine/render.mjs --film film/motion-test.json` | ✅ (motion page and main engine, via `engine/combat.js`) |
| `COMBAT` | **Combat layer (shared)** | The fight layer of both preview engines, in one module: blade contact detection (240 Hz segment distance, speed and gap thresholds), clash aim (`clashes`), hit-stop body time (`bodyT`/`filmT`; in `main.js` the shots, rigs and authored action times run on body time), smear ribbon, paper sparks + flash light, ink silhouette impact frame, camera punch, eye glow states + blinks + voice pulse (`cast.<id>.face: "eyes"`), auto sound cues (whoosh, steel clash or wood clap for a bokken, scrape) → `window.EVENTS` → `output/<film>.events.json` → SOUND; FX post stack (`fxBase`/`fx`) with a CA flash and bloom pulse on each contact | `engine/combat.js`, `engine/main.js`, `engine/motion.js`, `film/kuroko-duel.json` | `docs/FIX-LIST.md`, `docs/FILM-FORMAT.md` | `node engine/render.mjs --film film/kuroko-duel.json --vertical --still auto --prefix kd2-` | ✅ (main engine + motion page) |
| `SYNTHSFX` | **Synthesised sword sounds** | Our own layered clash (tink + ring + body + paper crinkle), light clash, scrape, 3 whooshes, draw shing; no licence needed | `tools/synth_sfx.sh`, `assets/sfx/` | `docs/FIX-LIST.md` | `bash tools/synth_sfx.sh` | ✅ |
| `VOICE` | **Voice (spoken lines)** | Film `"voice"` lines → Kokoro-82M TTS (Apache-2.0, CPU) → cinematic chain (warmth, compression, hall, inner-monologue) → `output/<film>.voice.json`: cues mixed by SOUND with beds ducked 8 dB, plus 24 fps loudness envelopes to pulse the eyes | `tools/voice.py`, `engine/voice-env.js`, `assets/voice/`, `film/voice-test.json` | `docs/VOICE.md` | `nice -n 10 python3 tools/voice.py film/x.json` | ✅ (wired into main.js and motion.js via fxBase / fx) |
| `THUMB` | **Thumbnails** | 16:9 + 9:16 from the decisive-blow frame, kanji title, brush swash | `engine/thumbnail.py` | `AGENTS.md` | `python3 engine/thumbnail.py film/x.json` | ✅ |
| `PLAYBOOK` | **Playbook page** | Interactive page: pipeline, live camera plot, motion and sound timeline, new-chat prompt | `docs/playbook.template.html`, `docs/build_playbook.py` | `docs/playbook.html` | `npm run playbook` | ✅ |
| `SHIMI` | **SHIMI (染み) stain sim** | Paint soaking into paper: two water layers, fibres, saturation-limited wicking, gravity field, drips, tide lines; presets; data maps | `engine/shimi.py` | `docs/SHIMI.md`, `docs/SHIMI-3D.md` | `python3 engine/shimi.py --preset kesa-cut` | ✅ 2D · 3D planned |
| `KIZU` | **KIZU (傷) wound layer** | Decides how paint leaves a cut: onset delay, beads → line, depth/region welling, brush swipe, heavy-bead drips (non-graphic); option --wound | `engine/shimi.py` | `docs/SHIMI.md` §1c | `python3 engine/shimi.py --preset face-cut --out output/shimi/face-cut` | ✅ 2D |
| `LOOKDEV` | **Lookdev stages** | Sword materials (metal / demonic / ink) | `engine/lookdev.*` | `docs/BLENDER-PLAN.md` | | ✅ |
| `BLENDER` | **Blender (realistic)** | Headless Cycles renders; demon-slash test (cut paper, ink slash, paint) | `blender/*.py` | `docs/BLENDER-PLAN.md` | `blender -b -P blender/demon_slash_test.py -- --state impact` | 🧪 test |
| `BWORLD` | **Blender world set (Ganryūjima)** | Build-once 3D location: faceted paper island, pines, rocks, Ocean-modifier sea with foam, cut-paper mountain rings with sky haze, Nishita dawn + paper sun, paper clouds, optional fog; named collections, fighter marks (`MARK_*`) and camera anchors (`CAM_*`); seeded and deterministic | `blender/world/build_world.py` | `docs/BLENDER-WORLD.md` | `blender -b -P blender/world/build_world.py -- --out output/world/ganryujima.blend --preview output/world/preview.png` | 🧪 v1 |
| `PAPERMAT` | **Paper materials (Blender)** | Reusable Lantern Origami shaders: faceted washi (true-normal facets, fibre bump, per-facet tone, translucency, inner glow, stripes, sky haze), paper sea, metal | `blender/world/paper_materials.py` | `docs/BLENDER-WORLD.md` §3 | | 🧪 v1 |
| `SLASHFX` | **Slash effects (Blender)** | Keyframed crescent slash: tapered folded arc, emissive core (amber human / crimson demonic), ink-brush edge, paper-shard spray, flare light; radius, sweep, thickness, colour, demonic flag | `blender/world/slash_fx.py` | `docs/BLENDER-WORLD.md` §4 | `blender -b -P blender/world/slash_fx.py -- --test output/world/slash-test.png` | 🧪 v1 |
| `GPU` | **GPU jobs** | Rent/run/stop RunPod pods (self-destruct timer); TRELLIS image → 3D | `gpu/*.py` | `AGENTS.md` rules | `python3 gpu/pod.py status` | ✅ (paid: ask first) |
| `MODELS` | **3D models** | 5 models from reference images (TRELLIS, MIT) | `assets/models/` | `assets/README.md` | | ✅ static (no rig yet) |
| `ANATOMY` | **Anatomy (third-party skill)** | Interactive isometric explainer figures (SVG/WebGL), for example "anatomy of a katana" Shorts; MIT, by wheresryan22 | `.claude/skills/anatomy/SKILL.md` | `.claude/skills/anatomy/SKILL.md` | `/anatomy explain how a katana is built` | ✅ installed |
| `STORY` | **Story bible** | World rules, characters, cursed swords (fiction), episode ideas | `docs/STORY-BIBLE.md` | | | ✅ |
| `SCENE` | **Scene writing** | Idea → logline → beat sheet (1 s hook, jo-ha-kyū) → voiced lines with timing and direction → moves, shot types, sounds, effects → film-JSON outline; 9 reusable templates, taste rules, checklist | `.claude/skills/scene-writing/SKILL.md`, `library/scene-templates.json` | `docs/SCENE-WRITING.md` | | ✅ |
| `DIRECTION` | **Scene direction** | Story beat → shot list → KUROKO rigs / motion-page camera beats → lighting mood → cut rhythm → taste review; 49 named shots (tested in 9:16 and 16:9), 17 direction styles (Kurosawa, Leone, Kubrick, Wong Kar-wai, Deakins, Spielberg, ufotable, MAPPA, Sword of the Stranger, Champloo, Shinkai, Kon, Itano, Arcane, Hong Kong, John Wick, dark monologue), 11 lighting moods, a fight-beat map | `.claude/skills/scene-direction/SKILL.md`, `library/shots.json` | `docs/DIRECTION.md` | | ✅ |
| `RESEARCH` | **Research** | History with confidence marks | `research/` | | | ✅ |
| `EFFECTS` | **Effects plan** | Face-touch scene, slash v2, anime effects (flash-step, shadow-vanish, speed lines, impact frame) | `docs/EFFECTS-PLAN.md` | | | 📋 planned |
| `FX` | **FX post-processing (three.js preview)** | Deterministic effect stack any page can import: bloom (UnrealBloomPass), one lens pass (colour-grade moods, vignette, film grain, letterbox, chromatic-aberration flash, radial speed lines, ink impact frame, flash/fade), light-shaft cards, seeded particles (dust/ember/petal/snow/ash/shard), glint "ping", trauma shake; `fxAt()` turns film `fx` events into per-frame params; catalogue of 42 effects in `library/effects.json` | `engine/fx.js`, `engine/fx-demo.html`, `engine/fx-demo.js`, `film/fx-demo.json`, `library/effects.json` | `docs/EFFECTS-CATALOG.md` | `node engine/render.mjs --page engine/fx-demo.html --film film/fx-demo.json --still 3.7,13.7 --prefix fx-` | 🧪 demo page (wired into main.js and motion.js) |

Legend: ✅ built and used · 🧪 working test · 📋 designed, not built.

## Where to put new things
- **A new pose:** `library/poses.json`. **A new move:** `library/moves.json`.
- **A new sword, character or outfit:** `library/swords/`, `library/characters/` or `library/outfits/`.
- **A new film:** `node engine/new-film.mjs <name> …`, which creates `film/<name>.json`.
- **A new named shot or direction style:** `library/shots.json` (test it with stills; guide `docs/DIRECTION.md`).
- **A new camera rig or behaviour:** `engine/kuroko.js` (export it in `RIG_TYPES` / `BEHAVIOURS` so the checker knows it).
- **A new SHIMI scenario:** add to `PRESETS` in `engine/shimi.py`.
- **A new system:** add a row here and in `systems.json`, a guide in `docs/`, and a line in `AGENTS.md` if it changes the rules.
- **Generated files** (videos, frames, stills) go to `output/`, which is not committed.

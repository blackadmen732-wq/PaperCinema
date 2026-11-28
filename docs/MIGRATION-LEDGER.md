# CINEVORA migration ledger

Every system in `systems.json` (69) classified for CINEVORA. Research and planning only: no code has moved, no
repo changed. Classes: **inherited** (used as is), **generalized** (the reusable core is lifted out, its
Paper-Cinema specialization kept as a preset), **preset** (a paper/samurai-specific look or rule kept as an
optional reference implementation), **external** (depends on an outside tool — licence noted, checked before use),
**deferred** (not yet registered or not ready). All first-party code is Paper Cinema's own (one owner, Mark);
treat it as all-rights-reserved until a licence is chosen. Generalization turns the samurai skeleton into a
universal articulated character, paper materials into a material system, sword-contact into object-contact, and
so on, without deleting the originals.

| System | Name | Does | Files | Class | External |
|---|---|---|---|---|---|
| `STYLE` | Lantern Origami | The look: faceted washi paper lit from inside; amber = human, crimson  | `—` | preset | own |
| `STRIKE` | Strike Grammar | Every attack in 6 beats: ready → wind-up → slash → hit-stop → follow-t | `—` | generalized | own |
| `FILM` | Film file | One JSON per film: shots, camera, performances, duels, events, shakes, | `film/*.json` | generalized | own |
| `CHECK` | Checker | Validates a film and explains every mistake in plain words | `engine/validate.mjs` | inherited | own |
| `MAKE` | One-command pipeline | check → stills → render → sound → playbook | `engine/make.mjs` | generalized | own |
| `FILMONE` | One-command film (Blender + sound) | `tools/film.sh film/<name>.json` → `output/<name>-final.mp4`: validate | `tools/film.sh,tools/render_plan.py` | generalized | own |
| `KAGGLEFARM` | Free Kaggle Blender farm | The render job as DATA (`job.json` in a private dataset: `blender/`, ` | `gpu/kaggle_blender/` | generalized | own |
| `NEWFILM` | New-film scaffolder | Signature opening + fight body + end card, vertical by default | `engine/new-film.mjs,library/openings/` | inherited | own |
| `ENGINE` | Preview engine | Builds the 3D paper world per frame (`window.renderAt(t)`), determinis | `engine/main.js,engine/index.html` | preset | own |
| `WORLD` | Sets + paper | Layered paper sea, island, coasts, sword studio; washi materials; 10 t | `engine/world.js,engine/paper.js` | preset | own |
| `SKELETON` | Skeleton + balance | Shared rig: two-part spine, neck, clavicles, shoulder/forearm twist, 2 | `engine/figure.js` | generalized | own |
| `MOTION` | Motion system | Keys of "second + pose", smooth monotone curves, breathing, cloth foll | `engine/figure.js,library/poses.json` | generalized | three.js (MIT) |
| `MOVES` | Fight moves | Named moves (jump-back, parry, lunge-shomen, kesa-giri, tsuki, bind, d | `engine/moves.js,library/moves.json` | inherited | own |
| `FOOTLOCK` | Planted feet + weight | Opt-in per film (`"motion": { "lockFeet": true }`): one precomputed pa | `engine/footlock.js,engine/figure.js` | generalized | own |
| `MOCAP` | Motion capture from video | Film a move with a phone → MediaPipe Pose Landmarker (Apache-2.0, CPU) | `tools/mocap.py,tools/mocap_film.py` | generalized | own |
| `REACT` | Reaction layer | Fighters watch each other; delayed threat response (function react) | `engine/main.js` | inherited | own |
| `DRAW` | Sword draw | One blade slides out of the scabbard into the grip, hand on the hilt | `engine/main.js` | preset | own |
| `KUROKO` | KUROKO camera | Automatic operator: rigs (frame/orbit/track/face/anchor/blade), feels  | `engine/kuroko.js,engine/resolve-camera.mjs` | preset | three.js (MIT) |
| `KEYCAM` | Keyframe camera | Hand-made camera paths (pos/look/fov) on smooth curves + shakes | `engine/main.js` | generalized | own |
| `LIBRARY` | Library | Swords from parts, characters on one body, outfits, patterns | `library/,engine/library.js` | preset | own |
| `RENDER` | Renderer | Headless Chrome, frame by frame → MP4; `--still`, `--vertical`, `--fro | `engine/render.mjs,engine/serve.mjs` | generalized | three.js (MIT);ffmpeg (LGPL/GPL, called);Playwright/Chromium (Apache-2.0, dev) |
| `SOUND` | Sound pipeline | Find (Openverse) → check (ffmpeg) → place at cue times → mix; Earshot  | `engine/sound.mjs,assets/sfx/` | generalized | earshot (MIT);ffmpeg (LGPL/GPL, called) |
| `CLASH` | Blade contact + hit-stop | Finds blade-to-blade contact (segment distance, 240 Hz), clash aim so  | `engine/motion.js,engine/motion.html` | preset | own |
| `COMBAT` | Combat layer (shared) | The fight layer of both preview engines, in one module: blade contact  | `engine/combat.js,engine/main.js` | preset | own |
| `AUDIT` | Studio audit (automated QA) | Runs on any film without drawing it: per-frame camera, joints on scree | `tools/audit.mjs,engine/audit-hooks.js` | preset | Playwright/Chromium (Apache-2.0, dev) |
| `STANDARD` | Studio standard | The rules every video must pass, taste + numbers; effects are light, c | `docs/STUDIO-STANDARD.md` | preset | own |
| `GROUNDFX` | Ground FX + afterimages | From the motion alone: dash kick-up, wake line, skid spray, take-off a | `engine/groundfx.js` | generalized | own |
| `CINECAM` | Cinematographer camera (motion pag | `cameraOpts.solver: 2` (subject-relative spring, hard cuts, in-frame / | `engine/motion.js,engine/combat.js` | generalized | own |
| `SYNTHSFX` | Synthesised sword sounds | Our own layered clash (tink + ring + body + paper crinkle), light clas | `tools/synth_sfx.sh,assets/sfx/` | preset | own |
| `EARSHOT` | Earshot sound bank (existing tool) | 252 code-made sound effects (MIT, github.com/Leonxlnx/earshot), each w | `engine/sound.mjs` | preset | own |
| `SONIC` | Sonic sound catalog (SonicGraph v1 | Every sound → one queryable record: measured attributes (length, peak  | `packages/sonic/,foley.mjs` | preset | earshot (MIT) |
| `AIROUTER` | Free model router | Sends writing, code, reasoning and image review to free models (Cerebr | `tools/ai.py` | generalized | own |
| `WORKER` | Free agent worker | Runs the free NVIDIA models in a tool loop (read/write/patch/search/ru | `tools/worker.py` | generalized | own |
| `OMNI` | OmniRoute gateway | Local MIT gateway (github.com/cheaper-inference/OmniRoute) over 400+ m | `tools/omni.sh,tools/ai.py` | inherited | own |
| `AETHERN` | Aethern shared core | The project-independent agent toolkit Paper Cinema now runs on: projec | `packages/aethern/,aethern.json` | preset | own |
| `BLENDERSKILLS` | Blender Skills pack (existing tool | 94 Blender skills for Claude Code (MIT, github.com/arjun988/blender-sk | `.claude/skills/,skills-lock.json` | generalized | own |
| `VOICE` | Voice (spoken lines) | Film `"voice"` lines → Kokoro-82M TTS (Apache-2.0, CPU) → cinematic ch | `tools/voice.py,engine/voice-env.js` | generalized | ffmpeg (LGPL/GPL, called);Kokoro ONNX (Apache-2.0) |
| `THUMB` | Thumbnails | 16:9 + 9:16 from the decisive-blow frame, kanji title, brush swash | `engine/thumbnail.py` | inherited | own |
| `PLAYBOOK` | Playbook page | Interactive page: pipeline, live camera plot, motion and sound timelin | `docs/playbook.template.html,docs/build_playbook.py` | generalized | own |
| `SHIMI` | SHIMI (染み) stain sim | Paint soaking into paper: two water layers, fibres, saturation-limited | `engine/shimi.py` | preset | own |
| `KIZU` | KIZU (傷) wound layer | Decides how paint leaves a cut: onset delay, beads → line, depth/regio | `engine/shimi.py` | inherited | own |
| `LOOKDEV` | Lookdev stages | Sword materials (metal / demonic / ink) | `engine/lookdev.*` | preset | own |
| `BLENDER` | Blender (realistic) | Headless Cycles renders; demon-slash test (cut paper, ink slash, paint | `blender/*.py` | preset | Blender (GPL, called) |
| `BWORLD` | Blender world set (Ganryūjima) | Build-once 3D location: faceted paper island, pines, rocks, Ocean-modi | `blender/world/build_world.py` | preset | own |
| `PAPERMAT` | Paper materials (Blender) | Reusable Lantern Origami shaders: faceted washi (true-normal facets, f | `blender/world/paper_materials.py` | preset | own |
| `SLASHFX` | Slash effects (Blender) | Keyframed crescent slash: tapered folded arc, emissive core (amber hum | `blender/world/slash_fx.py` | preset | own |
| `SETS` | Sets (modular, data-driven, Blende | A location = one JSON in `library/sets/`: kit pieces with positions, s | `blender/sets/kit.py,blender/sets/build_set.py` | preset | own |
| `POLYHAVEN` | Poly Haven layer (CC0 photo textur | Search / download / cache CC0 Poly Haven textures (diffuse, normal GL, | `tools/polyhaven.py,library/polyhaven.json` | preset | own |
| `CHARFACTORY` | Modular origami character factory | A character = one JSON recipe in `library/character-recipes/`: parts p | `blender/character/part_registry.py,blender/character/modular_builder.py` | preset | own |
| `BLENDERFILM` | Blender film render (TRELLIS hero) | The owner's reference character fights in Blender from film data: `too | `tools/export_motion.mjs,blender/character/rig_trellis.py` | preset | own |
| `GPU` | GPU jobs | Rent/run/stop RunPod pods (self-destruct timer); TRELLIS image → 3D | `gpu/*.py` | inherited | own |
| `MODELS` | 3D models | 5 models from reference images (TRELLIS, MIT) | `assets/models/` | inherited | own |
| `ANATOMY` | Anatomy (third-party skill) | Interactive isometric explainer figures (SVG/WebGL), for example "anat | `.claude/skills/anatomy/SKILL.md` | preset | own |
| `STORY` | Story bible | World rules, characters, cursed swords (fiction), episode ideas | `docs/STORY-BIBLE.md` | preset | own |
| `SCENE` | Scene writing | Idea → logline → beat sheet (1 s hook, jo-ha-kyū) → voiced lines with  | `.claude/skills/scene-writing/SKILL.md,library/scene-templates.json` | generalized | own |
| `DIRECTION` | Scene direction | Story beat → shot list → KUROKO rigs / motion-page camera beats → ligh | `.claude/skills/scene-direction/SKILL.md,library/shots.json` | preset | own |
| `RESEARCH` | Research | History with confidence marks | `research/` | inherited | own |
| `EFFECTS` | Effects plan | Face-touch scene, slash v2, anime effects (flash-step, shadow-vanish,  | `docs/EFFECTS-PLAN.md` | inherited | own |
| `FX` | FX post-processing (three.js previ | Deterministic effect stack any page can import: bloom (UnrealBloomPass | `engine/fx.js,engine/fx-demo.html` | generalized | own |
| `ARCH` | Architecture (the six modules) | The shape of the project: one canonical timeline + Timeline Exporter,  | `docs/ARCHITECTURE.md` | preset | own |
| `TIMELINE` | Canonical animation timeline | ONE interchange format every renderer reads: per-frame bone world tran | `tools/timeline.mjs,output/<film>.timeline.json` | preset | own |
| `FIGHTDIR` | Fight Director | The fight pipeline as one verification pass over the contact analysis: | `engine/combat.js` | preset | own |
| `CAMCHECK` | Camera evaluator (Camera Director) | Scores every shot against measurable requirements: subject / weapon /  | `tools/camera_check.mjs,library/shots.json` | generalized | Playwright/Chromium (Apache-2.0, dev) |
| `DAMAGE` | Paper Damage Bridge | The contract between a cut in the film and the paint in the paper: eve | `tools/paper_damage.mjs,engine/shimi.py` | preset | own |
| `RENDERSUP` | Render Supervisor | Renders a film shot by shot from the timeline: one quality-preset tabl | `tools/render_supervisor.mjs,engine/render.mjs` | generalized | own |
| `UEEXPORT` | Unreal export (verified FBX) | Our rigged origami character → an Unreal-ready FBX, with Epic's own Se | `blender/character/export_unreal.py,output/unreal/` | generalized | own |
| `TOOLSEVAL` | Outside-tool evaluation | Nine third-party tools checked against rule 6 (code AND weights read s | `docs/TOOLS-EVALUATED.md,docs/MOCAP-RESEARCH.md` | generalized | own |
| `TRELLIS2` | TRELLIS.2 Kaggle job | Image → 3D with Microsoft TRELLIS.2-4B (code MIT, weights MIT) on Kagg | `gpu/kaggle_trellis2/,blender/character/clay_compare.py` | generalized | own |
| `VYRN` | VYRN perception engine | Processes media once into a cached, queryable SQLite store of timestam | `vyrn/,output/vyrn/` | generalized | OpenCV (Apache-2.0) |

**Counts:** generalized 27, inherited 11, preset 31 (of 69).

## Not in systems.json — also to carry
- Research & plans: `docs/` (AETHERN-AUDIT, INTEGRATION, SONIC, VYRN, CAMERA, DIRECTION, STUDIO-STANDARD, the
  benchmark and token-investigation reports), the private `cinevora/` FORGE and review docs.
- Tests & fixtures: `tests/`, `packages/sonic/tests/`, `vyrn/tests/`, `packages/aethern/tests/`, `tools/test_new_film.mjs`,
  `tools/poc/`, `vyrn/bench/`, the regression report.
- Skills: `.claude/skills/` and the scene-direction / design skills.
- Assets: `assets/`, `library/` (shots, vocab, effects, promises), branding in private `cinevora/branding/`.
- Config & infra: `aethern.json`, `.mcp.json`, `package.json`, the Aethern CLI, worker and router.
- Failed/!-prefixed experiments (`film/_*.json`, pilot outputs): kept as "what not to repeat".

## External technology, sorted (licence to re-verify at source before any adoption)
- **Include (permissive code we could vendor):** earshot (MIT), DDSP (Apache-2.0), Steam Audio (Apache-2.0),
  OpenVDB (Apache-2.0), NVIDIA Warp (Apache-2.0), Motion-Matching (MIT), Kokoro (MIT/Apache). Keep attribution.
- **Call as a tool (not vendored):** Blender (GPL — call via its Python API, never link), ffmpeg (LGPL/GPL — call),
  librosa (ISC), Montreal Forced Aligner, Rhubarb (check).
- **Reimplement from the paper (no usable code / study only):** Disney Scalable Music, FilmComposer, V2M-Zero,
  spacetime constraints, The Virtual Cinematographer; Houdini and Unreal (architecture only, proprietary).
- **Incompatible / restricted for commercial use (do not ship):** MMAudio weights (reported non-commercial),
  HunyuanVideo-Foley (Tencent licence — read territory/use), any BBC/Freesound asset needing its own licence,
  any model whose weights forbid commercial use even when the code is permissive.

_Generated from systems.json on 2026-11-28; the class and generalization notes are a first pass to review._

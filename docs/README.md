# docs/: which guide to read, and when

| Read this | When you are… | It covers |
|---|---|---|
| `../AGENTS.md` | starting any session | Hub: map, commands, rules |
| `../SYSTEMS.md` | looking for where something lives | Every system, its files, guide, command and connections (+ `../systems.json`) |
| `ARCHITECTURE.md` | wanting the shape of the project, or adding a renderer / a module | The six modules around one canonical timeline (Timeline Exporter, Fight Director, Camera Director, Paper Damage Bridge, Render Supervisor, Visual Critic), the code that implements each, the gaps, and where a change goes |
| `TIMELINE-FORMAT.md` | writing or reading `output/<film>.timeline.json` | The one interchange format: coordinates (three.js ↔ Blender, defined once), the 24 fps clock, bones and root motion, the camera with focal length and focus distance, shots and cuts, events with stable ids, lights, assets, the backward-scrub check, coverage per film kind |
| `playbook.html` | learning the pipeline visually | Interactive: 9 steps, live camera plot, motion and sound timeline, new-chat prompt |
| `FILM-FORMAT.md` | writing or editing a film file | Every field of `film/*.json` and the golden path |
| `CAMERA.md` | directing the camera | Keyframes (§1–6), the **KUROKO** automatic operator (§7), motion-page beats with the `compose` framing solver and speed ramps (§8) |
| `DIRECTION.md` | choosing shots, cuts, rhythm and light for a scene | Film grammar (sizes, lenses, 180°/30° rules, coverage, match and J/L cuts), 17 direction styles (Kurosawa, Leone, ufotable, MAPPA…), shots per fight beat, lighting moods, Shorts rules, sources (procedure: `../.claude/skills/scene-direction/SKILL.md`, data: `../library/shots.json`) |
| `STUDIO-STANDARD.md` | making or reviewing ANY video | The rules every video must pass (taste + numbers): hook, staging, beat → camera table, camera moves, composition, timing tables (dash, turn, jump, slash, landing), posing, effects are light, shadow / paper look, cut props, sound and mix, the gate |
| `ARCHITECTURE.md` §Camera Director | choosing a shot, then proving it works | `tools/camera_check.mjs`: visibility, action clarity at the strike frame, size vs intent, 180°/30°, cut timing, camera motion and clearance, emotional fit; rejects with a reason and proposes the nearest passing library shot |
| `AUDIT.md` | about to render, or reviewing a render | The automated studio QA `tools/audit.mjs`: usage, every check with its number and severity, waivers, adding checks or page hooks |
| `AUDIT-dash-test.md` | wanting an example of a full review | The dash-test audit: 27 problems with frames, root causes and fixes, scores before / after, what was built |
| `ANIMATION.md` | making characters move | Skeleton with legs, poses, balance, moves, the draw, two-hand grip, reactions |
| `MOCAP-BENCHMARK.md` | choosing a motion-capture backend | GEM-X / video2mocap / MMPose / our MediaPipe solver measured on the same clip, with the licence verdict of each for monetised video |
| `MOCAP.md` | turning a phone video of a move into motion data | How to film, `tools/mocap.py` options and outputs, how it solves our channels, limits, measured accuracy, clean-up and anime timing on top |
| `VYRN.md` | asking what happens in a video (yours or a reference), checking sound sync on a final render, or adding a perception backend | The VYRN perception engine: commands, the store, the shared event format with Sonic, how each stage works, the audit of existing tools, licences, benchmark, limits |
| `MOCAP-RESEARCH.md` | wanting to improve `tools/mocap.py`, or wondering whether FreeMoCap / RGB MoCap help | Seven techniques read out of the other markerless systems (One Euro filtering, fixed bone lengths, root travel from the planted foot, no smoothing after contacts, pelvis-lock vs foot-lock, interpolating the fast frames, gravity from the image), what ours already does better, and why both of those systems are a no for one phone and a monetised video |
| `STYLE-AND-FIGHT-SYSTEM.md` | deciding how it should look and feel | The Lantern Origami style, the Strike Grammar, lighting, story structure |
| `SHIMI.md` | working on cuts, paint and stains | The slash sequence, SHIMI v2, the **KIZU** wound layer, presets, review, upgrade path |
| `SHIMI-3D.md` | putting stains on 3D characters | UV-space simulation, cut mapping, gravity maps, Blender/three.js shading, milestones |
| `COST.md` | keeping usage low | The four tiers and the free-worker commands |
| `AI-ROUTER.md` | sending work to free models | Which model does which job, speeds, rules |
| `FIX-LIST.md` | fixing stiff motion, silent clashes, framing | The review of what was wrong and the fixes, with status |
| `VOICE.md` | giving characters spoken lines | The `"voice"` schema, voices and licences (Kokoro-82M), directing delivery, the voice chain, ducking, eyes pulsing with the voice |
| `EFFECTS-PLAN.md` | adding effects | The face-touch scene, slash v2, anime effects (flash-step, shadow-vanish…) |
| `EFFECTS-CATALOG.md` | choosing or wiring screen effects | The FX module (`engine/fx.js`): bloom, grade moods, vignette, grain, letterbox, CA flash, speed lines, ink impact, light shafts, particles, glint; film `fx` events; 42-effect catalogue (`library/effects.json`) by story beat |
| `BLENDER-PLAN.md` | doing realistic renders | Blender pipeline, shaders, render costs, milestones M1–M8 |
| `BLENDER-WORLD.md` | filming in the Blender world set, adding slash effects | The Ganryūjima set (run, contents, marks, camera anchors), paper materials, slash library, measured render times |
| `KAGGLE-RENDER.md` | sending a Blender render to the free Kaggle farm, or a Kaggle run that will not finish | `gpu/kaggle_blender/`: the data-driven job, `run.sh pack/push/wait/get`, the heartbeat that survives a kill, and the eight measured runs that say what the cancel 11–18 s into every render is NOT (not the quota, the GPU, memory, disk, the dataset or any render setting) — so `--gpu` refuses and the local render is the one to use |
| `SETS.md` | making a new location (castle, dojo, forest…) or rendering a Blender still with characters in a set | The data-driven set system: write a JSON in `library/sets/`, the kit pieces and their parameters, materials, lighting presets, the Poly Haven layer (CC0 photo textures + HDRI ambient, `tools/polyhaven.py`), 2.5D paper-cut layers, characters on marks, render settings and measured times |
| `CHARACTER-FACTORY.md` | building a character out of folded paper parts, adding a part, or writing a character recipe | The modular origami character factory: the shared skeleton and its joints, the slot and layer table, sockets, how to add and validate a part, the recipe format (including `extends`/`swap` for a second character), the washi material family and the world-scale fibre rule, the nine validation checks and the pose sweep, the locked reference quality target, known weak spots |
| `CHARACTER-BLENDER.md` | rendering a film in Blender with the TRELLIS hero, rigging a TRELLIS model, using motion capture (BVH), or choosing a Blender camera move | The rig and its joint table (ours ↔ standard humanoid), the four skinning ways tested, pose / film / BVH drivers, `tools/export_motion.mjs`, what `film_blender.py` builds (light, slash of light, dust), the beat → camera table and 12 moves, new ideas, weak spots |
| `UNREAL-EXPORT.md` | taking a character or an animation to Unreal, now or the day a GPU machine exists | `blender/character/export_unreal.py`: Epic's own FBX settings table, which exporter actually writes the file (and why send2ue's is broken on Blender 4.5), the UE5 / Mixamo bone-name map, the three files and why they are three, the ten round-trip checks `--verify` runs with their measured values, and the Unreal-side import steps |
| `TOOLS-EVALUATED.md` | before adding ANY outside tool, model or asset | Nine tools checked against rule 6 with code and weights read separately: the licence verdict table, what was installed and tested on what, the Rigger comparison stills, the TRELLIS.2 licence trap (nvdiffrast / nvdiffrec are non-commercial), what is redundant with our own skills, and Fab's five licence pitfalls |
| `STORY-BIBLE.md` | writing a story | World rules, characters, cursed swords (fiction), episode ideas |
| `SCENE-WRITING.md` | writing a scene, monologue or hook | Beats for 30/45/60 s Shorts, lines and voice direction, shot types, taste rules (full procedure: `../.claude/skills/scene-writing/SKILL.md`, templates: `../library/scene-templates.json`) |
| `../research/` | making historical claims | Facts marked documented / tradition / our choice |

Regenerated files (don't edit by hand):
- `playbook.html`: from `playbook.template.html`, via `build_playbook.py`
- `../systems.json`: from `../SYSTEMS.md`, via `../tools/build_systems.py`

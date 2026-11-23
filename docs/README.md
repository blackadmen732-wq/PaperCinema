# docs/: which guide to read, and when

| Read this | When you are… | It covers |
|---|---|---|
| `../AGENTS.md` | starting any session | Hub: map, commands, rules |
| `../SYSTEMS.md` | looking for where something lives | Every system, its files, guide, command and connections (+ `../systems.json`) |
| `playbook.html` | learning the pipeline visually | Interactive: 9 steps, live camera plot, motion and sound timeline, new-chat prompt |
| `FILM-FORMAT.md` | writing or editing a film file | Every field of `film/*.json` and the golden path |
| `CAMERA.md` | directing the camera | Keyframes (§1–6) and the **KUROKO** automatic operator (§7) |
| `DIRECTION.md` | choosing shots, cuts, rhythm and light for a scene | Film grammar (sizes, lenses, 180°/30° rules, coverage, match and J/L cuts), 17 direction styles (Kurosawa, Leone, ufotable, MAPPA…), shots per fight beat, lighting moods, Shorts rules, sources (procedure: `../.claude/skills/scene-direction/SKILL.md`, data: `../library/shots.json`) |
| `ANIMATION.md` | making characters move | Skeleton with legs, poses, balance, moves, the draw, two-hand grip, reactions |
| `STYLE-AND-FIGHT-SYSTEM.md` | deciding how it should look and feel | The Lantern Origami style, the Strike Grammar, lighting, story structure |
| `SHIMI.md` | working on cuts, paint and stains | The slash sequence, SHIMI v2, the **KIZU** wound layer, presets, review, upgrade path |
| `SHIMI-3D.md` | putting stains on 3D characters | UV-space simulation, cut mapping, gravity maps, Blender/three.js shading, milestones |
| `FIX-LIST.md` | fixing stiff motion, silent clashes, framing | The review of what was wrong and the fixes, with status |
| `VOICE.md` | giving characters spoken lines | The `"voice"` schema, voices and licences (Kokoro-82M), directing delivery, the voice chain, ducking, eyes pulsing with the voice |
| `EFFECTS-PLAN.md` | adding effects | The face-touch scene, slash v2, anime effects (flash-step, shadow-vanish…) |
| `EFFECTS-CATALOG.md` | choosing or wiring screen effects | The FX module (`engine/fx.js`): bloom, grade moods, vignette, grain, letterbox, CA flash, speed lines, ink impact, light shafts, particles, glint; film `fx` events; 42-effect catalogue (`library/effects.json`) by story beat |
| `BLENDER-PLAN.md` | doing realistic renders | Blender pipeline, shaders, render costs, milestones M1–M8 |
| `BLENDER-WORLD.md` | filming in the Blender world set, adding slash effects | The Ganryūjima set (run, contents, marks, camera anchors), paper materials, slash library, measured render times |
| `STORY-BIBLE.md` | writing a story | World rules, characters, cursed swords (fiction), episode ideas |
| `SCENE-WRITING.md` | writing a scene, monologue or hook | Beats for 30/45/60 s Shorts, lines and voice direction, shot types, taste rules (full procedure: `../.claude/skills/scene-writing/SKILL.md`, templates: `../library/scene-templates.json`) |
| `../research/` | making historical claims | Facts marked documented / tradition / our choice |

Regenerated files (don't edit by hand):
- `playbook.html`: from `playbook.template.html`, via `build_playbook.py`
- `../systems.json`: from `../SYSTEMS.md`, via `../tools/build_systems.py`

# SKILLS.md — the map

Every skill in this repository, grouped by the job it does. Written for **any** agent: Claude Code
loads `.claude/skills/` by itself, and Codex, Grok, Cursor and anything else can read this page and
then read the one file it points at. Nothing here needs a particular product to be useful.

Read `AGENTS.md` first — it has the rules. This page is where you find the procedure.

## The four skills that carry this project

Read these before anything else. They are the whole of 25-26 Nov compressed, written command-first
for any agent, with the numbers that make each claim checkable and the dead ends that are not worth
re-running.

| skill | when |
|---|---|
| **[`pc-measure`](.claude/skills/pc-measure/SKILL.md)** | **first, and before and after every change.** If the number did not move, the fix did nothing |
| [`pc-character`](.claude/skills/pc-character/SKILL.md) | how the cast is made and why the paper reads as plastic |
| [`pc-animation`](.claude/skills/pc-animation/SKILL.md) | how it moves, captures, and fights |
| [`pc-effects`](.claude/skills/pc-effects/SKILL.md) | how a finished frame looks |

## The order of work

A film goes through these, in this order. Each line is a command you can run now; if a step fails it
says so and stops, and nothing further is worth doing until it passes.

| # | Step | Command | Skill |
|---|---|---|---|
| 1 | Write the film | `node engine/new-film.mjs <name> --jp 漢字 --en TITLE` | [`paper-cinema-film`](.claude/skills/paper-cinema-film/SKILL.md) |
| 2 | Check the file | `node engine/validate.mjs film/<name>.json` | same |
| 3 | Block it out, fast and wrong | `node engine/render.mjs --film film/<name>.json` | same — **boxes, a storyboard, never the deliverable** |
| 4 | **Look at six real frames** | `bash tools/shotsheet.sh film/<name>.json --set <set>` | [`qa-review`](.claude/skills/qa-review/SKILL.md) |
| 4b | Can the audience see it? | `blender -b -P blender/check_sight.py -- --film <name> --set <set>` | — |
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
| What to watch to learn this craft, in order | `docs/WATCH-LIST.md` |

## Four rules that cost people time here

1. **Boxes are not the character, and neither is the TRELLIS mesh.** Four things here can stand in
   for a person and only one is the character: `modular_builder.py` + `part_registry.py`, rendered by
   `blender/film_modular.py`. `engine/figure.js` is a storyboard, `origami_samurai.py` is the
   rejected first attempt, and `rig_trellis.py` is one fused shell whose arms cannot bend. The table
   and the reasons are in `docs/CHARACTER-BLENDER.md` — read it before proposing a fifth.
2. **Every frame is a pure function of time.** `window.renderAt(t)` must draw the same image for the
   same `t`, asked in any order, on any machine. Nothing may accumulate between frames. This is what
   lets frames render in parallel and a still match frame 77.
3. **Review on real frames, never on a model turnaround.** Three bugs shipped into a finished frame
   on 25 Nov - a studio lamp standing in shot, a cast lit for the set instead of for the shot, and a
   key light parented to the actor so it orbited with them like a flashlight. None of the three can
   exist in a turnaround on grey: nothing is ever in shot, nothing is lit by a world, nothing turns.
   `bash tools/shotsheet.sh` is the loop that would have caught all three, and it costs six frames.
4. **A stated fix is a promise.** It goes in `library/promises.json` with a command that proves it,
   the moment it is said. Checks that grep for a filename do not count — one of those passed while
   three films went out with the wrong character.

<!-- generated below this line by tools/build_skills.py -->

## START HERE — the four that carry this project

Everything learned on 25-26 Nov, compressed. Written for ANY agent: command-first, with the measured numbers and the dead ends, so nothing has to be re-derived. Read `pc-measure` first.

| skill | what it is for |
|---|---|
| [`pc-animation`](.claude/skills/pc-animation/SKILL.md) | Motion for Paper Cinema - the 46-channel pose system, the 26-move library, capture from video and CMU, cleaning the tremble out of it, and how a cinematic… |
| [`pc-character`](.claude/skills/pc-character/SKILL.md) | Build, judge and extend the folded-paper character - which of the four character systems is THE one, how parts and recipes work, how to bring in bought or… |
| [`pc-effects`](.claude/skills/pc-effects/SKILL.md) | The look of Paper Cinema - the paper slash, light, compositing, paper damage and ground reaction, and the measured reason frames come out flat. Use for… |
| [`pc-measure`](.claude/skills/pc-measure/SKILL.md) | The measurement discipline for Paper Cinema - every claim has a command that proves it. Use BEFORE and AFTER any change to motion, look, camera or… |
| [`pc-reference-motion`](.claude/skills/pc-reference-motion/SKILL.md) | Turn a reference video of real sword work into a verified Paper Cinema move - measure its real timing with reanimate instead of guessing frame counts, then… |

## The film pipeline

The project itself. The rest is support.

| skill | what it is for |
|---|---|
| [`camera-cinematography`](.claude/skills/camera-cinematography/SKILL.md) | Cinematic camera work in Blender including framing, lenses, composition, camera animation, and shot language beyond basic rendering setup via MCP. |
| [`graphify`](.claude/skills/graphify/SKILL.md) | "Use for any question about a codebase, its architecture, file relationships, or project content — especially when graphify-out/ exists, where the question… |
| [`paper-cinema-film`](.claude/skills/paper-cinema-film/SKILL.md) | Make or change a Lantern Origami sword-duel film in this repo (Paper Cinema). Use whenever the task is a new film, a new fight, camera moves, character… |
| [`qa-review`](.claude/skills/qa-review/SKILL.md) | Production QA gate for Blender assets using viewport screenshots, validation checklists, naming audits, and ship/no-ship verdicts via MCP. |
| [`scene-direction`](.claude/skills/scene-direction/SKILL.md) | Direct a Paper Cinema scene like a film director and anime layout artist - turn a story beat sheet into a shot list, then into KUROKO camera rigs (film… |
| [`scene-writing`](.claude/skills/scene-writing/SKILL.md) | Write the story of a Paper Cinema Short before any JSON is made — the idea, logline, beat sheet for a 30/45/60 s vertical Short with a 1-second hook, voiced… |
| [`vfx-fx`](.claude/skills/vfx-fx/SKILL.md) | Cinematic and game VFX in Blender including smoke, fire, particles, trails, and Geometry Nodes FX setups via MCP. |

## Outside tools (vendor/)

Fetched and pinned by `node tools/vendor.mjs`. Each skill says what it is for HERE and what it must not be used for.

| skill | what it is for |
|---|---|
| [`tool-agent-reach`](.claude/skills/tool-agent-reach/SKILL.md) | Read and search the open web - X/Twitter, Reddit, YouTube, GitHub, Bilibili, XiaoHongShu - from one CLI, no per-platform API keys. Use when the task needs… |
| [`tool-blender-mcp`](.claude/skills/tool-blender-mcp/SKILL.md) | Drive a RUNNING Blender from an AI agent - move objects, set materials, look through the camera, run Python - over MCP. Use for look development and quick… |
| [`tool-cinecode`](.claude/skills/tool-cinecode/SKILL.md) | Reference kit for films built entirely in code - an agent writes the script, renders every frame in headless Chrome and returns an MP4. Read it for… |
| [`tool-hyperframes`](.claude/skills/tool-hyperframes/SKILL.md) | Render HTML, CSS and seekable animation to a deterministic MP4. Use for titles, credits, lower thirds, end cards and any typography - the things that are… |
| [`tool-trellis2`](.claude/skills/tool-trellis2/SKILL.md) | Turn one image into a textured 3D model (GLB) with Microsoft TRELLIS.2. Use for PROPS and set dressing - a lantern, a bridge post, a boat, a rock - from a… |

## Blender, by task

The Scenario pack (MIT). Deep, task-shaped Blender procedure; `scenario-blender-expert` is the way in.

| skill | what it is for |
|---|---|
| [`scenario-blender-animation`](.claude/skills/scenario-blender-animation/SKILL.md) | "Use when animating characters or objects in Blender through Python, a bouncing ball, walk or run cycle, jump, acting shot, lip sync, eye darts or facial… |
| [`scenario-blender-expert`](.claude/skills/scenario-blender-expert/SKILL.md) | "Use when doing any 3D work in Blender through Python or an MCP bridge, headless or in a live session: modeling, sculpting a character or head, retopology,… |
| [`scenario-blender-export`](.claude/skills/scenario-blender-export/SKILL.md) | "Use when exporting a model, character or animation from Blender to a game engine, the web or a 3D printer: FBX, glTF/GLB, USD/USDZ or STL for Unity, Unreal… |
| [`scenario-blender-geometry-nodes`](.claude/skills/scenario-blender-geometry-nodes/SKILL.md) | "Use when building or debugging Geometry Nodes, headless or live: procedural modeling, scattering objects on a surface, arrays along a curve, repeat or… |
| [`scenario-blender-grease-pencil`](.claude/skills/scenario-blender-grease-pencil/SKILL.md) | "Use when drawing or animating with Grease Pencil in Blender 5.x from Python: 2D or 2.5D illustration, frame-by-frame animation, a cutout or part-based 2D… |
| [`scenario-blender-hard-surface`](.claude/skills/scenario-blender-hard-surface/SKILL.md) | "Use when modeling hard-surface objects in Blender (sci-fi panels, props, weapons, vehicles, robots, machined or product parts) with booleans and cutters,… |
| [`scenario-blender-lighting-rendering`](.claude/skills/scenario-blender-lighting-rendering/SKILL.md) | "Use when lighting, rendering or compositing in Blender: light a character, product or hero shot, interior at dusk or night, three-point or motivated… |
| [`scenario-blender-previs-storyboard`](.claude/skills/scenario-blender-previs-storyboard/SKILL.md) | "Use when turning a script or story into previs, layout, storyboards or an animatic in Blender: beats to shot list, camera and lens per shot, staging,… |
| [`scenario-blender-rigging`](.claude/skills/scenario-blender-rigging/SKILL.md) | 'Use when rigging a character, creature or prop in Blender through Python: "rig this character", Rigify metarig fitting or generation errors, automatic… |

## The character

Building, rigging and posing the folded paper cast.

| skill | what it is for |
|---|---|
| [`anatomy`](.claude/skills/anatomy/SKILL.md) | Build crafted, highly detailed, interactive isometric SVG figures that explain a technical idea as a real physical object (a test rig, a dial gauge, a… |
| [`animation`](.claude/skills/animation/SKILL.md) | Game-ready animation in Blender including walk/run/idle cycles, combat, mechanical animation, camera animation, constraints, Graph Editor, and NLA workflows… |
| [`blender-modeler`](.claude/skills/blender-modeler/SKILL.md) | Core Blender modeling specialist for Edit Mode, modifiers, collections, precision modeling, and scene organization. Use for general 3D modeling, blockouts,… |
| [`character-archetypes`](.claude/skills/character-archetypes/SKILL.md) | Character archetype art direction for Blender covering fantasy races, horror creatures, roles (knight, assassin, detective), and body types (mecha, android,… |
| [`character-artist`](.claude/skills/character-artist/SKILL.md) | AAA character modeling for human anatomy, stylization, facial topology, clothing, hair, and animation-ready meshes. Use for game characters, facial… |
| [`cloth-sim`](.claude/skills/cloth-sim/SKILL.md) | Garment blockout, cloth simulation, pin groups, and bake to shape keys or caches for characters and props in Blender via MCP. |
| [`creature-artist`](.claude/skills/creature-artist/SKILL.md) | AAA creature modeling for fantasy, aliens, monsters, and organic creature design with believable anatomy and movement. Use for creature blockouts, muscle… |
| [`hair-groom`](.claude/skills/hair-groom/SKILL.md) | Hair and fur grooming in Blender using curves, particle hair, geometry nodes, and game hair-card workflows. Use for characters, creatures, and real-time… |
| [`retopology`](.claude/skills/retopology/SKILL.md) | Production retopology for animation-ready, low-poly, quad-dominant meshes with proper edge loops and efficient polygon flow. Use after sculpting or… |
| [`rigging`](.claude/skills/rigging/SKILL.md) | Production rigging in Blender with armatures, IK/FK, constraints, weight painting, mechanical rigs, facial rigs, and drivers. Use before animation on… |
| [`sculpting`](.claude/skills/sculpting/SKILL.md) | Blender sculpting for organic and hard surface detail using Dyntopo, multiresolution, brushes, alpha workflow, wrinkles, and damage. Use when high-frequency… |

## The shot

Light it, shade it, render it, put it together.

| skill | what it is for |
|---|---|
| [`compositing`](.claude/skills/compositing/SKILL.md) | Blender compositor workflows for beauty stacks, render passes, color grade, glare, and delivery outputs via MCP. |
| [`lighting`](.claude/skills/lighting/SKILL.md) | Cinematic and game lighting in Blender including three-point lighting, HDRI, horror lighting, volumetrics, rim lighting, and mood-driven illumination. Use… |
| [`lookdev`](.claude/skills/lookdev/SKILL.md) | Look development loop for Blender assets combining materials, lighting, camera, and screenshot comparison until shading reads correctly via MCP. |
| [`materials`](.claude/skills/materials/SKILL.md) | Blender PBR and stylized material creation for metal, wood, concrete, fabric, glass, dirt, rust, and procedural shaders. Use for look development, material… |
| [`physics-sim`](.claude/skills/physics-sim/SKILL.md) | Rigid body, soft body, and destruction setups in Blender including constraints, cell fracture debris, and baked caches via MCP. |
| [`rendering`](.claude/skills/rendering/SKILL.md) | Blender rendering with Cycles and Eevee including sampling, denoising, camera setup, render passes, color management, and render optimization. Use for final… |
| [`scene-assembly`](.claude/skills/scene-assembly/SKILL.md) | Large scene layout in Blender with collections, linking, overrides, streaming-friendly organization, and set assembly via MCP. |
| [`set-dressing`](.claude/skills/set-dressing/SKILL.md) | Set dressing and environmental storytelling placement for interiors and exteriors using prop density, narrative clusters, and readability rules via MCP. |
| [`texture-workflow`](.claude/skills/texture-workflow/SKILL.md) | Production texture workflow for atlases, baking AO/curvature/normal/roughness maps, decals, and texture memory optimization. Use for game-ready texture… |
| [`uv-workflow`](.claude/skills/uv-workflow/SKILL.md) | Production UV unwrapping for seam placement, UV packing, texel density, UDIM, lightmap UVs, and modular UV layouts. Use when preparing meshes for texturing… |

## The world

Sets, props and everything the duel stands in.

| skill | what it is for |
|---|---|
| [`apocalypse-worlds`](.claude/skills/apocalypse-worlds/SKILL.md) | Apocalyptic and dystopian world art direction for Blender including post-apocalyptic, zombie, alien invasion, post-human, dystopian, and utopian contrast sets. |
| [`archviz`](.claude/skills/archviz/SKILL.md) | Architectural visualization in Blender for interiors/exteriors with real-world scale, camera composition, PBR materials, and still/animation delivery via MCP. |
| [`biome-worlds`](.claude/skills/biome-worlds/SKILL.md) | Biome and setting art direction for Blender covering underwater, desert, arctic, jungle, underground, and floating-island environments. |
| [`environment-artist`](.claude/skills/environment-artist/SKILL.md) | AAA environment art for modular kits, buildings, terrain, vegetation, architecture, and scene composition. Use for game-optimized environments, storytelling… |
| [`fantasy-worlds`](.claude/skills/fantasy-worlds/SKILL.md) | Fantasy world-building art direction for Blender covering medieval, high fantasy, dark fantasy, and urban fantasy asset language. |
| [`geometry-nodes`](.claude/skills/geometry-nodes/SKILL.md) | Blender Geometry Nodes for procedural modeling, scatter systems, vegetation, buildings, pipes, cables, and reusable node groups. Use for procedural asset… |
| [`hard-surface`](.claude/skills/hard-surface/SKILL.md) | AAA hard surface modeling for sci-fi, industrial, military, vehicles, weapons, robotics, and mechanical props. Use for boolean/bevel workflows, panel lines,… |
| [`historical-worlds`](.claude/skills/historical-worlds/SKILL.md) | Historical and period world art direction for Blender including Western, pirate, samurai/ninja, Viking, ancient Egypt/Greece/Rome, Victorian, modern, and… |
| [`procedural-modeling`](.claude/skills/procedural-modeling/SKILL.md) | Procedural asset creation for rocks, buildings, vegetation, roads, terrain, pipes, cables, and sci-fi panels using Geometry Nodes and modifier-based… |
| [`prop-artist`](.claude/skills/prop-artist/SKILL.md) | Everyday and hero prop modeling for furniture, tools, household objects, kitbash parts, and readable game props. Use when hard-surface is too… |
| [`sci-fi-punk-worlds`](.claude/skills/sci-fi-punk-worlds/SKILL.md) | Sci-fi and punk world art direction for Blender including hard sci-fi, space, cyberpunk, steampunk, dieselpunk, atompunk, solarpunk, biopunk, and clockpunk. |
| [`vegetation-artist`](.claude/skills/vegetation-artist/SKILL.md) | Vegetation and foliage authoring for Blender including trees, plants, grass cards, canopy LODs, and game-friendly leaf atlases via MCP. |
| [`vehicle-artist`](.claude/skills/vehicle-artist/SKILL.md) | Dedicated vehicle modeling for cars, trucks, aircraft, ships, boats, mechs, and transit assets with proportion, panel flow, and game LOD awareness in… |

## Look and mood

Art direction. Paper Cinema is `anime-style` + `stop-motion-craft-style` + `minimalist-style`; the rest are there to be borrowed from, not followed.

| skill | what it is for |
|---|---|
| [`analog-found-footage-horror`](.claude/skills/analog-found-footage-horror/SKILL.md) | Analog, VHS, CRT, and found-footage horror aesthetics for Blender shots including camera imperfections and documentary framing. |
| [`anime-style`](.claude/skills/anime-style/SKILL.md) | Anime and cel-shaded art direction for Blender with hard color breaks, toon shaders, clean silhouettes, and anime proportion language. |
| [`body-horror-style`](.claude/skills/body-horror-style/SKILL.md) | Body horror art direction for Blender focusing on flesh wrongness, mutation, fusion, and visceral material storytelling. |
| [`brutalist-mood`](.claude/skills/brutalist-mood/SKILL.md) | Brutalist and concrete-monument mood direction for Blender architecture and scenes with raw concrete, monumental scale, and austere composition. |
| [`cartoon-style`](.claude/skills/cartoon-style/SKILL.md) | Cartoon art direction for Blender with squash-stretch readable shapes, bold colors, and graphic silhouettes for games and animation. |
| [`chibi-style`](.claude/skills/chibi-style/SKILL.md) | Chibi and SD proportion art direction for Blender characters with oversized heads, simplified anatomy, and cute silhouette rules. |
| [`comic-book-style`](.claude/skills/comic-book-style/SKILL.md) | Comic book and graphic-novel art direction for Blender with ink-line emphasis, halftone cues, and high-contrast framing. |
| [`cosmic-eldritch-horror`](.claude/skills/cosmic-eldritch-horror/SKILL.md) | Cosmic, eldritch, and Lovecraftian horror art direction for Blender with non-Euclidean cues, impossible scale, and incomprehensible forms. |
| [`cozy-wholesome-mood`](.claude/skills/cozy-wholesome-mood/SKILL.md) | Cozy, cute, wholesome, relaxing, and peaceful mood direction for Blender assets and scenes. |
| [`dark-gritty-mood`](.claude/skills/dark-gritty-mood/SKILL.md) | Dark, grim, gritty, rusty, abandoned, decayed, industrial, lonely, and melancholic mood direction for Blender. |
| [`dream-surreal-mood`](.claude/skills/dream-surreal-mood/SKILL.md) | Dreamlike, surreal, mysterious, mystical, hopeful, and chaotic mood direction for Blender scenes. |
| [`dream-weirdcore-style`](.claude/skills/dream-weirdcore-style/SKILL.md) | Dreamcore, weirdcore, and traumacore-inspired art direction for Blender with nostalgic wrongness, liminal nostalgia, and surreal childhood spaces. |
| [`folk-horror-style`](.claude/skills/folk-horror-style/SKILL.md) | Folk horror art direction for Blender with rural ritual uncanny, pastoral daylight dread, and community-wrongness storytelling. |
| [`frutiger-aero-style`](.claude/skills/frutiger-aero-style/SKILL.md) | Frutiger Aero art direction for Blender with glossy skeuomorphism, aqua UI cues, nature-tech optimism, and mid-2000s futurism. |
| [`hand-painted-style`](.claude/skills/hand-painted-style/SKILL.md) | Hand-painted texture art direction for Blender with brushwork albedo, soft value transitions, and stylized PBR restraint. |
| [`hd-2d-style`](.claude/skills/hd-2d-style/SKILL.md) | HD-2D art direction combining pixel characters/sprites with 3D environments, depth of field, and theatrical lighting. |
| [`horror-style`](.claude/skills/horror-style/SKILL.md) | Psychological horror art direction for Blender assets inspired by Silent Hill, Resident Evil, Chilla's Art, Fear to Fathom, and Iron Lung. Use for sparse… |
| [`indie-horror-aesthetics`](.claude/skills/indie-horror-aesthetics/SKILL.md) | Indie horror aesthetic pack for Blender covering Silent Hill, Fear to Fathom, Puppet Combo, corporate horror, cabin/forest/hospital horror, and related looks. |
| [`isometric-style`](.claude/skills/isometric-style/SKILL.md) | Isometric and strategy-game art direction for Blender including diorama framing, true-iso camera setup, readable silhouettes, and tile asset rules. |
| [`liminal-space-style`](.claude/skills/liminal-space-style/SKILL.md) | Liminal space and Backrooms art direction for Blender with empty transitional architecture, wrong familiarity, and endless repetition. |
| [`lowpoly-style`](.claude/skills/lowpoly-style/SKILL.md) | Low-poly art direction for Blender inspired by PS1/PS2, Lethal Company, Mouthwashing, and Fear to Fathom. Use for readable silhouettes, minimal polygons,… |
| [`manga-style`](.claude/skills/manga-style/SKILL.md) | Manga-inspired art direction for Blender emphasizing monochrome value design, speed lines, screentone feel, and manga panel staging. |
| [`mascot-puppet-horror`](.claude/skills/mascot-puppet-horror/SKILL.md) | Mascot and puppet horror art direction for Blender with cheerful brand characters made wrong, felt/foam materials, and uncanny performance. |
| [`minimalist-style`](.claude/skills/minimalist-style/SKILL.md) | Minimalist and abstract-leaning art direction for Blender with reduced forms, limited palettes, and negative space. |
| [`neon-retrofuturism`](.claude/skills/neon-retrofuturism/SKILL.md) | Neon, vaporwave, synthwave, and retrofuturistic mood/art direction for Blender with grid horizons, chrome, and dusk palettes. |
| [`noir-style`](.claude/skills/noir-style/SKILL.md) | Noir art direction for Blender with high-contrast lighting, wet streets, silhouettes, and monochrome or limited-color grading. |
| [`painterly-style`](.claude/skills/painterly-style/SKILL.md) | Painterly art direction spanning watercolor and oil-painting looks for Blender using soft edges, pigment texture, and illustrative lighting. |
| [`pixel-art-style`](.claude/skills/pixel-art-style/SKILL.md) | Pixel-art and texel-constrained art direction for Blender assets destined for pixel rendering, low-res textures, or HD-2D-adjacent pixel reads. |
| [`psx-horror-style`](.claude/skills/psx-horror-style/SKILL.md) | PS1/PSX-era horror art direction combining low-poly affine textures, limited color depth, fog, and psychological horror staging for Blender assets. |
| [`realistic-style`](.claude/skills/realistic-style/SKILL.md) | Photorealistic AAA art direction for Blender including photogrammetry cleanup, real-world scale, high-poly workflows, PBR accuracy, and scan optimization.… |
| [`retro-16bit-style`](.claude/skills/retro-16bit-style/SKILL.md) | Retro 16-bit art direction for Blender-assisted SNES/Genesis-era color richness, dither cues, and sprite-like clarity. |
| [`retro-8bit-style`](.claude/skills/retro-8bit-style/SKILL.md) | Retro 8-bit art direction for Blender-assisted pixel/low-res aesthetics inspired by NES-era constraints. |
| [`stop-motion-craft-style`](.claude/skills/stop-motion-craft-style/SKILL.md) | Stop-motion and craft aesthetics for Blender including claymation, paper craft, and handmade physical-material cues. |
| [`stylized-style`](.claude/skills/stylized-style/SKILL.md) | Stylized art direction for Blender with shape language, exaggeration, color harmony, NPR rendering, and hand-painted asset workflows. Use for… |
| [`vector-style`](.claude/skills/vector-style/SKILL.md) | Vector-clean art direction for Blender with flat fills, sharp silhouettes, and UI-like graphic clarity. |
| [`visual-console-eras`](.claude/skills/visual-console-eras/SKILL.md) | Visual era art direction for Blender covering PS1–PS5 stylistic cues, retro arcade, DOS, CRT, VHS, and film-grain presentation. |
| [`voxel-style`](.claude/skills/voxel-style/SKILL.md) | Voxel and Minecraft-adjacent art direction for Blender with block grid modeling, limited palettes, and chunk-friendly assets. |

## Getting assets out

Export, optimise, ship to an engine.

| skill | what it is for |
|---|---|
| [`asset-optimization`](.claude/skills/asset-optimization/SKILL.md) | Validates and optimizes Blender assets for polycount, topology, UV efficiency, material count, naming, collections, and game-ready performance. Use before… |
| [`collision-proxy`](.claude/skills/collision-proxy/SKILL.md) | Collision proxy authoring for games including UCX/UHX naming, convex hulls, capsules, and simple collider meshes in Blender via MCP. |
| [`export-pipeline`](.claude/skills/export-pipeline/SKILL.md) | Production export from Blender to FBX, GLTF, OBJ, USD, and Alembic with scale, pivot, rotation, normals, materials, animation, and collision verification… |
| [`godot-export`](.claude/skills/godot-export/SKILL.md) | Godot-specific Blender export favoring GLTF/GLB with correct scale, materials, animation clips, and collision shapes via MCP. |
| [`lod-pipeline`](.claude/skills/lod-pipeline/SKILL.md) | Dedicated LOD generation, naming, screen-size targets, and validation for game meshes in Blender via MCP. |
| [`unity-export`](.claude/skills/unity-export/SKILL.md) | Unity-specific Blender export for scale, axis, materials, humanoid/generic rigs, LODs, and collision import via MCP. |
| [`unreal-export`](.claude/skills/unreal-export/SKILL.md) | Unreal Engine-specific Blender export for FBX scale, LODs, UCX collision, sockets, materials, and skeletal mesh workflows via MCP. |

## Game genres (imported, unused here)

From the Scenario pack. Paper Cinema makes films, not games; these stay because they are good reference for action staging and pacing.

| skill | what it is for |
|---|---|
| [`genre-action-combat`](.claude/skills/genre-action-combat/SKILL.md) | Art direction for action, hack-and-slash, beat 'em up, and fighting-game readable combat spaces and prop language in Blender. |
| [`genre-card-party-idle`](.claude/skills/genre-card-party-idle/SKILL.md) | Art direction for card games, deck builders, party games, idle/incremental, educational, and rhythm game presentational spaces in Blender. |
| [`genre-metroidvania-roguelike`](.claude/skills/genre-metroidvania-roguelike/SKILL.md) | Art direction for metroidvania, roguelike, and roguelite games in Blender with biome gates, room modules, and run-readable props. |
| [`genre-narrative-vn`](.claude/skills/genre-narrative-vn/SKILL.md) | Art direction for visual novel, interactive movie, walking simulator, and story-driven presentation spaces in Blender. |
| [`genre-open-world-sandbox`](.claude/skills/genre-open-world-sandbox/SKILL.md) | Art direction for open world and sandbox games in Blender with biome landmarks, traversable scale, and discovery props. |
| [`genre-puzzle-platformer`](.claude/skills/genre-puzzle-platformer/SKILL.md) | Art direction for puzzle and platformer games in Blender with readable interactables, jump volumes, and clear hazard language. |
| [`genre-racing-sports`](.claude/skills/genre-racing-sports/SKILL.md) | Art direction for racing and sports games in Blender with track landmarks, stadium kits, and high-speed readability. |
| [`genre-rpg`](.claude/skills/genre-rpg/SKILL.md) | Art direction for RPG, JRPG, CRPG, ARPG, and MMORPG worlds in Blender including loot rarity reads and region identity. |
| [`genre-shooter`](.claude/skills/genre-shooter/SKILL.md) | Art direction for FPS, TPS, shooter, battle royale, and extraction-shooter maps and props in Blender with sightline and cover language. |
| [`genre-soulslike`](.claude/skills/genre-soulslike/SKILL.md) | Art direction for soulslike games in Blender with monumental melancholy spaces, fog gates, bonfire landmarks, and lethal readability. |
| [`genre-stealth`](.claude/skills/genre-stealth/SKILL.md) | Art direction for stealth-game spaces in Blender with shadow volumes, patrol-friendly layouts, and concealment materials. |
| [`genre-strategy-sim`](.claude/skills/genre-strategy-sim/SKILL.md) | Art direction for strategy, RTS, turn-based strategy, tower defense, MOBA, city builder, colony sim, and simulation games in Blender. |
| [`genre-survival`](.claude/skills/genre-survival/SKILL.md) | Art direction for survival and survival-horror gameplay spaces in Blender emphasizing resource props, crafting readability, and tension routes. |

## Not grouped yet

Add them to GROUPS in `tools/build_skills.py` when you touch them.

| skill | what it is for |
|---|---|
| [`buy-the-geometry`](.claude/skills/buy-the-geometry/SKILL.md) | Turn a bought or AI-generated mesh (Tripo, Meshy, Rodin, Hunyuan3D-Part, or any GLB/FBX/OBJ) into a Paper Cinema character part - on a socket, on a bone, mad… |
| [`reanimate`](.claude/skills/reanimate/SKILL.md) | Clone a section, widget, page or animation from any reference (a live website URL, a screen recording, an mp4/mov/webm, a gif, a Lottie file, a prototype exp… |

---
119 skills. Generated by `python3 tools/build_skills.py` — do not edit below the marker.


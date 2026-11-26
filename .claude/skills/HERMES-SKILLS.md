# Skills brought in from Hermes Agent (Nov 26)

Mark, Nov 26: "bring the skills into our sessions". Source: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent),
MIT licence (`HERMES-SKILLS-LICENSE` beside this file), commit `04be1bc06ba9fb3a7326679b0036bb65daaeda85`, pinned in
`vendor/MANIFEST.json` as `hermes-agent`. Every file of each skill was read before it was added; the scripts' network hosts
were listed and checked.

| skill | from | why it is here | what changed |
|---|---|---|---|
| `comfyui` | `optional-skills/creative/comfyui` | AI images, video, audio and 3D (covers, concept art, textures, image-to-3D) | Claude Code note + description; `tests/` left out. Hosts: 127.0.0.1, cloud / platform / registry.comfy.org only |
| `heartmula` | `optional-skills/creative/heartmula` | open-source music (Apache-2.0 models): Episode 1 has no music | note + description (GPU, cost, model terms) |
| `youtube-content` | `skills/media/youtube-content` | transcripts of reference videos | note: `pip install youtube-transcript-api`, the Hermes package-manager setup does not apply; youtube.com must be reachable |
| `creative-ideation` | `optional-skills/creative/creative-ideation` | episode ideas, hooks, twists | note + description |
| `humanizer` | `skills/creative/humanizer` | captions and titles that do not read as AI | note + description; its own `LICENSE` (blader/humanizer, MIT) kept |

Every note maps the Hermes tool names to Claude Code (`terminal` = Bash, `read_file` = Read, `write_file`/`patch` =
Write/Edit, `vision_analyze` = Read the image, `image_generate` = not here).

**Read and left out:** `unreal-mcp` (needs Unreal Editor 5.8+ running on a GPU machine), `auteur` (web pages, not films),
`kanban-video-orchestrator` (runs only inside Hermes's own kanban and profiles), `manim-video` (maths explainers),
`ai-presenter-video` (talking-head presenters), `songwriting-and-ai-music` (song lyrics and Suno prompts; the films need
scores), `hyperframes` (already here as `tool-hyperframes`).

To update one: `node tools/vendor.mjs hermes-agent` at a new pinned commit, read the diff, copy, keep the note.

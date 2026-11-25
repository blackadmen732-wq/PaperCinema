---
name: tool-hyperframes
description: Render HTML, CSS and seekable animation to a deterministic MP4. Use for titles, credits, lower thirds, end cards and any typography - the things that are painful in three.js and easy in CSS. Apache-2.0, no per-render fee.
---

# HyperFrames — type and titles, rendered deterministically

Apache-2.0. Node 22+ and ffmpeg. Pinned in `vendor/MANIFEST.json`; fetch with
`node tools/vendor.mjs hyperframes` (clone with `GIT_LFS_SKIP_SMUDGE=1`; the tree is ~344 MB).
Upstream: https://github.com/heygen-com/hyperframes · its agent instructions:
`vendor/hyperframes/AGENTS.md` · its own skills: `vendor/hyperframes/skills/`.

## Why this one and not Remotion

Remotion is the better-known tool and does the same job. It is free for individuals and teams up to
three people, and then charges per developer seat for a company. AGENTS.md rule 6: nothing in this
project may put a licence condition on work that gets sold. HyperFrames is Apache-2.0 with no
per-render fee and no commercial threshold, writes HTML instead of React components, and is
deterministic — same input, same frames, every time, which is the same rule the rest of this
pipeline lives by. So it is the one that is vendored. Revideo (MIT) is the other clean option if
HyperFrames ever stops fitting.

## What it is for here

Titles, the card at the end, credits, a chapter heading, a subtitle burn-in. Laying out a line of
Japanese and a line of English, kerned, with a rule between them and a fade, is twenty minutes of
CSS and a bad afternoon in three.js. Everything that is *the world* — characters, water, the moon,
the fight — stays in the engine. HyperFrames composites over it.

## Use

```bash
cd vendor/hyperframes && npx hyperframes init ../../output/titles/<name>
```

```bash
npx hyperframes preview
```

```bash
npx hyperframes render
```

`preview` opens it live in a browser; `render` writes the MP4. `npx hyperframes skills update`
installs its own agent skills if you want its authoring help inside your agent.

## Fitting it to a film

1. Match the film's frame rate and size from `film/<name>.json` (`fps`, `width`, `height`) — a title
   at 30 fps over a 24 fps film will judder, and nothing will tell you why.
2. Render with alpha where it sits over the film; render opaque where it stands alone.
3. Join it in the same ffmpeg step the film already uses, not in a second pass with its own
   settings. One encode, one colour pipeline.
4. Keep the title's source project in `output/titles/<name>/` and its text in the film's own JSON,
   so the words live with the film and not in a folder nobody opens.

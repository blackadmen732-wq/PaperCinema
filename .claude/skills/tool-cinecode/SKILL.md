---
name: tool-cinecode
description: Reference kit for films built entirely in code - an agent writes the script, renders every frame in headless Chrome and returns an MP4. Read it for structure, titling and sound practice. It is a sibling to this project's engine, not a replacement for it.
---

# cinecode — the same bet, made by someone else

MIT. Pinned in `vendor/MANIFEST.json`; fetch with `node tools/vendor.mjs cinecode`.
Upstream: https://github.com/sarpstar/cinecode · English README: `vendor/cinecode/README.en.md` ·
its own agent instructions: `vendor/cinecode/AGENTS.md` and `vendor/cinecode/SKILL.md`.

## Why it is here

cinecode makes films the same way this project does: code draws every frame, headless Chrome renders
them, ffmpeg joins them. Nobody generates video with a model. That is the bet Paper Cinema already
made, built independently and in the open — which makes it the most useful thing in `vendor/` to
read, because it shows what the parts of this pipeline look like when someone else solves them.

Worth reading for:

- `vendor/cinecode/templates/` and `styles/` — how a look is made reusable instead of re-typed
- its sound work — music and effects authored beside the film, the gap this project still has
- `vendor/cinecode/SKILL.md` — a working example of a kit written so several different agents can
  run it, which is exactly what Mark asked this project's skills to become

## What NOT to do with it

Do not point it at a Paper Cinema film. It writes its own frames its own way; this project's films
are `film/<name>.json` driving `engine/`, with a canonical timeline every renderer reads. Two engines
making the same film is how a project ends up with three character systems again.

If you want to make a film **with** cinecode — a different film, a trailer, an explainer — install it
on its own, in its own folder, per its README: in Claude Code, "Install the cinecode skill from
https://github.com/sarpstar/cinecode". It installs into `~/.claude/skills/cinecode`. Keep one copy.

## Borrowing from it, properly

MIT means you may lift code if you keep the copyright line. When you do:

1. Copy it into this project's own file, with a comment saying where it came from and its licence.
2. Make it fit this engine's rule — **every frame is a pure function of time**. Anything that
   accumulates state between frames cannot come in; a still at 3.2 s has to match frame 77.
3. Record it in `library/promises.json` if it was promised, and in the file's own header if not.

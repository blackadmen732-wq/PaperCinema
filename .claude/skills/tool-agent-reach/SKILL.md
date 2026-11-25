---
name: tool-agent-reach
description: Read and search the open web - X/Twitter, Reddit, YouTube, GitHub, Bilibili, XiaoHongShu - from one CLI, no per-platform API keys. Use when the task needs real reference (a fight clip, a camera move, how a studio did a shot, what a repo actually does) rather than memory.
---

# Agent Reach — reference hunting

MIT. Python 3.10+. Pinned in `vendor/MANIFEST.json`; fetch with `node tools/vendor.mjs agent-reach`.
Upstream: https://github.com/Panniantong/Agent-Reach · English docs: `vendor/agent-reach/docs/README_en.md` ·
machine-readable summary: `vendor/agent-reach/llms.txt`.

## When to reach for this

Every good thing in this project came from looking at something real: the kesa-giri arc came from
footage, the hat silhouette from photographs, the cloth drag from watching a sleeve. Use it when the
task is **"find out how this actually looks or works"**, not when you already have the answer.

- a fight beat, a camera move or a transition you need to reverse-engineer → find the clip, read the
  comments, get the timestamps
- a repo someone recommended → read its README and issues before vendoring it
- "is this tool any good" → read what people who used it say, not the landing page

Do **not** use it to fetch something a plain web fetch already gives you, and never put Mark's name,
email or anything about this project into a query.

## Install (once per machine)

```bash
pip install "git+https://github.com/Panniantong/Agent-Reach@8d9ecc1f5521fe7d223cde782aaa4005695e2671"
```

```bash
agent-reach install --env=auto
```

Credentials, when a platform needs them, go in `~/.agent-reach/config.yaml` (mode 600). **Never** in a
file in this repository — AGENTS.md rule 7.

## Use

```bash
agent-reach --help
```

The CLI is the interface; `--help` is current and this file is not, so read it before guessing flags.
Work in this order: search for candidates, read the two or three that look right, then write down
what you learned in the doc that needed it. A reference you did not write down is a reference you
will fetch again.

## What it costs you

Nothing in money. It costs **trust**: the MIT licence covers the code, not the platforms. Each one has
its own terms about scraping and re-publishing. Read for reference; do not re-publish what you pull,
and do not build a product on top of someone else's feed.

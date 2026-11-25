---
name: tool-blender-mcp
description: Drive a RUNNING Blender from an AI agent - move objects, set materials, look through the camera, run Python - over MCP. Use for look development and quick checks on a machine with Blender open. Films stay scripted.
---

# Blender MCP — hands inside a live Blender

MIT. Pinned in `vendor/MANIFEST.json`; fetch with `node tools/vendor.mjs mcp-for-blender`.
Upstream: https://github.com/ahujasid/mcp-for-blender (formerly `blender-mcp`; the PyPI package is
now `mcp-for-blender`, old configs keep working). Third-party — not made by the Blender Foundation.

## What it is, and the one thing it is not

An MCP server plus a Blender add-on. The agent asks, the add-on does it in the open Blender window,
and the agent can look through the camera to see what happened. That loop — change something, look,
change it again — is what look development is, and it is miserable to do by writing a script and
re-running it.

It is **not** how films get made here. A film has to render the same way twice, on any machine, in
any frame order; that is `blender/film_modular.py` reading the canonical timeline. Anything you
discover through MCP gets written back into a script or a recipe, or it did not happen.

## It needs a Blender window, which this container does not have

This is a headless cloud container. Blender runs here with `-b` (background) only, so the add-on has
nothing to attach to. Run this on Mark's own machine, with Blender open.

## Install (on the machine with Blender)

macOS / Linux:

```bash
curl -LsSf https://www.mcp-for-blender.com/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://www.mcp-for-blender.com/install.ps1 | iex
```

It installs `uv` if missing, finds the MCP clients on the machine (Claude Desktop, Claude Code,
Codex, Cursor, VS Code, Windsurf, OpenCode, Antigravity), lets you pick, installs the Blender add-on
and enables it. It only adds a `blender` entry to each config and keeps a `.bak`. Then **fully quit
and reopen the AI app**, and open Blender — the add-on starts its server with Blender.

Already have `uv`? `uvx mcp-for-blender setup` does the same without the script.

## Use it for

- look development: light a shot, judge it, adjust — the thing a still-render loop is too slow for
- a sanity check on a `.blend` the pipeline produced, from several angles
- working out *how* to do something in Blender Python, which then gets written into a script here

## The warning that matters

Blender.org's own advisory: this server runs LLM-written Python inside Blender with no sandbox. It
can delete things and it can read things. Open it on a scratch file, not on work you cannot
reproduce, and save first. In this project everything is rebuilt from scripts and recipes, so the
blast radius is small — keep it that way by never pointing it at the only copy of anything.

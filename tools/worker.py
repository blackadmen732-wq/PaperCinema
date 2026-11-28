#!/usr/bin/env python3
"""FREE WORKER: gives the free models (NVIDIA Nemotron 550B, Kimi, Qwen) real tools, so they do the
heavy work instead of Claude agents. Costs nothing — the environment's proxy supplies the keys.

  python3 tools/worker.py "Add a docstring to every function in tools/polyhaven.py"
  python3 tools/worker.py --task-file brief.md --steps 40
  python3 tools/worker.py --model kimi "Find why film/x.json fails validate.mjs and fix it"
  python3 tools/worker.py --dry "..."            # show what it WOULD run, change nothing

How it works: the model is given a task and a small set of tools (read, write, list, search, run, look).
It answers with one JSON tool call per step; this script runs it, feeds the result back, and loops until
the model says DONE or the step budget runs out. A transcript lands in output/worker/<stamp>.md.

Safety (this runs unattended, so it is deliberately narrow):
  * every path must stay inside the repo
  * `run` uses an allow-list of commands, a timeout, and never a shell pipeline that deletes
  * writes are refused for AGENTS.md, .git/, gpu/ credentials and anything outside the repo
  * --dry shows the plan without touching anything
  * also refused now: find -delete, git clean, git reset --hard, git checkout -- , git push

The worker itself now lives in the shared core, packages/aethern/aethern/worker.py, configured by
aethern.json (project line, protected files, log folder). It gained one tool, `map`, which answers
from systems.json, so a worker orients in one call instead of reading SYSTEMS.md.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'packages', 'aethern'))
from aethern import config as _config, worker as _worker  # noqa: E402
from aethern.worker import ALLOW, DENY_RE, TOOLS, extract  # noqa: E402,F401  (kept importable)

LOGDIR = os.path.join(REPO, 'output', 'worker')


def main():
    _worker.main(worker=_worker.Worker(_config.load(REPO)), prog='tools/worker.py')


if __name__ == '__main__':
    main()

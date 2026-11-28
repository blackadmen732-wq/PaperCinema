#!/usr/bin/env python3
"""AI ROUTER: send heavy work to free models, keep Claude usage for direction.

  python3 tools/ai.py write "A 20 s ronin monologue before a duel"        # text/story/code
  python3 tools/ai.py review output/stills/x.png "worst 3 problems?"      # look at an image
  python3 tools/ai.py review output/frames-dt --sheet 12 "rate the dash"  # a folder → contact sheet
  python3 tools/ai.py think "why does the dash read as sliding?"          # hard reasoning
  python3 tools/ai.py list                                                # what is reachable, with speeds
  python3 tools/ai.py --model nemotron write "..."                        # force one model
  python3 tools/ai.py budget                                              # calls + time saved so far

Why: rendering needs a GPU (Kaggle), but writing, code and looking at frames are text work that
free models do well. Every call that goes here is Claude usage NOT spent (AGENTS.md rule 02).
Keys are injected by the environment's proxy, so no secrets live in this file (rule 7).

The router itself now lives in the shared core, packages/aethern/aethern/router.py, configured by
aethern.json (models, fallback order, the Paper Cinema system prompt, the usage log). This file keeps
the same commands and the same module attributes (run, encode, call, MODELS, ORDER...) for tools that
import it. New: identical prompts are answered from a 7-day cache (output/aethern/ai); --fresh skips it.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'packages', 'aethern'))
from aethern import config as _config, router as _router  # noqa: E402

_R = _router.Router(_config.load(REPO))
MODELS, ORDER, SYSTEM = _R.models, _R.order, _R.system
LOG, OMNI_KEY_FILE = _R.log, _R.omni_key_file
key_for, call, note = _R.key_for, _R.call, _R.note
sheet, encode = _router.sheet, _router.encode


def run(job, prompt, image=None, model=None, max_tokens=900, fresh=False):
    """Try the models for this job in order; first good answer wins."""
    return _R.run(job, prompt, image=image, model=model, max_tokens=max_tokens, fresh=fresh)


def main():
    _router.main(router=_R, prog='tools/ai.py')


if __name__ == '__main__':
    main()

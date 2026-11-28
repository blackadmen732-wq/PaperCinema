#!/usr/bin/env python3
"""BUILD SKILLS.md: one map of every skill in this repo, grouped by the job it does.

    python3 tools/build_skills.py            # rewrite SKILLS.md
    python3 tools/build_skills.py --check    # exit 1 if SKILLS.md is out of date

There are over a hundred skills here. A hundred folders is not a map; it is a pile, and a pile is
why the same work got done twice in this project more than once. This reads the frontmatter of every
.claude/skills/*/SKILL.md and writes them out in groups, so an agent - any agent, not only the one
that happens to auto-load them - can see the whole surface on one page and pick.

The ORDER OF WORK at the top is written by hand and kept verbatim; everything below the marker is
generated, so a new skill appears on the map by existing, not by someone remembering to list it.

The builder lives in the shared core (packages/aethern/aethern/skillmap.py). The groups are data now,
in aethern.json `skills.groups` (prefix / suffix / names): add or move a group THERE.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'packages', 'aethern'))
from aethern import config, skillmap  # noqa: E402

sys.exit(skillmap.main(sys.argv[1:], config.load(REPO)))

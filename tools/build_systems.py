"""Regenerate systems.json from SYSTEMS.md and check that every listed file exists.
    python3 tools/build_systems.py        (npm run systems)

The builder lives in the shared core (packages/aethern/aethern/catalog.py). What is Paper Cinema's own,
the connections between systems, the start-here list and the golden path, is in aethern.json `catalog`:
add a connection THERE now, not here. To ask the map a question instead of reading it:
    python3 packages/aethern/bin/aethern map show SOUND     (or: map find / deps / owner)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'packages', 'aethern'))
from aethern import catalog, config  # noqa: E402

sys.exit(catalog.build(config.load(ROOT)))

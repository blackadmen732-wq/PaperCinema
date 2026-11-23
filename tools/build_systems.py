"""Regenerate systems.json from SYSTEMS.md and check that every listed file exists.
    python3 tools/build_systems.py        (npm run systems)
"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
md = open('SYSTEMS.md').read()
rows = [l for l in md.split('## The catalogue')[1].split('Legend:')[0].splitlines() if l.startswith('| `')]
strip = lambda x: x.replace('**', '').strip()
systems = []
for l in rows:
    c = [x.strip() for x in l.strip('|').split('|')]
    systems.append({"id": c[0].strip('`'), "name": strip(c[1]), "does": strip(c[2]),
                    "files": re.findall(r'`([^`]+)`', c[3]), "guide": re.findall(r'`([^`]+)`', c[4]),
                    "command": (re.findall(r'`([^`]+)`', c[5]) or [None])[0],
                    "status": {'✅': 'built', '🧪': 'test', '📋': 'planned'}.get(c[6][:1], c[6]), "status_note": c[6]})
connections = [["RESEARCH", "FILM"], ["NEWFILM", "FILM"], ["LIBRARY", "FILM"], ["MOVES", "MOTION"], ["FILM", "CHECK"], ["CHECK", "ENGINE"],
               ["ENGINE", "SKELETON"], ["ENGINE", "MOTION"], ["ENGINE", "REACT"], ["ENGINE", "DRAW"], ["ENGINE", "KUROKO"], ["ENGINE", "KEYCAM"],
               ["ENGINE", "WORLD"], ["ENGINE", "RENDER"], ["RENDER", "SOUND"], ["FILM", "THUMB"], ["FILM", "PLAYBOOK"], ["KUROKO", "PLAYBOOK"],
               ["FILM", "KIZU"], ["KIZU", "SHIMI"], ["SHIMI", "BLENDER"], ["GPU", "MODELS"], ["MODELS", "BLENDER"], ["MAKE", "CHECK"], ["MAKE", "RENDER"],
               ["MAKE", "SOUND"], ["MAKE", "PLAYBOOK"],
               ["ENGINE", "COMBAT"], ["COMBAT", "SOUND"], ["COMBAT", "FX"], ["PAPERMAT", "BWORLD"], ["PAPERMAT", "SLASHFX"], ["BWORLD", "BLENDER"], ["SLASHFX", "BLENDER"]]
ids = {s['id'] for s in systems}
bad = [c for c in connections if c[0] not in ids or c[1] not in ids]
missing = []
for s in systems:
    for f in s['files'] + s['guide']:
        path = f.split('§')[0].strip()
        if any(ch in path for ch in '*<') or not path: continue
        if not os.path.exists(path): missing.append(f"{s['id']}: {path}")
json.dump({"_about": "Machine-readable catalogue of every Paper Cinema system. Generated from SYSTEMS.md by tools/build_systems.py; connections = [from, to] data flow.",
           "start_here": ["AGENTS.md", "SYSTEMS.md", ".claude/skills/paper-cinema-film/SKILL.md"],
           "golden_path": ["node engine/new-film.mjs <name> --jp 漢字 --en TITLE", "edit film/<name>.json", "node engine/validate.mjs film/<name>.json",
                           "node engine/render.mjs --film film/<name>.json --still auto", "node engine/make.mjs film/<name>.json",
                           "python3 engine/thumbnail.py film/<name>.json"],
           "systems": systems, "connections": connections}, open('systems.json', 'w'), ensure_ascii=False, indent=1)
print(f'systems.json: {len(systems)} systems, {len(connections)} connections')
for m in missing: print('  missing file:', m)
for b in bad: print('  bad connection:', b)
sys.exit(1 if missing or bad else 0)

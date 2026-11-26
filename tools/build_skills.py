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
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(REPO, '.claude', 'skills')
OUT = os.path.join(REPO, 'SKILLS.md')
MARK = '<!-- generated below this line by tools/build_skills.py -->'

# (heading, note, matcher). First match wins, so order matters.
GROUPS = [
    ('START HERE — the four that carry this project',
     'Everything learned on 25-26 Nov, compressed. Written for ANY agent: command-first, with the '
     'measured numbers and the dead ends, so nothing has to be re-derived. Read `pc-measure` first.',
     lambda n: n.startswith('pc-')),
    ('The film pipeline', 'The project itself. The rest is support.',
     lambda n: n in ('paper-cinema-film', 'qa-review', 'graphify', 'scene-direction', 'scene-writing',
                     'camera-cinematography', 'vfx-fx')),
    ('Outside tools (vendor/)', 'Fetched and pinned by `node tools/vendor.mjs`. Each skill says what it is for HERE and what it must not be used for.',
     lambda n: n.startswith('tool-')),
    ('Blender, by task', 'The Scenario pack (MIT). Deep, task-shaped Blender procedure; `scenario-blender-expert` is the way in.',
     lambda n: n.startswith('scenario-blender-')),
    ('The character', 'Building, rigging and posing the folded paper cast.',
     lambda n: n in ('character-artist', 'creature-artist', 'anatomy', 'character-archetypes', 'rigging',
                     'animation', 'cloth-sim', 'hair-groom', 'sculpting', 'retopology', 'blender-modeler')),
    ('The shot', 'Light it, shade it, render it, put it together.',
     lambda n: n in ('lighting', 'rendering', 'lookdev', 'materials', 'texture-workflow', 'compositing',
                     'uv-workflow', 'physics-sim', 'scene-assembly', 'set-dressing')),
    ('The world', 'Sets, props and everything the duel stands in.',
     lambda n: n.endswith('-worlds') or n in ('environment-artist', 'prop-artist', 'vehicle-artist',
                                              'vegetation-artist', 'procedural-modeling', 'geometry-nodes',
                                              'hard-surface', 'archviz')),
    ('Look and mood', 'Art direction. Paper Cinema is `anime-style` + `stop-motion-craft-style` + `minimalist-style`; the rest are there to be borrowed from, not followed.',
     lambda n: n.endswith('-style') or n.endswith('-mood') or n.endswith('-horror') or n.endswith('-aesthetics')
     or n in ('horror-style', 'indie-horror-aesthetics', 'visual-console-eras', 'neon-retrofuturism')),
    ('Getting assets out', 'Export, optimise, ship to an engine.',
     lambda n: n.endswith('-export') or n in ('export-pipeline', 'asset-optimization', 'collision-proxy', 'lod-pipeline')),
    ('Game genres (imported, unused here)', 'From the Scenario pack. Paper Cinema makes films, not games; these stay because they are good reference for action staging and pacing.',
     lambda n: n.startswith('genre-')),
]


def read(name):
    p = os.path.join(SKILLS, name, 'SKILL.md')
    if not os.path.isfile(p):
        return None
    head = open(p, encoding='utf-8').read(4000)
    m = re.search(r'^---\s*$(.*?)^---\s*$', head, re.S | re.M)
    fm = m.group(1) if m else ''
    d = re.search(r'^description:\s*(.+?)\s*$', fm, re.M)
    desc = d.group(1).strip() if d else ''
    desc = re.sub(r'\s+', ' ', desc)
    return desc


def build():
    names = sorted(n for n in os.listdir(SKILLS) if os.path.isdir(os.path.join(SKILLS, n)))
    seen, out = set(), []
    for title, note, match in GROUPS:
        rows = []
        for n in names:
            if n in seen or not match(n):
                continue
            desc = read(n)
            if desc is None:
                continue
            seen.add(n)
            rows.append((n, desc))
        if not rows:
            continue
        out.append(f'\n## {title}\n\n{note}\n')
        out.append('| skill | what it is for |')
        out.append('|---|---|')
        for n, d in rows:
            short = d if len(d) <= 160 else d[:157].rsplit(' ', 1)[0] + '…'
            out.append(f'| [`{n}`](.claude/skills/{n}/SKILL.md) | {short} |')
    rest = [n for n in names if n not in seen and read(n) is not None]
    if rest:
        out.append('\n## Not grouped yet\n\nAdd them to GROUPS in `tools/build_skills.py` when you touch them.\n')
        out.append('| skill | what it is for |')
        out.append('|---|---|')
        for n in rest:
            d = read(n)
            out.append(f'| [`{n}`](.claude/skills/{n}/SKILL.md) | {d if len(d) <= 160 else d[:157] + "…"} |')
    out.append(f'\n---\n{len(seen) + len(rest)} skills. Generated by `python3 tools/build_skills.py` — do not edit below the marker.\n')
    return '\n'.join(out)


HEAD = open(os.path.join(REPO, 'tools', 'skills_preamble.md'), encoding='utf-8').read().rstrip()
text = HEAD + '\n\n' + MARK + '\n' + build()

if '--check' in sys.argv:
    have = open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
    if have.strip() != text.strip():
        print('  SKILLS.md is out of date — run: python3 tools/build_skills.py')
        sys.exit(1)
    print(f'  SKILLS.md is current ({text.count("| [`")} skills listed)')
    sys.exit(0)

open(OUT, 'w', encoding='utf-8').write(text + '\n')
print(f'wrote SKILLS.md — {text.count("| [`")} skills')

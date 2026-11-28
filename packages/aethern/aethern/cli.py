"""aethern: one entry point an agent can learn from a 20-line help text instead of reading the docs."""
import os
import subprocess
import sys

from . import config as _config

HELP = """aethern — small answers for AI agents (run from anywhere inside a project with an aethern.json)

orient   map show ID [ID..]    one system: does, files (+line counts), guide, command, links
         map find WORDS        which systems match       map owner FILE   which systems list a file
         map deps ID [--up] [--depth N]   what it feeds / what feeds it      map list   all ids
         map ask Q             any of the above from one free-form query (id, file or words)
change   changed [--save]      files added/modified/removed since your last snapshot
         impact [--save]       changed files -> systems -> what those systems feed
         snapshot              move the snapshot to now        (--as NAME keeps a separate one)
notes    mem get TOPIC | --grep WORD     mem add TOPIC "fact"     mem topics     mem drop ID
labour   ai write|code|think|quick "prompt"   ai review IMG|DIR "question"   ai list   ai budget
         worker "task" [--steps N] [--dry]   a free model with read/search/patch/run/map tools
build    map build             regenerate the JSON map from its Markdown table
         skills [--check]      regenerate / check the skills map
         vendor [--check|--list|ID]   pinned outside tools    ledger [--open]   promise checks
Add --json to map/changed/impact/mem for machine-readable output. Exit 0 = ok.
"""

JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'js')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(HELP)
        return 0
    cmd, rest = argv[0], argv[1:]
    cfg = _config.load()
    if cmd == 'map':
        from . import catalog
        return catalog.main(rest, cfg) or 0
    if cmd in ('changed', 'impact', 'snapshot'):
        from . import index
        return index.main(rest, cfg, cmd)
    if cmd == 'mem':
        from . import memory
        return memory.main(rest, cfg)
    if cmd == 'ai':
        from . import router
        router.main(rest, router.Router(cfg))
        return 0
    if cmd == 'worker':
        from . import worker
        worker.main(rest, worker.Worker(cfg))
        return 0
    if cmd == 'skills':
        from . import skillmap
        return skillmap.main(rest, cfg)
    if cmd == 'vendor':
        v = cfg['vendor']
        return subprocess.call(['node', os.path.join(JS, 'vendor.mjs'), '--root', cfg.root,
                                '--manifest', v['manifest'], '--dir', v['dir'], *rest])
    if cmd == 'ledger':
        return subprocess.call(['node', os.path.join(JS, 'ledger.mjs'), '--root', cfg.root,
                                '--file', cfg['ledger']['file'], *rest])
    print(f'unknown command "{cmd}"\n\n{HELP}', file=sys.stderr)
    return 2

"""CAPABILITIES: one backend interface over Aethern, VYRN and Sonic, with selective discovery.

    aethern caps                    every capability, one line each (id + what it does)
    aethern caps find WORDS [--k 5] the few capabilities a task needs, best first (keyword match, no AI)
    aethern caps show ID            one capability's full contract (args, output, example, how it runs)
    aethern call ID [ARGS…]         run it; prints {"cap","ok","exit","ms","out"} (out parsed when JSON / JSON Lines)

Each module ships its own manifest (aethern-caps/1, schema/caps-1.schema.json) and stays usable on its own:
packages/aethern/capabilities.json, vyrn/capabilities.json, packages/sonic/capabilities.json. A project lists the
manifests it uses in aethern.json "capabilities" (a path, or {"file", "args"} to add host arguments such as a
catalog path). An agent loads the three tools of `aethern mcp` (find, show, call) instead of every tool definition,
and asks find for only what its current task needs. This decides which CINEVORA capabilities an agent sees; it does
not change which connectors or tools a Claude session itself loads (that is set in Claude's own settings).
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORD = re.compile(r'[a-z0-9]+')
STOP = set('a an and are as at be by can do does for from how i in into is it its me my of on one or the this to what when which with'.split())


def _manifests(cfg):
    entries = cfg.get('capabilities') or [os.path.join(HERE, 'capabilities.json')]
    out = []
    for e in entries:
        e = {'file': e} if isinstance(e, str) else dict(e)
        p = cfg.path(e['file'])
        try:
            m = json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError) as err:
            raise SystemExit(f'aethern caps: cannot read {e["file"]}: {err}')
        if m.get('format') != 'aethern-caps/1':
            raise SystemExit(f'aethern caps: {e["file"]} is not aethern-caps/1')
        m['_dir'], m['_args'] = os.path.dirname(os.path.abspath(p)), list(e.get('args') or [])
        out.append(m)
    return out


def load(cfg):
    """{id: capability}, each with its module's run settings attached"""
    caps = {}
    for m in _manifests(cfg):
        for c in m['caps']:
            if c['id'] in caps:
                raise SystemExit(f'aethern caps: {c["id"]} is defined twice')
            caps[c['id']] = {**c, 'module': m['module'], '_run': m['run'], '_dir': m['_dir'], '_args': m['_args'],
                             '_cwd': m.get('cwd', 'root')}
    return caps


def brief(c):
    return {'id': c['id'], 'does': c['does']}


def contract(c):
    return {k: v for k, v in c.items() if not k.startswith('_')} | {'run': ' '.join(argv(c, ['ARGS…']))}


def _words(text):
    """lower-case words without filler, plural s dropped (footsteps = footstep)"""
    return {w[:-1] if len(w) > 3 and w.endswith('s') and not w.endswith('ss') else w for w in WORD.findall(text.lower())} - STOP


def find(caps, query, k=5):
    """the k capabilities whose id, description and tags share the most words with the query (ties: id order)"""
    q = _words(query)
    scored = []
    for c in caps.values():
        idw, tags, does = _words(c['id']), _words(' '.join(c.get('tags', []))), _words(c['does'])
        s = 3 * len(q & idw) + 2 * len(q & tags) + len(q & does)
        if s:
            scored.append((-s, c['id']))
    return [caps[i] for _, i in sorted(scored)[:k]]


def argv(c, args):
    run = [x.replace('{dir}', c['_dir']) for x in c['_run']]
    prefix = c.get('prefix', c['id'].split('.')[1:])
    return [*run, *prefix, *args, *c['_args']]


def call(cfg, caps, cid, args):
    if cid not in caps:
        near = [x['id'] for x in find(caps, cid.replace('.', ' '), 3)]
        return {'cap': cid, 'ok': False, 'exit': 2, 'ms': 0, 'out': f'unknown capability; nearest: {near}'}
    c = caps[cid]
    t = time.time()
    p = subprocess.run(argv(c, args), cwd=cfg.root if c['_cwd'] == 'root' else c['_dir'], capture_output=True, text=True)
    text = p.stdout
    out = text
    try:
        if c.get('out') == 'json':
            out = json.loads(text)
        elif c.get('out') == 'jsonl':
            out = [json.loads(l) for l in text.splitlines() if l.strip()]
    except ValueError:
        pass
    r = {'cap': cid, 'ok': p.returncode == 0, 'exit': p.returncode, 'ms': round((time.time() - t) * 1000), 'out': out}
    if p.stderr.strip():
        r['err'] = p.stderr.strip()[-2000:]
    return r


def main(argv_, cfg, cmd):
    caps = load(cfg)
    if cmd == 'call':
        if not argv_:
            print('usage: aethern call ID [ARGS…]', file=sys.stderr)
            return 2
        r = call(cfg, caps, argv_[0], argv_[1:])
        print(json.dumps(r, ensure_ascii=False))
        return r['exit'] if r['exit'] in (0, 1, 2) else 1
    sub = argv_[0] if argv_ else 'list'
    if sub == 'find':
        k = 5
        if '--k' in argv_:
            i = argv_.index('--k')
            k = int(argv_[i + 1])
            argv_ = argv_[:i] + argv_[i + 2:]
        print(json.dumps([brief(c) for c in find(caps, ' '.join(argv_[1:]), k)], ensure_ascii=False))
        return 0
    if sub == 'show':
        missing = [i for i in argv_[1:] if i not in caps]
        if missing or len(argv_) < 2:
            print(f'unknown capability {missing}', file=sys.stderr)
            return 2
        print(json.dumps([contract(caps[i]) for i in argv_[1:]], ensure_ascii=False, indent=1))
        return 0
    if sub == 'list':
        for c in caps.values():
            print(f'{c["id"]:24} {c["does"]}')
        return 0
    print('usage: aethern caps [list | find WORDS [--k N] | show ID…]', file=sys.stderr)
    return 2

"""SHARED NOTES: decisions and facts any agent or person can add and any agent can query in a few lines.

AGENTS.md and CLAUDE.md are prose an agent must read whole. This is the opposite: one JSON line per
fact, tagged by topic, so `aethern mem get sound` returns the four facts about sound and nothing else.
The file is meant to be committed, so every machine and every agent sees the same notes.

    aethern mem add sound "Clash cues are aimed at the blade's fastest frame" [--by mark] [--ref docs/X.md]
    aethern mem get sound              notes on a topic (newest first)
    aethern mem get --grep whoosh      notes containing a word, any topic
    aethern mem topics                 every topic with its count
    aethern mem drop <id>              mark a note as no longer true (kept in the file, hidden from get)
A note that says the same thing as an existing one on the same topic is not added twice.
"""
import hashlib
import json
import os
import time


def _path(cfg):
    return cfg.path(cfg['memory_file'])


def _all(cfg):
    p = _path(cfg)
    if not os.path.exists(p):
        return []
    out = []
    for l in open(p, encoding='utf-8'):
        l = l.strip()
        if l:
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    return out


def _norm(t):
    return ' '.join(t.lower().split())


def live(cfg):
    rows = _all(cfg)
    dropped = {r['drop'] for r in rows if 'drop' in r}
    return [r for r in rows if 'id' in r and 'text' in r and r['id'] not in dropped]


def add(cfg, topic, text, by=None, ref=None):
    topic = topic.lower().strip()
    nid = hashlib.sha1(f'{topic}\n{_norm(text)}'.encode()).hexdigest()[:8]
    if any(r['id'] == nid for r in live(cfg)):
        return nid, False
    row = {'id': nid, 'topic': topic, 'text': text.strip(), 'at': time.strftime('%Y-%m-%d')}
    if by:
        row['by'] = by
    if ref:
        row['ref'] = ref
    p = _path(cfg)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    return nid, True


def get(cfg, topic=None, grep=None):
    rows = live(cfg)
    if topic:
        rows = [r for r in rows if r['topic'] == topic.lower()]
    if grep:
        g = grep.lower()
        rows = [r for r in rows if g in r['text'].lower() or g in r['topic']]
    return list(reversed(rows))


def drop(cfg, nid):
    if not any(r['id'] == nid for r in live(cfg)):
        return False
    with open(_path(cfg), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'drop': nid, 'at': time.strftime('%Y-%m-%d')}) + '\n')
    return True


def main(argv, cfg):
    import argparse
    ap = argparse.ArgumentParser(prog='aethern mem')
    ap.add_argument('cmd', choices=['add', 'get', 'topics', 'drop'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--grep')
    ap.add_argument('--by')
    ap.add_argument('--ref')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'add':
        if len(a.args) < 2:
            raise SystemExit('usage: aethern mem add <topic> "<fact>"')
        nid, new = add(cfg, a.args[0], ' '.join(a.args[1:]), a.by, a.ref)
        print(f'{"added" if new else "already noted"} {nid}')
        return 0
    if a.cmd == 'drop':
        ok = all(drop(cfg, n) for n in a.args)
        print('dropped' if ok else 'no such note')
        return 0 if ok else 1
    if a.cmd == 'topics':
        counts = {}
        for r in live(cfg):
            counts[r['topic']] = counts.get(r['topic'], 0) + 1
        for t, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            print(f'{n:4}  {t}')
        return 0
    rows = get(cfg, a.args[0] if a.args else None, a.grep)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False))
    else:
        for r in rows:
            print(f'{r["id"]} [{r["topic"]}] {r["text"]}' + (f' ({r["ref"]})' if r.get('ref') else ''))
        if not rows:
            print('no notes')
    return 0

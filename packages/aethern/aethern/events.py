"""SHARED EVENTS: one versioned format (aethern-event/1, schema/event-1.schema.json) that Sonic, VYRN and
the engine already write as JSON Lines, and three commands to use them without any AI call.

    aethern events check FILE…              every line valid? (exit 1 on the first bad file, with line numbers)
    aethern events merge FILE… [--out F]    one stream sorted by time; the same id from two tools is kept once
                                            (higher conf wins, ties keep the first file's), sources noted in data
    aethern events near T FILE… [--window 0.1] [--type X]   events within ±window seconds of T
"""
import json
import os

FIELDS = {'v', 'id', 'type', 't', 't1', 'f', 'source', 'method', 'conf', 'entities', 'data'}


def problems(ev):
    p = []
    if not isinstance(ev, dict):
        return ['not an object']
    for k in ('id', 'type', 'source'):
        if not isinstance(ev.get(k), str) or not ev.get(k):
            p.append(f'{k} must be a non-empty string')
    t = ev.get('t')
    if not isinstance(t, (int, float)) or isinstance(t, bool) or t < 0:
        p.append('t must be a number >= 0')
    t1 = ev.get('t1')
    if t1 is not None and (not isinstance(t1, (int, float)) or (isinstance(t, (int, float)) and t1 < t)):
        p.append('t1 must be a number >= t')
    if ev.get('v', 1) != 1:
        p.append(f'unknown version {ev.get("v")!r}')
    c = ev.get('conf')
    if c is not None and (not isinstance(c, (int, float)) or not 0 <= c <= 1):
        p.append('conf must be 0..1')
    if 'entities' in ev and not (isinstance(ev['entities'], list) and all(isinstance(x, str) for x in ev['entities'])):
        p.append('entities must be a list of strings')
    if 'data' in ev and not isinstance(ev['data'], dict):
        p.append('data must be an object')
    if 'f' in ev and ev['f'] is not None and not isinstance(ev['f'], int):
        p.append('f must be an integer frame')
    extra = set(ev) - FIELDS
    if extra:
        p.append(f'unknown field(s) {sorted(extra)}: put them in data')
    return p


def read(path):
    out = []
    with open(path, encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if line:
                out.append((n, json.loads(line)))
    return out


def check(paths):
    bad = {}
    for p in paths:
        errs = []
        for n, ev in read(p):
            for e in problems(ev):
                errs.append(f'line {n}: {e}')
        if errs:
            bad[p] = errs
    return bad


def merge(paths):
    by = {}
    order = []
    for p in paths:
        for _, ev in read(p):
            k = ev['id']
            if k not in by:
                by[k] = dict(ev)
                order.append(k)
                continue
            cur = by[k]
            seen = set(cur.setdefault('data', {}).get('also_from', [])) | {cur['source']}
            if ev.get('conf', 0) > cur.get('conf', 0):
                ev = dict(ev)
                ev.setdefault('data', {})
                ev['data']['also_from'] = sorted(seen - {ev['source']})
                by[k] = ev
            elif ev['source'] not in seen:
                cur['data']['also_from'] = sorted((seen | {ev['source']}) - {cur['source']})
    return sorted((by[k] for k in order), key=lambda e: (e['t'], e['id']))


def main(argv, cfg):
    import argparse
    ap = argparse.ArgumentParser(prog='aethern events')
    ap.add_argument('cmd', choices=['check', 'merge', 'near'])
    ap.add_argument('args', nargs='+')
    ap.add_argument('--out')
    ap.add_argument('--window', type=float, default=0.1)
    ap.add_argument('--type')
    a = ap.parse_args(argv)
    rel = lambda p: p if os.path.isabs(p) else cfg.path(p)
    if a.cmd == 'check':
        bad = check([rel(p) for p in a.args])
        for p, errs in bad.items():
            print(f'{p}: {len(errs)} problem(s)')
            for e in errs[:10]:
                print(f'  {e}')
        if not bad:
            print(f'{len(a.args)} file(s): every line is aethern-event/1')
        return 1 if bad else 0
    if a.cmd == 'merge':
        evs = merge([rel(p) for p in a.args])
        text = ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in evs)
        if a.out:
            tmp = rel(a.out) + '.tmp'
            open(tmp, 'w', encoding='utf-8').write(text)
            os.replace(tmp, rel(a.out))
            print(f'{len(evs)} events → {a.out}')
        else:
            print(text, end='')
        return 0
    t = float(a.args[0])
    evs = [e for e in merge([rel(p) for p in a.args[1:]]) if abs(e['t'] - t) <= a.window and (not a.type or e['type'] == a.type)]
    print(json.dumps(evs, ensure_ascii=False))
    return 0

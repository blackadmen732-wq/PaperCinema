"""SHARED EVENTS: one versioned format that Sonic, VYRN and the engine write as JSON Lines, and the commands to use
them without any AI call. Schemas: schema/event-2.schema.json (current) and schema/event-1.schema.json (still read).

    aethern events check FILE…                       every line valid? exit 1 with line numbers and reasons
    aethern events merge FILE… [--out F] [--tol S]   one aethern-event/2 stream sorted by time
    aethern events near T FILE… [--window 0.1] [--type X]   events within ±window seconds of T
    (merge and near also take --project P --media M: the ids given to version-1 lines, which have none)

Version 2 adds `project` and `media` (an event is unique by project + media + id), `evidence` (every observation
behind the event: which tool, how, how sure, when, what it measured) and `conflict` (true when those observations
disagree). Merging never drops an observation: when two tools report the same event differently, the merged event
keeps the most confident one on top, sets conflict: true, and lists all of them in evidence.
"""
import json
import math
import os
import re

V1 = {'v', 'id', 'type', 't', 't1', 'f', 'source', 'method', 'conf', 'entities', 'data'}
V2 = V1 | {'project', 'media', 'evidence', 'conflict'}
OBS = {'source', 'method', 'conf', 't', 't1', 'type', 'entities', 'data', 'file'}
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/-]*$')
TOL = 0.05     # seconds: two observations of one event further apart than this disagree


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def problems(ev):
    """the reasons a line is not a valid shared event (empty list = valid). Version 1 and 2 are both accepted."""
    if not isinstance(ev, dict):
        return ['not a JSON object']
    p = []
    v = ev.get('v', 1)
    if isinstance(v, bool) or v not in (1, 2):
        return [f'unknown version {v!r} (this reader knows 1 and 2)']
    for k in ('id', 'type', 'source'):
        if not isinstance(ev.get(k), str) or not ev.get(k).strip():
            p.append(f'{k} must be a non-empty string')
    t = ev.get('t')
    if not _num(t) or t < 0:
        p.append('t must be a finite number >= 0')
    t1 = ev.get('t1')
    if t1 is not None and (not _num(t1) or (_num(t) and t1 < t)):
        p.append('t1 must be a finite number >= t')
    c = ev.get('conf')
    if c is not None and (not _num(c) or not 0 <= c <= 1):
        p.append('conf must be a number 0..1')
    if 'entities' in ev and not (isinstance(ev['entities'], list) and all(isinstance(x, str) for x in ev['entities'])):
        p.append('entities must be a list of strings')
    if 'data' in ev and not isinstance(ev['data'], dict):
        p.append('data must be an object')
    if 'f' in ev and ev['f'] is not None and (not isinstance(ev['f'], int) or isinstance(ev['f'], bool) or ev['f'] < 0):
        p.append('f must be an integer frame >= 0')
    if 'method' in ev and ev['method'] is not None and not isinstance(ev['method'], str):
        p.append('method must be a string')
    if v == 2:
        for k in ('project', 'media'):
            if not isinstance(ev.get(k), str) or not ID.match(ev.get(k)):
                p.append(f'{k} is required in version 2: letters, digits and . _ : / - (got {ev.get(k)!r})')
        if 'conflict' in ev and not isinstance(ev['conflict'], bool):
            p.append('conflict must be true or false')
        evd = ev.get('evidence')
        if evd is not None:
            if not isinstance(evd, list) or not evd:
                p.append('evidence must be a non-empty list')
            else:
                for i, o in enumerate(evd):
                    if not isinstance(o, dict) or not isinstance(o.get('source'), str) or not o.get('source'):
                        p.append(f'evidence[{i}] must be an object with a source')
                        continue
                    if set(o) - OBS:
                        p.append(f'evidence[{i}]: unknown field(s) {sorted(set(o) - OBS)}')
                    if o.get('conf') is not None and (not _num(o['conf']) or not 0 <= o['conf'] <= 1):
                        p.append(f'evidence[{i}].conf must be 0..1')
                    if not _num(o.get('t')):
                        p.append(f'evidence[{i}].t is required: a finite number (when that observation saw it)')
                    if o.get('t1') is not None and not _num(o['t1']):
                        p.append(f'evidence[{i}].t1 must be a finite number')
                    if 'data' in o and not isinstance(o['data'], dict):
                        p.append(f'evidence[{i}].data must be an object')
    extra = set(ev) - (V2 if v == 2 else V1)
    if extra:
        p.append(f'unknown field(s) {sorted(extra)}: put them in data' + (' (or write version 2)' if v == 1 and extra & (V2 - V1) else ''))
    return p


def read(path):
    """[(line number, event or None, problems)] for every non-empty line; never raises on bad content"""
    out, seen = [], {}
    if not os.path.isfile(path):
        return [(0, None, ['file not found'])]
    with open(path, encoding='utf-8', errors='replace') as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line, parse_constant=lambda c: float('nan'))
            except json.JSONDecodeError as e:
                out.append((n, None, [f'not JSON ({e.msg} at column {e.colno})']))
                continue
            pr = problems(ev)
            if not pr:
                k = (ev.get('project'), ev.get('media'), ev['id'])
                if k in seen:
                    pr = [f'duplicate id {ev["id"]!r} (also on line {seen[k]})']
                else:
                    seen[k] = n
            out.append((n, ev, pr))
    return out


def check(paths):
    bad = {}
    for p in paths:
        errs = [f'line {n}: {e}' for n, _, pr in read(p) for e in pr]
        if errs:
            bad[p] = errs
    return bad


class Malformed(ValueError):
    pass


def upgrade(ev, project, media):
    """a version-1 event as version 2 (the ids come from the caller); a version-2 event is returned unchanged"""
    if ev.get('v', 1) == 2:
        return ev
    out = {'v': 2, 'project': project, 'media': media}
    out.update({k: v for k, v in ev.items() if k != 'v'})
    return out


def _observation(ev, file):
    o = {k: ev[k] for k in ('source', 'method', 'conf', 't', 't1', 'type', 'entities', 'data') if ev.get(k) is not None}
    o['file'] = os.path.basename(file)
    return o


def _disagree(a, b, tol):
    if a.get('type') != b.get('type'):
        return 'type'
    if _num(a.get('t')) and _num(b.get('t')) and abs(a['t'] - b['t']) > tol:
        return 't'
    if _num(a.get('t1')) and _num(b.get('t1')) and abs(a['t1'] - b['t1']) > tol:
        return 't1'
    ea, eb = set(a.get('entities') or []), set(b.get('entities') or [])
    if ea and eb and not ea & eb:
        return 'entities'
    return None


def _stem(p):
    s = re.sub(r'[^A-Za-z0-9._/-]+', '-', os.path.basename(p).split('.')[0]).strip('-')
    return s or 'unnamed'


def merge(paths, project=None, media=None, tol=TOL):
    """one aethern-event/2 list from several files. Raises Malformed (naming the bad lines) instead of guessing.
    Version-1 lines have no media id, so they get `media` from the caller. Without one, a single file's lines get
    file:<its name>; version-1 lines from several files are refused, because nothing says whether they are the same
    film (the same id in two films would otherwise merge into one event)."""
    bad = check(paths)
    if bad:
        raise Malformed('; '.join(f'{os.path.basename(p)} {e}' for p, errs in bad.items() for e in errs[:5]))
    v1 = [p for p in paths if any(ev.get('v', 1) == 1 for _, ev, _ in read(p))]
    if v1 and not media and len(paths) > 1:
        raise Malformed('version-1 lines (no media id) in ' + ', '.join(os.path.basename(p) for p in v1)
                        + ': say which media they belong to with --media, or merge them one file at a time')
    groups, order = {}, []
    for p in paths:
        for _, ev, _ in read(p):
            ev = upgrade(ev, project or 'unknown', media or f'file:{_stem(p)}')
            k = (ev['project'], ev['media'], ev['id'])
            obs = ev.get('evidence') or [_observation(ev, p)]
            if k not in groups:
                groups[k] = {'top': ev, 'obs': list(obs)}
                order.append(k)
            else:
                g = groups[k]
                g['obs'].extend(obs)
                if (ev.get('conf') or 0) > (g['top'].get('conf') or 0):
                    g['top'] = ev
    out = []
    for k in order:
        g = groups[k]
        ev = {kk: vv for kk, vv in g['top'].items() if kk not in ('evidence', 'conflict')}
        why = sorted({w for o in g['obs'] for w in [_disagree(o, g['obs'][0], tol)] if w})
        if len(g['obs']) > 1 or g['top'].get('evidence'):
            ev['evidence'] = g['obs']
        if why or g['top'].get('conflict'):
            ev['conflict'] = True
            ev['data'] = {**(ev.get('data') or {}), 'conflict_on': why or (ev.get('data') or {}).get('conflict_on', [])}
        out.append(ev)
    return sorted(out, key=lambda e: (e['t'], e['project'], e['media'], e['id']))


def project_id(cfg=None):
    """the project's id in events: aethern.json "id", else its "name" as a slug (Paper Cinema -> paper-cinema)"""
    cfg = cfg or {}
    if cfg.get('id'):
        return cfg['id']
    return re.sub(r'[^a-z0-9]+', '-', str(cfg.get('name') or 'unknown').lower()).strip('-') or 'unknown'


def main(argv, cfg):
    import argparse
    ap = argparse.ArgumentParser(prog='aethern events')
    ap.add_argument('cmd', choices=['check', 'merge', 'near'])
    ap.add_argument('args', nargs='+')
    ap.add_argument('--out')
    ap.add_argument('--window', type=float, default=0.1)
    ap.add_argument('--tol', type=float, default=TOL, help='seconds two observations may differ and still agree')
    ap.add_argument('--type')
    ap.add_argument('--project', help='project id for version-1 lines (default: aethern.json id or name)')
    ap.add_argument('--media', help='media id for version-1 lines (needed when version-1 lines come from more than one file)')
    a = ap.parse_args(argv)
    rel = lambda p: p if os.path.isabs(p) else cfg.path(p)
    if a.cmd == 'check':
        bad = check([rel(p) for p in a.args])
        for p, errs in bad.items():
            print(f'{p}: {len(errs)} problem(s)')
            for e in errs[:10]:
                print(f'  {e}')
            if len(errs) > 10:
                print(f'  … {len(errs) - 10} more')
        if not bad:
            print(f'{len(a.args)} file(s): every line is a valid shared event (aethern-event/1 or /2)')
        return 1 if bad else 0
    try:
        files = a.args if a.cmd == 'merge' else a.args[1:]
        evs = merge([rel(p) for p in files], a.project or project_id(cfg), a.media, a.tol)
    except Malformed as e:
        print(f'not merged, malformed input: {e}')
        return 1
    if a.cmd == 'merge':
        text = ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in evs)
        if a.out:
            tmp = rel(a.out) + '.tmp'
            open(tmp, 'w', encoding='utf-8').write(text)
            os.replace(tmp, rel(a.out))
            n = sum(1 for e in evs if e.get('conflict'))
            print(f'{len(evs)} events → {a.out}' + (f' ({n} with conflicting observations, all kept in evidence)' if n else ''))
        else:
            print(text, end='')
        return 0
    t = float(a.args[0])
    print(json.dumps([e for e in evs if abs(e['t'] - t) <= a.window and (not a.type or e['type'] == a.type)], ensure_ascii=False))
    return 0

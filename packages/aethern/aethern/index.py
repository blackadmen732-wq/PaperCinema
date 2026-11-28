"""CHANGE DETECTION: what changed in the project since an agent last looked, and which systems it touches.

`git status` answers "what changed since the last commit". An agent needs "what changed since I last
looked", which is a different question in a project where several agents and people commit all day.
This keeps a snapshot (size, mtime, sha1 per file) and hashes again only files whose size or mtime
moved, so a no-change check over ~900 files costs one stat per file.

    aethern changed            added / modified / removed since the snapshot (does not move it)
    aethern changed --save     same, then move the snapshot to now
    aethern snapshot           move the snapshot to now
    aethern impact             changed files → the systems that list them → what those systems feed
Snapshots are named (--as NAME), so two agents can each keep their own.
"""
import hashlib
import json
import os
import subprocess


def _files(cfg):
    root = cfg.root
    try:   # git knows the ignore rules better than we do; use it when it is there
        r = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=root,
                           capture_output=True, timeout=60)
        if r.returncode == 0:
            ign = tuple(i.rstrip('/') + '/' for i in cfg['index_ignore'])
            return sorted(p for p in r.stdout.decode().split('\0') if p and not p.startswith(ign)
                          and os.path.isfile(os.path.join(root, p)))
    except Exception:
        pass
    ign = set(cfg['index_ignore'])
    out = []
    for d, dirs, files in os.walk(root):
        rel = os.path.relpath(d, root)
        dirs[:] = [x for x in dirs if os.path.normpath(os.path.join(rel, x)) not in ign and x not in ign]
        out += [os.path.normpath(os.path.join(rel, f)) for f in files]
    return sorted(out)


def _sha(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _snap_path(cfg, name):
    return os.path.join(cfg.path(cfg['cache_dir']), f'snapshot-{name}.json')


def scan(cfg, prev=None):
    """Current state, re-hashing only what size/mtime says may have changed. Returns (state, hashed_count)."""
    prev = prev or {}
    cur, hashed = {}, 0
    for rel in _files(cfg):
        p = os.path.join(cfg.root, rel)
        try:
            st = os.stat(p)
        except OSError:
            continue
        old = prev.get(rel)
        if old and old[0] == st.st_size and old[1] == st.st_mtime_ns:
            cur[rel] = old
        else:
            cur[rel] = [st.st_size, st.st_mtime_ns, _sha(p)]
            hashed += 1
    return cur, hashed


def load_snapshot(cfg, name='default'):
    try:
        return json.load(open(_snap_path(cfg, name)))
    except Exception:
        return None


def save_snapshot(cfg, state, name='default'):
    p = _snap_path(cfg, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    json.dump(state, open(tmp, 'w'))
    os.replace(tmp, p)


def diff(old, cur):
    added = sorted(set(cur) - set(old))
    removed = sorted(set(old) - set(cur))
    modified = sorted(k for k in set(cur) & set(old) if cur[k][2] != old[k][2])
    return {'added': added, 'modified': modified, 'removed': removed}


def changed(cfg, name='default', save=False):
    old = load_snapshot(cfg, name)
    cur, hashed = scan(cfg, old)
    if old is None:
        save_snapshot(cfg, cur, name)
        return {'first_snapshot': True, 'files': len(cur), 'hashed': hashed, 'added': [], 'modified': [], 'removed': []}
    d = diff(old, cur)
    # moving mtimes with unchanged content would make every next check re-hash; store the fresh stats
    # only when asked to move the snapshot, so `changed` stays read-only about what it reports
    if save:
        save_snapshot(cfg, cur, name)
    d.update(files=len(cur), hashed=hashed)
    return d


def impact(cfg, d):
    from . import catalog
    touched = {}
    for f in d['added'] + d['modified'] + d['removed']:
        for sid in catalog.owner(cfg, f):
            touched.setdefault(sid, []).append(f)
    downstream = set()
    for sid in touched:
        for layer in catalog.deps(cfg, sid, depth=6):
            downstream.update(layer)
    return {'systems': touched, 'downstream': sorted(downstream - set(touched))}


def main(argv, cfg, cmd):
    import argparse
    ap = argparse.ArgumentParser(prog=f'aethern {cmd}')
    ap.add_argument('--as', dest='name', default='default')
    ap.add_argument('--save', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    if cmd == 'snapshot':
        cur, hashed = scan(cfg, load_snapshot(cfg, a.name))
        save_snapshot(cfg, cur, a.name)
        print(f'snapshot "{a.name}": {len(cur)} files ({hashed} hashed)')
        return 0
    d = changed(cfg, a.name, save=a.save)
    if cmd == 'impact':
        res = dict(changed={k: d[k] for k in ('added', 'modified', 'removed')}, **impact(cfg, d))
        if a.json:
            print(json.dumps(res))
        else:
            n = sum(len(v) for v in res['changed'].values())
            print(f'{n} file(s) changed since snapshot "{a.name}"')
            for sid, fs in res['systems'].items():
                print(f'  {sid}: {", ".join(fs[:4])}{" …" if len(fs) > 4 else ""}')
            if res['downstream']:
                print(f'  feeds: {", ".join(res["downstream"])}')
        return 0
    if a.json:
        print(json.dumps(d))
    elif d.get('first_snapshot'):
        print(f'first look: snapshot of {d["files"]} files saved; run again to see changes')
    else:
        n = len(d['added']) + len(d['modified']) + len(d['removed'])
        print(f'{n} change(s) since snapshot "{a.name}" ({d["files"]} files, {d["hashed"]} re-hashed)')
        for k, sym in (('added', '+'), ('modified', '~'), ('removed', '-')):
            for f in d[k][:40]:
                print(f'  {sym} {f}')
            if len(d[k]) > 40:
                print(f'  {sym} … {len(d[k]) - 40} more')
    return 0

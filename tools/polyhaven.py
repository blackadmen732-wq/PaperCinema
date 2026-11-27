#!/usr/bin/env python3
"""POLYHAVEN: search and download CC0 HDRIs and PBR textures from Poly Haven (polyhaven.com, public API
api.polyhaven.com) into a local cache, and keep the credits file up to date.

  python3 tools/polyhaven.py search stone wall --type textures [--limit 20]   # id, name, categories, downloads
  python3 tools/polyhaven.py search night --type hdris
  python3 tools/polyhaven.py get castle_wall_slates [--res 2k]                # textures: diffuse, nor_gl, rough, disp, ao
  python3 tools/polyhaven.py get moonless_golf --res 2k                       # HDRIs: one .hdr
  python3 tools/polyhaven.py sync                                             # every id in library/polyhaven.json
  python3 tools/polyhaven.py list                                             # what is cached
  python3 tools/polyhaven.py credits                                          # rewrite assets/polyhaven/CREDITS.md

Cache: assets/polyhaven/<id>/<id>_<map>_<res>.<ext> + meta.json (not committed: .gitignore). CREDITS.md (committed)
records id, name, type, authors, licence (CC0) and the URL of every downloaded asset. The role -> asset id manifest
is library/polyhaven.json; Blender reads it through blender/world/paper_materials.py (ph_* helpers).
All Poly Haven assets are CC0 (public domain): commercial use OK, credit not required but we credit anyway (rule 6).
"""
import argparse
import json
import os
import sys
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CACHE = os.path.join(REPO, 'assets', 'polyhaven')
MANIFEST = os.path.join(REPO, 'library', 'polyhaven.json')
API = 'https://api.polyhaven.com'
UA = 'paper-cinema-asset-tool/1.0'          # Poly Haven asks API clients for a distinctive User-Agent
TYPES = {'hdris': 0, 'textures': 1, 'models': 2}
# texture map name in the API -> our short name
MAPS = {'Diffuse': 'diff', 'nor_gl': 'nor_gl', 'Rough': 'rough', 'Displacement': 'disp', 'AO': 'ao'}


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return data if binary else json.loads(data.decode('utf-8'))


def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return False
    tmp = path + '.part'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, 'wb') as f:
        while True:
            b = r.read(1 << 16)
            if not b:
                break
            f.write(b)
    os.replace(tmp, path)
    return True


def search(words, kind='textures', limit=25, category=None):
    url = f'{API}/assets?t={kind}' + (f'&c={category}' if category else '')
    assets = fetch(url)
    words = [w.lower() for w in words]
    hits = []
    for aid, a in assets.items():
        hay = ' '.join([aid, a.get('name', ''), ' '.join(a.get('tags', [])), ' '.join(a.get('categories', [])),
                        a.get('category', '') or '', a.get('description', '') or '']).lower()
        if all(w in hay for w in words):
            hits.append((a.get('download_count', 0), aid, a))
    hits.sort(key=lambda h: -h[0])
    for dl, aid, a in hits[:limit]:
        print(f'{aid:34s} {a.get("name", "")[:30]:30s} {dl:>7d}  {",".join(a.get("categories", []))[:60]}')
    print(f'({len(hits)} matches, {len(assets)} {kind})')
    return hits


def get(aid, res='2k', fmt=None, quiet=False):
    info = fetch(f'{API}/info/{aid}')
    files = fetch(f'{API}/files/{aid}')
    d = os.path.join(CACHE, aid)
    os.makedirs(d, exist_ok=True)
    kind = {v: k for k, v in TYPES.items()}[info['type']]
    got = {}
    if kind == 'hdris':
        fmt = fmt or 'hdr'
        r = res if res in files['hdri'] else sorted(files['hdri'], key=lambda s: int(s[:-1]))[0]
        f = files['hdri'][r][fmt]
        p = os.path.join(d, f'{aid}_{r}.{fmt}')
        new = download(f['url'], p)
        got['hdri'] = os.path.relpath(p, REPO)
        if not quiet:
            print(('downloaded ' if new else 'cached     ') + got['hdri'], f'{f["size"] / 1e6:.1f} MB')
    elif kind == 'textures':
        fmt = fmt or 'jpg'
        for api_name, short in MAPS.items():
            if api_name not in files:
                continue
            r = res if res in files[api_name] else '1k' if '1k' in files[api_name] else next(iter(files[api_name]))
            ent = files[api_name][r]
            ext = fmt if fmt in ent else ('png' if 'png' in ent else next(iter(ent)))
            # displacement as 16-bit png when available is overkill at our scale; jpg is fine
            f = ent[ext]
            p = os.path.join(d, f'{aid}_{short}_{r}.{ext}')
            new = download(f['url'], p)
            got[short] = os.path.relpath(p, REPO)
            if not quiet:
                print(('downloaded ' if new else 'cached     ') + got[short], f'{f["size"] / 1e6:.1f} MB')
    elif kind == 'models':
        # glTF + its own textures, kept at the relative paths the .gltf names (textures/<id>_<map>_<res>.jpg)
        r = res if res in files.get('gltf', {}) else '1k' if '1k' in files.get('gltf', {}) else next(iter(files['gltf']))
        g = files['gltf'][r]['gltf']
        p = os.path.join(d, f'{aid}_{r}.gltf')
        new = download(g['url'], p)
        for rel, inc in g.get('include', {}).items():
            q = os.path.join(d, rel)
            os.makedirs(os.path.dirname(q), exist_ok=True)
            download(inc['url'], q)
        got['gltf'] = os.path.relpath(p, REPO)
        if not quiet:
            print(('downloaded ' if new else 'cached     ') + got['gltf'], f'{len(g.get("include", {}))} files with it')
    else:
        raise SystemExit(f'{aid}: type {kind} not supported (hdris, textures, models)')
    meta = {'id': aid, 'name': info.get('name', aid), 'type': kind, 'authors': sorted(info.get('authors', {})),
            'licence': 'CC0', 'url': f'https://polyhaven.com/a/{aid}', 'res': res, 'files': got,
            'scale': info.get('scale'), 'dimensions_mm': info.get('dimensions'), 'categories': info.get('categories', [])}
    json.dump(meta, open(os.path.join(d, 'meta.json'), 'w'), indent=1)
    return meta


def cached():
    out = []
    if os.path.isdir(CACHE):
        for aid in sorted(os.listdir(CACHE)):
            mp = os.path.join(CACHE, aid, 'meta.json')
            if os.path.exists(mp):
                out.append(json.load(open(mp)))
    return out


def credits():
    rows = cached()
    lines = ['# Poly Haven assets (CC0)', '',
             'Every texture and HDRI below comes from [Poly Haven](https://polyhaven.com) and is **CC0** (public domain:',
             'commercial use allowed, no attribution required; we credit the authors anyway). Downloaded with',
             '`python3 tools/polyhaven.py sync` (the files themselves are not committed; this list is). Roles: `library/polyhaven.json`.',
             '', '| Id | Name | Type | Authors | Licence | Link |', '|---|---|---|---|---|---|']
    for m in rows:
        lines.append(f'| `{m["id"]}` | {m["name"]} | {m["type"][:-1]} | {", ".join(m["authors"])} | CC0 | {m["url"]} |')
    os.makedirs(CACHE, exist_ok=True)
    open(os.path.join(CACHE, 'CREDITS.md'), 'w').write('\n'.join(lines) + '\n')
    print(f'wrote assets/polyhaven/CREDITS.md ({len(rows)} assets)')


def manifest_ids():
    M = json.load(open(MANIFEST))
    ids = {}
    for group in ('textures', 'hdris', 'models'):
        for role, ent in M.get(group, {}).items():
            ids.setdefault(ent['id'], ent.get('res', M.get('res', {}).get(group, '1k' if group == 'models' else '2k')))
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('search'); s.add_argument('words', nargs='*'); s.add_argument('--type', default='textures', choices=list(TYPES))
    s.add_argument('--limit', type=int, default=25); s.add_argument('--category')
    g = sub.add_parser('get'); g.add_argument('ids', nargs='+'); g.add_argument('--res', default='2k'); g.add_argument('--format')
    sub.add_parser('sync'); sub.add_parser('list'); sub.add_parser('credits')
    a = ap.parse_args()
    if a.cmd == 'search':
        search(a.words, a.type, a.limit, a.category)
    elif a.cmd == 'get':
        for i in a.ids:
            get(i, a.res, a.format)
        credits()
    elif a.cmd == 'sync':
        for i, r in manifest_ids().items():
            get(i, r)
        credits()
    elif a.cmd == 'list':
        for m in cached():
            print(f'{m["id"]:34s} {m["type"]:9s} {m["res"]:4s} {m["name"]}  ({", ".join(m["authors"])})')
    elif a.cmd == 'credits':
        credits()


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""LIBRARY: PaperCinema's asset library in Supabase (Mark, 28 Nov: "the test we did with the bucket, put it in and
transform it to paper: that's what I want the library for"). Existing free models (Poly Haven, CC0), our generated
parts, their PAPER versions and a still of each, in one private bucket with one catalogue row per asset, so any
session on any machine can find a part, fetch it and build a scene from it.

    python3 tools/library.py put  <local file> <library path>     # e.g. poly-haven/wooden_bucket_01/original.glb
    python3 tools/library.py get  <library path> <local file>
    python3 tools/library.py ls   [prefix]
    python3 tools/library.py row  '<json>' | @file.json          # upsert a catalogue row: id, kind, source required
    python3 tools/library.py rows [--kind prop] [--tag village]
    python3 tools/library.py selftest                             # put, ls, get, row, rows on a scratch file

The project: papercinema (ref pkqbqlhgffqatgryofxt), bucket pc-library (private, 50 MB a file on the free plan), table
public.pc_library (columns: docs/LIBRARY.md). Access goes through the project's 'library' edge function
(supabase/functions/library/index.ts): it holds the service role, this tool holds only the LIBRARY TOKEN, read from
$PC_LIBRARY_TOKEN or ~/.pc-library-token, never from the repo. Files travel through signed URLs straight to and from
Storage.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PROJECT = 'pkqbqlhgffqatgryofxt'
FN = 'https://%s.supabase.co/functions/v1/library' % PROJECT
TYPES = {'.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json', '.bin': 'application/octet-stream', '.png': 'image/png',
         '.jpg': 'image/jpeg', '.json': 'application/json', '.blend': 'application/octet-stream', '.mp4': 'video/mp4',
         '.txt': 'text/plain'}


def token():
    t = os.environ.get('PC_LIBRARY_TOKEN')
    if not t:
        p = os.path.expanduser('~/.pc-library-token')
        t = open(p).read().strip() if os.path.exists(p) else ''
    if not t:
        sys.exit('[library] no token: set PC_LIBRARY_TOKEN or write it to ~/.pc-library-token (it is never in the repo)')
    return t


def call(op, data=None, method=None, **q):
    url = FN + '?' + urllib.parse.urlencode(dict(op=op, **{k: v for k, v in q.items() if v is not None}))
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method or ('POST' if body else 'GET'),
                                 headers={'x-pc-token': token(), 'Content-Type': 'application/json'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read() or b'null')
        except urllib.error.HTTPError as e:
            msg = e.read()[:400].decode(errors='replace')
            if e.code < 500 or attempt == 3:
                sys.exit('[library] %s refused (%d): %s' % (op, e.code, msg))
        except urllib.error.URLError as e:
            if attempt == 3:
                sys.exit('[library] %s failed: %s (is %s.supabase.co allowed by the network?)' % (op, e, PROJECT))
        time.sleep(2 ** attempt)


def put(local, path):
    size = os.path.getsize(local)
    if size > 50 * 1024 * 1024:
        sys.exit('[library] %s is %.1f MB: over the free plan\'s 50 MB a file' % (local, size / 1e6))
    signed = call('upload-url', path=path)
    url = signed['signedUrl'] if signed['signedUrl'].startswith('http') else 'https://%s.supabase.co/storage/v1%s' % (PROJECT, signed['signedUrl'])
    req = urllib.request.Request(url, data=open(local, 'rb').read(), method='PUT',
                                 headers={'Content-Type': TYPES.get(os.path.splitext(local)[1].lower(), 'application/octet-stream'),
                                          'x-upsert': 'true'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                r.read()
            print('[library] put %s -> %s (%.2f MB)' % (local, path, size / 1e6))
            return path
        except urllib.error.HTTPError as e:
            if attempt == 3:
                sys.exit('[library] upload of %s failed (%d): %s' % (path, e.code, e.read()[:300]))
        except urllib.error.URLError as e:
            if attempt == 3:
                sys.exit('[library] upload of %s failed: %s' % (path, e))
        time.sleep(2 ** attempt)


def get(path, local):
    signed = call('download-url', path=path)
    url = signed['signedUrl'] if signed['signedUrl'].startswith('http') else 'https://%s.supabase.co/storage/v1%s' % (PROJECT, signed['signedUrl'])
    os.makedirs(os.path.dirname(os.path.abspath(local)), exist_ok=True)
    with urllib.request.urlopen(url, timeout=600) as r, open(local, 'wb') as fh:
        fh.write(r.read())
    print('[library] got %s -> %s (%.2f MB)' % (path, local, os.path.getsize(local) / 1e6))
    return local


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd = a[0]
    if cmd == 'put' and len(a) == 3:
        put(a[1], a[2])
    elif cmd == 'get' and len(a) == 3:
        get(a[1], a[2])
    elif cmd == 'ls':
        for o in call('list', path=a[1] if len(a) > 1 else '') or []:
            meta = o.get('metadata') or {}
            print('%-50s %10s  %s' % (o['name'] + ('/' if not o.get('id') else ''), meta.get('size', ''), o.get('updated_at') or ''))
    elif cmd == 'row' and len(a) == 2:
        row = json.load(open(a[1][1:])) if a[1].startswith('@') else json.loads(a[1])
        print(json.dumps(call('upsert-row', data=row), indent=1))
    elif cmd == 'rows':
        kind = a[a.index('--kind') + 1] if '--kind' in a else None
        tag = a[a.index('--tag') + 1] if '--tag' in a else None
        rows = call('rows', kind=kind, tag=tag) or []
        for r in rows:
            print('%-40s %-14s %-10s paper=%s' % (r['id'], r['kind'], r['source'], r.get('paper_path') or '-'))
        print('[library] %d row(s)' % len(rows))
    elif cmd == 'selftest':
        import tempfile
        d = tempfile.mkdtemp()
        src = os.path.join(d, 'probe.txt')
        open(src, 'w').write('library selftest %s\n' % time.time())
        put(src, '_selftest/probe.txt')
        names = [o['name'] for o in call('list', path='_selftest') or []]
        assert 'probe.txt' in names, names
        get('_selftest/probe.txt', os.path.join(d, 'back.txt'))
        assert open(src).read() == open(os.path.join(d, 'back.txt')).read()
        call('upsert-row', data={'id': '_selftest/probe', 'kind': 'test', 'source': 'selftest', 'original_path': '_selftest/probe.txt'})
        assert any(r['id'] == '_selftest/probe' for r in call('rows', kind='test'))
        print('[library] selftest PASS: put, ls, get (same bytes), row, rows')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()

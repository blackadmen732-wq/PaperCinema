#!/usr/bin/env python3
"""TRIPO: generate images and 3D parts with the Tripo API, with every credit logged.

The key is never in this repo or in a variable: the session's network proxy adds it to requests to
api.tripo3d.ai (saved once with the secure form). Anything else (a machine with its own key) can set
TRIPO_API_KEY; the default placeholder is overwritten by the proxy.

    python3 tools/tripo.py balance
    python3 tools/tripo.py upload <image>                              -> prints a file token
    python3 tools/tripo.py image  --prompt "..." [--ref <image>] --out output/tripo/<name>     (concept image)
    python3 tools/tripo.py model  --image <image> --out output/tripo/<name> [--version v3.5-20260815]
                                  [--faces 8000] [--hd] [--quad] [--parts]                    (3D model)
    python3 tools/tripo.py model  --prompt "..." --out ...                                     (text to 3D)
    python3 tools/tripo.py fetch  <task_id> --out output/tripo/<name>                          (re-download)

Every finished task appends {task, type, params, credits, balance_before, balance_after, files} to
output/tripo/ledger.jsonl, so the cost of every part is a number. A task polls until it is done (or --timeout).
Outputs: <out>.png (rendered preview or image), <out>.glb (textured model), <out>.task.json (the raw answer).
"""
import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

API = 'https://api.tripo3d.ai/v2/openapi'
KEY = os.environ.get('TRIPO_API_KEY', 'proxy-injected')
UA = 'papercinema-tripo/1.0'
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, 'output', 'tripo', 'ledger.jsonl')


def call(method, path, body=None, files=None, timeout=120):
    url = path if path.startswith('http') else API + path
    # a User-Agent of our own: Cloudflare in front of the API refuses Python's default one (error 1010)
    headers = {'Authorization': f'Bearer {KEY}', 'User-Agent': UA}
    data = None
    if files:
        b = uuid.uuid4().hex
        parts = []
        for field, fpath in files.items():
            ctype = mimetypes.guess_type(fpath)[0] or 'application/octet-stream'
            parts.append((f'--{b}\r\nContent-Disposition: form-data; name="{field}"; filename="{os.path.basename(fpath)}"'
                          f'\r\nContent-Type: {ctype}\r\n\r\n').encode() + open(fpath, 'rb').read() + b'\r\n')
        data = b''.join(parts) + f'--{b}--\r\n'.encode()
        headers['Content-Type'] = f'multipart/form-data; boundary={b}'
    elif body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, status = r.read().decode(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode(errors='replace'), e.code
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit(f'tripo: {method} {path} -> HTTP {status}: {raw[:300]!r}')
    if out.get('code') != 0:
        raise SystemExit(f'tripo: {method} {path} -> {out}')
    return out['data']


def balance():
    return call('GET', '/user/balance')['balance']


def upload(path):
    d = call('POST', '/upload', files={'file': path})
    return d.get('image_token') or d.get('file_token')


def file_ref(path):
    ext = os.path.splitext(path)[1].lstrip('.').lower().replace('jpeg', 'jpg')
    return {'type': ext, 'file_token': upload(path)}


def download(url, dest):
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, 'wb') as f:
        f.write(r.read())
    return dest


def wait(task_id, timeout=900):
    t0, iv = time.time(), 3
    while True:
        d = call('GET', f'/task/{task_id}')
        st = d.get('status')
        print(f'  [{int(time.time() - t0):4d}s] {st} {d.get("progress", "")}%', flush=True)
        if st in ('success', 'failed', 'cancelled', 'banned', 'expired', 'unknown'):
            return d
        if time.time() - t0 > timeout:
            raise SystemExit(f'tripo: task {task_id} still {st} after {timeout}s (fetch it later: tools/tripo.py fetch {task_id})')
        time.sleep(iv)
        iv = min(iv * 1.5, 15)


def save(d, out):
    """Download every output of a finished task next to <out>; return the files written."""
    files = {}
    o = d.get('output') or {}
    for key, ext in (('model', 'glb'), ('pbr_model', 'pbr.glb'), ('base_model', 'base.glb'),
                     ('rendered_image', 'png'), ('generated_image', 'image.png'), ('image', 'image.png')):
        url = o.get(key)
        if isinstance(url, dict):
            url = url.get('url')
        if url:
            dest = f'{out}.{ext}'
            try:
                files[key] = download(url, dest)
            except Exception as e:               # a blocked CDN host is a setup problem, say so plainly
                files[key] = f'NOT DOWNLOADED ({e}): {url}'
    json.dump(d, open(f'{out}.task.json', 'w'), indent=1)
    return files


def run(task, out, timeout):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    b0 = balance()
    tid = call('POST', '/task', task)['task_id']
    print(f'[tripo] {task["type"]} task {tid} (balance {b0})', flush=True)
    d = wait(tid, timeout)
    files = save(d, out)
    b1 = balance()
    rec = {'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'task': tid, 'type': task['type'],
           'status': d.get('status'), 'params': {k: v for k, v in task.items() if k not in ('file', 'files')},
           'credits': b0 - b1, 'balance_before': b0, 'balance_after': b1, 'out': out, 'files': files}
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, 'a') as f:
        f.write(json.dumps(rec) + '\n')
    print(f'[tripo] {d.get("status")}: {b0 - b1} credits (balance {b1}) -> {files}')
    if d.get('status') != 'success':
        raise SystemExit(1)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['balance', 'upload', 'image', 'model', 'fetch'])
    ap.add_argument('arg', nargs='?')
    ap.add_argument('--prompt')
    ap.add_argument('--negative')
    ap.add_argument('--ref', action='append', help='reference image(s) for an image edit')
    ap.add_argument('--image', help='image to turn into a 3D model')
    ap.add_argument('--out')
    ap.add_argument('--version', help='model_version (default: the server default)')
    ap.add_argument('--faces', type=int, help='face_limit')
    ap.add_argument('--hd', action='store_true', help='texture_quality detailed')
    ap.add_argument('--quad', action='store_true')
    ap.add_argument('--parts', action='store_true', help='generate_parts')
    ap.add_argument('--no-texture', action='store_true')
    ap.add_argument('--seed', type=int)
    ap.add_argument('--timeout', type=int, default=900)
    a = ap.parse_args()
    if a.cmd == 'balance':
        print(balance())
    elif a.cmd == 'upload':
        print(upload(a.arg))
    elif a.cmd == 'fetch':
        d = call('GET', f'/task/{a.arg}')
        print(d.get('status'), save(d, a.out))
    elif a.cmd == 'image':
        if a.ref:
            refs = [file_ref(p) for p in a.ref]
            task = {'type': 'generate_image', 'prompt': a.prompt}
            task.update({'file': refs[0]} if len(refs) == 1 else {'files': refs})
        else:
            task = {'type': 'text_to_image', 'prompt': a.prompt}
        if a.negative:
            task['negative_prompt'] = a.negative
        if a.version:
            task['model_version'] = a.version
        run(task, a.out, a.timeout)
    elif a.cmd == 'model':
        task = {'type': 'image_to_model', 'file': file_ref(a.image)} if a.image else \
               {'type': 'text_to_model', 'prompt': a.prompt}
        if a.negative and not a.image:
            task['negative_prompt'] = a.negative
        if a.version:
            task['model_version'] = a.version
        if a.faces:
            task['face_limit'] = a.faces
        if a.no_texture:
            task['texture'] = False
        if a.hd:
            task['texture_quality'] = 'detailed'
        if a.quad:
            task['quad'] = True
        if a.parts:
            task['generate_parts'] = True
        if a.seed is not None:
            task['model_seed'] = a.seed
        run(task, a.out, a.timeout)


if __name__ == '__main__':
    main()

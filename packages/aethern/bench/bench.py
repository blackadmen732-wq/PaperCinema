#!/usr/bin/env python3
"""BENCH: measure what the core saves an agent, on a real project, with numbers only.

    python3 bench/bench.py --root <project> [--ids SOUND,COMBAT] [--old-builder tools/_old_build.py] [--out file.json]

What it measures (every number is measured here; the token figures are chars/4, a standard rough
estimate, because no tokenizer ships with the standard library):
  orient   bytes an agent must read to answer "what is system X, its files and command?":
           the whole Markdown map (what a project guide tells agents to read), a `grep -w X` over it
           (the cheapest thing an agent does instead), and `aethern map show X`
  deps     "what does X feed?": the whole JSON map vs `aethern map deps X --depth 3`
  owner    "which system owns file F?": the whole JSON map vs `aethern map owner F`
  change   ms for a cold scan, a warm no-change check and a one-file change, against `git status`
  build    ms to rebuild the JSON map: the project's old builder (if given) vs `aethern map build`
  cache    a stub model server: requests and ms for a first call and a repeat of the same call
"""
import argparse
import http.server
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from aethern import catalog, config, index, router  # noqa: E402

AE = [sys.executable, os.path.join(HERE, 'bin', 'aethern')]


def cli(root, *a):
    r = subprocess.run(AE + list(a), cwd=root, capture_output=True, text=True)
    return r.stdout


def ms(fn, n=7):
    xs = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t) * 1000)
    return round(statistics.median(xs), 1)


def tok(chars):
    return round(chars / 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--ids', default='')
    ap.add_argument('--files', default='')
    ap.add_argument('--old-builder')
    ap.add_argument('--out')
    a = ap.parse_args()
    root = os.path.realpath(a.root)
    cfg = config.load(root)
    c = cfg['catalog']
    md = open(cfg.path(c['source']), encoding='utf-8').read()
    js = open(cfg.path(c['out']), encoding='utf-8').read()
    doc = catalog.load(cfg)
    ids = [i for i in a.ids.split(',') if i] or [s['id'] for s in doc['systems'][:5]]
    res = {'project': cfg.get('name'), 'when': time.strftime('%Y-%m-%d %H:%M'), 'note': 'tokens = chars / 4 (estimate)'}

    rows = []
    for i in ids:
        out = cli(root, 'map', 'show', i)
        g = subprocess.run(['grep', '-n', '-w', i, cfg.path(c['source'])], capture_output=True, text=True).stdout
        rows.append({'id': i, 'before_chars': len(md), 'grep_chars': len(g), 'after_chars': len(out)})
    res['orient'] = {'rows': rows, 'before_tokens': tok(len(md)),
                     'grep_tokens_median': tok(statistics.median(r['grep_chars'] for r in rows)),
                     'after_tokens_median': tok(statistics.median(r['after_chars'] for r in rows))}

    drows = [{'id': i, 'before_chars': len(js), 'after_chars': len(cli(root, 'map', 'deps', i, '--depth', '3'))} for i in ids]
    res['deps'] = {'rows': drows, 'before_tokens': tok(len(js)), 'after_tokens_median': tok(statistics.median(r['after_chars'] for r in drows))}

    files = [f for f in a.files.split(',') if f] or [s['files'][0] for s in doc['systems'] if s['files']][:5]
    orows = [{'file': f, 'before_chars': len(js), 'after_chars': len(cli(root, 'map', 'owner', f))} for f in files]
    res['owner'] = {'rows': orows, 'before_tokens': tok(len(js)), 'after_tokens_median': tok(statistics.median(r['after_chars'] for r in orows))}

    res['entry'] = {'help_chars': len(cli(root, 'help')), 'cli_ms': ms(lambda: cli(root, 'help'), 5)}

    # change detection, on a throwaway snapshot name so the project's own snapshot is untouched
    name = 'bench'
    sp = index._snap_path(cfg, name)
    if os.path.exists(sp):
        os.remove(sp)
    t = time.perf_counter()
    d0 = index.changed(cfg, name)
    cold = round((time.perf_counter() - t) * 1000, 1)
    warm = ms(lambda: index.changed(cfg, name), 5)
    hashed_warm = index.changed(cfg, name)['hashed']
    probe = os.path.join(root, 'aethern.json')
    st = os.stat(probe)
    os.utime(probe, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    t = time.perf_counter()
    d1 = index.changed(cfg, name)
    touched = round((time.perf_counter() - t) * 1000, 1)
    os.utime(probe, ns=(st.st_atime_ns, st.st_mtime_ns))
    git = ms(lambda: subprocess.run(['git', 'status', '--porcelain'], cwd=root, capture_output=True), 5)
    os.remove(sp)
    res['change'] = {'files': d0['files'], 'cold_ms': cold, 'warm_ms': warm, 'warm_rehashed': hashed_warm,
                     'touch_ms': touched, 'touch_rehashed': d1['hashed'], 'touch_reported_modified': len(d1['modified']),
                     'git_status_ms': git}

    # build speed (the JSON map is rewritten by both; it must come out identical)
    before = open(cfg.path(c['out']), 'rb').read()
    b = {'new_ms': ms(lambda: subprocess.run(AE + ['map', 'build'], cwd=root, capture_output=True))}
    b['new_identical'] = open(cfg.path(c['out']), 'rb').read() == before
    if a.old_builder:
        b['old_ms'] = ms(lambda: subprocess.run([sys.executable, a.old_builder], cwd=root, capture_output=True))
        b['old_identical'] = open(cfg.path(c['out']), 'rb').read() == before
    res['build'] = b

    # result cache against a local stub (measures the cache, not a real model's latency)
    calls = {'n': 0}

    class Stub(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            calls['n'] += 1
            self.rfile.read(int(self.headers['Content-Length']))
            data = json.dumps({'choices': [{'message': {'content': 'ok'}}], 'usage': {'total_tokens': 10}}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *x):
            pass

    srv = http.server.HTTPServer(('127.0.0.1', 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tmp = tempfile.mkdtemp()
    json.dump({'ai': {'cache': True, 'models': {'s': {'url': f'http://127.0.0.1:{srv.server_port}/v1', 'model': 'm', 'tags': ['code']}},
                      'order': {'code': ['s']}}}, open(os.path.join(tmp, 'aethern.json'), 'w'))
    R = router.Router(config.load(tmp))
    t = time.perf_counter(); R.run('code', 'same prompt'); miss = (time.perf_counter() - t) * 1000
    t = time.perf_counter(); R.run('code', 'same prompt'); hit = (time.perf_counter() - t) * 1000
    srv.shutdown(); srv.server_close(); shutil.rmtree(tmp)
    res['cache'] = {'first_call_requests': 1, 'repeat_requests': calls['n'] - 1, 'first_ms_stub': round(miss, 1), 'repeat_ms': round(hit, 2)}

    out = json.dumps(res, indent=1, ensure_ascii=False)
    print(out)
    if a.out:
        open(a.out, 'w').write(out + '\n')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""ASSET VAULT: the heavy files of PaperCinema in one list, and their copy in Supabase Storage (Mark, 28 Nov: "push
the characters and the heavy ones to Supabase").

Why: output/ is not in git, so every paid original from Tripo (image -> 3D, 30 credits each) lives ONLY on the
session's disk. A new session starts on a fresh machine: those files would be gone, and only the prepared parts in
assets/models/ai would survive. The vault lists them (size, sha256, kind, what they cost) and uploads them.

    python3 tools/asset_vault.py list                      # writes output/asset-manifest.json, prints the totals
    python3 tools/asset_vault.py upload --project <ref> [--bucket papercinema] [--only tripo] [--dry-run]
    python3 tools/asset_vault.py sql                       # the catalogue table (paste into Supabase, or the connector)

Upload: the Supabase Storage REST API, POST https://<ref>.supabase.co/storage/v1/object/<bucket>/<path>. The key is
NEVER in this file or the chat: it is saved on the environment through the secure form, and the session's network
proxy adds it to requests for that host (the code sends a placeholder). Files already in the bucket with the same
sha256 (kept in output/asset-vault.json) are skipped, so an interrupted upload just carries on. Free plan: 1 GB in all,
50 MB per file (every file here is smaller; the check refuses a larger one rather than fail half-way).
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, 'output', 'asset-manifest.json')
STATE = os.path.join(REPO, 'output', 'asset-vault.json')
MAX_FILE = 50 * 1024 * 1024

# what is heavy and worth keeping: (kind, folder, file endings)
SOURCES = [
    ('tripo-original', 'output/tripo', ('.glb', '.png', '.task.json', '.txt', '.log')),
    ('prepared-part', 'assets/models/ai', ('.glb', '.json', '.png')),
    ('render', 'output', ('-final.mp4',)),
    ('bench', 'output/bench', ('.mp4',)),
]
CONTENT_TYPES = {'.glb': 'model/gltf-binary', '.png': 'image/png', '.json': 'application/json', '.txt': 'text/plain',
                 '.log': 'text/plain', '.mp4': 'video/mp4'}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def build():
    rows = []
    seen = set()
    for kind, folder, ends in SOURCES:
        base = os.path.join(REPO, folder)
        if not os.path.isdir(base):
            continue
        walk = os.walk(base) if kind != 'render' else [(base, [], os.listdir(base))]
        for d, _sub, files in walk:
            for fn in sorted(files):
                if not fn.endswith(ends):
                    continue
                p = os.path.join(d, fn)
                rel = os.path.relpath(p, REPO)
                if rel in seen or not os.path.isfile(p):
                    continue
                seen.add(rel)
                row = {'path': rel, 'kind': kind, 'bytes': os.path.getsize(p), 'sha256': sha256(p)}
                if fn.endswith('.task.json'):        # what a Tripo task was and what it cost
                    try:
                        t = json.load(open(p))
                        row['tripo'] = {'type': t.get('type'), 'credits': int(t.get('consumed_credit') or 0),
                                        'task_id': t.get('task_id')}
                    except (OSError, ValueError):
                        pass
                rows.append(row)
    man = {'made': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'files': rows,
           'totals': {}}
    for r in rows:
        t = man['totals'].setdefault(r['kind'], {'files': 0, 'bytes': 0})
        t['files'] += 1
        t['bytes'] += r['bytes']
    man['tripo_credits_in_originals'] = sum((r.get('tripo') or {}).get('credits', 0) for r in rows)
    man['too_big_for_free_plan'] = [r['path'] for r in rows if r['bytes'] > MAX_FILE]
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    json.dump(man, open(MANIFEST, 'w'), indent=1)
    return man


def upload(man, project, bucket, only=None, dry=False):
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    base = 'https://%s.supabase.co/storage/v1/object/%s/' % (project, bucket)
    todo = [r for r in man['files'] if (not only or r['kind'].startswith(only)) and state.get(r['path']) != r['sha256']]
    big = [r['path'] for r in todo if r['bytes'] > MAX_FILE]
    if big:
        sys.exit('[vault] over the free plan\'s 50 MB per file, not uploaded: %s' % big)
    print('[vault] %d file(s), %.1f MB to upload to %s (%d already there)' % (
        len(todo), sum(r['bytes'] for r in todo) / 1e6, base, len(man['files']) - len(todo)))
    for r in todo:
        if dry:
            print('  would upload', r['path'])
            continue
        ext = os.path.splitext(r['path'])[1]
        req = urllib.request.Request(base + r['path'], data=open(os.path.join(REPO, r['path']), 'rb').read(), method='POST',
                                     headers={'Content-Type': CONTENT_TYPES.get(ext, 'application/octet-stream'),
                                              'x-upsert': 'true',
                                              # placeholder: the network proxy replaces it with the saved key
                                              'Authorization': 'Bearer proxy-injected', 'apikey': 'proxy-injected'})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    resp.read()
                state[r['path']] = r['sha256']
                json.dump(state, open(STATE, 'w'), indent=1)
                print('  ok', r['path'], '%.1f MB' % (r['bytes'] / 1e6))
                break
            except urllib.error.HTTPError as e:
                body = e.read()[:300]
                if e.code in (401, 403):
                    sys.exit('[vault] refused (%d): no key for this host yet, or the bucket does not exist: %s' % (e.code, body))
                if attempt == 3:
                    sys.exit('[vault] %s failed: %d %s' % (r['path'], e.code, body))
            except urllib.error.URLError as e:
                if attempt == 3:
                    sys.exit('[vault] %s failed: %s' % (r['path'], e))
            time.sleep(2 ** attempt)


SQL = """-- PaperCinema parts catalogue: every part any session can reuse (docs/AI-PARTS.md; files in Storage bucket
-- 'papercinema', listed by tools/asset_vault.py). One row per part.
create table if not exists pc_parts (
  name        text primary key,              -- the part id in library/ai-parts.json (e.g. kabuto_t1)
  slot        text not null,                 -- head, hair, hat, mask, torso, sleeve, hand, leg, foot, weapon, prop...
  kind        text not null,                 -- rigid | section (bound to bones) | cloth | set-piece
  source      text not null,                 -- tripo | poly-haven | sketchfab | procedural | ...
  licence     text,                          -- CC0, CC-BY (credit line), own (generated)
  credits     integer default 0,             -- what it cost on Tripo
  file_path   text,                          -- the prepared part in the bucket (assets/models/ai/...)
  original    text,                          -- the paid original in the bucket (output/tripo/...)
  look_board  text,                          -- which of Mark's boards it came from, if any
  used_in     text[] default '{}',           -- recipes / films that wear it
  checked     text,                          -- the proof: validator result, the still it was judged on
  created_at  timestamptz default now()
);
alter table pc_parts enable row level security;   -- only the service key (the pipeline) reads and writes it
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['list', 'upload', 'sql'])
    ap.add_argument('--project', help='the Supabase project ref (the <ref> in https://<ref>.supabase.co)')
    ap.add_argument('--bucket', default='papercinema')
    ap.add_argument('--only', help='a kind prefix: tripo, prepared, render, bench')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if a.cmd == 'sql':
        print(SQL)
        return
    man = build()
    mb = lambda b: b / 1e6                                       # noqa: E731
    print('[vault] %d files, %.1f MB -> %s' % (len(man['files']), mb(sum(r['bytes'] for r in man['files'])),
                                               os.path.relpath(MANIFEST, REPO)))
    for k, t in sorted(man['totals'].items()):
        print('  %-15s %4d files  %7.1f MB' % (k, t['files'], mb(t['bytes'])))
    print('  Tripo credits in the originals: %d; over 50 MB (free plan): %s' % (
        man['tripo_credits_in_originals'], man['too_big_for_free_plan'] or 'none'))
    if a.cmd == 'upload':
        if not a.project:
            sys.exit('[vault] --project <ref> is needed')
        upload(man, a.project, a.bucket, a.only, a.dry_run)


if __name__ == '__main__':
    main()

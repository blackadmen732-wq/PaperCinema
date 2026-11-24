#!/usr/bin/env python3
"""FREE WORKER: gives the free models (NVIDIA Nemotron 550B, Kimi, Qwen) real tools, so they do the
heavy work instead of Claude agents. Costs nothing — the environment's proxy supplies the keys.

  python3 tools/worker.py "Add a docstring to every function in tools/polyhaven.py"
  python3 tools/worker.py --task-file brief.md --steps 40
  python3 tools/worker.py --model kimi "Find why film/x.json fails validate.mjs and fix it"
  python3 tools/worker.py --dry "..."            # show what it WOULD run, change nothing

How it works: the model is given a task and a small set of tools (read, write, list, search, run, look).
It answers with one JSON tool call per step; this script runs it, feeds the result back, and loops until
the model says DONE or the step budget runs out. A transcript lands in output/worker/<stamp>.md.

Safety (this runs unattended, so it is deliberately narrow):
  * every path must stay inside the repo
  * `run` uses an allow-list of commands, a timeout, and never a shell pipeline that deletes
  * writes are refused for AGENTS.md, .git/, gpu/ credentials and anything outside the repo
  * --dry shows the plan without touching anything
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai  # the model router (tools/ai.py)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGDIR = os.path.join(REPO, 'output', 'worker')
# commands a worker may run. Anything else is refused and the model is told why.
ALLOW = {
    'node', 'python3', 'bash', 'ls', 'cat', 'head', 'tail', 'grep', 'rg', 'find', 'wc', 'sed', 'awk',
    'git', 'diff', 'sort', 'uniq', 'cut', 'tr', 'jq', 'mkdir', 'cp', 'mv', 'touch', 'echo', 'test',
    'ffmpeg', 'ffprobe', 'pip', 'npm', 'npx',
}
DENY_RE = re.compile(r'(^|[\s;&|])(rm|rmdir|shred|mkfs|dd|chmod\s+777|curl[^|]*\|\s*(ba)?sh)\b')
PROTECT = ('AGENTS.md', '.git/', 'gpu/.pod.json', '.kaggle', 'skills-lock.json')

TOOLS = """You have these tools. Reply with ONE json object per step and nothing else:
{"tool":"read","path":"engine/figure.js","start":1,"lines":120}      read part of a file
{"tool":"list","path":"library"}                                      list a directory
{"tool":"search","pattern":"makeMotion","path":"engine"}              search file contents
{"tool":"write","path":"tools/x.py","content":"..."}                  write a whole file
{"tool":"patch","path":"tools/x.py","old":"exact text","new":"..."}   replace exact text once
{"tool":"run","cmd":"node engine/validate.mjs film/dash-test.json"}   run a command (120 s limit)
{"tool":"look","path":"output/stills/x.png","ask":"what is wrong?"}   a vision model looks at an image
{"tool":"done","summary":"what you changed and what you verified"}    finish
Rules: paths are relative to the repo root. Make ONE call per reply. No prose outside the json.
Verify your work by running something before you call done. If a tool fails, read the error and adapt."""


def inside(path):
    full = os.path.realpath(os.path.join(REPO, path))
    return full.startswith(REPO + os.sep) or full == REPO, full


def do_read(a):
    ok, full = inside(a.get('path', ''))
    if not ok:
        return 'refused: path outside the repo'
    if not os.path.exists(full):
        return f'no such file: {a["path"]}'
    start, n = int(a.get('start', 1)), int(a.get('lines', 200))
    with open(full, errors='replace') as f:
        rows = f.readlines()
    chunk = rows[start - 1:start - 1 + n]
    return f'{a["path"]} lines {start}-{start + len(chunk) - 1} of {len(rows)}:\n' + ''.join(
        f'{start + i:5}\t{l}' for i, l in enumerate(chunk))


def do_list(a):
    ok, full = inside(a.get('path', '.'))
    if not ok:
        return 'refused: path outside the repo'
    try:
        return '\n'.join(sorted(os.listdir(full))[:200])
    except Exception as e:
        return f'error: {e}'


def do_search(a):
    pat, path = a.get('pattern', ''), a.get('path', '.')
    ok, _ = inside(path)
    if not ok:
        return 'refused: path outside the repo'
    skip = ['--exclude-dir=' + d for d in ('.git', 'node_modules', 'output', 'assets', '__pycache__')]
    try:
        r = subprocess.run(['grep', '-rnE', '--max-count=4', '-I', *skip, pat, path], cwd=REPO,
                           capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return 'search timed out: narrow it with a smaller "path" (e.g. "engine" not ".")'
    return (r.stdout or 'no matches')[:4000]


def protected(path):
    return any(path.startswith(p) or p in path for p in PROTECT)


def do_write(a, dry):
    p = a.get('path', '')
    ok, full = inside(p)
    if not ok:
        return 'refused: path outside the repo'
    if protected(p):
        return f'refused: {p} is protected; ask the director to change it'
    if dry:
        return f'[dry] would write {len(a.get("content",""))} bytes to {p}'
    os.makedirs(os.path.dirname(full) or REPO, exist_ok=True)
    open(full, 'w').write(a.get('content', ''))
    return f'wrote {p} ({len(a.get("content",""))} bytes)'


def do_patch(a, dry):
    p = a.get('path', '')
    ok, full = inside(p)
    if not ok:
        return 'refused: path outside the repo'
    if protected(p):
        return f'refused: {p} is protected'
    if not os.path.exists(full):
        return f'no such file: {p}'
    s = open(full, errors='replace').read()
    old = a.get('old', '')
    if s.count(old) != 1:
        return f'refused: "old" appears {s.count(old)} times; it must appear exactly once'
    if dry:
        return f'[dry] would patch {p}'
    open(full, 'w').write(s.replace(old, a.get('new', '')))
    return f'patched {p}'


def do_run(a, dry):
    cmd = a.get('cmd', '')
    first = shlex.split(cmd)[0] if cmd.strip() else ''
    if first not in ALLOW:
        return f'refused: "{first}" is not allowed. Allowed: {", ".join(sorted(ALLOW))}'
    if DENY_RE.search(cmd):
        return 'refused: that command can delete or overwrite things; ask the director'
    if dry:
        return f'[dry] would run: {cmd}'
    try:
        r = subprocess.run(f'nice -n 15 {cmd}', shell=True, cwd=REPO, capture_output=True,
                           text=True, timeout=int(a.get('timeout', 120)))
        out = (r.stdout + r.stderr).strip()
        return f'exit {r.returncode}\n{out[-3000:] or "(no output)"}'
    except subprocess.TimeoutExpired:
        return 'timed out (the limit is 120 s; run something smaller)'
    except Exception as e:
        return f'error: {e}'


def do_look(a):
    ok, full = inside(a.get('path', ''))
    if not ok or not os.path.exists(full):
        return 'no such image'
    try:
        text, _ = ai.run('review', a.get('ask', 'What is wrong with this image?'),
                         image=ai.encode(full), max_tokens=700)
        return text
    except Exception as e:
        return f'vision model failed: {e}'


def step(call, dry):
    t = call.get('tool')
    return {
        'read': lambda: do_read(call), 'list': lambda: do_list(call), 'search': lambda: do_search(call),
        'write': lambda: do_write(call, dry), 'patch': lambda: do_patch(call, dry),
        'run': lambda: do_run(call, dry), 'look': lambda: do_look(call),
    }.get(t, lambda: f'unknown tool "{t}". Use one of: read list search write patch run look done')()


def extract(text):
    """Pull the first json object out of the model's reply."""
    text = text.strip()
    if '```' in text:
        text = re.sub(r'```(?:json)?', '', text)
    i = text.find('{')
    while i >= 0:
        depth, in_str, esc = 0, False, False
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if esc: esc = False
                elif c == '\\': esc = True
                elif c == '"': in_str = False
            elif c == '"': in_str = True
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i:j + 1])
                    except Exception:
                        break
        i = text.find('{', i + 1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task', nargs='*')
    ap.add_argument('--task-file')
    ap.add_argument('--model', default=None, help='nemotron (default) | kimi | gptoss-cerebras | qwen-cerebras')
    ap.add_argument('--steps', type=int, default=25)
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    task = open(a.task_file).read() if a.task_file else ' '.join(a.task)
    if not task.strip():
        raise SystemExit('give it a task')

    os.makedirs(LOGDIR, exist_ok=True)
    log = os.path.join(LOGDIR, time.strftime('%m%d-%H%M%S') + '.md')
    hist = [f'TASK: {task}']
    print(f'worker on {a.model or "nemotron"} · {a.steps} steps · log {log}', flush=True)

    for n in range(1, a.steps + 1):
        prompt = (f'{TOOLS}\n\nYou are working in the Paper Cinema repo (vertical paper-craft samurai films).\n'
                  f'TASK: {task}\n\nWhat happened so far:\n' + '\n'.join(hist[-14:]) +
                  '\n\nYour next tool call (json only):')
        try:
            reply, meta = ai.run('code', prompt, model=a.model or 'nemotron', max_tokens=3000)
        except SystemExit as e:
            print('no model answered:', e); break
        call = extract(reply)
        if not call:
            hist.append('STEP: your reply had no json tool call. Reply with ONE json object only.')
            continue
        if call.get('tool') == 'done':
            hist.append(f'DONE: {call.get("summary", "")}')
            print(f'\n✓ done in {n} steps: {call.get("summary", "")}')
            break
        shown = {k: (v[:120] + '…' if isinstance(v, str) and len(v) > 120 else v) for k, v in call.items()}
        print(f'  {n:2}. {json.dumps(shown)[:160]}', flush=True)
        try:
            result = step(call, a.dry)
        except Exception as e:
            result = f'that tool call raised {type(e).__name__}: {e}. Try a different approach.'
        hist.append(f'STEP {n}: {json.dumps(shown)[:400]}\nRESULT: {result[:1500]}')
    else:
        print(f'\n! step budget ({a.steps}) used up')

    open(log, 'w').write('\n\n'.join(hist))
    print(f'transcript: {log}')


if __name__ == '__main__':
    main()

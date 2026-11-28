"""FREE WORKER: gives free models real tools (read, list, search, write, patch, run, look, map), so they
do multi-step work instead of a paid agent. Extracted from Paper Cinema's tools/worker.py.

    aethern worker "Add a docstring to every function in tools/x.py"
    aethern worker --task-file brief.md --steps 40
    aethern worker --model kimi "..."        aethern worker --dry "..."   (plan only, changes nothing)

The model answers with one JSON tool call per step; this runs it, feeds the result back, and loops
until the model says done or the step budget runs out. A transcript lands in the worker log dir.

Safety (this runs unattended, so it is deliberately narrow):
  * every path must stay inside the project root
  * `run` uses an allow-list of commands, a timeout, and refuses commands that delete, reset or push
  * writes are refused for protected paths (aethern.json `worker.protect`)
  * --dry shows the plan without touching anything
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import time

from . import config as _config
from . import router as _router

ALLOW = {
    'node', 'python3', 'bash', 'ls', 'cat', 'head', 'tail', 'grep', 'rg', 'find', 'wc', 'sed', 'awk',
    'git', 'diff', 'sort', 'uniq', 'cut', 'tr', 'jq', 'mkdir', 'cp', 'mv', 'touch', 'echo', 'test',
    'ffmpeg', 'ffprobe', 'pip', 'npm', 'npx',
}
# The Paper Cinema list caught rm/dd/mkfs and curl|sh. It let through `find -delete`, `git clean`,
# `git reset --hard`, `git checkout -- .` and `git push`, each of which destroys or publishes work
# just as surely, so those are refused too.
DENY_RE = re.compile(r'(^|[\s;&|])(rm|rmdir|shred|mkfs|dd|chmod\s+777|curl[^|]*\|\s*(ba)?sh)\b'
                     r'|\s-delete\b|\bgit\s+(clean|push|reset\s+--hard|checkout\s+--\s)')

TOOLS = """You have these tools. Reply with ONE json object per step and nothing else:
{"tool":"read","path":"src/app.py","start":1,"lines":120}             read part of a file
{"tool":"list","path":"src"}                                          list a directory
{"tool":"search","pattern":"def main","path":"src"}                   search file contents
{"tool":"write","path":"src/x.py","content":"..."}                    write a whole file
{"tool":"patch","path":"src/x.py","old":"exact text","new":"..."}     replace exact text once
{"tool":"run","cmd":"python3 -m unittest"}                            run a command (120 s limit)
{"tool":"look","path":"out/frame.png","ask":"what is wrong?"}         a vision model looks at an image
{"tool":"done","summary":"what you changed and what you verified"}    finish
Rules: paths are relative to the repo root. Make ONE call per reply. No prose outside the json.
Verify your work by running something before you call done. If a tool fails, read the error and adapt."""
MAP_TOOL = f'{chr(123)}"tool":"map","q":"API"{chr(125):<47}the project map: a system id, a file, or words'


class Worker:
    def __init__(self, cfg=None, root=None, router=None):
        self.cfg = cfg or _config.load(root)
        self.root = self.cfg.root
        w = self.cfg['worker']
        self.protect = tuple(w.get('protect', []))
        self.allow = ALLOW | set(w.get('allow_extra', []))
        self.project = w.get('project', '')
        self.model = w.get('model', 'nemotron')
        self.log_dir = self.cfg.path(w.get('log_dir', '.aethern/cache/worker'))
        self.router = router or _router.Router(self.cfg)
        self.has_map = bool(self.cfg.get('catalog'))
        self.tools_text = TOOLS if not self.has_map else TOOLS.replace(
            '\n{"tool":"done"', '\n' + MAP_TOOL + '\n{"tool":"done"', 1)

    def inside(self, path):
        full = os.path.realpath(os.path.join(self.root, path))
        return full.startswith(self.root + os.sep) or full == self.root, full

    def protected(self, path):
        return any(path.startswith(p) or p in path for p in self.protect)

    def do_read(self, a):
        ok, full = self.inside(a.get('path', ''))
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

    def do_list(self, a):
        ok, full = self.inside(a.get('path', '.'))
        if not ok:
            return 'refused: path outside the repo'
        try:
            return '\n'.join(sorted(os.listdir(full))[:200])
        except Exception as e:
            return f'error: {e}'

    def do_search(self, a):
        pat, path = a.get('pattern', ''), a.get('path', '.')
        ok, _ = self.inside(path)
        if not ok:
            return 'refused: path outside the repo'
        skip = ['--exclude-dir=' + d for d in ('.git', 'node_modules', 'output', 'assets', '__pycache__')]
        try:
            r = subprocess.run(['grep', '-rnE', '--max-count=4', '-I', *skip, pat, path], cwd=self.root,
                               capture_output=True, text=True, timeout=45)
        except subprocess.TimeoutExpired:
            return 'search timed out: narrow it with a smaller "path" (e.g. "src" not ".")'
        return (r.stdout or 'no matches')[:4000]

    def do_write(self, a, dry):
        p = a.get('path', '')
        ok, full = self.inside(p)
        if not ok:
            return 'refused: path outside the repo'
        if self.protected(p):
            return f'refused: {p} is protected; ask the director to change it'
        if dry:
            return f'[dry] would write {len(a.get("content",""))} bytes to {p}'
        os.makedirs(os.path.dirname(full) or self.root, exist_ok=True)
        open(full, 'w').write(a.get('content', ''))
        return f'wrote {p} ({len(a.get("content",""))} bytes)'

    def do_patch(self, a, dry):
        p = a.get('path', '')
        ok, full = self.inside(p)
        if not ok:
            return 'refused: path outside the repo'
        if self.protected(p):
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

    def do_run(self, a, dry):
        cmd = a.get('cmd', '')
        try:
            first = shlex.split(cmd)[0] if cmd.strip() else ''
        except ValueError as e:
            return f'refused: cannot parse the command ({e})'
        if first not in self.allow:
            return f'refused: "{first}" is not allowed. Allowed: {", ".join(sorted(self.allow))}'
        if DENY_RE.search(cmd):
            return 'refused: that command can delete, reset or publish things; ask the director'
        if dry:
            return f'[dry] would run: {cmd}'
        try:
            r = subprocess.run(f'nice -n 15 {cmd}', shell=True, cwd=self.root, capture_output=True,
                               text=True, timeout=int(a.get('timeout', 120)))
            out = (r.stdout + r.stderr).strip()
            return f'exit {r.returncode}\n{out[-3000:] or "(no output)"}'
        except subprocess.TimeoutExpired:
            return 'timed out (the limit is 120 s; run something smaller)'
        except Exception as e:
            return f'error: {e}'

    def do_look(self, a):
        ok, full = self.inside(a.get('path', ''))
        if not ok or not os.path.exists(full):
            return 'no such image'
        try:
            text, _ = self.router.run('review', a.get('ask', 'What is wrong with this image?'),
                                      image=_router.encode(full), max_tokens=700)
            return text
        except BaseException as e:
            return f'vision model failed: {e}'

    def do_map(self, a):
        from . import catalog
        return catalog.answer(self.cfg, str(a.get('q', '')))

    def step(self, call, dry):
        t = call.get('tool')
        return {
            'read': lambda: self.do_read(call), 'list': lambda: self.do_list(call), 'search': lambda: self.do_search(call),
            'write': lambda: self.do_write(call, dry), 'patch': lambda: self.do_patch(call, dry),
            'run': lambda: self.do_run(call, dry), 'look': lambda: self.do_look(call), 'map': lambda: self.do_map(call),
        }.get(t, lambda: f'unknown tool "{t}". Use one of: read list search write patch run look{" map" if self.has_map else ""} done')()

    def work(self, task, model=None, steps=25, dry=False, out=print):
        os.makedirs(self.log_dir, exist_ok=True)
        log = os.path.join(self.log_dir, time.strftime('%m%d-%H%M%S') + '.md')
        hist = [f'TASK: {task}']
        out(f'worker on {model or self.model} · {steps} steps · log {log}')
        for n in range(1, steps + 1):
            prompt = (f'{self.tools_text}\n\n{self.project}\n'
                      f'TASK: {task}\n\nWhat happened so far:\n' + '\n'.join(hist[-14:]) +
                      '\n\nYour next tool call (json only):')
            try:
                reply, meta = self.router.run('code', prompt, model=model or self.model, max_tokens=3000, fresh=True)
            except SystemExit as e:
                out(f'no model answered: {e}')
                break
            call = extract(reply)
            if not call:
                hist.append('STEP: your reply had no json tool call. Reply with ONE json object only.')
                continue
            if call.get('tool') == 'done':
                hist.append(f'DONE: {call.get("summary", "")}')
                out(f'\n✓ done in {n} steps: {call.get("summary", "")}')
                break
            shown = {k: (v[:120] + '…' if isinstance(v, str) and len(v) > 120 else v) for k, v in call.items()}
            out(f'  {n:2}. {json.dumps(shown)[:160]}')
            try:
                result = self.step(call, dry)
            except Exception as e:
                result = f'that tool call raised {type(e).__name__}: {e}. Try a different approach.'
            hist.append(f'STEP {n}: {json.dumps(shown)[:400]}\nRESULT: {result[:1500]}')
        else:
            out(f'\n! step budget ({steps}) used up')
        open(log, 'w').write('\n\n'.join(hist))
        out(f'transcript: {log}')
        return hist


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


def main(argv=None, worker=None, prog='aethern worker'):
    ap = argparse.ArgumentParser(prog=prog)
    ap.add_argument('task', nargs='*')
    ap.add_argument('--task-file')
    ap.add_argument('--model', default=None, help='nemotron (default) | kimi | gptoss-cerebras | qwen-cerebras')
    ap.add_argument('--steps', type=int, default=25)
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv)
    task = open(a.task_file).read() if a.task_file else ' '.join(a.task)
    if not task.strip():
        raise SystemExit('give it a task')
    W = worker or Worker()
    W.work(task, model=a.model, steps=a.steps, dry=a.dry, out=lambda s: print(s, flush=True))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""AI ROUTER: send heavy work to free models, keep Claude usage for direction.

  python3 tools/ai.py write "A 20 s ronin monologue before a duel"        # text/story/code
  python3 tools/ai.py review output/stills/x.png "worst 3 problems?"      # look at an image
  python3 tools/ai.py review output/frames-dt --sheet 12 "rate the dash"  # a folder → contact sheet
  python3 tools/ai.py think "why does the dash read as sliding?"          # hard reasoning
  python3 tools/ai.py list                                                # what is reachable, with speeds
  python3 tools/ai.py --model nemotron write "..."                        # force one model
  python3 tools/ai.py budget                                              # calls + time saved so far

Why: rendering needs a GPU (Kaggle), but writing, code and looking at frames are text work that
free models do well. Every call that goes here is Claude usage NOT spent (AGENTS.md rule 02).
Keys are injected by the environment's proxy, so no secrets live in this file (rule 7).
"""
import argparse
import base64
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(REPO, 'output', 'ai-usage.jsonl')

# host, model, what it is good at, rough tokens/second seen here
MODELS = {
    'qwen-cerebras':  dict(url='https://api.cerebras.ai/v1',        model='qwen-3.8-27b',                        tags={'write', 'code', 'quick'}, note='fastest'),
    'gptoss-cerebras': dict(url='https://api.cerebras.ai/v1',       model='gpt-oss-120b',                        tags={'write', 'code', 'think'},  note='fast, bigger'),
    'qwen-groq':      dict(url='https://api.groq.com/openai/v1',    model='qwen/qwen3.8-27b',                    tags={'write', 'code', 'quick'}, note='fast'),
    'gptoss-groq':    dict(url='https://api.groq.com/openai/v1',    model='openai/gpt-oss-120b',                 tags={'write', 'code', 'think'},  note='fast, bigger'),
    'nemotron':       dict(url='https://integrate.api.nvidia.com/v1', model='nvidia/nemotron-3-ultra-550b-a55b', tags={'think', 'write', 'code'},  note='550B, strongest free'),
    'vl-nemotron':    dict(url='https://integrate.api.nvidia.com/v1', model='nvidia/nemotron-3.5-super-vl-120b-a12b', tags={'review'},             note='sees images'),
    'glm-vl':         dict(url='https://integrate.api.nvidia.com/v1', model='z-ai/glm-5.3-flash',                tags={'review', 'write'},         note='sees images'),
    'kimi':           dict(url='https://integrate.api.nvidia.com/v1', model='moonshotai/kimi-k3.1-pro',          tags={'think', 'write', 'code'},  note='Kimi K3.1 Pro'),
    # paid, only used when OpenRouter has credit
    'kimi-or':        dict(url='https://openrouter.ai/api/v1',      model='moonshotai/kimi-k3.1-pro',            tags={'think', 'write'}, paid=True),
    'glm-or':         dict(url='https://openrouter.ai/api/v1',      model='z-ai/glm-5.3',                        tags={'think', 'write'}, paid=True),
}
# who to try, in order, per job
ORDER = {
    'write':  ['qwen-cerebras', 'qwen-groq', 'gptoss-cerebras', 'nemotron', 'kimi'],
    'code':   ['gptoss-cerebras', 'qwen-cerebras', 'gptoss-groq', 'nemotron'],
    'think':  ['nemotron', 'kimi', 'gptoss-cerebras', 'gptoss-groq'],
    'quick':  ['qwen-cerebras', 'qwen-groq'],
    'review': ['vl-nemotron', 'glm-vl'],
}
SYSTEM = ('Answer directly with the final answer only: no thinking out loud, no preamble.\n'
          'You work for Paper Cinema: cinematic paper-craft samurai Shorts, vertical 9:16, folded washi '
          'characters lit from inside (amber = human, crimson = demonic), red paint instead of blood, '
          'anime timing (slow wind-up, 3-4 frame snap, settle). Be concrete and brief: numbers, frame counts, '
          'file names. No filler, no apologies, no restating the question.')


def call(name, messages, max_tokens=900, timeout=300, temperature=0.6):
    m = MODELS[name]
    body = {'model': m['model'], 'max_tokens': max_tokens, 'temperature': temperature, 'messages': messages}
    req = urllib.request.Request(m['url'] + '/chat/completions', json.dumps(body).encode(),
                                 {'Authorization': 'Bearer proxy-injected', 'Content-Type': 'application/json'})
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=timeout))
    msg = d.get('choices', [{}])[0].get('message', {}) or {}
    text = msg.get('content') or ''
    if not text.strip():                       # some models put everything in the thinking field
        text = msg.get('reasoning_content') or ''
        for mark in ('**Final Answer', 'Final answer', '</think>', 'FINAL:'):
            if mark in text:
                text = text.split(mark, 1)[1]
                break
    if not text.strip():
        raise RuntimeError('empty answer')
    usage = d.get('usage', {})
    return text.strip(), dict(model=name, secs=round(time.time() - t0, 1),
                              tokens=usage.get('completion_tokens'), total=usage.get('total_tokens'))


def run(job, prompt, image=None, model=None, max_tokens=900):
    """Try the models for this job in order; first good answer wins."""
    content = prompt if not image else [{'type': 'text', 'text': prompt},
                                        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + image}}]
    messages = ([] if image else [{'role': 'system', 'content': SYSTEM}]) + [{'role': 'user', 'content': content}]
    tried = []
    for name in ([model] if model else ORDER[job]):
        if MODELS[name].get('paid') and os.environ.get('AI_ALLOW_PAID') != '1':
            continue
        try:
            text, meta = call(name, messages, max_tokens=max_tokens)
            meta.update(job=job, ok=True, at=time.strftime('%F %T'))
            note(meta)
            return text, meta
        except Exception as e:
            tried.append(f'{name}: {str(e)[:80]}')
    raise SystemExit('no model answered:\n  ' + '\n  '.join(tried))


def note(meta):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'a') as f:
        f.write(json.dumps(meta) + '\n')


def sheet(folder, n, out):
    """Make one contact sheet from a folder of frames, so a vision model sees the whole shot at once."""
    from PIL import Image
    files = sorted(glob.glob(os.path.join(folder, '*.jpg')) + glob.glob(os.path.join(folder, '*.png')))
    if not files:
        raise SystemExit(f'no frames in {folder}')
    pick = [files[round(i * (len(files) - 1) / max(n - 1, 1))] for i in range(min(n, len(files)))]
    ims = [Image.open(p).convert('RGB') for p in pick]
    w = 260
    h = round(w * ims[0].height / ims[0].width)
    cols = min(6, len(ims))
    rows = (len(ims) + cols - 1) // cols
    W = Image.new('RGB', (w * cols, h * rows))
    for i, im in enumerate(ims):
        W.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    W.save(out, quality=85)
    return out, len(pick)


def encode(path, px=1100):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    im.thumbnail((px, px))
    tmp = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'ai-img.jpg')
    im.save(tmp, quality=82)
    return base64.b64encode(open(tmp, 'rb').read()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job', choices=['write', 'code', 'think', 'quick', 'review', 'list', 'budget'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--model')
    ap.add_argument('--sheet', type=int, default=12, help='frames to sample when reviewing a folder')
    ap.add_argument('--max-tokens', type=int, default=1400)
    ap.add_argument('--out', help='write the answer to this file too')
    a = ap.parse_args()

    if a.job == 'list':
        print(f"{'name':16} {'job tags':26} {'ok':4} note")
        for n, m in MODELS.items():
            if m.get('paid') and os.environ.get('AI_ALLOW_PAID') != '1':
                print(f'{n:16} {",".join(sorted(m["tags"])):26} paid {m.get("note","needs OpenRouter credit")}')
                continue
            try:
                _, meta = call(n, [{'role': 'user', 'content': 'say OK'}], max_tokens=60, timeout=120)
                ok = f'{meta["secs"]}s'
            except Exception as e:
                ok = 'no'
            print(f'{n:16} {",".join(sorted(m["tags"])):26} {ok:4} {m.get("note","")}')
        return

    if a.job == 'budget':
        if not os.path.exists(LOG):
            print('no calls yet')
            return
        rows = [json.loads(l) for l in open(LOG)]
        secs = sum(r.get('secs', 0) for r in rows)
        toks = sum(r.get('total') or 0 for r in rows)
        by = {}
        for r in rows:
            by[r['model']] = by.get(r['model'], 0) + 1
        print(f'{len(rows)} calls off Claude · {toks:,} tokens · {secs/60:.1f} min of model time')
        for k, v in sorted(by.items(), key=lambda x: -x[1]):
            print(f'  {v:4}  {k}')
        return

    if a.job == 'review':
        target = a.args[0]
        prompt = ' '.join(a.args[1:]) or 'List the worst visual problems, with what to change. Be specific.'
        if os.path.isdir(target):
            tmp = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'ai-sheet.jpg')
            target, n = sheet(target, a.sheet, tmp)
            prompt = f'These {n} frames are a time sequence from one shot. ' + prompt
        text, meta = run('review', prompt, image=encode(target), model=a.model, max_tokens=a.max_tokens)
    else:
        text, meta = run(a.job, ' '.join(a.args), model=a.model, max_tokens=a.max_tokens)

    print(text)
    print(f'\n--- {meta["model"]} · {meta["secs"]}s · {meta.get("tokens")} tokens (Claude usage saved)', file=sys.stderr)
    if a.out:
        open(a.out, 'w').write(text + '\n')


if __name__ == '__main__':
    main()

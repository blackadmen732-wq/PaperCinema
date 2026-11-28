"""AI ROUTER: send heavy text and image work to free models, so the expensive agent only directs.

Extracted from Paper Cinema's tools/ai.py. What changed on the way out:
  * the model table, the fallback order, the system prompt and every path come from aethern.json
  * an optional result CACHE: the same job, model chain and prompt answered within `cache_ttl_days`
    is returned from disk with no network call (`--fresh` skips it). Cached answers are logged with
    "cached": true, so `budget` counts calls avoided, not only calls moved.

    aethern ai write "prompt"            aethern ai review img.png "question"
    aethern ai review frames/ --sheet 12 aethern ai think "..."   aethern ai list   aethern ai budget
"""
import argparse
import base64
import glob
import hashlib
import json
import os
import sys
import time
import urllib.request

from . import config as _config

# host, model, what it is good at. Same table Paper Cinema used; a project can replace it in aethern.json.
MODELS = {
    'qwen-cerebras':  dict(url='https://api.cerebras.ai/v1',        model='qwen-3.8-27b',                        tags={'write', 'code', 'quick'}, note='fastest'),
    'gptoss-cerebras': dict(url='https://api.cerebras.ai/v1',       model='gpt-oss-120b',                        tags={'write', 'code', 'think'},  note='fast, bigger'),
    'qwen-groq':      dict(url='https://api.groq.com/openai/v1',    model='qwen/qwen3.8-27b',                    tags={'write', 'code', 'quick'}, note='fast'),
    'gptoss-groq':    dict(url='https://api.groq.com/openai/v1',    model='openai/gpt-oss-120b',                 tags={'write', 'code', 'think'},  note='fast, bigger'),
    'nemotron':       dict(url='https://integrate.api.nvidia.com/v1', model='nvidia/nemotron-3-ultra-550b-a55b', tags={'think', 'write', 'code'},  note='550B, strongest free'),
    'vl-nemotron':    dict(url='https://integrate.api.nvidia.com/v1', model='nvidia/nemotron-3.5-super-vl-120b-a12b', tags={'review'},             note='sees images'),
    'glm-vl':         dict(url='https://integrate.api.nvidia.com/v1', model='z-ai/glm-5.3-flash',                tags={'review', 'write'},         note='sees images'),
    'kimi':           dict(url='https://integrate.api.nvidia.com/v1', model='moonshotai/kimi-k3.1-pro',          tags={'think', 'write', 'code'},  note='Kimi K3.1 Pro'),
    # OmniRoute (MIT, github.com/cheaper-inference/OmniRoute): a local gateway over 400 models with
    # automatic fallback, so a rate-limited provider does not stop the work.
    'omni':           dict(url='http://localhost:20128/v1',        model='auto',                                tags={'write', 'code', 'think', 'quick'}, note='gateway, auto-fallback'),
    'omni-code':      dict(url='http://localhost:20128/v1',        model='auto/best-coding',                    tags={'code', 'think'},                   note='gateway, coding route'),
    # paid, only used when OpenRouter has credit
    'kimi-or':        dict(url='https://openrouter.ai/api/v1',      model='moonshotai/kimi-k3.1-pro',            tags={'think', 'write'}, paid=True),
    'glm-or':         dict(url='https://openrouter.ai/api/v1',      model='z-ai/glm-5.3',                        tags={'think', 'write'}, paid=True),
}
ORDER = {
    'write':  ['qwen-cerebras', 'qwen-groq', 'gptoss-cerebras', 'nemotron', 'kimi', 'omni'],
    'code':   ['gptoss-cerebras', 'qwen-cerebras', 'gptoss-groq', 'nemotron', 'omni-code'],
    'think':  ['nemotron', 'kimi', 'gptoss-cerebras', 'gptoss-groq', 'omni-code'],
    'quick':  ['qwen-cerebras', 'qwen-groq', 'omni'],
    'review': ['vl-nemotron', 'glm-vl'],
}


class Router:
    def __init__(self, cfg=None, root=None):
        self.cfg = cfg or _config.load(root)
        a = self.cfg['ai']
        self.models = {k: dict(v, tags=set(v.get('tags', []))) for k, v in a['models'].items()} if a.get('models') else MODELS
        self.order = a.get('order') or ORDER
        self.system = a['system']
        self.log = self.cfg.path(a['log'])
        self.omni_key_file = os.path.expanduser(a['omni_key_file'])
        self.cache = bool(a.get('cache'))
        self.ttl = float(a.get('cache_ttl_days', 7)) * 86400
        self.cache_dir = os.path.join(self.cfg.path(self.cfg['cache_dir']), 'ai')

    # ------------------------------------------------------------------ one call
    def key_for(self, name):
        if name.startswith('omni'):
            try:
                return open(self.omni_key_file).read().strip()
            except Exception:
                return 'no-omniroute-key'
        return 'proxy-injected'

    def call(self, name, messages, max_tokens=900, timeout=300, temperature=0.6):
        m = self.models[name]
        body = {'model': m['model'], 'max_tokens': max_tokens, 'temperature': temperature, 'messages': messages}
        req = urllib.request.Request(m['url'] + '/chat/completions', json.dumps(body).encode(),
                                     {'Authorization': 'Bearer ' + self.key_for(name), 'Content-Type': 'application/json'})
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

    # ------------------------------------------------------------------ cache
    def _cache_path(self, job, chain, messages, max_tokens):
        h = hashlib.sha1(json.dumps([job, chain, messages, max_tokens], sort_keys=True).encode()).hexdigest()
        return os.path.join(self.cache_dir, h[:2], h + '.json')

    def _cache_get(self, p):
        try:
            if time.time() - os.path.getmtime(p) > self.ttl:
                return None
            with open(p) as f:
                return json.load(f)
        except Exception:
            return None

    def _cache_put(self, p, text, meta):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + '.tmp'
        with open(tmp, 'w') as f:
            json.dump({'text': text, 'meta': meta}, f)
        os.replace(tmp, p)

    # ------------------------------------------------------------------ the router
    def run(self, job, prompt, image=None, model=None, max_tokens=900, fresh=False):
        """Try the models for this job in order; first good answer wins."""
        content = prompt if not image else [{'type': 'text', 'text': prompt},
                                            {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + image}}]
        messages = ([] if image else [{'role': 'system', 'content': self.system}]) + [{'role': 'user', 'content': content}]
        chain = [model] if model else self.order[job]
        cp = self._cache_path(job, chain, messages, max_tokens) if self.cache else None
        if cp and not fresh:
            hit = self._cache_get(cp)
            if hit:
                meta = dict(hit['meta'], cached=True, secs=0, at=time.strftime('%F %T'))
                self.note(meta)
                return hit['text'], meta
        tried = []
        for name in chain:
            if self.models[name].get('paid') and os.environ.get('AI_ALLOW_PAID') != '1':
                continue
            try:
                text, meta = self.call(name, messages, max_tokens=max_tokens)
                meta.update(job=job, ok=True, at=time.strftime('%F %T'))
                self.note(meta)
                if cp:
                    self._cache_put(cp, text, meta)
                return text, meta
            except Exception as e:
                tried.append(f'{name}: {str(e)[:80]}')
        raise SystemExit('no model answered:\n  ' + '\n  '.join(tried))

    def note(self, meta):
        os.makedirs(os.path.dirname(self.log), exist_ok=True)
        with open(self.log, 'a') as f:
            f.write(json.dumps(meta) + '\n')

    def budget(self):
        if not os.path.exists(self.log):
            print('no calls yet')
            return
        rows = [json.loads(l) for l in open(self.log) if l.strip()]
        live = [r for r in rows if not r.get('cached')]
        hits = len(rows) - len(live)
        secs = sum(r.get('secs', 0) for r in live)
        toks = sum(r.get('total') or 0 for r in live)
        by = {}
        for r in rows:
            by[r['model']] = by.get(r['model'], 0) + 1
        print(f'{len(rows)} calls off Claude · {toks:,} tokens · {secs/60:.1f} min of model time'
              + (f' · {hits} answered from cache' if hits else ''))
        for k, v in sorted(by.items(), key=lambda x: -x[1]):
            print(f'  {v:4}  {k}')


# ---------------------------------------------------------------------- images
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


# ---------------------------------------------------------------------- CLI
def main(argv=None, router=None, prog='aethern ai'):
    R = router or Router()
    ap = argparse.ArgumentParser(prog=prog)
    ap.add_argument('job', choices=['write', 'code', 'think', 'quick', 'review', 'list', 'budget'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--model')
    ap.add_argument('--sheet', type=int, default=12, help='frames to sample when reviewing a folder')
    ap.add_argument('--max-tokens', type=int, default=1400, help='reasoning models need 3000+ for code')
    ap.add_argument('--out', help='write the answer to this file too')
    ap.add_argument('--fresh', action='store_true', help='skip the result cache for this call')
    a = ap.parse_args(argv)

    if a.job == 'list':
        print(f"{'name':16} {'job tags':26} {'ok':4} note")
        for n, m in R.models.items():
            if m.get('paid') and os.environ.get('AI_ALLOW_PAID') != '1':
                print(f'{n:16} {",".join(sorted(m["tags"])):26} paid {m.get("note","needs OpenRouter credit")}')
                continue
            try:
                _, meta = R.call(n, [{'role': 'user', 'content': 'say OK'}], max_tokens=60, timeout=120)
                ok = f'{meta["secs"]}s'
            except Exception:
                ok = 'no'
            print(f'{n:16} {",".join(sorted(m["tags"])):26} {ok:4} {m.get("note","")}')
        return

    if a.job == 'budget':
        R.budget()
        return

    if a.job in ('think', 'code') and a.max_tokens < 3000:
        a.max_tokens = 3000                      # reasoning models burn tokens thinking before the answer
    if a.job == 'review':
        target = a.args[0]
        prompt = ' '.join(a.args[1:]) or 'List the worst visual problems, with what to change. Be specific.'
        if os.path.isdir(target):
            tmp = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'ai-sheet.jpg')
            target, n = sheet(target, a.sheet, tmp)
            prompt = f'These {n} frames are a time sequence from one shot. ' + prompt
        text, meta = R.run('review', prompt, image=encode(target), model=a.model, max_tokens=a.max_tokens, fresh=a.fresh)
    else:
        text, meta = R.run(a.job, ' '.join(a.args), model=a.model, max_tokens=a.max_tokens, fresh=a.fresh)

    print(text)
    tail = 'from cache, no model call' if meta.get('cached') else f'{meta["secs"]}s · {meta.get("tokens")} tokens'
    print(f'\n--- {meta["model"]} · {tail} (Claude usage saved)', file=sys.stderr)
    if a.out:
        open(a.out, 'w').write(text + '\n')


if __name__ == '__main__':
    main()

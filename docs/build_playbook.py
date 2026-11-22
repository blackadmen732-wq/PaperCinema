"""Rebuild docs/playbook.html from the real film data, so the page never drifts from the film.

    python3 docs/build_playbook.py                      # uses film/ganryujima.json
    python3 docs/build_playbook.py film/<name>.json     # another film

Injects: the film JSON (shots, camera keys, shakes, titles, sound cues), the sound credits
(assets/sfx/credits.json) and one thumbnail per shot (rendered with engine/render.mjs --still).
"""
import base64, io, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = sys.argv[1] if len(sys.argv) > 1 else 'film/ganryujima.json'
film = json.load(open(os.path.join(ROOT, src)))

# one still per shot, taken from the middle of the shot (or the impact for shots that contain one)
from PIL import Image
thumbs = {}
times = []
for s in film['shots']:
    hits = [h['t'] + 0.1 for h in film.get('shakes', []) if s['start'] <= h['t'] < s['end']]
    times.append((s['id'], f"{round(hits[0] if hits else (s['start'] + s['end']) / 2, 2):g}"))
subprocess.run(['node', 'engine/render.mjs', '--film', src, '--still', ','.join(str(t) for _, t in times), '--prefix', 'pb-'],
               cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
bar = max(0, (film['height'] - film['width'] / film.get('letterbox', film['width'] / film['height'])) / 2)
for sid, t in times:
    im = Image.open(os.path.join(ROOT, f'output/stills/pb-t{t}.png')).convert('RGB')
    im = im.crop((0, int(bar), im.width, int(im.height - bar))).resize((480, int(480 * (im.height - 2 * bar) / im.width)))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=72)
    thumbs[sid] = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()

cred_path = os.path.join(ROOT, 'assets/sfx/credits.json')
credits = json.load(open(cred_path)) if os.path.exists(cred_path) else {}
credits = {k: {f: v.get(f) for f in ('title', 'creator', 'license', 'url')} for k, v in credits.items()}

html = open(os.path.join(ROOT, 'docs/playbook.template.html')).read()
html = (html.replace('/*FILM_JSON*/null', json.dumps(film, ensure_ascii=False))
            .replace('/*THUMBS*/{}', json.dumps(thumbs))
            .replace('/*CREDITS*/{}', json.dumps(credits, ensure_ascii=False))
            .replace('/*SRC*/"film/ganryujima.json"', json.dumps(src)))
open(os.path.join(ROOT, 'docs/playbook.html'), 'w').write(html)
print('wrote docs/playbook.html', f'({len(html) // 1024} KB, {len(thumbs)} thumbnails)')

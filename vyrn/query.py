"""Questions an agent asks of a processed piece of media. Every answer is short text (or --json), states its
confidence, and points to evidence instead of including pictures."""
import json, math, os, subprocess
from vyrn.store import cache_dir


def _fmt_t(t):
    return f'{t:.2f}s'


def _conf(c):
    return '' if c is None or c >= 0.999 else f' ~{c:.2f}'


LOW_CONF = 0.6


def inspect(st, ref, width=240):
    """the targeted look: one PNG strip of the frames before, at and after an event (or a time), cropped to the
    entities it involves when they are known. Made once and cached; an agent opens it only when the numbers are
    not enough (a low-confidence event, a disagreement, a question about appearance)."""
    m = st.media()
    src = m['stats'].get('render') or m['source']
    if src.endswith('.json'):
        return 'no picture: native (data) source; ingest with --render <video> to inspect', None
    fps = m['fps']
    ev = None
    try:
        t = float(ref)
    except ValueError:
        evs = [e for e in st.events() if e['id'] == ref]
        if not evs:
            return f'no event {ref}', None
        ev = evs[0]; t = ev['t0']
    f = int(round(t * fps))
    key = f'strip_{f}_{ev["id"] if ev else "t"}_{width}'
    row = st.q('SELECT path FROM evidence WHERE key=?', key)
    if row and os.path.exists(row[0][0]):
        return row[0][0], {'frames': [f - 1, f, f + 1]}
    box = None
    ents = (ev or {}).get('entities') or []
    boxes = []
    for e in ents:
        r = st.samples(e, f, f)
        if r and r[0]['x'] is not None:
            boxes.append((r[0]['x'], r[0]['y'], r[0]['x'] + r[0]['w'], r[0]['y'] + r[0]['h']))
    if boxes:
        x0 = max(0, min(b[0] for b in boxes) - 0.05); y0 = max(0, min(b[1] for b in boxes) - 0.05)
        x1 = min(1, max(b[2] for b in boxes) + 0.05); y1 = min(1, max(b[3] for b in boxes) + 0.05)
        box = [x0, y0, x1, y1]
    d = os.path.join(cache_dir(), m['id']); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, f'ev_{key}.png')
    vf = [f'select=between(n\\,{max(0, f - 1)}\\,{f + 1})']
    if box:
        vf.append(f'crop=iw*{box[2] - box[0]:.4f}:ih*{box[3] - box[1]:.4f}:iw*{box[0]:.4f}:ih*{box[1]:.4f}')
    vf += [f'scale={width}:-2', 'tile=3x1']
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', src, '-vf', ','.join(vf), '-frames:v', '1', out],
                   check=True)
    st.db.execute('INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?,?,?)',
                  (key, f, f / fps, 'strip', json.dumps(box), out, os.path.getsize(out)))
    st.commit()
    return out, {'frames': [f - 1, f, f + 1], 'box': box}


def _look(st, evs, limit=3):
    """confidence-based fallback: for the lowest-confidence events in an answer, point at a picture to check"""
    low = sorted([e for e in evs if e['conf'] is not None and e['conf'] < LOW_CONF and
                  not e['type'].startswith('sound') and e['source'] != 'engine'], key=lambda e: e['conf'])[:limit]
    lines = []
    for e in low:
        try:
            p, _ = inspect(st, e['id'])
            lines.append(f"  check {e['id']} (conf {e['conf']:.2f}): {p}")
        except Exception as ex:          # no picture available: say so, do not fail the answer
            lines.append(f"  check {e['id']} (conf {e['conf']:.2f}): no picture ({ex.__class__.__name__})")
    return lines


def summary(st):
    m = st.media()
    ents = st.entities()
    evs = st.events()
    counts = {}
    for e in evs:
        counts[e['type']] = counts.get(e['type'], 0) + 1
    lines = [f"{m['id']} {m['kind']} {os.path.basename(m['source'])}: {m['duration']:.2f}s {m['fps']:g}fps "
             f"{m['width']}x{m['height']}, {m['frames']} frames"]
    shots = m['stats'].get('shots')
    if shots:
        lines.append('shots: ' + ', '.join(f"{s['f0'] / m['fps']:.2f}-{(s['f1'] + 1) / m['fps']:.2f}s"
                                          + (' pan' if s['pan_px_per_frame'] > 0.3 else '') for s in shots))
    elif any(e['type'] == 'cut' for e in evs):
        lines.append('cuts: ' + ', '.join(_fmt_t(e['t0']) for e in evs if e['type'] == 'cut'))
    lines.append('entities: ' + ', '.join(
        f"{e['id']}({e['kind']}, {e['first_f'] / m['fps']:.1f}-{e['last_f'] / m['fps']:.1f}s{_conf(e['confidence'])})"
        for e in ents if e['kind'] != 'camera'))
    lines.append('events: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    return '\n'.join(lines), {'media': m, 'entities': ents, 'event_counts': counts}


def _motion(st, eid, f0, f1, fps):
    s = [r for r in st.samples(eid, f0, f1) if r['x'] is not None]
    if not s:
        return None
    a, b = s[0], s[-1]
    cx = lambda r: (r['x'] + r['w'] / 2, r['y'] + r['h'] / 2)
    (ax, ay), (bx, by) = cx(a), cx(b)
    sp = [r for r in s if r['speed'] is not None]
    pk = max(sp, key=lambda r: r['speed']) if sp else None
    merged = sum(1 for r in s if r['conf'] < 0.5)
    world = a['wx'] is not None
    d = {'entity': eid, 'from': [round(ax, 3), round(ay, 3)], 'to': [round(bx, 3), round(by, 3)],
         'peak_speed': round(pk['speed'], 3) if pk else None, 'peak_t': pk['t'] if pk else None,
         'unit': 'm/s (world)' if world else 'frame-heights/s (screen)', 'low_conf_frames': merged}
    return d


def window(st, t0, t1):
    m = st.media(); fps = m['fps']
    f0, f1 = int(math.floor(t0 * fps)), int(math.ceil(t1 * fps))
    evs = [e for e in st.events(t0, t1) if not e['type'].startswith('cue') or True]
    lines = [f'{_fmt_t(t0)}-{_fmt_t(t1)}:']
    for e in evs:
        who = ','.join(e['entities'])
        extra = ''
        d = e['data']
        if 'side' in d:
            extra = f" {d['side']}"
        if 'foot' in d:
            extra = f" {d['foot']}"
        if 'sfx' in d:
            extra = f" {d['sfx']}"
        if 'offset_ms' in d:
            extra = f" sound {d['offset_ms']:+.0f} ms"
        dur = f"-{_fmt_t(e['t1'])}" if e['t1'] - e['t0'] > 1e-6 else ''
        lines.append(f"  {_fmt_t(e['t0'])}{dur} {e['type']}{(' ' + who) if who else ''}{extra}{_conf(e['conf'])} [{e['id']}]")
    mot = []
    for ent in st.entities():
        if ent['kind'] in ('camera',):
            continue
        r = _motion(st, ent['id'], f0, f1, fps)
        if r:
            mot.append(r)
            lines.append(f"  {r['entity']}: centre {r['from']} -> {r['to']}, peak {r['peak_speed']} {r['unit']} at "
                         f"{_fmt_t(r['peak_t']) if r['peak_t'] is not None else '-'}"
                         + (f", {r['low_conf_frames']} uncertain frames (overlap)" if r['low_conf_frames'] else ''))
    rel = st.q('SELECT a,b,kind,t0,t1,value,conf FROM relations WHERE t1>=? AND t0<=? ORDER BY t0', t0, t1)
    for a, b, k, r0, r1, v, c in rel:
        lines.append(f'  {a}~{b} {k} {_fmt_t(r0)}-{_fmt_t(r1)} (min {v:.2f}){_conf(c)}')
    lines += _look(st, evs)
    return '\n'.join(lines), {'events': evs, 'motion': mot, 'relations': rel}


def when(st, pattern, entity=None):
    types = [pattern if '*' in pattern or '.' in pattern else pattern + '*']
    evs = st.events(types=types)
    if entity:
        evs = [e for e in evs if entity in e['entities']]
    if not evs:
        types2 = ['%' + pattern + '%']
        evs = st.events(types=types2)
    def label(e):
        g = e['data'].get('guess')
        o = e['data'].get('offset_ms')
        return (f" {g.split(' ')[0]}" if g else '') + (f' sound {o:+.0f}ms' if o is not None else '')
    txt = f'{pattern}: ' + (', '.join(f"{_fmt_t(e['t0'])}{label(e)}{_conf(e['conf'])}" for e in evs) if evs else 'none found')
    look = _look(st, evs)
    return txt + ('\n' + '\n'.join(look) if look else ''), evs


def track(st, entity, t0=None, t1=None, step=4, joint=None):
    fps = st.media()['fps']
    f0 = int(t0 * fps) if t0 is not None else None
    f1 = int(t1 * fps) if t1 is not None else None
    if joint:
        rows = st.q('SELECT f,sx,sy,wx,wy,wz,conf FROM joints WHERE entity=? AND joint=? AND (? IS NULL OR f>=?) '
                    'AND (? IS NULL OR f<=?) ORDER BY f', entity, joint, f0, f0, f1, f1)
        rows = rows[::step]
        txt = f'{entity}.{joint} (t: screen x,y | world x,y,z m):\n' + '\n'.join(
            f'  {f / fps:.2f}: {sx:.3f},{sy:.3f} | {wx:.2f},{wy:.2f},{wz:.2f}' for f, sx, sy, wx, wy, wz, c in rows)
        return txt, rows
    rows = st.samples(entity, f0, f1)[::step]
    txt = f'{entity} (t: box x,y,w,h in frame units, speed):\n' + '\n'.join(
        f"  {r['t']:.2f}: {r['x']:.3f},{r['y']:.3f},{r['w']:.3f},{r['h']:.3f} sp {r['speed'] or 0:.2f}{_conf(r['conf'])}"
        for r in rows if r['x'] is not None)
    return txt, rows


def relation(st, a, b, t0=None, t1=None):
    m = st.media(); fps = m['fps']
    sig = st.signal(f'dist.{a}~{b}') or st.signal(f'dist.{b}~{a}')
    lines = []
    out = {}
    if sig:
        v = list(sig['values'])
        i0 = int((t0 or 0) * fps); i1 = int((t1 if t1 is not None else len(v) / fps) * fps)
        seg = v[i0:i1 + 1]
        j = min(range(len(seg)), key=lambda k: seg[k])
        lines.append(f'{a}~{b} world distance: {seg[0]:.2f} m -> {seg[-1]:.2f} m, closest {seg[j]:.2f} m at '
                     f'{(i0 + j) / fps:.2f}s')
        out['distance'] = {'start': seg[0], 'end': seg[-1], 'min': seg[j], 'min_t': (i0 + j) / fps}
    else:
        sa = {r['f']: r for r in st.samples(a)}; sb = {r['f']: r for r in st.samples(b)}
        common = sorted(f for f in set(sa) & set(sb) if (t0 is None or f >= t0 * fps) and (t1 is None or f <= t1 * fps))
        if common:
            c = lambda r: (r['x'] + r['w'] / 2, r['y'] + r['h'] / 2)
            ds = [(f, math.dist(c(sa[f]), c(sb[f]))) for f in common]
            fmin, dmin = min(ds, key=lambda x: x[1])
            lines.append(f'{a}~{b} screen centre distance: {ds[0][1]:.3f} -> {ds[-1][1]:.3f} frame units, closest '
                         f'{dmin:.3f} at {fmin / fps:.2f}s (screen only: depth unknown)')
            out['distance'] = {'start': ds[0][1], 'end': ds[-1][1], 'min': dmin, 'min_t': fmin / fps}
        else:
            lines.append(f'{a} and {b} are never on screen together')
    rel = st.q('SELECT kind,t0,t1,value,conf FROM relations WHERE ((a=? AND b=?) OR (a=? AND b=?)) ORDER BY t0', a, b, b, a)
    for k, r0, r1, v, c in rel:
        if (t0 is None or r1 >= t0) and (t1 is None or r0 <= t1):
            lines.append(f'  {k} {_fmt_t(r0)}-{_fmt_t(r1)}{_conf(c)}')
    out['relations'] = rel
    return '\n'.join(lines), out


def _expected_from(path):
    """expected sound times from a timeline (its cue events), Sonic's report output/<film>.sonic.json (a list of
    picks: peakAt is the moment the sound is aimed at, t is where the file starts), or any shared-format events
    file (.jsonl, e.g. output/<film>.sonic.events.jsonl, whose t is already the aimed moment)"""
    if path.endswith('.jsonl'):
        exp = []
        for line in open(path, encoding='utf-8'):
            if line.strip():
                e = json.loads(line)
                d = e.get('data') or {}
                exp.append({'id': e['id'], 't': e['t'], 'what': d.get('sound', e['type']), 'why': d.get('cue')})
        return exp
    j = json.load(open(path, encoding='utf-8'))
    exp = []
    if isinstance(j, dict) and j.get('format') == 'paper-cinema-timeline':
        for e in j.get('events', []):
            if e['type'] == 'cue':
                # the cue's own time is the intended sound time; `why` names the visual event it belongs to
                exp.append({'id': e['id'], 't': e['t'], 'what': e.get('sfx', ''), 'why': e.get('why')})
        return exp
    rows = j if isinstance(j, list) else j.get('picks', [])
    for p in rows:
        t = p.get('peakAt', p.get('t'))
        if t is not None:
            exp.append({'id': p.get('cue', p.get('id', '')), 't': t, 'what': p.get('sound', p.get('pick', '')),
                        'why': p.get('cue')})
    return exp


SOUNDING = ('blade-contact', 'impact', 'footstep', 'ground', 'paper-cut')


def verify(st, truth, tol=0.1):
    """independent sync check: the measured sound of a FINAL render against the film's own picture events
    (blade contacts, impacts, footsteps, ground hits, paper cuts) from its timeline. It ignores the cue list and
    Sonic's picks entirely, so a cue placed at the wrong time is caught instead of being taken as the reference.
    Reports per event type, the overall offset (a whole track shifted) and the outliers."""
    j = json.load(open(truth, encoding='utf-8'))
    fps = st.media()['fps']
    ons = st.events(types=['sound.onset'])
    rows, used = [], set()
    for e in sorted(j.get('events', []), key=lambda e: e['t']):
        if e['type'] not in SOUNDING:
            continue
        c = [o for o in ons if abs(o['t0'] - e['t']) <= tol and o['id'] not in used]
        if c:
            o = min(c, key=lambda o: abs(o['t0'] - e['t'])); used.add(o['id'])
            rows.append({'id': e['id'], 'type': e['type'], 't': e['t'], 'onset': o['t0'],
                         'offset_ms': round((o['t0'] - e['t']) * 1000, 1)})
        else:
            rows.append({'id': e['id'], 'type': e['type'], 't': e['t'], 'onset': None, 'offset_ms': None})
    m = [r for r in rows if r['offset_ms'] is not None]
    half = 1000 / (2 * fps)
    lines = [f'picture events with a sound in {os.path.basename(truth)} vs onsets measured in the render: '
             f'{len(m)}/{len(rows)} heard within {tol * 1000:.0f} ms']
    if m:
        offs = sorted(r['offset_ms'] for r in m)
        med = offs[len(offs) // 2]
        lines.append(f'  overall offset {med:+.1f} ms (median); mean |offset| {sum(abs(x) for x in offs) / len(offs):.1f} ms')
    by = {}
    for r in rows:
        k = by.setdefault(r['type'], [0, 0]); k[0] += 1; k[1] += r['offset_ms'] is not None
    lines.append('  by type: ' + ', '.join(f'{k} {v[1]}/{v[0]}' for k, v in by.items()))
    for r in m:
        if abs(r['offset_ms']) > half:
            lines.append(f"  {r['id']} at {_fmt_t(r['t'])}: sound {'late' if r['offset_ms'] > 0 else 'early'} by {abs(r['offset_ms']):.0f} ms")
    silent = [r for r in rows if r['offset_ms'] is None]
    if silent:
        lines.append('  no sound heard for: ' + ', '.join(f"{r['id']}@{r['t']:.2f}" for r in silent[:10])
                     + (f' (+{len(silent) - 10} more)' if len(silent) > 10 else ''))
    return '\n'.join(lines), {'rows': rows, 'unexplained': [o['t0'] for o in ons if o['id'] not in used]}


def sync(st, expect=None, tol=0.1, visual=None):
    """is the sound in sync? Each expected moment (cue, or a visual impact) is matched to the nearest measured
    sound onset within tol seconds; the offset is measured minus expected (positive = sound late)."""
    ons = st.events(types=['sound.onset'])
    lines, rows = [], []
    if expect:
        targets = _expected_from(expect)
        title = f'expected sounds from {os.path.basename(expect)}'
        if visual:
            # grade against the visual event each cue belongs to, not the cue's own (possibly wrong) time
            src = json.load(open(expect)) if expect.endswith('.json') else {}
            vt = {e['id']: e['t'] for e in (src.get('events', []) if isinstance(src, dict) else [])}
            for x in targets:
                if x.get('why') in vt:
                    x['t'] = vt[x['why']]
            title += ' (graded against the visual events the cues belong to)'
    else:
        vis = st.events(types=['motion.freeze', 'blade-contact', 'impact'])
        targets = [{'id': e['id'], 't': e['data'].get('impact_t', e['t0']), 'what': e['type']} for e in vis]
        title = 'visual impacts vs sound onsets'
    used = set()
    for x in targets:
        cands = [o for o in ons if abs(o['t0'] - x['t']) <= tol and o['id'] not in used]
        if not cands:
            rows.append({**x, 'onset': None, 'offset_ms': None})
            continue
        o = min(cands, key=lambda o: abs(o['t0'] - x['t']))
        used.add(o['id'])
        rows.append({**x, 'onset': o['t0'], 'offset_ms': round((o['t0'] - x['t']) * 1000, 1), 'conf': o['conf']})
    matched = [r for r in rows if r['offset_ms'] is not None]
    bad = [r for r in matched if abs(r['offset_ms']) > 1000 / (2 * st.media()['fps'])]
    lines.append(f'{title}: {len(matched)}/{len(rows)} matched within {tol * 1000:.0f} ms')
    if matched:
        mae = sum(abs(r['offset_ms']) for r in matched) / len(matched)
        lines.append(f'  mean |offset| {mae:.1f} ms; out of sync (> half a frame): {len(bad)}')
    for r in bad:
        lines.append(f"  {r['id']} {r.get('what', '')} at {_fmt_t(r['t'])}: sound {'late' if r['offset_ms'] > 0 else 'early'} by {abs(r['offset_ms']):.0f} ms")
    for r in rows:
        if r['offset_ms'] is None:
            lines.append(f"  {r['id']} {r.get('what', '')} at {_fmt_t(r['t'])}: no sound found")
    extra = [o for o in ons if o['id'] not in used]
    if expect and extra:
        lines.append(f'  unexpected onsets: ' + ', '.join(_fmt_t(o['t0']) for o in extra[:12]))
    return '\n'.join(lines), {'rows': rows, 'unexpected': [o['t0'] for o in extra]}


def evidence(st, t, entity=None, pad=0.15, width=320):
    """one frame (or a crop around an entity) as a PNG, extracted once and cached; returns its path"""
    m = st.media()
    src = m['stats'].get('render') or m['source']
    if src.endswith('.json'):
        return 'no picture: this is a native (data) source; ingest the rendered video, or pass --render when ingesting', None
    fps = m['fps']; f = int(round(t * fps))
    box = None
    if entity:
        r = st.samples(entity, f, f)
        if not r or r[0]['x'] is None:
            return f'{entity} is not on screen at {t:.2f}s', None
        r = r[0]
        box = [max(0, r['x'] - pad * r['w']), max(0, r['y'] - pad * r['h']),
               min(1, r['x'] + r['w'] * (1 + pad)), min(1, r['y'] + r['h'] * (1 + pad))]
    key = f"{f}_{entity or 'frame'}_{width}"
    row = st.q('SELECT path FROM evidence WHERE key=?', key)
    if row and os.path.exists(row[0][0]):
        return row[0][0], box
    d = os.path.join(cache_dir(), m['id']); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, f'ev_{key}.png')
    vf = []
    if box:
        x0, y0, x1, y1 = box
        vf.append(f'crop=iw*{x1 - x0:.4f}:ih*{y1 - y0:.4f}:iw*{x0:.4f}:ih*{y0:.4f}')
    vf.append(f'scale={width}:-2')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{f / fps:.4f}', '-i', src, '-frames:v', '1',
                    '-vf', ','.join(vf), out], check=True)
    st.db.execute('INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?,?,?)',
                  (key, f, f / fps, 'crop' if box else 'frame', json.dumps(box), out, os.path.getsize(out)))
    st.commit()
    return out, box

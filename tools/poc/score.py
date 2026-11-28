#!/usr/bin/env python3
"""Blind planted-defect benchmark, step 3 of 3: the independent evaluator. THE ONLY reader of the answer key.

  python3 tools/poc/score.py

It loads output/poc/truth.json and the clean film + clean events (poc-clean.*) -- which the detector/
repairer (run.py) never sees -- and grades run.py's output for three films:

  poc-defect   four planted defects. Graded on:
     detection     did a finding land on each planted defect's real location (no being told where)?
     metadata      is each repaired value close to the clean answer? (the "right number" test)
     perceptual    does the detector that caught it now pass on the repaired film/events? (the "actually
                   fixed" test -- re-rendered geometry, re-posed feet, re-measured cue/contact gaps)
     preservation  did anything OUTSIDE the four defects change between clean and fixed?
  poc-control  a clean film: any defect finding is a FALSE POSITIVE.
  poc-style    one real defect (D2) plus a declared intentional silent contact: D2 must be caught and the
               silent beat must NOT be "repaired".

Metadata-correct and perceptually-correct are reported separately on purpose: a cue can sit at the right
time (metadata) without the mixed audio being right, and a repair can satisfy the constraint (perceptual)
without matching the clean value. Neither is claimed as the other.
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
TOL_MS, SIZE = 0.04, None
truth = json.load(open('output/poc/truth.json'))
clean = json.load(open('film/poc-clean.json'))                 # ANSWER KEY -- evaluator only
cev = json.load(open('output/poc-clean.events.json'))          # ANSWER KEY -- evaluator only
contacts = truth['contacts']
byid = {t['id']: t for t in truth['defect']}
PASS, FAIL, PART = 'PASS', 'FAIL', 'PARTIAL'
out = []

def load(tag):
    try:
        return json.load(open(f'output/poc/detections-{tag}.json'))['findings']
    except Exception:
        return None

def clash_at(cues, t):
    return [c for c in cues if 'clash' in c.get('id', '') and abs(c['t'] - t) <= TOL_MS]

def camera_size_ok(path, shot, frm, to):
    p = subprocess.run(['node', 'tools/camera_check.mjs', path, '--json', '--step', '3', '--from', str(frm), '--to', str(to)],
                       capture_output=True, text=True)
    try:
        sh = next(x for x in json.loads(p.stdout)['shots'] if x['id'] == shot)
        ch = sh.get('checks', {})
        return sh.get('rejects', 0) == 0 and ch.get('visibility', 1) >= 1 and ch.get('size', 1) >= 1
    except Exception:
        return None

def footslide_worst(path):
    p = subprocess.run(['node', 'tools/footslide.mjs', path, '--json'], capture_output=True, text=True)
    try:
        rows = json.loads(p.stdout)['rows']
        return max((f['worstRun'] for r in rows for f in r['feet'].values()), default=0), \
               any(f.get('flagged') for r in rows for f in r['feet'].values())
    except Exception:
        return None, None

# ============================ poc-defect ============================
f = load('poc-defect')
if f is None:
    out.append(('poc-defect', FAIL, 'run.py produced no detections'))
else:
    fixed = json.load(open('film/poc-defect-fixed.json'))
    fev = json.load(open('output/poc-defect-fixed.events.json'))
    rows = []

    # --- detection: each planted defect located, without being told ---
    det = {
        'D1': any(x['kind'] == 'camera' and x.get('where') == byid['D1']['shot'] for x in f),
        'D2': any(x['kind'] == 'footslide' for x in f),
        'D3': any(x['kind'] == 'sync' and abs(x.get('contact', -9) - byid['D3']['contact']) <= 0.01 for x in f),
        'D4': any(x['kind'] == 'missing' and abs(x.get('contact', -9) - byid['D4']['contact']) <= 0.01 for x in f),
    }
    rows.append(('detection', PASS if all(det.values()) else (PART if any(det.values()) else FAIL),
                 ' '.join(f'{k}={"y" if v else "n"}' for k, v in det.items())))

    # --- metadata-correct: repaired value near the clean answer ---
    clean_dist = clean['shots'][[s['id'] for s in clean['shots']].index(byid['D1']['shot'])]['rig']['dist']
    fix_dist = fixed['shots'][[s['id'] for s in fixed['shots']].index(byid['D1']['shot'])]['rig']['dist']
    meta = {
        'D1': abs(fix_dist - clean_dist) / clean_dist <= 0.25,       # within 25% of the clean distance
        'D2': fixed['motion'].get('lockFeet') == clean['motion'].get('lockFeet', True),
        'D3': bool(clash_at(fev['cues'], byid['D3']['contact'])),    # a clash cue back on the contact
        'D4': bool(clash_at(fev['cues'], byid['D4']['contact'])),    # a clash cue now at the contact
    }
    rows.append(('metadata-correct', PASS if all(meta.values()) else (PART if any(meta.values()) else FAIL),
                 f"D1 dist {fix_dist} vs clean {clean_dist}; D2 lockFeet {fixed['motion'].get('lockFeet')}; "
                 f"D3/D4 cue-on-contact {meta['D3']}/{meta['D4']}"))

    # --- perceptually-correct: re-run the detector on the repaired film/events ---
    d1shot = byid['D1']['shot']
    s = next(x for x in fixed['shots'] if x['id'] == d1shot)
    perc = {}
    perc['D1'] = camera_size_ok('film/poc-defect-fixed.json', d1shot, s['start'], s['end'])
    worst_after, flagged_after = footslide_worst('film/poc-defect-fixed.json')
    perc['D2'] = (flagged_after is False)
    perc['D3'] = all(clash_at(fev['cues'], ct) for ct in contacts)   # every contact now has a cue on it
    perc['D4'] = perc['D3']
    rows.append(('perceptual-correct', PASS if all(perc.values()) else (PART if any(v for v in perc.values()) else FAIL),
                 f"D1 framing-passes={perc['D1']}; D2 foot-slide worst {worst_after} flagged={flagged_after}; "
                 f"D3/D4 every contact cued={perc['D3']}"))

    # --- preservation: nothing outside the four defects moved ---
    d1_idx = [s['id'] for s in clean['shots']].index(byid['D1']['shot'])   # walk() emits index paths
    allowed_film = {f"shots[{d1_idx}].rig.dist", 'motion.lockFeet'}
    changed = []
    def walk(a, b, path=''):
        if isinstance(a, dict):
            for k in set(a) | set(b if isinstance(b, dict) else {}):
                walk(a.get(k), (b or {}).get(k) if isinstance(b, dict) else None, f'{path}.{k}' if path else k)
        elif isinstance(a, list):
            for i in range(max(len(a), len(b) if isinstance(b, list) else 0)):
                walk(a[i] if i < len(a) else None, b[i] if isinstance(b, list) and i < len(b) else None, f'{path}[{i}]')
        elif a != b:
            changed.append(path)
    walk(clean, fixed)
    unexpected_film = [c for c in changed if c not in allowed_film]
    # events: cues not tied to D3/D4 must be unchanged; the D3 snap and the D4 added cue are expected
    clean_cues = {c['id']: round(c['t'], 3) for c in cev['cues']}
    fev_cues = {c['id']: round(c['t'], 3) for c in fev['cues']}
    moved = [cid for cid, t in clean_cues.items()
             if cid in fev_cues and fev_cues[cid] != t and cid != byid['D3']['cue']]
    dropped = [cid for cid in clean_cues if cid not in fev_cues and cid not in byid['D4']['dropped']]
    ev_ok = not moved and not dropped
    rows.append(('preservation', PASS if (not unexpected_film and ev_ok) else FAIL,
                 f"film unexpected {unexpected_film or 'none'}; cues moved {moved or 'none'}; "
                 f"cues lost {dropped or 'none'}"))
    out.append(('poc-defect', rows))

# ============================ poc-control (clean: expect no findings) ============================
fc = load('poc-control')
if fc is None:
    out.append(('poc-control', [('clean-control', FAIL, 'not run')]))
else:
    fp = [x for x in fc if x['kind'] in ('camera', 'footslide', 'sync', 'missing')]
    out.append(('poc-control', [('false-positives', PASS if not fp else FAIL,
                                 f"{len(fp)} false finding(s): {[x['kind'] for x in fp] or 'none'}")]))

# ============================ poc-style (D2 real; silent beat intentional) ============================
fsd = load('poc-style')
if fsd is None:
    out.append(('poc-style', [('stylization', FAIL, 'not run')]))
else:
    caught_d2 = any(x['kind'] == 'footslide' for x in fsd)
    silent = truth['style']['intentional_silent_contact']
    wrongly_repaired = any(x['kind'] == 'missing' and abs(x.get('contact', -9) - (silent or -9)) <= 0.01 for x in fsd)
    respected = any(x['kind'] == 'skipped-intentional' and abs(x.get('contact', -9) - (silent or -9)) <= 0.01 for x in fsd)
    out.append(('poc-style', [
        ('real-defect-D2', PASS if caught_d2 else FAIL, f'foot-slide caught={caught_d2}'),
        ('respects-intent', PASS if (respected and not wrongly_repaired) else FAIL,
         f'silent contact {silent}: repaired={wrongly_repaired}, respected={respected}')]))

# ============================ report ============================
print('\n=== BLIND PLANTED-DEFECT BENCHMARK ===')
allpass = True
for tag, rows in out:
    print(f'\n{tag}:')
    for name, verdict, detail in (rows if isinstance(rows, list) else [rows]):
        allpass = allpass and verdict == PASS
        print(f'  [{verdict:7}] {name}: {detail}')
print('\nOVERALL:', 'PASS' if allpass else 'see PARTIAL/FAIL above')
json.dump([{ 'tag': t, 'rows': [list(r) for r in (rs if isinstance(rs, list) else [rs])]} for t, rs in out],
          open('output/poc/score.json', 'w'), indent=1)

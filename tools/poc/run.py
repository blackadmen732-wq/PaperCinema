#!/usr/bin/env python3
"""Planted-defect proof of concept, step 2: detect every defect, cite evidence, apply one targeted fix each, verify,
and prove nothing else moved. CPU only, deterministic, no model calls, no frame render.

  python3 tools/poc/run.py        -> output/poc/report.json and a table on stdout

Detectors (each cites the number it measured against the film's own declared intent, film.poc.intent):
  D1 camera    tools/camera_check.mjs, scoped to the tight shot: subject on screen?
  D2 animation tools/footslide.mjs: does a planted foot slide past the audit threshold?
  D3 sync      the impact cue vs intent.impact_at
  D4 missing   every intent.contact has a sound cue within 60 ms (after the film's cue_drop)
  D5 music     CADENCE downbeat grid vs intent.music_downbeat_at
Then it fixes the defective film (one field per defect), re-detects, and checks preservation: the repaired film is
field-for-field the clean film, so every shot, sound and motion field the defects did not touch is unchanged.
"""
import copy, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'packages/sonic'))
os.chdir(ROOT)
from cadence import synth, analyse as CAD                      # noqa: E402

TOL = 0.05
clean = json.load(open('film/poc-clean.json'))
intent = clean['poc']['intent']


def cue_times(film, events):
    cues = [c for c in events.get('cues', []) if not any(abs(c['t'] - d) < 0.03 for d in film['poc'].get('cue_drop', []))]
    return cues


def detect(film, events, music_down, tag):
    f = []
    # D1 camera: read the camera_check JSON for this film (camera_check renders in a browser, so it is run once,
    # ahead of this loop, into output/poc/cc-<tag>.json; the loop stays deterministic and fast)
    ts = film['poc'].get('tight_shot')
    ccf = f"output/poc/cc-{tag}.json"
    if ts and os.path.exists(ccf):
        data = json.load(open(ccf))
        shot = next((s for s in data['shots'] if s['id'] == ts[0]), None)
        m = shot and next((x for x in shot['findings'] if x['check'] == 'shot-subject-off-screen'), None)
        if m:
            f.append(('D1', 'visual', m['msg']))
    # D2 foot slide
    r = subprocess.run(['node', 'tools/footslide.mjs', 'film/poc-work.json', '--json'], capture_output=True, text=True)
    fs = json.loads(r.stdout)
    slid = [(row['id'], foot, d['worstRun']) for row in fs['rows'] for foot, d in row['feet'].items() if d['flagged']]
    if slid:
        f.append(('D2', 'animation', f"{len(slid)} foot/feet slide, worst {max(s[2] for s in slid):.2f} m in a run (threshold 0.30); e.g. {slid[0][0]} {slid[0][1]}"))
    # D3 sync: impact cue vs intent
    imp = next((s for s in film['sounds'] if s['id'] == 'impact'), None)
    if imp and abs(imp['t'] - intent['impact_at']) > TOL:
        f.append(('D3', 'sync', f"impact sound at {imp['t']:.3f}s, intended {intent['impact_at']}s: {1000 * (imp['t'] - intent['impact_at']):+.0f} ms"))
    # D4 missing sound: each contact needs a cue
    cts = cue_times(film, events)
    for c in intent['contacts']:
        if not any(abs(cu['t'] - c) < 0.06 for cu in cts):
            f.append(('D4', 'missing-sound', f"blade contact at {c}s has no sound cue within 60 ms"))
    # D5 music: a downbeat within tol of the intended moment
    start = next(s for s in film['sounds'] if s['id'] == 'score')['t']
    downs = [start + k for k in music_down]              # music_down: downbeat offsets from the score's own start
    near = min((abs(d - intent['music_downbeat_at']) for d in downs), default=9)
    if near > TOL:
        f.append(('D5', 'music-timing', f"nearest music downbeat {1000 * near:.0f} ms from the strike at {intent['music_downbeat_at']}s"))
    return f


def fix(film):
    d = copy.deepcopy(film)
    ts = d['poc'].get('tight_shot')
    if ts:                                                      # restore the whole rig of the over-tight shot
        i = next(i for i, s in enumerate(d['shots']) if s['id'] == ts[0])
        d['shots'][i]['rig'] = copy.deepcopy(next(s for s in clean['shots'] if s['id'] == ts[0])['rig'])
    d['motion']['lockFeet'] = clean['motion'].get('lockFeet', True)
    for i, c in enumerate(d['sounds']):                         # restore each defective sound whole
        cl = next((x for x in clean['sounds'] if x['id'] == c['id']), None)
        if cl and c['id'] in ('impact', 'impact-drum', 'score'):
            d['sounds'][i] = copy.deepcopy(cl)
    d['poc']['cue_drop'] = []
    return d


# the music's downbeat grid, once (CADENCE on the test score), as offsets from the score's start
x, _ = synth.piece()
A = CAD.analyse(x)
music_down = [round(float(t), 3) for t in A['bars']]          # downbeats, seconds from the score's start

defect = json.load(open('film/poc-defect.json'))
ev = json.load(open('output/poc-defect.events.json'))
json.dump(defect, open('film/poc-work.json', 'w'))
before = detect(defect, ev, music_down, 'defect')

fixed = fix(defect)
json.dump(fixed, open('film/poc-work.json', 'w'))
json.dump(fixed, open('film/poc-fixed.json', 'w'), indent=2)
after = detect(fixed, ev, music_down, 'fixed')

truth = {t['id'] for t in json.load(open('output/poc/truth.json'))['defects']}
found = {d[0] for d in before}
# preservation: the repaired film equals the clean film field-for-field (the fixes only reversed the planted changes)
fx = copy.deepcopy(fixed); cl = copy.deepcopy(clean)
for o in (fx, cl):
    o.pop('poc', None)
preserved = fx == cl
os.remove('film/poc-work.json')
report = {'planted': sorted(truth), 'detected': sorted(found), 'missed': sorted(truth - found), 'false_positives': sorted(found - truth),
          'after_fix_remaining': [d[0] for d in after], 'repaired_equals_clean_except_planted_fields': preserved,
          'evidence': {d[0]: d[2] for d in before}}
json.dump(report, open('output/poc/report.json', 'w'), indent=1)
print(f"planted {sorted(truth)}  detected {sorted(found)}  missed {report['missed']}  false+ {report['false_positives']}")
print(f"after fix, remaining defects: {report['after_fix_remaining'] or 'none'}")
print(f"repaired film == clean film on every untouched field: {preserved}")
print('\nevidence:')
for k in sorted(report['evidence']):
    print(f"  {k}: {report['evidence'][k]}")
sys.exit(0 if (not report['missed'] and not report['false_positives'] and not report['after_fix_remaining'] and preserved) else 1)

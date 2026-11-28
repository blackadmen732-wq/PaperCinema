#!/usr/bin/env python3
"""Blind planted-defect benchmark, step 2 of 3: detect and repair, WITHOUT the clean film.

  python3 tools/poc/run.py [poc-defect|poc-control|poc-style]   (default poc-defect)

This reads ONLY the film under test and its events. It never opens poc-clean.* -- the answer key lives
with the evaluator (tools/poc/score.py). It is not told where the defects are: it scans every shot and
every contact, decides what is wrong from measured evidence, and computes each repair from the
production constraint, not from a known-good value:

  camera   render the shot's geometry (camera_check). A shot whose subjects overflow the frame
           (visibility < 1 or a hard reject) is too tight. Widen its rig distance step by step and
           re-render until the shot passes. The distance is SEARCHED, never copied.
  footslide pose the rig (footslide). If a planted foot skates past the audit threshold while foot-lock
           is off, foot-lock is the known remedy: turn it on and re-measure to confirm the skate drops.
  sync     every blade contact is a measured picture event. A clash cue sitting more than 40 ms off a
           contact is snapped to the measured contact time.
  missing  a contact with no clash cue within 200 ms has lost its cue; synthesise one at the measured
           contact time -- UNLESS the film declares that contact an intentional silent beat.

Writes film/<tag>-fixed.json, output/<tag>-fixed.events.json, and output/poc/detections-<tag>.json
(the findings it discovered and the repairs it computed). No answer key is read or written.
"""
import copy, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
TAG = sys.argv[1] if len(sys.argv) > 1 else 'poc-defect'
SYNC_TOL, NEAR_WIN = 0.04, 0.20                       # a cue >40ms off is misaligned; search cues within 200ms

film = json.load(open(f'film/{TAG}.json'))
ev = json.load(open(f'output/{TAG}.events.json'))
contacts = sorted(round(c['t'], 3) for c in ev.get('contacts', []))
intentional_silent = set(round(t, 3) for t in film.get('poc', {}).get('intentional', {}).get('silent_contacts', []))
findings = []
WORK = f'film/{TAG}-fixed.json'                        # all film repairs are written here, never onto the input

def camera_json(path, frm=None, to=None):
    cmd = ['node', 'tools/camera_check.mjs', path, '--json', '--step', '3']
    if frm is not None: cmd += ['--from', str(frm), '--to', str(to)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return None

# ---- camera: find tight shots by rendered geometry, widen distance until each passes ----
json.dump(film, open(WORK, 'w'), indent=2)            # start the working copy from the input, unchanged
base = camera_json(WORK)
if base:
    def shot_ok(sh):                                              # the framing constraint the shot declares
        ch = sh.get('checks', {})
        return sh.get('rejects', 0) == 0 and ch.get('visibility', 1) >= 1 and ch.get('size', 1) >= 1
    for s in base.get('shots', []):
        fs = next((x for x in film['shots'] if x['id'] == s['id']), None)
        if not shot_ok(s) and fs and 'dist' in fs.get('rig', {}):
            start_dist = fs['rig']['dist']
            dist, ok = start_dist, False
            for _ in range(10):                                   # search a passing distance, do not copy one
                dist = round(dist * 1.2 + 0.05, 3)
                fs['rig']['dist'] = dist
                json.dump(film, open(WORK, 'w'), indent=2)        # camera_check reads the working file
                r = camera_json(WORK, fs['start'], fs['end'])
                sh = next((x for x in (r or {}).get('shots', []) if x['id'] == s['id']), None)
                if sh and shot_ok(sh):
                    ok = True
                    break
            ch = s.get('checks', {})
            findings.append({'kind': 'camera', 'where': s['id'], 'field': f"shots.{s['id']}.rig.dist",
                             'evidence': f"size {ch.get('size')} (measured {s.get('measuredSize')}), visibility {ch.get('visibility')}, rejects {s.get('rejects')} at dist {start_dist}",
                             'repair': {'from': start_dist, 'to': dist, 'verified': ok, 'method': 'widened distance until the shot framed its declared size'}})

# ---- footslide: measure skate; if planted feet flag while lock is off, the remedy is foot-lock ----
p = subprocess.run(['node', 'tools/footslide.mjs', WORK, '--json'], capture_output=True, text=True)
try:
    fsj = json.loads(p.stdout)
except Exception:
    fsj = None
if fsj:
    worst = max((f['worstRun'] for row in fsj['rows'] for f in row['feet'].values()), default=0)
    flagged = any(f.get('flagged') for row in fsj['rows'] for f in row['feet'].values())
    if flagged and film.get('motion', {}).get('lockFeet', True) is False:
        film['motion']['lockFeet'] = True                         # known remedy for planted-foot skate
        json.dump(film, open(WORK, 'w'), indent=2)
        p2 = subprocess.run(['node', 'tools/footslide.mjs', WORK, '--json'], capture_output=True, text=True)
        after = max((f['worstRun'] for row in json.loads(p2.stdout)['rows'] for f in row['feet'].values()), default=0)
        findings.append({'kind': 'footslide', 'where': 'motion.lockFeet', 'field': 'motion.lockFeet',
                         'evidence': f"worst planted-foot slide run {worst:.3f} m with foot-lock off",
                         'repair': {'from': False, 'to': True, 'verified': after < worst, 'worst_after': round(after, 3),
                                    'method': 'enabled foot-lock, re-measured'}})
json.dump(film, open(WORK, 'w'), indent=2)            # final working film (camera + foot-lock repairs)

# ---- sync / missing: judge every contact against its clash cues ----
fev = copy.deepcopy(ev)
clash = lambda c: 'clash' in c.get('id', '')
for ct in contacts:
    near = [c for c in fev['cues'] if clash(c) and abs(c['t'] - ct) <= NEAR_WIN]
    if near:
        for c in near:
            if abs(c['t'] - ct) > SYNC_TOL:
                findings.append({'kind': 'sync', 'where': c['id'], 'contact': ct,
                                 'evidence': f"clash cue {abs(c['t'] - ct) * 1000:.0f} ms off a measured contact",
                                 'repair': {'from': round(c['t'], 3), 'to': ct, 'method': 'snapped cue to measured contact'}})
                c['t'] = ct
    elif ct in intentional_silent:
        findings.append({'kind': 'skipped-intentional', 'contact': ct,
                         'evidence': 'contact declared an intentional silent beat; no cue added'})
    else:
        tmpl = next((c for c in fev['cues'] if clash(c)), None)
        cue = {**(tmpl or {'sfx': 'clash-a', 'len': 0.3, 'gain': 0.3}), 'id': f'repair-clash-{ct}', 't': ct,
               'why': 'synthesised at a measured contact with no cue'}
        fev['cues'].append(cue)
        findings.append({'kind': 'missing', 'where': f'contact@{ct}', 'contact': ct,
                         'evidence': 'measured contact with no clash cue within 200 ms',
                         'repair': {'added_cue_at': ct, 'method': 'synthesised cue at measured contact'}})
fev['cues'].sort(key=lambda c: c['t'])
json.dump(fev, open(f'output/{TAG}-fixed.events.json', 'w'))
json.dump({'tag': TAG, 'findings': findings}, open(f'output/poc/detections-{TAG}.json', 'w'), indent=1)

print(f'{TAG}: {len(findings)} findings ->',
      ', '.join(f"{f['kind']}:{f.get('where', f.get('contact'))}" for f in findings) or '(none)')

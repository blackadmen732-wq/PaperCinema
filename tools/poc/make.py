#!/usr/bin/env python3
"""Blind planted-defect benchmark, step 1 of 3: build the films and plant the defects.

The clean film IS the answer key. Only the evaluator (tools/poc/score.py) ever opens it; the detector/
repairer (tools/poc/run.py) never does. The defect films carry only the legitimate production intent a
real editable project has -- the shot list, the motion flags, the measured picture events (blade
contacts, from the renderer). They do NOT carry the correct camera distance, the right foot-lock state
or the correct cue times. Those are the answers, and live only in the clean film the evaluator holds.

  python3 tools/poc/make.py
Writes:
  film/poc-clean.json             the correct film (ANSWER KEY; only score.py reads it)
  output/poc-clean.events.json    its measured picture events (written by the renderer pipeline)
  film/poc-defect.json            the same film with D1 (camera too close) and D2 (foot-lock off) planted
  output/poc-defect.events.json   its events, with D3 (a clash cue shifted) and D4 (a clash cue dropped)
  film/poc-control.json           a clean control -- identical to clean, expect ZERO detections
  output/poc-control.events.json  the control's events (clean)
  film/poc-style.json             a stylization film: one REAL defect (D2) plus one DECLARED intentional
                                  choice (a deliberately silent contact), to check the repairer respects
                                  intent and does not "repair" it
  output/poc-style.events.json    the style film's events (the silent contact's cue removed on purpose)
  output/poc/truth.json           the answer key index, for score.py only

Defects, and why each is independently detectable and repairable without the clean film:
  D1 camera-too-close  S8's rig distance is cut so the fighters overflow the frame. A geometry render
                       (camera_check) measures the overflow; the repair widens the distance until the
                       render passes -- computed from the framing constraint, not copied.
  D2 foot-slide        motion.lockFeet is turned off, so planted feet skate. footslide measures the
                       skate; the repair is the known remedy (turn foot-lock back on) and is re-measured.
  D3 cue-misaligned    a clash cue is moved 120 ms off its contact. The contact time is a measured
                       picture event; the repair snaps the cue to it.
  D4 cue-missing       a clash cue is removed. A measured contact with no cue near it is the evidence;
                       the repair synthesises a cue at the measured contact time.
"""
import copy, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
os.makedirs('output/poc', exist_ok=True)
run = lambda *c: subprocess.run(list(c), check=True, capture_output=True, text=True)

# --- the clean film (answer key) -------------------------------------------------------------------
body = json.load(open('film/kuroko-duel.json'))
body['duration'] = 24
body['shots'] = [s for s in body['shots'] if s['start'] < 24]
body['shots'][-1]['end'] = min(body['shots'][-1]['end'], 24)
json.dump(body, open('output/poc/body.json', 'w'))
run('node', 'engine/new-film.mjs', 'poc-clean', '--body', 'output/poc/body.json', '--force')
run('node', 'engine/render.mjs', '--film', 'film/poc-clean.json', '--still', '0')   # -> output/poc-clean.events.json
clean = json.load(open('film/poc-clean.json'))
ev = json.load(open('output/poc-clean.events.json'))
contacts = sorted(round(c['t'], 3) for c in ev.get('contacts', []))
CLASH = ('clash', 'contact', 'impact', 'hit')
clash_cues = [c for c in ev.get('cues', []) if any(k in c.get('id', '') or k == c.get('sfx') for k in CLASH)] \
             or [c for c in ev.get('cues', []) if c.get('event', {}).get('kind') in ('clash', 'contact')]

# clean control: a byte-for-byte clean film under another name
control = copy.deepcopy(clean); control['title'] = clean.get('title', 'poc') + ' (control)'
json.dump(control, open('film/poc-control.json', 'w'), indent=2)
json.dump(ev, open('output/poc-control.events.json', 'w'))

# --- defect film: D1 (camera) + D2 (foot-lock) -----------------------------------------------------
truth = []
d = copy.deepcopy(clean)
s8 = next(s for s in d['shots'] if s['id'] == 'S8')
truth.append({'id': 'D1', 'kind': 'camera', 'shot': 'S8', 'field': 'shots.S8.rig.dist',
              'clean': s8['rig'].get('dist'), 'planted': 0.3})
s8['rig']['dist'] = 0.3
truth.append({'id': 'D2', 'kind': 'footslide', 'field': 'motion.lockFeet',
              'clean': clean['motion'].get('lockFeet', True), 'planted': False})
d['motion']['lockFeet'] = False
json.dump(d, open('film/poc-defect.json', 'w'), indent=2)

# --- defect events: D3 (cue shifted) + D4 (cue dropped) --------------------------------------------
de = copy.deepcopy(ev)
if clash_cues and len(contacts) >= 1:
    c0 = min(de['cues'], key=lambda c: abs(c['t'] - contacts[0]))
    truth.append({'id': 'D3', 'kind': 'sync', 'contact': contacts[0], 'cue': c0['id'],
                  'clean_t': round(c0['t'], 3), 'planted_offset_ms': 120})
    for c in de['cues']:
        if c['id'] == c0['id']:
            c['t'] = round(c['t'] + 0.12, 3)
if len(contacts) >= 2:
    near1 = [c for c in de['cues'] if abs(c['t'] - contacts[1]) < 0.05]
    truth.append({'id': 'D4', 'kind': 'missing', 'contact': contacts[1],
                  'dropped': [c['id'] for c in near1]})
    de['cues'] = [c for c in de['cues'] if abs(c['t'] - contacts[1]) >= 0.05]
json.dump(de, open('output/poc-defect.events.json', 'w'))

# --- stylization film: one real defect (D2) + one declared intentional silent contact --------------
st = copy.deepcopy(clean)
st['motion']['lockFeet'] = False                                    # real defect: feet slide
silent = contacts[0] if contacts else None
st['poc'] = {'intentional': {'silent_contacts': ([silent] if silent is not None else [])}}
json.dump(st, open('film/poc-style.json', 'w'), indent=2)
ste = copy.deepcopy(ev)
if silent is not None:                                              # the cue is absent ON PURPOSE
    ste['cues'] = [c for c in ste['cues'] if abs(c['t'] - silent) >= 0.05]
json.dump(ste, open('output/poc-style.events.json', 'w'))

json.dump({'defect': truth, 'contacts': contacts,
           'style': {'real_defect': 'D2', 'intentional_silent_contact': silent}},
          open('output/poc/truth.json', 'w'), indent=1)

for f in ('poc-clean', 'poc-control', 'poc-style', 'poc-defect'):
    r = subprocess.run(['node', 'engine/validate.mjs', f'film/{f}.json'], capture_output=True, text=True)
    print(f'{f:12} {"ok" if r.returncode == 0 else (r.stdout + r.stderr).strip().splitlines()[-1]}')
print('planted', sorted(t['id'] for t in truth), '| contacts', contacts,
      '| clash cues', [c['id'] for c in clash_cues])

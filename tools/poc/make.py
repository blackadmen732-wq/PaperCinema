#!/usr/bin/env python3
"""Planted-defect proof of concept, step 1: the clean 30-second film and its defective copy, with the answers.

  python3 tools/poc/make.py            -> film/poc-clean.json, film/poc-defect.json, output/poc/truth.json,
                                          output/poc/music.wav (CADENCE's synthetic 120 BPM piece, the test score)
The clean film is the starter scaffold (kuroko-duel body, signature opening, end card) with the last shot held to make
30 s, and a music bed whose downbeat lands on the final strike. The defective copy changes five things, each one
small and each one known: they are the truth the detectors are scored against.
"""
import copy, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'packages/sonic'))
from cadence import synth                                     # noqa: E402

os.chdir(ROOT)
os.makedirs('output/poc', exist_ok=True)
body = json.load(open('film/kuroko-duel.json'))
body['duration'] = 24
body['shots'][-1]['end'] = 24                                  # hold the aftermath: 6 s opening + 24 s body = 30 s
json.dump(body, open('output/poc/body.json', 'w'), indent=1)
subprocess.run(['node', 'engine/new-film.mjs', 'poc-clean', '--body', 'output/poc/body.json', '--force'], check=True, capture_output=True)
clean = json.load(open('film/poc-clean.json'))
x, truth_music = synth.piece()                                 # 120 BPM: a downbeat every 2.0 s
synth.write_wav(x, 'output/poc/music.wav')
O = 6.0                                                        # the opening's length: body time + O = film time
HIT = 11.45 + O                                                # the final strike ("impact" cue, the film's beat event)
start = round(HIT % 2.0, 3)                                    # music starts so a downbeat falls on the strike
clean['sounds'].append({'id': 'score', 'query': 'test score', 'min': 1000, 'max': 60000, 'file': 'output/poc/music.wav', 't': start, 'len': 30 - start, 'gain': 0.18, 'music': True})
# the director's intent, part of the film (a real editable production knows its own hit times): what the detectors check against
ev = json.load(open('output/poc-clean.events.json'))
contacts = [round(c['t'], 3) for c in ev.get('contacts', [])]
clean['poc'] = {'intent': {'impact_at': HIT, 'music_downbeat_at': HIT, 'contacts': contacts, 'beats_per_bar': 4, 'bpm': truth_music['bpm'], 'score_start': start},
                'cue_drop': [], 'tight_shot': None}
json.dump(clean, open('film/poc-clean.json', 'w'), indent=2)

d = copy.deepcopy(clean)
truth = []
# 1 visual: the camera pushed in far too close in shot S5 (subject cropped / off screen)
s5 = next(s for s in d['shots'] if s['id'] == 'S5')
truth.append({'id': 'D1', 'kind': 'visual', 'what': 'camera too close in S5: subjects cropped', 't0': s5['start'], 't1': s5['end'],
              'path': 'shots.S5.rig.dist', 'was': s5['rig'].get('dist'), 'now': 0.3})
s5['rig']['dist'] = 0.3
d['poc']['tight_shot'] = ['S5', s5['start'], s5['end']]
# 2 animation (KINESIS): foot locking off, so feet slide
truth.append({'id': 'D2', 'kind': 'animation', 'what': 'foot lock off: feet slide', 't0': O, 't1': 30, 'path': 'motion.lockFeet',
              'was': d['motion'].get('lockFeet'), 'now': False})
d['motion']['lockFeet'] = False
# 3 sync: the final strike's sound 120 ms late
for c in d['sounds']:
    if c['id'] in ('impact', 'impact-drum'):
        truth.append({'id': 'D3', 'part': c['id'], 'kind': 'sync', 'what': f'{c["id"]} 120 ms late', 't0': c['t'], 't1': c['t'] + 0.12,
                      'path': f'sounds.{c["id"]}.t', 'was': c['t'], 'now': round(c['t'] + 0.12, 3)})
        c['t'] = round(c['t'] + 0.12, 3)
# 4 missing sound: the second blade contact's clash is dropped from the mix (planted in the events file after render)
truth.append({'id': 'D4', 'kind': 'missing-sound', 'what': 'no sound on the second blade contact', 't0': 12.59, 't1': 12.6,
              'path': 'events.cues[auto-clash at 12.59]', 'was': 'present', 'now': 'removed'})
d['poc'] = {**d['poc'], 'cue_drop': [12.592]}
# 5 music: the score starts 300 ms late, so the downbeat misses the strike
m = next(c for c in d['sounds'] if c['id'] == 'score')
truth.append({'id': 'D5', 'kind': 'music-timing', 'what': 'score 300 ms late: downbeat misses the final strike', 't0': HIT, 't1': HIT,
              'path': 'sounds.score.t', 'was': m['t'], 'now': round(m['t'] + 0.3, 3)})
m['t'] = round(m['t'] + 0.3, 3)
json.dump(d, open('film/poc-defect.json', 'w'), indent=2)
json.dump({'film_s': clean['duration'], 'opening_s': O, 'hit_t': HIT, 'defects': truth}, open('output/poc/truth.json', 'w'), indent=1)
print(f'clean {clean["duration"]} s, planted:', ', '.join(sorted({t["id"] for t in truth})))

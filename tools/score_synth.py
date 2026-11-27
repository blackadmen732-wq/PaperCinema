#!/usr/bin/env python3
"""SCORE SYNTH: a film's music made here from a cue list (no download, no licence question: ours, CC0).

    python3 tools/score_synth.py --film film/<name>.json [--events output/<name>.bake-events.json] [--out FILE.wav]
    python3 tools/score_synth.py --demo                 (every instrument once: output/score-demo.wav)

The film file's `score` block:
  { "seed": 3, "key": "D", "scale": "in", "bpm": 72, "reverb": 0.28, "gain": 0.9,
    "cues": [ { "t": 0.2, "kind": "odaiko", "gain": 1.0 },
              { "t": 3.0, "until": 12, "kind": "drone", "note": "D2" },
              { "at": "contact", "dt": -0.1, "until_dt": 1.2, "kind": "silence" }, ... ] }

Times are seconds on the FILM clock (the frames as encoded). `at` names a bake event instead of a time: "contact"
(the measured blade contact) or "apex" (the fastest point of the swing), read from the bake events file and moved
later by the hit-stop frames inserted before it (post_fx `stops`), so the music lands on the frame the eye sees.

Instruments (synthesis, all numpy):
  odaiko   the big drum: a skin slap + a body whose pitch falls from 1.6x to its note, long hall tail
  taiko    a tighter drum (shime): higher, short
  pulse    a heartbeat of taiko pairs from `t` to `until`, its tempo going bpm0 -> bpm1
  roll     a shime roll (16ths) with a crescendo, `t` to `until`
  koto     plucked strings (Karplus-Strong): `notes` [[dt, note], ...] or one `note`
  shaku    a breathy bamboo flute: slides up into the note (kari), vibrato growing late in the note, breath noise
  drone    two detuned voices + a sub, swelling in and out, `t` to `until`
  rin      a small temple bowl: inharmonic partials, long ring
  silence  everything under it is cut (fast fades) from `t` to `until`: the hush before and after the hit

Scales (from the key): in (miyako-bushi: 1 b2 4 5 b6), yo (1 2 4 5 6), minyo (1 b3 4 5 b7). A note is a name
("D4", "Bb3") or a scale step: {"step": 3, "oct": 4}.
"""
import argparse
import json
import math
import os
import wave

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100
NAMES = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
         'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
SCALES = {'in': [0, 1, 5, 7, 8], 'yo': [0, 2, 5, 7, 9], 'minyo': [0, 3, 5, 7, 10]}


def midi(note, key='D', scale='in'):
    if isinstance(note, dict):
        steps = SCALES[scale]
        s = int(note['step'])
        o = int(note.get('oct', 4)) + s // len(steps)
        return 12 * (o + 1) + NAMES[key] + steps[s % len(steps)]
    n = note[:-1] if note[-1].isdigit() and not note[-2].isdigit() else note[:-2]
    o = int(note[len(n):])
    return 12 * (o + 1) + NAMES[n]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def fft_filter(x, lo=None, hi=None, order=2):
    """Band-limit x by a Butterworth-shaped magnitude mask in the frequency domain (no scipy here): order 2 is
    24 dB per octave outside the band."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1.0 / np.sqrt(1.0 + (lo / np.maximum(f, 1.0)) ** (2 * order))
    if hi:
        m *= 1.0 / np.sqrt(1.0 + (f / hi) ** (2 * order))
    return np.fft.irfft(X * m, n)


def env_ad(n, a, d):
    t = np.arange(n) / SR
    return (1 - np.exp(-t / max(a, 1e-4))) * np.exp(-t / d)


def drum(rng, f0, decay, slap, pitch_fall=0.6, dur=None):
    dur = dur or decay * 6
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + pitch_fall * np.exp(-t / 0.03))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * env_ad(n, 0.002, decay)
    body += 0.35 * np.sin(2.01 * ph) * env_ad(n, 0.002, decay * 0.35)
    nz = fft_filter(rng.normal(0, 1, n), hi=900 if f0 < 100 else 2600) * np.exp(-t / slap)
    return body + 0.5 * nz / (np.abs(nz).max() + 1e-9)


def karplus(rng, f, dur, bright=0.5, decay=0.996):
    """A plucked string: a noise burst circulating in a delay line one period long, averaged (the string's loss)."""
    n = int(dur * SR)
    N = max(2, int(round(SR / f)))
    out = np.zeros(n + N + 1)
    burst = rng.uniform(-1, 1, N)
    burst = bright * burst + (1 - bright) * np.convolve(burst, np.ones(5) / 5, 'same')     # the pluck's hardness
    out[:N] = burst
    i = N
    while i < n:                                   # each block depends only on the block one period earlier
        j = min(n, i + N)
        prev = out[i - N:j - N + 1]
        out[i:j] = decay * 0.5 * (prev[:-1] + prev[1:])[:j - i]
        i = j
    y = out[:n]
    y[: int(0.004 * SR)] += rng.normal(0, 0.15, int(0.004 * SR))          # the plectrum's click (tsume)
    return y * np.exp(-np.arange(n) / SR / (dur * 0.6))


def shaku(rng, f, dur, gain=1.0, slide=True, vib=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    semis = np.zeros(n)
    if slide:                                       # kari: the note is reached from below
        semis -= 1.0 * np.exp(-t / 0.09)
    late = np.clip((t / dur - 0.35) / 0.4, 0, 1)    # vibrato grows in the second half (the player's breath)
    semis += vib * late * np.sin(2 * np.pi * 5.2 * t)
    fr = f * 2 ** (semis / 12)
    ph = 2 * np.pi * np.cumsum(fr) / SR
    tone = np.sin(ph) + 0.28 * np.sin(2 * ph + 0.4) + 0.08 * np.sin(3 * ph)
    breath = fft_filter(rng.normal(0, 1, n), lo=f * 1.5, hi=min(9000, f * 6))
    breath /= (np.abs(breath).max() + 1e-9)
    a = np.clip(t / 0.22, 0, 1) ** 1.5 * np.clip((dur - t) / 0.45, 0, 1)
    muraiki = np.exp(-t / 0.06) * 0.6               # the breath burst that starts the note
    return gain * a * (tone * 0.8 + breath * (0.12 + 0.10 * late)) + muraiki * breath * 0.35


def drone(rng, f, dur, gain=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    v = np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.004 * t + 1.1) + 0.6 * np.sin(np.pi * f * t + 0.3)
    v += 0.25 * fft_filter(np.sign(np.sin(2 * np.pi * f * 0.5 * t)), hi=f * 3)          # a soft sub reed
    sw = np.clip(t / min(3.0, dur / 3), 0, 1) * np.clip((dur - t) / min(3.0, dur / 3), 0, 1)
    breathe = 0.8 + 0.2 * np.sin(2 * np.pi * t / 6.5)
    return gain * 0.35 * v * sw * breathe


def rin(f, dur, gain=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k, (r, d, a) in enumerate(((1.0, 4.0, 1.0), (2.76, 2.2, 0.55), (5.40, 1.2, 0.3), (8.93, 0.6, 0.18))):
        out += a * np.sin(2 * np.pi * f * r * t + k) * np.exp(-t / d) * (1 + 0.15 * np.sin(2 * np.pi * 3.1 * t))
    return gain * out * (1 - np.exp(-t / 0.002))


def reverb_ir(rng, secs=2.6, rt60=2.2):
    n = int(secs * SR)
    t = np.arange(n) / SR
    decay = np.exp(-6.91 * t / rt60)
    L = rng.normal(0, 1, n) * decay
    R = rng.normal(0, 1, n) * decay
    L, R = fft_filter(L, hi=5500), fft_filter(R, hi=5500)              # a dark, wooden hall
    L[:int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))          # pre-delay
    R[:int(0.017 * SR)] *= np.linspace(0, 1, int(0.017 * SR))
    norm = math.sqrt((L ** 2).sum())
    return L / norm, R / norm


def convolve(x, ir):
    n = len(x) + len(ir) - 1
    N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:len(x)]


def place(buf, sig, t, pan=0.0, gain=1.0):
    i = int(round(t * SR))
    if i >= buf.shape[0] or i + len(sig) <= 0:
        return
    s0 = max(0, -i)
    j = min(buf.shape[0], i + len(sig))
    seg = sig[s0:s0 + (j - max(i, 0))] * gain
    buf[max(i, 0):j, 0] += seg * math.cos((pan + 1) * math.pi / 4)
    buf[max(i, 0):j, 1] += seg * math.sin((pan + 1) * math.pi / 4)


def resolve_t(cue, events, fps):
    if 'at' not in cue:
        return float(cue.get('t', 0.0))
    if not events:
        raise SystemExit('score: cue %r needs the bake events file (--events)' % cue)
    ev = events.get(cue['at'])
    if not ev or 't' not in ev:
        raise SystemExit('score: the events file has no %r' % cue['at'])
    tb = float(ev['t']) + float(cue.get('dt', 0.0))
    # a hit-stop (tools/post_fx.py: stops [{tb, frames}]) holds the picture on its frame and moves everything after it
    shift = sum(int(s.get('frames', s.get('n', 0))) for s in (events.get('stops') or []) if float(s.get('tb', s.get('t', 0))) < tb)
    return tb + shift / fps


def render(score, dur, events=None, fps=30):
    rng = np.random.default_rng(int(score.get('seed', 3)))
    key, scale = score.get('key', 'D'), score.get('scale', 'in')
    dry = np.zeros((int((dur + 3) * SR), 2))
    wet_send = np.zeros_like(dry)
    mute = np.ones(dry.shape[0])
    for c in score.get('cues', []):
        k = c['kind']
        t = resolve_t(c, events, fps)
        g = float(c.get('gain', 1.0))
        pan = float(c.get('pan', 0.0))
        until = float(c['until']) if 'until' in c else (t + float(c['until_dt']) if 'until_dt' in c else None)
        send = float(c.get('verb', {'odaiko': 0.55, 'taiko': 0.35, 'pulse': 0.3, 'roll': 0.3, 'koto': 0.3,
                                     'shaku': 0.45, 'drone': 0.25, 'rin': 0.5}.get(k, 0.3)))
        sigs = []
        if k == 'odaiko':
            sigs.append((t, drum(rng, hz(midi(c.get('note', 'D1'), key, scale)), 0.55, 0.03), pan))
        elif k == 'taiko':
            sigs.append((t, drum(rng, hz(midi(c.get('note', 'D3'), key, scale)), 0.12, 0.012, 0.3), pan))
        elif k == 'pulse':
            b0, b1 = float(c.get('bpm0', 60)), float(c.get('bpm1', c.get('bpm0', 60)))
            tt = t
            while tt < until:
                u = (tt - t) / max(1e-6, until - t)
                bpm = b0 + (b1 - b0) * u
                for dt_, gg in ((0.0, 1.0), (0.16 * 60 / bpm, 0.6)):       # lub-dub
                    sigs.append((tt + dt_, gg * (0.6 + 0.4 * u) * drum(rng, hz(midi(c.get('note', 'D2'), key, scale)),
                                                                        0.22, 0.02), pan))
                tt += 60.0 / bpm
        elif k == 'roll':
            tt, step = t, 60.0 / float(c.get('bpm', 140)) / 4
            while tt < until:
                u = (tt - t) / max(1e-6, until - t)
                sigs.append((tt + rng.uniform(-0.008, 0.008), (0.25 + 0.75 * u ** 1.6) * drum(rng, hz(midi(c.get('note', 'A3'), key, scale)) *
                                                                  (1 + rng.uniform(-0.03, 0.03)), 0.08, 0.008, 0.25),
                             pan + rng.uniform(-0.15, 0.15)))
                tt += step
        elif k == 'koto':
            notes = c.get('notes') or [[0.0, c.get('note', 'D4')]]
            for dt_, nn in notes:
                f = hz(midi(nn, key, scale))
                sigs.append((t + float(dt_), karplus(rng, f, float(c.get('len', 2.4)), float(c.get('bright', 0.55))),
                             pan + 0.1 * math.sin(f)))
        elif k == 'shaku':
            phrase = c.get('notes') or [[0.0, c.get('note', 'A4'), float(c.get('len', 3.0))]]
            for dt_, nn, ln in phrase:
                sigs.append((t + float(dt_), shaku(rng, hz(midi(nn, key, scale)), float(ln), vib=float(c.get('vib', 0.35))), pan))
        elif k == 'drone':
            sigs.append((t, drone(rng, hz(midi(c.get('note', 'D2'), key, scale)), (until or t + 8) - t), pan))
        elif k == 'rin':
            sigs.append((t, rin(hz(midi(c.get('note', 'A5'), key, scale)), float(c.get('len', 5.0))), pan))
        elif k == 'silence':
            a_, b_ = int(t * SR), int((until or t + 0.5) * SR)
            f_ = int(float(c.get('fade', 0.04)) * SR)
            mute[max(0, a_ - f_):a_] = np.minimum(mute[max(0, a_ - f_):a_], np.linspace(1, 0, a_ - max(0, a_ - f_)))
            mute[a_:b_] = 0.0
            mute[b_:b_ + f_] = np.minimum(mute[b_:b_ + f_], np.linspace(0, 1, len(mute[b_:b_ + f_])))
            continue
        else:
            raise SystemExit('score: unknown instrument %r' % k)
        for tt, s, p in sigs:
            place(dry, s, tt, p, g)
            place(wet_send, s, tt, p, g * send)
    L, R = reverb_ir(rng, rt60=float(score.get('rt60', 2.2)))
    wet = np.stack([convolve(wet_send[:, 0], L), convolve(wet_send[:, 1], R)], 1)
    mix = dry + wet * float(score.get('reverb', 0.28)) * 6.0
    mix *= mute[:, None]
    mix = mix[:int(dur * SR)]
    fade = int(1.5 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    peak = np.abs(mix).max() + 1e-9
    return mix / peak * 0.89 * float(score.get('gain', 1.0))


def write(path, x):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())


DEMO = {'seed': 3, 'key': 'D', 'scale': 'in', 'cues': [
    {'t': 0.3, 'kind': 'odaiko'}, {'t': 2.0, 'kind': 'taiko'}, {'t': 3.0, 'until': 7.0, 'kind': 'pulse', 'bpm0': 60, 'bpm1': 96},
    {'t': 7.2, 'until': 9.4, 'kind': 'roll', 'gain': 0.8}, {'t': 9.6, 'kind': 'odaiko'},
    {'t': 11.0, 'kind': 'koto', 'notes': [[0, 'D4'], [0.45, 'Eb4'], [0.9, 'G4'], [1.6, 'A4'], [2.3, 'Bb4'], [3.0, 'A4']]},
    {'t': 15.0, 'kind': 'shaku', 'notes': [[0, 'A4', 2.6], [2.5, 'Bb4', 1.4], [3.8, 'A4', 3.2]]},
    {'t': 15.0, 'until': 23.0, 'kind': 'drone', 'note': 'D2', 'gain': 0.8}, {'t': 23.0, 'kind': 'rin'}]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--film')
    ap.add_argument('--events')
    ap.add_argument('--out')
    ap.add_argument('--demo', action='store_true')
    a = ap.parse_args()
    if a.demo:
        x = render(DEMO, 28.0)
        out = a.out or os.path.join(REPO, 'output', 'score-demo.wav')
    else:
        F = json.load(open(a.film))
        if 'score' not in F:
            raise SystemExit('score: the film has no "score" block')
        ev = json.load(open(a.events)) if a.events and os.path.exists(a.events) else None
        x = render(F['score'], float(F['duration']) + float(F['score'].get('tail', 0.0)), ev, float(F.get('fps', 30)))
        name = os.path.splitext(os.path.basename(a.film))[0]
        out = a.out or os.path.join(REPO, 'output', name + '-score.wav')
    write(out, x)
    print('[score] %.1f s stereo, peak %.2f -> %s' % (len(x) / SR, float(np.abs(x).max()), os.path.relpath(out, REPO)))


if __name__ == '__main__':
    main()

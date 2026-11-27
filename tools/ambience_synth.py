#!/usr/bin/env python3
"""AMBIENCE SYNTH: place beds made here, from nothing (no download, no licence question: ours, CC0).

    python3 tools/ambience_synth.py night  [--out assets/sfx/amb-night-village.wav] [--secs 60] [--seed 7]
    ffmpeg -i assets/sfx/amb-night-village.wav -b:a 160k assets/sfx/amb-night-village.mp3   (the committed copy)

night   a summer night street: 5-7 crickets (each its own pitch 3.6-5.2 kHz, pulse rate, chirp rhythm and place in
        the stereo field, near ones louder and brighter), a slow breath of wind (brown noise through a soft low-pass,
        swelling every few seconds), now and then a distant second chorus. The loop is seamless (the last 2 s are
        cross-faded into the first), so engine/sound.mjs can loop it under any length of film.

Why synthesis: this cloud environment cannot reach Openverse (27 Nov), and a cricket is a simple, well-studied sound:
a carrier near 4-5 kHz, amplitude-pulsed 3-5 times per chirp (the wing strokes), chirps repeating at 1-3 Hz.
"""
import argparse
import math
import os
import wave

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100


def cricket(n, rng, f0, pulses, pulse_hz, chirp_hz, duty, jitter):
    """One cricket: chirps of `pulses` wing-stroke pulses at pulse_hz, chirps every 1/chirp_hz s (with jitter)."""
    t = np.arange(n) / SR
    out = np.zeros(n)
    k = rng.uniform(0, 1.0 / chirp_hz)
    while k < n / SR:
        for p in range(pulses):
            s = k + p / pulse_hz
            a, b = int(s * SR), int((s + duty / pulse_hz) * SR)
            if a >= n:
                break
            b = min(b, n)
            m = b - a
            env = np.sin(np.linspace(0, math.pi, m)) ** 1.5
            ph = 2 * math.pi * f0 * t[a:b] * (1 + 0.004 * math.sin(p))
            out[a:b] += env * (np.sin(ph) + 0.25 * np.sin(2 * ph + 0.3))
        k += (1.0 / chirp_hz) * (1 + rng.uniform(-jitter, jitter))
    return out


def lowpass(x, cutoff):
    """One-pole low-pass (enough for wind and to darken a far cricket)."""
    a = math.exp(-2 * math.pi * cutoff / SR)
    try:
        from scipy.signal import lfilter
        return lfilter([1 - a], [1, -a], x)
    except ImportError:                  # the same filter, a plain loop (slow: ~2 s per minute of sound)
        y = np.empty_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc = (1 - a) * v + a * acc
            y[i] = acc
        return y


def moving_mean(x, n):
    """Mean over n samples, centred, O(len) (np.convolve with a 1 s box took 7 minutes, 27 Nov)."""
    c = np.cumsum(np.concatenate([[0.0], x]))
    h = n // 2
    i = np.arange(len(x))
    lo, hi = np.clip(i - h, 0, len(x)), np.clip(i + h + 1, 0, len(x))
    return (c[hi] - c[lo]) / (hi - lo)


def night(secs, seed):
    rng = np.random.default_rng(seed)
    n = int(secs * SR)
    L, R = np.zeros(n), np.zeros(n)
    for c in range(int(rng.integers(5, 8))):
        near = rng.uniform(0.25, 1.0)                      # 1 = close, loud, bright
        f0 = rng.uniform(3600, 5200)
        x = cricket(n, rng, f0, int(rng.integers(3, 6)), rng.uniform(28, 45), rng.uniform(1.2, 3.0),
                    rng.uniform(0.45, 0.7), 0.12)
        if near < 0.6:
            x = lowpass(x, 2500 + 4000 * near)             # far ones lose their edge
        pan = rng.uniform(-0.9, 0.9)
        g = 0.05 + 0.10 * near
        L += x * g * math.cos((pan + 1) * math.pi / 4)
        R += x * g * math.sin((pan + 1) * math.pi / 4)
    # wind: brown noise, low-passed, swelling slowly; a little decorrelated between the ears
    for ch, off in ((L, 0.0), (R, 1.7)):
        w = np.cumsum(rng.normal(0, 1, n))
        w -= moving_mean(w, SR)                              # remove the drift
        w = lowpass(w / (np.abs(w).max() + 1e-9), 380)
        swell = 0.55 + 0.45 * np.sin(2 * math.pi * np.arange(n) / SR / 7.3 + off) ** 2
        ch += w * 0.12 * swell
    # seamless loop: the last 2 s cross-faded into the first
    k = 2 * SR
    fade = np.linspace(0, 1, k)
    for ch in (L, R):
        ch[:k] = ch[:k] * fade + ch[-k:] * (1 - fade)
    L, R = L[:-k], R[:-k]
    peak = max(np.abs(L).max(), np.abs(R).max(), 1e-9)
    return np.stack([L, R], 1) / peak * 0.6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kind', choices=['night'])
    ap.add_argument('--out', default=os.path.join(REPO, 'assets', 'sfx', 'amb-night-village.wav'))
    ap.add_argument('--secs', type=float, default=62.0)
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    x = night(a.secs, a.seed)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with wave.open(a.out, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype('<i2').tobytes())
    print('[ambience] %s: %.1f s stereo -> %s' % (a.kind, len(x) / SR, os.path.relpath(a.out, REPO)))


if __name__ == '__main__':
    main()

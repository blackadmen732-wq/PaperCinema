#!/usr/bin/env python3
"""AV SYNC CHECK: where does a sound actually land in an exported clip, against the picture's contact frame?

    python3 tools/av_sync_check.py <clip.mp4> <film> [--hitstop N]

Finds the contact TRANSIENT inside the clip's final mixed audio by cross-correlating the transient clip itself
(output/<film>-sfx/transient.wav) against the mix around the expected time, so a whoosh peaking just before it
cannot fool a loudness detector. Compares that with the contact in film time from output/<film>.bake-events.json
and the first frame that shows it, and prints the offset in ms and in frames (pass within one frame).
"""
import json
import os
import subprocess
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def audio(path, sr=48000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32), sr


def main(clip, film, hitstop=0):
    ev = json.load(open(os.path.join(REPO, 'output', film + '.bake-events.json')))
    fps = ev['fps']
    t_c = ev['contact']['t']
    first_frame = int(np.ceil(t_c * fps - 1e-9)) + 1            # the first rendered frame at/after the contact
    mix, sr = audio(clip)
    tr, _ = audio(os.path.join(REPO, 'output', film + '-sfx', 'transient.wav'))
    tr = tr[: int(0.05 * sr)]                                    # the first 50 ms: the attack
    lo, hi = int(max(0, t_c - 0.25) * sr), int((t_c + 0.25) * sr)
    seg = mix[lo:hi + len(tr)]
    if len(seg) < len(tr) or not np.any(seg):
        print('[sync] %s: no audio around the contact (muted clip?)' % os.path.basename(clip))
        return None
    c = np.correlate(seg - seg.mean(), tr - tr.mean(), mode='valid')
    n = np.sqrt(np.convolve(seg ** 2, np.ones(len(tr)), mode='valid')) * np.linalg.norm(tr) + 1e-12
    k = int(np.argmax(c / n))
    t_audio = (lo + k) / sr
    off = t_audio - t_c
    print('[sync] %s: contact (bake) %.4f s = sub-frame %.2f, first frame showing it %d (%.4f s); transient found at '
          '%.4f s -> offset %+.1f ms (%+.2f frames) %s' % (
              os.path.basename(clip), t_c, t_c * fps + 1, first_frame, (first_frame - 1) / fps, t_audio, off * 1000,
              off * fps, 'PASS (within one frame)' if abs(off * fps) <= 1.0 else 'FAIL'))
    return off


if __name__ == '__main__':
    a = sys.argv[1:]
    hs = int(a[a.index('--hitstop') + 1]) if '--hitstop' in a else 0
    main(a[0], a[1], hs)

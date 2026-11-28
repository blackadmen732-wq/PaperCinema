"""Onset detection regressions: fast, from the repo's own sound files (ffmpeg decodes them) and synthetic tones."""
import os, subprocess, unittest
import numpy as np
from vyrn import audio as A

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SR = A.SR


def load(name):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(ROOT, 'assets/sfx', name), '-ac', '1', '-ar', str(SR),
                        '-f', 'f32le', '-'], capture_output=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def mix(parts, seconds=8):
    x = np.zeros(SR * seconds, np.float32)
    for s, t, g in parts:
        a = int(t * SR)
        x[a:a + s.size] += (s * g)[:x.size - a]
    return x


class OnsetTest(unittest.TestCase):
    def test_landing_thud_after_a_ringing_hit_is_heard(self):
        # dash-test 4.925 s: the land-thud started 71 ms after a ringing onset, but the gap was measured from that
        # onset's late flux peak (58 ms), so the landing was dropped as part of the same sound
        x = mix([(load('wood-chop.mp3'), 1.243, 1), (load('wood-chop.mp3'), 4.251, 1), (load('clash-light.mp3'), 4.251, 0.45),
                 (load('petal-rustle.mp3'), 4.559, 0.45), (load('land-thud.mp3'), 4.925, 1)])
        ts = [o['t'] for o in A.onsets(x)[0]]
        self.assertTrue(any(abs(t - 4.925) < 0.02 for t in ts), [round(t, 3) for t in ts if 4.7 < t < 5.1])

    def test_one_ringing_hit_is_one_onset(self):
        # a ring with a 20 ms attack used to give a second onset 9 ms after the first
        t = np.arange(SR) / SR
        r = (0.5 * np.sin(2 * np.pi * 3000 * t) * np.minimum(1, t / 0.02) * np.exp(-t * 8) * np.minimum(1, (1 - t) / 0.2)).astype(np.float32)
        x = mix([(r, 0.5, 1)], 2) + np.random.default_rng(0).normal(0, 1e-3, SR * 2).astype(np.float32)
        self.assertEqual([round(o['t'], 2) for o in A.onsets(x)[0]], [0.5])


if __name__ == '__main__':
    unittest.main()

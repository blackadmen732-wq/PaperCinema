"""VYRN's deterministic tests, part of `npm test`: the synthetic duel is made from one simulation (so the truth is
exact), ingested from its video, and graded. Floors are the results measured on the integration branch
(vyrn/bench/RESULTS.md); a change that makes VYRN worse fails here. No network, no AI calls, about 5 s.

  python3 -m unittest discover -s vyrn/tests -t .
"""
import json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BenchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='vyrn-test-')
        env = {**os.environ, 'VYRN_CACHE': os.path.join(cls.tmp.name, 'cache')}
        base = os.path.join(cls.tmp.name, 'duel')
        run = lambda *a: subprocess.run([sys.executable, '-m', *a], cwd=ROOT, env=env, capture_output=True, text=True)
        p = run('vyrn.bench.synth', '--out', base)
        assert p.returncode == 0, p.stderr
        p = run('vyrn.bench.run', base)
        assert p.returncode == 0, p.stderr
        cls.R = json.load(open(base + '.results.json'))
        cls.verify = run('vyrn', 'verify', base + '.mp4', '--truth', base + '.timeline.json')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_cuts_all_found_on_the_frame(self):
        c = self.R['cuts']
        self.assertEqual((c['hit'], c['missed'], c['false']), (c['truth'], 0, 0))

    def test_sound_onsets(self):
        s = self.R['sound']
        self.assertGreaterEqual(s['hit'], s['cues'] - 1)          # measured 20/21
        self.assertLessEqual(s['mae_ms'], 10)
        self.assertEqual(s['decoys_counted_as_hits'], 0)

    def test_planted_sync_fault_found_and_measured(self):
        f = self.R['sync_fault']
        self.assertTrue(f['correct'], f)
        self.assertAlmostEqual(f['measured_ms'], 83, delta=10)    # planted +83 ms, measured +82.9

    def test_verify_fails_the_faulty_scene(self):
        self.assertEqual(self.verify.returncode, 1, self.verify.stdout[-400:])

    def test_impacts(self):
        self.assertGreaterEqual(self.R['impacts']['hit'], 3)       # measured 3/5 (no hit-stop on the last ones)
        self.assertLessEqual(len(self.R['impacts']['false']), 1)

    def test_tracking_one_id_per_actor(self):
        for actor, t in self.R['tracking'].items():
            self.assertGreaterEqual(t['mean_iou'], 0.45, actor)   # measured 0.53 and 0.65
            self.assertEqual(t['distinct_ids'], 1, actor)

    def test_events_files_are_aethern_event_2(self):
        import glob
        files = glob.glob(os.path.join(self.tmp.name, 'cache', '*.events.jsonl'))
        self.assertEqual(len(files), 2)                           # the video and the native timeline
        p = subprocess.run([sys.executable, os.path.join(ROOT, 'packages/aethern/bin/aethern'), 'events', 'check', *files],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)
        first = json.loads(open(files[0]).readline())
        self.assertEqual((first['v'], first['project']), (2, 'paper-cinema'))

    def test_cached_reingest_is_fast(self):
        self.assertLess(self.R['cached_reingest_s'], 2.0)


if __name__ == '__main__':
    unittest.main()

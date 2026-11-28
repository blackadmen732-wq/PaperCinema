"""Tests for the Python half of the core. Stdlib only:  python3 -m unittest discover -s tests -v"""
import http.server
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aethern import caps, catalog, config, events, index, mcp, memory, router, skillmap, worker  # noqa: E402

SYSTEMS_MD = """# Systems
## The catalogue
| id | name | does | files | guide | command | status |
|---|---|---|---|---|---|---|
| `ALPHA` | **Alpha** | Reads input and makes frames | `src/a.py` | `docs/A.md` | `python3 src/a.py` | ✅ |
| `BETA` | **Beta sound** | Mixes sound for the frames | `src/b/`, `src/b.py` | `docs/B.md §2` | | 🧪 |
| `GAMMA` | **Gamma** | Planned exporter | `out/*.json` | | | 📋 |
Legend: done
"""


def make_project():
    d = tempfile.mkdtemp(prefix='aethern-test-')
    os.makedirs(os.path.join(d, 'src', 'b'))
    os.makedirs(os.path.join(d, 'docs'))
    for p, t in {'src/a.py': 'print(1)\nprint(2)\n', 'src/b.py': 'x = 1\n', 'docs/A.md': '# A\n', 'docs/B.md': '# B\n',
                 'SYSTEMS.md': SYSTEMS_MD}.items():
        open(os.path.join(d, p), 'w').write(t)
    cfg = {'name': 'T', 'catalog': {'source': 'SYSTEMS.md', 'out': 'systems.json', 'connections': [['ALPHA', 'BETA'], ['BETA', 'GAMMA']]},
           'skills': {'dir': 'skills', 'out': 'SKILLS.md', 'groups': [{'title': 'Core', 'note': 'n', 'prefix': ['core-']},
                                                                         {'title': 'Look', 'note': 'm', 'suffix': ['-style'], 'names': ['lighting']}]},
           'worker': {'protect': ['secret/', 'aethern.json']}}
    json.dump(cfg, open(os.path.join(d, 'aethern.json'), 'w'))
    for n, desc in (('core-a', 'Core skill'), ('noir-style', 'Noir'), ('lighting', 'Light it'), ('misc', 'Other')):
        os.makedirs(os.path.join(d, 'skills', n))
        open(os.path.join(d, 'skills', n, 'SKILL.md'), 'w').write(f'---\nname: {n}\ndescription: {desc}\n---\nbody\n')
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self.d = make_project()
        os.environ.pop('AETHERN_ROOT', None)
        self.cfg = config.load(self.d)
        catalog._LOADED.clear()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)


class ConfigTest(Base):
    def test_find_root_walks_up(self):
        self.assertEqual(config.find_root(os.path.join(self.d, 'src', 'b')), os.path.realpath(self.d))

    def test_defaults_fill_gaps(self):
        self.assertEqual(self.cfg['ai']['cache_ttl_days'], 7)
        self.assertEqual(self.cfg['worker']['protect'], ['secret/', 'aethern.json'])


class CatalogTest(Base):
    def test_build_and_check_files(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = catalog.build(self.cfg)
        self.assertEqual(code, 0, buf.getvalue())
        doc = json.load(open(os.path.join(self.d, 'systems.json')))
        self.assertEqual([s['id'] for s in doc['systems']], ['ALPHA', 'BETA', 'GAMMA'])
        self.assertEqual(doc['systems'][1]['status'], 'test')
        self.assertIsNone(doc['systems'][1]['command'])

    def test_missing_file_fails_build(self):
        os.remove(os.path.join(self.d, 'src', 'a.py'))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(catalog.build(self.cfg), 1)

    def test_show_has_line_counts_and_links(self):
        s = catalog.show(self.cfg, ['alpha'])[0]
        self.assertEqual(s['files'], {'src/a.py': 2})
        self.assertEqual(s['to'], ['BETA'])
        self.assertEqual(catalog.show(self.cfg, ['BETA'])[0]['files']['src/b/'], 'dir')
        self.assertEqual(catalog.show(self.cfg, ['NOPE'])[0]['error'], 'unknown id')

    def test_find_deps_owner(self):
        self.assertEqual(catalog.find(self.cfg, ['sound'])[0]['id'], 'BETA')
        self.assertEqual(catalog.deps(self.cfg, 'ALPHA', depth=3), [['BETA'], ['GAMMA']])
        self.assertEqual(catalog.deps(self.cfg, 'GAMMA', up=True), [['BETA']])
        self.assertEqual(catalog.owner(self.cfg, 'src/b/x.py'), ['BETA'])
        self.assertEqual(catalog.owner(self.cfg, './src/a.py'), ['ALPHA'])
        self.assertEqual(catalog.owner(self.cfg, 'out/z.json'), ['GAMMA'])

    def test_load_works_without_json_and_answer(self):
        self.assertFalse(os.path.exists(os.path.join(self.d, 'systems.json')))
        self.assertIn('"BETA"', catalog.answer(self.cfg, 'BETA'))
        self.assertIn('ALPHA', catalog.answer(self.cfg, 'src/a.py'))


class IndexTest(Base):
    def test_change_detection(self):
        first = index.changed(self.cfg)
        self.assertTrue(first['first_snapshot'])
        same = index.changed(self.cfg)
        self.assertEqual(same['added'] + same['modified'] + same['removed'], [])
        self.assertEqual(same['hashed'], 0)               # nothing moved, nothing re-hashed
        time.sleep(0.01)
        open(os.path.join(self.d, 'src', 'a.py'), 'a').write('print(3)\n')
        open(os.path.join(self.d, 'src', 'new.py'), 'w').write('')
        os.remove(os.path.join(self.d, 'docs', 'B.md'))
        d = index.changed(self.cfg, save=True)
        self.assertEqual((d['added'], d['modified'], d['removed']), (['src/new.py'], ['src/a.py'], ['docs/B.md']))
        self.assertEqual(index.changed(self.cfg)['modified'], [])
        imp = index.impact(self.cfg, d)
        self.assertEqual(sorted(imp['systems']), ['ALPHA', 'BETA'])
        self.assertEqual(imp['downstream'], ['GAMMA'])

    def test_touch_without_content_change_is_not_a_change(self):
        index.changed(self.cfg)
        p = os.path.join(self.d, 'src', 'b.py')
        os.utime(p, (time.time() + 5, time.time() + 5))
        d = index.changed(self.cfg)
        self.assertEqual(d['modified'], [])
        self.assertEqual(d['hashed'], 1)

    def test_cache_dir_is_not_indexed(self):
        index.changed(self.cfg)
        os.makedirs(self.cfg.path('.aethern/cache/x'), exist_ok=True)
        open(self.cfg.path('.aethern/cache/x/y'), 'w').write('z')
        self.assertEqual(index.changed(self.cfg)['added'], [])


class EventsTest(Base):
    def write(self, name, rows):
        p = os.path.join(self.d, name)
        open(p, 'w').write(''.join(json.dumps(r) + '\n' for r in rows))
        return p

    def test_check_and_merge(self):
        a = self.write('a.jsonl', [{'id': 'blade-contact.01', 'type': 'blade-contact', 't': 1.0, 'source': 'engine', 'conf': 1},
                                   {'id': 'footstep.01', 'type': 'footstep', 't': 0.5, 'source': 'engine', 'conf': 1}])
        b = self.write('b.jsonl', [{'id': 'blade-contact.01', 'type': 'blade-contact', 't': 1.02, 'source': 'vyrn.video', 'conf': 0.8, 'data': {}},
                                   {'id': 'sonic.pick.01', 'type': 'sonic.pick', 't': 1.0, 't1': 1.4, 'source': 'sonic', 'entities': ['x'], 'data': {}}])
        self.assertEqual(events.check([a, b]), {})
        m = events.merge([a, b])
        self.assertEqual([e['id'] for e in m], ['footstep.01', 'blade-contact.01', 'sonic.pick.01'])
        bc = m[1]
        self.assertEqual((bc['v'], bc['source'], bc['t']), (2, 'engine', 1.0))
        self.assertEqual([o['source'] for o in bc['evidence']], ['engine', 'vyrn.video'])   # both observations kept
        self.assertNotIn('conflict', bc)                                                    # 20 ms apart: they agree
        self.assertEqual(events.check([self.write('m.jsonl', m)]), {})                      # merged output is valid v2

    def test_bad_lines_are_named(self):
        p = self.write('bad.jsonl', [{'id': 'x', 'type': 'y', 't': -1, 'source': 's'}, {'id': 'x', 'type': 'y', 't': 1, 't1': 0.5, 'source': 's', 'extra': 1},
                                     {'v': 2, 'id': 'x', 'type': 'y', 't': 1, 'source': 's'}])
        errs = events.check([p])[p]
        self.assertTrue(any('line 1' in e and 't must' in e for e in errs))
        self.assertTrue(any('line 2' in e and 't1' in e for e in errs))
        self.assertTrue(any('line 2' in e and 'unknown field' in e for e in errs))
        self.assertTrue(any('line 3' in e and 'project is required' in e for e in errs))

    def test_malformed_lines_are_rejected_with_reasons(self):
        p = os.path.join(self.d, 'junk.jsonl')
        open(p, 'w').write('{"id": "a.01", "type": "a", "t": NaN, "source": "s"}\n'
                           '{not json\n'
                           '{"v": 3, "id": "a.02", "type": "a", "t": 1, "source": "s"}\n'
                           '{"v": 2, "project": "p", "media": "m", "id": "a.03", "type": "a", "t": 1, "source": "s", "evidence": [{"conf": 2}]}\n'
                           '{"id": "a.04", "type": "a", "t": 1, "source": "s", "f": true}\n'
                           '{"id": "a.05", "type": "a", "t": 1, "source": "s"}\n'
                           '{"id": "a.05", "type": "a", "t": 2, "source": "s"}\n')
        errs = events.check([p])[p]
        for n, what in [(1, 'finite'), (2, 'not JSON'), (3, 'unknown version'), (4, 'evidence[0]'), (5, 'f must'), (7, 'duplicate id')]:
            self.assertTrue(any(e.startswith(f'line {n}:') and what in e for e in errs), (n, what, errs))
        self.assertFalse(any(e.startswith('line 6:') for e in errs))
        with self.assertRaises(events.Malformed):
            events.merge([p])

    def test_conflicting_observations_are_kept_with_evidence(self):
        a = self.write('eng.jsonl', [{'id': 'impact.01', 'type': 'impact', 't': 4.30, 'source': 'engine', 'conf': 1, 'data': {'frame': 103}}])
        b = self.write('vid.jsonl', [{'id': 'impact.01', 'type': 'impact', 't': 4.42, 'source': 'vyrn.video', 'conf': 0.7, 'data': {'freeze': True}}])
        m = events.merge([a, b], project='paper-cinema', media='film:dash-test')
        self.assertEqual(len(m), 1)
        e = m[0]
        self.assertTrue(e['conflict'])
        self.assertEqual(e['data']['conflict_on'], ['t'])
        self.assertEqual((e['project'], e['media'], e['t']), ('paper-cinema', 'film:dash-test', 4.30))
        self.assertEqual([(o['source'], o['t'], o['data']) for o in e['evidence']],
                         [('engine', 4.30, {'frame': 103}), ('vyrn.video', 4.42, {'freeze': True})])
        # the same id in two media is two events, not a conflict
        c = self.write('v2.jsonl', [{'v': 2, 'project': 'paper-cinema', 'media': 'film:other', 'id': 'impact.01', 'type': 'impact', 't': 9, 'source': 'engine'}])
        self.assertEqual(len(events.merge([a, c], project='paper-cinema', media='film:dash-test')), 2)
        # merging the merged file again keeps the evidence and the conflict
        again = events.merge([self.write('m.jsonl', m)])
        self.assertTrue(again[0]['conflict'])
        self.assertEqual(len(again[0]['evidence']), 2)

    def test_project_id(self):
        self.assertEqual(events.project_id({'name': 'Paper Cinema'}), 'paper-cinema')
        self.assertEqual(events.project_id({'name': 'X', 'id': 'cinevora'}), 'cinevora')


class CapsTest(Base):
    def setUp(self):
        super().setUp()
        m = {'format': 'aethern-caps/1', 'module': 'echo', 'about': 'test', 'run': [sys.executable, '{dir}/echo.py'], 'cwd': 'root',
             'caps': [{'id': 'echo.json', 'does': 'say the arguments back as json', 'tags': ['repeat', 'json'], 'args': 'WORDS', 'out': 'json'},
                      {'id': 'echo.fail', 'does': 'exit with code one', 'tags': ['error'], 'args': '', 'out': 'text'},
                      {'id': 'echo.sound', 'does': 'pretend to check sound sync', 'tags': ['audio', 'sync'], 'args': '', 'out': 'text'}]}
        os.makedirs(os.path.join(self.d, 'mod'))
        json.dump(m, open(os.path.join(self.d, 'mod', 'capabilities.json'), 'w'))
        open(os.path.join(self.d, 'mod', 'echo.py'), 'w').write(
            'import json, sys\nif sys.argv[1] == "fail": sys.exit(1)\nprint(json.dumps(sys.argv[1:]))\n')
        self.cfg['capabilities'] = [{'file': 'mod/capabilities.json', 'args': ['--host']}]
        self.caps = caps.load(self.cfg)

    def test_find_returns_only_what_fits(self):
        self.assertEqual([c['id'] for c in caps.find(self.caps, 'is the audio in sync?')], ['echo.sound'])
        self.assertEqual(caps.find(self.caps, 'nothing matches here'), [])
        self.assertEqual(set(caps.brief(caps.find(self.caps, 'json')[0])), {'id', 'does'})

    def test_call_runs_the_module_with_host_args(self):
        r = caps.call(self.cfg, self.caps, 'echo.json', ['a', 'b'])
        self.assertEqual((r['ok'], r['out']), (True, ['json', 'a', 'b', '--host']))
        self.assertEqual(caps.call(self.cfg, self.caps, 'echo.fail', [])['exit'], 1)
        self.assertEqual(caps.call(self.cfg, self.caps, 'echo.nope', [])['exit'], 2)

    def test_mcp_three_tools(self):
        inp = io.StringIO('\n'.join(json.dumps(m) for m in [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'find', 'arguments': {'task': 'audio sync'}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'call', 'arguments': {'id': 'echo.json', 'args': ['x']}}},
        ]) + '\n')
        out = io.StringIO()
        mcp.main(self.cfg, inp, out)
        rs = [json.loads(l) for l in out.getvalue().splitlines()]
        self.assertEqual([r['id'] for r in rs], [1, 2, 3, 4])               # no answer to the notification
        self.assertEqual([t['name'] for t in rs[1]['result']['tools']], ['find', 'show', 'call'])
        self.assertEqual(json.loads(rs[2]['result']['content'][0]['text'])[0]['id'], 'echo.sound')
        self.assertEqual(json.loads(rs[3]['result']['content'][0]['text'])['out'], ['json', 'x', '--host'])


class MemoryTest(Base):
    def test_add_dedupe_get_drop(self):
        nid, new = memory.add(self.cfg, 'Sound', 'Clash  cues hit the apex', by='mark')
        self.assertTrue(new)
        self.assertFalse(memory.add(self.cfg, 'sound', 'clash cues hit the APEX')[1])
        memory.add(self.cfg, 'camera', 'Hard cuts on impact')
        self.assertEqual([r['id'] for r in memory.get(self.cfg, 'sound')], [nid])
        self.assertEqual(len(memory.get(self.cfg, grep='cuts')), 1)
        self.assertTrue(memory.drop(self.cfg, nid))
        self.assertEqual(memory.get(self.cfg, 'sound'), [])
        self.assertFalse(memory.drop(self.cfg, nid))


class SkillsTest(Base):
    def test_groups_and_check(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(skillmap.main([], self.cfg), 0)
        text = open(os.path.join(self.d, 'SKILLS.md')).read()
        self.assertLess(text.index('core-a'), text.index('## Look'))
        self.assertIn('[`lighting`](skills/lighting/SKILL.md)', text)
        self.assertIn('## Not grouped yet', text)
        self.assertIn('4 skills', text)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(skillmap.main(['--check'], self.cfg), 0)
            open(os.path.join(self.d, 'SKILLS.md'), 'a').write('edit\n')
            self.assertEqual(skillmap.main(['--check'], self.cfg), 1)


class _Stub(http.server.BaseHTTPRequestHandler):
    calls = 0

    def do_POST(self):
        _Stub.calls += 1
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        out = {'choices': [{'message': {'content': 'echo:' + body['messages'][-1]['content'][-20:]}}],
               'usage': {'completion_tokens': 5, 'total_tokens': 50}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class RouterTest(Base):
    def setUp(self):
        super().setUp()
        self.srv = http.server.HTTPServer(('127.0.0.1', 0), _Stub)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{self.srv.server_port}/v1'
        c = json.load(open(os.path.join(self.d, 'aethern.json')))
        c['ai'] = {'cache': True, 'models': {'stub': {'url': url, 'model': 'm', 'tags': ['write']},
                                             'dead': {'url': 'http://127.0.0.1:9/v1', 'model': 'm', 'tags': ['write']}},
                   'order': {'write': ['dead', 'stub'], 'code': ['stub']}}
        json.dump(c, open(os.path.join(self.d, 'aethern.json'), 'w'))
        self.R = router.Router(config.load(self.d))
        _Stub.calls = 0

    def tearDown(self):
        if self.srv:
            self.srv.shutdown()
            self.srv.server_close()
        super().tearDown()

    def test_fallback_cache_and_budget(self):
        t1, m1 = self.R.run('write', 'hello there')
        self.assertEqual(m1['model'], 'stub')            # 'dead' failed, the chain fell through
        self.assertEqual(_Stub.calls, 1)
        t2, m2 = self.R.run('write', 'hello there')
        self.assertEqual((t2, m2.get('cached')), (t1, True))
        self.assertEqual(_Stub.calls, 1)                 # the second answer cost no request
        self.R.run('write', 'hello there', fresh=True)
        self.assertEqual(_Stub.calls, 2)
        self.R.run('write', 'something else')
        self.assertEqual(_Stub.calls, 3)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.R.budget()
        self.assertIn('1 answered from cache', buf.getvalue())

    def test_expired_cache_is_a_miss(self):
        self.R.run('code', 'x')
        self.R.ttl = 0
        self.R.run('code', 'x')
        self.assertEqual(_Stub.calls, 2)

    def test_all_fail_raises(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.srv = None
        with self.assertRaises(SystemExit):
            self.R.run('code', 'unreachable')


class WorkerTest(Base):
    def setUp(self):
        super().setUp()
        self.W = worker.Worker(self.cfg)

    def test_paths_stay_inside(self):
        self.assertIn('refused', self.W.do_read({'path': '../../etc/passwd'}))
        self.assertIn('refused', self.W.do_write({'path': '/tmp/x', 'content': 'a'}, False))
        self.assertIn('protected', self.W.do_write({'path': 'secret/k', 'content': 'a'}, False))
        self.assertIn('lines 1-2 of 2', self.W.do_read({'path': 'src/a.py'}))

    def test_patch_needs_exactly_one_match(self):
        open(os.path.join(self.d, 'src', 'p.py'), 'w').write('a\na\nb\n')
        self.assertIn('appears 2 times', self.W.do_patch({'path': 'src/p.py', 'old': 'a', 'new': 'c'}, False))
        self.assertEqual(self.W.do_patch({'path': 'src/p.py', 'old': 'b', 'new': 'c'}, False), 'patched src/p.py')

    def test_run_allow_and_deny(self):
        self.assertIn('not allowed', self.W.do_run({'cmd': 'wget x'}, False))
        for c in ('rm -rf src', 'find . -delete', 'git push origin main', 'git reset --hard', 'git clean -fd'):
            self.assertIn('refused', self.W.do_run({'cmd': c}, False), c)
        self.assertTrue(self.W.do_run({'cmd': 'echo hi'}, False).startswith('exit 0'))
        self.assertIn('[dry]', self.W.do_run({'cmd': 'echo hi'}, True))

    def test_map_tool_and_extract(self):
        self.assertIn('"tool":"map"', self.W.tools_text)
        self.assertIn('ALPHA', self.W.do_map({'q': 'src/a.py'}))
        self.assertEqual(worker.extract('```json\n{"tool":"read","path":"a{b}"}\n```'), {'tool': 'read', 'path': 'a{b}'})
        self.assertIsNone(worker.extract('no json here'))


if __name__ == '__main__':
    unittest.main()

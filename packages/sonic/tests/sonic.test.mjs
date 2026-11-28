// Sonic as a standalone package: copied away from Paper Cinema, it still scans, picks and speaks aethern-event/1.
// Run: node --test packages/sonic/tests/sonic.test.mjs   (needs ffmpeg; python3 for the aethern events check)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const PKG = fileURLToPath(new URL('..', import.meta.url));
const REPO = path.resolve(PKG, '../..');
const AETHERN = path.join(REPO, 'packages/aethern/bin/aethern');

test('the package imports nothing outside itself', () => {
  for (const f of ['sonic.mjs', 'cli.mjs']) {
    const src = fs.readFileSync(path.join(PKG, f), 'utf8');
    const specs = [...src.matchAll(/^import .* from '([^']+)'/gm)].map((m) => m[1]);
    for (const s of specs) assert.ok(s.startsWith('node:') || s.startsWith('./'), `${f} imports ${s}`);
  }
});

test('the vocab shipped with the package is the one Paper Cinema uses', () => {
  assert.equal(fs.readFileSync(path.join(PKG, 'vocab.json'), 'utf8'), fs.readFileSync(path.join(REPO, 'library/sonic-vocab.json'), 'utf8'),
    'packages/sonic/vocab.json and library/sonic-vocab.json differ: copy the edited one over the other');
});

test('copied out of the repo: scan, pick from aethern-event/1, output passes aethern events check', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sonic-pkg-'));
  fs.cpSync(PKG, path.join(dir, 'sonic'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'sfx'));
  const ff = (args) => assert.equal(spawnSync('ffmpeg', ['-v', 'error', ...args]).status, 0);
  ff(['-f', 'lavfi', '-i', 'sine=f=3000:d=0.3', '-af', 'afade=t=out:st=0.05:d=0.25', path.join(dir, 'sfx/steel-clash-hit.wav')]);
  ff(['-f', 'lavfi', '-i', 'anoisesrc=d=0.5:c=pink:seed=7', '-af', 'afade=t=in:d=0.2,afade=t=out:st=0.25:d=0.25', path.join(dir, 'sfx/sword-whoosh.wav')]);
  const run = (...a) => spawnSync('node', ['sonic/cli.mjs', ...a], { cwd: dir, encoding: 'utf8' });
  const sc = run('scan');
  assert.equal(sc.status, 0, sc.stderr);
  assert.equal(JSON.parse(sc.stdout).files, 2);
  fs.writeFileSync(path.join(dir, 'in.jsonl'), [
    { v: 1, id: 'e1', type: 'combat.clash', t: 1.2, source: 'test', entities: ['kuro'], data: { material: 'steel', intensity: 0.8 } },
    { v: 1, id: 'e2', type: 'combat.whoosh', t: 2, source: 'test', data: { speed: 9 } },
    { v: 1, id: 'e3', type: 'scene.cut', t: 3, source: 'test' },                 // no sound for this kind: left out
  ].map((e) => JSON.stringify(e)).join('\n') + '\n');
  const pk = run('pick', 'in.jsonl', '--out', 'out.jsonl');
  assert.equal(pk.status, 0, pk.stderr);
  const out = fs.readFileSync(path.join(dir, 'out.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
  assert.deepEqual(out.map((e) => [e.type, e.t, e.data.kind, e.data.sound]),
    [['sonic.pick', 1.2, 'clash', 'steel-clash-hit'], ['sonic.pick', 2, 'whoosh', 'sword-whoosh']]);
  assert.deepEqual(out[0].entities, ['kuro']);
  const ck = spawnSync('python3', [AETHERN, 'events', 'check', path.join(dir, 'out.jsonl')], { encoding: 'utf8' });
  assert.equal(ck.status, 0, ck.stdout + ck.stderr);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('Paper Cinema adapter: its paths and its older cue ids; the package alone reads only cue.event', async () => {
  const pc = await import(path.join(REPO, 'engine/sonic.mjs'));
  const core = await import(path.join(PKG, 'sonic.mjs'));
  assert.equal(pc.DEFAULTS.catalog, 'assets/sfx/sonic.catalog.json');
  assert.equal(pc.DEFAULTS.vocab, 'library/sonic-vocab.json');
  const old = { id: 'auto-clash-3', t: 1.5, why: 'wood on wood, intensity 0.7' };
  assert.deepEqual(pc.eventOfCue(old), { kind: 'clash', material: 'wood', intensity: 0.7, peakAt: 1.5 });
  assert.equal(core.eventOfCue(old), null);
  assert.deepEqual(core.eventOfCue({ event: { kind: 'land' } }), { kind: 'land' });
});

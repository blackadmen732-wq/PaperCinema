// Tests for the JS half of the core:  node --test tests/
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { hashOf, loadState, isFresh, stateWriter } from '../js/state.mjs';
import { ledger } from '../js/ledger.mjs';
import { vendor } from '../js/vendor.mjs';

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'aethern-js-'));

test('hashOf is stable and 12 hex chars', () => {
  assert.equal(hashOf({ a: 1 }), hashOf({ a: 1 }));
  assert.notEqual(hashOf({ a: 1 }), hashOf({ a: 2 }));
  assert.match(hashOf([1, 2]), /^[0-9a-f]{12}$/);
});

test('loadState falls back, isFresh checks hash, status and extra keys', () => {
  assert.deepEqual(loadState('/no/such/file'), { shots: {} });
  assert.deepEqual(loadState('/no/such/file', 'parts'), { parts: {} });
  const done = { status: 'done', hash: 'h', quality: 'final' };
  assert.ok(isFresh(done, 'h', { quality: 'final' }));
  assert.ok(!isFresh(done, 'h', { quality: 'draft' }));
  assert.ok(!isFresh({ ...done, status: 'failed' }, 'h'));
  assert.ok(!isFresh(undefined, 'h'));
});

test('stateWriter serialises many concurrent saves into a valid file', async () => {
  const d = tmp(), p = path.join(d, 's.json');
  const state = { shots: {} };
  const save = stateWriter(p, state);
  await Promise.all(Array.from({ length: 50 }, (_, i) => { state.shots['S' + i] = { i }; return save(); }));
  await save.flush();
  assert.equal(Object.keys(JSON.parse(fs.readFileSync(p, 'utf8')).shots).length, 50);
  assert.ok(!fs.existsSync(p + '.tmp'));
});

test('ledger: a broken kept promise fails, an owed one does not', () => {
  const d = tmp();
  const write = (ps) => fs.writeFileSync(path.join(d, 'promises.json'), JSON.stringify({ promises: ps }));
  const quiet = () => {};
  write([{ id: 'a', status: 'kept', promise: 'p', check: 'true' }, { id: 'b', status: 'OPEN', promise: 'q', why: 'w', check: 'false' }]);
  assert.equal(ledger({ root: d, log: quiet }), 0);
  write([{ id: 'a', status: 'kept', promise: 'p', check: 'false' }]);
  assert.equal(ledger({ root: d, log: quiet }), 1);
  const lines = [];
  write([{ id: 'b', status: 'OPEN', promise: 'q', why: 'w', check: 'false' }]);
  assert.equal(ledger({ root: d, args: ['--open'], log: (s) => lines.push(s) }), 0);
  assert.match(lines.join('\n'), /1 promise\(s\) still owed/);
});

test('vendor --check reports a missing tool, --list prints it', () => {
  const d = tmp();
  fs.mkdirSync(path.join(d, 'vendor'));
  fs.writeFileSync(path.join(d, 'vendor', 'MANIFEST.json'), JSON.stringify({ tools: [{ id: 'x', url: 'u', commit: 'c', licence: 'MIT', size: '1 MB', what: 'w', why_here: 'y', skill: 's' }] }));
  const lines = [];
  assert.equal(vendor({ root: d, args: ['--check'], log: (s) => lines.push(s) }), 1);
  assert.match(lines.join('\n'), /missing {3}x/);
  assert.equal(vendor({ root: d, args: ['--list'], log: () => {} }), 0);
});

test('dom-stub installs a canvas that does not throw', async () => {
  await import('../js/dom-stub.mjs');
  const c = document.createElement('canvas');
  const g = c.getContext('2d');
  g.fillRect(0, 0, 1, 1);
  assert.equal(g.getImageData(0, 0, 2, 2).data.length, 16);
});

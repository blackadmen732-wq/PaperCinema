// Adaptive footsteps (packages/sonic/foley.mjs): deterministic, varied, shaped by what is known about each step.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { renderStep, footstepCues, stepEvents } from '../foley.mjs';

const rms = (y) => Math.sqrt(y.reduce((a, v) => a + v * v, 0) / y.length);
const bright = (y) => { let d = 0; for (let i = 1; i < y.length; i++) d += Math.abs(y[i] - y[i - 1]); return d / (y.reduce((a, v) => a + Math.abs(v), 0) + 1e-9); };
const cache = fs.mkdtempSync(path.join(os.tmpdir(), 'foley-'));

test('same step, same seed: the same samples; another seed: a different step', () => {
  const p = { surface: 'sand', footwear: 'bare', force: 0.6, seed: 'a' };
  assert.deepEqual(renderStep(p), renderStep(p));
  assert.notDeepEqual(renderStep(p), renderStep({ ...p, seed: 'b' }));
});

test('force, distance, footwear and surface shape the sound', () => {
  const base = { surface: 'wood', footwear: 'soft', force: 0.5, distance: 3, seed: 's' };
  assert.ok(rms(renderStep({ ...base, force: 1 })) > rms(renderStep({ ...base, force: 0.2 })), 'a harder step is louder');
  assert.ok(rms(renderStep({ ...base, distance: 12 })) < rms(renderStep(base)), 'a farther step is quieter');
  assert.ok(bright(renderStep({ ...base, distance: 12 })) < bright(renderStep(base)), 'a farther step loses its highs');
  const crest = (y) => Math.max(...y.map(Math.abs)) / rms(y);
  assert.ok(crest(renderStep({ ...base, surface: 'stone', footwear: 'geta' })) > crest(renderStep({ ...base, surface: 'sand', footwear: 'bare' })),
    'wooden sandals on stone click sharper than bare feet in sand');
  assert.ok(renderStep({ ...base, surface: 'metal' }).length > renderStep({ ...base, surface: 'stone' }).length, 'metal rings longer');
});

test('cues: one per step, none on a landing cue, both feet on one frame make one step, every step its own file', () => {
  const steps = [0.5, 1.0, 1.005, 1.5, 2.0, 2.5].map((t, i) => ({ t, actor: 'kojiro', side: i % 2 ? 'L' : 'R', speed: 2 + i * 0.3, point: [0, 0, i] }));
  const { cues, skipped } = footstepCues(steps, { surface: 'sand', cast: { kojiro: { weight: 85, footwear: 'geta' } }, cache,
    avoid: [{ t: 2.0, event: { kind: 'land', who: 'kojiro', peakAt: 2.0 } }, { t: 1.5, event: { kind: 'whoosh', who: 'kojiro' } }] });
  assert.deepEqual(cues.map((c) => c.event.peakAt), [0.5, 1, 1.5, 2.5]);
  assert.equal(cues[1].event.feet, 'both');
  assert.deepEqual(skipped.map((s) => s.why), ['both feet on one frame: one step', 'land cue already there']);
  assert.equal(new Set(cues.map((c) => c.file)).size, cues.length);
  assert.ok(cues.every((c) => fs.existsSync(c.file) && c.event.weight === 85 && c.event.footwear === 'geta'));
  const ev = stepEvents(cues, 'paper-cinema', 'film:test');
  assert.deepEqual([ev[0].v, ev[0].type, ev[0].t, ev[0].entities[0]], [2, 'sonic.step', 0.5, 'kojiro']);
});

test('the camera distance comes from the camera position at the step', () => {
  const { cues } = footstepCues([{ t: 1, actor: 'a', side: 'R', speed: 2, point: [0, 0, 10] }], { camera: () => [0, 0, 0], cache });
  assert.equal(cues[0].event.distance, 10);
});

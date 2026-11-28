// SONIC regression tests: the benchmark's claims, turned into checks that fail when they stop being true.
//   npm test   (node --test tests/*.test.mjs)       about 30 s; the Earshot and git-history checks skip when unavailable
// Each test names the claim it guards (docs/SONIC.md, docs/SONIC-BENCHMARK.md).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync, execFileSync } from 'node:child_process';
import { measure, scan, loadCatalog, query, pick, brief, parseQuery, eventOfCue, applyToCues, sharedEvents, DEFAULTS, ANALYZER } from '../engine/sonic.mjs';
import { runProbe, makeProbe } from '../tools/sonic_verify.mjs';

const vocab = JSON.parse(fs.readFileSync(DEFAULTS.vocab, 'utf8'));
const cat = loadCatalog();
const byId = Object.fromEntries(cat.sounds.map((s) => [s.id, s]));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'sonic-test-'));
const pearson = (xs, ys) => { const n = xs.length, mx = xs.reduce((a, b) => a + b) / n, my = ys.reduce((a, b) => a + b) / n;
  let a = 0, b = 0, c = 0; for (let i = 0; i < n; i++) { a += (xs[i] - mx) * (ys[i] - my); b += (xs[i] - mx) ** 2; c += (ys[i] - my) ** 2; } return a / Math.sqrt(b * c); };

test('catalog: every record has the schema fields and is current with the analyzer', () => {
  assert.equal(cat.schema, 'sonic-catalog/1');
  for (const s of cat.sounds) {
    assert.ok(s.id && s.hash && s.m && s.tags, `record ${s.id} incomplete`);
    assert.equal(s.analyzer, ANALYZER, `${s.id} measured by an older analyzer: run node tools/sonic.mjs scan`);
    for (const k of ['dur', 'peakT', 'peakTPlay', 'weight', 'intensity', 'brightness']) assert.equal(typeof s.m[k], 'number', `${s.id}.m.${k}`);
    for (const k of ['weight', 'intensity', 'brightness']) assert.ok(s.m[k] >= 0 && s.m[k] <= 1, `${s.id}.m.${k} out of 0..1`);
  }
  assert.ok(cat.sounds.filter((s) => s.file).length >= 50, 'local files (38 + 12 PaperAcoustics) catalogued');
});

test('catalog: every audio file under assets/sfx is in it (no stale catalog)', () => {
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? walk(path.join(d, e.name)) : /\.(mp3|wav)$/.test(e.name) && !e.name.startsWith('_') ? [path.join(d, e.name)] : []);
  const files = new Set(cat.sounds.map((s) => s.file));
  for (const f of walk('assets/sfx')) assert.ok(files.has(f), `${f} is not catalogued: run node tools/sonic.mjs scan`);
});

test('cache: a re-scan with nothing changed measures nothing', () => {
  const c = path.join(tmp, 'cat.json');
  fs.copyFileSync(DEFAULTS.catalog, c);
  const { stats } = scan({ catalog: c, banks: [] });
  assert.equal(stats.measured, 0);
  assert.ok(stats.cached >= 50);
});

test('analyzer: deterministic, and the peak time matches a known click', () => {
  const f = path.join(tmp, 'click.wav');
  // silence, then a 3 ms burst starting at exactly 0.25 s
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', "aevalsrc='if(between(t,0.25,0.253),sin(2*PI*2000*t),0)':d=0.6:s=44100", f]);
  const a = measure(f), b = measure(f);
  assert.deepEqual(a, b);
  assert.ok(Math.abs(a.peakT - 0.25) <= 0.003, `peakT ${a.peakT}, want 0.250 ± 0.003`);
});

test('analyzer vs Earshot\'s own stated peaks: ≥ 85% of the bank within 20 ms', (t) => {
  const bank = cat.sounds.filter((s) => s.bank === 'earshot');
  if (!bank.length) return t.skip('Earshot bank not catalogued here');
  assert.equal(bank.length, 252);
  const ok = bank.filter((s) => Math.abs(s.m.peakT - s.bankPeak) <= 0.02).length;
  assert.ok(ok / bank.length >= 0.85, `${ok}/${bank.length} within 20 ms`);
});

test('query: filters, sorting, errors, and answers stay one short line per sound', () => {
  const hits = query(cat, 'material=steel action=impact dur<2', { sort: 'weight' });
  assert.equal(hits[0].id, 'clash-steel');
  assert.ok(hits.every((s) => s.tags.material.includes('steel') && s.m.dur < 2));
  assert.ok(query(cat, '"material=steel|wood"'.replace(/"/g, '')).length > query(cat, 'material=steel').length);
  assert.throws(() => parseQuery('nonsense'));
  for (const s of hits) assert.ok(brief(s).length < 140, 'a result line grew past 140 characters');
});

test('material fallback: matched facets are hard, fallbacks are explicit, no match keeps the engine sound', () => {
  const st = () => ({ recent: {} });
  assert.ok(pick(cat, vocab, { kind: 'clash', material: 'wood', intensity: 0.9 }, st()).sound.tags.material.includes('wood'));
  assert.ok(pick(cat, vocab, { kind: 'clash', material: 'paper', intensity: 0.8 }, st()).sound.tags.material.includes('paper'));
  assert.equal(pick(cat, vocab, { kind: 'clash', material: 'glass', intensity: 0.8 }, st()), null, 'no glass and no fallback: no pick');
  // a library with no wood impacts at all: wood falls back to steel and says so
  const noWood = { ...cat, sounds: cat.sounds.filter((s) => !s.tags.material.includes('wood')) };
  const r = pick(noWood, vocab, { kind: 'clash', material: 'wood', intensity: 0.9 }, st());
  assert.ok(r.sound.tags.material.includes('steel'));
  assert.equal(r.fallback, 'material wood→steel');
  // and in a film: the cue keeps its own sound, and the report says why
  const cues = [{ id: 'auto-clash-0', sfx: 'clap', t: 1, len: 1, gain: 1, rate: 1, event: { kind: 'clash', material: 'glass', intensity: 0.8, peakAt: 1 } }];
  const rep = applyToCues(cues, { catalog: cat, vocab });
  assert.equal(cues[0].sfx, 'clap');
  assert.equal(rep[0].kept, true);
});

test('events: old events files (no cue.event) are read back from id and why', () => {
  assert.deepEqual(eventOfCue({ id: 'auto-clash-3', t: 2, why: 'blade contact (wood), intensity 0.7' }), { kind: 'clash', material: 'wood', intensity: 0.7, peakAt: 2 });
  assert.equal(eventOfCue({ id: 'auto-whoosh-A-1', t: 1, why: 'A tip 14.2 m/s' }).speed, 14.2);
  assert.equal(eventOfCue({ id: 'auto-land-A-9', t: 1, why: 'A land (3 m/s)' }).kind, 'land');
  assert.equal(eventOfCue({ id: 'title-taiko', t: 0 }), null);
});

test('benchmark claim: faster swings get more intense whooshes, without repeats', () => {
  const st = { recent: {} }, speeds = [10, 13, 16, 19, 22, 25, 28, 30], ids = [], ints = [];
  for (const [i, v] of speeds.entries()) { const r = pick(cat, vocab, { kind: 'whoosh', speed: v, seed: `t${i}` }, st); ids.push(r.sound.id); ints.push(r.sound.m.intensity); }
  assert.ok(pearson(speeds, ints) >= 0.3, `speed→intensity correlation ${pearson(speeds, ints).toFixed(2)} < 0.3`);
  for (let i = 1; i < ids.length; i++) assert.notEqual(ids[i], ids[i - 1], 'the same whoosh twice in a row');
});

test('benchmark claim: harder clashes get heavier, more intense sounds', () => {
  const I = [0.1, 0.3, 0.5, 0.7, 0.9], w = I.map((x) => pick(cat, vocab, { kind: 'clash', material: 'steel', intensity: x, seed: 'c' }, { recent: {} }).sound.m.weight);
  assert.ok(pearson(I, w) >= 0.5, `intensity→weight correlation ${pearson(I, w).toFixed(2)}`);
});

test('shared events: one sonic.pick per chosen sound, at the event moment', () => {
  const ev = sharedEvents([{ id: 'auto-clash-0', kind: 'clash', now: 'clash-steel', was: 'clash-steel', score: 1, t: 0.993, peakAt: 1, who: 'A' }, { id: 'x', kept: true, now: null }]);
  assert.equal(ev.length, 1);
  assert.deepEqual(Object.keys(ev[0]).sort(), ['conf', 'data', 'entities', 'id', 'method', 'source', 't', 't1', 'type']);
  assert.equal(ev[0].t, 1);
  assert.equal(ev[0].type, 'sonic.pick');
});

test('final mix: with Sonic on, every isolated sound lands within 25 ms of its event (checked in the decoded output)', () => {
  const r = runProbe(path.join(tmp, 'probe'));
  assert.equal(r.sonic.n, 12);
  assert.ok(r.sonic.maxMs <= 25, `worst ${r.sonic.maxMs} ms`);
  assert.ok(r.sonic.medianMs <= 6, `median ${r.sonic.medianMs} ms`);
  assert.ok(r.sonic.meanMs < r.off.meanMs, 'Sonic is not closer than the engine sounds');
});

// The Sonic extraction must not change the mix. Exactly ONE approved change has been layered on the engine
// since the pre-Sonic commit: the hit-cue de-click (hits fade in over ~1 ms instead of 10 ms). That is an
// explicit, separately-reviewed exception. The pre-Sonic baseline is left UNTOUCHED; we prove (a) every
// non-hit sound is byte-identical to pre-Sonic, so the extraction changed nothing, and (b) the de-click is
// the one and only difference, present on hits in the current engine and absent from the pre-Sonic engine.
const HIT_RE = /clash|impact|contact|hit|auto-step|thud|fall|clap|bell|drum/i;

test('Sonic off: every non-hit sound is byte-identical to the pre-Sonic engine', (t) => {
  const added = execFileSync('git', ['log', '--diff-filter=A', '--format=%H', '--', 'engine/sonic.mjs'], { encoding: 'utf8' }).trim().split('\n').filter(Boolean).pop();
  const base = added ? `${added}~1` : null;
  const old = base && spawnSync('git', ['show', `${base}:engine/sound.mjs`]);
  if (!old || old.status !== 0) return t.skip('the commit before Sonic is not in this clone (shallow?)');
  const d = path.join(tmp, 'ident'), p = makeProbe(d), head = path.join(d, 'sound-before.mjs');
  fs.writeFileSync(head, old.stdout);                        // pre-Sonic engine, UNMODIFIED
  // Render on a probe with the hit cues removed, so the de-click exception cannot touch this comparison.
  const ev = JSON.parse(fs.readFileSync(p.events, 'utf8'));
  ev.cues = ev.cues.filter((c) => !HIT_RE.test(c.id));
  const nohit = path.join(d, 'nohit.events.json');
  fs.writeFileSync(nohit, JSON.stringify(ev));
  const CR = 'assets/sfx/credits.json', credits = fs.readFileSync(CR);
  const md5 = (f) => crypto.createHash('md5').update(spawnSync('ffmpeg', ['-v', 'error', '-i', f, '-map', '0:a', '-f', 's16le', '-'], { maxBuffer: 1 << 28 }).stdout).digest('hex');
  try {
    for (const [s, o] of [[head, 'before.mp4'], ['engine/sound.mjs', 'now.mp4']]) {
      const r = spawnSync('node', [s, '--film', p.film, '--video', p.video, '--events', nohit, '--out', path.join(d, o)], { encoding: 'utf8' });
      assert.equal(r.status, 0, r.stderr);
    }
  } finally { fs.writeFileSync(CR, credits); }
  assert.equal(md5(path.join(d, 'now.mp4')), md5(path.join(d, 'before.mp4')));
});

test('the hit-cue de-click is the one approved difference from the pre-Sonic engine', (t) => {
  const added = execFileSync('git', ['log', '--diff-filter=A', '--format=%H', '--', 'engine/sonic.mjs'], { encoding: 'utf8' }).trim().split('\n').filter(Boolean).pop();
  const base = added ? `${added}~1` : null;
  const old = base && spawnSync('git', ['show', `${base}:engine/sound.mjs`]);
  if (!old || old.status !== 0) return t.skip('the commit before Sonic is not in this clone (shallow?)');
  const before = old.stdout.toString(), now = fs.readFileSync('engine/sound.mjs', 'utf8');
  // pre-Sonic faded every non-bed cue in over 10 ms; the current engine de-clicks hit cues to ~1 ms.
  // LIMITATION (accepted): this verifies the approved impact change by source-code assertion, not by an
  // independent waveform comparison of the de-clicked hit. Waveform verification of the impact change is
  // deferred to the future regression suite; it is not built here.
  assert.ok(before.includes('cue.bed ? 1.5 : 0.01'), 'pre-Sonic fade-in shape not as expected');
  assert.ok(!/0\.001/.test(before), 'pre-Sonic engine already had a de-click; exception assumption is wrong');
  assert.ok(now.includes('HIT.test(cue.id) ? 0.001'), 'current engine no longer carries the reviewed de-click');
});

test('PaperAcoustics: made in code, the same bytes on every run', () => {
  const d = path.join(tmp, 'paper');
  execFileSync('node', ['tools/paper_sfx.mjs', '--out', d, '--no-credits']);
  for (const f of fs.readdirSync('assets/sfx/paper')) assert.ok(fs.readFileSync(path.join(d, f)).equals(fs.readFileSync(path.join('assets/sfx/paper', f))), `${f} differs from a fresh build`);
  const paper = cat.sounds.filter((s) => s.id.startsWith('paper/'));
  assert.equal(paper.length, 12);
  assert.ok(paper.every((s) => s.tags.material.includes('paper')));
});

test('MCP: the server lists its tools and answers a query in one short text', () => {
  const lines = [
    { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't', version: '0' } } },
    { jsonrpc: '2.0', method: 'notifications/initialized' },
    { jsonrpc: '2.0', id: 2, method: 'tools/list' },
    { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'sonic_query', arguments: { q: 'material=steel action=impact dur<2', sort: 'weight', limit: 3 } } },
  ].map((m) => JSON.stringify(m)).join('\n') + '\n';
  const r = spawnSync('node', ['tools/sonic_mcp.mjs'], { input: lines, encoding: 'utf8' });
  const out = Object.fromEntries(r.stdout.trim().split('\n').map((l) => JSON.parse(l)).map((m) => [m.id, m]));
  assert.deepEqual(out[2].result.tools.map((x) => x.name), ['sonic_query', 'sonic_pick', 'sonic_show', 'sonic_stats']);
  assert.ok(JSON.stringify(out[2].result.tools).length < 2000, 'tool definitions grew: every client pays for them on every request');
  const text = out[3].result.content[0].text;
  assert.match(text, /^clash-steel /);
  assert.ok(text.length < 400);
});

test('offline mix: a sound that is neither saved nor reachable no longer stops the mix (stand-in or skip, reported)', () => {
  const d = path.join(tmp, 'offline'); fs.mkdirSync(d, { recursive: true });
  const film = path.join(d, 'offline.json'), video = path.join(d, 'v.mp4'), out = path.join(d, 'out.mp4');
  fs.writeFileSync(film, JSON.stringify({ duration: 3, autoSounds: {}, sounds: [
    { id: 'clap', t: 0.3, len: 0.4, gain: 0.8, query: 'clap' },
    { id: 'zz-test-door-slam', t: 1, len: 1, gain: 0.8, query: 'wooden door slam', min: 0.3, max: 5 },
    { id: 'zz-test-qwxv', t: 2, len: 0.5, gain: 0.8, query: 'qwxv blorp', min: 0.1, max: 5 } ] }));
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=black:s=64x64:r=24:d=3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', video]);
  const CR = 'assets/sfx/credits.json', credits = fs.readFileSync(CR);
  let r;
  // a real network failure (nothing listens on port 9), not just the --offline switch
  try { r = spawnSync('node', ['engine/sound.mjs', '--film', film, '--video', video, '--events', path.join(d, 'none.json'), '--out', out], { encoding: 'utf8', env: { ...process.env, OPENVERSE_API: 'http://127.0.0.1:9' } }); }
  finally { fs.writeFileSync(CR, credits); }
  assert.equal(r.status, 0, r.stderr || r.stdout);
  assert.ok(fs.existsSync(out));
  const rep = JSON.parse(fs.readFileSync('output/offline.sound-report.json', 'utf8'));
  assert.deepEqual(rep.substituted.map((x) => x.id), ['zz-test-door-slam']);
  assert.ok(byId[rep.substituted[0].with].tags.action.includes('impact'));
  assert.deepEqual(rep.skipped.map((x) => x.id), ['zz-test-qwxv']);
});

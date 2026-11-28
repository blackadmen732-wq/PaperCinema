#!/usr/bin/env node
// SONIC peak check, from the FINAL AUDIO: does each sound's loudest moment land on its event?
// It does not trust the catalog's measured peaks or Sonic's own report: it decodes the finished mix and finds, for
// every event that stands alone (no other event within --iso s), the loudest 1 ms in a window around it.
//
//   node tools/sonic_verify.mjs film/<name>.json                 real film: output/<name>.events.json + output/<name>-final.mp4
//   node tools/sonic_verify.mjs --events E.json --audio mix.mp4  any events file and any mix
//   node tools/sonic_verify.mjs --probe                          a built-in probe (one event every 1.2 s, no beds), mixed by
//                                                                engine/sound.mjs twice, Sonic off and on → output/sonic-verify/
// Options: --window 0.25 (s searched each side) --iso 0.6 --json. Exit 1 when the worst error is above --max (ms).
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync, execFileSync } from 'node:child_process';
import { eventOfCue } from '../engine/sonic.mjs';

const SR = 44100;
/** RMS envelope at 1 ms steps over 5 ms windows (the same 'loudest 5 ms' as the catalog's peakT) of the first audio stream of a file. */
export function envelope(file) {
  const r = spawnSync('ffmpeg', ['-v', 'error', '-i', file, '-map', '0:a:0', '-ac', '1', '-ar', String(SR), '-f', 'f32le', '-'], { maxBuffer: 1 << 30 });
  if (r.status !== 0) throw new Error(`cannot decode ${file}`);
  const x = new Float32Array(r.stdout.buffer, r.stdout.byteOffset, Math.floor(r.stdout.length / 4));
  const win = Math.round(5 * SR / 1000), env = new Float32Array(Math.floor(x.length * 1000 / SR));
  for (let i = 0; i < env.length; i++) { let s = 0; const a = Math.round(i * SR / 1000); for (let j = 0; j < win && a + j < x.length; j++) s += x[a + j] * x[a + j]; env[i] = Math.sqrt(s / win); }
  return env;
}
/** The moments the cues of an events file aim their peak at: { id, kind, t }. */
export function eventTimes(evData) {
  const out = [];
  for (const c of evData.cues ?? []) { const e = eventOfCue(c); if (e?.peakAt != null && !/-light$/.test(c.id)) out.push({ id: c.id, kind: e.kind, t: e.peakAt }); }
  return out.sort((a, b) => a.t - b.t);
}
/** For every isolated event: where the loudest moment of the mix actually is, and how far off that is. */
// A hit is judged by its ONSET: the first moment it comes within 6 dB of its loudest (the master limiter flattens a
// hit's top, and a low thud's "loudest 5 ms" is one crest of its wave). Everything else by its loudest 5 ms.
// Kinds with align: "onset" in the vocab are hits: the same rule Sonic aligns them by.
const ONSET = new Set(Object.entries(JSON.parse(fs.readFileSync('library/sonic-vocab.json', 'utf8')).events ?? {}).filter(([, v]) => v.align === 'onset').map(([k]) => k));
export function verify(audio, events, o = {}) {
  const env = envelope(audio), W = Math.round((o.window ?? 0.25) * 1000), iso = o.iso ?? 0.6;
  const rows = [];
  for (const e of events) {
    if (events.some((x) => x !== e && Math.abs(x.t - e.t) < iso)) continue;
    const c = Math.round(e.t * 1000), lo = Math.max(0, c - W), hi = Math.min(env.length - 1, c + W); let best = -1, at = c;
    for (let i = lo; i <= hi; i++) if (env[i] > best) { best = env[i]; at = i; }
    let on = lo; while (on < at && env[on] < best * 0.5) on++;   // first crossing from the left (the event is isolated)
    const by = ONSET.has(e.kind) ? 'onset' : 'peak', hit = by === 'onset' ? on : at;
    rows.push({ id: e.id, kind: e.kind, t: e.t, by, peak: at / 1000, onset: on / 1000, errMs: hit - c });
  }
  const abs = rows.map((r) => Math.abs(r.errMs)).sort((a, b) => a - b);
  return { rows, n: rows.length, skipped: events.length - rows.length, medianMs: abs[Math.floor((abs.length - 1) / 2)] ?? null,
    meanMs: abs.length ? +(abs.reduce((a, b) => a + b, 0) / abs.length).toFixed(1) : null, maxMs: abs.length ? abs[abs.length - 1] : null };
}

/** The probe: whooshes at several blade speeds, clashes at several intensities, ground events; one per 1.2 s, no beds. */
export function makeProbe(dir) {
  fs.mkdirSync(dir, { recursive: true });
  const dB = (x) => 10 ** (x / 20), r3 = (x) => +(+x).toFixed(3), cues = [];
  let t = 0.8;
  for (const v of [10, 14, 18, 22, 26, 30]) { const k = Math.max(0, Math.min(1, (v - 9) / 21)), n = cues.length;
    cues.push({ id: `auto-whoosh-A-${n}`, sfx: ['whoosh-a', 'whoosh-b', 'whoosh-c'][n % 3], t: r3(t - 0.06), len: 0.6, gain: r3(dB(-14)), rate: r3(0.85 + 0.5 * k),
      why: `A tip ${v.toFixed(1)} m/s`, event: { kind: 'whoosh', who: 'A', speed: v, peakAt: r3(t) } }); t += 1.2; }
  [0.2, 0.5, 0.8, 1.0].forEach((I, i) => { cues.push({ id: `auto-clash-${i}`, sfx: I >= 0.4 ? 'clash-steel' : 'clash-light', t: r3(t), len: 1.0, gain: r3(dB(-6 + 6 * I)), rate: 1,
    why: `blade contact, intensity ${I}`, event: { kind: 'clash', material: 'steel', intensity: I, peakAt: r3(t) } }); t += 1.2; });
  for (const [kind, sfx, extra] of [['dash', 'dash-burst', { speed: 8 }], ['land', 'land-thud', { speed: 3, height: 0.8 }]]) {
    cues.push({ id: `auto-${kind}-A-${cues.length}`, sfx, t: r3(t - (kind === 'dash' ? 0.03 : 0)), len: 0.8, gain: r3(dB(-8)), rate: 1, why: `A ${kind}`, event: { kind, who: 'A', peakAt: r3(t), ...extra } }); t += 1.2; }
  const dur = Math.ceil(t + 1);
  const film = { duration: dur, sounds: [], autoSounds: { preDip: 0 } };
  fs.writeFileSync(path.join(dir, 'probe.json'), JSON.stringify(film));
  // contacts/impacts left empty on purpose: no pre-hit dip, so nothing but the cue itself shapes each peak
  fs.writeFileSync(path.join(dir, 'probe.events.json'), JSON.stringify({ cues, contacts: [], stops: [], impacts: [] }));
  const video = path.join(dir, 'black.mp4');
  if (!fs.existsSync(video)) execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', `color=black:s=64x64:r=24:d=${dur}`, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', video]);
  return { film: path.join(dir, 'probe.json'), events: path.join(dir, 'probe.events.json'), video };
}
/** Mix the probe with engine/sound.mjs (Sonic off and on) and verify both from the decoded output. */
export function runProbe(dir = 'output/sonic-verify', script = 'engine/sound.mjs') {
  const p = makeProbe(dir), ev = JSON.parse(fs.readFileSync(p.events, 'utf8')), out = {};
  // engine/sound.mjs records credits for whatever it plays; a probe is not a film, so its credits are put back after
  const CR = 'assets/sfx/credits.json', credits = fs.readFileSync(CR);
  try { for (const mode of ['off', 'sonic']) {
    const mix = path.join(dir, `probe-${mode}.mp4`);
    const r = spawnSync('node', [script, '--film', p.film, '--video', p.video, '--events', p.events, '--out', mix, ...(mode === 'sonic' ? ['--sonic'] : [])], { encoding: 'utf8' });
    if (r.status !== 0) throw new Error(`probe mix (${mode}) failed: ${r.stderr || r.stdout}`);
    out[mode] = verify(mix, eventTimes(ev), { iso: 0.6 });
  } } finally { fs.writeFileSync(CR, credits); }
  return out;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const a = process.argv.slice(2), opt = (n, d) => { const i = a.indexOf('--' + n); return i >= 0 ? a[i + 1] : d; };
  const show = (name, v) => {
    if (a.includes('--json')) return;
    console.log(`${name}: ${v.n} isolated events (${v.skipped} skipped, too close to another) · error median ${v.medianMs} ms, mean ${v.meanMs} ms, worst ${v.maxMs} ms`);
    for (const r of v.rows) console.log(`  ${r.id.padEnd(18)} ${r.kind.padEnd(7)} event ${r.t.toFixed(3)} s → ${r.by} at ${(r.by === 'onset' ? r.onset : r.peak).toFixed(3)} s (${r.errMs >= 0 ? '+' : ''}${r.errMs} ms)`);
  };
  let res;
  if (a.includes('--probe')) { res = runProbe(); show('Sonic OFF (engine sounds)', res.off); show('Sonic ON', res.sonic); }
  else {
    const film = a.find((x) => x.endsWith('.json') && !x.startsWith('--')), base = film ? path.basename(film, '.json') : null;
    const evFile = opt('events', base && `output/${base}.events.json`), audio = opt('audio', base && [`output/${base}-final.mp4`, `output/${base}-sound.mp4`].find((f) => fs.existsSync(f)));
    if (!evFile || !audio || !fs.existsSync(evFile)) { console.error('need an events file and a mixed audio/video file (render the film first: bash tools/film.sh film/<name>.json)'); process.exit(2); }
    res = { mix: verify(audio, eventTimes(JSON.parse(fs.readFileSync(evFile, 'utf8'))), { window: +opt('window', 0.25), iso: +opt('iso', 0.6) }) };
    show(audio, res.mix);
  }
  if (a.includes('--json')) console.log(JSON.stringify(res));
  const max = +opt('max', NaN), worst = Math.max(...Object.values(res).map((v) => v.maxMs ?? 0));
  if (Number.isFinite(max) && worst > max) { console.error(`✗ worst peak error ${worst} ms > ${max} ms`); process.exit(1); }
}

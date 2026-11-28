#!/usr/bin/env node
// PAPERACOUSTICS: our own paper sounds, made in code (no recordings, no licence needed; like tools/synth_sfx.sh).
//   node tools/paper_sfx.mjs            → assets/sfx/paper/*.mp3 + credits in assets/sfx/credits.json
//   node tools/paper_sfx.mjs --list     → what it makes, one line each
//   node tools/paper_sfx.mjs --out dir --no-credits   → somewhere else, credits untouched (the regression test)
//
// Paper does not ring: it is a dry crackle of tiny fractures (a crease, a crumple, a tear is thousands of fibre
// breaks) over a soft body of air and card. So every sound here is built from three parts:
//   CRACKLE  sparse random clicks (a Poisson process), each a very short decaying band-passed burst; density and size
//            shape the gesture (a fold is a short dense run, a crumple long and coarse, a tear a fast sliding run)
//   AIR      filtered noise for the sheet moving (flutter, slide, slash)
//   BODY     a low damped thump for folded card being struck or pressed
// Deterministic: a seeded generator, so the same command makes the same audio on every machine.
// Then: node tools/sonic.mjs scan (the catalog tags them material=paper by their names). Guide: docs/SONIC.md.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const SR = 44100, argOut = process.argv.indexOf('--out'), OUT = argOut > 0 ? process.argv[argOut + 1] : 'assets/sfx/paper', CREDITS = 'assets/sfx/credits.json';
const WRITE_CREDITS = !process.argv.includes('--no-credits');
const rng = (seed) => () => { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const buf = (dur) => new Float64Array(Math.round(dur * SR));
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

// a 2-pole resonant band-pass (RBJ), run in place on a segment
function bandpass(x, f, q, from = 0, to = x.length) {
  const w = 2 * Math.PI * f / SR, al = Math.sin(w) / (2 * q), a0 = 1 + al;
  const b0 = al / a0, b2 = -al / a0, a1 = -2 * Math.cos(w) / a0, a2 = (1 - al) / a0;
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = from; i < to; i++) { const y = b0 * x[i] + b2 * x2 - a1 * y1 - a2 * y2; x2 = x1; x1 = x[i]; y2 = y1; y1 = y; x[i] = y; }
  return x;
}
const onepoleLP = (x, f) => { const a = Math.exp(-2 * Math.PI * f / SR); let y = 0; for (let i = 0; i < x.length; i++) { y = (1 - a) * x[i] + a * y; x[i] = y; } return x; };
const onepoleHP = (x, f) => { const a = Math.exp(-2 * Math.PI * f / SR); let y = 0, px = 0; for (let i = 0; i < x.length; i++) { y = a * (y + x[i] - px); px = x[i]; x[i] = y; } return x; };

/** CRACKLE: clicks at rate(t) per second, each size ~ size(t), centre frequency ~ band(t) Hz. */
function crackle(dur, { rate, size = () => 1, band = () => 4000, q = 1.4, seed = 1, grain = 0.0025 }) {
  const out = buf(dur), r = rng(seed), g = Math.max(8, Math.round(grain * SR)), tmp = new Float64Array(g * 4);
  let t = 0;
  while (t < dur) {
    const rt = Math.max(1, rate(t / dur));
    t += -Math.log(1 - r()) / rt;                        // Poisson: exponential gaps
    if (t >= dur) break;
    const i0 = Math.round(t * SR), a = size(t / dur) * (0.25 + 0.75 * r() ** 2) * (r() < 0.5 ? -1 : 1);
    const len = Math.round(g * (0.5 + 1.5 * r()));
    for (let k = 0; k < len; k++) tmp[k] = (r() * 2 - 1) * Math.exp(-6 * k / len);
    bandpass(tmp, clamp(band(t / dur) * (0.7 + 0.6 * r()), 300, 16000), q, 0, len);
    for (let k = 0; k < len && i0 + k < out.length; k++) out[i0 + k] += a * tmp[k];
    tmp.fill(0, 0, len);
  }
  return out;
}
/** AIR: noise through a band whose centre and level follow f(t) and env(t). */
function air(dur, { f, env, q = 0.9, seed = 7, steps = 64 }) {
  const out = buf(dur), r = rng(seed), n = out.length, seg = Math.ceil(n / steps);
  for (let i = 0; i < n; i++) out[i] = r() * 2 - 1;
  for (let s = 0; s < steps; s++) bandpass(out, f((s + 0.5) / steps), q, s * seg, Math.min(n, (s + 1) * seg));
  for (let i = 0; i < n; i++) out[i] *= env(i / n);
  return out;
}
/** BODY: a damped low sine with a quick downward pitch, the card's own thump. */
function body(dur, { f0 = 140, f1 = 70, decay = 18, seed = 3 }) {
  const out = buf(dur), r = rng(seed); let ph = 0;
  for (let i = 0; i < out.length; i++) { const t = i / SR, f = f1 + (f0 - f1) * Math.exp(-25 * t); ph += 2 * Math.PI * f / SR; out[i] = Math.sin(ph) * Math.exp(-decay * t) + 0.15 * (r() * 2 - 1) * Math.exp(-60 * t); }
  return onepoleLP(out, 600);
}
const mix = (...parts) => { const n = Math.max(...parts.map(([x]) => x.length)), o = new Float64Array(n);
  for (const [x, g = 1, at = 0] of parts) { const d = Math.round(at * SR); for (let i = 0; i < x.length && i + d < n; i++) o[i + d] += g * x[i]; } return o; };
const env = (pts) => (u) => { for (let i = 1; i < pts.length; i++) if (u <= pts[i][0]) { const [a, va] = pts[i - 1], [b, vb] = pts[i]; return va + (vb - va) * (u - a) / (b - a || 1); } return pts[pts.length - 1][1]; };
const bell = (c, w) => (u) => Math.exp(-(((u - c) / w) ** 2));

// ---------- the library: name → [seconds, what it is, how it is made] ----------
const LIB = {
  'paper-fold': [0.32, 'a crease pressed flat: a short dense crackle over a soft press', () => mix(
    [crackle(0.32, { rate: env([[0, 400], [0.15, 2600], [0.5, 900], [1, 40]]), size: env([[0, 0.4], [0.2, 1], [1, 0.3]]), band: () => 4200, seed: 11 }), 1],
    [body(0.25, { f0: 220, f1: 120, decay: 30, seed: 12 }), 0.25, 0.04])],
  'paper-unfold': [0.6, 'a folded sheet opening: sparse crackle rising, a little air', () => mix(
    [crackle(0.6, { rate: env([[0, 60], [0.6, 700], [1, 120]]), size: env([[0, 0.5], [0.7, 1], [1, 0.4]]), band: () => 3500, seed: 21 }), 0.9],
    [air(0.6, { f: env([[0, 900], [1, 2200]]), env: env([[0, 0], [0.5, 0.12], [1, 0]]), seed: 22 }), 1])],
  'paper-crinkle': [0.85, 'a sheet handled and crinkled: medium crackle that comes and goes', () =>
    crackle(0.85, { rate: (u) => 300 + 1500 * (0.5 + 0.5 * Math.sin(u * 19)) * env([[0, 0.3], [0.2, 1], [0.8, 1], [1, 0]])(u), size: () => 0.8, band: (u) => 3800 + 1400 * Math.sin(u * 7), seed: 31 })],
  'paper-crumple': [1.2, 'a sheet balled up in a fist: long, coarse, dense, lower', () => mix(
    [crackle(1.2, { rate: env([[0, 500], [0.3, 4200], [0.7, 3000], [1, 150]]), size: env([[0, 0.6], [0.4, 1], [1, 0.5]]), band: env([[0, 3200], [1, 2200]]), grain: 0.004, q: 1.1, seed: 41 }), 1],
    [air(1.2, { f: () => 700, env: env([[0, 0], [0.3, 0.1], [1, 0]]), seed: 42 }), 1])],
  'paper-tear-fast': [0.42, 'a fast rip: a run of fractures sliding down in pitch', () => mix(
    [crackle(0.42, { rate: env([[0, 900], [0.1, 9000], [0.8, 7000], [1, 300]]), size: env([[0, 0.5], [0.15, 1], [0.85, 0.9], [1, 0.2]]), band: env([[0, 6500], [1, 2600]]), grain: 0.0018, seed: 51 }), 1],
    [air(0.42, { f: env([[0, 3000], [1, 1500]]), env: env([[0, 0], [0.1, 0.15], [0.8, 0.12], [1, 0]]), seed: 52 }), 1])],
  'paper-tear-slow': [1.3, 'a slow tear: fibres giving in bursts', () =>
    crackle(1.3, { rate: (u) => 200 + 5000 * Math.max(0, Math.sin(u * 23)) ** 3 * env([[0, 0.4], [0.2, 1], [0.9, 1], [1, 0.1]])(u), size: () => 0.9, band: env([[0, 5200], [1, 3000]]), grain: 0.002, seed: 61 })],
  'paper-flutter': [0.75, 'a loose sheet flapping in the air', () =>
    air(0.75, { f: (u) => 900 + 500 * Math.sin(u * 60), env: (u) => (0.35 + 0.65 * Math.max(0, Math.sin(u * 2 * Math.PI * 9))) * env([[0, 0], [0.1, 1], [0.8, 0.8], [1, 0]])(u), q: 0.7, seed: 71 })],
  'paper-slash': [0.5, 'a paper blade cutting the air: a swish with a dry crackle edge, loudest at 0.16 s', () => mix(
    [air(0.5, { f: env([[0, 700], [0.32, 3600], [1, 1200]]), env: (u) => bell(0.32, 0.2)(u) * 0.9, seed: 81 }), 1],
    [crackle(0.5, { rate: (u) => 200 + 2500 * bell(0.32, 0.12)(u), size: () => 0.5, band: () => 6000, seed: 82 }), 0.7])],
  'paper-slide': [0.9, 'sheet over sheet: a smooth soft hiss', () =>
    air(0.9, { f: env([[0, 3800], [1, 3200]]), env: (u) => env([[0, 0], [0.15, 0.6], [0.85, 0.55], [1, 0]])(u) * (0.8 + 0.2 * Math.sin(u * 40)), q: 0.6, seed: 91 })],
  'paper-thump': [0.45, 'a folded paper body struck hard: a low card thump and a crackle of shards', () => mix(
    [body(0.45, { f0: 160, f1: 70, decay: 14, seed: 101 }), 1],
    [crackle(0.3, { rate: env([[0, 6000], [0.3, 1200], [1, 30]]), size: env([[0, 1], [1, 0.2]]), band: () => 3000, seed: 102 }), 0.5, 0.005])],
  'paper-tap': [0.22, 'a light knock on folded card', () => mix(
    [bandpass(body(0.22, { f0: 900, f1: 700, decay: 40, seed: 111 }).map((v) => v * 3), 850, 4), 1],
    [crackle(0.08, { rate: env([[0, 3000], [1, 100]]), size: () => 0.6, band: () => 5000, seed: 112 }), 0.4])],
  'paper-shred': [0.7, 'paper shards bursting apart: many tiny crackles thinning out', () =>
    crackle(0.7, { rate: env([[0, 8000], [0.15, 5000], [1, 50]]), size: env([[0, 1], [0.3, 0.6], [1, 0.15]]), band: (u) => 5500 - 2000 * u, grain: 0.0015, seed: 121 })],
};

function writeWav(file, x) {
  let pk = 0; for (const v of x) pk = Math.max(pk, Math.abs(v));
  const g = pk ? 10 ** (-1 / 20) / pk : 1, n = x.length, b = Buffer.alloc(44 + n * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + n * 2, 4); b.write('WAVEfmt ', 8); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(SR, 24); b.writeUInt32LE(SR * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(n * 2, 40);
  const fade = Math.round(0.004 * SR);
  for (let i = 0; i < n; i++) { const f = Math.min(1, (n - 1 - i) / fade); b.writeInt16LE(Math.round(clamp(x[i] * g * f, -1, 1) * 32767), 44 + i * 2); }
  fs.writeFileSync(file, b);
}

if (process.argv.includes('--list')) { for (const [k, [d, what]] of Object.entries(LIB)) console.log(`${k.padEnd(16)} ${d}s  ${what}`); process.exit(0); }
fs.mkdirSync(OUT, { recursive: true });
const credits = JSON.parse(fs.readFileSync(CREDITS, 'utf8'));
const tmp = path.join(OUT, '_tmp.wav');
for (const [name, [, what, make]] of Object.entries(LIB)) {
  const x = make(), mp3 = path.join(OUT, `${name}.mp3`);
  // light high-pass so no DC or sub rumble rides along, then the same format as the rest of assets/sfx
  writeWav(tmp, onepoleHP(x, 60));
  const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', tmp, '-ac', '2', '-ar', String(SR), '-b:a', '192k', '-map_metadata', '-1', '-fflags', '+bitexact', mp3]);
  if (r.status !== 0) throw new Error(`ffmpeg failed on ${name}: ${r.stderr}`);
  credits[`paper/${name}`] = { title: name, note: what, creator: 'Paper Cinema (synthesised in code, tools/paper_sfx.mjs)', license: 'own', source: 'synth', library: 'PaperAcoustics' };
  console.log(`✓ ${mp3}  ${what}`);
}
fs.rmSync(tmp, { force: true });
if (WRITE_CREDITS) fs.writeFileSync(CREDITS, JSON.stringify(credits, null, 2));
console.log(`${Object.keys(LIB).length} paper sounds. Next: node tools/sonic.mjs scan`);

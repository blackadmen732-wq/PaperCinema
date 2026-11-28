#!/usr/bin/env node
// SONIC benchmark: the same fight sound-tracked three ways, measured. Results → docs/SONIC-BENCHMARK.md.
//   node tools/sonic_bench.mjs [--film film/kuroko-duel.json] [--write]
//
// 1. HEAD   engine/sound.mjs as it was before SONIC (the commit before engine/sonic.mjs was added, or --base <rev>)
// 2. OFF    today's engine/sound.mjs, SONIC off          → must be bit-identical to HEAD
// 3. SONIC  today's engine/sound.mjs --sonic
// for two whoosh set-ups: the film's own (Earshot bank whooshes) and a plain one (whoosh-a/b/c files, as
// film/sword-mocap.json uses). The fight's events come from a FIXTURE in the exact format engine/combat.js and
// engine/groundfx.js write, because producing real ones needs headless Chromium (engine/render.mjs).
// Also measures: catalog scan (cold and cached), a query, and what an agent must read to answer
// "a heavy steel impact under 0.5 s" with and without the catalog.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import { scan, loadCatalog, query, brief } from '../engine/sonic.mjs';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const filmPath = opt('film', 'film/kuroko-duel.json');
// HEAD = the commit before SONIC was added (or HEAD itself while SONIC is not committed yet)
const added = execFileSync('git', ['log', '--diff-filter=A', '--format=%H', '--', 'engine/sonic.mjs'], { encoding: 'utf8' }).trim().split('\n').filter(Boolean).pop();
const BASE = opt('base', added ? `${added}~1` : 'HEAD');
const D = 'output/sonic-bench';
fs.mkdirSync(D, { recursive: true });
const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
const dB = (x) => 10 ** (x / 20);
const r3 = (x) => +(+x).toFixed(3);

// ---------- the fixture fight (combat.js / groundfx.js cue formulas, fixed numbers) ----------
const contacts = [[5.2, 0.25], [6.1, 0.55], [7.4, 0.82], [8.0, 0.35], [9.3, 0.95], [10.4, 0.15], [11.45, 0.62]];
const whooshes = [['A', 4.9, 12.5], ['B', 5.85, 18.0], ['A', 7.1, 26.0], ['B', 7.75, 14.0], ['A', 9.0, 29.0], ['B', 10.1, 10.5], ['A', 11.2, 21.0], ['B', 12.4, 16.5]];
const cues = [];
whooshes.forEach(([who, peak, v], n) => { const k = Math.max(0, Math.min(1, (v - 9) / 21));
  cues.push({ id: `auto-whoosh-${who}-${n}`, sfx: ['whoosh-a', 'whoosh-b', 'whoosh-c'][n % 3], t: r3(peak - 0.06), len: 0.6, gain: r3(dB(Math.min(-12, -18 + 8 * k))),
    rate: r3(0.85 + 0.5 * k), why: `${who} tip ${v.toFixed(1)} m/s`, event: { kind: 'whoosh', who, speed: v, peakAt: peak } }); });
contacts.forEach(([t, I], i) => cues.push({ id: `auto-clash-${i}`, sfx: I >= 0.4 ? 'clash-steel' : 'clash-light', t, len: 1.6, gain: r3(dB(-6 + 6 * I)), rate: 1,
  why: `blade contact, intensity ${I}`, event: { kind: 'clash', material: 'steel', intensity: I, speed: 4 + 10 * I, peakAt: t } }));
cues.push({ id: 'auto-scrape-90', sfx: 'steel-scrape', t: 9.35, len: 0.5, gain: r3(dB(-16)), why: 'blades sliding 0.50 s', event: { kind: 'scrape', material: 'steel', dur: 0.5 } });
for (const [kind, sfx, t, g, len, extra] of [['dash', 'dash-burst', 4.4, -7, 0.7, { speed: 8.5 }], ['skid', 'skid-dust', 4.95, -11, 0.8, { speed: 6.2 }],
  ['takeoff', 'jump-push', 12.8, -12, 0.4, { speed: 4.1 }], ['land', 'land-thud', 13.35, -5, 0.9, { speed: 3.0, height: 0.9 }]]) {
  cues.push({ id: `auto-${kind}-A-${cues.length}`, sfx, t: r3(t - (kind === 'dash' ? 0.03 : 0)), len, gain: r3(dB(g)), rate: 1, why: `A ${kind} (${extra.speed} m/s)`, event: { kind, who: 'A', peakAt: t, ...extra } });
}
cues.sort((a, b) => a.t - b.t);
const events = { cues, contacts: contacts.map(([t, intensity]) => ({ t, tb: t, intensity })), stops: [], impacts: [] };
fs.writeFileSync(`${D}/fight.events.json`, JSON.stringify(events, null, 1));

// ---------- films: as authored (Earshot whooshes) and plain (whoosh files) ----------
const plain = JSON.parse(JSON.stringify(film)); delete plain.autoSounds.whoosh.earshot;
fs.writeFileSync(`${D}/fight.json`, JSON.stringify(film));
fs.writeFileSync(`${D}/fight-plain.json`, JSON.stringify(plain));
const video = `${D}/black.mp4`;
if (!fs.existsSync(video)) execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', `color=black:s=180x320:r=24:d=${film.duration}`, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', video]);
fs.writeFileSync(`${D}/sound-head.mjs`, execFileSync('git', ['show', `${BASE}:engine/sound.mjs`]));

const pcmHash = (f) => crypto.createHash('md5').update(spawnSync('ffmpeg', ['-v', 'error', '-i', f, '-map', '0:a', '-f', 's16le', '-'], { maxBuffer: 1 << 28 }).stdout).digest('hex');
function run(script, filmFile, tag, extra = []) {
  const out = `${D}/${tag}.mp4`, t0 = process.hrtime.bigint();
  const r = spawnSync('node', [script, '--film', filmFile, '--video', video, '--events', `${D}/fight.events.json`, '--out', out, ...extra], { encoding: 'utf8' });
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  if (r.status !== 0) throw new Error(`${tag}: ${r.stderr || r.stdout}`);
  const lv = r.stdout.match(/level pass 2: .*?measures (-?[\d.]+) LUFS, true peak (-?[\d.]+)/);
  return { tag, ms: Math.round(ms), hash: pcmHash(out), lufs: lv ? +lv[1] : null, tp: lv ? +lv[2] : null, log: r.stdout };
}

// ---------- catalog: cold, cached, query ----------
const coldCat = `${D}/cold.catalog.json`;
const cold = scan({ catalog: coldCat, fresh: true }).stats;
const warm = scan({ catalog: coldCat }).stats;
fs.rmSync(coldCat);
scan({});                                     // the real catalog, refreshed
const cat = loadCatalog();
const byId = Object.fromEntries(cat.sounds.map((s) => [s.id, s]));
const esFile = (id) => `earshot/${id.replace(/[^a-z0-9.-]+/gi, '_')}-0.6-0.2`;
let t0 = process.hrtime.bigint();
const qText = spawnSync('node', ['tools/sonic.mjs', 'query', 'material=steel', 'action=impact', 'size=heavy', 'dur<0.5'], { encoding: 'utf8' }).stdout;
const qMs = Number(process.hrtime.bigint() - t0) / 1e6;
const qText2 = spawnSync('node', ['tools/sonic.mjs', 'query', 'material=steel', 'action=impact', 'dur<2', '--sort', 'weight', '--limit', '3'], { encoding: 'utf8' }).stdout;
// without the catalog an agent lists the folder, reads credits.json to learn what each file is, and measures the
// candidates with ffmpeg (the same volumedetect call engine/sound.mjs uses) to know durations and loudness
const lsText = fs.readdirSync('assets/sfx').join('\n');
const creditsText = fs.readFileSync('assets/sfx/credits.json', 'utf8');
const mp3 = fs.readdirSync('assets/sfx').filter((f) => /\.mp3$/.test(f));
const probe = mp3.map((f) => spawnSync('bash', ['-c', `ffmpeg -hide_banner -i "assets/sfx/${f}" -af volumedetect -f null - 2>&1`], { encoding: 'utf8' }).stdout).join('');
const tok = (s) => Math.round(s.length / 4);

// ---------- the three runs, two set-ups ----------
const runs = {};
for (const [name, ff] of [['earshot', `${D}/fight.json`], ['plain', `${D}/fight-plain.json`]]) {
  runs[name] = { head: run(`${D}/sound-head.mjs`, ff, `${name}-head`), off: run('engine/sound.mjs', ff, `${name}-off`), sonic: run('engine/sound.mjs', ff, `${name}-sonic`, ['--sonic']) };
  const base = path.basename(ff, '.json');
  runs[name].report = JSON.parse(fs.readFileSync(`output/${base}.sonic.json`, 'utf8'));
}

// ---------- what each run actually played, and how well it fits the fight ----------
function played(name, mode) {
  const ES = name === 'earshot' ? film.autoSounds.whoosh.earshot : null;
  const rep = Object.fromEntries(runs[name].report.map((r) => [r.id, r]));
  let n = 0;
  return cues.map((c) => {
    if (mode === 'sonic' && rep[c.id]) return { c, s: byId[rep[c.id].now], t: rep[c.id].t, rate: c.rate ?? 1 };
    if (ES && /^auto-whoosh/.test(c.id)) { const s = byId[esFile(ES[n++ % ES.length])]; return { c, s, t: c.t + 0.06 - 0.2, rate: 1 }; }
    return { c, s: byId[c.sfx], t: c.t, rate: c.rate ?? 1 };
  });
}
const pearson = (xs, ys) => { const n = xs.length, mx = xs.reduce((a, b) => a + b) / n, my = ys.reduce((a, b) => a + b) / n;
  let a = 0, b = 0, c = 0; for (let i = 0; i < n; i++) { a += (xs[i] - mx) * (ys[i] - my); b += (xs[i] - mx) ** 2; c += (ys[i] - my) ** 2; } return b && c ? a / Math.sqrt(b * c) : 0; };
function score(name, mode) {
  const P = played(name, mode);
  const of = (k) => P.filter((p) => p.c.event.kind === k);
  const align = P.filter((p) => ['whoosh', 'clash', 'dash', 'land'].includes(p.c.event.kind)).map((p) => Math.abs(p.t + p.s.m.peakT / p.rate - p.c.event.peakAt) * 1000);
  const wh = of('whoosh'), cl = of('clash');
  let repeats = 0; for (let i = 1; i < wh.length; i++) if (wh[i].s.id === wh[i - 1].s.id && wh[i].c.event.peakAt - wh[i - 1].c.event.peakAt < 1.5) repeats++;
  return {
    alignMeanMs: +(align.reduce((a, b) => a + b, 0) / align.length).toFixed(1), alignMaxMs: +Math.max(...align).toFixed(0),
    clashR: +pearson(cl.map((p) => p.c.event.intensity), cl.map((p) => p.s.m.intensity)).toFixed(2),
    clashWeightR: +pearson(cl.map((p) => p.c.event.intensity), cl.map((p) => p.s.m.weight)).toFixed(2),
    whooshR: +pearson(wh.map((p) => p.c.event.speed), wh.map((p) => p.s.m.intensity)).toFixed(2),
    distinct: { whoosh: new Set(wh.map((p) => p.s.id)).size, clash: new Set(cl.map((p) => p.s.id)).size },
    repeats,
  };
}
// measurement check: Earshot renders put their apex at 0.2 s by construction; the analyzer should find it
const apexCheck = cat.sounds.filter((s) => /-0\.2$/.test(s.id)).map((s) => `${s.id.replace('earshot/', '')} ${s.m.peakT}s`);

const R = { base: BASE.slice(0, 7), cold, warm, qMs: Math.round(qMs), qText, qText2,
  agent: { without: { calls: 2 + mp3.length, tokens: tok(lsText) + tok(creditsText) + tok(probe) }, with: { calls: 1, tokens: tok(qText2) } },
  runs: Object.fromEntries(Object.entries(runs).map(([k, v]) => [k, { head: { ms: v.head.ms, hash: v.head.hash, lufs: v.head.lufs, tp: v.head.tp }, off: { ms: v.off.ms, hash: v.off.hash, lufs: v.off.lufs, tp: v.off.tp },
    sonic: { ms: v.sonic.ms, lufs: v.sonic.lufs, tp: v.sonic.tp }, identical: v.head.hash === v.off.hash, before: score(k, 'head'), after: score(k, 'sonic'), picks: v.report }])),
  apexCheck };
fs.writeFileSync(`${D}/results.json`, JSON.stringify(R, null, 1));
console.log(JSON.stringify({ ...R, runs: Object.fromEntries(Object.entries(R.runs).map(([k, v]) => [k, { ...v, picks: v.picks.length }])) }, null, 1));

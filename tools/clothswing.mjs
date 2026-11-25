#!/usr/bin/env node
// CLOTH SWING: how far each sleeve streams away from vertical, at any moment of a film.
//   node tools/clothswing.mjs film/motion-test.json                 # a few sampled moments
//   node tools/clothswing.mjs film/motion-test.json --at 1.5,3.17   # exactly these times
//   node tools/clothswing.mjs film/motion-test.json --json
//
// A sleeve hangs straight down when the arm is still and trails when it swings (engine/figure.js,
// clothDrag). This measures that: 0 deg is hanging dead vertical, larger is flung further out.
// Rough reading: under ~15 deg is at rest, 30-50 is a committed swing, past ~60 is a hard strike.
//
// Why a tool and not an eye test: at full-body framing a sleeve is a few dozen pixels, so "did the
// cloth move" is not answerable from a still. The number is.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import { serve } from '../engine/serve.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const filmPath = args.find((a) => !a.startsWith('--'));
if (!filmPath) { console.error('usage: node tools/clothswing.mjs film/<name>.json [--at 1.5,3.2] [--json]'); process.exit(1); }
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
const dur = film.duration ?? 8;
const times = opt('at') ? opt('at').split(',').map(Number)
  : Array.from({ length: 9 }, (_, i) => +(dur * i / 8).toFixed(2));

const server = await serve(0);
const port = server.address().port;
const browser = await chromium.launch();
const page = await browser.newPage();
const tilt = (s) => +(Math.acos(Math.max(-1, Math.min(1, -s[1]))) * 180 / Math.PI).toFixed(1);
const measure = async (nodrag) => {
  await page.goto(`http://localhost:${port}/${film.page ?? 'engine/motion.html'}?render=1&film=/${filmPath}${nodrag ? '&nodrag=1' : ''}`);
  await page.waitForFunction('window.READY === true', null, { timeout: 600000 });
  const out = {};
  for (const t of times) {
    const p = await page.evaluate((tt) => window.probe(tt), t);
    for (const [id, v] of Object.entries(p)) {
      if (!v?.sleeves?.length) continue;
      out[`${t}|${id}`] = v.sleeves.map(tilt);
    }
  }
  return out;
};
const off = await measure(true);
const on = await measure(false);
const rows = Object.keys(on).map((k) => {
  const [t, who] = k.split('|');
  return { t: Number(t), who, deg: on[k], base: off[k] ?? on[k] };
});
await browser.close();
server.close();

if (args.includes('--json')) { console.log(JSON.stringify(rows, null, 1)); process.exit(0); }
console.log(`cloth swing · ${filmPath} · degrees off vertical, drag ON (and the change drag made)`);
console.log('  A raised arm already carries its sleeve away from vertical, so the bracketed number');
console.log('  is what the DRAG added: the same film measured again with ?nodrag=1, subtracted.');
const who = [...new Set(rows.map((r) => r.who))];
console.log(`  ${'time'.padEnd(7)}${who.map((w) => (w + ' R/L').padEnd(16)).join('')}`);
for (const t of times) {
  const cells = who.map((w) => {
    const r = rows.find((x) => x.t === t && x.who === w);
    if (!r) return '-'.padEnd(26);
    const d = r.deg.map((v, i) => `${v}${v - r.base[i] >= 0 ? '+' : ''}${(v - r.base[i]).toFixed(0)}`);
    return d.join(' / ').padEnd(26);
  });
  console.log(`  ${String(t).padEnd(7)}${cells.join('')}`);
}
const added = rows.flatMap((r) => r.deg.map((v, i) => Math.abs(v - r.base[i])));
const peak = Math.max(...added);
console.log(`\n  drag moves a sleeve by up to ${peak.toFixed(1)} deg` +
  (peak < 3 ? '  ← that is nothing; the drag is not reaching the cloth' : ''));

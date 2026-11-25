#!/usr/bin/env node
// JITTER: measure the tremble in a skeleton, per joint, in numbers.
//
//   node tools/jitter.mjs <film>            # one film
//   node tools/jitter.mjs --all             # every timeline in output/
//
// "It keeps shaking" is a real complaint and an unmeasurable one, so this measures it. Tremble is
// high-frequency ACCELERATION: a joint that moves smoothly has a position curve whose second
// difference is small and consistent; a joint that trembles has one that flips sign every frame.
// Both look the same if you only measure speed, which is why speed is the wrong number.
//
//   jerk      metres per frame^3 - how fast the acceleration itself is changing
//   flips     share of frames where the acceleration reverses direction. THE tell. Real motion
//             reverses a few times a second; noise reverses every other frame, so a flip rate near
//             0.5 is a joint being shaken rather than moved.
//
// A joint is called SHAKY when it flips more than 35% of its frames while actually moving. Report
// it, fix it, run it again: the number has to come down or the fix did nothing.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const args = process.argv.slice(2);
const FLIP_BAD = Number(args.includes('--flip') ? args[args.indexOf('--flip') + 1] : 0.35);
const MOVING = 0.0015;            // metres/frame: below this a joint is still, and noise is not tremble

function analyse(file) {
  const tl = JSON.parse(fs.readFileSync(file, 'utf8'));
  const order = tl.bones?.order;
  const frames = tl.frames ?? [];
  if (!order || frames.length < 5) return null;
  const out = [];
  for (const meta of tl.actors ?? []) {
    const aid = meta.id;
    if (meta.hidden) continue;
    // positions[j][f] = [x, y, z] of joint j at frame f
    const P = order.map(() => []);
    for (const fr of frames) {
      const a = (fr.actors ?? {})[aid];
      if (!a?.bones) continue;
      order.forEach((_, j) => P[j].push(a.bones[j].slice(0, 3)));
    }
    if (!P[0].length) continue;
    for (let j = 0; j < order.length; j++) {
      const p = P[j];
      const n = p.length;
      if (n < 5) continue;
      let flips = 0, counted = 0, jerk = 0, speed = 0;
      let prevAcc = null;
      for (let f = 2; f < n; f++) {
        const v1 = [0, 1, 2].map((k) => p[f][k] - p[f - 1][k]);
        const v0 = [0, 1, 2].map((k) => p[f - 1][k] - p[f - 2][k]);
        const acc = [0, 1, 2].map((k) => v1[k] - v0[k]);
        const sp = Math.hypot(...v1);
        speed += sp;
        if (sp < MOVING) { prevAcc = acc; continue; }   // standing still: not tremble
        counted++;
        if (prevAcc) {
          const dot = acc[0] * prevAcc[0] + acc[1] * prevAcc[1] + acc[2] * prevAcc[2];
          if (dot < 0) flips++;
          jerk += Math.hypot(acc[0] - prevAcc[0], acc[1] - prevAcc[1], acc[2] - prevAcc[2]);
        }
        prevAcc = acc;
      }
      if (counted < 8) continue;
      out.push({ actor: aid, joint: order[j], flip: flips / counted,
                 jerk: jerk / counted, speed: speed / (n - 1), frames: counted });
    }
  }
  return out;
}

const files = args.includes('--all')
  ? fs.readdirSync(`${ROOT}/output`).filter((f) => f.endsWith('.timeline.json')).map((f) => `${ROOT}/output/${f}`)
  : args.filter((a) => !a.startsWith('--')).map((a) => (a.endsWith('.json') ? a : `${ROOT}/output/${a}.timeline.json`));
if (!files.length) { console.error('usage: node tools/jitter.mjs <film> | --all'); process.exit(2); }

let worstAll = null, shakyTotal = 0;
for (const f of files) {
  const rows = analyse(f);
  if (!rows?.length) { console.log(`  ${path.basename(f)}: no bone data`); continue; }
  rows.sort((a, b) => b.flip - a.flip);
  const shaky = rows.filter((r) => r.flip > FLIP_BAD);
  shakyTotal += shaky.length;
  const avg = rows.reduce((s, r) => s + r.flip, 0) / rows.length;
  console.log(`\n${path.basename(f).replace('.timeline.json', '')}  ·  ${rows.length} joint tracks  ·  mean flip ${(avg * 100).toFixed(0)}%`);
  for (const r of rows.slice(0, 6)) {
    const mark = r.flip > FLIP_BAD ? 'SHAKY' : '     ';
    console.log(`  ${mark} ${r.actor.padEnd(7)} ${r.joint.padEnd(12)} flip ${(r.flip * 100).toFixed(0).padStart(3)}%   `
      + `jerk ${(r.jerk * 1000).toFixed(2).padStart(6)} mm/f³   speed ${(r.speed * 1000).toFixed(1).padStart(5)} mm/f`);
  }
  if (shaky.length > 6) console.log(`  … ${shaky.length} shaky joints in total`);
  if (!worstAll || rows[0].flip > worstAll.flip) worstAll = { ...rows[0], film: path.basename(f) };
}
console.log(`\n${shakyTotal} joint track(s) over ${FLIP_BAD * 100}% flip`
  + (worstAll ? ` · worst ${worstAll.joint} of ${worstAll.actor} at ${(worstAll.flip * 100).toFixed(0)}% in ${worstAll.film.replace('.timeline.json', '')}` : ''));
process.exit(shakyTotal ? 1 : 0);

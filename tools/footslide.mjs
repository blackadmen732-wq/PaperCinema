// FOOT SLIDE: measure how far a "planted" foot slides across the ground, without rendering anything.
//   node tools/footslide.mjs film/dash-test.json            # every performer
//   node tools/footslide.mjs film/dash-test.json --who hero --fps 24 --json
//
// Same definition as the studio audit's rule A1 (tools/audit.mjs, docs/AUDIT.md), but it poses the
// real rig in Node (three.js, the leg IK included, like tools/mocap_truth.mjs) instead of measuring a
// rendered page, so it runs in a second and can be used while tuning engine/footlock.js.
//
// A foot counts as PLANTED on a frame when the root is on the ground (y ≤ 0.03 m) and the foot joint
// is low (y ≤ 0.12 m). Slide = the horizontal distance that planted foot travels between two frames.
// Reported: total slide over the film, the peak speed, and the worst run (the audit flags a run of
// frames over 1 m/s that adds up to more than 0.4 m).
import fs from 'node:fs';

const ctx = new Proxy({}, { get: (_, k) => (k === 'getImageData' ? (x, y, w, h) => ({ data: new Uint8ClampedArray(w * h * 4) })
  : k === 'createLinearGradient' || k === 'createRadialGradient' ? () => ({ addColorStop() {} }) : k === 'measureText' ? () => ({ width: 1 }) : () => {}), set: () => true });
globalThis.document = { createElement: () => ({ width: 1, height: 1, getContext: () => ctx, style: {} }) };

const THREE = await import('three');
const { makeFigure, applyPose, makeMotion, resolveKeys } = await import('../engine/figure.js');
const { lockFeet } = await import('../engine/footlock.js');
const { expandMoves } = await import('../engine/moves.js');

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const film = JSON.parse(fs.readFileSync(args[0], 'utf8'));
const POSES = JSON.parse(fs.readFileSync('library/poses.json', 'utf8'));
const MOVES = JSON.parse(fs.readFileSync('library/moves.json', 'utf8'));
const FPS = Number(opt('fps', film.fps ?? 24)), DUR = film.duration, DT = 1 / FPS;
const SPEED = 1.0, DIST = 0.4;                         // the audit's thresholds (RULE.slideSpeed / slideDist)

const who = opt('who', null);
const rows = [];
for (const [id, c] of Object.entries(film.cast)) {
  if ((who && id !== who) || c.hidden) continue;
  const perf = film.performances[id];
  if (!perf?.keys) continue;
  const fig = makeFigure({});
  let motion = makeMotion(resolveKeys(expandMoves(perf.keys, MOVES), POSES), film.motion ?? {});
  if (film.motion?.lockFeet) motion = lockFeet(motion, DUR, film.motion.lockFeet);
  const v = new THREE.Vector3();
  const foot = (p, side) => { applyPose(fig, p); fig.root.updateMatrixWorld(true);
    return fig.legs[side].foot.getWorldPosition(v).clone(); };
  const r = { id, feet: {} };
  for (const side of ['r', 'l']) {
    let prev = null, total = 0, peak = 0, run = 0, worstRun = 0, worstAt = 0, planted = 0;
    for (let i = 0; i <= Math.round(DUR * FPS); i++) {
      const t = i * DT, p = motion(t), f = foot(p, side);
      const on = p.y <= 0.03 && f.y <= 0.12;
      if (on) planted++;
      if (on && prev) {
        const d = Math.hypot(f.x - prev.x, f.z - prev.z);
        if (d / DT > SPEED) { total += d; run += d; peak = Math.max(peak, d / DT); if (run > worstRun) { worstRun = run; worstAt = t; } }
        else run = 0;
      } else run = 0;
      prev = on ? f : null;
    }
    r.feet[side] = { totalSlide: +total.toFixed(3), peakSpeed: +peak.toFixed(2), worstRun: +worstRun.toFixed(3),
      worstAt: +worstAt.toFixed(2), plantedFrames: planted, flagged: worstRun > DIST };
  }
  rows.push(r);
}

if (args.includes('--json')) { console.log(JSON.stringify({ film: args[0], lockFeet: !!film.motion?.lockFeet, fps: FPS, rows }, null, 1)); }
else {
  console.log(`foot slide · ${args[0]} · ${FPS} fps · lockFeet ${film.motion?.lockFeet ? 'ON' : 'off'}`);
  for (const r of rows) for (const [side, f] of Object.entries(r.feet))
    console.log(`  ${r.id} ${side === 'r' ? 'right' : 'left '} foot: ${f.totalSlide.toFixed(2)} m total, peak ${f.peakSpeed.toFixed(1)} m/s, ` +
      `worst run ${f.worstRun.toFixed(2)} m at ${f.worstAt.toFixed(2)} s, planted ${f.plantedFrames} frames` +
      (f.flagged ? '  ← the audit would flag this' : ''));
}

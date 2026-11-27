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
const { expandMoves, loadClipsSync } = await import('../engine/moves.js');

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const film = JSON.parse(fs.readFileSync(args[0], 'utf8'));
const POSES = JSON.parse(fs.readFileSync('library/poses.json', 'utf8'));
const MOVES = JSON.parse(fs.readFileSync('library/moves.json', 'utf8'));
const CLIPS = loadClipsSync(MOVES, (n) => JSON.parse(fs.readFileSync(`library/mocap/${n}.json`, 'utf8')));
const FPS = Number(opt('fps', film.fps ?? 24)), DUR = film.duration, DT = 1 / FPS;
const SPEED = 1.0, DIST = 0.4;                         // the audit's thresholds (RULE.slideSpeed / slideDist)

const who = opt('who', null);
const rows = [];
for (const [id, c] of Object.entries(film.cast)) {
  if ((who && id !== who) || c.hidden) continue;
  const perf = film.performances[id];
  if (!perf?.keys) continue;
  const fig = makeFigure({});
  let motion = makeMotion(resolveKeys(expandMoves(perf.keys, MOVES, CLIPS), POSES), film.motion ?? {});
  if (film.motion?.lockFeet) motion = lockFeet(motion, DUR, film.motion.lockFeet);
  const v = new THREE.Vector3();
  const foot = (p, side) => { applyPose(fig, p); fig.root.updateMatrixWorld(true);
    return fig.legs[side].foot.getWorldPosition(v).clone(); };
  const r = { id, feet: {} };
  // GAIT: a step is a swing between two plants with the body on the ground; two feet swinging at the same time while
  // walking is a hop (27 Nov: Musashi hopped through both of his walks). Leaps and lunges (the root in the air or
  // faster than a foot can push) are not counted.
  if (motion.plan) {
    const { contactsR: cR, contactsL: cL, rate, air } = motion.plan;
    // steps only: a gap between two plants with no airborne sample (the planner's own air: off the ground or faster
    // than a foot can push) and not across a cut
    const cutsT = motion.cuts || [];
    const across = (a, b) => cutsT.some(([, t]) => a / rate < t && b / rate >= t);
    const swings = (cs) => cs.slice(0, -1).map((c, k) => [c.b + 1, cs[k + 1].a - 1])
      .filter(([a, b]) => b >= a && !across(a - 1, b + 1) && !air.slice(a, b + 1).some(Boolean));
    const sR = swings(cR), sL = swings(cL);
    const hops = [];
    for (const [a, b] of sR) for (const [c, d] of sL) {
      const lo = Math.max(a, c), hi = Math.min(b, d);
      if (hi >= lo) hops.push(+(lo / rate).toFixed(2));
    }
    r.gait = { stepsR: sR.length, stepsL: sL.length, hops };
  }
  for (const side of ['r', 'l']) {
    let prev = null, total = 0, peak = 0, run = 0, worstRun = 0, worstAt = 0, planted = 0;
    for (let i = 0; i <= Math.round(DUR * FPS); i++) {
      const t = i * DT, p = motion(t), f = foot(p, side);
      const on = p.y <= 0.03 && f.y <= 0.12;
      if (on) planted++;
      // a cut (a teleport between two key pieces, engine/figure.js) is not a slide: the feet jump with the body
      if ((motion.cuts || []).some(([, b]) => (i - 1) * DT < b - 1e-6 && t >= b - 1e-6)) { prev = on ? f : null; run = 0; continue; }
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
  for (const r of rows) {
    for (const [side, f] of Object.entries(r.feet))
      console.log(`  ${r.id} ${side === 'r' ? 'right' : 'left '} foot: ${f.totalSlide.toFixed(2)} m total, peak ${f.peakSpeed.toFixed(1)} m/s, ` +
        `worst run ${f.worstRun.toFixed(2)} m at ${f.worstAt.toFixed(2)} s, planted ${f.plantedFrames} frames` +
        (f.flagged ? '  ← the audit would flag this' : ''));
    if (r.gait) console.log(`  ${r.id} gait: ${r.gait.stepsR} right + ${r.gait.stepsL} left steps, both feet off the ground ` +
      `together while walking: ${r.gait.hops.length}${r.gait.hops.length ? ' at ' + r.gait.hops.slice(0, 12).join(', ') + ' s  ← a hop, not a walk' : ''}`);
  }
}

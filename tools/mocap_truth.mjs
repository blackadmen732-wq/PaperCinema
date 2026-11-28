// Ground truth for the motion-capture tests (docs/MOCAP.md): poses one performer of a motion-page film
// exactly as engine/motion.js does (keys + moves + motion layer + breathing + eyes-on-opponent + two-hand IK),
// then writes, for every frame, the EFFECTIVE channels (the left arm read back after the IK) and the world
// positions of the joints a pose estimator sees.
//   node tools/mocap_truth.mjs film/mocap-synth.json --who hero --fps 24 --out output/mocap/synth-truth.json
// Pure Node: the paper textures need a canvas, so a tiny no-op canvas stands in for the DOM.
import fs from 'node:fs';
import path from 'node:path';

// ---- a no-op DOM canvas: paper.js only draws textures, which nothing reads here ----
const ctx = new Proxy({}, { get: (_, k) => (k === 'getImageData' ? (x, y, w, h) => ({ data: new Uint8ClampedArray(w * h * 4) })
  : k === 'createLinearGradient' || k === 'createRadialGradient' ? () => ({ addColorStop() {} }) : k === 'measureText' ? () => ({ width: 1 }) : () => {}), set: () => true });
globalThis.document = { createElement: () => ({ width: 1, height: 1, getContext: () => ctx, style: {} }) };

const THREE = await import('three');
const { makeFigure, holdInHand, applyPose, makeMotion, resolveKeys, windowWeight, solveArm, gripHand } = await import('../engine/figure.js');
const { expandMoves, loadClipsSync } = await import('../engine/moves.js');
const { lockFeet } = await import('../engine/footlock.js');
const { makeKatana } = await import('../engine/props.js');

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const filmPath = args[0];
const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
const who = opt('who', Object.keys(film.cast)[0]);
const fps = Number(opt('fps', film.fps));
const out = opt('out', `output/mocap/${path.basename(filmPath, '.json')}-truth.json`);
const POSES = JSON.parse(fs.readFileSync('library/poses.json', 'utf8'));
const MOVES = JSON.parse(fs.readFileSync('library/moves.json', 'utf8'));
const CLIPS = loadClipsSync(MOVES, (n) => JSON.parse(fs.readFileSync(`library/mocap/${n}.json`, 'utf8')));

const cast = {};
Object.keys(film.cast).forEach((id, i) => {
  const fig = makeFigure({});
  const k = makeKatana();
  holdInHand(fig.rH, k.sword, -0.06);
  const perf = film.performances[id];
  let motion = makeMotion(resolveKeys(expandMoves(perf.keys, MOVES, CLIPS), POSES), film.motion ?? {});
  if (film.motion?.lockFeet) motion = lockFeet(motion, film.duration, film.motion.lockFeet, perf.gait);   // keep in step with engine/motion.js
  cast[id] = { id, fig, sword: k.sword, perf, phase: i * 1.7, motion };
});
const ids = Object.keys(cast);
const other = (id) => cast[ids.find((x) => x !== id)] ?? cast[id];

// same as poseOf() in engine/motion.js (keep in step with it)
function poseOf(c, tb) {
  const p = c.motion(tb);
  p.cx += 0.012 * Math.sin(tb * 2 * Math.PI * 0.3 + c.phase);
  p.rwz += 0.006 * Math.sin(tb * 2 * Math.PI * 0.7 + c.phase);
  p.rwx += 0.006 * Math.cos(tb * 2 * Math.PI * 0.7 + c.phase);
  const o = other(c.id).motion(tb);
  let yaw = Math.atan2(o.x - p.x, o.z - p.z) - p.ry - p.ty - p.cy;
  yaw = Math.max(-0.7, Math.min(0.7, Math.atan2(Math.sin(yaw), Math.cos(yaw))));
  p.ny += 0.4 * yaw;
  p.hy += 0.6 * yaw;
  return p;
}
const _v = new THREE.Vector3();
const W = (o, x = 0, y = 0, z = 0) => o.localToWorld(new THREE.Vector3(x, y, z)).toArray().map((v) => +v.toFixed(4));
const frames = [];
const dur = film.duration;
for (let i = 0; i <= Math.round(dur * fps); i++) {
  const t = i / fps;
  const c = cast[who], f = c.fig;
  const p = poseOf(c, t);
  applyPose(f, p);
  c.sword.quaternion.identity();
  f.root.updateMatrixWorld(true);
  const w = windowWeight(c.perf.twoHand, t);
  if (w > 0) { solveArm(f, 'l', c.sword.localToWorld(_v.set(-0.27, -0.018, 0)).clone(), null, w); gripHand(f, 'l', c.sword, w); }
  f.root.updateMatrixWorld(true);
  // effective left arm: read the IK result back as Euler angles
  const e = new THREE.Euler().setFromQuaternion(f.lS.quaternion, 'XYZ');
  const ch = {};
  for (const [k, v] of Object.entries(p)) ch[k] = +v.toFixed(4);
  ch.lsx = +e.x.toFixed(4); ch.lsy = +e.y.toFixed(4); ch.lsz = +e.z.toFixed(4); ch.lex = +f.lE.rotation.x.toFixed(4);
  const L = f.legs;
  const joints = {
    head: W(f.head, 0, 0.1, 0), nose: W(f.head, 0, 0.1, 0.09), lear: W(f.head, 0.085, 0.1, 0), rear: W(f.head, -0.085, 0.1, 0),
    rshoulder: W(f.rS), lshoulder: W(f.lS), relbow: W(f.rE), lelbow: W(f.lE), rwrist: W(f.rH), lwrist: W(f.lH),
    rhip: W(L.r.thigh), lhip: W(L.l.thigh), rknee: W(L.r.shin), lknee: W(L.l.shin), rankle: W(L.r.foot), lankle: W(L.l.foot),
    rtoe: W(L.r.foot, 0, -0.03, 0.16), ltoe: W(L.l.foot, 0, -0.03, 0.16), hips: W(f.hips), chest: W(f.upper, 0, 0.21, 0),
    tip: W(c.sword, 0.9, 0, 0),
  };
  frames.push({ t: +t.toFixed(4), ch, joints });
}
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify({ film: filmPath, who, fps, frames }));
console.log(`truth: ${frames.length} frames of ${who} → ${out}`);

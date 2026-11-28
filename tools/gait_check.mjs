// GAIT CHECK: measure how a performer WALKS, against the textbook numbers of a human walk, without rendering.
//   node tools/gait_check.mjs film/walk-bench.json              # every performer, every walking stretch
//   node tools/gait_check.mjs film/ganryujima-ep1.json --who target --json
//
// Why (Mark, 28 Nov: "improve the leg movement ... the skeleton should be able to work with the movement much
// better"): tools/footslide.mjs proves a planted foot does not slide and that the feet alternate, but a walk can
// pass both and still look weak: quick snapping steps, flat feet that never roll, hips that only sink. This tool
// poses the real rig in Node (three.js, the leg IK and engine/footlock.js included, as footslide.mjs does) at 60 Hz
// and measures what a gait lab measures, from the geometry alone (heel and toe points on the sandal, the joints),
// so the same numbers can be taken from any motion: ours, a motion capture, a new gait.
//
// A WALKING STRETCH is a run of at least 1.2 s with the body on the ground travelling at 0.5 m/s or more (0.3 s
// trimmed off each end: starting and stopping are not the cycle). A foot is ON THE GROUND while the lower of its heel
// and toe points is within 1.5 cm of the ground; a strike is the first sample on the ground, a toe-off the first
// one off it.
//
// The reference ranges (REF, adult walking at about 1.0-1.5 m/s; legs ~0.9 m like this figure's 0.46 + 0.44):
// stance about 60 % of a stride and swing 40 %, the two double supports together about 20-25 %, cadence 100-120
// steps/min (Bipedal gait cycle, Wikipedia; Normal Gait, University of Missouri PM&R); swing knee flexion about 60
// degrees, loading-response flexion 15-20, the centre of mass rising and falling about 5 cm and swaying about 4-5 cm
// (the textbook values: Perry & Burnfield, Gait Analysis; Saunders, Inman & Eberhart 1953). A rigid paper sandal has
// no toe joint, so its toe-off pitch is judged against what a rigid foot can do (pivoting on the toe), not the
// 50-60 degrees of a real foot bending at the ball.
import fs from 'node:fs';

const ctx = new Proxy({}, { get: (_, k) => (k === 'getImageData' ? (x, y, w, h) => ({ data: new Uint8ClampedArray(w * h * 4) })
  : k === 'createLinearGradient' || k === 'createRadialGradient' ? () => ({ addColorStop() {} }) : k === 'measureText' ? () => ({ width: 1 }) : () => {}), set: () => true });
globalThis.document = { createElement: () => ({ width: 1, height: 1, getContext: () => ctx, style: {} }) };

const THREE = await import('three');
const { makeFigure, applyPose, makeMotion, resolveKeys } = await import('../engine/figure.js');
const { lockFeet } = await import('../engine/footlock.js');
const { expandMoves, loadClipsSync } = await import('../engine/moves.js');

export const REF = {
  cadence: [100, 125, 'steps/min'],
  stance: [0.57, 0.65, 'of a stride'],
  swingTime: [0.33, 0.48, 's'],
  doubleSupport: [0.16, 0.28, 'of the time'],
  stepLength: [0.55, 0.8, 'm'],
  pelvisBob: [0.025, 0.06, 'm p2p'],
  pelvisSway: [0.02, 0.06, 'm p2p'],
  kneeSwing: [50, 70, 'deg'],
  kneeLoad: [8, 25, 'deg'],
  pitchStrike: [8, 25, 'deg toe up'],
  pitchToeOff: [-45, -15, 'deg heel up'],
  clearance: [0.008, 0.05, 'm'],
};

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const film = JSON.parse(fs.readFileSync(args[0], 'utf8'));
const POSES = JSON.parse(fs.readFileSync('library/poses.json', 'utf8'));
const MOVES = JSON.parse(fs.readFileSync('library/moves.json', 'utf8'));
const CLIPS = loadClipsSync(MOVES, (n) => JSON.parse(fs.readFileSync(`library/mocap/${n}.json`, 'utf8')));
const HZ = 60, DT = 1 / HZ, DUR = film.duration, N = Math.round(DUR * HZ) + 1;
const who = opt('who', null);

// sandal points in the foot's own frame (engine/figure.js: the zori box is 0.25 long from z -0.065 to 0.185, its
// underside 0.051 below the ankle)
const HEEL = new THREE.Vector3(0, -0.051, -0.065), TOE = new THREE.Vector3(0, -0.051, 0.185);
const v3 = () => new THREE.Vector3();
const mean = (a) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : NaN);
const r2 = (x, k = 3) => (Number.isFinite(x) ? +x.toFixed(k) : null);

function sample(fig, motion) {
  const S = [];
  for (let i = 0; i < N; i++) {
    const t = i * DT, p = motion(t);
    applyPose(fig, p);
    fig.root.updateMatrixWorld(true);
    const leg = (s) => {
      const L = fig.legs[s];
      return { hip: L.thigh.getWorldPosition(v3()), knee: L.shin.getWorldPosition(v3()), ankle: L.foot.getWorldPosition(v3()),
        heel: L.foot.localToWorld(HEEL.clone()), toe: L.foot.localToWorld(TOE.clone()) };
    };
    S.push({ t, root: [p.x, p.y, p.z], hips: fig.hips.getWorldPosition(v3()), head: fig.head.getWorldPosition(v3()),
      sR: fig.rS.getWorldPosition(v3()), sL: fig.lS.getWorldPosition(v3()), hR: fig.rH.getWorldPosition(v3()),
      hL: fig.lH.getWorldPosition(v3()), r: leg('r'), l: leg('l') });
  }
  return S;
}

const knee = (L) => {                                   // flexion: 0 = straight
  const a = L.hip.clone().sub(L.knee).normalize(), b = L.ankle.clone().sub(L.knee).normalize();
  return 180 - Math.acos(Math.max(-1, Math.min(1, a.dot(b)))) * 180 / Math.PI;
};
const pitch = (L) => {                                  // + toe up
  const d = L.toe.clone().sub(L.heel);
  return Math.atan2(d.y, Math.hypot(d.x, d.z)) * 180 / Math.PI;
};
const low = (L) => Math.min(L.heel.y, L.toe.y);

function stretches(S, cuts) {
  const sp = S.map((s, i) => {
    const a = S[Math.max(0, i - 6)], b = S[Math.min(N - 1, i + 6)];
    return Math.hypot(b.root[0] - a.root[0], b.root[2] - a.root[2]) / (b.t - a.t || 1);
  });
  const ok = S.map((s, i) => sp[i] >= 0.5 && s.root[1] <= 0.03 && !cuts.some(([, b]) => Math.abs(s.t - b) < 0.35));
  const out = [];
  for (let i = 0; i < N;) {
    if (!ok[i]) { i++; continue; }
    let j = i; while (j + 1 < N && ok[j + 1]) j++;
    const a = i + Math.round(0.3 * HZ), b = j - Math.round(0.3 * HZ);
    if ((j - i) * DT >= 1.2 && b > a) out.push([a, b, mean(sp.slice(a, b + 1))]);
    i = j + 1;
  }
  return out;
}

function measure(S, a, b, speed) {
  const G = Math.min(...S.slice(a, b + 1).flatMap((s) => [low(s.r), low(s.l)]));
  const on = { r: [], l: [] };
  for (const side of ['r', 'l']) {
    for (let i = a; i <= b; i++) on[side].push(low(S[i][side]) <= G + 0.015);
    // debounce: a run shorter than 0.06 s takes the state around it
    const o = on[side], m = Math.round(0.06 * HZ);
    for (let i = 0; i < o.length;) { let j = i; while (j + 1 < o.length && o[j + 1] === o[i]) j++;
      if (j - i + 1 < m && i > 0 && j < o.length - 1) for (let k = i; k <= j; k++) o[k] = !o[i]; i = j + 1; }
  }
  const ev = {};
  for (const side of ['r', 'l']) {
    const o = on[side], st = [], off = [];
    for (let k = 1; k < o.length; k++) { if (o[k] && !o[k - 1]) st.push(a + k); if (!o[k] && o[k - 1]) off.push(a + k); }
    ev[side] = { st, off };
  }
  const strides = [], stance = [], swing = [], kSw = [], kLd = [], pS = [], pT = [], clr = [], bob = [], sway = [], arm = [];
  for (const side of ['r', 'l']) {
    const { st, off } = ev[side];
    for (let k = 0; k + 1 < st.length; k++) {
      const s0 = st[k], s1 = st[k + 1], o = off.find((x) => x > s0 && x < s1);
      if (o == null) continue;
      strides.push((s1 - s0) * DT); stance.push((o - s0) / (s1 - s0)); swing.push((s1 - o) * DT);
      let mk = 0; for (let i = o; i < s1; i++) mk = Math.max(mk, knee(S[i][side])); kSw.push(mk);
      let ml = 0; for (let i = s0; i < s0 + Math.round(0.3 * (o - s0)); i++) ml = Math.max(ml, knee(S[i][side])); kLd.push(ml);
      pS.push(pitch(S[s0][side]));
      let mt = 90; for (let i = s0 + Math.round(0.8 * (o - s0)); i <= Math.min(s1, o + Math.round(0.1 * HZ)); i++) mt = Math.min(mt, pitch(S[i][side]));
      pT.push(mt);
      let mc = 9; for (let i = o + Math.round(0.25 * (s1 - o)); i <= o + Math.round(0.75 * (s1 - o)); i++) mc = Math.min(mc, S[i][side].toe.y - G);
      clr.push(mc);
      if (side === 'r') {
        // hips: height p2p over the stride; sideways = off a straight line through the stride (the travel line)
        const H = S.slice(s0, s1 + 1).map((s) => s.hips);
        bob.push(Math.max(...H.map((h) => h.y)) - Math.min(...H.map((h) => h.y)));
        const A = H[0], B = H[H.length - 1], d = [B.x - A.x, B.z - A.z], L = Math.hypot(...d) || 1, n = [-d[1] / L, d[0] / L];
        const lat = H.map((h) => (h.x - A.x) * n[0] + (h.z - A.z) * n[1]);
        sway.push(Math.max(...lat) - Math.min(...lat));
        const fw = [d[0] / L, d[1] / L];
        const ah = S.slice(s0, s1 + 1).map((s) => (s.hR.x - s.sR.x) * fw[0] + (s.hR.z - s.sR.z) * fw[1]);
        arm.push(Math.max(...ah) - Math.min(...ah));
      }
    }
  }
  // cadence and step length from all strikes in time order
  const all = [...ev.r.st.map((i) => [i, 'r']), ...ev.l.st.map((i) => [i, 'l'])].sort((x, y) => x[0] - y[0]);
  const steps = [];
  for (let k = 1; k < all.length; k++) if (all[k][1] !== all[k - 1][1]) {
    const A = S[all[k - 1][0]][all[k - 1][1]].ankle, B = S[all[k][0]][all[k][1]].ankle;
    steps.push(Math.hypot(B.x - A.x, B.z - A.z));
  }
  const cad = all.length > 1 ? 60 * (all.length - 1) / ((all[all.length - 1][0] - all[0][0]) * DT) : NaN;
  let both = 0; for (let k = 0; k < on.r.length; k++) if (on.r[k] && on.l[k]) both++;
  return {
    from: r2(S[a].t, 2), to: r2(S[b].t, 2), speed: r2(speed, 2), strikes: all.length,
    cadence: r2(cad, 0), stance: r2(mean(stance), 2), swingTime: r2(mean(swing), 2), doubleSupport: r2(both / on.r.length, 2),
    stepLength: r2(mean(steps), 2), pelvisBob: r2(mean(bob), 3), pelvisSway: r2(mean(sway), 3),
    kneeSwing: r2(mean(kSw), 0), kneeLoad: r2(mean(kLd), 0), pitchStrike: r2(mean(pS), 0), pitchToeOff: r2(mean(pT), 0),
    clearance: r2(mean(clr), 3), armSwing: r2(mean(arm), 2),
  };
}

const rows = [];
for (const [id, c] of Object.entries(film.cast)) {
  if ((who && id !== who) || c.hidden) continue;
  const perf = film.performances[id];
  if (!perf?.keys) continue;
  let motion = makeMotion(resolveKeys(expandMoves(perf.keys, MOVES, CLIPS), POSES), film.motion ?? {});
  if (film.motion?.lockFeet) motion = lockFeet(motion, DUR, film.motion.lockFeet);
  const S = sample(makeFigure({}), motion);
  for (const [a, b, sp] of stretches(S, motion.cuts || [])) rows.push({ id, ...measure(S, a, b, sp) });
}

const flag = (k, v) => (REF[k] && v != null && (v < REF[k][0] || v > REF[k][1]) ? ' ✗' : '');
if (args.includes('--json')) console.log(JSON.stringify({ film: args[0], hz: HZ, ref: REF, rows }, null, 1));
else {
  console.log(`gait · ${args[0]} · ${HZ} Hz · lockFeet ${film.motion?.lockFeet ? 'ON' : 'off'} · ✗ = outside the human range`);
  for (const r of rows) {
    console.log(`  ${r.id} ${r.from}-${r.to} s at ${r.speed} m/s, ${r.strikes} strikes`);
    for (const k of Object.keys(REF)) console.log(`    ${k.padEnd(14)} ${String(r[k]).padStart(7)}   human ${REF[k][0]}-${REF[k][1]} ${REF[k][2]}${flag(k, r[k])}`);
    console.log(`    ${'armSwing'.padEnd(14)} ${String(r.armSwing).padStart(7)}   (hand travel along the walk, m p2p; a hand on the hilt barely swings)`);
  }
  if (!rows.length) console.log('  no walking stretch (>= 1.2 s at >= 0.5 m/s on the ground)');
}

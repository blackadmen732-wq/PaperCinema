// Folded-paper characters. Faceless, like the reference art.
// Rig: root → hips → torso → head / shoulders → elbows → hands.
// Figure faces +z. Its right side is -x.
import * as THREE from 'three';
import { paper } from './paper.js';

function m(geo, mat) {
  const x = new THREE.Mesh(geo, mat);
  x.castShadow = true;
  x.receiveShadow = true;
  return x;
}

// Leg proportions (metres). Hip joints sit ~0.90 m high, so a standing leg is slightly bent.
export const LEG = { thigh: 0.46, shin: 0.44, hipY: 0.92, footY: 0.04 };

export function makeFigure(c) {
  // A cloth value is either a colour ("#2b4a6b") or a patterned cloth
  // ({ "color": "#2b4a6b", "pattern": "seigaiha", "fg": "#e8dcc4", "scale": 1 }).
  const P = (v) => (typeof v === 'string' || v == null)
    ? paper(v ?? '#888888', { repeat: 6 })
    : paper(v.color, { repeat: v.repeat ?? 3, pattern: { pattern: v.pattern, fg: v.fg, scale: v.scale } });
  const root = new THREE.Group();
  root.rotation.order = 'YXZ';
  const hips = new THREE.Group();
  hips.position.y = 0.92;
  root.add(hips);

  // hakama upper part: short pleated skirt over the hips (swings with sway / swayx)
  const hakama = new THREE.Group();
  hips.add(hakama);
  const skirt = m(new THREE.CylinderGeometry(0.17, 0.3, 0.34, 6, 1, true), P(c.hakama));
  skirt.position.y = -0.17;
  hakama.add(skirt);
  const pleat = m(new THREE.ConeGeometry(0.15, 0.36, 3, 1, true), P(c.hakamaFold ?? c.hakama));
  pleat.rotation.x = Math.PI;
  pleat.position.set(0, -0.18, 0.17);
  pleat.scale.set(1, 1, 0.3);
  hakama.add(pleat);

  // legs: hip → thigh → knee → shin → foot. Hakama are split, very wide trousers,
  // so each leg wears its own flared paper trouser leg. Solved by leg IK every frame
  // (solveLegs) so feet stay planted and knees bend when the hips drop.
  const leg = (sgn) => {
    const thigh = new THREE.Group();
    root.add(thigh);
    const tLeg = m(new THREE.CylinderGeometry(0.11, 0.15, LEG.thigh, 5, 1, true), P(c.hakama));
    tLeg.position.y = -LEG.thigh / 2;
    thigh.add(tLeg);
    const shin = new THREE.Group();
    shin.position.y = -LEG.thigh;
    thigh.add(shin);
    const sLeg = m(new THREE.CylinderGeometry(0.15, 0.2, LEG.shin, 5, 1, true), P(c.hakamaFold ?? c.hakama));
    sLeg.position.y = -LEG.shin / 2 + 0.03;
    shin.add(sLeg);
    const foot = new THREE.Group();
    foot.position.y = -LEG.shin;
    shin.add(foot);
    const sole = m(new THREE.BoxGeometry(0.085, 0.05, 0.22), P(c.foot ?? '#e8e1d2'));
    sole.position.set(0, -0.015, 0.06);
    foot.add(sole);
    return { thigh, shin, foot, side: sgn };
  };
  const legs = { r: leg(-1), l: leg(1) };

  const torso = new THREE.Group();
  hips.add(torso);
  const chest = m(new THREE.CylinderGeometry(0.21, 0.16, 0.54, 5), P(c.robe));
  chest.position.y = 0.27;
  torso.add(chest);
  const obi = m(new THREE.CylinderGeometry(0.175, 0.175, 0.09, 6), P(c.obi ?? '#2b2420'));
  obi.position.y = 0.04;
  torso.add(obi);
  // crossed kimono collar (eri): two folded strips forming a V
  for (const sgn of [1, -1]) {
    const eri = m(new THREE.BoxGeometry(0.05, 0.42, 0.012), P(c.collar ?? '#ece4d2'));
    eri.position.set(sgn * 0.045, 0.32, 0.185);
    eri.rotation.z = sgn * 0.38;
    eri.rotation.x = -0.12;
    torso.add(eri);
  }
  if (c.haori) {
    // open over-jacket panels hanging from the shoulders
    for (const sgn of [1, -1]) {
      const panel = m(new THREE.BoxGeometry(0.17, 0.7, 0.02), P(c.haori));
      panel.position.set(sgn * 0.13, 0.17, 0.17);
      panel.rotation.set(-0.08, 0, sgn * 0.05);
      torso.add(panel);
    }
    const back = m(new THREE.BoxGeometry(0.42, 0.72, 0.02), P(c.haori));
    back.position.set(0, 0.16, -0.17);
    back.rotation.x = 0.1;
    torso.add(back);
  }

  const head = new THREE.Group();
  head.position.y = 0.55;
  torso.add(head);
  const neck = m(new THREE.CylinderGeometry(0.045, 0.055, 0.1, 5), P(c.skin));
  neck.position.y = 0.03;
  head.add(neck);
  const face = m(new THREE.DodecahedronGeometry(0.1), P(c.skin));
  face.scale.set(0.88, 1.18, 0.98);
  face.position.y = 0.16;
  head.add(face);
  const hair = m(new THREE.DodecahedronGeometry(0.1), P(c.hair ?? '#1c1a1c'));
  hair.scale.set(0.95, 1.05, 0.95);
  hair.position.set(0, 0.2, -0.03);
  head.add(hair);
  const knot = m(new THREE.BoxGeometry(0.04, 0.035, 0.12), P(c.hair ?? '#1c1a1c'));
  knot.position.set(0, 0.3, -0.02);
  knot.rotation.x = -0.3;
  head.add(knot);
  let bandTail = null;
  if (c.band) {
    const band = m(new THREE.CylinderGeometry(0.103, 0.103, 0.035, 8, 1, true), P(c.band));
    band.position.y = 0.27;
    band.scale.set(1.04, 1, 1.08);
    head.add(band);
    bandTail = new THREE.Group();
    bandTail.position.set(0, 0.27, -0.1);
    for (const sgn of [1, -1]) {
      const t = m(new THREE.BoxGeometry(0.035, 0.16, 0.006), P(c.band));
      t.position.set(sgn * 0.02, -0.08, -0.01);
      t.rotation.set(0.35, 0, sgn * 0.25);
      bandTail.add(t);
    }
    head.add(bandTail);
  }
  if (c.kasa) {
    // sugegasa: shallow conical straw hat
    const hat = m(new THREE.ConeGeometry(0.36, 0.17, 12, 1, true), paper('#d8c9a8', { repeat: 8 }));
    hat.position.y = 0.36;
    head.add(hat);
  }

  const arm = (sgn) => {
    const shoulder = new THREE.Group();
    shoulder.position.set(sgn * 0.23, 0.47, 0);
    torso.add(shoulder);
    const up = m(new THREE.CylinderGeometry(0.065, 0.12, 0.32, 4), P(c.sleeve ?? c.robe));
    up.position.y = -0.15;
    up.rotation.y = Math.PI / 4;
    shoulder.add(up);
    const elbow = new THREE.Group();
    elbow.position.y = -0.3;
    shoulder.add(elbow);
    const fore = m(new THREE.CylinderGeometry(0.1, 0.06, 0.25, 4), P(c.sleeve ?? c.robe));
    fore.position.y = -0.12;
    fore.rotation.y = Math.PI / 4;
    elbow.add(fore);
    const hand = new THREE.Group();
    hand.position.y = -0.29;
    elbow.add(hand);
    const fist = m(new THREE.BoxGeometry(0.06, 0.08, 0.07), P(c.skin));
    hand.add(fist);
    return { shoulder, elbow, hand };
  };
  const R = arm(-1), Lf = arm(1);

  return {
    root, hips, torso, head, hakama, bandTail, legs,
    rS: R.shoulder, rE: R.elbow, rH: R.hand,
    lS: Lf.shoulder, lE: Lf.elbow, lH: Lf.hand,
  };
}

/** Attach a sword-like prop (built along +x) to a hand, grip point at gripX. */
export function holdInHand(hand, prop, gripX = -0.06) {
  const holder = new THREE.Group();
  const a = Math.SQRT1_2;
  const xAxis = new THREE.Vector3(0, -a, a);
  const yAxis = new THREE.Vector3(0, a, a);
  const zAxis = new THREE.Vector3().crossVectors(xAxis, yAxis);
  holder.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xAxis, yAxis, zAxis));
  holder.position.copy(xAxis.clone().multiplyScalar(-gripX)).add(new THREE.Vector3(0, -0.01, 0));
  holder.add(prop);
  hand.add(holder);
  return holder;
}

export const BASE_POSE = {
  x: 0, y: 0, z: 0, ry: 0, rx: 0, rz: 0,
  tx: 0, ty: 0, tz: 0, hx: 0, hy: 0,
  rsx: 0.05, rsz: 0.12, rex: -0.15,
  lsx: 0.05, lsz: -0.12, lex: -0.15,
  rwx: 0, lwx: 0,
  sway: 0, swayx: 0,
  // lower body: stance = distance between feet front-to-back (right foot forward, kenjutsu style),
  // crouch = how far the hips drop (knees bend), weight = -1 back foot … +1 front foot,
  // stride/phase = walking step size and cycle phase (set by the engine while walking)
  stance: 0.12, crouch: 0, weight: 0, stride: 0, phase: 0,
};

export function applyPose(f, p) {
  f.root.position.set(p.x, p.y, p.z);
  // balance: hips drop with crouch and shift over the loaded foot
  f.hips.position.set(0, LEG.hipY - p.crouch, p.weight * p.stance * 0.35);
  if (f.legs) solveLegs(f, p);
  f.root.rotation.set(p.rx, p.ry, p.rz);
  f.torso.rotation.set(p.tx + p.weight * 0.05, p.ty, p.tz);
  f.head.rotation.set(p.hx, p.hy, 0);
  f.rS.rotation.set(p.rsx, 0, p.rsz);
  f.rE.rotation.x = p.rex;
  f.lS.rotation.set(p.lsx, 0, p.lsz);
  f.lE.rotation.x = p.lex;
  f.rH.rotation.x = p.rwx;
  f.lH.rotation.x = p.lwx;
  f.hakama.rotation.z = p.sway;
  f.hakama.rotation.x = p.swayx ?? 0;
}

export const smooth = (k) => k * k * (3 - 2 * k);

/** keys: [[time, poseOverrides], ...] — evaluates a smooth pose at time t. */
export function track(keys, t) {
  const full = keys.map(([k, p]) => [k, { ...BASE_POSE, ...p }]);
  if (t <= full[0][0]) return { ...full[0][1] };
  for (let i = 0; i < full.length - 1; i++) {
    const [t0, a] = full[i], [t1, b] = full[i + 1];
    if (t <= t1) {
      const k = smooth((t - t0) / (t1 - t0));
      const out = {};
      for (const key in a) out[key] = a[key] + (b[key] - a[key]) * k;
      return out;
    }
  }
  return { ...full[full.length - 1][1] };
}

// ---------------------------------------------------------------------------
// SMOOTH MOTION
// A performance is a list of keys: { t, pose: "name", ...overrides }.
// Each joint channel is interpolated with a monotone cubic curve (Fritsch–Carlson):
// velocity is continuous through every key (no robotic stop at each pose) and the
// curve never overshoots a key (no wobble). Holding a pose = two keys with the same pose.
// ---------------------------------------------------------------------------
const CHANNELS = Object.keys(BASE_POSE);

function monotoneTangents(ts, vs) {
  const n = ts.length, m = new Array(n).fill(0), d = [];
  for (let k = 0; k < n - 1; k++) d.push((vs[k + 1] - vs[k]) / (ts[k + 1] - ts[k]));
  for (let k = 1; k < n - 1; k++) {
    if (d[k - 1] * d[k] <= 0) continue;            // turning point or hold → stop there smoothly
    const h0 = ts[k] - ts[k - 1], h1 = ts[k + 1] - ts[k];
    const w1 = 2 * h1 + h0, w2 = h1 + 2 * h0;
    m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k]);
  }
  return m;                                         // first/last tangent 0 = start and end at rest
}

/** Build a motion from resolved keys [[t, fullPose], ...]; returns (t) => pose. */
export function makeMotion(keys) {
  const ts = keys.map((k) => k[0]);
  const curves = {};
  for (const c of CHANNELS) {
    const vs = keys.map((k) => k[1][c] ?? BASE_POSE[c]);
    curves[c] = { vs, m: monotoneTangents(ts, vs) };
  }
  return (t) => {
    const out = {};
    const n = ts.length;
    let i = 0;
    while (i < n - 2 && t >= ts[i + 1]) i++;
    for (const c of CHANNELS) {
      const { vs, m } = curves[c];
      if (n === 1 || t <= ts[0]) { out[c] = vs[0]; continue; }
      if (t >= ts[n - 1]) { out[c] = vs[n - 1]; continue; }
      const h = ts[i + 1] - ts[i], u = (t - ts[i]) / h;
      const h00 = 2 * u ** 3 - 3 * u ** 2 + 1, h10 = u ** 3 - 2 * u ** 2 + u, h01 = -2 * u ** 3 + 3 * u ** 2, h11 = u ** 3 - u ** 2;
      out[c] = h00 * vs[i] + h10 * h * m[i] + h01 * vs[i + 1] + h11 * h * m[i + 1];
    }
    return out;
  };
}

/** Resolve data keys ({ t, pose, ...overrides }) against the pose library. */
export function resolveKeys(keys, poses) {
  let last = { ...BASE_POSE };
  return keys.map((k) => {
    const named = k.pose ? poses[k.pose] : {};
    if (k.pose && !named) throw new Error(`Unknown pose "${k.pose}" at t=${k.t}`);
    // x / z / ry (where the body stands and faces) carry over from the previous key unless given.
    // y / rx / rz (crouch, tilt) reset to 0 unless given. Joints come from the named pose,
    // or from the previous key when the key has no pose (an "overrides only" key).
    const joints = k.pose ? { ...BASE_POSE, ...named } : { ...last };
    const full = { ...joints, x: last.x, z: last.z, ry: last.ry, y: 0, rx: 0, rz: 0 };
    for (const [key, v] of Object.entries(k)) if (key in BASE_POSE) full[key] = v;
    last = full;
    return [k.t, full];
  });
}

/** Weight 0..1 inside time windows [[t0, t1], ...] with soft edges. */
export function windowWeight(windows, t, fade = 0.15) {
  let w = 0;
  for (const [a, b] of windows ?? []) {
    if (t < a - fade || t > b + fade) continue;
    w = Math.max(w, Math.min(1, (t - (a - fade)) / fade, ((b + fade) - t) / fade));
  }
  return Math.max(0, Math.min(1, w));
}

// ---------------------------------------------------------------------------
// TWO-HAND GRIP (inverse kinematics)
// Moves the left shoulder + elbow so the left hand lands on a world-space target
// (the end of the sword handle). Small deterministic search, starting from the
// animated pose every frame, so the result is the same on every render.
// ---------------------------------------------------------------------------
const _hand = new THREE.Vector3();
/** Bend one arm ('l' or 'r') so that hand lands on a world-space target. */
export function reachHand(f, side, target, weight = 1) {
  if (weight <= 0) return;
  const S = side === 'r' ? f.rS : f.lS, E = side === 'r' ? f.rE : f.lE, H = side === 'r' ? f.rH : f.lH;
  const start = [S.rotation.x, S.rotation.z, E.rotation.x];
  const p = start.slice();
  const err = (q) => {
    S.rotation.x = q[0];
    S.rotation.z = q[1];
    E.rotation.x = Math.max(-2.6, Math.min(0, q[2]));
    S.updateMatrixWorld(true);
    H.getWorldPosition(_hand);
    return _hand.distanceToSquared(target);
  };
  let best = err(p), step = 0.35;
  for (let it = 0; it < 40 && step > 0.003; it++) {
    let improved = false;
    for (let k = 0; k < 3; k++) for (const dir of [1, -1]) {
      const q = p.slice(); q[k] += dir * step;
      const e = err(q);
      if (e < best) { best = e; p[k] = q[k]; improved = true; }
    }
    if (!improved) step *= 0.5;
  }
  err(start.map((v, k) => v + (p[k] - v) * weight));
}
export const reachLeftHand = (f, target, weight = 1) => reachHand(f, 'l', target, weight);

// ---------------------------------------------------------------------------
// LEGS (analytic two-bone IK in the figure's side plane)
// Feet are planted from the stance; the hip height comes from crouch. Knees always bend forward.
// ---------------------------------------------------------------------------
export function solveLegs(f, p) {
  const L1 = LEG.thigh, L2 = LEG.shin;
  const hipY = LEG.hipY - p.crouch - 0.02, hipZ = p.weight * p.stance * 0.35;
  for (const leg of [f.legs.r, f.legs.l]) {
    const front = leg.side < 0;                       // right foot leads
    let fz = (front ? 1 : -1) * p.stance / 2, fy = LEG.footY;
    if (p.stride > 0) {                               // walking: feet swing in opposite phase
      const ph = p.phase + (front ? 0 : Math.PI);
      fz += Math.sin(ph) * p.stride / 2;
      fy += Math.max(0, Math.cos(ph)) * 0.07;
    }
    let dz = fz - hipZ, dy = fy - hipY;
    let d = Math.hypot(dz, dy);
    const maxD = (L1 + L2) * 0.999;
    if (d > maxD) { dz *= maxD / d; dy *= maxD / d; d = maxD; }
    const phi = Math.atan2(dz, -dy);                  // hip→foot angle from straight down (toward +z)
    const a = Math.acos(Math.max(-1, Math.min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))));
    const thighAng = phi + a;                         // knee goes forward
    const kz = hipZ + L1 * Math.sin(thighAng), ky = hipY - L1 * Math.cos(thighAng);
    const shinAng = Math.atan2(hipZ + dz - kz, -(hipY + dy - ky));
    leg.thigh.position.set(leg.side * 0.1, hipY, hipZ);
    leg.thigh.rotation.set(-thighAng, 0, leg.side * 0.04);
    leg.shin.rotation.x = -(shinAng - thighAng);
    leg.foot.rotation.x = shinAng;                    // sole stays flat on the ground
  }
}

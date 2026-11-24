// Folded-paper characters. Faceless by default, like the reference art ({ face: 'eyes' } adds
// two glowing eye slits with lids, for close-ups).
// Rig: root → hips → torso (waist) → upper (chest) → neck → head
//                                  upper → clavicle → shoulder → elbow → twist (forearm) → hand.
// Legs: root → thigh → shin → foot (solved by leg IK). Every rigid paper part overlaps its
// neighbour at the joint, and small folded covers hide the gaps, so it never looks broken.
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
  // detail (default on; { detail: false } = the old simple body): hanging kimono sleeves, trouser pleats,
  // zori sandals, an obi knot with a cord, and (with { hairLong: true }) long hair strands, like the
  // carved paper reference figure.
  const detail = c.detail !== false;
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
    thigh.rotation.order = 'ZXY';            // bend in the leg plane (x), then roll the plane sideways (z)
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
    if (detail) {
      // zori: a dark sole under the tabi, and a red thong strap
      const zori = m(new THREE.BoxGeometry(0.1, 0.022, 0.25), P(c.sandal ?? '#2a2320'));
      zori.position.set(0, -0.04, 0.06);
      foot.add(zori);
      const strap = m(new THREE.BoxGeometry(0.09, 0.012, 0.016), P(c.strap ?? '#8e2420'));
      strap.position.set(0, 0.012, 0.11);
      strap.rotation.x = 0.5;
      foot.add(strap);
      // three folded pleats down the front of each trouser leg
      for (const k of [-1, 0, 1]) {
        const pl = m(new THREE.BoxGeometry(0.012, LEG.shin * 0.95, 0.02), P(c.hakamaFold ?? c.hakama));
        pl.position.set(k * 0.06, -LEG.shin / 2 + 0.03, 0.17 - Math.abs(k) * 0.03);
        pl.rotation.x = -0.1;
        shin.add(pl);
      }
    }
    return { thigh, shin, foot, side: sgn };
  };
  const legs = { r: leg(-1), l: leg(1) };

  // Spine in two parts: the waist (torso, pivot at the hips) and the chest (upper, pivot 0.26 m up).
  // The two robe pieces overlap by 6 cm so the bend never opens a gap.
  const torso = new THREE.Group();
  hips.add(torso);
  const belly = m(new THREE.CylinderGeometry(0.19, 0.16, 0.3, 5), P(c.robe));
  belly.position.y = 0.15;
  torso.add(belly);
  const obi = m(new THREE.CylinderGeometry(0.175, 0.175, 0.09, 6), P(c.obi ?? '#2b2420'));
  obi.position.y = 0.04;
  torso.add(obi);
  if (detail) {
    const knot = m(new THREE.BoxGeometry(0.07, 0.05, 0.04), P(c.obi ?? '#2b2420'));
    knot.position.set(0.05, 0.03, 0.17);
    knot.rotation.z = 0.3;
    torso.add(knot);
    const cord = m(new THREE.BoxGeometry(0.02, 0.16, 0.012), P(c.cord ?? '#8e2420'));
    cord.position.set(0.07, -0.05, 0.18);
    cord.rotation.z = 0.15;
    torso.add(cord);
  }
  const upper = new THREE.Group();
  upper.position.y = 0.26;
  torso.add(upper);
  const chest = m(new THREE.CylinderGeometry(0.21, 0.182, 0.3, 5), P(c.robe));
  chest.position.y = 0.14;
  upper.add(chest);
  // crossed kimono collar (eri): two folded strips forming a V
  for (const sgn of [1, -1]) {
    const eri = m(new THREE.BoxGeometry(0.05, 0.42, 0.012), P(c.collar ?? '#ece4d2'));
    eri.position.set(sgn * 0.045, 0.06, 0.185);
    eri.rotation.z = sgn * 0.38;
    eri.rotation.x = -0.12;
    upper.add(eri);
  }
  if (c.haori) {
    // open over-jacket panels hanging from the shoulders (they move with the chest)
    for (const sgn of [1, -1]) {
      const panel = m(new THREE.BoxGeometry(0.17, 0.7, 0.02), P(c.haori));
      panel.position.set(sgn * 0.13, -0.09, 0.17);
      panel.rotation.set(-0.08, 0, sgn * 0.05);
      upper.add(panel);
    }
    const back = m(new THREE.BoxGeometry(0.42, 0.72, 0.02), P(c.haori));
    back.position.set(0, -0.1, -0.17);
    back.rotation.x = 0.1;
    upper.add(back);
  }

  // neck (nods/turns on its own) → head. A folded collar cone hides the base of the neck.
  const neckG = new THREE.Group();
  neckG.position.y = 0.29;
  upper.add(neckG);
  const neck = m(new THREE.CylinderGeometry(0.045, 0.055, 0.1, 5), P(c.skin));
  neck.position.y = 0.03;
  neckG.add(neck);
  const collarCone = m(new THREE.CylinderGeometry(0.07, 0.11, 0.06, 6, 1, true), P(c.collar ?? '#ece4d2'));
  collarCone.position.y = 0.28;
  upper.add(collarCone);
  const head = new THREE.Group();
  head.position.y = 0.06;
  neckG.add(head);
  const face = m(new THREE.DodecahedronGeometry(0.1), P(c.skin));
  face.scale.set(0.88, 1.18, 0.98);
  face.position.y = 0.1;
  head.add(face);
  let lids = [], eyeMat = null;
  if (c.face === 'eyes') {
    // two narrow eye slits that glow amber from the inner lantern light, a folded brow above,
    // and skin-paper lids that close by scaling (lid 0 = open, 1 = shut)
    const brow = m(new THREE.BoxGeometry(0.15, 0.014, 0.03), P(c.skin));
    brow.position.set(0, 0.135, 0.083);
    brow.rotation.x = -0.25;
    head.add(brow);
    for (const sgn of [1, -1]) {
      const eye = new THREE.Group();
      eye.position.set(sgn * 0.034, 0.112, 0.088);
      eye.rotation.set(-0.12, sgn * 0.32, sgn * -0.12);
      eyeMat ??= paper(c.eyes ?? '#ffb04a', { glow: 1.2 }).clone();   // own material: each fighter's eyes glow on their own
      const slit = new THREE.Mesh(new THREE.BoxGeometry(0.036, 0.011, 0.006), eyeMat);
      eye.add(slit);
      const pupil = new THREE.Mesh(new THREE.BoxGeometry(0.009, 0.011, 0.007), paper('#1a1210'));
      pupil.position.x = -sgn * 0.004;
      eye.add(pupil);
      const lid = m(new THREE.BoxGeometry(0.042, 0.016, 0.006), P(c.skin));
      lid.position.set(0, 0.009, 0.0015);
      lid.scale.y = 0.05;
      eye.add(lid);
      lids.push(lid);
      head.add(eye);
    }
  }
  const hair = m(new THREE.DodecahedronGeometry(0.1), P(c.hair ?? '#1c1a1c'));
  hair.scale.set(0.95, 1.05, 0.95);
  hair.position.set(0, 0.14, -0.03);
  head.add(hair);
  if (c.hairLong) {
    // long hair: tapered folded strands from the back of the head down past the shoulders
    for (let i = 0; i < 7; i++) {
      const a = (i / 6 - 0.5) * 2.2;
      const st = m(new THREE.ConeGeometry(0.035, 0.42, 3), P(c.hair ?? '#1c1a1c'));
      st.rotation.set(Math.PI + 0.18, 0, a * 0.12);
      st.position.set(Math.sin(a) * 0.085, -0.06, -0.03 - Math.cos(a) * 0.06);
      head.add(st);
    }
  }
  const knot = m(new THREE.BoxGeometry(0.04, 0.035, 0.12), P(c.hair ?? '#1c1a1c'));
  knot.position.set(0, 0.24, -0.02);
  knot.rotation.x = -0.3;
  head.add(knot);
  let bandTail = null;
  if (c.band) {
    const band = m(new THREE.CylinderGeometry(0.103, 0.103, 0.035, 8, 1, true), P(c.band));
    band.position.y = 0.21;
    band.scale.set(1.04, 1, 1.08);
    head.add(band);
    bandTail = new THREE.Group();
    bandTail.position.set(0, 0.21, -0.1);
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
    const hat = m(new THREE.ConeGeometry(0.36, 0.17, 12, 1, true), paper(c.kasaColor ?? '#d8c9a8', { repeat: 8 }));
    hat.position.y = 0.3;
    head.add(hat);
  }

  // clavicle (shrug / forward) → shoulder (ball joint) → elbow (hinge) → twist (forearm roll) → hand
  // (wrist: flex + side bend). Folded diamonds cover the elbow so the bend never shows a gap.
  const arm = (sgn) => {
    const clav = new THREE.Group();
    clav.position.set(sgn * 0.07, 0.21, 0);
    upper.add(clav);
    const shoulder = new THREE.Group();
    shoulder.position.set(sgn * 0.16, 0, 0);
    clav.add(shoulder);
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
    const cover = m(new THREE.OctahedronGeometry(0.075), P(c.sleeve ?? c.robe));
    cover.scale.set(1, 0.8, 1);
    elbow.add(cover);
    const twist = new THREE.Group();
    elbow.add(twist);
    let tamoto = null;
    if (detail) {
      // tamoto: the wide kimono sleeve hangs from the forearm; hangCloth() turns it toward the ground
      tamoto = new THREE.Group();
      tamoto.position.y = -0.1;
      twist.add(tamoto);
      const panel = m(new THREE.BoxGeometry(0.03, 0.26, 0.2), P(c.sleeve ?? c.robe));
      panel.position.set(0, -0.11, 0);
      tamoto.add(panel);
      const hem = m(new THREE.BoxGeometry(0.034, 0.03, 0.2), P(c.sleeveHem ?? c.haori ?? c.collar ?? '#ece4d2'));
      hem.position.set(0, -0.235, 0);
      tamoto.add(hem);
    }
    const hand = new THREE.Group();
    hand.position.y = -0.29;
    twist.add(hand);
    if (c.hands === 'fist') {
      const fist = m(new THREE.BoxGeometry(0.06, 0.08, 0.07), P(c.skin));
      hand.add(fist);
    } else {
      // GRIP HAND (default): folded fingers wrapped round the sword handle, thumb over the top, back of the
      // hand toward the outside, the way a swordsman holds the tsuka (te-no-uchi). The handle runs along the
      // hand's local (0, -0.707, 0.707) axis (see holdInHand), so the grip is built around that axis.
      const grip = new THREE.Group();
      grip.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), GRIP_AXIS);
      grip.position.set(0, -0.01, 0);
      hand.add(grip);
      const skin = P(c.skin);
      for (let i = 0; i < 4; i++) {                       // four fingers, each a folded C round the handle
        const f = m(new THREE.CylinderGeometry(0.027, 0.027, 0.017, 5, 1, true, 0.35 * Math.PI, 1.35 * Math.PI), skin);
        f.rotation.z = Math.PI / 2;                       // cylinder axis → grip x (the handle)
        f.position.x = -0.03 + i * 0.019;
        f.scale.set(1, 1, 1 - i * 0.05);                  // little finger slightly smaller
        grip.add(f);
      }
      const back = m(new THREE.BoxGeometry(0.08, 0.018, 0.05), skin);   // back of the hand, knuckles toward the blade
      back.position.set(0, 0.03, -0.012);
      back.rotation.x = -0.35;
      grip.add(back);
      const thumb = m(new THREE.BoxGeometry(0.05, 0.014, 0.016), skin); // thumb over the top of the handle
      thumb.position.set(0.012, 0.004, 0.026);
      thumb.rotation.y = -0.25;
      grip.add(thumb);
      const wrist = m(new THREE.BoxGeometry(0.05, 0.05, 0.045), skin);  // the wrist block joins the forearm
      wrist.position.set(0, 0.035, 0);
      hand.add(wrist);
    }
    return { clav, shoulder, elbow, twist, hand, tamoto };
  };
  const R = arm(-1), Lf = arm(1);

  return {
    root, hips, torso, upper, neck: neckG, head, hakama, bandTail, legs, lids, eyeMat,
    sleeves: [R.tamoto, Lf.tamoto].filter(Boolean),
    rC: R.clav, rS: R.shoulder, rE: R.elbow, rT: R.twist, rH: R.hand,
    lC: Lf.clav, lS: Lf.shoulder, lE: Lf.elbow, lT: Lf.twist, lH: Lf.hand,
  };
}

const GRIP_AXIS = new THREE.Vector3(0, -Math.SQRT1_2, Math.SQRT1_2);   // the handle's direction in a hand's frame

/** Turn a hand ('l' or 'r') so its grip axis lies along the sword's handle (after IK put it there):
 *  the left hand then truly wraps the tsuka instead of floating beside it. weight blends from the keyed wrist. */
const _gq = new THREE.Quaternion(), _gp = new THREE.Quaternion(), _ga = new THREE.Vector3(), _gs = new THREE.Vector3();
export function gripHand(f, side, sword, weight = 1) {
  if (weight <= 0) return;
  const H = side === 'r' ? f.rH : f.lH;
  H.updateMatrixWorld(true);
  H.getWorldQuaternion(_gq);
  _ga.copy(GRIP_AXIS).applyQuaternion(_gq);                       // where the hand's grip points now
  _gs.set(1, 0, 0).applyQuaternion(sword.getWorldQuaternion(_gp)); // the handle's direction (sword +x)
  const fix = new THREE.Quaternion().setFromUnitVectors(_ga, _gs);
  const want = fix.multiply(_gq);                                  // world orientation we want
  H.parent.getWorldQuaternion(_gp);
  const local = _gp.invert().multiply(want);
  H.quaternion.slerp(local, weight);
  H.updateMatrixWorld(true);
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
  // added joints (all 0 = the old rig): chest cx/cy/cz (bend/turn/side) above the waist,
  // neck nx/ny, head roll hz, clavicles rcy/rcz (forward/shrug), shoulder twist rsy, forearm
  // twist rfy, wrist side-bend rwz (the cutting snap), ankles rax/lax, eyelids lid (0 open … 1 shut)
  cx: 0, cy: 0, cz: 0, nx: 0, ny: 0, hz: 0,
  rcy: 0, rcz: 0, lcy: 0, lcz: 0, rsy: 0, lsy: 0, rfy: 0, lfy: 0, rwz: 0, lwz: 0,
  rax: 0, lax: 0, lid: 0,
  // lower body: stance = distance between feet front-to-back (right foot forward, kenjutsu style),
  // crouch = how far the hips drop (knees bend), weight = -1 back foot … +1 front foot,
  // stride/phase = walking step size and cycle phase (set by the engine while walking)
  stance: 0.12, crouch: 0, weight: 0, stride: 0, phase: 0,
};

export function applyPose(f, p) {
  f.root.position.set(p.x, p.y, p.z);
  // balance: hips drop with crouch and shift over the loaded foot
  f.hips.position.set(0, LEG.hipY - p.crouch, p.weight * p.stance * 0.35);
  f.root.rotation.set(p.rx, p.ry, p.rz);
  if (f.legs) solveLegs(f, p);                 // after the root transform: world-locked feet need it
  const v = (k) => p[k] ?? 0;
  f.torso.rotation.set(p.tx + p.weight * 0.05, p.ty, p.tz);
  if (f.upper) f.upper.rotation.set(v('cx'), v('cy'), v('cz'));
  if (f.neck) f.neck.rotation.set(v('nx'), v('ny'), 0);
  f.head.rotation.set(p.hx, p.hy, v('hz'));
  if (f.rC) { f.rC.rotation.set(0, v('rcy'), -v('rcz')); f.lC.rotation.set(0, -v('lcy'), v('lcz')); }
  f.rS.rotation.set(p.rsx, v('rsy'), p.rsz);
  f.rE.rotation.x = p.rex;
  f.lS.rotation.set(p.lsx, v('lsy'), p.lsz);
  f.lE.rotation.x = p.lex;
  if (f.rT) { f.rT.rotation.y = v('rfy'); f.lT.rotation.y = v('lfy'); }
  f.rH.rotation.set(p.rwx, 0, v('rwz'));
  f.lH.rotation.set(p.lwx, 0, v('lwz'));
  for (const lid of f.lids ?? []) lid.scale.y = 0.05 + 0.95 * Math.min(1, Math.max(0, v('lid')));
  if (f.sleeves?.length) hangCloth(f, v('sway'));
  f.hakama.rotation.z = p.sway;
  f.hakama.rotation.x = p.swayx ?? 0;
}

/** Sleeves hang toward the ground (80%), whatever the arm does, plus a little swing from the cloth sway. */
const _hq = new THREE.Quaternion(), _hd = new THREE.Vector3(), _hy = new THREE.Vector3(0, -1, 0);
function hangCloth(f, sway = 0) {
  f.root.updateMatrixWorld(true);
  for (const g of f.sleeves) {
    g.quaternion.identity();
    g.parent.getWorldQuaternion(_hq);
    _hd.set(sway * 0.4, -1, 0).normalize().applyQuaternion(_hq.invert());
    g.quaternion.setFromUnitVectors(_hy, _hd);
    g.quaternion.slerp(new THREE.Quaternion(), 0.2);
  }
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

// ---------------------------------------------------------------------------
// ANIME MOTION LAYER (opt-in: makeMotion(keys, { overlap: true }) or film "motion": { "overlap": true })
// 1. Follow-through: each joint runs a few frames behind the one before it (hips lead, then chest,
//    shoulder, elbow, wrist; cloth last). A key with "drag": 0 (a contact) pulls every joint into
//    sync on that frame, so the far joints whip to catch up — the snap.
// 2. Snap easing: a key with "ease": [x1, y1, x2, y2] (cubic-bezier, CSS style) shapes the segment
//    that arrives at it. "snap" = accelerate and stop dead; "antic" = quick start, slow creep.
// 3. Overshoot and settle: a key with "settle": true (or a number = strength) makes each joint pass
//    the pose a little and settle back (closed-form damped spring, so any frame can be rendered alone).
// ---------------------------------------------------------------------------
const FPS_LAG = 24;
const LAG_GROUPS = [
  [-2, ['hx', 'hy', 'hz', 'nx', 'ny', 'stance', 'crouch', 'weight', 'rax', 'lax']],
  [-1, ['x', 'z', 'ry']],
  [1, ['cx', 'cy', 'cz', 'rcy', 'rcz', 'lcy', 'lcz']],
  [1.5, ['rsx', 'rsy', 'rsz', 'lsx', 'lsy', 'lsz']],
  [2, ['rex', 'lex']],
  [2.5, ['rfy', 'lfy']],
  [3, ['rwx', 'rwz', 'lwx', 'lwz', 'sway', 'swayx']],
];
export const LAG = Object.fromEntries(LAG_GROUPS.flatMap(([f, cs]) => cs.map((c) => [c, f])));
// overshoot fraction, frequency (Hz), damping ratio
const SETTLE_GROUPS = [
  [[0.03, 3, 0.5], ['ry', 'stance', 'crouch', 'weight', 'tx', 'ty', 'tz']],
  [[0.04, 3, 0.5], ['hx', 'hy', 'hz', 'nx', 'ny']],
  [[0.05, 3, 0.5], ['cx', 'cy', 'cz']],
  [[0.06, 3, 0.5], ['rsx', 'rsy', 'rsz', 'lsx', 'lsy', 'lsz', 'rcy', 'rcz', 'lcy', 'lcz']],
  [[0.08, 3, 0.5], ['rex', 'lex']],
  [[0.12, 5, 0.4], ['rwx', 'rwz', 'lwx', 'lwz', 'rfy', 'lfy']],
  [[0.3, 1.6, 0.25], ['sway', 'swayx']],
];
export const SETTLE = Object.fromEntries(SETTLE_GROUPS.flatMap(([v, cs]) => cs.map((c) => [c, v])));
// The end slopes are finite on purpose: an infinite slope means infinite speed at the key.
// snap: ends 2.7x faster than average (a hard stop); antic: starts 3.7x faster, then creeps.
export const EASES = { snap: [0.55, 0, 0.85, 0.6], antic: [0.15, 0.55, 0.35, 1], out: [0.2, 0.6, 0.35, 1], in: [0.65, 0, 0.8, 0.4] };

/** CSS-style cubic-bezier easing: returns u → eased u (Newton + bisection, exact enough for frames). */
export function bezier(x1, y1, x2, y2) {
  const B = (a, b, u) => 3 * a * u * (1 - u) ** 2 + 3 * b * u * u * (1 - u) + u ** 3;
  const dB = (a, b, u) => 3 * a * (1 - u) ** 2 + 6 * (b - a) * u * (1 - u) + 3 * (1 - b) * u * u;
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let u = x;
    for (let i = 0; i < 8; i++) {
      const d = dB(x1, x2, u);
      if (Math.abs(d) < 1e-6) break;
      u = Math.min(1, Math.max(0, u - (B(x1, x2, u) - x) / d));
    }
    return B(y1, y2, u);
  };
}

/** Damped-spring overshoot after a key, travel D into the key, time tau after it. */
function settleOffset(D, tau, [o, f, z]) {
  if (tau <= 0 || tau > 2.5 || D === 0) return 0;
  const w = 2 * Math.PI * f, wd = w * Math.sqrt(1 - z * z);
  const tp = Math.atan(wd / (z * w)) / wd;                    // time of the first peak
  const A = o * D / (Math.exp(-z * w * tp) * Math.sin(wd * tp));
  return A * Math.exp(-z * w * tau) * Math.sin(wd * tau);
}

/** Build a motion from resolved keys [[t, fullPose, meta?], ...]; returns (t) => pose. */
export function makeMotion(keys, opts = {}) {
  const ts = keys.map((k) => k[0]);
  const meta = keys.map((k) => k[2] ?? {});
  const overlap = !!opts.overlap;
  const eases = meta.map((mt) => {
    const e = typeof mt.ease === 'string' ? EASES[mt.ease] : mt.ease;
    return e ? bezier(...e) : null;
  });
  const arcs = meta.map((mt, i) => (mt.arcTo ? 0 : mt.arc ?? 0));
  const jumps = [];
  meta.forEach((mt, i) => {
    if (!mt.arc || !mt.arcTo) return;
    let i1 = ts.findIndex((x) => Math.abs(x - mt.arcTo) < 1e-6);
    if (i1 <= i) throw new Error(`arcTo ${mt.arcTo}: no key at that time after ${ts[i]}`);
    jumps.push({ t0: ts[i], t1: ts[i1], i0: i, i1, h: mt.arc, hang: Math.min(0.8, mt.hang ?? 0) });
  });
  const curves = {};
  for (const c of CHANNELS) {
    const vs = keys.map((k) => k[1][c] ?? BASE_POSE[c]);
    curves[c] = { vs, m: monotoneTangents(ts, vs) };
  }
  const n = ts.length;
  const seg = (t) => { let i = 0; while (i < n - 2 && t >= ts[i + 1]) i++; return i; };
  const evalC = (c, t) => {
    const { vs, m } = curves[c];
    if (n === 1 || t <= ts[0]) return vs[0];
    if (t >= ts[n - 1]) return vs[n - 1];
    const i = seg(t);
    const h = ts[i + 1] - ts[i], u = (t - ts[i]) / h;
    // "arc": h + "arcTo": t = one jump spanning several keys (poses change in the air, the flight stays one
    // parabola). "hang": 0..0.8 slows the middle of the flight (anime hang time at the top).
    for (const J of jumps) {
      if (t < J.t0 || t >= J.t1 || (c !== 'x' && c !== 'z' && c !== 'y')) continue;
      let w = (t - J.t0) / (J.t1 - J.t0);
      w += J.hang * Math.sin(2 * Math.PI * w) / (2 * Math.PI);   // hang: slow near the apex
      const a = curves[c].vs[J.i0], b2 = curves[c].vs[J.i1];
      return a + (b2 - a) * w + (c === 'y' ? 4 * J.h * w * (1 - w) : 0);
    }
    // "arc": h on a key = a jump to the next key: constant speed across the ground, parabolic height
    if (arcs[i]) {
      if (c === 'x' || c === 'z') return vs[i] + (vs[i + 1] - vs[i]) * u;
      if (c === 'y') return vs[i] + (vs[i + 1] - vs[i]) * u + 4 * arcs[i] * u * (1 - u);
    }
    if (eases[i + 1]) return vs[i] + (vs[i + 1] - vs[i]) * eases[i + 1](u);
    const h00 = 2 * u ** 3 - 3 * u ** 2 + 1, h10 = u ** 3 - 2 * u ** 2 + u, h01 = -2 * u ** 3 + 3 * u ** 2, h11 = u ** 3 - u ** 2;
    return h00 * vs[i] + h10 * h * m[i] + h01 * vs[i + 1] + h11 * h * m[i + 1];
  };
  // drag(t): how much follow-through lag applies now (1 normally, "drag" on a key, linear between keys)
  const drags = meta.map((mt) => mt.drag ?? 1);
  const drag = (t) => {
    if (t <= ts[0]) return drags[0];
    if (t >= ts[n - 1]) return drags[n - 1];
    const i = seg(t), u = (t - ts[i]) / (ts[i + 1] - ts[i]);
    return drags[i] + (drags[i + 1] - drags[i]) * u;
  };
  const settles = meta.map((mt, i) => (mt.settle && i > 0 ? (mt.settle === true ? 1 : mt.settle) : 0));
  return (t) => {
    const out = {};
    const d = overlap ? drag(t) : 0;
    for (const c of CHANNELS) {
      const tc = overlap ? t - ((LAG[c] ?? 0) / FPS_LAG) * d : t;
      let v = evalC(c, tc);
      if (SETTLE[c]) {
        for (let k = 1; k < n; k++) {
          if (!settles[k] || tc <= ts[k]) continue;
          const { vs } = curves[c];
          v += settles[k] * settleOffset(vs[k] - vs[k - 1], tc - ts[k], SETTLE[c]);
        }
      }
      out[c] = v;
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
    return [k.t, full, { ease: k.ease, drag: k.drag, settle: k.settle, arc: k.arc, arcTo: k.arcTo, hang: k.hang }];
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
// ANALYTIC ARM IK (stable: one exact answer per frame, so no elbow pops between frames)
// Places the hand of one arm ('l' or 'r') on a world target. The elbow bends toward the pole
// direction (world space, default: down and out to that side). weight blends from the keyed arm.
// ---------------------------------------------------------------------------
const ARM = { upper: 0.3, fore: 0.29 };
const _S = new THREE.Vector3(), _T = new THREE.Vector3(), _P = new THREE.Vector3(), _q0 = new THREE.Quaternion();
const _ma = new THREE.Matrix4(), _mb = new THREE.Matrix4(), _inv = new THREE.Matrix4(), _qp = new THREE.Quaternion();
export function solveArm(f, side, target, pole, weight = 1) {
  if (weight <= 0) return;
  const S = side === 'r' ? f.rS : f.lS, E = side === 'r' ? f.rE : f.lE;
  const parent = S.parent;
  parent.updateMatrixWorld(true);
  _inv.copy(parent.matrixWorld).invert();
  // target and pole in the parent's (clavicle) space, relative to the shoulder pivot
  _T.copy(target).applyMatrix4(_inv).sub(S.position);
  parent.getWorldQuaternion(_qp);
  const sgn = side === 'r' ? -1 : 1;
  _P.copy(pole ?? new THREE.Vector3(sgn * 0.6, -1, -0.2)).applyQuaternion(_qp.invert()).normalize();
  const L1 = ARM.upper, L2 = ARM.fore;
  let d = _T.length();
  d = Math.min(Math.max(d, Math.abs(L1 - L2) + 1e-3), (L1 + L2) * 0.999);
  const cosE = (L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2);
  const rex = -(Math.PI - Math.acos(Math.max(-1, Math.min(1, cosE))));
  // the chain in the shoulder's own frame after bending the elbow
  const H = new THREE.Vector3(0, -L1 - L2 * Math.cos(rex), -L2 * Math.sin(rex));
  const El = new THREE.Vector3(0, -L1, 0);
  const a = H.clone().normalize();
  const e = El.clone().addScaledVector(a, -El.dot(a)).normalize();
  const a2 = _T.clone().normalize();
  const e2 = _P.clone().addScaledVector(a2, -_P.dot(a2));
  if (e2.lengthSq() < 1e-8) e2.set(0, -1, 0).addScaledVector(a2, a2.y);
  e2.normalize();
  _ma.makeBasis(a, e, a.clone().cross(e));
  _mb.makeBasis(a2, e2, a2.clone().cross(e2));
  const q = new THREE.Quaternion().setFromRotationMatrix(_mb.multiply(_ma.transpose()));
  _q0.copy(S.quaternion);
  S.quaternion.copy(_q0.slerp(q, weight));
  E.rotation.x += (rex - E.rotation.x) * weight;
  S.updateMatrixWorld(true);
}

// ---------------------------------------------------------------------------
// LEGS (analytic two-bone IK)
// Default: the feet are placed from the stance in the figure's side plane, so they follow the hips.
// With `p._feet` (engine/footlock.js) each foot is given a WORLD position instead: the foot is pinned
// to the ground and the leg is solved from it, so the hips move over the feet instead of dragging
// them. The target is brought into the root's frame, so the leg plane can now tilt sideways: the
// thigh takes a z-roll (hip abduction, Euler order ZXY) and bends in the rolled plane.
// Knees always bend forward.
// ---------------------------------------------------------------------------
const _legM = new THREE.Matrix4(), _legV = new THREE.Vector3();
export function solveLegs(f, p) {
  const L1 = LEG.thigh, L2 = LEG.shin;
  const hipY = LEG.hipY - p.crouch - 0.02, hipZ = p.weight * p.stance * 0.35;
  if (p._feet) { f.root.updateMatrix(); _legM.copy(f.root.matrix).invert(); }   // root hangs off the scene
  for (const leg of [f.legs.r, f.legs.l]) {
    const front = leg.side < 0;                       // right foot leads
    let fx = leg.side * 0.1, fz = (front ? 1 : -1) * p.stance / 2, fy = LEG.footY;
    if (p._feet) {
      const w = front ? p._feet.r : p._feet.l;
      _legV.set(w[0], w[1], w[2]).applyMatrix4(_legM);
      fx = _legV.x; fy = _legV.y; fz = _legV.z;
    } else if (p.stride > 0) {                        // walking: feet swing in opposite phase
      const ph = p.phase + (front ? 0 : Math.PI);
      fz += Math.sin(ph) * p.stride / 2;
      fy += Math.max(0, Math.cos(ph)) * 0.07;
    }
    // roll the leg plane sideways so it contains the hip→foot line, then solve inside that plane
    const sx = fx - leg.side * 0.1, sy = fy - hipY;
    const roll = Math.atan2(sx, -sy) + leg.side * 0.04;
    let dz = fz - hipZ, dy = -Math.hypot(sx, sy);
    let d = Math.hypot(dz, dy);
    const maxD = (L1 + L2) * 0.999;
    if (d > maxD) { dz *= maxD / d; dy *= maxD / d; d = maxD; }
    const phi = Math.atan2(dz, -dy);                  // hip→foot angle from straight down (toward +z)
    const a = Math.acos(Math.max(-1, Math.min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))));
    const thighAng = phi + a;                         // knee goes forward
    const kz = hipZ + L1 * Math.sin(thighAng), ky = hipY - L1 * Math.cos(thighAng);
    const shinAng = Math.atan2(hipZ + dz - kz, -(hipY + dy - ky));
    leg.thigh.position.set(leg.side * 0.1, hipY, hipZ);
    leg.thigh.rotation.set(-thighAng, 0, roll);
    leg.shin.rotation.x = -(shinAng - thighAng);
    leg.foot.rotation.x = shinAng + (front ? (p.rax ?? 0) : (p.lax ?? 0));   // flat on the ground (+ ankle)
  }
}

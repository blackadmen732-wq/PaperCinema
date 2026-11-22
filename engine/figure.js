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

  // hakama: a wide faceted paper skirt + folded front pleat
  const hakama = new THREE.Group();
  hips.add(hakama);
  const skirt = m(new THREE.CylinderGeometry(0.17, 0.36, 0.9, 6, 1, true), P(c.hakama));
  skirt.position.y = -0.45;
  hakama.add(skirt);
  const pleat = m(new THREE.ConeGeometry(0.16, 0.86, 3, 1, true), P(c.hakamaFold ?? c.hakama));
  pleat.rotation.x = Math.PI;
  pleat.position.set(0, -0.46, 0.2);
  pleat.scale.set(1, 1, 0.3);
  hakama.add(pleat);
  for (const x of [-0.1, 0.1]) {
    const foot = m(new THREE.BoxGeometry(0.08, 0.05, 0.2), P(c.foot ?? '#e8e1d2'));
    foot.position.set(x, -0.89, 0.08);
    hips.add(foot);
  }

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
    root, hips, torso, head, hakama, bandTail,
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
  sway: 0,
};

export function applyPose(f, p) {
  f.root.position.set(p.x, p.y, p.z);
  f.root.rotation.set(p.rx, p.ry, p.rz);
  f.torso.rotation.set(p.tx, p.ty, p.tz);
  f.head.rotation.set(p.hx, p.hy, 0);
  f.rS.rotation.set(p.rsx, 0, p.rsz);
  f.rE.rotation.x = p.rex;
  f.lS.rotation.set(p.lsx, 0, p.lsz);
  f.lE.rotation.x = p.lex;
  f.rH.rotation.x = p.rwx;
  f.lH.rotation.x = p.lwx;
  f.hakama.rotation.z = p.sway;
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

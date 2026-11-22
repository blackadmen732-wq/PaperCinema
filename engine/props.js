// Paper props: the original long sword, Musashi's oar-carved bokken, the boat.
// Units are metres. Swords are built along +x (blade toward +x),
// mune (back of blade) toward +y, edge toward -y. Origin = blade base (habaki).
import * as THREE from 'three';
import { paper, rng } from './paper.js';

const extrude = (shape, depth, bevel = 0, segs = 1) =>
  new THREE.ExtrudeGeometry(shape, {
    depth, bevelEnabled: bevel > 0, bevelThickness: bevel * 0.6,
    bevelSize: bevel, bevelSegments: segs, curveSegments: 6,
  }).translate(0, 0, -depth / 2);

function mesh(geo, mat, shadow = true) {
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = shadow;
  m.receiveShadow = shadow;
  return m;
}

/**
 * The film's original sword: "Shiokaze" — a paper interpretation of a
 * Momoyama/early-Edo long blade (the type tradition gives Kojirō).
 * See research/katana-design.md for every choice and its source.
 */
export function makeKatana(o = {}) {
  const L = o.nagasa ?? 0.91;       // ~3 shaku blade
  const sori = o.sori ?? 0.027;      // curvature
  const tsukaLen = o.tsukaLen ?? 0.33;
  const w0 = 0.033, w1 = 0.024;      // motohaba / sakihaba
  const yc = (u) => -4 * sori * u * (1 - u);
  const w = (u) => w0 + (w1 - w0) * u;
  const slope0 = Math.atan(-4 * sori / L);

  const mat = {
    blade: paper('#aeb3b9', { repeat: 30, rough: 0.42, metal: 0.45, bump: 0.25 }),
    hamon: paper('#f1eee6', { repeat: 30, rough: 0.35, metal: 0.15, bump: 0.2 }),
    copper: paper('#a9683a', { repeat: 40, rough: 0.5, metal: 0.55 }),
    iron: paper('#34302d', { repeat: 40, rough: 0.6, metal: 0.4 }),
    ito: paper('#17161b', { repeat: 40, rough: 0.95 }),
    same: paper('#e8e0cc', { repeat: 40 }),
    gold: paper('#c49a45', { repeat: 40, rough: 0.45, metal: 0.6 }),
    lacquer: paper('#141113', { repeat: 25, rough: 0.32, metal: 0.12, bump: 0.15 }),
    sageo: paper('#9e1f1c', { repeat: 40, rough: 0.85 }),
    horn: paper('#2a2522', { repeat: 40, rough: 0.5 }),
    ...(o.materials ?? {}),
  };

  // ---------- blade ----------
  const sword = new THREE.Group();
  sword.name = 'sword';
  const kissakiLen = 0.065;
  const uy = 1 - kissakiLen / L;
  const N = 48;
  const s = new THREE.Shape();
  s.moveTo(0, yc(0));
  s.lineTo(0, yc(0) - w(0));
  for (let i = 1; i <= N; i++) {
    const u = (i / N) * uy;
    s.lineTo(u * L, yc(u) - w(u));
  }
  const tip = new THREE.Vector2(L, yc(1) - w1 * 0.05);
  s.quadraticCurveTo(L - 0.004, yc(1) - w1 * 0.85, tip.x, tip.y);
  for (let i = N; i >= 0; i--) {
    const u = (i / N) * 0.995;
    s.lineTo(u * L, yc(u));
  }
  const blade = mesh(extrude(s, 0.005, 0.0022), mat.blade);
  sword.add(blade);

  // hamon: a white paper strip glued along the edge, wavy (notare/gunome) border
  const h = new THREE.Shape();
  const r = rng(11);
  const ph = r() * 6;
  const hamonH = (u) => w(u) * (0.3 + 0.07 * Math.sin(u * 46 + ph) + 0.04 * Math.sin(u * 103));
  h.moveTo(0.02 * L, yc(0.02) - w(0.02));
  for (let i = 1; i <= N; i++) {
    const u = 0.02 + (i / N) * (uy - 0.02);
    h.lineTo(u * L, yc(u) - w(u));
  }
  h.quadraticCurveTo(L - 0.006, yc(1) - w1 * 0.8, L - 0.008, yc(1) - w1 * 0.25);
  for (let i = N; i >= 0; i--) {
    const u = 0.02 + (i / N) * (uy - 0.02);
    h.lineTo(u * L, yc(u) - w(u) + hamonH(u));
  }
  const hg = new THREE.ShapeGeometry(h, 4);
  for (const side of [1, -1]) {
    const hm = mesh(hg, mat.hamon, false);
    hm.position.z = side * 0.0051;
    sword.add(hm);
  }

  // habaki (copper collar)
  const habaki = mesh(new THREE.BoxGeometry(0.03, w0 + 0.006, 0.012), mat.copper);
  habaki.position.set(0.015, -w0 / 2, 0);
  sword.add(habaki);

  // tsuba: round iron guard with wave (nami) openwork — original design
  const ts = new THREE.Shape();
  const R = 0.043;
  for (let i = 0; i <= 14; i++) {
    const a = (i / 14) * Math.PI * 2;
    const rr = R * (0.97 + 0.03 * Math.cos(a * 3));
    i === 0 ? ts.moveTo(Math.cos(a) * rr, Math.sin(a) * rr) : ts.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
  }
  const hole = (pts) => { const p = new THREE.Path(); pts.forEach((q, i) => (i ? p.lineTo(...q) : p.moveTo(...q))); p.closePath(); ts.holes.push(p); };
  // nakago-ana (tang hole), long along blade height
  hole([[0, 0.016], [0.004, 0.006], [0.004, -0.016], [-0.004, -0.016], [-0.004, 0.006]]);
  // kogai / kozuka hitsu-ana
  hole([[0.013, 0.012], [0.019, 0.006], [0.019, -0.006], [0.013, -0.012]]);
  hole([[-0.013, 0.008], [-0.018, 0.004], [-0.018, -0.008], [-0.013, -0.01]]);
  // wave curls
  for (const [cx, cy, sgn] of [[0.026, 0.024, 1], [-0.026, -0.024, -1], [-0.025, 0.026, 1], [0.025, -0.026, -1]]) {
    const pts = [];
    for (let k = 0; k <= 6; k++) {
      const a = sgn * (k / 6) * Math.PI * 1.3;
      const rr = 0.007 * (1 - k / 9);
      pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]);
    }
    pts.push([cx, cy]);
    hole(pts);
  }
  const tsuba = mesh(extrude(ts, 0.0055, 0.0012), mat.iron);
  tsuba.rotation.y = Math.PI / 2;
  tsuba.position.set(-0.003, -w0 / 2, 0);
  sword.add(tsuba);

  // tsuka (handle) continues the curve backwards
  const tsuka = new THREE.Group();
  tsuka.rotation.z = slope0; // slope0 < 0 → kashira end tilts up, continuing the curve
  tsuka.position.set(-0.006, -w0 / 2, 0);
  sword.add(tsuka);
  const fuchi = mesh(new THREE.BoxGeometry(0.022, 0.036, 0.027), mat.iron);
  fuchi.position.x = -0.011;
  tsuka.add(fuchi);
  const coreLen = tsukaLen - 0.045;
  const core = mesh(new THREE.BoxGeometry(coreLen, 0.032, 0.025), mat.ito);
  core.position.x = -0.022 - coreLen / 2;
  tsuka.add(core);
  // samegawa diamonds showing through the black ito wrap
  const dia = new THREE.Shape();
  dia.moveTo(-0.012, 0); dia.lineTo(0, 0.009); dia.lineTo(0.012, 0); dia.lineTo(0, -0.009); dia.closePath();
  const dg = new THREE.ShapeGeometry(dia);
  const nD = 9;
  for (let i = 0; i < nD; i++) {
    for (const side of [1, -1]) {
      const d = mesh(dg, mat.same, false);
      d.position.set(-0.035 - i * (coreLen - 0.02) / nD, 0, side * 0.0128);
      tsuka.add(d);
    }
    // raised ito crossings on top/bottom edges
    const x = mesh(new THREE.BoxGeometry(0.01, 0.034, 0.027), mat.ito);
    x.position.x = -0.029 - i * (coreLen - 0.02) / nD;
    x.rotation.x = 0.25;
    tsuka.add(x);
  }
  // menuki (gold ornaments under the wrap)
  for (const side of [1, -1]) {
    const mk = mesh(new THREE.DodecahedronGeometry(0.0065), mat.gold, false);
    mk.scale.set(1.8, 0.8, 0.6);
    mk.position.set(-0.03 - coreLen * (side > 0 ? 0.35 : 0.55), side * 0.004, side * 0.0135);
    tsuka.add(mk);
  }
  const kashira = mesh(new THREE.BoxGeometry(0.02, 0.034, 0.027), mat.iron);
  kashira.position.x = -tsukaLen + 0.01;
  tsuka.add(kashira);

  // ---------- saya (scabbard), black lacquer ----------
  const saya = new THREE.Group();
  saya.name = 'saya';
  const sl = L * 1.04;
  const ss = new THREE.Shape();
  const M = 40;
  ss.moveTo(0, yc(0) + 0.007);
  ss.lineTo(0, yc(0) - w0 - 0.008);
  for (let i = 1; i <= M; i++) {
    const u = i / M;
    ss.lineTo(u * sl, yc(Math.min(u, 1)) - w(Math.min(u, 1)) - 0.008 + (u > 0.97 ? (u - 0.97) * 0.3 : 0));
  }
  ss.quadraticCurveTo(sl + 0.01, yc(1) - w1 * 0.4, sl, yc(1) + 0.007);
  for (let i = M; i >= 0; i--) {
    const u = i / M;
    ss.lineTo(u * sl, yc(Math.min(u, 1)) + 0.007);
  }
  saya.add(mesh(extrude(ss, 0.02, 0.004), mat.lacquer));
  const koiguchi = mesh(new THREE.BoxGeometry(0.018, w0 + 0.026, 0.03), mat.horn);
  koiguchi.position.set(0.009, -w0 / 2, 0);
  saya.add(koiguchi);
  const kojiri = mesh(new THREE.BoxGeometry(0.03, w1 + 0.022, 0.03), mat.iron);
  kojiri.position.set(sl - 0.012, yc(1) - w1 / 2 + 0.002, 0);
  saya.add(kojiri);
  const kurikata = mesh(new THREE.BoxGeometry(0.022, 0.012, 0.01), mat.horn);
  kurikata.position.set(0.11, yc(0.12) - w0 - 0.008, 0.012);
  saya.add(kurikata);
  const sageoPts = [
    [0.11, -0.05, 0.016], [0.07, -0.12, 0.028], [0.13, -0.21, 0.03],
    [0.22, -0.16, 0.024], [0.28, -0.08, 0.016], [0.33, -0.06, 0.014],
  ].map((p) => new THREE.Vector3(...p));
  const sageo = mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(sageoPts), 40, 0.0045, 5), mat.sageo);
  saya.add(sageo);

  return { sword, saya, length: L, tsukaLen };
}

/** Musashi's wooden sword, traditionally carved from a spare boat oar (~110 cm). */
export function makeBokken() {
  const g = new THREE.Group();
  const total = 1.12, grip = 0.32, L = total - grip;
  const sori = 0.02;
  const yc = (x) => -4 * sori * ((x + grip) / total) * (1 - (x + grip) / total);
  const s = new THREE.Shape();
  const pts = 20;
  s.moveTo(-grip, yc(-grip));
  for (let i = 0; i <= pts; i++) { const x = -grip + (i / pts) * total; s.lineTo(x, yc(x) - (x < 0 ? 0.03 : 0.036 - 0.01 * (x / L))); }
  s.lineTo(L + 0.01, yc(L) - 0.012);
  for (let i = pts; i >= 0; i--) { const x = -grip + (i / pts) * total; s.lineTo(x, yc(x)); }
  const wood = paper('#9a7550', { repeat: 25, rough: 0.95 });
  const m = mesh(extrude(s, 0.03, 0.005), wood);
  m.position.y = 0.017;
  g.add(m);
  return g;
}

/** Small Japanese rowing boat (kobune) folded from paper. */
export function makeBoat() {
  const g = new THREE.Group();
  const wood = paper('#7a6047', { repeat: 4 });
  const dark = paper('#4b3a2b', { repeat: 4 });
  const side = new THREE.Shape();
  side.moveTo(-1.6, 0.35); side.lineTo(-1.25, 0); side.lineTo(1.2, 0); side.lineTo(1.5, 0.3);
  side.lineTo(1.5, 0.36); side.lineTo(-1.6, 0.42); side.closePath();
  for (const x of [-0.42, 0.42]) {
    const m = mesh(extrude(side, 0.04), wood);
    m.rotation.y = Math.PI / 2;
    m.position.x = x;
    m.rotation.z = x > 0 ? -0.12 : 0.12;
    g.add(m);
  }
  const floor = mesh(new THREE.BoxGeometry(0.78, 0.04, 2.5), dark);
  floor.position.y = 0.04;
  g.add(floor);
  const bow = mesh(new THREE.BoxGeometry(0.9, 0.38, 0.05), wood);
  bow.position.set(0, 0.2, -1.42); bow.rotation.x = 0.5;
  g.add(bow);
  const stern = mesh(new THREE.BoxGeometry(0.9, 0.3, 0.05), wood);
  stern.position.set(0, 0.18, 1.32); stern.rotation.x = -0.4;
  g.add(stern);
  return g;
}

export function makeOar() {
  const g = new THREE.Group();
  const wood = paper('#8b6a48', { repeat: 20 });
  const shaft = mesh(new THREE.BoxGeometry(0.035, 0.035, 2.2), wood);
  g.add(shaft);
  const blade = mesh(new THREE.BoxGeometry(0.12, 0.015, 0.6), wood);
  blade.position.z = 1.2;
  g.add(blade);
  return g;
}

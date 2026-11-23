// MOTION TEST page: one hero, one opponent, the upgraded skeleton and the anime motion layer.
//   node engine/render.mjs --page engine/motion.html --film film/motion-test.json
// Everything is a pure function of time, so any frame renders on its own (window.renderAt(t)).
//
// What happens here, in order, every frame:
//   1. BODY TIME: hit-stops freeze the fighters (not the camera, sparks or sound) at each blade contact.
//   2. POSE: keyed motion (+ follow-through lag, snap easing, overshoot) + breathing + eyes on the
//      opponent; the left hand finds the handle with analytic arm IK.
//   3. EVENTS (computed once at load): blade-to-blade contact found by segment distance at 240 Hz,
//      whooshes from tip speed, scrapes from sliding contact → window.EVENTS (sound cues).
//   4. CAMERA (computed once at load): rigs aim at real joints (eyes, elbow, wrist, tsuba), then a
//      spring smooths the path at 240 Hz; impacts add a punch, shake and roll.
//   5. EFFECTS: smear ribbon behind the blade tip, sparks, one-frame ink impact frame.
import * as THREE from 'three';
import { paper } from './paper.js';
import { buildWorld } from './world.js';
import { expandMoves } from './moves.js';
import { makeKatana } from './props.js';
import { loadCharacter } from './library.js';
import { makeFigure, holdInHand, applyPose, makeMotion, resolveKeys, windowWeight, solveArm, smooth } from './figure.js';
import { loadVoice } from './voice-env.js';
import * as combat from './combat.js';
import { clamp, bladeSeg, closestSegSeg, RATE } from './combat.js';
import { createFX, fxAt } from './fx.js';

const params = new URLSearchParams(location.search);
const film = await (await fetch(params.get('film') ?? '/film/motion-test.json')).json();
const VERTICAL = params.get('aspect') === 'vertical' || (film.format === 'vertical' && params.get('aspect') !== 'horizontal');
const W = VERTICAL ? 720 : film.width, H = VERTICAL ? 1280 : film.height;
const FPS = film.fps, DUR = film.duration;
const FILM_NAME = (params.get('film') ?? '/film/motion-test.json').split('/').pop().replace('.json', '');
const VOICE = film.voice ? await loadVoice(FILM_NAME) : null;   // spoken lines → eyes pulse (docs/VOICE.md)
let FILM_TIME = 0;                                                // film time of the frame being drawn (voice does not freeze in hit-stop)

const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('c'), antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.getElementById('stage').style.width = W + 'px';
document.getElementById('stage').style.height = H + 'px';

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(36, W / H, 0.02, 600);
const world = buildWorld(scene);
world.setMode(film.mode ?? 'dawn');

// ---------- cast ----------
const POSES = await (await fetch('/library/poses.json')).json();
const MOVES = await (await fetch('/library/moves.json')).json();
const cast = {};
for (const [id, c] of Object.entries(film.cast)) {
  const preset = await loadCharacter(c.character);
  const fig = makeFigure({ ...preset.colors, ...preset.accessories, band: preset.accessories.band ?? undefined,
    haori: preset.accessories.haori ?? undefined, face: c.face });
  scene.add(fig.root);
  const k = makeKatana();
  holdInHand(fig.rH, k.sword, -0.06);
  const perf = film.performances[id];
  const motion = makeMotion(resolveKeys(expandMoves(perf.keys, MOVES), POSES), film.motion ?? {});
  if (c.hidden) fig.root.visible = false;               // an invisible target (e.g. the tree) the hero looks at
  cast[id] = { id, fig, sword: k.sword, bladeLen: k.length, motion, perf, hidden: !!c.hidden, phase: Object.keys(cast).length * 1.7 };
}
const ids = Object.keys(cast);
const other = (id) => cast[ids.find((x) => x !== id)];

// ---------- posing at a body time ----------
const _v = new THREE.Vector3(), _w = new THREE.Vector3();
function poseOf(c, tb) {
  const p = c.motion(tb);
  // moving hold: slow breath in the chest, a 4 mm circle at the tip — nothing is ever perfectly still
  p.cx += 0.012 * Math.sin(tb * 2 * Math.PI * 0.3 + c.phase);
  p.rwz += 0.006 * Math.sin(tb * 2 * Math.PI * 0.7 + c.phase);
  p.rwx += 0.006 * Math.cos(tb * 2 * Math.PI * 0.7 + c.phase);
  combat.applyEyes(c, p, tb, FILM_TIME, { fps: FPS, voice: VOICE, contacts: CONTACTS });
  // eyes on the opponent: neck takes 40% of the turn, head 60%
  const o = other(c.id).motion(tb);
  let yaw = Math.atan2(o.x - p.x, o.z - p.z) - p.ry - p.ty - p.cy;
  yaw = Math.max(-0.7, Math.min(0.7, Math.atan2(Math.sin(yaw), Math.cos(yaw))));
  p.ny += 0.4 * yaw;
  p.hy += 0.6 * yaw;
  return p;
}
// CLASH AIM, EYES, blade segments, contacts, hit-stop, cues, ribbon, sparks, impact frame: engine/combat.js
let CONTACTS = null;                                              // set after the contact analysis (auto eye states)
function poseAll(tb) {
  for (const c of Object.values(cast)) { applyPose(c.fig, poseOf(c, tb)); c.sword.quaternion.identity(); }
  combat.clashAim(film.clashes, cast, tb);
  for (const c of Object.values(cast)) {
    c.fig.root.updateMatrixWorld(true);
    // two-hand grip: the left hand closes on the handle, 27 cm behind the guard
    const w = windowWeight(c.perf.twoHand, tb);
    if (w > 0) solveArm(c.fig, 'l', c.sword.localToWorld(_v.set(-0.27, -0.018, 0)).clone(), null, w);
    c.fig.root.updateMatrixWorld(true);
  }
}

// ---------- 3. EVENTS: contacts, whooshes, scrapes (in body time, 240 Hz) → window.EVENTS ----------
const hero = cast[ids[0]], foe = cast[ids[1]];
console.log('[motion] cast ready, analysing', performance.now() | 0);
const C = combat.analyse({ film, fighters: [hero, foe], pose: poseAll, fps: FPS, dur: DUR, armed: hero.hidden || foe.hidden ? () => false : null });
const { contacts, stops, bodyT } = C;
CONTACTS = contacts;
window.EVENTS = C.events;

// ---------- PROPS: cuttable paper trees (film.props.trees) ----------
// { id, x, z, height, color, cut: { t, y, tilt, delay, dir }, split: { t } }
//   cut: the blade passes at t; a thin glowing seam shows, then after "delay" the top slides along the cut and
//   topples over (heavy, slow, anime timing); split: the falling top is cut again in the air and flies apart.
const TREES = (film.props?.trees ?? []).map((tr) => makeTree(tr));
// authored impacts: { t, intensity, at: "<tree id>" | [x,y,z], ink, sparks } → camera punch, paper chips, ink frame
const IMPACTS = (film.impacts ?? []).map((i) => {
  const tr = TREES.find((x) => x.tr.id === i.at);
  const p = Array.isArray(i.at) ? i.at : tr ? tr.point().toArray() : [0, 1, 0];
  return { intensity: 0.6, ...i, point: p };
});
function makeTree(tr) {
  const P = (hex, o = {}) => paper(hex, { repeat: 4, ...o });
  const root = new THREE.Group(); root.position.set(tr.x, 0, tr.z); scene.add(root);
  const H = tr.height ?? 3.2, cy = tr.cut?.y ?? 1.1, trunkR = 0.16;
  const mk = (g, m) => { const o = new THREE.Mesh(g, m); o.castShadow = o.receiveShadow = true; return o; };
  const base = mk(new THREE.CylinderGeometry(trunkR * 0.95, trunkR * 1.2, cy, 6), P('#4a3426'));
  base.position.y = cy / 2; root.add(base);
  const top = new THREE.Group(); top.position.y = cy; root.add(top);           // pivot at the cut
  const halves = [-1, 1].map((sgn) => { const h = new THREE.Group(); top.add(h); return h; });
  const sc = tr.crown ?? 0.7;   // crown size
  const tiers = [[0.5, 1.15, 0.9], [0.95, 0.95, 0.85], [1.35, 0.72, 0.75], [1.7, 0.45, 0.6]].map(([y, r, h]) => [y, r * sc, h * sc]);
  const col = tr.color ?? '#e9a3b4';
  halves.forEach((h, k) => {
    const trunk = mk(new THREE.CylinderGeometry(trunkR * 0.7, trunkR * 0.95, H - cy, 6, 1, false, k * Math.PI, Math.PI), P('#4a3426'));
    trunk.position.y = (H - cy) / 2; h.add(trunk);
    for (const [y, r, hh] of tiers) {
      const cone = mk(new THREE.ConeGeometry(r, hh, 9, 1, false, k * Math.PI, Math.PI), P(col, { glow: 0.08 }));
      cone.position.y = y + (H - cy - 2.0); h.add(cone);
    }
  });
  const seam = new THREE.Mesh(new THREE.TorusGeometry(trunkR * 1.02, 0.008, 4, 16), paper('#ffd9a0', { glow: 3, fog: false }));
  seam.rotation.x = Math.PI / 2; seam.position.y = cy; seam.visible = false; root.add(seam);
  const dir = new THREE.Vector3(...(tr.cut?.dir ?? [0, 0, 1])).normalize();     // where the top slides and falls
  const axis = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), dir).normalize();
  const tilt = ((tr.cut?.tilt ?? 10) * Math.PI) / 180;
  return {
    tr, root, top, halves,
    point: () => new THREE.Vector3(tr.x, cy, tr.z),
    update(t) {
      top.position.set(0, cy, 0); top.quaternion.identity(); halves.forEach((h) => { h.position.set(0, 0, 0); h.rotation.set(0, 0, 0); });
      seam.visible = false;
      if (!tr.cut || t < tr.cut.t) return;
      const tau = t - tr.cut.t, d = tr.cut.delay ?? 0.45;
      seam.visible = tau < d + 0.3; seam.material.emissiveIntensity = 3 * Math.max(0, 1 - tau / (d + 0.3));
      if (tau < d) { top.position.y = cy + 0.003 * Math.sin(tau * 120); return; }   // the cut has happened; nothing moves yet
      const u = tau - d;
      const slide = Math.min(0.25, 0.9 * u * u);                                      // slides along the tilted cut
      const topple = (Math.PI / 2) * Math.min(1, Math.pow(Math.max(0, u - 0.15) / (tr.cut.fall ?? 1.6), 2));   // tips over, slowly then fast
      top.position.addScaledVector(dir, slide).y -= Math.tan(tilt) * slide;
      top.quaternion.setFromAxisAngle(axis, topple);
      const ground = Math.max(0, topple - 1.1) * 0.9;                                 // the top drops as it lies down
      top.position.y = Math.max(0.15, top.position.y - ground);
      if (tr.split && t >= tr.split.t) {                                              // cut again in the air: halves fly apart
        const v = t - tr.split.t;
        halves.forEach((h, k) => {
          const sg = k ? 1 : -1;
          h.position.set(sg * (1.6 * v), -2.5 * v * v, 0.4 * v);
          h.rotation.set(sg * 1.2 * v, 0, sg * 2.2 * v);
        });
      }
    },
  };
}

// ---------- 4. CAMERA: rigs aim at real joints, then a spring smooths it ----------
const FEELS = { locked: [6, 1], dolly: [1.8, 1], crane: [0.7, 1.1], handheld: [2.5, 0.7], torpedo: [4, 0.62] };
const BEATS = film.camera;
const beatAt = (t) => { let b = BEATS[0]; for (const x of BEATS) if (t >= x.t) b = x; return b; };
const worldOf = (o, x = 0, y = 0, z = 0) => o.localToWorld(new THREE.Vector3(x, y, z));
function joint(c, name) {
  const f = c.fig;
  switch (name) {
    case 'eyes': return worldOf(f.head, 0, 0.11, 0.06);
    case 'shoulder': return worldOf(f.rS);
    case 'elbow': return worldOf(f.rE);
    case 'wrist': return worldOf(f.rH);
    case 'tsuba': return worldOf(c.sword, 0.0, -0.012, 0);
    case 'tip': return worldOf(c.sword, c.bladeLen, -0.012, 0);
    case 'hips': return worldOf(f.hips);
    case 'head': return worldOf(f.head, 0, 0.1, 0);
  }
  throw new Error('unknown joint ' + name);
}
const UP = new THREE.Vector3(0, 1, 0);
function rigTarget(b, t, tb) {
  const vfov = b.fov ?? 36;
  if (b.rig === 'face') {
    const c = cast[b.who], eye = joint(c, 'eyes');
    const fwd = new THREE.Vector3(0, 0, 1).applyQuaternion(c.fig.head.getWorldQuaternion(new THREE.Quaternion())).setY(0).normalize();
    fwd.applyAxisAngle(UP, (b.angle ?? 0) * Math.PI / 180);
    const pos = eye.clone().addScaledVector(fwd, b.dist ?? 0.45).add(new THREE.Vector3(0, b.lift ?? 0, 0));
    return { pos, look: eye.clone().add(new THREE.Vector3(0, -0.01, 0)), fov: vfov };
  }
  if (b.rig === 'slide') {
    const c = cast[b.who];
    const pts = b.path.map((n) => joint(c, n));
    const lens = [0]; for (let i = 1; i < pts.length; i++) lens.push(lens[i - 1] + pts[i].distanceTo(pts[i - 1]));
    const u = smooth(clamp((t - b.t) / ((b.until ?? b.t + 1) - b.t), 0, 1)) * lens[lens.length - 1];
    const at = (L) => { let i = 1; while (i < pts.length - 1 && lens[i] < L) i++; const k = clamp((L - lens[i - 1]) / (lens[i] - lens[i - 1] || 1), 0, 1); return pts[i - 1].clone().lerp(pts[i], k); };
    const p = at(u), ahead = at(Math.min(lens[lens.length - 1], u + 0.08));
    // to the hero's right and a little in front, slightly above
    const rq = c.fig.root.getWorldQuaternion(new THREE.Quaternion());
    const right = new THREE.Vector3(-1, 0, 0).applyQuaternion(rq), fwd = new THREE.Vector3(0, 0, 1).applyQuaternion(rq);
    const [wr, wu, wf] = b.from ?? [0.75, 0.12, 0.62];   // where the camera sits: weights for right / up / front of the fighter
    const off = right.multiplyScalar(wr).addScaledVector(fwd, wf).add(new THREE.Vector3(0, wu, 0)).normalize().multiplyScalar(b.offset ?? 0.4);
    return { pos: p.clone().add(off), look: ahead, fov: vfov };
  }
  const subIds = b.subjects ?? ids;
  const hipsOf = (id) => { const tr = TREES.find((x) => x.tr.id === id); return tr ? tr.root.position.clone().setY(0.95) : joint(cast[id], 'hips'); };
  const subs = subIds.map((id) => cast[id] ?? { id });
  const center = subIds.reduce((s, id) => s.add(hipsOf(id)), new THREE.Vector3()).multiplyScalar(1 / subIds.length);
  if (b.rig === 'orbit') {
    const a = ((b.deg0 + ((b.deg1 ?? b.deg0) - b.deg0) * smooth(clamp((t - b.t) / ((b.until ?? DUR) - b.t), 0, 1))) * Math.PI) / 180;
    // follow: the look point rides with the subject (jumps), camY = camera height relative to it (negative = looking up)
    const look = b.follow ? center.clone().add(new THREE.Vector3(0, b.lookUp ?? 0.35, 0)) : center.clone().setY(b.height ?? 1.1);
    const camY = b.follow ? (b.camY ?? 0) : 0.15;
    const pos = look.clone().add(new THREE.Vector3(Math.sin(a) * b.radius, camY, Math.cos(a) * b.radius));
    pos.y = Math.max(0.12, pos.y);                                                    // never under the ground
    return { pos, look, fov: vfov };
  }
  // frame: both fighters, seen from "angle" degrees off the side view (0 = side-on, 90 = behind the hero)
  const axis = hipsOf(subIds[subIds.length - 1]).sub(hipsOf(subIds[0])).setY(0);
  const sep = axis.length(); axis.normalize();
  const sideDir = new THREE.Vector3().crossVectors(UP, axis).normalize();   // points to one side of the duel line
  const a = (b.angle ?? 30) * Math.PI / 180;
  const dir = sideDir.clone().multiplyScalar(Math.cos(a)).addScaledVector(axis, -Math.sin(a)).normalize();
  const full = (b.size ?? 'full') === 'full';
  const halfH = full ? 1.05 : 0.62, halfW = (sep * Math.cos(a)) / 2 + (full ? 0.6 : 0.4);
  const tv = Math.tan((vfov * Math.PI) / 360), th = tv * (W / H);
  const dist = Math.max(halfH / tv, halfW / th) * 1.05;
  const look = center.clone().setY((full ? 1.0 : 1.4) + (b.lookUp ?? 0));
  const e = (b.elev ?? 0) * Math.PI / 180;
  const pos = look.clone().addScaledVector(dir, dist * Math.cos(e)).add(new THREE.Vector3(0, dist * Math.sin(e), 0));
  pos.y = Math.max(0.25, pos.y);                                                     // never under the sand
  return { pos, look, fov: vfov };
}
// integrate the spring at 240 Hz with a 1 s pre-roll; the look point is 1.5x stiffer than the body
console.log('[motion] analysis done, camera', performance.now() | 0);
const camPath = [];
{
  let pos = null, look = null, fov = 0;
  const vp = new THREE.Vector3(), vl = new THREE.Vector3(); let vf = 0;
  const step = (x, v, target, f, z, dt) => {             // critically/under-damped spring, semi-implicit Euler
    const w = 2 * Math.PI * f;
    v.addScaledVector(target.clone().sub(x), w * w * dt).multiplyScalar(1 / (1 + 2 * z * w * dt));
    x.addScaledVector(v, dt);
  };
  for (let i = -RATE; i <= DUR * RATE; i++) {
    const t = Math.max(0, i / RATE), tb = bodyT(t);
    poseAll(tb);
    const b = beatAt(t), tg = rigTarget(b, t, tb);
    const [f, z] = FEELS[b.feel ?? 'dolly'];
    if (!pos) { pos = tg.pos.clone(); look = tg.look.clone(); fov = tg.fov; }
    const dt = 1 / RATE;
    step(pos, vp, tg.pos, f, z, dt);
    step(look, vl, tg.look, f * 1.5, Math.max(z, 0.8), dt);
    const w = 2 * Math.PI * f; vf = (vf + (tg.fov - fov) * w * w * dt) / (1 + 2 * z * w * dt); fov += vf * dt;
    if (b.feel === 'handheld') {                          // a breathing operator: smooth low-frequency drift
      const n = (s) => Math.sin(t * 1.7 + s) * 0.6 + Math.sin(t * 3.1 + s * 2) * 0.4;
      pos.x += n(1) * 0.0006; pos.y += n(2) * 0.0005;
    }
    if (i >= 0) camPath.push({ pos: pos.clone(), look: look.clone(), fov });
  }
}
function placeCamera(t) {
  const x = clamp(t * RATE, 0, camPath.length - 1), i = Math.floor(x), k = x - i, a = camPath[i], b = camPath[Math.min(i + 1, camPath.length - 1)];
  camera.position.copy(a.pos).lerp(b.pos, k);
  const look = a.look.clone().lerp(b.look, k);
  const { fov, roll } = combat.punch([...contacts, ...IMPACTS], t, camera, a.fov + (b.fov - a.fov) * k);   // impact punch: fov kick, shake, roll
  camera.fov = fov;
  camera.updateProjectionMatrix();
  camera.up.set(0, 1, 0);
  camera.lookAt(look);
  camera.rotateZ((roll * Math.PI) / 180);
}

// ---------- 5. EFFECTS: smear ribbon, sparks (engine/combat.js); post FX (engine/fx.js) when the film has fxBase / fx ----------
const SPARKS2 = combat.makeSparks(scene, camera, IMPACTS.filter((i) => i.sparks !== false));
const RIB = combat.makeRibbons(scene, Object.values(cast), { ribbon: film.effects?.ribbon, fps: FPS, pose: poseAll, tipSpeedAt: C.tipSpeedAt });
const ribbons = RIB.meshes;
const SPARKS = combat.makeSparks(scene, camera, contacts);
const FX = film.fxBase || film.fx ? createFX(renderer, scene, camera, { width: W, height: H, seed: 7, fps: FPS }) : null;
const FX_TRACK = FX ? [...(film.fx ?? []), ...combat.contactFx(contacts, film.effects?.contactFx)] : [];

// ---------- frame ----------
const flashEl = document.getElementById('flash'), fadeEl = document.getElementById('fade');
window.renderAt = (t) => {
  FILM_TIME = t;
  world.update(t);
  const tb = bodyT(t);
  poseAll(tb);
  // hit-stop jitter: during a stop the fighters shiver ±6 mm in opposite directions on alternate frames
  const inStop = stops.find((s) => t >= s.t && t < s.t + s.d);
  if (inStop) {
    const sgn = Math.round(t * FPS) % 2 ? 1 : -1;
    hero.fig.root.position.z += 0.006 * sgn; foe.fig.root.position.z -= 0.006 * sgn;
    for (const c of Object.values(cast)) c.fig.root.updateMatrixWorld(true);
  }
  placeCamera(t);
  const impactFrame = combat.isImpactFrame(film, contacts, t, FPS) || IMPACTS.some((i) => i.ink && t >= i.t && t < i.t + 1 / FPS);
  RIB.update(tb, impactFrame);
  if (inStop) { hero.fig.root.updateMatrixWorld(true); }
  for (const tr of TREES) tr.update(t);
  const fl = Math.max(SPARKS.update(t), SPARKS2.update(t));  // sparks + flash light
  flashEl.style.opacity = impactFrame ? 0 : Math.min(0.35, fl * 0.3);
  fadeEl.style.opacity = clamp(Math.max(1 - t / 0.6, (t - (DUR - 0.6)) / 0.6), 0, 1);
  if (impactFrame) {
    combat.renderInkFrame(renderer, scene, camera, [...Object.values(cast).filter((c) => !c.hidden).map((c) => c.fig.root), ...TREES.map((x) => x.root)], ribbons);
    return;
  }
  if (FX) FX.render(t, fxAt(t, FX_TRACK, film.fxBase, FPS));
  else renderer.render(scene, camera);
};

window.cam = (t) => { const x = clamp(Math.round(t * RATE), 0, camPath.length - 1); const c = camPath[x]; return { pos: c.pos.toArray(), look: c.look.toArray(), fov: c.fov }; };
window.tryPose = (id, pose) => { applyPose(cast[id].fig, { ...cast[id].motion(0), ...pose }); cast[id].fig.root.updateMatrixWorld(true); const s = bladeSeg(cast[id]); return { tip: s.tip.toArray().map((v) => +v.toFixed(2)), guard: s.guard.toArray().map((v) => +v.toFixed(2)) }; };
window.probe = (tb) => {
  poseAll(tb);
  const r = {};
  for (const id of ids) { const s = bladeSeg(cast[id]); r[id] = { tip: s.tip.toArray().map((v) => +v.toFixed(3)), guard: s.guard.toArray().map((v) => +v.toFixed(3)), eyes: joint(cast[id], 'eyes').toArray().map((v) => +v.toFixed(3)) }; }
  const A = bladeSeg(hero), B = bladeSeg(foe);
  r.d = +closestSegSeg(A.a, A.tip, B.a, B.tip).d.toFixed(3);
  return r;
};
await document.fonts.ready;
window.FILM = film;
window.READY = true;
console.log('[motion] ready', performance.now() | 0);
if (!params.has('render')) {
  if (params.has('t')) window.renderAt(parseFloat(params.get('t')));
  else { const t0 = performance.now(); const loop = () => { window.renderAt(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); }
}

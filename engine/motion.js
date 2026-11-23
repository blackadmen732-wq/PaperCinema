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
import { buildWorld } from './world.js';
import { expandMoves } from './moves.js';
import { makeKatana } from './props.js';
import { loadCharacter } from './library.js';
import { makeFigure, holdInHand, applyPose, makeMotion, resolveKeys, windowWeight, solveArm, smooth } from './figure.js';
import { paper, rng } from './paper.js';

const params = new URLSearchParams(location.search);
const film = await (await fetch(params.get('film') ?? '/film/motion-test.json')).json();
const VERTICAL = params.get('aspect') === 'vertical' || (film.format === 'vertical' && params.get('aspect') !== 'horizontal');
const W = VERTICAL ? 720 : film.width, H = VERTICAL ? 1280 : film.height;
const FPS = film.fps, DUR = film.duration;

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
  cast[id] = { id, fig, sword: k.sword, bladeLen: k.length, motion, perf, phase: Object.keys(cast).length * 1.7 };
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
  const e = eyesAt(c, tb);
  p.lid = Math.max(p.lid, e.lid);
  if (c.fig.eyeMat) c.fig.eyeMat.emissiveIntensity = e.g * (1 - 0.8 * p.lid);
  // eyes on the opponent: neck takes 40% of the turn, head 60%
  const o = other(c.id).motion(tb);
  let yaw = Math.atan2(o.x - p.x, o.z - p.z) - p.ry - p.ty - p.cy;
  yaw = Math.max(-0.7, Math.min(0.7, Math.atan2(Math.sin(yaw), Math.cos(yaw))));
  p.ny += 0.4 * yaw;
  p.hy += 0.6 * yaw;
  return p;
}
// CLASH AIM: inside a film "clashes" window the defender's wrist turns the blade (pivoting at the guard,
// at most 35°) so it lies across the attacker's blade at fraction s of its length. The blades meet on
// the planned frame and stay crossed through a bind, instead of hoping two keyed arcs intersect.
const _qa = new THREE.Quaternion(), _qw = new THREE.Quaternion(), _qi = new THREE.Quaternion();
function clashAim(tb) {
  for (const cl of film.clashes ?? []) {
    const ramp = cl.ramp ?? 0.1;
    const w = smooth(clamp((tb - (cl.t - ramp)) / ramp, 0, 1)) * (1 - smooth(clamp((tb - (cl.until ?? cl.t + 0.2)) / 0.15, 0, 1)));
    if (w <= 0) continue;
    const att = cast[cl.attacker], def = cast[cl.defender];
    att.fig.root.updateMatrixWorld(true); def.fig.root.updateMatrixWorld(true);
    const P = att.sword.localToWorld(new THREE.Vector3(att.bladeLen * (cl.s ?? 0.6), -0.012, 0));
    const g = def.sword.localToWorld(new THREE.Vector3(0, -0.012, 0)), tip = def.sword.localToWorld(new THREE.Vector3(def.bladeLen, -0.012, 0));
    const cur = tip.sub(g).normalize(), want = P.sub(g).normalize();
    _qa.setFromUnitVectors(cur, want);
    const ang = 2 * Math.acos(clamp(_qa.w, -1, 1)), maxA = ((cl.maxDeg ?? 35) * Math.PI) / 180;
    _qw.identity().slerp(_qa, w * Math.min(1, maxA / Math.max(ang, 1e-6)));
    def.sword.parent.getWorldQuaternion(_qi);
    const local = _qi.clone().invert().multiply(_qw).multiply(_qi);
    def.sword.quaternion.premultiply(local);
    def.fig.root.updateMatrixWorld(true);
  }
}
// EYES: glow follows a per-performance "eyes" list [[t, glow], ...] (idle 0.9, focus 1.4, anticipation 2.2,
// decide 3.5, struck 0.4), plus a blink (2 frames shut, 1 hold, 3 open) at each time in "blinks".
function eyesAt(c, tb) {
  const ks = c.perf.eyes ?? [[0, 1.2]];
  let g = ks[0][1];
  for (let i = 0; i < ks.length; i++) {
    if (tb >= ks[i][0]) g = ks[i][1];
    if (i < ks.length - 1 && tb >= ks[i][0] && tb < ks[i + 1][0]) {
      const k = (tb - ks[i][0]) / (ks[i + 1][0] - ks[i][0]);
      g = ks[i][1] + (ks[i + 1][1] - ks[i][1]) * k;
    }
  }
  let lid = 0;
  for (const b of c.perf.blinks ?? []) {
    const f = (tb - b) * FPS;
    if (f >= 0 && f < 6) lid = Math.max(lid, f < 2 ? f / 2 : f < 3 ? 1 : 1 - (f - 3) / 3);
  }
  return { g, lid };
}
function poseAll(tb) {
  for (const c of Object.values(cast)) { applyPose(c.fig, poseOf(c, tb)); c.sword.quaternion.identity(); }
  clashAim(tb);
  for (const c of Object.values(cast)) {
    c.fig.root.updateMatrixWorld(true);
    // two-hand grip: the left hand closes on the handle, 27 cm behind the guard
    const w = windowWeight(c.perf.twoHand, tb);
    if (w > 0) solveArm(c.fig, 'l', c.sword.localToWorld(_v.set(-0.27, -0.018, 0)).clone(), null, w);
    c.fig.root.updateMatrixWorld(true);
  }
}
// blade segment in world space: from 20% up the blade to the tip (the part that can touch)
function bladeSeg(c, out = {}) {
  out.a = c.sword.localToWorld(new THREE.Vector3(c.bladeLen * 0.2, -0.012, 0));
  out.tip = c.sword.localToWorld(new THREE.Vector3(c.bladeLen, -0.012, 0));
  out.mid = c.sword.localToWorld(new THREE.Vector3(c.bladeLen * 0.55, -0.012, 0));
  out.guard = c.sword.localToWorld(new THREE.Vector3(0, -0.012, 0));
  return out;
}
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
function closestSegSeg(p1, q1, p2, q2) {
  const d1 = q1.clone().sub(p1), d2 = q2.clone().sub(p2), r = p1.clone().sub(p2);
  const a = d1.dot(d1), e = d2.dot(d2), f = d2.dot(r), c = d1.dot(r), b = d1.dot(d2);
  const den = a * e - b * b;
  let s = den > 1e-9 ? clamp((b * f - c * e) / den, 0, 1) : 0, t = (b * s + f) / e;
  if (t < 0) { t = 0; s = clamp(-c / a, 0, 1); } else if (t > 1) { t = 1; s = clamp((b - c) / a, 0, 1); }
  const c1 = p1.clone().addScaledVector(d1, s), c2 = p2.clone().addScaledVector(d2, t);
  return { s, t, c1, c2, d: c1.distanceTo(c2) };
}

// ---------- 3. EVENTS: contacts, whooshes, scrapes (in body time, 240 Hz) ----------
const RATE = 240, hero = cast[ids[0]], foe = cast[ids[1]];
const samples = [];
for (let i = 0; i <= DUR * RATE; i++) {
  const tb = i / RATE;
  poseAll(tb);
  const A = bladeSeg(hero), B = bladeSeg(foe);
  const cs = closestSegSeg(A.a, A.tip, B.a, B.tip);
  samples.push({ tb, tipH: A.tip, tipF: B.tip, d: cs.d, point: cs.c1.clone().lerp(cs.c2, 0.5), sH: cs.s, sF: cs.t });
}
const speed = (i, key) => i > 0 ? samples[i][key].distanceTo(samples[i - 1][key]) * RATE : 0;
samples.forEach((s, i) => { s.vH = speed(i, 'tipH'); s.vF = speed(i, 'tipF'); });
const contacts = [];
let minD = { d: 9, tb: 0 }, apart = true;
for (let i = 1; i < samples.length; i++) {
  const s = samples[i], p = samples[i - 1];
  if (s.d < minD.d) minD = { d: s.d, tb: s.tb };
  const closing = s.d < p.d;
  if (s.d > 0.08) apart = true;                       // a new contact needs the blades to have parted first
  if (s.d < 0.03 && closing && apart) {
    apart = false;
    // relative speed at the contact point (approximate: the two tips' relative velocity, scaled by position along the blade)
    const vRel = Math.abs(s.vH * (0.2 + 0.8 * s.sH) - s.vF * (0.2 + 0.8 * s.sF) * 0.3);
    const I = clamp((vRel - 3) / 17, 0, 1);
    contacts.push({ tb: s.tb, point: s.point.toArray(), intensity: +I.toFixed(3), vRel: +vRel.toFixed(2) });
  }
}
// hit-stops: 2 + 2I frames at each contact; later times shift by the earlier stops
const HS = film.effects?.hitStop ?? { min: 3, max: 4 };
const stops = [];
let shift = 0;
for (const c of contacts) {
  const d = clamp(Math.round(2 + 2 * c.intensity), HS.min, HS.max) / FPS;
  c.t = c.tb + shift;
  stops.push({ t: c.t, tb: c.tb, d });
  shift += d;
}
const bodyT = (t) => t - stops.reduce((s, st) => s + clamp(t - st.t, 0, st.d), 0);
const filmT = (tb) => tb + stops.filter((st) => st.tb < tb).reduce((a, st) => a + st.d, 0);   // body time → film time
// sound cues
const AS = film.autoSounds ?? {};
const cues = [];
const dB = (x) => +Math.pow(10, x / 20).toFixed(3);
{ // whooshes: tip speed crosses "on" m/s, re-arms below "rearm", at least 6 frames apart; placed on the speed peak
  const on = AS.whoosh?.on ?? 9, rearm = AS.whoosh?.rearm ?? 6, sfx = AS.whoosh?.sfx ?? ['swing'];
  for (const [who, key] of [['hero', 'vH'], ['foe', 'vF']]) {
    let armed = true, peak = null, n = 0, lastT = -9;
    let cool = false;                                   // after a contact: wait for the blade to slow down
    for (const s of samples) {
      const hit = contacts.find((c) => Math.abs(s.tb - c.tb) < 0.5 / RATE);
      if (cool) { if (s[key] < rearm) cool = false; continue; }
      if (armed && s[key] > on) { armed = false; peak = s; }
      else if (!armed) {
        if (s[key] > peak[key] && !hit) peak = s;
        if (s[key] < rearm || hit) {                    // a whoosh ends when the blade slows or hits something
          if (hit) cool = true;
          armed = true;
          const t = filmT(peak.tb);
          if (t - lastT > 6 / FPS) {
            const k = clamp((peak[key] - 9) / 21, 0, 1);
            cues.push({ id: `auto-whoosh-${who}-${n}`, sfx: sfx[n % sfx.length], t: +Math.max(0, t - 0.06).toFixed(3), len: 0.6,
              gain: dB(Math.min(-12, -18 + 8 * k)), rate: +(0.85 + 0.5 * k).toFixed(3), why: `${who} tip ${peak[key].toFixed(1)} m/s` });
            n++; lastT = t;
          }
        }
      }
    }
  }
}
contacts.forEach((c, i) => cues.push({ id: `auto-clash-${i}`, sfx: c.intensity >= 0.4 ? (AS.clash?.sfx ?? 'clash-steel') : (AS.clash?.light ?? 'clash-light'), t: +c.t.toFixed(3), len: 1.6,
  gain: dB(-6 + 6 * c.intensity), rate: +(1 + 0.06 * (rng(i + 3)() - 0.5) * 2).toFixed(3), why: `blade contact, intensity ${c.intensity}` }));
{ // scrape: blades within 4 cm for more than 4 frames while the contact point slides
  let run = [];
  const flush = () => {
    if (run.length > 4 * RATE / FPS) {
      const t0 = filmT(run[0].tb), t1 = filmT(run[run.length - 1].tb);
      cues.push({ id: `auto-scrape-${cues.length}`, sfx: AS.scrape?.sfx ?? 'steel-scrape', query: AS.scrape?.query, t: +t0.toFixed(3),
        len: +Math.max(0.4, t1 - t0).toFixed(3), gain: dB(-16), why: `blades sliding ${(t1 - t0).toFixed(2)} s` });
    }
    run = [];
  };
  for (const s of samples) { if (s.d < 0.04) run.push(s); else flush(); }
  flush();
}
cues.sort((a, b) => a.t - b.t);
window.EVENTS = { contacts, stops, cues, minDistance: { d: +minD.d.toFixed(4), t: +minD.tb.toFixed(3) } };

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
  const subs = (b.subjects ?? ids).map((id) => cast[id]);
  const center = subs.reduce((s, c) => s.add(joint(c, 'hips')), new THREE.Vector3()).multiplyScalar(1 / subs.length);
  if (b.rig === 'orbit') {
    const a = ((b.deg0 + (b.deg1 - b.deg0) * smooth(clamp((t - b.t) / (DUR - b.t), 0, 1))) * Math.PI) / 180;
    const look = center.clone().setY(b.height ?? 1.1);
    return { pos: look.clone().add(new THREE.Vector3(Math.sin(a) * b.radius, 0.15, Math.cos(a) * b.radius)), look, fov: vfov };
  }
  // frame: both fighters, seen from "angle" degrees off the side view (0 = side-on, 90 = behind the hero)
  const axis = joint(subs[subs.length - 1], 'hips').sub(joint(subs[0], 'hips')).setY(0);
  const sep = axis.length(); axis.normalize();
  const sideDir = new THREE.Vector3().crossVectors(UP, axis).normalize();   // points to one side of the duel line
  const a = (b.angle ?? 30) * Math.PI / 180;
  const dir = sideDir.clone().multiplyScalar(Math.cos(a)).addScaledVector(axis, -Math.sin(a)).normalize();
  const full = (b.size ?? 'full') === 'full';
  const halfH = full ? 1.05 : 0.62, halfW = (sep * Math.cos(a)) / 2 + (full ? 0.6 : 0.4);
  const tv = Math.tan((vfov * Math.PI) / 360), th = tv * (W / H);
  const dist = Math.max(halfH / tv, halfW / th) * 1.05;
  const look = center.clone().setY(full ? 1.0 : 1.4);
  const e = (b.elev ?? 0) * Math.PI / 180;
  const pos = look.clone().addScaledVector(dir, dist * Math.cos(e)).add(new THREE.Vector3(0, dist * Math.sin(e), 0));
  return { pos, look, fov: vfov };
}
// integrate the spring at 240 Hz with a 1 s pre-roll; the look point is 1.5x stiffer than the body
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
  let fov = a.fov + (b.fov - a.fov) * k, roll = 0;
  for (const c of contacts) {                             // impact punch: fov kick, shake, roll
    const tau = t - c.t;
    if (tau < 0 || tau > 0.6) continue;
    const I = 0.5 + 0.5 * c.intensity, env = Math.exp(-tau / 0.12);
    fov -= 7 * I * env;
    const sh = 0.02 * I * Math.max(0, 1 - tau / 0.25);
    camera.position.x += Math.sin(t * 91) * sh; camera.position.y += Math.cos(t * 77) * sh;
    roll += 3 * I * env * Math.sin(tau * 40 + 1);
  }
  camera.fov = fov;
  camera.updateProjectionMatrix();
  camera.up.set(0, 1, 0);
  camera.lookAt(look);
  camera.rotateZ((roll * Math.PI) / 180);
}

// ---------- 5. EFFECTS ----------
// smear ribbon: a white paper strip swept by the blade (tip → 55% point), tapering to nothing at its tail
const RIB = film.effects?.ribbon ?? { minSpeed: 5, frames: 3 };
const RN = 28;
const ribGeo = new THREE.BufferGeometry();
ribGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(RN * 2 * 3), 3));
ribGeo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(RN * 2 * 4), 4));
const idx = [];
for (let j = 0; j < RN - 1; j++) { const a = j * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
ribGeo.setIndex(idx);
const ribMat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, side: THREE.DoubleSide, fog: false, toneMapped: false });
const ribbons = {};
for (const id of ids) { const m = new THREE.Mesh(ribGeo.clone(), ribMat); m.frustumCulled = false; scene.add(m); ribbons[id] = m; }
function tipSpeedAt(id, tb) { const i = clamp(Math.round(tb * RATE), 1, samples.length - 1); return id === ids[0] ? samples[i].vH : samples[i].vF; }
function updateRibbons(t, tb, red = false) {
  const span = RIB.frames / FPS;
  const hist = [];
  for (let j = 0; j < RN; j++) {
    const tj = tb - (j / (RN - 1)) * span;
    poseAll(Math.max(0, tj));
    hist.push(Object.fromEntries(ids.map((id) => [id, { ...bladeSeg(cast[id]), v: tipSpeedAt(id, Math.max(0, tj)) }])));
  }
  poseAll(tb);
  for (const id of ids) {
    const g = ribbons[id].geometry, P = g.attributes.position.array, C = g.attributes.color.array;
    let any = 0;
    for (let j = 0; j < RN; j++) {
      const h = hist[j][id], u = j / (RN - 1);
      const inner = h.mid.clone().lerp(h.tip, u * 0.85);
      P.set(h.tip.toArray(), j * 6); P.set(inner.toArray(), j * 6 + 3);
      const sf = clamp((h.v - RIB.minSpeed) / 6, 0, 1);
      const al = 0.9 * Math.pow(1 - u, 1.5) * sf;
      any = Math.max(any, al);
      const col = red ? [0.75, 0.08, 0.06] : [1, 0.97, 0.9];
      C.set([...col, al], j * 8); C.set([...col, al * 0.35], j * 8 + 4);
    }
    g.attributes.position.needsUpdate = true; g.attributes.color.needsUpdate = true;
    g.computeBoundingSphere();
    ribbons[id].visible = any > 0.01;
  }
}
// sparks: small white-gold paper shards, aimed out of the contact
function makeSparks(seed, n) {
  const r = rng(seed), g = new THREE.Group(); scene.add(g);
  const tri = new THREE.Shape(); tri.moveTo(0, 0.012); tri.lineTo(0.008, -0.006); tri.lineTo(-0.007, -0.005); tri.closePath();
  const geo = new THREE.ShapeGeometry(tri), parts = [];
  for (let i = 0; i < n; i++) {
    const m = new THREE.Mesh(geo, paper(['#fff6dc', '#ffd27a', '#ffe9b0'][i % 3], { repeat: 30, glow: 1.6, fog: false }));
    const a = r() * Math.PI * 2, e = r() * 1.4 - 0.4, sp = 1.5 + r() * 3.5;
    parts.push({ m, v: new THREE.Vector3(Math.cos(a) * Math.cos(e) * sp, Math.sin(e) * sp + 0.8, Math.sin(a) * Math.cos(e) * sp), w: r() * 20, s: 0.6 + r() });
    g.add(m);
  }
  return (t, t0, origin) => {
    const dt = t - t0; g.visible = dt >= 0 && dt < 0.55; if (!g.visible) return;
    const drag = (1 - Math.exp(-3 * dt)) / 3;
    for (const p of parts) {
      p.m.position.set(origin.x + p.v.x * drag, origin.y + p.v.y * drag - 2 * dt * dt, origin.z + p.v.z * drag);
      p.m.rotation.set(p.w * dt, p.w * 0.7 * dt, p.w * 1.3 * dt);
      p.m.scale.setScalar(p.s * (1 - dt / 0.55));
      p.m.lookAt(camera.position);
    }
  };
}
const sparks = contacts.map((c, i) => ({ fn: makeSparks(40 + i, Math.round(24 + 40 * c.intensity)), c }));
const flashLight = new THREE.PointLight(0xffe2a8, 0, 3, 2); scene.add(flashLight);
const inkMat = new THREE.MeshBasicMaterial({ color: '#0d0b0a', fog: false, side: THREE.DoubleSide });
const washi = new THREE.Color('#f1e7d3');

// ---------- frame ----------
const flashEl = document.getElementById('flash'), fadeEl = document.getElementById('fade');
window.renderAt = (t) => {
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
  const impactFrame = film.effects?.impactFrame !== false && contacts.some((c) => t >= c.t && t < c.t + 1 / FPS);
  updateRibbons(t, tb, impactFrame);
  if (inStop) { hero.fig.root.updateMatrixWorld(true); }
  // sparks + flash light
  let fl = 0;
  for (const { fn, c } of sparks) {
    const o = new THREE.Vector3(...c.point);
    fn(t, c.t, o);
    const tau = t - c.t;
    if (tau >= 0 && tau < 0.3) { fl = Math.max(fl, (1 - tau / 0.3) * (0.6 + c.intensity)); flashLight.position.copy(o); }
  }
  flashLight.intensity = 6 * fl;
  flashEl.style.opacity = impactFrame ? 0 : Math.min(0.35, fl * 0.3);
  fadeEl.style.opacity = clamp(Math.max(1 - t / 0.6, (t - (DUR - 0.6)) / 0.6), 0, 1);
  if (impactFrame) {
    // ONE frame: washi-white page, fighters as flat ink silhouettes, a red streak along the cut
    const bg = scene.background, fog = scene.fog;
    scene.background = washi; scene.fog = null;
    const hidden = scene.children.filter((o) => o.visible && !Object.values(cast).some((c) => c.fig.root === o) && !Object.values(ribbons).includes(o));
    for (const o of hidden) o.visible = false;              // only the fighters: ink on a blank page
    scene.overrideMaterial = inkMat;
    for (const r of Object.values(ribbons)) r.visible = false;
    renderer.render(scene, camera);
    scene.overrideMaterial = null;
    renderer.autoClear = false;
    const only = new THREE.Scene(); for (const r of Object.values(ribbons)) { only.add(r); r.visible = true; }
    renderer.render(only, camera);
    for (const r of Object.values(ribbons)) scene.add(r);
    for (const o of hidden) o.visible = true;
    renderer.autoClear = true;
    scene.background = bg; scene.fog = fog;
    return;
  }
  renderer.render(scene, camera);
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
if (!params.has('render')) {
  if (params.has('t')) window.renderAt(parseFloat(params.get('t')));
  else { const t0 = performance.now(); const loop = () => { window.renderAt(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); }
}

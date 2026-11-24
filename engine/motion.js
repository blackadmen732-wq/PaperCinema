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
import { makeFigure, holdInHand, applyPose, makeMotion, resolveKeys, windowWeight, solveArm, gripHand, smooth } from './figure.js';
import { lockFeet } from './footlock.js';
import { loadVoice } from './voice-env.js';
import * as combat from './combat.js';
import { clamp, bladeSeg, closestSegSeg, RATE } from './combat.js';
import { createFX, fxAt } from './fx.js';
import { analyseGround, groundCues, makeDust, makeContactShadows, makeAfterimages } from './groundfx.js';
import { installAudit } from './audit-hooks.js';

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
if (film.light) world.setLight(film.light);                      // { sun, hemi, fill, ground }: lift the shadows (docs/STUDIO-STANDARD.md §8)

// ---------- cast ----------
const POSES = await (await fetch('/library/poses.json')).json();
const MOVES = await (await fetch('/library/moves.json')).json();
const cast = {};
for (const [id, c] of Object.entries(film.cast)) {
  const preset = await loadCharacter(c.character);
  const spec = { ...preset.colors, ...preset.accessories, band: preset.accessories.band ?? undefined, haori: preset.accessories.haori ?? undefined };
  const fig = makeFigure({ ...spec, face: c.face });
  scene.add(fig.root);
  const k = makeKatana();
  holdInHand(fig.rH, k.sword, -0.06);
  const perf = film.performances[id];
  let motion = makeMotion(resolveKeys(expandMoves(perf.keys, MOVES), POSES), film.motion ?? {});
  // film.motion.lockFeet: plant the feet in the world and let the weight fall on them (engine/footlock.js)
  if (film.motion?.lockFeet) motion = lockFeet(motion, DUR, film.motion.lockFeet);
  if (c.hidden) fig.root.visible = false;               // an invisible target (e.g. the tree) the hero looks at
  cast[id] = { id, fig, sword: k.sword, bladeLen: k.length, motion, perf, hidden: !!c.hidden, phase: Object.keys(cast).length * 1.7,
    demonic: !!c.demonic, glow: c.glow, makeGhost: () => makeFigure(spec) };
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
    if (w > 0) gripHand(c.fig, 'l', c.sword, w);         // the left hand wraps the end of the handle
    c.fig.root.updateMatrixWorld(true);
  }
}

// ---------- 3. EVENTS: contacts, whooshes, scrapes (in body time, 240 Hz) → window.EVENTS ----------
const hero = cast[ids[0]], foe = cast[ids[1]];
console.log('[motion] cast ready, analysing', performance.now() | 0);
const C = combat.analyse({ film, fighters: [hero, foe], pose: poseAll, fps: FPS, dur: DUR, armed: hero.hidden || foe.hidden ? () => false : null });
const { contacts, stops, bodyT } = C;
CONTACTS = contacts;
// THREE CLOCKS. film time t (what the viewer sees: camera, sound, post FX) → speed ramps (film.ramps) → world time s
// (sparks, dust, props, authored impacts; hit-stops are placed on it) → hit-stops → body time tb (the keys).
const R = combat.makeRamps(film.ramps, DUR);
const worldT = R.worldT;
const toFilm = (tb) => R.filmOf(C.filmT(tb));                      // body time → film time
const contactsF = contacts.map((c) => ({ ...c, t: R.filmOf(c.t) }));   // the contacts on the film clock (ink frame, punch, FX)
// GROUND: dash / skid / take-off / landing found from the motion → dust, wake, sound cues (film.effects.ground: false = off)
const VISIBLE = Object.values(cast).filter((c) => !c.hidden);
const G = analyseGround({ fighters: VISIBLE, dur: DUR, filmT: C.filmT, opts: film.effects?.ground ?? {} });
const GROUND_ON = film.effects?.ground !== false;
const gCues = GROUND_ON && film.autoSounds?.ground !== false ? groundCues(G.events, film.autoSounds?.ground ?? {}) : [];
window.EVENTS = { ...C.events, contacts: contacts.map((c) => ({ ...c, tWorld: c.t, t: +R.filmOf(c.t).toFixed(3) })),
  cues: [...C.cues, ...gCues].map((c) => ({ ...c, t: +R.filmOf(c.t).toFixed(3) })).sort((a, b) => a.t - b.t),
  ground: G.events.filter((e) => !['wake', 'skidding'].includes(e.kind)).map((e) => ({ ...e, t: +R.filmOf(e.t).toFixed(3) })),
  ramps: R.list.map((r) => ({ t: r.t, rate: r.rate, film0: r.film0, film1: r.film1 })),
  warp: R.list.length || stops.length ? { dt: 0.02, film: Array.from({ length: Math.ceil(DUR / 0.02) + 1 }, (_, i) => +toFilm(i * 0.02).toFixed(4)) } : null };

// ---------- PROPS: cuttable paper trees (film.props.trees) ----------
// { id, x, z, height, color, cut: { t, y, tilt, delay, dir }, split: { t } }
//   cut: the blade passes at t; a thin glowing seam shows, then after "delay" the top slides along the cut and
//   topples over (heavy, slow, anime timing); split: the falling top is cut again in the air and flies apart.
const TREES = (film.props?.trees ?? []).map((tr) => makeTree(tr));
// authored impacts: { t, intensity, at: "<tree id>" | [x,y,z], ink, sparks } → camera punch, paper chips, ink frame
const IMPACTS = (film.impacts ?? []).map((i) => {
  const tr = TREES.find((x) => x.tr.id === i.at);
  const p = Array.isArray(i.at) ? i.at : tr ? tr.point().toArray() : [0, 1, 0];
  return { intensity: 0.6, ...i, point: p, tf: R.filmOf(i.t) };
});
const IMPACTS_F = IMPACTS.map((i) => ({ ...i, t: i.tf }));         // on the film clock (camera punch, ink frame)
window.EVENTS.impacts = IMPACTS_F.map((i) => ({ t: +i.t.toFixed(3), intensity: i.intensity, point: i.point, ink: !!i.ink }));
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
    // keep-out volumes for the camera guards at the last update(t): [{ x, z, r, y0, y1 }] (stump, standing crown or falling top)
    solids(t) {
      const fallen = tr.cut && t >= tr.cut.t + (tr.cut.delay ?? 0.45);
      const out = [{ x: tr.x, z: tr.z, r: 0.24, y0: 0, y1: fallen ? cy + 0.1 : H - 1.2 * sc }];
      if (tr.split && t >= tr.split.t) return out;
      root.updateMatrixWorld(true);
      const c = top.localToWorld(new THREE.Vector3(0, H - cy - 1.0, 0));
      out.push({ x: c.x, z: c.z, r: 1.15 * sc + 0.1, y0: c.y - 1.0, y1: c.y + 1.1 });
      return out;
    },
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
        if (tr.split.world) {
          // world-space ballistic halves: thrown sideways (away from the cutter's path), a short hop up, then they fall,
          // hit the ground and stay there (never through the sand, never through the fighter)
          const qi = top.quaternion.clone().invert();
          const side = new THREE.Vector3(...(tr.split.side ?? [1, 0, 0])).normalize(), sp = tr.split.speed ?? 2.2;
          const y0 = top.position.y + 0.9;                                            // rough height of the crown when it is cut
          const vy = tr.split.up ?? 1.4, tg = (vy + Math.sqrt(vy * vy + 2 * 6 * Math.max(0.01, y0 - 0.45))) / 6;   // heavy paper: g = 6
          const u2 = Math.min(v, tg), rest = v >= tg;
          halves.forEach((h, k) => {
            const sg = k ? -1 : 1, sl = rest ? 0.12 * (1 - Math.exp(-(v - tg) * 5)) : 0;   // a short slide when it lands
            const w = side.clone().multiplyScalar(sg * (sp * u2 + sl)).addScaledVector(dir, 0.5 * u2).add(new THREE.Vector3(0, vy * u2 - 3 * u2 * u2, 0));
            h.position.copy(w.applyQuaternion(qi));
            h.rotation.set(sg * 0.5 * u2, 0, sg * 1.1 * u2);
          });
        } else halves.forEach((h, k) => {
          const sg = k ? 1 : -1;
          h.position.set(sg * (1.6 * v), -2.5 * v * v, 0.4 * v);
          h.rotation.set(sg * 1.2 * v, 0, sg * 2.2 * v);
        });
      }
    },
  };
}

// ---------- 4. CAMERA: rigs aim at real joints, then a spring smooths it ----------
// Guide: docs/CAMERA.md §8 (motion-page beats), docs/STUDIO-STANDARD.md §3 (which camera for which beat).
// A beat: { t | act, rig, feel, cut, until | untilAct, ... }. "act" / "untilAct" = action time (converted to film time
// through the speed ramps, so a beat can start "when the blade lands" whatever the slow motion does).
// film.cameraOpts.solver: 2 = the cinematographer's spring: it works on the offset from the subject (the subject can
// never out-run it), "cut": true is a hard cut, guards keep the subject in frame, the lens above the ground and out
// of props. Without it the camera is the old world-space spring (older films render as before).
const FEELS = { locked: [6, 1], dolly: [1.8, 1], crane: [0.7, 1.1], handheld: [2.5, 0.7], torpedo: [4, 0.62], whip: [7, 0.85] };
const SOLVER2 = (film.cameraOpts?.solver ?? 1) >= 2;
const BEATS = film.camera.map((b) => ({ ...b, t: b.act !== undefined ? R.filmOf(b.act) : b.t, until: b.untilAct !== undefined ? R.filmOf(b.untilAct) : b.until }));
BEATS.forEach((b, i) => { b.i = i; b.end = b.until ?? BEATS[i + 1]?.t ?? DUR; });
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
    case 'chest': return worldOf(f.upper ?? f.torso, 0, 0.25, 0);
    case 'head': return worldOf(f.head, 0, 0.1, 0);
  }
  throw new Error('unknown joint ' + name);
}
const UP = new THREE.Vector3(0, 1, 0);
const GROUND_Y = (x, z) => ((film.mode ?? 'dawn') === 'dawn' ? world.groundAt(x, z) : 0);
const lerp = (a, b, k) => a + (b - a) * k;
// guards: is the straight line from the lens to the subject clear of the props? (cylinders from TREES[].solids)
function losClear(pos, P, solids) {
  for (const c of solids) {
    const dx = P.x - pos.x, dz = P.z - pos.z, L2 = dx * dx + dz * dz || 1e-9;
    const k = clamp(((c.x - pos.x) * dx + (c.z - pos.z) * dz) / L2, 0, 0.93);       // stop short of the subject itself
    const px = pos.x + dx * k, pz = pos.z + dz * k, py = pos.y + (P.y - pos.y) * k;
    if (Math.hypot(px - c.x, pz - c.z) < c.r + 0.3 && py > c.y0 - 0.1 && py < c.y1 + 0.25) return false;
  }
  return true;
}
function rigTarget(b, t, tb, s) {
  const vfov = b.fov ?? 36;
  if (b.rig === 'face') {
    const c = cast[b.who], eye = joint(c, 'eyes');
    const fwd = new THREE.Vector3(0, 0, 1).applyQuaternion(c.fig.head.getWorldQuaternion(new THREE.Quaternion())).setY(0).normalize();
    fwd.applyAxisAngle(UP, (b.angle ?? 0) * Math.PI / 180);
    const pos = eye.clone().addScaledVector(fwd, b.dist ?? 0.45).add(new THREE.Vector3(0, b.lift ?? 0, 0));
    return { pos, look: eye.clone().add(new THREE.Vector3(0, -0.01, 0)), fov: vfov, anchor: eye };
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
    return { pos: p.clone().add(off), look: ahead, fov: vfov, anchor: p };
  }
  const subIds = b.subjects ?? ids;
  const hipsOf = (id) => { const tr = TREES.find((x) => x.tr.id === id); return tr ? tr.root.position.clone().setY(0.95) : joint(cast[id], 'hips'); };
  if (b.rig === 'compose') {
    // THE FRAMING SOLVER: say where the subject sits in the frame and how big it is; the solver finds the camera.
    //   subjects[0] = who; size (fraction of the frame height that "span" metres fill; default span 1.8 = the whole
    //   figure); screen [sx, sy] (0..1, where the subject's middle sits; default centre) or lead (0.16 = lead room: the
    //   subject sits off-centre, with the space in front of its motion or gaze); az (degrees around the subject,
    //   0 = +z side) and elev (degrees up; negative = low angle); basis "world" | "facing" (az 0 = in front of the
    //   subject, frozen at the start of the beat) | "target" (az 0 = seen from the target's side, 180 = over the
    //   shoulder towards "target"); aim = a joint instead of the whole body (close-ups).
    //   Every number takes a 0/1 pair (az0 → az1 orbit, elev0 → elev1 crane, size0 → size1 push-in / pull-back,
    //   fov0 → fov1 with a fixed size = dolly-zoom, roll0 → roll1 dutch), eased over the beat ("ease": "inOut" | "out" | "in" | "linear").
    const raw = clamp((t - b.t) / Math.max(1e-6, b.end - b.t), 0, 1);
    const u = b.ease === 'linear' ? raw : b.ease === 'out' ? 1 - (1 - raw) ** 3 : b.ease === 'in' ? raw ** 3 : smooth(raw);
    const L = (k, d) => lerp(b[k + '0'] ?? b[k] ?? d, b[k + '1'] ?? b[k] ?? b[k + '0'] ?? d, u);
    const who = subIds[0], c = cast[who];
    let P, facing = 0, vel = new THREE.Vector3();
    if (c) {
      const root = c.fig.root.position, top = worldOf(c.fig.head, 0, 0.3, 0), hips = joint(c, 'hips');
      P = b.aim ? joint(c, b.aim) : new THREE.Vector3(hips.x, (root.y + top.y) / 2, hips.z);
      facing = c.fig.root.rotation.y;
      const m0 = c.motion(Math.max(0, tb - 0.02)), m1 = c.motion(tb + 0.02), rate = R.rateAt(t);
      vel.set(m1.x - m0.x, m1.y - m0.y, m1.z - m0.z).multiplyScalar(rate / 0.04);        // what the viewer sees (slow motion included)
    } else P = hipsOf(who);
    let basis = 0;
    if (b.basis === 'facing' && c) { b._basis ??= c.motion(bodyT(worldT(b.t))).ry; basis = b._basis; }
    else if (b.basis === 'target') { const q = hipsOf(b.target ?? subIds[1]); basis = Math.atan2(q.x - P.x, q.z - P.z); }
    const fov = L('fov', 36), size = L('size', 0.6), span = b.span ?? (b.aim ? 0.6 : 1.8);
    const tv = Math.tan((fov * Math.PI) / 360), th = tv * (W / H);
    const dist = span / size / (2 * tv);
    const solids = [...TREES.filter((x) => !subIds.includes(x.tr.id) || b.guard === 'all').flatMap((x) => x.solids(s)), ...((film.mode ?? 'dawn') === 'dawn' ? world.obstacles : [])];
    const build = (azDeg) => {
      const a = (azDeg * Math.PI) / 180 + basis, e = (L('elev', 0) * Math.PI) / 180;
      const dir = new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), Math.cos(a) * Math.cos(e));
      const right = new THREE.Vector3().crossVectors(UP, dir).normalize(), up = new THREE.Vector3().crossVectors(dir, right);
      let [sx, sy] = b.screen ?? [0.5, 0.5];
      if (b.lead) {                                    // lead room: space in front of the motion, else in front of the gaze
        const vr = vel.dot(right), g = new THREE.Vector3(Math.sin(facing), 0, Math.cos(facing)).dot(right);
        sx = 0.5 - b.lead * (Math.abs(vr) > 0.8 ? Math.sign(vr) * Math.min(1, Math.abs(vr) / 4) : 0.6 * g);
        if (!b.screen) sy = 0.5 + clamp(vel.y / 8, -0.08, 0.1);                           // rising: room above
      }
      const off = right.clone().multiplyScalar((0.5 - sx) * 2 * dist * th).addScaledVector(up, (sy - 0.5) * 2 * dist * tv);
      const pos = P.clone().addScaledVector(dir, dist).add(off);
      const minY = GROUND_Y(pos.x, pos.z) + (b.minY ?? 0.14);
      if (pos.y < minY) pos.y = minY;                                                     // never under the sand
      return { pos, look: P.clone().add(off) };
    };
    const az = L('az', 90);
    let best = build(az);
    if (b.guard !== false) {
      // props out of the lens: swing round the subject (a few degrees at a time) until the line of sight is clear,
      // then step back out of any prop the lens ended up inside
      const pts = c ? [P, new THREE.Vector3(P.x, c.fig.root.position.y + 0.2, P.z), worldOf(c.fig.head, 0, 0.1, 0)] : [P];   // middle, feet, head
      for (const d of [0, 7, -7, 14, -14, 22, -22, 32, -32, 45, -45, 60, -60]) { const c2 = build(az + d); if (pts.every((q) => losClear(c2.pos, q, solids))) { best = c2; break; } }
      for (const q of solids) {
        const dx = best.pos.x - q.x, dz = best.pos.z - q.z, d = Math.hypot(dx, dz) || 1e-6, keep = q.r + 0.3;
        if (d < keep && best.pos.y > q.y0 - 0.2 && best.pos.y < q.y1 + 0.2) { best.pos.x = q.x + (dx / d) * keep; best.pos.z = q.z + (dz / d) * keep; }
      }
    }
    return { pos: best.pos, look: best.look, fov, roll: L('roll', 0), anchor: P, keep: b.keep ?? [0.72, 0.8] };
  }
  const center = subIds.reduce((s2, id) => s2.add(hipsOf(id)), new THREE.Vector3()).multiplyScalar(1 / subIds.length);
  if (b.rig === 'orbit') {
    const a = ((b.deg0 + ((b.deg1 ?? b.deg0) - b.deg0) * smooth(clamp((t - b.t) / ((b.until ?? DUR) - b.t), 0, 1))) * Math.PI) / 180;
    // follow: the look point rides with the subject (jumps), camY = camera height relative to it (negative = looking up)
    const look = b.follow ? center.clone().add(new THREE.Vector3(0, b.lookUp ?? 0.35, 0)) : center.clone().setY(b.height ?? 1.1);
    const camY = b.follow ? (b.camY ?? 0) : 0.15;
    const pos = look.clone().add(new THREE.Vector3(Math.sin(a) * b.radius, camY, Math.cos(a) * b.radius));
    pos.y = Math.max(0.12, pos.y);                                                    // never under the ground
    return { pos, look, fov: vfov, anchor: center };
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
  return { pos, look, fov: vfov, anchor: center };
}
// integrate the spring at 240 Hz with a 1 s pre-roll; the look point is 1.5x stiffer than the body
console.log('[motion] analysis done, camera', performance.now() | 0);
const camPath = [];
{
  let pos = null, look = null, fov = 0, roll = 0, last = null;
  const vp = new THREE.Vector3(), vl = new THREE.Vector3(); let vf = 0;
  const A = new THREE.Vector3();                           // solver 2: the (slightly lagging) subject the spring hangs from
  const step = (x, v, target, f, z, dt) => {             // critically/under-damped spring, semi-implicit Euler
    const w = 2 * Math.PI * f;
    v.addScaledVector(target.clone().sub(x), w * w * dt).multiplyScalar(1 / (1 + 2 * z * w * dt));
    x.addScaledVector(v, dt);
  };
  for (let i = -RATE; i <= DUR * RATE; i++) {
    const t = Math.max(0, i / RATE), s = worldT(t), tb = bodyT(s);
    poseAll(tb);
    if (SOLVER2) for (const tr of TREES) tr.update(s);
    const b = beatAt(t), tg = rigTarget(b, t, tb, s);
    const [f, z] = FEELS[b.feel ?? 'dolly'];
    const dt = 1 / RATE;
    if (!SOLVER2) {
      if (!pos) { pos = tg.pos.clone(); look = tg.look.clone(); fov = tg.fov; }
      step(pos, vp, tg.pos, f, z, dt);
      step(look, vl, tg.look, f * 1.5, Math.max(z, 0.8), dt);
      const w = 2 * Math.PI * f; vf = (vf + (tg.fov - fov) * w * w * dt) / (1 + 2 * z * w * dt); fov += vf * dt;
      if (b.feel === 'handheld') {                          // a breathing operator: smooth low-frequency drift
        const n = (q) => Math.sin(t * 1.7 + q) * 0.6 + Math.sin(t * 3.1 + q * 2) * 0.4;
        pos.x += n(1) * 0.0006; pos.y += n(2) * 0.0005;
      }
      if (i >= 0) camPath.push({ pos: pos.clone(), look: look.clone(), fov, roll: 0, beat: b.i });
      continue;
    }
    // solver 2: pos / look are OFFSETS from the subject; the subject is followed with a tiny lag ("lag" seconds)
    const rp = tg.pos.clone().sub(tg.anchor), rl = tg.look.clone().sub(tg.anchor);
    if (!pos || (b !== last && b.cut)) { pos = rp.clone(); look = rl.clone(); fov = tg.fov; roll = tg.roll ?? 0; vp.set(0, 0, 0); vl.set(0, 0, 0); vf = 0; A.copy(tg.anchor); }
    else if (b !== last) { const d = A.clone().sub(tg.anchor); pos.add(d); look.add(d); A.copy(tg.anchor); }   // new subject: the spring carries the move
    last = b;
    A.lerp(tg.anchor, 1 - Math.exp(-dt / Math.max(1e-4, b.lag ?? 0.02)));
    step(pos, vp, rp, f, z, dt);
    step(look, vl, rl, f * 1.5, Math.max(z, 0.8), dt);
    const w = 2 * Math.PI * f; vf = (vf + (tg.fov - fov) * w * w * dt) / (1 + 2 * z * w * dt); fov += vf * dt;
    roll += ((tg.roll ?? 0) - roll) * (1 - Math.exp(-dt * 6));
    if (i < 0) continue;
    const P = A.clone().add(pos), Lk = A.clone().add(look);
    if (b.feel === 'handheld') { const n = (q) => Math.sin(t * 1.7 + q) * 0.6 + Math.sin(t * 3.1 + q * 2) * 0.4; P.x += n(1) * 0.012; P.y += n(2) * 0.01; }
    if (tg.keep) {                                         // guard: the subject never leaves the frame
      const fw = Lk.clone().sub(P).normalize(), r = new THREE.Vector3().crossVectors(fw, UP).normalize(), u = new THREE.Vector3().crossVectors(r, fw);
      const d = tg.anchor.clone().sub(P), zc = d.dot(fw);
      if (zc > 0.2) {
        const tv = Math.tan((fov * Math.PI) / 360), th = tv * (W / H);
        const nx = d.dot(r) / (zc * th), ny = d.dot(u) / (zc * tv);
        if (Math.abs(nx) > tg.keep[0]) { const m = (nx - Math.sign(nx) * tg.keep[0]) * zc * th; P.addScaledVector(r, m); Lk.addScaledVector(r, m); }
        if (Math.abs(ny) > tg.keep[1]) { const m = (ny - Math.sign(ny) * tg.keep[1]) * zc * tv; P.addScaledVector(u, m); Lk.addScaledVector(u, m); }
      }
    }
    P.y = Math.max(GROUND_Y(P.x, P.z) + 0.12, P.y);        // guard: never under the sand
    camPath.push({ pos: P, look: Lk, fov, roll, beat: b.i });
  }
}
const HITS_F = [...contactsF, ...IMPACTS_F];
function placeCamera(t) {
  const x = clamp(t * RATE, 0, camPath.length - 1), i = Math.floor(x), k = x - i, a = camPath[i], b = camPath[Math.min(i + 1, camPath.length - 1)];
  const cutHere = a.beat !== b.beat && BEATS[b.beat].cut && SOLVER2;   // never blend across a hard cut
  camera.position.copy(a.pos); if (!cutHere) camera.position.lerp(b.pos, k);
  const look = a.look.clone(); if (!cutHere) look.lerp(b.look, k);
  const { fov, roll } = combat.punch(HITS_F, t, camera, cutHere ? a.fov : a.fov + (b.fov - a.fov) * k);   // impact punch: fov kick, shake, roll
  camera.fov = fov;
  camera.updateProjectionMatrix();
  camera.up.set(0, 1, 0);
  camera.lookAt(look);
  camera.rotateZ(((roll + a.roll) * Math.PI) / 180);
}

// ---------- 5. EFFECTS: light smear, sparks, shock rings (engine/combat.js); dust, contact shadows, afterimages
// (engine/groundfx.js); post FX (engine/fx.js) when the film has fxBase / fx ----------
const SPARKS2 = combat.makeSparks(scene, camera, IMPACTS.filter((i) => i.sparks !== false), { light: film.effects?.sparkLight ?? 6 });
const RIB = combat.makeRibbons(scene, Object.values(cast), { ribbon: film.effects?.ribbon, fps: FPS, pose: poseAll, tipSpeedAt: C.tipSpeedAt });
const ribbons = RIB.meshes;
const SPARKS = combat.makeSparks(scene, camera, contacts, { light: film.effects?.sparkLight ?? 6 });
const DUST = GROUND_ON ? makeDust(scene, G.events, film.effects?.ground ?? {}) : null;
const SHADOWS = film.effects?.contactShadow !== false ? makeContactShadows(scene, VISIBLE, film.effects?.contactShadow ?? {}) : null;
const GHOSTS = film.effects?.afterimage !== false ? makeAfterimages(scene, VISIBLE, film.effects?.afterimage ?? {}) : null;
const FX = film.fxBase || film.fx ? createFX(renderer, scene, camera, { width: W, height: H, seed: 7, fps: FPS }) : null;
// post-FX track on the film clock: authored events ("body": true = action time), contact flashes, impact flashes,
// speed lines on every dash (film.effects.speedLines: false = off)
const FX_TRACK = FX ? [
  ...(film.fx ?? []).map((e) => (e.body ? { ...e, t: toFilm(e.t) } : e)),
  ...combat.contactFx(HITS_F.filter((h) => h.fx !== false), film.effects?.contactFx),
  ...(film.effects?.speedLines === false || !GROUND_ON ? [] : G.events.filter((e) => e.kind === 'dash').map((e) => ({ t: R.filmOf(e.t), effect: 'speed-lines', dur: 0.3, amount: 0.7, ...(film.effects?.speedLines ?? {}) }))),
] : [];
// glints that travel along the steel: film.effects.glints [{ t (action time), who, dur, from, to }] + one at the start of each speed ramp
const GLINTS = film.effects?.glints === false ? [] : [...(film.effects?.glints ?? []), ...R.list.map((r) => ({ t: r.t - 0.02, who: VISIBLE[0]?.id, dur: 0.22 }))];

// ---------- frame ----------
const flashEl = document.getElementById('flash'), fadeEl = document.getElementById('fade');
const FADE = { in: 0.6, out: 0.6, ...(film.fade ?? {}) };
/** Everything except the draw: poses, props, camera, effects for film time t. */
function stage(t) {
  FILM_TIME = t;
  world.update(t);
  const s = worldT(t), tb = bodyT(s);
  poseAll(tb);
  // hit-stop jitter: during a stop the fighters shiver ±6 mm in opposite directions on alternate frames
  const inStop = stops.find((st) => s >= st.t && s < st.t + st.d);
  if (inStop) {
    const sgn = Math.round(t * FPS) % 2 ? 1 : -1;
    hero.fig.root.position.z += 0.006 * sgn; foe.fig.root.position.z -= 0.006 * sgn;
    for (const c of Object.values(cast)) c.fig.root.updateMatrixWorld(true);
  }
  placeCamera(t);
  const impactFrame = combat.isImpactFrame(film, contactsF, t, FPS) || IMPACTS_F.some((i) => i.ink && t >= i.t && t < i.t + 1 / FPS);
  RIB.update(tb, impactFrame);
  if (inStop) { hero.fig.root.updateMatrixWorld(true); }
  for (const tr of TREES) tr.update(s);
  SHADOWS?.update();
  GHOSTS?.update(tb, G.speedAt, R.rateAt(t));
  DUST?.update(s);
  const fl = Math.max(SPARKS.update(s), SPARKS2.update(s));  // sparks + flash light
  flashEl.style.opacity = impactFrame ? 0 : Math.min(0.35, fl * 0.3);
  fadeEl.style.opacity = clamp(Math.max(FADE.in > 0 ? 1 - t / FADE.in : 0, FADE.out > 0 ? (t - (DUR - FADE.out)) / FADE.out : 0), 0, 1);
  return { s, tb, impactFrame };
}
window.renderAt = (t) => {
  const { tb, impactFrame } = stage(t);
  if (impactFrame) {
    combat.renderInkFrame(renderer, scene, camera, [...Object.values(cast).filter((c) => !c.hidden).map((c) => c.fig.root), ...(film.effects?.inkProps ? TREES.map((x) => x.root) : [])], ribbons);   // fighters only: one clean silhouette
    return;
  }
  if (FX) {
    const p = fxAt(t, FX_TRACK, film.fxBase, FPS);
    const gl = combat.bladeGlints(GLINTS, cast, tb, t);
    if (gl.length) p.glint = [...(Array.isArray(p.glint) ? p.glint : p.glint ? [p.glint] : []), ...gl];
    FX.render(t, p);
  } else renderer.render(scene, camera);
};

// studio QA hooks (tools/audit.mjs, docs/AUDIT.md): measurements for any film time, without drawing
installAudit({
  scene, camera, W, H, fps: FPS, dur: DUR, page: 'motion',
  fighters: () => Object.values(cast),
  cuts: SOLVER2 ? BEATS.filter((b) => b.cut && b.t > 0).map((b) => +b.t.toFixed(4)) : [],
  meta: { solver: SOLVER2 ? 2 : 1, beats: BEATS.map((b) => ({ t: +b.t.toFixed(3), rig: b.rig, cut: !!b.cut, note: b.note })), ramps: window.EVENTS.ramps,
    effects: { ground: GROUND_ON, contactShadow: !!SHADOWS, afterimage: !!GHOSTS, smear: (film.effects?.ribbon?.style ?? 'light'), fx: !!FX } },
  stage(t) {
    const st = stage(t), b = beatAt(t);
    return { tb: st.tb, shot: b.i, cut: false, rate: R.rateAt(t), impactFrame: st.impactFrame, smear: RIB.level,
      subjects: (b.who ? [b.who] : b.subjects ?? ids).filter((id) => cast[id] && !cast[id].hidden) };
  },
});

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

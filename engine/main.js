// Film engine: loads a shot list (film/*.json), builds the paper world,
// runs the choreography, and exposes window.renderAt(t) so every frame
// is deterministic (the renderer captures frame by frame → MP4).
import * as THREE from 'three';
import { buildWorld, STUDIO_X } from './world.js';
import { makeKuroko } from './kuroko.js';
import { expandMoves, loadClips } from './moves.js';
import { makeKatana, makeBokken, makeBoat, makeOar } from './props.js';
import { makeFigure, holdInHand, applyPose, track, smooth, makeMotion, resolveKeys, windowWeight, solveArm, gripHand, reachHand, BASE_POSE } from './figure.js';
import { lockFeet } from './footlock.js';
import { paper, rng } from './paper.js';
import { loadVoice } from './voice-env.js';
import * as combat from './combat.js';
import { createFX, fxAt } from './fx.js';
import { analyseGround, groundCues, makeDust, makeContactShadows } from './groundfx.js';
import { installAudit } from './audit-hooks.js';

const params = new URLSearchParams(location.search);
const film = await (await fetch(params.get('film') ?? '/film/ganryujima.json')).json();
const VERTICAL = params.get('aspect') === 'vertical' || (film.format === 'vertical' && params.get('aspect') !== 'horizontal');
const W = VERTICAL ? 720 : film.width, H = VERTICAL ? 1280 : film.height;
if (VERTICAL) { film.letterbox = 0; document.body.classList.add('vertical'); }
const FPS = film.fps ?? 24;
const FILM_NAME = (params.get('film') ?? '/film/ganryujima.json').split('/').pop().replace('.json', '');
const VOICE = film.voice ? await loadVoice(FILM_NAME) : null;   // spoken lines → eyes pulse (docs/VOICE.md)
// optional film.cast: { kojiro: { face: 'eyes' }, musashi: { face: 'eyes', weapon: 'bokken' | 'katana' } }
const CAST = film.cast ?? {};

// ---------- renderer / scene ----------
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.getElementById('stage').style.width = W + 'px';
document.getElementById('stage').style.height = H + 'px';
const barH = film.letterbox ? Math.max(0, (H - W / film.letterbox) / 2) : 0;
document.querySelectorAll('.bar').forEach((b) => (b.style.height = barH + 'px'));

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, W / H, 0.02, 600);
const world = buildWorld(scene);

// ---------- cast & props ----------
const studioKatana = makeKatana();
const studioRig = new THREE.Group();
studioRig.position.set(STUDIO_X, 1.2, 0);
studioRig.add(studioKatana.saya, studioKatana.sword);
scene.add(studioRig);

const kojiro = makeFigure({
  robe: '#efe6d4', sleeve: '#efe6d4', haori: '#9c2a25', hakama: '#5c2220', hakamaFold: '#4a1b19',
  skin: '#efe3cc', collar: '#f6eedf', obi: '#2a1d1a', face: CAST.kojiro?.face, eyes: CAST.kojiro?.eyes,
});
scene.add(kojiro.root);
const hipKatana = makeKatana();
const hipRig = new THREE.Group();
hipRig.position.set(0.2, 0.02, 0.12);
hipRig.rotation.y = Math.PI / 2;
const hipInner = new THREE.Group();
hipInner.rotation.set(Math.PI, 0, 0.42);
hipInner.add(hipKatana.saya, hipKatana.sword);
hipRig.add(hipInner);
kojiro.hips.add(hipRig);
const handKatana = makeKatana();
holdInHand(kojiro.rH, handKatana.sword, -0.06);
// The ONE visible drawn blade. hipKatana.sword (sliding in the scabbard) and handKatana.sword (in the
// grip) are invisible reference frames; the visible blade follows the scabbard frame while it slides
// out, then blends into the grip frame over a few frames, so there is no swap and no jump.
hipKatana.sword.traverse((o) => { if (o.isMesh) o.visible = false; });
handKatana.sword.traverse((o) => { if (o.isMesh) o.visible = false; });
const blade = makeKatana().sword;
blade.matrixAutoUpdate = false;
scene.add(blade);
const _pa = new THREE.Vector3(), _pb = new THREE.Vector3(), _qa = new THREE.Quaternion(), _qb = new THREE.Quaternion(), _sc = new THREE.Vector3();
const flyingSaya = makeKatana().saya;
scene.add(flyingSaya);

const musashi = makeFigure({
  robe: '#3d4252', sleeve: '#3d4252', hakama: '#4b3e34', hakamaFold: '#3d322a',
  skin: '#efe3cc', collar: '#d9d2c2', obi: '#1f1b19', band: '#f3eee2', face: CAST.musashi?.face, eyes: CAST.musashi?.eyes,
});
scene.add(musashi.root);
// Musashi's weapon: the carved oar bokken (history) by default, or a katana
const MUSASHI_KATANA = CAST.musashi?.weapon === 'katana';
const musashiKatana = MUSASHI_KATANA ? makeKatana() : null;
const musashiBokken = MUSASHI_KATANA ? musashiKatana.sword : makeBokken();
holdInHand(musashi.rH, musashiBokken, MUSASHI_KATANA ? -0.06 : -0.05);
const flyingTail = new THREE.Group();
for (const sgn of [1, -1]) {
  const tp = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.16, 0.006), paper('#f3eee2', { repeat: 6 }));
  tp.position.x = sgn * 0.02;
  tp.rotation.z = sgn * 0.25;
  flyingTail.add(tp);
}
scene.add(flyingTail);

const boat = makeBoat();
scene.add(boat);
const boatman = makeFigure({ robe: '#7a756b', hakama: '#625d55', skin: '#efe3cc', kasa: true });
boatman.root.position.set(0, 0.06, 1.0);
boatman.root.rotation.y = Math.PI;
boat.add(boatman.root);
const oar = makeOar();
oar.position.set(0.35, 0.5, 1.9);
boat.add(oar);

// ---------- paper-shard bursts ----------
function makeBurst(n, colors, seed, power = 1) {
  const r = rng(seed);
  const g = new THREE.Group();
  scene.add(g);
  const tri = new THREE.Shape();
  tri.moveTo(0, 0.03); tri.lineTo(0.022, -0.018); tri.lineTo(-0.02, -0.014); tri.closePath();
  const geo = new THREE.ShapeGeometry(tri);
  const parts = [];
  for (let i = 0; i < n; i++) {
    const m = new THREE.Mesh(geo, paper(colors[i % colors.length], { repeat: 30, glow: 0.15 }));
    m.castShadow = true;
    const a = r() * Math.PI * 2, e = r() * 1.2 - 0.2, sp = (1.2 + r() * 3) * power;
    parts.push({ m, v: new THREE.Vector3(Math.cos(a) * Math.cos(e) * sp, Math.sin(e) * sp + 1.2, Math.sin(a) * Math.cos(e) * sp),
      w: new THREE.Vector3(r() * 14, r() * 14, r() * 14), s: 0.6 + r() * 1.6 });
    g.add(m);
  }
  return (t, t0, origin) => {
    const dt = t - t0;
    g.visible = dt >= 0 && dt < 3;
    if (!g.visible) return;
    const drag = (1 - Math.exp(-2.2 * dt)) / 2.2;
    for (const p of parts) {
      p.m.position.set(origin.x + p.v.x * drag, Math.max(0.01, origin.y + p.v.y * drag - 1.6 * dt * dt), origin.z + p.v.z * drag);
      p.m.rotation.set(p.w.x * dt, p.w.y * dt, p.w.z * dt);
      p.m.scale.setScalar(p.s * (dt < 2.2 ? 1 : 1 - (dt - 2.2) / 0.8));
    }
  };
}
const impactBurst = makeBurst(80, ['#a8322d', '#efe6d4', '#c49a45', '#f6eedf'], 9, 1);
const splashBurst = makeBurst(36, ['#f3ecdd', '#dfe6ee', '#efe5d0'], 21, 0.7);

// ---------- choreography: read from the film file (performances + events) ----------
const PI = Math.PI;
const POSES = await (await fetch('/library/poses.json')).json();
const EV = film.events ?? {};
const ev = (name, fallback) => EV[name] ?? fallback;
const PERF = film.performances ?? {};
const MOVES = await (await fetch('/library/moves.json')).json();
// Recorded-motion moves need their clips. loadClips fetches only the ones this library names.
const CLIPS = await loadClips(MOVES, async (n) => (await fetch(`/library/mocap/${n}.json`)).json());
const motionOf = (id) => {   // film.motion.overlap = anime layer, film.motion.lockFeet = planted feet + weight
  const m = makeMotion(resolveKeys(expandMoves(PERF[id].keys, MOVES, CLIPS), POSES), film.motion ?? {});
  return film.motion?.lockFeet ? lockFeet(m, film.duration ?? 36, film.motion.lockFeet) : m;
};
const kojiroMotion = motionOf('kojiro');
const musashiMotion = motionOf('musashi');
const boatPose = { ...BASE_POSE, ...POSES[PERF.musashi.boatPose ?? 'stand-blade-low'] };

const pair = {};
for (const d of film.duels ?? []) { pair[d.a] = d.b; pair[d.b] = d.a; }

/** REACTION LAYER: fighters respond to each other automatically inside film.duels windows.
 *  1. Eyes on the opponent: the head turns and tilts toward the other fighter's head (clamped).
 *  2. Threat response: when the opponent's sword arm moves fast, this fighter sinks and shifts weight
 *     back ~0.12 s later (human reaction time), then relaxes. */
const REACT_DELAY = 0.12;
function armSpeed(motion, t) {
  const a = motion(t), b = motion(t - 1 / 24);
  return Math.hypot(a.rsx - b.rsx, a.rex - b.rex, a.rwx - b.rwx) * 24;   // rad/s
}
function react(selfPose, selfMotion, otherMotion, t, duel) {
  const w = windowWeight([[duel.from, duel.to]], t, 0.4);
  if (w <= 0) return selfPose;
  const o = otherMotion(t);
  // 1. look at the opponent (in the fighter's own frame)
  const dx = o.x - selfPose.x, dz = o.z - selfPose.z;
  let yaw = Math.atan2(dx, dz) - selfPose.ry;
  yaw = Math.atan2(Math.sin(yaw), Math.cos(yaw));
  selfPose.hy += w * Math.max(-0.6, Math.min(0.6, yaw - selfPose.ty));
  selfPose.hx += w * Math.max(-0.15, Math.min(0.2, (selfPose.crouch - o.crouch) * 0.8));
  // 2. threat response from the opponent's swing speed, delayed by reaction time
  let threat = 0;
  for (let k = 0; k < 4; k++) threat = Math.max(threat, armSpeed(otherMotion, t - REACT_DELAY - k / 24));
  const tense = w * Math.min(1, Math.max(0, (threat - 2) / 6));
  selfPose.crouch += 0.05 * tense;
  selfPose.weight -= 0.2 * tense;
  selfPose.tx -= 0.04 * tense;
  return selfPose;
}

/** Life on top of the keyed motion: breathing while still, cloth trailing behind movement. */
function addLife(motion, t, pose, phase) {
  const prev = motion(t - 1 / 24);
  const vx = (pose.x - prev.x) * 24, vz = (pose.z - prev.z) * 24;
  const fwd = vx * Math.sin(pose.ry) + vz * Math.cos(pose.ry);      // speed along facing
  const side = vx * Math.cos(pose.ry) - vz * Math.sin(pose.ry);
  const still = Math.max(0, 1 - Math.hypot(vx, vz) * 3);
  pose.tx += 0.012 * Math.sin(t * 1.9 + phase) * still;            // breathing
  pose.hx += 0.008 * Math.sin(t * 1.9 + phase + 0.6) * still;
  pose.swayx += Math.max(-0.25, Math.min(0.25, -fwd * 0.12));      // hakama trails behind the step
  pose.sway += Math.max(-0.2, Math.min(0.2, side * 0.1));
  return pose;
}

function boatZ(t) {
  const t0 = ev('boat-arrives', 12.5);
  if (t < t0) return 17.5;
  if (t < t0 + 3.9) { const k = (t - t0) / 3.9; return 17.5 + (5.4 - 17.5) * (1 - Math.pow(1 - k, 3)); }
  return 5.4;
}

// ---------- camera ----------
const easeFn = { linear: (k) => k, inOut: (k) => 0.5 - 0.5 * Math.cos(Math.PI * k) };
function shotAt(t) {
  return film.shots.find((s) => t >= s.start && t < s.end) ?? film.shots[film.shots.length - 1];
}
const curves = new Map();
function placeCamera(shot, t) {
  if (shot.rig) {                                        // KUROKO rig
    const c = kuroko.at(shot, t);
    camera.position.set(...c.pos);
    camera.fov = c.fov;
    camera.updateProjectionMatrix();
    camera.up.set(0, 1, 0);
    camera.lookAt(...c.look);
    camera.rotateZ(c.roll * Math.PI / 180);
    return;
  }
  if (!curves.has(shot.id)) {
    curves.set(shot.id, {
      pos: new THREE.CatmullRomCurve3(shot.camera.map((k) => new THREE.Vector3(...k.pos))),
      look: new THREE.CatmullRomCurve3(shot.camera.map((k) => new THREE.Vector3(...k.look))),
    });
  }
  const c = curves.get(shot.id);
  const keys = shot.camera;
  const k = (easeFn[shot.ease] ?? easeFn.inOut)(Math.min(1, Math.max(0, (t - shot.start) / (shot.end - shot.start))));
  const tt = shot.start + k * (shot.end - shot.start);
  let i = 0;
  while (i < keys.length - 2 && tt > keys[i + 1].t) i++;
  const f = Math.min(1, Math.max(0, (tt - keys[i].t) / (keys[i + 1].t - keys[i].t)));
  const u = (i + f) / (keys.length - 1);
  camera.position.copy(c.pos.getPoint(u));
  camera.fov = keys[i].fov + (keys[i + 1].fov - keys[i].fov) * f;
  camera.updateProjectionMatrix();
  camera.lookAt(c.look.getPoint(u));
}

// ---------- overlays ----------
const titleEls = film.titles.map((tl) => {
  const el = document.createElement('div');
  el.className = 'title ' + tl.style;
  el.innerHTML = (tl.jp ? `<div class="jp">${tl.jp}</div>` : '') +
    (tl.en ? `<div class="en">${tl.en}</div>` : '') + (tl.sub ? `<div class="sub">${tl.sub}</div>` : '');
  document.getElementById('stage').appendChild(el);
  return el;
});
const fadeEl = document.getElementById('fade');
const flashEl = document.getElementById('flash');

// ---------- posing the fighters at a BODY time (hit-stops freeze this clock, not the camera, sparks or sound) ----------
const tmp = new THREE.Vector3();
const tDraw = ev('kojiro-draw', 18.25), tThrow = ev('kojiro-throws-scabbard', 20.05);
const tCut = ev('headband-cut', 25.45);
const boatUntil = PERF.musashi.rideBoatUntil ?? 0;
let FILM_TIME = 0, CONTACTS = null, wGrip = 0;
const eyeOpts = () => ({ fps: FPS, voice: VOICE, contacts: CONTACTS });
// the one visible drawn blade: scabbard-slide frame → grip frame, blended over ~6 frames once the tip clears
function composeBlade() {
  hipKatana.sword.matrixWorld.decompose(_pa, _qa, _sc);
  handKatana.sword.matrixWorld.decompose(_pb, _qb, _sc);
  blade.matrix.compose(_pa.lerp(_pb, wGrip), _qa.slerp(_qb, wGrip), _sc.set(1, 1, 1));
  blade.matrixWorld.copy(blade.matrix);                // blade sits directly in the scene
  blade.updateMatrixWorld(true);
}
const FIGHTERS = {
  kojiro: { id: 'kojiro', fig: kojiro, perf: PERF.kojiro, sword: blade, aimObject: handKatana.sword, bladeLen: handKatana.length,
    yOff: -0.012, material: 'steel', beforeAim: composeBlade, afterAim: composeBlade },
  musashi: { id: 'musashi', fig: musashi, perf: PERF.musashi, sword: musashiBokken, bladeLen: MUSASHI_KATANA ? musashiKatana.length : 0.8,
    yOff: MUSASHI_KATANA ? -0.012 : -0.01, material: MUSASHI_KATANA ? 'steel' : 'wood' },
};
function placeBoat(tb) {
  boat.position.set(0.6, -0.2 + 0.04 * Math.sin(tb * 1.6), boatZ(tb));
  boat.rotation.set(0.02 * Math.sin(tb * 1.1), 0, 0.03 * Math.sin(tb * 1.3));
}
function poseFighters(tb) {
  placeBoat(tb);
  // Kojirō: keyed motion from the film file + life + reactions + eyes
  const duel = (film.duels ?? [])[0];
  let kp = addLife(kojiroMotion, tb, kojiroMotion(tb), 0);
  if (duel) kp = react(kp, kojiroMotion, musashiMotion, tb, duel);
  combat.applyEyes(FIGHTERS.kojiro, kp, tb, FILM_TIME, eyeOpts());
  applyPose(kojiro, kp);
  // thumb push (3 cm), then the blade slides out along the scabbard (saya stays on the hip)
  const kDraw = Math.min(1, Math.max(0, (tb - tDraw) / 0.37));
  hipKatana.sword.position.x = -(0.03 * Math.min(1, kDraw * 6) + 0.72 * smooth(Math.max(0, (kDraw - 0.15) / 0.85)));
  // Musashi: rides the boat until rideBoatUntil, then keyed motion + walk cycle + life
  let mp;
  if (tb < boatUntil) {
    mp = { ...boatPose, x: boat.position.x, y: boat.position.y + 0.08, z: boat.position.z - 0.55, ry: PI, rz: boat.rotation.z };
  } else {
    mp = addLife(musashiMotion, tb, musashiMotion(tb), 1.3);
    if (duel) mp = react(mp, musashiMotion, kojiroMotion, tb, duel);
    if (windowWeight(PERF.musashi.walk, tb, 0.01) > 0) {
      const ph = tb * PI * 2 * 1.0;                // one stride cycle per second = two steps
      mp.phase = ph; mp.stride = 0.55;              // legs swing in opposite phase (solveLegs)
      mp.y += Math.abs(Math.sin(ph)) * 0.02;
      mp.sway += Math.sin(ph) * 0.06;
      mp.lsx += Math.sin(ph) * 0.25;
    }
  }
  combat.applyEyes(FIGHTERS.musashi, mp, tb, FILM_TIME, eyeOpts());
  applyPose(musashi, mp);
  handKatana.sword.quaternion.identity(); musashiBokken.quaternion.identity();   // clash aim turns these
  kojiro.root.updateMatrixWorld(true);
  musashi.root.updateMatrixWorld(true);
  // the right hand rests on, then grips, the handle while the blade is still in the scabbard
  const handOnHilt = windowWeight([[0, tDraw + 0.3]], tb, 0.12);
  if (handOnHilt > 0) reachHand(kojiro, 'r', hipKatana.sword.localToWorld(tmp.set(-0.08, -0.018, 0)).clone(), handOnHilt);
  wGrip = smooth(Math.min(1, Math.max(0, (tb - (tDraw + 0.3)) / 0.25)));
  composeBlade();
  // clash aim (film.clashes): the defender's wrist turns the blade across the attacker's
  combat.clashAim(film.clashes, FIGHTERS, tb);
  // two-hand grip: the left hand closes on the end of the handle (analytic arm IK, no pops)
  const wk = windowWeight(PERF.kojiro.twoHand, tb), wm = windowWeight(PERF.musashi.twoHand, tb);
  if (wk > 0) solveArm(kojiro, 'l', blade.localToWorld(tmp.set(-0.27, -0.018, 0)).clone(), null, wk);
  if (wk > 0) gripHand(kojiro, 'l', blade, wk);
  if (wm > 0) solveArm(musashi, 'l', musashiBokken.localToWorld(MUSASHI_KATANA ? tmp.set(-0.27, -0.018, 0) : tmp.set(-0.26, 0.002, 0)).clone(), null, wm);
  if (wm > 0) gripHand(musashi, 'l', musashiBokken, wm);
  kojiro.root.updateMatrixWorld(true);
  musashi.root.updateMatrixWorld(true);
  musashi.bandTail.visible = tb < tCut;
}

// ---------- COMBAT (engine/combat.js): blade contacts at 240 Hz → hit-stop, sparks, ribbon, impact frame, sound cues ----------
// Off with "combat": false. No contact can happen before Kojirō's blade is in his grip or while Musashi rides the boat.
const COMBAT_ON = film.combat !== false;
const C = COMBAT_ON
  ? combat.analyse({ film, fighters: [FIGHTERS.kojiro, FIGHTERS.musashi], pose: poseFighters, fps: FPS, dur: film.duration, symmetric: true,
    armed: (tb) => tb > tDraw + 0.55 && tb >= boatUntil })
  : { contacts: [], stops: [], cues: [], bodyT: (t) => t, filmT: (t) => t, tipSpeedAt: () => 0, events: { contacts: [], stops: [], cues: [] } };
const { contacts, stops, bodyT, filmT } = C;
CONTACTS = contacts;
// automatic whoosh / clash / scrape cues go to sound.mjs only when the film asks for them ("autoSounds")
window.EVENTS = { ...C.events, cues: film.autoSounds ? C.cues : [] };
// FIGHT DIRECTOR (engine/combat.js direct): reach, the defender's reaction time, the clash aim residual and the
// blade trajectories at 240 Hz → ONE verified event per strike (contact + sound + camera + damage read this one).
const DIR = COMBAT_ON ? combat.direct({ film, fighters: [FIGHTERS.kojiro, FIGHTERS.musashi], pose: poseFighters, C, fps: FPS }) : { strikes: [], findings: [] };
window.EVENTS.strikes = DIR.strikes;
window.EVENTS.fightDirector = DIR.findings;

// authored action times (shakes, impact, headband cut) are in body time: move them past the hit-stops
const SHAKES = (film.shakes ?? []).map((s) => ({ ...s, t: filmT(s.t) }));
const tHit = filmT(ev('impact', 25.6)), tCutF = filmT(tCut);
const INK_AT = (film.effects?.impactFrame?.at ?? []).map(filmT);   // ink frames on blows that are not blade contacts

// KUROKO camera operator: frames characters by name and reacts to their motion.
// Shots, rigs and anchor beats are timed to the action, so the camera runs on BODY time too: a hit-stop inserts
// frames into the film without pushing the cuts early. The punch, shakes, sparks, titles and sound run on film time.
const _bf = { origin: [0, 0, 0], x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] };
const _m4 = new THREE.Matrix4(), _e = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
const kuroko = makeKuroko({
  motions: { kojiro: kojiroMotion, musashi: musashiMotion },
  impacts: [...new Set([...(film.shakes ?? []).map((s) => s.t), ...(EV.impact !== undefined ? [EV.impact] : []),
    ...contacts.map((c) => c.tb).filter((t) => !(film.shakes ?? []).some((s) => Math.abs(s.t - t) < 0.1))])],
  pair,
  aspect: W / H,
  bladeFrame: () => {                                   // live frame of the drawn blade (for the blade rig)
    _m4.copy(blade.matrixWorld);
    _m4.extractBasis(_e[0], _e[1], _e[2]);
    const o = new THREE.Vector3().setFromMatrixPosition(_m4);
    _bf.origin = o.toArray(); _bf.x = _e[0].toArray(); _bf.y = _e[1].toArray(); _bf.z = _e[2].toArray();
    return _bf;
  },
});

// effects: smear ribbon, sparks, post FX (engine/fx.js, only when the film has "fxBase" or "fx")
const RIB = COMBAT_ON ? combat.makeRibbons(scene, [FIGHTERS.kojiro, FIGHTERS.musashi], { ribbon: film.effects?.ribbon, fps: FPS, pose: poseFighters, tipSpeedAt: C.tipSpeedAt }) : null;
const SPARKS = combat.makeSparks(scene, camera, contacts, { light: film.effects?.sparkLight ?? 6 });
const FX = (film.fxBase || film.fx) && !params.has('nofx') ? createFX(renderer, scene, camera, { width: W, height: H, seed: 7, fps: FPS }) : null;
const FX_TRACK = FX ? [...(film.fx ?? []).map((e) => (e.body ? { ...e, t: filmT(e.t) } : e)), ...combat.contactFx(contacts, film.effects?.contactFx)] : [];   // "body": true = timed to the action
if (FX) {                                               // particle fields named in fxBase / fx (dust, ember, petal, snow, ash, shard)
  const names = new Set([...Object.keys(film.fxBase?.particles ?? {}), ...(film.fx ?? []).filter((e) => e.effect === 'particles').map((e) => e.name)]);
  for (const n of names) {
    const o = film.fxParticles?.[n] ?? {};
    FX.particles({ name: n, kind: o.kind ?? n, center: o.center ?? [0, 1.5, 0], size: o.size ?? [7, 3.6, 7], ...o });
  }
}

// ---------- frame ----------
// GROUND FX (engine/groundfx.js), opt-in per film: effects.ground {} = dust on every dash / skid / landing (+ sound cues),
// effects.contactShadow {} = a soft pool of shadow under each fighter
const GFIGHT = [{ ...FIGHTERS.kojiro, motion: kojiroMotion }, { ...FIGHTERS.musashi, motion: musashiMotion }];
const GROUND = film.effects?.ground ? analyseGround({ fighters: GFIGHT, dur: film.duration, filmT, opts: film.effects.ground }) : null;
const DUST = GROUND ? makeDust(scene, GROUND.events, film.effects.ground) : null;
const CSHADOWS = film.effects?.contactShadow ? makeContactShadows(scene, GFIGHT, film.effects.contactShadow) : null;
if (GROUND && film.autoSounds) window.EVENTS.cues = [...window.EVENTS.cues, ...groundCues(GROUND.events, film.autoSounds.ground ?? {})].sort((a, b) => a.t - b.t);
if (GROUND) window.EVENTS.ground = GROUND.events.filter((e) => !['wake', 'skidding'].includes(e.kind));
let NO_DRAW = false;                                    // the audit measures a frame without drawing it
window.renderAt = (t) => {
  FILM_TIME = t;
  const tb = bodyT(t);
  const shot = shotAt(tb);
  world.setMode(shot.mode);
  world.update(t);

  // studio sword: draw the blade 9.6s → 11.8s
  studioKatana.sword.position.x = -0.78 * smooth(Math.min(1, Math.max(0, (t - ev('studio-blade-draw', 9.6)) / 2.2)));

  // fighters (and the boat they may ride) at body time
  poseFighters(tb);
  const row = tb < ev('boat-arrives', 12.5) + 3.9 ? Math.sin(tb * 2.4) : 0;
  oar.rotation.set(0.45, 0.25 * row, 0);
  applyPose(boatman, track([[0, { rsx: -0.9 + 0.3 * row, rsz: 0.3, rex: -0.6, lsx: -0.9 + 0.3 * row, lsz: -0.2, lex: -0.6, tx: 0.15 + 0.1 * row }]], tb));
  boatman.root.position.set(0, 0.06, 1.0);
  boatman.root.rotation.y = PI;

  hipKatana.saya.visible = tb < tThrow;
  // thrown scabbard
  const ks = (t - filmT(tThrow)) / 1.35;
  flyingSaya.visible = ks >= 0 && ks <= 1.0;
  if (flyingSaya.visible) {
    const a = new THREE.Vector3(0.35, 1.0, -0.6), b = new THREE.Vector3(1.9, -0.25, 6.4);
    flyingSaya.position.copy(a.lerp(b, ks)).add(new THREE.Vector3(0, 2.4 * 4 * ks * (1 - ks), 0));
    flyingSaya.rotation.set(0.3, 1.4 + ks * 2, ks * 11);
  }
  splashBurst(t, filmT(ev('scabbard-splash', 21.4)), new THREE.Vector3(1.9, -0.15, 6.4));

  const kt = (t - tCutF) / 3;
  flyingTail.visible = kt >= 0 && kt < 1;
  if (flyingTail.visible) {
    flyingTail.position.set(-0.7 * kt + 0.12 * Math.sin(kt * 14), 1.78 - 1.75 * smooth(kt), 0.9 + 1.2 * kt);
    flyingTail.rotation.set(Math.sin(kt * 11) * 1.2, kt * 6, Math.cos(kt * 9) * 0.8);
  }

  // smear ribbon (re-poses the recent past, then the present again)
  const impactFrame = COMBAT_ON && combat.isImpactFrame(film, contacts, t, FPS, INK_AT);
  if (RIB) RIB.update(tb, impactFrame);
  // hit-stop jitter: during a stop the fighters shiver ±6 mm in opposite directions on alternate frames
  if (stops.some((s) => t >= s.t && t < s.t + s.d)) {
    const sgn = Math.round(t * FPS) % 2 ? 1 : -1;
    kojiro.root.position.z += 0.006 * sgn; musashi.root.position.z -= 0.006 * sgn;
    kojiro.root.updateMatrixWorld(true); musashi.root.updateMatrixWorld(true);
    composeBlade();
  }

  // impact: paper shards burst from the point of the blow
  kojiro.head.getWorldPosition(tmp);
  impactBurst(t, tHit, tmp.clone().add(new THREE.Vector3(0, 0.22, 0)));

  // camera path from the shot list, then any shakes listed in film.shakes, then the punch of each blade contact
  placeCamera(shot, tb);
  for (const sh of SHAKES) {
    const k = (t - sh.t) / sh.dur;
    if (k > 0 && k < 1) {
      const s = (1 - k) * sh.amp;   // strongest at the hit, fading out
      camera.position.x += Math.sin(t * 90) * s;
      camera.position.y += Math.cos(t * 77) * s;
    }
  }
  if (contacts.length) {                               // KUROKO rigs already punch the fov in; keyframe shots get it here
    const pu = combat.punch(contacts, t, camera, camera.fov, { fov: shot.rig ? 0 : 7 });
    camera.fov = pu.fov; camera.updateProjectionMatrix();
    camera.rotateZ((pu.roll * Math.PI) / 180);
  }
  const fl = SPARKS.update(t);                          // sparks + flash light
  DUST?.update(t);
  CSHADOWS?.update();

  // overlays: titles, fades, flash
  film.titles.forEach((tl, i) => {
    const a = Math.min(1, (t - tl.start) / 0.5, (tl.end - t) / 0.5);
    titleEls[i].style.opacity = Math.max(0, a);
  });
  let fade = 0;
  const edges = film.shots.filter((s) => s.mode === 'studio').flatMap((s) => [s.start, s.end]);
  for (const e of edges) fade = Math.max(fade, 1 - Math.abs(tb - e) / 0.35);
  fade = Math.max(fade, 1 - t / 0.8, (t - (film.duration - 1)) / 1);
  fadeEl.style.opacity = Math.min(1, Math.max(0, fade));
  const hitFlash = t > tHit && t < tHit + 0.35 ? 0.55 * (1 - (t - tHit) / 0.35) : 0;
  const inkPost = FX_TRACK.some((e) => e.effect === 'ink-impact' && t >= e.t && t < e.t + (e.dur ?? 2 / FPS));   // keep the ink frame clean
  flashEl.style.opacity = impactFrame || inkPost ? 0 : Math.max(hitFlash, Math.min(0.35, fl * 0.3));

  if (NO_DRAW) return;
  if (impactFrame) {                                   // ONE frame: ink silhouettes on a washi page
    combat.renderInkFrame(renderer, scene, camera, [kojiro.root, musashi.root, blade], RIB.meshes);
    return;
  }
  if (FX) FX.render(t, fxAt(t, FX_TRACK, film.fxBase, FPS));
  else renderer.render(scene, camera);
};
// studio QA hooks (tools/audit.mjs, docs/AUDIT.md)
installAudit({
  scene, camera, W, H, fps: FPS, dur: film.duration, page: 'main',
  fighters: () => [FIGHTERS.kojiro, FIGHTERS.musashi],
  meta: { effects: { ground: !!GROUND, contactShadow: !!CSHADOWS, smear: film.effects?.ribbon?.style ?? 'light', fx: !!FX },
    shots: film.shots.map((s) => ({ id: s.id, start: s.start, end: s.end })) },
  stage(t) {
    NO_DRAW = true; try { window.renderAt(t); } finally { NO_DRAW = false; }
    const tb = bodyT(t), shot = shotAt(tb);
    const names = [...(shot.rig?.subjects ?? []), shot.rig?.subject, shot.rig?.who].filter((n) => typeof n === 'string');
    const subjects = names.length ? [...new Set(names.map((n) => n.split('.')[0]))].filter((id) => FIGHTERS[id]) : null;
    return { tb, shot: film.shots.indexOf(shot), free: shot.mode === 'studio' || !shot.rig, subjects, smear: RIB?.level,
      impactFrame: COMBAT_ON && combat.isImpactFrame(film, contacts, t, FPS, INK_AT) };
  },
});
window.probe = (tb) => {                               // blade positions and distance at a body time (debugging clashes)
  poseFighters(tb);
  const A = combat.bladeSeg(FIGHTERS.kojiro), B = combat.bladeSeg(FIGHTERS.musashi);
  const r3 = (v) => v.toArray().map((x) => +x.toFixed(3));
  return { kojiro: { tip: r3(A.tip), guard: r3(A.guard) }, musashi: { tip: r3(B.tip), guard: r3(B.guard) }, d: +combat.closestSegSeg(A.a, A.tip, B.a, B.tip).d.toFixed(3) };
};

await document.fonts.ready;
window.FILM = film;
window.READY = true;

// Preview mode: ?t=12.3 shows one frame; otherwise plays in real time.
if (!params.has('render')) {
  if (params.has('t')) window.renderAt(parseFloat(params.get('t')));
  else {
    const t0 = performance.now();
    const loop = () => { window.renderAt(((performance.now() - t0) / 1000) % film.duration); requestAnimationFrame(loop); };
    loop();
  }
}

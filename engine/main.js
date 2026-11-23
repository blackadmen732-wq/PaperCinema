// Film engine: loads a shot list (film/*.json), builds the paper world,
// runs the choreography, and exposes window.renderAt(t) so every frame
// is deterministic (the renderer captures frame by frame → MP4).
import * as THREE from 'three';
import { buildWorld, STUDIO_X } from './world.js';
import { makeKatana, makeBokken, makeBoat, makeOar } from './props.js';
import { makeFigure, holdInHand, applyPose, track, smooth, makeMotion, resolveKeys, windowWeight, reachLeftHand, BASE_POSE } from './figure.js';
import { paper, rng } from './paper.js';

const params = new URLSearchParams(location.search);
const film = await (await fetch(params.get('film') ?? '/film/ganryujima.json')).json();
const W = film.width, H = film.height;

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
const barH = Math.max(0, (H - W / (film.letterbox || W / H)) / 2);
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
  skin: '#efe3cc', collar: '#f6eedf', obi: '#2a1d1a',
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
const flyingSaya = makeKatana().saya;
scene.add(flyingSaya);

const musashi = makeFigure({
  robe: '#3d4252', sleeve: '#3d4252', hakama: '#4b3e34', hakamaFold: '#3d322a',
  skin: '#efe3cc', collar: '#d9d2c2', obi: '#1f1b19', band: '#f3eee2',
});
scene.add(musashi.root);
const musashiBokken = makeBokken();
holdInHand(musashi.rH, musashiBokken, -0.05);
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
const motionOf = (id) => makeMotion(resolveKeys(PERF[id].keys, POSES));
const kojiroMotion = motionOf('kojiro');
const musashiMotion = motionOf('musashi');
const boatPose = { ...BASE_POSE, ...POSES[PERF.musashi.boatPose ?? 'stand-blade-low'] };

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

// ---------- frame ----------
const tmp = new THREE.Vector3();
window.renderAt = (t) => {
  const shot = shotAt(t);
  world.setMode(shot.mode);
  world.update(t);

  // studio sword: draw the blade 9.6s → 11.8s
  studioKatana.sword.position.x = -0.78 * smooth(Math.min(1, Math.max(0, (t - ev('studio-blade-draw', 9.6)) / 2.2)));

  // boat + boatman
  boat.position.set(0.6, -0.2 + 0.04 * Math.sin(t * 1.6), boatZ(t));
  boat.rotation.set(0.02 * Math.sin(t * 1.1), 0, 0.03 * Math.sin(t * 1.3));
  const row = t < ev('boat-arrives', 12.5) + 3.9 ? Math.sin(t * 2.4) : 0;
  oar.rotation.set(0.45, 0.25 * row, 0);
  applyPose(boatman, track([[0, { rsx: -0.9 + 0.3 * row, rsz: 0.3, rex: -0.6, lsx: -0.9 + 0.3 * row, lsz: -0.2, lex: -0.6, tx: 0.15 + 0.1 * row }]], t));
  boatman.root.position.set(0, 0.06, 1.0);
  boatman.root.rotation.y = PI;

  // Kojirō: keyed motion from the film file + life
  applyPose(kojiro, addLife(kojiroMotion, t, kojiroMotion(t), 0));
  const tDraw = ev('kojiro-draw', 18.25), tThrow = ev('kojiro-throws-scabbard', 20.05);
  hipKatana.sword.position.x = -0.75 * smooth(Math.min(1, Math.max(0, (t - tDraw) / 0.37)));
  hipKatana.sword.visible = t < tDraw + 0.37;
  handKatana.sword.visible = t >= tDraw + 0.37;
  hipKatana.saya.visible = t < tThrow;
  // thrown scabbard
  const ks = (t - tThrow) / 1.35;
  flyingSaya.visible = ks >= 0 && ks <= 1.0;
  if (flyingSaya.visible) {
    const a = new THREE.Vector3(0.35, 1.0, -0.6), b = new THREE.Vector3(1.9, -0.25, 6.4);
    flyingSaya.position.copy(a.lerp(b, ks)).add(new THREE.Vector3(0, 2.4 * 4 * ks * (1 - ks), 0));
    flyingSaya.rotation.set(0.3, 1.4 + ks * 2, ks * 11);
  }
  splashBurst(t, ev('scabbard-splash', 21.4), new THREE.Vector3(1.9, -0.15, 6.4));

  // Musashi: rides the boat until rideBoatUntil, then keyed motion + walk cycle + life
  let mp;
  const boatUntil = PERF.musashi.rideBoatUntil ?? 0;
  if (t < boatUntil) {
    mp = { ...boatPose, x: boat.position.x, y: boat.position.y + 0.08, z: boat.position.z - 0.55, ry: PI, rz: boat.rotation.z };
  } else {
    mp = addLife(musashiMotion, t, musashiMotion(t), 1.3);
    if (windowWeight(PERF.musashi.walk, t, 0.01) > 0) {
      const ph = t * PI * 2 * 1.7;
      mp.y += Math.abs(Math.sin(ph)) * 0.025;
      mp.sway += Math.sin(ph) * 0.06;
      mp.lsx += Math.sin(ph) * 0.25;
    }
  }
  applyPose(musashi, mp);

  // two-hand grip: left hand finds the end of the handle (inverse kinematics)
  kojiro.root.updateMatrixWorld(true);
  musashi.root.updateMatrixWorld(true);
  if (handKatana.sword.visible) reachLeftHand(kojiro, handKatana.sword.localToWorld(tmp.set(-0.27, -0.018, 0)).clone(), windowWeight(PERF.kojiro.twoHand, t));
  reachLeftHand(musashi, musashiBokken.localToWorld(tmp.set(-0.26, 0.002, 0)).clone(), windowWeight(PERF.musashi.twoHand, t));

  const tCut = ev('headband-cut', 25.45);
  musashi.bandTail.visible = t < tCut;
  const kt = (t - tCut) / 3;
  flyingTail.visible = kt >= 0 && kt < 1;
  if (flyingTail.visible) {
    flyingTail.position.set(-0.7 * kt + 0.12 * Math.sin(kt * 14), 1.78 - 1.75 * smooth(kt), 0.9 + 1.2 * kt);
    flyingTail.rotation.set(Math.sin(kt * 11) * 1.2, kt * 6, Math.cos(kt * 9) * 0.8);
  }

  // impact: paper shards burst from the point of the blow
  kojiro.head.getWorldPosition(tmp);
  impactBurst(t, ev('impact', 25.6), tmp.clone().add(new THREE.Vector3(0, 0.22, 0)));

  // camera path from the shot list, then any shakes listed in film.shakes
  placeCamera(shot, t);
  for (const sh of film.shakes ?? []) {
    const k = (t - sh.t) / sh.dur;
    if (k > 0 && k < 1) {
      const s = (1 - k) * sh.amp;   // strongest at the hit, fading out
      camera.position.x += Math.sin(t * 90) * s;
      camera.position.y += Math.cos(t * 77) * s;
    }
  }

  // overlays: titles, fades, flash
  film.titles.forEach((tl, i) => {
    const a = Math.min(1, (t - tl.start) / 0.5, (tl.end - t) / 0.5);
    titleEls[i].style.opacity = Math.max(0, a);
  });
  let fade = 0;
  const edges = film.shots.filter((s) => s.mode === 'studio').flatMap((s) => [s.start, s.end]);
  for (const e of edges) fade = Math.max(fade, 1 - Math.abs(t - e) / 0.35);
  fade = Math.max(fade, 1 - t / 0.8, (t - (film.duration - 1)) / 1);
  fadeEl.style.opacity = Math.min(1, Math.max(0, fade));
  const tHit = ev('impact', 25.6);
  flashEl.style.opacity = t > tHit && t < tHit + 0.35 ? 0.55 * (1 - (t - tHit) / 0.35) : 0;

  renderer.render(scene, camera);
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

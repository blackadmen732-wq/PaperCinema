// FX DEMO page: one paper figure, each engine/fx.js effect in turn (film/fx-demo.json, vertical 720×1280).
//   node engine/render.mjs --page engine/fx-demo.html --film film/fx-demo.json --still 1,4,6.5 --prefix fx-
// Pure function of time (window.renderAt(t)); the page is also a usage example for fx.js.
import * as THREE from 'three';
import { buildWorld } from './world.js';
import { paper } from './paper.js';
import { makeKatana } from './props.js';
import { loadCharacter } from './library.js';
import { makeFigure, holdInHand, applyPose, BASE_POSE, solveArm } from './figure.js';
import { createFX, fxAt, shake, traumaAt } from './fx.js';

const params = new URLSearchParams(location.search);
const film = await (await fetch(params.get('film') ?? '/film/fx-demo.json')).json();
const W = film.width ?? 720, H = film.height ?? 1280, FPS = film.fps ?? 24, DUR = film.duration;

const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('c'), antialias: false, preserveDrawingBuffer: true });
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
const camera = new THREE.PerspectiveCamera(34, W / H, 0.02, 600);
const world = buildWorld(scene);

// ---------- a dark paper hall (demo-only set, far from the island): one hard key from high behind-left, the
// moody "70% darkness, one shaft, strong rim" recipe from research/reference-videos.md ----------
const HALL_X = -200;
const hall = new THREE.Group(); hall.position.x = HALL_X; scene.add(hall);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), paper('#2b2420', { repeat: 0.8 }));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; hall.add(floor);
const wall = new THREE.Mesh(new THREE.PlaneGeometry(30, 12), paper('#1d1816', { repeat: 0.6 }));
wall.position.set(0, 6, -5); wall.receiveShadow = true; hall.add(wall);
for (const [x, z] of [[-2.6, -3.2], [2.4, -3.0], [-4.2, -1.0], [4.0, -0.6]]) {   // cut-paper pillars
  const pil = new THREE.Mesh(new THREE.BoxGeometry(0.42, 7, 0.42), paper('#3a2d26', { repeat: 2 }));
  pil.position.set(x, 3.5, z); pil.castShadow = pil.receiveShadow = true; hall.add(pil);
}
const hallKey = new THREE.SpotLight(0xffc98a, 0, 14, 0.34, 0.55, 1.2);
hallKey.position.set(-1.6, 5.2, -2.2); hallKey.target.position.set(0.2, 0.8, 0.4);
hallKey.castShadow = true; hallKey.shadow.mapSize.set(1024, 1024);
hall.add(hallKey, hallKey.target);
const hallRim = new THREE.PointLight(0xff9a4a, 0, 4, 1.5); hallRim.position.set(0.6, 1.8, -1.2); hall.add(hallRim);

// ---------- the figure ----------
const POSES = await (await fetch('/library/poses.json')).json();
const preset = await loadCharacter(film.character ?? 'kojiro');
const fig = makeFigure({ ...preset.colors, ...preset.accessories, band: preset.accessories.band ?? undefined,
  haori: preset.accessories.haori ?? undefined, face: 'eyes' });
scene.add(fig.root);
const k = makeKatana();
holdInHand(fig.rH, k.sword, -0.06);
const eyeBase = fig.eyeMat?.emissive.clone();

// ---------- FX: one stack, plus the scene-space pieces it owns ----------
const fx = createFX(renderer, scene, camera, { width: W, height: H, seed: 7, fps: FPS });
fx.shafts({ name: 'key', origin: [HALL_X - 1.6, 5.2, -2.2], target: [HALL_X + 0.4, 0, 0.8], count: 8, width: 0.55, spread: 1.3, color: [1.0, 0.74, 0.45], intensity: 0.24 });
const parts = {
  dust: fx.particles({ name: 'dust', kind: 'dust', center: [0, 1.5, 0.3], size: [4, 3.2, 4] }),
  ember: fx.particles({ name: 'ember', kind: 'ember', center: [0, 1.4, 0.2], size: [4, 3.4, 4], color: [1.0, 0.28, 0.12] }),
  petal: fx.particles({ name: 'petal', kind: 'petal', center: [0, 1.5, 0.6], size: [5, 3.6, 5] }),
  snow: fx.particles({ name: 'snow', kind: 'snow', center: [0, 1.6, 0.6], size: [6, 4, 6] }),
  ash: fx.particles({ name: 'ash', kind: 'ash', center: [0, 1.6, 0.6], size: [6, 4, 6] }),
};
const partCenters = Object.fromEntries(Object.entries(parts).map(([n, h]) => [n, h.material.uniforms.uCenter.value.clone()]));

// ---------- sections ----------
const sections = film.sections;
const sectionAt = (t) => { let s = sections[0]; for (const x of sections) if (t >= x.t) s = x; return s; };
const label = document.getElementById('label');
const v = (a) => new THREE.Vector3(...a);
function point(name) {
  fig.root.updateMatrixWorld(true);
  if (name === 'tip') return k.sword.localToWorld(new THREE.Vector3(k.length * 0.98, -0.012, 0));
  if (name === 'edge') return k.sword.localToWorld(new THREE.Vector3(k.length * 0.72, -0.016, 0));
  if (name === 'eyes') return fig.head.localToWorld(new THREE.Vector3(0, 0.11, 0.06));
  return Array.isArray(name) ? v(name) : name;
}

window.renderAt = (t) => {
  const s = sectionAt(t), lt = t - s.t, inHall = s.mode === 'hall', ox = inHall ? HALL_X : 0;
  world.setMode(inHall ? 'studio' : 'dawn');   // studio mode = dark sky, no fog, dim lights
  hallKey.intensity = inHall ? (s.key ?? 70) : 0; hallRim.intensity = inHall ? (s.rim ?? 6) : 0;
  world.update(t);
  // pose: named pose + slow breathing; left hand on the handle
  const p = { ...BASE_POSE, ...POSES[s.pose ?? 'chudan'], x: ox, z: 0, ry: 0 };
  p.cx = (p.cx ?? 0) + 0.015 * Math.sin(t * 2 * Math.PI * 0.3);
  p.hx = (p.hx ?? 0) + 0.02;
  applyPose(fig, p);
  fig.root.updateMatrixWorld(true);
  if (!['stand-blade-low', 'low-ready', 'zanshin'].includes(s.pose)) {
    solveArm(fig, 'l', k.sword.localToWorld(new THREE.Vector3(-0.27, -0.018, 0)), null, 1);
    fig.root.updateMatrixWorld(true);
  }
  if (fig.eyeMat) {
    fig.eyeMat.emissive.copy(s.eyeColor ? new THREE.Color(s.eyeColor) : eyeBase);
    fig.eyeMat.emissiveIntensity = s.eyes ?? 1.4;
  }
  // camera: a slow push-in along the look line, then trauma shake from the section's hits
  const c = s.cam, pos = v(c.pos).add(new THREE.Vector3(ox, 0, 0)), look = v(c.look).add(new THREE.Vector3(ox, 0, 0));
  pos.lerp(look, (c.push ?? 0) * lt);
  camera.fov = c.fov ?? 34; camera.updateProjectionMatrix();
  camera.position.copy(pos); camera.up.set(0, 1, 0); camera.lookAt(look); camera.updateMatrixWorld();
  shake(camera, t, { trauma: traumaAt(lt, s.hits ?? []), pos: 0.04, rollDeg: 3 });
  // particles follow the figure into the hall
  for (const [n, h] of Object.entries(parts)) h.material.uniforms.uCenter.value.copy(partCenters[n]).add(new THREE.Vector3(ox, 0, 0));
  // effect params: section base + its events (section-relative times → absolute), glint points resolved on the body
  const track = (s.fx ?? []).map((e) => ({ ...e, t: s.t + e.t, ...(e.at ? { at: point(e.at) } : {}) }));
  const fp = fxAt(t, track, s.base ?? {}, FPS);
  label.innerHTML = `${s.name}<small>engine/fx.js · ${sections.indexOf(s) + 1}/${sections.length}</small>`;
  label.style.color = fp.ink?.amount > 0.5 ? '#1a1410' : '#f3e7cf';
  label.style.textShadow = fp.ink?.amount > 0.5 ? 'none' : '';
  window.FX_PARAMS = fp;   // for debugging: the params of the last rendered frame
  fx.render(t, fp);
};

await document.fonts.ready;
window.FILM = film;
window.fx = fx;   // debugging handle
window.READY = true;
if (!params.has('render')) {
  if (params.has('t')) window.renderAt(parseFloat(params.get('t')));
  else { const t0 = performance.now(); const loop = () => { window.renderAt(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); }
}

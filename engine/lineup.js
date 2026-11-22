// Library lineup: shows presets side by side.
//   ?show=swords&swords=shiokaze,kurenai-oni,byakko,yamikaze
//   ?show=characters&characters=musashi,kojiro,ronin
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { loadParts, loadSword, loadCharacter, buildSword, buildCharacter } from './library.js';
import { holdInHand, applyPose, BASE_POSE } from './figure.js';
import { paper } from './paper.js';

const params = new URLSearchParams(location.search);
const film = await (await fetch(params.get('film') ?? '/film/lineup.json')).json();
const W = film.width, H = film.height;
const show = params.get('show') ?? 'swords';

const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('c'), antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = show === 'swords' ? 1.25 : 1.05;
renderer.shadowMap.enabled = true;
document.getElementById('stage').style.width = W + 'px';
document.getElementById('stage').style.height = H + 'px';

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(30, W / H, 0.01, 60);
const parts = await loadParts();
const labels = document.getElementById('labels');
const label = (text, xPct) => {
  const d = document.createElement('div');
  d.className = 'label';
  d.style.left = xPct + '%';
  d.textContent = text;
  labels.appendChild(d);
};

let glowMats = [];
let anyGlow = false;
let envScene, strips = [];

if (show === 'swords') {
  const names = (params.get('swords') ?? 'shiokaze,kurenai-oni,byakko,yamikaze').split(',');
  scene.background = new THREE.Color('#050505');
  const gap = 0.36;
  for (let i = 0; i < names.length; i++) {
    const spec = await loadSword(names[i]);
    const k = buildSword(spec, parts, 'metal');
    const g = new THREE.Group();
    g.add(k.sword);
    k.sword.rotation.z = Math.PI / 2;   // blade pointing up
    k.sword.position.x = -0.04;
    g.add(k.saya);
    k.saya.rotation.z = Math.PI / 2;
    k.saya.position.set(0.1, 0.0, -0.02);
    g.position.set((i - (names.length - 1) / 2) * gap, -0.1, 0);
    g.rotation.y = -0.35;
    scene.add(g);
    if (k.glowMaterial) { glowMats.push(k.glowMaterial); anyGlow = true; }
    label(spec.name, 50 + ((i - (names.length - 1) / 2) * 22));
  }
  camera.position.set(0, 0.35, 2.75);
  camera.lookAt(0, 0.3, 0);
  // light studio captured into reflections
  envScene = new THREE.Scene();
  envScene.background = new THREE.Color('#020202');
  const strip = (w, h, c, k) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(c).multiplyScalar(k), side: THREE.DoubleSide }));
    envScene.add(m); strips.push(m); return m;
  };
  strip(1.6, 9, '#ffffff', 7); strip(1.0, 9, '#ffd9a8', 5); strip(8, 0.8, '#bcd4ff', 3);
  const key = new THREE.SpotLight(0xffffff, 30, 12, 0.7, 0.8, 1.5);
  key.position.set(1.2, 2.2, 2.4);
  scene.add(key, new THREE.AmbientLight(0xffffff, 0.08));
} else {
  const names = (params.get('characters') ?? 'musashi,kojiro,ronin').split(',');
  const outfits = (params.get('outfits') ?? '').split(',');
  scene.background = new THREE.Color('#d9c4a0');
  scene.add(new THREE.HemisphereLight(0xfff0d8, 0x3a4560, 1.0));
  const sun = new THREE.DirectionalLight(0xffc27e, 2.6);
  sun.position.set(-3, 5, 4);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -4, right: 4, top: 4, bottom: -4 });
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0xffa860, 2.0);
  rim.position.set(2, 3, -4);
  scene.add(rim);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), paper('#cdb48a', { repeat: 1 }));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);
  const back = new THREE.Mesh(new THREE.PlaneGeometry(20, 8), paper('#e8d3ac', { repeat: 0.5, glow: 0.25, glowColor: '#f3b878' }));
  back.position.set(0, 3, -3);
  scene.add(back);
  const gap = names.length > 3 ? 1.0 : 1.25;
  for (let i = 0; i < names.length; i++) {
    let preset = await loadCharacter(names[i]);
    if (outfits[i]) {
      // an outfit swaps cloth colours/patterns on the same shared body
      const o = await (await fetch(`/library/outfits/${outfits[i]}.json`)).json();
      const acc = { ...preset.accessories };
      if ('haori' in o.colors) acc.haori = o.colors.haori;
      preset = { ...preset, name: o.name, colors: { ...preset.colors, ...o.colors }, accessories: acc };
    }
    const f = buildCharacter(preset);
    scene.add(f.root);
    applyPose(f, { ...BASE_POSE, x: (i - (names.length - 1) / 2) * gap, ry: 0.25 - i * 0.25,
      rsx: -0.75, rsz: 0.3, rex: -0.6, lsx: -0.7, lsz: -0.3, lex: -0.6 });
    if (preset.weapon && preset.weapon !== 'bokken') {
      const k = buildSword(await loadSword(preset.weapon), parts, 'paper');
      holdInHand(f.rH, k.sword, -0.06);
    }
    label(preset.name, 50 + ((i - (names.length - 1) / 2) * (names.length > 3 ? 23 : 30)));
  }
  camera.position.set(0, 1.25, 5.6);
  camera.lookAt(0, 1.0, 0);
}

let composer = null;
if (anyGlow) {
  composer = new EffectComposer(renderer);
  composer.setSize(W, H);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(W, H), 0.6, 0.4, 2.2));
  composer.addPass(new OutputPass());
}
const pmrem = new THREE.PMREMGenerator(renderer);
let envRT = null;

window.renderAt = (t) => {
  if (envScene) {
    const u = (t % film.duration) / film.duration;
    strips[0].position.set(-4 + u * 8, 1.5, 3.5); strips[0].lookAt(0, 0, 0);
    strips[1].position.set(3.5, 0.5, -2 + u * 4); strips[1].lookAt(0, 0, 0);
    strips[2].position.set(0, 4, 2.5 - u * 3); strips[2].lookAt(0, 0, 0);
    if (envRT) envRT.dispose();
    envRT = pmrem.fromScene(envScene, 0.015);
    scene.environment = envRT.texture;
  }
  const beat = Math.pow(Math.max(0, Math.sin(t * Math.PI * 1.4)), 12);
  for (const g of glowMats) g.emissiveIntensity = 3.5 + beat * 4;
  if (composer) composer.render(); else renderer.render(scene, camera);
};
window.FILM = film;
window.READY = true;
if (!params.has('render')) {
  const t0 = performance.now();
  const loop = () => { window.renderAt((performance.now() - t0) / 1000); requestAnimationFrame(loop); };
  loop();
}

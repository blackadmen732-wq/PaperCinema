// Look-development stage for weapons: the same sword in different render modes.
//   ?mode=metal    real polished steel with moving light reflections
//   ?mode=demonic  black steel, crimson glow from the temper line, bloom
//   ?mode=ink      black-and-white sumi-e / manga ink panel for story moments
// Reflections: a hidden "light studio" (moving softbox strips) is captured
// every frame into an environment map, so the highlights really travel
// along the blade as the lights or camera move.
import * as THREE from 'three';
import { OutlineEffect } from 'three/addons/effects/OutlineEffect.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { makeKatana } from './props.js';

const params = new URLSearchParams(location.search);
const film = await (await fetch(params.get('film') ?? '/film/lookdev.json')).json();
const mode = params.get('mode') ?? 'metal';
const W = film.width, H = film.height;

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = mode === 'ink' ? THREE.NoToneMapping : THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = mode === 'metal' ? 1.5 : 1.0;
document.getElementById('stage').style.width = W + 'px';
document.getElementById('stage').style.height = H + 'px';

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(30, W / H, 0.01, 50);

// ---------- materials per mode ----------
const phys = (o) => new THREE.MeshPhysicalMaterial(o);
let materials;
if (mode === 'ink') {
  const grad = new THREE.DataTexture(new Uint8Array([20, 20, 20, 255, 140, 140, 140, 255, 255, 255, 255, 255]), 3, 1);
  grad.minFilter = grad.magFilter = THREE.NearestFilter;
  grad.needsUpdate = true;
  const toon = (c) => new THREE.MeshToonMaterial({ color: c, gradientMap: grad, side: THREE.DoubleSide });
  materials = {
    blade: toon('#f4f4f4'), hamon: toon('#ffffff'), copper: toon('#9a9a9a'), iron: toon('#3a3a3a'),
    ito: toon('#111111'), same: toon('#e8e8e8'), gold: toon('#bdbdbd'), lacquer: toon('#0c0c0c'),
    sageo: toon('#222222'), horn: toon('#1a1a1a'),
  };
} else {
  const demonic = mode === 'demonic';
  materials = {
    blade: phys({ color: demonic ? '#2a2a30' : '#dfe3e8', metalness: 1, roughness: demonic ? 0.16 : 0.07, side: THREE.DoubleSide }),
    hamon: phys({ color: demonic ? '#120203' : '#f4f3ef', metalness: demonic ? 0.2 : 1, roughness: 0.32,
      emissive: demonic ? '#ff1e14' : '#000000', emissiveIntensity: demonic ? 2.2 : 0, side: THREE.DoubleSide }),
    copper: phys({ color: '#c98b52', metalness: 1, roughness: 0.22 }),
    iron: phys({ color: '#4a4542', metalness: 1, roughness: 0.42 }),
    ito: phys({ color: '#141318', roughness: 0.85, sheen: 1, sheenColor: '#3a3a44', sheenRoughness: 0.4 }),
    same: phys({ color: demonic ? '#a3151a' : '#e6ddc8', roughness: 0.6,
      emissive: demonic ? '#ff1e14' : '#000000', emissiveIntensity: demonic ? 0.35 : 0, side: THREE.DoubleSide }),
    gold: phys({ color: '#d7a748', metalness: 1, roughness: 0.18 }),
    lacquer: phys({ color: '#080708', roughness: 0.12, clearcoat: 1, clearcoatRoughness: 0.05 }),
    sageo: phys({ color: '#9e1f1c', roughness: 0.8, sheen: 1, sheenColor: '#ff5a4a' }),
    horn: phys({ color: '#1c1917', roughness: 0.3, clearcoat: 0.6 }),
  };
}

// ---------- the sword ----------
const k = makeKatana({ materials });
const rig = new THREE.Group();
rig.add(k.sword, k.saya);
k.saya.position.set(0.1, -0.11, 0.02);   // scabbard lies beside the drawn blade
k.saya.rotation.z = 0.03;
rig.rotation.set(0.15, -0.35, 0.95);       // diagonal, like a poster
scene.add(rig);
rig.traverse((m) => { if (m.isMesh) { m.castShadow = false; } });

// ---------- light studio (captured into reflections) ----------
const envScene = new THREE.Scene();
envScene.background = new THREE.Color(mode === 'demonic' ? '#050203' : '#020202');
const strip = (w, h, color, intensity) => {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h),
    new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), side: THREE.DoubleSide }));
  envScene.add(m);
  return m;
};
const s1 = strip(1.6, 9, '#ffffff', 7);
const s2 = strip(1.0, 9, mode === 'demonic' ? '#ff3020' : '#ffd9a8', 5);
const s3 = strip(8, 0.8, '#bcd4ff', 3);
const floorGlow = strip(6, 6, mode === 'demonic' ? '#400606' : '#1a1410', 1);
floorGlow.rotation.x = -Math.PI / 2; floorGlow.position.y = -3;
const pmrem = new THREE.PMREMGenerator(renderer);
let envRT = null;

// direct lights for non-metal parts
const key = new THREE.SpotLight(0xffffff, 30, 12, 0.6, 0.8, 1.5);
key.position.set(1.2, 2.2, 2.4);
scene.add(key, key.target);
scene.add(new THREE.AmbientLight(0xffffff, mode === 'ink' ? 1.2 : 0.08));
const ink = new THREE.DirectionalLight(0xffffff, 2.2);
ink.position.set(-1, 2, 2);
if (mode === 'ink') scene.add(ink);
const ember = new THREE.PointLight(0xff2a1a, 1, 0.6, 2);
if (mode === 'demonic') scene.add(ember);

scene.background = new THREE.Color(mode === 'ink' ? '#f7f5f0' : '#050505');

// ---------- render paths ----------
let outline = null, composer = null;
if (mode === 'ink') outline = new OutlineEffect(renderer, { defaultThickness: 0.006, defaultColor: [0, 0, 0] });
if (mode === 'demonic') {
  composer = new EffectComposer(renderer);
  composer.setSize(W, H);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(W, H), 0.9, 0.5, 0.75));
  composer.addPass(new OutputPass());
}

if (mode === 'ink') {
  const t = document.createElement('div');
  t.className = 'ink-text';
  t.innerHTML = '<div class="vert">一期一会</div><div class="big">刃</div>';
  document.getElementById('stage').appendChild(t);
}

const tipWorld = new THREE.Vector3();
window.renderAt = (t) => {
  const d = film.duration;
  const u = t / d;
  // camera: slow macro dolly from the guard toward the tip
  // wide (whole sword) → push in on the guard, orbiting slightly
  const e = 0.5 - 0.5 * Math.cos(Math.PI * u);
  const a = -0.35 + e * 0.7;
  const dist = 3.1 - e * 1.9;
  camera.position.set(Math.sin(a) * dist, 0.25 + e * 0.05, Math.cos(a) * dist);
  camera.lookAt(0.12 - e * 0.1, 0.22 - e * 0.14, 0);
  // lights sweep past → highlights run along the blade
  s1.position.set(-4 + u * 8, 1.5, 3.5); s1.lookAt(0, 0, 0);
  s2.position.set(3.5, 0.5, -2 + u * 4); s2.lookAt(0, 0, 0);
  s3.position.set(0, 4, 2.5 - u * 3); s3.lookAt(0, 0, 0);
  if (mode !== 'ink') {
    if (envRT) envRT.dispose();
    envRT = pmrem.fromScene(envScene, 0.015);
    scene.environment = envRT.texture;
  }
  if (mode === 'demonic') {
    // heartbeat pulse in the glow
    const beat = Math.pow(Math.max(0, Math.sin(t * Math.PI * 1.4)), 12);
    materials.hamon.emissiveIntensity = 1.6 + beat * 3;
    k.sword.localToWorld(tipWorld.set(0.5, -0.02, 0));
    ember.position.copy(tipWorld).add(new THREE.Vector3(0, 0, 0.15));
    ember.intensity = 0.6 + beat * 1.2;
  }
  if (outline) outline.render(scene, camera);
  else if (composer) composer.render();
  else renderer.render(scene, camera);
};

window.FILM = film;
window.READY = true;
if (!params.has('render')) {
  const t0 = performance.now();
  const loop = () => { window.renderAt(((performance.now() - t0) / 1000) % film.duration); requestAnimationFrame(loop); };
  loop();
}

// The paper world: layered cut-paper sea, Ganryūjima island, distant coasts,
// the dawn sun, and a dark "studio" set used for the sword close-up.
import * as THREE from 'three';
import { paper, rng, lerpColor } from './paper.js';

export const STUDIO_X = 200;

function waveShape(seed, topY, amp, freq, width = 260, bottom = -6, step = 1.5) {
  const r = rng(seed);
  const p1 = r() * 6.28, p2 = r() * 6.28;
  const s = new THREE.Shape();
  s.moveTo(-width / 2, bottom);
  for (let x = -width / 2; x <= width / 2 + 0.01; x += step) {
    s.lineTo(x, topY + amp * Math.sin(x * freq + p1) + amp * 0.45 * Math.sin(x * freq * 2.7 + p2));
  }
  s.lineTo(width / 2, bottom);
  s.closePath();
  return s;
}

function ridgeShape(seed, base, h, width = 300) {
  const r = rng(seed);
  const ph = [r() * 6, r() * 6, r() * 6];
  const s = new THREE.Shape();
  s.moveTo(-width / 2, -10);
  for (let x = -width / 2; x <= width / 2; x += 2.5) {
    const y = base + h * (0.55 * Math.abs(Math.sin(x * 0.035 + ph[0])) +
      0.3 * Math.abs(Math.sin(x * 0.09 + ph[1])) + 0.15 * Math.abs(Math.sin(x * 0.23 + ph[2])));
    s.lineTo(x, y);
  }
  s.lineTo(width / 2, -10);
  s.closePath();
  return s;
}

function card(shape, mat, z, depth = 0.05) {
  const g = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false, curveSegments: 2 });
  const mesh = new THREE.Mesh(g, mat);
  mesh.position.z = z;
  mesh.receiveShadow = true;
  return mesh;
}

function skyTexture(stops) {
  const c = document.createElement('canvas');
  c.width = 4; c.height = 512;
  const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 0, 512);
  stops.forEach(([k, col]) => grad.addColorStop(k, col));
  g.fillStyle = grad;
  g.fillRect(0, 0, 4, 512);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function makePine(x, z, h, seed) {
  const r = rng(seed);
  const g = new THREE.Group();
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.14, h, 5), paper('#4a3a2e', { repeat: 4 }));
  trunk.position.y = h / 2;
  trunk.rotation.z = (r() - 0.5) * 0.35;
  trunk.castShadow = true;
  g.add(trunk);
  const leaf = paper('#3b4536', { repeat: 3 });
  for (let i = 0; i < 4; i++) {
    const cone = new THREE.Mesh(new THREE.ConeGeometry(1.1 - i * 0.18, 0.55, 7), leaf);
    cone.scale.y = 0.55;
    cone.position.set((r() - 0.5) * 0.8, h * (0.65 + i * 0.13), (r() - 0.5) * 0.5);
    cone.rotation.y = r() * 3;
    cone.castShadow = true;
    g.add(cone);
  }
  g.position.set(x, 0, z);
  return g;
}

export function buildWorld(scene) {
  const animated = [];
  const dawn = new THREE.Group();
  scene.add(dawn);

  // ---- lights ----
  const hemi = new THREE.HemisphereLight(0xfff0d8, 0x3a4560, 0.9);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xffc27e, 3.2);
  sun.position.set(-12, 11, -26);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -11, right: 11, top: 11, bottom: -11, near: 1, far: 70 });
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.03;
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0x9db0d6, 0.55);
  fill.position.set(8, 4, 20);
  scene.add(fill);

  // ---- sky, sun disc, clouds ----
  const skyDawn = skyTexture([[0, '#9aa0ad'], [0.45, '#e3cba6'], [0.72, '#f3b77f'], [1, '#e9a66f']]);
  const sunDisc = new THREE.Mesh(new THREE.CircleGeometry(7, 20), new THREE.MeshBasicMaterial({ color: '#f39a52', fog: false }));
  sunDisc.position.set(8, 6, -110);
  dawn.add(sunDisc);
  const halo = new THREE.Mesh(new THREE.CircleGeometry(16, 20),
    new THREE.MeshBasicMaterial({ color: '#f7c58c', transparent: true, opacity: 0.35, fog: false }));
  halo.position.set(8, 6, -111);
  dawn.add(halo);
  const cloudMat = paper('#f1e2c6', { glow: 0.35, glowColor: '#f6c48c' });
  for (let i = 0; i < 6; i++) {
    const r = rng(40 + i);
    const s = waveShape(40 + i, 0, 0.6, 0.3, 40 + r() * 30, -1.2, 2);
    const c = card(s, cloudMat, -70 - i * 6, 0.05);
    c.position.set((r() - 0.5) * 80, 14 + r() * 10, c.position.z);
    dawn.add(c);
  }

  // ---- distant coasts (Kyushu / Honshu sides of the strait) ----
  [[-52, '#6f7488', 4, 3], [-64, '#9b9aa3', 7, 5], [-80, '#c4b8a9', 10, 9]].forEach(([z, col, h, seed]) => {
    const m = card(ridgeShape(seed, -0.5, h), paper(col), z, 0.1);
    m.position.x = seed * 7 - 30;
    dawn.add(m);
  });

  // ---- sea: layered cut-paper wave cards with a cream "foam" edge ----
  const seaFloor = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), paper('#26324a', { repeat: 0.2 }));
  seaFloor.rotation.x = -Math.PI / 2;
  seaFloor.position.y = -0.3;
  seaFloor.receiveShadow = true;
  dawn.add(seaFloor);
  const addWave = (z, col, foam, seed, top, amp, freq) => {
    const g = new THREE.Group();
    g.add(card(waveShape(seed, top, amp, freq), paper(col), 0));
    if (foam) g.add(card(waveShape(seed, top + 0.06, amp, freq), paper(foam, { glow: 0.12 }), -0.04));
    g.position.z = z;
    dawn.add(g);
    const r = rng(seed * 3);
    animated.push({ g, ph: r() * 6, sp: 0.4 + r() * 0.5, ax: 0.35 + r() * 0.4 });
  };
  let seed = 100;
  for (let z = 5.6; z < 66; z += 2.3) {
    const k = (z - 5.6) / 60;
    addWave(z, lerpColor('#1e2b44', '#7b86a0', k), lerpColor('#efe5d0', '#cdbfae', k), seed++, -0.02 + k * 0.1, 0.12 + k * 0.08, 0.5 - k * 0.2);
  }
  for (let z = -14; z > -46; z -= 3.6) {
    const k = (-14 - z) / 32;
    addWave(z, lerpColor('#4a5a77', '#a4a7b0', k), '#e2d3bc', seed++, 0, 0.15, 0.3);
  }

  // ---- Ganryūjima: a small, low, flat island ----
  const isl = new THREE.Shape();
  const r = rng(5);
  for (let i = 0; i <= 22; i++) {
    const a = (i / 22) * Math.PI * 2;
    const rr = 8.6 + (i === 22 ? 0 : (r() - 0.5) * 1.3);
    i === 0 ? isl.moveTo(Math.cos(a) * rr, Math.sin(a) * rr) : isl.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
  }
  const islandGeo = new THREE.ExtrudeGeometry(isl, { depth: 0.6, bevelEnabled: true, bevelSize: 0.5, bevelThickness: 0.2, bevelSegments: 1 });
  const island = new THREE.Mesh(islandGeo, paper('#d8c6a1', { repeat: 0.6 }));
  island.rotation.x = -Math.PI / 2;
  island.position.set(0, -0.8, -4.5);
  island.receiveShadow = true;
  dawn.add(island);
  // dune + grass layers (stacked paper)
  const layer = (rad, col, y, z, sd) => {
    const s = new THREE.Shape();
    const rr = rng(sd);
    for (let i = 0; i <= 16; i++) {
      const a = (i / 16) * Math.PI * 2;
      const q = rad * (0.85 + (i === 16 ? 0.15 : rr() * 0.3));
      i === 0 ? s.moveTo(Math.cos(a) * q * 1.3, Math.sin(a) * q) : s.lineTo(Math.cos(a) * q * 1.3, Math.sin(a) * q);
    }
    const m = new THREE.Mesh(new THREE.ExtrudeGeometry(s, { depth: 0.12, bevelEnabled: false }), paper(col, { repeat: 0.8 }));
    m.rotation.x = -Math.PI / 2;
    m.position.set(0, y - 0.12, z);
    m.receiveShadow = true;
    dawn.add(m);
  };
  layer(5.2, '#c3b18b', 0.12, -8, 61);
  layer(3.6, '#7f7f5c', 0.24, -9.2, 62);
  [[-4.6, -7.6, 3.4], [-2.1, -10, 4.2], [3.4, -8.8, 3.8], [6.1, -6.4, 3.1], [-6.8, -4.6, 2.8], [1.2, -11, 3.6]]
    .forEach(([x, z, h], i) => dawn.add(makePine(x, z, h, 70 + i)));
  const rockMat = paper('#6b665f', { repeat: 2 });
  [[2.6, 2.2, 0.35], [-3.2, 1.6, 0.25], [4.2, -1.5, 0.45], [-1.7, 3.3, 0.2]].forEach(([x, z, s]) => {
    const rk = new THREE.Mesh(new THREE.DodecahedronGeometry(s), rockMat);
    rk.position.set(x, s * 0.4, z);
    rk.castShadow = rk.receiveShadow = true;
    dawn.add(rk);
  });

  // ---- studio set for the sword close-up (lit through layered paper) ----
  const studio = new THREE.Group();
  studio.position.x = STUDIO_X;
  scene.add(studio);
  const glowBack = new THREE.Mesh(new THREE.PlaneGeometry(14, 8), paper('#e59a52', { glow: 0.9, glowColor: '#f0a25a' }));
  glowBack.position.set(0, 1.5, -3.2);
  studio.add(glowBack);
  [['#5a1c14', 1.95, -2.6, 0.22], ['#3a1612', 1.62, -2.0, 0.18], ['#24110e', 1.3, -1.4, 0.16], ['#130b0a', 0.92, -0.8, 0.12]]
    .forEach(([col, top, z, amp], i) => {
      const c = card(waveShape(300 + i, top, amp, 2.2 + i * 0.4, 14, -3, 0.08), paper(col, { repeat: 3 }), z, 0.03);
      studio.add(c);
      animated.push({ g: c, ph: i, sp: 0.5, ax: 0.05, studio: true });
    });
  const ember = new THREE.PointLight(0xffa860, 14, 7, 1.2);
  ember.position.set(0, 1.4, -2.3);
  studio.add(ember);
  const key = new THREE.SpotLight(0xfff0dc, 40, 10, 0.45, 0.7, 1.4);
  key.position.set(0.5, 3.0, 2.2);
  key.target.position.set(0, 1.2, 0);
  studio.add(key, key.target);

  const fogDawn = new THREE.Fog('#e6c49c', 28, 150);
  const skyStudio = new THREE.Color('#0d0a09');

  // things a camera must not fly through or hide the subject behind (dawn set): [{ x, z, r, y0, y1 }] — camera guards, audit
  const obstacles = [
    ...[[2.6, 2.2, 0.35], [-3.2, 1.6, 0.25], [4.2, -1.5, 0.45], [-1.7, 3.3, 0.2]].map(([x, z, r]) => ({ x, z, r: r + 0.05, y0: 0, y1: r * 1.5 })),
    ...[[-4.6, -7.6, 3.4], [-2.1, -10, 4.2], [3.4, -8.8, 3.8], [6.1, -6.4, 3.1], [-6.8, -4.6, 2.8], [1.2, -11, 3.6]].flatMap(([x, z, h]) => [{ x, z, r: 0.25, y0: 0, y1: h }, { x, z, r: 1.2, y0: h * 0.6, y1: h * 1.15 }]),
  ];
  // height of the sand at (x, z) in the dawn set: the island top is 0, the two stacked dune layers are 0.12 and 0.24
  const groundAt = (x, z) => {
    const inL = (rad, zc) => ((x / (rad * 1.5)) ** 2 + ((z - zc) / (rad * 1.15)) ** 2) < 1;
    return inL(3.6, -9.2) ? 0.24 : inL(5.2, -8) ? 0.12 : 0;
  };
  return {
    dawn, studio, sun, hemi, fill, obstacles, groundAt,
    /** film.light = { sun, hemi, fill } multiplies the dawn lights (lift the shadows, soften the sun); call after setMode */
    setLight(o = {}) { sun.intensity *= o.sun ?? 1; hemi.intensity *= o.hemi ?? 1; fill.intensity *= o.fill ?? 1; if (o.ground) hemi.groundColor.set(o.ground); },
    setMode(mode) {
      if (mode === 'studio') {
        scene.background = skyStudio;
        scene.fog = null;
        hemi.intensity = 0.15;
        sun.intensity = 0.6;
        fill.intensity = 0.15;
      } else {
        scene.background = skyDawn;
        scene.fog = fogDawn;
        hemi.intensity = 0.9;
        sun.intensity = 3.2;
        fill.intensity = 0.55;
      }
    },
    update(t) {
      for (const a of animated) {
        a.g.position.x = Math.sin(t * a.sp + a.ph) * a.ax;
        if (!a.studio) a.g.position.y = Math.sin(t * a.sp * 1.7 + a.ph) * 0.03;
      }
    },
  };
}

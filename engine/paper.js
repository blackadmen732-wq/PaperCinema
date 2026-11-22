// Paper materials: every surface in the film is "paper".
// Each material gets a procedurally generated washi-style texture
// (speckle + fibres), flat shading for crisp folds, and optional glow
// to fake light shining through thin paper.
import * as THREE from 'three';
import { drawPattern } from './patterns.js';

export function rng(seed) {
  let s = (seed >>> 0) || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >>> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

const canvasCache = new Map();
function paperCanvas(hex, seed, pattern) {
  const key = hex + ':' + seed + ':' + JSON.stringify(pattern ?? null);
  if (canvasCache.has(key)) return canvasCache.get(key);
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const g = c.getContext('2d');
  g.fillStyle = hex;
  g.fillRect(0, 0, 512, 512);
  if (pattern) drawPattern(g, 512, { ...pattern, color: hex });
  const r = rng(seed);
  const img = g.getImageData(0, 0, 512, 512);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const n = (r() - 0.5) * 16;
    d[i] += n; d[i + 1] += n; d[i + 2] += n;
  }
  g.putImageData(img, 0, 0);
  g.lineCap = 'round';
  for (let i = 0; i < 1100; i++) {
    const x = r() * 512, y = r() * 512, a = r() * Math.PI * 2, l = 6 + r() * 30;
    g.strokeStyle = r() < 0.5 ? 'rgba(255,255,255,0.11)' : 'rgba(0,0,0,0.08)';
    g.lineWidth = 0.6 + r() * 0.9;
    g.beginPath();
    g.moveTo(x, y);
    g.quadraticCurveTo(
      x + Math.cos(a + 0.7) * l * 0.5, y + Math.sin(a + 0.7) * l * 0.5,
      x + Math.cos(a) * l, y + Math.sin(a) * l);
    g.stroke();
  }
  canvasCache.set(key, c);
  return c;
}

const matCache = new Map();
/**
 * paper('#c23b2e', { repeat: 20, rough: 0.9, metal: 0, glow: 0.1 })
 * repeat: texture tiles per metre (small props need high values)
 */
export function paper(hex, opts = {}) {
  const repeat = opts.repeat ?? 1;
  const key = JSON.stringify([hex, opts]);
  if (matCache.has(key)) return matCache.get(key);
  const tex = new THREE.CanvasTexture(paperCanvas(hex, opts.seed ?? 7, opts.pattern));
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(repeat, repeat);
  tex.anisotropy = 4;
  const m = new THREE.MeshStandardMaterial({
    map: tex,
    bumpMap: tex,
    bumpScale: opts.bump ?? 0.6,
    roughness: opts.rough ?? 0.92,
    metalness: opts.metal ?? 0,
    flatShading: true,
    side: THREE.DoubleSide,
    transparent: !!opts.transparent,
    opacity: opts.opacity ?? 1,
  });
  if (opts.glow) {
    m.emissive = new THREE.Color(opts.glowColor ?? hex);
    m.emissiveIntensity = opts.glow;
  }
  if (opts.fog === false) m.fog = false;
  matCache.set(key, m);
  return m;
}

export function lerpColor(a, b, k) {
  return '#' + new THREE.Color(a).lerp(new THREE.Color(b), k).getHexString();
}

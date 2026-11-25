// Paper materials: every surface in the film is "paper".
// Each material gets a procedurally generated washi texture: speckle, fibres and BLOTTING, flat
// shading for crisp folds, and optional glow to fake light shining through thin paper.
//
// Two maps, not one. The colour map says what the paper looks like; the height map says how the
// surface stands up, and only the height map drives the bump. Reusing the colour map as the bump
// (which this file used to do) is a cheap trick that is wrong for ink: a dark blot would read as a
// DENT, when dye soaking into washi leaves the surface flat and only the fibre stands proud.
//
// Blotting is the thing the owner asked for, and it is what paint-brush (PaintCode) does well:
// pigment does not land evenly. It pools, it dries darker at the rim of a pool ("coffee ring"),
// and it soaks further along a fibre than across it. Flat colour plus fine noise cannot look
// handmade, because handmade means uneven at a size the eye can see.
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
function paperCanvas(hex, seed, pattern, opts) {
  const key = hex + ':' + seed + ':' + (opts?.blot ?? 1) + ':' + JSON.stringify(pattern ?? null);
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
  // Blots are features of ONE sheet. When a material tiles its texture many times across a surface
  // (the dunes use repeat ~20), the same 26 pools repeat with it and read as polka dots instead of
  // handmade paper. So the strength falls off as the tiling rises: strong on a sheet seen whole,
  // nearly gone on ground that repeats to the horizon. opts.blot overrides it either way.
  // Blots only make sense at the size of a real sheet of washi, so they are scaled by the tiling
  // and fade at BOTH extremes. The dunes tile at repeat 0.2, so one tile spans hundreds of metres
  // and a pool becomes a field-sized stain; a small prop at repeat 20 repeats the same 18 pools
  // until they read as polka dots. Full strength sits around repeat 1, where one tile is about one
  // sheet. opts.blot overrides it, and opts.blot = 0 turns blotting off entirely.
  const rep = opts?.repeat ?? 1;
  const fit = Math.min(1, rep) / Math.sqrt(Math.max(1, rep));
  drawBlots(g, 512, r, 18, (opts?.blot ?? 1) * fit);
  canvasCache.set(key, c);
  return c;
}

/** Pigment pools. Dye does not land evenly on washi: it gathers, and it dries darker at the rim of
 *  a pool (the "coffee ring"), and it runs further along a fibre than across it.
 *
 *  Drawn with `multiply`, not as a colour. The first version tinted each pool with the paper's own
 *  hue at low opacity, which changed the pixels by one or two levels out of 255 and was invisible
 *  in the render. Density is what ink actually varies: a wetter patch is the same colour, darker.
 *  Multiply does exactly that and keeps the paper's hue whatever colour the sheet is. */
function drawBlots(g, size, r, n = 26, strength = 1) {
  g.save();
  g.globalCompositeOperation = 'multiply';
  for (let i = 0; i < n; i++) {
    const x = r() * size, y = r() * size;
    const rad = size * (0.06 + r() * 0.14);
    const deep = 1 - (0.05 + r() * 0.07) * strength;        // pool centre: ~5-12% darker
    const rim = 1 - (0.10 + r() * 0.09) * strength;         // rim: where the pigment piled up
    const grey = (v) => `rgb(${Math.round(v * 255)},${Math.round(v * 255)},${Math.round(v * 255)})`;
    // Set the transform FIRST, then build the gradient in that same space, centred on the origin.
    // Building it at (x, y) and then translating by (x, y) puts the gradient's centre at (2x, 2y),
    // so the circle drawn at the origin is filled with the gradient's OUTER stop - white - and
    // multiply by white changes nothing. That silent no-op is why this looked broken.
    g.translate(x, y);
    g.rotate(r() * Math.PI);
    g.scale(1, 0.45 + r() * 0.5);                           // dye runs along the fibre, not across
    const grad = g.createRadialGradient(0, 0, rad * 0.1, 0, 0, rad);
    grad.addColorStop(0.0, grey(deep));
    grad.addColorStop(0.70, grey(deep + (1 - deep) * 0.35));
    grad.addColorStop(0.92, grey(rim));
    grad.addColorStop(1.0, 'rgb(255,255,255)');             // white is the identity for multiply
    g.fillStyle = grad;
    g.beginPath();
    g.arc(0, 0, rad, 0, Math.PI * 2);
    g.fill();
    g.setTransform(1, 0, 0, 1, 0, 0);
  }
  g.restore();
}

const heightCache = new Map();
/** The surface, not the colour: mid grey is the sheet, lighter stands proud. Fibres are raised
 *  threads; a blot adds only a faint rim, because soaked dye does not lift the paper. */
function heightCanvas(seed) {
  if (heightCache.has(seed)) return heightCache.get(seed);
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const g = c.getContext('2d');
  g.fillStyle = '#808080';
  g.fillRect(0, 0, 512, 512);
  const r = rng(seed ^ 0x9e37);
  const img = g.getImageData(0, 0, 512, 512);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const n = (r() - 0.5) * 22;                       // the sheet's own tooth
    d[i] += n; d[i + 1] += n; d[i + 2] += n;
  }
  g.putImageData(img, 0, 0);
  g.lineCap = 'round';
  for (let i = 0; i < 1400; i++) {                     // raised fibres
    const x = r() * 512, y = r() * 512, a = r() * Math.PI * 2, l = 8 + r() * 36;
    g.strokeStyle = `rgba(255,255,255,${0.05 + r() * 0.13})`;
    g.lineWidth = 0.6 + r() * 1.3;
    g.beginPath();
    g.moveTo(x, y);
    g.quadraticCurveTo(x + Math.cos(a + 0.7) * l * 0.5, y + Math.sin(a + 0.7) * l * 0.5,
                       x + Math.cos(a) * l, y + Math.sin(a) * l);
    g.stroke();
  }
  for (let i = 0; i < 26; i++) {                       // the faint ridge at a pool's rim
    const x = r() * 512, y = r() * 512, rad = 512 * (0.05 + r() * 0.13);
    const grad = g.createRadialGradient(x, y, rad * 0.8, x, y, rad);
    grad.addColorStop(0, 'rgba(255,255,255,0)');
    grad.addColorStop(0.9, 'rgba(255,255,255,0.09)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grad;
    g.beginPath();
    g.arc(x, y, rad, 0, Math.PI * 2);
    g.fill();
  }
  heightCache.set(seed, c);
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
  const tex = new THREE.CanvasTexture(paperCanvas(hex, opts.seed ?? 7, opts.pattern, opts));
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(repeat, repeat);
  tex.anisotropy = 4;
  // Height is its own map. See the note at the top of this file for why it is not the colour map.
  const h = new THREE.CanvasTexture(heightCanvas(opts.seed ?? 7));
  h.wrapS = h.wrapT = THREE.RepeatWrapping;
  h.repeat.set(repeat, repeat);
  h.anisotropy = 4;
  const m = new THREE.MeshStandardMaterial({
    map: tex,
    bumpMap: h,
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

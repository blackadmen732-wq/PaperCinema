// FX: post-processing and screen effects for the three.js preview (Lantern Origami look).
// Every effect is a pure function of film time t (seeded, no feedback buffers), so any frame renders on its own.
//
//   import { createFX, fxAt, MOODS, shake } from './fx.js';
//   const fx = createFX(renderer, scene, camera, { width: W, height: H, seed: 7 });
//   fx.particles({ name: 'dust', kind: 'dust', center: [0, 1.4, 0], size: [6, 4, 6] });   // once, at load
//   fx.shafts({ name: 'sun', origin: [-3, 6, -6], target: [0.5, 0, 1] });
//   const glint = fx.glint();                                                             // a sprite you aim per frame
//   window.renderAt = (t) => { ...pose, camera...; shake(camera, t, { trauma }); fx.render(t, fxAt(t, film.fx, film.fxBase)); };
//
// Guide: docs/EFFECTS-CATALOG.md · catalogue of every effect: library/effects.json.
// Uses three.js addons (MIT): EffectComposer, RenderPass, UnrealBloomPass, OutputPass, ShaderPass.
// The page's import map must map "three/addons/" to /node_modules/three/examples/jsm/ (see engine/fx-demo.html).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

// ---------- colour moods (display-space grade: lift / gamma / gain per channel, saturation, contrast) ----------
// amber = human, crimson = demonic (house rule). "kurosawa" is a black-and-white grade for flashbacks.
export const MOODS = {
  neutral:  { exposure: 1, contrast: 1, saturation: 1, lift: [0, 0, 0], gamma: [1, 1, 1], gain: [1, 1, 1], mono: 0 },
  dawn:     { exposure: 1.02, contrast: 1.08, saturation: 1.05, lift: [0.015, 0.01, 0.03], gamma: [0.98, 1, 1.04], gain: [1.05, 1.0, 0.92], mono: 0 },
  lantern:  { exposure: 1.0, contrast: 1.18, saturation: 1.1, lift: [0.02, 0.01, 0.0], gamma: [0.95, 1.0, 1.08], gain: [1.1, 0.98, 0.82], mono: 0 },
  moonlit:  { exposure: 0.9, contrast: 1.12, saturation: 0.7, lift: [0.0, 0.015, 0.045], gamma: [1.08, 1.02, 0.94], gain: [0.86, 0.96, 1.08], mono: 0 },
  demonic:  { exposure: 0.95, contrast: 1.25, saturation: 1.15, lift: [0.03, 0.0, 0.01], gamma: [0.92, 1.1, 1.08], gain: [1.12, 0.84, 0.82], mono: 0 },
  kurosawa: { exposure: 1.0, contrast: 1.35, saturation: 0, lift: [0.01, 0.01, 0.01], gamma: [1, 1, 1], gain: [1.02, 1.02, 1.02], mono: 1 },
  ash:      { exposure: 0.95, contrast: 0.95, saturation: 0.45, lift: [0.04, 0.035, 0.03], gamma: [1, 1, 1], gain: [0.96, 0.95, 0.92], mono: 0 },
};

/** Defaults for every per-frame parameter. Missing keys in fx.render(t, p) fall back to these (all "off" but the grade). */
export const DEFAULTS = {
  bloom: { strength: 0.0, radius: 0.4, threshold: 0.85 },
  grade: MOODS.neutral,
  vignette: { amount: 0, softness: 0.55, roundness: 0.6, color: [0.02, 0.015, 0.01] },
  grain: { amount: 0, size: 1.5 },
  letterbox: { amount: 0, ratio: 2.39, y: 0, color: [0, 0, 0] },
  ca: { amount: 0, center: [0.5, 0.5] },                                // amount in pixels at the frame edge
  speedLines: { amount: 0, center: [0.5, 0.5], inner: 0.28, density: 90, width: 0.5, color: [0.05, 0.04, 0.035], fps: 12 },
  ink: { amount: 0, threshold: 0.42, paper: [0.95, 0.91, 0.83], inkColor: [0.05, 0.04, 0.04], accent: [1.0, 0.62, 0.2], invert: 0 },
  flash: { amount: 0, color: [1.0, 0.96, 0.9] },
  fade: { amount: 0, color: [0, 0, 0] },
  shafts: {},                                                            // { name: intensity }
  particles: {},                                                         // { name: intensity }
  glint: null,                                                           // { at: [x,y,z] | Vector3, t0, dur, size (px), color }
};

const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const smooth = (k) => k * k * (3 - 2 * k);
const v3 = (a) => (a?.isVector3 ? a : new THREE.Vector3(...(a ?? [0, 0, 0])));
function rng(seed) {                       // xorshift32, same family as paper.js
  let s = (seed >>> 0) || 1;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
}

// ---------- the one-pass "Lantern lens" shader: CA → speed lines → grade → ink → vignette → grain → flash/fade → letterbox ----------
const LensShader = {
  uniforms: {
    tDiffuse: { value: null }, uRes: { value: new THREE.Vector2(720, 1280) }, uFrame: { value: 0 }, uSeed: { value: 7 },
    uExposure: { value: 1 }, uContrast: { value: 1 }, uSat: { value: 1 }, uMono: { value: 0 },
    uLift: { value: new THREE.Vector3() }, uGamma: { value: new THREE.Vector3(1, 1, 1) }, uGain: { value: new THREE.Vector3(1, 1, 1) },
    uVig: { value: 0 }, uVigSoft: { value: 0.55 }, uVigRound: { value: 0.6 }, uVigColor: { value: new THREE.Vector3() },
    uGrain: { value: 0 }, uGrainSize: { value: 1.5 },
    uBox: { value: 0 }, uBoxRatio: { value: 2.39 }, uBoxY: { value: 0 }, uBoxColor: { value: new THREE.Vector3() },
    uCA: { value: 0 }, uCACenter: { value: new THREE.Vector2(0.5, 0.5) },
    uSL: { value: 0 }, uSLCenter: { value: new THREE.Vector2(0.5, 0.5) }, uSLInner: { value: 0.28 }, uSLDensity: { value: 90 },
    uSLWidth: { value: 0.5 }, uSLColor: { value: new THREE.Vector3() }, uSLFrame: { value: 0 },
    uInk: { value: 0 }, uInkThr: { value: 0.42 }, uInkPaper: { value: new THREE.Vector3() }, uInkInk: { value: new THREE.Vector3() },
    uInkAccent: { value: new THREE.Vector3() }, uInkInvert: { value: 0 },
    uFlash: { value: 0 }, uFlashColor: { value: new THREE.Vector3(1, 1, 1) }, uFade: { value: 0 }, uFadeColor: { value: new THREE.Vector3() },
  },
  vertexShader: /* glsl */`varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse; uniform vec2 uRes; uniform float uFrame, uSeed;
    uniform float uExposure, uContrast, uSat, uMono; uniform vec3 uLift, uGamma, uGain;
    uniform float uVig, uVigSoft, uVigRound; uniform vec3 uVigColor;
    uniform float uGrain, uGrainSize;
    uniform float uBox, uBoxRatio, uBoxY; uniform vec3 uBoxColor;
    uniform float uCA; uniform vec2 uCACenter;
    uniform float uSL, uSLInner, uSLDensity, uSLWidth, uSLFrame; uniform vec2 uSLCenter; uniform vec3 uSLColor;
    uniform float uInk, uInkThr, uInkInvert; uniform vec3 uInkPaper, uInkInk, uInkAccent;
    uniform float uFlash, uFade; uniform vec3 uFlashColor, uFadeColor;
    varying vec2 vUv;
    float hash11(float p) { p = fract(p * 0.1031); p *= p + 33.33; p *= p + p; return fract(p); }
    float hash21(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
    float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
    void main() {
      vec2 uv = vUv;
      float aspect = uRes.x / uRes.y;
      // 1. chromatic aberration: R pushed out, B pulled in, radially from the centre (grows to the edges)
      vec3 col;
      if (uCA > 0.001) {
        vec2 d = uv - uCACenter; float r = length(d * vec2(aspect, 1.0));
        vec2 off = d * (uCA / uRes.y) * (0.4 + 1.6 * r);
        col.r = texture2D(tDiffuse, uv + off).r;
        col.g = texture2D(tDiffuse, uv).g;
        col.b = texture2D(tDiffuse, uv - off).b;
      } else col = texture2D(tDiffuse, uv).rgb;
      // 2. grade (display space): exposure → lift/gamma/gain → contrast around mid-grey → saturation / mono
      col *= uExposure;
      col = uLift + col * (uGain - uLift);
      col = pow(max(col, 0.0), 1.0 / max(uGamma, vec3(0.01)));
      col = (col - 0.5) * uContrast + 0.5;
      float L = luma(col);
      col = mix(vec3(L), col, uSat);
      col = mix(col, vec3(L), uMono);
      col = clamp(col, 0.0, 1.0);
      // 3. ink impact frame: the picture becomes sumi ink on washi; the brightest light (eyes, glow) stays as an accent colour
      if (uInk > 0.001) {
        float l = luma(col); if (uInkInvert > 0.5) l = 1.0 - l;
        float paperK = smoothstep(uInkThr - 0.04, uInkThr + 0.04, l);
        vec3 ink = mix(uInkInk, uInkPaper, paperK);
        float acc = smoothstep(0.9, 0.98, luma(texture2D(tDiffuse, uv).rgb)) * (1.0 - uInkInvert);
        ink = mix(ink, uInkAccent, acc);
        col = mix(col, ink, uInk);
      }
      // 4. radial speed lines (manga "shūchū-sen"): tapered ink wedges, re-drawn on twos
      if (uSL > 0.001) {
        vec2 p = (uv - uSLCenter) * vec2(aspect, 1.0);
        float r = length(p), a = atan(p.y, p.x) / 6.2831853 + 0.5;
        float n = uSLDensity, cell = floor(a * n), f = fract(a * n);
        float h = hash21(vec2(cell, uSLFrame + uSeed)), h2 = hash21(vec2(cell * 1.7, uSLFrame * 0.37 + uSeed));
        float on = step(0.35, h);
        float start = uSLInner * (0.85 + 0.6 * h2);
        float grow = smoothstep(start, start + 0.12, r);                  // fade in from the clear centre
        float w = uSLWidth * (0.25 + 0.75 * h) * clamp((r - start) / 0.6, 0.0, 1.0);   // wedge: thicker outward
        float line = 1.0 - smoothstep(w * 0.5, w * 0.5 + 0.06, abs(f - 0.5) * 2.0 * 0.5);
        col = mix(col, uSLColor, clamp(line * on * grow * uSL, 0.0, 1.0));
      }
      // 5. vignette (cos⁴-like falloff, roundness mixes between frame-shaped and circular)
      if (uVig > 0.001) {
        vec2 d = (uv - 0.5) * vec2(mix(1.0, aspect, uVigRound), 1.0) * 2.0;
        float v = smoothstep(1.0 - uVigSoft, 1.0 + uVigSoft * 0.5, length(d) * 0.72);
        col = mix(col, uVigColor, v * uVig);
      }
      // 6. film grain: per-frame seeded, strongest in the mid-tones, protected highlights
      if (uGrain > 0.001) {
        vec2 g = floor(uv * uRes / uGrainSize);
        float nz = hash21(g + vec2(uFrame * 17.0 + uSeed, uFrame * 3.0)) + hash21(g * 1.31 + uFrame) - 1.0;
        float l = luma(col);
        col += nz * uGrain * (0.35 + 0.65 * (1.0 - abs(l - 0.45) * 1.6));
      }
      // 7. flash (white-amber) and fade (to black)
      col = mix(col, uFlashColor, clamp(uFlash, 0.0, 1.0));
      col = mix(col, uFadeColor, clamp(uFade, 0.0, 1.0));
      // 8. letterbox: a strip of aspect uBoxRatio (w/h); amount 0..1 slides the bars in
      if (uBox > 0.001) {
        float stripH = clamp(aspect / uBoxRatio, 0.0, 1.0);
        float halfH = mix(0.5, stripH * 0.5, smoothstep(0.0, 1.0, uBox));
        float c = 0.5 + uBoxY;
        float inside = step(c - halfH, uv.y) * step(uv.y, c + halfH);
        col = mix(uBoxColor, col, inside);
      }
      gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
    }`,
};

// ---------- light shafts: additive gradient cards from a light, turning to face the camera around their own axis ----------
const ShaftShader = {
  vertexShader: /* glsl */`varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform vec3 uColor; uniform float uAlpha; varying vec2 vUv;
    void main() {
      float along = smoothstep(0.0, 0.12, vUv.y) * pow(1.0 - vUv.y, 1.6);      // bright near the light, dies away
      float across = 1.0 - abs(vUv.x - 0.5) * 2.0; across = across * across * (3.0 - 2.0 * across);
      gl_FragColor = vec4(uColor * along * across * uAlpha, 1.0);
    }`,
};

// ---------- particles: one Points cloud per kind, positions = fract(seed + velocity·t) inside a box (no state) ----------
const PART_KINDS = {
  // vel m/s (x,y,z), wobble m, size m, colour, blending, count
  dust:   { vel: [0.03, 0.015, 0.01], wob: 0.05, size: 0.012, color: [1.0, 0.9, 0.72], add: true,  count: 500, glow: 1.0, shape: 0 },
  ember:  { vel: [0.08, 0.38, 0.0],   wob: 0.12, size: 0.018, color: [1.0, 0.55, 0.18], add: true, count: 220, glow: 2.2, shape: 0 },
  petal:  { vel: [0.25, -0.32, 0.05], wob: 0.25, size: 0.07,  color: [0.98, 0.78, 0.8], add: false, count: 420, glow: 0.0, shape: 1 },
  snow:   { vel: [0.05, -0.45, 0.0],  wob: 0.08, size: 0.03, color: [0.96, 0.96, 1.0], add: false, count: 900, glow: 0.0, shape: 0 },
  ash:    { vel: [0.06, -0.12, 0.02], wob: 0.15, size: 0.03,  color: [0.35, 0.33, 0.32], add: false, count: 220, glow: 0.0, shape: 1 },
  shard:  { vel: [0.0, -0.2, 0.0],    wob: 0.3,  size: 0.04,  color: [0.95, 0.91, 0.82], add: false, count: 140, glow: 0.0, shape: 2 },
};
const PartShader = {
  vertexShader: /* glsl */`
    attribute vec4 aSeed; attribute vec4 aSeed2;
    uniform float uTime, uSize, uWob, uScale; uniform vec3 uVel, uBox, uCenter;
    varying float vFade, vRot, vTw; varying vec4 vSeed;
    void main() {
      vec3 sp = uVel * (0.6 + 0.8 * aSeed2.x);
      vec3 u = fract(aSeed.xyz + sp * uTime / uBox);
      vec3 wob = vec3(sin(uTime * (0.7 + aSeed2.y) + aSeed.w * 6.28), sin(uTime * (0.5 + aSeed2.z) + aSeed.x * 6.28), cos(uTime * (0.6 + aSeed2.y) + aSeed.y * 6.28)) * uWob;
      vec3 p = uCenter + (u - 0.5) * uBox + wob;
      vec3 e = min(u, 1.0 - u); vFade = smoothstep(0.0, 0.12, min(e.x, min(e.y, e.z)));   // fade at the box walls: no pops
      vRot = aSeed2.w * 6.28 + uTime * (aSeed2.x - 0.5) * 4.0;
      vTw = 0.6 + 0.4 * sin(uTime * (3.0 + 5.0 * aSeed2.z) + aSeed.w * 30.0);
      vSeed = aSeed;
      vec4 mv = modelViewMatrix * vec4(p, 1.0);
      gl_PointSize = clamp(uSize * (0.5 + aSeed2.y) * uScale / -mv.z, 0.0, 64.0);
      gl_Position = projectionMatrix * mv;
    }`,
  fragmentShader: /* glsl */`
    uniform vec3 uColor; uniform float uAlpha, uGlow, uShape; varying float vFade, vRot, vTw; varying vec4 vSeed;
    void main() {
      vec2 q = gl_PointCoord - 0.5;
      float a;
      if (uShape < 0.5) { a = smoothstep(0.5, 0.0, length(q)); a *= a; }                 // soft dot
      else {
        float c = cos(vRot), s = sin(vRot); q = mat2(c, -s, s, c) * q;
        if (uShape < 1.5) { q.x *= 2.2; a = 1.0 - smoothstep(0.32, 0.4, length(q)); }    // petal / flake: thin ellipse, turning
        else { q.y += 0.12; a = step(abs(q.x) * 1.6, 0.36 - q.y) * step(-0.18, q.y); }   // paper shard: a triangle
      }
      a *= vFade * uAlpha * vTw;
      if (a < 0.01) discard;
      vec3 col = uColor * (1.0 + uGlow) * (0.85 + 0.3 * vSeed.z);
      gl_FragColor = vec4(col, a);
    }`,
};

// ---------- glint "ping": 4-ray star + a thin diagonal pair + core, billboarded ----------
const GlintShader = {
  vertexShader: /* glsl */`varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform vec3 uColor; uniform float uAlpha, uRot; varying vec2 vUv;
    void main() {
      vec2 p = (vUv - 0.5) * 2.0;
      float c = cos(uRot), s = sin(uRot); p = mat2(c, -s, s, c) * p;
      float r = length(p);
      float rays = pow(max(0.0, 1.0 - abs(p.x) * 28.0 - abs(p.y) * 0.9), 1.5) + pow(max(0.0, 1.0 - abs(p.y) * 28.0 - abs(p.x) * 0.9), 1.5);
      vec2 d = mat2(0.7071, -0.7071, 0.7071, 0.7071) * p;
      float diag = 0.45 * (pow(max(0.0, 1.0 - abs(d.x) * 40.0 - abs(d.y) * 1.8), 2.0) + pow(max(0.0, 1.0 - abs(d.y) * 40.0 - abs(d.x) * 1.8), 2.0));
      float core = exp(-r * r * 90.0) * 1.4 + exp(-r * r * 12.0) * 0.25;
      float v = (rays + diag + core) * uAlpha;
      gl_FragColor = vec4(uColor * v, 1.0);
    }`,
};

/**
 * Builds the effect stack for one renderer/scene/camera. Call once at load.
 * opts: { width, height, seed }
 */
export function createFX(renderer, scene, camera, opts = {}) {
  const W = opts.width ?? renderer.domElement.width, H = opts.height ?? renderer.domElement.height;
  const seed = opts.seed ?? 7;
  const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 }));
  composer.setPixelRatio(1);
  composer.setSize(W, H);
  const renderPass = new RenderPass(scene, camera);
  const bloomPass = new UnrealBloomPass(new THREE.Vector2(W, H), 0, 0.4, 0.85);
  const outputPass = new OutputPass();                       // tone mapping + sRGB, from the renderer's settings
  const lensPass = new ShaderPass(LensShader);
  lensPass.uniforms.uRes.value.set(W, H);
  lensPass.uniforms.uSeed.value = seed % 97;
  composer.addPass(renderPass); composer.addPass(bloomPass); composer.addPass(outputPass); composer.addPass(lensPass);

  const shaftSets = {}, partSets = {}, glints = [];

  /** Light shafts ("god rays"): count cards from origin toward target; intensity per frame via p.shafts[name]. */
  function shafts(o = {}) {
    const r = rng(o.seed ?? seed + 11);
    const origin = v3(o.origin ?? [0, 6, -4]), target = v3(o.target ?? [0, 0, 0]);
    const g = new THREE.Group(); g.name = 'fx-shafts-' + (o.name ?? 'shafts');
    scene.add(g);
    const color = new THREE.Color(...(o.color ?? [1.0, 0.78, 0.5]));
    const n = o.count ?? 7, spread = o.spread ?? 1.2, len = o.length ?? origin.distanceTo(target) * 1.25;
    const cards = [];
    const dir0 = target.clone().sub(origin).normalize();
    const side = new THREE.Vector3().crossVectors(dir0, new THREE.Vector3(0, 1, 0)).normalize();
    if (side.lengthSq() < 0.01) side.set(1, 0, 0);
    const up2 = new THREE.Vector3().crossVectors(side, dir0).normalize();
    for (let i = 0; i < n; i++) {
      const w = (o.width ?? 0.5) * (0.4 + r() * 1.2);
      const geo = new THREE.PlaneGeometry(1, 1).translate(0, 0.5, 0);          // y runs from the light (0) to the far end (1)
      const mat = new THREE.ShaderMaterial({ ...ShaftShader, uniforms: { uColor: { value: color }, uAlpha: { value: 0 } },
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false });
      const m = new THREE.Mesh(geo, mat); m.frustumCulled = false;
      const off = side.clone().multiplyScalar((r() - 0.5) * spread).addScaledVector(up2, (r() - 0.5) * spread * 0.5);
      cards.push({ m, w, len: len * (0.75 + r() * 0.4), off, dir: target.clone().add(off.clone().multiplyScalar(1.6)).sub(origin.clone().add(off)).normalize(),
        ph: r() * 6.28, sp: 0.15 + r() * 0.35, base: 0.35 + r() * 0.65 });
      g.add(m);
    }
    const h = {
      group: g, origin,
      update(t, k) {
        g.visible = k > 0.001;
        if (!g.visible) return;
        for (const c of cards) {
          const o0 = origin.clone().add(c.off);
          const axis = c.dir;
          // cylindrical billboard: the card's plane contains the axis and faces the camera as much as it can
          const toCam = camera.position.clone().sub(o0);
          const nrm = toCam.sub(axis.clone().multiplyScalar(toCam.dot(axis))).normalize();
          const x = new THREE.Vector3().crossVectors(axis, nrm).normalize();
          c.m.matrixAutoUpdate = false;
          c.m.matrix.makeBasis(x.multiplyScalar(c.w), axis.clone().multiplyScalar(c.len), nrm).setPosition(o0);
          c.m.matrixWorldNeedsUpdate = true;
          const flick = 0.75 + 0.25 * Math.sin(t * c.sp * 6.28 + c.ph) * Math.sin(t * c.sp * 2.7 + c.ph * 2);
          c.m.material.uniforms.uAlpha.value = k * (o.intensity ?? 0.22) * c.base * flick;
        }
      },
    };
    shaftSets[o.name ?? 'shafts'] = h;
    h.update(0, 0);
    return h;
  }

  /** Seeded particle field (dust | ember | petal | snow | ash | shard); intensity per frame via p.particles[name]. */
  function particles(o = {}) {
    const kind = PART_KINDS[o.kind ?? 'dust'];
    if (!kind) throw new Error('fx.particles: unknown kind ' + o.kind + ' (use ' + Object.keys(PART_KINDS).join(', ') + ')');
    const n = o.count ?? kind.count, r = rng(o.seed ?? seed + 23);
    const s1 = new Float32Array(n * 4), s2 = new Float32Array(n * 4);
    for (let i = 0; i < n * 4; i++) { s1[i] = r(); s2[i] = r(); }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    geo.setAttribute('aSeed', new THREE.BufferAttribute(s1, 4));
    geo.setAttribute('aSeed2', new THREE.BufferAttribute(s2, 4));
    const mat = new THREE.ShaderMaterial({
      ...PartShader,
      uniforms: {
        uTime: { value: 0 }, uSize: { value: o.particleSize ?? kind.size }, uWob: { value: o.wobble ?? kind.wob }, uScale: { value: H / (2 * Math.tan((camera.fov * Math.PI) / 360)) },
        uVel: { value: v3(o.velocity ?? kind.vel) }, uBox: { value: v3(o.size ?? [6, 4, 6]) }, uCenter: { value: v3(o.center ?? [0, 1.4, 0]) },
        uColor: { value: v3(o.color ?? kind.color) }, uAlpha: { value: 0 }, uGlow: { value: o.glow ?? kind.glow }, uShape: { value: kind.shape },
      },
      transparent: true, depthWrite: false, blending: kind.add ? THREE.AdditiveBlending : THREE.NormalBlending, fog: false,
    });
    const pts = new THREE.Points(geo, mat); pts.frustumCulled = false; pts.name = 'fx-particles-' + (o.name ?? o.kind);
    scene.add(pts);
    const h = {
      points: pts, material: mat,
      update(t, k) {
        pts.visible = k > 0.001;
        mat.uniforms.uTime.value = t + (o.preroll ?? 30);    // pre-roll so the field is already spread at t = 0
        mat.uniforms.uAlpha.value = k * (o.opacity ?? 1);
        mat.uniforms.uScale.value = H / (2 * Math.tan((camera.fov * Math.PI) / 360));
      },
    };
    partSets[o.name ?? o.kind] = h;
    h.update(0, 0);
    return h;
  }

  /** Glint "ping": a star sprite. Usually driven by p.glint = { at, t0, dur, size, color }. */
  function glint(o = {}) {
    const mat = new THREE.ShaderMaterial({ ...GlintShader, uniforms: { uColor: { value: new THREE.Color(...(o.color ?? [1, 0.93, 0.78])) }, uAlpha: { value: 0 }, uRot: { value: 0 } },
      transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, fog: false });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat); m.frustumCulled = false; m.renderOrder = 999; m.name = 'fx-glint';
    scene.add(m);
    const h = {
      mesh: m,
      /** g: { at, t0, dur (s), size (px), color, rot } — envelope: 1-frame pop, peak at 30%, gone by dur */
      update(t, g) {
        m.visible = false;
        if (!g) return;
        const dur = g.dur ?? 0.3, k = (t - (g.t0 ?? 0)) / dur;
        if (k < 0 || k > 1) return;
        const env = k < 0.3 ? smooth(k / 0.3) : Math.pow(1 - (k - 0.3) / 0.7, 1.6);
        const at = v3(g.at);
        const dist = camera.position.distanceTo(at);
        const worldPerPx = (2 * Math.tan((camera.fov * Math.PI) / 360) * dist) / H;
        const px = (g.size ?? 140) * (0.35 + 0.65 * env);
        m.position.copy(at); m.quaternion.copy(camera.quaternion); m.scale.setScalar(px * worldPerPx);
        if (g.color) mat.uniforms.uColor.value.setRGB(...g.color);
        mat.uniforms.uAlpha.value = env * (g.intensity ?? 1.6);
        mat.uniforms.uRot.value = (g.rot ?? 0.2) + k * 0.5;
        m.visible = env > 0.002;
      },
    };
    glints.push(h);
    return h;
  }

  const u = lensPass.uniforms;
  const setV = (uni, a) => (a?.isVector3 || a?.isVector2 ? uni.value.copy(a) : uni.value.set(...a));
  /** Render one frame. t = film time (s), p = per-frame params (see DEFAULTS; fxAt() builds them from a film track). */
  function render(t, p = {}) {
    const fps = opts.fps ?? 24;
    const P = (k) => ({ ...DEFAULTS[k], ...(p[k] ?? {}) });
    const bl = P('bloom'), gr = P('grade'), vg = P('vignette'), gn = P('grain'), lb = P('letterbox'), ca = P('ca'), sl = P('speedLines'), ik = P('ink'), fl = P('flash'), fd = P('fade');
    bloomPass.strength = bl.strength; bloomPass.radius = bl.radius; bloomPass.threshold = bl.threshold;
    bloomPass.enabled = bl.strength > 0.001;
    u.uFrame.value = Math.floor(t * fps + 1e-4) % 1000;
    u.uExposure.value = gr.exposure; u.uContrast.value = gr.contrast; u.uSat.value = gr.saturation; u.uMono.value = gr.mono ?? 0;
    setV(u.uLift, gr.lift); setV(u.uGamma, gr.gamma); setV(u.uGain, gr.gain);
    u.uVig.value = vg.amount; u.uVigSoft.value = vg.softness; u.uVigRound.value = vg.roundness; setV(u.uVigColor, vg.color);
    u.uGrain.value = gn.amount; u.uGrainSize.value = gn.size;
    u.uBox.value = lb.amount; u.uBoxRatio.value = lb.ratio; u.uBoxY.value = lb.y; setV(u.uBoxColor, lb.color);
    u.uCA.value = ca.amount; setV(u.uCACenter, ca.center);
    u.uSL.value = sl.amount; setV(u.uSLCenter, sl.center); u.uSLInner.value = sl.inner; u.uSLDensity.value = sl.density;
    u.uSLWidth.value = sl.width; setV(u.uSLColor, sl.color); u.uSLFrame.value = Math.floor(t * (sl.fps ?? 12) + 1e-4);
    u.uInk.value = ik.amount; u.uInkThr.value = ik.threshold; setV(u.uInkPaper, ik.paper); setV(u.uInkInk, ik.inkColor);
    setV(u.uInkAccent, ik.accent); u.uInkInvert.value = ik.invert;
    u.uFlash.value = fl.amount; setV(u.uFlashColor, fl.color); u.uFade.value = fd.amount; setV(u.uFadeColor, fd.color);
    camera.updateMatrixWorld();
    for (const [name, h] of Object.entries(shaftSets)) h.update(t, p.shafts?.[name] ?? 0);
    for (const [name, h] of Object.entries(partSets)) h.update(t, p.particles?.[name] ?? 0);
    const gl = Array.isArray(p.glint) ? p.glint : p.glint ? [p.glint] : [];
    while (glints.length < gl.length) glint();
    glints.forEach((h, i) => h.update(t, gl[i]));
    composer.render();
  }

  return { composer, bloomPass, lensPass, outputPass, render, shafts, particles, glint, shaftSets, partSets,
    setSize(w, h) { composer.setSize(w, h); u.uRes.value.set(w, h); bloomPass.setSize(w, h); } };
}

// ---------- timeline: film "fx" events → per-frame params ----------
// An event: { "t": 3.2, "effect": "ca-flash", "dur": 0.25, ...overrides }. Envelopes (frames at 24 fps):
//   ca-flash      amount peaks on the first frame, exp decay over dur (default 0.25 s, 14 px)
//   flash         white-amber frame, linear out over dur (default 2 frames)
//   ink-impact    ink = 1 for dur (default 2 frames); { invert: 1 } for a negative frame
//   speed-lines   ramps in over 2 frames, holds, out over 3 frames
//   letterbox     bars slide in over "in" seconds (default 0.6), stay until "until" (or forever)
//   bloom-pulse   bloom strength +amount, decaying over dur
//   glint         a ping at "at" ([x,y,z]) lasting dur (default 0.3 s)
//   grade         cross-fade to mood "mood" over "in" seconds (default 1)
//   shafts / particles   fade { name } in over "in" (1 s) and out at "until" over "out" (1 s)
//   fade          fade to colour over dur (in) — use for cut to black
// fxAt merges event contributions onto base (film.fxBase). It is pure: fxAt(t) never depends on earlier frames.
function lerpMood(a, b, k) {
  const L = (x, y) => (Array.isArray(x) ? x.map((v, i) => v + (y[i] - v) * k) : x + (y - x) * k);
  return Object.fromEntries(Object.keys(MOODS.neutral).map((key) => [key, L(a[key] ?? MOODS.neutral[key], b[key] ?? MOODS.neutral[key])]));
}
const moodOf = (g) => (typeof g === 'string' ? MOODS[g] : g?.mood ? { ...MOODS[g.mood], ...g, mood: undefined } : { ...MOODS.neutral, ...(g ?? {}) });

export function fxAt(t, track = [], base = {}, fps = 24) {
  const p = JSON.parse(JSON.stringify(base ?? {}));
  p.grade = moodOf(base?.grade ?? 'neutral');
  p.shafts = { ...(base?.shafts ?? {}) }; p.particles = { ...(base?.particles ?? {}) };
  const glints = [];
  const add = (k, field, v) => { p[k] = { ...DEFAULTS[k], ...(p[k] ?? {}) }; p[k][field] = Math.max(p[k][field] ?? 0, v); };
  const win = (e) => {                                   // fade-in / hold / fade-out window
    const tin = e.in ?? 1, tout = e.out ?? 1, until = e.until ?? Infinity;
    return clamp((t - e.t) / Math.max(tin, 1e-4), 0, 1) * (1 - clamp((t - until) / Math.max(tout, 1e-4), 0, 1));
  };
  for (const e of [...(track ?? [])].sort((a, b) => a.t - b.t)) {
    const tau = t - e.t;
    if (tau < 0) continue;
    const f = 1 / fps;
    switch (e.effect) {
      case 'ca-flash': { const d = e.dur ?? 0.25; if (tau < d * 2) add('ca', 'amount', (e.amount ?? 14) * Math.exp(-tau / (d / 3))); break; }
      case 'flash': { const d = e.dur ?? 2 * f; if (tau < d) { add('flash', 'amount', (e.amount ?? 0.85) * (1 - tau / d)); if (e.color) p.flash.color = e.color; } break; }
      case 'ink-impact': { const d = e.dur ?? 2 * f; if (tau < d) { p.ink = { ...DEFAULTS.ink, ...(p.ink ?? {}), ...e, amount: e.amount ?? 1 }; } break; }
      case 'speed-lines': {
        const d = e.dur ?? 0.6; if (tau > d + 3 * f) break;
        const k = clamp(tau / (2 * f), 0, 1) * (1 - clamp((tau - d) / (3 * f), 0, 1));
        p.speedLines = { ...DEFAULTS.speedLines, ...(p.speedLines ?? {}), ...e, amount: Math.max(p.speedLines?.amount ?? 0, (e.amount ?? 0.9) * k) };
        break;
      }
      case 'letterbox': { const k = smooth(win({ in: 0.6, out: 0.6, ...e })); p.letterbox = { ...DEFAULTS.letterbox, ...(p.letterbox ?? {}), ...e, amount: Math.max(p.letterbox?.amount ?? 0, k) }; break; }
      case 'bloom-pulse': { const d = e.dur ?? 0.4; if (tau < d * 2) { p.bloom = { ...DEFAULTS.bloom, ...(p.bloom ?? {}) }; p.bloom.strength += (e.amount ?? 1.2) * Math.exp(-tau / (d / 3)); } break; }
      case 'glint': { const d = e.dur ?? 0.3; if (tau < d) glints.push({ ...e, t0: e.t, dur: d }); break; }
      case 'grade': { const k = smooth(clamp(tau / (e.in ?? 1), 0, 1)); p.grade = lerpMood(p.grade, moodOf(e.mood ?? e), k); break; }
      case 'shafts': p.shafts[e.name] = Math.max(p.shafts[e.name] ?? 0, smooth(win(e)) * (e.amount ?? 1)); break;
      case 'particles': p.particles[e.name] = Math.max(p.particles[e.name] ?? 0, smooth(win(e)) * (e.amount ?? 1)); break;
      case 'fade': { const k = clamp(tau / (e.dur ?? 0.6), 0, 1); add('fade', 'amount', k * (e.amount ?? 1)); if (e.color) p.fade.color = e.color; break; }
      default: break;                                    // unknown effects are ignored here (the checker reports them)
    }
  }
  if (glints.length) p.glint = glints;
  return p;
}

/** Deterministic camera shake ("trauma" model): offset ∝ trauma², smooth value noise sampled at t. Call after placing the camera. */
export function shake(camera, t, o = {}) {
  const tr = clamp(o.trauma ?? 0, 0, 1), k = tr * tr;
  if (k <= 0) return;
  const f = o.freq ?? 18, s = o.seed ?? 3;
  const noise = (x, c) => {                              // 1D value noise, smooth, seeded per channel
    const i = Math.floor(x), fr = x - i, h = (n) => { const v = Math.sin((n + c * 57.31 + s * 13.7) * 127.1) * 43758.5453; return (v - Math.floor(v)) * 2 - 1; };
    return h(i) + (h(i + 1) - h(i)) * smooth(fr);
  };
  const x = t * f;
  const right = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion), up = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion);
  const amp = o.pos ?? 0.03;
  camera.position.addScaledVector(right, noise(x, 1) * amp * k).addScaledVector(up, noise(x, 2) * amp * k);
  camera.rotateZ(((o.rollDeg ?? 2.5) * Math.PI / 180) * noise(x, 3) * k);
  camera.updateMatrixWorld();
}

/** Trauma from impacts: [{ t, amount }] → 0..1 at time t (linear decay over decay seconds, summed and clamped). */
export function traumaAt(t, hits = [], decay = 0.45) {
  let s = 0;
  for (const h of hits) { const d = t - h.t; if (d >= 0 && d < decay) s += (h.amount ?? 0.8) * (1 - d / decay); }
  return clamp(s, 0, 1);
}

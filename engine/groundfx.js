// GROUND FX: what the body does to the world when it moves fast (shared by engine/motion.js and engine/main.js).
// Everything is a pure function of time. Rules: docs/STUDIO-STANDARD.md §7.
//
//   const G = analyseGround({ fighters: [{ id, motion }], dur, filmT })   // once at load: dash / skid / take-off / landing
//   const dust = makeDust(scene, G.events, { seed })     → dust.update(worldTime)
//   const shadows = makeContactShadows(scene, fighters)  → shadows.update()         (after posing)
//   const ghosts = makeAfterimages(scene, fighters, { makeGhost, minSpeed, count, gap, color }) → ghosts.update(tb)
//   groundCues(G.events) → sound cues (dash burst, skid, push-off, landing thud) for window.EVENTS
//
// Dust is sand (the world is paper and sand); afterimages are light (the fighters are lanterns: what leaves
// them is their light).
import * as THREE from 'three';
import { rng } from './paper.js';
import { applyPose } from './figure.js';

const HZ = 120;
const dB = (x) => +Math.pow(10, x / 20).toFixed(3);

/** Finds what the feet do: { events: [{ kind, tb, t, pos: [x, z], dir: [x, z], speed, id }], speedAt(id, tb) } */
export function analyseGround({ fighters, dur, filmT = (x) => x, opts = {} }) {
  const dashOn = opts.dashSpeed ?? 6, events = [], tracks = {};
  for (const f of fighters) {
    const S = [];
    for (let i = 0; i <= dur * HZ; i++) { const tb = i / HZ, p = f.motion(tb); S.push({ tb, x: p.x, y: p.y, z: p.z }); }
    // speed over a 1/12 s window (keyed easing makes the instant speed lumpy; the feet do not care)
    const N = HZ / 24;
    S.forEach((s, i) => { const q = S[Math.max(0, i - N)], n = S[Math.min(S.length - 1, i + N)], dt = (n.tb - q.tb) || 1; s.vx = (n.x - q.x) / dt; s.vz = (n.z - q.z) / dt; s.v = Math.hypot(s.vx, s.vz); });
    tracks[f.id] = S;
    let dashing = false, peak = 0, air = false, top = 0, skidding = false, last = -1;
    const ev = (kind, s, extra = {}) => events.push({ kind, id: f.id, tb: +s.tb.toFixed(4), t: +filmT(s.tb).toFixed(4), pos: [s.x, s.z],
      dir: s.v > 0.01 ? [s.vx / s.v, s.vz / s.v] : [0, 1], speed: +s.v.toFixed(2), ...extra });
    for (let i = 1; i < S.length; i++) {
      const s = S[i], p = S[i - 1], grounded = s.y < 0.03;
      if (!air && !grounded) { air = true; top = 0; ev('takeoff', p); }
      if (air) top = Math.max(top, s.y);
      if (air && grounded) { air = false; if (top > 0.12) ev('land', s, { height: +top.toFixed(2) }); }
      if (!grounded) { dashing = skidding = false; continue; }
      if (!dashing && !skidding && s.v > dashOn) { dashing = true; peak = s.v; ev('dash', s); }
      if (dashing) {
        peak = Math.max(peak, s.v);
        if (s.tb - last >= 1 / 60) { ev('wake', s); last = s.tb; }
        if (s.v < 0.6 * peak && S[Math.min(S.length - 1, i + HZ / 8)].v < 0.75 * s.v) {   // really stopping (not a lump in the keyed speed) dashing = false; skidding = true; ev('skid', s, { peak: +peak.toFixed(1) }); }
      } else if (skidding) {
        if (s.v < 0.8) skidding = false;
        else if (s.tb - last >= 1 / 60) { ev('skidding', s); last = s.tb; }
      }
    }
  }
  events.sort((a, b) => a.t - b.t);
  const speedAt = (id, tb) => { const S = tracks[id]; return S[Math.max(0, Math.min(S.length - 1, Math.round(tb * HZ)))].v; };
  return { events, speedAt };
}

/** Sound cues for the ground events (sfx made by tools/synth_sfx.sh). */
export function groundCues(events, o = {}) {
  const cues = [];
  const add = (e, sfx, gainDb, len, rate = 1, lead = 0) => cues.push({ id: `auto-${e.kind}-${e.id}-${cues.length}`, sfx, t: +Math.max(0, e.t - lead).toFixed(3), len,
    gain: dB(gainDb + (o.trim ?? 0)), rate: +rate.toFixed(3), why: `${e.id} ${e.kind} (${e.speed} m/s)` });
  for (const e of events) {
    if (e.kind === 'dash') add(e, 'dash-burst', -7, 0.7, 1, 0.03);
    else if (e.kind === 'skid') add(e, 'skid-dust', -11, 0.8, 0.9 + Math.min(0.3, (e.peak ?? 8) / 60));
    else if (e.kind === 'takeoff') add(e, 'jump-push', -12, 0.4);
    else if (e.kind === 'land') add(e, 'land-thud', -5 + Math.min(3, (e.height ?? 0.3) * 2), 0.9);
  }
  return cues;
}

// ---------- DUST: soft cut-paper sand puffs + a wake line on the ground + a landing ring ----------
function puffTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'), r = rng(11);
  g.filter = 'blur(3px)';
  g.fillStyle = '#fff';
  g.beginPath();
  for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2, rr = 19 + r() * 8; g[i ? 'lineTo' : 'moveTo'](32 + Math.cos(a) * rr, 32 + Math.sin(a) * rr); }
  g.closePath(); g.fill();
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
export function makeDust(scene, events, o = {}) {
  const group = new THREE.Group(); group.userData.noAudit = true; scene.add(group);
  const tex = puffTexture(), r = rng(o.seed ?? 31), amount = o.amount ?? 1;
  const cols = (o.colors ?? ['#f3deb2', '#e2c38d', '#fff0cf']).map((c) => new THREE.Color(c));
  const puffs = [];
  const puff = (e, v, life, s0, s1, lift = 0.04) => {
    const m = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color: cols[puffs.length % cols.length], transparent: true, depthWrite: false, opacity: 0, rotation: r() * 6.28 }));
    m.visible = false; group.add(m);
    puffs.push({ m, t0: e.t + r() * 0.02, p0: new THREE.Vector3(e.pos[0] + (r() - 0.5) * 0.3, lift + r() * 0.06, e.pos[1] + (r() - 0.5) * 0.3), v, life, s0, s1, spin: (r() - 0.5) * 2 });
  };
  const V = (e, along, side, up) => new THREE.Vector3(e.dir[0] * along - e.dir[1] * side, up, e.dir[1] * along + e.dir[0] * side);
  for (const e of events) {
    const n = (k) => Math.max(1, Math.round(k * amount));
    if (e.kind === 'dash') for (let i = 0; i < n(12); i++) puff(e, V(e, -(1.2 + r() * 2.6), (r() - 0.5) * 1.6, 0.5 + r() * 1.5), 0.55 + r() * 0.35, 0.16, 0.7);
    else if (e.kind === 'wake') for (let i = 0; i < n(2); i++) puff(e, V(e, -0.3 - r() * 0.6, (r() - 0.5) * 1.1, 0.25 + r() * 0.5), 0.4 + r() * 0.25, 0.1, 0.42);
    else if (e.kind === 'skid' || e.kind === 'skidding') for (let i = 0; i < n(e.kind === 'skid' ? 8 : 3); i++) puff(e, V(e, (0.25 + r() * 0.45) * Math.max(3, e.speed), (r() - 0.5) * 1.6, 0.5 + r() * 1.3), 0.5 + r() * 0.35, 0.14, 0.62);
    else if (e.kind === 'takeoff') for (let i = 0; i < n(8); i++) { const a = r() * 6.28; puff(e, new THREE.Vector3(Math.cos(a) * 1.3, 0.3 + r() * 0.5, Math.sin(a) * 1.3), 0.45, 0.12, 0.45); }
    else if (e.kind === 'land') for (let i = 0; i < n(20); i++) { const a = (i / 20) * 6.28 + r() * 0.3, sp = 1.6 + r() * 1.8; puff(e, new THREE.Vector3(Math.cos(a) * sp, 0.25 + r() * 0.8, Math.sin(a) * sp), 0.6 + r() * 0.35, 0.18, 0.8); }
  }
  // the wake: a pale line pressed into the sand along each dash, fading behind the runner
  const wakes = [];
  const runs = {};
  for (const e of events) if (e.kind === 'wake' || e.kind === 'skidding') (runs[e.id] ??= []).push(e);
  for (const list of Object.values(runs)) {
    let seg = [];
    const flush = () => {
      if (seg.length > 2) {
        const P = new Float32Array(seg.length * 6), C = new Float32Array(seg.length * 8);
        seg.forEach((e, i) => { const w = 0.11; P.set([e.pos[0] - e.dir[1] * w, 0.015, e.pos[1] + e.dir[0] * w, e.pos[0] + e.dir[1] * w, 0.015, e.pos[1] - e.dir[0] * w], i * 6); });
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.BufferAttribute(P, 3)); g.setAttribute('color', new THREE.BufferAttribute(C, 4));
        const idx = []; for (let j = 0; j < seg.length - 1; j++) { const a = j * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
        g.setIndex(idx);
        const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
        m.frustumCulled = false; group.add(m);
        wakes.push({ m, seg: seg.slice() });
      }
      seg = [];
    };
    for (const e of list) { if (seg.length && e.t - seg[seg.length - 1].t > 0.05) flush(); seg.push(e); }
    flush();
  }
  // landing ring: a thin ring of pale sand racing outwards
  const rings = events.filter((e) => e.kind === 'land').map((e) => {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.86, 1, 28), new THREE.MeshBasicMaterial({ color: '#fff3d6', transparent: true, depthWrite: false, side: THREE.DoubleSide, opacity: 0 }));
    m.rotation.x = -Math.PI / 2; m.position.set(e.pos[0], 0.02, e.pos[1]); m.visible = false; group.add(m);
    return { m, e };
  });
  function update(t) {
    for (const p of puffs) {
      const a = t - p.t0, vis = a >= 0 && a < p.life;
      p.m.visible = vis; if (!vis) continue;
      const u = a / p.life, drag = (1 - Math.exp(-3.2 * a)) / 3.2;
      p.m.position.set(p.p0.x + p.v.x * drag, p.p0.y + p.v.y * drag + 0.12 * a, p.p0.z + p.v.z * drag);
      p.m.scale.setScalar(p.s0 + (p.s1 - p.s0) * (1 - (1 - u) * (1 - u)));
      p.m.material.opacity = 0.62 * Math.min(1, a / 0.03) * Math.pow(1 - u, 1.4);
      p.m.material.rotation += 0;
    }
    for (const w of wakes) {
      const C = w.m.geometry.attributes.color.array; let any = 0;
      w.seg.forEach((e, i) => { const a = t - e.t, al = a < 0 ? 0 : 0.5 * Math.max(0, 1 - a / 0.9); any = Math.max(any, al); C.set([1, 0.95, 0.82, al, 1, 0.95, 0.82, al], i * 8); });
      w.m.geometry.attributes.color.needsUpdate = true; w.m.visible = any > 0.004;
    }
    for (const { m, e } of rings) {
      const a = t - e.t, vis = a >= 0 && a < 0.45; m.visible = vis; if (!vis) continue;
      const u = a / 0.45; m.scale.setScalar(0.25 + 1.9 * (1 - (1 - u) * (1 - u))); m.material.opacity = 0.5 * (1 - u);
    }
  }
  return { group, update };
}

// ---------- CONTACT SHADOW: a soft dark pool under each fighter (reads the feet on the ground, and the height of a jump) ----------
export function makeContactShadows(scene, fighters, o = {}) {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'), gr = g.createRadialGradient(32, 32, 2, 32, 32, 31);
  gr.addColorStop(0, 'rgba(0,0,0,1)'); gr.addColorStop(0.45, 'rgba(0,0,0,0.55)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  const tex = new THREE.CanvasTexture(c);
  const group = new THREE.Group(); group.userData.noAudit = true; scene.add(group);
  const list = fighters.filter((f) => !f.hidden).map((f) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: tex, color: o.color ?? '#2a1620', transparent: true, depthWrite: false, opacity: 0.5, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
    m.rotation.x = -Math.PI / 2; m.renderOrder = 1; group.add(m);
    return { f, m };
  });
  const _p = new THREE.Vector3();
  function update() {
    for (const { f, m } of list) {
      f.fig.hips.getWorldPosition(_p);
      const h = Math.max(0, f.fig.root.position.y), gy = o.ground ?? 0;
      m.visible = f.fig.root.visible;
      m.position.set(_p.x, gy + 0.012, _p.z);
      m.rotation.z = f.fig.root.rotation.y;
      m.scale.set(0.95 + 0.7 * h, 1.25 + 0.7 * h, 1);
      m.material.opacity = (o.opacity ?? 0.55) / (1 + 2.2 * h);
    }
  }
  return { group, update };
}

// ---------- AFTERIMAGES: 2–3 ghosts of light left behind a body that moves faster than the eye ----------
/** makeGhost() → a figure like the fighter's (engine/figure.js makeFigure). Ghosts are flat, additive, amber (or opts.color). */
export function makeAfterimages(scene, fighters, o = {}) {
  const count = o.count ?? 3, gap = o.gap ?? 0.03, minSpeed = o.minSpeed ?? 7;
  const group = new THREE.Group(); group.userData.noAudit = true; scene.add(group);
  const sets = fighters.filter((f) => !f.hidden && f.makeGhost).map((f) => {
    const ghosts = [];
    for (let i = 0; i < count; i++) {
      const fig = f.makeGhost();
      const mat = new THREE.MeshBasicMaterial({ color: o.color ?? f.glow ?? '#ffb060', transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, toneMapped: false });
      fig.root.traverse((m) => { if (m.isMesh) { m.material = mat; m.castShadow = m.receiveShadow = false; } });
      fig.root.visible = false; group.add(fig.root);
      ghosts.push({ fig, mat });
    }
    return { f, ghosts };
  });
  function update(tb, speedAt) {
    for (const { f, ghosts } of sets) {
      const k = Math.max(0, Math.min(1, (speedAt(f.id, tb) - minSpeed) / 6));
      const now = f.motion(tb);
      ghosts.forEach((gh, i) => {
        const tg = tb - (i + 1) * gap, p = f.motion(Math.max(0, tg));
        const far = Math.hypot(p.x - now.x, p.z - now.z, p.y - now.y);
        const kk = Math.max(k, Math.max(0, Math.min(1, (speedAt(f.id, Math.max(0, tg)) - minSpeed) / 6)) * 0.8);
        gh.fig.root.visible = kk > 0.03 && far > 0.12 && tg > 0;
        if (!gh.fig.root.visible) return;
        applyPose(gh.fig, p);
        gh.mat.opacity = (o.opacity ?? 0.42) * kk * Math.pow(0.58, i);
      });
    }
  }
  return { group, update };
}

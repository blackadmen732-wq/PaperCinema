// COMBAT: the shared fight layer for the preview pages (engine/motion.js and engine/main.js).
// Everything is a pure function of time, so any frame renders on its own.
//
//   import * as combat from './combat.js';
//   const fighters = [{ id, fig, sword, bladeLen, yOff, material: 'steel' | 'wood', perf }, ...]   // exactly two
//   pose(tb) poses everyone at body time tb and calls combat.clashAim(film.clashes, byId, tb) before the hand IK
//   const C = combat.analyse({ film, fighters, pose, fps, dur });   // once at load
//   C.bodyT(t) · C.filmT(tb) · C.contacts · C.stops · C.cues · C.events (→ window.EVENTS → sound.mjs)
//
// Pieces: blade contact detection at 240 Hz (segment distance), clash aim (film.clashes), hit-stop body time,
// automatic sound cues (whoosh from tip speed, clash or wood clap at contacts, scrape while sliding),
// eye glow states + blinks + voice pulse, camera punch, smear ribbon, paper sparks, the one-frame ink impact frame.
// Guide: docs/ANIMATION.md (clashes), docs/FIX-LIST.md (eyes, sound), docs/VOICE.md (voice pulse).
import * as THREE from 'three';
import { smooth } from './figure.js';
import { paper, rng } from './paper.js';
import { voiceLevel } from './voice-env.js';

export const RATE = 240;
export const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const dB = (x) => +Math.pow(10, x / 20).toFixed(3);

// ---------- geometry ----------
/** Blade segment in world space: from 20% up the blade to the tip (the part that can touch). */
export function bladeSeg(c, out = {}) {
  const y = c.yOff ?? -0.012;
  out.a = c.sword.localToWorld(new THREE.Vector3(c.bladeLen * 0.2, y, 0));
  out.tip = c.sword.localToWorld(new THREE.Vector3(c.bladeLen, y, 0));
  out.mid = c.sword.localToWorld(new THREE.Vector3(c.bladeLen * 0.55, y, 0));
  out.guard = c.sword.localToWorld(new THREE.Vector3(0, y, 0));
  return out;
}
export function closestSegSeg(p1, q1, p2, q2) {
  const d1 = q1.clone().sub(p1), d2 = q2.clone().sub(p2), r = p1.clone().sub(p2);
  const a = d1.dot(d1), e = d2.dot(d2), f = d2.dot(r), c = d1.dot(r), b = d1.dot(d2);
  const den = a * e - b * b;
  let s = den > 1e-9 ? clamp((b * f - c * e) / den, 0, 1) : 0, t = (b * s + f) / e;
  if (t < 0) { t = 0; s = clamp(-c / a, 0, 1); } else if (t > 1) { t = 1; s = clamp((b - c) / a, 0, 1); }
  const c1 = p1.clone().addScaledVector(d1, s), c2 = p2.clone().addScaledVector(d2, t);
  return { s, t, c1, c2, d: c1.distanceTo(c2) };
}

// ---------- CLASH AIM ----------
// Inside a film "clashes" window the defender's wrist turns the blade (pivoting at the guard, at most maxDeg,
// default 35°) so it lies across the attacker's blade at fraction s of its length. The blades meet on the
// planned frame and stay crossed through a bind, instead of hoping two keyed arcs intersect.
// byId: { id: fighter }. A fighter may give afterAim() to rebuild anything that follows its sword (main.js blade).
const _qa = new THREE.Quaternion(), _qw = new THREE.Quaternion(), _qi = new THREE.Quaternion();
export function clashAim(clashes, byId, tb) {
  for (const cl of clashes ?? []) {
    const ramp = cl.ramp ?? 0.1;
    const w = smooth(clamp((tb - (cl.t - ramp)) / ramp, 0, 1)) * (1 - smooth(clamp((tb - (cl.until ?? cl.t + 0.2)) / 0.15, 0, 1)));
    if (w <= 0) continue;
    const att = byId[cl.attacker], def = byId[cl.defender];
    if (!att || !def) continue;
    att.fig.root.updateMatrixWorld(true); def.fig.root.updateMatrixWorld(true);
    att.beforeAim?.(); def.beforeAim?.();
    const ya = att.yOff ?? -0.012, yd = def.yOff ?? -0.012;
    const P = att.sword.localToWorld(new THREE.Vector3(att.bladeLen * (cl.s ?? 0.6), ya, 0));
    const g = def.sword.localToWorld(new THREE.Vector3(0, yd, 0)), tip = def.sword.localToWorld(new THREE.Vector3(def.bladeLen, yd, 0));
    const cur = tip.sub(g).normalize(), want = P.sub(g).normalize();
    _qa.setFromUnitVectors(cur, want);
    const ang = 2 * Math.acos(clamp(_qa.w, -1, 1)), maxA = ((cl.maxDeg ?? 35) * Math.PI) / 180;
    _qw.identity().slerp(_qa, w * Math.min(1, maxA / Math.max(ang, 1e-6)));
    const turn = def.aimObject ?? def.sword;               // the object whose rotation carries the blade
    turn.parent.getWorldQuaternion(_qi);
    const local = _qi.clone().invert().multiply(_qw).multiply(_qi);
    turn.quaternion.premultiply(local);
    def.fig.root.updateMatrixWorld(true);
    def.afterAim?.();
  }
}

// ---------- EYES ----------
// Glow follows a per-performance "eyes" list [[t, glow], ...] (idle 0.9, focus 1.4, anticipation 2.2, decide 3.5,
// struck 0.4), plus a blink (2 frames shut, 1 hold, 3 open) at each time in "blinks".
// Without an "eyes" list, auto states from the contacts: focus 1.2, anticipation 2.2 over the 0.3 s before a
// contact, a one-frame "decide" flare 3.5 on it, then back to focus over 0.35 s.
export function eyesAt(perf, tb, fps, contacts = null) {
  const ks = perf?.eyes ?? [[0, 1.2]];
  let g = ks[0][1];
  for (let i = 0; i < ks.length; i++) {
    if (tb >= ks[i][0]) g = ks[i][1];
    if (i < ks.length - 1 && tb >= ks[i][0] && tb < ks[i + 1][0]) {
      const k = (tb - ks[i][0]) / (ks[i + 1][0] - ks[i][0]);
      g = ks[i][1] + (ks[i + 1][1] - ks[i][1]) * k;
    }
  }
  if (!perf?.eyes && contacts) {
    for (const c of contacts) {
      const tau = tb - c.tb;
      if (tau > -0.3 && tau < 0) g = Math.max(g, 1.2 + 1.0 * smooth((tau + 0.3) / 0.3));
      else if (tau >= 0 && tau < 1 / fps) g = Math.max(g, 3.5);
      else if (tau >= 1 / fps && tau < 0.35) g = Math.max(g, 2.2 + (1.2 - 2.2) * smooth(tau / 0.35));
    }
  }
  let lid = 0;
  for (const b of perf?.blinks ?? []) {
    const f = (tb - b) * fps;
    if (f >= 0 && f < 6) lid = Math.max(lid, f < 2 ? f / 2 : f < 3 ? 1 : 1 - (f - 3) / 3);
  }
  return { g, lid };
}
/** Eyes into a pose: lids close for blinks, glow (with the voice pulse, in film time) set on the eye material. */
export function applyEyes(c, p, tb, filmTime, { fps, voice, contacts }) {
  const e = eyesAt(c.perf, tb, fps, contacts);
  p.lid = Math.max(p.lid ?? 0, e.lid);
  if (c.fig.eyeMat) c.fig.eyeMat.emissiveIntensity = e.g * (1 + 0.8 * voiceLevel(voice, c.id, filmTime)) * (1 - 0.8 * p.lid);
  return p;
}

// ---------- ANALYSIS: contacts, hit-stops, sound cues (in body time, 240 Hz) ----------
/**
 * analyse({ film, fighters: [A, B], pose(tb), fps, dur, armed?(tb) }) → { samples, contacts, stops, bodyT, filmT, cues, events, tipSpeedAt }
 * armed(tb) false = no contact can happen then (blade still in the scabbard, rider in the boat...).
 * symmetric: contact speed = the true relative speed of the two blades at the contact point (either fighter may
 * attack); default is the
 * motion page's rule (fighter A attacks: A's speed minus 30% of B's).
 * film.effects: contactMinSpeed (m/s, slower touches are not clashes unless inside a clashes window),
 * contactGap (s, a new contact needs this long since the last one), hitStop {min, max} frames or false.
 */
export function analyse({ film, fighters, pose, fps, dur, armed = null, symmetric = false }) {
  const [A0, B0] = fighters;
  const samples = [];
  for (let i = 0; i <= dur * RATE; i++) {
    const tb = i / RATE;
    pose(tb);
    const A = bladeSeg(A0), B = bladeSeg(B0);
    const cs = closestSegSeg(A.a, A.tip, B.a, B.tip);
    const d = !armed || armed(tb) ? cs.d : 9;
    samples.push({ tb, tipH: A.tip, tipF: B.tip, d, point: cs.c1.clone().lerp(cs.c2, 0.5), sH: cs.s, sF: cs.t, ...(symmetric ? { aH: A.a, aF: B.a } : {}) });
  }
  const speed = (i, key) => i > 0 ? samples[i][key].distanceTo(samples[i - 1][key]) * RATE : 0;
  samples.forEach((s, i) => { s.vH = speed(i, 'tipH'); s.vF = speed(i, 'tipF'); });
  const contacts = [];
  const minV = film.effects?.contactMinSpeed ?? 0;      // slower touches (blades resting together) are not clashes
  const gap = film.effects?.contactGap ?? 0;
  const inClash = (tb) => (film.clashes ?? []).some((cl) => tb >= cl.t - (cl.ramp ?? 0.1) - 0.05 && tb <= (cl.until ?? cl.t + 0.2));
  let minD = { d: 9, tb: 0 }, apart = true;
  for (let i = 1; i < samples.length; i++) {
    const s = samples[i], p = samples[i - 1];
    if (s.d < minD.d) minD = { d: s.d, tb: s.tb };
    const closing = s.d < p.d;
    if (s.d > 0.08) apart = true;                       // a new contact needs the blades to have parted first
    if (s.d < 0.03 && closing && apart && !(gap && contacts.length && s.tb - contacts[contacts.length - 1].tb < gap)) {
      apart = false;
      // relative speed at the contact point (approximate: the two tips' relative velocity, scaled by position along the blade)
      const at = (q, a, tip, u) => q[a].clone().lerp(q[tip], u);   // the contact point on each blade, now and one step before
      const vRel = symmetric
        ? at(s, 'aH', 'tipH', s.sH).sub(at(p, 'aH', 'tipH', s.sH)).sub(at(s, 'aF', 'tipF', s.sF).sub(at(p, 'aF', 'tipF', s.sF))).length() * RATE
        : Math.abs(s.vH * (0.2 + 0.8 * s.sH) - s.vF * (0.2 + 0.8 * s.sF) * 0.3);
      const I = clamp((vRel - 3) / 17, 0, 1);
      if (vRel >= minV || inClash(s.tb)) contacts.push({ tb: s.tb, point: s.point.toArray(), intensity: +I.toFixed(3), vRel: +vRel.toFixed(2) });
    }
  }
  // hit-stops: 2 + 2I frames at each contact; later times shift by the earlier stops
  const HS = film.effects?.hitStop ?? { min: 3, max: 4 };
  const stops = [];
  let shift = 0;
  if (HS !== false) for (const c of contacts) {
    const d = clamp(Math.round(2 + 2 * c.intensity), HS.min, HS.max) / fps;
    c.t = c.tb + shift;
    stops.push({ t: c.t, tb: c.tb, d });
    shift += d;
  } else for (const c of contacts) c.t = c.tb;
  const bodyT = (t) => t - stops.reduce((s, st) => s + clamp(t - st.t, 0, st.d), 0);
  const filmT = (tb) => tb + stops.filter((st) => st.tb < tb).reduce((a, st) => a + st.d, 0);   // body time → film time
  // sound cues
  const AS = film.autoSounds ?? {};
  const cues = [];
  const labels = [A0.label ?? A0.id, B0.label ?? B0.id];
  { // whooshes: tip speed crosses "on" m/s, re-arms below "rearm", at least 6 frames apart; placed on the speed peak
    const on = AS.whoosh?.on ?? 9, rearm = AS.whoosh?.rearm ?? 6, sfx = AS.whoosh?.sfx ?? ['swing'];
    for (const [who, key] of [[labels[0], 'vH'], [labels[1], 'vF']]) {
      let armedW = true, peak = null, n = 0, lastT = -9;
      let cool = false;                                   // after a contact: wait for the blade to slow down
      for (const s of samples) {
        const hit = contacts.find((c) => Math.abs(s.tb - c.tb) < 0.5 / RATE);
        if (cool) { if (s[key] < rearm) cool = false; continue; }
        if (armedW && s[key] > on) { armedW = false; peak = s; }
        else if (!armedW) {
          if (s[key] > peak[key] && !hit) peak = s;
          if (s[key] < rearm || hit) {                    // a whoosh ends when the blade slows or hits something
            if (hit) cool = true;
            armedW = true;
            const t = filmT(peak.tb);
            if (t - lastT > 6 / fps) {
              const k = clamp((peak[key] - 9) / 21, 0, 1);
              cues.push({ id: `auto-whoosh-${who}-${n}`, sfx: sfx[n % sfx.length], t: +Math.max(0, t - 0.06).toFixed(3), len: 0.6,
                gain: dB(Math.min(-12, -18 + 8 * k)), rate: +(0.85 + 0.5 * k).toFixed(3), why: `${who} tip ${peak[key].toFixed(1)} m/s` });
              n++; lastT = t;
            }
          }
        }
      }
    }
  }
  // at most whoosh.maxPerSec whooshes in any second (both fighters together): the loudest win (docs/FIX-LIST.md)
  if (AS.whoosh?.maxPerSec) {
    const all = cues.filter((c) => c.id.startsWith('auto-whoosh-')).sort((a, b) => b.gain - a.gain || a.t - b.t);
    const keep = [];
    for (const c of all) if (keep.filter((k) => Math.abs(k.t - c.t) < 1).length < AS.whoosh.maxPerSec && !keep.some((k) => Math.abs(k.t - c.t) < 0.25)) keep.push(c);
    for (let i = cues.length - 1; i >= 0; i--) if (cues[i].id.startsWith('auto-whoosh-') && !keep.includes(cues[i])) cues.splice(i, 1);
  }
  // clash: steel on steel = clash-steel (or clash-light below intensity 0.4); wood involved (bokken) = a dry wood clap
  // pitched down (rate 0.8) layered with a light clash, no long steel ring
  const wood = fighters.some((f) => f.material === 'wood');
  contacts.forEach((c, i) => {
    const rate = +(1 + 0.06 * (rng(i + 3)() - 0.5) * 2).toFixed(3);
    if (wood) {
      const W = AS.clash?.wood ?? { sfx: 'clap', rate: 0.8, light: 'clash-light' };
      cues.push({ id: `auto-clash-${i}`, sfx: W.sfx ?? 'clap', t: +c.t.toFixed(3), len: 1.0,
        gain: dB(-6 + 6 * c.intensity), rate: +((W.rate ?? 0.8) * rate).toFixed(3), why: `blade contact (wood), intensity ${c.intensity}` });
      if (W.light !== false) cues.push({ id: `auto-clash-${i}-light`, sfx: W.light ?? 'clash-light', t: +c.t.toFixed(3), len: 1.0,
        gain: dB(-14 + 6 * c.intensity), rate, why: `blade contact (wood), light layer` });
    } else {
      cues.push({ id: `auto-clash-${i}`, sfx: c.intensity >= 0.4 ? (AS.clash?.sfx ?? 'clash-steel') : (AS.clash?.light ?? 'clash-light'), t: +c.t.toFixed(3), len: 1.6,
        gain: dB(-6 + 6 * c.intensity), rate, why: `blade contact, intensity ${c.intensity}` });
    }
  });
  { // scrape: blades within 4 cm for more than 4 frames while the contact point slides
    let run = [];
    const flush = () => {
      // wood on wood/steel barely sings: only a planned bind (inside a clashes window) scrapes
      if (run.length > 4 * RATE / fps && (!wood || run.some((s) => inClash(s.tb)))) {
        const t0 = filmT(run[0].tb), t1 = filmT(run[run.length - 1].tb);
        cues.push({ id: `auto-scrape-${cues.length}`, sfx: wood ? (AS.scrape?.wood ?? AS.scrape?.sfx ?? 'steel-scrape') : (AS.scrape?.sfx ?? 'steel-scrape'), query: AS.scrape?.query, t: +t0.toFixed(3),
          len: +Math.max(0.4, t1 - t0).toFixed(3), gain: dB(wood ? -22 : -16), why: `blades sliding ${(t1 - t0).toFixed(2)} s` });
      }
      run = [];
    };
    for (const s of samples) { if (s.d < 0.04) run.push(s); else flush(); }
    flush();
  }
  cues.sort((a, b) => a.t - b.t);
  const events = { contacts, stops, cues, minDistance: { d: +minD.d.toFixed(4), t: +minD.tb.toFixed(3) } };
  const tipSpeedAt = (id, tb) => { const i = clamp(Math.round(tb * RATE), 1, samples.length - 1); return id === A0.id ? samples[i].vH : samples[i].vF; };
  return { samples, contacts, stops, bodyT, filmT, cues, events, tipSpeedAt };
}

// ---------- CAMERA PUNCH at each contact: fov kick, shake, roll (call after placing the camera position) ----------
/** Moves camera.position (shake) and returns { fov, roll } with the punch added to the given fov. */
export function punch(contacts, t, camera, fov, opts = {}) {
  let roll = 0;
  const kick = opts.fov ?? 7;
  for (const c of contacts) {
    const tau = t - c.t;
    if (tau < 0 || tau > 0.6) continue;
    const I = 0.5 + 0.5 * c.intensity, env = Math.exp(-tau / 0.12);
    fov -= kick * I * env;
    const sh = 0.02 * I * Math.max(0, 1 - tau / 0.25);
    camera.position.x += Math.sin(t * 91) * sh; camera.position.y += Math.cos(t * 77) * sh;
    roll += 3 * I * env * Math.sin(tau * 40 + 1);
  }
  return { fov, roll };
}

// ---------- SMEAR RIBBON: a white paper strip swept by the blade (tip → 55% point), tapering to nothing at its tail ----------
/** makeRibbons(scene, fighters, { ribbon: {minSpeed, frames}, fps, pose, tipSpeedAt }) → { meshes, update(tb, red) } */
export function makeRibbons(scene, fighters, { ribbon, fps, pose, tipSpeedAt }) {
  const RIB = ribbon ?? { minSpeed: 5, frames: 3 };
  const RN = 28;
  const ribGeo = new THREE.BufferGeometry();
  ribGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(RN * 2 * 3), 3));
  ribGeo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(RN * 2 * 4), 4));
  const idx = [];
  for (let j = 0; j < RN - 1; j++) { const a = j * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
  ribGeo.setIndex(idx);
  const ribMat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, side: THREE.DoubleSide, fog: false, toneMapped: false });
  const meshes = {};
  for (const f of fighters) { const m = new THREE.Mesh(ribGeo.clone(), ribMat); m.frustumCulled = false; scene.add(m); meshes[f.id] = m; }
  function update(tb, red = false) {
    const span = RIB.frames / fps;
    const hist = [];
    for (let j = 0; j < RN; j++) {
      const tj = tb - (j / (RN - 1)) * span;
      pose(Math.max(0, tj));
      hist.push(Object.fromEntries(fighters.map((f) => [f.id, { ...bladeSeg(f), v: tipSpeedAt(f.id, Math.max(0, tj)) }])));
    }
    pose(tb);
    for (const f of fighters) {
      const g = meshes[f.id].geometry, P = g.attributes.position.array, C = g.attributes.color.array;
      let any = 0;
      for (let j = 0; j < RN; j++) {
        const h = hist[j][f.id], u = j / (RN - 1);
        const inner = h.mid.clone().lerp(h.tip, u * 0.85);
        P.set(h.tip.toArray(), j * 6); P.set(inner.toArray(), j * 6 + 3);
        const sf = clamp((h.v - RIB.minSpeed) / 6, 0, 1);
        const al = 0.9 * Math.pow(1 - u, 1.5) * sf;
        any = Math.max(any, al);
        const col = red ? [0.75, 0.08, 0.06] : [1, 0.97, 0.9];
        C.set([...col, al], j * 8); C.set([...col, al * 0.35], j * 8 + 4);
      }
      g.attributes.position.needsUpdate = true; g.attributes.color.needsUpdate = true;
      g.computeBoundingSphere();
      meshes[f.id].visible = any > 0.01;
    }
  }
  return { meshes, update };
}

// ---------- SPARKS: small white-gold paper shards aimed out of each contact, plus a flash light ----------
function makeSparkBurst(scene, camera, seed, n) {
  const r = rng(seed), g = new THREE.Group(); scene.add(g);
  const tri = new THREE.Shape(); tri.moveTo(0, 0.012); tri.lineTo(0.008, -0.006); tri.lineTo(-0.007, -0.005); tri.closePath();
  const geo = new THREE.ShapeGeometry(tri), parts = [];
  for (let i = 0; i < n; i++) {
    const m = new THREE.Mesh(geo, paper(['#fff6dc', '#ffd27a', '#ffe9b0'][i % 3], { repeat: 30, glow: 1.6, fog: false }));
    const a = r() * Math.PI * 2, e = r() * 1.4 - 0.4, sp = 1.5 + r() * 3.5;
    parts.push({ m, v: new THREE.Vector3(Math.cos(a) * Math.cos(e) * sp, Math.sin(e) * sp + 0.8, Math.sin(a) * Math.cos(e) * sp), w: r() * 20, s: 0.6 + r() });
    g.add(m);
  }
  return (t, t0, origin) => {
    const dt = t - t0; g.visible = dt >= 0 && dt < 0.55; if (!g.visible) return;
    const drag = (1 - Math.exp(-3 * dt)) / 3;
    for (const p of parts) {
      p.m.position.set(origin.x + p.v.x * drag, origin.y + p.v.y * drag - 2 * dt * dt, origin.z + p.v.z * drag);
      p.m.rotation.set(p.w * dt, p.w * 0.7 * dt, p.w * 1.3 * dt);
      p.m.scale.setScalar(p.s * (1 - dt / 0.55));
      p.m.lookAt(camera.position);
    }
  };
}
/** makeSparks(scene, camera, contacts) → update(t) → flash level 0..~1.6 (drive an overlay or an fx flash with it) */
export function makeSparks(scene, camera, contacts, opts = {}) {
  const sparks = contacts.map((c, i) => ({ fn: makeSparkBurst(scene, camera, 40 + i, Math.round(24 + 40 * c.intensity)), c }));
  const flashLight = new THREE.PointLight(0xffe2a8, 0, 3, 2); scene.add(flashLight);
  const update = (t) => {
    let fl = 0;
    for (const { fn, c } of sparks) {
      const o = new THREE.Vector3(...c.point);
      fn(t, c.t, o);
      const tau = t - c.t;
      if (tau >= 0 && tau < 0.3) { fl = Math.max(fl, (1 - tau / 0.3) * (0.6 + c.intensity)); flashLight.position.copy(o); }
    }
    flashLight.intensity = (opts.light ?? 6) * fl;
    return fl;
  };
  return { update, flashLight };
}

// ---------- INK IMPACT FRAME: ONE frame, washi-white page, fighters as flat ink silhouettes, red ribbon streak ----------
// film.effects.impactFrame: true (every contact, the default), false, or { minIntensity, max } = only the strongest
// "max" contacts at or above minIntensity (ties: the earliest), since an ink frame on every clash tires the eye.
export function impactContacts(film, contacts) {
  const o = film.effects?.impactFrame;
  if (o === false) return [];
  if (!o || o === true) return contacts;
  return contacts.filter((c) => c.intensity >= (o.minIntensity ?? 0))
    .sort((a, b) => b.intensity - a.intensity || a.t - b.t).slice(0, o.max ?? Infinity);
}
// extra: more film times that get the ink frame (main.js: film.effects.impactFrame.at, body times of blows that are
// not blade contacts, such as the decisive hit)
export const isImpactFrame = (film, contacts, t, fps, extra = []) =>
  impactContacts(film, contacts).some((c) => t >= c.t && t < c.t + 1 / fps) || extra.some((x) => t >= x && t < x + 1 / fps);
const inkMat = new THREE.MeshBasicMaterial({ color: '#0d0b0a', fog: false, side: THREE.DoubleSide });
const washi = new THREE.Color('#f1e7d3');
/** keep: scene children drawn as ink (fighter roots, a free-standing blade); ribbons: { id: mesh } drawn on top. */
export function renderInkFrame(renderer, scene, camera, keep, ribbons) {
  const bg = scene.background, fog = scene.fog;
  scene.background = washi; scene.fog = null;
  const rib = Object.values(ribbons);
  const hidden = scene.children.filter((o) => o.visible && !keep.includes(o) && !rib.includes(o));
  for (const o of hidden) o.visible = false;              // only the fighters: ink on a blank page
  scene.overrideMaterial = inkMat;
  for (const r of rib) r.visible = false;
  renderer.render(scene, camera);
  scene.overrideMaterial = null;
  renderer.autoClear = false;
  const only = new THREE.Scene(); for (const r of rib) { only.add(r); r.visible = true; }
  renderer.render(only, camera);
  for (const r of rib) scene.add(r);
  for (const o of hidden) o.visible = true;
  renderer.autoClear = true;
  scene.background = bg; scene.fog = fog;
}

/** FX events made from the contacts (for engine/fx.js fxAt): a chromatic-aberration flash and a bloom pulse on each. */
export function contactFx(contacts, o = {}) {
  if (o === false) return [];
  return contacts.flatMap((c) => [
    { t: c.t, effect: 'ca-flash', amount: (o.ca ?? 8) + (o.caI ?? 10) * c.intensity, dur: 0.25 },
    { t: c.t, effect: 'bloom-pulse', amount: (o.bloom ?? 0.5) + 0.6 * c.intensity, dur: 0.3 },
  ]);
}

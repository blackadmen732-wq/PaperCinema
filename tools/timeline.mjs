// TIMELINE EXPORTER: the ONE canonical animation timeline every renderer reads (format: docs/TIMELINE-FORMAT.md).
//   node tools/timeline.mjs film/<name>.json              → output/<name>.timeline.json
//   node tools/timeline.mjs --all                         → every film in film/
//   options: --sub N (weapon sub-samples per frame, default 4) · --out file · --step N (sample every Nth frame)
//            --no-scrub (skip the backward-scrub determinism check) · --horizontal · --quiet · --pretty
//
// It opens the film's own page in headless Chrome (the engine that renders the preview), asks it to pose every frame
// WITHOUT drawing where the page allows it, and writes what the engine really did: per-frame world transforms of
// every bone, root motion, the weapon (also at sub-frame resolution), the camera (position, rotation, focal length,
// focus distance), the shot list with its cut frames, events with stable ids, lights, effect parameters and asset
// references. Nothing is re-implemented, so no renderer can drift from the preview.
//
// Coverage: engine/motion.html films (camera beats) AND the shots-based main engine (engine/index.html:
// ganryujima, kuroko-duel). Gallery pages without a cast (lineup, lookdev, fx-demo) export camera + metadata only.
// The pages keep their objects private, so ONE line is added to the copy of the engine module the browser receives
// (the file on disk is never touched). If a page publishes window.PCX itself, that is used instead.
//
// Coordinates: three.js, +y up, metres, figure faces +z. ONE conversion to Blender (Z-up) is defined in
// timeline.coords.toBlender and documented in docs/TIMELINE-FORMAT.md §3; every consumer uses that and nothing else.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { serve } from '../engine/serve.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes('--' + n);
export const VERSION = 1;

// ---------- the bone order (engine/figure.js) and the standard humanoid names (blender/character/rig_trellis.py) ----------
export const BONES = ['root', 'hips', 'waist', 'chest', 'neck', 'head',
  'clavicle.R', 'shoulder.R', 'elbow.R', 'twist.R', 'hand.R',
  'clavicle.L', 'shoulder.L', 'elbow.L', 'twist.L', 'hand.L',
  'thigh.R', 'shin.R', 'foot.R', 'thigh.L', 'shin.L', 'foot.L', 'hakama'];
export const HUMANOID = {
  root: 'Root', hips: 'Hips', waist: 'Spine', chest: 'Spine1', neck: 'Neck', head: 'Head',
  'clavicle.R': 'RightShoulder', 'shoulder.R': 'RightArm', 'elbow.R': 'RightForeArm', 'twist.R': 'RightForeArmRoll', 'hand.R': 'RightHand',
  'clavicle.L': 'LeftShoulder', 'shoulder.L': 'LeftArm', 'elbow.L': 'LeftForeArm', 'twist.L': 'LeftForeArmRoll', 'hand.L': 'LeftHand',
  'thigh.R': 'RightUpLeg', 'shin.R': 'RightLeg', 'foot.R': 'RightFoot',
  'thigh.L': 'LeftUpLeg', 'shin.L': 'LeftLeg', 'foot.L': 'LeftFoot', hakama: 'Hakama',
};
// camera: three.js fov is VERTICAL degrees; one film back for everybody (full frame 36 x 24 mm, fit vertical)
export const SENSOR = { width: 36, height: 24, fit: 'vertical' };
export const focalOf = (fovDeg) => +((SENSOR.height / 2) / Math.tan((fovDeg * Math.PI) / 360)).toFixed(3);

// ---------- the one line each engine gets, so the exporter can see its private objects ----------
const HOOK = {
  'engine/motion.js': 'window.PCX ??= { kind: "motion", camera, cast, stage, trees: typeof TREES !== "undefined" ? TREES : [], beats: typeof BEATS !== "undefined" ? BEATS : [] };\n',
  'engine/main.js': 'window.PCX ??= { kind: "main", camera, cast: FIGHTERS, trees: [], beats: [],\n'
    + '  stage: (t) => { NO_DRAW = true; try { window.renderAt(t); } finally { NO_DRAW = false; } const tb = bodyT(t); const s = shotAt(tb); return { tb, shot: film.shots.indexOf(s), mode: s.mode, impactFrame: false }; } };\n',
  default: 'window.PCX ??= { kind: "simple", camera, cast: {}, trees: [], beats: [], stage: (t) => { window.renderAt(t); return { tb: t }; } };\n',
};

export function moduleOf(pagePath) {
  const html = fs.readFileSync(pagePath, 'utf8');
  const m = html.match(/<script\s+type="module"\s+src="\/?([^"]+)"/);
  return m ? m[1] : null;
}

// ---------- the sampler that runs inside the page ----------
/* eslint-disable */
function PAGE_SAMPLE({ frames, sub, bones, wantSub }) {
  const P = window.PCX, film = window.FILM, FPS = film.fps ?? 24;
  const cast = P.cast ?? {};
  const J = {
    root: (f) => f.root, hips: (f) => f.hips, waist: (f) => f.torso, chest: (f) => f.upper, neck: (f) => f.neck, head: (f) => f.head,
    'clavicle.R': (f) => f.rC, 'shoulder.R': (f) => f.rS, 'elbow.R': (f) => f.rE, 'twist.R': (f) => f.rT, 'hand.R': (f) => f.rH,
    'clavicle.L': (f) => f.lC, 'shoulder.L': (f) => f.lS, 'elbow.L': (f) => f.lE, 'twist.L': (f) => f.lT, 'hand.L': (f) => f.lH,
    'thigh.R': (f) => f.legs?.r.thigh, 'shin.R': (f) => f.legs?.r.shin, 'foot.R': (f) => f.legs?.r.foot,
    'thigh.L': (f) => f.legs?.l.thigh, 'shin.L': (f) => f.legs?.l.shin, 'foot.L': (f) => f.legs?.l.foot, hakama: (f) => f.hakama,
  };
  const r = (v) => +v.toFixed(5);
  const xf = (o) => {
    if (!o) return null;
    o.updateWorldMatrix(true, false);
    const e = o.matrixWorld.elements;
    const q = o.getWorldQuaternion(new o.quaternion.constructor());
    return [e[12], e[13], e[14], q.x, q.y, q.z, q.w].map(r);
  };
  const camera = P.camera;
  const ids = Object.keys(cast);
  const out = { frames: [], sub: [] };
  const sample = (t) => {
    const st = P.stage(t) ?? {};
    camera.updateMatrixWorld(true);
    const F = { t: r(t), tb: r(st.tb ?? t), rate: st.rate ?? 1, shot: st.shot ?? null, mode: st.mode ?? null,
      impactFrame: !!st.impactFrame,
      cam: [...camera.position.toArray(), ...camera.quaternion.toArray(), camera.fov].map(r), actors: {}, props: [] };
    for (const id of ids) {
      const c = cast[id];
      const fig = c.fig;
      if (!fig) continue;
      fig.root.updateMatrixWorld(true);
      const A = { hidden: !!c.hidden, root: xf(fig.root), ry: r(fig.root.rotation.y),
        bones: bones.map((n) => (J[n] ? xf(J[n](fig)) : null)), weapon: xf(c.sword) };
      if (c.motion) {
        const p = c.motion(F.tb);
        A.pose = Object.fromEntries(Object.entries(p).map(([k, v]) => [k, typeof v === 'number' ? r(v) : v]));
      }
      if (fig.eyeMat) A.eyes = r(fig.eyeMat.emissiveIntensity ?? 0);
      F.actors[id] = A;
    }
    for (const T of P.trees ?? []) F.props.push({ id: T.tr?.id ?? null, top: xf(T.top), halves: (T.halves ?? []).map(xf) });
    return F;
  };
  out.propSpecs = (P.trees ?? []).map((T) => ({ ...T.tr, base: T.root?.position?.toArray?.() ?? [0, 0, 0] }));
  for (const f of frames) out.frames.push({ f, ...sample(f / FPS) });
  if (wantSub) {
    for (const f of frames) for (let k = 1; k < sub; k++) {
      const t = (f + k / sub) / FPS;
      if (t > film.duration) continue;
      const st = P.stage(t) ?? {};
      const row = { t: +t.toFixed(5), tb: +(st.tb ?? t).toFixed(5), actors: {} };
      for (const id of ids) if (cast[id].sword) row.actors[id] = { weapon: xf(cast[id].sword) };
      out.sub.push(row);
    }
  }
  return out;
}
/* eslint-enable */

// ---------- derived events ----------
const vlen = (a) => Math.hypot(a[0], a[1], a[2]);
const vsub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];

/** tip of the weapon in world space from a [px,py,pz,qx,qy,qz,qw] transform (blade along +x) */
export function weaponTip(xf, bladeLen) {
  const [px, py, pz, x, y, z, w] = xf;
  // rotate (bladeLen, 0, 0) by the quaternion
  const vx = bladeLen, vy = 0, vz = 0;
  const ix = w * vx + y * vz - z * vy, iy = w * vy + z * vx - x * vz, iz = w * vz + x * vy - y * vx, iw = -x * vx - y * vy - z * vz;
  return [px + ix * w + iw * -x + iy * -z - iz * -y, py + iy * w + iw * -y + iz * -x - ix * -z, pz + iz * w + iw * -z + ix * -y - iy * -x];
}

/** swings: the weapon tip speed crosses "on" m/s and falls back under "off" → one attack-start per swing */
function attackEvents(samples, actors, fps, on = 9, off = 6) {
  const ev = [];
  for (const a of actors) {
    const len = a.weapon?.bladeLen ?? 0.91;
    const rows = samples.filter((s) => s.actors[a.id]?.weapon).map((s) => ({ t: s.t, tip: weaponTip(s.actors[a.id].weapon, len) }));
    let armed = true, start = null, peak = null, peakV = 0;
    for (let i = 1; i < rows.length; i++) {
      const v = vlen(vsub(rows[i].tip, rows[i - 1].tip)) / Math.max(1e-4, rows[i].t - rows[i - 1].t);
      if (armed && v > on) { armed = false; start = rows[i - 1].t; peak = rows[i].t; peakV = v; }
      else if (!armed) {
        if (v > peakV) { peakV = v; peak = rows[i].t; }
        if (v < off) { armed = true; ev.push({ type: 'attack-start', actor: a.id, t: +start.toFixed(3), peak: +peak.toFixed(3), speed: +peakV.toFixed(2) }); }
      }
    }
  }
  return ev.sort((x, y) => x.t - y.t);
}

/** footsteps: a foot comes down (y crosses 0.055 falling) after having been clear of the ground */
function footEvents(frames, ids, fps) {
  const ev = [];
  const iR = BONES.indexOf('foot.R'), iL = BONES.indexOf('foot.L');
  for (const id of ids) for (const [side, idx] of [['R', iR], ['L', iL]]) {
    let up = false;
    for (let i = 1; i < frames.length; i++) {
      const a = frames[i].actors[id], p = frames[i - 1].actors[id];
      if (!a || !p || a.hidden || !a.bones[idx] || !p.bones[idx]) continue;
      const y = a.bones[idx][1], py = p.bones[idx][1];
      if (y > 0.1) up = true;
      else if (up && y <= 0.055 && y < py) {
        up = false;
        ev.push({ type: 'footstep', actor: id, side, t: frames[i].t, point: a.bones[idx].slice(0, 3), speed: +((py - y) * fps).toFixed(2) });
      }
    }
  }
  return ev.sort((x, y) => x.t - y.t);
}

// ---------- the export ----------
export async function exportTimeline(filmPath, o = {}) {
  const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
  const NAME = path.basename(filmPath, '.json');
  const SUB = Number(o.sub ?? 4);
  const STEP = Math.max(1, Number(o.step ?? 1));
  const FPS = film.fps ?? 24;
  const DUR = film.duration;
  const NF = Math.round(DUR * FPS);
  const pagePath = film.page ?? 'engine/index.html';
  const modulePath = moduleOf(pagePath);
  const VERT = film.format === 'vertical' && !o.horizontal;
  const W = VERT ? 720 : (film.width ?? 1280), H = VERT ? 1280 : (film.height ?? 720);
  const say = (...m) => { if (!o.quiet) console.log(...m); };

  const server = await serve(0);
  const port = server.address().port;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.on('pageerror', (e) => console.error('PAGE ERROR:', e.message));
  const hook = HOOK[modulePath] ?? HOOK.default;
  if (modulePath) await page.route('**/' + modulePath, async (route) => {
    const src = fs.readFileSync(modulePath, 'utf8');
    const at = src.lastIndexOf('window.READY = true');
    if (at < 0) throw new Error(`timeline: ${modulePath} has no "window.READY = true" line to hook`);
    await route.fulfill({ contentType: 'text/javascript', body: src.slice(0, at) + hook + src.slice(at) });
  });
  // A crashed page never sets READY, and a ten-minute wait for that is how `--all` looked hung for
  // thirteen minutes on the gallery pages. Two minutes is longer than any page here needs to build
  // its scene, and the failure now says which page and what to do about it.
  const READY_MS = Number(opt('ready-timeout', 120000));
  await page.goto(`http://localhost:${port}/${pagePath}?render=1&film=/${filmPath}${VERT ? '&aspect=vertical' : ''}`);
  try {
    await page.waitForFunction('window.READY === true', null, { timeout: READY_MS });
  } catch {
    const closed = page.isClosed();
    await browser.close().catch(() => {});
    server.close();
    throw new Error(`timeline: ${pagePath} never set window.READY within ${READY_MS / 1000}s`
      + (closed ? ' — the browser died, usually memory: render fewer films at once.'
                : ' — the page loaded but never finished building. Open it with npm run preview and look at the console.')
      + ' Raise it with --ready-timeout <ms> if the page is genuinely that slow.');
  }
  const kind = await page.evaluate(() => window.PCX?.kind ?? null);
  if (!kind) { await browser.close(); server.close(); throw new Error(`timeline: ${pagePath} does not publish window.PCX and no hook is known for ${modulePath}`); }
  const EVENTS = await page.evaluate(() => window.EVENTS ?? null);
  const META = await page.evaluate(() => window.AUDIT?.meta ?? null);

  const frameList = [];
  for (let f = 0; f < NF; f += STEP) frameList.push(f);
  if (frameList[frameList.length - 1] !== NF - 1) frameList.push(NF - 1);
  const t0 = Date.now();
  const raw = await page.evaluate(PAGE_SAMPLE, { frames: frameList, sub: SUB, bones: BONES, wantSub: SUB > 1 });
  say(`timeline ${NAME}: sampled ${raw.frames.length} frames (+${raw.sub.length} weapon sub-samples) in ${((Date.now() - t0) / 1000).toFixed(0)} s (page ${kind})`);

  // scrub check: ask for a handful of frames again, in reverse order, and compare (a timeline must be the same
  // whether the viewer plays forward or drags backwards: every page function must be pure in t)
  let scrub = { checked: false };
  if (o.scrub !== false && raw.frames.length > 6) {
    const pick = [0, 0.17, 0.34, 0.5, 0.66, 0.83, 0.99].map((k) => frameList[Math.floor(k * (frameList.length - 1))]);
    const back = await page.evaluate(PAGE_SAMPLE, { frames: [...pick].reverse(), sub: SUB, bones: BONES, wantSub: false });
    let maxCam = 0, maxBone = 0;
    for (const b of back.frames) {
      const fwd = raw.frames.find((x) => x.f === b.f);
      if (!fwd) continue;
      maxCam = Math.max(maxCam, ...b.cam.map((v, i) => Math.abs(v - fwd.cam[i])));
      for (const id of Object.keys(b.actors)) (b.actors[id].bones ?? []).forEach((bn, i) => {
        const g = fwd.actors[id]?.bones?.[i];
        if (bn && g) maxBone = Math.max(maxBone, ...bn.map((v, k) => Math.abs(v - g[k])));
      });
    }
    scrub = { checked: true, frames: pick, maxCameraDrift: +maxCam.toFixed(6), maxBoneDrift: +maxBone.toFixed(6), stable: maxCam < 1e-3 && maxBone < 1e-3 };
    if (!scrub.stable) say(`! timeline ${NAME}: scrubbing backward changes the frame (camera ${scrub.maxCameraDrift} m, bone ${scrub.maxBoneDrift} m): a page function is not pure in t`);
  }
  await browser.close();
  server.close();

  // ---------- actors ----------
  const ids = Object.keys(raw.frames[0]?.actors ?? {});
  const castSpec = film.cast ?? {};
  const actors = ids.map((id) => ({
    id,
    character: castSpec[id]?.character ?? id,
    demonic: !!castSpec[id]?.demonic,
    hidden: !!raw.frames[0].actors[id].hidden,
    rootMotion: true,
    weapon: { kind: castSpec[id]?.weapon ?? (film.page ? 'katana' : id === 'musashi' ? 'bokken' : 'katana'),
      bladeLen: 0.91, handle: 0.33, grip: -0.06, leftGrip: -0.27,
      frame: 'blade along +x from the guard (x = 0), edge toward -y, handle along -x' },
    animation: { source: 'sampled', note: 'per-frame world transforms in frames[].actors[id].bones (no clip reference)' },
  }));

  // ---------- events with stable ids ----------
  const ev = [];
  const push = (type, data) => ev.push({ type, ...data });
  if (EVENTS?.strikes?.length) for (const c of EVENTS.strikes) push('blade-contact', { t: c.t, tb: c.tb, point: c.point, intensity: c.intensity,
    speed: c.speed, attacker: c.attacker, defender: c.defender, reactionFrames: c.reactionFrames, verified: c.verified, drives: c.drives });
  else for (const c of EVENTS?.contacts ?? []) push('blade-contact', { t: c.t ?? c.tb, tb: c.tb, point: c.point, intensity: c.intensity, speed: c.vRel, verified: null });
  for (const s of EVENTS?.stops ?? []) push('hit-stop', { t: s.t, tb: s.tb, duration: s.d });
  for (const g of EVENTS?.ground ?? []) push(g.kind === 'land' || g.kind === 'jump' ? 'footstep' : 'ground', { ...g, actor: g.id ?? g.who ?? null });
  for (const i of EVENTS?.impacts ?? []) push('impact', { t: i.t, intensity: i.intensity, point: i.point, ink: !!i.ink });
  for (const c of EVENTS?.cues ?? []) push('cue', { t: c.t, sfx: c.sfx, gain: c.gain, len: c.len, rate: c.rate, why: c.why, source: c.id });
  for (const s of film.sounds ?? []) push('cue', { t: s.t, sfx: s.sfx ?? s.query ?? s.id, gain: s.gain, len: s.len, why: 'authored', source: s.id ?? null });
  // film.events: named story beats in seconds. A negative time means "this beat does not happen in this film".
  for (const [k, t] of Object.entries(film.events ?? {})) if (typeof t === 'number' && t >= 0) push(/cut/.test(k) ? 'paper-cut' : 'beat', { t, name: k });
  for (const tr of film.props?.trees ?? []) {
    if (tr.cut) push('paper-cut', { t: tr.cut.t, target: tr.id, part: 'trunk', height: tr.cut.y, tilt: tr.cut.tilt, delay: tr.cut.delay, dir: tr.cut.dir });
    if (tr.split) push('paper-cut', { t: tr.split.t, target: tr.id, part: 'trunk-top' });
  }
  for (const i of film.impacts ?? []) if (i.at && typeof i.at === 'string') push('paper-cut', { t: i.t, target: i.at, part: 'trunk', intensity: i.intensity ?? 0.6, from: 'impact' });
  for (const v of film.voice ?? []) push('voice', { t: v.t, actor: v.who ?? v.id ?? null, line: v.text ?? v.line ?? null });
  for (const tl of film.titles ?? []) push('title', { t: tl.start, until: tl.end, style: tl.style, text: [tl.jp, tl.en, tl.sub].filter(Boolean).join(' / ') });
  ev.push(...attackEvents(raw.sub.length ? [...raw.frames, ...raw.sub].sort((a, b) => a.t - b.t) : raw.frames, actors, FPS));
  if (!(EVENTS?.ground ?? []).length) ev.push(...footEvents(raw.frames, ids, FPS));
  ev.sort((a, b) => (a.t ?? 0) - (b.t ?? 0) || a.type.localeCompare(b.type));
  const seq = {};
  for (const e of ev) {
    seq[e.type] = (seq[e.type] ?? -1) + 1;
    e.id = `${e.type}.${String(seq[e.type]).padStart(2, '0')}`;
    e.f = Math.round((e.t ?? 0) * FPS);
    if (e.t !== undefined) e.t = +e.t.toFixed(4);
  }

  // ---------- shots and cuts ----------
  let shots = [];
  if (film.shots?.length) {
    shots = film.shots.map((s, i) => ({ id: s.id ?? `S${i + 1}`, name: s.name ?? null, start: s.start, end: s.end,
      f0: Math.round(s.start * FPS), f1: Math.round(s.end * FPS) - 1, mode: s.mode ?? null,
      camera: s.rig ? { kind: 'rig', ...s.rig } : { kind: 'keyframes', ease: s.ease ?? 'inOut', keys: s.camera ?? [] },
      cutIn: i > 0 }));
  } else if (META?.beats?.length || film.camera?.length) {
    const beats = META?.beats ?? film.camera.map((b) => ({ t: b.t ?? 0, rig: b.rig, cut: !!b.cut, note: b.note }));
    shots = beats.map((b, i) => ({ id: `B${i + 1}`, name: b.note ?? null, start: b.t, end: beats[i + 1]?.t ?? DUR,
      f0: Math.round(b.t * FPS), f1: Math.round((beats[i + 1]?.t ?? DUR) * FPS) - 1,
      camera: { kind: 'beat', rig: b.rig ?? null }, cutIn: !!b.cut }));
  }
  const cuts = shots.filter((s) => s.cutIn).map((s) => s.f0);

  // ---------- camera track (frame-sampled), with focal length and focus distance ----------
  const focusOf = (F) => {
    const names = ids.filter((id) => !F.actors[id]?.hidden);
    const pts = names.map((id) => F.actors[id].bones[BONES.indexOf('chest')]).filter(Boolean);
    if (!pts.length) return null;
    const d = pts.map((p) => vlen(vsub(p.slice(0, 3), F.cam.slice(0, 3))));
    return +Math.min(...d).toFixed(4);
  };
  const frames = raw.frames.map((F) => {
    const shot = shots.find((s) => F.f >= s.f0 && F.f <= s.f1) ?? null;
    const row = {
      f: F.f, t: F.t, tb: F.tb, rate: F.rate, shot: shot?.id ?? null, cut: cuts.includes(F.f), impactFrame: F.impactFrame,
      camera: { pos: F.cam.slice(0, 3), rot: F.cam.slice(3, 7), fov: F.cam[7], focal_mm: focalOf(F.cam[7]), focus_m: focusOf(F), aperture: film.camera?.aperture ?? 2.8 },
      actors: {}, props: F.props,
    };
    for (const id of ids) {
      const A = F.actors[id];
      row.actors[id] = { hidden: A.hidden, root: A.root, ry: A.ry, bones: A.bones, weapon: A.weapon, eyes: A.eyes, pose: A.pose };
    }
    return row;
  });

  // ---------- lights, effects, assets ----------
  const lights = {
    preset: film.mode ?? (shots[0]?.mode ?? 'dawn'),
    perShot: shots.filter((s) => s.mode).map((s) => ({ shot: s.id, preset: s.mode })),
    overrides: film.light ?? null,
    note: 'the preset is resolved by the renderer (engine/world.js setMode / setLight, blender/sets lighting presets); '
      + 'amber = human, crimson = demonic (AGENTS.md rule 4)',
  };
  const effects = { ...(film.effects ?? {}) , fxBase: film.fxBase ?? null, fx: film.fx ?? null, ramps: EVENTS?.ramps ?? film.ramps ?? [],
    warp: EVENTS?.warp ?? null, autoSounds: film.autoSounds ?? null };
  const assets = [];
  const asset = (role, id, p) => { if (id && !assets.some((a) => a.role === role && a.id === id)) assets.push({ role, id, path: p }); };
  for (const a of actors) asset('character', a.character, `library/characters/${a.character}.json`);
  asset('poses', 'poses', 'library/poses.json');
  asset('moves', 'moves', 'library/moves.json');
  if (film.props?.trees?.length) asset('prop', 'paper-tree', 'engine/props.js');
  for (const e of ev) if (e.type === 'cue' && e.sfx) asset('sfx', e.sfx, `assets/sfx/${e.sfx}.wav`);
  if (film.voice) asset('voice', NAME, `output/${NAME}.voice.json`);

  const timeline = {
    format: 'paper-cinema-timeline',
    version: VERSION,
    generated: { by: 'tools/timeline.mjs', at: new Date().toISOString().slice(0, 19) + 'Z', page: pagePath, engine: kind },
    film: { name: NAME, title: film.title ?? NAME, path: filmPath, page: pagePath, fps: FPS, duration: DUR, frames: NF,
      format: VERT ? 'vertical' : 'horizontal', width: W, height: H, letterbox: film.letterbox ?? null },
    clock: { fps: FPS, base: 'film', note: 'frame f is film time f / fps; frames[].tb is the body clock (hit-stops and '
      + 'speed ramps removed) that the pose keys use; frames[].rate is the speed-ramp rate of that frame',
      sub: SUB, subNote: 'weapon transforms also at sub-frame resolution in subframes[] (motion blur, slash trails, contact tests)' },
    coords: {
      space: 'three.js', up: '+y', forward: 'the figure faces +z', handed: 'right', units: 'metres',
      rotation: 'quaternion [x, y, z, w], world space; transforms are [px, py, pz, qx, qy, qz, qw]',
      angles: 'degrees (fov is VERTICAL degrees)',
      toBlender: {
        position: '(x, y, z) -> (x, -z, y)',
        quaternion: '(x, y, z, w) -> Blender (w, x, -z, y)',
        basis: [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
        note: 'ONE conversion for the whole project (docs/TIMELINE-FORMAT.md §3). Implemented in '
          + 'blender/character/rig_trellis.py v3()/q3() and used unchanged by every reader.',
      },
      camera: { fov: 'vertical degrees', sensor: SENSOR, focal: 'focal_mm = (sensor.height / 2) / tan(fov / 2)',
        focus: 'focus_m = distance from the lens to the nearest visible actor chest', aperture: 'f-stop' },
    },
    scrub,
    actors,
    bones: { order: BONES, standard: HUMANOID, space: 'world', rootIndex: 0,
      note: 'bone 0 ("root") carries the root motion: every other bone is already in world space, so root motion is '
        + 'never applied twice. A renderer that wants local transforms multiplies by the inverse of the parent.' },
    shots, cuts, lights, effects, assets,
    props: { trees: raw.propSpecs ?? [] },
    fightDirector: EVENTS?.fightDirector ?? null,
    events: ev,
    frames,
    subframes: raw.sub,
  };
  const out = o.out ?? `output/${NAME}.timeline.json`;
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify(timeline, null, o.pretty ? 1 : 0));
  say(`timeline ${NAME}: ${frames.length} frames · ${actors.length} actor(s) · ${shots.length} shot(s) · ${ev.length} event(s)`
    + ` · scrub ${scrub.checked ? (scrub.stable ? 'stable' : 'DRIFTS') : 'skipped'} → ${out} (${(fs.statSync(out).size / 1e6).toFixed(1)} MB)`);
  return { timeline, out };
}

// ---------- CLI ----------
if (import.meta.url === `file://${process.argv[1]}`) {
  const films = flag('all') ? fs.readdirSync('film').filter((f) => f.endsWith('.json')).map((f) => `film/${f}`)
    : args.filter((a) => a.endsWith('.json'));
  if (!films.length) { console.error('usage: node tools/timeline.mjs film/<name>.json [--sub 4] [--step N] [--out file] | --all'); process.exit(2); }
  let bad = 0;
  for (const f of films) {
    try {
      await exportTimeline(f, { sub: +opt('sub', 4), step: +opt('step', 1), out: films.length === 1 ? opt('out') : undefined,
        scrub: !flag('no-scrub'), horizontal: flag('horizontal'), quiet: flag('quiet'), pretty: flag('pretty') });
    } catch (e) { bad++; console.error(`✗ ${f}: ${e.message}`); }
  }
  process.exit(bad ? 1 : 0);
}

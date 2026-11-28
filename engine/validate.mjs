// Film checker: run before any render. Explains every problem in plain words.
//   node engine/validate.mjs [film/<name>.json]
// Exit code 0 = OK, 1 = errors found (warnings never fail).
import fs from 'node:fs';
import { RIG_TYPES, FEELS, BEHAVIOURS } from './kuroko.js';
import { expandMoves, loadClipsSync } from './moves.js';
import { MOVES as CAM_MOVES } from './camfx.js';

const filmPath = process.argv[2] ?? 'film/ganryujima.json';
const errors = [], warnings = [];
const err = (where, msg) => errors.push(`✗ ${where}: ${msg}`);
const warn = (where, msg) => warnings.push(`! ${where}: ${msg}`);
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const isVec3 = (v) => Array.isArray(v) && v.length === 3 && v.every(isNum);

let film;
try { film = JSON.parse(fs.readFileSync(filmPath, 'utf8')); }
catch (e) { console.log(`✗ ${filmPath}: cannot read or parse JSON (${e.message})`); process.exit(1); }
const poses = JSON.parse(fs.readFileSync('library/poses.json', 'utf8'));
const moves = JSON.parse(fs.readFileSync('library/moves.json', 'utf8'));
const CLIPS = loadClipsSync(moves, (n) => JSON.parse(fs.readFileSync(`library/mocap/${n}.json`, 'utf8')));
const JOINTS = ['x', 'y', 'z', 'ry', 'rx', 'rz', 'tx', 'ty', 'tz', 'hx', 'hy', 'rsx', 'rsz', 'rex', 'lsx', 'lsz', 'lex', 'rwx', 'lwx', 'sway', 'swayx', 'stance', 'crouch', 'weight',
  'cx', 'cy', 'cz', 'nx', 'ny', 'hz', 'rcy', 'rcz', 'lcy', 'lcz', 'rsy', 'lsy', 'rfy', 'lfy', 'rwz', 'lwz', 'rax', 'lax', 'lid',
  'stride', 'phase'];   // stride/phase: walking feet; motion capture keys a left-foot-forward stance with them (docs/MOCAP.md)
const MOTION_FIELDS = ['ease', 'drag', 'settle', 'arc', 'arcTo', 'hang', 'cut'];   // anime motion layer (docs/ANIMATION.md §10); cut: true = a new piece of continuity starts at this key (engine/figure.js makeMotion)
const D = film.duration;
// Joint limits (radians / metres): what the paper body can do without looking broken. Outside = a warning.
// Same limits the poses in library/cuts.json were solved with (docs/ANIMATION.md §11).
import { LIMITS } from './limits.js';   // shared with engine/moves.js, which clamps to them
const limitWarned = new Set();
const checkLimits = (where, obj) => {
  for (const [k, v] of Object.entries(obj ?? {})) {
    const l = LIMITS[k];
    if (l && isNum(v) && (v < l[0] - 1e-9 || v > l[1] + 1e-9) && !limitWarned.has(where + k)) { limitWarned.add(where + k); warn(where, `${k} = ${v} is past the joint limit ${l[0]} … ${l[1]}; the limb will look broken`); }
  }
};

// --- basics
for (const k of ['fps', 'width', 'height', 'duration']) if (!isNum(film[k]) || film[k] <= 0) err(k, `must be a positive number (got ${JSON.stringify(film[k])})`);
if (film.format && !['vertical', 'horizontal'].includes(film.format)) err('format', `must be "vertical" (9:16 Shorts/TikTok/Reels) or "horizontal" (16:9) (got ${JSON.stringify(film.format)})`);
if (film.fps && (film.fps < 12 || film.fps > 60)) warn('fps', `${film.fps} is unusual; films use 24`);

// --- shots + camera
const shots = film.shots ?? [];
const SPECIAL = !shots.length && !Array.isArray(film.camera) && (film.page || !Object.keys(film.performances ?? {}).length);   // gallery / demo pages
if (SPECIAL) warn('shots', 'no shots: fine for a gallery or demo page (render it with --page), not for a film');
else if (!shots.length && !Array.isArray(film.camera)) err('shots', 'a film needs at least one shot (or a "camera" beat list on the motion page)');
let prevEnd = 0;
shots.forEach((s, i) => {
  const w = `shots[${i}] (${s.id ?? 'no id'})`;
  if (!s.id) err(w, 'needs an "id" like "S1"');
  if (!isNum(s.start) || !isNum(s.end) || s.end <= s.start) { err(w, `start/end must be numbers with end > start (got ${s.start}–${s.end})`); return; }
  if (Math.abs(s.start - prevEnd) > 1e-6) (s.start > prevEnd ? warn : err)(w, `starts at ${s.start}s but the previous shot ends at ${prevEnd}s (${s.start > prevEnd ? 'gap: the camera will hold the last shot' : 'overlap'})`);
  prevEnd = s.end;
  if (!['dawn', 'studio'].includes(s.mode)) err(w, `mode must be "dawn" or "studio" (got ${JSON.stringify(s.mode)})`);
  if (s.ease && !['linear', 'inOut'].includes(s.ease)) err(w, `ease must be "linear" or "inOut" (got ${JSON.stringify(s.ease)})`);
  if (s.rig) {
    const r = s.rig, P = film.performances ?? {};
    if (!RIG_TYPES.includes(r.type)) err(`${w}.rig`, `type must be one of ${RIG_TYPES.join(', ')} (got ${JSON.stringify(r.type)})`);
    if (r.feel && !FEELS[r.feel]) err(`${w}.rig`, `feel must be one of ${Object.keys(FEELS).join(', ')} (got ${JSON.stringify(r.feel)})`);
    for (const b of r.behaviours ?? []) if (!BEHAVIOURS[b]) err(`${w}.rig`, `unknown behaviour "${b}". Known: ${Object.keys(BEHAVIOURS).join(', ')}`);
    const names = [...(r.subjects ?? []), ...(r.subject ? [r.subject] : []), ...(r.target ? [r.target] : []), ...(r.beats ?? []).flatMap((b) => [...(b.subjects ?? []), ...(b.subject ? [b.subject] : [])])];
    for (const n of names) if (!P[n.split('.')[0]]) err(`${w}.rig`, `subject "${n}" is not a performer (known: ${Object.keys(P).join(', ')}); parts: .head .chest .hips .hand .root`);
    if (['frame', 'track', 'face'].includes(r.type) && !names.length) err(`${w}.rig`, `a "${r.type}" rig needs "subjects" or "subject"`);
    if (r.type === 'anchor') (r.beats ?? []).forEach((b, j) => {
      if (!isNum(b.t) || b.t < s.start || b.t > s.end) err(`${w}.rig.beats[${j}]`, `t must be inside the shot (${s.start}–${s.end}s)`);
      if (!RIG_TYPES.includes(b.type) || b.type === 'anchor') err(`${w}.rig.beats[${j}]`, 'each beat needs a type: frame, orbit, track, face or blade');
    });
    if (r.fov !== undefined && (!isNum(r.fov) || r.fov < 10 || r.fov > 80)) err(`${w}.rig`, 'fov must be 10–80');
  }
  const keys = s.camera ?? [];
  if (!s.rig && keys.length < 2) err(w, 'needs a KUROKO "rig" or at least 2 camera keyframes');
  keys.forEach((k, j) => {
    const kw = `${w}.camera[${j}]`;
    if (!isNum(k.t)) err(kw, 't must be a number');
    else if (k.t < s.start - 1e-6 || k.t > s.end + 1e-6) err(kw, `t=${k.t} is outside the shot (${s.start}–${s.end}s)`);
    if (j > 0 && isNum(k.t) && k.t <= keys[j - 1].t) err(kw, `keyframes must be in time order (t=${k.t} after t=${keys[j - 1].t})`);
    if (!isVec3(k.pos)) err(kw, 'pos must be [x, y, z] numbers');
    if (!isVec3(k.look)) err(kw, 'look must be [x, y, z] numbers');
    if (!isNum(k.fov) || k.fov < 10 || k.fov > 90) err(kw, `fov must be 10–90 (got ${k.fov}); 28 close, 36 normal, 42 wide`);
    if (isVec3(k.pos) && s.mode === 'dawn' && k.pos[1] < 0.15) warn(kw, `camera height ${k.pos[1]} m is at or below the ground`);
    if (isVec3(k.pos) && isVec3(k.look) && Math.hypot(...k.pos.map((v, n) => v - k.look[n])) < 0.2) err(kw, 'pos and look are almost the same point; the camera cannot aim');
  });
  if (keys.length && keys[0].t !== s.start) warn(w, `first camera key is at ${keys[0].t}s, not the shot start ${s.start}s`);
});
if (shots.length && Math.abs(prevEnd - D) > 1e-6) warn('shots', `last shot ends at ${prevEnd}s but duration is ${D}s`);

const PERFS0 = film.performances ?? {};
// --- event-driven camera moves (film.cameraMoves, engine/camfx.js)
(film.cameraMoves ?? []).forEach((m, i) => {
  const w = `cameraMoves[${i}]`;
  if (!CAM_MOVES.includes(m.move)) err(w, `move must be one of ${CAM_MOVES.join(', ')} (got ${JSON.stringify(m.move)})`);
  if (m.t === undefined && m.act === undefined && m.at !== 'contact') err(w, 'needs a time: t (film), act (action) or at: "contact"');
  if (m.move === 'rack' && !PERFS0[m.to]) err(w, `rack "to" must name a performer (known: ${Object.keys(PERFS0).join(', ')})`);
  if (m.move === 'crash' && m.zoom !== undefined && (!isNum(m.zoom) || m.zoom < 1.05 || m.zoom > 4)) err(w, 'zoom = how many times closer (1.05–4)');
  if (m.move === 'whip' && film.cameraOpts?.solver !== 2) warn(w, 'a whip pan belongs on a hard cut ("cut": true needs cameraOpts.solver: 2)');
});

// --- motion-page camera beats (film.camera, engine/motion.js)
const PERFS = film.performances ?? {};
if (film.camera !== undefined) {
  if (!Array.isArray(film.camera) || !film.camera.length) err('camera', 'must be a list of camera beats [{ t, rig, … }]');
  else film.camera.forEach((b, i) => {
    const w = `camera[${i}]`;
    const bt = b.act ?? b.t, prev = i > 0 ? film.camera[i - 1].act ?? film.camera[i - 1].t : -1;   // "act" = action time (follows the speed ramps)
    if (!isNum(bt) || bt < 0 || bt > D) err(w, `t (film time) or act (action time) must be a time within 0–${D}s`);
    if (i > 0 && (b.act === undefined) !== (film.camera[i - 1].act === undefined)) warn(w, 'mixing "t" and "act" beats: order is checked only within one clock');
    else if (i > 0 && isNum(bt) && bt <= prev) err(w, 'beats must be in time order');
    if (!['face', 'slide', 'frame', 'orbit', 'compose'].includes(b.rig)) err(w, `rig must be face, slide, frame, orbit or compose (got ${JSON.stringify(b.rig)})`);
    if (b.feel && !['locked', 'dolly', 'crane', 'handheld', 'torpedo', 'whip'].includes(b.feel)) err(w, `feel must be locked, dolly, crane, handheld, torpedo or whip (got ${JSON.stringify(b.feel)})`);
    if (b.rig === 'compose') {
      for (const k of ['size', 'size0', 'size1']) if (b[k] !== undefined && (!isNum(b[k]) || b[k] < 0.08 || b[k] > 4)) err(w, `${k} = the fraction of the frame height the subject fills (0.08–4; 0.6 = full figure with air)`);
      if (b.screen && (!Array.isArray(b.screen) || b.screen.some((v) => !isNum(v) || v < 0.1 || v > 0.9))) err(w, 'screen must be [sx, sy] between 0.1 and 0.9 (0.5, 0.5 = centre)');
      if (b.basis && !['world', 'facing', 'target'].includes(b.basis)) err(w, 'basis must be world, facing or target');
      if (b.basis === 'target' && !PERFS[b.target ?? (b.subjects ?? [])[1]]) err(w, 'basis "target" needs "target" (or a second subject) naming a performer');
      if (b.cut && film.cameraOpts?.solver !== 2) warn(w, '"cut" needs cameraOpts.solver: 2');
    }
    if (['face', 'slide'].includes(b.rig) && !PERFS[b.who]) err(w, `"who" must name a performer (known: ${Object.keys(PERFS).join(', ')})`);
    if (b.rig === 'slide') {
      for (const n of b.path ?? []) if (!['eyes', 'shoulder', 'elbow', 'wrist', 'tsuba', 'tip', 'hips', 'head'].includes(n)) err(w, `unknown joint "${n}" in path (eyes, shoulder, elbow, wrist, tsuba, tip, hips, head)`);
      if (!Array.isArray(b.path) || b.path.length < 2) err(w, 'a slide needs a "path" of at least 2 joints');
    }
    const PROPS = (film.props?.trees ?? []).map((tr) => tr.id);
    for (const n of b.subjects ?? []) if (!PERFS[n] && !PROPS.includes(n)) err(w, `subject "${n}" is not a performer or a prop (film.props.trees ids)`);
    if (b.fov !== undefined && (!isNum(b.fov) || b.fov < 10 || b.fov > 80)) err(w, 'fov must be 10–80');
  });
}
// --- speed ramps (film.ramps, motion page): [{ t (action time), rate, in, hold, out }] — docs/STUDIO-STANDARD.md §4
if (film.ramps !== undefined) {
  if (!Array.isArray(film.ramps)) err('ramps', 'must be a list [{ t, rate, in, hold, out }]');
  else film.ramps.forEach((r, i) => {
    const w = `ramps[${i}]`;
    if (!isNum(r.t) || r.t < 0 || r.t > D) err(w, `t (action time where the slow-down starts) must be within 0–${D}s`);
    if (!isNum(r.rate) || r.rate < 0.1 || r.rate > 1) err(w, 'rate must be 0.1–1 (0.2–0.35 = anime slow motion, 0.45–0.6 = a breath)');
    for (const k of ['in', 'hold', 'out']) if (r[k] !== undefined && (!isNum(r[k]) || r[k] < 0 || r[k] > 3)) err(w, `${k} is screen seconds (0–3)`);
    if ((r.hold ?? 0.4) > 1.2) warn(w, 'a slow-motion hold longer than 1.2 s kills the rhythm of a Short');
    if (i > 0 && isNum(r.t) && r.t <= film.ramps[i - 1].t) err(w, 'ramps must be in time order');
  });
}

// --- cast (look of each performer): face, eyes colour, weapon
const COLOR = /^#[0-9a-f]{6}$/i;
for (const [id, c] of Object.entries(film.cast ?? {})) {
  const w = `cast.${id}`;
  if (!PERFS[id]) warn(w, `no performance "${id}" (performers: ${Object.keys(PERFS).join(', ')})`);
  if (c.face !== undefined && c.face !== 'eyes') err(w, `face must be "eyes" (glowing eye slits with lids) or left out (faceless) (got ${JSON.stringify(c.face)})`);
  if (c.eyes !== undefined && !COLOR.test(c.eyes)) err(w, `eyes must be a colour like "#ffb04a" (amber = human, crimson = demonic)`);
  if (c.weapon !== undefined && !['bokken', 'katana'].includes(c.weapon)) err(w, `weapon must be "bokken" or "katana" (got ${JSON.stringify(c.weapon)})`);
  if (c.character !== undefined && !fs.existsSync(`library/characters/${c.character}.json`)) warn(w, `no library/characters/${c.character}.json`);
}

// --- clashes (planned blade contacts: the defender's blade is turned to meet the attacker's)
(film.clashes ?? []).forEach((c, i) => {
  const w = `clashes[${i}]`;
  if (!isNum(c.t) || c.t < 0 || c.t > D) err(w, `t (the contact second) must be within 0–${D}s`);
  if (c.until !== undefined && (!isNum(c.until) || c.until < c.t)) err(w, 'until must be a time at or after t (how long the blades stay crossed)');
  if (!PERFS[c.attacker] || !PERFS[c.defender]) err(w, `attacker and defender must name performers (got ${c.attacker}, ${c.defender})`);
  else if (c.attacker === c.defender) err(w, 'attacker and defender must be two different performers');
  if (c.s !== undefined && (!isNum(c.s) || c.s < 0.1 || c.s > 1)) err(w, 's (where on the attacker\'s blade, 0.1–1) out of range');
  if (c.ramp !== undefined && (!isNum(c.ramp) || c.ramp <= 0 || c.ramp > 0.6)) err(w, 'ramp must be 0–0.6 s');
  if (c.maxDeg !== undefined && (!isNum(c.maxDeg) || c.maxDeg <= 0 || c.maxDeg > 90)) err(w, 'maxDeg must be 0–90');
  else if ((c.maxDeg ?? 35) > 60) warn(w, `maxDeg ${c.maxDeg}: a wrist turn this large can look forced; better move the fighters or the keys closer`);
});

// --- effects (contacts, hit-stop, ribbon, impact frame) and automatic sounds
const E = film.effects;
if (E !== undefined) {
  if (E.hitStop !== undefined && E.hitStop !== false && !(isNum(E.hitStop.min) && isNum(E.hitStop.max) && E.hitStop.max >= E.hitStop.min)) err('effects.hitStop', 'must be { min, max } frames (max ≥ min) or false');
  if (E.ribbon !== undefined && !(isNum(E.ribbon.minSpeed) && (isNum(E.ribbon.frames) || (E.ribbon.style ?? 'light') !== 'paper'))) err('effects.ribbon', 'must be { minSpeed (m/s), style: "light" (default; afterglow frames, color, gain) | "paper" (frames) }');
  if (E.ribbon?.style !== undefined && !['light', 'paper'].includes(E.ribbon.style)) err('effects.ribbon.style', 'must be "light" (a crescent of light, the default) or "paper" (the old paper strip)');
  for (const k of ['ground', 'contactShadow', 'afterimage', 'speedLines']) if (E[k] !== undefined && E[k] !== false && typeof E[k] !== 'object') err(`effects.${k}`, 'must be false (off) or an options object (docs/STUDIO-STANDARD.md §7)');
  if (E.glints !== undefined && E.glints !== false && !(Array.isArray(E.glints) && E.glints.every((g) => isNum(g.t) && PERFS[g.who]))) err('effects.glints', 'must be false or a list [{ t (action time), who (performer), dur, from, to }]');
  if (E.impactFrame !== undefined && typeof E.impactFrame !== 'boolean') {
    const o = E.impactFrame;
    if (typeof o !== 'object' || (o.minIntensity !== undefined && !isNum(o.minIntensity)) || (o.max !== undefined && !isNum(o.max)) || (o.at !== undefined && !(Array.isArray(o.at) && o.at.every(isNum)))) err('effects.impactFrame', 'must be true, false or { minIntensity 0–1, max (count), at: [body seconds] }');
  }
  for (const k of ['contactMinSpeed', 'contactGap', 'sparkLight']) if (E[k] !== undefined && (!isNum(E[k]) || E[k] < 0)) err(`effects.${k}`, 'must be a number ≥ 0');
}
const AS = film.autoSounds;
if (AS !== undefined) {
  const sfxOk = (v) => typeof v === 'string' && (fs.existsSync(`assets/sfx/${v}.mp3`) || fs.existsSync(`assets/sfx/${v}.wav`));
  const chk = (where, v) => { if (v !== undefined && v !== false && !sfxOk(v)) warn(where, `no sound file assets/sfx/${v}.mp3 (sound.mjs will search for it)`); };
  (AS.whoosh?.sfx ?? []).forEach((v, i) => chk(`autoSounds.whoosh.sfx[${i}]`, v));
  chk('autoSounds.clash.sfx', AS.clash?.sfx); chk('autoSounds.clash.light', AS.clash?.light);
  chk('autoSounds.clash.wood.sfx', AS.clash?.wood?.sfx); chk('autoSounds.clash.wood.light', AS.clash?.wood?.light); chk('autoSounds.scrape.sfx', AS.scrape?.sfx);
  if (AS.whoosh?.maxPerSec !== undefined && (!isNum(AS.whoosh.maxPerSec) || AS.whoosh.maxPerSec < 1)) err('autoSounds.whoosh.maxPerSec', 'must be ≥ 1');
}
if (film.combat !== undefined && typeof film.combat !== 'boolean') err('combat', 'must be true or false (false = no contact detection, hit-stop or combat effects)');
if (film.motion !== undefined && (typeof film.motion !== 'object' || (film.motion.overlap !== undefined && typeof film.motion.overlap !== 'boolean'))) err('motion', 'must be { "overlap": true | false, "lockFeet": true | false | { … } }');
if (film.motion?.lockFeet !== undefined && typeof film.motion.lockFeet !== 'boolean' && typeof film.motion.lockFeet !== 'object') err('motion.lockFeet', 'must be true, false or an object of overrides (docs/ANIMATION.md §12)');

// --- post FX (engine/fx.js, docs/EFFECTS-CATALOG.md)
const MOODS = ['neutral', 'dawn', 'lantern', 'moonlit', 'demonic', 'kurosawa', 'ash'];   // keep in step with MOODS in engine/fx.js
const FX_EVENTS = ['ca-flash', 'flash', 'ink-impact', 'speed-lines', 'letterbox', 'bloom-pulse', 'glint', 'grade', 'shafts', 'particles', 'fade'];
const PART_KINDS = ['dust', 'ember', 'petal', 'snow', 'ash', 'shard'];
const moodOk = (g) => (typeof g === 'string' ? MOODS.includes(g) : typeof g === 'object' && (!g.mood || MOODS.includes(g.mood)));
if (film.fxBase !== undefined) {
  const B = film.fxBase;
  if (typeof B !== 'object' || Array.isArray(B)) err('fxBase', 'must be an object like { "grade": "dawn", "bloom": { "strength": 0.4 }, "vignette": { "amount": 0.5 } }');
  else {
    if (B.grade !== undefined && !moodOk(B.grade)) err('fxBase.grade', `must be a mood (${MOODS.join(', ')}) or a grade object`);
    for (const [k, f] of [['bloom', 'strength'], ['vignette', 'amount'], ['grain', 'amount'], ['letterbox', 'amount']]) if (B[k] !== undefined && !isNum(B[k][f])) err(`fxBase.${k}`, `needs a number "${f}"`);
    if ((B.bloom?.strength ?? 0) > 1.2) warn('fxBase.bloom', `strength ${B.bloom.strength} is very strong; glowing eyes and sparks will blow out (0.3–0.6 is usual)`);
    for (const n of Object.keys(B.particles ?? {})) if (!PART_KINDS.includes(film.fxParticles?.[n]?.kind ?? n)) err(`fxBase.particles.${n}`, `unknown particle kind (${PART_KINDS.join(', ')}); or set its kind in fxParticles.${n}.kind`);
  }
}
(film.fx ?? []).forEach((e, i) => {
  const w = `fx[${i}]`;
  if (!isNum(e.t) || e.t < 0 || e.t > D) err(w, `t must be within 0–${D}s`);
  if (!FX_EVENTS.includes(e.effect)) err(w, `unknown effect ${JSON.stringify(e.effect)}. Known: ${FX_EVENTS.join(', ')}`);
  if (e.effect === 'grade' && !moodOk(e.mood ?? e)) err(w, `mood must be one of ${MOODS.join(', ')}`);
  if (['shafts', 'particles'].includes(e.effect) && !e.name) err(w, `a ${e.effect} event needs the "name" of the field`);
  if (e.effect === 'glint' && !isVec3(e.at)) err(w, 'a glint needs "at": [x, y, z] (a world point)');
  if (e.body !== undefined && typeof e.body !== 'boolean') err(w, 'body must be true (timed to the action: moves later with the hit-stops) or false');
});
if ((film.fx ?? []).length && film.fxBase === undefined) warn('fx', 'fx events without fxBase: the post stack runs with a neutral grade');

// --- voice lines (docs/VOICE.md)
const vids = new Set();
(film.voice ?? []).forEach((v, i) => {
  const w = `voice[${i}] (${v.id ?? 'no id'})`;
  if (!v.id) err(w, 'needs an "id"'); else if (vids.has(v.id)) err(w, `id "${v.id}" is used twice`);
  vids.add(v.id);
  if (!PERFS[v.who]) err(w, `"who" must name a performer (known: ${Object.keys(PERFS).join(', ')}); the eyes of that fighter pulse with the words`);
  if (!isNum(v.t) || v.t < 0 || v.t > D) err(w, `t must be within 0–${D}s`);
  if (!v.text || typeof v.text !== 'string') err(w, 'needs the spoken "text"');
  if (v.speed !== undefined && (!isNum(v.speed) || v.speed < 0.5 || v.speed > 1.5)) err(w, 'speed must be 0.5–1.5');
});

// --- shakes, events, titles
(film.shakes ?? []).forEach((s, i) => {
  if (!isNum(s.t) || !isNum(s.dur) || !isNum(s.amp)) err(`shakes[${i}]`, 'needs t, dur and amp numbers');
  else if (s.amp > 0.05) warn(`shakes[${i}]`, `amp ${s.amp} is very strong (0.015 = strong hit)`);
});
for (const [k, v] of Object.entries(film.events ?? {})) if (!isNum(v) || v < -60 || v > D) err(`events.${k}`, `must be a time up to ${D}s; use a negative time for "already happened before the film starts" (got ${v})`);
(film.titles ?? []).forEach((t, i) => {
  if (!isNum(t.start) || !isNum(t.end) || t.end <= t.start) err(`titles[${i}]`, 'start/end must be numbers with end > start');
  // "quote": a spoken line, italic in quotation marks (tools/titles.py burns motion-page titles into the frames)
  if (!['hero', 'left', 'bottom', 'quote', 'endcard'].includes(t.style)) err(`titles[${i}]`, `style must be "hero", "left", "bottom", "quote" or "endcard" (got ${JSON.stringify(t.style)})`);
  if (!t.jp && !t.en) err(`titles[${i}]`, 'needs "jp" and/or "en" text');
});

// --- sounds
const ids = new Set();
(film.sounds ?? []).forEach((c, i) => {
  const w = `sounds[${i}] (${c.id ?? 'no id'})`;
  if (!c.id) err(w, 'needs an "id"');
  else if (ids.has(c.id)) err(w, `id "${c.id}" is used twice; each cue needs its own id`);
  ids.add(c.id);
  if (!isNum(c.t) || c.t < 0 || c.t > D) err(w, `t must be within 0–${D}s`);
  if (c.sfx) return;                        // reuses a sound already in assets/sfx by id: no search needed
  if (c.file) {                             // a ready local file (a synthesized score, a made sound): no search either
    if (!isNum(c.len) || c.len <= 0) err(w, 'len (seconds used) must be > 0');
    if (!isNum(c.gain) || c.gain < 0 || c.gain > 2) err(w, 'gain must be 0–2 (1 = normal)');
    return;
  }
  if (!c.query) err(w, 'needs "query" search words, e.g. "sword unsheath"');
  if (!isNum(c.len) || c.len <= 0) err(w, 'len (seconds used) must be > 0');
  if (!isNum(c.min) || !isNum(c.max) || c.max <= c.min) err(w, 'min/max (milliseconds) must be numbers with max > min');
  if (isNum(c.t) && isNum(c.len) && c.t + c.len > D + 0.5) warn(w, `runs past the end of the film (${(c.t + c.len).toFixed(1)}s)`);
  if (!isNum(c.gain) || c.gain < 0 || c.gain > 2) err(w, 'gain must be 0–2 (1 = normal)');
  if (c.body !== undefined && typeof c.body !== 'boolean') err(w, 'body must be true (timed to the action: moves later with the hit-stops) or false');
});

// --- performances
for (const [id, p] of Object.entries(film.performances ?? {})) {
  const w = `performances.${id}`;
  const keys = p.keys ?? [];
  if (!keys.length) err(w, 'needs a "keys" list');
  keys.forEach((k, j) => {
    const kw = `${w}.keys[${j}]`;
    if (!isNum(k.t)) err(kw, 't must be a number');
    if (j > 0 && isNum(k.t) && k.t <= keys[j - 1].t && !keys[j - 1].move) err(kw, `keys must be in time order with no repeats (t=${k.t} after t=${keys[j - 1].t}); to hold a pose, repeat it at a later time`);
    if (k.move && !moves[k.move]) err(kw, `unknown move "${k.move}". Known moves: ${Object.keys(moves).filter((n) => !n.startsWith('_')).join(', ')}`);
    if (k.move && k.pose) err(kw, 'use either "move" or "pose" on a key, not both');
    checkLimits(kw, k);
    if (k.pose && poses[k.pose]) checkLimits(`pose "${k.pose}" (library/poses.json)`, poses[k.pose]);
    if (k.move && Array.isArray(moves[k.move])) moves[k.move].forEach((bt, n) => { checkLimits(`move "${k.move}" beat ${n} (library/moves.json)`, bt); if (poses[bt.pose]) checkLimits(`pose "${bt.pose}" (library/poses.json)`, poses[bt.pose]); else err(`move "${k.move}" beat ${n}`, `unknown pose "${bt.pose}"`); });
    if (k.pose && !poses[k.pose]) err(kw, `unknown pose "${k.pose}". Known poses: ${Object.keys(poses).filter((n) => !n.startsWith('_')).join(', ')}`);
    for (const key of Object.keys(k)) if (!['t', 'pose', 'note', 'move', 'speed', 'dist', 'anime', ...MOTION_FIELDS].includes(key) && !JOINTS.includes(key)) err(kw, `unknown field "${key}". Allowed: t, pose, move, speed, dist, anime, note, ${MOTION_FIELDS.join(', ')}, ${JOINTS.join(', ')}`);
    if (j > 0 && isNum(k.t)) {
      const dt = k.t - keys[j - 1].t;
      const moved = ['x', 'z'].map((a) => (k[a] ?? null)).some((v) => v !== null);
      // dense keys (motion capture) may move every frame: only a jump faster than 6 m/s is a teleport
      const pk = keys[j - 1], dist = isNum(pk.x) && isNum(pk.z) && isNum(k.x) && isNum(k.z) ? Math.hypot(k.x - pk.x, k.z - pk.z) : null;
      // a teleport on purpose (hidden by a camera cut) says so with "cut": true (engine/figure.js splits the curve there)
      if (moved && dt < 0.15 && (dist === null || dist / dt > 6) && !k.cut) warn(kw, `position changes in ${dt.toFixed(2)}s; that is a teleport, not a step (if a camera cut hides it, mark the key "cut": true)`);
    }
  });
  try {
    const ex = expandMoves(keys, moves, CLIPS);
    // Check the EXPANDED keys as well. A move with an `anime` dial, or a retargeted capture, makes
    // its numbers here and not in the film file, so checking only what the author typed missed them
    // entirely — which is how a head 53 degrees past its limit shipped in a film that validated.
    for (const k of ex) checkLimits(`${w} (after moves are expanded, t=${k.t}s)`, k);
    for (let j = 1; j < ex.length; j++) if (ex[j].t <= ex[j - 1].t) {
      err(w, `after moves are expanded, a key at ${ex[j].t}s comes before or at ${ex[j - 1].t}s; the previous move is still running. Start the next key later (jump-back lasts 0.85 s, lunge-shomen 1.0 s; see library/moves.json)`);
      break;
    }
  } catch (e) { err(w, e.message); }
  for (const f of ['walk', 'twoHand']) (p[f] ?? []).forEach((win, j) => {
    if (!Array.isArray(win) || win.length !== 2 || !win.every(isNum) || win[1] <= win[0]) err(`${w}.${f}[${j}]`, 'must be [start, end] seconds with end > start');
  });
  if (p.boatPose && !poses[p.boatPose]) err(`${w}.boatPose`, `unknown pose "${p.boatPose}"`);
  if (p.eyes !== undefined) {
    if (!Array.isArray(p.eyes) || !p.eyes.every((e) => Array.isArray(e) && e.length === 2 && e.every(isNum))) err(`${w}.eyes`, 'must be [[t, glow], …] (idle 0.9, focus 1.4, anticipation 2.2, decide 3.5, struck 0.4)');
    else p.eyes.forEach((e, j) => { if (j > 0 && e[0] <= p.eyes[j - 1][0]) err(`${w}.eyes[${j}]`, 'times must increase'); if (e[1] < 0 || e[1] > 5) err(`${w}.eyes[${j}]`, 'glow must be 0–5'); });
    if (!film.cast?.[id]?.face && !film.page) warn(`${w}.eyes`, `the eyes only show with cast.${id}.face = "eyes"`);
  }
  if (p.blinks !== undefined && !(Array.isArray(p.blinks) && p.blinks.every(isNum))) err(`${w}.blinks`, 'must be a list of seconds');
  // envelopes [[t, amount], ...]: life = the breathing/idle layer (0 = a dead body), track = how much the head turns
  // to the opponent (0 = looks where the body faces, 1 = full tracking; engine/motion.js poseOf)
  for (const f of ['life', 'track']) {
    if (p[f] === undefined) continue;
    if (!Array.isArray(p[f]) || !p[f].every((e) => Array.isArray(e) && e.length === 2 && e.every(isNum))) err(`${w}.${f}`, 'must be [[t, amount], …]');
    else p[f].forEach((e, j) => { if (j > 0 && e[0] < p[f][j - 1][0]) err(`${w}.${f}[${j}]`, 'times must not go back'); if (e[1] < 0 || e[1] > 1.5) err(`${w}.${f}[${j}]`, 'amount must be 0-1.5'); });
  }
  // gait (engine/footlock.js, with motion.lockFeet): arms = how much each arm [right, left] swings while walking, 0-1.5
  // (0 = it holds something: a hand on the hilt never swings)
  if (p.gait !== undefined) {
    const a = p.gait?.arms;
    if (typeof p.gait !== 'object' || Array.isArray(p.gait)) err(`${w}.gait`, 'must be an object, e.g. { "arms": [0.3, 1] }');
    else if (a !== undefined && !(Array.isArray(a) && a.length === 2 && a.every((x) => isNum(x) && x >= 0 && x <= 1.5))) err(`${w}.gait.arms`, 'must be [right, left], each 0-1.5');
    if (!film.motion?.lockFeet) warn(`${w}.gait`, 'the gait only acts with motion.lockFeet');
  }
}

(film.duels ?? []).forEach((d, i) => {
  const P = film.performances ?? {};
  if (!P[d.a] || !P[d.b]) err(`duels[${i}]`, `a and b must name performances (got ${d.a}, ${d.b})`);
  if (!isNum(d.from) || !isNum(d.to) || d.to <= d.from) err(`duels[${i}]`, 'from/to must be seconds with to > from');
});

for (const line of warnings) console.log(line);
for (const line of errors) console.log(line);
console.log(errors.length ? `\n${errors.length} error(s) in ${filmPath}. Fix them before rendering.` : `✓ ${filmPath} is valid (${shots.length} shots, ${(film.sounds ?? []).length} sounds, ${Object.keys(film.performances ?? {}).length} performers, ${warnings.length} warning(s)).`);
process.exit(errors.length ? 1 : 0);

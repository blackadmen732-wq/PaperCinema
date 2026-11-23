// Film checker: run before any render. Explains every problem in plain words.
//   node engine/validate.mjs [film/<name>.json]
// Exit code 0 = OK, 1 = errors found (warnings never fail).
import fs from 'node:fs';

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
const JOINTS = ['x', 'y', 'z', 'ry', 'rx', 'rz', 'tx', 'ty', 'tz', 'hx', 'hy', 'rsx', 'rsz', 'rex', 'lsx', 'lsz', 'lex', 'rwx', 'lwx', 'sway', 'swayx'];
const D = film.duration;

// --- basics
for (const k of ['fps', 'width', 'height', 'duration']) if (!isNum(film[k]) || film[k] <= 0) err(k, `must be a positive number (got ${JSON.stringify(film[k])})`);
if (film.fps && (film.fps < 12 || film.fps > 60)) warn('fps', `${film.fps} is unusual; films use 24`);

// --- shots + camera
const shots = film.shots ?? [];
if (!shots.length) err('shots', 'a film needs at least one shot');
let prevEnd = 0;
shots.forEach((s, i) => {
  const w = `shots[${i}] (${s.id ?? 'no id'})`;
  if (!s.id) err(w, 'needs an "id" like "S1"');
  if (!isNum(s.start) || !isNum(s.end) || s.end <= s.start) { err(w, `start/end must be numbers with end > start (got ${s.start}–${s.end})`); return; }
  if (Math.abs(s.start - prevEnd) > 1e-6) (s.start > prevEnd ? warn : err)(w, `starts at ${s.start}s but the previous shot ends at ${prevEnd}s (${s.start > prevEnd ? 'gap: the camera will hold the last shot' : 'overlap'})`);
  prevEnd = s.end;
  if (!['dawn', 'studio'].includes(s.mode)) err(w, `mode must be "dawn" or "studio" (got ${JSON.stringify(s.mode)})`);
  if (s.ease && !['linear', 'inOut'].includes(s.ease)) err(w, `ease must be "linear" or "inOut" (got ${JSON.stringify(s.ease)})`);
  const keys = s.camera ?? [];
  if (keys.length < 2) err(w, 'camera needs at least 2 keyframes (start and end)');
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

// --- shakes, events, titles
(film.shakes ?? []).forEach((s, i) => {
  if (!isNum(s.t) || !isNum(s.dur) || !isNum(s.amp)) err(`shakes[${i}]`, 'needs t, dur and amp numbers');
  else if (s.amp > 0.05) warn(`shakes[${i}]`, `amp ${s.amp} is very strong (0.015 = strong hit)`);
});
for (const [k, v] of Object.entries(film.events ?? {})) if (!isNum(v) || v < 0 || v > D) err(`events.${k}`, `must be a time within 0–${D}s (got ${v})`);
(film.titles ?? []).forEach((t, i) => {
  if (!isNum(t.start) || !isNum(t.end) || t.end <= t.start) err(`titles[${i}]`, 'start/end must be numbers with end > start');
  if (!['hero', 'left', 'bottom'].includes(t.style)) err(`titles[${i}]`, `style must be "hero", "left" or "bottom" (got ${JSON.stringify(t.style)})`);
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
  if (!c.query) err(w, 'needs "query" search words, e.g. "sword unsheath"');
  if (!isNum(c.len) || c.len <= 0) err(w, 'len (seconds used) must be > 0');
  if (!isNum(c.min) || !isNum(c.max) || c.max <= c.min) err(w, 'min/max (milliseconds) must be numbers with max > min');
  if (isNum(c.t) && isNum(c.len) && c.t + c.len > D + 0.5) warn(w, `runs past the end of the film (${(c.t + c.len).toFixed(1)}s)`);
  if (!isNum(c.gain) || c.gain < 0 || c.gain > 2) err(w, 'gain must be 0–2 (1 = normal)');
});

// --- performances
for (const [id, p] of Object.entries(film.performances ?? {})) {
  const w = `performances.${id}`;
  const keys = p.keys ?? [];
  if (!keys.length) err(w, 'needs a "keys" list');
  keys.forEach((k, j) => {
    const kw = `${w}.keys[${j}]`;
    if (!isNum(k.t)) err(kw, 't must be a number');
    if (j > 0 && isNum(k.t) && k.t <= keys[j - 1].t) err(kw, `keys must be in time order with no repeats (t=${k.t} after t=${keys[j - 1].t}); to hold a pose, repeat it at a later time`);
    if (k.pose && !poses[k.pose]) err(kw, `unknown pose "${k.pose}". Known poses: ${Object.keys(poses).filter((n) => !n.startsWith('_')).join(', ')}`);
    for (const key of Object.keys(k)) if (!['t', 'pose', 'note'].includes(key) && !JOINTS.includes(key)) err(kw, `unknown field "${key}". Allowed: t, pose, note, ${JOINTS.join(', ')}`);
    if (j > 0 && isNum(k.t)) {
      const dt = k.t - keys[j - 1].t;
      const moved = ['x', 'z'].map((a) => (k[a] ?? null)).some((v) => v !== null);
      if (moved && dt < 0.15) warn(kw, `position changes in ${dt.toFixed(2)}s; that is a teleport, not a step`);
    }
  });
  for (const f of ['walk', 'twoHand']) (p[f] ?? []).forEach((win, j) => {
    if (!Array.isArray(win) || win.length !== 2 || !win.every(isNum) || win[1] <= win[0]) err(`${w}.${f}[${j}]`, 'must be [start, end] seconds with end > start');
  });
  if (p.boatPose && !poses[p.boatPose]) err(`${w}.boatPose`, `unknown pose "${p.boatPose}"`);
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

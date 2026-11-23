// Camera resolver (Node, no browser): computes where KUROKO puts the camera on every frame of every
// rig shot, plus where each fighter stands, and writes output/<film>.camera.json.
// The playbook uses it to draw KUROKO camera paths; reviewers can see exactly why the camera moved.
//   node engine/resolve-camera.mjs [film/<name>.json]
import fs from 'node:fs';
import path from 'node:path';
import { makeMotion, resolveKeys } from './figure.js';
import { expandMoves } from './moves.js';
import { makeKuroko } from './kuroko.js';

const filmPath = process.argv[2] ?? 'film/ganryujima.json';
const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
const poses = JSON.parse(fs.readFileSync('library/poses.json', 'utf8'));
const moves = JSON.parse(fs.readFileSync('library/moves.json', 'utf8'));
const motions = {};
for (const [id, p] of Object.entries(film.performances ?? {})) motions[id] = makeMotion(resolveKeys(expandMoves(p.keys, moves), poses));
const pair = {};
for (const d of film.duels ?? []) { pair[d.a] = d.b; pair[d.b] = d.a; }
const impacts = [...new Set([...(film.shakes ?? []).map((s) => s.t), ...(film.events?.impact !== undefined ? [film.events.impact] : [])])];
const aspect = (process.argv.includes('--vertical') ? 720 / 1280 : film.width / film.height);
const kuroko = makeKuroko({ motions, impacts, pair, aspect });
const r = (v) => Math.round(v * 1000) / 1000;

const out = { film: path.basename(filmPath), fps: film.fps, shots: {}, subjects: {} };
for (const shot of film.shots) {
  if (!shot.rig) continue;
  const rows = [];
  for (let f = Math.round(shot.start * film.fps); f < Math.round(shot.end * film.fps); f++) {
    const t = f / film.fps;
    const c = kuroko.at(shot, t);
    rows.push([r(t), ...c.pos.map(r), ...c.look.map(r), r(c.fov), r(c.roll)]);
  }
  out.shots[shot.id] = rows;
}
for (const id of Object.keys(motions)) {
  const rows = [];
  for (let f = 0; f <= film.duration * film.fps; f += 2) { const p = motions[id](f / film.fps); rows.push([r(f / film.fps), r(p.x), r(p.z)]); }
  out.subjects[id] = rows;
}
fs.mkdirSync('output', { recursive: true });
const dest = `output/${path.basename(filmPath, '.json')}.camera.json`;
fs.writeFileSync(dest, JSON.stringify(out));
console.log(`wrote ${dest}: ${Object.keys(out.shots).length} KUROKO shots, ${Object.keys(out.subjects).length} subjects`);

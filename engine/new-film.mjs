// Start a new film that always opens and ends the signature way.
//   node engine/new-film.mjs <name> --jp 一騎打ち --en "ICHIKI-UCHI" --sub "One-on-one" --next "Next: the cursed blade"
//        [--body film/kuroko-duel.json] [--opening lantern-wave] [--endcard paper-cinema]
// = signature opening (library/openings) + a fight body (any film, times shifted) + end card (library/endcards).
// Then edit film/<name>.json (research, cast, choreography, camera) and run: node engine/make.mjs film/<name>.json
import fs from 'node:fs';
import { execSync } from 'node:child_process';

const a = process.argv.slice(2);
const name = a[0];
if (!name || name.startsWith('--')) { console.log('usage: node engine/new-film.mjs <name> --jp <kanji> --en <title> [--sub ..] [--next ..] [--body film/x.json]'); process.exit(1); }
const opt = (k, d) => { const i = a.indexOf('--' + k); return i >= 0 ? a[i + 1] : d; };
const fill = (o, vars) => JSON.parse(JSON.stringify(o).replace(/\{(jp|en|sub|next)\}/g, (_, k) => (vars[k] ?? '').replace(/"/g, '\\"')));
const vars = { jp: opt('jp', '紙の剣'), en: opt('en', name.toUpperCase()), sub: opt('sub', ''), next: opt('next', 'Next episode soon') };
const opening = fill(JSON.parse(fs.readFileSync(`library/openings/${opt('opening', 'lantern-wave')}.json`, 'utf8')), vars);
const endcard = fill(JSON.parse(fs.readFileSync(`library/endcards/${opt('endcard', 'paper-cinema')}.json`, 'utf8')), vars);
const body = JSON.parse(fs.readFileSync(opt('body', 'film/kuroko-duel.json'), 'utf8'));
const O = opening.duration;
const sh = (t) => +(t + O).toFixed(4);

// drop the body's own hero titles and end cards (the templates replace them)
body.titles = (body.titles ?? []).filter((t) => !['hero', 'endcard'].includes(t.style));
for (const s of body.shots) {
  s.start = sh(s.start); s.end = sh(s.end);
  for (const k of s.camera ?? []) k.t = sh(k.t);
  for (const b of s.rig?.beats ?? []) b.t = sh(b.t);
}
for (const s of body.shakes ?? []) s.t = sh(s.t);
for (const k of Object.keys(body.events ?? {})) if (body.events[k] >= 0) body.events[k] = sh(body.events[k]);
for (const p of Object.values(body.performances ?? {})) {
  for (const k of p.keys) k.t = sh(k.t);
  for (const f of ['twoHand', 'walk']) if (p[f]) p[f] = p[f].map(([x, y]) => [sh(x), sh(y)]);
  if (p.rideBoatUntil) p.rideBoatUntil = sh(p.rideBoatUntil);
}
for (const d of body.duels ?? []) { d.from = sh(d.from); d.to = sh(d.to); }
// Everything else in the body that carries a time moves too. Forgetting `clashes` left the clash aim
// 6 s before the strike it was written for, so the blades never met (28 Nov pilot: 0 contacts).
for (const c of body.clashes ?? []) { c.t = sh(c.t); if (c.until != null) c.until = sh(c.until); }
for (const f of body.fx ?? []) if (typeof f.t === 'number') f.t = sh(f.t);
for (const r of body.ramps ?? []) if (typeof r.t === 'number') r.t = sh(r.t);
for (const v of body.voice ?? []) if (typeof v.t === 'number') v.t = sh(v.t);
if (Array.isArray(body.effects?.impactFrame?.at)) body.effects.impactFrame.at = body.effects.impactFrame.at.map(sh);
// A body written for 16:9 loses its two-shots in 9:16: an orbit at the same radius sees a third of
// the width, so both fighters fall out of frame (28 Nov pilot: no subject in frame 6-9 s). Pull
// those orbits back so the pair fits the narrow frame. The factor is measured (tools/camera_check.mjs).
const VERTICAL_ORBIT_PULLBACK = 2;
const toVertical = opt('format', 'vertical') === 'vertical' && body.format !== 'vertical';
if (toVertical) for (const s of body.shots) {
  if (s.rig?.type === 'orbit' && (s.rig.subjects?.length ?? 0) >= 2 && typeof s.rig.radius === 'number')
    s.rig.radius = +(s.rig.radius * VERTICAL_ORBIT_PULLBACK).toFixed(3);
}
for (const t of body.titles) { t.start = sh(t.start); t.end = sh(t.end); }
const D = +(body.duration + O).toFixed(4);
const sounds = (body.sounds ?? []).filter((c) => !opening.sounds.some((o) => o.id === c.id) && !endcard.sounds.some((o) => o.id === c.id))
  .map((c) => (c.bed ? { ...c, t: 0, len: D } : { ...c, t: sh(c.t) }));
const E = D - endcard.duration;
const film = {
  ...body,
  title: `${vars.en} — ${vars.sub}`.replace(/ — $/, ''),
  format: opt('format', 'vertical'),   // Shorts / TikTok / Reels by default; --format horizontal for YouTube 16:9
  duration: D,
  shots: [...opening.shots, ...body.shots],
  titles: [...opening.titles, ...body.titles, ...endcard.titles.map((t) => ({ ...t, start: +(E + t.start).toFixed(3), end: +(E + t.end).toFixed(3) }))],
  sounds: [...opening.sounds, ...sounds, ...endcard.sounds.map((c) => ({ ...c, t: +(E + c.t).toFixed(3) }))],
};
// --foley [surface]: the new film starts with adaptive footsteps on (engine/sound.mjs; off unless asked)
if (a.includes('--foley')) { const v = opt('foley'); film.autoSounds = { ...(film.autoSounds ?? {}), footsteps: { surface: v && !v.startsWith('--') ? v : 'sand' } }; }
const out = `film/${name}.json`;
if (fs.existsSync(out) && !a.includes('--force')) { console.log(`${out} already exists (add --force to overwrite)`); process.exit(1); }
fs.writeFileSync(out, JSON.stringify(film, null, 2));
console.log(`wrote ${out} (${D}s: ${O}s signature opening + ${body.duration}s body + end card)`);
execSync(`node engine/validate.mjs ${out}`, { stdio: 'inherit' });

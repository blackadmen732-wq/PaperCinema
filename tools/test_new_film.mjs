#!/usr/bin/env node
// REGRESSION TEST for the new-film scaffold (engine/new-film.mjs). Two failures it guards against,
// both found by the 28 Nov head-to-head pilot in the scaffold every new film starts from:
//   1. the clash aim stayed at the body's own times, 6 s before the strikes, so the blades never met
//      (0 contacts, no clash sound);
//   2. a 16:9 body scaffolded as 9:16 kept its orbit radius, so both fighters left the frame (6-9 s).
//
//   node tools/test_new_film.mjs            data checks only, under a second
//   node tools/test_new_film.mjs --browser  also renders: contacts > 0, and the camera checker passes
//                                           every orbit two-shot (about 2 minutes, headless Chrome)
// Exit 0 = pass. It scaffolds film/_test-scaffold.json and deletes it afterwards.
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';

const NAME = '_test-scaffold', OUT = `film/${NAME}.json`;
const body = JSON.parse(fs.readFileSync('film/kuroko-duel.json', 'utf8'));
const opening = JSON.parse(fs.readFileSync('library/openings/lantern-wave.json', 'utf8'));
const O = opening.duration;
let fail = 0;
const ok = (cond, msg) => { console.log(`  ${cond ? '✓' : '✗'} ${msg}`); if (!cond) fail++; };
const near = (a, b) => Math.abs(a - b) < 1e-3;

try {
  execFileSync('node', ['engine/new-film.mjs', NAME, '--jp', '試', '--en', 'TEST', '--force'], { stdio: 'pipe' });
  const f = JSON.parse(fs.readFileSync(OUT, 'utf8'));
  console.log(`new-film scaffold (opening ${O} s + kuroko-duel body)`);
  ok((body.clashes ?? []).length > 0 && f.clashes.every((c, i) => near(c.t, body.clashes[i].t + O) && (c.until == null || near(c.until, body.clashes[i].until + O))),
    'every clash moved with its strike (t and until + opening)');
  ok(f.clashes.every((c) => c.t >= O && c.t <= f.duration), 'no clash lands inside the opening or past the end');
  ok((f.fx ?? []).every((x, i) => near(x.t, body.fx[i].t + O)), 'fx times moved');
  const at = f.effects?.impactFrame?.at ?? [];
  ok(at.every((t, i) => near(t, body.effects.impactFrame.at[i] + O)), 'impact-frame times moved');
  const orb = (s) => s.rig?.type === 'orbit' && (s.rig.subjects?.length ?? 0) >= 2;
  const bodyOrbits = body.shots.filter(orb), filmOrbits = f.shots.filter((s) => orb(s) && s.start >= O);
  ok(f.format !== 'vertical' || body.format === 'vertical' || filmOrbits.every((s, i) => s.rig.radius >= bodyOrbits[i].rig.radius * 1.99),
    'vertical scaffold pulls two-shot orbits back');

  if (process.argv.includes('--browser')) {
    const r = execFileSync('node', ['engine/render.mjs', '--film', OUT, '--still', String(O + 1)], { encoding: 'utf8' });
    const contacts = +(r.match(/events: (\d+) contacts/)?.[1] ?? 0);
    ok(contacts > 0, `blades meet: ${contacts} contact(s) detected`);
    for (const s of filmOrbits) {
      let res;
      try { res = execFileSync('node', ['tools/camera_check.mjs', OUT, '--from', String(s.start), '--to', String(s.end + 0.2), '--quiet', '--json'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }); }
      catch (e) { res = e.stdout?.toString() ?? '{}'; }
      const shot = (JSON.parse(res).shots ?? []).find((x) => x.id === s.id);
      ok(shot && shot.checks?.visibility === 1 && shot.verdict === 'passed', `${s.id} "${s.name}": fighters in frame (${shot?.verdict ?? 'not measured'})`);
    }
  }
} finally {
  fs.rmSync(OUT, { force: true });
  for (const x of ['events', 'camera-check', 'audit'].flatMap((k) => [`output/${NAME}.${k}.json`, `output/${NAME}.${k}.md`])) fs.rmSync(x, { force: true });
}
console.log(fail ? `\n${fail} check(s) FAILED` : '\nall checks pass');
process.exit(fail ? 1 : 0);

#!/usr/bin/env node
// PROMISES: every fix that was stated out loud, with a command that proves it (AGENTS.md rule 0a).
//
//   node tools/promises.mjs                  # run every check, exit 1 if a KEPT promise has broken
//   node tools/promises.mjs --open           # just list what is still owed
//   node tools/promises.mjs --check-limits   # the built-in check: no joint past its limit, any film
//   node tools/promises.mjs --check-sleeve-clearance
//
// Why this exists. On 25 Nov the films were rendered with the box character after that exact
// problem had been written down as item one of docs/FIX-EVERYTHING.md the same morning. Writing a
// problem down is not a safeguard; a list nobody runs is a diary. This one runs.
//
// The rule it enforces: a promise marked `kept` whose check fails is a REGRESSION and fails the
// run. A promise marked OPEN is a debt, reported but not an error, so the list can be honest about
// what is still owed without blocking work.
import fs from 'node:fs';
import { execSync } from 'node:child_process';
import { LIMITS } from '../engine/limits.js';

const args = process.argv.slice(2);
const ROOT = new URL('..', import.meta.url).pathname;

// ---------------------------------------------------------------- built-in checks
function checkLimits() {
  const files = fs.readdirSync(`${ROOT}output`).filter((f) => f.endsWith('.timeline.json'));
  if (!files.length) { console.log('  no timelines built yet (run tools/timeline.mjs) — cannot check'); return true; }
  let bad = 0, worst = null;
  for (const f of files) {
    const tl = JSON.parse(fs.readFileSync(`${ROOT}output/${f}`, 'utf8'));
    for (const fr of tl.frames ?? []) {
      for (const [aid, a] of Object.entries(fr.actors ?? {})) {
        for (const [ch, v] of Object.entries(a.pose ?? {})) {
          const l = LIMITS[ch];
          if (!l || typeof v !== 'number') continue;
          const over = v < l[0] ? l[0] - v : v > l[1] ? v - l[1] : 0;
          if (over > 1e-6) { bad++; if (!worst || over > worst.over) worst = { f, frame: fr.f, aid, ch, v, l, over }; }
        }
      }
    }
  }
  if (bad) console.log(`  ${bad} joint value(s) past a limit — worst ${worst.ch}=${worst.v.toFixed(2)} (limit ${worst.l}) at ${worst.f} frame ${worst.frame}, ${worst.aid}`);
  else console.log(`  checked ${files.length} timeline(s): no joint past its limit`);
  return bad === 0;
}

// The sleeve check moved out of here on purpose. It used to read the shoulder angle and ASSUME a
// raised arm means a buried head — a guess about geometry, and a guess cannot tell you whether a fix
// worked. It is now two measurements of where the cloth actually ends up, one per character system:
//   tools/sleeve_check.mjs   the preview engine (engine/figure.js, run headless in node)
//   blender/check_sleeve.py  the character the films render (the deformed mesh, under Blender)
// A fix proved on one is not proved on the other, so library/promises.json runs both.

function checkCharacter() {
  // Which character system actually made each finished film. tools/film.mjs writes
  // output/<name>.render.json on every run, so this reads the pipeline's own output instead of
  // grepping the source for a promise. A film whose sidecar says `boxes` and is not marked as a
  // preview is the exact failure this ledger exists for.
  const dir = `${ROOT}output`;
  if (!fs.existsSync(dir)) { console.log('  nothing rendered yet — cannot check'); return true; }
  const side = fs.readdirSync(dir).filter((f) => f.endsWith('.render.json'));
  const mp4 = fs.readdirSync(dir).filter((f) => f.endsWith('.mp4') && !f.endsWith('-sound.mp4'));
  let bad = 0;
  for (const f of side) {
    const r = JSON.parse(fs.readFileSync(`${dir}/${f}`, 'utf8'));
    if (r.character !== 'modular' && !r.preview) { console.log(`  ${f}: rendered with ${r.character}, not marked a preview`); bad++; }
  }
  const unaccounted = mp4.filter((m) => !side.includes(m.replace(/\.mp4$/, '.render.json')));
  if (unaccounted.length) {
    // An mp4 with no sidecar predates this check or was made by hand. Say so rather than pass it.
    console.log(`  ${unaccounted.length} film(s) with no render record: ${unaccounted.join(', ')} — re-render with npm run film`);
    bad += unaccounted.length;
  }
  if (!bad) console.log(`  ${side.length} render record(s): every finished film used the modular paper character`);
  return bad === 0;
}

if (args.includes('--check-limits')) process.exit(checkLimits() ? 0 : 1);
if (args.includes('--check-character')) process.exit(checkCharacter() ? 0 : 1);

// ---------------------------------------------------------------- the ledger
const L = JSON.parse(fs.readFileSync(`${ROOT}library/promises.json`, 'utf8'));
const open = L.promises.filter((p) => p.status === 'OPEN');

if (args.includes('--open')) {
  console.log(`${open.length} promise(s) still owed:\n`);
  for (const p of open) console.log(`  ${p.id}\n    ${p.promise}\n    why: ${p.why}\n`);
  process.exit(0);
}

console.log(`PROMISES · ${L.promises.length} stated, ${open.length} still owed\n`);
let broken = 0;
for (const p of L.promises) {
  let ok = false, note = '';
  try { execSync(p.check, { cwd: ROOT, stdio: 'pipe' }); ok = true; }
  catch (e) { note = (e.stdout?.toString() || e.message).trim().split('\n').pop() ?? ''; }
  if (p.status === 'kept') {
    console.log(`  ${ok ? '✓' : '✗ REGRESSION'}  ${p.id}`);
    if (!ok) { broken++; console.log(`      ${p.promise}\n      ${note}`); }
  } else {
    console.log(`  ${ok ? '✓ now true (mark it kept)' : '…  owed'}  ${p.id}`);
    console.log(`      ${p.promise}`);
  }
}
console.log(`\n${broken ? `${broken} kept promise(s) have BROKEN — that is a regression` : 'no kept promise has broken'}`);
process.exit(broken ? 1 : 0);

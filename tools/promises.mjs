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
import { LIMITS } from '../engine/limits.js';
import { ledger } from '../packages/aethern/js/ledger.mjs';

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
  const side = new Set(fs.readdirSync(dir).filter((f) => f.endsWith('.render.json')).map((f) => f.replace(/\.render\.json$/, '')));
  let bad = 0;
  for (const base of side) {
    const r = JSON.parse(fs.readFileSync(`${dir}/${base}.render.json`, 'utf8'));
    if (r.character !== 'modular' && !r.preview) { console.log(`  ${base}: rendered with ${r.character}, not marked a preview`); bad++; }
  }
  // Only things that are FILMS count: a name in film/. output/ also holds turntables, galleries and
  // sound experiments, and calling those unrendered films would make this check noise, which is how
  // a check stops being read. Derived names (-final, -sound, -with-sound, -vertical…) answer to
  // their film's record, because they are that render with something added.
  const films = new Set(fs.readdirSync(`${ROOT}film`).filter((f) => f.endsWith('.json')).map((f) => f.replace(/\.json$/, '')));
  const stale = new Set();
  for (const m of fs.readdirSync(dir).filter((f) => f.endsWith('.mp4'))) {
    const name = m.replace(/\.mp4$/, '');
    const base = [...films].filter((f) => name === f || name.startsWith(f + '-')).sort((a, b) => b.length - a.length)[0];
    if (!base) continue;                       // not a film: a turntable, a gallery, a sound test
    if (!side.has(base)) stale.add(base);
  }
  if (stale.size) {
    console.log(`  ${stale.size} film(s) on disk with no render record — made before this check, with the box character:`);
    console.log(`    ${[...stale].sort().join(', ')}`);
    console.log('    re-render each with: bash tools/film.sh film/<name>.json');
    bad += stale.size;
  }
  if (!bad) console.log(`  ${side.size} render record(s): every finished film used the modular paper character`);
  return bad === 0;
}

if (args.includes('--check-limits')) process.exit(checkLimits() ? 0 : 1);
if (args.includes('--check-character')) process.exit(checkCharacter() ? 0 : 1);

// ---------------------------------------------------------------- the ledger
// The ledger runner is generic and lives in the shared core (packages/aethern/js/ledger.mjs);
// the two built-in checks above are Paper Cinema's own and stay here.
process.exit(ledger({ root: ROOT, file: 'library/promises.json', args }));

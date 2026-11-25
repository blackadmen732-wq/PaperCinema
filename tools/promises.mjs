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

function checkSleeveClearance() {
  // A raised arm must not bury the head. The sleeve hangs from the forearm, so when the shoulder
  // goes above horizontal the hem rises with it; this measures how far the arm is raised and
  // reports the worst frame. The real fix is for the sleeve to shorten or fold past shoulder
  // height — until then this stays OPEN and names the frame to look at.
  const files = fs.readdirSync(`${ROOT}output`).filter((f) => f.endsWith('.timeline.json'));
  if (!files.length) { console.log('  no timelines built yet — cannot check'); return false; }
  const RAISED = -1.2;                       // shoulder pitch past which the sleeve covers the head
  let worst = null, n = 0;
  for (const f of files) {
    const tl = JSON.parse(fs.readFileSync(`${ROOT}output/${f}`, 'utf8'));
    for (const fr of tl.frames ?? []) {
      for (const [aid, a] of Object.entries(fr.actors ?? {})) {
        for (const ch of ['rsx', 'lsx']) {
          const v = a.pose?.[ch];
          if (typeof v === 'number' && v < RAISED) { n++; if (!worst || v < worst.v) worst = { f, frame: fr.f, aid, ch, v }; }
        }
      }
    }
  }
  if (n) console.log(`  ${n} frame(s) raise an arm past ${RAISED} rad — worst ${worst.ch}=${worst.v.toFixed(2)} at ${worst.f} frame ${worst.frame}, ${worst.aid}`);
  else console.log('  no arm raised far enough to bury the head');
  return n === 0;
}

if (args.includes('--check-limits')) process.exit(checkLimits() ? 0 : 1);
if (args.includes('--check-sleeve-clearance')) process.exit(checkSleeveClearance() ? 0 : 1);

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

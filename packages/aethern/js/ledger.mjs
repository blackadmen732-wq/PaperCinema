// PROMISE LEDGER: every fix that was stated out loud, each with a command that proves it.
// Extracted from Paper Cinema's tools/promises.mjs (its film-specific checks stay there).
//
//   node ledger.mjs [--root DIR] [--file promises.json]      run every check; exit 1 if a KEPT promise broke
//   node ledger.mjs --open                                   list what is still owed
//
// Ledger: { "promises": [{ id, promise, why, status: "kept" | "OPEN", check: "<shell command, exit 0 = true>" }] }
// A `kept` promise whose check fails is a REGRESSION and fails the run. An OPEN one is a debt: reported, not an error.
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

export function ledger({ root, file = 'promises.json', args = [], log = console.log } = {}) {
  const ROOT = path.resolve(root ?? process.cwd());
  const L = JSON.parse(fs.readFileSync(path.join(ROOT, file), 'utf8'));
  const open = L.promises.filter((p) => p.status === 'OPEN');
  if (args.includes('--open')) {
    log(`${open.length} promise(s) still owed:\n`);
    for (const p of open) log(`  ${p.id}\n    ${p.promise}\n    why: ${p.why}\n`);
    return 0;
  }
  log(`PROMISES · ${L.promises.length} stated, ${open.length} still owed\n`);
  let broken = 0;
  for (const p of L.promises) {
    let ok = false, note = '';
    try { execSync(p.check, { cwd: ROOT, stdio: 'pipe' }); ok = true; }
    catch (e) { note = (e.stdout?.toString() || e.message).trim().split('\n').pop() ?? ''; }
    if (p.status === 'kept') {
      log(`  ${ok ? '✓' : '✗ REGRESSION'}  ${p.id}`);
      if (!ok) { broken++; log(`      ${p.promise}\n      ${note}`); }
    } else {
      log(`  ${ok ? '✓ now true (mark it kept)' : '…  owed'}  ${p.id}`);
      log(`      ${p.promise}`);
    }
  }
  log(`\n${broken ? `${broken} kept promise(s) have BROKEN — that is a regression` : 'no kept promise has broken'}`);
  return broken ? 1 : 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const a = process.argv.slice(2);
  const take = (n) => { const i = a.indexOf(n); if (i < 0) return undefined; const v = a[i + 1]; a.splice(i, 2); return v; };
  const root = take('--root'), file = take('--file');
  process.exit(ledger({ root, ...(file && { file }), args: a }));
}

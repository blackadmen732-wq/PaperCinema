#!/usr/bin/env node
// VENDOR: fetch every outside tool this project uses, at the exact commit vendor/MANIFEST.json names.
//
//   node tools/vendor.mjs              # fetch everything that is missing
//   node tools/vendor.mjs --check      # report only: present? right commit? right licence?
//   node tools/vendor.mjs agent-reach  # one tool by id
//   node tools/vendor.mjs --list       # what each tool is for, and which skill explains it
//
// Why the trees are not committed. HyperFrames alone is 344 MB of docs and test fixtures; five tools
// committed whole would make this repository slower to clone than the tools are to fetch, and a
// repository nobody can clone is not a tool anybody can use. The commit hash is the contract: the
// same hash gives the same bytes on any machine, for any agent, today or in a year. The clone is a
// cache, and `--check` proves the cache matches the contract.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const VENDOR = path.join(ROOT, 'vendor');
const M = JSON.parse(fs.readFileSync(path.join(VENDOR, 'MANIFEST.json'), 'utf8'));
const args = process.argv.slice(2);
const only = args.filter((a) => !a.startsWith('--'));
const tools = only.length ? M.tools.filter((t) => only.includes(t.id)) : M.tools;
if (only.length && !tools.length) {
  console.error(`unknown tool id. known: ${M.tools.map((t) => t.id).join(', ')}`);
  process.exit(2);
}

const git = (a, cwd = VENDOR) => execFileSync('git', a, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
const dirOf = (t) => path.join(VENDOR, t.id);

if (args.includes('--list')) {
  for (const t of M.tools) {
    console.log(`\n${t.id}  (${t.licence}, ${t.size})`);
    console.log(`  ${t.what}`);
    console.log(`  here because: ${t.why_here}`);
    console.log(`  how to use it: ${t.skill}`);
    if (t.needs_gpu) console.log('  needs a GPU');
    if (t.needs_gui) console.log('  needs a Blender window open (not this headless container)');
  }
  for (const r of M.rejected ?? []) console.log(`\n${r.name}  NOT VENDORED\n  ${r.why}`);
  process.exit(0);
}

if (args.includes('--check')) {
  let bad = 0;
  for (const t of tools) {
    const d = dirOf(t);
    if (!fs.existsSync(d)) { console.log(`  missing   ${t.id}  — run: node tools/vendor.mjs ${t.id}`); bad++; continue; }
    let head = '';
    try { head = git(['rev-parse', 'HEAD'], d); } catch { console.log(`  not a git checkout  ${t.id}`); bad++; continue; }
    const lic = fs.readdirSync(d).find((f) => /^LICEN[CS]E/i.test(f));
    const text = lic ? fs.readFileSync(path.join(d, lic), 'utf8').slice(0, 400) : '';
    const claimed = t.licence.toLowerCase().startsWith('apache') ? /apache license/i : new RegExp(`${t.licence} license`, 'i');
    const licOk = claimed.test(text);
    const ok = head === t.commit && licOk;
    console.log(`  ${ok ? 'ok       ' : 'MISMATCH '} ${t.id}  ${head.slice(0, 10)}${head === t.commit ? '' : ` (want ${t.commit.slice(0, 10)})`}${licOk ? '' : `  LICENCE does not read as ${t.licence}`}`);
    if (!ok) bad++;
  }
  console.log(bad ? `\n${bad} tool(s) not as pinned` : '\nevery tool present at its pinned commit, licence as claimed');
  process.exit(bad ? 1 : 0);
}

fs.mkdirSync(VENDOR, { recursive: true });
let failed = 0;
for (const t of tools) {
  const d = dirOf(t);
  if (fs.existsSync(d)) {
    let head = '';
    try { head = git(['rev-parse', 'HEAD'], d); } catch { /* not a checkout */ }
    if (head === t.commit) { console.log(`  have   ${t.id}`); continue; }
    console.log(`  ${head ? 'wrong commit' : 'not a checkout'}: ${t.id} — delete vendor/${t.id} and run again`);
    failed++;
    continue;
  }
  console.log(`  fetch  ${t.id}  (${t.size}, ${t.licence})`);
  try {
    // A shallow clone cannot check out an arbitrary commit, so fetch that one commit by hash.
    git(['init', '-q', t.id]);
    git(['remote', 'add', 'origin', t.url], d);
    execFileSync('git', ['fetch', '-q', '--depth', '1', 'origin', t.commit],
      { cwd: d, stdio: 'inherit', env: { ...process.env, GIT_LFS_SKIP_SMUDGE: '1' } });
    git(['checkout', '-q', 'FETCH_HEAD'], d);
    console.log(`         at ${t.commit.slice(0, 10)}`);
  } catch (e) {
    console.log(`  FAILED ${t.id}: ${(e.stderr?.toString() || e.message).trim().split('\n').pop()}`);
    fs.rmSync(d, { recursive: true, force: true });
    failed++;
  }
}
console.log(failed ? `\n${failed} tool(s) could not be fetched` : '\nall tools present — node tools/vendor.mjs --check to verify');
process.exit(failed ? 1 : 0);

// VENDOR: fetch every outside tool a project uses, at the exact commit its manifest names.
// Extracted from Paper Cinema's tools/vendor.mjs; the root, manifest and command name are parameters.
//
//   node vendor.mjs [--root DIR] [--manifest vendor/MANIFEST.json]           fetch everything missing
//   ... --check      report only: present? right commit? right licence?
//   ... <id>         one tool by id
//   ... --list       what each tool is for, and which skill explains it
//
// Manifest: { "tools": [{ id, url, commit, licence, size, what, why_here, skill, needs_gpu?, needs_gui? }],
//             "rejected": [{ name, why }] }
// The commit hash is the contract: the same hash gives the same bytes on any machine. The clone is a cache.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

/** returns the exit code; prints what a person or agent needs, nothing more */
export function vendor({ root, manifest = 'vendor/MANIFEST.json', dir = 'vendor', args = [], cmd = 'aethern vendor', guiNote = 'needs a desktop window open (not a headless machine)', log = console.log } = {}) {
  const ROOT = path.resolve(root ?? process.cwd());
  const VENDOR = path.join(ROOT, dir);
  const M = JSON.parse(fs.readFileSync(path.join(ROOT, manifest), 'utf8'));
  const only = args.filter((a) => !a.startsWith('--'));
  const tools = only.length ? M.tools.filter((t) => only.includes(t.id)) : M.tools;
  if (only.length && !tools.length) {
    console.error(`unknown tool id. known: ${M.tools.map((t) => t.id).join(', ')}`);
    return 2;
  }
  const git = (a, cwd = VENDOR) => execFileSync('git', a, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
  const dirOf = (t) => path.join(VENDOR, t.id);

  if (args.includes('--list')) {
    for (const t of M.tools) {
      log(`\n${t.id}  (${t.licence}, ${t.size})`);
      log(`  ${t.what}`);
      log(`  here because: ${t.why_here}`);
      log(`  how to use it: ${t.skill}`);
      if (t.needs_gpu) log('  needs a GPU');
      if (t.needs_gui) log(`  ${guiNote}`);
    }
    for (const r of M.rejected ?? []) log(`\n${r.name}  NOT VENDORED\n  ${r.why}`);
    return 0;
  }

  if (args.includes('--check')) {
    let bad = 0;
    for (const t of tools) {
      const d = dirOf(t);
      if (!fs.existsSync(d)) { log(`  missing   ${t.id}  — run: ${cmd} ${t.id}`); bad++; continue; }
      let head = '';
      try { head = git(['rev-parse', 'HEAD'], d); } catch { log(`  not a git checkout  ${t.id}`); bad++; continue; }
      const lic = fs.readdirSync(d).find((f) => /^LICEN[CS]E/i.test(f));
      const text = lic ? fs.readFileSync(path.join(d, lic), 'utf8').slice(0, 400) : '';
      const claimed = t.licence.toLowerCase().startsWith('apache') ? /apache license/i : new RegExp(`${t.licence} license`, 'i');
      const licOk = claimed.test(text);
      const ok = head === t.commit && licOk;
      log(`  ${ok ? 'ok       ' : 'MISMATCH '} ${t.id}  ${head.slice(0, 10)}${head === t.commit ? '' : ` (want ${t.commit.slice(0, 10)})`}${licOk ? '' : `  LICENCE does not read as ${t.licence}`}`);
      if (!ok) bad++;
    }
    log(bad ? `\n${bad} tool(s) not as pinned` : '\nevery tool present at its pinned commit, licence as claimed');
    return bad ? 1 : 0;
  }

  fs.mkdirSync(VENDOR, { recursive: true });
  let failed = 0;
  for (const t of tools) {
    const d = dirOf(t);
    if (fs.existsSync(d)) {
      let head = '';
      try { head = git(['rev-parse', 'HEAD'], d); } catch { /* not a checkout */ }
      if (head === t.commit) { log(`  have   ${t.id}`); continue; }
      log(`  ${head ? 'wrong commit' : 'not a checkout'}: ${t.id} — delete ${dir}/${t.id} and run again`);
      failed++;
      continue;
    }
    log(`  fetch  ${t.id}  (${t.size}, ${t.licence})`);
    try {
      // A shallow clone cannot check out an arbitrary commit, so fetch that one commit by hash.
      git(['init', '-q', t.id]);
      git(['remote', 'add', 'origin', t.url], d);
      execFileSync('git', ['fetch', '-q', '--depth', '1', 'origin', t.commit],
        { cwd: d, stdio: 'inherit', env: { ...process.env, GIT_LFS_SKIP_SMUDGE: '1' } });
      git(['checkout', '-q', 'FETCH_HEAD'], d);
      log(`         at ${t.commit.slice(0, 10)}`);
    } catch (e) {
      log(`  FAILED ${t.id}: ${(e.stderr?.toString() || e.message).trim().split('\n').pop()}`);
      fs.rmSync(d, { recursive: true, force: true });
      failed++;
    }
  }
  log(failed ? `\n${failed} tool(s) could not be fetched` : `\nall tools present — ${cmd} --check to verify`);
  return failed ? 1 : 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const a = process.argv.slice(2);
  const take = (n) => { const i = a.indexOf(n); if (i < 0) return undefined; const v = a[i + 1]; a.splice(i, 2); return v; };
  const root = take('--root'), manifest = take('--manifest'), dir = take('--dir');
  process.exit(vendor({ root, ...(manifest && { manifest }), ...(dir && { dir }), args: a }));
}

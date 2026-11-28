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
//
// The fetcher lives in the shared core (packages/aethern/js/vendor.mjs); this keeps the command.
import path from 'node:path';
import { vendor } from '../packages/aethern/js/vendor.mjs';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
process.exit(vendor({ root: ROOT, manifest: 'vendor/MANIFEST.json', dir: 'vendor', args: process.argv.slice(2), cmd: 'node tools/vendor.mjs', guiNote: 'needs a Blender window open (not this headless container)' }));

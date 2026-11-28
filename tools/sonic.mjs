#!/usr/bin/env node
// SONIC command line: the sound catalog, queried instead of read. Guide: docs/SONIC.md.
//
//   node tools/sonic.mjs scan [--fresh] [--root dir]...     measure new/changed sounds, re-tag all → assets/sfx/sonic.catalog.json
//   node tools/sonic.mjs query material=steel action=impact dur<0.5 [--sort weight] [--limit 5] [--json]
//   node tools/sonic.mjs pick clash material=steel intensity=0.8 [--n 4]   what an engine event would get (and the runners-up)
//   node tools/sonic.mjs show <id> [--json]                  one sound, every attribute
//   node tools/sonic.mjs tag <id> material=wood weight=0.3   hand edit (kept in assets/sfx/sonic.tags.json, survives every scan)
//   node tools/sonic.mjs untag <id> [facet]                  drop a hand edit
//   node tools/sonic.mjs stats                               counts per facet value: what the library has and lacks
//   node tools/sonic.mjs schema                              the record format, for a program or an agent
//
// Output is short on purpose (one line per sound). --json gives full records for programs.
// Options: --catalog <file> --vocab <file> --overrides <file> --credits <file> (defaults in engine/sonic.mjs).
import fs from 'node:fs';
import { scan, loadCatalog, query, pick, brief, parseQuery, DEFAULTS, SCHEMA, ANALYZER } from '../engine/sonic.mjs';

const argv = process.argv.slice(2);
const flags = {}, pos = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a.startsWith('--')) {
    const k = a.slice(2), nxt = argv[i + 1];
    if (['json', 'fresh'].includes(k)) flags[k] = true;
    else if (k === 'root') (flags.roots ??= []).push(argv[++i]);
    else { flags[k] = nxt; i++; }
  } else pos.push(a);
}
const cfg = { ...DEFAULTS };
for (const k of ['catalog', 'vocab', 'overrides', 'credits']) if (flags[k]) cfg[k] = flags[k];
if (flags.roots) cfg.roots = flags.roots;
const [cmd, ...rest] = pos;
const out = (x) => process.stdout.write((typeof x === 'string' ? x : JSON.stringify(x, null, flags.json === true ? 0 : 1)) + '\n');
const readJSON = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

try {
  if (cmd === 'scan') {
    const { stats } = scan({ ...cfg, fresh: flags.fresh });
    out(`${stats.files} sounds → ${cfg.catalog} (${stats.measured} measured, ${stats.cached} from cache) in ${stats.ms} ms` +
      Object.entries(stats.banks).map(([b, v]) => v.available ? `\n  bank ${b} ${v.version}: ${v.count} sounds` : `\n  bank ${b}: tool not installed, kept ${v.kept} earlier records`).join(''));
  } else if (cmd === 'query' || cmd === 'q') {
    const cat = loadCatalog(cfg.catalog);
    const hits = query(cat, rest, { sort: flags.sort, limit: flags.limit ? +flags.limit : 10 });
    const total = query(cat, rest).length;
    if (flags.json) out(hits);
    else out(hits.length ? hits.map(brief).join('\n') + (total > hits.length ? `\n… ${total - hits.length} more (--limit)` : '') : 'no match');
  } else if (cmd === 'pick') {
    const [kind, ...kv] = rest;
    const cat = loadCatalog(cfg.catalog), vocab = readJSON(cfg.vocab, {});
    if (!vocab.events?.[kind]) throw new Error(`unknown event kind "${kind}" (vocab has: ${Object.keys(vocab.events ?? {}).join(', ')})`);
    const ev = { kind };
    for (const t of parseQuery(kv)) ev[t.key] = Number.isFinite(+t.val) ? +t.val : t.val;
    const state = { recent: {} }, n = +(flags.n ?? 1), rows = [];
    for (let i = 0; i < n; i++) { const r = pick(cat, vocab, { ...ev, seed: `${flags.seed ?? 'cli'}:${i}` }, state); if (r) rows.push(r); }
    if (!rows.length) out('no sound fits this event (the engine would keep its own sound)');
    else if (flags.json) out(rows.map((r) => ({ id: r.sound.id, file: r.sound.file, score: r.score, of: r.alternatives, why: r.why })));
    else out(rows.map((r) => `${brief(r.sound)}  score ${r.score} (1 of ${r.alternatives})${r.fallback ? `  fallback: ${r.fallback}` : ''}`).join('\n'));
  } else if (cmd === 'show') {
    const s = loadCatalog(cfg.catalog).sounds.find((x) => x.id === rest[0]);
    if (!s) throw new Error(`no sound "${rest[0]}" (try: node tools/sonic.mjs query id~${rest[0] ?? ''})`);
    out(flags.json ? s : `${brief(s)}\n${s.file} · ${s.source} · ${s.license ?? 'licence unknown'}${s.edited ? ' · hand-edited' : ''}\n` +
      Object.entries(s.m).map(([k, v]) => `${k}=${v}`).join(' ') + '\n' + Object.entries(s.tags).map(([k, v]) => `${k}: ${v.join(', ') || '-'}`).join('\n'));
  } else if (cmd === 'tag' || cmd === 'untag') {
    const [id, ...kv] = rest;
    const cat = loadCatalog(cfg.catalog);
    if (!cat.sounds.some((s) => s.id === id)) throw new Error(`no sound "${id}"`);
    const ov = readJSON(cfg.overrides, {});
    if (cmd === 'untag') { if (kv.length) for (const k of kv) delete ov[id]?.[k]; else delete ov[id]; if (ov[id] && !Object.keys(ov[id]).length) delete ov[id]; }
    else for (const t of parseQuery(kv)) (ov[id] ??= {})[t.key] = Number.isFinite(+t.val) ? +t.val : t.val.split(',');
    fs.writeFileSync(cfg.overrides, JSON.stringify(ov, null, 1) + '\n');
    scan(cfg);
    out(brief(loadCatalog(cfg.catalog).sounds.find((s) => s.id === id)));
  } else if (cmd === 'stats') {
    const cat = loadCatalog(cfg.catalog), c = {};
    for (const s of cat.sounds) for (const [f, vs] of Object.entries(s.tags)) for (const v of vs) ((c[f] ??= {})[v] = (c[f][v] ?? 0) + 1);
    out(flags.json ? c : `${cat.count} sounds\n` + Object.entries(c).map(([f, vs]) => `${f}: ` + Object.entries(vs).sort((a, b) => b[1] - a[1]).map(([v, n]) => `${v} ${n}`).join(', ')).join('\n'));
  } else if (cmd === 'schema') {
    out({ schema: SCHEMA, analyzer: ANALYZER, record: {
      id: 'path under its root, no extension', file: 'path from the repo root', hash: 'sha1 of the bytes (16 hex): the cache key',
      source: 'local | synth | earshot | <credits source>', license: 'from credits.json', edited: 'true when sonic.tags.json changes it',
      m: { dur: 's', peakDb: 'dBFS', rmsDb: 'dBFS', crest: 'dB', peakT: 's to the loudest 10 ms', attack: 's from -20 dB to peak', decay: 's from peak to -20 dB',
        centroid: 'Hz', low: 'energy share < 250 Hz', high: 'energy share > 4 kHz', zcr: 'zero crossings per sample', flatness: '0 tonal … 1 noise',
        brightness: '0..1', weight: '0..1', intensity: '0..1', sharpness: '0..1 (fast attack)', tonal: '0..1' },
      tags: { material: [], action: [], environment: [], intent: [], texture: [], size: ['light|medium|heavy'] } },
      query: 'key=value key!=value key>n key<n key>=n key<=n key~text; a|b means either', events: 'vocab.events (library/sonic-vocab.json)' });
  } else {
    out(fs.readFileSync(new URL(import.meta.url), 'utf8').split('\n').filter((l) => l.startsWith('//')).slice(0, 16).map((l) => l.slice(3)).join('\n'));
    process.exit(cmd ? 2 : 0);
  }
} catch (e) { console.error(`✗ ${e.message}`); process.exit(1); }

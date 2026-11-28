#!/usr/bin/env node
// Sonic's own command line, with no host app. Paths default to the working directory (see DEFAULTS in sonic.mjs).
//   node packages/sonic/cli.mjs scan [--roots sfx,more] [--catalog F]        measure + tag every sound, write the catalog
//   node packages/sonic/cli.mjs pick EVENTS.jsonl [--catalog F] [--out F]    aethern-event/1 in, "sonic.pick" events out
//   node packages/sonic/cli.mjs query material=steel action=impact dur<0.5 [--catalog F]
//   node packages/sonic/cli.mjs footsteps STEPS.jsonl [--surface sand] [--footwear bare] [--weight 70] [--room open] [--out F]
//        foot-contact events in, one synthesized step each (wavs in the cache), sonic.step events out
import fs from 'node:fs';
import { configure, scan, loadCatalog, query, brief, pickForEvents } from './sonic.mjs';
import { footstepCues, stepEvents } from './foley.mjs';

const argv = process.argv.slice(2);
const opt = (k) => { const i = argv.indexOf(`--${k}`); if (i < 0) return undefined; const v = argv[i + 1]; argv.splice(i, 2); return v; };
const surface = opt('surface'), footwear = opt('footwear'), weight = opt('weight'), room = opt('room');
const out = opt('out'), seed = opt('seed'), roots = opt('roots'), catalog = opt('catalog'), vocab = opt('vocab'), cache = opt('cache'), project = opt('project'), media = opt('media');
configure({ ...(catalog ? { catalog } : {}), ...(vocab ? { vocab } : {}), ...(cache ? { cache } : {}), ...(roots ? { roots: roots.split(',') } : {}) });
const [cmd, ...rest] = argv;
const readEvents = (f) => fs.readFileSync(f, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));

if (cmd === 'scan') {
  const { stats } = scan();
  console.log(JSON.stringify(stats));
} else if (cmd === 'pick' && rest[0]) {
  const { events, picks } = pickForEvents(readEvents(rest[0]), { seed, project, media });
  const text = events.map((e) => JSON.stringify(e)).join('\n') + (events.length ? '\n' : '');
  if (out) fs.writeFileSync(out, text); else process.stdout.write(text);
  console.error(`sonic: ${events.length} of ${picks.length} events got a sound`);
} else if (cmd === 'footsteps' && rest[0]) {
  const evs = readEvents(rest[0]).filter((e) => /footstep|foot-ground/.test(e.type));
  const { cues, skipped } = footstepCues(evs, { surface, footwear, weight: weight ? +weight : undefined, room, seed, cache: cache ? `${cache}/foley` : undefined });
  const lines = stepEvents(cues, project ?? evs.find((e) => e.project)?.project ?? 'unknown', media ?? evs.find((e) => e.media)?.media ?? 'unknown');
  const text = lines.map((e) => JSON.stringify(e)).join('\n') + (lines.length ? '\n' : '');
  if (out) fs.writeFileSync(out, text); else process.stdout.write(text);
  console.error(`sonic: ${cues.length} step(s) from ${evs.length} foot contact(s), ${skipped.length} merged or left to another cue`);
} else if (cmd === 'query') {
  for (const s of query(loadCatalog(), rest.join(' '))) console.log(brief(s));
} else {
  console.error('usage: cli.mjs scan | footsteps STEPS.jsonl | pick EVENTS.jsonl [--out F] [--project P --media M] | query WORDS   [--catalog F] [--roots a,b] [--vocab F] [--cache D]');
  process.exit(2);
}

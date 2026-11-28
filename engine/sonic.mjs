// SONIC for Paper Cinema: the adapter between this app and the standalone Sonic package (packages/sonic).
// Sonic itself lives in packages/sonic/sonic.mjs and imports nothing from Paper Cinema, so it can move to the
// CINEVORA package as is. This file does the two Paper Cinema parts:
//   1. points Sonic at Paper Cinema's files (assets/sfx, library/sonic-vocab.json, .cache/sonic);
//   2. reads Paper Cinema's older cues, whose event is only in the cue id and "why" text (eventOfCue below).
// Every importer keeps using this path and these names, so Paper Cinema behaves exactly as before.
// Guide and schema: docs/SONIC.md, packages/sonic/README.md.
import * as core from '../packages/sonic/sonic.mjs';

core.configure({
  roots: ['assets/sfx'],
  catalog: 'assets/sfx/sonic.catalog.json',
  overrides: 'assets/sfx/sonic.tags.json',
  credits: 'assets/sfx/credits.json',
  vocab: 'library/sonic-vocab.json',
  banks: ['earshot'],
  cache: '.cache/sonic',
});

export const { ANALYZER, SCHEMA, DEFAULTS, measure, tagsFor, bankFile, scan, loadCatalog, parseQuery, query, brief, pick,
  sharedEvents, localStandIn, pickForEvents, configure } = core;

/**
 * The event a cue stands for. New events files carry cue.event (engine/combat.js, engine/groundfx.js); older ones
 * are read back from the cue's id, gain and "why" text, so every events file already written works too.
 */
export function eventOfCue(c) {
  if (c.event) return c.event;
  const id = c.id ?? '', why = c.why ?? '';
  const num = (re) => { const m = why.match(re); return m ? +m[1] : undefined; };
  if (/^auto-whoosh-/.test(id)) return { kind: 'whoosh', speed: num(/tip ([\d.]+) m\/s/), peakAt: c.earshot ? c.t : +(c.t + 0.06).toFixed(3) };
  if (/^auto-clash-\d+$/.test(id)) return { kind: 'clash', material: /wood/.test(why) ? 'wood' : 'steel', intensity: num(/intensity ([\d.]+)/), peakAt: c.t };
  if (/^auto-scrape-/.test(id)) return { kind: 'scrape', material: /wood|clap/.test(c.sfx ?? '') ? 'wood' : 'steel', dur: c.len };
  const g = id.match(/^auto-(dash|skid|takeoff|land)-/);
  if (g) return { kind: g[1], speed: num(/\(([\d.]+) m\/s\)/) };
  return null;
}

/** Sonic's applyToCues, reading Paper Cinema's cues (older ids included) with eventOfCue. */
export function applyToCues(cues, o = {}) {
  return core.applyToCues(cues, { eventOf: eventOfCue, ...o });
}

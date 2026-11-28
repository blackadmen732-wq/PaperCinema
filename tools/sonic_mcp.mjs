#!/usr/bin/env node
// SONIC over MCP: the sound catalog as four small tools any MCP client (Claude Code, other agents) can call.
// No dependencies: MCP's stdio transport is newline-delimited JSON-RPC 2.0, answered here by hand.
//   registered for Claude Code in .mcp.json; by hand:  node tools/sonic_mcp.mjs   (run from the repo root)
// Answers are one line per sound, the same as the CLI (docs/SONIC.md), so a query costs tens of tokens, not a file.
// Tool descriptions are kept short on purpose: every connected client pays for them in every request.
import readline from 'node:readline';
import { loadCatalog, query, pick, brief, parseQuery, scan, DEFAULTS } from '../engine/sonic.mjs';
import fs from 'node:fs';

const vocab = () => JSON.parse(fs.readFileSync(DEFAULTS.vocab, 'utf8'));
const TOOLS = [
  { name: 'sonic_query', description: 'Find sounds. q: space-separated terms key=value key!=value key>n key<n key~text (a|b = either). Keys: material action texture size intent source id; dur weight intensity brightness sharpness tonal peakT. One line per sound: id dur w=weight i=intensity b=brightness [tags].',
    inputSchema: { type: 'object', properties: { q: { type: 'string' }, sort: { type: 'string', description: 'attribute, high first; -attr low first' }, limit: { type: 'integer' } }, required: ['q'] } },
  { name: 'sonic_pick', description: 'The sound an engine event gets. kind: whoosh clash scrape dash skid takeoff land tear fold. Optional: material intensity(0-1) speed(m/s) height(m) dur(s); n = also show the next picks.',
    inputSchema: { type: 'object', properties: { kind: { type: 'string' }, material: { type: 'string' }, intensity: { type: 'number' }, speed: { type: 'number' }, height: { type: 'number' }, dur: { type: 'number' }, n: { type: 'integer' } }, required: ['kind'] } },
  { name: 'sonic_show', description: 'Every measured attribute and tag of one sound id.',
    inputSchema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] } },
  { name: 'sonic_stats', description: 'How many sounds per tag (what the library has and lacks), or re-scan with rescan=true.',
    inputSchema: { type: 'object', properties: { rescan: { type: 'boolean' } } } },
];

function call(name, a = {}) {
  if (name === 'sonic_query') {
    const cat = loadCatalog(), all = query(cat, a.q), hits = query(cat, a.q, { sort: a.sort, limit: a.limit ?? 8 });
    return hits.length ? hits.map(brief).join('\n') + (all.length > hits.length ? `\n+${all.length - hits.length} more` : '') : 'no match';
  }
  if (name === 'sonic_pick') {
    const { n = 1, ...ev } = a, v = vocab();
    if (!v.events?.[ev.kind]) return `unknown kind; known: ${Object.keys(v.events ?? {}).join(' ')}`;
    const cat = loadCatalog(), state = { recent: {} }, rows = [];
    for (let i = 0; i < Math.min(8, n); i++) { const r = pick(cat, v, { ...ev, seed: `mcp:${i}` }, state); if (r) rows.push(`${brief(r.sound)} score ${r.score}${r.fallback ? ` fallback ${r.fallback}` : ''}`); }
    return rows.join('\n') || 'no sound fits (the engine keeps its own sound)';
  }
  if (name === 'sonic_show') {
    const s = loadCatalog().sounds.find((x) => x.id === a.id);
    if (!s) return `no sound "${a.id}"`;
    return `${brief(s)}\n${s.file ?? `bank ${s.bank}:${s.earshot}`} ${s.source} ${s.license ?? ''}\n` + Object.entries(s.m).map(([k, v]) => `${k}=${v}`).join(' ') + '\n' +
      Object.entries(s.tags).filter(([, v]) => v.length).map(([k, v]) => `${k}:${v.join(',')}`).join(' ');
  }
  if (name === 'sonic_stats') {
    if (a.rescan) { const { stats } = scan({}); return `${stats.files} sounds (${stats.measured} measured, ${stats.cached} cached) ${stats.ms} ms`; }
    const cat = loadCatalog(), c = {};
    for (const s of cat.sounds) for (const [f, vs] of Object.entries(s.tags)) for (const v of vs) ((c[f] ??= {})[v] = (c[f][v] ?? 0) + 1);
    return `${cat.count} sounds\n` + Object.entries(c).map(([f, vs]) => `${f}: ` + Object.entries(vs).sort((x, y) => y[1] - x[1]).map(([v, k]) => `${v} ${k}`).join(', ')).join('\n');
  }
  throw new Error(`unknown tool ${name}`);
}

const send = (m) => process.stdout.write(JSON.stringify(m) + '\n');
readline.createInterface({ input: process.stdin }).on('line', (line) => {
  if (!line.trim()) return;
  let msg; try { msg = JSON.parse(line); } catch { return send({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'parse error' } }); }
  const { id, method, params = {} } = msg;
  if (id === undefined) return;                                   // notifications (initialized, cancelled): nothing to answer
  try {
    if (method === 'initialize') return send({ jsonrpc: '2.0', id, result: { protocolVersion: params.protocolVersion ?? '2025-06-18', capabilities: { tools: {} }, serverInfo: { name: 'sonic', version: '1.0.0' } } });
    if (method === 'ping') return send({ jsonrpc: '2.0', id, result: {} });
    if (method === 'tools/list') return send({ jsonrpc: '2.0', id, result: { tools: TOOLS } });
    if (method === 'tools/call') {
      try { return send({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: call(params.name, params.arguments) }] } }); }
      catch (e) { return send({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: e.message }], isError: true } }); }
    }
    send({ jsonrpc: '2.0', id, error: { code: -32601, message: `method not found: ${method}` } });
  } catch (e) { send({ jsonrpc: '2.0', id, error: { code: -32603, message: e.message } }); }
});

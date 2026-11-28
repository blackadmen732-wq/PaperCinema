// SONIC: the sound catalog ("SonicGraph" v1). Every sound file becomes one record of MEASURED attributes
// (from its audio) and SEMANTIC tags (from its name, credits and a vocabulary file), so a program or an
// AI agent can ask for "a heavy steel impact under 0.5 s" in one call instead of opening files.
//
//   import { scan, loadCatalog, query, pick } from './sonic.mjs'
//   CLI: node tools/sonic.mjs scan | query material=steel action=impact dur<0.5 | pick clash intensity=0.8
//
// Generic by design: nothing here knows about swords or Paper Cinema. The words, the event kinds and how an
// event maps to a sound all live in a vocabulary JSON (library/sonic-vocab.json by default). Local only:
// ffmpeg decodes, plain JS measures, no network, no AI calls. A content-hash cache means a file whose bytes
// did not change is never decoded again. Guide and schema: docs/SONIC.md.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';

export const ANALYZER = 'sonic-analyzer/1';          // bump when the measurements change: the cache re-measures
export const SCHEMA = 'sonic-catalog/1';
export const DEFAULTS = {
  roots: ['assets/sfx'],
  catalog: 'assets/sfx/sonic.catalog.json',
  overrides: 'assets/sfx/sonic.tags.json',
  credits: 'assets/sfx/credits.json',
  vocab: 'library/sonic-vocab.json',
};
const AUDIO = /\.(mp3|wav|ogg|flac|m4a|aac|opus)$/i;
const SR = 22050;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const r3 = (x) => +(+x).toFixed(3);
const readJSON = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

// ---------- MEASURE: decode once, measure envelope + spectrum ----------
function decode(file) {
  const r = spawnSync('ffmpeg', ['-v', 'error', '-i', file, '-ac', '1', '-ar', String(SR), '-f', 'f32le', '-'], { maxBuffer: 1 << 30 });
  if (r.status !== 0) throw new Error(`ffmpeg could not decode ${file}: ${String(r.stderr).slice(0, 160)}`);
  const b = r.stdout;
  return new Float32Array(b.buffer, b.byteOffset, Math.floor(b.length / 4));
}
function fft(re, im) {                                // in-place radix-2
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit;
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const a = -2 * Math.PI / len, wr = Math.cos(a), wi = Math.sin(a);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let k = 0; k < len / 2; k++) {
        const ur = re[i + k], ui = im[i + k], j = i + k + len / 2;
        const vr = re[j] * cr - im[j] * ci, vi = re[j] * ci + im[j] * cr;
        re[i + k] = ur + vr; im[i + k] = ui + vi; re[j] = ur - vr; im[j] = ui - vi;
        const t = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = t;
      }
    }
  }
}
const db = (x) => 20 * Math.log10(x + 1e-9);

/** Measured attributes of one audio file. Deterministic: the same bytes give the same numbers. */
export function measure(file) {
  const x = decode(file), n = x.length, dur = n / SR;
  if (!n) return { dur: 0, silent: true };
  let pk = 0, ss = 0, zc = 0;
  for (let i = 0; i < n; i++) { const a = Math.abs(x[i]); if (a > pk) pk = a; ss += x[i] * x[i]; if (i && (x[i] >= 0) !== (x[i - 1] >= 0)) zc++; }
  // 10 ms RMS envelope
  const H = Math.round(SR / 100), env = [];
  for (let i = 0; i < n; i += H) { let s = 0; const e = Math.min(n, i + H); for (let j = i; j < e; j++) s += x[j] * x[j]; env.push(Math.sqrt(s / (e - i))); }
  let pi = 0; env.forEach((v, i) => { if (v > env[pi]) pi = i; });
  const peakEnv = env[pi], thr = peakEnv * 0.1;          // -20 dB below the loudest 10 ms
  let a0 = pi; while (a0 > 0 && env[a0 - 1] > thr) a0--;
  let d1 = pi; while (d1 < env.length - 1 && env[d1 + 1] > thr) d1++;
  // spectrum: 2048-point frames, energy-weighted average over the first 20 s
  const N = 2048, hop = 1024, lim = Math.min(n, 20 * SR), win = new Float32Array(N).map((_, i) => 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (N - 1)));
  const avg = new Float64Array(N / 2); let wsum = 0, flatSum = 0, flatW = 0;
  const re = new Float64Array(N), im = new Float64Array(N);
  for (let s = 0; s + N <= lim || (s === 0 && lim < N); s += hop) {
    let e = 0;
    for (let i = 0; i < N; i++) { const v = (x[s + i] ?? 0) * win[i]; re[i] = v; im[i] = 0; e += v * v; }
    if (e < 1e-7) { if (s + N > lim) break; continue; }
    fft(re, im);
    let lg = 0, ar = 0;
    for (let k = 1; k < N / 2; k++) { const p = re[k] * re[k] + im[k] * im[k]; avg[k] += p; lg += Math.log(p + 1e-12); ar += p; }
    const m = N / 2 - 1; flatSum += e * Math.exp(lg / m) / (ar / m + 1e-12); flatW += e; wsum += e;
    if (s + N > lim) break;
  }
  const hz = (k) => k * SR / N;
  let tot = 0, cen = 0, low = 0, high = 0;
  for (let k = 1; k < N / 2; k++) { const p = avg[k]; tot += p; cen += p * hz(k); if (hz(k) < 250) low += p; if (hz(k) > 4000) high += p; }
  const centroid = tot ? cen / tot : 0;
  const rmsDb = db(Math.sqrt(ss / n)), peakDb = db(pk), crest = peakDb - rmsDb;
  const flatness = flatW ? flatSum / flatW : 1;
  const attack = (pi - a0) / 100, decay = (d1 - pi) / 100;
  let as = 0; for (let i = a0; i <= d1; i++) as += env[i] * env[i];
  const bodyDb = db(Math.sqrt(as / (d1 - a0 + 1)));        // loudness of the sound's active part (-20 dB window)
  // derived 0..1 descriptors (the scale every query and every event target uses)
  const brightness = clamp((Math.log2(Math.max(centroid, 1)) - Math.log2(100)) / (Math.log2(5000) - Math.log2(100)));
  const lowR = tot ? low / tot : 0;
  const weight = clamp(0.5 * (1 - brightness) + 0.5 * clamp(lowR / 0.35));
  // files are usually peak-normalised, so the peak says little; the energy of the active part says how hard it is
  const sharpness = clamp(1 - attack / 0.12);
  const intensity = clamp(0.7 * clamp((bodyDb + 32) / 24) + 0.3 * sharpness);
  return {
    dur: r3(dur), peakDb: +peakDb.toFixed(1), rmsDb: +rmsDb.toFixed(1), bodyDb: +bodyDb.toFixed(1), crest: +crest.toFixed(1),
    peakT: r3(pi / 100), attack: r3(attack), decay: r3(decay), centroid: Math.round(centroid),
    low: r3(lowR), high: r3(tot ? high / tot : 0), zcr: r3(zc / dur / SR), flatness: r3(flatness),
    brightness: r3(brightness), weight: r3(weight), intensity: r3(intensity),
    sharpness: r3(sharpness), tonal: r3(clamp(1 - flatness / 0.1)),
  };
}

// ---------- TAG: words → facets (vocabulary), plus a few tags read straight from the measurements ----------
const words = (...s) => s.filter(Boolean).join(' ').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
export function tagsFor(m, text, vocab) {
  const w = new Set(text.flatMap((t) => words(t)));
  for (const x of [...w]) if (x.endsWith('s')) w.add(x.slice(0, -1));
  const tags = {};
  for (const [facet, values] of Object.entries(vocab.facets ?? {})) {
    tags[facet] = Object.entries(values).filter(([, kws]) => kws.some((k) => w.has(k))).map(([v]) => v);
  }
  const tex = [];
  if (m.sharpness >= 0.75) tex.push('transient');
  if (m.dur >= 3 && m.decay >= 1.5) tex.push('sustained');
  if (m.tonal >= 0.6) tex.push('tonal'); else if (m.tonal <= 0.4) tex.push('noisy');
  if (m.decay >= 0.6 && m.tonal >= 0.4) tex.push('ringing');
  if (m.brightness >= 0.65) tex.push('bright'); else if (m.brightness <= 0.3) tex.push('dark');
  tags.texture = [...new Set([...(tags.texture ?? []), ...tex])];
  tags.size = [m.weight >= 0.62 ? 'heavy' : m.weight <= 0.38 ? 'light' : 'medium'];
  if (m.dur >= 8 && !tags.action?.length) tags.action = ['bed'];
  return tags;
}

// ---------- SCAN: walk roots, hash, measure what changed, tag everything ----------
function walk(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = path.join(dir, d.name);
    if (d.isDirectory()) return walk(p);
    return AUDIO.test(d.name) && !d.name.startsWith('_') ? [p] : [];
  }).sort();
}
const idOf = (root, file) => path.relative(root, file).replace(/\\/g, '/').replace(AUDIO, '');
/** credits.json key for a file: its id, or "earshot:<bank id>" for a rendered Earshot sound (swish_blade-0.6-0.2 → swish/blade). */
function creditFor(id, credits) {
  if (credits[id]) return credits[id];
  const m = id.match(/^earshot\/(.+?)-[\d.]+-(?:[\d.]+|x)$/);
  if (m) { const k = Object.keys(credits).find((c) => c.startsWith('earshot:') && c.slice(8).replace(/[^a-z0-9.-]+/gi, '_') === m[1]); if (k) return { ...credits[k], bank: k.slice(8) }; }
  return null;
}

/**
 * Build or refresh the catalog. Unchanged files (same content hash, same analyzer) keep their measurements;
 * tags are always recomputed (cheap), so a vocabulary or override edit applies at once.
 * Returns { catalog, stats: { files, measured, cached, ms } }.
 */
export function scan(o = {}) {
  const cfg = { ...DEFAULTS, ...o };
  const t0 = Date.now();
  const vocab = readJSON(cfg.vocab, { facets: {}, events: {} });
  const credits = readJSON(cfg.credits, {});
  const overrides = readJSON(cfg.overrides, {});
  const old = o.fresh ? {} : Object.fromEntries((readJSON(cfg.catalog, { sounds: [] }).sounds ?? []).map((s) => [s.hash, s]));
  const sounds = []; let measured = 0, cached = 0;
  for (const root of cfg.roots) for (const file of walk(root)) {
    const buf = fs.readFileSync(file);
    const hash = crypto.createHash('sha1').update(buf).digest('hex').slice(0, 16);
    const id = idOf(root, file);
    let m = old[hash]?.analyzer === ANALYZER ? (old[hash].measured ?? old[hash].m) : null;   // never the hand-edited numbers
    if (m) cached++; else { m = measure(file); measured++; }
    const cr = creditFor(id, credits);
    const source = id.startsWith('earshot/') ? 'earshot' : cr?.source === 'synth' || /synth/i.test(cr?.creator ?? '') ? 'synth' : cr ? (cr.source ?? 'credited') : 'local';
    const tags = tagsFor(m, [id.replace(/^earshot\//, ''), cr?.title, cr?.query, cr?.bank], vocab);
    const ov = overrides[id] ?? {};
    for (const [k, v] of Object.entries(ov)) if (k in tags || Array.isArray(v)) tags[k] = Array.isArray(v) ? v : [v];
    const rec = { id, file: file.replace(/\\/g, '/'), hash, analyzer: ANALYZER, source, license: cr?.license ?? null, m, tags };
    for (const k of ['weight', 'intensity', 'brightness', 'sharpness', 'tonal']) if (typeof ov[k] === 'number') { rec.measured ??= m; rec.m = { ...rec.m, [k]: ov[k] }; }
    if (Object.keys(ov).length) rec.edited = true;
    sounds.push(rec);
  }
  const catalog = { schema: SCHEMA, analyzer: ANALYZER, vocab: cfg.vocab, roots: cfg.roots, count: sounds.length, sounds };
  if (o.write !== false) fs.writeFileSync(cfg.catalog, JSON.stringify(catalog, null, 1) + '\n');
  return { catalog, stats: { files: sounds.length, measured, cached, ms: Date.now() - t0 } };
}

export function loadCatalog(file = DEFAULTS.catalog) {
  const c = readJSON(file, null);
  if (!c) throw new Error(`no sound catalog at ${file}: run  node tools/sonic.mjs scan`);
  return c;
}

// ---------- QUERY: "material=steel action=impact dur<0.5 weight>=0.6 id~clash" ----------
const NUM = new Set(['dur', 'peakDb', 'rmsDb', 'bodyDb', 'crest', 'peakT', 'attack', 'decay', 'centroid', 'low', 'high', 'zcr', 'flatness', 'brightness', 'weight', 'intensity', 'sharpness', 'tonal']);
export function parseQuery(q) {
  const terms = Array.isArray(q) ? q : String(q).trim().split(/\s+/).filter(Boolean);
  return terms.map((t) => {
    const m = t.match(/^([a-zA-Z_]+)(!=|>=|<=|=|>|<|~)(.+)$/);
    if (!m) throw new Error(`bad query term "${t}" (use key=value, key!=value, key>n, key<n, key>=n, key<=n or key~text)`);
    return { key: m[1], op: m[2], val: m[3] };
  });
}
function valueOf(s, key) {
  if (NUM.has(key)) return s.m[key];
  if (key === 'id' || key === 'file' || key === 'source' || key === 'license') return s[key] ?? '';
  return s.tags[key] ?? [];
}
function test(s, { key, op, val }) {
  const v = valueOf(s, key);
  if (NUM.has(key)) {
    const x = +val;
    return op === '>' ? v > x : op === '<' ? v < x : op === '>=' ? v >= x : op === '<=' ? v <= x : op === '!=' ? v !== x : op === '=' ? Math.abs(v - x) < 1e-9 : false;
  }
  const alts = val.toLowerCase().split('|');
  const list = Array.isArray(v) ? v.map(String) : [String(v)];
  const hit = op === '~' ? list.some((x) => alts.some((a) => x.toLowerCase().includes(a))) : list.some((x) => alts.includes(x.toLowerCase()));
  return op === '!=' ? !hit : hit;
}
/** Filter the catalog. sort: an attribute (descending; prefix "-" for ascending). Returns matching records. */
export function query(cat, q, o = {}) {
  const terms = parseQuery(q);
  let out = cat.sounds.filter((s) => terms.every((t) => test(s, t)));
  if (o.sort) { const asc = o.sort.startsWith('-'), k = o.sort.replace(/^-/, ''); out.sort((a, b) => (asc ? 1 : -1) * ((valueOf(a, k) ?? 0) - (valueOf(b, k) ?? 0))); }
  return o.limit ? out.slice(0, o.limit) : out;
}
/** One compact line per sound: what an agent needs to choose, nothing else. */
export function brief(s) {
  const t = s.tags, m = s.m;
  const tg = [...(t.material ?? []), ...(t.action ?? []), ...(t.size ?? []), ...(t.texture ?? [])].join(',');
  return `${s.id}  ${m.dur}s  w${m.weight} i${m.intensity} b${m.brightness}  [${tg}]`;
}

// ---------- PICK: an engine event → the best sound, with variation ----------
const hash01 = (str) => parseInt(crypto.createHash('md5').update(String(str)).digest('hex').slice(0, 8), 16) / 0xffffffff;
const mapRange = (x, [a, b], [c, d]) => c + (d - c) * clamp((x - a) / (b - a || 1));
/**
 * pick(cat, vocab, event, state) → { sound, score, alternatives, why } or null.
 * event: { kind, material?, intensity?, speed?, height?, dur?, seed? } — kinds and their mapping live in vocab.events.
 * state: { recent: { [kind]: [ids] } } — shared across calls so the same kind does not repeat a recent sound.
 */
export function pick(cat, vocab, event, state = {}) {
  const spec = vocab.events?.[event.kind];
  if (!spec) return null;
  const need = Object.entries(spec.need ?? {});
  const pool = cat.sounds.filter((s) => need.every(([f, v]) => (s.tags[f] ?? []).includes(v))
    && (spec.minDur == null || s.m.dur >= spec.minDur) && (spec.maxDur == null || s.m.dur <= spec.maxDur));
  if (!pool.length) return null;
  const scored = pool.map((s) => {
    let score = 0; const why = [];
    // a sound named for the event ("dash-burst" for a dash) is the author's own hint: worth a bonus
    const nameWords = s.id.toLowerCase().split(/[^a-z0-9]+/);
    if ((spec.words ?? [event.kind]).some((w) => nameWords.includes(w))) { score += 0.6; why.push('named'); }
    for (const f of spec.match ?? []) if (event[f] != null) {
      if ((s.tags[f] ?? []).includes(event[f])) { score += 1.5; why.push(`${f}=${event[f]}`); } else score -= 1.5;
    }
    for (const [f, v] of Object.entries(spec.prefer ?? {})) if (event[f] == null && (s.tags[f] ?? []).includes(v)) { score += 0.5; why.push(`${f}=${v}`); }
    for (const [attr, t] of Object.entries(spec.targets ?? {})) {
      const x = event[t.from]; if (x == null) continue;
      const want = mapRange(x, t.in, t.out), d = Math.abs((s.m[attr] ?? 0) - want);
      score -= (t.w ?? 1) * d * 2; why.push(`${attr}≈${want.toFixed(2)} (${s.m[attr]})`);
    }
    return { s, score: +score.toFixed(3), why };
  }).sort((a, b) => b.score - a.score || a.s.id.localeCompare(b.s.id));
  // variety: among the candidates close to the best, skip the latest picks of this kind, then choose by seed
  const best = scored[0].score, margin = event.margin ?? spec.margin ?? 0.15;
  const recent = (state.recent ??= {})[event.kind] ??= [];
  let near = scored.filter((c) => c.score >= best - margin);
  const avoid = recent.slice(-(spec.variety ?? 0));
  const fresh = near.filter((c) => !avoid.includes(c.s.id));
  // nothing new close to the best: widen the window (3× the margin) before repeating a sound just heard
  const wider = fresh.length ? fresh : scored.filter((c) => c.score >= best - 3 * margin && !avoid.includes(c.s.id)).slice(0, 1);
  if (wider.length) near = wider;
  const choice = near[Math.floor(hash01(event.seed ?? JSON.stringify(event)) * near.length) % near.length];
  recent.push(choice.s.id);
  return { sound: choice.s, score: choice.score, why: choice.why, alternatives: near.length, spec };
}

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

/**
 * Re-pick the sounds of a cue list from the catalog (engine/sound.mjs calls this when a film opts in).
 * Keeps every cue's time, gain and rate; changes which file plays, keeps its level close to the sound it
 * replaces (matchLevel), and lines up the new sound's measured peak with the event's moment (align: peak).
 * Returns the report: one row per cue it touched.
 */
export function applyToCues(cues, o = {}) {
  const cat = o.catalog ?? loadCatalog(o.catalogPath);
  const vocab = o.vocab ?? readJSON(o.vocabPath ?? cat.vocab ?? DEFAULTS.vocab, { events: {} });
  const kinds = o.kinds ? new Set(o.kinds) : null;
  const byId = Object.fromEntries(cat.sounds.map((s) => [s.id, s]));
  const state = { recent: {} }, report = [];
  for (const c of [...cues].sort((a, b) => a.t - b.t)) {
    const ev = eventOfCue(c);
    if (!ev || (kinds && !kinds.has(ev.kind))) continue;
    const r = pick(cat, vocab, { ...ev, seed: `${o.seed ?? ''}:${c.id}` }, state);
    if (!r) continue;
    const was = c.earshot ? null : byId[c.sfx];
    let gain = c.gain ?? 1;
    if (o.matchLevel !== false && was) gain *= 10 ** (clamp(was.m.rmsDb - r.sound.m.rmsDb, -9, 9) / 20);
    let t = c.t;
    if (r.spec.align === 'peak' && ev.peakAt != null) t = Math.max(0, ev.peakAt - r.sound.m.peakT / (c.earshot ? 1 : (c.rate ?? 1)));   // a rate plays the file faster: its peak comes sooner
    report.push({ id: c.id, kind: ev.kind, was: c.earshot ? `earshot:${c.earshot}` : c.sfx, now: r.sound.id, score: r.score, of: r.alternatives, t: r3(t), why: r.why.join(' ') });
    Object.assign(c, { file: r.sound.file, sfx: r.sound.id, t: r3(t), gain: r3(gain), sonic: { id: r.sound.id, score: r.score, event: ev } });
    if (c.earshot) { delete c.earshot; delete c.apex; c.len = Math.min(c.len ?? r.sound.m.dur, r.sound.m.dur); if (c.rate == null) c.rate = 1; }
  }
  return report;
}

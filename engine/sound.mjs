// Sound pipeline: FIND → CHECK → PLACE, driven by the film's "sounds" cue list.
//   node engine/sound.mjs                 → output/ganryujima-sound.mp4
//   node engine/sound.mjs --film film/x.json --video output/x.mp4 --refresh
//
// FIND:  search Openverse (millions of free CC0 / CC-BY sounds) for each cue's query.
// CHECK: download candidates and measure them with ffmpeg; reject silent, too-quiet
//        or wrong-length files; trim leading silence. First candidate that passes wins.
// PLACE: the engine already knows the exact second of every slash/impact/step from the
//        choreography, so each sound is dropped at its cue time and mixed under the video.
// Credits for every sound (title, author, licence, link) go to assets/sfx/credits.json.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const filmPath = opt('film', 'film/ganryujima.json');
const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
const base = path.basename(filmPath, '.json');
const video = opt('video', `output/${base}.mp4`);
const out = opt('out', `output/${base}-sound.mp4`);
const dir = 'assets/sfx';
fs.mkdirSync(dir, { recursive: true });
const creditsPath = path.join(dir, 'credits.json');
const credits = fs.existsSync(creditsPath) ? JSON.parse(fs.readFileSync(creditsPath, 'utf8')) : {};
const localOnly = args.includes('--local-only');
const UA = { 'User-Agent': 'paper-cinema/1.0' };

function stats(file) {
  let txt = '';
  try { execFileSync('ffmpeg', ['-hide_banner', '-i', file, '-af', 'volumedetect', '-f', 'null', '-'], { stdio: 'pipe' }); }
  catch (e) { txt = String(e.stderr ?? ''); }
  if (!txt) txt = String(execFileSync('bash', ['-c', `ffmpeg -hide_banner -i "${file}" -af volumedetect -f null - 2>&1`]));
  const num = (re) => { const m = txt.match(re); return m ? parseFloat(m[1]) : NaN; };
  const d = txt.match(/Duration: (\d+):(\d+):([\d.]+)/);
  return { dur: d ? +d[1] * 3600 + +d[2] * 60 + +d[3] : 0, mean: num(/mean_volume: (-?[\d.]+) dB/), max: num(/max_volume: (-?[\d.]+) dB/) };
}

async function find(cue) {
  if (cue.file) return fs.existsSync(cue.file) ? cue.file : (console.log(`✗ ${cue.id}: missing file ${cue.file}`), null);
  const file = path.join(dir, `${cue.id}.mp3`);
  if (fs.existsSync(file) && credits[cue.id] && !args.includes('--refresh')) return file;
  if (localOnly) throw new Error(`Missing local sound ${cue.id}: ${file}`);
  const url = `https://api.openverse.org/v1/audio/?q=${encodeURIComponent(cue.query)}&license=cc0,by&page_size=20`;
  const res = await (await fetch(url, { headers: UA })).json();
  const cands = (res.results ?? []).filter((r) => r.duration && r.duration >= cue.min && r.duration <= cue.max && r.url);
  for (const r of cands.slice(0, 8)) {
    const raw = path.join(dir, `_cand.${(r.filetype || 'mp3').replace(/[^a-z0-9]/g, '')}`);
    try {
      const buf = Buffer.from(await (await fetch(r.url, { headers: UA })).arrayBuffer());
      fs.writeFileSync(raw, buf);
      // trim leading silence, normalise format
      execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', raw, '-af',
        'silenceremove=start_periods=1:start_threshold=-45dB', '-ac', '2', '-ar', '44100', '-b:a', '192k', file]);
      const s = stats(file);
      const okLen = s.dur >= Math.min(cue.len, 0.25);
      const okLoud = s.max > -12 && s.mean > -45;
      if (okLen && okLoud) {
        credits[cue.id] = { title: r.title, creator: r.creator, license: r.license, license_version: r.license_version,
          source: r.source, url: r.foreign_landing_url, query: cue.query, measured: s };
        console.log(`✓ ${cue.id.padEnd(13)} "${r.title}" by ${r.creator} (${r.license}) ${s.dur.toFixed(1)}s peak ${s.max}dB`);
        return file;
      }
      console.log(`  ${cue.id}: rejected "${r.title}" (len ${s.dur.toFixed(1)}s, peak ${s.max}dB, mean ${s.mean}dB)`);
    } catch (e) {
      console.log(`  ${cue.id}: failed candidate "${r.title}": ${String(e.message).slice(0, 80)}`);
    }
  }
  console.log(`✗ ${cue.id}: no usable sound for "${cue.query}" — try another query or generate one`);
  return null;
}

// Automatic cues (whooshes, clashes, scrapes found from the motion) come from an events file
// written by the renderer: --events output/<film>.events.json (default: used when it exists).
const evPath = opt('events', `output/${base}.events.json`);
const evData = fs.existsSync(evPath) ? JSON.parse(fs.readFileSync(evPath, 'utf8')) : null;
const autoCues = evData?.cues ?? [];
if (autoCues.length) console.log(`+ ${autoCues.length} automatic cues from ${evPath}`);
// film.autoSounds.whoosh.earshot: [ids] → automatic whooshes come from the Earshot bank, peak aimed at the blade's
// fastest moment (the analysis places whoosh cues 0.06 s before the speed peak; the apex puts the loudest point on it)
const ES = film.autoSounds?.whoosh?.earshot;
if (ES?.length) {
  let n = 0;
  for (const c of autoCues) if (/^auto-whoosh/.test(c.id)) {
    Object.assign(c, { earshot: ES[n++ % ES.length], t: c.t + 0.06, apex: 0.2, len: 0.6 });
    delete c.sfx; delete c.rate;
  }
}
// A cue with "body": true is timed to the fighters' action (body time): it moves later by every hit-stop before it.
const stops = evData?.stops ?? [];
// With speed ramps (film.ramps, motion page) the events file carries a table: body time → film time ("warp").
const warp = evData?.warp ?? null;
const filmT = (tb) => {
  if (warp) { const x = Math.max(0, Math.min(warp.film.length - 1, tb / warp.dt)), i = Math.floor(x); return warp.film[i] + (warp.film[Math.min(i + 1, warp.film.length - 1)] - warp.film[i]) * (x - i); }
  return tb + stops.filter((st) => st.tb < tb).reduce((a, st) => a + st.d, 0);
};
for (const c of film.sounds ?? []) if (c.body && (stops.length || warp)) c.t = +filmT(c.t).toFixed(3);
// Spoken lines (VOICE, docs/VOICE.md) come from output/<film>.voice.json, written by tools/voice.py:
// cues with a ready "file" (no search), plus the speech windows used to duck beds/music under the voice.
const voicePath = opt('voice', `output/${base}.voice.json`);
const voice = fs.existsSync(voicePath) ? JSON.parse(fs.readFileSync(voicePath, 'utf8')) : null;
const voiceCues = voice?.cues ?? [];
if (voiceCues.length) console.log(`+ ${voiceCues.length} voice lines from ${voicePath}`);
function earshot(cue) {
  const dur = cue.len ?? 0.8, apex = cue.apex ?? null;
  const key = `${cue.earshot}-${dur}-${apex ?? 'x'}`.replace(/[^a-z0-9.-]+/gi, '_');
  const file = path.join(dir, 'earshot', `${key}.wav`);
  if (!fs.existsSync(file)) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const a = ['sfx', 'render', cue.earshot, '-o', file, '--dur', String(dur)];
    if (apex != null) a.push('--apex', String(apex));
    try { execFileSync('earshot', a, { stdio: 'pipe' }); }
    catch (e) { console.log(`✗ earshot ${cue.earshot}: ${String(e.stderr ?? e.message).slice(0, 160)}`); return null; }
  }
  credits[`earshot:${cue.earshot}`] = { title: cue.earshot, creator: 'Earshot sound bank (Leonxlnx/earshot)', license: 'MIT', source: 'https://github.com/Leonxlnx/earshot' };
  console.log(`✓ ${cue.id.padEnd(13)} earshot ${cue.earshot}`);
  return file;
}

const placed = [];
for (const cue of [...(film.sounds ?? []), ...autoCues, ...voiceCues]) {
  // "sfx" reuses another sound by its id (one file, many cues); defaults for length checks
  // "earshot": "<bank id>" renders a sound from the Earshot bank (MIT, github.com/Leonxlnx/earshot; 252 sounds,
  // no network), aimed so its loudest moment ("apex", seconds into the sound) lands where the cue wants it.
  if (cue.earshot) {
    const f = earshot(cue);
    if (f) placed.push({ cue: { ...cue, t: Math.max(0, cue.t - (cue.apex ?? 0)) }, f });
    continue;
  }
  const lib = cue.sfx ? { min: 0.2, max: 8, len: cue.len, query: cue.query ?? cue.sfx, ...cue, id: cue.sfx } : cue;
  const f = await find(lib);
  if (f) placed.push({ cue, f });
}
if (localOnly && placed.length !== (film.sounds?.length ?? 0) + autoCues.length + voiceCues.length) {
  throw new Error('A local audio cue failed to load.');
}
if (!localOnly) fs.writeFileSync(creditsPath, JSON.stringify(credits, null, 2));

// PLACE + MIX
const inputs = ['-i', video];
const filters = [];
placed.forEach(({ cue, f }, i) => {
  if (cue.bed) inputs.push('-stream_loop', '-1');
  inputs.push('-i', f);
  const fadeOut = Math.min(0.6, cue.len / 3);
  // rate: play faster/higher (>1) or slower/lower (<1), like a tape speed change
  const rate = cue.rate && cue.rate !== 1 ? `asetrate=44100*${cue.rate},aresample=44100,` : '';
  filters.push(`[${i + 1}:a]${rate}atrim=0:${cue.len},asetpts=PTS-STARTPTS,afade=t=in:d=${cue.bed ? 1.5 : 0.01},` +
    `afade=t=out:st=${(cue.len - fadeOut).toFixed(2)}:d=${fadeOut.toFixed(2)},volume=${cue.gain},` +
    `adelay=${Math.round(cue.t * 1000)}|${Math.round(cue.t * 1000)}[a${i}]`);
});
// DUCK: beds and music ("bed" or "music" cues) dip under speech by voice.duck.db (default 8 dB).
// Default "exact": a volume curve from the known speech windows (precise depth, ramps of attack/release s).
// --duck sidechain: ffmpeg sidechaincompress keyed by the voice bus (depth then follows the voice level).
const duckIdx = placed.map(({ cue }, i) => (cue.bed || cue.music ? i : -1)).filter((i) => i >= 0);
const voiceIdx = placed.map(({ cue }, i) => (cue.voice ? i : -1)).filter((i) => i >= 0);
let mixIn = placed.map((_, i) => (duckIdx.includes(i) && voiceIdx.length ? '' : `[a${i}]`)).join('');
let nIn = placed.length;
if (voiceIdx.length && duckIdx.length) {
  const d = voice.duck ?? {}, depth = 10 ** (-(d.db ?? 8) / 20), at = d.attack ?? 0.12, rl = d.release ?? 0.45;
  const beds = duckIdx.map((i) => `[a${i}]`).join('');
  filters.push(`${beds}amix=inputs=${duckIdx.length}:normalize=0:dropout_transition=0[beds]`);
  if (opt('duck', 'exact') === 'sidechain') {
    filters.push(`${voiceIdx.map((i) => `[a${i}]`).join('')}amix=inputs=${voiceIdx.length}:normalize=0,asplit=2[vkey][vsc]`);
    filters.push(`[beds][vsc]sidechaincompress=threshold=0.015:ratio=8:attack=${at * 1000}:release=${rl * 1000}:knee=3[bedsd]`);
    mixIn = mixIn.replace(voiceIdx.map((i) => `[a${i}]`).join(''), '') + '[vkey]';
    nIn = nIn - duckIdx.length - voiceIdx.length + 2;
  } else {
    const wins = (voice.lines ?? []).map((l) => `clip(min((t-${(l.t0 - at).toFixed(3)})/${at},(${(l.t1 + rl).toFixed(3)}-t)/${rl}),0,1)`);
    const amt = wins.reduce((a, w) => (a ? `max(${a},${w})` : w), '');
    filters.push(`[beds]volume=eval=frame:volume='1-${(1 - depth).toFixed(4)}*${amt}'[bedsd]`);
    nIn = nIn - duckIdx.length + 1;
  }
  mixIn += '[bedsd]';
  console.log(`  ducking ${duckIdx.length} bed/music cue(s) by ${d.db ?? 8} dB under ${voiceIdx.length} voice line(s) (${opt('duck', 'exact')})`);
}
const ending = Math.min(film.duration, 1.5);
filters.push(`${mixIn}amix=inputs=${nIn}:normalize=0:dropout_transition=0,alimiter=limit=0.9,` +
  `apad,afade=t=out:st=${film.duration - ending}:d=${ending}[mix]`);
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...inputs, '-filter_complex', filters.join(';'),
  '-map', '0:v', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-t', String(film.duration), out]);
console.log(`\nwrote ${out} with ${placed.length}/${(film.sounds ?? []).length + autoCues.length + voiceCues.length} sounds` +
  `${voiceCues.length ? ` (${voiceCues.length} voice lines)` : ''}. Credits: ${creditsPath}`);

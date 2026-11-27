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
import { execFileSync, spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const filmPath = opt('film', 'film/ganryujima.json');
const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
const base = path.basename(filmPath, '.json');
const video = opt('video', `output/${base}.mp4`);
// The output is as long as the VIDEO when the video is longer than the film (a hit-stop cut adds frames): cutting
// at film.duration dropped the last frames of a 3-frame hit-stop clip.
let DUR = film.duration;
try {
  const vd = parseFloat(String(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video])));
  if (vd > DUR) DUR = vd;
} catch { /* no video yet: film.duration */ }
const out = opt('out', `output/${base}-sound.mp4`);
const dir = 'assets/sfx';
fs.mkdirSync(dir, { recursive: true });
const creditsPath = path.join(dir, 'credits.json');
const credits = fs.existsSync(creditsPath) ? JSON.parse(fs.readFileSync(creditsPath, 'utf8')) : {};
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
    catch (e) {
      // A MISSING TOOL IS NOT A MISSING SOUND. This used to log a line and return null, so a film
      // rendered silent in that cue and nothing failed - and `earshot` was installed by hand in one
      // container and pinned nowhere, so that was one fresh machine away from happening. It is now
      // in vendor/MANIFEST.json; say how to get it rather than quietly dropping the sound.
      const msg = String(e.stderr ?? e.message);
      if (/ENOENT|not found/i.test(msg)) {
        console.log(`✗ earshot is not installed — every automatic whoosh and clash will be SILENT.\n`
          + `  node tools/vendor.mjs earshot && pip install ./vendor/earshot`);
      } else {
        console.log(`✗ earshot ${cue.earshot}: ${msg.slice(0, 160)}`);
      }
      return null;
    }
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
fs.writeFileSync(creditsPath, JSON.stringify(credits, null, 2));

// PRE-HIT DIP (docs/STUDIO-STANDARD.md: a hit stands at least 9 dB above what comes just before it).
// Every hit the eye sees (the events file's impacts and blade contacts) gets a hole punched in the bed and in
// the whooshes just before it: -preDip dB from t-0.30 s to t-0.03 s, back up over 0.12 s. The transient then
// lands in a quieter moment instead of fighting the whoosh that led into it.
const PRE_DIP = +opt('pre-dip', film.autoSounds?.preDip ?? 11);     // dB (0 turns it off)
const hitTimes = [...(evData?.impacts ?? []), ...(evData?.contacts ?? [])]
  .map((h) => +h.t).filter((t) => t > 0.05).sort((a, b) => a - b);
const dipCurve = () => {
  if (!PRE_DIP || !hitTimes.length) return '';
  const depth = 1 - 10 ** (-PRE_DIP / 20);
  // open over 0.12 s from t-0.42, hold wide open to t-0.06, shut in 0.04 s: the whole of the window the audit
  // measures against (t-0.30 … t-0.03) is dipped, and the transient itself (from t-0.01) is untouched.
  const w = hitTimes.map((t) => `clip(min((t-${(t - 0.42).toFixed(3)})/0.12,(${(t - 0.02).toFixed(3)}-t)/0.04),0,1)`);
  const amt = w.reduce((a, b) => (a ? `max(${a},${b})` : b), '');
  return `volume=eval=frame:volume='1-${depth.toFixed(4)}*${amt}'`;
};
const DIPC = dipCurve();
if (DIPC) console.log(`  dipping beds and whooshes ${PRE_DIP} dB before ${hitTimes.length} hit(s)`);
const WHOOSH = /whoosh|swish|air-cut|shing/i;
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
    `adelay=${Math.round(cue.t * 1000)}|${Math.round(cue.t * 1000)}` +
    `${DIPC && (cue.bed || cue.music || WHOOSH.test(cue.id)) ? ',' + DIPC : ''}[a${i}]`);
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
// LEVEL (two measured passes): the film has to land at -14 LUFS integrated under a true peak of -1 dBFS
// (Shorts/broadcast practice; docs/STUDIO-STANDARD.md, and tools/audit.mjs fails the film outside -14 ± 2).
// A fight mix cannot get there with one linear gain — the clashes are 15 dB above the rest, so ffmpeg's
// loudnorm would switch to its dynamic mode and flatten exactly the transients the hits live on. Instead:
// measure the whole programme, apply ONE makeup gain with a true-peak limiter after it, measure again and
// correct for what the limiter shaved. The dynamics (and the dipped hole before each hit) survive.
const TARGET = +opt('lufs', -14), CEIL = +opt('peak', -1);
// the limiter works on samples; an oversampled TRUE peak (and the AAC encode) comes out a few tenths above
// that, so aim it 0.5 dB under the ceiling and the finished file measures at or below it.
const CEIL_LIN = (10 ** ((CEIL - 0.5) / 20)).toFixed(4);
const chain = (gain, meter) => `${mixIn}amix=inputs=${nIn}:normalize=0:dropout_transition=0,` +
  `afade=t=out:st=${DUR - 1.5}:d=1.5,volume=${gain.toFixed(2)}dB,` +
  `alimiter=level=false:limit=${CEIL_LIN}${meter ? ',ebur128=peak=true' : ''}[mix]`;
// spawnSync, not a shell: the filter graph is full of single quotes (the dip expressions) and no amount of
// shell quoting survives that.
const ff = (a) => {
  const r = spawnSync('ffmpeg', a, { encoding: 'utf8', maxBuffer: 1 << 26 });
  if (r.status !== 0) {
    console.error(((r.stderr ?? '') + (r.stdout ?? '')).split('\n').slice(-12).join('\n'));
    throw new Error(`sound: ffmpeg failed (exit ${r.status}) — see the lines above`);
  }
  return (r.stderr ?? '') + (r.stdout ?? '');
};
const measure = (gain) => {
  const txt = ff(['-hide_banner', '-nostats', '-y', ...inputs, '-filter_complex', filters.concat(chain(gain, true)).join(';'),
    '-map', '[mix]', '-t', String(DUR), '-f', 'null', '-']);
  const g = (re) => { const m = txt.match(re); return m ? parseFloat(m[1]) : NaN; };
  return { lufs: g(/Integrated loudness:\s+I:\s+(-?[\d.]+)/), tp: g(/True peak:\s*\n\s*Peak:\s+(-?[\d.]+)/) };
};
const clamp = (g) => Math.max(-24, Math.min(24, g));
const m1 = measure(0);
let gain = Number.isFinite(m1.lufs) ? clamp(TARGET - m1.lufs) : 0;
console.log(`  level pass 1: the mix measures ${m1.lufs} LUFS, true peak ${m1.tp} dBFS` +
  ` → ${gain >= 0 ? '+' : ''}${gain.toFixed(1)} dB makeup, ceiling ${CEIL} dBFS`);
if (gain) {
  const m2 = measure(gain);
  const corr = Number.isFinite(m2.lufs) ? clamp(gain + (TARGET - m2.lufs)) : gain;
  console.log(`  level pass 2: with the gain and the limiter it measures ${m2.lufs} LUFS, true peak ${m2.tp} dBFS` +
    ` → ${corr >= 0 ? '+' : ''}${corr.toFixed(1)} dB for the final mix`);
  gain = corr;
}
ff(['-y', '-loglevel', 'error', ...inputs, '-filter_complex', filters.concat(chain(gain, false)).join(';'),
  '-map', '0:v', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', String(DUR), out]);
console.log(`\nwrote ${out} with ${placed.length}/${(film.sounds ?? []).length + autoCues.length + voiceCues.length} sounds` +
  `${voiceCues.length ? ` (${voiceCues.length} voice lines)` : ''}. Credits: ${creditsPath}`);

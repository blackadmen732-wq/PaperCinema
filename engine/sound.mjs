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

const placed = [];
for (const cue of film.sounds ?? []) {
  const f = await find(cue);
  if (f) placed.push({ cue, f });
}
fs.writeFileSync(creditsPath, JSON.stringify(credits, null, 2));

// PLACE + MIX
const inputs = ['-i', video];
const filters = [];
placed.forEach(({ cue, f }, i) => {
  if (cue.bed) inputs.push('-stream_loop', '-1');
  inputs.push('-i', f);
  const fadeOut = Math.min(0.6, cue.len / 3);
  filters.push(`[${i + 1}:a]atrim=0:${cue.len},asetpts=PTS-STARTPTS,afade=t=in:d=${cue.bed ? 1.5 : 0.01},` +
    `afade=t=out:st=${(cue.len - fadeOut).toFixed(2)}:d=${fadeOut.toFixed(2)},volume=${cue.gain},` +
    `adelay=${Math.round(cue.t * 1000)}|${Math.round(cue.t * 1000)}[a${i}]`);
});
const mixIn = placed.map((_, i) => `[a${i}]`).join('');
filters.push(`${mixIn}amix=inputs=${placed.length}:normalize=0:dropout_transition=0,alimiter=limit=0.9,` +
  `afade=t=out:st=${film.duration - 1.5}:d=1.5[mix]`);
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...inputs, '-filter_complex', filters.join(';'),
  '-map', '0:v', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', String(film.duration), out]);
console.log(`\nwrote ${out} with ${placed.length}/${(film.sounds ?? []).length} sounds. Credits: ${creditsPath}`);

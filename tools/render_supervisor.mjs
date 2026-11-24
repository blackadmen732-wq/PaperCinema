// RENDER SUPERVISOR: turns one canonical timeline into finished frames, shot by shot, and survives a crash.
// Module map: docs/ARCHITECTURE.md §Render Supervisor. Format: docs/TIMELINE-FORMAT.md.
//
//   node tools/render_supervisor.mjs film/<name>.json                      # preview quality, every shot, resumable
//   node tools/render_supervisor.mjs film/<name>.json --quality final      # draft | preview | final | hero
//   node tools/render_supervisor.mjs film/<name>.json --shots S3,S4        # only these shots
//   node tools/render_supervisor.mjs film/<name>.json --plan               # print the plan, render nothing
//   node tools/render_supervisor.mjs film/<name>.json --resume             # skip the shots already done (default)
//   node tools/render_supervisor.mjs film/<name>.json --restart            # forget the state and start again
//   options: --renderer preview|blender · --retries 1 · --out output/shots/<film> · --quiet
//
// What it does that a bare render does not:
//   * SHOT LIST: it renders per shot (from the timeline), so a 36 s film is 6-8 jobs, not one 55-minute gamble.
//   * QUALITY PRESETS: one table (below) for every renderer, so "final" means the same thing everywhere.
//   * FAILURE HANDLING: a shot that fails is retried, then marked failed; the other shots still finish.
//   * RESUME: the state of every shot lives in output/<film>.render-state.json, so a killed run picks up where it
//     stopped, and a changed timeline (its hash) invalidates only the shots whose frames changed.
import { execFileSync, spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes('--' + n);

// ---------- quality presets (one table for every renderer) ----------
export const QUALITY = {
  draft:   { scale: 0.5, fps: 12, blender: { samples: 8, res: '216x384', blur: false, fog: 0.008 }, note: 'is the motion right?' },
  preview: { scale: 1, fps: 24, blender: { samples: 16, res: '432x768', blur: true, fog: 0.012 }, note: 'the default: look at it' },
  final:   { scale: 1, fps: 24, blender: { samples: 64, res: '720x1280', blur: true, fog: 0.012 }, note: 'the render that ships' },
  hero:    { scale: 1, fps: 24, blender: { samples: 192, res: '1080x1920', blur: true, fog: 0.012 }, note: 'one still for a thumbnail' },
};

const hashOf = (obj) => crypto.createHash('sha1').update(JSON.stringify(obj)).digest('hex').slice(0, 12);

/** the plan: one job per shot, with the frames it owns and the hash of those frames */
export function planFrom(TL, { quality = 'preview', only = null } = {}) {
  const Q = QUALITY[quality] ?? QUALITY.preview;
  const shots = TL.shots?.length ? TL.shots : [{ id: 'ALL', name: TL.film.title, f0: 0, f1: TL.film.frames - 1 }];
  return shots
    .filter((s) => !only || only.includes(s.id))
    .map((s) => {
      const frames = TL.frames.filter((f) => f.f >= s.f0 && f.f <= s.f1);
      return {
        shot: s.id, name: s.name ?? '', f0: s.f0, f1: s.f1, frames: frames.length,
        seconds: +((s.f1 - s.f0 + 1) / TL.film.fps).toFixed(2),
        quality, preset: Q,
        hash: hashOf({ cam: frames.map((f) => f.camera), actors: frames.map((f) => f.actors) }),
      };
    });
}

export function loadState(p) { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return { shots: {} }; } }

// ---------- CLI ----------
if (import.meta.url === `file://${process.argv[1]}`) {
  const filmPath = args.find((a) => a.endsWith('.json'));
  if (!filmPath) { console.error('usage: node tools/render_supervisor.mjs film/<name>.json [--quality preview] [--shots S1,S2] [--plan] [--restart]'); process.exit(2); }
  const NAME = path.basename(filmPath, '.json');
  const quality = opt('quality', 'preview');
  if (!QUALITY[quality]) { console.error(`unknown quality "${quality}": ${Object.keys(QUALITY).join(' | ')}`); process.exit(2); }
  const tlPath = `output/${NAME}.timeline.json`;
  if (!fs.existsSync(tlPath) || fs.statSync(tlPath).mtimeMs < fs.statSync(filmPath).mtimeMs) {
    const { exportTimeline } = await import('./timeline.mjs');
    await exportTimeline(filmPath, { quiet: flag('quiet') });
  }
  const TL = JSON.parse(fs.readFileSync(tlPath, 'utf8'));
  const only = opt('shots') ? opt('shots').split(',') : null;
  const plan = planFrom(TL, { quality, only });
  const statePath = `output/${NAME}.render-state.json`;
  const state = flag('restart') ? { shots: {} } : loadState(statePath);
  state.film = NAME; state.quality = quality; state.timeline = tlPath;
  const outDir = opt('out', `output/shots/${NAME}`);
  const renderer = opt('renderer', 'preview');
  const retries = +opt('retries', 1);

  console.log(`RENDER SUPERVISOR ${NAME}: ${plan.length} shot(s), quality ${quality} (${QUALITY[quality].note}), renderer ${renderer}`);
  for (const j of plan) {
    const done = state.shots[j.shot];
    const fresh = done && done.hash === j.hash && done.status === 'done' && done.quality === quality;
    console.log(`  ${j.shot.padEnd(5)} f${String(j.f0).padStart(4)}-${String(j.f1).padEnd(4)} ${String(j.seconds).padStart(5)} s  ${fresh ? 'done (resume: skip)' : done?.status === 'failed' ? 'failed before: retry' : 'to render'}  ${j.name}`);
  }
  if (flag('plan')) { fs.writeFileSync(`output/${NAME}.render-plan.json`, JSON.stringify({ film: NAME, quality, renderer, outDir, plan }, null, 1)); console.log(`\nplan: output/${NAME}.render-plan.json (nothing was rendered)`); process.exit(0); }

  fs.mkdirSync(outDir, { recursive: true });
  let failed = 0, skipped = 0, made = 0;
  for (const j of plan) {
    const done = state.shots[j.shot];
    if (done && done.hash === j.hash && done.status === 'done' && done.quality === quality && !flag('restart')) { skipped++; continue; }
    const prefix = `${j.shot}-`;
    let ok = false, err = null;
    for (let tryN = 0; tryN <= retries && !ok; tryN++) {
      const t0 = Date.now();
      try {
        if (renderer === 'blender') {
          const B = process.env.BLENDER ?? '/opt/blender-dl/blender-4.5.16-linux-x64/blender';
          const Q = QUALITY[quality].blender;
          const a = ['-b', '-t', '2', '-P', 'blender/film_blender.py', '--', '--film', filmPath, '--timeline', tlPath,
            '--out', path.join(outDir, j.shot), '--frames', `${j.f0}-${j.f1}`, '--samples', String(Q.samples), '--res', Q.res];
          if (!Q.blur) a.push('--no-blur');
          execFileSync('nice', ['-n', '10', B, ...a], { stdio: flag('quiet') ? 'ignore' : 'inherit' });
        } else {
          const a = ['engine/render.mjs', '--film', filmPath, '--from', String(j.f0 / TL.film.fps), '--to', String((j.f1 + 1) / TL.film.fps),
            '--prefix', prefix, '--still', 'auto'];
          if (TL.film.format === 'vertical') a.push('--vertical');
          execFileSync('nice', ['-n', '10', 'node', ...a], { stdio: flag('quiet') ? 'ignore' : 'inherit' });
        }
        ok = true;
        state.shots[j.shot] = { status: 'done', hash: j.hash, quality, renderer, out: outDir, seconds: +((Date.now() - t0) / 1000).toFixed(1), at: new Date().toISOString() };
        made++;
      } catch (e) {
        err = e.message.split('\n')[0];
        console.error(`  ! ${j.shot} failed (try ${tryN + 1}/${retries + 1}): ${err}`);
      }
      fs.writeFileSync(statePath, JSON.stringify(state, null, 1));
    }
    if (!ok) { failed++; state.shots[j.shot] = { status: 'failed', hash: j.hash, quality, renderer, error: err, at: new Date().toISOString() }; fs.writeFileSync(statePath, JSON.stringify(state, null, 1)); }
  }
  console.log(`\n${NAME}: ${made} shot(s) rendered, ${skipped} skipped (already done), ${failed} failed → ${outDir}`);
  console.log(`state: ${statePath} (run again to resume; --restart to forget)`);
  process.exit(failed ? 1 : 0);
}

// RENDER SUPERVISOR: turns one canonical timeline into finished frames, shot by shot, and survives a crash.
// Module map: docs/ARCHITECTURE.md §Render Supervisor. Format: docs/TIMELINE-FORMAT.md.
//
//   node tools/render_supervisor.mjs film/<name>.json                      # preview quality, every shot, resumable
//   node tools/render_supervisor.mjs film/<name>.json --quality final      # draft | preview | final | hero
//   node tools/render_supervisor.mjs film/<name>.json --shots S3,S4        # only these shots
//   node tools/render_supervisor.mjs film/<name>.json --plan               # print the plan, render nothing
//   node tools/render_supervisor.mjs film/<name>.json --resume             # skip the shots already done (default)
//   node tools/render_supervisor.mjs film/<name>.json --restart            # forget the state and start again
//   node tools/render_supervisor.mjs film/<name>.json --workers 4           # render 4 shots at once
//   node tools/render_supervisor.mjs film/<name>.json --plan --rate 0.18    # what a rented GPU would cost
//   options: --renderer preview|blender · --retries 1 · --out output/shots/<film> · --quiet · --spf N
//
// WHY WORKERS. A rented GPU is billed by wall-clock hour, not by frame, so an idle one costs the
// same as a busy one. The way to spend less is to finish more inside the hour you are paying for,
// which means arriving with the work prepared and running every shot at once. That is possible here
// only because every effect is a pure function of time, so no frame depends on the frame before it.
// --plan prices the job first, from seconds-per-frame measured on our own past renders.
//
// What it does that a bare render does not:
//   * SHOT LIST: it renders per shot (from the timeline), so a 36 s film is 6-8 jobs, not one 55-minute gamble.
//   * QUALITY PRESETS: one table (below) for every renderer, so "final" means the same thing everywhere.
//   * FAILURE HANDLING: a shot that fails is retried, then marked failed; the other shots still finish.
//   * RESUME: the state of every shot lives in output/<film>.render-state.json, so a killed run picks up where it
//     stopped, and a changed timeline (its hash) invalidates only the shots whose frames changed.
import { execFile, execFileSync, spawnSync } from 'node:child_process';
import { promisify } from 'node:util';
import os from 'node:os';
const run = promisify(execFile);
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

// Hash-keyed resume state is shared with any job made of independent parts (packages/aethern/js/state.mjs).
import { hashOf, loadState, isFresh, stateWriter } from '../packages/aethern/js/state.mjs';
export { loadState };

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
    const fresh = isFresh(done, j.hash, { quality });
    console.log(`  ${j.shot.padEnd(5)} f${String(j.f0).padStart(4)}-${String(j.f1).padEnd(4)} ${String(j.seconds).padStart(5)} s  ${fresh ? 'done (resume: skip)' : done?.status === 'failed' ? 'failed before: retry' : 'to render'}  ${j.name}`);
  }
  // ---- what this job costs, from OUR OWN measured render times ----------------------------------
  // A rented GPU bills wall-clock hours. What decides the bill is not how many frames there are but
  // how long the machine is switched on, so the only numbers that matter are seconds-per-frame and
  // how many shots run at once. Both are measured, not guessed: every finished shot records its own
  // seconds and frame count in the state file, so this estimate improves every time we render.
  const past = Object.values(state.shots).filter((d) => d.status === 'done' && d.seconds && d.frames);
  const measured = past.length ? past.reduce((a, d) => a + d.seconds, 0) / past.reduce((a, d) => a + d.frames, 0) : null;
  const perFrame = Number(opt('spf', 0)) || measured || (renderer === 'blender' ? 17 : 4);
  const totalFrames = plan.reduce((a, j) => a + (j.f1 - j.f0 + 1), 0);
  const cpus = os.cpus().length;
  const W = Math.max(1, Math.min(Number(opt('workers', 0)) || Math.min(plan.length, Math.max(1, cpus - 1)), plan.length));
  const serialMin = (totalFrames * perFrame) / 60;
  const wallMin = serialMin / W;
  const rate = Number(opt('rate', 0));
  console.log(`\n  ${totalFrames} frames · ${perFrame.toFixed(2)} s/frame (${measured ? `measured from ${past.length} past shot(s)` : 'estimated, nothing measured yet'})`);
  console.log(`  one at a time: ${serialMin.toFixed(1)} min · ${W} in parallel: ${wallMin.toFixed(1)} min`);
  if (rate) {
    console.log(`  at $${rate.toFixed(2)}/hr: about $${(rate * wallMin / 60).toFixed(2)}, against $${(rate * serialMin / 60).toFixed(2)} one at a time`);
    console.log('  the workers are the saving, not the GPU: the machine bills the same either way');
  } else {
    console.log('  pass --rate 0.18 to price this against a rented GPU');
  }

  if (flag('plan')) { fs.writeFileSync(`output/${NAME}.render-plan.json`, JSON.stringify({ film: NAME, quality, renderer, outDir, workers: W, totalFrames, perFrame, serialMin: +serialMin.toFixed(1), wallMin: +wallMin.toFixed(1), plan }, null, 1)); console.log(`\nplan: output/${NAME}.render-plan.json (nothing was rendered)`); process.exit(0); }

  fs.mkdirSync(outDir, { recursive: true });
  let failed = 0, skipped = 0, made = 0;

  // WORKERS: a rented GPU is billed by the hour, not by the frame, so an idle one costs the same as
  // a busy one. Shots are independent — every effect in this engine is a pure function of time, so a
  // frame never depends on the frame before it — which means they can all render at once. That is
  // the whole reason the "no accumulated simulation" rule was worth keeping.
  const workers = W;   // decided with the cost estimate above, so the printed plan is what runs

  const queue = [];
  for (const j of plan) {
    const done = state.shots[j.shot];
    if (isFresh(done, j.hash, { quality }) && !flag('restart')) { skipped++; continue; }
    queue.push(j);
  }
  if (queue.length) console.log(`rendering ${queue.length} shot(s) on ${workers} worker(s)\n`);

  // One writer at a time: several workers finishing together would otherwise interleave writes and
  // leave the resume file truncated, which costs a whole re-render.
  // (stateWriter also writes to a temp file and renames, so a crash mid-write keeps the old state.)
  const saveState = stateWriter(statePath, state);

  const cmdFor = (j) => {
    if (renderer === 'blender') {
      const B = process.env.BLENDER ?? '/opt/blender-dl/blender-4.5.16-linux-x64/blender';
      const Q = QUALITY[quality].blender;
      const a = ['-b', '-t', String(Math.max(1, Math.floor(cpus / workers))), '-P', 'blender/film_blender.py', '--',
        '--film', filmPath, '--timeline', tlPath, '--out', path.join(outDir, j.shot),
        '--frames', `${j.f0}-${j.f1}`, '--samples', String(Q.samples), '--res', Q.res];
      if (!Q.blur) a.push('--no-blur');
      return ['nice', ['-n', '10', B, ...a]];
    }
    // --still auto means "the middle of EVERY shot plus every impact", for the whole film, whatever
    // --from/--to say. Passing it per shot made each job render the same film-wide still set: two
    // shots produced byte-identical PNGs. On a GPU billed by the hour that is the worst kind of bug,
    // because it looks like progress. Each shot gets its own midpoint instead.
    const mid = ((j.f0 + j.f1) / 2 / TL.film.fps).toFixed(2);
    const a = ['engine/render.mjs', '--film', filmPath, '--from', String(j.f0 / TL.film.fps), '--to', String((j.f1 + 1) / TL.film.fps),
      '--prefix', `${j.shot}-`, '--still', mid];
    if (TL.film.format === 'vertical') a.push('--vertical');
    return ['nice', ['-n', '10', 'node', ...a]];
  };

  const renderOne = async (j) => {
    for (let tryN = 0; tryN <= retries; tryN++) {
      const t0 = Date.now();
      try {
        const [cmd, a] = cmdFor(j);
        await run(cmd, a, { maxBuffer: 64 * 1024 * 1024 });
        const secs = +((Date.now() - t0) / 1000).toFixed(1);
        // `frames` is recorded ONLY when the job actually rendered a sequence, because the cost
        // estimate divides seconds by frames. The preview renderer makes one still per shot, so
        // recording 120 frames for it would claim 0.4 s/frame and under-quote the next GPU job by
        // a factor of ten. A still records its seconds and no frame count.
        state.shots[j.shot] = { status: 'done', hash: j.hash, quality, renderer, out: outDir, seconds: secs,
                                kind: renderer === 'blender' ? 'sequence' : 'still',
                                ...(renderer === 'blender' ? { frames: j.f1 - j.f0 + 1 } : {}),
                                at: new Date().toISOString() };
        made++;
        if (!flag('quiet')) console.log(renderer === 'blender'
          ? `  ✓ ${j.shot}  ${j.f1 - j.f0 + 1} frames in ${secs}s  (${(secs / (j.f1 - j.f0 + 1)).toFixed(2)}s/frame)`
          : `  ✓ ${j.shot}  still at ${((j.f0 + j.f1) / 2 / TL.film.fps).toFixed(2)}s in ${secs}s`);
        await saveState();
        return;
      } catch (e) {
        const err = (e.stderr || e.message || '').split('\n').filter(Boolean).pop() || 'unknown error';
        console.error(`  ! ${j.shot} failed (try ${tryN + 1}/${retries + 1}): ${err.slice(0, 160)}`);
        if (tryN === retries) {
          failed++;
          state.shots[j.shot] = { status: 'failed', hash: j.hash, quality, renderer, error: err.slice(0, 300), at: new Date().toISOString() };
          await saveState();
        }
      }
    }
  };

  let next = 0;
  await Promise.all(Array.from({ length: workers }, async () => {
    while (next < queue.length) await renderOne(queue[next++]);
  }));
  await saveState.flush();

  console.log(`\n${NAME}: ${made} shot(s) rendered, ${skipped} skipped (already done), ${failed} failed → ${outDir}`);
  console.log(`state: ${statePath} (run again to resume; --restart to forget)`);
  process.exit(failed ? 1 : 0);
}

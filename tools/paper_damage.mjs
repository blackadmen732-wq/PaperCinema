// PAPER DAMAGE BRIDGE: the contract between a cut in the film and the paint that soaks into the paper.
// Design: docs/SHIMI-3D.md (UV-space simulation) · wound behaviour: docs/SHIMI.md §1c (KIZU) · module map:
// docs/ARCHITECTURE.md §Paper Damage Bridge.
//
//   node tools/paper_damage.mjs film/<name>.json            # → output/<name>.damage.json (+ damage events in the timeline)
//   options: --no-merge (do not write the events back into the timeline) · --quiet · --seed N
//
// It reads the canonical timeline (docs/TIMELINE-FORMAT.md), takes every verified cut event, and emits ONE damage
// event per wound in the form both renderers read (Blender `paper_mat_shimi`, the three.js preview, and
// `engine/shimi.py` for the simulation itself). Nothing here simulates: this is the bridge, and today it is a STUB
// for the geometry step — the polyline is PLANNED from the blade sweep (the real one needs the mesh's `shimi` UV
// layer, SHIMI-3D milestone 2). Every record says so (`polyline.source`), so no renderer can mistake it for a
// measured sweep.
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes('--' + n);

// shot size → simulation resolution (docs/SHIMI-3D.md §1)
export const RES = [
  { max: 0.3, shot: 'wide', mm_per_texel: 2, window: 256 },
  { max: 0.7, shot: 'mid', mm_per_texel: 1, window: 512 },
  { max: 1.6, shot: 'close', mm_per_texel: 0.5, window: 1024 },
  { max: 99, shot: 'macro', mm_per_texel: 0.25, window: 2048 },
];
export const resFor = (subjectHeight) => RES.find((r) => subjectHeight <= r.max) ?? RES[1];

/** which part of a paper body the cut point belongs to (the parts of engine/figure.js / the character factory) */
export function partAt(point, actorRootY = 0) {
  const y = (point?.[1] ?? 1) - actorRootY;
  if (y > 1.5) return 'head';
  if (y > 1.15) return 'neck';
  if (y > 0.8) return 'torso';
  if (y > 0.55) return 'obi';
  if (y > 0.2) return 'hakama';
  return 'foot';
}

/**
 * timeline → damage events.
 * One event per cut: `{ id, type, target, part, t, f, seed, window, mm_per_texel, gravity, polyline, wound }`.
 * `wound` is the KIZU side of the contract (how the paint leaves the cut), `polyline` the SHIMI side (where).
 */
export function damageFromTimeline(TL, { seed = 7 } = {}) {
  const FPS = TL.film.fps;
  const sizeAtFrame = (f) => {
    // the shot's framing decides the texel size: the actor height on screen is not in the timeline, so use the
    // shot's declared size, then the camera distance as a fallback
    const shot = TL.shots.find((s) => f >= s.f0 && f <= s.f1);
    const named = shot?.camera?.size ?? shot?.camera?.rig?.size ?? null;
    if (named) return { wide: 0.25, full: 0.5, medium: 0.8, close: 1.3, extreme: 2.2 }[named] ?? 0.6;
    const fr = TL.frames.find((x) => x.f === f) ?? TL.frames[0];
    const d = fr?.camera?.focus_m ?? 4;
    return Math.max(0.1, Math.min(2.4, 3.2 / d));
  };
  const out = [];
  const cuts = TL.events.filter((e) => e.type === 'paper-cut');
  const strikes = TL.events.filter((e) => e.type === 'blade-contact' || e.type === 'impact');
  let n = 0;
  for (const e of [...cuts, ...strikes.filter((s) => s.target || s.ink)]) {
    const f = e.f ?? Math.round(e.t * FPS);
    const size = sizeAtFrame(f);
    const r = resFor(size);
    const fr = TL.frames.find((x) => x.f === f) ?? TL.frames[TL.frames.length - 1];
    const actorIds = Object.keys(fr?.actors ?? {});
    const target = e.target ?? actorIds.find((id) => !fr.actors[id].hidden) ?? null;
    const rootY = target && fr?.actors?.[target] ? fr.actors[target].root[1] : 0;
    const point = e.point ?? null;
    const part = e.part ?? partAt(point, rootY);
    // the blade sweep around the cut, at sub-frame resolution: the PLANNED path of the wound
    const sweep = (TL.subframes ?? []).concat(TL.frames.map((x) => ({ t: x.t, actors: x.actors })))
      .filter((s) => Math.abs(s.t - e.t) <= 0.08)
      .sort((a, b) => a.t - b.t)
      .map((s) => {
        const id = actorIds.find((a) => s.actors[a]?.weapon);
        return id ? { t: +s.t.toFixed(4), weapon: s.actors[id].weapon } : null;
      })
      .filter(Boolean);
    out.push({
      id: `damage.${String(n++).padStart(2, '0')}`,
      type: 'cut',
      from: e.id,                                     // the ONE verified event this wound belongs to
      target, part,
      t: e.t, f, tb: e.tb ?? null,
      seed: seed + n,
      shot: r.shot, window: [r.window, r.window], mm_per_texel: r.mm_per_texel,
      gravity: { mode: 'uniform', dir: [0, -1, 0], note: 'per-texel field: pass a .npy to engine/shimi.py --gravity-map' },
      polyline: {
        source: 'planned',
        stub: true,
        note: 'planned from the blade sweep in timeline.subframes; the real UV polyline comes from the mesh cut '
          + '(bmesh.ops.bisect_plane in Blender, plane-triangle in three.js): docs/SHIMI-3D.md §2',
        plane: point ? { point, normal: [0, 1, 0] } : null,
        sweep,
        points: sweep.length ? sweep.map((s, i) => ({ u: +(i / Math.max(1, sweep.length - 1)).toFixed(4), v: 0.5,
          depth: +Math.min(1, 0.4 + 0.6 * (e.intensity ?? 0.6)).toFixed(3), t: s.t })) : [],
      },
      wound: {                                        // KIZU: how the paint leaves this cut (engine/shimi.py --wound)
        preset: part === 'head' || part === 'neck' ? 'face-cut' : 'kesa-cut',
        onset_s: +(0.08 + 0.12 * (1 - (e.intensity ?? 0.6))).toFixed(3),
        depth: +Math.min(1, 0.4 + 0.6 * (e.intensity ?? 0.6)).toFixed(3),
        pigment: 'paint (never blood: AGENTS.md rule 4)',
        drips: (e.intensity ?? 0.6) > 0.5,
      },
      render: { blender: 'paper_mat_shimi (blender/world/paper_materials.py)', preview: 'engine/paper.js onBeforeCompile',
        cache: `output/shimi/${TL.film.name}/damage.${String(n - 1).padStart(2, '0')}/${part}/` },
      status: 'contract-only (no simulation run yet)',
    });
  }
  return out;
}

// ---------- CLI ----------
if (import.meta.url === `file://${process.argv[1]}`) {
  const filmPath = args.find((a) => a.endsWith('.json'));
  if (!filmPath) { console.error('usage: node tools/paper_damage.mjs film/<name>.json [--no-merge] [--seed N]'); process.exit(2); }
  const NAME = path.basename(filmPath, '.json');
  const tlPath = `output/${NAME}.timeline.json`;
  if (!fs.existsSync(tlPath) || fs.statSync(tlPath).mtimeMs < fs.statSync(filmPath).mtimeMs) {
    const { exportTimeline } = await import('./timeline.mjs');
    await exportTimeline(filmPath, { quiet: flag('quiet') });
  }
  const TL = JSON.parse(fs.readFileSync(tlPath, 'utf8'));
  const damage = damageFromTimeline(TL, { seed: +opt('seed', 7) });
  fs.writeFileSync(`output/${NAME}.damage.json`, JSON.stringify({ film: NAME, format: 'paper-cinema-damage', version: 1,
    fps: TL.film.fps, from: tlPath, events: damage }, null, 1));
  if (!flag('no-merge')) {
    TL.events = [...TL.events.filter((e) => e.type !== 'damage'), ...damage.map((d) => ({ ...d, type: 'damage' }))]
      .sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
    fs.writeFileSync(tlPath, JSON.stringify(TL, null, 0));
  }
  if (!flag('quiet')) {
    console.log(`PAPER DAMAGE ${NAME}: ${damage.length} wound(s) → output/${NAME}.damage.json${flag('no-merge') ? '' : ` (+ merged into ${tlPath})`}`);
    for (const d of damage) console.log(`  ${d.id} ${String(d.part).padEnd(7)} f${String(d.f).padStart(4)} from ${d.from.padEnd(18)} ${d.shot} ${d.mm_per_texel} mm/texel  ${d.polyline.points.length} planned point(s)`);
    if (damage.length) console.log('  (polyline is PLANNED: the measured UV sweep is SHIMI-3D milestone 2)');
  }
}

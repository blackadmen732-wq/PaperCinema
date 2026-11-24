// CAMERA EVALUATOR: scores every shot of a film against the measurable requirements of a shot, rejects the ones that
// fail with the reason, and proposes the nearest passing alternative from library/shots.json.
// Guides: docs/CAMERA.md, docs/DIRECTION.md, docs/AUDIT.md, docs/ARCHITECTURE.md §Camera Director.
//
//   node tools/camera_check.mjs film/<name>.json              # measure the film, score every shot, exit 1 on a reject
//   node tools/camera_check.mjs film/<name>.json --step 2      # long films: measure every 2nd frame
//   node tools/camera_check.mjs film/<name>.json --json        # the data only
//   node tools/camera_check.mjs film/<name>.json --quiet
//
// It is also the camera section of the studio audit: tools/audit.mjs imports evaluateCamera() and passes the frames
// it has already measured, so the audit costs nothing extra and can never disagree with this tool.
//
// What is measured, per shot (the plan's section 8):
//   1 subject visibility  fighter, weapon and target on screen and unoccluded
//   2 action clarity      at every strike frame: the contact is on screen, unoccluded, big enough, the lens is steady
//   3 framing size        measured subject height vs the size the shot asks for (wide/full/medium/close/extreme)
//   4 continuity          the 180° line across each cut, and the 30° rule
//   5 event timing        cuts do not land on top of a strike or inside a hit-stop; every strike is covered by a shot
//   6 camera motion       smooth (no whip without a cut, no jerk) and clear of geometry
//   7 emotional fit       the shot family fits the beat (library/shots.json beat_map)
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);

// ---------- the numbers ----------
export const CRULE = {
  onScreen: 0.5,              // share of a subject's 8 key joints in frame
  strikeSize: 0.18,           // subject height at a strike frame (share of the frame height)
  strikePan: 20,              // degrees per frame at a strike frame (above this the money frame smears)
  nearGeometry: 0.25,         // metres from the lens to any prop during a shot
  whipTurn: 90, whipWindow: 8,   // 90° of turn inside 8 frames that is NOT following the subject = a whip
  smearTurn: 120,             // ...and any turn this big inside the window smears the background, tracking or not
  jerk: 14,                   // change of pan rate between frames (deg/frame²)
  turn30: 30,                 // the 30-degree rule
  cutAfterStrike: 3,          // frames: a cut this soon after a contact throws the blow away
  sizeBand: { wide: [0.1, 0.4], full: [0.33, 0.62], medium: [0.5, 0.95], close: [0.8, 2.2], extreme: [1.5, 9] },
  sizeOrder: ['wide', 'full', 'medium', 'close', 'extreme'],
};
const SEV_W = { reject: 4, warn: 1.5, note: 0.5 };
const deg = (a, b) => (Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))) * 180) / Math.PI;
const dist3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const med = (xs) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[s.length >> 1] : 0; };

/** project a world point with a frame's camera (pos + quaternion + vertical fov) → [x, y, depth] in 0..1 screen space.
 *  cam.rot is the camera's world quaternion (engine/audit-hooks.js); without it the basis is rebuilt from cam.dir
 *  with +y up (roll is then ignored). */
function project(cam, p) {
  const [qx, qy, qz, qw] = cam.rot ?? quatFromDir(cam.dir);
  const d = [p[0] - cam.pos[0], p[1] - cam.pos[1], p[2] - cam.pos[2]];
  // rotate d by the inverse camera quaternion
  const ix = -qx, iy = -qy, iz = -qz;
  const tx = 2 * (iy * d[2] - iz * d[1]), ty = 2 * (iz * d[0] - ix * d[2]), tz = 2 * (ix * d[1] - iy * d[0]);
  const v = [d[0] + qw * tx + iy * tz - iz * ty, d[1] + qw * ty + iz * tx - ix * tz, d[2] + qw * tz + ix * ty - iy * tx];
  const depth = -v[2];
  if (depth <= 1e-4) return [9, 9, depth];
  const ty2 = Math.tan((cam.fov * Math.PI) / 360);
  const y = v[1] / (depth * ty2), x = v[0] / (depth * ty2 * cam.aspect);
  return [(x + 1) / 2, (1 - y) / 2, depth];
}
/** look-at quaternion for a camera pointing along dir with +y up → [x, y, z, w] */
function quatFromDir(dir = [0, 0, -1]) {
  const z = [-dir[0], -dir[1], -dir[2]];                       // three.js cameras look down -z
  const n = Math.hypot(...z) || 1;
  z[0] /= n; z[1] /= n; z[2] /= n;
  let up = [0, 1, 0];
  if (Math.abs(z[1]) > 0.999) up = [0, 0, 1];
  const x = [up[1] * z[2] - up[2] * z[1], up[2] * z[0] - up[0] * z[2], up[0] * z[1] - up[1] * z[0]];
  const nx = Math.hypot(...x) || 1;
  x[0] /= nx; x[1] /= nx; x[2] /= nx;
  const y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]];
  const m = [x, y, z];                                         // columns of the rotation matrix
  const tr = m[0][0] + m[1][1] + m[2][2];
  if (tr > 0) { const s2 = Math.sqrt(tr + 1) * 2; return [(m[1][2] - m[2][1]) / s2, (m[2][0] - m[0][2]) / s2, (m[0][1] - m[1][0]) / s2, 0.25 * s2]; }
  if (m[0][0] > m[1][1] && m[0][0] > m[2][2]) { const s2 = Math.sqrt(1 + m[0][0] - m[1][1] - m[2][2]) * 2; return [0.25 * s2, (m[1][0] + m[0][1]) / s2, (m[2][0] + m[0][2]) / s2, (m[1][2] - m[2][1]) / s2]; }
  if (m[1][1] > m[2][2]) { const s2 = Math.sqrt(1 + m[1][1] - m[0][0] - m[2][2]) * 2; return [(m[1][0] + m[0][1]) / s2, 0.25 * s2, (m[2][1] + m[1][2]) / s2, (m[2][0] - m[0][2]) / s2]; }
  const s2 = Math.sqrt(1 + m[2][2] - m[0][0] - m[1][1]) * 2;
  return [(m[2][0] + m[0][2]) / s2, (m[2][1] + m[1][2]) / s2, 0.25 * s2, (m[0][1] - m[1][0]) / s2];
}
const onScreen = (q) => q && q[2] > 0.02 && q[0] >= 0 && q[0] <= 1 && q[1] >= 0 && q[1] <= 1;

// ---------- the evaluator ----------
/**
 * @param F     frames measured by window.AUDIT.at(t) (engine/audit-hooks.js), in order
 * @param META  window.AUDIT.meta
 * @param EVENTS window.EVENTS (contacts, impacts, stops, ground) or null
 * @param film  the film JSON
 * @param STEP  measurement step in frames (1 = every frame)
 * @returns { shots, findings, score, verdict, strikes }
 */
export function evaluateCamera({ F, META, EVENTS, film, STEP = 1, library = null }) {
  const FPS = film.fps ?? 24, DUR = film.duration;
  const LIB = library ?? JSON.parse(fs.readFileSync(path.join(path.dirname(new URL(import.meta.url).pathname), '..', 'library/shots.json'), 'utf8'));
  const vertical = (META?.W ?? film.width) < (META?.H ?? film.height);
  const aspect = (META?.W ?? film.width) / (META?.H ?? film.height);
  const ids = Object.keys(F[0]?.fighters ?? {});
  const findings = [];
  const add = (check, sev, shot, t0, t1, msg, fix, extra = {}) =>
    findings.push({ check, sev, shot, t0: +(+t0).toFixed(3), t1: +(+t1).toFixed(3), f0: Math.round(t0 * FPS), f1: Math.round(t1 * FPS), msg, fix, ...extra });

  // per-frame derived values
  F.forEach((d, i) => {
    d.i = i;
    d.f = Math.round(d.t * FPS);
    d.aspect = d.cam.aspect ?? aspect;
    const p = F[i - 1];
    d.pan = p ? deg(d.cam.dir, p.cam.dir) / STEP : 0;
    d.camStep = p ? dist3(d.cam.pos, p.cam.pos) / STEP : 0;
    d.subjects = (d.subjects?.length ? d.subjects : ids).filter((id) => d.fighters[id]?.visible);
    d.size = Math.max(0, ...d.subjects.map((id) => { const b = d.fighters[id].box; return b[3] - b[1]; }));
    // how much of the turn is simply following the subject (a tracking arc), and how much is a whip of the background
    const bearing = (row) => {
      const id = row.subjects[0];
      if (!id) return null;
      const c = row.fighters[id].joints.chest, k = row.cam.pos;
      const v = [c[0] - k[0], c[1] - k[1], c[2] - k[2]], n = Math.hypot(...v) || 1;
      return [v[0] / n, v[1] / n, v[2] / n];
    };
    const b0 = p ? bearing(p) : null, b1 = bearing(d);
    d.track = b0 && b1 ? deg(b0, b1) / STEP : 0;
    d.whip = Math.max(0, d.pan - d.track);
  });

  // the shot list: from the film (main engine), the camera beats (motion page) or the measured cuts
  const shotsIn = film.shots?.length
    ? film.shots.map((s, k) => ({ id: s.id ?? `S${k + 1}`, name: s.name ?? '', start: s.start, end: s.end, rig: s.rig ?? null,
      kind: s.rig ? 'rig' : 'keyframes', mode: s.mode ?? null }))
    : (META?.beats ?? []).map((b, k, a) => ({ id: `B${k + 1}`, name: b.note ?? '', start: b.t, end: a[k + 1]?.t ?? DUR,
      rig: typeof b.rig === 'string' ? { type: b.rig } : (b.rig ?? null), kind: 'beat', cut: !!b.cut }));
  const shots = shotsIn.length ? shotsIn : [{ id: 'ALL', name: 'the whole film', start: 0, end: DUR, rig: null, kind: 'none' }];
  shots.forEach((s, k) => {
    // a real CUT: the main engine changes shot on a cut; a motion-page beat only cuts when it says so
    s.isCut = k > 0 && (s.kind === 'beat' ? !!s.cut : true);
  });
  for (const s of shots) {
    s.f0 = Math.round(s.start * FPS); s.f1 = Math.round(s.end * FPS) - 1;
    s.frames = F.filter((d) => d.f >= s.f0 && d.f <= s.f1);
    s.intent = s.rig?.size ?? s.rig?.size0 ?? null;
    s.checks = {}; s.rejects = 0; s.warns = 0;
  }

  // strikes: the ONE verified event list (blade contacts + authored impacts), on the film clock
  const strikes = [
    ...(EVENTS?.contacts ?? []).map((c, k) => ({ id: `blade-contact.${String(k).padStart(2, '0')}`, t: c.t ?? c.tb, point: c.point, intensity: c.intensity })),
    ...(EVENTS?.impacts ?? []).map((c, k) => ({ id: `impact.${String(k).padStart(2, '0')}`, t: c.t, point: c.point, intensity: c.intensity })),
  ].filter((s) => s.t >= 0 && s.t <= DUR).sort((a, b) => a.t - b.t);
  const near = (t) => F.reduce((b, d) => (Math.abs(d.t - t) < Math.abs(b.t - t) ? d : b), F[0]);
  const shotOf = (t) => shots.find((s) => t >= s.start && t < s.end) ?? null;

  for (const s of shots) {
    if (!s.frames.length) { add('shot-not-measured', 'note', s.id, s.start, s.end, `no measured frame falls inside shot ${s.id}`, 'shorter than the measuring step: run with --step 1'); continue; }
    const live = s.frames.filter((d) => !d.free && !d.impactFrame && d.subjects.length);

    const mSizeOf = (rows) => med(rows.map((d) => d.size));
    // ---- 1. subject visibility: fighter, weapon and target on screen and unoccluded ----
    if (live.length) {
      const lost = live.filter((d) => !d.subjects.some((id) => d.fighters[id].onScreen >= CRULE.onScreen || (d.fighters[id].box[3] - d.fighters[id].box[1] > 1.2 && d.fighters[id].onScreen >= 0.12)));
      const hidden = live.filter((d) => d.subjects.some((id) => { const b = d.fighters[id].blocked; return b && b.head && b.chest; }));
      const noBlade = live.filter((d) => d.subjects.some((id) => { const bl = d.fighters[id].blade; return bl && !onScreen(bl.tipScreen) && !onScreen(bl.guardScreen); }));
      s.checks.visibility = +(1 - (lost.length + hidden.length) / live.length).toFixed(3);
      if (lost.length > live.length * 0.1)
        add('shot-subject-off-screen', 'reject', s.id, lost[0].t, lost[lost.length - 1].t,
          `${s.id}: the subject is out of frame for ${lost.length * STEP} of ${live.length * STEP} frames (first at f${lost[0].f})`,
          'the camera has lost the subject: raise the framing solver (compose / KUROKO frame rig) or widen the size');
      if (hidden.length >= 3 / STEP)
        add('shot-subject-occluded', 'reject', s.id, hidden[0].t, hidden[hidden.length - 1].t,
          `${s.id}: head and chest are behind a prop for ${hidden.length * STEP} frames (first at f${hidden[0].f})`,
          'move the camera off the prop line (a wipe may last 1-3 frames) or move the prop');
      if (noBlade.length > live.length * 0.5 && mSizeOf(live) < 2 && live.some((d) => d.subjects.some((id) => d.fighters[id].blade)))
        add('shot-weapon-off-screen', 'warn', s.id, s.start, s.end,
          `${s.id}: the blade is out of frame in ${Math.round((noBlade.length / live.length) * 100)}% of the shot`,
          'a sword film needs the sword: lower the size (wider) or aim the frame between the eyes and the blade');
      const pair = live.filter((d) => d.subjects.length >= 2);
      const halfPair = pair.filter((d) => d.subjects.filter((id) => d.fighters[id].onScreen >= CRULE.onScreen).length < 2);
      if (pair.length > 4 && halfPair.length > pair.length * 0.6)
        add('shot-target-off-screen', 'warn', s.id, s.start, s.end, `${s.id}: the shot asks for two subjects but only one is in frame`, 'widen the size, raise angle (depth staging) or make it a single');
    }

    // ---- 3. framing size vs intent ----
    const mSize = med(live.map((d) => d.size));
    s.measuredSize = +mSize.toFixed(3);
    if (s.intent && CRULE.sizeBand[s.intent]) {
      const [lo, hi] = CRULE.sizeBand[s.intent];
      s.checks.size = mSize >= lo && mSize <= hi ? 1 : 0;
      if (mSize < lo * 0.75 || mSize > hi * 1.35)
        add('shot-size-vs-intent', 'warn', s.id, s.start, s.end,
          `${s.id}: asks for "${s.intent}" (${lo}-${hi} of the frame height) but measures ${mSize.toFixed(2)}`,
          mSize < lo ? 'lower rig "dist" (0.5-0.75 in 9:16) or raise the fov' : 'raise "dist" or lower the fov: the body is cropped');
    }

    // ---- 6. camera motion: smooth, and clear of geometry ----
    const pans = s.frames.slice(1).map((d) => d.pan);
    s.checks.smooth = 1;
    // a whip: the total turn inside a short window with no cut inside it
    for (let a = 1; a < s.frames.length; a++) {
      const b = Math.min(s.frames.length - 1, a + Math.round(CRULE.whipWindow / STEP));
      let turn = 0, whip = 0;
      for (let k = a; k <= b; k++) { turn += s.frames[k].pan * STEP; whip += s.frames[k].whip * STEP; }
      const held = s.frames.slice(a, b + 1).every((d) => d.subjects.some((id) => d.fighters[id].onScreen >= CRULE.onScreen));
      const cutInside = s.frames.slice(a, b + 1).some((d) => d.cut || shots.some((o) => o.isCut && o.f0 === d.f));
      const hard = turn > CRULE.smearTurn || whip > CRULE.whipTurn;
      if ((hard || turn > CRULE.whipTurn) && !cutInside) {
        const why = `${s.id}: the camera turns ${turn.toFixed(0)}° in ${(b - a + 1) * STEP} frames with no cut (f${s.frames[a].f}-f${s.frames[b].f})`
          + ` — ${whip.toFixed(0)}° of it is not following the subject${held ? '' : ', and the subject leaves the frame'}`;
        if (hard) {
          s.checks.smooth = 0;
          add('shot-whip-without-cut', 'reject', s.id, s.frames[a].t, s.frames[b].t, `${why}: the picture smears`,
            'a turn that big is a CUT, not a move: mark the beat "cut": true, or spread the turn over 0.5 s or more (a whip pan is 3-6 frames and ends on a cut)');
          break;
        }
        add('shot-fast-pan', 'note', s.id, s.frames[a].t, s.frames[b].t, `${why}: fast, but it follows the subject`,
          'fine as a tracking arc; check the still for background smear');
      }
    }
    const jerks = s.frames.slice(2).filter((d, k) => Math.abs(d.pan - s.frames[k + 1].pan) > CRULE.jerk);
    if (jerks.length > 2 && s.checks.smooth) {
      s.checks.smooth = 0.5;
      add('shot-camera-jerk', 'note', s.id, jerks[0].t, jerks[jerks.length - 1].t,
        `${s.id}: the pan rate jumps by more than ${CRULE.jerk}°/frame² on ${jerks.length} frames`, 'ease the move (a spring feel) or cut');
    }
    const inGeo = s.frames.filter((d) => d.nearest < CRULE.nearGeometry);
    s.checks.clear = inGeo.length ? 0 : 1;
    if (inGeo.length) {
      const worst = inGeo.reduce((a, b) => (b.nearest < a.nearest ? b : a));
      const strike = strikes.find((x) => Math.abs(x.t - worst.t) < 0.15);
      const type = s.rig?.type ? `${s.rig.type} ` : '';
      add('shot-camera-in-geometry', 'reject', s.id, inGeo[0].t, inGeo[inGeo.length - 1].t,
        `${s.id}: the ${type}camera passes through geometry (${worst.nearest.toFixed(2)} m from the lens)`
        + (strike ? ` during the strike at f${worst.f}` : ` at f${worst.f}`) + `, ${inGeo.length * STEP} frame(s)`,
        'keep 0.3 m clear of every prop: raise the radius / dist, move the orbit degrees off the prop, or cut around it',
        { worstFrame: worst.f, nearest: worst.nearest, duringStrike: !!strike });
    }
    if (s.frames.some((d) => d.cam.underGround || (d.cam.ground !== null && d.cam.pos[1] < d.cam.ground + 0.08))) {
      const bad = s.frames.find((d) => d.cam.underGround || (d.cam.ground !== null && d.cam.pos[1] < d.cam.ground + 0.08));
      s.checks.clear = 0;
      add('shot-camera-under-ground', 'reject', s.id, bad.t, bad.t, `${s.id}: the lens is at or under the ground at f${bad.f}`, 'raise the camera height / minY, or lower the elevation angle');
    }

    // ---- 7. emotional fit: does the shot family fit the beat it covers? ----
    const hit = strikes.filter((x) => x.t >= s.start && x.t < s.end);
    s.beat = hit.length ? (hit.some((x) => (x.intensity ?? 0) >= 0.6) ? 'decisive' : 'exchange')
      : s.f0 === 0 ? 'hook' : s.start > DUR - 2.5 ? 'aftermath' : live.length && mSize > 0.9 ? 'tension' : 'tension';
    if (hit.length && mSize < 0.2) {
      add('shot-emotion-mismatch', 'warn', s.id, s.start, s.end,
        `${s.id}: a ${s.beat} beat (${hit.map((h) => h.id).join(', ')}) is played at ${(mSize * 100).toFixed(0)}% of the frame height: the blow has no weight`,
        'an impact beat wants the body at 50% or more of the frame (impact-close, impact-zoom)');
    }
  }

  // ---- 4. continuity: the 180° line and the 30° rule, across each cut ----
  const sideAt = (d) => {
    const v = ids.filter((id) => d.fighters[id]?.visible && d.fighters[id].onScreen >= 0.4);
    if (v.length < 2) return 0;
    const A = d.fighters[v[0]].joints.hips, B = d.fighters[v[1]].joints.hips;
    return Math.sign((B[0] - A[0]) * (d.cam.pos[2] - A[2]) - (B[2] - A[2]) * (d.cam.pos[0] - A[0]));
  };
  for (let k = 1; k < shots.length; k++) {
    const prev = shots[k - 1], cur = shots[k];
    if (!cur.isCut || !prev.frames.length || !cur.frames.length) continue;
    const a = prev.frames[prev.frames.length - 1], b = cur.frames[0];
    const sa = sideAt(a), sb = sideAt(b);
    const moved = /orbit|track|anchor/.test(prev.rig?.type ?? '') || /orbit|track|anchor/.test(cur.rig?.type ?? '');
    if (sa && sb && sa !== sb && !moved) {
      cur.checks.continuity = 0;
      add('cut-crosses-the-line', 'warn', cur.id, b.t, b.t, `the cut into ${cur.id} at f${b.f} crosses the 180° line: the fighters swap sides of the screen`,
        'stay on one side (hero: positive angle, foe: negative angle), cross inside a visible orbit, or cut through a neutral profile shot');
    } else cur.checks.continuity = 1;
    const turn = deg(a.cam.dir, b.cam.dir);
    const stepOf = (v) => CRULE.sizeOrder.findIndex((n) => { const [lo, hi] = CRULE.sizeBand[n]; return v >= lo && v <= hi; });
    const sizeJump = Math.abs(stepOf(cur.measuredSize) - stepOf(prev.measuredSize));
    if (turn < CRULE.turn30 && sizeJump < 2 && prev.frames.length * STEP > 4)
      add('cut-under-30-degrees', 'note', cur.id, b.t, b.t, `the cut into ${cur.id} changes the angle by only ${turn.toFixed(0)}° and the size by ${sizeJump} step(s): it reads as a jump cut`,
        'change the angle by 30° or more, or the size by two steps (30-degree rule), or make it a Kurosawa axial cut on a sudden action');
  }

  // ---- 2. action clarity at the strike frames · 5. event timing ----
  const cutFrames = shots.filter((s) => s.isCut).map((s) => s.f0);
  for (const x of strikes) {
    const d = near(x.t);
    const s = shotOf(x.t);
    const q = x.point ? project({ pos: d.cam.pos, rot: d.cam.rot, fov: d.cam.fov, aspect: d.aspect }, x.point) : null;
    const clear = { onScreen: q ? onScreen(q) : null, size: d.size, pan: d.pan, occluded: d.subjects.some((id) => { const b = d.fighters[id].blocked; return b && b.head && b.chest; }) };
    x.shot = s?.id ?? null; x.clarity = clear;
    if (!s) add('strike-not-covered', 'reject', null, x.t, x.t, `${x.id} at f${d.f} falls outside every shot`, 'extend a shot over the blow: the cut must be visible');
    if (q && !onScreen(q) && !d.impactFrame)
      add('strike-off-screen', 'reject', s?.id ?? null, x.t, x.t, `${x.id}: the point of contact is ${q[2] <= 0.02 ? 'BEHIND the lens' : `off screen (${q[0].toFixed(2)}, ${q[1].toFixed(2)})`} at f${d.f}`,
        'the blade must meet the target on a frame the camera can see: frame the contact point (compose "screen"), not the body centre');
    if (clear.occluded)
      add('strike-occluded', 'reject', s?.id ?? null, x.t, x.t, `${x.id}: the fighter is behind a prop on the strike frame f${d.f}`, 'clear the line of sight for the three frames around every contact');
    if (d.size < CRULE.strikeSize && !d.impactFrame)
      add('strike-too-small', 'warn', s?.id ?? null, x.t, x.t, `${x.id}: the subject is ${(d.size * 100).toFixed(0)}% of the frame height on the strike frame f${d.f}`, `a strike reads at ${CRULE.strikeSize * 100}% or more: move in or cut to impact-close`);
    if (d.pan > CRULE.strikePan)
      add('strike-camera-smear', 'warn', s?.id ?? null, x.t, x.t, `${x.id}: the camera turns ${d.pan.toFixed(0)}°/frame on the strike frame f${d.f}`, 'hold the lens through the contact (the punch is enough); whip before or after, never on the frame');
    const cut = cutFrames.find((cf) => cf > d.f && cf - d.f <= CRULE.cutAfterStrike / STEP);
    if (cut !== undefined)
      add('cut-throws-away-the-blow', 'warn', s?.id ?? null, x.t, cut / FPS, `${x.id} at f${d.f} is cut away ${cut - d.f} frame(s) later`,
        'let a blow land: hold 4-8 frames after contact (hit-stop + reaction), then cut; or cut ON the contact frame');
  }

  // ---------- score and proposals ----------
  let penalty = 0;
  for (const f of findings) penalty += SEV_W[f.sev] ?? 0;
  const score = Math.max(0, +(10 - penalty / Math.max(1, shots.length / 2)).toFixed(1));
  for (const s of shots) {
    s.findings = findings.filter((f) => f.shot === s.id);
    s.rejects = s.findings.filter((f) => f.sev === 'reject').length;
    s.warns = s.findings.filter((f) => f.sev === 'warn').length;
    s.verdict = s.rejects ? 'REJECTED' : s.warns ? 'pass with notes' : 'passed';
    if (s.rejects) s.alternatives = propose(s, LIB, vertical);
    delete s.frames;
  }
  const rejects = findings.filter((f) => f.sev === 'reject').length;
  return { shots, findings, strikes, score, vertical,
    verdict: rejects ? 'REJECTED' : findings.some((f) => f.sev === 'warn') ? 'pass with notes' : 'passed', rejects };
}

/** the nearest passing alternative from library/shots.json for a shot that was rejected */
export function propose(shot, LIB, vertical) {
  const key = vertical ? '9x16' : '16x9';
  const beat = shot.beat ?? 'exchange';
  const want = LIB.beat_map?.[beat] ?? LIB.beat_map?.exchange ?? [];
  const bad = new Set(shot.findings.filter((f) => f.sev === 'reject').map((f) => f.check));
  const sizeWanted = shot.intent && CRULE.sizeBand[shot.intent] ? CRULE.sizeBand[shot.intent] : [0.33, 0.95];
  const mid = (sizeWanted[0] + sizeWanted[1]) / 2;
  const cands = [];
  for (const c of LIB.shots ?? []) {
    const rig = (vertical ? c.rig : c.rig_16x9 ?? c.rig) ?? null;
    if (!rig || c.engine !== 'ready') continue;
    const h = (c.measured?.[key]?.far_subject_height_pct ?? null);
    const size = h === null ? null : h / 100;
    let why = [];
    let s = 0;
    if (want.includes(c.id)) { s += 3; why.push(`the beat map lists it for "${beat}"`); }
    else if (c.family && beat.startsWith(c.family.slice(0, 4))) s += 1;
    if (size !== null) {
      if (size >= sizeWanted[0] * 0.8 && size <= sizeWanted[1] * 1.25) { s += 2; why.push(`measured ${h}% of the frame height fits "${shot.intent ?? beat}"`); }
      s -= Math.min(2, Math.abs(size - mid));
    }
    // the reason the shot was rejected decides what the alternative must avoid
    if (bad.has('shot-camera-in-geometry') || bad.has('shot-camera-under-ground')) {
      if (rig.type === shot.rig?.type && rig.type === 'orbit') { s -= 2; why.push('(same orbit family: check the radius)'); }
      if ((rig.radius ?? rig.dist ?? 1) >= (shot.rig?.radius ?? shot.rig?.dist ?? 0)) { s += 1.5; why.push('stands further off the props'); }
      if ((rig.elevation ?? 0) > (shot.rig?.elevation ?? 0)) { s += 0.5; why.push('looks down, over the props'); }
    }
    if (bad.has('shot-whip-without-cut')) {
      if (['locked', 'dolly', 'crane'].includes(rig.feel ?? c.feel)) { s += 1.5; why.push(`its feel is "${rig.feel ?? c.feel}": it cannot whip`); }
      if ((c.behaviours ?? rig.behaviours ?? []).length === 0) s += 0.5;
    }
    if (bad.has('shot-subject-off-screen') || bad.has('strike-off-screen')) {
      if (rig.type === 'frame' || rig.type === 'face') { s += 1.5; why.push('a frame rig keeps the subject composed by construction'); }
    }
    if (bad.has('shot-subject-occluded')) {
      if ((rig.elevation ?? 0) >= 8) { s += 1; why.push('a higher elevation clears foreground props'); }
    }
    // the 180° line: keep the side of the failing shot
    if (shot.rig?.angle !== undefined && rig.angle !== undefined && Math.sign(rig.angle) === Math.sign(shot.rig.angle)) { s += 0.5; why.push('same side of the 180° line'); }
    cands.push({ id: c.id, name: c.name, family: c.family, emotion: c.emotion, size: size, score: +s.toFixed(2),
      rig, why: why.join('; ') || `closest ${c.family} shot for this beat` });
  }
  cands.sort((a, b) => b.score - a.score);
  return cands.slice(0, 3).map((c) => ({ ...c, paste: `library/shots.json → shots[id=${c.id}] → ${vertical ? 'rig' : 'rig_16x9'}` }));
}

// ---------- report ----------
export function cameraReport(R, name) {
  const L = [];
  L.push(`# CAMERA CHECK ${name}: ${R.verdict} · ${R.score}/10`, '');
  L.push(`${R.shots.length} shot(s) · ${R.strikes.length} strike(s) · ${R.findings.filter((f) => f.sev === 'reject').length} reject, `
    + `${R.findings.filter((f) => f.sev === 'warn').length} warn, ${R.findings.filter((f) => f.sev === 'note').length} note`, '');
  L.push('| Shot | frames | size | verdict | why |', '|---|---|---|---|---|');
  for (const s of R.shots) L.push(`| ${s.id} ${s.name ?? ''} | ${s.f0}-${s.f1} | ${s.measuredSize ?? '-'} ${s.intent ? `(asks ${s.intent})` : ''} | ${s.verdict} | ${s.findings.map((f) => f.check).join(', ') || '-'} |`);
  L.push('');
  for (const f of R.findings) {
    L.push(`**${f.sev.toUpperCase()} ${f.check}** (${f.shot ?? '-'}, f${f.f0}${f.f1 !== f.f0 ? `-f${f.f1}` : ''}): ${f.msg}`);
    L.push(`  - fix: ${f.fix}`);
  }
  for (const s of R.shots.filter((x) => x.alternatives?.length)) {
    L.push('', `### ${s.id} was rejected — nearest passing alternatives from library/shots.json`);
    for (const a of s.alternatives) L.push(`- **${a.id}** (${a.name}; ${a.emotion}) — ${a.why}. Paste: ${a.paste}`);
  }
  L.push('', '_Measured by tools/camera_check.mjs (docs/ARCHITECTURE.md §Camera Director). What it cannot judge — taste, '
    + 'silhouette, line of action — look at the stills._');
  return L.join('\n');
}

// ---------- CLI: measure the film ourselves ----------
if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
  const flag = (n) => args.includes('--' + n);
  const filmPath = args.find((a) => a.endsWith('.json'));
  if (!filmPath) { console.error('usage: node tools/camera_check.mjs film/<name>.json [--step N] [--json] [--quiet]'); process.exit(2); }
  const { chromium } = require('playwright');
  const { serve } = await import('../engine/serve.mjs');
  const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
  const NAME = path.basename(filmPath, '.json');
  const FPS = film.fps ?? 24, NF = Math.round(film.duration * FPS);
  const VERT = film.format === 'vertical' && !flag('horizontal');
  const STEP = Math.max(1, +opt('step', 1));
  const server = await serve(0);
  const port = server.address().port;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: VERT ? { width: 720, height: 1280 } : { width: film.width ?? 1280, height: film.height ?? 720 } });
  page.on('pageerror', (e) => console.error('PAGE ERROR:', e.message));
  const pagePath = opt('page', film.page ?? 'engine/index.html');
  await page.goto(`http://localhost:${port}/${pagePath}?render=1&film=/${filmPath}${VERT ? '&aspect=vertical' : ''}`);
  await page.waitForFunction('window.READY === true', null, { timeout: 600000 });
  if (!(await page.evaluate(() => !!window.AUDIT))) {
    console.error(`✗ ${pagePath} has no camera hooks (window.AUDIT): add installAudit(...) from engine/audit-hooks.js`);
    await browser.close(); server.close(); process.exit(2);
  }
  const META = await page.evaluate(() => window.AUDIT.meta);
  const EVENTS = await page.evaluate(() => window.EVENTS ?? null);
  const F = [];
  for (let i = 0; i < NF; i += STEP) F.push(await page.evaluate((t) => window.AUDIT.at(t), i / FPS));
  await browser.close();
  server.close();
  const R = evaluateCamera({ F, META, EVENTS, film, STEP });
  fs.mkdirSync('output', { recursive: true });
  fs.writeFileSync(`output/${NAME}.camera-check.json`, JSON.stringify(R, null, 1));
  const md = cameraReport(R, NAME);
  fs.writeFileSync(`output/${NAME}.camera-check.md`, md);
  if (flag('json')) console.log(JSON.stringify(R, null, 1));
  else if (!flag('quiet')) {
    console.log(`\nCAMERA CHECK ${NAME}: ${R.verdict} · ${R.score}/10 · ${R.shots.length} shots, ${R.strikes.length} strikes`);
    for (const s of R.shots) console.log(`  ${s.id.padEnd(4)} f${String(s.f0).padStart(4)}-${String(s.f1).padEnd(4)} size ${String(s.measuredSize ?? '-').padEnd(5)} ${s.verdict}`);
    for (const f of R.findings) console.log(`${f.sev.toUpperCase().padEnd(7)} ${(f.shot ?? '-').padEnd(4)} f${String(f.f0).padStart(4)}  ${f.check.padEnd(26)} ${f.msg}`);
    for (const s of R.shots.filter((x) => x.alternatives?.length)) {
      console.log(`\n${s.id} rejected → nearest passing alternative(s) in library/shots.json:`);
      for (const a of s.alternatives) console.log(`  ${a.id.padEnd(22)} ${a.why}`);
    }
    console.log(`\nreport: output/${NAME}.camera-check.md  (data: output/${NAME}.camera-check.json)`);
  }
  process.exit(R.rejects ? 1 : 0);
}

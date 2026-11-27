// KUROKO (黒衣) — the camera system. Named after kabuki's black-clad stagehands who move everything unseen.
//
// A shot can use hand-made keyframes ("camera": [...]) or a KUROKO rig ("rig": {...}).
// A rig frames CHARACTERS BY NAME (not typed coordinates), reacts to their motion with BEHAVIOURS,
// and moves with a FEEL (a spring that gives the camera weight: locked, dolly, crane, handheld, torpedo).
// Everything is deterministic: the spring is integrated on a fixed 240 Hz grid from the start of the shot.
//
// Pure module (no DOM): used by the browser engine and by Node tools.

// ---------------------------------------------------------------- vector helpers
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const len = (a) => Math.hypot(a[0], a[1], a[2]);
const norm = (a) => { const l = len(a) || 1; return mul(a, 1 / l); };
const lerp = (a, b, k) => add(a, mul(sub(b, a), k));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const smooth01 = (k) => { k = clamp(k, 0, 1); return k * k * (3 - 2 * k); };
const DEG = Math.PI / 180;

// ---------------------------------------------------------------- feels (camera weight)
// f = natural frequency (Hz): how quickly it catches up. z = damping: 1 = no overshoot, < 1 = overshoot.
// noise = handheld wobble (metres, degrees, Hz). maxSpeed = metres per second cap.
export const FEELS = {
  // f Hz, z damping (from the fight-camera research: locked ~0.1 s settle, dolly ~0.35 s, crane ~1 s, handheld ~5% overshoot, torpedo ~8%)
  locked:   { f: 6.0, z: 1.0,  noise: null,                                       maxSpeed: 12 },
  dolly:    { f: 1.8, z: 1.0,  noise: null,                                       maxSpeed: 4 },
  crane:    { f: 0.7, z: 1.1,  noise: { pos: 0.003, rot: 0.0, hz: 0.2 },          maxSpeed: 2.5 },
  handheld: { f: 2.5, z: 0.7,  noise: { pos: 0.006, rot: 0.3, hz: 1.1, tremor: 0.06 }, maxSpeed: 5 },
  torpedo:  { f: 4.0, z: 0.62, noise: { pos: 0.0, rot: 0.05, hz: 8 },              maxSpeed: 10 },
};
export const LOOKAHEAD = 3 / 24;   // offline advantage: react ~3 frames BEFORE the motion, like an operator who knows the choreography

// ---------------------------------------------------------------- behaviours (motion-reactive)
// Each reads motion signals and returns modifiers: dist (×), fov (+deg), up (+m), roll (+deg), look (+[x,y,z]).
export const BEHAVIOURS = {
  // Retreat / jump back → pull back to reveal the move (film grammar: show the space being given up).
  reveal: (s) => { const k = smooth01((-s.approachMin - 0.6) / 1.6); return { dist: 1 + 0.38 * k, fov: 4 * k }; },
  // Lunge → push in with the attacker.
  push: (s) => { const k = smooth01((s.approachMax - 0.8) / 1.8); return { dist: 1 - 0.2 * k, fov: -3 * k }; },
  // Jump → camera rises with the body.
  jump: (s) => { const k = smooth01((s.riseMax - 0.4) / 1.2); return { up: 0.45 * k, look: [0, 0.2 * k, 0] }; },
  // Impact → a fast punch-in that recovers (rises in 2 frames, decays over ~10).
  // Stagger / reel → Dutch tilt.
  dutch: (s) => ({ roll: 7 * smooth01((s.staggerMax - 0.35) / 0.4) }),
  // Fast blade → look leans toward the swing.
  whip: (s) => { const k = smooth01((s.armMax - 6) / 8); return { look: mul(s.attackDir, 0.25 * k) }; },
  // Lead room: frame ahead of whoever is moving.
  // (cap scales with the shot: 0.35 m was nothing in a wide frame; ~12% of the camera distance keeps the room visible)
  lead: (s) => ({ look: mul(s.moveDir, clamp(s.speedMax * 0.12, 0, Math.max(0.35, 0.12 * (s.dist ?? 3)))) }),
};
export const DEFAULT_BEHAVIOURS = ['reveal', 'push', 'jump', 'dutch', 'lead'];
// Impulses (added AFTER the spring so hits land on their exact frame): impact punch-in + recoil.

// ---------------------------------------------------------------- subjects
/** Body points from pure motion functions: motions = { id: (t) => pose }. */
export function makeSubjects(motions) {
  const pt = (id, part, t) => {
    const p = motions[id](t);
    const f = [Math.sin(p.ry), 0, Math.cos(p.ry)];
    const hips = add([p.x, p.y + 0.92 - (p.crouch ?? 0), p.z], mul(f, (p.weight ?? 0) * (p.stance ?? 0.12) * 0.35));
    const lean = Math.sin(p.tx ?? 0);
    if (part === 'root') return [p.x, p.y, p.z];
    if (part === 'hips') return hips;
    if (part === 'head') return add(hips, add([0, 0.72, 0], mul(f, lean * 0.7)));
    if (part === 'hand') return add(hips, add([0, 0.3, 0], mul(f, 0.45 + lean * 0.3)));
    return add(hips, add([0, 0.42, 0], mul(f, lean * 0.4)));       // chest (default)
  };
  return (name, t) => {
    const [id, part] = name.split('.');
    if (!motions[id]) throw new Error(`KUROKO: unknown subject "${name}"`);
    return pt(id, part ?? 'chest', t);
  };
}

// ---------------------------------------------------------------- signals
function signals(ctx, t, ids) {
  const { motions, subject, pair, impacts } = ctx;
  const h = 1 / 24;
  let approachMin = 0, approachMax = 0, riseMax = 0, staggerMax = 0, armMax = 0, speedMax = 0;
  let moveDir = [0, 0, 0], attackDir = [0, 0, 0];
  for (const id of ids) {
    const a = motions[id](t), b = motions[id](t - h);
    const vel = [(a.x - b.x) / h, 0, (a.z - b.z) / h];
    const speed = len(vel);
    const other = pair[id];
    let approach = 0;
    if (other) {
      const o = motions[other](t);
      const toward = norm([o.x - a.x, 0, o.z - a.z]);
      approach = vel[0] * toward[0] + vel[2] * toward[2];
      const arm = Math.hypot(a.rsx - b.rsx, a.rex - b.rex, (a.rwx ?? 0) - (b.rwx ?? 0)) / h;
      if (arm > armMax) { armMax = arm; attackDir = toward; }
    }
    approachMin = Math.min(approachMin, approach);
    approachMax = Math.max(approachMax, approach);
    const rise = ((a.y - (a.crouch ?? 0)) - (b.y - (b.crouch ?? 0))) / h;
    riseMax = Math.max(riseMax, rise);
    staggerMax = Math.max(staggerMax, clamp(-(a.weight ?? 0), 0, 1) * clamp(-(a.tx ?? 0) * 3 + Math.abs(a.tz ?? 0) * 2, 0, 1));
    if (speed > speedMax) { speedMax = speed; moveDir = norm(vel); }
  }
  let impactPulse = 0;
  for (const ti of impacts) {
    const d = (t - ti) * 24;                                       // frames since impact
    if (d > -2 && d < 12) impactPulse = Math.max(impactPulse, d < 0 ? (d + 2) / 2 : Math.exp(-d / 4));
  }
  return { approachMin, approachMax, riseMax, staggerMax, armMax, speedMax, moveDir, attackDir, impactPulse };
}

// ---------------------------------------------------------------- rigs (target camera before the spring)
const SIZES = { wide: 7.0, full: 3.2, medium: 2.0, close: 0.85, extreme: 0.38 };   // width of frame (m) for one subject

function rigTarget(rig, t, ctx, shot) {
  const S = ctx.subject;
  const vfov = rig.fov ?? 34;
  const hfov = 2 * Math.atan(Math.tan((vfov * DEG) / 2) * ctx.aspect);
  const u = clamp((t - shot.start) / (shot.end - shot.start), 0, 1);
  const subjects = rig.subjects ?? (rig.subject ? [rig.subject] : []);

  if (rig.type === 'frame') {
    const pts = subjects.map((n) => S(n, t));
    const mid = mul(pts.reduce((a, b) => add(a, b), [0, 0, 0]), 1 / pts.length);
    let axis = pts.length > 1 ? norm([pts[1][0] - pts[0][0], 0, pts[1][2] - pts[0][2]]) : [1, 0, 0];
    if (pts.length === 1) {                                         // single subject: look at its front
      const id = subjects[0].split('.')[0];
      const p = ctx.motions[id](t);
      axis = [Math.cos(p.ry), 0, -Math.sin(p.ry)];
    }
    const sep = pts.length > 1 ? len(sub(pts[1], pts[0])) : 0;
    // frame fill (research spec): width = separation + 2 × 0.55 m arm/sword margin, height by shot size
    const size = rig.size ?? (pts.length > 1 ? 'full' : 'medium');
    // azimuth: 0 = profile, + toward subject[0]'s back. In vertical video the default is an over-the-shoulder
    // 55° (depth staging), and only the separation seen across the screen counts toward the width.
    const vertical = ctx.aspect < 1;
    const ang = clamp(rig.angle ?? (vertical && pts.length > 1 ? 55 : 0), -75, 75) * DEG;
    const W = pts.length > 1 ? sep * Math.abs(Math.cos(ang)) + 1.1 : (SIZES[size] ?? 2);
    const Hh = { wide: 4, full: 1.9, medium: 1.0, close: 0.45, extreme: 0.2 }[size] ?? 1.9;
    const dist = Math.max(W / (2 * 0.62 * Math.tan(hfov / 2)), Hh / (2 * 0.7 * Math.tan((vfov * DEG) / 2)), 0.8) * (rig.dist ?? 1);
    let n = [-axis[2], 0, axis[0]];                                 // perpendicular to the subjects' line
    if (rig.side === 'right') n = mul(n, -1);
    n = norm(add(mul(n, Math.cos(ang)), mul(axis, -Math.sin(ang))));
    const el = (rig.elevation ?? 4) * DEG;                          // -5…+15° recommended
    const pos = add(mid, add(mul(n, dist * Math.cos(el)), [0, dist * Math.sin(el) + (rig.height ?? 0), 0]));
    const look = add(mid, [0, rig.lookUp ?? -0.05, 0]);
    return { pos, look, fov: vfov, dist, center: mid };
  }
  if (rig.type === 'orbit') {
    const c = rig.target ? S(rig.target, t) : mul(add(S(subjects[0], t), S(subjects[1], t)), 0.5);
    const deg = ((rig.deg0 ?? 0) + ((rig.deg1 ?? 90) - (rig.deg0 ?? 0)) * u) * DEG;
    const r = rig.radius ?? 3.5;
    const pos = add(c, [Math.sin(deg) * r, rig.height ?? 0.2, Math.cos(deg) * r]);
    return { pos, look: c, fov: vfov, dist: r, center: c };
  }
  if (rig.type === 'track') {                                       // torpedo / chase: ride with a subject
    const id = subjects[0].split('.')[0];
    const p = ctx.motions[id](t);
    const c = S(subjects[0], t);
    const f = [Math.sin(p.ry), 0, Math.cos(p.ry)], r = [Math.cos(p.ry), 0, -Math.sin(p.ry)];
    const o = rig.offset ?? [0.7, 0.25, -2.4];                      // [right, up, back(-)/front(+)]
    const pos = add(c, add(add(mul(r, -o[0]), [0, o[1], 0]), mul(f, o[2])));
    const ahead = add(c, mul(f, rig.lookAhead ?? 1.2));
    return { pos, look: ahead, fov: vfov, dist: len(o), center: c };
  }
  if (rig.type === 'face') {                                        // face-snap close-up
    const id = subjects[0].split('.')[0];
    const p = ctx.motions[id](t);
    const head = S(`${id}.head`, t);
    const ang = p.ry + (rig.angle ?? 25) * DEG;
    const d = rig.dist ?? 0.9;
    const pos = add(head, [Math.sin(ang) * d, rig.height ?? 0.02, Math.cos(ang) * d]);
    return { pos, look: add(head, [0, -0.03, 0]), fov: rig.fov ?? 24, dist: d, center: head };
  }
  if (rig.type === 'anchor') {                                      // one continuous take through beats
    const beats = rig.beats;
    let b = beats[0];
    for (const x of beats) if (t >= x.t) b = x;
    return rigTarget({ ...b, behaviours: [] }, t, ctx, shot);
  }
  if (rig.type === 'blade') {                                       // rides the blade (needs a live blade frame)
    const fr = ctx.bladeFrame?.(t);
    if (!fr) return rigTarget({ type: 'frame', subjects }, t, ctx, shot);
    const o = rig.offset ?? [-0.25, 0.08, 0.18];                    // along blade, up, side (blade space)
    const pos = add(fr.origin, add(add(mul(fr.x, o[0]), mul(fr.y, o[1])), mul(fr.z, o[2])));
    return { pos, look: add(fr.origin, mul(fr.x, rig.lookAlong ?? 0.6)), fov: rig.fov ?? 30, dist: 0.4, center: fr.origin };
  }
  throw new Error(`KUROKO: unknown rig type "${rig.type}"`);
}

function applyBehaviours(rig, target, t, ctx, ids) {
  const names = rig.behaviours ?? DEFAULT_BEHAVIOURS;
  if (!names.length) return { ...target, roll: rig.roll ?? 0 };
  const s = { ...signals(ctx, t + LOOKAHEAD, ids), dist: target.dist };
  let dist = 1, fov = 0, up = 0, roll = rig.roll ?? 0, look = [0, 0, 0];
  for (const n of names) {
    const m = BEHAVIOURS[n](s);
    if (m.dist) dist *= m.dist;
    if (m.fov) fov += m.fov;
    if (m.up) up += m.up;
    if (m.roll) roll += m.roll;
    if (m.look) look = add(look, m.look);
  }
  dist = clamp(dist, 0.6, 1.6); fov = clamp(fov, -8, 8); roll = clamp(roll, -10, 10);
  const offset = sub(target.pos, target.center);
  const pos = add(add(target.center, mul(offset, dist)), [0, up, 0]);
  return { pos, look: add(target.look, look), fov: target.fov + fov, roll };
}

// ---------------------------------------------------------------- the camera operator
/**
 * makeKuroko({ motions, impacts, pair, aspect, bladeFrame }) → { at(shot, t) → { pos, look, fov, roll } }
 * motions: { id: (t) => pose }, impacts: [seconds], pair: { id: opponentId }.
 */
export function makeKuroko(opts) {
  const ctx = { ...opts, subject: makeSubjects(opts.motions) };
  const cache = new Map();
  const H = 1 / 240;

  function target(shot, t) {
    const rig = shot.rig;
    const ids = [...new Set((rig.subjects ?? (rig.subject ? [rig.subject] : (rig.beats ?? []).flatMap((b) => b.subjects ?? [b.subject])))
      .filter(Boolean).map((n) => n.split('.')[0]))];
    const raw = rigTarget(rig, t, ctx, shot);
    return applyBehaviours(rig, raw, t, ctx, ids);
  }
  const pack = (c) => [...c.pos, ...c.look, c.fov, c.roll];

  function at(shot, t) {
    const feel = FEELS[shot.rig.feel ?? 'dolly'];
    const w = 2 * Math.PI * feel.f, z = feel.z;
    let st = cache.get(shot.id);
    const stepOf = (time) => Math.floor((time - shot.start) / H + 1e-9);
    const want = Math.max(0, stepOf(t));
    if (!st || st.k > want) {                                         // start of shot: 1 s pre-roll so it opens settled
      const x0 = pack(target(shot, shot.start - 1));
      st = { k: -240, x: x0, v: x0.map(() => 0), g: x0, gv: x0.map(() => 0) };
    }
    const ff = shot.rig.feedForward ?? 1;                             // 0 = the old lagging look point
    while (st.k < want) {                                             // fixed-step spring integration
      st.k++;
      const tt = shot.start + st.k * H;
      const goal = pack(target(shot, tt));
      for (let i = 0; i < goal.length; i++) st.gv[i] += ((goal[i] - st.g[i]) / H - st.gv[i]) * 0.08;   // smoothed goal speed
      st.g = goal;
      for (let i = 0; i < st.x.length; i++) {
        const wi = i >= 3 && i < 6 ? w * 1.5 : w;                    // look point 1.5× stiffer: subject never slides out
        const zi = i >= 6 ? 1 : z;                                    // fov and roll never overshoot
        // feed-forward on the LOOK point: a spring chasing a moving goal trails it by speed × 2ζ/ω (2 m at 30 m/s on
        // a dolly). An operator who knows the choreography aims where the subject IS; the body still lags (weight).
        const gi = i >= 3 && i < 6 ? goal[i] + ff * st.gv[i] * (2 * zi / wi) : goal[i];
        const a = wi * wi * (gi - st.x[i]) - 2 * zi * wi * st.v[i];
        st.v[i] += a * H;
        st.x[i] += st.v[i] * H;
      }
      const sp = Math.hypot(st.v[0], st.v[1], st.v[2]);               // speed cap (metres/second)
      if (sp > feel.maxSpeed) for (let i = 0; i < 3; i++) st.v[i] *= feel.maxSpeed / sp;
    }
    cache.set(shot.id, st);
    let [px, py, pz, lx, ly, lz, fov, roll] = st.x;
    // --- impulses after the spring: impact punch-in (2 f) + recoil (4 f) + settle (10 f)
    for (const ti of ctx.impacts) {
      const d = (t - ti) * 24;
      if (d < -2 || d > 16) continue;
      const k = d < 0 ? (d + 2) / 2 : d < 4 ? 1 - d / 4 * 1.6 : -0.6 * Math.exp(-(d - 4) / 4);
      fov -= 7 * k;                                                   // punch in, then a small recoil out
      const dir = norm([lx - px, ly - py, lz - pz]);
      px += dir[0] * 0.07 * k; py += dir[1] * 0.07 * k; pz += dir[2] * 0.07 * k;
    }
    // --- handheld / drift noise, seeded, angles scaled by lens so it reads the same on screen
    if (feel.noise) {
      const n = feel.noise, q = t * n.hz * 2 * Math.PI, lens = fov / 36;
      const wob = (a, b, c) => Math.sin(q * a + b) * 0.6 + Math.sin(q * c + b * 1.7) * 0.4;
      px += n.pos * wob(1.0, 1.3, 2.31); py += n.pos * wob(0.83, 4.1, 1.93); pz += n.pos * wob(1.17, 2.7, 2.71);
      roll += n.rot * lens * wob(0.71, 0.4, 1.61);
      if (n.tremor) { lx += n.tremor * 0.02 * Math.sin(t * 2 * Math.PI * 7.3); ly += n.tremor * 0.02 * Math.sin(t * 2 * Math.PI * 8.1 + 1); }
    }
    // --- guards: minimum distance from bodies, camera above the ground
    for (const id of Object.keys(ctx.motions)) {
      const c = ctx.subject(id, t), off = [px - c[0], py - c[1], pz - c[2]], dd = len(off);
      const minD = shot.rig.type === 'face' || shot.rig.type === 'blade' ? 0.3 : 0.8;
      if (dd < minD && dd > 1e-6) { const k2 = minD / dd; px = c[0] + off[0] * k2; py = c[1] + off[1] * k2; pz = c[2] + off[2] * k2; }
    }
    py = Math.max(0.15, py);
    return { pos: [px, py, pz], look: [lx, ly, lz], fov: clamp(fov, 10, 80), roll };
  }
  return { at, subject: ctx.subject };
}

export const RIG_TYPES = ['frame', 'orbit', 'track', 'face', 'anchor', 'blade'];

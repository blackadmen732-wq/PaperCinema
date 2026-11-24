// FOOT LOCK + WEIGHT (opt-in: film "motion": { "lockFeet": true })
//
// The problem it fixes: every pose is a joint angle, so the legs are drawn from the hips down and the
// feet go wherever the hips take them. A travelling body therefore skates: the audit (tools/audit.mjs,
// rule A1) sees a "planted" foot slide metres across the ground.
//
// What this does, in one precomputed pass over the whole performance:
//   1. SAMPLE the finished motion (after the anime layer) at `rate` Hz: root x/y/z, facing, stance,
//      crouch, weight, stride/phase — and from those the *nominal* world position of each foot, i.e.
//      exactly where engine/figure.js solveLegs would put it today.
//   2. CONTACTS. A foot is in the air when the root is off the ground (a jump) or when the body is
//      travelling faster than a foot can push (`runSpeed`): that is a lunge or a leap, not a step.
//      Everything else is ground time, and ground time is cut into CONTACTS: the longest run of frames
//      whose nominal foot positions all sit within `tol` of one point. That one point is the plant —
//      the mean of the nominal path, so the body passes *over* the foot instead of the foot chasing
//      the body (that is also how a sprint is caught: you plant ahead and rotate over it).
//   3. STEPS. Between two contacts the foot swings for `swing` seconds: lift, travel, plant, on a
//      smoothstep with a sine arc. The two feet are staggered so they do not leave the ground together
//      at walking speed.
//   4. WEIGHT. With the feet pinned, the hips are no longer free:
//      · reach — if a pinned foot is further from its hip than the leg is long, the hips must DROP
//        (`crouch`) until the leg reaches. A long stride therefore sinks the body by itself.
//      · support polygon — the span between the planted feet (plus the soles). When the centre of
//        mass leaves it the body is falling: it leans the way it is falling (`rx`/`rz`, a rotation
//        about the ground, i.e. about the feet), the hips drop further, and the next plant is thrown
//        `lead` ahead along the travel direction to catch it.
//
// Everything is a pure function of t: the plan is built once from a uniform grid, and evaluation only
// looks it up, so any frame still renders on its own (window.renderAt(t)) and stills match the video.
import { LEG } from './figure.js';

export const FOOTLOCK = {
  rate: 120,         // planning grid (Hz)
  tol: 0.13,         // how far the nominal foot may wander from the plant before the foot must step (m)
  swing: 0.15,       // how long a step takes (s)
  lift: 0.12,        // peak foot lift in a step (m), scaled by step length
  runSpeed: 4.0,     // above this ground speed the feet are off the ground (a lunge / leap), m/s
  air: 0.03,         // root height that counts as airborne (m)
  flight: 0.2,       // how high the feet come off the ground in a lunge / leap (m)
  ramp: 0.07,        // push-off / reach-down time at the two ends of a flight (s)
  lead: 0.08,        // catch step: throw the plant this many seconds of travel ahead
  lean: 0.55,        // falling lean per metre of centre-of-mass overhang (rad/m)
  drop: 0.3,         // hip drop per metre of overhang (m/m)
  maxLean: 0.22, maxDrop: 0.3,
  smooth: 0.08,      // smoothing window for the hip/lean pass (s)
  sole: [0.055, 0.11],   // half width / half length of a sole: the support polygon of one foot (m)
};

const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const ss = (u) => u * u * (3 - 2 * u);

/** Where solveLegs would put a foot today, in the world. side: -1 right (leads), +1 left. */
function nominal(p, side) {
  const front = side < 0;
  let lz = (front ? 1 : -1) * p.stance / 2, ly = LEG.footY;
  if (p.stride > 0) {
    const ph = p.phase + (front ? 0 : Math.PI);
    lz += Math.sin(ph) * p.stride / 2;
    ly += Math.max(0, Math.cos(ph)) * 0.07;
  }
  const lx = side * 0.1, c = Math.cos(p.ry), s = Math.sin(p.ry);
  return [p.x + lx * c + lz * s, p.y + ly, p.z - lx * s + lz * c];
}

/**
 * Wrap a motion (t) => pose so the feet are planted in the world and the body carries its weight.
 * @param motion  the finished motion function, e.g. from makeMotion()
 * @param dur     film duration (s)
 * @param opts    true, or overrides of FOOTLOCK
 * @returns (t) => pose, with `_feet` = { r: [x,y,z], l: [x,y,z], rc, lc } (rc/lc = 1 while planted)
 */
export function lockFeet(motion, dur, opts = {}) {
  const O = { ...FOOTLOCK, ...(opts === true ? {} : opts) };
  const RATE = O.rate, DT = 1 / RATE, N = Math.max(2, Math.ceil(dur * RATE) + 1);
  const P = [];                                       // the sampled performance
  for (let i = 0; i < N; i++) P.push(motion(i * DT));
  const nomR = P.map((p) => nominal(p, -1)), nomL = P.map((p) => nominal(p, 1));
  // ground speed of the root, central difference
  const spd = P.map((p, i) => {
    const a = P[Math.max(0, i - 1)], b = P[Math.min(N - 1, i + 1)];
    const n = Math.min(N - 1, i + 1) - Math.max(0, i - 1);
    return n ? Math.hypot(b.x - a.x, b.z - a.z) / (n * DT) : 0;
  });
  const air = P.map((p, i) => p.y > O.air || spd[i] > O.runSpeed);
  // velocity direction, for the catch step
  const vel = P.map((p, i) => {
    const a = P[Math.max(0, i - 1)], b = P[Math.min(N - 1, i + 1)];
    const n = (Math.min(N - 1, i + 1) - Math.max(0, i - 1)) * DT;
    return n ? [(b.x - a.x) / n, (b.z - a.z) / n] : [0, 0];
  });
  const swingN = Math.max(1, Math.round(O.swing * RATE));

  /** Cut the ground time into contacts: [{ a, b, pos }] (a..b inclusive, pos = the plant). */
  function contacts(nom, firstEnd) {
    const out = [];
    let i = 0;
    while (i < N) {
      if (air[i]) { i++; continue; }
      let sx = 0, sz = 0, n = 0, j = i - 1;
      const cap = out.length === 0 && firstEnd != null ? firstEnd : N - 1;
      for (let k = i; k <= Math.min(cap, N - 1); k++) {
        if (air[k]) break;
        const mx = (sx + nom[k][0]) / (n + 1), mz = (sz + nom[k][2]) / (n + 1);
        let bad = false;                               // every frame of the contact must stay near the plant
        for (let q = i; q <= k; q++) if (Math.hypot(nom[q][0] - mx, nom[q][2] - mz) > O.tol) { bad = true; break; }
        if (bad) break;
        sx += nom[k][0]; sz += nom[k][2]; n++; j = k;
      }
      if (n === 0) { i++; continue; }                  // one frame cannot even hold itself: treat as air
      const mid = (i + j) >> 1;
      out.push({ a: i, b: j, pos: [sx / n + vel[mid][0] * O.lead, LEG.footY, sz / n + vel[mid][1] * O.lead] });
      i = j + 1 + swingN;
    }
    return out;
  }
  const cR = contacts(nomR, null);
  // stagger the left foot: its first contact ends halfway through the right foot's first one
  const cL = contacts(nomL, cR.length ? Math.max(0, (cR[0].a + cR[0].b) >> 1) : null);

  /** Fill a per-sample path: planted inside a contact, a lifted arc between two, nominal in the air. */
  function path(cs, nom) {
    const out = nom.map((p) => [p[0], p[1], p[2], 0]);
    for (let k = 0; k < cs.length; k++) {
      const c = cs[k];
      for (let i = c.a; i <= c.b; i++) out[i] = [c.pos[0], c.pos[1], c.pos[2], 1];
      const nx = cs[k + 1];
      if (!nx || nx.a <= c.b + 1) continue;
      const len = Math.hypot(nx.pos[0] - c.pos[0], nx.pos[2] - c.pos[2]);
      const h = clamp(len * 0.28, 0.02, O.lift);
      for (let i = c.b + 1; i < nx.a; i++) {
        if (air[i]) continue;                          // a jump in the middle of a step wins
        const u = ss((i - c.b) / (nx.a - c.b));
        out[i] = [c.pos[0] + (nx.pos[0] - c.pos[0]) * u, LEG.footY + h * Math.sin(Math.PI * u),
          c.pos[2] + (nx.pos[2] - c.pos[2]) * u, 0];
      }
    }
    // FLIGHT: a leap or a lunge. The feet leave the ground (so nothing "planted" can slide), follow the
    // body, and blend out of the last plant and into the next one: push off, trail, reach down, land.
    const rampN = Math.max(1, Math.round(O.ramp * RATE));
    for (let i = 0; i < N;) {
      if (!air[i]) { i++; continue; }
      let j = i; while (j + 1 < N && air[j + 1]) j++;
      const prev = cs.filter((c) => c.b < i).pop(), next = cs.find((c) => c.a > j);
      const len = j - i + 1, r = Math.min(rampN, Math.max(1, len >> 1));
      if (prev && next) {
        // one arc from the foot that pushed off to the foot that lands: eased at both ends, so the
        // foot is already high before it travels (and a "planted" foot never races across the ground)
        const span = Math.hypot(next.pos[0] - prev.pos[0], next.pos[2] - prev.pos[2]);
        const h = clamp(span * 0.12, O.flight, 1.0);
        for (let k = i; k <= j; k++) {
          const u = (k - i + 1) / (len + 1), w = ss(u);
          out[k] = [prev.pos[0] + (next.pos[0] - prev.pos[0]) * w, nom[k][1] + h * Math.sin(Math.PI * u),
            prev.pos[2] + (next.pos[2] - prev.pos[2]) * w, 0];
        }
      } else {
        for (let k = i; k <= j; k++) {                 // no plant on one side: follow the body, lifted
          const up = O.flight * ss(Math.min(1, (k - i + 1) / r, (j - k + 1) / r));
          out[k] = [nom[k][0], nom[k][1] + up, nom[k][2], 0];
        }
      }
      i = j + 1;
    }
    return out;
  }
  const fR = path(cR, nomR), fL = path(cL, nomL);

  // ---- weight: reach (hips must drop to keep a pinned foot) + centre of mass over the support ----
  const maxD = (LEG.thigh + LEG.shin) * 0.985;
  const addC = new Array(N).fill(0), addRx = new Array(N).fill(0), addRz = new Array(N).fill(0);
  for (let i = 0; i < N; i++) {
    const p = P[i], c = Math.cos(p.ry), s = Math.sin(p.ry);
    const hipZ = p.weight * p.stance * 0.35, hipY = LEG.hipY - p.crouch - 0.02;
    let drop = 0;
    const sup = [];                                   // planted feet, in the root's frame
    for (const [f, side] of [[fR[i], -1], [fL[i], 1]]) {
      const dx = f[0] - p.x, dz = f[2] - p.z;
      const lx = dx * c - dz * s, lz = dx * s + dz * c;     // inverse of the y-rotation above
      if (!f[3]) continue;
      sup.push([lx, lz]);
      const h = Math.hypot(lx - side * 0.1, lz - hipZ);
      const reach = f[1] - p.y + Math.sqrt(Math.max(0, maxD * maxD - h * h));
      drop = Math.max(drop, hipY - reach);
    }
    let mz = 0, mx = 0;
    if (sup.length) {                                 // overhang of the centre of mass (above the hips)
      const zs = sup.map((q) => q[1]), xs = sup.map((q) => q[0]);
      const z0 = Math.min(...zs) - O.sole[1], z1 = Math.max(...zs) + O.sole[1];
      const x0 = Math.min(...xs) - O.sole[0], x1 = Math.max(...xs) + O.sole[0];
      mz = hipZ > z1 ? hipZ - z1 : hipZ < z0 ? hipZ - z0 : 0;
      mx = 0 > x1 ? -x1 : 0 < x0 ? -x0 : 0;
    }
    addC[i] = clamp(Math.max(0, drop) + O.drop * Math.abs(mz), 0, O.maxDrop);
    addRx[i] = clamp(O.lean * mz, -O.maxLean, O.maxLean);
    addRz[i] = clamp(-O.lean * mx, -O.maxLean, O.maxLean);
  }
  // smooth the hip/lean pass (a box filter) so a new contact never pops
  const win = Math.max(1, Math.round(O.smooth * RATE));
  const blur = (A) => A.map((_, i) => {
    let s = 0, n = 0;
    for (let k = i - win; k <= i + win; k++) { s += A[clamp(k, 0, N - 1)]; n++; }
    return s / n;
  });
  const sC = blur(addC), sRx = blur(addRx), sRz = blur(addRz);

  const lerp3 = (A, i, j, u) => [A[i][0] + (A[j][0] - A[i][0]) * u, A[i][1] + (A[j][1] - A[i][1]) * u,
    A[i][2] + (A[j][2] - A[i][2]) * u];
  const out = (t) => {
    const p = motion(t);
    const g = clamp(t * RATE, 0, N - 1), i = Math.min(N - 2, Math.floor(g)), u = g - i, j = i + 1;
    p._feet = { r: lerp3(fR, i, j, u), l: lerp3(fL, i, j, u), rc: fR[u < 0.5 ? i : j][3], lc: fL[u < 0.5 ? i : j][3] };
    p.crouch += sC[i] + (sC[j] - sC[i]) * u;
    p.rx += sRx[i] + (sRx[j] - sRx[i]) * u;
    p.rz += sRz[i] + (sRz[j] - sRz[i]) * u;
    return p;
  };
  out.plan = { contactsR: cR, contactsL: cL, rate: RATE, opts: O };
  return out;
}

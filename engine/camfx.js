// CAMERA MOVES on events: the anime camera accents a film asks for by name, timed to the action (Mark, 27 Nov:
// "the camera alive: zoom, twist a little, tracking, like anime"). Pure module (no DOM, no three.js): the browser
// engine (engine/motion.js placeCamera) applies the result after the framing spring and the impact punch, so the
// exported camera (tools/timeline.mjs) and therefore the Blender render carry every move.
//
// film.cameraMoves = [{ move, t | act | at: "contact" (+ "offset" s), ... }]
//   crash   crash zoom: the lens snaps in by "zoom" (default 1.7x) over "in" s (0.1), holds "hold" (0.35), eases
//           back over "out" (0.4; out: 0 = stays in until the next cut).
//   (every move except whip and rack ends at the next hard cut unless it says "across": true)
//   whip    whip pan through a cut: the last "dur"/2 s before t the view swings "deg" (default 60) to one side,
//           the first "dur"/2 s after t it arrives from the other side ("dir" 1 = right, -1 = left). Put t on a cut.
//   dutch   Dutch tilt: roll to "deg" (default 8) over "in" (0.25), hold "hold" (0.6), back over "out" (0.4).
//   breath  handheld breathing between t and "until": a slow, small sway ("amp" degrees, default 0.35).
//   shake   a sharp shake that decays over "dur" (0.35) with "amp" degrees (default 1.2) - for a hit on a
//           non-contact frame (contacts already shake through combat.punch).
//   rack    rack focus: over "dur" s (0.3) the focus moves from actor "from" to actor "to" (focus is exported as
//           frames[].camera.focus_on and Blender keys the depth of field from it).
// Every move is deterministic (seeded by its index), so isolated and sequential renders agree.

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const smooth = (k) => { k = clamp(k, 0, 1); return k * k * (3 - 2 * k); };
const easeOut = (k) => 1 - (1 - clamp(k, 0, 1)) ** 3;

export const MOVES = ['crash', 'whip', 'dutch', 'breath', 'shake', 'rack'];

/** moves: film.cameraMoves; o = { filmOf(actTime), contacts: [{ t (film clock) }], cuts: [film times] } */
export function makeCameraMoves(moves, o = {}) {
  const list = (moves ?? []).map((m, i) => {
    let t = m.t;
    if (m.act !== undefined) t = o.filmOf ? o.filmOf(m.act) : m.act;
    if (m.at === 'contact') t = o.contacts?.[m.contact ?? 0]?.t;
    if (t === undefined || t === null || !Number.isFinite(t)) throw new Error(`cameraMoves[${i}] (${m.move}): no time (t, act or at: "contact"; at: "contact" needs a blade contact the ENGINE detects - for a contact only the final bake has, give t from output/<film>.bake-events.json)`);
    if (!MOVES.includes(m.move)) throw new Error(`cameraMoves[${i}]: unknown move "${m.move}" (one of ${MOVES.join(', ')})`);
    let until = m.until;
    if (m.untilAct !== undefined) until = o.filmOf ? o.filmOf(m.untilAct) : m.untilAct;
    return { ...m, i, t: t + (m.offset ?? 0), until };
  });
  const cuts = (o.cuts ?? []).slice().sort((a, b) => a - b);
  const nextCut = (t) => cuts.find((c) => c > t + 1e-6) ?? Infinity;

  function at(t) {
    let fovMul = 1, yaw = 0, pitch = 0, roll = 0, focusOn = null;
    for (const m of list) {
      const d = t - m.t;
      // a move belongs to its shot: it ends at the next hard cut (a whip pan crosses the cut by design; a rack
      // focus hands the focus on; "across": true keeps any other move running through the cut)
      if (!m.across && m.move !== 'whip' && m.move !== 'rack' && d >= 0 && t >= nextCut(m.t)) continue;
      if (m.move === 'crash') {
        const zin = m.in ?? 0.1, hold = m.hold ?? 0.35, out = m.out ?? 0.4, z = m.zoom ?? 1.7;
        if (d < 0) continue;
        let k;
        if (d < zin) k = easeOut(d / zin);
        else if (out <= 0) k = 1;                                     // stays in until the next cut
        else k = 1 - smooth((d - zin - hold) / out);
        fovMul /= 1 + (z - 1) * k;
      } else if (m.move === 'whip') {
        const half = (m.dur ?? 0.16) / 2, deg = (m.deg ?? 60) * (m.dir ?? 1);
        if (d > -half && d < 0) yaw += deg * ((d + half) / half) ** 2;              // accelerate away
        else if (d >= 0 && d < half) yaw -= deg * (1 - easeOut(d / half));             // arrive, decelerating
      } else if (m.move === 'dutch') {
        const din = m.in ?? 0.25, hold = m.hold ?? 0.6, out = m.out ?? 0.4;
        if (d < 0) continue;
        const k = d < din ? smooth(d / din) : 1 - smooth((d - din - hold) / Math.max(1e-6, out));
        roll += (m.deg ?? 8) * k;
      } else if (m.move === 'breath') {
        const end = m.until ?? Infinity;
        if (d < 0 || t > end) continue;
        const fade = Math.min(1, d / 0.4, (end - t) / 0.4), a = (m.amp ?? 0.35) * fade, s = m.i * 1.7;
        yaw += a * (Math.sin(t * 2.1 + s) * 0.6 + Math.sin(t * 3.7 + s * 2) * 0.4);
        pitch += a * 0.7 * (Math.sin(t * 1.6 + s * 3) * 0.6 + Math.sin(t * 2.9 + s) * 0.4);
        roll += a * 1.1 * Math.sin(t * 1.3 + s * 5);
      } else if (m.move === 'shake') {
        const dur = m.dur ?? 0.35;
        if (d < 0 || d > dur) continue;
        const a = (m.amp ?? 1.2) * (1 - d / dur) ** 2, s = m.i * 3.1;
        yaw += a * Math.sin(d * 71 + s); pitch += a * Math.sin(d * 89 + s * 2); roll += a * 0.6 * Math.sin(d * 53 + s);
      } else if (m.move === 'rack') {
        if (d < 0) { if (focusOn === null && m.from) focusOn = { from: m.from, to: m.from, k: 0 }; continue; }
        focusOn = { from: m.from ?? null, to: m.to, k: smooth(d / (m.dur ?? 0.3)) };
      }
    }
    return { fovMul, yaw, pitch, roll, focusOn };
  }
  return { at, list };
}

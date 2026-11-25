// Expands named fight moves (library/moves.json) inside a performance into ordinary pose keys.
//   { "t": 3.2, "move": "jump-back", "speed": 1, "dist": 1 }
//
// A move is EITHER a list of pose beats (hand-authored) OR a slice of recorded motion capture:
//   "sword-strike": { "clip": "sword-a", "from": 1.2, "to": 3.4, "anime": 1.25 }
// A clip move reads library/mocap/<clip>.json, which stores per-frame channel values (rsx, rex,
// stance, stride ...) rather than pose names. Both kinds are called the same way, so a film never
// has to care which it is, and both are placed relative to where the fighter stands and faces.
//
// "anime" is deliberate unrealism. Motion capture is a recording of a real person, and a real
// person is not an anime character: the extremes are too small and the holds too short. anime > 1
// pushes every angle further from the clip's own average, so a raised sword goes higher and a
// crouch goes lower, while the timing and the contacts stay exactly where the capture put them.
// 1 = the recording untouched. Around 1.2-1.4 reads as animation; past ~1.8 limbs start to break.
// Positions in a move are relative to where the fighter stands and faces when the move starts.
// A beat's "turn" (radians) turns the fighter relative to that start facing (captured moves, tools/mocap.py);
// the fighter keeps the last beat's facing after the move.
// Pure module: used by the browser engine, the checker and the Node camera resolver.

import { LIMITS, clampCh, NO_EXAGGERATE } from './limits.js';

// Channels that are angles and may be exaggerated. Positions, timing and gait phase must not be:
// scaling those would move the fighter somewhere the film did not ask for, or break foot contact.
const ANGLE_CH = ['tx', 'ty', 'tz', 'cx', 'cy', 'cz', 'nx', 'ny', 'hx', 'hy', 'hz',
                  'rsx', 'rsy', 'rsz', 'rex', 'rwx', 'lsx', 'lsy', 'lsz', 'lex', 'lwx', 'crouch'];

function clipKeys(def, k, x, z, ry, clips) {
  const clip = clips?.[def.clip];
  if (!clip) throw new Error(`Move "${k.move}" needs mocap clip "${def.clip}" (library/mocap/${def.clip}.json)`);
  const speed = k.speed ?? 1, anime = k.anime ?? def.anime ?? 1;
  const from = def.from ?? 0, to = def.to ?? Infinity;
  const slice = clip.keys.filter((c) => c.t >= from && c.t <= to);
  if (!slice.length) throw new Error(`Move "${k.move}": clip "${def.clip}" has nothing between ${from}s and ${to}s`);

  // Exaggerate away from the SLICE's own average, so the clip keeps its shape and only its
  // extremes grow. Averaging over the whole clip instead would bias every pose toward a stance
  // the fighter never holds in this beat.
  const mean = {};
  if (anime !== 1) {
    for (const ch of ANGLE_CH) {
      const v = slice.filter((c) => c[ch] !== undefined).map((c) => c[ch]);
      if (v.length) mean[ch] = v.reduce((a, b) => a + b, 0) / v.length;
    }
  }
  const c0 = slice[0];
  const fx = Math.sin(ry), fz = Math.cos(ry);
  const sx = Math.cos(ry), sz = -Math.sin(ry);
  const out = [];
  for (const c of slice) {
    // The capture's own travel, rotated into the direction this fighter is facing.
    const dFwd = (c.z ?? 0) - (c0.z ?? 0), dSide = (c.x ?? 0) - (c0.x ?? 0);
    const key = { t: +(k.t + (c.t - c0.t) / speed).toFixed(4),
                  x: x + fx * dFwd + sx * dSide, z: z + fz * dFwd + sz * dSide,
                  ry: ry + ((c.ry ?? 0) - (c0.ry ?? 0)) };
    for (const [f, v] of Object.entries(c)) {
      if (['t', 'x', 'z', 'ry'].includes(f)) continue;
      // Exaggerate, then CLAMP. Without the clamp a 1.3 dial put the head 53 degrees back, past
      // its own limit, and the film still validated because nothing checked expanded keys.
      // The head and neck are never exaggerated at all: see NO_EXAGGERATE in engine/limits.js.
      const scaled = (anime !== 1 && mean[f] !== undefined && !NO_EXAGGERATE.has(f))
        ? mean[f] + (v - mean[f]) * anime : v;
      key[f] = clampCh(f, scaled);
    }
    for (const [f, v] of Object.entries(k)) {
      if (!['t', 'move', 'speed', 'dist', 'anime', 'note', 'x', 'z', 'ry'].includes(f)) key[f] = v;
    }
    out.push(key);
  }
  return out;
}

export function expandMoves(keys, moves, clips) {
  const out = [];
  let x = 0, z = 0, ry = 0;
  for (const k of keys) {
    if (k.x !== undefined) x = k.x;
    if (k.z !== undefined) z = k.z;
    if (k.ry !== undefined) ry = k.ry;
    if (!k.move) { out.push(k); continue; }
    const beats = moves[k.move];
    if (!beats) throw new Error(`Unknown move "${k.move}" at t=${k.t}`);
    if (!Array.isArray(beats)) {                          // a recorded-motion move, not pose beats
      const got = clipKeys(beats, k, x, z, ry, clips);
      out.push(...got);
      const last = got[got.length - 1];
      x = last.x; z = last.z; ry = last.ry;
      continue;
    }
    const speed = k.speed ?? 1, dist = k.dist ?? 1;
    const fx = Math.sin(ry), fz = Math.cos(ry);          // forward
    const sx = Math.cos(ry), sz = -Math.sin(ry);         // the fighter's left (+x when facing +z)
    let endX = x, endZ = z, endRy = ry;
    for (const b of beats) {
      const fwd = (b.fwd ?? 0) * dist, side = (b.side ?? 0) * dist;
      const key = { t: +(k.t + b.dt / speed).toFixed(4), pose: b.pose, x: x + fx * fwd + sx * side, z: z + fz * fwd + sz * side, ry: ry + (b.turn ?? 0) };
      for (const [f, v] of Object.entries(b)) if (!['dt', 'pose', 'fwd', 'side', 'turn'].includes(f)) key[f] = v;
      for (const [f, v] of Object.entries(k)) if (!['t', 'move', 'speed', 'dist', 'note', 'x', 'z', 'ry'].includes(f)) key[f] = v;
      out.push(key);
      endX = key.x; endZ = key.z; endRy = ry + (b.turn ?? 0);   // only "turn" carries over (an absolute beat "ry" does not, as before)
    }
    x = endX; z = endZ; ry = endRy;
  }
  return out;
}

// Which mocap clips a move library needs, so a caller can fetch exactly those and no more.
export function clipNames(moves) {
  return [...new Set(Object.values(moves).filter((m) => !Array.isArray(m) && m?.clip).map((m) => m.clip))];
}

// Load those clips. `read` takes a clip name and returns its parsed json (fetch in the browser,
// readFile in Node), so this module stays pure and works in both.
export async function loadClips(moves, read) {
  const out = {};
  for (const n of clipNames(moves)) out[n] = await read(n);
  return out;
}

// Node callers read from disk synchronously; this keeps their call sites one line.
export function loadClipsSync(moves, readSync) {
  const out = {};
  for (const n of clipNames(moves)) out[n] = readSync(n);
  return out;
}

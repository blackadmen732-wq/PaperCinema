// Expands named fight moves (library/moves.json) inside a performance into ordinary pose keys.
//   { "t": 3.2, "move": "jump-back", "speed": 1, "dist": 1 }
// Positions in a move are relative to where the fighter stands and faces when the move starts.
// A beat's "turn" (radians) turns the fighter relative to that start facing (captured moves, tools/mocap.py);
// the fighter keeps the last beat's facing after the move.
// Pure module: used by the browser engine, the checker and the Node camera resolver.

export function expandMoves(keys, moves) {
  const out = [];
  let x = 0, z = 0, ry = 0;
  for (const k of keys) {
    if (k.x !== undefined) x = k.x;
    if (k.z !== undefined) z = k.z;
    if (k.ry !== undefined) ry = k.ry;
    if (!k.move) { out.push(k); continue; }
    const beats = moves[k.move];
    if (!beats) throw new Error(`Unknown move "${k.move}" at t=${k.t}`);
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

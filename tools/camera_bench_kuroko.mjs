// KUROKO on the camera bench: the real camera module (engine/kuroko.js) films the bench ball, so it is scored on
// the same flight and the same measurements as the four bench operators (tools/camera_bench.py).
//   node tools/camera_bench_kuroko.mjs <ball.json> <out.json>
// ball.json = { fps, ball: [[x, y, z] Blender z-up per frame], dashes: [{ start_s, dur_s }] }
// out.json  = { <operator>: [{ pos, target, lens }] } in Blender z-up, lens in mm for a 36 mm vertical sensor.
// KUROKO frames people by name: the ball becomes a "subject" whose chest is the ball and whose facing is its heading.
// It knows the dashes as impacts (its punch-in), and nothing about the boxes (it has no line-of-sight check).
import fs from 'node:fs';
import { makeKuroko } from '../engine/kuroko.js';

const [, , inPath, outPath] = process.argv;
const B = JSON.parse(fs.readFileSync(inPath, 'utf8'));
const fps = B.fps, N = B.ball.length, dur = N / fps;
const P3 = B.ball.map(([x, y, z]) => [x, z, -y]);                 // Blender z-up -> three.js y-up
const at = (t) => {
  const x = Math.max(0, Math.min(N - 1, t * fps)), i = Math.floor(x), k = x - i, a = P3[i], b = P3[Math.min(N - 1, i + 1)];
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
};
// heading: smoothed direction of travel (a ball has no face; KUROKO's single-subject rigs need one)
const heading = [];
{
  let ry = 0;
  for (let i = 0; i < N; i++) {
    const a = P3[Math.max(0, i - 1)], b = P3[Math.min(N - 1, i + 1)], vx = b[0] - a[0], vz = b[2] - a[2];
    if (Math.hypot(vx, vz) * fps / 2 > 0.5) {
      const want = Math.atan2(vx, vz);
      let d = want - ry; d = Math.atan2(Math.sin(d), Math.cos(d));
      ry += d * 0.35;
    }
    heading.push(ry);
  }
}
const ryAt = (t) => heading[Math.max(0, Math.min(N - 1, Math.round(t * fps)))];
const motions = {
  ball: (t) => { const p = at(t); return { x: p[0], y: p[1] - 1.34, z: p[2], ry: ryAt(t), crouch: 0, weight: 0, tx: 0, tz: 0 }; },
};
const impacts = B.dashes.map((d) => d.start_s);
const kuroko = makeKuroko({ motions, impacts, pair: {}, aspect: 540 / 960 });
// two KUROKO set-ups a director would pick for a flying subject
const SHOTS = {
  'kuroko-frame': { id: 'kf', start: 0, end: dur, rig: { type: 'frame', subject: 'ball', size: 'wide', fov: 34, feel: 'dolly' } },
  'kuroko-track': { id: 'kt', start: 0, end: dur, rig: { type: 'track', subject: 'ball', offset: [1.2, 1.0, -4.5], fov: 40, feel: 'torpedo' } },
};
const out = {};
for (const [name, shot] of Object.entries(SHOTS)) {
  out[name] = [];
  for (let i = 0; i < N; i++) {
    const c = kuroko.at(shot, i / fps);
    const toB = ([x, y, z]) => [x, -z, y];                          // three.js -> Blender
    const lens = 18 / Math.tan((c.fov * Math.PI) / 360);           // 36 mm sensor, vertical fit
    out[name].push({ pos: toB(c.pos), target: toB(c.look), lens, roll: c.roll });
  }
}
fs.writeFileSync(outPath, JSON.stringify(out));
console.log(`[kuroko-bench] ${Object.keys(out).join(', ')}: ${N} frames -> ${outPath}`);

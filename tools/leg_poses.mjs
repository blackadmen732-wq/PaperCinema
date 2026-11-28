// LEG POSES: every pose of library/poses.json through engine/figure.js's leg solver (stance feet, no foot plan):
// the knee bend, the soft-IK stretch, the heel the reach rule raised and how far each sole is off the ground.
//
//   node tools/leg_poses.mjs [--json out.json] [--only a,b]
//
// What good looks like (28 Nov, Mark: "fix the leg"): a standing knee 5-10 deg, no leg stretched past 2%, every
// planted sole on the ground (the toes of a raised heel included), the knee never past LEG.kneeMax.
import fs from 'node:fs';

const ctx = new Proxy({}, { get: (_, k) => (k === 'getImageData' ? (x, y, w, h) => ({ data: new Uint8ClampedArray(w * h * 4) })
  : k === 'createLinearGradient' || k === 'createRadialGradient' ? () => ({ addColorStop() {} }) : k === 'measureText' ? () => ({ width: 1 }) : () => {}), set: () => true });
globalThis.document = { createElement: () => ({ width: 1, height: 1, getContext: () => ctx, style: {} }) };
const THREE = await import('three');
const F = await import('../engine/figure.js');
const { makeFigure, applyPose, BASE_POSE, LEG } = F;

const argv = process.argv.slice(2);
const opt = (n) => (argv.includes('--' + n) ? argv[argv.indexOf('--' + n) + 1] : null);
const poses = JSON.parse(fs.readFileSync('library/poses.json', 'utf8'));
const only = opt('only')?.split(',');
const fig = makeFigure({ robe: '#888888', hakama: '#444444' });
const W = (o, x = 0, y = 0, z = 0) => o.localToWorld(new THREE.Vector3(x, y, z));
// the sole under the ankle, at the heel and at the toe tip (the toe tip rides the toe joint when there is one)
const sole = -(LEG.footY ?? 0.04);
const rows = [];
for (const [name, P] of Object.entries(poses)) {
  if (typeof P !== 'object' || (only && !only.includes(name))) continue;
  const p = { ...BASE_POSE, ...P };
  applyPose(fig, p);
  fig.root.updateMatrixWorld(true);
  const row = { pose: name };
  for (const [s, L] of Object.entries(fig.legs)) {
    const h = W(L.thigh), k = W(L.shin), a = W(L.foot);
    const knee = THREE.MathUtils.radToDeg(k.clone().sub(h).angleTo(a.clone().sub(k)));
    const heel = W(L.foot, 0, sole, -0.065).y;
    const toe = L.toe ? W(L.toe, 0, sole - LEG.toeY, 0.17 - LEG.toeZ).y : W(L.foot, 0, sole, 0.17).y;
    row[s] = { knee: +knee.toFixed(1), stretch: +L.thigh.scale.x.toFixed(3), heel: +(heel * 100).toFixed(1), toe: +(toe * 100).toFixed(1) };
  }
  rows.push(row);
}
const f1 = (x) => x.toFixed(1).padStart(6);
console.log('pose                     knee R  knee L  stretch R/L    heel R/L cm   toe R/L cm');
for (const r of rows) {
  console.log(`${r.pose.padEnd(22)} ${f1(r.r.knee)}  ${f1(r.l.knee)}   ${r.r.stretch.toFixed(3)}/${r.l.stretch.toFixed(3)}  ${f1(r.r.heel)}/${f1(r.l.heel)}  ${f1(r.r.toe)}/${f1(r.l.toe)}`);
}
const all = rows.flatMap((r) => [r.r, r.l]);
const st = rows.find((r) => r.pose === 'neutral');
console.log(`SUMMARY ${rows.length} poses: neutral knee ${st?.r.knee}/${st?.l.knee} deg | worst stretch ${Math.max(...all.map((x) => x.stretch)).toFixed(3)}`
  + ` | lowest toe ${Math.min(...all.map((x) => x.toe)).toFixed(1)} cm | highest toe ${Math.max(...all.map((x) => x.toe)).toFixed(1)} cm`
  + ` | max knee ${Math.max(...all.map((x) => x.knee)).toFixed(1)} deg | heels raised ${all.filter((x) => x.heel - x.toe > 2).length}`);
if (opt('json')) fs.writeFileSync(opt('json'), JSON.stringify(rows, null, 1));

// MOTION EXPORT: the one source of truth for Blender (docs/CHARACTER-BLENDER.md).
//   node tools/export_motion.mjs film/dash-test.json              → output/dash-test.motion.json
//   options: --sub N (samples per frame, default 4: sub-frames feed the slash trail and motion blur) · --out file
// It opens the film's own preview page in headless Chrome (the same engine that renders the preview), asks it to pose
// every frame WITHOUT drawing, and writes what the engine really did: every joint's world transform (after the motion
// curves, follow-through, leg IK, two-hand grip, clash aim, hit-stop and speed ramps), the sword, the pose channels,
// the camera (position, rotation, fov, after the spring and the impact punch), the tree props and the events.
// Nothing is re-implemented, so Blender can never drift from the preview.
//
// The motion page keeps its objects private. The exporter adds ONE line to the copy of engine/motion.js that the
// browser receives (the file on disk is not touched). If the page ever publishes window.PC itself, that is used.
// Coordinates are three.js: +y up, the figure faces +z, metres. blender/character/rig_trellis.py converts
// (x, y, z) → (x, -z, y).
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { serve } from '../engine/serve.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const filmPath = args.find((a) => a.endsWith('.json'));
if (!filmPath) { console.error('usage: node tools/export_motion.mjs film/<name>.json [--sub 4] [--out file]'); process.exit(2); }
const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
const NAME = path.basename(filmPath, '.json');
const SUB = Number(opt('sub', 4));
const out = opt('out', `output/${NAME}.motion.json`);
const pagePath = film.page ?? 'engine/index.html';
if (!pagePath.endsWith('motion.html')) { console.error(`export_motion: only films on engine/motion.html are supported for now (this film uses ${pagePath})`); process.exit(2); }
const VERT = film.format === 'vertical' && !args.includes('--horizontal');

const server = await serve(0);
const port = server.address().port;
const browser = await chromium.launch({
  executablePath: process.env.PAPERCINEMA_CHROMIUM || undefined,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: VERT ? { width: 720, height: 1280 } : { width: film.width, height: film.height } });
page.on('pageerror', (e) => console.error('PAGE ERROR:', e.message));
const HOOK = 'window.PC ??= { cast, camera, stage, TREES: typeof TREES !== "undefined" ? TREES : [] };\n';
await page.route('**/engine/motion.js', async (route) => {
  const src = fs.readFileSync('engine/motion.js', 'utf8');
  const at = src.lastIndexOf('window.READY = true');
  if (at < 0) throw new Error('export_motion: engine/motion.js has no "window.READY = true" line to hook');
  await route.fulfill({ contentType: 'text/javascript', body: src.slice(0, at) + HOOK + src.slice(at) });
});
await page.goto(`http://localhost:${port}/${pagePath}?render=1&film=/${filmPath}${VERT ? '&aspect=vertical' : ''}`);
await page.waitForFunction('window.READY === true', null, { timeout: 600000 });

const data = await page.evaluate(({ SUB }) => {
  const { cast, camera, stage, TREES } = window.PC;
  const film = window.FILM, FPS = film.fps, N = Math.round(film.duration * FPS) * SUB;
  const r = (v) => +v.toFixed(5);
  const JOINTS = {
    root: (f) => f.root, hips: (f) => f.hips, waist: (f) => f.torso, chest: (f) => f.upper, neck: (f) => f.neck, head: (f) => f.head,
    'clavicle.R': (f) => f.rC, 'shoulder.R': (f) => f.rS, 'elbow.R': (f) => f.rE, 'twist.R': (f) => f.rT, 'hand.R': (f) => f.rH,
    'clavicle.L': (f) => f.lC, 'shoulder.L': (f) => f.lS, 'elbow.L': (f) => f.lE, 'twist.L': (f) => f.lT, 'hand.L': (f) => f.lH,
    'thigh.R': (f) => f.legs.r.thigh, 'shin.R': (f) => f.legs.r.shin, 'foot.R': (f) => f.legs.r.foot,
    'thigh.L': (f) => f.legs.l.thigh, 'shin.L': (f) => f.legs.l.shin, 'foot.L': (f) => f.legs.l.foot,
    hakama: (f) => f.hakama,
  };
  const names = Object.keys(JOINTS);
  const xf = (o) => {
    o.updateWorldMatrix(true, false);
    const e = o.matrixWorld.elements;
    const p = [e[12], e[13], e[14]];
    const q = o.getWorldQuaternion(new o.quaternion.constructor());
    return [...p, q.x, q.y, q.z, q.w].map(r);
  };
  const ids = Object.keys(cast);
  const frames = [];
  for (let i = 0; i <= N; i++) {
    const t = Math.min(film.duration, i / (FPS * SUB));
    const st = stage(t);
    camera.updateMatrixWorld(true);
    const F = { t: r(t), tb: r(st.tb), impactFrame: !!st.impactFrame, cam: [...camera.position.toArray(), ...camera.quaternion.toArray(), camera.fov].map(r), cast: {}, trees: [] };
    for (const id of ids) {
      const c = cast[id];
      if (c.hidden) continue;
      c.fig.root.updateMatrixWorld(true);
      const whole = i % SUB === 0;                                    // joints on whole frames; the sword on every sub-frame
      F.cast[id] = { sword: xf(c.sword) };
      if (whole) {
        F.cast[id].joints = names.map((n) => xf(JOINTS[n](c.fig)));
        const p = c.motion(st.tb);
        let w = 0;                                                    // two-hand grip weight (same soft window as the engine)
        for (const [a, b] of c.perf.twoHand ?? []) if (st.tb >= a - 0.15 && st.tb <= b + 0.15) w = Math.max(w, Math.min(1, (st.tb - (a - 0.15)) / 0.15, ((b + 0.15) - st.tb) / 0.15));
        F.cast[id].twoHand = r(Math.max(0, w));
        F.cast[id].pose = Object.fromEntries(Object.entries(p).map(([k, v]) => [k, r(v)]));
        if (c.fig.eyeMat) F.cast[id].eyes = r(c.fig.eyeMat.emissiveIntensity ?? 0);
      }
    }
    if (i % SUB === 0) for (const T of TREES) F.trees.push({ top: xf(T.top), halves: T.halves.map(xf) });
    frames.push(F);
  }
  const first = cast[ids.find((id) => !cast[id].hidden)];
  return {
    film: { title: film.title, fps: FPS, duration: film.duration, format: film.format, width: film.width, height: film.height },
    sub: SUB, coords: 'three.js: +y up, figure faces +z, metres; transforms = [px, py, pz, qx, qy, qz, qw] in world space',
    joints: names,
    sword: { bladeLen: first?.bladeLen ?? 0.91, handle: 0.33, grip: -0.06, leftGrip: -0.27, note: 'sword frame: blade along +x from the guard (x = 0), edge toward -y, handle along -x' },
    cast: Object.fromEntries(ids.map((id) => [id, { character: film.cast[id].character, hidden: !!cast[id].hidden, demonic: !!cast[id].demonic }])),
    trees: TREES.map((T) => ({ ...T.tr, base: T.root.position.toArray() })),
    camera: { note: 'cam = [px, py, pz, qx, qy, qz, qw, fov]; fov is vertical, in degrees', beats: window.AUDIT?.meta?.beats ?? null, cuts: window.AUDIT?.meta?.cuts ?? null },
    ramps: film.ramps ?? [], impacts: window.EVENTS?.impacts ?? [], events: window.EVENTS ?? null,
    frames,
  };
}, { SUB });

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(data));
console.log(`motion: ${data.frames.length} samples (${SUB} per frame), ${Object.keys(data.frames[0].cast).length} fighter(s), ${data.trees.length} tree(s) → ${out} (${(fs.statSync(out).size / 1e6).toFixed(1)} MB)`);
await browser.close();
server.close();

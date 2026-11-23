// STUDIO AUDIT: automated quality control for ANY Paper Cinema film (docs/AUDIT.md, rules: docs/STUDIO-STANDARD.md).
//   node tools/audit.mjs film/<name>.json                       geometry + sound checks, pixels on a few rendered samples
//   node tools/audit.mjs film/<name>.json --frames output/frames-x   pixel checks on frames that are already rendered
//   node tools/audit.mjs film/<name>.json --pixels 0            no pixel checks (fastest: nothing is drawn)
//   options: --step N (measure every Nth frame, default 1) · --pixels N (render every Nth frame for the pixel checks,
//            default: about 14 samples) · --sound output/<name>-sound.mp4 · --strict (majors also fail) · --quiet
// It opens the film's page in headless Chrome and asks window.AUDIT.at(t) (engine/audit-hooks.js) for every frame:
// camera, joints on screen, lines of sight, foreground blockers, blade, feet. Nothing is drawn for that, so a
// 7 s film takes about half a minute. Then it measures the sound (the mixed MP4 if it exists, the cue lists always).
// Prints a scored report, writes output/<film>.audit.md and .audit.json, exits 1 on any CRITICAL finding.
import { createRequire } from 'node:module';
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { serve } from '../engine/serve.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes('--' + n);
const filmPath = args.find((a) => a.endsWith('.json'));
if (!filmPath) { console.error('usage: node tools/audit.mjs film/<name>.json [--frames dir] [--pixels N] [--step N] [--sound file] [--strict]'); process.exit(2); }
const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
const NAME = path.basename(filmPath, '.json');
const FPS = film.fps ?? 24, DUR = film.duration, NF = Math.round(DUR * FPS);
const VERT = film.format === 'vertical' && !flag('horizontal');
const WAIVE = film.audit?.waive ?? [];                       // [{ check, from, to, why }] (film seconds): a deliberate exception

// ---------- the numbers (docs/STUDIO-STANDARD.md gives the reasons) ----------
const RULE = {
  onScreenMin: 0.5,          // share of a subject's 8 key joints inside the frame
  sizeTiny: 0.07, sizeSmall: 0.12,   // subject height as a share of the frame height
  blockersMajor: 0.35, blockersCritical: 0.6,
  nearGeometry: 0.12, nearSubject: 0.28, bladeLens: 0.12,
  camGroundClear: 0.08,
  panPop: 35, panSwim: 12,   // degrees per frame
  slideSpeed: 1.0, slideDist: 0.4,   // a planted foot: m/s and metres
  popStep: 0.45, tipNoSmear: 1.2, tipTeleport: 3.2,   // metres per frame
  deadMinor: 1.5, deadMajor: 3.0,    // seconds without any life
  shotShort: 0.33, shotLong: 8,
  slowShareMinor: 0.25, slowShareMajor: 0.35, slowRateMin: 0.15,
  lumaBlack: 10, lumaBright: 225, clipMajor: 0.45, clipMinor: 0.2, flatStd: 6,
  hitOverPre: 9, mush: 0.06, lufs: [-16, -12],
  safeTop: 0.06, safeBottom: 0.82, leadEdge: 0.62,
};
const CATS = ['hook', 'staging', 'camera', 'composition', 'animation', 'slash/smear', 'effects', 'picture', 'sound', 'edit/rhythm'];
const WEIGHT = { critical: 4, major: 1.5, minor: 0.5, info: 0 };
const findings = [];
const fr = (t) => Math.round(t * FPS);
function add(check, cat, sev, t0, t1, msg, fix) {
  const w = WAIVE.find((x) => x.check === check && t0 >= (x.from ?? 0) - 1e-6 && t1 <= (x.to ?? DUR) + 1e-6);
  findings.push({ check, cat, sev: w ? 'info' : sev, t0: +t0.toFixed(3), t1: +t1.toFixed(3), f0: fr(t0), f1: fr(t1), msg: w ? `${msg} (waived: ${w.why ?? 'no reason given'})` : msg, fix, waived: !!w });
}
/** runs of consecutive frames where test(frame) is true → [{ a, b, frames }] (indices into F) */
function runs(F, test) {
  const out = []; let a = -1;
  F.forEach((d, i) => { const ok = test(d, i); if (ok && a < 0) a = i; if ((!ok || i === F.length - 1) && a >= 0) { const b = ok ? i : i - 1; out.push({ a, b, frames: F.slice(a, b + 1) }); a = -1; } });
  return out;
}
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], len = (v) => Math.hypot(...v), dist = (a, b) => len(sub(a, b));
const angle = (a, b) => (Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))) * 180) / Math.PI;

// ---------- 1. measure ----------
const server = await serve(0);
const port = server.address().port;
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: VERT ? { width: 720, height: 1280 } : { width: film.width ?? 1280, height: film.height ?? 720 } });
page.on('pageerror', (e) => console.error('PAGE ERROR:', e.message));
const pagePath = opt('page', film.page ?? 'engine/index.html');
await page.goto(`http://localhost:${port}/${pagePath}?render=1&film=/${filmPath}${VERT ? '&aspect=vertical' : ''}`);
await page.waitForFunction('window.READY === true', null, { timeout: 600000 });
const has = await page.evaluate(() => !!window.AUDIT);
if (!has) { console.error(`✗ ${pagePath} has no audit hooks (window.AUDIT). Add installAudit(...) from engine/audit-hooks.js.`); await browser.close(); server.close(); process.exit(2); }
const META = await page.evaluate(() => window.AUDIT.meta);
const EVENTS = await page.evaluate(() => window.EVENTS ?? null);
const STEP = Math.max(1, +opt('step', 1));
const F = [];
const t0wall = Date.now();
for (let i = 0; i < NF; i += STEP) F.push(await page.evaluate((t) => window.AUDIT.at(t), i / FPS));
if (!flag('quiet')) console.log(`measured ${F.length} frames of ${NAME} in ${((Date.now() - t0wall) / 1000).toFixed(0)} s (page ${META.page})`);
const DT = STEP / FPS;

// pixels: frames on disk, or a few samples rendered now
const pixFn = async ({ b64, mime }) => {
  const img = await createImageBitmap(await (await fetch(`data:${mime};base64,${b64}`)).blob());
  const c = new OffscreenCanvas(72, 128), g = c.getContext('2d');
  g.drawImage(img, 0, 0, 72, 128);
  const d = g.getImageData(0, 0, 72, 128).data, n = d.length / 4;
  let s = 0, s2 = 0, clip = 0, dark = 0, sat = 0;
  for (let i = 0; i < d.length; i += 4) {
    const y = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
    s += y; s2 += y * y; if (y > 250) clip++; if (y < 16) dark++;
    sat += Math.max(d[i], d[i + 1], d[i + 2]) - Math.min(d[i], d[i + 1], d[i + 2]);
  }
  const mean = s / n;
  return { mean: +mean.toFixed(1), std: +Math.sqrt(Math.max(0, s2 / n - mean * mean)).toFixed(1), clip: +(clip / n).toFixed(3), dark: +(dark / n).toFixed(3), sat: +(sat / n).toFixed(1) };
};
const PIX = [];                                              // { i (frame), t, mean, std, clip, dark, sat }
const framesDir = opt('frames');
if (framesDir) {
  const files = fs.readdirSync(framesDir).filter((f) => /^f\d+\.jpe?g$/.test(f)).sort();
  if (Math.abs(files.length - NF) > 2) console.log(`! ${framesDir} has ${files.length} frames but the film has ${NF}: the frames are from an older version; pixel checks may point at the wrong moments`);
  const every = Math.max(1, +opt('pixels', 2));
  for (let i = 0; i < Math.min(files.length, NF); i += every) PIX.push({ i, t: i / FPS, ...(await page.evaluate(pixFn, { b64: fs.readFileSync(path.join(framesDir, files[i])).toString('base64'), mime: 'image/jpeg' })) });
} else if (opt('pixels') !== '0') {
  const every = +opt('pixels', Math.max(1, Math.round(NF / 14)));
  const want = new Set([0, 1, NF - 1]);
  for (let i = 0; i < NF; i += every) want.add(i);
  for (const h of [...(EVENTS?.impacts ?? []), ...(EVENTS?.contacts ?? [])]) want.add(Math.min(NF - 1, fr(h.t) + 2));
  for (const i of [...want].sort((a, b) => a - b)) {
    await page.evaluate((t) => window.renderAt(t), i / FPS);
    const b64 = (await page.screenshot({ type: 'jpeg', quality: 80 })).toString('base64');
    PIX.push({ i, t: i / FPS, ...(await page.evaluate(pixFn, { b64, mime: 'image/jpeg' })) });
  }
}
await browser.close();
server.close();

// ---------- 2. geometry checks ----------
const ids = Object.keys(F[0].fighters);
const vis = (d) => ids.filter((id) => d.fighters[id].visible);
const subjectsOf = (d) => (d.subjects?.length ? d.subjects.filter((id) => d.fighters[id]?.visible) : vis(d));
const cuts = new Set();                                      // frame indices (into F) that start a new shot
for (const c of META.cuts ?? []) cuts.add(Math.ceil((c * FPS - 1e-6) / STEP));
F.forEach((d, i) => {
  if (!i) return;
  const p = F[i - 1];
  d.camStep = dist(d.cam.pos, p.cam.pos); d.pan = angle(d.cam.dir, p.cam.dir);
  if (d.shot !== p.shot && META.page !== 'motion') cuts.add(i);
  if (!META.cuts && d.camStep > 1.0 && d.pan > 20) cuts.add(i);
});
const isCut = (i) => cuts.has(i);
const free = (d) => d.free === true || d.impactFrame;       // a shot that is not about the fighters, or the one-frame ink page

// V1: subject off screen
for (const r of runs(F, (d) => !free(d) && subjectsOf(d).length > 0 && !subjectsOf(d).some((id) => d.fighters[id].onScreen >= RULE.onScreenMin))) {
  const n = r.frames.length * STEP;
  add('subject-off-screen', 'staging', n >= 3 ? 'critical' : 'major', r.frames[0].t, r.frames[r.frames.length - 1].t,
    `no subject is in the frame for ${n} frame(s) (best: ${Math.max(...r.frames.map((d) => Math.max(...subjectsOf(d).map((id) => d.fighters[id].onScreen)))) * 100 | 0}% of the joints)`,
    'the camera lost the subject: use the "compose" rig or cameraOpts.solver 2 (the spring follows the subject), or lower the beat\'s lag');
}
// V2: subject hidden behind something
for (const r of runs(F, (d) => !free(d) && subjectsOf(d).some((id) => { const b = d.fighters[id].blocked; return b && b.head && b.chest; }))) {
  const n = r.frames.length * STEP;
  add('subject-occluded', 'camera', n >= 3 ? 'critical' : 'major', r.frames[0].t, r.frames[r.frames.length - 1].t, `head and chest are hidden behind an object for ${n} frame(s)`,
    'move the camera (compose rig: its guard swings round props) or the prop; a foreground wipe must be shorter than 3 frames');
}
for (const r of runs(F, (d) => !free(d) && subjectsOf(d).some((id) => { const b = d.fighters[id].blocked; return b && (b.head || b.hips) && !(b.head && b.chest); }))) {
  if (r.frames.length * STEP >= 4) add('subject-part-hidden', 'camera', 'minor', r.frames[0].t, r.frames[r.frames.length - 1].t, `a prop covers the head or the hips for ${r.frames.length * STEP} frames`, 'check the still: is the pose still readable?');
}
// V3: size in frame
const sizeOf = (d) => Math.max(0, ...subjectsOf(d).map((id) => { const b = d.fighters[id].box; return b[3] - b[1]; }));
for (const r of runs(F, (d) => !free(d) && subjectsOf(d).length > 0 && sizeOf(d) < RULE.sizeSmall)) {
  const sec = r.frames.length * DT, m = Math.min(...r.frames.map(sizeOf));
  if (m < RULE.sizeTiny && sec > 0.4) add('subject-tiny', 'staging', 'major', r.frames[0].t, r.frames[r.frames.length - 1].t, `the subject is only ${(m * 100).toFixed(0)}% of the frame height for ${sec.toFixed(1)} s`, 'vertical frames need the fighter at 45% or more in action and 12% or more in the widest shot');
  else if (sec > 1.0) add('subject-small', 'staging', 'minor', r.frames[0].t, r.frames[r.frames.length - 1].t, `the subject is ${(m * 100).toFixed(0)}% of the frame height for ${sec.toFixed(1)} s`, 'fine for one establishing shot; otherwise move in');
}
// C1–C4: where the lens is
for (const r of runs(F, (d) => d.cam.underGround || (d.cam.ground !== null && d.cam.pos[1] < d.cam.ground + RULE.camGroundClear)))
  add('camera-under-ground', 'camera', 'critical', r.frames[0].t, r.frames[r.frames.length - 1].t, `the camera is at or under the ground (${Math.min(...r.frames.map((d) => d.cam.pos[1] - (d.cam.ground ?? 0))).toFixed(2)} m above it)`, 'raise the camera (minY) or lower the elevation angle');
for (const r of runs(F, (d) => d.nearest < RULE.nearGeometry))
  add('camera-in-geometry', 'camera', r.frames.length * STEP >= 2 ? 'critical' : 'major', r.frames[0].t, r.frames[r.frames.length - 1].t, `geometry is ${Math.min(...r.frames.map((d) => d.nearest)).toFixed(2)} m from the lens (inside a prop or the ground)`, 'keep 0.3 m clear of every prop (compose rig guard) and of the ground');
for (const r of runs(F, (d) => !free(d) && d.nearestSubject < RULE.nearSubject))
  if (r.frames.length * STEP >= 2) add('camera-in-subject', 'camera', 'major', r.frames[0].t, r.frames[r.frames.length - 1].t, `the lens is ${Math.min(...r.frames.map((d) => d.nearestSubject)).toFixed(2)} m from the body (it passes through the fighter)`, 'cut instead of flying through the body, or widen the orbit radius');
for (const r of runs(F, (d) => vis(d).some((id) => (d.fighters[id].bladeToCam ?? 9) < RULE.bladeLens)))
  add('blade-through-lens', 'camera', 'minor', r.frames[0].t, r.frames[r.frames.length - 1].t, 'a blade passes within 12 cm of the lens', 'fine as a deliberate wipe (1–2 frames); otherwise move the camera off the cutting plane');
for (const r of runs(F, (d) => !free(d) && d.blockers > RULE.blockersMajor)) {
  const n = r.frames.length * STEP, m = Math.max(...r.frames.map((d) => d.blockers));
  if (n >= 3) add('foreground-blocker', 'camera', m > RULE.blockersCritical && n >= 6 ? 'critical' : 'major', r.frames[0].t, r.frames[r.frames.length - 1].t, `props in front of the subject cover ${(m * 100).toFixed(0)}% of the frame for ${n} frames`, 'a foreground prop may frame the shot (up to 35% of the frame, at an edge), never fill it');
}
// C5: pops and swimming
F.forEach((d, i) => {
  if (!i || isCut(i) || free(d)) return;
  if (d.pan > RULE.panPop) add('camera-pop', 'camera', 'major', d.t, d.t, `the camera turns ${d.pan.toFixed(0)}° in one frame without a cut`, 'mark the beat "cut": true, or ease the move (feel: "whip" takes 4–6 frames)');
});
for (const r of runs(F, (d, i) => i > 0 && !isCut(i) && d.pan > RULE.panSwim && d.pan <= RULE.panPop))
  if (r.frames.length * STEP >= 5) add('camera-swim', 'camera', 'minor', r.frames[0].t, r.frames[r.frames.length - 1].t, `the camera pans faster than ${RULE.panSwim}°/frame for ${r.frames.length * STEP} frames: the picture smears`, 'a whip pan is 3–6 frames; a longer move must be slower or become a cut');
// K: composition
const chest = (d, id) => d.fighters[id].screen.chest, headS = (d, id) => d.fighters[id].screen.head;
const lead = F.map((d, i) => {
  const id = subjectsOf(d)[0]; if (!id || !i || isCut(i) || !F[i - 1].fighters[id].visible) return 0;
  const vx = (chest(d, id)[0] - chest(F[i - 1], id)[0]) / DT;      // frame widths per second
  return Math.abs(vx) > 0.25 && ((vx > 0 && chest(d, id)[0] > RULE.leadEdge) || (vx < 0 && chest(d, id)[0] < 1 - RULE.leadEdge)) ? 1 : 0;
});
for (const r of runs(F, (d, i) => lead[i] === 1)) if (r.frames.length * STEP >= 4) add('no-lead-room', 'composition', 'minor', r.frames[0].t, r.frames[r.frames.length - 1].t, 'the subject moves towards the near edge of the frame (no lead room)', 'place the subject on the third it comes FROM (compose rig: "lead": 0.16)');
for (const r of runs(F, (d) => !free(d) && subjectsOf(d).some((id) => { const h = d.fighters[id].screen.headTop, f = d.fighters[id]; return f.onScreen >= 0.5 && f.box[3] - f.box[1] < 1.0 && h[1] < 0.015; })))
  if (r.frames.length * STEP >= 6) add('head-cropped', 'composition', 'minor', r.frames[0].t, r.frames[r.frames.length - 1].t, 'the top of the head is cut by the frame in a full or medium shot', 'give headroom (5–12% of the frame) or commit to a close-up');
for (const r of runs(F, (d) => !free(d) && subjectsOf(d).length > 0 && subjectsOf(d).every((id) => d.fighters[id].onScreen >= 0.5 && (headS(d, id)[1] > RULE.safeBottom || headS(d, id)[1] < RULE.safeTop))))
  if (r.frames.length * DT >= 0.5) add('face-outside-safe-zone', 'composition', 'minor', r.frames[0].t, r.frames[r.frames.length - 1].t, 'the face sits where the Shorts interface covers the picture (top 6% or bottom 18%)', 'keep faces between 6% and 82% of the height');
{
  const c = F.filter((d) => !free(d) && subjectsOf(d).length).map((d) => chest(d, subjectsOf(d)[0])[0]);
  const centred = c.filter((x) => Math.abs(x - 0.5) < 0.06).length / (c.length || 1);
  if (c.length > FPS && centred > 0.85) add('always-centred', 'composition', 'minor', 0, DUR, `the subject is dead centre in ${(centred * 100).toFixed(0)}% of the frames`, 'use the thirds: lead room for motion and gaze (compose rig "screen" / "lead")');
}
// A1: feet sliding
for (const id of ids) {
  for (const foot of ['rFoot', 'lFoot']) {
    const sp = F.map((d, i) => {
      const f = d.fighters[id], p = F[i - 1]?.fighters[id];
      if (!i || !f.visible || !p?.visible || f.root[1] > 0.03 || f.joints[foot][1] > 0.12) return 0;
      const a = f.joints[foot], b = p.joints[foot];
      return Math.hypot(a[0] - b[0], a[2] - b[2]);
    });
    for (const r of runs(F, (d, i) => sp[i] / DT > RULE.slideSpeed)) {
      const m = r.frames.reduce((s, d, k) => s + sp[r.a + k], 0);
      if (m > RULE.slideDist && foot === 'rFoot') add('foot-slide', 'animation', META.effects?.ground ? 'minor' : 'major', r.frames[0].t, r.frames[r.frames.length - 1].t,
        `${id}: a planted foot slides ${m.toFixed(1)} m (${(Math.max(...r.frames.map((d, k) => sp[r.a + k])) / DT).toFixed(0)} m/s)` + (META.effects?.ground ? '; dust covers it' : ''),
        'a dash or skid must read as one: dust wake, afterimages, a leaning pose; a walk needs steps (stride) or world-locked feet');
    }
  }
}
// A2: joint pops · A3: blade
for (const id of ids) {
  const rel = (d, j) => sub(d.fighters[id].joints[j], d.fighters[id].joints.chest);
  for (const j of ['rHand', 'lHand', 'head']) {
    const st = F.map((d, i) => (i && d.fighters[id].visible && F[i - 1].fighters[id].visible ? dist(rel(d, j), rel(F[i - 1], j)) / Math.max(0.2, d.rate) : 0));
    st.forEach((s, i) => { if (i > 0 && i < st.length - 1 && s > RULE.popStep * STEP && s > 4 * Math.max(st[i - 1], st[i + 1], 0.02)) add('joint-pop', 'animation', 'major', F[i].t, F[i].t, `${id}: ${j} jumps ${s.toFixed(2)} m in one frame and stops`, 'a single-frame jump is a pop: check the keys around it (IK flip, an angle that wraps past ±180°)'); });
  }
  const ry = F.map((d, i) => (i ? Math.abs(d.fighters[id].ry - F[i - 1].fighters[id].ry) : 0));
  ry.forEach((a, i) => { if (a > 1.75 * STEP && F[i].fighters[id].visible) add('body-flip', 'animation', 'major', F[i].t, F[i].t, `${id}: the whole body turns ${((a * 180) / Math.PI).toFixed(0)}° in one frame`, 'a turn needs at least 4 frames: head first, then hips, then the blade'); });
  const tip = F.map((d, i) => (i && d.fighters[id].blade && F[i - 1].fighters[id].blade ? dist(d.fighters[id].blade.tip, F[i - 1].fighters[id].blade.tip) / STEP : 0));
  for (const r of runs(F, (d, i) => tip[i] > RULE.tipTeleport))
    add('blade-teleport', 'slash/smear', 'major', r.frames[0].t, r.frames[r.frames.length - 1].t, `${id}: the blade tip moves ${Math.max(...r.frames.map((d, k) => tip[r.a + k])).toFixed(1)} m in one frame (over ${(RULE.tipTeleport * FPS).toFixed(0)} m/s)`, 'slow the body through the cut with a speed ramp (film.ramps), or add an in-between; a smear cannot cover this much');
  for (const r of runs(F, (d, i) => tip[i] > RULE.tipNoSmear && tip[i] <= RULE.tipTeleport && d.fighters[id].smear !== undefined && d.fighters[id].smear < 0.15 && !d.impactFrame))
    add('fast-blade-no-smear', 'slash/smear', 'major', r.frames[0].t, r.frames[r.frames.length - 1].t, `${id}: the tip moves ${(Math.max(...r.frames.map((d, k) => tip[r.a + k])) * FPS).toFixed(0)} m/s with no smear`, 'every tip faster than about 12 m/s needs the light crescent (effects.ribbon.minSpeed)');
}
// A4: dead holds
{
  const alive = F.map((d, i) => {
    const p = F[Math.max(0, i - Math.round(12 / STEP))];
    if (dist(d.cam.pos, p.cam.pos) > 0.03 || angle(d.cam.dir, p.cam.dir) > 0.4 || Math.abs(d.cam.fov - p.cam.fov) > 0.3) return true;
    return vis(d).some((id) => p.fighters[id].visible && Object.keys(d.fighters[id].joints).some((j) => dist(d.fighters[id].joints[j], p.fighters[id].joints[j]) > 0.02));
  });
  for (const r of runs(F, (d, i) => i > 12 / STEP && !alive[i] && !free(d))) {
    const sec = r.frames.length * DT + 0.5;
    if (sec >= RULE.deadMinor) add('dead-hold', 'animation', sec >= RULE.deadMajor ? 'major' : 'minor', r.frames[0].t - 0.5, r.frames[r.frames.length - 1].t, `nothing moves for ${sec.toFixed(1)} s (no joint more than 2 cm, camera still)`, 'a hold must breathe: a moving hold, cloth, a slow push-in (2–5% per second), or cut it shorter');
  }
}
// E: cuts
const cutList = [...cuts].filter((i) => i > 0 && i < F.length).sort((a, b) => a - b);
{
  const edges = [0, ...cutList, F.length];
  const shots = edges.slice(1).map((e, k) => (e - edges[k]) * DT);
  shots.forEach((s, k) => {
    const t = edges[k] * DT;
    if (s < RULE.shotShort && shots.length > 1) add('shot-too-short', 'edit/rhythm', 'minor', t, t + s, `a ${Math.round(s * FPS)}-frame shot: too short to read`, 'inserts need 6–10 frames, action shots 12 or more');
    if (s > RULE.shotLong) add('shot-too-long', 'edit/rhythm', 'minor', t, t + s, `one shot runs ${s.toFixed(1)} s`, 'a Short wants a new angle or a clear camera move every 2–4 s');
  });
  for (const i of cutList) {
    const a = F[i - 1], b = F[i], v = vis(a).filter((id) => b.fighters[id].visible && a.fighters[id].onScreen >= 0.5 && b.fighters[id].onScreen >= 0.5);
    if (v.length >= 2) {
      const side = (d) => { const A = d.fighters[v[0]].joints.hips, B = d.fighters[v[1]].joints.hips; return Math.sign((B[0] - A[0]) * (d.cam.pos[2] - A[2]) - (B[2] - A[2]) * (d.cam.pos[0] - A[0])); };
      if (side(a) !== side(b)) add('line-cross', 'edit/rhythm', 'minor', b.t, b.t, 'the cut crosses the 180° line (the fighters swap sides of the screen)', 'stay on one side of the line between them, or cross it in a move, or cut through a neutral shot on the line');
    } else if (v.length === 1 && i > 3 && i < F.length - 3) {
      const vx = (d0, d1) => (chest(d1, v[0])[0] - chest(d0, v[0])[0]) / (2 * DT);
      const va = vx(F[i - 3], a), vb = vx(b, F[i + 2]);
      if (F[i - 3].fighters[v[0]].visible && F[i + 2].fighters[v[0]].visible && Math.abs(va) > 0.15 && Math.abs(vb) > 0.15 && Math.sign(va) !== Math.sign(vb)) add('direction-flip', 'edit/rhythm', 'minor', b.t, b.t, 'the subject changes screen direction across the cut', 'keep the direction of travel across a cut, or cut on the turn');
    }
  }
}
// T: speed ramps
if (META.ramps?.length) {
  const slow = F.filter((d) => d.rate < 0.7).length / F.length;
  if (slow > RULE.slowShareMinor) add('too-much-slow-motion', 'edit/rhythm', slow > RULE.slowShareMajor ? 'major' : 'minor', 0, DUR, `${(slow * 100).toFixed(0)}% of the film is in slow motion`, 'slow motion is for 2–3 key moments: under a quarter of the running time');
  const hits = [...(EVENTS?.impacts ?? []), ...(EVENTS?.contacts ?? []), ...(EVENTS?.ground ?? [])].map((h) => h.t);
  for (const r of META.ramps) {
    if (r.rate < RULE.slowRateMin) add('ramp-too-slow', 'edit/rhythm', 'minor', r.film0, r.film1, `a speed ramp goes down to ${r.rate}x`, 'below 0.15x a 24 fps preview stutters; 0.2–0.35 is the anime range');
    const turn = F.some((d, i) => i && d.t >= r.film0 && d.t <= r.film1 && ids.some((id) => Math.abs(d.fighters[id].ry - F[i - 1].fighters[id].ry) / Math.max(0.1, d.rate) > 0.12));
    const apex = F.some((d, i) => i > 0 && i < F.length - 1 && d.t >= r.film0 && d.t <= r.film1 && ids.some((id) => d.fighters[id].root[1] > 0.3 && d.fighters[id].root[1] >= F[i - 1].fighters[id].root[1] && d.fighters[id].root[1] >= F[i + 1].fighters[id].root[1]));
    if (!hits.some((h) => h >= r.film0 - 0.05 && h <= r.film1 + 0.05) && !turn && !apex) add('ramp-without-moment', 'edit/rhythm', 'minor', r.film0, r.film1, 'slow motion with no key moment inside it (no impact, landing, apex or turn)', 'put the ramp on the contact frame, the apex or the look');
  }
}
// H: the hook
{
  const first = F.filter((d) => d.t <= 0.5);
  if (!first.some((d) => free(d) || subjectsOf(d).some((id) => d.fighters[id].onScreen >= 0.5))) add('hook-no-subject', 'hook', 'major', 0, 0.5, 'no subject on screen in the first half second', 'a Short is judged in 1 second: open on the character or on the action');
  const p0 = PIX.find((p) => p.i === 0);
  if (p0 && p0.mean < RULE.lumaBlack + 4) add('hook-black', 'hook', 'major', 0, 0, `the film opens on black (first frame luma ${p0.mean})`, 'no fade from black on a Short: the first frame is the thumbnail of the scroll (film.fade.in ≤ 0.12)');
  const move = F.findIndex((d, i) => i > 0 && (isCut(i) || d.camStep / DT > 0.25 || vis(d).some((id) => F[i - 1].fighters[id].visible && Object.keys(d.fighters[id].joints).some((j) => dist(d.fighters[id].joints[j], F[i - 1].fighters[id].joints[j]) / DT > 1.2))));
  if (move < 0 || F[move].t > 2.0) add('hook-slow', 'hook', 'minor', 0, 2, `nothing moves faster than a breath in the first ${move < 0 ? DUR.toFixed(1) : F[move].t.toFixed(1)} s`, 'give the first second an event: a move, a cut, a line, a camera push');
}
// FX: effects that must exist
if (META.effects) {
  const g = (EVENTS?.ground ?? []).filter((e) => ['dash', 'skid', 'land'].includes(e.kind));
  if (g.length && !META.effects.ground) add('no-dust', 'effects', 'major', g[0].t, g[g.length - 1].t, `${g.length} dash / skid / landing event(s) without dust`, 'effects.ground must stay on: every dash, skid and landing kicks up sand');
  if (META.effects.smear === 'paper') add('paper-smear', 'effects', 'minor', 0, DUR, 'the smear is the old paper strip', 'effects are light, not paper: effects.ribbon.style "light"');
  if (!META.effects.fx) add('no-post-fx', 'effects', 'minor', 0, DUR, 'no post FX (no fxBase): no bloom on the eyes and the smear, no grade, no grain', 'add fxBase { grade, bloom, vignette, grain }');
}
// P: pixels
if (PIX.length) {
  const inkAt = (i) => F[Math.round(i / STEP)]?.impactFrame;
  const mid = PIX.filter((p) => p.t > 0.3 && p.t < DUR - 0.7);
  for (const p of mid) {
    if (p.mean < RULE.lumaBlack) add('black-frame', 'picture', 'critical', p.t, p.t, `frame ${p.i} is black (luma ${p.mean})`, 'a black frame inside a film is a render fault or the camera inside geometry');
    else if (!inkAt(p.i) && (p.mean > RULE.lumaBright || p.clip > RULE.clipMajor)) add('over-bright', 'picture', 'major', p.t, p.t, `frame ${p.i} is burnt out (luma ${p.mean}, ${(p.clip * 100).toFixed(0)}% clipped)`, 'lower the flash light / bloom (effects.sparkLight, impact "light"); a flash is 1–2 frames');
    else if (!inkAt(p.i) && p.clip > RULE.clipMinor) add('clipping', 'picture', 'minor', p.t, p.t, `frame ${p.i}: ${(p.clip * 100).toFixed(0)}% of the picture is clipped white`, 'glow should be the brightest thing, not a white hole: lower bloom strength or the light');
    if (!inkAt(p.i) && p.std < RULE.flatStd && p.mean >= RULE.lumaBlack) add('blank-frame', 'picture', 'major', p.t, p.t, `frame ${p.i} is almost one flat tone (contrast ${p.std})`, 'the subject left the frame or something fills the lens');
  }
  const stds = mid.filter((p) => !inkAt(p.i)).map((p) => p.std);
  const avg = stds.reduce((a, b) => a + b, 0) / (stds.length || 1);
  if (stds.length > 4 && avg < 38) add('low-contrast', 'picture', 'minor', 0, DUR, `the picture is flat on average (luma spread ${avg.toFixed(0)}; a lit paper scene with real shadow reaches 45–65)`, 'more shape from light: a darker shadow side, a rim light, a deeper grade (fxBase.grade), vignette');
}

// ---------- 3. sound ----------
const HITS = [...(EVENTS?.contacts ?? []).map((c) => ({ t: c.t, kind: 'blade contact', strong: true })), ...(EVENTS?.impacts ?? []).map((c) => ({ t: c.t, kind: 'impact' })),
  ...(EVENTS?.ground ?? []).filter((e) => e.kind === 'land').map((e) => ({ t: e.t, kind: 'landing' })), ...(film.shakes ?? []).map((s) => ({ t: s.t, kind: 'impact (shake)' }))]
  .sort((a, b) => a.t - b.t).filter((h, i, a) => !i || h.t - a[i - 1].t > 0.08);
const warp = EVENTS?.warp;
const toFilm = (c) => (c.body && warp ? (() => { const x = Math.max(0, Math.min(warp.film.length - 1, c.t / warp.dt)), i = Math.floor(x); return warp.film[i] + (warp.film[Math.min(i + 1, warp.film.length - 1)] - warp.film[i]) * (x - i); })() : c.t);
const CUES = [...(film.sounds ?? []).map((c) => ({ ...c, t: toFilm(c) })), ...(EVENTS?.cues ?? [])].filter((c) => !c.bed && !c.music).sort((a, b) => a.t - b.t);
const isWhoosh = (c) => /whoosh|swing|dash/.test(c.sfx ?? c.id);
{
  for (const h of HITS.filter((x) => x.strong)) if (!CUES.some((c) => isWhoosh(c) && c.t > h.t - 0.4 && c.t < h.t - 0.01)) add('no-whoosh-before-contact', 'sound', 'minor', h.t, h.t, 'a blade contact with no whoosh in the 0.4 s before it', 'the whoosh peaks 2 frames before the contact (autoSounds.whoosh)');
  for (const h of HITS) if (!CUES.some((c) => !isWhoosh(c) && Math.abs(c.t - h.t) < 0.07)) add('hit-without-sound', 'sound', 'major', h.t, h.t, `${h.kind} at ${h.t.toFixed(2)} s has no sound cue on it`, 'every hit the eye sees needs a transient on the same frame (film.sounds with "body": true, or autoSounds)');
  const tr = CUES.filter((c) => !c.layer);
  for (let i = 1; i < tr.length; i++) if (tr[i].t - tr[i - 1].t < RULE.mush && !(tr[i].id ?? '').startsWith((tr[i - 1].id ?? '~') + '-') && !((tr[i].sfx ?? '') === (tr[i - 1].sfx ?? '~'))) {
    const twoHits = HITS.some((h) => Math.abs(h.t - tr[i].t) < 0.05);
    if (!twoHits || !isWhoosh(tr[i - 1])) add('sound-mush', 'sound', 'minor', tr[i - 1].t, tr[i].t, `"${tr[i - 1].id}" and "${tr[i].id}" start ${(1000 * (tr[i].t - tr[i - 1].t)).toFixed(0)} ms apart`, 'two transients closer than 60 ms blur into one: offset one, or mark it "layer": "<id>" if it is a layer of the same hit');
  }
  const wh = CUES.filter(isWhoosh);
  for (let i = 1; i < wh.length; i++) if (wh[i].sfx && wh[i].sfx === wh[i - 1].sfx && wh[i].t - wh[i - 1].t < 1.5) add('same-whoosh-twice', 'sound', 'minor', wh[i - 1].t, wh[i].t, `the same whoosh ("${wh[i].sfx}") twice in a row`, 'use at least 3 whoosh sources and rotate them');
  for (const w of wh) if (wh.filter((x) => x.t >= w.t && x.t < w.t + 1).length > 3) { add('too-many-whooshes', 'sound', 'minor', w.t, w.t + 1, 'more than 3 whooshes in one second', 'autoSounds.whoosh.maxPerSec: 2'); break; }
}
const soundPath = opt('sound', fs.existsSync(`output/${NAME}-sound.mp4`) ? `output/${NAME}-sound.mp4` : null);
let SOUND = null;
if (soundPath && fs.existsSync(soundPath)) {
  const SR = 16000, pcm = spawnSync('ffmpeg', ['-loglevel', 'error', '-i', soundPath, '-ac', '1', '-ar', String(SR), '-f', 's16le', '-'], { maxBuffer: 1 << 28 }).stdout;
  const n = Math.floor(pcm.length / 2), W = SR / 100, env = [];
  let peak = 0;
  for (let i = 0; i + W <= n; i += W) { let s = 0; for (let k = 0; k < W; k++) { const v = pcm.readInt16LE((i + k) * 2) / 32768; s += v * v; peak = Math.max(peak, Math.abs(v)); } env.push(10 * Math.log10(s / W + 1e-10)); }
  const soundDur = env.length / 100;
  const mx = (a, b) => Math.max(-99, ...env.slice(Math.max(0, Math.round(a * 100)), Math.max(0, Math.round(b * 100))));
  const stale = Math.abs(soundDur - DUR) > 0.25;
  SOUND = { file: soundPath, dur: soundDur, peak: +(20 * Math.log10(peak + 1e-9)).toFixed(1), stale };
  if (stale) add('sound-out-of-date', 'sound', 'major', 0, DUR, `${soundPath} is ${soundDur.toFixed(2)} s long but the film is ${DUR} s: the mix is from an older cut`, 'render and run engine/sound.mjs again; measured sound checks are skipped');
  else {
    for (const h of HITS) {
      const hit = mx(h.t - 0.01, h.t + 0.13), pre = mx(h.t - 0.3, h.t - 0.03), d = hit - pre;
      h.hitDb = +hit.toFixed(1); h.overPre = +d.toFixed(1);
      if (hit < -38) add('hit-inaudible', 'sound', 'major', h.t, h.t, `${h.kind} at ${h.t.toFixed(2)} s is nearly silent in the mix (${hit.toFixed(0)} dB)`, 'raise the cue gain; the hit is the loudest thing in its half second');
      else if (d < RULE.hitOverPre) add('hit-not-above-whoosh', 'sound', h.strong && d < 6 ? 'major' : 'minor', h.t, h.t, `${h.kind} at ${h.t.toFixed(2)} s is only ${d.toFixed(0)} dB above what comes just before it (rule: ${RULE.hitOverPre} dB)`, 'dip the whoosh and the beds 80 ms before the hit, or raise the hit');
    }
    for (const r of runs(env.map((v, i) => ({ v, t: i / 100 })), (e) => e.v < -58)) if (r.frames.length > 70 && r.frames[0].t > 0.2 && r.frames[r.frames.length - 1].t < DUR - 0.8) add('silence-gap', 'sound', 'minor', r.frames[0].t, r.frames[r.frames.length - 1].t, `${(r.frames.length / 100).toFixed(1)} s of digital silence`, 'a bed (wind, sea, room tone) never drops out; silence before a strike is a dip of 12 dB, not zero');
    if (SOUND.peak > -0.4) add('sound-clipping', 'sound', 'minor', 0, DUR, `the mix peaks at ${SOUND.peak} dBFS`, 'limiter at -1 dBTP');
    const eb = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', soundPath, '-af', 'ebur128', '-f', 'null', '-'], { encoding: 'utf8' }).stderr ?? '';
    const m = eb.match(/Integrated loudness:\s+I:\s+(-?[\d.]+) LUFS/);
    if (m) { SOUND.lufs = +m[1]; if (SOUND.lufs < RULE.lufs[0] || SOUND.lufs > RULE.lufs[1]) add('loudness', 'sound', 'minor', 0, DUR, `integrated loudness ${SOUND.lufs} LUFS (target -14 ± 2)`, 'loudnorm=I=-14:TP=-1.5:LRA=9 at the end of the mix'); }
    const voicePath = `output/${NAME}.voice.json`;
    if (fs.existsSync(voicePath)) for (const l of JSON.parse(fs.readFileSync(voicePath, 'utf8')).lines ?? []) for (const h of HITS) if (h.t > l.t0 + 0.05 && h.t < l.t1 - 0.05) add('speech-over-action', 'sound', 'minor', h.t, h.t, `a ${h.kind} lands in the middle of a spoken line (${l.t0.toFixed(1)}–${l.t1.toFixed(1)} s)`, 'lines sit in the pauses of the fight; move the line or the blow by 0.3 s');
  }
} else add('no-mix', 'sound', 'info', 0, DUR, 'no mixed video found: only the cue lists were checked', `render, then node engine/sound.mjs --film ${filmPath}`);

// ---------- 4. score + report ----------
// the same fault found several times counts with a falling weight (1, 0.5, 0.33…), so one broken beat does not zero a category
const scores = Object.fromEntries(CATS.map((c) => [c, 10]));
const seen = {};
for (const f of [...findings].sort((a, b) => a.t0 - b.t0)) { const k = (seen[f.check] = (seen[f.check] ?? 0) + 1); scores[f.cat] = Math.max(0, scores[f.cat] - WEIGHT[f.sev] / k); }
for (const c of CATS) scores[c] = +scores[c].toFixed(1);
const total = +(CATS.reduce((s, c) => s + scores[c], 0) / CATS.length).toFixed(1);
const count = (s) => findings.filter((f) => f.sev === s).length;
const crit = count('critical'), maj = count('major'), min = count('minor');
const order = { critical: 0, major: 1, minor: 2, info: 3 };
findings.sort((a, b) => order[a.sev] - order[b.sev] || a.t0 - b.t0);
const sz = F.filter((d) => !free(d) && subjectsOf(d).length).map(sizeOf);
const metrics = {
  frames: NF, measured: F.length, cuts: cutList.length, avgShot: +(DUR / (cutList.length + 1)).toFixed(2),
  subjectSize: { min: +Math.min(...sz, 9).toFixed(2), median: +([...sz].sort((a, b) => a - b)[sz.length >> 1] ?? 0).toFixed(2), max: +Math.max(...sz, 0).toFixed(2) },
  slowMotionShare: +(F.filter((d) => d.rate < 0.7).length / F.length).toFixed(2),
  maxBlockers: +Math.max(...F.map((d) => d.blockers)).toFixed(2), pixelsChecked: PIX.length, sound: SOUND, hits: HITS,
};
const verdict = crit ? 'FAIL' : maj ? (flag('strict') ? 'FAIL (strict)' : 'PASS with majors') : 'PASS';
const icon = { critical: '✗ CRITICAL', major: '! major', minor: '· minor', info: '  info' };
const span = (f) => (f.f0 === f.f1 ? `f${f.f0} (${f.t0.toFixed(2)} s)` : `f${f.f0}–${f.f1} (${f.t0.toFixed(2)}–${f.t1.toFixed(2)} s)`);
const lines = [];
lines.push(`# Studio audit: ${NAME}`, '',
  `**${verdict}** · score **${total}/10** · ${crit} critical, ${maj} major, ${min} minor · ${NF} frames at ${FPS} fps (${DUR} s) · page \`${pagePath}\``, '',
  `Made by \`node tools/audit.mjs ${filmPath}\`. Rules and reasons: \`docs/STUDIO-STANDARD.md\`. How to read this: \`docs/AUDIT.md\`.`, '',
  '## Scores (measured rules only)', '', '| Category | Score | Findings |', '|---|---|---|',
  ...CATS.map((c) => `| ${c} | ${scores[c]} | ${findings.filter((f) => f.cat === c && f.sev !== 'info').length} |`), '',
  '## Findings', '', findings.length ? '| Severity | Where | Category | Check | What | Fix |\n|---|---|---|---|---|---|' : 'None.',
  ...findings.map((f) => `| ${f.sev} | ${span(f)} | ${f.cat} | \`${f.check}\` | ${f.msg} | ${f.fix ?? ''} |`), '',
  '## Numbers', '',
  `- Shots: ${cutList.length + 1} (${cutList.length} cuts at ${cutList.map((i) => (i * DT).toFixed(2)).join(', ') || 'none'} s), average ${metrics.avgShot} s`,
  `- Subject height in frame: min ${(metrics.subjectSize.min * 100).toFixed(0)}%, median ${(metrics.subjectSize.median * 100).toFixed(0)}%, max ${(metrics.subjectSize.max * 100).toFixed(0)}%`,
  `- Slow motion: ${(metrics.slowMotionShare * 100).toFixed(0)}% of the film${META.ramps?.length ? ` (${META.ramps.length} ramps)` : ''} · largest foreground blocker ${(metrics.maxBlockers * 100).toFixed(0)}% of the frame`,
  `- Pixels checked on ${PIX.length} frame(s)${framesDir ? ` from ${framesDir}` : ''}${PIX.length ? `: luma ${Math.min(...PIX.map((p) => p.mean))}–${Math.max(...PIX.map((p) => p.mean))}, most clipped ${(Math.max(...PIX.map((p) => p.clip)) * 100).toFixed(0)}%` : ''}`,
  SOUND ? `- Sound: ${SOUND.file}, ${SOUND.lufs ?? '?'} LUFS, peak ${SOUND.peak} dBFS${SOUND.stale ? ' (OUT OF DATE)' : ''}; hits: ${HITS.map((h) => `${h.t.toFixed(2)} s ${h.kind}${h.overPre !== undefined ? ` +${h.overPre} dB` : ''}`).join(' · ') || 'none'}` : '- Sound: not mixed yet (cue lists only)', '',
  '## Not measurable: look at the stills (docs/STUDIO-STANDARD.md §11 checklist)', '',
  '- [ ] Idea and hook: can you say the film in one sentence, and does second 1 promise it?',
  '- [ ] Every key pose reads as a black silhouette, with one line of action from the back foot to the blade tip',
  '- [ ] Anticipation → action → follow-through → settle on every strike, jump and turn (timing tables in the standard)',
  '- [ ] The cut is visible: the blade meets the target on a frame the camera can see',
  '- [ ] Light: one key, a darker shadow side, glow is the brightest thing; shadows soft and warm, not black holes',
  '- [ ] Effects are light and energy (smear, flash, ring, glint); only dust and a few shards are matter', '');
const md = lines.join('\n');
fs.mkdirSync('output', { recursive: true });
fs.writeFileSync(`output/${NAME}.audit.md`, md);
fs.writeFileSync(`output/${NAME}.audit.json`, JSON.stringify({ film: filmPath, verdict, total, scores, counts: { critical: crit, major: maj, minor: min }, findings, metrics, rules: RULE, pixels: PIX }, null, 1));
if (!flag('quiet')) {
  console.log(`\nSTUDIO AUDIT ${NAME}: ${verdict} · ${total}/10 · ${crit} critical, ${maj} major, ${min} minor`);
  console.log(CATS.map((c) => `${c} ${scores[c]}`).join(' · '));
  for (const f of findings) console.log(`${icon[f.sev].padEnd(11)} ${span(f).padEnd(28)} ${f.cat.padEnd(12)} ${f.msg}`);
  console.log(`\nreport: output/${NAME}.audit.md  (data: output/${NAME}.audit.json)`);
}
process.exit(crit || (flag('strict') && maj) ? 1 : 0);

// SONIC ADAPTIVE FOLEY: footsteps from skeletal foot contacts, synthesized on the CPU, no samples and no AI calls.
//
//   import { footstepCues, renderStep } from './foley.mjs'
//   const { cues, skipped } = footstepCues(stepEvents, { surface: 'sand', cast: { kojiro: { weight: 80, footwear: 'geta' } },
//                                                       camera: (t) => [x, y, z], room: 'open', avoid: groundCues, cache })
//
// Every step is its own sound, made from what is known about it (physically inspired, in the spirit of Cook's and
// Farnell's footstep models): a heel strike then a toe roll, each an excitation (footwear) filtered by the surface
// (sand crunches in fine grains, wood thumps and rings, stone clicks, metal rings, grass and earth thud dull),
// scaled by contact force (character weight x foot speed). The gap between heel and toe shrinks as the step gets
// faster. Distance to the camera lowers the level and the highs (air absorption); the acoustic space adds early
// reflections. A seed per actor, foot and step varies grain positions, pitch and level, so no two steps are identical,
// and the same film always renders the same steps. Steps that land on a cue the motion already has (a landing,
// a take-off, a dash, a skid) are left to that cue, and both feet landing on one frame make one step.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const FOLEY = 'sonic-foley/1';
const SR = 44100;
const DIST_FLOOR = 0.3;

// surface: grain = noise grains per heel (crunch), lp/hp = band of the noise, modes = resonances [Hz, decay s, level],
// click = hard transient share, body = low thump share
export const SURFACES = {
  sand: { grain: 26, lp: 5200, hp: 500, modes: [], click: 0.1, body: 0.35, len: 0.16 },
  earth: { grain: 8, lp: 2200, hp: 120, modes: [[90, 0.05, 0.6]], click: 0.15, body: 0.8, len: 0.12 },
  grass: { grain: 18, lp: 3800, hp: 900, modes: [], click: 0.05, body: 0.3, len: 0.18 },
  wood: { grain: 2, lp: 3000, hp: 150, modes: [[180, 0.08, 0.9], [420, 0.05, 0.5], [1150, 0.025, 0.25]], click: 0.5, body: 0.6, len: 0.15 },
  stone: { grain: 4, lp: 7000, hp: 900, modes: [[2400, 0.012, 0.3]], click: 0.9, body: 0.25, len: 0.08 },
  metal: { grain: 1, lp: 8000, hp: 600, modes: [[620, 0.35, 0.5], [1730, 0.22, 0.4], [3380, 0.12, 0.3]], click: 0.8, body: 0.2, len: 0.5 },
  water: { grain: 30, lp: 4500, hp: 300, modes: [], click: 0.02, body: 0.2, len: 0.3 },
};
// footwear: hard = attack sharpness and click share, damp = how much it softens the surface, heel = heel/toe balance
export const FOOTWEAR = {
  bare: { hard: 0.15, damp: 0.6, heel: 0.55 },
  soft: { hard: 0.35, damp: 0.4, heel: 0.6 },
  sandal: { hard: 0.55, damp: 0.25, heel: 0.6 },
  geta: { hard: 0.95, damp: 0.05, heel: 0.5 },        // wooden sandals: a clack on anything hard
  boot: { hard: 0.8, damp: 0.15, heel: 0.75 },
};
export const ROOMS = { open: [], room: [[0.011, 0.35], [0.019, 0.25], [0.031, 0.15]], hall: [[0.023, 0.4], [0.047, 0.3], [0.083, 0.22], [0.131, 0.12]] };

function prng(seed) {                                  // mulberry32 from a string seed
  let a = parseInt(crypto.createHash('sha1').update(String(seed)).digest('hex').slice(0, 8), 16) >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const onePole = (x, fc, hp = false) => {             // first-order low/high-pass, in place
  const a = Math.exp(-2 * Math.PI * fc / SR); let y = 0, px = 0;
  for (let i = 0; i < x.length; i++) { const v = x[i]; y = hp ? a * (y + v - px) : (1 - a) * v + a * y; px = v; x[i] = y; }
  return x;
};

/** One footstep as mono samples at 44.1 kHz. p: { surface, footwear, force 0..1, weight kg, gait 0 walk .. 1 run, distance m, room, seed } */
export function renderStep(p) {
  const S = SURFACES[p.surface] ?? SURFACES.earth, F = FOOTWEAR[p.footwear] ?? FOOTWEAR.soft, R = ROOMS[p.room] ?? [];
  const rnd = prng(p.seed ?? 'step');
  const jit = (a) => 1 + (rnd() * 2 - 1) * a;
  const force = Math.max(0.05, Math.min(1, p.force ?? 0.5));
  const heavy = Math.max(0.6, Math.min(1.6, (p.weight ?? 70) / 70));
  const gap = (0.085 - 0.06 * (p.gait ?? 0)) * jit(0.15);           // heel -> toe
  const len = S.len * (0.8 + 0.4 * force) + gap + 0.15 + (R.at(-1)?.[0] ?? 0);
  const x = new Float32Array(Math.ceil(len * SR));
  const hit = (t0, amp, sharp) => {
    const i0 = Math.floor(t0 * SR);
    // excitation: a short noise burst (sharper with harder footwear and more force) plus a low body thump
    const dec = 0.002 + 0.018 * (1 - sharp);
    const n = Math.floor(S.len * SR);
    const burst = new Float32Array(n);
    const grains = Math.max(1, Math.round(S.grain * (0.6 + 0.6 * force) * jit(0.2)));
    for (let g = 0; g < grains; g++) {                // granular crunch: each grain a tiny decaying noise
      const at = Math.floor((g === 0 ? 0 : Math.pow(rnd(), 1.6) * S.len * 0.8) * SR), gl = Math.floor((0.002 + 0.006 * rnd()) * SR), ga = (g === 0 ? 1 : 0.25 + 0.5 * rnd());
      for (let k = 0; k < gl && at + k < n; k++) burst[at + k] += ga * (rnd() * 2 - 1) * Math.exp(-k / (dec * SR + 1));
    }
    onePole(burst, S.hp, true);
    onePole(burst, S.lp * (0.6 + 0.4 * force) * (1 - 0.5 * F.damp) * jit(0.08));
    const click = S.click * (0.4 + F.hard) * (1 - F.damp * 0.7);
    for (let k = 0; k < n && i0 + k < x.length; k++) x[i0 + k] += amp * (0.6 + click) * burst[k];
    const f0 = 70 / Math.sqrt(heavy) * jit(0.05), bd = 0.03 + 0.03 * heavy;
    for (let k = 0; k < Math.floor(bd * 4 * SR) && i0 + k < x.length; k++) {
      const t = k / SR; x[i0 + k] += amp * S.body * heavy * 0.9 * Math.sin(2 * Math.PI * f0 * t) * Math.exp(-t / bd) * Math.min(1, t / 0.002);
    }
    for (const [fm, d, l] of S.modes) {               // surface resonances, struck harder by hard footwear
      const f = fm * jit(0.03), dd = d * (1 - 0.5 * F.damp);
      for (let k = 0; k < Math.floor(dd * 5 * SR) && i0 + k < x.length; k++) { const t = k / SR; x[i0 + k] += amp * l * (0.4 + 0.6 * F.hard) * Math.sin(2 * Math.PI * f * t) * Math.exp(-t / dd); }
    }
  };
  const amp = (0.35 + 0.65 * force) * jit(0.12);
  hit(0.002, amp * F.heel * 1.4, F.hard);
  hit(0.002 + gap, amp * (1 - F.heel) * 1.2, F.hard * 0.7);
  // distance: inverse-distance level beyond 2 m, air and occlusion take the highs
  const d = Math.max(1, p.distance ?? 3);
  onePole(x, Math.max(1800, 16000 / Math.sqrt(d)));
  const g = Math.min(1, Math.max(DIST_FLOOR, 2 / d));      // a film mix cheats distance: a far step drops ~10 dB at most
  // the space: early reflections (delay s, level)
  const y = Float32Array.from(x);
  for (const [dt, l] of R) { const o = Math.floor(dt * SR); for (let i = 0; i + o < y.length; i++) y[i + o] += l * x[i]; }
  let peak = 0;
  for (let i = 0; i < y.length; i++) { y[i] *= g; peak = Math.max(peak, Math.abs(y[i])); }
  if (peak > 0.98) for (let i = 0; i < y.length; i++) y[i] *= 0.98 / peak;
  const fade = Math.floor(0.02 * SR);
  for (let i = 0; i < fade; i++) y[y.length - 1 - i] *= i / fade;
  return y;
}

export function writeWav(file, y) {
  const b = Buffer.alloc(44 + y.length * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + y.length * 2, 4); b.write('WAVEfmt ', 8); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20);
  b.writeUInt16LE(1, 22); b.writeUInt32LE(SR, 24); b.writeUInt32LE(SR * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34);
  b.write('data', 36); b.writeUInt32LE(y.length * 2, 40);
  for (let i = 0; i < y.length; i++) b.writeInt16LE(Math.round(Math.max(-1, Math.min(1, y[i])) * 32767), 44 + i * 2);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, b);
}

const AVOID = /^(land|takeoff|dash|skid)$/;
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

/**
 * Footstep events (aethern-event footstep lines, or timeline footsteps: { t, actor | entities[0], side, speed, point })
 * -> cues for a mixer: { id, file, t, len, gain, why, event }. ctx: surface (name, or (step) => name), cast { id: { weight,
 * footwear } }, footwear / weight defaults, camera (t) => [x, y, z] or null, room, avoid (cues with event.kind), seed,
 * cache (folder for the rendered wavs), gain (dB trim), minGap (s, per actor).
 */
export function footstepCues(steps, ctx = {}) {
  const norm = steps.map((e) => {
    const d = e.data ?? e;
    return { t: +e.t, who: d.actor ?? e.actor ?? e.entities?.[0] ?? 'someone', side: d.side ?? e.side ?? '?', speed: +(d.speed ?? e.speed ?? 1.5),
      point: d.point ?? e.point ?? null, gait: d.gait, id: e.id };
  }).filter((s) => Number.isFinite(s.t)).sort((a, b) => a.t - b.t);
  const avoid = (ctx.avoid ?? []).map((c) => ({ t: c.event?.peakAt ?? c.t, who: c.event?.who ?? null, kind: c.event?.kind })).filter((c) => AVOID.test(c.kind ?? ''));
  const cues = [], skipped = [], last = {};
  const minGap = ctx.minGap ?? 0.12, cache = ctx.cache ?? '.cache/sonic/foley';
  for (const s of norm) {
    const clash = avoid.find((c) => Math.abs(c.t - s.t) < 0.15 && (!c.who || c.who === s.who));
    if (clash) { skipped.push({ t: s.t, who: s.who, why: `${clash.kind} cue already there` }); continue; }
    if (last[s.who] != null && s.t - last[s.who] < minGap) {
      const prev = cues.findLast((c) => c.event.who === s.who);
      if (prev && s.t - prev.t < 0.02) { prev.event.feet = 'both'; prev.event.force = Math.min(1, prev.event.force * 1.25); }   // both feet down
      skipped.push({ t: s.t, who: s.who, why: s.t - last[s.who] < 0.02 ? 'both feet on one frame: one step' : `under ${minGap} s after the last step` });
      continue;
    }
    last[s.who] = s.t;
    const who = ctx.cast?.[s.who] ?? {};
    const weight = who.weight ?? ctx.weight ?? 70, footwear = who.footwear ?? ctx.footwear ?? 'soft';
    const surface = typeof ctx.surface === 'function' ? ctx.surface(s) : (ctx.surface ?? 'earth');
    const force = Math.min(1, (weight / 70) * Math.min(1, s.speed / 3.5));
    const gait = s.gait ?? Math.min(1, Math.max(0, (s.speed - 1.5) / 3));
    const cam = ctx.camera?.(s.t);
    const distance = cam && s.point ? dist(cam, s.point) : (ctx.distance ?? 3);
    cues.push({ t: s.t, event: { kind: 'step', who: s.who, side: s.side, surface, footwear, weight, force: +(+force).toFixed(2), gait: +gait.toFixed(2),
      distance: +distance.toFixed(2), room: ctx.room ?? 'open', peakAt: +s.t.toFixed(3), source: s.id ?? null } });
  }
  cues.forEach((c, i) => {
    const e = c.event, seed = `${ctx.seed ?? ''}:${e.who}:${e.side}:${i}`;
    const params = { surface: e.surface, footwear: e.footwear, force: e.force * (e.feet === 'both' ? 1 : 1), weight: e.weight, gait: e.gait, distance: e.distance, room: e.room, seed };
    const key = crypto.createHash('sha1').update(JSON.stringify([FOLEY, params])).digest('hex').slice(0, 16);
    const file = path.join(cache, `${key}.wav`);
    let len;
    if (!fs.existsSync(file)) { const y = renderStep(params); writeWav(file, y); len = y.length / SR; } else len = (fs.statSync(file).size - 44) / 2 / SR;
    Object.assign(c, { id: `auto-step-${e.who}-${i}`, file, t: +Math.max(0, c.t - 0.002).toFixed(3), len: +len.toFixed(3), gain: +(10 ** ((ctx.gain ?? 0) / 20)).toFixed(3),
      why: `${e.who} ${e.side} foot on ${e.surface} (${e.footwear}, ${e.weight} kg, force ${e.force}, ${e.distance} m)` });
  });
  return { cues, skipped };
}

/** The steps as aethern-event/2 lines ("sonic.step"), so VYRN (`vyrn sync --expect`) or any tool can check them in the mix */
export function stepEvents(cues, project, media) {
  return cues.map((c, i) => ({ v: 2, project, media, id: `sonic.step.${String(i).padStart(3, '0')}`, type: 'sonic.step', t: c.event.peakAt,
    source: 'sonic', method: FOLEY, conf: 1, entities: [c.event.who],
    data: { cue: c.id, kind: 'step', aim: 'onset', sound: path.basename(c.file), side: c.event.side, surface: c.event.surface,
      footwear: c.event.footwear, force: c.event.force, distance: c.event.distance, room: c.event.room } }));
}

#!/usr/bin/env node
// SLEEVE CLEARANCE, measured instead of guessed.
//
//   node tools/sleeve_check.mjs            # every timeline in output/
//   node tools/sleeve_check.mjs a.timeline.json b.timeline.json
//
// The old check read the shoulder angle and assumed a raised arm means a buried head. That is a
// guess about geometry, and a guess cannot tell you whether a fix worked. This builds the real
// figure (engine/figure.js runs in node: three.js scene maths needs no canvas), applies each frame's
// pose, and measures where the sleeve actually is: the closest distance from the head's centre to
// the sleeve panel, treated as the segment from the sleeve's pivot on the forearm down to its hem.
//
// Fails if that distance drops below CLEAR for any frame of any film.
import fs from 'node:fs';
import './headless_dom.mjs';           // must come before figure.js: the paper textures want a canvas
import * as THREE from 'three';
import { makeFigure, applyPose, BASE_POSE } from '../engine/figure.js';

const HEAD_R = 0.11;      // the face is a 0.1 dodecahedron scaled (0.88, 1.18, 0.98)
const HEM_CLEAR = 0.04;   // the HEM is the visible edge: it must stay 4 cm clear of the head
const PANEL_CLEAR = 0;    // the panel may pass beside the head (the forearm does too) but never inside it
const HEM_Y = -0.235;     // the hem's local y inside the sleeve group (see makeFigure)

const fig = makeFigure({
  robe: '#efe6d4', sleeve: '#efe6d4', haori: '#9c2a25', hakama: '#5c2220',
  skin: '#efe3cc', collar: '#f6eedf', obi: '#2a1d1a', face: 'eyes',
});

const headC = new THREE.Vector3(), a = new THREE.Vector3(), b = new THREE.Vector3(), ab = new THREE.Vector3(), ac = new THREE.Vector3();

/** Shortest distance from point p to the segment a→b. */
function segDist(p, A, B) {
  ab.subVectors(B, A); ac.subVectors(p, A);
  const len2 = ab.lengthSq();
  const t = len2 > 0 ? Math.min(1, Math.max(0, ac.dot(ab) / len2)) : 0;
  return ac.sub(ab.multiplyScalar(t)).length();
}

/** Two gaps for this pose, both in metres and both negative when inside the head:
 *  hem   - the bottom edge of the sleeve, the line that reads on screen if it crosses the face
 *  panel - the whole sleeve from its mouth on the forearm down to that hem */
function gapsFor(pose) {
  applyPose(fig, { ...BASE_POSE, ...pose });
  fig.root.updateMatrixWorld(true);
  headC.set(0, 0.1, 0); fig.head.localToWorld(headC);
  let hem = Infinity, panel = Infinity;
  for (const g of fig.sleeves) {
    a.set(0, 0, 0); g.localToWorld(a);
    b.set(0, HEM_Y, 0); g.localToWorld(b);
    hem = Math.min(hem, b.distanceTo(headC) - HEAD_R);
    panel = Math.min(panel, segDist(headC, a, b) - HEAD_R);
  }
  return { hem, panel };
}

const files = process.argv.slice(2).filter((s) => !s.startsWith('--'));
const list = files.length ? files : fs.readdirSync('output').filter((f) => f.endsWith('.timeline.json'));
if (!list.length) { console.log('  no timelines built yet (run tools/timeline.mjs --all) — cannot check'); process.exit(1); }

let bad = 0, worstHem = null, worstPanel = null;
for (const name of list) {
  const path = name.includes('/') ? name : `output/${name}`;
  const tl = JSON.parse(fs.readFileSync(path, 'utf8'));
  for (const fr of tl.frames ?? []) {
    for (const [aid, act] of Object.entries(fr.actors ?? {})) {
      if (!act.pose) continue;
      const g = gapsFor(act.pose);
      const where = { name, frame: fr.f, aid };
      if (!worstHem || g.hem < worstHem.v) worstHem = { ...where, v: g.hem };
      if (!worstPanel || g.panel < worstPanel.v) worstPanel = { ...where, v: g.panel };
      if (g.hem < HEM_CLEAR || g.panel < PANEL_CLEAR) bad++;
    }
  }
}

const say = (w) => `${(w.v * 100).toFixed(1)} cm at ${w.name} frame ${w.frame}, ${w.aid}`;
if (bad) {
  console.log(`  ${bad} frame(s) bury the head in cloth — worst hem ${say(worstHem)}; worst panel ${say(worstPanel)}`);
  process.exit(1);
}
console.log(`  checked ${list.length} timeline(s): worst hem ${say(worstHem)}, worst panel ${say(worstPanel)} — both clear`);

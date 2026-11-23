// One command for the whole pipeline:  check → stills → render → sound → playbook
//   node engine/make.mjs [film/<name>.json]      (npm run film)
// Stops at the first failing step and says which one.
import { execSync } from 'node:child_process';
const film = process.argv[2] ?? 'film/ganryujima.json';
const steps = [
  ['Check the film file', `node engine/validate.mjs ${film}`],
  ['Render check stills (output/stills/)', `node engine/render.mjs --film ${film} --still auto`],
  ['Render every frame (slow: about 1.5 s per frame on CPU)', `node engine/render.mjs --film ${film}`],
  ['Find, check and place sounds', `node engine/sound.mjs --film ${film}`],
  ['Rebuild the playbook page', `python3 docs/build_playbook.py ${film}`],
];
for (const [i, [name, cmd]] of steps.entries()) {
  console.log(`\n=== Step ${i + 1}/${steps.length}: ${name}\n$ ${cmd}`);
  try { execSync(cmd, { stdio: 'inherit' }); }
  catch { console.log(`\nStopped at step ${i + 1} (${name}). Fix the problem above and run again.`); process.exit(1); }
}
console.log('\nDone. Video with sound: output/<film>-sound.mp4');

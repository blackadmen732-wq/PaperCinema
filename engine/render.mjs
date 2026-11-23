// Renders the film frame by frame in headless Chromium and encodes an MP4 with ffmpeg.
//   node engine/render.mjs                      → output/ganryujima.mp4
//   node engine/render.mjs --still 6,9,25.6     → output/stills/t6.png ...
//   node engine/render.mjs --from 24 --to 30    → render only part of the film
//   node engine/render.mjs --film film/other.json --out output/other.mp4
//   node engine/render.mjs --page engine/lookdev.html --film film/lookdev.json --query mode=metal --still 2 --prefix metal-
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { serve } from './serve.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf('--' + name); return i >= 0 ? args[i + 1] : dflt; };
const filmPath = opt('film', 'film/ganryujima.json');
const film = JSON.parse(fs.readFileSync(filmPath, 'utf8'));
const stills = opt('still');

const server = await serve(0);
const port = server.address().port;
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: args.includes('--vertical') ? { width: 720, height: 1280 } : { width: film.width, height: film.height } });
page.on('pageerror', (e) => console.error('PAGE ERROR:', e.message));
page.on('console', (m) => { if (m.type() === 'error') console.error('console:', m.text()); });
const pagePath = opt('page', 'engine/index.html');
const extra = [opt('query', ''), args.includes('--vertical') ? 'aspect=vertical' : ''].filter(Boolean).join('&');
await page.goto(`http://localhost:${port}/${pagePath}?render=1&film=/${filmPath}${extra ? '&' + extra : ''}`);
await page.waitForFunction('window.READY === true', null, { timeout: 120000 });

if (stills) {
  fs.mkdirSync('output/stills', { recursive: true });
  // --still auto = the middle of every shot plus every impact (a quick visual check of the whole film)
  const list = stills === 'auto'
    ? [...film.shots.map((s) => +((s.start + s.end) / 2).toFixed(2)), ...(film.shakes ?? []).map((s) => +(s.t + 0.1).toFixed(2))]
    : stills.split(',').map(Number);
  for (const t of list) {
    await page.evaluate((t) => window.renderAt(t), t);
    await page.screenshot({ path: `output/stills/${opt('prefix', '')}t${t}.png` });
    console.log('still', t);
  }
} else {
  const from = Number(opt('from', 0)), to = Number(opt('to', film.duration));
  const out = opt('out', `output/${path.basename(filmPath, '.json')}.mp4`);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const dir = opt('frames', 'output/frames');
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const frames = Math.round((to - from) * film.fps);
  const started = Date.now();
  for (let i = 0; i < frames; i++) {
    const t = from + i / film.fps;
    await page.evaluate((t) => window.renderAt(t), t);
    await page.screenshot({ type: 'jpeg', quality: 93, path: `${dir}/f${String(i).padStart(5, '0')}.jpg` });
    if (i % 24 === 0) console.log(`frame ${i}/${frames}  t=${t.toFixed(2)}s  ${((Date.now() - started) / 1000).toFixed(0)}s elapsed`);
  }
  console.log('encoding…');
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(film.fps), '-i', `${dir}/f%05d.jpg`,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['ignore', 'inherit', 'inherit'] });
  await new Promise((r) => ff.on('close', r));
  console.log('wrote', out);
}
await browser.close();
server.close();

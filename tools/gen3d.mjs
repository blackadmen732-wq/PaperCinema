#!/usr/bin/env node
// GEN3D: buy geometry from a 3D-generation service and bring it back as a file on disk.
//
//   node tools/gen3d.mjs text  "<prompt>"            --out assets/models/<name>.glb
//   node tools/gen3d.mjs image <reference.png|webp>  --out assets/models/<name>.glb
//   node tools/gen3d.mjs segment <model.glb>         --out assets/models/parts/<name>/
//   node tools/gen3d.mjs whoami                      # is a key reaching the service?
//
//   --service tripo|meshy   (default tripo)   --quality standard|detailed   --wait 900
//
// Why this file is vendor-agnostic. The thing worth owning is the skeleton, the timeline and the
// fight; the geometry is a commodity and the vendor for it will change. Everything downstream takes
// a GLB and nothing downstream knows where it came from: `reg.asset_part()` turns any GLB into a
// part on a socket, on a bone, made of paper (see .claude/skills/buy-the-geometry/SKILL.md). So a
// new service is a new `BACKENDS` entry, not a new pipeline.
//
// THE KEY IS NEVER IN A FILE (AGENTS.md rule 7). The environment's proxy injects credentials per
// host, so this sends a placeholder and the proxy replaces it. If the service answers 401, the key
// has not been added for that host yet — ask for it with the secure form, never in chat.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const args = process.argv.slice(2);
const cmd = args[0];
const subject = args[1];
const opt = (n, d) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : d; };

const SERVICE = opt('service', 'tripo');
const QUALITY = opt('quality', 'detailed');
const WAIT_S = Number(opt('wait', 900));
const OUT = opt('out');

// ---------------------------------------------------------------- the services
// Each backend says only: where to post, what to post, how to read a status, and where the file is.
const BACKENDS = {
  tripo: {
    host: 'openapi.tripo3d.ai',
    // $20/mo Pro is the cheapest plan whose output may be sold; the free tier is non-commercial,
    // which AGENTS.md rule 6 rules out for anything in this project.
    create: (kind, body) => ({
      url: `https://openapi.tripo3d.ai/v3/generation/${kind === 'image' ? 'image-to-model' : 'text-to-model'}`,
      body: { model: 'v3.1-20260211', texture: true, pbr: true, texture_quality: QUALITY, ...body },
    }),
    segment: (fileUrl) => ({
      url: 'https://openapi.tripo3d.ai/v3/processing/segmentation',
      body: { model_url: fileUrl, mode: 'semantic' },
    }),
    taskId: (j) => j?.data?.task_id ?? j?.task_id,
    status: (id) => `https://openapi.tripo3d.ai/v3/task/${id}`,
    read: (j) => {
      const d = j?.data ?? j;
      return { state: d?.status, progress: d?.progress ?? 0,
               files: [d?.output?.pbr_model, d?.output?.model, ...(d?.output?.parts ?? [])].filter(Boolean) };
    },
  },
  meshy: {
    host: 'api.meshy.ai',
    // Paid plans own their output; the free tier is CC BY 4.0, which means attribution on anything
    // sold. Rule 6 again.
    create: (kind, body) => ({
      url: `https://api.meshy.ai/openapi/v2/${kind === 'image' ? 'image-to-3d' : 'text-to-3d'}`,
      body: kind === 'image' ? body : { mode: 'preview', should_texture: true, ...body },
    }),
    segment: () => { throw new Error('meshy: no segmentation endpoint in the docs — generate parts separately, or use tripo'); },
    taskId: (j) => j?.result ?? j?.id,
    status: (id, kind) => `https://api.meshy.ai/openapi/v2/${kind === 'image' ? 'image-to-3d' : 'text-to-3d'}/${id}`,
    read: (j) => ({ state: j?.status, progress: j?.progress ?? 0,
                    files: [j?.model_urls?.glb, j?.model_url].filter(Boolean) }),
  },
};

const B = BACKENDS[SERVICE];
if (!B) { console.error(`unknown --service ${SERVICE}. known: ${Object.keys(BACKENDS).join(', ')}`); process.exit(2); }

const DONE = /^(SUCCESS|succeeded|completed|done)$/i;
const FAILED = /^(FAILED|failed|cancelled|expired|banned|unknown)$/i;

async function call(url, init = {}) {
  const r = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      // Placeholder on purpose. The proxy swaps it for the real key; a real key must never be typed
      // here, pasted into chat, or written to a file in this repository.
      Authorization: 'Bearer PROXY_INJECTED',
      ...(init.headers ?? {}),
    },
  });
  const text = await r.text();
  let j = null;
  try { j = JSON.parse(text); } catch { /* not json */ }
  if (r.status === 401 || r.status === 403) {
    throw new Error(`${B.host} refused the request (${r.status}). No credential is reaching it yet — `
      + 'the key goes in through the environment\'s secure form, for this host, and is never put in a file.');
  }
  if (!r.ok) throw new Error(`${url} -> ${r.status}: ${text.slice(0, 300)}`);
  return j ?? text;
}

async function poll(id, kind) {
  const until = Date.now() + WAIT_S * 1000;
  let last = -1;
  while (Date.now() < until) {
    const j = await call(B.status(id, kind));
    const { state, progress, files } = B.read(j);
    if (progress !== last) { process.stdout.write(`\r  ${state ?? '…'}  ${progress}%   `); last = progress; }
    if (DONE.test(state ?? '')) { console.log(); return files; }
    if (FAILED.test(state ?? '')) throw new Error(`\n  task ${id} ended as ${state}`);
    await new Promise((r) => setTimeout(r, 5000));
  }
  throw new Error(`\n  task ${id} did not finish within ${WAIT_S}s — raise it with --wait`);
}

async function download(url, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  const r = await fetch(url);
  if (!r.ok) throw new Error(`download ${url} -> ${r.status}`);
  fs.writeFileSync(dest, Buffer.from(await r.arrayBuffer()));
  const kb = (fs.statSync(dest).size / 1024).toFixed(0);
  console.log(`  wrote ${path.relative(ROOT, dest)}  (${kb} KB)`);
}

// ---------------------------------------------------------------- commands
if (cmd === 'whoami') {
  try {
    await call(B.status('probe-nonexistent-task', 'text'));
    console.log(`  ${SERVICE}: a credential is reaching ${B.host}`);
  } catch (e) {
    const m = String(e.message);
    if (/refused the request/.test(m)) { console.log(`  ${SERVICE}: ${m}`); process.exit(1); }
    console.log(`  ${SERVICE}: reached ${B.host} (it answered: ${m.slice(0, 120)})`);
  }
  process.exit(0);
}

if (!cmd || !subject || !OUT) {
  console.log(fs.readFileSync(new URL(import.meta.url), 'utf8').split('\n').slice(2, 14).join('\n').replace(/^\/\/ ?/gm, ''));
  process.exit(2);
}

if (cmd === 'text' || cmd === 'image') {
  let body;
  if (cmd === 'image') {
    const p = path.isAbsolute(subject) ? subject : path.join(ROOT, subject);
    if (!fs.existsSync(p)) { console.error(`no such reference image: ${subject}`); process.exit(2); }
    const ext = path.extname(p).slice(1).toLowerCase();
    const mime = ext === 'jpg' ? 'jpeg' : ext;
    body = { file: { type: mime, data: fs.readFileSync(p).toString('base64') } };
  } else {
    body = { prompt: subject };
  }
  const { url, body: payload } = B.create(cmd, body);
  console.log(`${SERVICE} ${cmd} -> ${path.relative(ROOT, path.isAbsolute(OUT) ? OUT : path.join(ROOT, OUT))}`);
  const j = await call(url, { method: 'POST', body: JSON.stringify(payload) });
  const id = B.taskId(j);
  if (!id) throw new Error(`no task id in the reply: ${JSON.stringify(j).slice(0, 300)}`);
  console.log(`  task ${id}`);
  const files = await poll(id, cmd);
  if (!files.length) throw new Error('task finished with no file');
  await download(files[0], path.isAbsolute(OUT) ? OUT : path.join(ROOT, OUT));
  console.log('\nNext: register it as a part —\n'
    + "  reg.asset_part('<name>', slot='<slot>', socket='<socket>', bone='<bone>',\n"
    + `                 file='${OUT}', height=<metres>, material='washi_natural')\n`
    + '  (.claude/skills/buy-the-geometry/SKILL.md)');
} else if (cmd === 'segment') {
  // One character generated once, then cut into parts, is the ONLY way sixteen parts end up in the
  // same style. Sixteen separate generations give sixteen different characters.
  const { url, body } = B.segment(subject);
  const j = await call(url, { method: 'POST', body: JSON.stringify(body) });
  const id = B.taskId(j);
  console.log(`  segmentation task ${id}`);
  const files = await poll(id, 'segment');
  const dir = path.isAbsolute(OUT) ? OUT : path.join(ROOT, OUT);
  let i = 0;
  for (const f of files) await download(f, path.join(dir, `part_${String(++i).padStart(2, '0')}.glb`));
  console.log(`\n  ${i} part(s) in ${path.relative(ROOT, dir)}`);
} else {
  console.error(`unknown command ${cmd} — want text, image, segment or whoami`);
  process.exit(2);
}

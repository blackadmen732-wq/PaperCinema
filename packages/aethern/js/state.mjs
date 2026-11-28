// JOB STATE: hash-keyed resume for any job made of independent parts (shots, chunks, files).
// Extracted from Paper Cinema's tools/render_supervisor.mjs, where it lets a killed render pick up where it
// stopped and re-render only the shots whose frames changed.
//
//   import { hashOf, loadState, stateWriter, isFresh } from '<aethern>/js/state.mjs';
//   const state = loadState('output/x.state.json');                 // { parts: {} } when missing or unreadable
//   const job = { id: 'S3', hash: hashOf(inputsOfS3) };
//   if (isFresh(state.shots[job.id], job.hash, { quality })) skip();
//   const save = stateWriter('output/x.state.json', state);          // one writer at a time
//   state.shots[job.id] = { status: 'done', hash: job.hash, quality }; await save();
import crypto from 'node:crypto';
import fs from 'node:fs';

/** short, stable content hash of any JSON-able value (12 hex chars of sha1, as the render supervisor used) */
export const hashOf = (obj) => crypto.createHash('sha1').update(JSON.stringify(obj)).digest('hex').slice(0, 12);

/** the saved state, or an empty one with `key` ({ shots: {} } by default) */
export function loadState(p, key = 'shots') { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return { [key]: {} }; } }

/** true when a part was finished with the same hash (and the same values for every key in `same`) */
export function isFresh(done, hash, same = {}) {
  return !!done && done.status === 'done' && done.hash === hash && Object.entries(same).every(([k, v]) => done[k] === v);
}

/**
 * A save function that serialises writes. Several workers finishing together would otherwise
 * interleave writes and leave the state file truncated, which costs a whole re-run.
 * Each write goes to a temp file and is renamed into place, so a crash mid-write keeps the old state.
 */
export function stateWriter(p, state) {
  let writing = Promise.resolve();
  const save = () => {
    writing = writing.then(async () => {
      const tmp = `${p}.tmp`;
      await fs.promises.writeFile(tmp, JSON.stringify(state, null, 1));
      await fs.promises.rename(tmp, p);
    });
    return writing;
  };
  save.flush = () => writing;
  return save;
}

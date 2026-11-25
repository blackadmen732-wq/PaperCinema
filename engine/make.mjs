// This used to be the whole pipeline, and it rendered the film with engine/figure.js — boxes and
// flat cards. Three character systems existed and this one used the worst, so every improvement to
// the real paper character was invisible in the only thing anyone ever watched.
//
// It is kept as a signpost rather than deleted, because it is named in older notes and in habit.
//   bash tools/film.sh film/<name>.json      the film: the modular paper character, through Blender
//   node engine/render.mjs --film <f>        the fast box pass, for blocking and timing only
import path from 'node:path';
const film = process.argv[2] ?? 'film/<name>.json';
const name = path.basename(film, '.json');
console.log(`
engine/make.mjs no longer makes films. It rendered them with the BOX character.

  Make the film          bash tools/film.sh ${film}
                         (validate -> motion -> timeline -> events -> audit -> Blender with the
                          modular paper character -> encode -> voice -> sound -> report)

  Block it out fast      node engine/render.mjs --film ${film}
                         Boxes. A storyboard. Minutes instead of an hour, and never the deliverable.

  Was it the real one?   node tools/promises.mjs --check-character
                         Reads output/${name}.render.json, which the pipeline writes as it renders.
`);
process.exit(2);

// A canvas stub so the engine's figure code can be MEASURED in node.
//
// engine/paper.js paints the washi textures on a 2d canvas. The scene maths - where a bone, a sleeve
// hem or a head ends up - does not depend on a single pixel of it, so a checker that only measures
// positions does not need a real canvas, only one that does not throw. Importing this module before
// engine/figure.js installs the smallest `document` that paper.js will accept.
//
// Never import this from anything that renders. It makes blank textures on purpose.
// The stub itself lives in the shared core; this path stays so every importer keeps working.
import '../packages/aethern/js/dom-stub.mjs';

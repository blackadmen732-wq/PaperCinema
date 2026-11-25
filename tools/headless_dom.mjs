// A canvas stub so the engine's figure code can be MEASURED in node.
//
// engine/paper.js paints the washi textures on a 2d canvas. The scene maths - where a bone, a sleeve
// hem or a head ends up - does not depend on a single pixel of it, so a checker that only measures
// positions does not need a real canvas, only one that does not throw. Importing this module before
// engine/figure.js installs the smallest `document` that paper.js will accept.
//
// Never import this from anything that renders. It makes blank textures on purpose.
const ctx2d = () => {
  const noop = () => {};
  const self = {
    canvas: null, fillStyle: '#000', strokeStyle: '#000', lineWidth: 1, lineCap: 'butt',
    globalAlpha: 1, globalCompositeOperation: 'source-over', filter: 'none', font: '10px sans-serif',
    fillRect: noop, strokeRect: noop, clearRect: noop, beginPath: noop, closePath: noop,
    moveTo: noop, lineTo: noop, arc: noop, ellipse: noop, quadraticCurveTo: noop, bezierCurveTo: noop,
    fill: noop, stroke: noop, save: noop, restore: noop, translate: noop, rotate: noop, scale: noop,
    setTransform: noop, transform: noop, clip: noop, drawImage: noop, fillText: noop, setLineDash: noop,
    createLinearGradient: () => ({ addColorStop: noop }),
    createRadialGradient: () => ({ addColorStop: noop }),
    createPattern: () => null,
    measureText: () => ({ width: 0 }),
    getImageData: (x, y, w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }),
    putImageData: noop,
  };
  return self;
};

if (typeof globalThis.document === 'undefined') {
  globalThis.document = {
    createElement(tag) {
      if (tag !== 'canvas') return { style: {}, appendChild() {}, setAttribute() {} };
      const c = { width: 300, height: 150, style: {}, nodeType: 1, getContext: () => ctx2d(), toDataURL: () => '' };
      return c;
    },
    createElementNS(_ns, tag) { return this.createElement(tag); },
    body: { appendChild() {} },
  };
}
if (typeof globalThis.window === 'undefined') globalThis.window = globalThis;

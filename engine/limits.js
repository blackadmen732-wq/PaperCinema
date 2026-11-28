// JOINT LIMITS: how far each channel may go before the limb reads as broken.
//
// One list, shared. These used to live inside engine/validate.mjs, where they warned about keys an
// author typed by hand and nothing else. That left a hole: a `move` with an `anime` dial, or a
// retargeted capture, produces its keys at EXPANSION time, so nothing was ever checked against
// these numbers. On 25 Nov that hole put the head at hx = -0.92 against a limit of 0.6 — the
// character threw its head 53 degrees back through a sword raise, in a film that passed validation.
//
// So: moves.js clamps to these, validate.mjs checks against these, and both import this file.
export const LIMITS = {
  rsx: [-3.1, 0.9], lsx: [-3.1, 0.9], rsz: [-1.6, 1.6], lsz: [-1.6, 1.6], rsy: [-1.2, 1.2], lsy: [-1.2, 1.2],
  rex: [-2.6, 0], lex: [-2.6, 0], rfy: [-1.6, 1.6], lfy: [-1.6, 1.6], rwx: [-1.0, 1.4], lwx: [-1.0, 1.4],
  rwz: [-0.6, 0.6], lwz: [-0.6, 0.6], tx: [-0.5, 1.2], ty: [-0.9, 0.9], tz: [-0.6, 0.6],
  cx: [-0.35, 0.5], cy: [-0.6, 0.6], cz: [-0.35, 0.35], nx: [-0.5, 0.5], ny: [-0.7, 0.7],
  hx: [-0.6, 0.6], hy: [-0.9, 0.9], hz: [-0.4, 0.4],
  rcy: [-0.35, 0.35], rcz: [-0.35, 0.35], lcy: [-0.35, 0.35], lcz: [-0.35, 0.35],
  rax: [-0.6, 0.7], lax: [-0.6, 0.7], rtx: [-0.3, 0.9], ltx: [-0.3, 0.9],
  px: [-0.35, 0.5], py: [-0.6, 0.6], pz: [-0.3, 0.3], stance: [0, 1.3], crouch: [-0.05, 0.6], weight: [-1, 1],
};

/** Hold a channel inside its limit. Unknown channels pass through untouched. */
export function clampCh(ch, v) {
  const l = LIMITS[ch];
  if (!l || typeof v !== 'number' || !Number.isFinite(v)) return v;
  return v < l[0] ? l[0] : v > l[1] ? l[1] : v;
}

// The head and neck are deliberately NOT exaggerated. Pushing a shoulder further reads as power;
// pushing a head further reads as a broken neck, because a viewer knows what a neck can do and has
// no intuition for a shoulder's limit. Anime exaggerates the body and holds the head still: the
// face is where the audience is looking.
export const NO_EXAGGERATE = new Set(['nx', 'ny', 'hx', 'hy', 'hz']);

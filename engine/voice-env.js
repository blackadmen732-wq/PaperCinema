// VOICE → eye glow: how loud a character is speaking at time t (0..1), from output/<film>.voice.json.
// Guide: docs/VOICE.md §6. Pure function of time, so any frame renders on its own.
//   import { loadVoice, voiceLevel } from './voice-env.js';
//   const voice = await loadVoice('voice-test');                 // null when the film has no voice file
//   emissive = glow * (1 + 0.8 * voiceLevel(voice, 'hero', t)); // pulse the eyes with the words
export async function loadVoice(film) {
  try {
    const r = await fetch(`/output/${film}.voice.json`);
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

export function voiceLevel(voice, who, t) {
  if (!voice) return 0;
  let v = 0;
  for (const e of voice.envelopes ?? []) {
    if (e.who !== who) continue;
    const f = (t - e.t0) * (e.fps ?? 24);
    if (f < 0 || f >= e.env.length) continue;
    const i = Math.floor(f), k = f - i;                     // linear between frames (smooth at any render fps)
    v = Math.max(v, e.env[i] * (1 - k) + (e.env[i + 1] ?? 0) * k);
  }
  return v;
}

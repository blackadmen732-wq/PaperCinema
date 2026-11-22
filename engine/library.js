// Library loader: builds swords and characters from the JSON presets in /library.
// Swords are assembled from parts (blade, tsuba, tsuka, saya, glow) listed in
// library/parts.json, so changing one line in a preset swaps that part.
import * as THREE from 'three';
import { makeKatana } from './props.js';
import { makeFigure } from './figure.js';
import { paper } from './paper.js';

const cache = {};
const getJSON = async (url) => (cache[url] ??= await (await fetch(url)).json());

export const loadParts = () => getJSON('/library/parts.json');
export const loadSword = (name) => getJSON(`/library/swords/${name}.json`);
export const loadCharacter = (name) => getJSON(`/library/characters/${name}.json`);

/**
 * buildSword(spec, parts, style)  style: 'metal' (real reflections) | 'paper' (Lantern Origami)
 * Returns makeKatana's { sword, saya, ... } plus .glowMaterial for animating the glow.
 */
export function buildSword(spec, parts, style = 'metal') {
  const metal = (name) => parts.metals[name] ?? parts.metals.iron;
  const steel = parts.steels[spec.blade.steel] ?? parts.steels.polished;
  const fin = parts.sayaFinishes[spec.saya.finish] ?? parts.sayaFinishes.lacquer;
  const glow = spec.glow;
  let m;
  if (style === 'paper') {
    const p = (c, o = {}) => paper(c, { repeat: 30, ...o });
    m = {
      blade: p(steel.color, { rough: 0.45, metal: 0.45 }),
      hamon: p(glow ? glow.color : steel.hamon, glow ? { glow: glow.strength } : {}),
      copper: p(metal(spec.habaki).color, { metal: 0.5 }),
      iron: p(metal(spec.tsuba.metal).color, { metal: 0.4 }),
      ito: p(spec.tsuka.wrap), same: p(spec.tsuka.diamonds),
      gold: p(metal(spec.tsuka.menuki).color, { metal: 0.6 }),
      lacquer: p(spec.saya.color, { rough: 0.35 }), sageo: p(spec.saya.cord), horn: p('#2a2522'),
    };
  } else {
    const phys = (o) => new THREE.MeshPhysicalMaterial({ side: THREE.DoubleSide, ...o });
    const metalMat = (name) => phys({ color: metal(name).color, metalness: 1, roughness: metal(name).rough });
    m = {
      blade: phys({ color: steel.color, metalness: 1, roughness: steel.rough }),
      hamon: phys({ color: glow ? '#120203' : steel.hamon, metalness: glow ? 0.2 : 1, roughness: 0.32,
        emissive: glow ? glow.color : '#000000', emissiveIntensity: glow ? glow.strength * 2 : 0 }),
      copper: metalMat(spec.habaki),
      iron: metalMat(spec.tsuba.metal),
      ito: phys({ color: spec.tsuka.wrap, roughness: 0.85, sheen: 1, sheenColor: '#3a3a44' }),
      same: phys({ color: spec.tsuka.diamonds, roughness: 0.6,
        emissive: glow ? glow.color : '#000000', emissiveIntensity: glow ? 0.3 : 0 }),
      gold: metalMat(spec.tsuka.menuki),
      lacquer: phys({ color: spec.saya.color, roughness: fin.rough, clearcoat: fin.clearcoat, clearcoatRoughness: 0.05 }),
      sageo: phys({ color: spec.saya.cord, roughness: 0.8, sheen: 1 }),
      horn: phys({ color: '#1c1917', roughness: 0.3, clearcoat: 0.6 }),
    };
  }
  const k = makeKatana({
    nagasa: spec.blade.length, sori: spec.blade.curve, tsukaLen: spec.tsuka.length,
    tsubaShape: spec.tsuba.shape, tsubaCutout: spec.tsuba.cutout, materials: m,
  });
  k.glowMaterial = glow ? m.hamon : null;
  k.spec = spec;
  return k;
}

/** One shared rigged body; the preset only changes colours and accessories. */
export function buildCharacter(preset) {
  return makeFigure({ ...preset.colors, ...preset.accessories, band: preset.accessories.band ?? undefined,
    haori: preset.accessories.haori ?? undefined });
}

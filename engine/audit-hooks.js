// AUDIT HOOKS: what the studio QA (tools/audit.mjs, docs/AUDIT.md) reads from a preview page.
// A page calls installAudit(...) once; nothing here runs unless the audit tool asks (window.AUDIT.at(t)),
// so pages render exactly as before.
//
//   installAudit({ scene, camera, W, H, fps, dur, page, fighters: () => [{ id, fig, sword, bladeLen, yOff, hidden }],
//                  stage(t) → { tb, subjects?, shot?, cut?, rate?, impactFrame?, smear? }, cuts?: [film times], meta?: {} })
//   stage(t) must pose everything and place the camera for film time t WITHOUT drawing.
//
// window.AUDIT.at(t) → one frame of measurements: camera, every fighter's joints (world + screen), blade, a screen
// box, lines of sight (ray casts against everything that is not a fighter), a 8 x 14 grid of rays for foreground
// blockers and the nearest geometry, the ground under the camera.
import * as THREE from 'three';

const JOINTS = {
  headTop: (f) => [f.head, 0, 0.3, 0], head: (f) => [f.head, 0, 0.1, 0], chest: (f) => [f.upper ?? f.torso, 0, 0.25, 0],
  hips: (f) => [f.hips, 0, 0, 0], rHand: (f) => [f.rH, 0, 0, 0], lHand: (f) => [f.lH, 0, 0, 0],
  rFoot: (f) => [f.legs?.r.foot ?? f.root, 0, 0, 0], lFoot: (f) => [f.legs?.l.foot ?? f.root, 0, 0, 0],
};
const r3 = (v) => [+v.x.toFixed(4), +v.y.toFixed(4), +v.z.toFixed(4)];

export function installAudit(o) {
  const { scene, camera, W, H } = o;
  const ray = new THREE.Raycaster();
  const _v = new THREE.Vector3(), _n = new THREE.Vector3(), _d = new THREE.Vector3();
  const under = (obj, roots) => { for (let p = obj; p; p = p.parent) if (roots.includes(p)) return true; return false; };
  const shown = (obj) => { for (let p = obj; p; p = p.parent) if (!p.visible) return false; return true; };
  const noAudit = (obj) => { for (let p = obj; p; p = p.parent) if (p.userData?.noAudit) return true; return false; };
  let solids = null;
  function collect(roots) {                       // every opaque mesh that is not part of a fighter
    const list = [];
    scene.traverse((m) => {
      if (!m.isMesh || m.isSprite || under(m, roots) || noAudit(m)) return;
      const mat = Array.isArray(m.material) ? m.material[0] : m.material;
      if (!mat || mat.transparent || mat.opacity < 0.9) return;
      if (!m.geometry.boundingSphere) m.geometry.computeBoundingSphere();
      m.userData._big = m.geometry.boundingSphere.radius * Math.max(m.scale.x, m.scale.z) > 6;   // ground, sea, sky cards
      list.push(m);
    });
    return list;
  }
  const first = (origin, dir, far) => {
    ray.set(origin, dir); ray.near = 0.001; ray.far = far;
    for (const h of ray.intersectObjects(solids, false)) if (shown(h.object)) return h;
    return null;
  };
  const isGround = (h) => {
    if (!h.face) return false;
    _n.copy(h.face.normal).transformDirection(h.object.matrixWorld);
    return h.object.userData._big && Math.abs(_n.y) > 0.7;
  };
  const project = (p) => {
    _v.copy(p).applyMatrix4(camera.matrixWorldInverse);
    const depth = -_v.z;
    _v.applyMatrix4(camera.projectionMatrix);
    return [+((_v.x + 1) / 2).toFixed(4), +((1 - _v.y) / 2).toFixed(4), +depth.toFixed(3)];
  };

  function at(t) {
    const st = o.stage(t) ?? {};
    scene.updateMatrixWorld(true);
    camera.updateMatrixWorld(true);
    camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
    const fighters = o.fighters();
    const roots = fighters.map((f) => f.fig.root);
    if (!solids) solids = collect(roots);
    const camPos = camera.position.clone(), fwd = camera.getWorldDirection(new THREE.Vector3());
    const out = { t: +t.toFixed(4), tb: +(st.tb ?? t).toFixed(4), shot: st.shot ?? null, cut: !!st.cut, rate: st.rate ?? 1,
      impactFrame: !!st.impactFrame, subjects: st.subjects ?? null,
      cam: { pos: r3(camPos), dir: r3(fwd), fov: +camera.fov.toFixed(2), aspect: +(W / H).toFixed(4) }, fighters: {} };
    let nearestSubject = Infinity;
    for (const f of fighters) {
      const vis = !f.hidden && shown(f.fig.root);
      const F = { visible: vis, root: r3(f.fig.root.position), ry: +f.fig.root.rotation.y.toFixed(4), joints: {}, screen: {} };
      if (!vis) { out.fighters[f.id] = F; continue; }
      let x0 = 9, y0 = 9, x1 = -9, y1 = -9, on = 0, n = 0;
      for (const [name, fn] of Object.entries(JOINTS)) {
        const [obj, x, y, z] = fn(f.fig);
        const p = obj.localToWorld(new THREE.Vector3(x, y, z));
        const s = project(p);
        F.joints[name] = r3(p); F.screen[name] = s;
        n++;
        if (s[2] > 0.02) { x0 = Math.min(x0, s[0]); x1 = Math.max(x1, s[0]); y0 = Math.min(y0, s[1]); y1 = Math.max(y1, s[1]); if (s[0] >= 0 && s[0] <= 1 && s[1] >= 0 && s[1] <= 1) on++; }
        nearestSubject = Math.min(nearestSubject, p.distanceTo(camPos));
      }
      F.box = [x0, y0, x1, y1].map((v) => +v.toFixed(4));
      F.onScreen = +(on / n).toFixed(3);
      F.dist = +new THREE.Vector3(...F.joints.chest).distanceTo(camPos).toFixed(3);
      if (f.sword && shown(f.sword)) {
        const yo = f.yOff ?? -0.012;
        const g = f.sword.localToWorld(new THREE.Vector3(0, yo, 0)), tip = f.sword.localToWorld(new THREE.Vector3(f.bladeLen, yo, 0));
        F.blade = { guard: r3(g), tip: r3(tip), tipScreen: project(tip) };
        // the blade passing through the lens: distance from the camera to the blade segment
        const ab = tip.clone().sub(g), k = Math.max(0, Math.min(1, camPos.clone().sub(g).dot(ab) / ab.lengthSq()));
        F.bladeToCam = +g.clone().addScaledVector(ab, k).distanceTo(camPos).toFixed(3);
      }
      // line of sight to head, chest and hips: anything that is not a fighter in the way?
      F.blocked = {};
      for (const name of ['head', 'chest', 'hips']) {
        const p = new THREE.Vector3(...F.joints[name]);
        const d = p.distanceTo(camPos);
        const h = first(camPos, _d.copy(p).sub(camPos).normalize(), d - 0.12);
        F.blocked[name] = h && !(isGround(h) && h.point.y < 0.05 && p.y < 0.2) ? +(h.distance).toFixed(2) : 0;
      }
      if (st.smear) F.smear = +(st.smear[f.id] ?? 0).toFixed(3);
      out.fighters[f.id] = F;
    }
    // a grid of rays: foreground blockers (things nearer than the subject that are not ground) and the nearest geometry
    const GX = 8, GY = 14;
    const subjD = Math.min(...Object.values(out.fighters).filter((f) => f.visible).map((f) => f.dist), 1e9);
    let blockers = 0, nearest = Infinity;
    const cells = [];
    for (let j = 0; j < GY; j++) for (let i = 0; i < GX; i++) {
      _v.set(((i + 0.5) / GX) * 2 - 1, 1 - ((j + 0.5) / GY) * 2, 0.5).unproject(camera).sub(camPos).normalize();
      const h = first(camPos, _v, Math.min(subjD, 80));
      if (!h) continue;
      nearest = Math.min(nearest, h.distance);
      if (!isGround(h) && h.distance < subjD * 0.85) { blockers++; cells.push(i + j * GX); }
    }
    out.blockers = +(blockers / (GX * GY)).toFixed(3);
    out.blockerCells = cells;
    out.nearest = +Math.min(nearest, 99).toFixed(3);
    out.nearestSubject = +Math.min(nearestSubject, 99).toFixed(3);
    // ground under the camera: the highest up-facing big surface under it; and is a big surface right above it?
    ray.set(new THREE.Vector3(camPos.x, 60, camPos.z), new THREE.Vector3(0, -1, 0)); ray.near = 0; ray.far = 200;
    let ground = null, roof = null;
    for (const h of ray.intersectObjects(solids, false)) {
      if (!shown(h.object) || !isGround(h)) continue;
      if (h.point.y <= camPos.y + 0.02) { ground = h.point.y; break; }
      roof = h.point.y;
    }
    out.cam.ground = ground === null ? null : +ground.toFixed(3);
    out.cam.underGround = roof !== null && roof - camPos.y < 30;
    return out;
  }
  window.AUDIT = { meta: { page: o.page, W, H, fps: o.fps, dur: o.dur, cuts: o.cuts ?? null, ...(o.meta ?? {}) }, at };
}

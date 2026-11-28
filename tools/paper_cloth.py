#!/usr/bin/env python3
"""PAPER CLOTH: garments that move like folded paper, not like fabric (Mark, 27 Nov: "make the clothes like real
sleeves and paper, like real clothes that can move").

Position-based dynamics (the method games and film cloth use), with paper's own rules:

  1. paper does not stretch        distance constraints along every edge of the panel's grid (and its diagonals)
  2. paper is stiff to bend...     a bending constraint across every interior edge (the two opposite corners keep
                                   their distance), strong
  3. ...except along its creases   edges marked as folds bend easily: the panel hinges on its crease lines like
                                   origami, flat facets between them (fabric bends everywhere; paper does not)
  4. it never enters the body      every point is pushed out of the body's capsules (the bake's collision bodies)
  5. it hangs from the body        pinned points follow their bone every sub-step
  6. air                           gravity, drag, and wind pushing each triangle by how squarely it faces the wind
                                   (a sleeve side-on to the wind barely moves; face-on it billows)

Pure numpy and deterministic (the same motion gives the same cloth, so every render worker agrees): the bake runs it
once per garment and writes every frame's points. Blender's own Python has numpy, so the same module runs there.

    cl = PaperCloth(rest_points, triangles, pins, creases=[(i, j), ...])
    for frame in ...: cl.step(1 / 30, pin_targets, capsules=[(a, b, r), ...], wind=(x, y, z))
    cl.X  -> the points now

`grid(nu, nv, origin, du, dv)` builds a panel: a rectangle of points with its triangles; `crease_lines` marks folds.
"""
import math

import numpy as np


def grid(nu, nv, origin, du, dv):
    """Points of an nu x nv panel starting at `origin`, columns along du (m per step, a vector), rows along dv; and its
    triangles (two per cell, alternating diagonals so the panel has no preferred fold)."""
    o, du, dv = np.asarray(origin, float), np.asarray(du, float), np.asarray(dv, float)
    X = np.array([o + du * i + dv * j for j in range(nv) for i in range(nu)])
    tris = []
    for j in range(nv - 1):
        for i in range(nu - 1):
            a, b, c, d = j * nu + i, j * nu + i + 1, (j + 1) * nu + i, (j + 1) * nu + i + 1
            if (i + j) % 2:
                tris += [(a, b, d), (a, d, c)]
            else:
                tris += [(a, b, c), (b, d, c)]
    return X, np.array(tris, int)


def crease_lines(nu, nv, columns=(), rows=()):
    """The edges of the grid that lie on fold lines: every edge along a vertical line at column i (for i in columns)
    and along a horizontal line at row j."""
    out = set()
    for i in columns:
        for j in range(nv - 1):
            out.add(tuple(sorted((j * nu + i, (j + 1) * nu + i))))
    for j in rows:
        for i in range(nu - 1):
            out.add(tuple(sorted((j * nu + i, j * nu + i + 1))))
    return out


class PaperCloth:
    def __init__(self, X0, tris, pins=(), creases=(), stretch=1.0, bend=0.6, crease_bend=0.02, drag=1.2,
                 thickness=0.012, density=0.25, iterations=10, substeps=6, plastic=0.0, tethers=True, solver='gs'):
        """density: kg per square metre of the panel (washi ~0.05, a heavy folded paper costume ~0.2-0.4: light enough
        for the wind to lift it, heavy enough not to flutter like tissue). Each point carries a third of the mass of
        every triangle it belongs to."""
        self.X = np.array(X0, float)
        self.P = self.X.copy()                       # last positions (velocity = (X - P) / dt)
        self.tris = np.asarray(tris, int)
        n = len(self.X)
        A, B, C = self.X[self.tris[:, 0]], self.X[self.tris[:, 1]], self.X[self.tris[:, 2]]
        tri_area = 0.5 * np.linalg.norm(np.cross(B - A, C - A), axis=1)
        m = np.zeros(n)
        for k in range(3):
            np.add.at(m, self.tris[:, k], tri_area * density / 3.0)
        self.mass = np.maximum(m, 1e-6)
        self.w = 1.0 / self.mass
        self.pins = np.array(sorted(set(int(p) for p in pins)), int)
        self.w[self.pins] = 0.0
        self.drag, self.thick = drag, thickness
        self.iterations, self.substeps = iterations, substeps
        self.plastic = plastic                       # 0: always springs back to its rest folds; >0 creases remember
        # edges and their triangles
        edge_tris = {}
        for t, (a, b, c) in enumerate(self.tris):
            for e in ((a, b), (b, c), (c, a)):
                edge_tris.setdefault(tuple(sorted(e)), []).append(t)
        E = np.array(sorted(edge_tris), int)
        self.E = E
        self.E_rest = np.linalg.norm(self.X[E[:, 1]] - self.X[E[:, 0]], axis=1)
        self.E_k = np.full(len(E), stretch)
        # bending: across every interior edge, the two corners opposite it keep their distance
        creases = {tuple(sorted(c)) for c in creases}
        Bi, Bj, Bk = [], [], []
        for e, ts in edge_tris.items():
            if len(ts) != 2:
                continue
            k0 = [v for v in self.tris[ts[0]] if v not in e][0]
            k1 = [v for v in self.tris[ts[1]] if v not in e][0]
            Bi.append(k0)
            Bj.append(k1)
            Bk.append(crease_bend if e in creases else bend)
        self.B = np.array([Bi, Bj], int).T if Bi else np.zeros((0, 2), int)
        self.B_rest = np.linalg.norm(self.X[self.B[:, 1]] - self.X[self.B[:, 0]], axis=1) if len(Bi) else np.zeros(0)
        self.B_k = np.array(Bk, float)
        # LONG-RANGE ATTACHMENTS (Kim, Chentanez & Mueller 2012): every free point is tethered to every pin by its rest
        # distance ALONG THE SHEET (shortest path over the rest edges). However fast the pins move, no point can get
        # further from a pin than the paper between them allows. Without them, a sleeve on Kojiro's striking arm
        # (~10 m/s at the elbow) stretched 31%; the edge constraints alone cannot pass a jerk that fast down the sheet.
        self.T_i = self.T_j = np.zeros(0, int)
        self.T_L = np.zeros(0)
        if tethers and len(self.pins):
            import heapq
            adj = [[] for _ in range(n)]
            for (i, j), L in zip(E, self.E_rest):
                adj[i].append((j, L))
                adj[j].append((i, L))
            Ti, Tj, TL = [], [], []
            for pin in self.pins:
                dist = np.full(n, np.inf)
                dist[pin] = 0.0
                hq = [(0.0, int(pin))]
                while hq:
                    d0, u = heapq.heappop(hq)
                    if d0 > dist[u]:
                        continue
                    for v_, L in adj[u]:
                        if d0 + L < dist[v_]:
                            dist[v_] = d0 + L
                            heapq.heappush(hq, (d0 + L, v_))
                for q in range(n):
                    if self.w[q] > 0 and np.isfinite(dist[q]):
                        Ti.append(q)
                        Tj.append(int(pin))
                        TL.append(dist[q])
            self.T_i, self.T_j, self.T_L = np.array(Ti, int), np.array(Tj, int), np.array(TL)
        # GAUSS-SEIDEL BY COLOUR: constraints split into groups in which no two share a point, solved group after group
        # with full corrections (each group vectorised). The averaged Jacobi pass converges far slower: on Kojiro's
        # strike (the arm stopping from 4 m/s in two frames) it left the sheet stretched 25% at 10 iterations x 6
        # sub-steps (14% at 40 iterations); paper must not stretch.
        self.solver = solver
        self.E_groups = self._colour(self.E)
        self.B_groups = self._colour(self.B) if len(self.B) else []
        self.frame = 0
        self.log = {'pushed': [], 'stretch': []}

    @staticmethod
    def _colour(pairs):
        """Greedy edge colouring: lists of constraint indices, no two in a list sharing a point."""
        groups, used = [], []
        for c, (i, j) in enumerate(np.asarray(pairs, int)):
            for g, pts in zip(groups, used):
                if i not in pts and j not in pts:
                    g.append(c)
                    pts.update((int(i), int(j)))
                    break
            else:
                groups.append([c])
                used.append({int(i), int(j)})
        return [np.array(g, int) for g in groups]

    def _distance_gs(self, pairs, rest, k, groups):
        for g in groups:
            i, j = pairs[g, 0], pairs[g, 1]
            d = self.X[j] - self.X[i]
            L = np.linalg.norm(d, axis=1)
            ws = self.w[i] + self.w[j]
            ok = (L > 1e-9) & (ws > 0)
            if not ok.any():
                continue
            i, j, d, L, ws = i[ok], j[ok], d[ok], L[ok], ws[ok]
            s = (L - rest[g][ok]) / ws * k[g][ok]
            corr = d / L[:, None] * s[:, None]
            self.X[i] += corr * self.w[i][:, None]
            self.X[j] -= corr * self.w[j][:, None]

    # ------------------------------------------------------------------ constraints (Jacobi, averaged, vectorised)
    def _distance(self, idx, rest, k, omega=1.0):
        i, j = idx[:, 0], idx[:, 1]
        d = self.X[j] - self.X[i]
        L = np.linalg.norm(d, axis=1)
        ok = L > 1e-9
        n = np.zeros_like(d)
        n[ok] = d[ok] / L[ok, None]
        ws = self.w[i] + self.w[j]
        good = ok & (ws > 0)
        C = (L - rest)
        s = np.zeros(len(L))
        s[good] = C[good] / ws[good] * k[good]
        corr = n * s[:, None]
        dX = np.zeros_like(self.X)
        cnt = np.zeros(len(self.X))
        np.add.at(dX, i, corr * self.w[i][:, None])
        np.add.at(dX, j, -corr * self.w[j][:, None])
        np.add.at(cnt, i, good.astype(float))
        np.add.at(cnt, j, good.astype(float))
        self.X += omega * dX / np.maximum(cnt, 1.0)[:, None]

    def _tether(self):
        """Pull every point back inside each of its tethers (only the free end moves; unilateral)."""
        if not len(self.T_i):
            return
        d = self.X[self.T_i] - self.X[self.T_j]
        L = np.linalg.norm(d, axis=1)
        over = L > self.T_L
        if not over.any():
            return
        # several tethers can pull one point: apply the tightest (the largest overshoot) per point
        k = np.where(over)[0]
        excess = L[k] - self.T_L[k]
        order = np.argsort(-excess)
        seen = set()
        for idx in k[order]:
            q = int(self.T_i[idx])
            if q in seen:
                continue
            seen.add(q)
            dd = self.X[q] - self.X[self.T_j[idx]]
            l = float(np.linalg.norm(dd))
            if l > self.T_L[idx]:
                self.X[q] = self.X[self.T_j[idx]] + dd / l * self.T_L[idx]

    def _collide(self, capsules):
        pushed = 0
        for a, b, r in capsules:
            a, b = np.asarray(a, float), np.asarray(b, float)
            ab = b - a
            L2 = float(ab @ ab) or 1e-12
            t = np.clip(((self.X - a) @ ab) / L2, 0.0, 1.0)
            c = a + t[:, None] * ab
            d = self.X - c
            dist = np.linalg.norm(d, axis=1)
            inside = (dist < r + self.thick) & (self.w > 0)
            if inside.any():
                nrm = d[inside] / np.maximum(dist[inside], 1e-9)[:, None]
                self.X[inside] = c[inside] + nrm * (r + self.thick)
                pushed += int(inside.sum())
        return pushed

    def _aero(self, wind, rho=0.6):
        """Each triangle is pushed by the wind relative to its own motion, by how squarely it faces it."""
        A, B, C = self.X[self.tris[:, 0]], self.X[self.tris[:, 1]], self.X[self.tris[:, 2]]
        cr = np.cross(B - A, C - A)
        area2 = np.linalg.norm(cr, axis=1)
        nrm = cr / np.maximum(area2, 1e-12)[:, None]
        v = (self.X - self.P)                         # this sub-step's motion (scaled below)
        vt = (v[self.tris[:, 0]] + v[self.tris[:, 1]] + v[self.tris[:, 2]]) / 3.0
        rel = np.asarray(wind, float)[None, :] - vt / self._h
        f = rho * 0.5 * area2 * np.sum(rel * nrm, axis=1)            # pressure on the face
        F = nrm * f[:, None]
        acc = np.zeros_like(self.X)
        for k in range(3):
            np.add.at(acc, self.tris[:, k], F / 3.0)
        return acc * self.w[:, None]

    # ------------------------------------------------------------------ one frame
    def step(self, dt, pin_targets=None, capsules=(), wind=(0.0, 0.0, 0.0), gravity=(0.0, 0.0, -9.81)):
        """Advance one frame of dt seconds. pin_targets: (len(pins), 3) where the pinned points are at the END of the
        frame (they are moved there smoothly over the sub-steps)."""
        h = dt / self.substeps
        self._h = h
        g = np.asarray(gravity, float)
        pin0 = self.X[self.pins].copy() if len(self.pins) else None
        pushed = 0
        for s in range(self.substeps):
            v = (self.X - self.P) / h * math.exp(-self.drag * h)
            acc = np.where(self.w[:, None] > 0, g[None, :], 0.0) + self._aero(wind)
            self.P = self.X.copy()
            self.X = self.X + v * h + acc * h * h
            if pin_targets is not None and len(self.pins):
                u = (s + 1) / self.substeps
                self.X[self.pins] = pin0 + (np.asarray(pin_targets, float) - pin0) * u
            for _ in range(self.iterations):
                if self.solver == 'gs':
                    self._distance_gs(self.E, self.E_rest, self.E_k, self.E_groups)
                    if len(self.B):
                        self._distance_gs(self.B, self.B_rest, self.B_k, self.B_groups)
                else:
                    self._distance(self.E, self.E_rest, self.E_k)
                    if len(self.B):
                        self._distance(self.B, self.B_rest, self.B_k)
                self._tether()
                pushed += self._collide(capsules)
            if pin_targets is not None and len(self.pins):
                self.X[self.pins] = pin0 + (np.asarray(pin_targets, float) - pin0) * ((s + 1) / self.substeps)
        if self.plastic > 0 and len(self.B):          # creases remember: the bending rest drifts toward the shape now
            now = np.linalg.norm(self.X[self.B[:, 1]] - self.X[self.B[:, 0]], axis=1)
            self.B_rest += (now - self.B_rest) * self.plastic
        stretch = np.abs(np.linalg.norm(self.X[self.E[:, 1]] - self.X[self.E[:, 0]], axis=1) / self.E_rest - 1.0)
        self.log['pushed'].append(pushed)
        self.log['stretch'].append(float(stretch.max()))
        self.frame += 1
        return self.X


if __name__ == '__main__':
    # a quick self-test: a 0.5 x 0.45 m panel pinned along its top edge falls, settles, does not stretch
    X, T = grid(9, 8, (0, 0, 0), (0.0625, 0, 0), (0, 0, -0.064))
    cl = PaperCloth(X, T, pins=range(9), creases=crease_lines(9, 8, columns=(2, 4, 6)))
    for _ in range(60):
        cl.step(1 / 30, pin_targets=X[:9], wind=(0, 3.0, 0))
    print('max stretch %.3f%%, lowest point %.3f m, hem swing %.3f m' % (
        100 * max(cl.log['stretch']), cl.X[:, 2].min(), float(np.abs(cl.X[-9:, 1]).max())))

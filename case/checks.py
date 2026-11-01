"""Printability checks of the exported print files: thin walls and steep overhangs.

Run:  .venv/bin/python -m case.checks
"""
from collections import Counter

import numpy as np
import trimesh

from . import params as P


def thin_walls(m, limit=0.9, n=40000, seed=5):
    """Walls thinner than `limit`, measured between facing surfaces (edges ignored)."""
    pts, face = trimesh.sample.sample_surface(m, n, seed=seed)
    nrm = m.face_normals[face]
    o = pts - nrm * 0.01
    loc, idx, tri = m.ray.intersects_location(o, -nrm, multiple_hits=False)
    t = np.full(n, np.nan)
    t[idx] = np.linalg.norm(loc - o[idx], axis=1)
    facing = np.zeros(n, bool)
    facing[idx] = (m.face_normals[tri] * nrm[idx]).sum(1) < -0.8
    thin = facing & (t < limit)
    spots = Counter(map(tuple, (pts[thin] // 5 * 5).astype(int)))
    return thin.mean(), np.nanmin(np.where(facing, t, np.nan)), [(k, v, np.nanmedian(t[thin & np.all((pts // 5 * 5).astype(int) == k, axis=1)])) for k, v in spots.most_common(6)]


def overhangs(m, deg, above=0.3, low=4.0):
    """Area of faces overhanging more than `deg` from vertical (not counting the bed)."""
    n, c, a = m.face_normals, m.triangles_center, m.area_faces
    down = (n[:, 2] < -np.sin(np.radians(deg))) & (c[:, 2] > above)
    return a[down].sum(), a[down & (c[:, 2] < low)].sum()


def main(stage="print"):
    for name in ["base", "lid"]:
        m = trimesh.load(P.BUILD / stage / f"mx_case_{name}.stl")
        share, tmin, spots = thin_walls(m)
        print(f"{name}: walls under 0.9 mm on {share * 100:.2f}% of the surface (min {tmin:.2f} mm)")
        for k, v, t in spots:
            print(f"   at {tuple(int(c) for c in k)}: {v} samples, {t:.2f} mm")
        for deg in (50, 60, 70):
            a, low = overhangs(m, deg)
            print(f"   overhang steeper than {deg} deg: {a:.0f} mm2 (within 4 mm of the bed {low:.0f})")


if __name__ == "__main__":
    main()

"""Voronoi lattice on the outer surface, cut through the wall as tapered ribs.

Seeds are spread over the outer surface, denser where the composition wants
material. Every wall voxel is projected onto the outer surface; its distance u
to the nearest Voronoi edge decides whether it is rib (u <= half-width) or hole.
The rib half-width depends on depth: 45 degree chamfer at the outer face, then
a wedge that narrows inward, then a small chamfer at the inner face. Where the
composition field s reaches 1 the half-width outgrows the cells and the wall is
solid, so solid areas dissolve into the lattice instead of ending at a seam.
"""
import numpy as np
import trimesh
from scipy.spatial import cKDTree

from . import form
from . import params as P

RIB_W = 3.6          # rib width at full width, just under the outer chamfer
RIB_CHAMFER = 0.8    # outer chamfer
RIB_INNER_CHAMFER = 0.5
RIB_TAPER = 0.8 / 5.2  # half-width lost per mm of depth (3.6 -> 2.0 over 6 mm)
CELL_OPEN = 11.0     # seed spacing where the lattice is most open
CELL_DENSE = 5.5     # seed spacing next to solid areas
MAX_DEPTH_OPEN = 8.0  # ribs reach in towards the mouse at most this far
SKIN_SOLID = 4.0      # solid areas are a skin this thick


def smooth_step(a, b, t):
    u = np.clip((t - a) / (b - a), 0.0, 1.0)
    return u * u * (3 - 2 * u)


def composition(p, contacts, magnets):
    """'Heel': solid at the back and the bottom, opening diagonally towards the
    nose and the top. Plus solid spots for the hinge, magnets, pads and a belt
    along the parting plane. Returns s in [0, 1], 1 = solid."""
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    u = 0.55 * (y + 56) / 112 + 0.45 * (1 - (z + 4.6) / 43.6)
    s = smooth_step(0.42, 0.86, u)
    belt = np.exp(-(form.plane_distance(y, z) / 3.5) ** 2)
    hinge = np.exp(-((np.hypot(y - P.HINGE_Y, z - form.part_z(P.HINGE_Y)) / 9) ** 2)) * (np.abs(x) < 26)
    s = np.maximum.reduce([s, belt, hinge])
    for c in magnets:
        s = np.maximum(s, np.exp(-(np.linalg.norm(p - c, axis=-1) / 7) ** 2))
    for _, q, n, r in contacts:
        s = np.maximum(s, np.exp(-(np.linalg.norm(p - q, axis=-1) / (r + 3)) ** 2))
    return np.clip(s, 0, 1)


def seeds(surface, contacts, magnets, seed=7):
    """Variable-density dart throwing on the outer surface."""
    pts, _ = trimesh.sample.sample_surface(surface, 150_000, seed=seed)
    rng = np.random.default_rng(seed)
    pts = pts[rng.permutation(len(pts))]
    s = composition(pts, contacts, magnets)
    radius = CELL_OPEN + (CELL_DENSE - CELL_OPEN) * s
    tree = cKDTree(pts)
    free = np.ones(len(pts), bool)
    keep = []
    for i in range(len(pts)):
        if free[i]:
            keep.append(i)
            free[tree.query_ball_point(pts[i], radius[i])] = False
    return pts[keep]


def edge_distance(proj, seed_pts, k=8):
    """Distance from points on the surface to the nearest Voronoi edge."""
    tree = cKDTree(seed_pts)
    _, idx = tree.query(proj, k=k, workers=-1)
    a = seed_pts[idx[:, 0]]
    da = np.sum((proj - a) ** 2, axis=1)
    u = np.full(len(proj), np.inf, np.float32)
    for j in range(1, k):
        b = seed_pts[idx[:, j]]
        ab = np.linalg.norm(b - a, axis=1)
        u = np.minimum(u, (np.sum((proj - b) ** 2, axis=1) - da) / (2 * ab))
    return u


def half_width(depth, inner, s):
    """Rib half-width at a given depth below the outer face and distance to the
    inner face. Grows without bound as s -> 1."""
    w = RIB_W / 2 + 12.0 * smooth_step(0.55, 1.0, s)
    outer = w - RIB_CHAMFER + depth
    wedge = w - np.maximum(depth - RIB_CHAMFER, 0) * RIB_TAPER
    return np.minimum.reduce([outer, wedge, wedge - RIB_INNER_CHAMFER + inner])

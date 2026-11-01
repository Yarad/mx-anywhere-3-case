"""Voronoi lattice on the outer surface, cut through the wall as tapered ribs.

Seeds are spread over the outer surface, denser where the composition wants
material and towards the hinge. Every wall voxel is projected onto the outer
surface; its distance u to the nearest Voronoi edge decides whether it is rib
(u <= half-width) or hole. The rib half-width depends on depth: 45 degree
chamfer at the outer face, then a wedge that narrows inward, then a small
chamfer at the inner face. Where the composition field s reaches 1 the
half-width outgrows the cells and the wall is solid, so solid areas dissolve
into the lattice instead of ending at a seam.

The mouse rests on lattice nodes: three seeds are placed around each contact
so a node (three ribs meeting) sits right over it, and the ribs fatten a little
around that node to give the bumper a landing.
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
RIB_MIN = 2.0         # the wedge never gets thinner than this
RIB_MIN_FACE = 1.0    # inner face left after the inner chamfer
CELL_OPEN = 11.0     # seed spacing of the lattice
CELL_HINGE = 5.0     # seed spacing right at the hinge
HINGE_REACH = 52.0   # distance from the hinge axis over which cells grow to CELL_OPEN
HINGE_CURVE = 0.8    # < 1: cells stay large longer and shrink only close to the hinge
MAX_DEPTH_OPEN = 8.0  # ribs reach in towards the mouse at most this far
SKIN_SOLID = 3.0      # solid areas are a skin this thick
NODE_FAT = 1.3        # extra rib half-width at a contact node


def smooth_step(a, b, t):
    u = np.clip((t - a) / (b - a), 0.0, 1.0)
    return u * u * (3 - 2 * u)


def hinge_distance(p):
    za = form.part_z(P.HINGE_Y) + P.KNUCKLE_R
    return np.hypot(p[..., 1] - P.HINGE_Y, p[..., 2] - za)


def composition(p, magnets):
    """'Heel': solid at the back and the bottom, opening diagonally towards the
    nose and the top. Plus solid spots for the hinge and magnets and a belt
    along the parting plane. Returns s in [0, 1], 1 = solid."""
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    # steep enough diagonal that the solid heel wraps over the back edge of the lid
    u = 0.62 * (y + 56) / 112 + 0.38 * (1 - (z + 4.6) / 43.6)
    s = smooth_step(0.42, 0.82, u)
    belt = np.exp(-(form.plane_distance(y, z) / 3.5) ** 2)
    hinge = np.exp(-((hinge_distance(p) / 9) ** 2)) * (np.abs(x) < 26)
    s = np.maximum.reduce([s, belt, hinge])
    for c in magnets:
        s = np.maximum(s, np.exp(-(np.linalg.norm(p - c, axis=-1) / 7) ** 2))
    return np.clip(s, 0, 1)


def cell_size(p, magnets):
    """Seed spacing: large everywhere, smaller only towards the hinge. Solid
    areas keep large cells; their holes close up instead (see half_width)."""
    t = np.clip((hinge_distance(p) - 8) / HINGE_REACH, 0, 1) ** HINGE_CURVE
    return CELL_HINGE + (CELL_OPEN - CELL_HINGE) * t


def contact_nodes(surface, contacts, magnets):
    """Point on the outer surface over each contact that lies in the lattice
    (contacts inside solid areas need no node), with the spacing there."""
    nodes = []
    for name, q, n, r in contacts:
        p, _, tri = trimesh.proximity.closest_point(surface, [q])
        p = p[0]
        if composition(p, magnets) > 0.5:
            continue
        nodes.append((name, p, surface.face_normals[tri[0]], r))
    return nodes


def seeds(surface, nodes, magnets, seed=7):
    """Variable-density dart throwing on the outer surface, after three seeds
    around every contact node."""
    fixed = []
    for _, p, n, _ in nodes:
        a = np.cross(n, [0, 0, 1.0] if abs(n[2]) < 0.9 else [1.0, 0, 0])
        a /= np.linalg.norm(a)
        b = np.cross(n, a)
        rho = 0.58 * cell_size(p[None], magnets)[0]
        for k in range(3):
            t = 2 * np.pi * k / 3 + np.pi / 2
            q = p + rho * (np.cos(t) * a + np.sin(t) * b)
            fixed.append(trimesh.proximity.closest_point(surface, [q])[0][0])
    fixed = np.array(fixed).reshape(-1, 3)

    pts, _ = trimesh.sample.sample_surface(surface, 150_000, seed=seed)
    rng = np.random.default_rng(seed)
    pts = np.vstack([fixed, pts[rng.permutation(len(pts))]])
    radius = cell_size(pts, magnets)
    tree = cKDTree(pts)
    free = np.ones(len(pts), bool)
    keep = []
    for i in range(len(pts)):
        if free[i] or i < len(fixed):
            keep.append(i)
            hit = tree.query_ball_point(pts[i], radius[i] if i >= len(fixed) else 0.8 * radius[i])
            free[hit] = False
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


def node_fat(proj, nodes):
    """Extra half-width around the contact nodes: a soft landing for the bumper."""
    out = np.zeros(len(proj), np.float32)
    for _, p, _, r in nodes:
        d = np.linalg.norm(proj - p, axis=1)
        out = np.maximum(out, NODE_FAT * min(r / 4.5, 1.0) * np.exp(-(d / (0.7 * r + 1.0)) ** 2))
    return out


def half_width(depth, inner, s, extra=0.0):
    """Rib half-width at a given depth below the outer face and distance to the
    inner face. Grows without bound as s -> 1."""
    w = RIB_W / 2 + extra + 12.0 * smooth_step(0.55, 1.0, s)
    outer = w - RIB_CHAMFER + depth
    wedge = np.maximum(w - np.maximum(depth - RIB_CHAMFER, 0) * RIB_TAPER, RIB_MIN / 2)  # deep ribs stop narrowing
    inner_face = np.maximum(wedge - RIB_INNER_CHAMFER, RIB_MIN_FACE / 2) + inner
    return np.minimum.reduce([outer, wedge, inner_face])

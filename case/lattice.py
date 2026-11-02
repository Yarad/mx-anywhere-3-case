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

RIB_W, RIB_CHAMFER, RIB_INNER_CHAMFER, RIB_MIN_FACE = P.RIB_W, P.RIB_CHAMFER, P.RIB_INNER_CHAMFER, P.RIB_MIN_FACE
MAX_DEPTH_OPEN, SKIN_SOLID, NODE_FAT = P.MAX_DEPTH_OPEN, P.SKIN_SOLID, P.NODE_FAT
# rib cross-sections: depth where the taper starts, half-width lost per mm deeper, narrowest rib
RIBS = {
    "wedge": (RIB_CHAMFER, 0.8 / 5.2, 2.0),      # narrows inward: 3.6 -> 2.0 over 6 mm
    "octagon": (RIB_CHAMFER, 0.0, RIB_W),        # full width all the way in
    "keel": (RIB_CHAMFER + 1.6, 1.0, 1.6),       # octagon outside, a 45 degree step, then a thin web
}
TAPER_FROM, RIB_TAPER, RIB_MIN = RIBS[P.RIB]
Y0, LENGTH = form.Y_FRONT - 0.5, form.Y_BACK - form.Y_FRONT  # composition runs nose -> back
Z0, HEIGHT = form.Z_BOTTOM, round(form.Z_TOP - form.Z_BOTTOM, 6)  # and bottom -> top


def smooth_step(a, b, t):
    u = np.clip((t - a) / (b - a), 0.0, 1.0)
    return u * u * (3 - 2 * u)


def hinge_distance(p):
    za = form.part_z(P.HINGE_Y) + P.KNUCKLE_R
    return np.hypot(p[..., 1] - P.HINGE_Y, p[..., 2] - za)


def composition(p, magnets, contacts=()):
    """Where the wall is solid: s in [0, 1], 1 = solid. The design's large-scale
    pattern (heel, tail, bottom, belt or none for bone), plus what every case
    needs solid: a belt along the parting plane, the hinge and the magnets."""
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    uy = (y - Y0) / LENGTH       # 0 at the nose, 1 at the back
    uz = (z - Z0) / HEIGHT       # 0 at the bottom, 1 at the top
    belt_w = 3.5
    if P.COMPOSITION == "heel":  # steep enough diagonal that the solid heel wraps over the back edge of the lid
        s = smooth_step(0.42, 0.82, 0.62 * (y - Y0) / LENGTH + 0.38 * (1 - (z - Z0) / HEIGHT))
    elif P.COMPOSITION == "tail":
        s = smooth_step(0.6, 0.95, uy)
    elif P.COMPOSITION == "bottom":
        s = smooth_step(0.55, 0.9, 1 - uz)
    else:  # bone, belt
        s = np.zeros_like(uy)
        belt_w = 8.0 if P.COMPOSITION == "belt" else belt_w
    belt = np.exp(-(form.plane_distance(y, z) / belt_w) ** 2)
    hinge = np.exp(-((hinge_distance(p) / 9) ** 2)) * (np.abs(x) < P.KNUCKLE_SPAN / 2 + 6)
    s = np.maximum.reduce([s, belt, hinge])
    for c in magnets:
        s = np.maximum(s, np.exp(-(np.linalg.norm(p - c, axis=-1) / 7) ** 2))
    if P.COMPOSITION == "bone":  # solid islands under the bumpers too
        for _, c, _, r in contacts:
            s = np.maximum(s, np.exp(-(np.linalg.norm(p - c, axis=-1) / (r + 4)) ** 2))
    return np.clip(s, 0, 1)


def button_distance(p):
    """Distance from points to the nearest button zone."""
    d = np.full(p.shape[:-1], np.inf)
    for b in P.BUTTONS:
        out = [np.maximum.reduce([lo - p[..., i], p[..., i] - hi, np.zeros(p.shape[:-1])])
               for i, (lo, hi) in enumerate((b["x"], b["y"], b["z"]))]
        d = np.minimum(d, np.sqrt(sum(o ** 2 for o in out)))
    return d


def cell_size(p, magnets):
    """Seed spacing: cell_open, shrinking to cell_fine towards the hinge or over
    the buttons. Solid areas keep large cells; their holes close up instead
    (see half_width)."""
    if P.FINE_NEAR == "hinge":
        t = np.clip((hinge_distance(p) - 8) / P.FINE_REACH, 0, 1) ** P.FINE_CURVE
    elif P.FINE_NEAR == "buttons" and P.BUTTONS:
        t = np.clip((button_distance(p) - 4) / (P.FINE_REACH / 2), 0, 1) ** P.FINE_CURVE
    else:
        t = np.ones(p.shape[:-1])
    return P.CELL_FINE + (P.CELL_OPEN - P.CELL_FINE) * t


def contact_nodes(surface, contacts, magnets):
    """Point on the outer surface over each contact that lies in the lattice
    (contacts inside solid areas need no node), with the spacing there."""
    nodes = []
    for name, q, n, r in contacts:
        p, _, tri = trimesh.proximity.closest_point(surface, [q])
        p = p[0]
        if composition(p, magnets, contacts) > 0.5:
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
    wedge = np.maximum(w - np.maximum(depth - TAPER_FROM, 0) * RIB_TAPER, RIB_MIN / 2)  # deep ribs stop narrowing
    inner_face = np.maximum(wedge - RIB_INNER_CHAMFER, RIB_MIN_FACE / 2) + inner
    return np.minimum.reduce([outer, wedge, inner_face])

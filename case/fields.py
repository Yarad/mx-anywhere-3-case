"""Signed distance fields on a regular grid. Negative = inside.

The case is built from these fields: the outer body, the mouse, the cavity the
mouse needs (gap per zone, swept along the ways the case opens), the parting
plane and the lip. Hinge, pin holes and magnet pockets are exact meshes added
later in build.py.
"""
import hashlib
import json

import numpy as np
import trimesh
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes

from . import form
from . import params as P


class Grid:
    def __init__(self, h=P.VOXEL, lo=P.GRID_MIN, hi=P.GRID_MAX):
        self.h = h
        self.lo = np.asarray(lo, float)
        self.n = np.ceil((np.asarray(hi) - self.lo) / h).astype(int) + 1
        self.axes = [self.lo[i] + h * np.arange(self.n[i]) for i in range(3)]

    @property
    def shape(self):
        return tuple(self.n)

    def mesh(self):
        return np.meshgrid(*[a.astype(np.float32) for a in self.axes], indexing="ij", copy=False)

    def chunks(self, size=40):
        """Yield (slice along x, X, Y, Z) blocks to keep memory down."""
        for i in range(0, self.n[0], size):
            sl = slice(i, min(i + size, self.n[0]))
            X, Y, Z = np.meshgrid(self.axes[0][sl], self.axes[1], self.axes[2], indexing="ij")
            yield sl, X, Y, Z

    def to_mesh(self, field, level=0.0):
        """Marching cubes of the region field < level, as a trimesh in world mm."""
        vol = np.pad(field - level, 1, constant_values=1.0)
        vol[np.abs(vol) < 1e-4] = 1e-4  # no grid point exactly on the surface: no degenerate triangles
        v, f, _, _ = marching_cubes(vol, level=0.0, spacing=(self.h,) * 3)
        v += self.lo - self.h
        m = trimesh.Trimesh(v, f, process=True)
        m.update_faces(m.nondegenerate_faces())
        m.remove_unreferenced_vertices()
        if m.volume < 0:
            m.invert()
        return m


def _cached(name, key, compute):
    P.CACHE.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:12]
    path = P.CACHE / f"{name}-{digest}.npy"
    if path.exists():
        return np.load(path)
    arr = compute()
    np.save(path, arr)
    return arr


def _signed_from_samples(grid, pts, normals, inside_fn, plane_near=0.0):
    """Distance to sampled surface points; sign from the nearest sample's normal
    close to the surface and from inside_fn farther away. Within plane_near of
    the surface the distance is taken to the nearest sample's tangent plane,
    which is smooth where the point distance would be bumpy."""
    tree = cKDTree(pts)
    out = np.empty(grid.shape, np.float32)
    for sl, X, Y, Z in grid.chunks():
        q = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
        d, idx = tree.query(q, k=1, distance_upper_bound=12.0, workers=-1)
        far = ~np.isfinite(d)
        idx[far] = 0
        d[far] = 12.0
        side = np.einsum("ij,ij->i", q - pts[idx], normals[idx])
        inside = np.where(d < 1.0, side < 0, inside_fn(sl).ravel())
        signed = np.where(inside, -d, d)
        signed = np.where(d < plane_near, side, signed)
        out[sl] = signed.reshape(X.shape)
    return out


def mouse_sdf(grid):
    def compute():
        m = trimesh.load(P.SCAN)
        pts, face = trimesh.sample.sample_surface(m, 1_500_000, seed=1)
        normals = m.face_normals[face]
        # occupancy for the far field: fill the voxel shell of the surface
        tree = cKDTree(pts)
        shell = np.zeros(grid.shape, bool)
        for sl, X, Y, Z in grid.chunks():
            d, _ = tree.query(np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1), k=1,
                              distance_upper_bound=grid.h, workers=-1)
            shell[sl] = np.isfinite(d).reshape(X.shape)
        filled = ndimage.binary_fill_holes(shell)
        return _signed_from_samples(grid, pts, normals, lambda sl: filled[sl])
    return _cached("mouse", [P.SCAN.stat().st_size, grid.h, list(grid.lo), list(grid.n)], compute)


def outer_sdf(grid):
    def compute():
        F = np.empty(grid.shape, np.float32)
        for sl, X, Y, Z in grid.chunks():
            F[sl] = form.implicit(X, Y, Z)
        v, f = form.surface_mesh()
        surf = trimesh.Trimesh(v, f, process=False)
        surf.fix_normals()
        normals = np.nan_to_num(np.asarray(surf.vertex_normals))
        return _signed_from_samples(grid, v, normals, lambda sl: F[sl] < 0, plane_near=1.5)
    key = [form.PLAN, form.PROFILE_LOWER, form.PROFILE_UPPER, form.SECTION, grid.h, list(grid.lo), list(grid.n)]
    return _cached("outer", key, compute)


# --- contact points ---------------------------------------------------------------

def contact_points():
    """Surface point and outward normal of every contact on the mouse."""
    m = trimesh.load(P.SCAN)
    out = []
    for name, kind, a, b, c, r in P.CONTACTS:
        if kind == "bottom":
            out.append((name, np.array([a, b, P.TABLE_Z]), np.array([0, 0, -1.0]), r))
            continue
        if kind == "top":
            o, d = [a, b, 60.0], [0, 0, -1.0]
        elif kind == "side":
            o, d = [70.0 * a, b, c], [-a, 0, 0]
        else:  # front
            o, d = [a, -80.0, c], [0, 1.0, 0]
        loc, _, tri = m.ray.intersects_location([o], [d], multiple_hits=False)
        # smoothed normal: plane through the scan's neighbourhood, facing the ray
        near = m.vertices[np.linalg.norm(m.vertices - loc[0], axis=1) < 3.0]
        n = trimesh.points.plane_fit(near)[1]
        n = n if np.dot(n, d) < 0 else -n
        out.append((name, loc[0], n / np.linalg.norm(n), r))
    return out


def _smooth_step(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def gap_field(grid, contacts):
    """Wanted gap between mouse and case, attached to the mouse's features."""
    g = np.empty(grid.shape, np.float32)
    for sl, X, Y, Z in grid.chunks():
        ramp = lambda s: _smooth_step(s / 1.5)  # 1.5 mm soft edge
        top = ramp(15 - Y) * ramp(Z - 10) * ramp(28.5 - np.abs(X))
        side = ramp(X - 26.5) * ramp(Y + 27) * ramp(-2 - Y) * ramp(Z - 13) * ramp(25 - Z)
        gg = P.GAP + np.maximum((P.GAP_BUTTONS - P.GAP) * top, (P.GAP_SIDE_BUTTONS - P.GAP) * side)
        for _, p, n, r in contacts:
            q = np.stack([X - p[0], Y - p[1], Z - p[2]], -1)
            along = q @ n
            radial = np.linalg.norm(q - along[..., None] * n, axis=-1)
            gg = np.where((radial < r + 0.3) & (along > -3) & (along < 8), P.GAP_PAD, gg)
        g[sl] = gg
    return g


def pad_bosses(grid, contacts):
    """Cylinders from each contact out through the wall (SDF, unclipped)."""
    out = np.full(grid.shape, 1e3, np.float32)
    for sl, X, Y, Z in grid.chunks():
        o = out[sl]
        for _, p, n, r in contacts:
            q = np.stack([X - p[0], Y - p[1], Z - p[2]], -1)
            along = q @ n
            radial = np.linalg.norm(q - along[..., None] * n, axis=-1)
            o = np.minimum(o, np.maximum(radial - r, -along))
        out[sl] = o
    return out


# --- sweeps -----------------------------------------------------------------------

def sweep_up(field):
    """Region swept when the mouse is lifted straight up out of the base."""
    return np.minimum.accumulate(field, axis=2)


def hinge_axis():
    z = form.part_z(P.HINGE_Y) + P.KNUCKLE_R
    return np.array([P.HINGE_Y, z])


def sweep_open(grid, field, max_deg, step):
    """Region the lid must avoid while it opens around the hinge axis."""
    a = (hinge_axis() - grid.lo[1:]) / grid.h
    out = field.copy()
    for deg in np.arange(step, max_deg + 1e-6, step):
        t = np.radians(deg)
        c, s = np.cos(t), np.sin(t)
        R = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
        off = np.concatenate([[0], a - R[1:, 1:] @ a])
        rot = ndimage.affine_transform(field, R, offset=off, order=1, mode="nearest")
        np.minimum(out, rot, out=out)
    return out


def plane_field(grid):
    out = np.empty(grid.shape, np.float32)
    for sl, X, Y, Z in grid.chunks():
        out[sl] = form.plane_distance(Y, Z)
    return out

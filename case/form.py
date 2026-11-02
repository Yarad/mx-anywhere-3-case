"""Outer form of the case: three Bezier curves combined into one smooth body.

plan    -- top-view outline, right half (x, y); plan_left, if given, the left half
           (x > 0 as well) for a form that follows an asymmetric mouse
profile -- side-view outline (y, z), split into a lower and an upper chain
section -- front-view cross-section, normalised: half-width u(v) for v in [0, 1]
           from the flat bottom (v = 0) to the top (v = 1)

A point is inside when zb(y) <= z <= zt(y) and |x| <= hw(y) * u(v), hw taken from
the half of the plan on the point's side. The curves live in mice/<mouse>/derived.toml.
"""
import numpy as np

from . import params as P

PLAN = P.FORM["plan"]
PLAN_LEFT = P.FORM.get("plan_left")
PROFILE_LOWER = P.FORM["profile_lower"]
PROFILE_UPPER = P.FORM["profile_upper"]
SECTION = P.FORM["section"]


def bezier(segments, n=400):
    """Sample a chain of cubic Bezier segments into an (m, 2) polyline."""
    t = np.linspace(0, 1, n)[:, None]
    out = []
    for i, (a, b, c, d) in enumerate(segments):
        a, b, c, d = map(np.asarray, (a, b, c, d))
        pts = (1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * c + t ** 3 * d
        out.append(pts if i == 0 else pts[1:])
    return np.vstack(out)


_plan = bezier(PLAN)
_plan_left = bezier(PLAN_LEFT) if PLAN_LEFT else _plan
_lower = bezier(PROFILE_LOWER)
_upper = bezier(PROFILE_UPPER)[::-1]
_section = bezier(SECTION)
Y_FRONT, Y_BACK = _plan[0, 1], _plan[-1, 1]
Z_BOTTOM, Z_TOP = round(float(_lower[:, 1].min()), 6), round(float(_upper[:, 1].max()), 6)


def half_width(y, left=False):
    pl = _plan_left if left else _plan
    return np.interp(y, pl[:, 1], pl[:, 0], left=0.0, right=0.0)


def z_bottom(y):
    return np.interp(y, _lower[:, 0], _lower[:, 1])


def z_top(y):
    return np.interp(y, _upper[:, 0], _upper[:, 1])


def section_u(v):
    return np.interp(v, _section[:, 1], _section[:, 0])


def implicit(x, y, z):
    """Continuous field, negative inside the outer body. Units are mm along x, so
    the zero set is exact but the values are not distances."""
    zb, zt = z_bottom(y), z_top(y)
    h = np.maximum(zt - zb, 1e-3)
    v = np.clip((z - zb) / h, 0.0, 1.0)
    hw = np.where(x < 0, half_width(y, True), half_width(y)) if PLAN_LEFT else half_width(y)
    f = np.maximum.reduce([np.abs(x) - hw * section_u(v), zb - z, z - zt])
    outside = (y < Y_FRONT) | (y > Y_BACK)
    return np.where(outside, np.maximum(f, 1.0), f)


def surface_mesh(n_y=520, n_side=240, n_bottom=48):
    """The outer surface sampled straight from the Bezier curves (no inversion of
    the section curve), as a closed tube collapsing to points at the tips."""
    k = np.linspace(0, np.pi, n_y)
    ys = (Y_FRONT + Y_BACK) / 2 - (Y_BACK - Y_FRONT) / 2 * np.cos(k)  # dense at the tips
    side = bezier(SECTION, n_side // 2)                      # (u, v) right side, bottom -> top
    bottom = np.c_[np.linspace(-0.8, 0.8, n_bottom), np.zeros(n_bottom)][1:-1]
    loop = np.vstack([bottom[n_bottom // 2 - 1:], side, side[::-1][1:-1] * [-1, 1], bottom[:n_bottom // 2 - 1]])
    hw, hl, zb, zt = half_width(ys), half_width(ys, True), z_bottom(ys), z_top(ys)
    X = np.where(loop[None, :, 0] < 0, hl[:, None], hw[:, None]) * loop[None, :, 0]
    Y = np.repeat(ys[:, None], len(loop), 1)
    Z = zb[:, None] + (zt - zb)[:, None] * loop[None, :, 1]
    verts = np.stack([X, Y, Z], -1).reshape(-1, 3)
    m = len(loop)
    i, j = np.meshgrid(np.arange(n_y - 1), np.arange(m), indexing="ij")
    a, b = i * m + j, i * m + (j + 1) % m
    c, d = a + m, b + m
    faces = np.concatenate([np.stack([a, c, b], -1).reshape(-1, 3), np.stack([b, c, d], -1).reshape(-1, 3)])
    return verts, faces


def part_z(y):
    return P.PART_Z0 + P.PART_SLOPE * y


def plane_distance(y, z):
    """Signed distance to the parting plane, positive on the lid side."""
    return (z - part_z(y)) / np.sqrt(1 + P.PART_SLOPE ** 2)


PLANE_NORMAL = np.array([0.0, -P.PART_SLOPE, 1.0]) / np.sqrt(1 + P.PART_SLOPE ** 2)

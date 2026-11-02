"""A stand-in mouse from its dimensions, for when there is no scan: a smooth body
with a flat bottom, built from the same kind of curves as the case.

The shape knobs are fractions (0 = front tip, 1 = back tip along the length; of
the full width or height across), with defaults measured on the MX Anywhere 3.
The body is only as good as the numbers, so cases from it use thicker bumpers.
"""
import numpy as np
import trimesh

from .curves import sample

SHAPE = {  # knob: (default, what it is)
    "hump": (0.63, "where the mouse is highest, along the length from the front"),
    "widest": (0.65, "where the mouse is widest, along the length from the front"),
    "nose_width": (0.78, "width a tenth of the length behind the front tip, of the full width"),
    "back_width": (0.72, "width a tenth of the length before the back tip, of the full width"),
    "nose_height": (0.25, "height of the front tip, of the full height"),
    "back_height": (0.58, "height of the back tip, of the full height"),
}
SECTION = [[[0.88, 0.0], [0.97, 0.03], [1.0, 0.18], [1.0, 0.42]],
           [[1.0, 0.42], [1.0, 0.78], [0.72, 1.0], [0.0, 1.0]]]


def curves(length, width, height, **knobs):
    k = {name: knobs.get(name, d) for name, (d, _) in SHAPE.items()}
    L, hw, H = length, width / 2, height
    yf, yb = -L / 2, L / 2
    y_nose, y_wide, y_back = yf + 0.1 * L, yf + k["widest"] * L, yb - 0.1 * L
    plan = [[[0, yf], [0.55 * k["nose_width"] * hw, yf], [k["nose_width"] * hw, y_nose - 0.06 * L], [k["nose_width"] * hw, y_nose]],
            [[k["nose_width"] * hw, y_nose], [k["nose_width"] * hw, y_nose + 0.2 * L], [hw, y_wide - 0.2 * L], [hw, y_wide]],
            [[hw, y_wide], [hw, y_wide + 0.12 * L], [k["back_width"] * hw, y_back - 0.08 * L], [k["back_width"] * hw, y_back]],
            [[k["back_width"] * hw, y_back], [k["back_width"] * hw, y_back + 0.07 * L], [0.6 * k["back_width"] * hw, yb], [0, yb]]]
    zf, zb_, y_top = k["nose_height"] * H, k["back_height"] * H, yf + k["hump"] * L
    upper = [[[yf, zf], [yf, zf + 0.25 * (H - zf)], [y_top - 0.35 * (y_top - yf), H], [y_top, H]],
             [[y_top, H], [y_top + 0.45 * (yb - y_top), H], [yb, zb_ + 0.5 * (H - zb_)], [yb, zb_]]]
    lower = [[[yf, zf], [yf, 0.3 * zf], [yf + 2, 0], [yf + 6, 0]],
             [[yf + 6, 0], [yf + 6 + (L - 12) / 3, 0], [yb - 6 - (L - 12) / 3, 0], [yb - 6, 0]],
             [[yb - 6, 0], [yb - 0.1 * L, 0], [yb, 0.12 * zb_], [yb, zb_]]]
    return plan, lower, upper


def body(length, width, height, n_y=400, n_side=160, **knobs):
    """Closed mesh of the stand-in, flat bottom on z = 0, front tip at y = -length / 2."""
    plan, lower, upper = curves(length, width, height, **knobs)
    p, lo, up = sample(plan, 200), sample(lower, 200), sample(upper, 200)
    lo, up = lo[np.argsort(lo[:, 0])], up[np.argsort(up[:, 0])]
    k = np.linspace(0, np.pi, n_y)[1:-1]
    ys = -length / 2 * np.cos(k)
    hw = np.interp(ys, p[:, 1], p[:, 0])
    zb, zt = np.interp(ys, lo[:, 0], lo[:, 1]), np.interp(ys, up[:, 0], up[:, 1])
    side = sample(SECTION, n_side // 2)
    u0 = SECTION[0][0][0]
    bottom = np.c_[np.linspace(-u0, u0, 24), np.zeros(24)][1:-1]
    loop = np.vstack([bottom[11:], side, side[::-1][1:-1] * [-1, 1], bottom[:11]])
    loop = loop[np.r_[True, np.any(np.diff(loop, axis=0) != 0, axis=1)]]  # segment joints appear twice
    X = hw[:, None] * loop[None, :, 0]
    Z = zb[:, None] + (zt - zb)[:, None] * loop[None, :, 1]
    Y = np.repeat(ys[:, None], len(loop), 1)
    verts = np.stack([X, Y, Z], -1).reshape(-1, 3)
    m, n = len(loop), len(ys)
    i, j = np.meshgrid(np.arange(n - 1), np.arange(m), indexing="ij")
    a, b = i * m + j, i * m + (j + 1) % m
    faces = [np.stack([a, a + m, b], -1).reshape(-1, 3), np.stack([b, a + m, b + m], -1).reshape(-1, 3)]
    tips = len(verts) + np.arange(2)  # close the tube at the tips
    zf, zbk = np.interp(ys[0], lo[:, 0], lo[:, 1]), np.interp(ys[-1], lo[:, 0], lo[:, 1])
    verts = np.vstack([verts, [[0, -length / 2, (zf + np.interp(ys[0], up[:, 0], up[:, 1])) / 2],
                               [0, length / 2, (zbk + np.interp(ys[-1], up[:, 0], up[:, 1])) / 2]]])
    ring = np.arange(m)
    faces.append(np.stack([np.full(m, tips[0]), (ring + 1) % m, ring], -1))
    last = (n - 1) * m
    faces.append(np.stack([np.full(m, tips[1]), last + ring, last + (ring + 1) % m], -1))
    mesh = trimesh.Trimesh(verts, np.vstack(faces), process=True)
    mesh.fix_normals()
    return mesh

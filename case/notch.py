"""Finger notch: a cut in the base under the lid's edge at the magnet end (+Y, opposite
the hinge), shaped like the lid notch on the front edge of a MacBook Pro.

Along the middle it is a straight 45 degree chamfer of the base's top outer edge; at
both ends the chamfer narrows along a short round curve to a point on the edge. The lid
stays as it is: its straight edge now overhangs the chamfer, and a fingertip finds it.

[design] notch_size = [width, ends, leg]:
  width  point to point along the edge
  ends   length of each narrowing end, a circular arc tangent to the straight part
  leg    the chamfer's leg: as deep down the outer face as it reaches in under the lid

The cutter is made on a fine local grid and taken off the base as an exact mesh, like
the magnet pockets.
"""
import numpy as np
import trimesh
from skimage.measure import marching_cubes

from . import form

ABOVE = 0.15     # the cutter ends this far above the parting plane: the lip is further in
H = 0.1          # grid step of the cutter, mm


def outer_y(x, z):
    """y of the outer surface at the back end at (x, z), by bisection of the form."""
    a = np.full(np.shape(x), form.Y_BACK - 12.0)  # inside
    b = np.full(np.shape(x), form.Y_BACK + 0.5)   # outside
    for _ in range(36):
        m = (a + b) / 2
        inside = form.implicit(x, m, z) < 0
        a, b = np.where(inside, m, a), np.where(inside, b, m)
    return (a + b) / 2


def leg_along(x, x0, width, ends, leg):
    """Chamfer leg along the edge: `leg` along the straight middle, then a circular arc
    tangent to it that reaches 0 at the points (and goes negative past them)."""
    s = np.abs(x - x0) - (width / 2 - ends)
    r = (ends ** 2 + leg ** 2) / (2 * leg)
    return np.where(s <= 0, leg, leg - (r - np.sqrt(np.clip(r ** 2 - s ** 2, 0, None))))


def field(X, Y, Z, x0, width, ends, leg):
    """Negative inside the cutter. t: depth in from the outer face along y."""
    t = outer_y(X[:, :1, :], Z[:, :1, :]) - Y
    below = form.part_z(Y) - Z
    chamfer = (t + below - leg_along(X, x0, width, ends, leg)) / np.sqrt(2)
    return np.maximum(chamfer, -below - ABOVE)  # nothing above the parting plane: the lip is there


def cutter(width, ends, leg, x0=0.0):
    """The notch as a closed trimesh, in the case frame."""
    tip = form.Y_BACK
    zp = form.part_z(tip)
    xs = np.arange(x0 - width / 2 - 2, x0 + width / 2 + 2 + H, H)
    ys = np.arange(tip - leg - 3, tip + 2, H)
    zs = np.arange(zp - leg - 3, zp + ABOVE + 1.5, H)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    vol = np.pad(field(X, Y, Z, x0, width, ends, leg), 1, constant_values=1.0)
    vol[np.abs(vol) < 1e-4] = 1e-4  # no grid point exactly on the surface: no degenerate triangles
    v, faces, _, _ = marching_cubes(vol, 0.0, spacing=(H, H, H))
    v += np.array([xs[0], ys[0], zs[0]]) - H
    m = trimesh.Trimesh(v, faces, process=True)
    if m.volume < 0:
        m.invert()
    return m

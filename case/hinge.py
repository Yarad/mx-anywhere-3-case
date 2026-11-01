"""Exact mechanical features as manifolds: hinge knuckles, pin holes, magnet pockets."""
import numpy as np
from manifold3d import CrossSection, Manifold, Mesh

from . import form
from . import params as P

SEG = 72


def to_manifold(tm):
    m = Manifold(Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                      tri_verts=np.asarray(tm.faces, np.uint32)))
    if m.is_empty():
        raise ValueError(f"mesh did not convert to a manifold: {m.status()}")
    return m


def to_trimesh(m):
    import trimesh
    mesh = m.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=False)


def frame(z_to, y_to, origin):
    """3x4 transform taking local z to z_to and local y to y_to."""
    z_to, y_to = np.asarray(z_to, float), np.asarray(y_to, float)
    x_to = np.cross(y_to, z_to)
    return np.column_stack([x_to, y_to, z_to, origin])


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def x_cylinder(x0, x1, y, z, r):
    return Manifold.cylinder(x1 - x0, r, circular_segments=SEG).transform(frame([1, 0, 0], [0, 1, 0], [x0, y, z]))


def knuckle_ranges():
    n, gap = P.KNUCKLE_N, P.KNUCKLE_GAP
    length = (P.KNUCKLE_SPAN - (n - 1) * gap) / n
    x0 = -P.KNUCKLE_SPAN / 2
    return [(x0 + i * (length + gap), x0 + i * (length + gap) + length) for i in range(n)]


def axis():
    return P.HINGE_Y, form.part_z(P.HINGE_Y) + P.KNUCKLE_R


def _knuckle(xa, xb, lid, grow=0.0):
    ya, za = axis()
    r = P.KNUCKLE_R + grow
    cyl = x_cylinder(xa - grow, xb + grow, ya, za, r)
    yb = ya + P.KNUCKLE_LEAF + grow
    if lid:  # web from the barrel back into the lid, its underside on the parting plane
        web = box(xa - grow, xb + grow, ya, yb, form.part_z(yb) - grow, za + r)
    else:    # web from the barrel down into the base's front wall
        web = box(xa - grow, xb + grow, ya, yb, form.part_z(ya) - 4.5, za + grow)
    return Manifold.batch_hull([cyl, web])


def above_plane(sign=1):
    """Half-space on the lid side (sign=1) or the base side (sign=-1) of the plane."""
    big = box(-100, 100, -100, 100, 0, 100) if sign > 0 else box(-100, 100, -100, 100, -100, 0)
    t = np.degrees(np.arctan(P.PART_SLOPE))
    return big.rotate([t, 0, 0]).translate([0, 0, P.PART_Z0])


def lid_knuckles():
    parts = [_knuckle(a, b, True) for i, (a, b) in enumerate(knuckle_ranges()) if i % 2]
    return Manifold.batch_boolean(parts, _add()) ^ above_plane(1)


def base_knuckles():
    return Manifold.batch_boolean([_knuckle(a, b, False) for i, (a, b) in enumerate(knuckle_ranges()) if not i % 2], _add())


def ear_clearance():
    """What the lid gives up around the base's knuckles."""
    g = P.KNUCKLE_CLEAR
    return Manifold.batch_boolean([_knuckle(a, b, False, g) for i, (a, b) in enumerate(knuckle_ranges()) if not i % 2], _add())


def lid_knuckle_sweep():
    """What the base gives up so the lid knuckles can turn up to OPEN_SWEEP_DEG."""
    ya, za = axis()
    out = []
    for i, (a, b) in enumerate(knuckle_ranges()):
        if not i % 2:
            continue
        k = _knuckle(a, b, True, P.KNUCKLE_CLEAR)
        steps = np.linspace(0, P.OPEN_SWEEP_DEG, 13)
        rot = [k.translate([0, -ya, -za]).rotate([s, 0, 0]).translate([0, ya, za]) for s in steps]
        out += [Manifold.batch_hull([rot[j], rot[j + 1]]) for j in range(len(rot) - 1)]
    return Manifold.batch_boolean(out, _add())


def teardrop_hole(d, up):
    """Horizontal hole along x with a 45 degree roof pointing `up` (printable without support)."""
    r = d / 2
    ya, za = axis()
    tip = CrossSection([[(-r * 0.7071, r * 0.7071), (0, r * 1.4142), (r * 0.7071, r * 0.7071)]])
    sec = (CrossSection.circle(r, SEG) + tip).hull()
    x0 = -P.KNUCKLE_SPAN / 2 - 2
    hole = Manifold.extrude(sec, P.KNUCKLE_SPAN + 4)
    up = np.asarray(up, float) / np.linalg.norm(up)
    return hole.transform(frame([1, 0, 0], up, [x0, ya, za]))


def magnet_pocket(center, into_lid):
    n = form.PLANE_NORMAL if into_lid else -form.PLANE_NORMAL
    cyl = Manifold.cylinder(P.MAG_DEPTH + 0.5, P.MAG_D / 2, circular_segments=SEG).translate([0, 0, -0.5])
    side = np.cross(n, [1, 0, 0])
    return cyl.transform(frame(n, side / np.linalg.norm(side), center))


def _add():
    from manifold3d import OpType
    return OpType.Add

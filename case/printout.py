"""Print-ready files: parts turned to their print orientation, simplified, checked.

base -- flat bottom on the bed, no supports
lid  -- parting plane (rim) on the bed; tree supports from the bed inside the dome
"""
import numpy as np
import trimesh

from . import hinge
from . import params as P

SIMPLIFY_TOL = 0.01  # mm: removes marching-cubes over-tessellation, invisible in print


def oriented(lid, base):
    tilt = np.degrees(np.arctan(P.PART_SLOPE))
    out = {}
    for name, m in [("base", base), ("lid", lid.rotate([-tilt, 0, 0]))]:
        m = m.simplify(SIMPLIFY_TOL)
        lo = np.asarray(m.bounding_box()[:3])
        out[name] = m.translate([0, 0, -lo[2]])
    return out


def thickness(mesh, n=20000, seed=3):
    """Wall thickness at random surface points: distance to the next surface inward."""
    pts, face = trimesh.sample.sample_surface(mesh, n, seed=seed)
    nrm = mesh.face_normals[face]
    origins = pts - nrm * 0.01
    loc, idx, _ = mesh.ray.intersects_location(origins, -nrm, multiple_hits=False)
    t = np.full(n, np.nan)
    t[idx] = np.linalg.norm(loc - origins[idx], axis=1)
    return t


def overhang_area(mesh, limit_deg=45, above=0.3):
    n, c, a = mesh.face_normals, mesh.triangles_center, mesh.area_faces
    down = (n[:, 2] < -np.cos(np.radians(limit_deg))) & (c[:, 2] > above)
    return a[down].sum(), a[down & (c[:, 2] < 4)].sum()


def export(lid, base, out, log):
    parts = oriented(lid, base)
    meshes = {k: hinge.to_trimesh(v) for k, v in parts.items()}
    for name, m in meshes.items():
        m.export(out / f"mx_case_{name}.stl")
        t = thickness(m)
        oh, oh_low = overhang_area(m)
        v = parts[name].volume() / 1000
        log(f"{name}: {len(m.faces)} triangles, watertight {m.is_watertight}, size {np.round(m.extents, 1)} mm, "
            f"{v:.1f} cm3 ~ {v * P.DENSITY:.0f} g {P.MATERIAL}")
        log(f"  wall: min {np.nanmin(t):.2f}, 1% {np.nanpercentile(t, 1):.2f}, median {np.nanmedian(t):.2f} mm; "
            f"under 1.0 mm: {np.mean(t < 1.0) * 100:.2f}% of surface")
        log(f"  overhang >45 deg: {oh:.0f} mm2 (of it within 4 mm of the bed: {oh_low:.0f} mm2)")
    # one plate with both parts, side by side, for the slicer
    plate = trimesh.Scene()
    w = [meshes["base"].extents[0], meshes["lid"].extents[0]]
    gap = 12.0
    xs = [-(w[1] + gap) / 2, (w[0] + gap) / 2]
    for (name, m), x in zip(meshes.items(), xs):
        m = m.copy()
        c = m.bounds.mean(0)
        m.apply_translation([x - c[0], -c[1], 0])
        plate.add_geometry(m, node_name=f"mx_case_{name}", geom_name=f"mx_case_{name}")
    plate.export(out / "mx_case_plate.3mf")
    log(f"plate: {np.round(plate.extents[:2], 1)} mm")

"""Stage 1: closed shell without the lattice.

Run:  .venv/bin/python -m case.build
Writes build/stage1/{lid,base}.stl and assembly GLBs for viewing.
"""
import time

import numpy as np
import trimesh
from scipy import ndimage

from . import fields as F
from . import form, hinge, lattice
from .preview import preview
from . import params as P

OUT = P.BUILD / "stage1"


def log(msg, t0=[time.time()]):
    print(f"[{time.time() - t0[0]:6.1f}s] {msg}", flush=True)


def sample(grid, field, pts):
    idx = ((np.asarray(pts) - grid.lo) / grid.h).T
    return ndimage.map_coordinates(field, idx, order=1, mode="nearest")


def find_magnets(grid, O, Cb, Cl):
    """Spot on the back half of the rim with the most material around it, on the right; mirrored."""
    xs, ys = np.meshgrid(np.arange(4, 36, 0.25), np.arange(15, 56, 0.25), indexing="ij")
    pts = np.stack([xs.ravel(), ys.ravel(), form.part_z(ys.ravel())], 1)
    room = np.minimum.reduce([-sample(grid, O, pts), sample(grid, Cb, pts), sample(grid, Cl, pts)])
    best = int(np.argmax(room))
    c = pts[best]
    return [c * [-1, 1, 1], c], float(room[best])


def lattice_walls(grid, O, Cb, Cl, Pl, pads, contacts, magnets):
    """Walls of base and lid with the Voronoi lattice cut through them."""
    s_out = grid.to_mesh(O)
    seed_pts = lattice.seeds(s_out, contacts, magnets)
    log(f"lattice: {len(seed_pts)} cells")
    gx, gy, gz = np.gradient(O, grid.h)
    walls = []
    for C in (Cb, Cl):
        keep =np.minimum(np.abs(Pl) - P.RIM_BAND, pads)
        wall = np.maximum(O, -C)
        mask = (wall < 0.6) & (O > -lattice.MAX_DEPTH_OPEN - 1)
        idx = np.nonzero(mask)
        x = np.stack([grid.axes[i][idx[i]] for i in range(3)], 1)
        g = np.stack([gx[idx], gy[idx], gz[idx]], 1)
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
        o = O[idx]
        proj = x - o[:, None] * g
        s = lattice.composition(proj, contacts, magnets)
        depth = -o
        cap = lattice.MAX_DEPTH_OPEN + (lattice.SKIN_SOLID - lattice.MAX_DEPTH_OPEN) * s
        inner = np.minimum(C[idx], cap - depth)
        rib = lattice.edge_distance(proj, seed_pts) - lattice.half_width(depth, inner, s)
        cut = np.full(grid.shape, 1e3, np.float32)
        cut[idx] = np.maximum(rib, -inner)  # rib, and nothing deeper than the cap
        cut = np.minimum(cut, keep)  # rim belt and pads stay full thickness
        walls.append(np.maximum(wall, cut))
    return walls


def build(stage="stage1"):
    global OUT
    OUT = P.BUILD / stage
    with_lattice = stage != "stage1"
    OUT.mkdir(parents=True, exist_ok=True)
    grid = F.Grid()
    log(f"grid {grid.shape} = {np.prod(grid.shape) / 1e6:.1f} M voxels")
    sm = F.mouse_sdf(grid); log("mouse sdf")
    O = F.outer_sdf(grid); log("outer sdf")
    contacts = F.contact_points()
    for name, p, n, r in contacts:
        log(f"  contact {name:8s} at ({p[0]:6.1f} {p[1]:6.1f} {p[2]:6.1f}) normal ({n[0]:5.2f} {n[1]:5.2f} {n[2]:5.2f})")
    Cg = sm - F.gap_field(grid, contacts); log("gap field")
    Cb = F.sweep_up(Cg); log("base cavity (lifted out)")
    Cl = F.sweep_open(grid, Cg, P.LID_SWEEP_DEG, P.LID_SWEEP_STEP); log("lid cavity (opening sweep)")
    Pl = F.plane_field(grid)
    pads = F.pad_bosses(grid, contacts)
    Y = grid.axes[1][None, :, None].astype(np.float32)

    magnets, room = find_magnets(grid, O, Cb, Cl)
    log(f"magnets at x=±{magnets[1][0]:.1f} y={magnets[1][1]:.1f} z={magnets[1][2]:.1f}; "
        f"room {room:.2f} mm (need {P.MAG_D / 2 + P.MAG_SKIN:.2f})")

    lip = np.maximum.reduce([-Pl, Pl - P.LIP_H, -Cb, Cb - P.LIP_T, P.LIP_FRONT_Y - Y + 0 * Pl,
                             (Pl + Cb - (P.LIP_H + P.LIP_T - P.LIP_CHAMFER)) / np.sqrt(2), O])
    for c in magnets:  # no lip where the magnets sit
        X3, Y3, Z3 = grid.mesh()
        lip = np.maximum(lip, P.LIP_MAGNET_KEEPOUT - np.sqrt((X3 - c[0]) ** 2 + (Y3 - c[1]) ** 2))
        del X3, Y3, Z3

    if with_lattice:
        base_w, lid_w = lattice_walls(grid, O, Cb, Cl, Pl, pads, contacts, magnets)
    else:
        keep = np.minimum.reduce([-O - P.MAX_WALL, np.abs(Pl) - P.RIM_BAND, pads])
        base_w = np.maximum.reduce([O, -Cb, keep])
        lid_w = np.maximum.reduce([O, -Cl, keep])
    base_f = np.minimum(np.maximum(base_w, Pl), lip)
    lid_f = np.maximum.reduce([lid_w, -Pl, -(lip - P.LIP_CLEAR)])
    log("part fields")

    base = hinge.to_manifold(grid.to_mesh(base_f))
    lid = hinge.to_manifold(grid.to_mesh(lid_f))
    cav_b = hinge.to_manifold(grid.to_mesh(Cb))
    cav_l = hinge.to_manifold(grid.to_mesh(Cl))
    log("surfaces")

    n = form.PLANE_NORMAL
    lid = (lid + hinge.lid_knuckles()) - hinge.ear_clearance() - cav_l
    lid = lid - hinge.teardrop_hole(P.PIN_HOLE_LID, n)
    base = (base + hinge.base_knuckles()) - hinge.lid_knuckle_sweep() - cav_b
    base = base - hinge.teardrop_hole(P.PIN_HOLE_BASE, [0, 0, 1])
    for c in magnets:
        lid = lid - hinge.magnet_pocket(c, True)
        base = base - hinge.magnet_pocket(c, False)
    log("hinge, pin holes, magnet pockets")

    lid_t, base_t = hinge.to_trimesh(lid), hinge.to_trimesh(base)
    lid_t.export(OUT / "lid.stl")
    base_t.export(OUT / "base.stl")
    mouse = grid.to_mesh(sm)  # clean, consistently wound copy of the scan

    report(lid, base, hinge.to_manifold(mouse), magnets)
    export_views(lid_t, base_t, mouse)
    preview(stage)  # light GLBs for the viewer
    np.savez_compressed(OUT / "info.npz", magnets=np.array(magnets))
    log("done")


def report(lid, base, ms, magnets):
    for name, part in [("lid", lid), ("base", base)]:
        v = part.volume() / 1000
        log(f"{name}: {v:.1f} cm3 = {v * P.PETG_DENSITY:.0f} g PETG solid; genus {part.genus()}; "
            f"touches mouse {(part ^ ms).volume():.2f} mm3")
    log(f"lid/base overlap {(lid ^ base).volume():.3f} mm3")
    ya, za = hinge.axis()
    worst = []
    for deg in [5, 15, 30, 45, 60, 90, 120]:
        opened = lid.translate([0, -ya, -za]).rotate([deg, 0, 0]).translate([0, ya, za])
        worst.append(f"{deg}°: mouse {(opened ^ ms).volume():.2f}, base {(opened ^ base).volume():.2f}")
    log("opening, overlap mm3 -> " + "; ".join(worst))


def export_views(lid_t, base_t, mouse):
    ya, za = hinge.axis()

    def scene(open_deg):
        s = trimesh.Scene()
        colors = {"base": [0.36, 0.42, 0.45, 1.0], "lid": [0.85, 0.84, 0.80, 1.0], "mouse": [0.12, 0.12, 0.12, 1.0]}
        lid_m = lid_t.copy()
        if open_deg:
            T = trimesh.transformations.rotation_matrix(np.radians(open_deg), [1, 0, 0], [0, ya, za])
            lid_m.apply_transform(T)
        for name, m in [("base", base_t), ("lid", lid_m), ("mouse", mouse)]:
            m = m.copy()
            mat = trimesh.visual.material.PBRMaterial(name=name, baseColorFactor=colors[name],
                                                      metallicFactor=0.0, roughnessFactor=0.7)
            m.visual = trimesh.visual.TextureVisuals(material=mat)
            s.add_geometry(m, node_name=name, geom_name=name)
        return s

    scene(0).export(OUT / "assembly_closed.glb")
    scene(105).export(OUT / "assembly_open.glb")


if __name__ == "__main__":
    import sys
    build(*sys.argv[1:])

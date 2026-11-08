"""Build the case of the current mouse (see params.py):

  stage1  closed shell without the lattice
  stage2  with the lattice, preview grid
  print   print grid, parts turned to their print orientation

Run:  .venv/bin/python -m case <mouse> build [stage]
Writes build/<mouse>/<stage>/{lid,base}.stl, light preview GLBs and, for print, the print files.
"""
import json
import time

import numpy as np
import trimesh
from scipy import ndimage

from . import fields as F
from . import form, hinge, lattice, notch, printout
from .preview import preview
from . import params as P

OUT = P.BUILD / "stage1"
OPTION = False  # building a quick, coarse variant for an option sheet


def log(msg, t0=[time.time()]):
    print(f"[{time.time() - t0[0]:6.1f}s] {msg}", flush=True)


def sample(grid, field, pts):
    idx = ((np.asarray(pts) - grid.lo) / grid.h).T
    return ndimage.map_coordinates(field, idx, order=1, mode="nearest")


def find_magnets(grid, O, Cb, Cl):
    """Spot on the back of the rim with the most material around it, on the right;
    mirrored, or searched on the left too when the form is asymmetric."""
    def best(sign):
        xs, ys = np.meshgrid(sign * np.arange(*P.MAGNET_X, 0.25), np.arange(*P.MAGNET_Y, 0.25), indexing="ij")
        pts = np.stack([xs.ravel(), ys.ravel(), form.part_z(ys.ravel())], 1)
        room = np.minimum.reduce([-sample(grid, O, pts), sample(grid, Cb, pts), sample(grid, Cl, pts)])
        i = int(np.argmax(room))
        fits = room >= P.MAG_D / 2 + P.MAG_SKIN + 0.15
        if P.MAGNET_PICK == "back" and fits.any():  # the furthest back spot that holds a magnet
            i = int(np.argmax(np.where(fits, pts[:, 1], -np.inf)))
        return pts[i], float(room[i])

    c, room = best(1)
    if not form.PLAN_LEFT:
        return [c * [-1, 1, 1], c], room
    left, room_left = best(-1)
    return [left, c], min(room, room_left)


def notch_report(grid, Cb, magnets, x0):
    """How much room the finger notch leaves: in towards the lid's groove (or the cavity
    without a lip) along the parting plane, and sideways to the magnet pockets."""
    width, ends, leg = P.NOTCH_SIZE
    y_out = float(notch.outer_y(np.array(x0), np.array(form.part_z(form.Y_BACK) - 0.5)))
    ts = np.arange(0, 10, 0.05)
    ys = y_out - ts
    pts = np.stack([np.full_like(ts, x0), ys, form.part_z(ys) + 0.05], 1)
    groove = P.LIP_T + P.LIP_CLEAR if P.LIP == "inner" else 0.0  # the lid's groove wall, or the cavity
    inward = ts[np.argmax(sample(grid, Cb, pts) <= groove)] - leg - notch.ABOVE
    sideways = min(abs(c[0] - x0) for c in magnets) - P.MAG_D / 2 - P.MAG_SKIN - width / 2
    msg = (f"finger notch {width:g} mm wide, {leg:g} mm chamfer: room in to the "
           f"{'lid groove' if groove else 'cavity'} {inward:.2f} mm, to the magnets {sideways:.1f} mm")
    if inward < 0.3 or sideways < 1.0:
        msg += "  <-- too tight: make [design] notch_size smaller"
    return msg


def seed_points(s_out, nodes, magnets):
    """The approved lattice layout if it was made for the same cells, else a new one."""
    made_for = {"cell_open": P.CELL_OPEN, "cell_fine": P.CELL_FINE, "fine_near": P.FINE_NEAR,
                "contacts": P.CONTACT_STYLE, "form": json.dumps(P.FORM, sort_keys=True)}
    info = P.SEEDS_FILE.with_suffix(".json")
    if P.SEEDS_FILE.exists() and (not info.exists() or json.loads(info.read_text()) == made_for):
        return np.load(P.SEEDS_FILE)  # same cells at any resolution
    pts = lattice.seeds(s_out, nodes, magnets)
    if not OPTION:  # trying a choice leaves the approved layout alone
        np.save(P.SEEDS_FILE, pts)
        info.write_text(json.dumps(made_for, indent=1))
    return pts


def lattice_walls(grid, O, Cb, Cl, Pl, pads, contacts, magnets):
    """Walls of base and lid with the Voronoi lattice cut through them."""
    s_out = grid.to_mesh(O)
    nodes = lattice.contact_nodes(s_out, contacts, magnets) if P.CONTACT_STYLE == "nodes" else []
    seed_pts = seed_points(s_out, nodes, magnets)
    log(f"lattice: {len(seed_pts)} cells, contact nodes: {', '.join(n[0] for n in nodes) or 'none'}")
    gx, gy, gz = np.gradient(O, grid.h)
    walls = []
    keep = np.abs(Pl) - P.RIM_BAND  # rim belt stays full thickness
    if P.CONTACT_STYLE == "pads":  # and so do round pads under the bumpers
        keep = np.minimum(keep, pads)
    for C in (Cb, Cl):
        wall = np.maximum(O, -C)
        mask = (wall < 0.6) & (O > -lattice.MAX_DEPTH_OPEN - 1)
        idx = np.nonzero(mask)
        x = np.stack([grid.axes[i][idx[i]] for i in range(3)], 1)
        g = np.stack([gx[idx], gy[idx], gz[idx]], 1)
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
        o = O[idx]
        proj = x - o[:, None] * g
        s = lattice.composition(proj, magnets, contacts)
        depth = -o
        cap = lattice.MAX_DEPTH_OPEN + (lattice.SKIN_SOLID - lattice.MAX_DEPTH_OPEN) * s
        inner = np.minimum(C[idx], cap - depth)
        hw = lattice.half_width(depth, inner, s, lattice.node_fat(proj, nodes))
        rib = lattice.edge_distance(proj, seed_pts) - hw
        cut = np.full(grid.shape, 1e3, np.float32)
        cut[idx] = np.maximum(rib, -inner)  # rib, and nothing deeper than the cap
        cut = np.minimum(cut, keep)
        walls.append(np.maximum(wall, cut))
    return walls


def build(stage="stage1"):
    global OUT, OPTION
    OUT = P.BUILD / stage
    OPTION = stage.startswith("options/")
    with_lattice = stage != "stage1" and P.LATTICE == "voronoi"
    OUT.mkdir(parents=True, exist_ok=True)
    grid = F.Grid(h=P.VOXEL_PRINT if stage == "print" else 0.5 if OPTION else P.VOXEL)
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
    if P.LIP == "none":
        lip = np.full(grid.shape, 1e3, np.float32)

    if with_lattice:
        base_w, lid_w = lattice_walls(grid, O, Cb, Cl, Pl, pads, contacts, magnets)
    else:  # stage 1 preview, or a plain shell when the design has no lattice
        wall = P.MAX_WALL if stage == "stage1" else P.SKIN_SOLID
        keep = np.minimum.reduce([-O - wall, np.abs(Pl) - P.RIM_BAND, pads])
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
    if P.NOTCH == "chamfer":
        x0 = float(np.mean([c[0] for c in magnets]))
        base = base - hinge.to_manifold(notch.cutter(*P.NOTCH_SIZE, x0=x0))
        log(notch_report(grid, Cb, magnets, x0))
    # marching cubes leaves sub-voxel crumbs in the lattice: keep the one real body of each part
    lid, base = (max(m.decompose(), key=lambda c: c.volume()) for m in (lid, base))
    log("hinge, pin holes, magnet pockets")

    lid_t, base_t = hinge.to_trimesh(lid), hinge.to_trimesh(base)
    lid_t.export(OUT / "lid.stl")
    base_t.export(OUT / "base.stl")
    mouse = grid.to_mesh(sm)  # clean, consistently wound copy of the scan

    if OPTION:
        log("done")
        return
    report(lid, base, hinge.to_manifold(mouse), magnets)
    if stage == "print":
        printout.export(lid, base, OUT, log)
    else:
        export_views(lid_t, base_t, mouse)
    preview(stage)  # light GLBs for the viewer
    np.savez_compressed(OUT / "info.npz", magnets=np.array(magnets))
    log("done")


def report(lid, base, ms, magnets):
    for name, part in [("lid", lid), ("base", base)]:
        v = part.volume() / 1000
        log(f"{name}: {v:.1f} cm3 = {v * P.DENSITY:.0f} g {P.MATERIAL} solid; genus {part.genus()}; "
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

    from .preview import Z_UP_TO_Y_UP
    for name, deg in [("closed", 0), ("open", 105)]:
        sc = scene(deg)
        sc.apply_transform(Z_UP_TO_Y_UP)  # glTF is Y-up
        sc.export(OUT / f"assembly_{name}.glb")


if __name__ == "__main__":
    import sys
    build(*sys.argv[1:])

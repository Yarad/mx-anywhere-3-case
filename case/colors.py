"""Colour schemes for the case, rendered side by side for choosing.

Two kinds of scheme:
- one colour per part: only an instruction for the print shop, no change to the model;
- solid areas and lattice in different colours within one part: needs a
  multi-colour printer (AMS) and splits each part into two bodies.

Run:  .venv/bin/python -m case.colors
"""
import subprocess

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from . import hinge, lattice  # noqa: E402
from . import params as P  # noqa: E402
from .preview import Z_UP_TO_Y_UP  # noqa: E402

OUT = P.BUILD / "colors"
MOUSE = "#2B2B2C"  # graphite MX Anywhere 3
# PETG colours 3D Pixel has in stock: (hex, metallic)
PETG = {
    "белый": ("#F2F1EC", 0.0), "белый прозрачный": ("#D9E2E6", 0.0), "серый": ("#8C8E90", 0.0),
    "серый металлик": ("#75787C", 0.55), "чёрный": ("#1E1E1F", 0.0), "красный": ("#D8262B", 0.0),
    "оранжевый": ("#F07A1A", 0.0), "жёлтый": ("#F3D21E", 0.0), "синий": ("#1F4FD1", 0.0),
    "фиолетовый": ("#7A55D6", 0.0), "бордово-фиолетовый": ("#8E1B3A", 0.0), "бронза": ("#A2873A", 0.5),
}
SCHEMES = [  # (title, base, lid, solid areas or None)
    ("A · крышка белая, основание серый металлик", "серый металлик", "белый", None),
    ("B · крышка бронза, основание чёрное", "чёрный", "бронза", None),
    ("C · крышка оранжевая, основание чёрное", "чёрный", "оранжевый", None),
    ("D · крышка белая прозрачная, основание серое", "серый", "белый прозрачный", None),
    ("E · всё серый металлик", "серый металлик", "серый металлик", None),
    ("F · крышка бордово-фиолетовая, основание чёрное", "чёрный", "бордово-фиолетовый", None),
]


def rgba(hex_color):
    h = hex_color.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0]


def material(color):
    hex_color, metal = PETG.get(color, (color, 0.0))
    return trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
        baseColorFactor=rgba(hex_color), metallicFactor=metal, roughnessFactor=0.45 if metal else 0.65))


def split_solid(mesh, magnets, threshold=0.7):
    """Faces of the solid areas (heel, belt, hinge, magnets) and of the lattice."""
    s = lattice.composition(mesh.triangles_center, magnets)
    solid = s > threshold
    return mesh.submesh([np.nonzero(solid)[0]], append=True), mesh.submesh([np.nonzero(~solid)[0]], append=True)


def render_all(stage="print"):
    OUT.mkdir(parents=True, exist_ok=True)
    d = P.BUILD / stage
    magnets = list(np.load(d / "info.npz")["magnets"])
    parts = {k: hinge.to_trimesh(hinge.to_manifold(trimesh.load(d / f"{k}.stl")).simplify(0.03)) for k in ("base", "lid")}
    mouse = trimesh.load(P.SCAN)
    mouse.fix_normals()
    pngs = []
    for i, (title, base_c, lid_c, solid_c) in enumerate(SCHEMES):
        s = trimesh.Scene()
        for name, m in parts.items():
            color = base_c if name == "base" else lid_c
            if solid_c:
                solid, rest = split_solid(m, magnets)
                for tag, sub, c in [("solid", solid, solid_c), ("lattice", rest, color)]:
                    sub = sub.copy()
                    sub.visual = material(c)
                    s.add_geometry(sub, node_name=f"{name}_{tag}")
            else:
                m = m.copy()
                m.visual = material(color)
                s.add_geometry(m, node_name=name)
        mm = mouse.copy()
        mm.visual = material(MOUSE)
        s.add_geometry(mm, node_name="mouse")
        s.apply_transform(Z_UP_TO_Y_UP)
        glb = OUT / f"scheme_{i}.glb"
        s.export(glb)
        for cam in ("iso", "150:12"):
            png = OUT / f"scheme_{i}_{cam.replace(':', '_')}.png"
            subprocess.run(["cadgen", "+0.8.4", "snapshot", str(glb), str(png), f"--camera={cam}"],
                           check=True, capture_output=True)
        pngs.append((title, OUT / f"scheme_{i}_iso.png", OUT / f"scheme_{i}_150_12.png"))
    fig, axs = plt.subplots(len(pngs), 2, figsize=(12, 4.6 * len(pngs)))
    for row, (title, a, b) in zip(axs, pngs):
        for ax, p in zip(row, (a, b)):
            ax.imshow(mpimg.imread(p)[120:1100, 150:1450])
            ax.axis("off")
        row[0].set_title(title, fontsize=15, loc="left")
    plt.tight_layout()
    plt.savefig(OUT / "schemes.png", dpi=55)
    print(OUT / "schemes.png")


if __name__ == "__main__":
    render_all()


def scheme_views(base_color, lid_color, lid_alpha=1.0, tag="custom", stage="print", open_deg=105):
    """Closed and open GLBs of one scheme, plus a sheet of views. A lid_alpha
    below 1 hints at translucent filament (the viewer blends, snapshots may not)."""
    OUT.mkdir(parents=True, exist_ok=True)
    d = P.BUILD / stage
    parts = {k: hinge.to_trimesh(hinge.to_manifold(trimesh.load(d / f"{k}.stl")).simplify(0.03)) for k in ("base", "lid")}
    mouse = trimesh.load(P.SCAN)
    mouse.fix_normals()
    ya, za = hinge.axis()
    out = {}
    for state, deg in [("closed", 0), ("open", open_deg)]:
        s = trimesh.Scene()
        for name, m, color, alpha in [("base", parts["base"], base_color, 1.0), ("lid", parts["lid"], lid_color, lid_alpha),
                                      ("mouse", mouse, MOUSE, 1.0)]:
            m = m.copy()
            if name == "lid" and deg:
                m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(deg), [1, 0, 0], [0, ya, za]))
            hex_color, metal = PETG.get(color, (color, 0.0))
            mat = trimesh.visual.material.PBRMaterial(
                baseColorFactor=rgba(hex_color)[:3] + [alpha], metallicFactor=metal, roughnessFactor=0.5,
                alphaMode="BLEND" if alpha < 1 else "OPAQUE", doubleSided=alpha < 1)
            m.visual = trimesh.visual.TextureVisuals(material=mat)
            s.add_geometry(m, node_name=name)
        s.apply_transform(Z_UP_TO_Y_UP)
        out[state] = OUT / f"{tag}_{state}.glb"
        s.export(out[state])
    shots = [("closed", "iso", "спереди"), ("closed", "150:12", "сзади"), ("closed", "top", "сверху"),
             ("closed", "90:5", "сбоку"), ("open", "iso", "открыт"), ("open", "300:45", "открыт, сверху")]
    fig, axs = plt.subplots(2, 3, figsize=(18, 10))
    for ax, (state, cam, title) in zip(axs.ravel(), shots):
        png = OUT / f"{tag}_{state}_{cam.replace(':', '_')}.png"
        subprocess.run(["cadgen", "+0.8.4", "snapshot", str(out[state]), str(png), f"--camera={cam}"],
                       check=True, capture_output=True)
        ax.imshow(mpimg.imread(png)[60:1140, 100:1500])
        ax.set_title(title, fontsize=15)
        ax.axis("off")
    plt.tight_layout()
    sheet = OUT / f"{tag}_views.png"
    plt.savefig(sheet, dpi=55)
    return out, sheet

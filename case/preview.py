"""Light preview GLBs of a build stage for the viewer: simplified meshes, closed and open.

Run:  .venv/bin/python -m case.preview [stage]
"""
import sys

import numpy as np
import trimesh

from . import hinge
from . import params as P

COLORS = {"base": [0.36, 0.42, 0.45, 1.0], "lid": [0.85, 0.84, 0.80, 1.0], "mouse": [0.12, 0.12, 0.12, 1.0]}


def light(path, tol=0.03):
    m = hinge.to_manifold(trimesh.load(path))
    return hinge.to_trimesh(m.simplify(tol))


def preview(stage="stage2", open_deg=105):
    d = P.BUILD / stage
    parts = {"base": light(d / "base.stl"), "lid": light(d / "lid.stl")}
    mouse = trimesh.load(P.SCAN)
    mouse.fix_normals()
    parts["mouse"] = mouse
    ya, za = hinge.axis()
    for name, deg in [("closed", 0), ("open", open_deg)]:
        s = trimesh.Scene()
        for part, m in parts.items():
            m = m.copy()
            if part == "lid" and deg:
                m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(deg), [1, 0, 0], [0, ya, za]))
            mat = trimesh.visual.material.PBRMaterial(name=part, baseColorFactor=COLORS[part],
                                                      metallicFactor=0.0, roughnessFactor=0.7)
            m.visual = trimesh.visual.TextureVisuals(material=mat)
            s.add_geometry(m, node_name=part, geom_name=part)
        out = d / f"preview_{name}.glb"
        s.export(out)
        print(out, f"{out.stat().st_size / 1e6:.1f} MB", {k: len(v.faces) for k, v in parts.items()})


if __name__ == "__main__":
    preview(*sys.argv[1:])

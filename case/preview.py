"""Light preview GLBs of a build stage for the viewer: simplified meshes, closed and open.
Also the closed and open case as plain STLs for GitHub's 3D viewer, in docs/3d.

Run:  .venv/bin/python -m case.preview [stage]
      .venv/bin/python -m case.preview github
"""
import sys

import numpy as np
import trimesh

from . import hinge
from . import params as P

Z_UP_TO_Y_UP = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
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
        s.apply_transform(Z_UP_TO_Y_UP)  # glTF is Y-up: lay the case flat in viewers
        s.export(out)
        print(out, f"{out.stat().st_size / 1e6:.1f} MB", {k: len(v.faces) for k, v in parts.items()})


def github(stage="print", open_deg=105, limit=9.5e6):
    """One STL per state with both parts, coarsened just enough to stay under
    GitHub's 10 MB display limit. No mouse: the scan is not ours to publish."""
    d = P.BUILD / stage
    out = P.ROOT / "docs" / "3d"
    out.mkdir(parents=True, exist_ok=True)
    ms = [hinge.to_manifold(trimesh.load(d / f"{k}.stl")) for k in ("base", "lid")]
    for tol in (0.04, 0.05, 0.06, 0.08, 0.1):
        base, lid = (hinge.to_trimesh(m.simplify(tol)) for m in ms)
        if 84 + 50 * (len(base.faces) + len(lid.faces)) < limit:  # binary STL size
            break
    ya, za = hinge.axis()
    for name, deg in [("closed", 0), ("open", open_deg)]:
        m = lid.copy()
        if deg:
            m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(deg), [1, 0, 0], [0, ya, za]))
        f = out / f"case_{name}.stl"
        trimesh.util.concatenate([base, m]).export(f)
        print(f, f"{f.stat().st_size / 1e6:.1f} MB", f"tolerance {tol} mm")


if __name__ == "__main__":
    github() if sys.argv[1:] == ["github"] else preview(*sys.argv[1:])

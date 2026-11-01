"""Cross-section sheet of a build stage: lid, base and mouse cut by several planes.

Run:  .venv/bin/python -m case.review [stage]
"""
import sys

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import params as P  # noqa: E402

COLORS = {"base": "#5F5E5A", "lid": "#B4B2A9", "mouse": "#2C2C2A"}


def cut(mesh, origin, normal, axes):
    s = mesh.section(plane_origin=origin, plane_normal=normal)
    if s is None:
        return []
    return [np.asarray(e)[:, axes] for e in s.discrete]


def sheet(stage="stage1"):
    d = P.BUILD / stage
    parts = {"base": trimesh.load(d / "base.stl"), "lid": trimesh.load(d / "lid.stl"),
             "mouse": trimesh.load(P.SCAN)}
    planes = [("x = 0", [0, 0, 0], [1, 0, 0], [1, 2]), ("x = 17", [17, 0, 0], [1, 0, 0], [1, 2]),
              ("y = -30", [0, -30, 0], [0, 1, 0], [0, 2]), ("y = 0", [0, 0, 0], [0, 1, 0], [0, 2]),
              ("y = 30", [0, 30, 0], [0, 1, 0], [0, 2]), ("x = 8 (hinge)", [8, 0, 0], [1, 0, 0], [1, 2])]
    fig, axs = plt.subplots(3, 2, figsize=(14, 15))
    for ax, (title, o, n, ix) in zip(axs.ravel(), planes):
        for name, m in parts.items():
            for e in cut(m, o, n, ix):
                if name == "mouse":
                    ax.plot(e[:, 0], e[:, 1], color=COLORS[name], lw=0.8)
                else:
                    ax.fill(e[:, 0], e[:, 1], color=COLORS[name], alpha=0.85, lw=0)
        ax.set_aspect("equal")
        ax.grid(alpha=0.25)
        ax.set_title(title)
    if "hinge" in planes[-1][0]:
        axs.ravel()[-1].set_xlim(-62, -40)
        axs.ravel()[-1].set_ylim(-5, 20)
    plt.tight_layout()
    out = d / "sections.png"
    plt.savefig(out, dpi=70)
    print(out)


if __name__ == "__main__":
    sheet(*(sys.argv[1:] or []))

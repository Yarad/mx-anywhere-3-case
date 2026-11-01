"""Where to glue the bumpers: a shaded look into the base from above and into the
lid from below (as you hold it opened), with every contact numbered.

Run:  .venv/bin/python -m case.bumper_map [stage]
"""
import sys

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import fields as F  # noqa: E402
from . import form  # noqa: E402
from . import params as P  # noqa: E402

LABELS = {
    "nose": "носик перед колесом", "strip": "полоса за SmartShift", "back_l": "сзади сбоку",
    "back_r": "сзади сбоку", "back_c": "сзади по центру", "foot_fl": "под передней ножкой",
    "foot_fr": "под передней ножкой", "foot_bl": "под задней ножкой",
    "foot_br": "под задней ножкой", "side_l": "бок", "side_r": "бок",
    "front_l": "перёд, рядом с USB-C", "front_r": "перёд, рядом с USB-C",
}


def shaded(mesh, from_below, step=0.25):
    lo, hi = mesh.bounds
    xs = np.arange(lo[0] - 2, hi[0] + 2, step)
    ys = np.arange(lo[1] - 2, hi[1] + 2, step)
    X, Y = np.meshgrid(xs, ys)
    z0, d = (lo[2] - 5, 1.0) if from_below else (hi[2] + 5, -1.0)
    o = np.c_[X.ravel(), Y.ravel(), np.full(X.size, z0)]
    loc, idx, tri = mesh.ray.intersects_location(o, np.tile([0, 0, d], (len(o), 1)), multiple_hits=False)
    img = np.ones(X.size)
    light = np.array([-0.4, 0.5, -d * 0.8])
    light /= np.linalg.norm(light)
    img[idx] = 0.35 + 0.6 * np.clip(mesh.face_normals[tri] @ light, 0, 1)
    return img.reshape(X.shape), [xs[0], xs[-1], ys[0], ys[-1]]


def draw(stage="print"):
    d = P.BUILD / stage
    contacts = F.contact_points()
    fig, axs = plt.subplots(1, 2, figsize=(14, 12.5))
    for ax, part, below, title in [(axs[0], "base", False, "Основание — вид сверху внутрь"),
                                   (axs[1], "lid", True, "Крышка, откинутая вперёд — вид сверху внутрь")]:
        m = trimesh.load(P.BUILD / "stage2" / f"{part}.stl") if not (d / f"{part}.stl").exists() \
            else trimesh.load(d / f"{part}.stl")
        img, ext = shaded(m, below)
        if below:  # the lid opened 180 degrees around the hinge: y flips, x stays
            img, ext = img[::-1], [ext[0], ext[1], -ext[3], -ext[2]]
        ax.imshow(img, origin="lower", extent=ext, cmap="gray", vmin=0, vmax=1)
        k = 0
        for i, (name, p, n, r) in enumerate(contacts, 1):
            on_lid = p[2] > form.part_z(p[1])
            if on_lid != (part == "lid"):
                continue
            x, y = p[0], (-p[1] if below else p[1])
            dia = 4.5 if name == "nose" else 6.0
            ax.add_patch(plt.Circle((x, y), dia / 2, fill=False, color="#D85A30", lw=2.5))
            ax.annotate(str(i), (x, y), xytext=(x + 6, y + 3), color="#D85A30", fontsize=15,
                        fontweight="bold", arrowprops=dict(arrowstyle="-", color="#D85A30", lw=1))
            ax.text(0.02, -0.04 - 0.035 * k, f"{i} — {LABELS[name]}" + (" (Ø 4–5 мм)" if name == "nose" else ""),
                    transform=ax.transAxes, fontsize=12, color="#712B13", va="top")
            k += 1
        hinge_y = 1.0 if below else 0.0
        ax.text(0.5, hinge_y + (0.01 if below else -0.015), "петля", transform=ax.transAxes, ha="center",
                va="bottom" if below else "top", fontsize=12, color="#5F5E5A")
        ax.text(1.0, 0.5, "сторона\nбоковых\nкнопок", transform=ax.transAxes, ha="left", va="center",
                fontsize=11, color="#5F5E5A")
        ax.set_title(title, fontsize=14, pad=22)
        ax.set_aspect("equal")
        ax.axis("off")
    plt.suptitle("Карта демпферов: силиконовые самоклеящиеся Ø 6 × 2 мм, 13 шт", fontsize=16)
    plt.subplots_adjust(left=0.03, right=0.92, top=0.9, bottom=0.25, wspace=0.25)
    out = d / "bumper_map.png"
    plt.savefig(out, dpi=80)
    print(out)


if __name__ == "__main__":
    draw(*sys.argv[1:])

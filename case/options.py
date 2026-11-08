"""Pictures of the choices for one design parameter, on the current mouse.

  python -m case <mouse> options <parameter> [value ...]

Lattice, composition, cells, contacts and colours are built for real at a coarse
grid (half a minute or so per choice) and drawn closed, from the front left and
from the back right; rib, lip, hinge, form and parting are drawn as diagrams; the
finger notch is cut from a coarse build and drawn close up.
Writes build/<mouse>/options/<parameter>.png, choices lettered A, B, C...
"""
import json
import os
import string
import subprocess
import sys

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import params as P  # noqa: E402
from . import render as R  # noqa: E402

CHOICES = {  # parameter -> [(value, caption)]
    "lattice": [("voronoi", "Voronoi lattice"), ("none", "no lattice: plain shell")],
    "composition": [("heel", "heel: solid back and bottom"), ("bone", "bone: solid only where it works"),
                    ("tail", "tail: solid back"), ("bottom", "bottom: solid bottom"),
                    ("belt", "belt: wide band along the parting line")],
    "fine_near": [("hinge", "cells shrink towards the hinge"), ("buttons", "cells shrink over the buttons"),
                  ("none", "same cells everywhere")],
    "cells": [({"cell_open": 11.0, "cell_fine": 5.0}, "11 -> 5 mm"), ({"cell_open": 8.0, "cell_fine": 5.0}, "8 -> 5 mm"),
              ({"cell_open": 14.0, "cell_fine": 6.0}, "14 -> 6 mm")],
    "contacts": [("nodes", "the mouse rests on lattice nodes"), ("pads", "round pads under the bumpers")],
    "colors": [({"lid": "white-transparent", "base": "gray"}, "lid white transparent, base gray"),
               ({"lid": "white", "base": "gray-metallic"}, "lid white, base gray metallic"),
               ({"lid": "bronze", "base": "black"}, "lid bronze, base black"),
               ({"lid": "orange", "base": "black"}, "lid orange, base black"),
               ({"lid": "gray-metallic", "base": "gray-metallic"}, "all gray metallic"),
               ({"lid": "burgundy", "base": "black"}, "lid burgundy, base black")],
    "rib": [("wedge", "wedge: narrows towards the mouse"), ("octagon", "octagon: full width all the way"),
            ("keel", "keel: a thin web under an octagon")],
    "lip": [("inner", "lip on the base inside the lid"), ("none", "no lip: the hinge and magnets align")],
    "hinge": [("front", "hinge at the front, magnets at the back"), ("back", "hinge at the back, magnets at the front")],
    "form": [("symmetric", "symmetric form"), ("follow", "each side follows the mouse")],
    "parting": [("tilted", "tilted through the widest points"), ("horizontal", "horizontal")],
    "notch": [("chamfer", "finger notch, like a MacBook Pro's"),
              ("none", "no notch: lid and base meet flush")],
}
BUILT = {"lattice", "composition", "fine_near", "cells", "contacts"}


def design_change(param, value):
    if param == "cells":
        return value
    return {param: value}


def build_variant(param, value, i):
    stage = f"options/{param}-{i}"
    env = {**os.environ, "MOUSE_CASE": P.MOUSE, "CASE_DESIGN": json.dumps(design_change(param, value))}
    subprocess.run([sys.executable, "-m", "case.build", stage], env=env, check=True, capture_output=True)
    return P.BUILD / stage


def closed_views(d, colors=None, views=("iso", "iso back", "side")):
    colors = colors or P.PRINT_COLORS
    from .colors import PETG
    parts = [(trimesh.load(d / f"{k}.stl"), R.rgb(PETG.get(colors[k], (colors[k],))[0])) for k in ("base", "lid")]
    return [R.shade(parts, v, px=0.35) for v in views]


def built_sheet(param, values, out):
    rows = []
    for i, (value, caption) in enumerate(values):
        print(f"  {string.ascii_uppercase[i]}: {caption}", flush=True)
        views = ("iso", "top", "side") if param in ("cells", "fine_near") else ("iso", "iso back", "side")
        rows.append((caption, closed_views(build_variant(param, value, i), views=views)))
    return grid_sheet(rows, out, f"{P.NAME}: {param}")


def colour_sheet(values, out):
    d = P.BUILD / "stage2" if (P.BUILD / "stage2" / "lid.stl").exists() else build_variant("colors", P.LATTICE, 0)
    return grid_sheet([(caption, closed_views(d, value)) for value, caption in values], out, f"{P.NAME}: colours")


def notch_sheet(values, out):
    """The back of the case with and without the finger notch, close up and cut through
    the middle. The case is built once without it; the notch is cut from that base."""
    from . import form, hinge, notch
    d = build_variant("notch", "none", 0)
    lid, plain = trimesh.load(d / "lid.stl"), trimesh.load(d / "base.stl")
    mouse = trimesh.load(P.SCAN)
    width, ends, leg = P.NOTCH_SIZE
    zp = float(form.part_z(form.Y_BACK))

    def near_back(m):
        m = m.slice_plane([0, form.Y_BACK - 16, 0], [0, 1, 0], cap=True)
        m = m.slice_plane([0, 0, zp - 12], [0, 0, 1], cap=True)
        return m.slice_plane([0, 0, zp + 12], [0, 0, -1], cap=True)

    from .colors import PETG
    colors = [R.rgb(PETG[P.PRINT_COLORS[k]][0]) for k in ("base", "lid")]
    R.VIEWS["back below"] = ([-0.55, -0.78, 0.30], [0, 0, 1])
    fig, axs = plt.subplots(len(values), 3, figsize=(20, 5.4 * len(values)), squeeze=False,
                            gridspec_kw={"width_ratios": [1.3, 1.2, 0.62]})
    for r, (value, caption) in enumerate(values):
        base = plain
        if value == "chamfer":
            cut = hinge.to_manifold(plain) - hinge.to_manifold(notch.cutter(width, ends, leg))
            base = hinge.to_trimesh(max(cut.decompose(), key=lambda m: m.volume()))
        parts = [(near_back(base), colors[0]), (near_back(lid), [0.93, 0.92, 0.88])]
        for c, (view, light) in enumerate([("back", (-0.25, 0.85, 0.45)), ("back below", (-0.3, 0.8, 0.5))]):
            img, ext = R.shade(parts, view, px=0.08, light=light)
            ax = axs[r, c]
            ax.imshow(img, origin="lower", extent=ext)
            ax.axis("off")
            if view == "back":
                ax.set_xlim(-width / 2 - 14, width / 2 + 14)
                ax.set_ylim(zp - 7, zp + 5)
        ax = axs[r, 2]
        for m, col in [(base, "#5F5E5A"), (lid, "#C9A227"), (mouse, R.INK)]:
            for e in m.section(plane_origin=[0, 0, 0], plane_normal=[1, 0, 0]).discrete:
                ax.plot(e[:, 1], e[:, 2], color=col, lw=1.5)
        ax.set_xlim(form.Y_BACK - 11, form.Y_BACK + 2)
        ax.set_ylim(zp - 9, zp + 7)
        ax.set_aspect("equal")
        ax.grid(alpha=0.25)
        ax.set_title("cut through the middle: base grey, lid yellow", fontsize=11, loc="left")
        axs[r, 0].set_title(f"{string.ascii_uppercase[r]} · {caption}", loc="left", fontsize=15)
    fig.suptitle(f"{P.NAME}: finger notch at the magnet end, {width:g} mm wide, {leg:g} mm chamfer, "
                 f"ends {ends:g} mm", fontsize=16)
    plt.tight_layout()
    plt.savefig(out, dpi=60)
    plt.close(fig)
    return out


def grid_sheet(rows, out, title):
    fig, axs = plt.subplots(len(rows), 3, figsize=(15, 4.6 * len(rows)), squeeze=False)
    for r, (caption, views) in enumerate(rows):
        for c, (img, ext) in enumerate(views):
            ax = axs[r, c]
            ax.imshow(img, origin="lower", extent=ext)
            ax.axis("off")
        axs[r, 0].set_title(f"{string.ascii_uppercase[r]} · {caption}", loc="left", fontsize=15)
    fig.suptitle(title, fontsize=16)
    plt.tight_layout()
    plt.savefig(out, dpi=60)
    plt.close(fig)
    return out


# --- diagrams ---------------------------------------------------------------------------------

def rib_sheet(values, out):
    """Half-width of a rib against depth, mirrored: what a cut across one rib looks like."""
    import importlib
    from . import lattice
    depth = np.linspace(0, 6, 300)
    widths = {}
    for value in ["octagon"] + [v for v, _ in values]:
        os.environ["CASE_DESIGN"] = json.dumps({"rib": value})
        importlib.reload(P)
        importlib.reload(lattice)
        widths[value] = lattice.half_width(depth, 6 - depth, np.zeros_like(depth))
    os.environ.pop("CASE_DESIGN", None)
    importlib.reload(P)
    full = np.trapezoid(2 * widths["octagon"], depth)
    fig, axs = plt.subplots(1, len(values), figsize=(5 * len(values), 5))
    for ax, (i, (value, caption)) in zip(axs, enumerate(values)):
        hw = widths[value]
        area = np.trapezoid(2 * hw, depth)
        ax.fill_betweenx(-depth, -hw, hw, color=R.CASE_C)
        ax.axhline(0, color=R.INK, lw=0.8)
        ax.text(0, 0.3, "outer surface", ha="center", fontsize=10)
        ax.text(0, -6.4, "towards the mouse", ha="center", va="top", fontsize=10)
        ax.set_title(f"{string.ascii_uppercase[i]} · {caption}\nweight {area / full * 100:.0f}% of a full octagon",
                     loc="left", fontsize=12)
        ax.set_xlim(-4, 4)
        ax.set_ylim(-7.5, 1)
        ax.set_aspect("equal")
        ax.axis("off")
    fig.suptitle("Rib cross-section, 6 mm deep (same outside look for all)", fontsize=14)
    plt.tight_layout()
    plt.savefig(out, dpi=70)
    plt.close(fig)
    return out


def lip_sheet(values, out):
    fig, axs = plt.subplots(1, 2, figsize=(10, 5))
    for ax, (i, (value, caption)) in zip(axs, enumerate(values)):
        base = [(0, 0), (4, 0), (4, 6), (0, 6)]
        lid = [(0, 6), (4, 6), (4, 12), (0, 12)]
        if value == "inner":
            base += [(2.6, 6), (4, 6), (4, 8.5), (2.6, 8.5)]
            lid = [(0, 6), (2.4, 6), (2.4, 8.7), (4, 8.7), (4, 12), (0, 12)]
            ax.add_patch(plt.Polygon([(2.6, 6), (4, 6), (4, 8.5), (2.6, 8.5)], color="#5F5E5A"))
        ax.add_patch(plt.Polygon([(0, 0), (4, 0), (4, 6), (0, 6)], color="#5F5E5A"))
        ax.add_patch(plt.Polygon(lid, color="#B4B2A9"))
        ax.text(-0.3, 3, "base", ha="right", va="center")
        ax.text(-0.3, 10, "lid", ha="right", va="center")
        ax.text(2, -0.6, "outside      mouse", ha="center", va="top", fontsize=9)
        ax.set_title(f"{string.ascii_uppercase[i]} · {caption}", loc="left", fontsize=12)
        ax.set_xlim(-2, 6)
        ax.set_ylim(-2, 13)
        ax.set_aspect("equal")
        ax.axis("off")
    fig.suptitle("Wall cut across the parting line", fontsize=14)
    plt.tight_layout()
    plt.savefig(out, dpi=70)
    plt.close(fig)
    return out


def side_sheet(param, values, out):
    """Hinge end and parting plane, drawn on the mouse from the side."""
    m = trimesh.load(P.SCAN)
    lo, hi = m.bounds
    fig, axs = plt.subplots(1, len(values), figsize=(7 * len(values), 4.6))
    for ax, (i, (value, caption)) in zip(axs, enumerate(values)):
        R.silhouette(ax, m, [1, 2])
        if param == "hinge":
            y = lo[1] - 5 if value == P.HINGE_END else hi[1] + 5
            other = hi[1] + 3 if value == P.HINGE_END else lo[1] - 3
            ax.add_patch(plt.Circle((y, 8), 3.5, color="#185FA5"))
            ax.text(y, 13, "hinge", ha="center")
            ax.add_patch(plt.Rectangle((other - 1.5, 14), 3, 6, color="#D85A30"))
            ax.text(other, 22, "magnets", ha="center")
        else:
            ys = np.array([lo[1] - 6, hi[1] + 6])
            z = P.PART_Z0 + P.PART_SLOPE * ys if value == "tilted" else np.full(2, P.PART_Z0)
            ax.plot(ys, z, color="#D85A30", lw=2)
            ax.text(ys[1], z[1] + 1, "lid above / base below", ha="right", va="bottom", fontsize=9)
        ax.set_title(f"{string.ascii_uppercase[i]} · {caption}", loc="left", fontsize=12)
        ax.set_aspect("equal")
        ax.axis("off")
    fig.suptitle(f"{P.NAME}, from the side, front on the left", fontsize=14)
    plt.tight_layout()
    plt.savefig(out, dpi=70)
    plt.close(fig)
    return out


def form_sheet(values, out):
    """The form as fitted now against the other style (fitted on the fly)."""
    m = trimesh.load(P.SCAN)
    curves = {}
    for value, caption in values:
        if value == P.FORM_STYLE:
            curves[caption] = P.FORM
            continue
        res = subprocess.run([sys.executable, "-m", "case.fit", "--json"], capture_output=True, text=True, check=True,
                             env={**os.environ, "MOUSE_CASE": P.MOUSE, "CASE_DESIGN": json.dumps({"form": value})})
        curves[caption] = json.loads(res.stdout.strip().splitlines()[-1])
    colors = ["#185FA5", "#D85A30"]
    return R.form_sheet({f"{string.ascii_uppercase[i]} · {k}": (c, colors[i]) for i, (k, c) in enumerate(curves.items())},
                        m, out, title=f"{P.NAME}: outer form")


def main(param, *only):
    if param not in CHOICES:
        sys.exit(f"parameters: {', '.join(CHOICES)}")
    values = [v for v in CHOICES[param] if not only or str(v[0]) in only]
    out = P.BUILD / "options"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{param}.png"
    if param in BUILT:
        built_sheet(param, values, path)
    elif param == "colors":
        colour_sheet(values, path)
    elif param == "rib":
        rib_sheet(values, path)
    elif param == "lip":
        lip_sheet(values, path)
    elif param == "notch":
        notch_sheet(values, path)
    elif param in ("hinge", "parting"):
        side_sheet(param, values, path)
    else:
        form_sheet(values, path)
    print(path)


if __name__ == "__main__":
    main(*sys.argv[1:])

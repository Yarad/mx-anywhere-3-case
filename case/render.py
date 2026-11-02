"""Pictures without any viewer: the outer form's curves over the mouse, and shaded
orthographic views of meshes by ray casting (for intake and option sheets).
"""
import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

VIEWS = {  # direction the camera looks along, and the screen's up
    "top": ([0, 0, -1], [0, 1, 0]),
    "bottom": ([0, 0, 1], [0, 1, 0]),
    "side": ([-1, 0, 0], [0, 0, 1]),     # from +X: the side buttons of a right-handed mouse
    "other side": ([1, 0, 0], [0, 0, 1]),
    "front": ([0, 1, 0], [0, 0, 1]),
    "back": ([0, -1, 0], [0, 0, 1]),
    "iso": ([-0.55, 0.62, -0.56], [0, 0, 1]),   # from the front left, above
    "iso back": ([0.55, -0.62, -0.56], [0, 0, 1]),
}
INK, MOUSE_C, CASE_C, ZONE_C, CONTACT_C = "#2C2C2A", "#4A4A48", "#8C8E90", "#E24B4A", "#1D9E75"


def shade(parts, view="iso", px=0.25, light=(-0.35, 0.45, 0.82)):
    """parts: [(mesh, rgb)]. Returns an RGB image and the extent of the screen in mm."""
    d, up = (np.asarray(v, float) for v in VIEWS[view])
    d /= np.linalg.norm(d)
    right = np.cross(d, up)
    right /= np.linalg.norm(right)
    up = np.cross(right, d)
    mesh = trimesh.util.concatenate([m for m, _ in parts])
    owner = np.concatenate([np.full(len(m.faces), i) for i, (m, _) in enumerate(parts)])
    v = mesh.vertices
    u_, w_ = v @ right, v @ up
    us = np.arange(u_.min() - 3, u_.max() + 3, px)
    ws = np.arange(w_.min() - 3, w_.max() + 3, px)
    U, W = np.meshgrid(us, ws)
    back = (v @ d).min() - 10
    o = U.ravel()[:, None] * right + W.ravel()[:, None] * up + back * d
    loc, idx, tri = mesh.ray.intersects_location(o, np.tile(d, (len(o), 1)), multiple_hits=False)
    img = np.ones((U.size, 3))
    lv = np.asarray(light, float)
    lv = lv[0] * right + lv[1] * up - lv[2] * d
    lv /= np.linalg.norm(lv)
    n = mesh.face_normals[tri]
    n = np.where(((n @ -d) < 0)[:, None], -n, n)  # inner faces seen through holes
    s = 0.35 + 0.65 * np.clip(n @ lv, 0, 1)
    colors = np.array([c for _, c in parts], float)[owner[tri]]
    img[idx] = colors * s[:, None]
    return img.reshape(U.shape + (3,)), [us[0], us[-1], ws[0], ws[-1]]


def rgb(hex_color):
    h = hex_color.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def sheet(panels, out, cols=3, size=4.2, title=None):
    """panels: [(title, image, extent)] -> one PNG."""
    rows = (len(panels) + cols - 1) // cols
    fig, axs = plt.subplots(rows, cols, figsize=(cols * size, rows * size), squeeze=False)
    for ax in axs.ravel():
        ax.axis("off")
    for ax, (t, img, ext) in zip(axs.ravel(), panels):
        ax.imshow(img, origin="lower", extent=ext)
        ax.set_title(t, fontsize=12)
    if title:
        fig.suptitle(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(out, dpi=70)
    plt.close(fig)
    return out


def plate_picture(scene, out):
    """The parts on the bed in their colours, for an order without cadgen."""
    parts = []
    for name, geom in scene.geometry.items():
        m = geom.copy()
        m.apply_transform(scene.graph.get(name)[0] if name in scene.graph.nodes else np.eye(4))
        c = m.visual.material.baseColorFactor[:3] / 255 if hasattr(m.visual, "material") else [0.6] * 3
        parts.append((m, np.asarray(c, float)))
    for m, _ in parts:  # scenes come Y-up for glTF; back to Z-up
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    img, ext = shade(parts, "iso")
    sheet([("", img, ext)], out, cols=1, size=7)


# --- the outer form's curves ---------------------------------------------------------------

def silhouette(ax, mouse, axes, color=MOUSE_C):
    """Filled outline of the mouse projected on two axes."""
    from scipy import ndimage
    p = mouse.sample(60000)[:, axes] if len(mouse.faces) else mouse.vertices[:, axes]
    lo, h = p.min(0) - 2, 0.4
    n = np.ceil((p.max(0) + 2 - lo) / h).astype(int)
    occ = np.zeros(n, bool)
    ij = ((p - lo) / h).astype(int)
    occ[ij[:, 0], ij[:, 1]] = True
    occ = ndimage.binary_fill_holes(ndimage.binary_closing(occ, iterations=2))
    xs, ys = lo[0] + h * np.arange(n[0]), lo[1] + h * np.arange(n[1])
    ax.contourf(xs, ys, occ.T.astype(float), levels=[0.5, 1.5], colors=[color], alpha=0.25)
    ax.contour(xs, ys, occ.T.astype(float), levels=[0.5], colors=[color], linewidths=0.8, linestyles="--")


def chain(ax, segments, color, nodes=True, flip_x=False, lw=2.0, label=None):
    from .curves import sample
    s = [[[(-x if flip_x else x), y] for x, y in seg] for seg in segments]
    pts = sample(s)
    ax.plot(pts[:, 0], pts[:, 1], color=color, lw=lw, label=label)
    if nodes:
        for a, b, c, d in s:
            ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=0.6, alpha=0.6)
            ax.plot([c[0], d[0]], [c[1], d[1]], color=color, lw=0.6, alpha=0.6)
            ax.plot([b[0], c[0]], [b[1], c[1]], "o", color=color, ms=3)
            ax.plot([a[0], d[0]], [a[1], d[1]], "s", color=color, ms=5)


def form_sheet(forms, mouse, out, part_z=None, title=None):
    """Top, side and front views of one or more outer forms over the mouse.
    forms: {label: (curves, colour)}; part_z: function y -> z of the parting plane."""
    from .curves import sample
    fig, axs = plt.subplots(1, 3, figsize=(17, 6.8), gridspec_kw={"width_ratios": [1.0, 1.35, 0.95]})
    silhouette(axs[0], mouse, [0, 1])
    silhouette(axs[1], mouse, [1, 2])
    silhouette(axs[2], mouse, [0, 2])
    for label, (c, color) in forms.items():
        chain(axs[0], c["plan"], color, label=label)
        chain(axs[0], c.get("plan_left") or c["plan"], color, nodes=bool(c.get("plan_left")), flip_x=True)
        chain(axs[1], c["profile_lower"], color)
        chain(axs[1], c["profile_upper"], color)
        # front view: the section at its widest, scaled by the plan and profile there
        plan = sample(c["plan"])
        y = plan[np.argmax(plan[:, 0]), 1]
        lower, upper = sample(c["profile_lower"]), sample(c["profile_upper"])
        zb = np.interp(y, *lower[np.argsort(lower[:, 0])].T)
        zt = np.interp(y, *upper[np.argsort(upper[:, 0])].T)
        sec = sample(c["section"])
        hw = plan[:, 0].max()
        left = sample(c.get("plan_left") or c["plan"])[:, 0].max()
        axs[2].plot(sec[:, 0] * hw, zb + sec[:, 1] * (zt - zb), color=color, lw=2)
        axs[2].plot(-sec[:, 0] * left, zb + sec[:, 1] * (zt - zb), color=color, lw=2)
        axs[2].plot([-0.8 * left, 0.8 * hw], [zb, zb], color=color, lw=2)
    if part_z is not None:
        ys = np.linspace(*axs[1].get_xlim(), 2)
        axs[1].plot(ys, part_z(ys), color="#D85A30", lw=1.2, ls="-.", label="parting plane")
    for ax, t in zip(axs, ["top (front down)", "side (front left)", "front (at the widest point)"]):
        ax.set_aspect("equal")
        ax.set_title(t)
        ax.grid(alpha=0.2)
    axs[0].legend(loc="upper right", fontsize=9)
    if part_z is not None:
        axs[1].legend(loc="upper right", fontsize=9)
    if title:
        fig.suptitle(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(out, dpi=70)
    plt.close(fig)
    return out

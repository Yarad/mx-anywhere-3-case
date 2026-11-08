"""Start a case for a new mouse, and draw the pictures to check it.

  python -m case <mouse> new --scan FILE [--front -y] [--up +z] [--scale 1] [options]
  python -m case <mouse> new --dims LENGTH WIDTH HEIGHT [--hump 0.63 ...] [options]
  python -m case <mouse> intake      pictures: orientation, buttons and contacts, outer form

`new` brings the scan into the case frame (front of the mouse at -Y, top at +Z,
feet on z = 0, centred) or builds a stand-in from the dimensions, proposes button
zones and contacts from the proportions of the MX Anywhere 3, writes
mice/<mouse>/case.toml, fits derived.toml and draws the pictures.

Options:
  --name "Logitech M720"        the mouse's name
  --side-buttons left|right|none   thumb buttons, as the user holds the mouse (default none)
  --strip                       the top has a fixed strip between the main buttons (like the MX Anywhere 3):
                                rest the mouse on it too
  --hinge front|back            which end of the mouse goes to the hinge (default front)
  --force                       overwrite an existing case.toml
Without --front/--up the scan is turned automatically: the longest side becomes the
length, the flattest face the bottom, and the front is the end farther from the hump.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
AXES = {"+x": [1, 0, 0], "-x": [-1, 0, 0], "+y": [0, 1, 0], "-y": [0, -1, 0], "+z": [0, 0, 1], "-z": [0, 0, -1]}


# --- the mouse in the case frame ---------------------------------------------------------

def load_scan(path, scale=None):
    m = trimesh.load(path, force="mesh")
    if scale is None:  # mice are 80-140 mm long: guess metres, centimetres and inches
        size = m.extents.max()
        scale = next((s for s in (1, 1000, 10, 25.4) if 60 <= size * s <= 200), 1)
        if scale != 1:
            print(f"the scan is {size:g} units long: taking it as {dict({1000: 'm', 10: 'cm', 25.4: 'in'})[scale]}")
    m.apply_scale(scale)
    return m


def orient(m, front=None, up=None):
    """Rotation that takes the mouse's front to -Y and its top to +Z."""
    if front and up:
        f, u = np.asarray(AXES[front], float), np.asarray(AXES[up], float)
    else:
        c = m.vertices - m.vertices.mean(0)
        _, _, vt = np.linalg.svd(c[np.random.default_rng(0).choice(len(c), min(len(c), 20000))], full_matrices=False)
        length, minor = vt[0], vt[2]
        # the bottom is flat: more of the surface lies near that end of the minor axis
        # (scans often have their normals the wrong way round, so they are not asked)
        pts = trimesh.sample.sample_surface(m, 40000, seed=0)[0]
        s = pts @ minor
        low = (s < s.min() + 1.0).sum() > (s > s.max() - 1.0).sum()
        u = minor if low else -minor
        # up is square to the plane the feet stand on, not to the principal axis
        foot = pts[s < s.min() + 1.0] if low else pts[s > s.max() - 1.0]
        n = trimesh.points.plane_fit(foot)[1]
        u = n if n @ u > 0 else -n
        length = length - (length @ u) * u
        length /= np.linalg.norm(length)
        # and the length along the mouse's mirror plane: the yaw where it best matches its mirror image
        from scipy.spatial import cKDTree
        side = np.cross(length, u)
        q = pts[::8] - pts.mean(0)
        best = min(np.radians(np.arange(-12, 12.01, 0.25)), key=lambda a: _mirror_gap(
            q, np.cos(a) * side + np.sin(a) * length, cKDTree(q)))
        length = np.cos(best) * length - np.sin(best) * side
        # the front: the end farther from the highest point
        top = m.vertices[np.argmax(m.vertices @ u)]
        f = length if (top - m.vertices.mean(0)) @ length < 0 else -length
    Y, Z = -f, u
    R = np.array([np.cross(Y, Z), Y, Z])  # rows: the case's X (the user's left), Y and Z in the scan's frame
    T = np.eye(4)
    T[:3, :3] = R
    return T


def _mirror_gap(q, normal, tree):
    """Mean distance from points mirrored across the plane through the centre with this normal."""
    c = q.mean(0)
    mirrored = q - 2 * ((q - c) @ normal)[:, None] * normal
    return float(np.mean(tree.query(mirrored)[0]))


def to_frame(m, T, hinge="front"):
    m = m.copy()
    m.apply_transform(T)
    if hinge == "back":  # the back of the mouse goes to the hinge, which is always at -Y
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 0, 1]))
    lo, hi = m.bounds
    m.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    return m


def stand_in(dims, hinge="front"):
    """The mouse built from case.toml's [mouse] dimensions, in the case frame."""
    from .proxy import body
    d = dict(dims)
    m = body(d.pop("length"), d.pop("width"), d.pop("height"), **d)
    if hinge == "back":
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 0, 1]))
    return m


# --- proposals ------------------------------------------------------------------------------

def proposals(m, side_buttons="none", strip=False):
    """Button zones and contacts as fractions of the mouse, from the MX Anywhere 3.
    Front at -Y: f(t) is the y a fraction t of the length behind the front tip."""
    lo, hi = m.bounds
    L, hw, H = hi[1] - lo[1], max(-lo[0], hi[0]), hi[2]
    f = lambda t: round(float(lo[1] + t * L), 1)
    xs = lambda t: round(float(t * hw), 1)
    z = lambda t: round(float(t * H), 1)
    v = m.vertices
    widest = f(0.0) + round(float(np.argmax([np.abs(v[(v[:, 1] >= y) & (v[:, 1] < y + 1), 0]).max(initial=0)
                                             for y in np.arange(lo[1], hi[1], 1.0)])), 1)
    buttons = [{"name": "main buttons and wheel", "x": [-xs(0.88), xs(0.88)], "y": [-np.inf, f(0.65)],
                "z": [z(0.3), np.inf], "gap": 3.0}]
    if side_buttons != "none":
        s = 1 if side_buttons == "left" else -1  # the user's left is +X
        x = [xs(0.82), np.inf] if s > 0 else [-np.inf, -xs(0.82)]
        buttons.append({"name": "side buttons", "x": x, "y": [f(0.23), f(0.48)], "z": [z(0.38), z(0.74)], "gap": 2.5})
    contacts = []
    if strip:
        contacts += [
            {"name": "nose", "ray": "top", "at": [0.0, f(0.088)], "r": 2.5, "bumper_d": 4.5,
             "en": "nose in front of the wheel", "ru": "носик перед колесом"},
            {"name": "strip", "ray": "top", "at": [0.0, f(0.54)], "r": 4.5,
             "en": "fixed strip between the buttons", "ru": "полоса между клавишами"}]
    contacts += [
        {"name": "back_l", "ray": "top", "at": [-xs(0.52), f(0.80)], "r": 4.5, "en": "back, side", "ru": "сзади сбоку"},
        {"name": "back_r", "ray": "top", "at": [xs(0.52), f(0.80)], "r": 4.5, "en": "back, side", "ru": "сзади сбоку"},
        {"name": "back_c", "ray": "top", "at": [0.0, f(0.90)], "r": 4.5, "en": "back, centre", "ru": "сзади по центру"},
        {"name": "foot_fl", "ray": "bottom", "at": [-xs(0.43), f(0.15)], "r": 4.5, "en": "under a front foot", "ru": "под передней ножкой"},
        {"name": "foot_fr", "ray": "bottom", "at": [xs(0.43), f(0.15)], "r": 4.5, "en": "under a front foot", "ru": "под передней ножкой"},
        {"name": "foot_bl", "ray": "bottom", "at": [-xs(0.51), f(0.77)], "r": 4.5, "en": "under a back foot", "ru": "под задней ножкой"},
        {"name": "foot_br", "ray": "bottom", "at": [xs(0.51), f(0.77)], "r": 4.5, "en": "under a back foot", "ru": "под задней ножкой"},
        {"name": "side_l", "ray": "side", "side": -1, "at": [widest, z(0.13)], "r": 4.0, "en": "side", "ru": "бок"},
        {"name": "side_r", "ray": "side", "side": 1, "at": [widest, z(0.13)], "r": 4.0, "en": "side", "ru": "бок"},
        {"name": "front_l", "ray": "front", "at": [-xs(0.43), z(0.13)], "r": 3.0, "en": "front", "ru": "перёд"},
        {"name": "front_r", "ray": "front", "at": [xs(0.43), z(0.13)], "r": 3.0, "en": "front", "ru": "перёд"},
    ]
    return buttons, contacts


def flipped(buttons, contacts):
    """The same features after turning the mouse 180 degrees about Z (hinge at its back)."""
    neg = lambda r: [-r[1], -r[0]]
    buttons = [{**b, "x": neg(b["x"]), "y": neg(b["y"])} for b in buttons]
    ray = {"front": "back", "back": "front"}
    out = []
    for c in contacts:
        a, b = c["at"]
        if c["ray"] in ("top", "bottom"):
            c = {**c, "at": [-a, -b]}
        elif c["ray"] == "side":
            c = {**c, "side": -c["side"], "at": [-a, b]}
        else:
            c = {**c, "ray": ray[c["ray"]], "at": [-a, b]}
        out.append(c)
    return buttons, out


# --- case.toml --------------------------------------------------------------------------------

def toml_value(v):
    if isinstance(v, str):
        return '"' + v.replace('"', '\\"') + '"'
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(toml_value(x) for x in v) + "]"
    if isinstance(v, (bool, np.bool_)):
        return "true" if v else "false"
    v = float(v)
    return "inf" if v == np.inf else "-inf" if v == -np.inf else f"{round(v, 3):g}"


def inline(d):
    return "{ " + ", ".join(f"{k} = {toml_value(v)}" for k, v in d.items()) + " }"


CASE_TOML = """# Carry case for the {name}: the mouse, its features and the design.
# Anything not set here comes from case/defaults.toml; geometry computed from the
# mouse is in derived.toml (python -m case {slug} fit).
#
# Lengths in mm in the case frame: front of the mouse at -Y (the hinge end), top at +Z,
# the user's left at +X, feet on z = 0. Check the pictures from `python -m case {slug} intake`.

[mouse]
name = {name_q}
mesh = {mesh}   # repository-relative, in the case frame
source = "{source}"                 # scan | dimensions
{dims}table_z = 0.0

# Zones the case keeps clear of: inside each box the gap grows to `gap` (soft 1.5 mm edges).
buttons = [
{buttons}]

# Where the mouse rests on bumpers. The point on the mouse is found by a ray:
#   top / bottom: straight down / up at at = [x, y]   (bottom: under a foot, on the table plane)
#   side: from side = +1 (+X) or -1 at at = [y, z]
#   front / back: from -Y / +Y at at = [x, z]
# r is the radius of the landing; bumper_d a smaller bumper than [parts] bumper, if needed.
contacts = [
{contacts}]

[design]   # the choices; see case/defaults.toml for every option
lattice = "voronoi"
composition = "heel"
cell_open = 11.0
cell_fine = 5.0
fine_near = "hinge"
rib = "wedge"
rib_width = 3.6
form = "{form}"
parting = "tilted"
lip = "inner"
hinge = "{hinge}"
contacts = "nodes"
notch = "chamfer"
notch_size = [20.0, 3.0, 2.5]
colors = {{ lid = "white-transparent", base = "gray" }}

[parts]
material = "PETG"
rod = 3.0
magnet = [6.0, 2.0]
bumper = {bumper}

[print]
order_language = "en"
"""


def write_case(slug, name, source, mesh_rel, buttons, contacts, hinge, dims=None, asymmetric=False):
    d = ROOT / "mice" / slug
    dims_line = ""
    if dims:
        dims_line = "dimensions = " + inline(dims) + "   # the stand-in is rebuilt from these if mouse.stl is missing\n"
    text = CASE_TOML.format(
        name=name, slug=slug, name_q=toml_value(name), mesh=toml_value(mesh_rel), source=source, dims=dims_line,
        buttons="".join(f"  {inline(b)},\n" for b in buttons), contacts="".join(f"  {inline(c)},\n" for c in contacts),
        form="follow" if asymmetric else "symmetric", hinge=hinge,
        # a stand-in is only as good as its numbers: thicker bumpers take up the difference
        bumper="[6.0, 3.0]   # thicker bumpers for a mouse built from its dimensions" if source == "dimensions" else "[6.0, 2.0]")
    (d / "case.toml").write_text(text, encoding="utf-8")
    return d / "case.toml"


def asymmetry(m):
    """Mean difference between the mouse and its mirror image, mm."""
    from scipy.spatial import cKDTree
    p = trimesh.sample.sample_surface(m, 20000, seed=1)[0]
    d, _ = cKDTree(p).query(p * [-1, 1, 1])
    return float(np.mean(d))


def new(args):
    slug = args.mouse
    d = ROOT / "mice" / slug
    if (d / "case.toml").exists() and not args.force:
        sys.exit(f"{d / 'case.toml'} exists (use --force to start over)")
    d.mkdir(parents=True, exist_ok=True)
    if args.scan:
        raw = load_scan(args.scan, args.scale)
        m = to_frame(raw, orient(raw, args.front, args.up), args.hinge)
        source, dims = "scan", None
    else:
        from .proxy import SHAPE
        L, W, H = args.dims
        dims = {"length": L, "width": W, "height": H, **{k: getattr(args, k) for k in SHAPE if getattr(args, k) is not None}}
        m, source = stand_in(dims, args.hinge), "dimensions"
    m.export(d / "mouse.stl")
    lo, hi = m.bounds
    print(f"mouse: {hi[1] - lo[1]:.1f} x {hi[0] - lo[0]:.1f} x {hi[2] - lo[2]:.1f} mm (length x width x height)")
    # proposals are made with the front at -Y, then turned with the mouse
    front_m = m.copy()
    if args.hinge == "back":
        front_m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 0, 1]))
    buttons, contacts = proposals(front_m, args.side_buttons, args.strip)
    if args.hinge == "back":
        buttons, contacts = flipped(buttons, contacts)
    asym = asymmetry(m) if source == "scan" else 0.0
    print(f"asymmetry: {asym:.2f} mm on average against its mirror image"
          + (" -> form = follow" if asym > 1.5 else " -> symmetric form"))
    path = write_case(slug, args.name or slug, source, str((d / "mouse.stl").relative_to(ROOT)), buttons, contacts,
                      args.hinge, dims, asymmetric=asym > 1.5)
    print(path)
    subprocess.run([sys.executable, "-m", "case", slug, "fit"], check=True, cwd=ROOT)
    subprocess.run([sys.executable, "-m", "case", slug, "intake"], check=True, cwd=ROOT)


# --- pictures --------------------------------------------------------------------------------

def pictures(slug):
    """build/<mouse>/intake/: orientation.png, features.png, form.png."""
    from . import fields as F
    from . import form
    from . import params as P
    from . import render as R
    out = P.BUILD / "intake"
    out.mkdir(parents=True, exist_ok=True)
    m = trimesh.load(P.SCAN)
    gray = R.rgb("#9C9A92")

    titles = {"top": "from above (front at the bottom)", "side": "from the user's left (+X), front on the left",
              "other side": "from the user's right (-X)", "front": "from the front", "back": "from the back",
              "iso": "from the front left"}
    panels = [(titles[v], *R.shade([(m, gray)], v, px=0.3)) for v in ("top", "iso", "front", "side", "other side", "back")]
    R.sheet(panels, out / "orientation.png", title=f"{P.NAME}: is the front at -Y (the hinge end) and the top up?")

    contacts = F.contact_points()
    panels = []
    for view in ("top", "side", "other side", "bottom"):
        img, ext = R.shade([(m, gray)], view, px=0.3)
        panels.append((view, img, ext, view))
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 4, figsize=(22, 6.5))
    for ax, (title, img, ext, view) in zip(axs, panels):
        ax.imshow(img, origin="lower", extent=ext)
        d, up = (np.asarray(v, float) for v in R.VIEWS[view])
        right = np.cross(d / np.linalg.norm(d), up)
        lo, hi = m.bounds[0] - 1, m.bounds[1] + 1
        for b in P.BUTTONS:
            box = np.array([np.clip(b[k], lo[i], hi[i]) for i, k in enumerate("xyz")])
            corners = np.array(np.meshgrid(*box)).reshape(3, -1).T
            u, w = corners @ right, corners @ up
            ax.add_patch(plt.Rectangle((u.min(), w.min()), np.ptp(u), np.ptp(w), color=R.ZONE_C, alpha=0.25, lw=0))
            ax.add_patch(plt.Rectangle((u.min(), w.min()), np.ptp(u), np.ptp(w), fill=False, ec=R.ZONE_C, lw=1.2))
        for i, (name, p, n, r) in enumerate(contacts, 1):
            if n @ d > 0.3:  # facing away from this view
                continue
            u, w = p @ right, p @ up
            ax.add_patch(plt.Circle((u, w), max(r, 2.5), color=R.CONTACT_C, alpha=0.85))
            ax.annotate(f"{i} {name}", (u, w), xytext=(u + 4, w + 3), fontsize=9, color="#085041")
        ax.set_title({"top": "from above", "side": "from the user's left (+X)", "other side": "from the user's right (-X)",
                      "bottom": "from below (front at the bottom)"}[view])
        ax.set_aspect("equal")
        ax.axis("off")
    fig.suptitle(f"{P.NAME}: button zones (red, the case keeps clear) and contacts (green, bumpers)", fontsize=14)
    plt.tight_layout()
    plt.savefig(out / "features.png", dpi=65)
    plt.close(fig)

    R.form_sheet({"case": (P.FORM, "#185FA5")}, m, out / "form.png", part_z=form.part_z,
                 title=f"{P.NAME}: outer form (squares: Bezier nodes, dots: handles) and the parting plane")
    for f in ("orientation.png", "features.png", "form.png"):
        print(out / f)


def main():
    ap = argparse.ArgumentParser(prog="python -m case <mouse> new", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["new", "pictures"])
    ap.add_argument("mouse")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--scan")
    src.add_argument("--dims", nargs=3, type=float, metavar=("LENGTH", "WIDTH", "HEIGHT"))
    ap.add_argument("--front", choices=list(AXES))
    ap.add_argument("--up", choices=list(AXES))
    ap.add_argument("--scale", type=float)
    ap.add_argument("--name")
    ap.add_argument("--side-buttons", choices=["left", "right", "none"], default="none")
    ap.add_argument("--strip", action="store_true")
    ap.add_argument("--hinge", choices=["front", "back"], default="front")
    ap.add_argument("--force", action="store_true")
    from .proxy import SHAPE
    for k, (dflt, help_) in SHAPE.items():
        ap.add_argument(f"--{k.replace('_', '-')}", dest=k, type=float, help=f"{help_} (default {dflt})")
    args = ap.parse_args()
    if args.action == "pictures":
        pictures(args.mouse)
    elif not (args.scan or args.dims):
        ap.error("give --scan FILE or --dims LENGTH WIDTH HEIGHT")
    else:
        new(args)


if __name__ == "__main__":
    main()

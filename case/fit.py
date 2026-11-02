"""Fit mice/<mouse>/derived.toml to the mouse: the parting plane, the outer form,
the hinge, where the magnets may go and the grid.

The outer form keeps the curves of the MX Anywhere 3 case, with the same few
Bezier nodes. Its control points move until the form holds the cavity (the mouse
plus its gaps, swept along the ways the case opens) under at least [fit] wall of
material, while staying as close to it as the curves allow.

Run:  .venv/bin/python -m case <mouse> fit            fit and write derived.toml
      .venv/bin/python -m case <mouse> fit --check    only report the wall the current form leaves
"""
import importlib
import json
import sys

import numpy as np
import trimesh
from scipy.optimize import least_squares

from . import params as P
from .curves import sample, to_nodes, to_segments

# the MX Anywhere 3 case, drawn by hand: the shape every fit starts from
TEMPLATE = {
    "plan": [[[0, -55.5], [18, -55.5], [28.5, -53], [32, -45]], [[32, -45], [34.5, -39], [35.4, -26], [35.8, -10]],
             [[35.8, -10], [36.1, 5], [37.5, 15], [37, 25]], [[37, 25], [38, 46], [32, 56.5], [0, 56.5]]],
    "profile_upper": [[[56.5, 19], [56.5, 30], [46.5, 39], [15, 39]], [[15, 39], [-15, 39], [-32, 33.5], [-45, 22.5]],
                      [[-45, 22.5], [-52, 16.5], [-55.5, 12], [-55.5, 7.5]]],
    "section": [[[0.8, 0.0], [0.87, 0.06], [1.0, 0.188], [1.0, 0.424]],
                [[1.0, 0.424], [1.0, 0.753], [0.693, 1.0], [0.0, 1.0]]],
}
T_HALF, T_FRONT, T_BACK, T_TOP, T_MOUSE_TOP = 32.42, -55.5, 56.5, 39.0, 33.47  # MX3 mouse and case extents


def fit_chain(nodes, value_axis, target, fixed_tangent, free_ends=True, weight_short=25.0, cap=None):
    """Move the inner nodes (position, tangent angle, handles) and the end handles
    so the chain's `value_axis` coordinate stays at or beyond target(y) and close to it.
    target: (ys, values) on 1 mm bins, NaN where nothing constrains the chain.
    fixed_tangent: indices of inner nodes whose tangent keeps its direction.
    free_ends: whether the handles at the start and the end may change (a bool for both).
    cap: the value may not go beyond this."""
    ys, vals = target
    defined = ~np.isnan(vals)
    vfill = np.where(defined, vals, 0.0)

    def unpack(x):
        out = [[n[0].copy(), n[1].copy(), n[2], n[3]] for n in nodes]
        k = 0
        if ends[0]:
            out[0][3] = x[k]; k += 1
        if ends[1]:
            out[-1][2] = x[k]; k += 1
        for i in range(1, len(nodes) - 1):
            out[i][0] = x[k:k + 2].copy(); k += 2
            if i not in fixed_tangent:
                a = x[k]; k += 1
                out[i][1] = np.array([np.cos(a), np.sin(a)])
            out[i][2], out[i][3] = x[k], x[k + 1]; k += 2
        return out

    ends = (free_ends, free_ends) if isinstance(free_ends, bool) else free_ends
    x0 = ([nodes[0][3]] if ends[0] else []) + ([nodes[-1][2]] if ends[1] else [])
    for i in range(1, len(nodes) - 1):
        x0 += list(nodes[i][0])
        if i not in fixed_tangent:
            x0.append(np.arctan2(nodes[i][1][1], nodes[i][1][0]))
        x0 += [nodes[i][2], nodes[i][3]]
    x0 = np.array(x0, float)
    scale = np.where(np.abs(x0) > 5, np.abs(x0), 5.0)

    y_axis = 0 if value_axis == 1 else 1
    direction = np.sign(nodes[-1][0][y_axis] - nodes[0][0][y_axis])  # the chain runs one way along y

    def residual(x):
        pts = sample(to_segments(unpack(x)))
        y, v = pts[:, y_axis], pts[:, value_axis]
        loops = np.maximum(-np.diff(y) * direction, 0) * 200  # no doubling back
        over = np.maximum(v - cap, 0) * 100 if cap is not None else np.zeros(0)
        tv = np.interp(y, ys, vfill)
        ok = np.interp(y, ys, defined.astype(float)) > 0.99
        short = np.where(ok, np.maximum(tv - v, 0), 0) * weight_short
        close = np.where(ok, v - tv, 0) * 0.6
        lens = np.array([l for n in unpack(x) for l in n[2:]])
        handles = np.minimum(lens, 0.5) * 50 - 25  # no handles shorter than 0.5 mm
        return np.concatenate([short, close, (x - x0) / scale * 2.0, np.minimum(handles, 0), loops, over])

    res = least_squares(residual, x0, method="trf", max_nfev=400)
    return unpack(res.x)


# --- the plan: a tamer family of curves ---------------------------------------------------
# Inner nodes sit at the template's shares of the length; each has an x, a tangent along
# the target outline there, and every handle is a bounded share of its segment's chord.
# Free handles, nodes and tangents would find S-bends and loops; this family stays calm.
NODE_AT = (0.094, 0.406, 0.719)


def plan_params(segments):
    yf, yb = segments[0][0][1], segments[-1][3][1]
    nodes = to_nodes(segments)
    ys = yf + np.array(NODE_AT) * (yb - yf)
    pts = sample(segments, 200)
    xs = np.interp(ys, pts[:, 1], pts[:, 0])
    ang = [np.arctan2(n[1][0], n[1][1]) for n in nodes[1:-1]]  # from +Y towards +X
    ratios = []
    for (a, b, c, d) in segments:
        chord = np.linalg.norm(np.subtract(d, a))
        ratios += [np.linalg.norm(np.subtract(b, a)) / chord, np.linalg.norm(np.subtract(d, c)) / chord]
    return np.r_[xs, ang, np.clip(ratios, 0.16, 0.69)]


def plan_from(x, yf, yb):
    ys = yf + np.array(NODE_AT) * (yb - yf)
    pts = [np.array([0.0, yf])] + [np.array([xi, yi]) for xi, yi in zip(x[:3], ys)] + [np.array([0.0, yb])]
    tan = [np.array([1.0, 0.0])] + [np.array([np.sin(a), np.cos(a)]) for a in x[3:6]] + [np.array([-1.0, 0.0])]
    segs = []
    for i in range(4):
        chord = np.linalg.norm(pts[i + 1] - pts[i])
        segs.append([pts[i], pts[i] + tan[i] * x[6 + 2 * i] * chord, pts[i + 1] - tan[i + 1] * x[7 + 2 * i] * chord,
                     pts[i + 1]])
    return [[list(map(float, q)) for q in s] for s in segs]


def fit_plan(segments, target, weight_short=25.0):
    """The plan's half outline at or beyond target(y) and close to it."""
    ys, vals = target
    defined = ~np.isnan(vals)
    vfill = np.where(defined, vals, 0.0)
    yf, yb = segments[0][0][1], segments[-1][3][1]
    node_y = yf + np.array(NODE_AT) * (yb - yf)
    smooth = np.convolve(np.interp(ys, ys[defined], vals[defined]), np.ones(9) / 9, mode="same")
    angles = np.arctan(np.interp(node_y, ys, np.gradient(smooth, ys)))  # along the target there
    p0 = plan_params(segments)
    free = np.r_[0:3, 6:14]
    lo = np.r_[np.full(3, 1.0), np.full(8, 0.15)]
    hi = np.r_[np.full(3, 200.0), np.full(8, 0.7)]
    lo[3], hi[3] = p0[6] - 0.05, p0[6] + 0.05  # the nose keeps the template's blunt front (a long hinge)
    x0 = np.clip(p0[free], lo + 1e-6, hi - 1e-6)
    scale = np.where(np.abs(x0) > 5, np.abs(x0), 5.0)
    full = lambda x: np.r_[x[:3], angles, x[3:]]

    def residual(x):
        pts = sample(plan_from(full(x), yf, yb))
        tv = np.interp(pts[:, 1], ys, vfill)
        ok = np.interp(pts[:, 1], ys, defined.astype(float)) > 0.99
        short = np.where(ok, np.maximum(tv - pts[:, 0], 0), 0) * weight_short
        close = np.where(ok, pts[:, 0] - tv, 0) * 0.6
        loops = np.maximum(-np.diff(pts[:, 1]), 0) * 200
        return np.concatenate([short, close, (x - x0) / scale * 2.0, loops])

    return plan_from(full(least_squares(residual, x0, bounds=(lo, hi), max_nfev=400).x), yf, yb)


# --- what the form has to hold --------------------------------------------------------

def parting(mouse):
    """Plane through the points where the mouse reaches furthest forward and back."""
    v, (lo, hi) = mouse.vertices, mouse.bounds
    zf = round(2 * float(v[v[:, 1] < lo[1] + 0.5, 2].mean())) / 2
    zb = round(2 * float(v[v[:, 1] > hi[1] - 0.5, 2].mean())) / 2
    if P.PARTING == "horizontal":
        return round((zf + zb) / 2, 1), 0.0, zf, zb
    slope = round((zb - zf) / (hi[1] - lo[1]), 3)
    return round(zf - slope * lo[1], 1), slope, zf, zb


def first_guess(mouse, zf, zb, yf=None, yb=None):
    """The template stretched over the mouse, from tip yf to tip yb."""
    lo, hi = mouse.bounds
    yf = round(lo[1] - P.FIT["front"], 1) if yf is None else yf
    yb = round(hi[1] + P.FIT["back"], 1) if yb is None else yb
    floor = round(P.TABLE_Z - P.FIT["floor"], 2)
    top = hi[2] + (T_TOP - T_MOUSE_TOP)
    sx, sy = max(-lo[0], hi[0]) / T_HALF, (yb - yf) / (T_BACK - T_FRONT)
    plan = [[[x * sx, yf + (y - T_FRONT) * sy] for x, y in seg] for seg in TEMPLATE["plan"]]
    plan[0][0], plan[-1][3] = [0.0, yf], [0.0, yb]
    sz = (top - floor) / (T_TOP + 4.6)
    upper = [[[yf + (y - T_FRONT) * sy, floor + (z + 4.6) * sz] for y, z in seg] for seg in TEMPLATE["profile_upper"]]
    upper[0][0], upper[0][1] = [yb, zb], [yb, zb + 0.47 * (top - zb)]
    upper[-1][2], upper[-1][3] = [yf, zf + 0.15 * (top - zf)], [yf, zf]
    return {"plan": plan, "profile_upper": upper, "profile_lower": lower(yf, yb, zf, zb, floor),
            "section": TEMPLATE["section"]}


def lower(yf, yb, zf, zb, floor):
    """Flat bottom with the template's rounded ends, in millimetres."""
    return [[[yf, zf], [yf, floor + 0.38 * (zf - floor)], [yf + 3.5, floor], [yf + 9.5, floor]],
            [[yf + 9.5, floor], [yf + 9.5 + (yb - yf - 23) / 3, floor], [yb - 13.5 - (yb - yf - 23) / 3, floor],
             [yb - 13.5, floor]],
            [[yb - 13.5, floor], [yb - 5.0, floor], [yb, floor + 0.53 * (zb - floor)], [yb, zb]]]


def extras(form_curves, z0, slope):
    """Everything in derived.toml besides the form, read off the form."""
    pts = sample(form_curves["plan"] + (form_curves.get("plan_left") or []))
    yf, yb = form_curves["plan"][0][0][1], form_curves["plan"][-1][3][1]
    up = sample(form_curves["profile_upper"])
    floor = form_curves["profile_lower"][1][0][1]
    hw_max = float(pts[:, 0].max())
    hinge_y = yf + 1.0
    hw_hinge = min(float(np.interp(hinge_y + 2.0, s[:, 1], s[:, 0]))
                   for s in [sample(form_curves["plan"])] + ([sample(form_curves["plan_left"])] if form_curves.get("plan_left") else []))
    half = lambda v, up_: (np.ceil(v * 2) / 2) if up_ else (np.floor(v * 2) / 2)
    length = yb - yf
    return {
        "grid_min": [half(-hw_max - 4.0, False), half(yf - 6.5, False), half(floor - 2.4, False)],
        "grid_max": [half(hw_max + 4.0, True), half(yb + 4.5, True), half(float(up[:, 1].max()) + 3.5, True)],
        "part_z0": z0, "part_slope": slope, "hinge_y": round(hinge_y, 2),
        "knuckle_span": float(np.clip(2 * np.floor(hw_hinge), 20, 44)),
        "lip_front_y": round(yf + 0.69 * length, 1),
        "magnet_x": [4.0, round(hw_max - 1.0)], "magnet_y": [round(yf + 0.63 * length), round(yb - 0.5)],
    }


def apply(derived):
    """Make derived values current for the modules that read them."""
    P.FORM = derived["form"]
    P.GRID_MIN, P.GRID_MAX = tuple(derived["grid_min"]), tuple(derived["grid_max"])
    P.PART_Z0, P.PART_SLOPE, P.HINGE_Y = derived["part_z0"], derived["part_slope"], derived["hinge_y"]
    P.KNUCKLE_SPAN, P.LIP_FRONT_Y = derived["knuckle_span"], derived["lip_front_y"]
    P.MAGNET_X, P.MAGNET_Y = derived["magnet_x"], derived["magnet_y"]
    from . import form
    importlib.reload(form)
    return form


def cavity_points(h=0.6):
    """Points on the cavity's surface with outward normals, the bottom left out."""
    from . import fields as F
    importlib.reload(F)
    grid = F.Grid(h=h)
    Cg = F.mouse_sdf(grid) - F.gap_field(grid, F.contact_points())
    Pl = F.plane_field(grid)
    C = np.where(Pl > 0, F.sweep_open(grid, Cg, P.LID_SWEEP_DEG, 5.0), F.sweep_up(Cg))
    cav = grid.to_mesh(C)
    n = np.asarray(cav.vertex_normals)
    keep = n[:, 2] > -0.6  # the floor under the mouse is set by [fit] floor, not by the wall
    return cav.vertices[keep], n[keep], grid


def magnet_points(V, N, z0, slope, mouse):
    """Wall points that leave room for a magnet pocket where the rim turns the
    back corners: the most diagonal spot on each side and its neighbourhood."""
    room = P.MAG_D / 2 + P.MAG_SKIN
    pd = (V[:, 2] - (z0 + slope * V[:, 1])) / np.sqrt(1 + slope ** 2)
    out = []
    for side in (1, -1):
        cand = (np.abs(pd) < 1.5) & (V[:, 1] > mouse.bounds[1][1] - 15) & (N[:, 1] > 0.3) & (N[:, 0] * side > 0.3)
        if not cand.any():
            continue
        best = np.argmax(np.where(cand, N[:, 1] + N[:, 0] * side, -9))
        out.append(V[best] + N[best] * (2 * room + 0.3))
    return np.array(out).reshape(-1, 3)


def envelope(ys_pts, vals, lo, hi, step=1.0):
    """Largest value per bin of y (NaN where no point falls)."""
    bins = np.arange(np.floor(lo) - step, np.ceil(hi) + 2 * step, step)
    out = np.full(len(bins), np.nan)
    idx = np.clip(np.round((ys_pts - bins[0]) / step).astype(int), 0, len(bins) - 1)
    np.fmax.at(out, idx, vals)
    return bins, out


def majorant(ys, vals):
    """The smallest concave curve over the envelope: the outline spans the mouse's
    waist instead of following it in."""
    ok = ~np.isnan(vals)
    pts = np.c_[ys[ok], vals[ok]]
    hull = []
    for p in pts:  # upper hull, monotone chain
        while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (p[1] - hull[-2][1])
                                  - (hull[-1][1] - hull[-2][1]) * (p[0] - hull[-2][0])) >= 0:
            hull.pop()
        hull.append(p)
    hull = np.array(hull)
    out = np.full_like(vals, np.nan)
    out[ok] = np.interp(ys[ok], hull[:, 0], hull[:, 1])
    return out


def bump(push, idx, amount):
    """Raise each bin of push by the largest amount asked for it."""
    d = np.zeros_like(push)
    np.maximum.at(d, idx, amount)
    push += d


def fit_form(guess, T, M, z0, slope):
    """Fit the profile to the side silhouette of the wall points T, the plan to
    their top silhouette (each side for a following form) and the section's
    shoulder to the points scaled into plan and profile. Where points still poke
    out, push whichever curve holds them there: the roof, the shoulder or the plan.
    M: points that need room for the magnets; only the plan makes that room."""
    form = apply({"form": guess, **extras(guess, z0, slope)})
    yf, yb = guess["plan"][0][0][1], guess["plan"][-1][3][1]
    push_top = np.zeros(len(envelope(T[:1, 1], T[:1, 1], yf, yb)[0]))
    push_side = {1: push_top.copy(), -1: push_top.copy()}
    push_sec = np.zeros(len(envelope(T[:1, 1], T[:1, 1], 0.0, 1.0, step=0.02)[0]))
    shoulder_v = TEMPLATE["section"][1][0][1]  # below this the section is full width (and the 45 degree foot)
    curves = best = guess
    worst_best = np.inf
    sides = (1, -1) if P.FORM_STYLE == "follow" else (1,)
    as_list = lambda segs: [[list(map(float, p)) for p in s] for s in segs]
    for round_ in range(8):
        ys, top = envelope(T[:, 1], T[:, 2], yf, yb)
        top = majorant(ys, top)
        upper = fit_chain(to_nodes(curves["profile_upper"]), 1, (ys, top + push_top), fixed_tangent={1})
        curves = {**curves, "profile_upper": as_list(to_segments(upper))}
        zb_m, zt_m = form.z_bottom(M[:, 1]), form.z_top(M[:, 1])
        u_m = np.maximum(form.section_u(np.clip((M[:, 2] - zb_m) / (zt_m - zb_m), 0, 1)), 0.3)
        for side in sides:
            sel = (T[:, 0] * side >= 0) if len(sides) == 2 else np.ones(len(T), bool)
            ys, wide = envelope(T[sel, 1], np.abs(T[sel, 0]), yf, yb)
            sel_m = (M[:, 0] * side >= 0) if len(sides) == 2 else np.ones(len(M), bool)
            wide = majorant(ys, np.fmax(wide, envelope(M[sel_m, 1], np.abs(M[sel_m, 0]) / u_m[sel_m], yf, yb)[1]))
            key = "plan" if side == 1 else "plan_left"
            curves = {**curves, key: fit_plan(curves.get(key) or curves["plan"], (ys, wide + push_side[side]))}
        form = apply({"form": curves, **extras(curves, z0, slope)})
        # the section: how wide the points are, as a share of the plan, at each share of the height;
        # only the shoulder rounds more or less, the 45 degree foot stays for printing without support
        zb_, zt_ = form.z_bottom(T[:, 1]), form.z_top(T[:, 1])
        v = np.clip((T[:, 2] - zb_) / np.maximum(zt_ - zb_, 1e-3), 0, 1)
        hw = np.where(T[:, 0] < 0, form.half_width(T[:, 1], True), form.half_width(T[:, 1]))
        r = np.abs(T[:, 0]) / np.maximum(hw, 1e-3)
        vs, need = envelope(v, np.minimum(r, 1.0), 0.0, 1.0, step=0.02)
        need = np.where(vs >= shoulder_v, need + push_sec, np.nan)
        shoulder = fit_chain(to_nodes(TEMPLATE["section"][1:]), 0, (vs, np.minimum(need, 1.0)), fixed_tangent=set(), cap=1.0)
        curves = {**curves, "section": TEMPLATE["section"][:1] + as_list(to_segments(shoulder))}
        form = apply({"form": curves, **extras(curves, z0, slope)})
        f = form.implicit(T[:, 0], T[:, 1], T[:, 2])
        f_m = form.implicit(M[:, 0], M[:, 1], M[:, 2])
        out = f > 0.05
        print(f"  round {round_ + 1}: {out.sum()} of {len(T)} wall points outside the form, worst {f.max():.2f} mm; "
              f"magnets short of room by {max(f_m.max(), 0):.2f} mm", file=sys.stderr)
        f = np.maximum(f, -1)
        if f_m.max() > 0.05:  # the magnets' room comes from the plan
            for side in sides:
                s = (M[:, 0] * side >= 0) if len(sides) == 2 else np.ones(len(M), bool)
                im = np.clip(np.round(M[s, 1] - ys[0]).astype(int), 0, len(ys) - 1)
                bump(push_side[side], im, np.maximum(f_m[s], 0) * 0.7)
            f = np.r_[f, f_m]
        if f.max() < worst_best:
            best, worst_best = curves, f.max()
        if f.max() <= 0.05:
            break
        f = f[:len(T)]
        fo, vo = f[out], v[out]
        idx = np.clip(np.round(T[out, 1] - ys[0]).astype(int), 0, len(ys) - 1)
        roof = vo > 0.92                    # over the top: the profile
        shoulder_out = ~roof & (vo >= shoulder_v)  # on the shoulder: the section
        flank = ~roof & ~shoulder_out       # where the section is full width or the foot: the plan
        bump(push_top, idx[roof], 0.7 * fo[roof] + 0.1)
        vi = np.clip(np.round(vo[shoulder_out] / 0.02).astype(int) + 1, 0, len(push_sec) - 1)
        bump(push_sec, vi, 0.7 * fo[shoulder_out] / np.maximum(hw[out][shoulder_out], 1) + 0.005)
        for side in sides:
            s = (T[out, 0] * side >= 0) if len(sides) == 2 else np.ones(out.sum(), bool)
            bump(push_side[side], idx[flank & s], 0.7 * fo[flank & s] + 0.1)
        np.clip(push_top, 0, 8, out=push_top)
        np.clip(push_sec, 0, 0.3, out=push_sec)
        for side in sides:
            np.clip(push_side[side], 0, 8, out=push_side[side])
    if worst_best > 0.05:
        print(f"  the form still leaves {worst_best:.2f} mm too little wall somewhere: check form.png", file=sys.stderr)
    return best


def write(derived):
    def fmt(v):
        if isinstance(v, list):
            return "[" + ", ".join(fmt(x) for x in v) + "]"
        return f"{round(float(v), 3):g}" if isinstance(v, (float, int, np.floating)) else repr(v)
    lines = ["# Geometry derived from the mouse, written by `python -m case <mouse> fit`.",
             "# Rerun fit after changing the mouse, its gaps or [fit]; edit by hand only to try something.", ""]
    for k in ("grid_min", "grid_max", "part_z0", "part_slope", "hinge_y", "knuckle_span", "lip_front_y",
              "magnet_x", "magnet_y"):
        lines.append(f"{k} = {fmt(derived[k])}")
    lines += ["", "[form]"]
    for k in ("plan", "plan_left", "profile_lower", "profile_upper", "section"):
        if derived["form"].get(k):
            lines.append(f"{k} = [\n" + "".join(f"  {fmt(s)},\n" for s in derived["form"][k]) + "]")
    (P.DIR / "derived.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def wall_report(T_cav, n):
    """How thick the current form is over the cavity (distance along the normal)."""
    from . import form
    t = np.zeros(len(T_cav))
    for step in np.arange(0.2, 12, 0.2):  # march out until we leave the form
        q = T_cav + n * step
        inside = form.implicit(q[:, 0], q[:, 1], q[:, 2]) < 0
        t = np.where(inside, step, t)
    return t


def compute(mouse):
    """derived.toml's contents for the mouse."""
    z0, slope, zf, zb = parting(mouse)
    print(f"parting plane: {zf:g} mm at the nose, {zb:g} mm at the back -> z = {z0:g} + {slope:g} y", file=sys.stderr)
    guess = first_guess(mouse, zf, zb)
    for _ in range(3):  # the tips must clear the cavity, which moves with the hinge at the front tip
        apply({"form": guess, **extras(guess, z0, slope)})
        V, N, _ = cavity_points()
        T = V + N * P.FIT["wall"]
        yf0, yb0 = guess["plan"][0][0][1], guess["plan"][-1][3][1]
        yf, yb = min(yf0, np.floor((T[:, 1].min() - 0.3) * 2) / 2), max(yb0, np.ceil((T[:, 1].max() + 0.3) * 2) / 2)
        if (yf, yb) == (yf0, yb0):
            break
        print(f"  tips moved to y = {yf:g} and {yb:g} to clear the cavity", file=sys.stderr)
        guess = first_guess(mouse, zf, zb, yf, yb)
    T = T[np.random.default_rng(0).permutation(len(T))[:30000]]
    curves = fit_form(guess, T, magnet_points(V, N, z0, slope, mouse), z0, slope)
    return {"form": curves, **extras(curves, z0, slope)}


def main(args):
    mouse = trimesh.load(P.SCAN)
    if "--check" in args:
        V, N, _ = cavity_points()
        t = wall_report(V, N)
        print(f"wall over the cavity: min {t.min():.1f}, 1% {np.percentile(t, 1):.1f}, "
              f"5% {np.percentile(t, 5):.1f}, median {np.median(t):.1f} mm")
        return
    derived = compute(mouse)
    if "--json" in args:  # for option sheets: print, don't write
        print(json.dumps(derived["form"]))
        return
    write(derived)
    print(P.DIR / "derived.toml")


if __name__ == "__main__":
    main(sys.argv[1:])

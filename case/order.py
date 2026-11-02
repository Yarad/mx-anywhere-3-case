"""Order package for the print shop: one STL per part with its colour in the
name, a picture of the parts as they lie on the bed in their colours, a picture
of the finished case and the order text to paste into a message. Everything zipped.

Run after the print build:  .venv/bin/python -m case <mouse> order
The language of the order is [print] order_language in the mouse's case.toml.
"""
import os
import shutil
import subprocess
import zipfile

import numpy as np
import trimesh

from . import hinge
from . import params as P
from .colors import PALETTE, color_name, material

TEXT = {
    "ru": {
        "parts": {"base": "основание", "lid": "крышка"},
        "setup": {
            "base": "дном на стол, как в файле. Поддержки не нужны.",
            "lid": "плоским краем на стол, куполом вверх, как в файле. Поддержки древовидные, "
                   "ТОЛЬКО от стола (растут внутри купола). Снаружи поддержек быть не должно.",
        },
        "item": "{i}. {name} — {part}.\n   Цвет: {material} {color}.\n"
                "   Габарит {sx:.0f} × {sy:.0f} × {sz:.0f} мм, около {grams:.0f} г без поддержек.\n   Положение: {setup}",
        "body": """Здравствуйте! Хочу заказать печать двух деталей из {material}.

{items}

Для обеих деталей:
- материал {material}, сопло 0.4 мм, слой 0.2 мм, 3 периметра, заполнение 100 %;
- размеры в миллиметрах, масштаб 1:1, ориентацию в файлах не менять — она уже правильная для печати;
- отверстия петли ({holes} мм) печатаются без поддержек, их не трогать;
- {colors_note}

Вложения: na_stole.png — положение деталей на столе{sheet_note}.
""",
        "two_colors": "детали разных цветов, поэтому печатать их отдельными заданиями.",
        "one_color": "обе детали одного цвета, их можно печатать одним заданием.",
        "sheet": ", cveta.png — как должен выглядеть готовый чехол",
        "bed": "na_stole.png", "views": "cveta.png", "order": "zakaz.txt",
    },
    "en": {
        "parts": {"base": "base", "lid": "lid"},
        "setup": {
            "base": "flat bottom on the bed, as in the file. No supports.",
            "lid": "flat rim on the bed, dome up, as in the file. Tree supports from the build plate "
                   "ONLY (they grow inside the dome). No supports on the outside.",
        },
        "item": "{i}. {name}: the {part}.\n   Colour: {material} {color}.\n"
                "   {sx:.0f} × {sy:.0f} × {sz:.0f} mm, about {grams:.0f} g without supports.\n   On the bed: {setup}",
        "body": """Hello! I would like two parts printed in {material}.

{items}

For both parts:
- {material}, 0.4 mm nozzle, 0.2 mm layers, 3 walls, 100 % infill;
- millimetres, scale 1:1; please keep the orientation of the files, it is already the print orientation;
- the hinge holes ({holes} mm) print without supports, please leave them as they are;
- {colors_note}

Attached: on_the_bed.png shows the parts on the bed{sheet_note}.
""",
        "two_colors": "the parts are in different colours, so they are separate print jobs.",
        "one_color": "both parts are the same colour and can share one print job.",
        "sheet": ", finished_case.png the finished case",
        "bed": "on_the_bed.png", "views": "finished_case.png", "order": "order.txt",
    },
}


def build(stage="print"):
    t = TEXT[P.ORDER_LANGUAGE]
    src = P.BUILD / stage
    out = P.BUILD / "order"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    items, scene = [], trimesh.Scene()
    x = 0.0
    for i, part in enumerate(("base", "lid"), 1):
        color = P.PRINT_COLORS[part]
        name = f"case_{part}_{P.MATERIAL}_{color}.stl"
        shutil.copy(src / f"mx_case_{part}.stl", out / name)
        m = trimesh.load(out / name)
        sx, sy, sz = m.extents
        items.append(t["item"].format(i=i, name=name, part=t["parts"][part], material=P.MATERIAL,
                                      color=color_name(color, P.ORDER_LANGUAGE), sx=sx, sy=sy, sz=sz,
                                      grams=m.volume / 1000 * P.DENSITY, setup=t["setup"][part]))
        m = hinge.to_trimesh(hinge.to_manifold(m).simplify(0.03))  # the renderer skips colour on heavy meshes
        m.apply_translation([x - m.bounds[0, 0], -m.bounds.mean(0)[1], 0])
        x = m.bounds[1, 0] + 12
        m.visual = material(color)
        scene.add_geometry(m, node_name=part)
    lo, hi = np.array(scene.bounds)
    bed = trimesh.creation.box(extents=[hi[0] - lo[0] + 24, hi[1] - lo[1] + 24, 1.0])
    bed.apply_translation([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, -0.55])
    bed.visual = material("#3A3B3D")  # the printer bed, also makes the renderer honour the colours
    scene.add_geometry(bed, node_name="bed")

    sheet = colour_sheet()
    if sheet:
        shutil.copy(sheet, out / t["views"])
    holes = f"{P.PIN_HOLE_BASE:g} / {P.PIN_HOLE_LID:g}"
    same = P.PRINT_COLORS["base"] == P.PRINT_COLORS["lid"]
    (out / t["order"]).write_text(t["body"].format(
        material=P.MATERIAL, items="\n\n".join(items), holes=holes,
        colors_note=t["one_color"] if same else t["two_colors"], sheet_note=t["sheet"] if sheet else ""),
        encoding="utf-8")

    from .preview import Z_UP_TO_Y_UP
    scene.apply_transform(Z_UP_TO_Y_UP)
    glb = P.BUILD / f"order_plate_{os.getpid()}.glb"  # fresh path: the engine keeps appearance per path
    scene.export(glb)
    try:
        subprocess.run(["cadgen", "+0.8.4", "snapshot", str(glb), str(out / t["bed"]), "--camera=iso"],
                       check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        from .render import plate_picture  # no cadgen: draw it ourselves
        plate_picture(scene, out / t["bed"])
    glb.unlink()

    zpath = P.BUILD / f"{P.MOUSE}_case_order.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            z.write(f, f.name)
    print(out)
    print(zpath, f"{zpath.stat().st_size / 1e6:.1f} MB")


def colour_sheet():
    """Views of the finished case in its colours (needs cadgen)."""
    from .colors import scheme_views
    lid = P.PRINT_COLORS["lid"]
    try:
        _, sheet = scheme_views(P.PRINT_COLORS["base"], lid, lid_alpha=0.6 if "transparent" in lid else 1.0,
                                tag="chosen", lang=P.ORDER_LANGUAGE)
        return sheet
    except (OSError, subprocess.CalledProcessError):
        return None


if __name__ == "__main__":
    assert set(P.PRINT_COLORS.values()) <= set(PALETTE), f"unknown colour in {P.PRINT_COLORS}"
    build()

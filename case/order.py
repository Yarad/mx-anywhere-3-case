"""Order package for the print shop: one STL per part with its colour in the
name, a picture of the parts as they lie on the bed in their colours, and the
order text to paste into a message. Everything zipped.

Run after `python -m case.build print`:  .venv/bin/python -m case.order
"""
import os
import shutil
import subprocess
import zipfile

import numpy as np
import trimesh

from . import hinge
from . import params as P
from .colors import PETG, material

PARTS = {"base": "основание", "lid": "крышка"}
SETUP = {
    "base": "дном на стол, как в файле. Поддержки не нужны.",
    "lid": "плоским краем на стол, куполом вверх, как в файле. Поддержки древовидные, "
           "ТОЛЬКО от стола (растут внутри купола). Снаружи поддержек быть не должно.",
}

TEXT = """Здравствуйте! Хочу заказать печать двух деталей из PETG.

{items}

Для обеих деталей:
- материал PETG, сопло 0.4 мм, слой 0.2 мм, 3 периметра, заполнение 100 %;
- размеры в миллиметрах, масштаб 1:1, ориентацию в файлах не менять — она уже правильная для печати;
- отверстия петли (3.0 и 3.25 мм) печатаются без поддержек, их не трогать;
- детали разных цветов, поэтому печатать их отдельными заданиями.

Вложения: na_stole.png — положение деталей на столе, cveta.png — как должен выглядеть
готовый чехол (крышка белая прозрачная, основание серое).
"""


def build(stage="print"):
    src = P.BUILD / stage
    out = P.BUILD / "order"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    items, scene = [], trimesh.Scene()
    x = 0.0
    for i, (part, ru) in enumerate(PARTS.items(), 1):
        color_ru, color_en = P.PRINT_COLORS[part]
        name = f"mx_case_{part}_PETG_{color_en}.stl"
        shutil.copy(src / f"mx_case_{part}.stl", out / name)
        m = trimesh.load(out / name)
        grams = m.volume / 1000 * P.PETG_DENSITY
        sx, sy, sz = m.extents
        items.append(f"{i}. {name} — {ru}.\n"
                     f"   Цвет: PETG {color_ru}.\n"
                     f"   Габарит {sx:.0f} × {sy:.0f} × {sz:.0f} мм, около {grams:.0f} г без поддержек.\n"
                     f"   Положение: {SETUP[part]}")
        m = hinge.to_trimesh(hinge.to_manifold(m).simplify(0.03))  # the renderer skips colour on heavy meshes
        m.apply_translation([x - m.bounds[0, 0], -m.bounds.mean(0)[1], 0])
        x = m.bounds[1, 0] + 12
        m.visual = material(color_ru)
        scene.add_geometry(m, node_name=part)
    lo, hi = np.array(scene.bounds)
    bed = trimesh.creation.box(extents=[hi[0] - lo[0] + 24, hi[1] - lo[1] + 24, 1.0])
    bed.apply_translation([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, -0.55])
    bed.visual = material("#3A3B3D")  # the printer bed, also makes the renderer honour the colours
    scene.add_geometry(bed, node_name="bed")
    (out / "zakaz.txt").write_text(TEXT.format(items="\n\n".join(items)), encoding="utf-8")

    from .preview import Z_UP_TO_Y_UP
    scene.apply_transform(Z_UP_TO_Y_UP)
    glb = P.BUILD / "colors" / f"order_plate_{os.getpid()}.glb"  # fresh path: the engine keeps appearance per path
    scene.export(glb)
    subprocess.run(["cadgen", "+0.8.4", "snapshot", str(glb), str(out / "na_stole.png"), "--camera=iso"],
                   check=True, capture_output=True)
    glb.unlink()

    # made by colors.scheme_views for the chosen scheme; the print shop reads Russian
    sheet = next((f for f in (P.BUILD / "colors" / "D_frosted_views.ru.png", P.BUILD / "colors" / "D_frosted_views.png")
                  if f.exists()), None)
    if sheet:
        shutil.copy(sheet, out / "cveta.png")

    with zipfile.ZipFile(P.BUILD / "mx_case_order.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            z.write(f, f.name)
    print(out)
    print(P.BUILD / "mx_case_order.zip", f"{(P.BUILD / 'mx_case_order.zip').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    build()

# MX Anywhere 3 case — printing and assembly

**English** · [Русский](PRINTING.ru.md)

## Print files

`.venv/bin/python -m case.build print` writes them to `build/print/`:

| File | What it is |
| --- | --- |
| `mx_case_plate.3mf` | both parts on one plate, already in print orientation |
| `mx_case_base.stl` | the base, in print orientation |
| `mx_case_lid.stl` | the lid, in print orientation |

The bumper map comes from `.venv/bin/python -m case.bumper_map`: `build/print/bumper_map.png` (Russian version: `bumper_map.ru.png`).

## Ordering a print

`.venv/bin/python -m case.order` builds `build/mx_case_order.zip`, ready to send to a print shop:

| In the zip | What it is |
| --- | --- |
| `mx_case_base_PETG_gray.stl` | the base — **grey PETG** |
| `mx_case_lid_PETG_white-transparent.stl` | the lid — **translucent white PETG** |
| `zakaz.txt` | the order text: colours, orientation on the bed, supports, settings (in Russian) |
| `na_stole.png`, `cveta.png` | the parts as they lie on the bed, and the finished case |

The colours are set in `case/params.py` (`PRINT_COLORS`). An STL has no colour, so it goes into the file name and the order text. Parts in different colours are printed as separate jobs.

## Print settings

- **Material:** PETG.
- **Printer:** anything with a 220 × 220 mm bed or larger; both parts fit on one plate.
- **Nozzle / layer:** 0.4 mm / 0.2 mm.
- **Walls:** 3 perimeters, 100 % infill — the parts are thin, so they are practically solid anyway.
- **Base:** flat bottom on the bed. **No supports.**
- **Lid:** flat rim (the parting plane) on the bed, dome up. **Tree supports from the build plate only** — they grow inside the dome and hold the lattice ribs from below. There must be no supports on the outside of the lid.
- **Hinge holes** have a teardrop top and print without supports.
- Do not change the orientation: the files already have the right one.

## What to buy

| What | How many |
| --- | --- |
| Neodymium disc magnets 6 × 2 mm | 4 |
| Rod or screw Ø 3 mm, 40 mm long (M3 × 40 screw, steel rod or knitting needle) | 1 |
| Self-adhesive silicone bumpers Ø 6 × 2 mm | 12 |
| Bumper Ø 4–5 × 2 mm (or a piece of one) for the nose in front of the wheel | 1 |
| Glue: cyanoacrylate (super glue) or epoxy | for the magnets |

## Assembly

1. **Magnets.** There is a Ø 6.2 mm pocket in each back corner of the lid and of the base. Stack all 4 magnets in one column and mark the top face of each. Glue them into the base **marked face out** (towards the parting line) and into the lid **marked face into the pocket** (towards its bottom). Check that the lid pulls shut before the glue sets.
2. **Hinge.** Line up the knuckles of the lid and the base and push the rod through: it is a press fit in the base knuckles (Ø 3.0) and turns freely in the lid knuckles (Ø 3.25). If it is too tight, run a 3.2–3.3 mm drill through the lid holes.
3. **Bumpers** — following the map below: 8 in the base, 5 in the lid. Each one goes on a thickened lattice node or on solid wall, right at its number. The mouse touches the case only through them; everything else is 1.7 mm away from the mouse.

![Bumper map](docs/bumper_map.png)

## If something does not fit

Everything is in `case/params.py` and `case/lattice.py`, rebuilt with one command:

- a different rod — `PIN_HOLE_LID`, `PIN_HOLE_BASE`;
- different bumpers (height) — `GAP`, `GAP_PAD` (gap = bumper height − 0.3 mm);
- a lip that is too tight or too loose — `LIP_CLEAR`;
- different magnets — `MAG_D`, `MAG_DEPTH`.

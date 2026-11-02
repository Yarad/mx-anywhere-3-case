# Parameters of a mouse case

Every parameter the skill could offer, where it lives and its default. The defaults are the
choices made for the Logitech MX Anywhere 3 case (`mice/mx-anywhere-3/`).

Config files: `mice/<mouse>/case.toml` (the mouse and the choices) over `case/defaults.toml`
(everything else); `mice/<mouse>/derived.toml` is computed by `fit`.

Levels:
- **ask**: the skill asks about it, with a picture of the choices.
- **intake**: asked while taking the mouse in, because it changes how the mouse is set up.
- **default**: not asked; mention it once in the summary, change only if the person brings it up.
- **technical**: never offered; change only on an explicit request, and say what it risks.
- **derived**: computed from the mouse; adjust only to fix a problem `build` reports.
- **planned**: offered in the original design session but not built yet. Mention as "not
  available yet" if the person asks for something like it.

## The mouse (intake)

| Parameter | Where | Default | Notes |
| --- | --- | --- | --- |
| Scan | `new --scan FILE` | — | STL/OBJ/PLY/3MF, any units (guessed: mm, cm, m, in). Best input. |
| Dimensions | `new --dims L W H` | — | Without a scan: length, width, height in mm. Builds a smooth stand-in; bumpers get 3 mm thick to take up the difference. |
| Shape knobs | `--hump --widest --nose-width --back-width --nose-height --back-height` | 0.63, 0.65, 0.78, 0.72, 0.25, 0.58 | Only with `--dims`; fractions of length / width / height. Ask only if the person can describe the shape ("hump far back", "narrow nose"). |
| Orientation | `--front --up` | automatic | Axis of the scan pointing to the mouse's front, and up. Automatic: longest side = length, flattest face = bottom, front = end farther from the hump. Confirm on `orientation.png`. |
| Side buttons | `--side-buttons left/right/none` | none (MX3: left) | As the person holds the mouse. Adds a 2.5 mm clearance zone. |
| Fixed strip | `--strip` | off (MX3: on) | A non-moving strip between the main buttons the case may rest on (adds two top contacts). |
| Button zones | `[mouse] buttons` | proposed | Boxes the case keeps clear of, with their gap. Check on `features.png`. |
| Contacts | `[mouse] contacts` | proposed (11, MX3: 13) | Rays to points the case rests on: back of the top, under the feet, sides, front. Check on `features.png`. |

## Design (ask)

| # | Parameter | Key in `[design]` | Choices | Default | Picture |
| --- | --- | --- | --- | --- | --- |
| 1 | Lattice | `lattice` | `voronoi` · `none` (plain shell) | `voronoi` | `options lattice` |
| 2 | Where it stays solid | `composition` | `heel` (solid back and bottom, opening diagonally to the nose and top) · `bone` (solid only at hinge, magnets, contacts, rim) · `tail` (solid back) · `bottom` (solid bottom) · `belt` (wide band along the parting line) | `heel` | `options composition` |
| 3 | Cell size | `cell_open`, `cell_fine` | mm; e.g. 11 → 5, 8 → 5, 14 → 6 | 11 → 5 | `options cells` |
| 4 | Where cells get fine | `fine_near` | `hinge` · `buttons` · `none` | `hinge` | `options fine_near` |
| 5 | Rib cross-section | `rib` | `wedge` (narrows inward, 80 % weight) · `octagon` (full, 100 %) · `keel` (thin web, 71 %) | `wedge` | `options rib` |
| 6 | Rib width outside | `rib_width` | mm | 3.6 | — |
| 7 | Outer form | `form` | `symmetric` · `follow` (each side follows its side of an asymmetric mouse) | `symmetric` (intake picks `follow` when the mouse is > 1.5 mm asymmetric) | `options form` |
| 8 | Parting line | `parting` | `tilted` (through the widest points of nose and back) · `horizontal` | `tilted` | `options parting` |
| 9 | Overlap at the parting line | `lip` | `inner` (lip on the base inside a groove of the lid, back third) · `none` | `inner` | `options lip` |
| 10 | Hinge end | `hinge` (intake: `--hinge`) | `front` · `back`; magnets at the other end | `front` | `options hinge` |
| 11 | How the mouse rests | `contacts` | `nodes` (lattice nodes thicken under the bumpers) · `pads` (round full-thickness pads) | `nodes` | `options contacts` |
| 12 | Clearance over buttons | `gap` of each zone in `[mouse] buttons` | mm | 3.0 on top, 2.5 on the sides | `features.png` |
| 13 | Colours | `colors = { lid, base }` | names in `case/colors.py` `PALETTE`: white, white-transparent, gray, gray-metallic, black, red, orange, yellow, blue, purple, burgundy, bronze | lid `white-transparent`, base `gray` | `options colors` |

Changing `hinge` after intake: run `new` again with `--hinge back --force` (the mouse is turned
round), then `fit`. Changing `form` or `parting`: run `fit` again. The rest only needs `build`.

## Bought parts, material, printing (default)

| Parameter | Where | Default | Notes |
| --- | --- | --- | --- |
| Material | `[parts] material` | PETG | PETG · PLA (softens at 50–55 °C, e.g. in a hot car) · ABS / ASA (warp on thin lattice). |
| Hinge rod | `[parts] rod` | 3.0 mm | M3 × 40 screw, steel rod or knitting needle; 1.75 for a piece of filament (wears faster). Holes: lid rod + 0.25, base = rod. |
| Magnets | `[parts] magnet` | 6 × 2 mm, 2 pairs | The most common size in 3D printing (Gridfinity). Pockets 0.2 wider, 0.1 deeper; glued in after printing. |
| Bumpers | `[parts] bumper` | Ø 6 × 2 mm, self-adhesive | Height sets the gap: gap = height − 0.3. Silicone holds the mouse firmly; felt lets it slide in and out more easily. 3 mm for a stand-in from dimensions. |
| Order language | `[print] order_language` | `ru` for the MX3, `en` for new mice | Text and file names of the print-shop zip. |
| Print settings | `PRINTING.md` | PETG, 0.4 nozzle, 0.2 layer, 3 walls, 100 % | Base bottom down without supports; lid rim down with tree supports from the bed only. |

## Technical (only on request)

In `[tech]` of `case/defaults.toml`, overridable per mouse:
`voxel` 0.3 / `voxel_print` 0.2 (grid), `bumper_squeeze` 0.3, `rod_play` 0.25, `max_wall` 4.5,
`rim_band` 6, lip `lip_h` 2.5 × `lip_t` 1.4 with `lip_clear` 0.2 and `lip_chamfer` 0.6,
`lip_magnet_keepout` 5, knuckles `knuckle_r` 3.5, `knuckle_n` 5, `knuckle_gap` 0.4,
`knuckle_clear` 0.4, `knuckle_leaf` 5, `open_sweep_deg` 120, `lid_sweep_deg` 50,
`lid_sweep_step` 2.5, `magnet_skin` 0.4, ribs `rib_chamfer` 0.8, `rib_inner_chamfer` 0.5,
`rib_min_face` 1.0, `max_depth` 8, `skin_solid` 3, `node_fat` 1.3, cells `fine_reach` 52,
`fine_curve` 0.8.

`[fit]`: `wall` 2.0 (least material over the cavity), `front` 5.5, `back` 6.5, `floor` 4.0.

## Derived (fit)

In `derived.toml`: the outer form (`plan`, `plan_left` for `follow`, `profile_lower`,
`profile_upper`, `section`), `part_z0` + `part_slope` (parting plane), `hinge_y`,
`knuckle_span`, `lip_front_y`, `magnet_x`, `magnet_y`, `magnet_pick`, `grid_min`, `grid_max`.
The MX3's form was drawn by hand; `fit` reproduces it within about a millimetre.

## Planned (not built yet)

From the original design session; say so if asked, and offer the nearest built choice.

- Lattice patterns: hexagons, octagons with squares, triangles with curved edges, flow lines
  (nearest: `voronoi`).
- Compositions: frame with a solid spine, solid islands only at the contacts, a diagonal band
  (nearest: `bone`, `heel`).
- Overlap: a skirt of the lid outside the base, tongue and groove (nearest: `inner`).
- Hinge: snap-fit on cones (nearest: printed knuckles with a rod; a filament rod is `rod = 1.75`).
- Magnets: three pairs sealed inside with a print pause (nearest: two glued pairs).
- Parting line following the mouse's widest contour (not printable flat; nearest: `tilted`).
- Two colours within one part, solid areas and lattice (needs a multi-material printer).
- Buttons sitting inside a cell opening instead of under a rib (rejected: things poke through).

---
name: mouse-case
description: Design a 3D-printable hard carry case for any computer mouse (Voronoi lattice, printed hinge, magnets, bumpers) from a 3D scan or just its dimensions, then build print files and a print-shop order. Use when someone wants a case, cover or travel box for their mouse, wants to change the design of a case in mice/, or wants print files or an order for one.
---

# Mouse case

This repository builds a lattice carry case around a mouse so nothing presses its buttons in a
backpack: a lid and a base printed separately, a printed hinge on a rod, two pairs of magnets,
a Voronoi lattice that dissolves into solid areas, and self-adhesive bumpers on lattice nodes
as the only contact with the mouse. The code is in `case/`; each mouse has a folder in `mice/`.
`mice/mx-anywhere-3/` is the worked example and the source of every default.

Talk to the person in their language. Commands below run from the repository root.

## The rules

- **A picture for every choice.** Before asking about a design parameter, make its sheet with
  `python -m case <mouse> options <parameter>` and show it (open the PNG, or use an inline
  viewer if the session has one). Choices are lettered A, B, C on the sheet; use the same
  letters in the question. Never ask someone to pick from text alone.
- **Ask in rounds**, numbered, each question with your recommendation (the default unless the
  mouse suggests otherwise), worded so "yes" accepts it. Ask only the parameters marked *ask*
  and *intake* in [references/parameters.md](references/parameters.md). Bought parts and
  material keep their defaults unless the person raises them; technical ones only on request.
- **Facts are your job.** Measure the mouse, read the build report, look at the pictures
  yourself before showing them. Decisions are the person's.
- **Show the work stage by stage**: intake pictures, then the stage 2 case, then print files.
- **Never commit a third-party scan.** `mice/*/mouse.stl` is git-ignored. Commit it only if the
  person says the scan is theirs or its licence allows it.

## Setup (once)

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

`cadgen` (from text-to-cad) is optional: it renders the colour sheet and the bed picture of the
order; without it the order uses the built-in renderer.

## 1. Take the mouse in

Ask for: a name for the folder (`logitech-m720`), the scan **or** length × width × height in
mm, whether it has thumb buttons and on which side as they hold it, whether the top has a fixed
strip between the main buttons, and which end should hold the hinge (front by default).

```bash
.venv/bin/python -m case <mouse> new --scan path/to/scan.stl --name "Logitech M720" --side-buttons left
.venv/bin/python -m case <mouse> new --dims 107 59 26.5 --name "Logitech Pebble" --hump 0.55
```

`new` brings the mouse into the case frame (front at −Y, top at +Z, the user's left at +X, feet
on z = 0), proposes button zones and contacts, writes `mice/<mouse>/case.toml`, fits
`derived.toml` and draws `build/<mouse>/intake/`:

- `orientation.png` — is the front at the bottom of the top view, and the top up? If not, run
  `new` again with `--front` and `--up` (`+x`, `-y`, …: the scan's axis that points to the
  mouse's front, and up) and `--force`.
- `features.png` — red boxes the case keeps clear of (buttons), green dots where it rests.
  Move or add them in `case.toml` (`buttons`, `contacts`) to match the real mouse: no contact
  on a button, every foot under a bottom contact. Then `fit` and `intake` again.
- `form.png` — the outer form over the mouse. It should hold the mouse with a calm outline.

Show the three pictures and confirm them before designing. For a stand-in from dimensions, say
plainly that the fit is approximate and the bumpers are 3 mm to take up the difference.

## 2. Design

One round of questions, each with its sheet, in this order: lattice, composition, cell size,
where cells get fine, rib cross-section, how the mouse rests (nodes or pads), overlap (lip),
parting line, form (only if the mouse is asymmetric), clearance over buttons, finger notch,
colours. The hinge end was settled at intake. Built sheets (lattice, composition, cells, fine_near, contacts)
take about half a minute per choice; run them in the background and ask the diagram questions
meanwhile.

```bash
.venv/bin/python -m case <mouse> options composition
```

Write the answers into `[design]` of `case.toml`. If `form` or `parting` changed, run
`.venv/bin/python -m case <mouse> fit` and show `form.png` again; for `hinge`, run `new` again
with `--hinge … --force` (keep the answers: put them back into `[design]`).

## 3. Build and check

```bash
.venv/bin/python -m case <mouse> build stage2
```

Read the log yourself. A good build says `touches mouse 0.00 mm3` for both parts,
`lid/base overlap` about 0, every opening angle `0.00`, and magnet `room` at least the `need`.
Show the case: `build/<mouse>/stage2/preview_closed.glb` and `preview_open.glb` in a 3D viewer,
or pictures from `case.render.shade`. When it is wrong:

| Report | Fix |
| --- | --- |
| touches mouse > 0 | a contact or zone is off: check `features.png`, then `fit` |
| magnet room < need | raise `[fit] back` (or `wall`) in `case.toml`, then `fit` |
| opening overlap > 0 | raise `[tech] knuckle_clear` or move `[fit] front` out, then `fit` |
| `fit` says the form leaves too little wall | look at `form.png`; raise `[fit] wall` or the tip offsets |
| a contact ray misses the mouse | move that contact's `at` onto the mouse |

The lattice layout is kept in `mice/<mouse>/seeds.npy` once built; delete it to roll another
pattern. It is made again by itself when the cells, contacts or form change.

## 4. Print

```bash
.venv/bin/python -m case <mouse> build print     # build/<mouse>/print: STLs in print orientation, 3MF plate
.venv/bin/python -m case <mouse> checks          # thin walls, overhangs
.venv/bin/python -m case <mouse> bumper_map      # where the bumpers go, English and Russian
.venv/bin/python -m case <mouse> order           # zip for a print shop: STLs named with colours, order text
```

Tell the person what to buy: 4 magnets (`[parts] magnet`), the rod (`rod`, 40 mm long),
bumpers (`bumper`, one per contact), glue; and how to print it (see `PRINTING.md`). Optional:
`python -m case <mouse> preview github` writes small STLs to `mice/<mouse>/3d/` that GitHub
shows in 3D.

## 5. Keep it

Offer to commit `mice/<mouse>/` (`case.toml`, `derived.toml`, `seeds.npy`, `3d/`) — not the
scan unless allowed. Commit or push only when asked.

## Reference

- [references/parameters.md](references/parameters.md): every parameter, its level, choices and default.
- `case/defaults.toml`: all defaults with comments; `mice/mx-anywhere-3/case.toml`: a complete example.
- `python -m case --help`: the commands.

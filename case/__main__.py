"""Run a command for one mouse:  .venv/bin/python -m case <mouse> <command> [args]

  new       start a case for a new mouse from a scan or from its dimensions (see intake.py)
  fit       fit the outer form and the rest of derived.toml to the mouse
  intake    pictures of the mouse with its buttons, contacts and the fitted form
  options   pictures of the choices for one design parameter
  build     build the case: stage1 | stage2 | print
  checks    thin walls and overhangs of the print files
  bumper_map, order, preview, colors, review   as in the README

<mouse> is a folder in mice/. `python -m case list` shows them.
"""
import os
import runpy
import sys
from pathlib import Path

COMMANDS = {"new": "intake", "fit": "fit", "intake": "intake", "options": "options", "build": "build",
            "checks": "checks", "bumper_map": "bumper_map", "order": "order", "preview": "preview",
            "colors": "colors", "review": "review"}

mice = Path(__file__).resolve().parent.parent / "mice"
args = sys.argv[1:]
if not args or args[0] in ("-h", "--help"):
    print(__doc__)
    sys.exit(0)
if args[0] == "list":
    for d in sorted(p for p in mice.iterdir() if (p / "case.toml").exists()):
        print(d.name)
    sys.exit(0)
if len(args) < 2 or args[1] not in COMMANDS:
    sys.exit(f"usage: python -m case <mouse> <{'|'.join(COMMANDS)}> [args]")
mouse, command = args[0], args[1]
os.environ["MOUSE_CASE"] = mouse
if command == "new":  # intake creates the folder; the other commands need it
    sys.argv = ["case.intake", "new", mouse] + args[2:]
elif command == "intake":
    sys.argv = ["case.intake", "pictures", mouse] + args[2:]
else:
    sys.argv = [f"case.{COMMANDS[command]}"] + args[2:]
runpy.run_module(f"case.{COMMANDS[command]}", run_name="__main__", alter_sys=True)

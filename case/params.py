"""Parameters of a carry case, read from the mouse's folder:

  mice/<mouse>/case.toml     the mouse (mesh, buttons, contacts) and the design choices
  mice/<mouse>/derived.toml  geometry computed from the mouse (`python -m case <mouse> fit`)
  case/defaults.toml         everything not set in case.toml

The mouse is picked by the MOUSE_CASE environment variable; `python -m case <mouse> ...`
sets it. All lengths are millimetres in the case frame: front of the mouse at -Y, top
at +Z, the user's left (thumb side of a right-handed mouse) at +X, the table the feet
stand on at z = TABLE_Z.
"""
import json
import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MICE = ROOT / "mice"
MOUSE = os.environ.get("MOUSE_CASE", "mx-anywhere-3")
DIR = MICE / MOUSE
BUILD = ROOT / "build" / MOUSE
CACHE = ROOT / "build" / "cache"
SEEDS_FILE = DIR / "seeds.npy"  # the approved lattice layout; delete to re-roll


def merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(path):
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


if not (DIR / "case.toml").exists():
    raise SystemExit(f"no mouse '{MOUSE}': {DIR / 'case.toml'} is missing (python -m case new ...)")
CONFIG = merge(load(ROOT / "case" / "defaults.toml"), load(DIR / "case.toml"))
if os.environ.get("CASE_DESIGN"):  # one-off design changes, as JSON: how option sheets try the choices
    CONFIG = merge(CONFIG, {"design": json.loads(os.environ["CASE_DESIGN"])})
DERIVED = load(DIR / "derived.toml")
_m, _d, _p, _t = CONFIG["mouse"], CONFIG["design"], CONFIG["parts"], CONFIG["tech"]

# --- the mouse ---------------------------------------------------------------------
NAME = _m["name"]
SCAN = ROOT / _m["mesh"]
TABLE_Z = _m.get("table_z", 0.0)
BUTTONS = _m.get("buttons", [])
CONTACT_INFO = {c["name"]: c for c in _m.get("contacts", [])}


def _contact(c):
    """(name, ray, a, b, c, landing radius) as fields.contact_points reads it."""
    a, b = c["at"]
    if c["ray"] in ("top", "bottom"):
        return c["name"], c["ray"], a, b, None, c["r"]
    if c["ray"] == "side":
        return c["name"], "side", float(c["side"]), a, b, c["r"]
    return c["name"], c["ray"], a, None, b, c["r"]  # front / back: at = [x, z]


CONTACTS = [_contact(c) for c in _m.get("contacts", [])]
if not SCAN.exists() and _m.get("source") == "dimensions":  # a stand-in is rebuilt, not kept in git
    from .intake import stand_in
    stand_in(_m["dimensions"], CONFIG["design"]["hinge"]).export(SCAN)

# --- design ------------------------------------------------------------------------
LATTICE = _d["lattice"]
COMPOSITION = _d["composition"]
CELL_OPEN = _d["cell_open"]
CELL_FINE = _d["cell_fine"]
FINE_NEAR = _d["fine_near"]
RIB = _d["rib"]
RIB_W = _d["rib_width"]
FORM_STYLE = _d["form"]
PARTING = _d["parting"]
LIP = _d["lip"]
HINGE_END = _d["hinge"]
CONTACT_STYLE = _d["contacts"]
PRINT_COLORS = _d["colors"]

# --- parts -------------------------------------------------------------------------
MATERIAL = _p["material"]
DENSITY = {"PETG": 1.27, "PLA": 1.24, "ABS": 1.04, "ASA": 1.07}.get(MATERIAL, 1.27)  # g/cm3
ROD = _p["rod"]
PIN_HOLE_LID = round(ROD + _t["rod_play"], 4)  # free fit: lid knuckles turn on the rod
PIN_HOLE_BASE = ROD                            # press fit: the base holds the rod
MAGNET = _p["magnet"]
MAG_D = round(MAGNET[0] + 0.2, 4)
MAG_DEPTH = round(MAGNET[1] + 0.1, 4)
BUMPER = _p["bumper"]
GAP = round(BUMPER[1] - _t["bumper_squeeze"], 4)  # the mouse touches only the bumpers
GAP_PAD = GAP                                       # at contacts inside button zones
ORDER_LANGUAGE = CONFIG["print"]["order_language"]

# --- technical ---------------------------------------------------------------------
VOXEL = _t["voxel"]
VOXEL_PRINT = _t["voxel_print"]
MAX_WALL = _t["max_wall"]
RIM_BAND = _t["rim_band"]
LIP_H, LIP_T, LIP_CLEAR, LIP_CHAMFER = _t["lip_h"], _t["lip_t"], _t["lip_clear"], _t["lip_chamfer"]
LIP_MAGNET_KEEPOUT = _t["lip_magnet_keepout"]
KNUCKLE_R = _t["knuckle_r"]
KNUCKLE_N = _t["knuckle_n"]
KNUCKLE_GAP = _t["knuckle_gap"]
KNUCKLE_CLEAR = _t["knuckle_clear"]
KNUCKLE_LEAF = _t["knuckle_leaf"]
OPEN_SWEEP_DEG = _t["open_sweep_deg"]
LID_SWEEP_DEG = _t["lid_sweep_deg"]
LID_SWEEP_STEP = _t["lid_sweep_step"]
MAG_SKIN = _t["magnet_skin"]
RIB_CHAMFER = _t["rib_chamfer"]
RIB_INNER_CHAMFER = _t["rib_inner_chamfer"]
RIB_MIN_FACE = _t["rib_min_face"]
MAX_DEPTH_OPEN = _t["max_depth"]
SKIN_SOLID = _t["skin_solid"]
NODE_FAT = _t["node_fat"]
FINE_REACH = _t["fine_reach"]
FINE_CURVE = _t["fine_curve"]
FIT = CONFIG["fit"]

# --- derived from the mouse ----------------------------------------------------------
if DERIVED:
    GRID_MIN = tuple(DERIVED["grid_min"])
    GRID_MAX = tuple(DERIVED["grid_max"])
    PART_Z0 = DERIVED["part_z0"]
    PART_SLOPE = DERIVED["part_slope"]
    HINGE_Y = DERIVED["hinge_y"]
    KNUCKLE_SPAN = DERIVED["knuckle_span"]
    LIP_FRONT_Y = DERIVED["lip_front_y"]
    MAGNET_X = DERIVED["magnet_x"]
    MAGNET_Y = DERIVED["magnet_y"]
    MAGNET_PICK = DERIVED.get("magnet_pick", "back")  # back: furthest back spot that fits; room: most room
    FORM = DERIVED["form"]
else:  # a new mouse before `fit`: only intake and fit may run
    FORM = None

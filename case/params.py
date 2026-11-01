"""Parameters of the MX Anywhere 3 carry case.

All lengths are millimetres in the frame of the mouse scan: front of the mouse
(USB-C, wheel) at -Y, left side with the side buttons at +X, the table plane the
feet stand on at z = TABLE_Z.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = ROOT / "Logitech MX Anywhere 3.stl"
BUILD = ROOT / "build"
CACHE = BUILD / "cache"
SEEDS_FILE = ROOT / "case" / "approved_seeds.npy"  # delete to re-roll the lattice

TABLE_Z = -0.57

# --- SDF grid -----------------------------------------------------------------
VOXEL = 0.3
VOXEL_PRINT = 0.2
GRID_MIN = (-41.0, -62.0, -7.0)
GRID_MAX = (41.0, 61.0, 42.5)

# --- gaps between the mouse and the case ----------------------------------------
GAP = 1.7            # default: the mouse touches only the 2 mm bumpers (0.3 mm squeeze)
GAP_BUTTONS = 3.0    # over wheel, SmartShift, left/right buttons
GAP_SIDE_BUTTONS = 2.5  # side buttons: pressed sideways, stiff wall right next to them
GAP_PAD = 1.7        # at contacts inside button zones (strip, nose): back to the bumper gap
MAX_WALL = 4.5       # stage 1: wall is capped this far in from the outer surface
RIM_BAND = 6.0       # full wall thickness this far either side of the parting plane

# --- parting plane z = PART_Z0 + PART_SLOPE * y ----------------------------------
PART_Z0 = 14.0
PART_SLOPE = 0.12

# --- lip on the base, along the sides and the back -------------------------------
LIP_H = 2.5
LIP_T = 1.4
LIP_CLEAR = 0.2
LIP_CHAMFER = 0.6
LIP_FRONT_Y = 22.0   # lip only around the back third: the walls along the sides are too thin
                     # for lip + groove + skirt; the hinge keeps the front aligned
LIP_MAGNET_KEEPOUT = 5.0

# --- hinge -----------------------------------------------------------------------
PIN_HOLE_LID = 3.25   # free fit: lid knuckles turn on the rod
PIN_HOLE_BASE = 3.0   # press fit: the base holds the rod
KNUCKLE_R = 3.5
KNUCKLE_SPAN = 40.0   # total length along x
KNUCKLE_N = 5         # odd knuckles (1, 3, 5) belong to the base, even to the lid
KNUCKLE_GAP = 0.4
KNUCKLE_CLEAR = 0.4
KNUCKLE_LEAF = 5.0    # how far the knuckle's web reaches back into the wall
HINGE_Y = -54.5
OPEN_SWEEP_DEG = 120  # base is cleared for the lid knuckles up to this angle
LID_SWEEP_DEG = 50    # lid cavity is swept around the mouse up to this angle
LID_SWEEP_STEP = 2.5

# --- magnets 6 x 2 mm in open, glued pockets ---------------------------------------
MAG_D = 6.2
MAG_DEPTH = 2.1
MAG_SKIN = 0.4  # one 0.4 mm extrusion line around the pocket

# --- contact points ----------------------------------------------------------------
# (name, how the point is found, x, y, z, pad radius)
#   top    : ray straight down at (x, y)
#   bottom : under a foot at (x, y) on the table plane
#   side   : ray from the side at (y, z), x gives the side (+1 / -1)
#   front  : ray from the front at (x, z)
CONTACTS = [
    ("nose",    "top",    0.0, -41.2, None, 2.5),
    ("strip",   "top",    0.0,   4.0, None, 4.5),
    ("back_l",  "top",  -17.0,  30.0, None, 4.5),
    ("back_r",  "top",   17.0,  30.0, None, 4.5),
    ("back_c",  "top",    0.0,  40.0, None, 4.5),
    ("foot_fl", "bottom", -14.0, -35.0, None, 4.5),
    ("foot_fr", "bottom",  14.0, -35.0, None, 4.5),
    ("foot_bl", "bottom", -16.5,  27.0, None, 4.5),
    ("foot_br", "bottom",  16.5,  27.0, None, 4.5),
    ("side_l",  "side",   -1.0,  15.0, 4.0, 4.0),
    ("side_r",  "side",    1.0,  15.0, 4.0, 4.0),
    ("front_l", "front", -14.0, None, 4.0, 3.0),
    ("front_r", "front",  14.0, None, 4.0, 3.0),
]

PETG_DENSITY = 1.27  # g/cm3

# chosen PETG colours from 3D Pixel's palette: (name for the order, name for file names)
PRINT_COLORS = {
    "base": ("серый", "gray"),
    "lid": ("белый прозрачный", "white-transparent"),
}

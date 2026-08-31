"""Colors, fonts and formatting helpers. One place to restyle the whole app."""

import sys

# ---- palette: deep space + neon -------------------------------------------
VOID      = "#07070f"   # window background
DEEP      = "#0d0d1a"   # panel background
SURFACE   = "#15152a"   # card background
SURFACE_2 = "#1c1c38"   # card hover / raised
STROKE    = "#2a2a4d"   # borders
STROKE_HI = "#3d3d70"

TEXT      = "#e6e9ff"
MUTED     = "#8a8ab5"
FAINT     = "#5a5a85"

CYAN      = "#22e3ff"
MAGENTA   = "#ff2d9b"
LIME      = "#9dff3c"
GOLD      = "#ffc93c"
VIOLET    = "#8b5cff"
RED       = "#ff4d6d"

UP        = LIME
DOWN      = RED

# rank medals
MEDALS = {1: GOLD, 2: "#cfd8ff", 3: "#ff9a4d"}

# risk tiers -> color
TIER_COLOR = {"SAFE": CYAN, "BALANCED": VIOLET, "DEGEN": MAGENTA}


# ---- fonts ----------------------------------------------------------------
def _pick(*names):
    """First font family that exists is chosen at runtime by Tk anyway;
    we just order them per platform."""
    return names[0]


if sys.platform == "darwin":
    DISPLAY = "Helvetica Neue"
    BODY = "Helvetica Neue"
    NUMS = "SF Mono"
elif sys.platform.startswith("win"):
    DISPLAY = "Segoe UI"
    BODY = "Segoe UI"
    NUMS = "Consolas"
else:
    DISPLAY = "DejaVu Sans"
    BODY = "DejaVu Sans"
    NUMS = "DejaVu Sans Mono"


def display(size, weight="bold"):
    return (DISPLAY, size, weight)


def body(size, weight="normal"):
    return (BODY, size, weight)


def nums(size, weight="normal"):
    return (NUMS, size, weight)


# ---- number formatting ----------------------------------------------------
def money(value, decimals=2):
    """1234567.8 -> '1,234,567.80'"""
    return ("{:,.%df}" % decimals).format(value)


def compact(value):
    """1234567 -> '1.23M' — for tight spaces."""
    sign = "-" if value < 0 else ""
    a = abs(value)
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return "%s%.2f%s" % (sign, a / div, suffix)
    return "%s%.0f" % (sign, a)


def signed(value, decimals=1, suffix=""):
    return "%s%s%s" % ("+" if value >= 0 else "", money(value, decimals), suffix)


def short_addr(addr, head=6, tail=4):
    return addr if len(addr) <= head + tail + 3 else addr[:head] + "…" + addr[-tail:]


def pnl_color(value):
    return UP if value >= 0 else DOWN

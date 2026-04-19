"""
sparkview/layers/power_rails.py
GB10 power rail monitor via SPBM hwmon (antheas/spark_hwmon kernel module).
Hidden on non-GB10 systems — no SPBM hwmon device present.

Confirmed from spbm.c source (github.com/antheas/spark_hwmon):

  Power channels — standard hwmon power*_label (under hwmon dir):
    "gpu"      line 70  SPBM_TE_TOTAL_GPU_OUT_OFFSET
    "dc_input" line 69  SPBM_TE_CHR_TELEMETRY_OFFSET
    "syspl1"   line 76  SPBM_PWR_AVG_EWMA_S_SYSPL1_OFFSET  (cap r/w)
    "prereg"   line 71  SPBM_TE_PREREG_IN_OFFSET

  Status channels — device_attribute (line 662: sa->dev_attr.attr.name)
  Registered on the ACPI device, NOT under hwmon dir:
    "prochot"  line 105  SPBM_PROCHOT_STATUS_OFFSET
    "pl_level" line 106  SPBM_PL_CUR_LEVEL_STATUS_OFFSET
    "tj_max_c" line 107  SPBM_PKG_TJ_MAX_C_OFFSET  (decidegrees ÷10 → °C)

  ACPI device path: /sys/bus/platform/devices/NVDA8800:00/

Units:
  power*_input  µW  → scale 1e-6 → W
  power*_cap    µW  → scale 1e-6 → W
  tj_max_c      decidegrees → scale 0.1 → °C
  prochot       0/1
  pl_level      int
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from typing import Optional

from rich.text import Text

# ── ACPI device path for status attributes ────────────────────────────────────
_ACPI_DEVICE = "/sys/bus/platform/devices/NVDA8800:00"


# ── Detection ────────────────────────────────────────────────────────────────

def _find_spbm_hwmon() -> Optional[str]:
    """Return hwmon sysfs dir for the spbm device, or None."""
    for name_path in glob.glob("/sys/class/hwmon/hwmon*/name"):
        try:
            if open(name_path).read().strip().startswith("spbm"):
                return os.path.dirname(name_path)
        except OSError:
            continue
    return None


def is_available() -> bool:
    return _find_spbm_hwmon() is not None


# ── Sysfs primitives ──────────────────────────────────────────────────────────

def _read_float(path: str, scale: float = 1.0) -> Optional[float]:
    try:
        return float(open(path).read().strip()) * scale
    except (OSError, ValueError):
        return None


def _read_int(path: str) -> Optional[int]:
    try:
        return int(open(path).read().strip())
    except (OSError, ValueError):
        return None


# ── hwmon power channel lookup ────────────────────────────────────────────────

def _find_power_channel(hwmon: str, label: str, suffix: str) -> Optional[str]:
    """
    Find powerM_<suffix> where powerM_label == label.
    Exact label strings from spbm.c — no guessing.
    """
    for lp in glob.glob(os.path.join(hwmon, "power*_label")):
        try:
            if open(lp).read().strip() == label:
                p = lp[: -len("_label")] + f"_{suffix}"
                return p if os.path.exists(p) else None
        except OSError:
            continue
    return None


# ── Peak tracker (session memory) ────────────────────────────────────────────

_peak_gpu_w: float = 0.0


def _update_peak(gpu_w: Optional[float]) -> None:
    global _peak_gpu_w
    if gpu_w is not None and gpu_w > _peak_gpu_w:
        _peak_gpu_w = gpu_w


# ── Data ─────────────────────────────────────────────────────────────────────

@dataclass
class PowerRailsData:
    gpu_w:        Optional[float] = None   # instantaneous GPU draw
    peak_gpu_w:   float           = 0.0    # session peak GPU draw
    dc_w:         Optional[float] = None   # DC input from brick
    syspl1_act_w: Optional[float] = None   # SysPL1 EWMA actual
    syspl1_cap_w: Optional[float] = None   # SysPL1 cap (power limit)
    cap_exceeded: bool            = False   # actual > cap
    prochot:      Optional[bool]  = None   # hardware throttle flag
    pl_level:     Optional[int]   = None   # active power limit level
    tj_rise_c:    Optional[float] = None   # thermal rise (decidegrees ÷10)


# ── Read ──────────────────────────────────────────────────────────────────────

def read() -> Optional[PowerRailsData]:
    hwmon = _find_spbm_hwmon()
    if hwmon is None:
        return None

    uW = 1e-6   # µW → W

    d = PowerRailsData()

    # ── Power channels (hwmon dir) ────────────────────────────────────────────

    # GPU instantaneous draw — "gpu" label, line 70 spbm.c
    p = _find_power_channel(hwmon, "gpu", "input")
    if p:
        d.gpu_w = _read_float(p, uW)

    # DC input from brick — "dc_input" label, line 69 spbm.c
    p = _find_power_channel(hwmon, "dc_input", "input")
    if p:
        d.dc_w = _read_float(p, uW)

    # SysPL1 actual + cap — "syspl1" label, lines 76/142 spbm.c
    p_in  = _find_power_channel(hwmon, "syspl1", "input")
    p_cap = _find_power_channel(hwmon, "syspl1", "cap")
    if p_in:
        d.syspl1_act_w = _read_float(p_in, uW)
    if p_cap:
        d.syspl1_cap_w = _read_float(p_cap, uW)

    if d.syspl1_act_w and d.syspl1_cap_w:
        d.cap_exceeded = d.syspl1_act_w > d.syspl1_cap_w

    # ── Status channels (ACPI device dir, NOT hwmon dir) ─────────────────────
    # spbm.c line 662: sa->dev_attr.attr.name = status_chans[i].label
    # Registered on NVDA8800:00 device, not on hwmon device

    p = os.path.join(_ACPI_DEVICE, "prochot")
    if os.path.exists(p):
        v = _read_int(p)
        d.prochot = bool(v) if v is not None else None

    p = os.path.join(_ACPI_DEVICE, "pl_level")
    if os.path.exists(p):
        d.pl_level = _read_int(p)

    # tj_max_c — decidegrees, ÷10 → °C. Driver note: ~40 idle = 4.0°C rise
    p = os.path.join(_ACPI_DEVICE, "tj_max_c")
    if os.path.exists(p):
        v = _read_float(p, 0.1)
        d.tj_rise_c = round(v, 1) if v is not None else None

    # ── Session peak ──────────────────────────────────────────────────────────
    _update_peak(d.gpu_w)
    d.peak_gpu_w = _peak_gpu_w

    return d


# ── Render ────────────────────────────────────────────────────────────────────

def render(grid, sep) -> bool:
    """
    Append PWR row to Rich grid.
    Returns False if SPBM device absent — hidden on non-GB10 systems.
    Only emits fields that were actually read from hardware.

    Example (healthy):
      PWR   GPU 36W  peak 47W  DC 38.8W  Cap 30W  ○  Tj+4.8°C

    Example (throttling):
      PWR   GPU 11W  peak 47W  DC 38.8W  Cap 30W  ● PROCHOT  PL1  Tj+4.8°C
    """
    d = read()
    if d is None:
        return False

    t = Text()
    t.append("PWR    ", style="bold cyan")

    # GPU instantaneous
    if d.gpu_w is not None:
        t.append(f"GPU {d.gpu_w:.0f}W  ", style="white")

    # Session peak — pzmosquito's request
    if d.peak_gpu_w > 0:
        t.append(f"peak {d.peak_gpu_w:.0f}W  ", style="white")

    # DC input
    if d.dc_w is not None:
        t.append(f"DC {d.dc_w:.1f}W  ", style="white")

    # SysPL1 cap — red when exceeded
    if d.syspl1_cap_w is not None:
        cap_style = "red bold" if d.cap_exceeded else "white"
        cap_str = f"Cap {d.syspl1_cap_w:.0f}W"
        if d.cap_exceeded and d.syspl1_act_w is not None:
            cap_str += f" ({d.syspl1_act_w:.0f}W act)"
        t.append(cap_str + "  ", style=cap_style)

    # PROCHOT — twaggs88's request
    if d.prochot is not None:
        if d.prochot:
            t.append("● PROCHOT  ", style="red bold")
        else:
            t.append("○          ", style="green dim")

    # Active PL level
    if d.pl_level is not None and d.pl_level > 0:
        t.append(f"PL{d.pl_level}  ", style="yellow")

    # Thermal rise
    if d.tj_rise_c is not None and d.tj_rise_c > 0:
        rise_style = (
            "red"    if d.tj_rise_c > 15 else
            "yellow" if d.tj_rise_c > 8  else
            "white"
        )
        t.append(f"Tj+{d.tj_rise_c}°C", style=rise_style)

    grid.add_row(t)
    sep(grid)
    return True

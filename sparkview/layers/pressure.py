"""PSI memory pressure layer for sparkview."""

from __future__ import annotations

import pathlib

PSI_PATH = pathlib.Path("/proc/pressure/memory")


def get_pressure() -> dict:
    """Read PSI memory pressure from /proc/pressure/memory."""
    result = {
        "available": False,
        "some_avg10": 0.0,
        "full_avg10": 0.0,
        "level": "LOW",
    }
    try:
        lines = PSI_PATH.read_text().strip().splitlines()
        for line in lines:
            parts = {
                k: float(v)
                for k, v in (
                    p.split("=") for p in line.split()[1:] if "=" in p and "total" not in p
                )
            }
            if line.startswith("some"):
                result["some_avg10"] = parts.get("avg10", 0.0)
            elif line.startswith("full"):
                result["full_avg10"] = parts.get("avg10", 0.0)
        result["available"] = True
        s = result["some_avg10"]
        f = result["full_avg10"]
        if f > 0.10 or s > 0.30:
            result["level"] = "CRITICAL"
        elif f > 0.05 or s > 0.15:
            result["level"] = "HIGH"
        elif s > 0.05:
            result["level"] = "MOD"
        else:
            result["level"] = "LOW"
    except Exception:  # noqa: BLE001
        pass
    return result

"""CPU layer for sparkview."""

from __future__ import annotations

import psutil


def get_cpu_info() -> dict:
    per_core = psutil.cpu_percent(interval=0.1, percpu=True)
    active = sum(1 for c in per_core if c > 0)

    cpu_temp = None
    try:
        temps = psutil.sensors_temperatures()
        for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
            if key in temps and temps[key]:
                readings = [t.current for t in temps[key]]
                cpu_temp = max(readings)
                break
    except Exception:  # noqa: BLE001
        pass

    return {
        "percent": sum(per_core) / len(per_core),
        "per_core": per_core,
        "count": psutil.cpu_count(),
        "active": active,
        "freq": psutil.cpu_freq(),
        "temperature": cpu_temp,
    }

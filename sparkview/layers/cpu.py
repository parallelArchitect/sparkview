"""CPU layer for sparkview."""

from __future__ import annotations

import psutil


def get_cpu_info() -> dict:
    """Return CPU info."""
    per_core = psutil.cpu_percent(interval=0.1, percpu=True)
    return {
        "percent": sum(per_core) / len(per_core),
        "per_core": per_core,
        "count": psutil.cpu_count(),
        "freq": psutil.cpu_freq(),
    }

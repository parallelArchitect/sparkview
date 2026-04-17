"""Memory layer for sparkview — GB10 coherent UMA aware."""

from __future__ import annotations

import psutil


def get_memory() -> dict:
    """Return memory info, UMA-aware for GB10 / DGX Spark.

    On coherent UMA platforms (GB10), MemAvailable reflects
    actually allocatable memory, not MemTotal.
    """
    vm = psutil.virtual_memory()
    return {
        "total": vm.total,
        "available": vm.available,
        "used": vm.used,
        "percent": vm.percent,
    }

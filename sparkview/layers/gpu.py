"""GPU layer for sparkview — NVML query via nvitop, GB10 UMA aware."""

from __future__ import annotations

import psutil

try:
    from nvitop import Device

    NVITOP_AVAILABLE = True
except ImportError:
    NVITOP_AVAILABLE = False

UMA_THRESHOLD = 0.9


def is_coherent_uma(device: "Device") -> bool:
    """Detect GB10-style coherent UMA."""
    try:
        mem = device.memory_info()
        vm = psutil.virtual_memory()
        if mem.total is None or vm.total == 0:
            return False
        return mem.total >= vm.total * UMA_THRESHOLD
    except Exception:  # noqa: BLE001
        return False


def get_gpu_info() -> list[dict]:
    """Return GPU info for all devices."""
    if not NVITOP_AVAILABLE:
        return []
    results = []
    for device in Device.all():
        try:
            uma = is_coherent_uma(device)
            vm = psutil.virtual_memory()
            mem = device.memory_info()
            procs = []
            for p in device.processes().values():
                try:
                    cpu = p.cpu_percent()
                    procs.append(
                        {
                            "pid": p.pid,
                            "user": p.username(),
                            "gpu_mem": p.gpu_memory(),
                            "cpu_pct": cpu,
                            "cmd": p.name(),
                        }
                    )
                except Exception:  # noqa: BLE001
                    continue
            results.append(
                {
                    "index": device.index,
                    "name": device.name(),
                    "utilization": device.gpu_utilization(),
                    "temperature": device.temperature(),
                    "power": device.power_usage(),
                    "is_uma": uma,
                    "mem_total": vm.available if uma else mem.total,
                    "mem_used": mem.used,
                    "processes": sorted(procs, key=lambda x: x["gpu_mem"] or 0, reverse=True),
                }
            )
        except Exception:  # noqa: BLE001
            continue
    return results

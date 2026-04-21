from __future__ import annotations

import platform
from datetime import datetime

try:
    from nvitop import Device

    NVITOP_AVAILABLE = True
except ImportError:
    NVITOP_AVAILABLE = False


def get_info() -> dict:
    info = {
        "time": datetime.now().strftime("%I:%M:%S %p"),
        "uptime": "",
        "kernel": platform.release(),
        "driver": "",
        "cuda": "",
        "gpu_name": "",
    }

    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        d, rem = divmod(int(secs), 86400)
        h, rem = divmod(rem, 3600)
        m = rem // 60
        info["uptime"] = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
    except Exception:  # noqa: BLE001
        pass

    if NVITOP_AVAILABLE:
        try:
            devices = Device.all()
            if devices:
                info["driver"] = devices[0].driver_version()
                info["cuda"] = devices[0].cuda_driver_version()
                info["gpu_name"] = devices[0].name()
        except Exception:  # noqa: BLE001
            pass

    return info

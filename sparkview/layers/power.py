"""Power layer for sparkview — reads spark_hwmon sysfs if available,
falls back to nvidia-smi power.draw if not, reports unavailable if neither works."""
from __future__ import annotations
import pathlib
import subprocess

SPBM_HWMON_PATH = pathlib.Path("/sys/class/hwmon")


def get_power_info() -> dict:
    """Return power info from spark_hwmon sysfs if installed,
    falling back to nvidia-smi power.draw on platforms where spark_hwmon
    is absent but NVML exposes power (e.g. ASUS GX10).
    Returns available=False with source='unavailable' on DGX Spark reference
    units where neither path works."""
    result = {"available": False, "power_w": None, "source": None}

    # --- Path 1: spark_hwmon sysfs ---
    try:
        for hwmon in SPBM_HWMON_PATH.iterdir():
            name_file = hwmon / "name"
            if name_file.exists() and "spbm" in name_file.read_text().strip().lower():
                power_file = hwmon / "power1_input"
                if power_file.exists():
                    microwatts = int(power_file.read_text().strip())
                    result["available"] = True
                    result["power_w"] = microwatts / 1_000_000
                    result["source"] = "spbm_hwmon"
                    return result
    except Exception:  # noqa: BLE001
        pass

    # --- Path 2: nvidia-smi power.draw fallback ---
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=power.draw",
                "--format=csv,noheader,nounits",
            ],
            timeout=2,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if out and out.lower() not in ("n/a", "[n/a]", ""):
            result["available"] = True
            result["power_w"] = float(out)
            result["source"] = "nvml"
            return result
    except Exception:  # noqa: BLE001
        pass

    # --- Neither path worked ---
    result["source"] = "unavailable"
    return result

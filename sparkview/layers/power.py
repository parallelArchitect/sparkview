"""Power layer for sparkview — reads spark_hwmon sysfs if available."""

from __future__ import annotations

import pathlib

SPBM_HWMON_PATH = pathlib.Path("/sys/class/hwmon")


def get_power_info() -> dict:
    """Return power info from sysfs hwmon if spark_hwmon is installed."""
    result = {"available": False, "power_w": None, "source": None}
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
    return result

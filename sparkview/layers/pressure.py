from __future__ import annotations

import pathlib

PSI_MEM_PATH = pathlib.Path("/proc/pressure/memory")
PSI_IO_PATH = pathlib.Path("/proc/pressure/io")


def _parse_psi(path: pathlib.Path) -> dict:
    result = {"available": False, "some_avg10": 0.0, "full_avg10": 0.0, "level": "LOW"}
    try:
        lines = path.read_text().strip().splitlines()
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


def get_pressure() -> dict:
    mem = _parse_psi(PSI_MEM_PATH)
    io = _parse_psi(PSI_IO_PATH)
    return {"mem": mem, "io": io}

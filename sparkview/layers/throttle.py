"""Throttle detection layer for sparkview.

Logic derived from spark-gpu-throttle-check v2.1.0 (parallelArchitect).
Uses nvidia-smi for clock and throttle reason data.
"""

from __future__ import annotations

import subprocess

CLOCK_THRESHOLD_MHZ = 1400.0
LOAD_GATE_PCT = 10

PROBLEM_THROTTLE_BITS: dict[int, str] = {
    0x0000000000000008: "HW_SLOWDOWN",
    0x0000000000000010: "SW_THERMAL_SLOWDOWN",
    0x0000000000000020: "HW_THERMAL_SLOWDOWN",
    0x0000000000000080: "HW_POWER_BRAKE_SLOWDOWN",
    0x0000000000000100: "SW_POWER_CAP",
}


def decode_throttle(bitmask: int) -> list[str]:
    return [name for bit, name in PROBLEM_THROTTLE_BITS.items() if bitmask & bit]


def has_problem_throttle(bitmask: int) -> bool:
    return any(bitmask & bit for bit in PROBLEM_THROTTLE_BITS)


def query_nvidia_smi() -> list[dict] | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,clocks.current.graphics,clocks.max.graphics,"
                "pstate,power.draw,clocks_throttle_reasons.active,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        gpus = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 7:
                continue

            def sf(s: str) -> float | None:
                try:
                    return float(s)
                except ValueError:
                    return None

            throttle_raw = 0
            try:
                raw = parts[5]
                throttle_raw = int(raw, 16) if raw.startswith("0x") else 0
            except (ValueError, IndexError):
                pass

            gpus.append(
                {
                    "index": int(parts[0]) if parts[0].isdigit() else 0,
                    "clk_mhz": sf(parts[1]),
                    "clk_max_mhz": sf(parts[2]),
                    "pstate": parts[3],
                    "power_w": sf(parts[4]),
                    "throttle_raw": throttle_raw,
                    "throttle_reasons": decode_throttle(throttle_raw),
                    "problem_throttle": has_problem_throttle(throttle_raw),
                    "util_pct": sf(parts[6]),
                }
            )
        return gpus if gpus else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_throttle_info(gpu_procs: list[dict] | None = None) -> list[dict]:
    """Return throttle status per GPU — four states, load-gated."""
    gpus = query_nvidia_smi()
    if not gpus:
        return []
    results = []
    for g in gpus:
        clk = g["clk_mhz"]
        clk_max = g["clk_max_mhz"]
        util = g["util_pct"] or 0
        problem = g["problem_throttle"]
        reasons = g["throttle_reasons"]
        pstate = g.get("pstate", "P0")
        if clk is None or clk_max is None:
            results.append({"index": g["index"], "available": False})
            continue
        locked = clk_max < 2900 and clk_max > 0 and abs(clk - clk_max) < 50
        if util < LOAD_GATE_PCT or pstate not in ("P0", "P1", "P2"):
            status = "IDLE"
        elif locked:
            status = "LOCKED"
        elif clk < CLOCK_THRESHOLD_MHZ or problem:
            status = "THROTTLED"
        else:
            status = "PASS"
        results.append(
            {
                "index": g["index"],
                "available": True,
                "status": status,
                "clk_mhz": clk,
                "clk_max_mhz": clk_max,
                "pstate": pstate,
                "power_w": g["power_w"],
                "util_pct": util,
                "throttle_reasons": reasons,
                "problem_throttle": problem,
                "locked": locked,
            }
        )
    return results

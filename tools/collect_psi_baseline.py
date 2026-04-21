#!/usr/bin/env python3
"""
collect_psi_baseline.py — sparkview PSI baseline collector for GB10 calibration.

Samples /proc/pressure/memory and /proc/pressure/io every second for a set
duration and saves timestamped JSON output for community calibration.

Usage:
  python3 collect_psi_baseline.py --duration 120 --label idle
  python3 collect_psi_baseline.py --duration 120 --label vllm_loaded
  python3 collect_psi_baseline.py --duration 120 --label inference_running

Output:
  ~/sparkview_logs/psi_baseline/sparkview_psi_baseline_<label>_<timestamp>.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import subprocess
import time
from datetime import datetime

# ── PSI paths ────────────────────────────────────────────────────────────────
PSI_MEM = pathlib.Path("/proc/pressure/memory")
PSI_IO = pathlib.Path("/proc/pressure/io")
LOG_DIR = pathlib.Path.home() / "sparkview_logs" / "psi_baseline"


def _parse_psi(path: pathlib.Path) -> dict:
    try:
        lines = path.read_text().strip().splitlines()
        result = {}
        for line in lines:
            parts = line.split()
            kind = parts[0]  # "some" or "full"
            kv = {p.split("=")[0]: float(p.split("=")[1]) for p in parts[1:]}
            result[kind] = kv
        return result
    except (OSError, ValueError, IndexError):
        return {}


def _system_info() -> dict:
    info = {
        "hostname": platform.node(),
        "kernel": platform.release(),
        "collected": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        out = (
            subprocess.check_output(
                ["nvidia-smi", "--query-gpu=driver_version,name", "--format=csv,noheader"],
                text=True,
                timeout=5,
            )
            .strip()
            .splitlines()[0]
        )
        driver, gpu = [x.strip() for x in out.split(",")]
        info["driver"] = driver
        info["gpu"] = gpu
    except Exception:
        info["driver"] = "unknown"
        info["gpu"] = "unknown"
    try:
        mem = pathlib.Path("/proc/meminfo").read_text()
        for line in mem.splitlines():
            if line.startswith("MemTotal:"):
                info["mem_total_gb"] = round(int(line.split()[1]) / (1024**2), 1)
            if line.startswith("MemAvailable:"):
                info["mem_available_gb"] = round(int(line.split()[1]) / (1024**2), 1)
    except OSError:
        pass
    return info


def _stats(vals: list) -> dict:
    if not vals:
        return {}
    return {
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "mean": round(sum(vals) / len(vals), 4),
        "p90": round(sorted(vals)[int(len(vals) * 0.90)], 4),
        "p99": round(sorted(vals)[int(len(vals) * 0.99)], 4),
    }


def collect(duration: int, label: str, interval: float = 1.0) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    print("sparkview PSI baseline collector")
    print(f"  label:    {label}")
    print(f"  duration: {duration}s")
    print(f"  output:   {LOG_DIR}")
    print(f"  started:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if not PSI_MEM.exists():
        print("ERROR: /proc/pressure/memory not found — PSI not supported on this kernel")
        return ""
    if not PSI_IO.exists():
        print("ERROR: /proc/pressure/io not found — IO PSI not supported on this kernel")
        return ""

    samples = []
    log_lines = []
    start = time.monotonic()
    n = 0

    try:
        while time.monotonic() - start < duration:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            mem = _parse_psi(PSI_MEM)
            io = _parse_psi(PSI_IO)
            t = round(time.monotonic() - start, 1)

            sample = {"t": t, "ts": ts, "mem": mem, "io": io}
            samples.append(sample)

            mem_some = mem.get("some", {}).get("avg10", 0.0)
            mem_full = mem.get("full", {}).get("avg10", 0.0)
            io_some = io.get("some", {}).get("avg10", 0.0)
            io_full = io.get("full", {}).get("avg10", 0.0)

            line = (
                f"{ts}  t={t:6.1f}s  "
                f"mem some={mem_some:.4f} full={mem_full:.4f}  "
                f"io  some={io_some:.4f} full={io_full:.4f}"
            )
            log_lines.append(line)
            n += 1

            print(f"  [{t:6.1f}s]  mem some={mem_some:.4f}  io some={io_some:.4f}", end="\r")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nInterrupted — saving collected samples...")

    print(f"\n  collected {n} samples")

    # ── Stats ─────────────────────────────────────────────────────────────────
    mem_some_vals = [s["mem"].get("some", {}).get("avg10", 0) for s in samples]
    mem_full_vals = [s["mem"].get("full", {}).get("avg10", 0) for s in samples]
    io_some_vals = [s["io"].get("some", {}).get("avg10", 0) for s in samples]
    io_full_vals = [s["io"].get("full", {}).get("avg10", 0) for s in samples]

    summary = {
        "mem_some": _stats(mem_some_vals),
        "mem_full": _stats(mem_full_vals),
        "io_some": _stats(io_some_vals),
        "io_full": _stats(io_full_vals),
    }

    # ── Write JSON ────────────────────────────────────────────────────────────
    ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = f"sparkview_psi_baseline_{label}_{ts_file}"
    json_path = LOG_DIR / f"{basename}.json"
    log_path = LOG_DIR / f"{basename}.log"

    output = {
        "tool": "sparkview_psi_baseline_collector",
        "version": "1.0.0",
        "label": label,
        "duration": duration,
        "samples": n,
        "system": _system_info(),
        "summary": summary,
        "data": samples,
    }

    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)

    # ── Write human-readable log ──────────────────────────────────────────────
    with open(log_path, "w") as f:
        f.write("sparkview PSI baseline log\n")
        f.write(f"label:    {label}\n")
        f.write(f"duration: {duration}s\n")
        f.write(f"samples:  {n}\n")
        f.write(f"system:   {platform.node()} / {platform.release()}\n")
        f.write("\n")
        f.write(
            f"{'timestamp':<22}  {'t':>7}  "
            f"{'mem_some':>10}  {'mem_full':>10}  "
            f"{'io_some':>10}  {'io_full':>10}\n"
        )
        f.write("-" * 80 + "\n")
        for line in log_lines:
            f.write(line + "\n")
        f.write("\n")
        f.write("Summary:\n")
        for key, st in summary.items():
            f.write(
                f"  {key:<12}  min={st.get('min', '?')}  max={st.get('max', '?')}  "
                f"mean={st.get('mean', '?')}  p90={st.get('p90', '?')}  "
                f"p99={st.get('p99', '?')}\n"
            )

    print(f"\n  json: {json_path}")
    print(f"  log:  {log_path}")
    print()
    print("  Summary:")
    for key, st in summary.items():
        print(
            f"    {key:<12}  min={st.get('min', '?')}  max={st.get('max', '?')}  "
            f"mean={st.get('mean', '?')}  p90={st.get('p90', '?')}"
        )

    return str(json_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="sparkview PSI baseline collector — GB10 calibration"
    )
    parser.add_argument(
        "--duration", type=int, default=120, help="Collection duration in seconds (default: 120)"
    )
    parser.add_argument(
        "--label",
        type=str,
        default="idle",
        choices=["idle", "vllm_loaded", "inference_running", "post_inference", "custom"],
        help="Workload label for this collection run",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0, help="Sample interval in seconds (default: 1.0)"
    )
    args = parser.parse_args()
    collect(args.duration, args.label, args.interval)

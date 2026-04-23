from __future__ import annotations

import gzip
import json
import os
import shutil
from datetime import datetime

from sparkview.layers import power_rails

LOG_DIR = os.path.expanduser("~/sparkview_logs")
_log_file = None
_log_path = None
_log_dir = None
_logging_active = False
_anomaly_start = None
_trigger_reason = None
_peak_temps: dict = {"gpu": 0.0, "cpu": 0.0}
_peak_gpu_w: float = 0.0
_snapshot_count = 0
_last_info: dict = {}


def _get_event_dir() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    event_dir = os.path.join(LOG_DIR, ts)
    os.makedirs(event_dir, exist_ok=True)
    return event_dir


def _detect_trigger(psi: dict, throttle: list, mem: dict, gpus: list, cpu: dict | None) -> str:
    pwr = power_rails.read()
    if pwr and pwr.prochot:
        return "PROCHOT"
    mem_psi = psi.get("mem", psi)
    if mem_psi.get("level") in ("MOD", "HIGH", "CRITICAL"):
        return f"PSI_{mem_psi.get('level')}"
    for th in throttle:
        if th.get("status") in ("THROTTLED", "LOCKED"):
            return f"CLOCK_{th.get('status')}"
    if (mem.get("percent", 0) or 0) > 85 and (mem.get("swap_percent", 0) or 0) > 1:
        return "MEM_SWAP_PRESSURE"
    for g in gpus:
        if g.get("temperature") and g["temperature"] > 80:
            return f"GPU_TEMP_{g['temperature']:.0f}C"
    if cpu and cpu.get("temperature") and cpu["temperature"] > 80:
        return f"CPU_TEMP_{cpu['temperature']:.0f}C"
    return "UNKNOWN"


def should_log(psi: dict, throttle: list, mem: dict, gpus: list, cpu: dict | None = None) -> bool:
    pwr = power_rails.read()
    if pwr and pwr.prochot:
        return True
    mem_psi = psi.get("mem", psi)
    if mem_psi.get("level") in ("MOD", "HIGH", "CRITICAL"):
        return True
    for th in throttle:
        if th.get("status") in ("THROTTLED", "LOCKED"):
            return True
    swap_pct = mem.get("swap_percent", 0) or 0
    mem_pct = mem.get("percent", 0) or 0
    if mem_pct > 85 and swap_pct > 1:
        return True
    for g in gpus:
        if g.get("temperature") and g["temperature"] > 80:
            return True
    if cpu and cpu.get("temperature") and cpu["temperature"] > 80:
        return True
    return False


def write_log(
    info: dict,
    gpus: list,
    mem: dict,
    cpu: dict,
    psi: dict,
    throttle: list,
    peak_gpu_temp: float = 0.0,
    peak_cpu_temp: float = 0.0,
) -> str | None:
    global _log_file, _log_path, _log_dir, _logging_active
    global _anomaly_start, _trigger_reason, _peak_temps, _snapshot_count, _last_info

    if not _logging_active:
        _log_dir = _get_event_dir()
        _log_path = os.path.join(_log_dir, "anomaly.log")
        _log_file = open(_log_path, "w")  # noqa: WPS515
        _anomaly_start = datetime.now()
        _trigger_reason = _detect_trigger(psi, throttle, mem, gpus, cpu)
        _snapshot_count = 0
        _peak_temps = {"gpu": peak_gpu_temp, "cpu": peak_cpu_temp}
        _last_info = info
        _log_file.write("=== sparkview anomaly log ===\n")
        _log_file.write(f"Started: {_anomaly_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
        _log_file.write(f"Trigger: {_trigger_reason}\n")
        _log_file.write(
            f"Driver: {info.get('driver', '?')} | "
            f"CUDA: {info.get('cuda', '?')} | "
            f"Kernel: {info.get('kernel', '?')} | "
            f"Uptime: {info.get('uptime', '?')}\n\n"
        )
        _log_file.flush()
        _logging_active = True

    _snapshot_count += 1
    _peak_temps["gpu"] = max(_peak_temps["gpu"], peak_gpu_temp)
    _peak_temps["cpu"] = max(_peak_temps["cpu"], peak_cpu_temp)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _log_file.write(f"--- {ts} ---\n")

    for g in gpus:
        util = g.get("utilization") or 0
        temp = g.get("temperature") or 0
        pw = (g.get("power") or 0) / 1000
        mu = g.get("mem_used") or 0
        mt = g.get("mem_total") or 0
        _log_file.write(
            f"GPU:   {util}%  {temp}°C (peak {peak_gpu_temp:.0f}°C)  {pw:.1f}W  "
            f"Mem {mu / (1024**3):.1f}Gi/{mt / (1024**3):.1f}Gi\n"
        )

    mp = mem.get("percent", 0)
    mu = mem.get("used", 0)
    mt = mem.get("total", 0)
    sp = mem.get("swap_percent", 0)
    su = mem.get("swap_used", 0)
    st = mem.get("swap_total", 0)
    _log_file.write(f"MEM:   {mp:.1f}%  Used {mu / (1024**3):.1f}Gi / {mt / (1024**3):.1f}Gi\n")
    _log_file.write(f"SWAP:  {sp:.1f}%  Used {su / (1024**3):.1f}Gi / {st / (1024**3):.1f}Gi\n")

    cpu_pct = cpu.get("percent", 0)
    active = cpu.get("active", 0)
    total_cores = cpu.get("count", 0)
    cpu_temp = cpu.get("temperature")
    cpu_temp_str = f"  {cpu_temp:.0f}°C (peak {peak_cpu_temp:.0f}°C)" if cpu_temp else ""
    _log_file.write(f"CPU:   {cpu_pct:.1f}%  Active {active}/{total_cores}{cpu_temp_str}\n")

    for th in throttle:
        status = th.get("status", "?")
        clk = th.get("clk_mhz", 0) or 0
        clk_max = th.get("clk_max_mhz", 0) or 0
        pstate = th.get("pstate", "?")
        _log_file.write(f"CLOCK: {status}  {clk:.0f}MHz / {clk_max:.0f}MHz  {pstate}\n")

    mem_psi = psi.get("mem", psi)
    level = mem_psi.get("level", "?")
    some = mem_psi.get("some_avg10", 0)
    full = mem_psi.get("full_avg10", 0)
    _log_file.write(f"PSI:   {level}  some {some:.2f}  full {full:.2f}\n")

    pwr = power_rails.read()
    if pwr is not None:
        global _peak_gpu_w
        if pwr.gpu_w is not None and pwr.gpu_w > _peak_gpu_w:
            _peak_gpu_w = pwr.gpu_w
        prochot_str = "ACTIVE" if pwr.prochot else "ok"
        dc_str = f"DC {pwr.dc_w:.1f}W" if pwr.dc_w is not None else ""
        cap_str = f"Cap {pwr.syspl1_cap_w:.0f}W" if pwr.syspl1_cap_w is not None else ""
        act_str = f"act {pwr.syspl1_act_w:.0f}W" if pwr.syspl1_act_w is not None else ""
        tj_str = f"Tj+{pwr.tj_rise_c}°C" if pwr.tj_rise_c is not None else ""
        gpu_w_str = f"{pwr.gpu_w:.0f}W" if pwr.gpu_w is not None else "?"
        _log_file.write(
            f"PWR:   GPU {gpu_w_str}  {dc_str}  {cap_str}  {act_str}  "
            f"PROCHOT {prochot_str}  PL{pwr.pl_level}  {tj_str}\n"
        )

    procs = sorted(
        [p for g in gpus for p in g.get("processes", [])],
        key=lambda x: x["gpu_mem"] or 0,
        reverse=True,
    )[:8]
    if procs:
        _log_file.write("PROC:\n")
        for p in procs:
            gm = (p.get("gpu_mem") or 0) / (1024**3)
            _log_file.write(
                f"  {p['pid']:<10} {str(p.get('user', '?'))[:12]:<12} "
                f"{gm:.1f}Gi  {p.get('cpu_pct', 0):.1f}%  {p.get('cmd', '?')}\n"
            )

    _log_file.write("\n")
    _log_file.flush()
    return _log_path


def stop_log() -> str | None:
    global _log_file, _log_path, _log_dir, _logging_active
    global _anomaly_start, _trigger_reason, _peak_temps, _snapshot_count

    if _logging_active and _log_file:
        global _peak_gpu_w
        end_time = datetime.now()
        duration = (end_time - _anomaly_start).seconds if _anomaly_start else 0

        _log_file.write(f"=== log closed {end_time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        _log_file.close()
        _log_file = None

        summary = {
            "trigger": _trigger_reason,
            "started": _anomaly_start.strftime("%Y-%m-%d %H:%M:%S") if _anomaly_start else "",
            "ended": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": duration,
            "snapshots": _snapshot_count,
            "peak_gpu_temp_c": round(_peak_temps["gpu"], 1),
            "peak_cpu_temp_c": round(_peak_temps["cpu"], 1),
            "peak_gpu_w": round(_peak_gpu_w, 1),
            "driver": _last_info.get("driver", "?"),
            "cuda": _last_info.get("cuda", "?"),
            "kernel": _last_info.get("kernel", "?"),
        }
        summary_path = os.path.join(_log_dir, "summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        gz_path = _log_path + ".gz"
        with open(_log_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(_log_path)

        _logging_active = False
        _anomaly_start = None
        _trigger_reason = None
        _snapshot_count = 0
        _peak_temps = {"gpu": 0.0, "cpu": 0.0}
        _peak_gpu_w = 0.0
        return _log_dir

    return None


def is_logging() -> bool:
    return _logging_active

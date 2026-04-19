"""sparkview — GB10 Grace Blackwell unified memory GPU monitor."""

from __future__ import annotations

import sys
import time

import psutil
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from sparkview.layers import power_rails
from sparkview.layers.cpu import get_cpu_info
from sparkview.layers.gpu import get_gpu_info
from sparkview.layers.info import get_info
from sparkview.layers.logger import should_log, stop_log, write_log
from sparkview.layers.memory import get_memory
from sparkview.layers.network import get_net_info
from sparkview.layers.power import get_power_info
from sparkview.layers.pressure import get_pressure
from sparkview.layers.throttle import get_throttle_info

THROTT_COLORS = {
    "IDLE": "dim",
    "PASS": "green",
    "WARN": "yellow",
    "LOCKED": "orange1",
    "THROTTLED": "bold red",
}

console = Console()
REFRESH = 2.0
BAR_W = 20


def bar(pct: float, w: int = BAR_W) -> str:
    f = int(w * min(pct, 100) / 100)
    return "█" * f + "░" * (w - f)


def gi(b: int | None) -> str:
    if b is None:
        return "N/A"
    return f"{b / (1024**3):.1f}Gi"


def psi_color(level: str) -> str:
    return {"LOW": "green", "MOD": "yellow", "HIGH": "red", "CRITICAL": "bold red"}.get(
        level, "white"
    )


def sep(grid: Table) -> None:
    grid.add_row(Text(""))


_last = {}
_peak_gpu_temp = 0.0
_peak_cpu_temp = 0.0


def build(term_height: int = 40) -> Table:
    gpus = get_gpu_info()
    mem = get_memory()
    cpu = get_cpu_info()
    power = get_power_info()
    psi = get_pressure()
    net = get_net_info()
    throttle = get_throttle_info(gpus)
    info = get_info()
    _last.update(
        {"gpus": gpus, "mem": mem, "cpu": cpu, "psi": psi, "throttle": throttle, "info": info}
    )
    is_uma = any(g["is_uma"] for g in gpus)

    grid = Table.grid(padding=(0, 1))
    grid.add_column()

    # ── GPU ──────────────────────────────────────────
    for g in gpus:
        util = g["utilization"] or 0
        pw = f"{g['power'] / 1000:.1f}W" if g["power"] else "N/A"
        temp = f"{g['temperature']}°C" if g["temperature"] else "N/A"
        t = Text()
        t.append("GPU    ", style="bold cyan")
        t.append(f"{bar(util)} ", style="green")
        t.append(f"{util:3d}%")
        t.append(f"  {temp}  {pw}  Mem {gi(g['mem_used'])}/{gi(g['mem_total'])}")
        if g["is_uma"]:
            mem_psi = psi.get("mem", psi)
            io_psi = psi.get("io", {})
            pwr = power_rails.read() if power_rails.is_available() else None
            # red — critical: hardware brake, throttle, high pressure, high temp
            uma_red = (
                mem_psi.get("level") in ("HIGH", "CRITICAL")
                or io_psi.get("level") in ("HIGH", "CRITICAL")
                or any(th.get("status") == "THROTTLED" for th in throttle)
                or any(g.get("temperature", 0) > 80 for g in gpus)
                or (pwr and pwr.prochot)
            )
            # yellow — warning: approaching limits
            uma_yellow = (
                mem_psi.get("level") == "MOD"
                or io_psi.get("level") == "MOD"
                or any(th.get("status") == "LOCKED" for th in throttle)
                or any(60 <= g.get("temperature", 0) <= 80 for g in gpus)
                or (pwr and pwr.cap_exceeded)
            )
            if uma_red:
                uma_style = "bold red"
            elif uma_yellow:
                uma_style = "yellow bold"
            else:
                uma_style = "green bold"
            t.append("  ⚡UMA", style=uma_style)
        grid.add_row(t)
    sep(grid)

    # ── MEM ──────────────────────────────────────────
    mp = mem["percent"]
    t = Text()
    t.append("MEM    ", style="bold cyan")
    t.append(f"{bar(mp)} ", style="green")
    t.append(f"{mp:4.1f}%  Used {gi(mem['used'])} / {gi(mem['total'])}")
    grid.add_row(t)
    grid.add_row(Text("  "))

    # ── SWAP ─────────────────────────────────────────
    sw = psutil.swap_memory()
    sp = sw.percent
    t = Text()
    t.append("SWAP   ", style="bold cyan")
    t.append(f"{bar(sp)} ", style="yellow" if sp > 20 else "green")
    t.append(f"{sp:4.1f}%  Used {gi(sw.used)} / {gi(sw.total)}")
    grid.add_row(t)
    sep(grid)

    # ── CPU ──────────────────────────────────────────
    cp = cpu["percent"]
    cores = cpu["per_core"]
    t = Text()
    t.append("CPU    ", style="bold cyan")
    t.append(f"{bar(cp)} ", style="green")
    t.append(
        f"{cp:4.1f}%  Max {max(cores):.0f}%  Active {sum(1 for c in cores if c > 5)}/{len(cores)}"
    )
    grid.add_row(t)
    sep(grid)

    # ── THROTTLE
    for th in throttle:
        if not th["available"]:
            continue
        status = th["status"]
        clk = th.get("clk_mhz") or 0
        clk_max = th.get("clk_max_mhz") or 0
        color = THROTT_COLORS.get(status, "white")
        pct = (clk / clk_max * 100) if clk_max > 0 and status != "IDLE" else 0
        bar_str = "░" * BAR_W if status == "IDLE" else bar(pct)
        reasons = th.get("throttle_reasons", [])
        reason_str = f"  [{', '.join(reasons)}]" if reasons else ""
        t = Text()
        t.append("CLOCK  ", style="bold cyan")
        t.append(f"{bar_str} ", style=color)
        t.append(f"{status:8s}", style=color + " bold")
        t.append(f"  {clk:.0f}MHz / {clk_max:.0f}MHz  {th['pstate']}{reason_str}")
        grid.add_row(t)
    sep(grid)

    # ── PSI ──────────────────────────────────────────
    mem_psi = psi.get("mem", {})
    io_psi = psi.get("io", {})
    if mem_psi.get("available"):
        level = mem_psi["level"]
        color = psi_color(level)
        score = min(mem_psi["some_avg10"] * 100 / 0.30, 100)
        label = "UMA    " if is_uma else "PSI    "
        t = Text()
        t.append(label, style="bold magenta")
        t.append(f"{bar(score)} ", style=color)
        t.append(f"{level:8s}", style=color + " bold")
        t.append(f"  some {mem_psi['some_avg10']:.2f}  full {mem_psi['full_avg10']:.2f}")
        grid.add_row(t)
    sep(grid)
    if io_psi.get("available"):
        level = io_psi["level"]
        color = psi_color(level)
        score = min(io_psi["some_avg10"] * 100 / 0.30, 100)
        t = Text()
        t.append(" IO    ", style="bold cyan")
        t.append(f"{bar(score)} ", style=color)
        t.append(f"{level:8s}", style=color + " bold")
        t.append(f"  some {io_psi['some_avg10']:.2f}  full {io_psi['full_avg10']:.2f}")
        grid.add_row(t)
    if mem_psi.get("available") or io_psi.get("available"):
        sep(grid)

    # ── TEMP ────────────────────────────────────────
    global _peak_gpu_temp, _peak_cpu_temp
    gpu_temp = max((g["temperature"] for g in gpus if g.get("temperature")), default=None)
    cpu_temp = cpu.get("temperature")
    if gpu_temp is not None:
        _peak_gpu_temp = max(_peak_gpu_temp, gpu_temp)
    if cpu_temp is not None:
        _peak_cpu_temp = max(_peak_cpu_temp, cpu_temp)
    if gpu_temp is not None or cpu_temp is not None:
        peak_val = max(v for v in [gpu_temp, cpu_temp] if v is not None)
        temp_color = "green" if peak_val < 60 else "yellow" if peak_val < 80 else "bold red"
        t = Text()
        t.append("TEMP   ", style="bold cyan")
        t.append(f"{bar(peak_val, w=20)} ", style=temp_color)
        parts = []
        if gpu_temp is not None:
            parts.append(f"GPU {gpu_temp:.0f}°C↑{_peak_gpu_temp:.0f}°C")
        if cpu_temp is not None:
            parts.append(f"CPU {cpu_temp:.0f}°C↑{_peak_cpu_temp:.0f}°C")
        t.append("  ".join(parts), style=temp_color)
        grid.add_row(t)
        sep(grid)

    # ── NET
    for n in net:
        state = n["state"]
        color = "green" if state == "UP" else "dim"
        rx = n["rx_rate"]
        tx = n["tx_rate"]
        speed = f"{n['speed_mbps'] // 1000}G" if n["speed_mbps"] else "?"

        def fmt_rate(b: float) -> str:
            if b >= 1e9:
                return f"{b / 1e9:5.1f}GB/s"
            if b >= 1e6:
                return f"{b / 1e6:5.1f}MB/s"
            return f"{b / 1e3:5.1f}KB/s"

        t = Text()
        t.append("NET    ", style="bold cyan")
        t.append(f"{n['iface']:18s}", style=color)
        t.append(f"{state:5s}", style=color + " bold")
        if state == "UP":
            t.append(f"  {speed}  TX {fmt_rate(tx)}  RX {fmt_rate(rx)}", style=color)
            if n["rx_errors"] > 0 or n["tx_errors"] > 0:
                t.append(f"  ERR rx:{n['rx_errors']} tx:{n['tx_errors']}", style="red")
        grid.add_row(t)
    if net:
        sep(grid)

    # ── POWER ────────────────────────────────────────
    # GB10: spark_hwmon rails (gpu, dc_input, syspl1, prochot, pl_level, tj_max_c)
    # Discrete: NVML power draw fallback
    if not power_rails.render(grid, sep):
        if power["available"]:
            t = Text()
            t.append("PWR    ", style="bold cyan")
            t.append(f"{power['power_w']:.1f}W", style="green")
            t.append(f"  {power['source']}", style="dim")
            grid.add_row(t)
            sep(grid)

    # ── INFO ─────────────────────────────────────────────
    t = Text()
    t.append("INFO   ", style="bold cyan")
    parts = []
    if info["time"]:
        parts.append(info["time"])
    if info["driver"]:
        parts.append(f"Driver {info['driver']}")
    if info["cuda"]:
        parts.append(f"CUDA {info['cuda']}")
    if info["kernel"]:
        parts.append(f"Kernel {info['kernel']}")
    if info["uptime"]:
        parts.append(f"Up {info['uptime']}")
    t.append("  |  ".join(parts), style="dim")
    grid.add_row(t)

    grid.add_row(Text("─" * 60, style="dim"))
    # ── PROCESSES ────────────────────────────────────
    procs = sorted(
        [p for g in gpus for p in g.get("processes", [])],
        key=lambda x: x["gpu_mem"] or 0,
        reverse=True,
    )[: max(3, term_height - 20)]

    if procs:
        t = Text()
        t.append("PROC   ", style="bold cyan")
        t.append(f"{'PID':<7} {'USER':<10} {'GPU-MEM':>8} {'CPU%':>5}  CMD", style="dim")
        grid.add_row(t)
        for p in procs:
            t = Text()
            t.append("       ")
            t.append(
                f"{p['pid']:<7} {str(p['user'])[:10]:<10} "
                f"{gi(p['gpu_mem']):>8} {p['cpu_pct']:>4.0f}%  {p['cmd'][:28]}"
            )
            grid.add_row(t)
        sep(grid)

    grid.add_row(Text("  [dim]Ctrl+C to quit  sparkview v0.2.2[/dim]"))
    return grid


def main() -> None:
    try:
        with Live(console=console, refresh_per_second=1, screen=True) as live:
            while True:
                data = build(console.size.height)
                live.update(data)
                if _last and should_log(
                    _last["psi"], _last["throttle"], _last["mem"], _last["gpus"], _last["cpu"]
                ):
                    write_log(
                        _last["info"],
                        _last["gpus"],
                        _last["mem"],
                        _last["cpu"],
                        _last["psi"],
                        _last["throttle"],
                        peak_gpu_temp=_peak_gpu_temp,
                        peak_cpu_temp=_peak_cpu_temp,
                    )
                time.sleep(REFRESH)
    except KeyboardInterrupt:
        path = stop_log()
        if path:
            console.print(f"\n[yellow]anomaly log saved to {path}[/yellow]")
        console.print("\n[green]sparkview exited.[/green]")
        sys.exit(0)


if __name__ == "__main__":
    main()

"""Network layer for sparkview — ConnectX-7 aware, sysfs only.

Detects mlx5 (ConnectX-7) interfaces on GB10 / DGX Spark.
Reads TX/RX from /sys/class/net/*/statistics/ for throughput calculation.
No subprocess, no ethtool dependency.
"""

from __future__ import annotations

import pathlib
import time

NET_SYS = pathlib.Path("/sys/class/net")

# Known primary interface names from NVIDIA playbook
CX7_PRIMARY = {"enp1s0f0np0", "enp1s0f1np1", "enP2p1s0f0np0", "enP2p1s0f1np1"}

_prev_stats: dict[str, dict] = {}
_prev_time: float = 0.0


def is_mlx5(iface: str) -> bool:
    """Detect if interface uses mlx5 driver (ConnectX-7)."""
    try:
        driver = (NET_SYS / iface / "device" / "driver").resolve().name
        return "mlx5" in driver
    except Exception:  # noqa: BLE001
        return False


def read_stat(iface: str, stat: str) -> int:
    """Read a single sysfs network statistic."""
    try:
        return int((NET_SYS / iface / "statistics" / stat).read_text().strip())
    except Exception:  # noqa: BLE001
        return 0


def read_operstate(iface: str) -> str:
    try:
        return (NET_SYS / iface / "operstate").read_text().strip().upper()
    except Exception:  # noqa: BLE001
        return "UNKNOWN"


def read_speed(iface: str) -> int | None:
    """Read negotiated link speed in Mbps."""
    try:
        val = int((NET_SYS / iface / "speed").read_text().strip())
        return val if val > 0 else None
    except Exception:  # noqa: BLE001
        return None


def read_address(iface: str) -> str:
    try:
        return (NET_SYS / iface / "address").read_text().strip()
    except Exception:  # noqa: BLE001
        return ""


def get_net_info() -> list[dict]:
    """Return ConnectX-7 interface stats with throughput rates."""
    global _prev_time  # noqa: PLW0603

    now = time.monotonic()
    elapsed = now - _prev_time if _prev_time > 0 else 1.0
    _prev_time = now

    # Discover interfaces — prefer known CX7 names, fallback to mlx5 detection
    ifaces = []
    if NET_SYS.exists():
        for iface_path in sorted(NET_SYS.iterdir()):
            name = iface_path.name
            if name in CX7_PRIMARY or is_mlx5(name):
                if name not in ifaces:
                    ifaces.append(name)

    # Sort: primary names first
    ifaces.sort(key=lambda x: (0 if x in CX7_PRIMARY else 1, x))

    results = []
    for iface in ifaces:
        rx = read_stat(iface, "rx_bytes")
        tx = read_stat(iface, "tx_bytes")
        rx_err = read_stat(iface, "rx_errors")
        tx_err = read_stat(iface, "tx_errors")
        rx_drop = read_stat(iface, "rx_dropped")

        prev = _prev_stats.get(iface, {})
        rx_rate = max(0, (rx - prev.get("rx", rx)) / elapsed) if prev else 0.0
        tx_rate = max(0, (tx - prev.get("tx", tx)) / elapsed) if prev else 0.0

        _prev_stats[iface] = {"rx": rx, "tx": tx}

        state = read_operstate(iface)
        speed = read_speed(iface)

        results.append(
            {
                "iface": iface,
                "state": state,
                "speed_mbps": speed,
                "rx_rate": rx_rate,
                "tx_rate": tx_rate,
                "rx_errors": rx_err,
                "tx_errors": tx_err,
                "rx_dropped": rx_drop,
                "address": read_address(iface),
                "primary": iface in CX7_PRIMARY,
            }
        )

    return results

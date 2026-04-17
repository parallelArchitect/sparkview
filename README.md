# sparkview

Operator-grade GPU monitor for NVIDIA GPUs with native support for GB10 / DGX Spark coherent unified memory architecture.

## Features

- GPU utilization, temperature, power, memory — live from NVML
- Automatic GB10 / DGX Spark UMA detection at runtime
- Displays MemAvailable instead of MemTotal on coherent UMA platforms
- Memory pressure (PSI) — LOW / MOD / HIGH / CRITICAL from /proc/pressure/memory
- Clock/throttle detection — IDLE / PASS / LOCKED / THROTTLED — load-gated
- CPU per-core utilization and active core count
- SWAP monitoring
- Process list sorted by GPU memory usage
- ConnectX-7 network layer — TX/RX throughput, link state, error detection
- Clean exit on Ctrl+C

## ConnectX-7 / DGX Spark Cluster

On GB10 systems, sparkview auto-detects ConnectX-7 (mlx5) interfaces and displays live TX/RX throughput per interface. Hidden on non-GB10 hardware.

Interface names per NVIDIA dual-Spark playbook: `enp1s0f0np0`, `enp1s0f1np1`, `enP2p1s0f0np0`, `enP2p1s0f1np1`.

Detects degraded links — 13 Gbps instead of 200 Gbps — via sysfs statistics. No ethtool dependency.

## Install

```bash
pip install nvitop psutil rich textual
```

## Run

```bash
python3 main.py
```

## GB10 / DGX Spark

On coherent UMA platforms, nvmlDeviceGetMemoryInfo returns NVML_SUCCESS with total equal to system MemTotal (~121GB). sparkview detects this automatically and uses MemAvailable for display instead. No configuration required.

The PSI memory pressure signal (/proc/pressure/memory) provides early warning of UMA memory contention before swap or system freeze.

Requires validation on GB10 / DGX Spark hardware. Author does not currently have access to a coherent UMA system. If you run this on GB10, please open an issue with your results.

## Clock States

| State | Meaning |
|-------|---------|
| IDLE | GPU not under load — not evaluating |
| PASS | Clock healthy under load |
| LOCKED | Clock externally capped via nvidia-smi -lgc |
| THROTTLED | Low clock under load — PD issue suspected |

Current implementation uses a fixed threshold:

- Clock < 1400 MHz under sustained load → THROTTLED

This threshold is derived from field data collected on GB10 hardware using the spark-gpu-throttle-check tool, where healthy operation reaches ~2400 MHz and degraded systems consistently operate in the 500–850 MHz range.

Detection is load-gated — THROTTLED is only evaluated when GPU utilization confirms active workload, avoiding false positives during idle or low-utilization states.

## Author

parallelArchitect
Human-directed GPU engineering with AI assistance.

## License

MIT

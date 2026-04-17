# sparkview

Operator-grade GPU monitor for NVIDIA GPUs with GB10 / DGX Spark–aware unified memory handling.

## Features

- GPU utilization, temperature, power, memory — via NVML
- Runtime detection of coherent UMA (GB10 / DGX Spark)
- Memory display uses `MemAvailable` instead of `MemTotal` on UMA systems
- Memory pressure (PSI) — LOW / MOD / HIGH / CRITICAL from `/proc/pressure/memory`
- Load-gated clock states — IDLE / PASS / LOCKED / THROTTLED
- CPU utilization and active core count
- SWAP monitoring
- Process list sorted by GPU memory usage
- ConnectX-7 network layer — TX/RX throughput, link state, error detection
- Clean exit on Ctrl+C

## ConnectX-7 / DGX Spark Cluster

On GB10 systems, sparkview detects ConnectX-7 (mlx5) interfaces at runtime and displays live TX/RX throughput per interface. Hidden on non-GB10 systems.

Interface naming follows NVIDIA dual-Spark topology:

```
enp1s0f0np0
enp1s0f1np1
enP2p1s0f0np0
enP2p1s0f1np1
```

Degraded link behavior (e.g. ~13 Gb/s instead of ~200 Gb/s) is inferred from sustained TX/RX throughput via sysfs statistics. No `ethtool` dependency.

## Install

```bash
git clone https://github.com/parallelArchitect/sparkview.git
cd sparkview

# create a virtual environment (recommended on DGX Spark)
python3 -m venv sparkview-venv

# activate it
source ~/sparkview/sparkview-venv/bin/activate

# install dependencies
pip install nvitop psutil rich textual
```

## Run

```bash
python3 main.py
```

Add a permanent alias for one-command launch from terminal:

```bash
echo "alias sparkview='source ~/sparkview/sparkview-venv/bin/activate && python3 ~/sparkview/main.py'" >> ~/.bashrc
source ~/.bashrc
```

Then just type `sparkview` from terminal to launch.

## GB10 / DGX Spark

On coherent UMA platforms, `nvmlDeviceGetMemoryInfo` may report `total ≈ MemTotal` (~121 GB). This does not reflect allocatable memory.

sparkview detects this condition at runtime and uses `MemAvailable` for display instead.

The PSI memory pressure signal (`/proc/pressure/memory`) provides visibility into memory contention before swap or system freeze.

Requires validation on GB10 / DGX Spark hardware. If you run this on Spark, please open an issue with your results.

## Clock States

| State     | Meaning                                       |
| --------- | --------------------------------------------- |
| IDLE      | GPU not under load — not evaluated            |
| PASS      | Clock healthy under load                      |
| LOCKED    | Clock externally capped via `nvidia-smi -lgc` |
| THROTTLED | Low clock under load — PD issue suspected     |

Current implementation uses a fixed threshold:

- Clock < 1400 MHz under sustained load → THROTTLED

This threshold is derived from field observations on GB10 systems using the `spark-gpu-throttle-check` tool, where healthy operation reaches ~2400 MHz and degraded systems operate in the ~500–850 MHz range.

Detection is load-gated — evaluation only occurs when GPU utilization confirms active workload.

## Author

parallelArchitect
Human-directed GPU engineering with AI assistance.

## License

MIT

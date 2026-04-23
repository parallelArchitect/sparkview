# sparkview

Operator-grade GPU monitor for NVIDIA GPUs with GB10 / DGX Spark–aware unified memory handling.

## Features

- GPU utilization, temperature, power, memory — via NVML
- Runtime detection of coherent UMA (GB10 / DGX Spark)
- Memory display uses `vm.total - vm.available` for accurate UMA reporting
- Memory pressure (PSI) — LOW / MOD / HIGH / CRITICAL from `/proc/pressure/memory`
- Load-gated clock states — IDLE / PASS / LOCKED / THROTTLED
- CPU utilization and active core count
- SWAP monitoring
- TEMP row — current and session peak for GPU and CPU, color-coded green/yellow/red
- INFO row — time, driver version, CUDA version, kernel, uptime
- Process list sorted by GPU memory usage, scales to terminal height
- PWR row — GB10 power rail monitor via spark_hwmon (gpu, dc_input, syspl1, PROCHOT, PL level, Tj-rise) — hidden on non-GB10 systems
- Anomaly auto-logger — automatically logs to `~/sparkview_logs/` when issues are detected
- Clean exit on Ctrl+C

> **Note:** This tool is not fully validated on GB10 / DGX Spark hardware. If you run it on Spark, please open an issue with your results.
>
> Community discussion and field results: https://forums.developer.nvidia.com/t/sparkview-gpu-monitor-tool-with-gb10-aware-unified-memory-handling/366877

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

## Anomaly Logging

sparkview automatically starts logging when any of these conditions are detected:

- PSI memory pressure reaches MOD, HIGH, or CRITICAL
- GPU clock drops to THROTTLED or LOCKED under load
- Memory > 85% with swap active
- GPU or CPU temperature exceeds 80°C
- PROCHOT hardware throttle active (GB10 with spark_hwmon)

Logs are saved to `~/sparkview_logs/<timestamp>/`:

- `anomaly.log.gz` — full compressed snapshot log, one entry every 2 seconds
- `summary.json` — machine-readable event summary including trigger, duration, peak temps, driver, CUDA, kernel version, and peak GPU power draw

## GB10 / DGX Spark

On coherent UMA platforms, `nvmlDeviceGetMemoryInfo` may report `total ≈ MemTotal` (~121 GB). This does not reflect allocatable memory.

sparkview detects this condition at runtime and uses `vm.total - vm.available` for used memory and `vm.total` as the display total — accurate under any workload including heavy inference loads.

The PSI memory pressure signal (`/proc/pressure/memory`) provides visibility into memory contention before swap or system freeze.

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


## GB10 Power Rails (spark_hwmon)

v0.2.3 removes the IO PSI row (false CRITICAL on GB10 with VLLM idle).

v0.2.2 adds a PWR row for GB10 systems using the spark_hwmon kernel module (https://github.com/antheas/spark_hwmon).

Install:

    git clone https://github.com/antheas/spark_hwmon.git
    cd spark_hwmon
    sudo dkms add .
    sudo dkms build spbm/0.3.0
    sudo dkms install spbm/0.3.0

sparkview detects the spbm hwmon device automatically on next run. Hidden on non-GB10 systems. PROCHOT feeds the anomaly logger and turns the UMA indicator red.

## PSI Baseline Collector


    python3 tools/collect_psi_baseline.py --duration 120 --label idle
    python3 tools/collect_psi_baseline.py --duration 120 --label vllm_loaded
    python3 tools/collect_psi_baseline.py --duration 120 --label inference_running

Saves JSON + log to ~/sparkview_logs/psi_baseline/ with min, max, mean, p90, p99 per PSI channel.

## Related Tools

- [spark-gpu-throttle-check](https://github.com/parallelArchitect/spark-gpu-throttle-check) — point-in-time GPU clock diagnostic, throttle cause identification, baseline drift detection
- [cuda-unified-memory-analyzer](https://github.com/parallelArchitect/cuda-unified-memory-analyzer) — UMA fault counts, migration bytes, and memory pressure diagnostics for GB10 and discrete GPUs
- [nvidia-uma-fault-probe](https://github.com/parallelArchitect/nvidia-uma-fault-probe) — cycle-accurate UMA fault latency and bandwidth measurement, C and PTX
- [nvml-unified-shim](https://github.com/parallelArchitect/nvml-unified-shim) — fixes NVML memory reporting on UMA platforms, MemAvailable instead of MemTotal
- [dgx-forensic-collect](https://github.com/parallelArchitect/dgx-forensic-collect) — targeted forensic data collector for DGX Spark, EFI pstore, rasdaemon, DOE mailbox state

## Author

parallelArchitect
Human-directed GPU engineering with AI assistance.

## License

MIT

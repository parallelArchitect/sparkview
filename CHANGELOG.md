## v0.2.3 — 2026-04-23

### Fixed
- Removed IO PSI row — false CRITICAL on GB10 with VLLM idle
- IO PSI references removed from anomaly logger and pressure detection

## v0.2.2 — 2026-04-19

### Added
- PWR row — GB10 power rail monitor via spark_hwmon (antheas/spark_hwmon)
  - GPU instantaneous draw, session peak, DC input, SysPL1 cap
  - PROCHOT status, active PL level, Tj thermal rise
  - Hidden on non-GB10 systems — shown only when spbm hwmon device present
- PROCHOT triggers anomaly logger — captured in anomaly.log.gz and summary.json
- PROCHOT turns ⚡UMA indicator red — visible at a glance
- peak_gpu_w added to summary.json

### Why PWR matters
- DC input < SysPL1 cap = power brick not delivering enough = PD throttle
- PROCHOT ACTIVE = hardware brake fired = clock drop to 611MHz
- These two signals explain why CLOCK shows THROTTLED

# Changelog

## v0.2.0 — 2026-04-18

### Added
- TEMP row — current and session peak for GPU and CPU, color-coded green (<60°C) / yellow (60–80°C) / red (>80°C)
- INFO row — live time (12hr), driver version, CUDA version, kernel, uptime
- Anomaly auto-logger — starts automatically when issues are detected, stops and compresses on clear
  - Logs saved to `~/sparkview_logs/<timestamp>/anomaly.log.gz`
  - Machine-readable `summary.json` per event — trigger, duration, peak temps, driver, CUDA, kernel
- ⚡UMA indicator turns red when PSI HIGH, CLOCK THROTTLED, or temp > 80°C

### Fixed
- UMA memory reporting — now uses `vm.total - vm.available` for used memory, accurate under heavy inference loads
- UMA detection — tightened to `0.9 ≤ mem.total/vm.total ≤ 1.1`, prevents false positives on large discrete GPUs
- PROC list CPU% capped at 100% — prevents psutil multi-core artifact
- CLOCK / PSI alignment — consistent 8-char status field width
- Terminal height scaling for PROC list — dynamic, no hardcoded row limit

### Changed
- INFO row sits tight between PSI and PROC — no blank line separator
- Removed ConnectX-7 from feature list pending GB10 validation

## v0.1.0 — 2026-04-17

### Added
- Initial release
- GPU utilization, temperature, power, memory via NVML
- GB10 / DGX Spark coherent UMA detection at runtime
- PSI memory pressure — LOW / MOD / HIGH / CRITICAL
- Load-gated clock states — IDLE / PASS / LOCKED / THROTTLED
- CPU utilization and active core count
- SWAP monitoring
- Process list sorted by GPU memory usage
- venv install instructions per community feedback

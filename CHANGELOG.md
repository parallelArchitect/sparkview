# Changelog

## v0.2.1 — 2026-04-18

### Added
- IO PSI row — `/proc/pressure/io` — detects data pipeline starvation before GPU utilization drops
- IO PSI anomaly trigger — logs automatically when IO PSI reaches MOD, HIGH, or CRITICAL
- IO_PSI trigger recorded in `summary.json` — distinguishes IO bottleneck from memory pressure
- Visual separation between PSI and IO rows

### Why IO PSI matters
- PSI LOW + IO CRITICAL = pure IO bottleneck (dataloader, checkpoint, network FS)
- PSI HIGH + IO CRITICAL = system contention (memory reclaim + disk fighting)
- Without IO PSI you see GPU idle. With IO PSI you know why.

## v0.2.0 — 2026-04-18

### Added
- TEMP row — current and session peak for GPU and CPU, color-coded green (<60°C) / yellow (60–80°C) / red (>80°C)
- INFO row — live time, driver version, CUDA version, kernel, uptime
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

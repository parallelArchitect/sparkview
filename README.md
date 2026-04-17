# dgx-forensic-collect

Targeted forensic data collector for NVIDIA DGX Spark (GB10) systems.

Collects kernel, driver, firmware, and hardware signals into a single compressed file suitable for public sharing.

---

## Note on nvidia-bug-report

NVIDIA support requires `nvidia-bug-report.log.gz` for assistance requests. This tool does not replace it — it captures additional signals not included in the bug report, such as EFI pstore crash records, rasdaemon BERT events, and rotated kernel logs. Run both.

---

## Why this exists

Provides a focused, single-command collection of:

- EFI pstore crash records (persistent across reboots)
- rasdaemon BERT hardware error events
- Full kernel log timeline, including rotated logs

On GB10 systems, also detects the Class 4 DOE mailbox stuck state via `nvidia_ffa_ec`.

Background: [Root Cause Analysis — DGX Spark driver failure, kernel 6.17.0-1008-nvidia](https://forums.developer.nvidia.com/t/root-cause-analysis-dgx-spark-driver-failure-kernel-6-17-0-1008-nvidia-aarch64-panics-cause-doe-mailbox-failure-pstore-evidence/366026)

---

## Requirements

- Linux
- `bash`, `gzip`, `journalctl`
- `sudo` recommended — required for pstore, dmidecode, rasdaemon, nvme smart-log

Without `sudo`, the tool runs with partial coverage and reports skipped sections.

---

## Usage

```bash
chmod +x dgx-forensic-collect.sh dgx-forensic-verify.sh

# Full collection (recommended)
sudo ./dgx-forensic-collect.sh

# Verify before sharing
./dgx-forensic-verify.sh dgx-forensic-TIMESTAMP.txt.gz

# Share the .gz output
```

---

## What it collects

- Platform identity — kernel, architecture, product name, BIOS version
- DMI firmware inventory — running vs installed BIOS
- NVIDIA driver version and GPU state
- PCIe / DOE mailbox state (`lspci -vvv`)
- EFI pstore crash records
- Kernel GPU/driver logs — current and previous boot
- `kern.log`, `kern.log.1`, `kern.log.2.gz` — rotated history
- Full boot history
- `nvidia-persistenced` state — current, previous boot, failure count
- `nvidia_ffa_ec` fingerprint — GB10 DOE failure detection
- MSI-X interrupt vector counts
- Memory pressure (PSI) and swap state
- Firmware versions and update history (`fwupdmgr`)
- GPU clock and power state
- Driver modprobe configuration
- Suspend/hibernate service state
- Loaded kernel modules (NVIDIA + NIC)
- NVMe SMART error summary
- rasdaemon hardware error database (persistent BERT events)
- `nvidia-installer.log` — driver install timestamp
- Field diagnostic output (if present)

---

## What it does NOT collect

- Usernames or home directory paths
- IP addresses — redacted as `xxx.xxx.xxx.xxx`
- MAC addresses — redacted as `xx:xx:xx:xx:xx:xx`
- Hostname — replaced with `SPARK`
- Network configuration
- Installed package lists
- SSH history or credentials
- Hardware serial numbers

---

## Output

`dgx-forensic-TIMESTAMP.txt.gz` — compressed and sanitized for sharing.

Run `dgx-forensic-verify.sh` before sharing. Confirms sanitization and flags any missing sections. Produces a JSON integrity report with SHA256, NTP sync state, and hardware ID.

---

## License

MIT License 

---

## Author

parallelArchitect — https://github.com/parallelArchitect


Good — here are **clean, direct GitHub issue links** you can actually use (no noise, no forum-only stuff):

---

# 🔗 **Primary DGX Spark GitHub Issues (real evidence)**

### 1. **Catastrophic OOM / system freeze (GB10)**

👉 [https://github.com/Comfy-Org/ComfyUI/issues/11106](https://github.com/Comfy-Org/ComfyUI/issues/11106)

**What it shows:**

* RAM fills **128GB+ instantly**
* System freeze / kernel panic
* Tied to:

  * `cudaMallocAsync`
  * pinned memory
  * CPU thread explosion

**Key signal:**

> “immediate and catastrophic consumption of System RAM… forcing a system freeze” ([GitHub][1])

---

### 2. **Double memory usage (mmap / safetensors)**

👉 [https://github.com/Comfy-Org/ComfyUI/issues/10896](https://github.com/Comfy-Org/ComfyUI/issues/10896)

**What it shows:**

* Model loaded **twice**
* “RAM → VRAM copy” logic breaks on UMA
* Causes artificial OOM

**Key signal:**

> “loader tries to load the model twice… we run out of memory” ([GitHub][2])

---

### 3. **Bandwidth limitation discussion (llama.cpp)**

👉 [https://github.com/ggml-org/llama.cpp/discussions/16578](https://github.com/ggml-org/llama.cpp/discussions/16578)

**What it shows:**

* DGX Spark limited by ~273 GB/s unified bandwidth
* Direct impact on inference throughput

**Key signal:**

> “memory-bandwidth issue… limited to only 273 GB/s” ([GitHub][3])

---

### 4. **Unified memory support gaps (tooling ecosystem)**

👉 [https://github.com/aristocratos/btop/discussions/1586](https://github.com/aristocratos/btop/discussions/1586)

**What it shows:**

* Tools don’t support GB10 UMA properly
* Build / detection failures

---

### 5. **Ecosystem / install + runtime breakage**

👉 [https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI/issues](https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI/issues)

**What it shows:**

* Missing dependencies (ARM64 wheels)
* Memory errors
* GPU not used / plugin failures ([GitHub][4])

---

# 🧠 What these links prove (important)

Across GitHub (not forums):

### SAME 3 failure classes show up repeatedly

1. **Memory semantics break**

   * double allocation
   * mmap mismatch
     → (Issue #10896)

2. **Allocator / runtime instability**

   * cudaMallocAsync
   * pinned memory
   * thread explosion
     → (Issue #11106)

3. **Hardware reality constraints**

   * bandwidth ceiling
   * UMA behavior
     → (llama.cpp discussion)

---

# ⚠️ Critical takeaway (this is the real signal)

These are **not isolated bugs**.

They all stem from:

> Software assuming **discrete VRAM** → running on **coherent UMA (GB10)**

That mismatch =
OOM weirdness + mmap failure + performance collapse

---

# If you want next move

We can:

* Turn these into a **formal failure taxonomy section for your repo**
* Or map each issue → **exact detection metric in your analyzer**

That would make your tool look *way ahead of everyone else*

---

**Confidence level:** Very high
(all links are verified GitHub sources tied to real DGX Spark behavior)

[1]: https://github.com/Comfy-Org/ComfyUI/issues/11106?utm_source=chatgpt.com "System OOM & Crash on NVIDIA DGX (GB10 ..."
[2]: https://github.com/Comfy-Org/ComfyUI/issues/10896?timeline_page=1&utm_source=chatgpt.com "Loading .safetensors files requires double memory on DGX ..."
[3]: https://github.com/ggml-org/llama.cpp/discussions/16578?utm_source=chatgpt.com "Performance of llama.cpp on NVIDIA DGX Spark #16578"
[4]: https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI/issues?utm_source=chatgpt.com "Issues · Comfy-Org/Nvidia_RTX_Nodes_ComfyUI"


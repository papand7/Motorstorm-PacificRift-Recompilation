# T190 correctness and stability

## In game

**Not run (0 launches).** Race progression, stability, rendering and reservation behaviour of B are unverified.

Checks prepared per run (`analyze_t190.py`; the runner uses `--stop-on-fatal`):

| Check | Source | T184 P |
|---|---|---|
| Race reached, stop at race + 75 s | runner log, `summary.md` | yes |
| Serious GPU/FIFO errors (`Present() Timeout`, `DEVICE_REMOVED`, resync) | stderr/stdout | 0 |
| Reservation anomalies (`[ppu-steals-resv]`, `[spu-coh…]`, `[resv…]`, lost/failed reservation, hang/deadlock) | stderr/stdout | 0 |
| `[vm-gates]` banner | B: present with the page count; P: absent | — |
| Rendering | No frame dumps in this configuration: judged by heartbeat draws and the absence of RSX errors, not by images | not verified in T184 either |

## Offline (VERIFIED)

Tree `ps3recomp-t190` = `a26240c5`; logs in `generated/analysis/t190/logs/`.

| Test | Result |
|---|---|
| `test_vm_page_gates.py` | 0 failures: gates, reservations close pages, LR on an inline store to a reserved line, 300,000-op inline vs out-of-line differential |
| `test_vm_store_fast.py` | 89 passed |
| `test_ppu_regpromo.py --seeds 4` | 0 failures, mutants detected |
| A/B exe build | 312/312 steps, exit 0 |

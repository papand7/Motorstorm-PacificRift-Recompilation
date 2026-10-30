Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# GPU synchronization and the 84 ms mode

**No wait was removed.** In the 84 ms mode, wait is 56-66 ms while `gpu_total` is 0.8 ms and GPU idle 91 ms (T162 AA2, light scene). The wait therefore is not GPU execution. T167 links it to present or remote-session behaviour, which is **unproven in the game**.

Heavy-frame GPU timestamps from the game do not exist. Bench GPU time is 0.2 ms on the RTX and 3 ms on the integrated GPU, with all draws clipped, so it says nothing about the game's GPU load. `RSX_PERF_DEEP=1` is designed to supply this at no added waits.

`test_cpath_trace`, `test_present_progress` and SPURS tests pass in the final suite. BLOCKED on a game run.

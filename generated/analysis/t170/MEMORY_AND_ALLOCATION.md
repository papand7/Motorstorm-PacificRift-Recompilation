Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# Memory

From `RSX_PERF_DEEP=1`, heavy bench, all optimizations with 3 workers:

| adapter | peak working set | GPU memory |
|---|---|---|
| RTX 5060 | 99 MB | 294 MB |
| integrated AMD | 354 MB | 305 MB |

Game peak on record: 647-707 MB working set; GPU memory not recorded.

New allocations: memo table (1,024 entries) and pool queue (4,096 jobs). Their exact share was not measured per arm. No frame-time allocation issue was found.

Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# D3D12 recording

Game `cmd` is about 10 ms in heavy frames. No separate recording change shipped. Bench `cmd` fell 5.0 -> 3.0 ms as a side effect of the other arms.

Bench counters per frame: 3,452 CBV creates (2 per draw, not deduplicated), 256 SRV creates, 27,344 SRV reuses, 233.8 table sets, 1,509 table skips.

**Rejected: `RSX_VP_CB_REUSE`.** Reusing identical constant banks gave no gain (51 vs 53 ms; 49.9 vs 49.5 ms), so it was removed.

Remaining candidate: CBV deduplication, at most a few ms. Untested.

The debug layer adds about 36-50 ms here, so `cmd` from any `D3D12_DBG` run is unusable.

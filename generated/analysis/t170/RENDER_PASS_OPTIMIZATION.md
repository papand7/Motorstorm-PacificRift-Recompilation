Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# Render passes

**No pass was removed or merged, and shadows and motion blur are unchanged.** Stage timers show the cost is per draw, not per pass, so no evidence favours pass changes. Per-pass cost in the game is unmeasured because RSXI captures record no vertex formats or shader code and cannot be replayed.

T169's flags stay as T169 left them. `RSX_DEPTH_STATE=1` speckles vehicles (T169) and is left out of the requested game baseline.

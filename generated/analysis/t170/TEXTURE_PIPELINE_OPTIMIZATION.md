Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# Texture pipeline

**No new change: this is no longer the bottleneck when the flags are on.** `RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1 RSX_TEX_BUDGET_MB=1024` took game `tex` from 178-208 ms (T161/T162 runs without them) to 4.2-5.0 ms. About 99% of lookups hit the bound entry; decode is 0.37 MB per frame. VERIFIED from recorded runs.

Those flags are still opt-in, and a run without them loses over 100 ms. That is the largest single setup risk.

Remaining cost: 27,600 lookups per frame in the bench, about 1.1 ms. Not worth further work now. Tests `test_tex_mips`, `c_tex_snapshot`, `test_tex_snapshot_wwatch` pass in the final suite.

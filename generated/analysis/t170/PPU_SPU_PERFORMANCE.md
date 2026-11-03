Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# PPU and SPU

**No PPU or SPU code changed.** Heavy frames are not limited here (other 4.3 of 91.6 ms); no physics timestep, simulation constant or sync primitive was touched.

Light frames do have about 22 ms outside the renderer (49 ms total), which caps gains there. Attributing it needs a game run: PARTIAL.

SPURS tests pass at `fda8c9b` (`test_spurs_kick_wake` is known to be flaky).

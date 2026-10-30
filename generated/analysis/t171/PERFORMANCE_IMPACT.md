# T171: performance impact

Status: **structural analysis only; not measured in game** (no launch authorized).

- The fix adds no draws, copies, barriers, or GPU synchronization.
- The three WPOS programs compile with one helper line and carry the window in their pipeline key. The window method stayed constant at height 720 in the captures read, so no extra pipelines are expected.
- All other pipelines keep their previous key and text.
- T145's A1 3.50 FPS (off) against B1 3.98 and D1 3.97 (on) is not attributable to the switch, so it is not claimed as a gain.
- T170 coordination: no T170 report exists (its branch sits at the same `542420e`), so there is nothing to reconcile.

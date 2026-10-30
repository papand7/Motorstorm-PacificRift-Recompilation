Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# Critical path

Heavy frame (TT3, 91.6 ms; wait 0.1, other 4.3): the render thread is on the critical path. **Expand (53 ms) and D3D12 record (23 ms) run serially** and account for most of the frame. VERIFIED from the game's stage timers; `expand` and `rf` overlap other stages and are not added.

| stage | concurrency | heavy state | evidence |
|---|---|---|---|
| PPU guest, SPU/SPURS | parallel with the drain | not limiting heavy (other 4.3); limiting light (other 22.2 of 49) | game timers, PARTIAL |
| FIFO drain and draw callbacks | render thread | 82.3 ms, contains expand | game timers |
| Vertex expansion | render thread; optional pool | **largest stage** | game, bench |
| Texture lookup and upload | render thread | 4.2 ms with residency flags | game; was 178-208 without |
| FP scan and PSO lookup | render thread | 8.8 ms | game, bench |
| Command recording | render thread | 10.1 ms | game |
| Submit, GPU, present | queue | 0.45 / unknown in heavy game / 0.2 | game; bench GPU 0.2-3 ms |
| GPU sync wait | render thread | 0.1 in normal mode, 56-66 in the 84 ms mode | game |

The sampling profiler showed line attributions skid, and `_NLG_Return2` is really memcpy. Line-level numbers were treated as pointers and each was confirmed by an A/B.

Light scenes are a different problem: about 22 ms is outside the renderer, so RSX work alone cannot take them far below that.

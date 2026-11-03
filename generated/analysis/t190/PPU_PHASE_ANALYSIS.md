# T190 PPU phase analysis

**Not measured: 0 launches.**

Phases on guest tid 1 (`[PT]`, T183 definitions):
- `havok`: the `30B710` Havok wait;
- `after`: post-Havok PPU, from Havok exit to the first `50D868`;
- `emit`: push-buffer emission;
- `spin`: the `50C818` frame-end Wws wait;
- also `before` and `gap`.

Reference, T184 P, mean (median) ms:

| before | havok | after | emit | gap | spin |
|---:|---:|---:|---:|---:|---:|
| 0.79 (0.76) | 25.04 (24.56) | 23.00 (22.87) | 5.60 (5.57) | 2.39 (2.38) | 11.65 (11.42) |

Havok SPU in T184 P:
- 25.3 task runs per frame;
- 115.5 ms of task time per frame across workers, 97.6 % on-CPU;
- solver `putllc` failures 18.1 %.

**How the runs will be read:**

| Question | Evidence | Reading |
|---|---|---|
| PPU execution saving | `after`/`emit` fall in B, and the main-thread CPU (`cpu.jsonl`) falls by about the same | CPU saving |
| Absorbed by waiting | `havok`/`spin` rise as `after` falls; frame time flat | the frame is SPU-bound there; no frame gain |
| SPU synchronization | `[spu-task-stats]` getllar/putllc/fail per run, `[spurs-busy]`, `[sc-wait]`/`[hle-wait]` (`logs/arm_<tag>.txt`) | expected unchanged: inline stores never touch reserved pages |

**Inline-store hit and fallback counts: not measurable on this build.**
- The implementation has no hit counter.
- `PS3_VM_STATS` forces every store out of line, which disables arm B.
- Adding counters would change the code under test, which T190 forbids.
- The only direct evidence is the `[vm-gates]` banner (pages opened at fill time).
- Pages closed later by SPU reservations are not logged.

**Offline expectation, UNVERIFIED in game** (T189):
- 1.48× on one real store-heavy function;
- about 0.95–1.05× on short real paths.

`after` is 23 ms of a 68.5 ms frame. Even a 10 % `after` gain is about 2.3 ms (3 %) at most, and only if the SPU waits don't absorb it.

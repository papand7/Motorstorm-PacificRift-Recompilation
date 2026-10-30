# T170 game benchmark results

**Status: BLOCKED after one of three launches.** Arm A's guest crashed 54 s after race entry, and the FIFO resync that followed fails the request's stop conditions. Arms B and C were not launched, so **no in-game comparison exists and the optimizations are not validated in game.** Parallel expansion has still never run in the game.

| item | value |
|---|---|
| exe SHA-256 | `f46eb9910d7eb01974fbe43d33b2ad163bd5811eae29a7e60c1c96e1aa80d9c1` (pinned copy, checked by runner and guard) |
| source | ps3recomp `fda8c9b`; exe built after that commit, no source file newer than the exe |
| device | RTX 5060 for the whole run (`gpu.csv`) |
| session | local console session; `SM_REMOTESESSION` 0 throughout |
| launches | 1: `20261030-213543-t170-AA1`, 203.2 s, no manual driving, fresh private HDD |
| effective | `[visual] effective` all switches 0; no debug-layer line; `D3D12_DBG` absent from the environment |

Effective flags: `RSX_VP_FAST_FETCH=0 RSX_FP_SCAN_MEMO=0 RSX_VP_PARALLEL=0`, the T165 base, `TEXRES`, `RSX_PERF_DEEP=1`. The dry-run comparison showed arms B and C differ from A only in the three flags. Deep profiling (+0.5 ms in the bench) and 16 frame dumps every 64 presents stayed on, needed for stage times, GPU times and correctness. No RSXI, visual diagnostics or c33 watch.

## The crash (VERIFIED as observed, cause unknown)

- Race entry 125.99 s. Last heartbeat 180.25 s (race + 54 s), race clock about 00:18. Then no frames or heartbeats until the stop at 203.14 s.
- First sign, on guest thread 1: `[ppu] unresolved indirect call -> 0x00CB7FA8`, object `0x16217950` whose vtable word is `0x3F800000` (float 1.0), so the object holds data rather than a C++ object. Null reads and dropped null writes follow from guest function `0x00BB9800`.
- About 6 cores busy during the freeze, GPU at 3-5%.
- At 203.14 s: `FIFO CALL to unmapped IO 0x1F6ABC44`, `FIFO resync (unmapped-CALL) 0x00220124 -> put 0`. The runner stopped on that line.
- No Present timeout, device removal or Present failure.

**Not known to be pre-existing.** This message appears in none of the other 149 most recent run directories, including about 25 long runs. perfnext TT3 (older exe) reached 62 s of race frame time without it. T169's runs stopped at race + 45 s, before this point, so the T169 head isn't cleared either. One crash can't separate a T170 change from T168/T169 changes or a rare race.

HYPOTHESIS: guest memory corruption or a stale read. Candidates active in arm A: the always-on write-combined fix, the `cellGcm` sync hook (null with parallel off), and `RSX_PERF_DEEP`'s environment change. None has been shown to touch guest memory; none has been ruled out.

## Measurements, arm A only

All race frames precede the crash: 771 frames, 58.0 s of frame time. Classes by records. Dump frames are included, so p99 and max are unreliable, and PSO misses dominate the first 20 s.

| phase | frames | FPS | p50 | p95 | p99 | records | expand | record | tex | pso | cmd | wait | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all race | 771 | 13.3 | 70.7 | 82.5 | 160.3 | 4,277 | 20.8 | 21.6 | 3.1 | 10.4 | 8.1 | 0.1 | 21.8 |
| light < 3,000 | 208 | 14.2 | 47.6 | 56.6 | 541.7 | 1,433 | 8.5 | 20.8 | 1.7 | 16.3 | 2.8 | 0.0 | 28.9 |
| mid | 420 | 13.7 | 71.4 | 79.4 | 137.2 | 4,320 | 23.4 | 19.0 | 3.1 | 5.7 | 10.1 | 0.1 | 21.0 |
| heavy >= 5,000 | 143 | 11.2 | 77.0 | 88.6 | 153.8 | 6,105 | 30.9 | 30.7 | 5.3 | 15.5 | 9.9 | 0.1 | 13.9 |
| race + 20-30 s, no PSO misses | 133 | 13.3 | 75.4 | 82.5 | 88.6 | 5,304 | 28.4 | 19.1 | 4.1 | 6.2 | 8.8 | 0.1 | 17.3 |

Times in ms; stage columns are means.

- **PSO:** 135 misses, 4.66 s in total, in the race; the 2.4 s worst frame comes from PSO time (`pso` max 1,449 ms in its window).
- **Vs TT3 (91.6 ms mean, expand 53.2):** heavy mean 89.4, expand 30.9 at 10% fewer records. Expansion fell by more than record counts explain, consistent with the write-combined fix. Frame totals are not otherwise comparable: another exe, and PSO misses here.
- **GPU fence wait:** 0.1 ms. The last `[gpu-prof]` reports show about 24 ms of GPU idle per frame, but they aren't per race phase.
- **CPU, race + 0-54 s:** game 3.38 cores, busiest threads 0.66 and 0.54 cores; system busy 6.94 of 12. Threads are unnamed in the sample.
- **Guest sync:** `[sc-wait]` lines are present; not analysed, as there is no second arm to compare.
- **Whether work moved between threads, arm C's ordering, incomplete vertex data:** not answered; no arm B or C.

## Correctness, arm A only

10 presented frames were dumped; four were inspected at reduced size (the last shows race clock 00:18.36). VERIFIED in those: vehicle, rider, terrain, trees, HUD and race clock draw. The ground is overexposed with streaks; it was not compared against anything here and isn't attributed to T170. Shadows and texture integrity weren't assessed at this size. No frame comparison between arms exists.

## Interference

- **Godot** (two processes, not launched by T170) used about 51% of the RTX 3D engine during startup, per another session's check at 21:35:50, and last appears in the CPU samples about race + 10 s. Its effect on the first 10 s of race isn't separable; the 20-30 s row is clear of its CPU use.
- **Ollama:** two idle `llama-server` processes held most of the roughly 5.4 GB of VRAM in use before launch, of 8.15 GB; peak total 6.67 GB, no overflow seen. Left running: not T170's to stop.
- **LeOffice** used about 1.15 cores during the race.
- Another session ran two brief checks at 21:35:45-21:35:58, in startup. No other game process.

## Guard

`run_guard_t167.py post`: STOP for the FIFO resync and for termination (the runner ended the session 2 s before the cap, because of the resync). Pre guard ok. No retry was made.

## Recommended settings

No default changes. Keep `RSX_VP_FAST_FETCH`, `RSX_FP_SCAN_MEMO` and `RSX_VP_PARALLEL` opt-in and off, and don't treat `RSX_VP_PARALLEL` as safe: synthetic byte matches don't cover this. Before spending the remaining launches, find out whether this crash exists without T170: the same route on the T169 head past race + 54 s, which needs its own launch authorization.

## Limits

One run, no repeat, not an idle host. CPU figures are 5 s samples. `[perf-deep]` windows mix phases. Vertex and record times aren't GPU times; this exe has no in-game counters for parallel jobs.

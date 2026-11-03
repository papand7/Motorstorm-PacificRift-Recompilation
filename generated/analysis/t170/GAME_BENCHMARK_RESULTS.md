# T170 game benchmark results

**Status: BLOCKED after one of three launches.** Arm A's guest crashed 54 s after race entry, and the FIFO resync that followed fails the request's stop conditions. Arms B and C were not launched, so **no in-game comparison exists and the optimizations are not validated in game.** Parallel expansion has still never run in the game. **A T169 baseline launch reproduced the crash: it is an inherited lifter gap, not a T170 regression (see "T169 baseline crash isolation").**

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

The first version of this section called the object "data rather than a C++ object" and proposed guest memory corruption. **That reading was wrong; see below.** The vtable line is a generic dump of `r3`.

## T169 baseline crash isolation (one launch)

**Result: the same failure reproduces on T169, so it is inherited, not caused by T170.** VERIFIED: it is a recompiler gap, a jump table in `func_00CB7D80` the lifter did not recognise, and not guest memory corruption.

| item | value |
|---|---|
| exe SHA-256 | `59019e06b9a39074ea2d47e90dd3c41f0299d73463e610db2ce8fa030011ba08`, `build/motorstorm-t169`, pinned copy |
| source | ps3recomp `542420e`, T170's direct parent, per the T169 runner's record (built 4 min after the commit); same `port-t161` and `ppu-hooked-staging`; `CMakeCache` differs from T170's only in paths |
| flags | identical to arm A: all 53 `--env` entries compared, except run-specific paths. `RSX_FP_SCAN_MEMO`, `RSX_VP_PARALLEL` and `RSX_PERF_DEEP` don't exist in this exe. `[visual] effective` all 0, no debug-layer lines, no `D3D12_DBG` |
| session | `20261030-214922-t170base-AB1`, local console, fresh private HDD, same route and flyover skip, no manual driving |
| host | Ollama stopped by T170 (peak GPU memory 1,039 MiB vs 6.67 GB). Another session's bounded Godot test was left to expire before launch, and none ran during it. LeOffice stayed open (it hosts this session), 18 CPU s over the race |
| stop | runner stop 3 s after the crash, 162.5 s. Race + 70 s not reached |
| guard | post STOP: exit code 1 (expected, killed) and "0 heavy frames", which disagrees with the 142 the summary counts; not investigated |

| crash field | T170 arm A | T169 baseline |
|---|---|---|
| race entry, host s | 125.99 | 123.26 |
| crash, after race entry | about 54 s | **36.1 s** |
| guest frame / race frames | 5454 / 771 | 5141 / 510 |
| target, PPU thread | `0x00CB7FA8`, tid 1 | same |
| `r3`, `r0`, `r8`, `r9`, `r11`, LR | `16217950`, `130`, `16219800`, `4`, `00CB7FA8`, `14B42E10` | same |
| `r3[0..7]` | `3F800000 3F19999A 3F800000 3E99999A 0 BDA74033 0 0` | same |
| guest call chain | `func_00BB82D8` < `B97F40` < `B95B10` < `B77450` < `30B710` < `8CF1C0` | same |
| null writes after | `func_00BB9800` at `NULL+0x12C` | same |

### Cause

From the original code at `0x00CB7E50`-`0x00CB7E74`, the lifted source and the crash registers:

- The guest code is a switch: `cmplwi r0,0x1C`, `ld r11,0x1F0(r1)`, `lwzx r0,r9,r11`, `add r11,r0,r11`, `mtctr r11`, `bctr`, with 29 relative offsets inline at `0x00CB7E78`.
- `r9 = 4` selects entry 1, whose stored word is `0x130`, and `0x00CB7E78 + 0x130 = 0x00CB7FA8`. The registers match exactly, so **the guest computed a correct target.**
- The lifted code (`ppu_recomp_026.cpp`, 78 lines into the function) emits `ps3_indirect_call(ctx)` for this `bctr`, with no `switch`, as it does for a resolved table later in the same function. `0x00CB7FA8` isn't a function entry, so dispatch fails.
- `0x00CB7FA8` has no static branch, pointer or data reference in the ELF, consistent with only this table reaching it.
- LR `14B42E10` isn't corrupt: the function does `mtlr r6` at `0x00CB7D90`, and `r6` holds that value. `r3` is an ordinary argument pointing at floats, so the `vtable=3F800000` line means nothing here.
- The null writes follow from it: the failed dispatch returns into the caller with registers it doesn't expect. INFERRED from the sequence; not traced.
- PPU/SPU sync, SPU tasks and RSX aren't needed to explain the fault. Both runs spawned image `341580667` tasks just before it. RSX kept running until the stop.

**Not known:** what makes the game reach this switch, or why at a different time per run. It isn't a fixed time: exe `59019e` ran to race + 45 s under other settings without it, and about 25 older long runs never showed it. No write watch ran on `r3`'s buffer; identical contents and addresses plus the correct table lookup leave no need for one.

### T169 vs arm A, same route

| 20-30 s after race entry, no PSO misses | p50 | expand | record | other |
|---|---:|---:|---:|---:|
| T169 | 71.8 | 40.2 | 17.6 | 5.6 |
| T170 arm A | 75.4 | 28.4 | 19.1 | 17.3 |

Heavy frames: mean 88.9 vs 89.4, expand 44.3 vs 30.9. **The write-combined fix cut expansion by 12-13 ms, but `other` rose by about the same amount, so frame time didn't improve.** The work probably moved rather than disappeared. Not proven: one run each, arm A adds `RSX_PERF_DEEP`, and the 20-30 s window itself is quiet in both.

### Next step

Fix the lifter so this `bctr` resolves: its table base comes from a stack spill (`ld r11,0x1F0(r1)`), a likely reason the pattern was missed (HYPOTHESIS). Scan all lifted code for the same shape, since other unresolved switches may be waiting. Then regenerate, rebuild and rerun past race + 70 s. This needs separate authorization. Arms B and C should wait for it, because any run can end early here.

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

No default changes. Keep `RSX_VP_FAST_FETCH`, `RSX_FP_SCAN_MEMO` and `RSX_VP_PARALLEL` opt-in and off, and don't treat `RSX_VP_PARALLEL` as safe: synthetic byte matches don't cover this. Before spending the remaining launches, fix the unresolved jump table described above.

## Limits

One run, no repeat, not an idle host. CPU figures are 5 s samples. `[perf-deep]` windows mix phases. Vertex and record times aren't GPU times; this exe has no in-game counters for parallel jobs.

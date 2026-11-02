# T183: race FPS critical path

Status: **PARTIAL. What limits race FPS is identified from T182's in-game logs: the guest frame thread and the SPU work it waits on, not the RSX. No large fix exists yet, because SPU task time and PPU time by function have never been measured. One small opt-in optimization and one measurement were added. No game launch, so no FPS gain is claimed.**

## 1. Baseline

| Item | Value |
|---|---|
| Reference | T182 `e9ba485f8f9cbb2556e19fdfb45acd7867cb5aa1`, exe `a1cd6f1f…3786` |
| Evidence | Existing logs of T182 runs `Rr1`, `Bb1`, `Dd1`; one run per arm, race last 55 s, records >= 1000, no shader miss in the frame |
| Branch | `agent/t183-race-fps-bottleneck`, `ps3recomp-t183`, `root-t183` |
| Head | `766d35755bbd99adbd0e11d39b6bee6da2556f8d` |
| Exe | `build/motorstorm-t183`, rc=0, SHA-256 `c32cd09dd02447a6a4791af69a84c4aa653639f31ee5d3d8129a1324d6119b97` |

## 2. What the counters mean

All `[rsx-frame-perf]` times are from the RSX drain/present thread (`rsx_frame_perf.h`, `rsx_d3d12_backend.c`). None measures the guest.

| Counter | Calculation | Overlap |
|---|---|---|
| `wall_ms` | Time between closes of presenting passes | The real frame time |
| `drain_ms` | All of `cellGcm_rsx_process_fifo` | Contains `draw_cb`, `expand`, `flush`, and in-drain passes |
| `draw_cb_ms` | Time in draw callbacks | Contains `expand`, `flush`, VS misses |
| `expand_ms` | `draw_cb - flush - vs_miss` | Inside `drain` |
| `flush_ms` | Early replays started from a draw callback | Inside `drain`, overlaps `rf` |
| `rf_ms` | All `render_frame` passes | `in_drain` part is inside `drain` |
| `record_ms` | Recording phase of passes | Inside `rf`; contains `tex`, `pso`, `cmd` |
| `other_ms` | `wall - drain - (rf - in_drain)`, floored at 0 | **A residual**, not guest CPU |

**`other_ms` is mostly render-thread idle** (PARTIAL). In D the busy counters total 33.3 ms and the thread used 28.8 ms of CPU per 68.4 ms frame, leaving about 35 ms off CPU, the same size as `other` (35.0 ms). The thread is waiting for guest commands, so vertex savings simply turn into more `other`.

## 3. Critical-path timeline

Guest thread `tid 1`, from the `[PT]` sites already in the logs. Mean ms per frame. Each perf line was joined to its guest frame by stderr order. **The phases sum to the frame:** 71.21, 68.11, 68.37 against 71.24, 68.13, 68.39, and `wall_ms` agrees within 0.1 ms. `r` is the per-frame correlation with frame time in D.

| Order | Phase | Site | R | B | D | r (D) |
|---|---|---|---:|---:|---:|---:|
| 1 | RSX reference wait | `72E1E0` | 0.06 | 0.04 | 0.05 | +0.29 |
| 2 | Before Havok wait | | 0.78 | 0.73 | 0.73 | +0.13 |
| 3 | **Havok SPU wait** | `30B710` | **24.99** | **24.17** | **25.59** | **+0.79** |
| 4 | **Havok return to first push buffer** | | **25.13** | **23.16** | **22.50** | +0.09 |
| 5 | Push-buffer emit | `50D868` first to last | 5.65 | 5.53 | 5.31 | +0.18 |
| 6 | Gap | | 2.40 | 2.26 | 2.24 | +0.10 |
| 7 | **Frame-end Wws spin** | `50C818` | **12.20** | **12.22** | **11.94** | -0.09 |
| | **Frame** | | **71.24** | **68.13** | **68.39** | |

For comparison, RSX terms in D: `drain` 29.8 ms, r = -0.38; `expand` 15.7 ms, r = +0.32 (it follows draw load, which also loads the guest).

**Answers:**

- **The next frame is decided by `tid 1`, a serial sequence.** VERIFIED for these runs. It almost never waits on the RSX (0.05 ms), so the RSX could take no time at all and the phases above would still total 68 ms.
- **Why D gained nothing:** the 14 % `expand` saving is off this path. VERIFIED as the mechanism, replacing T182's hypothesis.
- **Host CPU isn't saturated:** 4.6-4.9 of 12 logical CPUs, busiest thread about 0.65 of a core. Those are 5 s samples, so bursts could hide.
- **Is the game limited by a serial dependency:** yes on `tid 1`, with parallel SPU waves inside it. Removing all Havok wait would give about 23 FPS, and all Havok and spin about 32 FPS. These are ceilings from arithmetic, not forecasts.

## 4. Ranked hotspots

Share of the 68.4 ms D frame.

| # | Hotspot | ms | Share | Class | Evidence | Label |
|---|---|---:|---:|---|---|---|
| 1 | Havok wait: 25 SPU task runs per frame, mostly on 5 threads | 25.6 | 37 % | Guest compute through lifted SPU code, split unknown | r = +0.79; explains most frame variation | VERIFIED as time |
| 2 | Havok return to first push buffer | 22.5 | 33 % | Mostly PPU guest code; JobBatch wait about 3 ms from earlier frames | `tid 1` CPU 37 ms per frame | VERIFIED as time, functions unknown |
| 3 | Wws spin | 11.9 | 17 % | Guest busy-wait on SPU jobs; 5 lanes use 23 ms CPU each | Shrinks only if jobs finish sooner (T152) | VERIFIED as time |
| 4 | Emit | 5.3 | 8 % | PPU | | VERIFIED as time |
| 5 | Gap, before Havok | 3.0 | 4 % | PPU | | VERIFIED as time |
| 6 | RSX wait | 0.05 | 0.1 % | Render starvation doesn't occur on the guest | | VERIFIED |

**Other brief items:**

| Item | Finding | Label |
|---|---|---|
| GPU submission, fence | Submit 0.3 ms, present 0.2 ms, wait 0.0 ms, on the render thread only | VERIFIED |
| Task threads | About 100-124 ms CPU per frame, process CPU minus live threads. Divided by 5 that is 20-25 ms, close to the 25 ms wait, so tasks look on-CPU rather than sleeping. Spinning inside a task isn't excluded | PARTIAL |
| Host overhead per task | Thread per run: 0.3-0.45 ms per chain at light load (T156 offline) | PARTIAL |
| Logging | About 83 task lines and 53 `[PT]` lines per frame; see section 6 | VERIFIED count |
| Instrumentation overhead | Not measured in game. `[PT]` stays on because the route needs it | BLOCKED |
| Lock contention, runnable vs blocked, scheduling latency, SMT sharing, core affinity | No data in these runs | BLOCKED; needs arm S |
| R to B `after` falling 2 ms | Cause unknown; less render-thread memory or SMT pressure is a HYPOTHESIS | HYPOTHESIS |

## 5. Root cause

Race FPS is limited by guest work on `tid 1` and the SPU work it waits for, run through lifted code. T158's open question still stands: Havok solver time did not respond to codegen, and no run has split it. No game run has used `PS3_SPU_TASK_STATS` or `PS3_SAMPLE`.

T182's fixed-site data can't name functions, so an optimization aimed at items 1-3 would be speculation. None was attempted.

## 6. Implemented changes

Commit `766d3575`; one revert removes it. Both are off unless set.

| Change | Flag | Why |
|---|---|---|
| Stops four per-task log lines after 64 each, including a `fflush` | `PS3_SPU_TASK_QUIET=1`, exactly `1` | They run on the frame thread and task threads, about 83 per frame. No guest state or wait depends on them. Runner milestones counting `dispatch HIT` undercount when on |
| Adds `cpu_cyc` and `fn_tsc` to `[spu-task-stats]` | `PS3_SPU_TASK_STATS=<ms>` | Their ratio is the on-CPU share of each lifted task, which answers T158's question with `mfc_ns` |

No new sampler code was needed: `PS3_SAMPLE`, `PS3_SAMPLE_MAIN` and `PS3_SAMPLE_TOP` already rank `tid 1` by function.

**Existing flags never run in game on this line:** `PS3_ICALL_FAST=1` (T152, 15.2 to 5.9 ns per hot indirect call) and `PS3_SPU_TASK_POOL=1` (T156). Neither requires code changes, and arm C tests them. Their source tests passed in the suite.

## 7. Offline benchmarks

`runtime/spu/tests/bench_task_log.c`, 77 production-format lines per frame from 5 concurrent threads, stderr to a file on the game-log disk. 5 interleaved runs of 2,000 frames, ranges of medians. **Synthetic; another GPU load was present, CPU load unknown.**

| | Default | Quiet |
|---|---:|---:|
| Line time per frame, summed over threads | 607-627 µs | 2.8-3.1 µs |
| Wall per frame | 204-211 µs | 1.9-2.1 µs |

So the upper bound is about 0.2 ms of a 68 ms frame, about 0.3 %. This is a small optimization and doesn't address the limit.

## 8. Regression

| Check | Result | Label |
|---|---|---|
| Full suite through `env_t169.cmd` | **162 pass, 0 fail, 43 skip** | VERIFIED |
| Exact base T182, recorded | 161, 0, 43; the extra pass is `test_spu_task_log` | VERIFIED |
| `test_spu_task_log` | 0 failures: unset, `1`, wrong values, 64 lines across 8 racing threads, source pins | VERIFIED |
| `tests/test_spu_task_stats.py` (not in the suite) | 0 failures, guest state hash identical unset, on, malformed | VERIFIED |
| `test_spu_task_pool` | 3 seeds, 2,020 checks each, 0 failures | VERIFIED |
| Suite rewrites of `scratch/ppu_conformance*` | Restored | VERIFIED |

## 9. Build and audit

Build rc=0, exe above, built after the head commit with the T182 recipe and `generated/ppu-t173-staging`; no relift. Code audit `--tree` on a copy passed; this report `--staged --private-reports`. Runner `prepare`, `envcheck` and `dryrun C` passed; arm differences are exactly the flags in section 11, and nothing was launched.

## 10. Expected against measured

| Claim | Kind |
|---|---|
| Phase timeline, RSX off the path | Measured in game, T182 logs |
| `other_ms` mostly idle | Derived from measured CPU and counters |
| Task threads on-CPU | Inferred from CPU totals |
| Quiet saves up to about 0.2 ms | Measured, synthetic |
| Pool saves 0.3-0.45 ms | Measured offline by T156 |
| `PS3_ICALL_FAST` frame gain | Unknown; call frequency unmeasured |
| Any T183 FPS gain | **None measured.** Expect at most small single-digit percent from arm C (HYPOTHESIS) |
| 30 FPS or more | No supporting path yet |

## 11. Proposed runtime test (not authorized, nothing launched)

`generated/analysis/t183/ab/run_t183.py`, generated by `tools/make_runner_t183.py`, exe pinned. Same preflight, game data, route and resolution as T182. All arms use a copy of T182's warmed shader cache, to control cache warming. Stop at race + 75 s. No retries.

| Order | Arm | Flags beyond T182 B | Decides |
|---|---|---|---|
| 1 | S, not timed | `PS3_SAMPLE=2`, `PS3_SAMPLE_MAIN=1`, `PS3_SAMPLE_TOP=25`, `PS3_SPU_TASK_STATS=1000`, `SPURS_BUSY_MS=1000`, `PS3_SC_WAIT_MS=1000`, `PS3_HLE_WAIT_MS=1000` | Functions in hotspot 2; on-CPU, DMA and atomic share in hotspot 1; lane use. **The most valuable launch** |
| 2, 5 | B | None | Baseline, with its run-to-run spread |
| 3, 4 | C | `PS3_ICALL_FAST=1`, `PS3_SPU_TASK_POOL=1`, `PS3_SPU_TASK_QUIET=1` | Combined gain |

Five launches, or arm S alone first, which may change what to test. Measure with `tools/frame_join_t183.py` and T182's stats: FPS, median and p95 frame, every phase in section 3, render counters, CPU, GPU, memory, crashes, stalls.

**Pass for C:** frame time lower than the B-to-B spread, explained by a phase that moved. S's sampling distorts timing, so it isn't an FPS arm. Rendering correctness isn't covered by these flags' arms: none changes RSX output, but a frame comparison would need dumps, which this runner strips.

## 12. Evidence

Tools in `tools/`: `frame_join_t183.py`, `phases_t183.py`, `pre_sites_t183.py`, `make_runner_t183.py`, `run_all_t183.py`, `patch_t183.py`. Private and untracked, because the audit blocks `.cmd` files under `generated/`: `bench_task_log_t183.cmd`, `build_t183.cmd` in the main tree's `generated/analysis/t183/tools`, plus `generated/runs`, `generated/analysis/t183/ev`, `ab`.

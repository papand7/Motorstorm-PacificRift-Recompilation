# T149: MotorStorm Pacific Rift, PPU/SPU critical-path optimization

Labels: VERIFIED, PARTIAL, HYPOTHESIS, BLOCKED. Four authorised game launches (§15); no push, no merge, and no GitHub operation.
Short findings: `CRITICAL_PATH_FINDINGS.md`.

## Answer in brief

1. **Measured (§15, 4 authorised race runs):** SPURS dispatch is not on the critical path.
   - At most 2.7 ms of about 115 ms idle per lane per frame is the scheduler's; the rest is the guest having no work ready (VERIFIED).
2. **Default T146 runtime:** the RSX drain gates the frame (157 ms per frame, 79 ms of it the texture-snapshot hash).
   - With the performance preset, the RSX and the PPU frame thread's own compute (56 ms) gate together.
3. **No SPURS/PPU optimization was justified, and none was implemented.**
   - `PS3_USLEEP_SPIN=2` gave no race gain and slowed loading.
   - No default was changed.
4. **Delivered:**
   - the instrumentation (`ce32629`, off by default);
   - the analysis tools, with tests;
   - the A/B data (private).

## 1. Baseline and source commit

- **ps3recomp:** worktree `ps3recomp-t149-critical-path`, branch `agent/t149-ppu-spu-critical-path`.
- **Base:** `80fe5de`, the T146 tip of `integration/t146-unified-runtime`. T146 was still finishing during this task: its exe `build/motorstorm-t146` was linked at 19:00, and report §5/6/10 are unfilled. This is the newest committed integration with a passing suite.
- **Absent from the base:**
  - T144 `PS3_SPURS_LANE_HANDOFF` (uncommitted in `ps3recomp-t144s`);
  - misc-hle-features;
  - the WWS AOT exe block (`MSPR_WWS_AOT`, `port-t106aot`);
  - `PPU_RAW_STORE_COH` in the exe (needs a re-lift).
- **T149 commit:** `ce32629` (one commit on `80fe5de`).
- **Untouched control:** a detached worktree, `ps3recomp-t149-base` at `80fe5de`, used only to run the same suite.

## 2. Profiling methodology

The work reuses and extends the T134 `PS3_CRITICAL_PATH_TRACE` stream (`include/ps3emu/ps3_ftrace.h`):
- one QPC clock;
- a bounded Vyukov queue that drops spans rather than block;
- a writer thread.

No second profiler was added.

| Timeline item (brief §3) | Recorded by | Status |
|---|---|---|
| PPU job submission (kick) | **new 36 `SPURS_KICK`**: a guest atomic commit to the instance's line 0, with counts of ready and signalled workloads | T149 |
| Job eligible / ready queue | **new 37 `SPURS_PASS`**: per coordinator pass, admitted / free lanes / eligible / eligible at maxContention | T149 (workload level) |
| Coordinator dispatch | 24 `SPURS_PICK` (workload, lane, kicked) | T134 |
| Lane wake → SPU execution start/end | 25 `SPURS_PM` residency, with kernel polls | T134 |
| Wws job spans inside a residency | 26–30 (`PS3_FTRACE_SPUJOB=3214:1320`) | existing |
| SPU tasks (Havok) | 34 `SPU_TASK` | T134 |
| Completion → PPU resuming | **new 35 `GUEST_FN`**: every call of the PT sites, on the trace clock (the wait sites `0x4AACA0`, `0x5F74B0`, `0x30B710`, `0x50C818`, `0x72E1E0` and the primitive `0x4B63F0`), with usleep (2) and syscalls (1) | T149 |
| RSX submission / execution | `0x50D868` / `0x736770` via 35; drain 7, record 33, GPU wait 12 | T149 + T134 |
| Host CPU per thread | 32 `HOST_CPU` | T134 |

**Not observable without decoding guest structures:** individual Wws job dependencies. They live in guest memory and are resolved by the guest policy module on the SPU. The trace sees them as residency, polls and job spans, and as the PPU's waits on the done counters (`[r3+0x2560]`) (BLOCKED, not needed for the workload-level classification).

**Overhead:**
- Trace off: 0.18 ns per guard (`test_cpath_trace` bench). The line-0 hook stays unset (pinned).
- Trace on: 40.8 ns per span.

## 3. PPU/SPU timeline (measured, older lineages)

| Build | Frame | ref (RSX) | PRE (SPU tasks + jobs) | emit | spin (Wws) |
|---|---:|---:|---:|---:|---:|
| One lane (T145 A1/B1/D1, today, debug layer on) | 254–294 | 8.6–11.5 | 120–137 | 78–92 | 45–51 |
| One lane (T122, 23 arms) | 193–243 | 0–0.3 | 93–116 | 58–77 | 38–48 |
| Five lanes (T106 B) | 136 | 45–47 | 54 | 21 | 12.5 |
| Five lanes + Wws AOT (T106 D) | 129 | 80–82 | 40 | 6 | 0.3 |

Sources:
- `t149/tools/phases_t145.txt` (new; the T134 definitions applied to today's T145 runs);
- `t134/phases_all.txt`;
- T106 `AB_RESULTS.md`.

## 4. Critical-path reconstruction

- **One lane (VERIFIED):**
  - Wws jobs are admitted to one SPURS lane.
  - PRE, emit and the frame-end spin all wait on SPU work.
  - The RSX thread is idle 114–168 ms per frame.
- **Five lanes (VERIFIED, T106):**
  - The PPU's SPU waits shrink by 123 ms.
  - The frame thread now waits 45–82 ms at `0x72E1E0` for the RSX.
  - The RSX drain thread is busy about 130 of 134 ms, of which vertex expansion takes 107.
  - **The gate is the guest RSX command processing on the host**, not SPURS.
- **Unified runtime:** BLOCKED. It has five lanes, T119's VS memo and getenv-once on by default, and T122 epoch / T119 compact as opt-ins.
  - The RSX drain is expected to gate by default (HYPOTHESIS).
  - With the performance preset, PRE is expected to gate (HYPOTHESIS, T123/T134).

## 5. Idle-time classification

**Existing data:**
- The lanes are 68% (B) and 91% (D) idle.
- The five lanes are evenly loaded.

That leaves "no guest work", "ready, waiting for a pass", "admitted, waiting for the lane thread", "maxContention" and "frame thread asleep despite done" **inseparable** (BLOCKED).

The T149 report splits each lane's idle time into these categories. The categories are defined in `tools/cpath_report.py` and verified on a known-answer trace:

| Category | Meaning | Brief category |
|---|---|---|
| `no_work` | nothing ready or signalled | no job / dependencies / PPU not submitting / barrier |
| `kick_wait` | kicked after the last pass began | ready, waiting for coordinator dispatch |
| `ready_unadmitted` | eligible below maxContention, a lane free, not admitted | admission rule / poll backoff (host) |
| `capped` | eligible only at maxContention | guest limit |
| `pick_to_run` | admitted, lane thread not yet in the policy module | host sleeping despite work / wake latency |

Alongside it, the report gives:
- mean eligible workloads, kicks per frame and passes per frame;
- per guest wait site, the frame-thread time split by whether SPU work ran, only RSX work ran, both, or nothing ran. "Nothing" is wake latency or untraced work.

## 6. Dependency-chain findings

- **Guest dependencies (preserved):**
  - Havok task waves;
  - `JobBatch::Wait`;
  - PVS;
  - the Wws issued/done counters;
  - the RSX reference.
- **Host-introduced delays:**
  - maxContention stored as 1 (fixed, default-on);
  - the kick → pass delay (periodic 1 ms; opt-in T123/T123B fixes, never measured in game);
  - pass → lane wake;
  - usleep overshoot (520 µs for a 250 µs request).

See `CRITICAL_PATH_FINDINGS.md`.

## 7. Confirmed bottlenecks

| # | Bottleneck | Status |
|---|---|---|
| 1 | Wws on one lane (lineage without `b84ed80`) | VERIFIED; fixed by default in the unified runtime |
| 2 | RSX drain (vertex expansion, texture snapshot) on its host thread, once five lanes run | VERIFIED on T106; opt-in reductions (T122 epoch, T119 compact) unmeasured in combination. **Outside PPU/SPU**: by the brief's own completion rule, this is where effort should go if the trace confirms it |
| 3 | PRE (Havok waves + in-frame waits) | HYPOTHESIS: next gate after #2 |
| 4 | Frame-thread wake overshoot | PARTIAL: real per poll; share of the path BLOCKED |

## 8. Implemented optimizations

- **Scheduling, dispatch, PPU and SPU: none.**
  - No change has a measured rationale on the current runtime.
  - The existing candidates are already implemented as opt-ins:
    - T123 kick wake;
    - T123B event scheduler;
    - T121 `PS3_USLEEP_SPIN=2`;
    - T144 lane handoff (pending, a synthetic regression).
  - Only the game trace can choose between them.
- **Instrumentation (`ce32629`, opt-in via `PS3_CRITICAL_PATH_TRACE`):** kinds 35/36/37, the PT → trace bridge, and `cpath_report.py` guest-site and lane-idle sections. On a 768k-span race-sized synthetic trace the report runs in 27 s.

## 9. Correctness tests

- **Suite:** `t149/tools/run_all_t149.cmd` (a copy of T146's: every `tools/test_*.py` plus the C renderer tests). Timing-sensitive tests run serially. The run overlapped the end of T146's build.

  | Tree | PASS | SKIP | FAIL |
  |---|---:|---:|---:|
  | `ps3recomp-t149-critical-path` | 133 | 43 | 2 |
  | `ps3recomp-t149-base` (`80fe5de`, untouched) | 133 | 43 | 2 |

- The same two failures appear in both trees, so neither comes from T149:
  - `test_rt_pool_srv_layout`: "pool evicts only surfaces unused this frame";
  - `test_vpc_watch`: "the environment is read once".
- `test_spurs_kick_wake` failed on its first T149 run. Its source pin required the publish condition verbatim. The pin now accepts `&& !PS3_FT_ON()`, which still keeps the hook unset by default, and the test then passed: kick→done median, 2 seeds × 20 rounds.
- **SPURS, scheduler and timing tests** (all PASS in both trees):
  - `test_spurs_event_sched`, `test_spurs_scheduler`, `test_spurs_wkl_maxcont`, `test_spurs_admit`;
  - `test_spurs_wws_concurrency`, `test_spurs_wws_stress` (3 seeds × one lane and guest, 40 rounds);
  - `test_spu_exec_sse` (T136), `test_timer_usleep`, `test_vm_store_fast`, `test_ppu_trace`.
- **New tests:** in `test_cpath_trace`:
  - pins for every new hook;
  - a known-answer trace for the guest-site split (spu 10 / rsx 5 / none 5 ms) and for the lane-idle split (pick_to_run 0.9, kick_wait 3.0, no_work 5.6, capped 29.475 ms per frame, eligible mean 0.295).
- `test_ppu_lift` rewrites `scratch/ppu_conformance.*` (known since T146). It was restored in both trees and not committed.
- **Public audit:** `audit_public.py --staged` reports the 25 inherited BLOCKs only, none in T149's files.

## 10. Performance comparisons

| Kind | Result |
|---|---|
| Synthetic microbenchmark | trace off 0.18 ns per guard; trace on 40.8 ns per span |
| Scheduler stress | no scheduler change, so no comparison; the stress suites pass unchanged |
| Game critical path | not measured (no authorisation) |
| Game FPS | **no claim** |

## 11. Remaining bottlenecks

1. The RSX drain on its host thread, if the trace confirms it gates the unified runtime. That is renderer work, not PPU/SPU.
2. PRE: Havok waves and in-frame waits.
3. Frame-thread wake overshoot.
4. Wws jobs in the interpreter. The AOT exe block is not in `port/`.
5. Below 30 Hz the fixed 33.3 ms step runs slower than real time (unchanged; `PS3_SIM_PACE` stays off).

## 12. Runtime switches

- **New:** none. The new records ride on the existing `PS3_CRITICAL_PATH_TRACE=1 | <start s>:<seconds>[:<path>]`, which is unset and off by default. The guest-site spans need `PS3_TRACE_FILE` with `fn=` sites (`t149/ab/cpath_sites.cfg`).
- **Unchanged defaults:** T123B, T134, T144 (lane handoff not integrated) and every T146 default.

## 13. Integration instructions (T146 or the next unified baseline)

- `ce32629` applies to `integration/t146-unified-runtime` at `80fe5de` with no conflicts, because it is a child of it: `git cherry-pick -x ce32629`.
- Files: `include/ps3emu/ps3_ftrace.h`, `libs/spurs/cellSpurs.c`, `runtime/ppu/ppu_trace.cpp`, `tools/cpath_report.py`, `tools/test_cpath_trace.py`, `tools/test_spurs_kick_wake.py`.
- Possible conflict: T144's `ps3recomp-t144s` lane-handoff work also edits the coordinator pass and the PM worker in `cellSpurs.c`. Keep both hunks; T149's touch only the pass's start, its end and the kick hook.
- **Exe:** `build/motorstorm-t149`, built with `t149/tools/build_t149.cmd` (standard `port/`, T146 cache options). Built 19:31-19:40 on 2026-10-28, rc=0 (280 steps, `--parallel 11`); exe sha256 `57c22ad9065d23f3ef8a93ac667cd31d481b4179c224c07e3557141fa21e084b` (383.9 MB). VERIFIED: builds and links; never launched.

## 14. Bounded game A/B (authorised and run, results in §15)

- **Runner:** `t149/ab/run_t149ab.py`, generated by `t149/ab/make_runner.py` from the T145/T106 runner: same route, intro skip and controller; race entry = first `[rsx-hb]` with `last_draws >= 200`.
- **Limits:** stop at race entry + 90 s, hard cap 440 s, **4 launches**.
- **Every arm:**
  - sets T146's defaults explicitly (`preset_common`);
  - uses PT config `t149/ab/cpath_sites.cfg`;
  - runs `SPURS_BUSY_MS=1000 PS3_SC_WAIT_MS=1000 PS3_SPURS_SCHED_STATS=1000 RSX_FRAME_PERF=12,1,100000`;
  - runs no debug layer, no RSXI, and no `PS3_SIM_PACE`.
- **Trace window:** host s 175–240, which is race entry + about 12..77 s if entry falls at 161–164 s as in T145. The analysis flags a later entry.

| Arm | Env | Purpose |
|---|---|---|
| P0 | T146 defaults + trace | the unified runtime's real critical path |
| P1 | performance-test preset (epoch, compact, PSO cache, SRV reuse, bind dedup, event scheduler) + trace | what gates once the RSX drain shrinks |
| P2 | P1 + `PS3_USLEEP_SPIN=2` + trace | the frame-thread wake latency's share (CPU cost recorded) |
| P3 | P1, trace off | trace overhead and P1's FPS |

```
py -3 generated/analysis/t149/ab/run_t149ab.py prepare b
py -3 generated/analysis/t149/ab/run_t149ab.py launch P0 P0a      (then P1, P2, P3)
py -3 generated/analysis/t149/ab/ana_t149.py <rtdir> <run_dir>    # cpath + phases + spurs-sched JSON
py -3 generated/analysis/t122/ab/ana_t122.py <run_dir>             # FPS, frame-time spread
```

**Decision rules:**
- **If P0/P1 gate on `rsx`:** the next work is renderer (drain/expand), and SPURS is left alone.
- **If they gate on `spu`:**
  - `kick_wait` + `pick_to_run` large → dispatch; prefer the existing event scheduler if P1 beats P0 on PRE.
  - `no_work` dominant → guest dependencies; nothing to optimise in the scheduler.
- **If they gate on `idle`** (waits overlapping nothing): wake latency; P2 shows how much of it `PS3_USLEEP_SPIN=2` recovers, and at what CPU cost.
- Each arm gets 1 run within the 4-launch limit. Single runs are compared on phase means over about 300 frames, not on FPS alone.

## 15. Game A/B results (authorised 2026-10-28, 4 launches, run 20:17–20:35)

- **Setup:** exe sha256 `57c22ad9…a21e084b`, sequential launches with no build or analysis running alongside, and every arm reached the race (`controller_stop=race entry + 90 s`).
- **Data:** run dirs `generated/runs/20261028-*-t149-ab-p{0..3}r1`, JSON in `t149/ab/ana_p*r1.json`; both stay private and uncommitted.
- **Sample size:** one run per arm, so differences of a few ms are within noise until repeated (PARTIAL).

| Arm | Race FPS (`ana_t122`) | Frame (PT) | ref | PRE | emit | spin | Race entry |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 defaults + trace | 6.57 | 136.9 | 39.7 | 55.7 | 23.4 | 15.4 | ~149 s |
| P1 perf preset + trace | 7.29 | 121.3 | 26.4 | 50.1 | 19.4 | 23.0 | ~154 s |
| P2 P1 + usleep spin + trace | 7.21 | 121.4 | 27.0 | 44.1 | 22.7 | 25.2 | ~230 s |
| P3 P1, no trace | 7.07 | 123.8 | 26.1 | 51.1 | 20.2 | 24.2 | ~153 s |

**Critical path, from the trace (P0, P1; VERIFIED):**

| | P0 defaults | P1 perf preset |
|---|---|---|
| Frame-thread gate (frames gated by) | RSX + SPU both 306, RSX 55, running 1: **RSX dominant** | running 270, RSX 137, both 5, SPU 1: **PPU compute + RSX** |
| Frame thread running / blocked, ms per frame | 48 / 127 | 56 / 101 |
| RSX drain / record / tex snapshot, ms per frame | 157 / 43 / **79** | 106 / 84 / 1.3 |
| ref wait `0x72E1E0` (all on RSX) | 70 ms | 49 ms |
| `JobBatch::Wait 0x4AACA0` | 41 ms (38 overlapping RSX + SPU) | 36 ms (15 SPU only) |
| Wws spin `0x50C818` / PVS `0x5F74B0` / Havok `0x30B710` | 22 / 18 / 17 ms | 34 / 16 / 17 ms |
| SPURS lane busy (each of 5) | 34.5% | 42.3% |
| Lane idle per frame: no_work / kick_wait / pick_to_run / ready_unadmitted / capped | 111.6 / 1.7 / 0.65 / 0.09 / 0.12 ms | 89.4 / 0.22 / 0.54 / 0.06 / 0.09 ms |
| `[spurs-sched]` kick→admit p50/p95/p99 | 45 / 1218 / 2048 µs (periodic) | 19 / 861 / 1448 µs (event) |
| Host CPU per frame (PPU + RSX + SPURS lanes) | 79 + 153 + 304 ms ≈ 3.1 cores | 79 + 72 + 330 ms ≈ 3.1 cores |

**Findings:**
1. **SPURS dispatch is not on the critical path** (VERIFIED).
   - Of about 115 ms idle per lane per frame, at most 2.7 ms (P0) or 0.9 ms (P1, with the event scheduler) is scheduler-attributable (`kick_wait` + `pick_to_run` + `ready_unadmitted` + `capped`). The rest is `no_work`: the guest had nothing ready.
   - The event scheduler cuts `kick_wait` 8× (1.7 → 0.22 ms), but that cannot move a frame of 120+ ms.
   - Lane CPU time matches lane busy time, so the lanes do not spin.
2. **Default unified runtime (P0): the RSX gates the frame** (VERIFIED). Drain is 157 ms per frame, half of it (79 ms) the `PS3_TEX_SNAPSHOT` hash, the same cost T119 found. The guest's ref wait is the largest single wait (70 ms).
3. **Performance preset (P1): the RSX and the PPU frame thread's own compute (56 ms) gate together**; SPU-only waits are 17 ms per frame (JobBatch 15, PVS 9). The texture-snapshot epoch removes the 79 ms hash, and the frame shortens 15.6 ms (PT) or +0.72 FPS (PARTIAL, n = 1).
4. **`PS3_USLEEP_SPIN=2` (P2) is not justified** (PARTIAL).
   - The race frame is the same as P1 (121.4 vs 121.3 ms); PRE −6 ms is offset by spin +2 ms and emit +3 ms.
   - Loading to the race took about 76 s longer (entry about 230 s vs 154 s), so P2's trace window covers only about 10 s of race; its trace columns are pre-race and are not used above.
5. **Trace overhead:** P1 (trace) vs P3 (no trace) is −2.5 ms per frame, within single-run noise, so the overhead is not measurable at this sample size.
6. **Frame definitions differ:** `cpath_report`'s frame mean (P0 175 ms, P1 157 ms) is longer than the PT frame because its p95 includes flip stalls of 290–440 ms. Use the PT phases for frame time and the trace for attribution.

**Conclusion:**
- **No host SPURS/PPU-scheduling optimization is justified, and none was implemented.**
- **The next critical-path work belongs to the renderer:** drain and record; and making the T122 epoch/compaction preset the default, which needs its own correctness review.
- **After that, the PPU frame thread's compute.**
- **No change to any default.** The brief forbids FPS claims without game measurements; the FPS above are single-run measurements.

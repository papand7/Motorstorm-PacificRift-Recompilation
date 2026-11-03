# T134: MotorStorm Pacific Rift, PPU/SPU critical path

- **Branch:** `agent/t134-ppu-spu-critical-path` (worktree `ps3recomp-t134`).
- **Base:** T122 `2b639c2`; the tip is `b1ded1e`.
- **Not done:** no game build, no launch, no merge, no push.
- **Labels:** VERIFIED (measured), PARTIAL (measured in part, or on a sibling build), HYPOTHESIS (inferred, not measured).

## Answer in brief

1. **Why T122 runs at about 5 fps (VERIFIED).**
   - T122 sits on the renderer line (T113 `2562ba8`). That line never received the SPU-line commits T106 measured, including guest maxContention (`b84ed80`). So MotorStorm's Wws_Job workload runs on **one SPURS lane**.
   - All 23 T122 race runs have the same main-thread phase profile as T106's one-lane arm A:
     - frame 193–243 ms, with 0 ms waiting for the RSX;
     - about 100 ms in PRE, 60 ms in emit, 40 ms in the frame-end SPU-job spin.
   - The RSX thread is idle 114–168 ms per frame. The frame is SPU-gated, and the texture-snapshot fix could not move it.
2. **What follows once the lane limit is lifted (VERIFIED on T106's SPU line).**
   - Five lanes: 138 ms frames, with 47 ms of the frame thread waiting for the RSX. The RSX drain is the next gate.
   - T122's epoch and T119's compaction cut the drain from 77 to 15.6 ms (VERIFIED, one lane).
   - What remains on the PPU path is PRE + emit + spin + gap: about 91 ms without the SPU job AOT and about 49 ms with it (T106 B and D phases). Those are the next ceilings: about 11 and about 20 fps (HYPOTHESIS: upper bounds, not measured in combination).
3. **What T134 delivers.**
   - The SPU-line commits are carried onto the T122 renderer line as 26 cherry-picks (`-x`): 19 from the SPU line, 3 from T123, 3 from T123B and 1 from T121. This is the integration that removes the measured one-lane gate. The SPURS/SPU suite passes, but there has been **no game run of this combination** yet.
   - A streamed critical-path profiler, `PS3_CRITICAL_PATH_TRACE`, and an analyser, `tools/cpath_report.py`.
   - A runtime A/B plan whose runner is generated but has not been run.

## 1. Profiling methodology

### Existing evidence (no new launch)

- **Main-thread frame phases:** `t134/tools/phases_all.py` reads the `[PT]` trace that every T106 and T122 A/B run recorded (`ab_fps.cfg`).
  - It uses the T104/T106 definitions: frame = `0x72E1E0` entry to entry; ref = its duration; PRE = ref exit → first `0x50D868`; emit = first → last `0x50D868`; gap = → `0x50C818`; spin = `0x50C818` duration.
  - Window: race entry +5..+75 s, the same for every run.
  - Results: `t134/phases_all.txt` and `.json`.
- **SPURS lanes and syscall time:** `t134/tools/lanes_scwait.py` reads T106's `[spurs-busy]` (SPURS_BUSY_MS=1000) and `[sc-wait]` (PS3_SC_WAIT_MS=1000) lines, over 75 one-second reports. Results: `t134/lanes_scwait_t106.json`.
- **Renderer numbers:** T122's `ab/results.tsv` and `ab/ana_*.json`.

### New profiler (`392eb21`, `54c2662`, `b1ded1e`)

- **Basis:** it extends the existing `PS3_FTRACE` timeline (`include/ps3emu/ps3_ftrace.h`) instead of adding a second tracer.
- **Switch:** `PS3_CRITICAL_PATH_TRACE=1 | <start s>:<seconds>[:<path>]`.
  - Spans go into a bounded multi-producer queue, `PS3_FTRACE_CAP` cells (default 1M, 48 MB).
  - One writer thread drains it every 20 ms and flushes every `PS3_CRITICAL_PATH_SAMPLE_MS` (250 ms). A killed run therefore keeps its trace.
  - A full queue drops the span and counts the drop; a hook never blocks.
  - Off, a hook costs one load and a branch.
- **Timestamps:** QPC (monotonic, ns).
- **What is recorded:**

  | Kind | What it records |
  |---|---|
  | existing 1/2 | PPU syscalls ≥ `PS3_FTRACE_MIN_US` and merged usleep runs, per guest thread with the guest call site |
  | existing 3/4 | SPU channel waits and SPU busy time |
  | existing 5/6 | RSX semaphore acquires |
  | existing 7 | RSX drain passes |
  | existing 8/9 | flips (FIFO and guest request) |
  | existing 10 | presents |
  | existing 12 | GPU fence waits |
  | existing 26–30 | SPU job spans (`PS3_FTRACE_SPUJOB`) |
  | new 18 TEXSNAP | per-draw texture-snapshot time, KB hashed |
  | new 24 SPURS_PICK | coordinator admission: workload, lane, kicked |
  | new 25 SPURS_PM | a lane's policy-module residency, with its kernel polls |
  | new 32 HOST_CPU | per registered host thread and sample interval: run time from `QueryThreadCycleTime` (TSC-calibrated) and user+kernel time from `GetThreadTimes` |
  | new 33 RSX_RECORD | one D3D12 `render_frame` |
  | new 34 SPU_TASK | one asynchronous SPU task run |
  | new `H` lines | name host threads: PPU threads (guest tid), SPURS lanes, coordinator, RSX drain |

  Kinds 18, 24 and 25 keep the numbers the perf line (`agent/perf-integration-307b08a`, `agent/t25-perf`) already uses.
- **Analyser:** `tools/cpath_report.py`. A frame is the interval between two guest flip requests. Per frame it reports:
  - the frame thread's running, usleep and syscall time (by number);
  - how much of its waiting overlapped SPURS lane work, SPU tasks or RSX work. Each of these is a union over its threads; concurrent durations are never summed.
  - mean lanes busy;
  - host CPU per role (CPU time can exceed wall time on several cores, and is labelled as CPU);
  - a gate: running, spu, rsx, both or idle.

  The gate is an attribution by overlap, not a proof of causality. The output can be text, JSON, or per-frame JSONL.
- **Not covered:**
  - **Ready-but-not-scheduled time:** this needs ETW.
  - **Cache misses and memory bandwidth:** no hardware counters.
  - **Lock contention inside the host runtime:** only lv2 syscall time is visible.
  - **Guest PPU function profiles:** use the existing PT/`PPU_HOTMAP` tools.

## 2. Frame timeline and critical-path model

Main-thread phases (ms per race frame, means; `phases_all.txt`). The frame thread is guest tid 1 (`main`).

| Build / arm | Frames | Frame (p50) | ref (RSX wait) | PRE | emit | gap | spin (SPU jobs) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T106 A1/A2: one lane | 326/308 | 212/225 | 0.0 | 105/113 | 66/70 | 2.1 | 40/42 |
| **T122, all 23 arms** | 287–360 | 193–238 | 0.0–0.3 | 93–116 | 58–77 | 2.0–2.5 | 38–48 |
| T106 B1/B2: five lanes | 503/507 | 136/135 | 47.5/46.7 | 54 | 21 | 2.9 | 12.9/12.5 |
| T106 D1/D2: five lanes + SPU job AOT | 519/518 | 129/129 | 82.5/82.2 | 40 | 6 | 2.8 | 0.3 |

SPURS lanes and the frame thread's sleep (T106, race window; `lanes_scwait_t106.json`):

| Arm | Lanes busy (mean, of 5) | Wws_Job (wid1) lane time per frame | tid1 in `sys_timer_usleep` | Calls/s, mean |
|---|---:|---:|---:|---:|
| A1, one lane | 0.89 | 125 ms | 634 ms/s (63%) | 1189, 534 µs |
| B1, five lanes | 1.61 | 158 ms | 684 ms/s (68%) | 1308, 523 µs |
| D1, five lanes + AOT | 0.47 | 46 ms | 779 ms/s (78%) | 1488, 524 µs |

### Model

The frame thread runs, then waits on the guest's own primitives. The wait primitive is a spin plus `usleep(250)`; T121 measured it returning after 520 µs. The waits are:

1. PRE: SPU tasks and jobs: Havok taskset waves, `JobBatch::Wait 0x4AACA0`, `PVSComputerImpl::WaitForCompletion 0x5F74B0`.
2. emit and spin: Wws jobs (`0x50C818`, frame-end).
3. ref: the RSX reaching the previous frame's reference (`0x72E1E0`).

The frame ends at whichever producer finishes last.

- **T122 (one lane):**
  - The single lane is saturated (0.89 busy) and runs 125 ms of Wws work per frame.
  - The RSX is idle 114–168 ms per frame, and ref is 0.
  - **The gate is SPURS Wws admission to one lane.** The phase profile is VERIFIED across 23 runs. The lane occupancy is measured on T106 A (same one-lane admission), so PARTIAL for T122.
- **Five lanes (T106 B):**
  - Lanes busy rise to 1.61.
  - PRE + emit + spin fall by 123 ms, and ref rises to 47 ms. **The gate is the RSX drain** (VERIFIED, T106 B; RSX thread busy about 130 of 134 ms, `expand_ms` 107 ms).
- **Five lanes + AOT (T106 D):**
  - Wws lane time falls 158 → 46 ms per frame and the spin disappears.
  - Ref rises to 82 ms: the RSX gate, more clearly.

## 3. Ranked hotspots (critical-path ms per frame)

| # | Hotspot | Evidence | Size | Status |
|---|---|---|---|---|
| 1 | Wws_Job admitted to one SPURS lane (maxContention stored as 1) on the T113/T122 line | Phases A vs B; lanes 0.89 → 1.61 | PRE + emit + spin 211 → 88 ms (−123 ms); fps 4.67 → 7.15 (+57%, T106) | Integrated in T134 (default); not run in this combination |
| 2 | RSX drain (vertex expansion + texture-snapshot hashing) once five lanes run | ref 47 ms (B), 82 ms (D) | drain 77 → 15.6 ms with T119 + epoch (T122, one lane) | Epoch in T134 (opt-in); T119 a separate branch, applies cleanly |
| 3 | Wws jobs in the SPU interpreter | wid1 158 → 46 ms lane time per frame with AOT; emit 21 → 6, spin 12.5 → 0, PRE 54 → 40 | about 41 ms of the PPU path (B → D) | AOT build block only in `port-t106aot` (not in `port/`) |
| 4 | Frame-thread wake latency: `usleep(250)` returns after about 523 µs, 1300–1500 calls/s | `[sc-wait]`, T121 | The excess is about 270 µs per poll. Its share of the critical path is not separable without the new trace | T121 `PS3_USLEEP_SPIN=2` integrated (opt-in; costs about 0.99 of a core while sleeping) |
| 5 | SPURS kick → run latency | T123: p50 0.68 ms in game. Fixture: kick → done 15.5 ms → 48 µs with `PS3_SPURS_KICK_WAKE=1` | Small per kick, several waves per frame | T123/T123B opt-ins integrated |
| 6 | Image fingerprint per SPU task dispatch | T123 bench: 2.000 → 0.040 ms per frame (25 tasks) | 2 ms | Integrated (T123 default on) |

### Not on the critical path

- PPU guest compute, HLE dispatch and guest↔host memory translation (T121). tid1 is off-CPU for 63–78% of the frame.
- GPU waits: 0.00 ms per frame (T122).
- Allocation and copying: the snapshot copies are 0 in the race (T122).

## 4. Guest and host evidence

### Guest frame sites

Taken from the T104/T106/T132B maps; none is newly identified here.

| Address | What it is |
|---|---|
| `0x72E1E0` | ref throttle (one entry per guest frame; usleep(30), returns at `0x72E5C0`) |
| `0x50D868` | ExecutePushBuffer |
| `0x50C818` | frame-end SPU-job spin; jobs issued/done at `[r3+0x44C]` / `[r3+0x2560]` |
| `0x736770` | PUT flush |
| `0x4AACA0`, `0x5F74B0`, `0x30B710` | SPU waits inside the frame: JobBatch::Wait, PVS WaitForCompletion, Havok |

The main loop is `0x82358`, and `Timer::Step 0x435F28` has a fixed dt of 33,333 µs.

### SPU workloads

- **Instance and workloads:** SPURS instance `0x1003F180`; wid1 = Wws_Job (maxContention 5 from the guest); wid2 and wid0 are smaller.
- **Taskset:** Havok `0x16209480`, which runs about 25 asynchronous tasks per frame in 4 waves inside PRE (T123).

### Host threads (T121, five lanes)

- The RSX host thread uses 0.93 cores.
- tid1 uses 0.30.
- Each of the 5 PM lanes uses about 0.36.

Total CPU is far below the 9600X's 12 logical CPUs, so the SPU lanes are **not oversubscribed** (PARTIAL: whole-run averages, not per frame).

### Contradictions

- **Wait primitive (`0x4B63F0`):** T106 calls it a condvar spin; T121 calls it a LockFreeMutex back-off.
- **Main loop:** T106 uses `0x82688` as the race main loop; T132 gives `0x82358`, which contains it.

Neither changes the model above.

## 5. Implemented optimizations and integration

Carried onto the T122 renderer line as cherry-picks (`git cherry-pick -x`, original hash in each message). All applied without conflicts.

| T134 commits | From | What | Default | Measured effect |
|---|---|---|---|---|
| `66e5f5c`, `d9ce380` | `5fcb348`, `3bbeb5a` | SPURS_BUSY_MS lane accounting | off | diagnostic |
| `ce3741d`, `6f8a880`, `56301e5`, `57a8c32`, `e005379`, `8cf2360` | `33df4f7`, `d7fc0a9`, `a9679cc`, `6be362a`, `5e5666d`, `8f41c5c` | read maxContention; five-lane safety (contention bytes under the lock-line lock, per-worker TLS, four race fixes) | on | correctness for five lanes |
| `d884519` … `894bb09` (7) | `ff640c8` … `dc0af2d` | SPU job spans, relocatable WWS AOT runtime (selected only with an AOT build), ftrace arm | off / no AOT objects in `port/` | none without AOT |
| `531e6f4` | `df863f4` | `PS3_SPURS_READY_LEVEL=1` admission rule | off | — |
| `9d3152d` | `4a1ee48` | `PS3_SC_WAIT_MS` per-thread syscall time | off | diagnostic |
| **`1ee4268`** | **`b84ed80`** | **store the guest maxContention**; `PS3_SPURS_GUEST_MAXCONT=0` restores one lane | **on** | **+57% race fps on the SPU line (T106 A/B/B/A)** |
| `b10497f`, `1c97915` | T123 `6b8700b`, `044f766` | exact fingerprint memo; `PS3_SPU_FP_CACHE=0` opts out | on | 2.000 → 0.040 ms per frame (bench) |
| `49fe173` | T123 `e48f279` | `PS3_SPURS_KICK_WAKE=1` | off | fixture kick → done 15.5 ms → 48 µs |
| `1f31963`, `37e88f0`, `ea0ba12` | T123B `46fc26e`, `c57d792`, `77aeaf6` | `PS3_SPURS_SCHED_STATS`, `PS3_SPURS_EVENT_SCHED=1` | off | fixture p99 kick → done 1194 → 41 µs (T123B) |
| `3334464` | T121 `9dfe2ca` | `PS3_USLEEP_SPIN=2` (timer, then a spin tail) | off | usleep(250) 517 → 250.1 µs, at 0.99 CPU of wall |

T134's own commits:

| Commit | What |
|---|---|
| `392eb21` | PS3_CRITICAL_PATH_TRACE, the new records, `cpath_report.py`, `ftrace_report.py` compatibility, the tests |
| `54c2662` | the TEXSNAP span inside `vp_record_tex_snap`'s body, so T115B and T133 merge cleanly |
| `b1ded1e` | RSX_RECORD as a cleanup-scoped span inside `render_frame`, so the existing source pins keep reading the real body |

Each optimization keeps an opt-out or is opt-in, as in its source branch.

- **Not changed:** guest synchronization, waits, physics constants, simulation dt.
- **Kept:** T113 shader-span reads and T122 submission and fences, untouched.

**No new optimization of T134's own is proposed.** The next measurable gate after integration is inside PRE (Havok SPU tasks plus PPU) or the RSX. Telling them apart in the integrated build needs the new trace from a game run, and inventing a change before that would be guesswork.

## 6. Offline benchmark results (synthetic; not game fps)

| Benchmark | Baseline | T134 | Notes |
|---|---|---|---|
| Trace hook, off (`PS3_FT_ON()`) | — | 0.18 ns | `test_cpath_trace bench` |
| Streamed span (push + timestamp) | — | 43 ns | 200k spans, 0 dropped |
| Stream completeness | — | 4 × 20,000 spans, each exactly once, per-producer order kept | 0 drops |
| Full queue (64 cells, 100k burst) | — | written 64 + dropped 99,936 = emitted | counted in the trailer |
| Host CPU sampler | — | spinner 0.99 / sleeper 0.000 of wall (cycle time); spinner 1.00 (GetThreadTimes) | 50 ms samples |
| SPURS one lane vs guest maxContention (fixture) | peak 1 lane, mask 0x1 | peak 5 lanes, mask 0x1F; 900 jobs once each | `test_spurs_wws_concurrency` |
| Kick → done, inline kicks (fixture) | median 15,513 µs | 48 µs with `PS3_SPURS_KICK_WAKE=1` | `test_spurs_kick_wake` |
| Event scheduler (fixture) | — | kick → done p50 8 / p95 36 / p99 184 µs; 0 policy runs from 3.16M spurious wakes | `test_spurs_event_sched` |
| usleep(250) | 517 µs (T121) | 250.1 µs with `PS3_USLEEP_SPIN=2`; never early; CPU 0.99 of wall | `test_timer_usleep` |
| Fingerprint per frame | 2.000 ms | 0.040 ms | T123 bench; `test_spu_fp_cache`: 0 wrong of 32,000 concurrent lookups |

Memory: the trace allocates its queue only when on. The default is 48 MB, and `PS3_FTRACE_CAP` changes it.

## 7. Correctness and regression tests

- **Suite:** `t134/tools/run_suite_t134.cmd ps3recomp-t122 ps3recomp-t134`, which wraps `run_suite_t134.py`. It is a copy of T123B's list, plus `test_cpath_trace`, `test_tex_snapshot_epoch` and `test_rt_vis_trace`. Logs are in `t134/logs/final2/` and `suite_final2.txt`.
  - On `ps3recomp-t134`: every test PASS or SKIP. 0 FAIL (`logs/suite_final2.txt`). The 8 SKIPs are POSIX-only fixtures that skip identically on the T122 baseline; the T122 tree lacks the SPU-line tests (ABSENT).
  - `test_spu_reloc_job` links only through the suite's cc shim. A bare `clang` passes `-lm` on Windows, which is an environment limitation.
- **Compile check:** `t134/tools/tu_t134.cmd` compiles the changed TUs with the exact `build.ninja` flags and compares warning counts against base.
  - All files compile (rc=0).
  - `cellSpurs.c` and `spu_workload.c` gain 81 warnings each, all inside the newly included `ps3_ftrace.h`, of kinds every other ftrace user already shows.
  - The other files are unchanged (equal counts).
- **Public audit:** `audit_public.py --staged` lists only the 25 inherited items.
- **Merge checks** (`git merge-tree`, T134 tip):
  - Clean with T119, T115B, T120, T121, T131, T132B and T133.
  - T116: one backend conflict, inherited from T122.
  - T123B: conflicts expected; T134 already contains T123B as cherry-picks, and T123B's base carries old duplicate renderer commits.
  - `git diff 2562ba8 agent/t119-renderer-performance` applies cleanly to T134.

### Potential regressions

1. **Five lanes on the renderer line is a new combination.** The SPU-line safety commits come with it, and the stress and concurrency fixtures pass. The T106 game runs (0 NOSYS / spu-depth errors) were on the SPU line, not on this tree.
2. **`PS3_USLEEP_SPIN=2` spins.** It must be A/B'd against the five lanes and the RSX thread for cores.
3. **Trace volume and CPU.** The writer thread's CPU and file size need checking in the CT arm. The queue drops instead of blocking.

## 8. Runtime A/B plan (needs authorisation for builds and launches)

### Files

`generated/analysis/t134/ab/`: `build_b.cmd`, `build_c.cmd`, `make_runner.py` → `run_t134ab.py` (generated, not run).

- **Route:** T106/T122 (route, intro skip, controller, race entry = first 200-draw frame, stop at entry + 90 s).
- **Windows:** T122 `ana_t122.py` windows (+15..+85 s), plus `t134/tools/phases_all.py` and `lanes_scwait.py`.

### Exes

- **b** = this branch.
- **c** = b + the T119 diff (`git archive` + `git apply`, as T122 did).

Each exe is copied and sha-pinned.

### Arms

`RSX_GPU_SYNC=20`, `RSX_FRAME_PERF=12,1,100000`, `SPURS_BUSY_MS=1000` and `PS3_SC_WAIT_MS=1000` are set in every arm. The epoch is on in every arm except K2.

| Arm | Exe | Keys | Question |
|---|---|---|---|
| K0 / K1 | b | `PS3_SPURS_GUEST_MAXCONT=0` / default | Does guest maxContention reproduce T106's +57% on the renderer line? |
| K2 | b | K1 without the epoch | Does the epoch move the critical path once five lanes run? |
| C0 / C1 | c | as K0 / K1, + `RSX_VP_COMPACT=1` | Full integration: does the RSX stop gating (ref → about 0)? |
| CU / CW / CE | c | C1 + `PS3_USLEEP_SPIN=2` / `PS3_SPURS_KICK_WAKE=1` / `PS3_SPURS_EVENT_SCHED=1` | Wake-latency opt-ins once the frame is PPU/SPU-gated |
| CT | c | C1 + `PS3_CRITICAL_PATH_TRACE=120:300:cpath.txt` | Timeline: `tools/cpath_report.py cpath.txt --frames-out` (trace arm; not an fps arm) |
| IK0 / IC1 | c | C0 / C1 + `CELLMARK_IGPU=1` | The same on the 2-CU iGPU (not a Radeon 890M) |

- **Order:** K0 K1 K1 K0 C1 C0 C0 C1 (ABBA), then the opt-in arms twice each, then CT.
- **Acceptance:** an fps change larger than the A/B/B/A spread, and the frame-phase shift that explains it (ref, PRE, emit, spin).
- **Correctness checks per run:** 0 NOSYS, 0 spu-depth, 0 VPVB errors; 21 jobs per frame; Bink copies and torn frames as in T122.

## 9. Integration dependencies

- **T119** (`agent/t119-renderer-performance`): needed for the RSX drain to stop gating. It applies cleanly; exe c uses it.
- **The SPU job AOT build block** (`MSPR_WWS_AOT`, `port-t106aot`, lines 203–222 of `port-t70`; T106 `AOT_FEASIBILITY.md`). It is a port build change with private lifted inputs, and T106 measured hotspot 3 with it. `port/` is game-specific build configuration, so it was left untouched here.
- **T116** (PSO cache): one backend conflict, inherited from T122.
- **T132B** `PS3_SIM_PACE` (real-time fixed-step pacing): merges cleanly. Real-time gameplay independent of render fps needs it once the frame rate is below 30 Hz. It does not change the critical path.
- **The branch overlaps T123B** (now contained as cherry-picks). Integrate T134 rather than both.

## 10. Remaining bottlenecks

1. **After the lane limit and the RSX:** PRE (Havok tasks in 4 waves plus PPU) at 40–54 ms is the largest PPU-path term (T106 B/D). The CT trace will show whether PRE waits overlap SPU tasks (SPU-gated) or nothing (latency).
2. **Wws jobs in the interpreter (without AOT):** emit 21 + spin 12.5 ms.
3. **Frame-thread wake overshoot** from the 0.5 ms host timer tick.
4. **Below 30 Hz the simulation runs slower than real time.** It is a fixed 33.3 ms step per frame, and this is unchanged here; see T132B.
5. **No measurements yet of the integrated build:** fps, its spread, per-thread CPU, lanes busy.

## Commands

```
# evidence from existing runs
py -3 generated/analysis/t134/tools/phases_all.py            > generated/analysis/t134/phases_all.txt
py -3 generated/analysis/t134/tools/lanes_scwait.py generated/runs/*t106-ab-{A1,B1,D1}
# tests
generated\analysis\t134\tools\run_suite_t134.cmd ps3recomp-t122 ps3recomp-t134
generated\analysis\t134\tools\tu_t134.cmd libs/video/rsx_d3d12_backend.c libs/spurs/cellSpurs.c ...
python tools/test_cpath_trace.py                              (in ps3recomp-t134, CC=clang)
# A/B (not run: needs authorisation)
generated\analysis\t134\ab\build_b.cmd ; build_c.cmd ; py -3 generated/analysis/t134/ab/run_t134ab.py prepare b|c
py -3 generated/analysis/t134/ab/run_t134ab.py launch K0 k0a
python ps3recomp-t134/tools/cpath_report.py <run_dir>/cpath.txt --frames-out frames.jsonl
```

# T24: PS3Recomp performance, synchronisation and upstream audit (2026-10-25)

Offline only: no game launch, no change to any worktree or build, nothing merged or pushed. Scripts, benchmarks and outputs: `generated/analysis/t24/perf_audit/`. The concurrent inFAMOUSreborn compatibility audit by another session is `generated/analysis/t24/INFAMOUS_AUDIT.md`; the other `t24/` files are that session's.

## 1. Trees examined

| Tree | Branch / HEAD | State |
|---|---|---|
| `ps3recomp-t17` (secondary perf branch) | `agent/perf-integration-307b08a` @ `3b38721` | clean |
| `ps3recomp-t18iso` | detached @ `3b38721` | clean |
| `ps3recomp-307b08a` (= primary `motorstorm/v0.17-integration`) | detached @ `307b08a` | clean, read only |
| `ps3recomp` | `motorstorm/v0.15-local` @ `f373398` | 2 pre-existing modified scratch files, not touched |

All three findings in section 7 are present unchanged at `307b08a` (`rsx_d3d12_backend.c:5941/5962`, `sys_timer.c:274`, `ppu_sysprx.cpp:363`, `ppu_loader.cpp:1601`).

## 2. Upstream examined

- `https://github.com/whompay/inFAMOUSreborn`, HEAD **`2e9405c72408d28f505b6636a2f9cb6b6125aa85`** ("Renderer frame overlap", 2026-10-23).
- Read-only clone: `scratch/t24/infamous` (never built or run). Its bundled runtime is `ps3recomp/`; per the other session, its closest sp00nznet ancestor is `a679051`.
- **`2e9405c` itself (VERIFIED)** changes one line: `installer/infamous.toml` gains `RF_TRIPLE="1", RF_EARLY="1"`. It contains no code change.
  - `RF_TRIPLE` (`rsx_d3d12_backend.c:666-671`) gives 3 record parities, so the FIFO thread skips its wait for GPU N-1. Its own log string reads "perf207: no gain".
  - `RF_EARLY` (`:5357-5367`, needs `RF_TRIPLE`) runs the prepass before the render thread's `wait_for_gpu`.
  - Both only act on top of `RF_ASYNC` (default on, `:11593-11705`), the separate render thread that replays recorded frames.
- **MotorStorm (VERIFIED):** none of `RF_ASYNC/TRIPLE/EARLY`.
  - `render_frame` runs on the FIFO thread (`wait_for_gpu` `:6044`, `ExecuteCommandLists` `:7464`, `Present(1,0)` vsync `:7629`).
  - The loop in `port/main.cpp:205-269` uses a flat `Sleep(4)`.
- **Relevance to the 75 ms frame: none measurable.** The guest never waits on RSX or GPU progress during normal garage frames (section 5). The RSX thread runs at 0.48–0.64 cpu/wall and drains in 29–43 ms per 75 ms frame. Frame overlap can only lower present latency, not shorten the guest frame.

## 3. Source comparison (UP = upstream bundled ps3recomp, MS = `ps3recomp-t17`)

| Area | UP | MS | Assessment |
|---|---|---|---|
| sub-ms `sys_timer_usleep` | PAUSE spin ≤50 µs, `SwitchToThread` spin 51–999 µs (`sys_timer.c:270-306`) | per-thread high-resolution waitable timer for every request (`sys_timer.c:273-282`); `PS3_USLEEP_SPIN=1` restores the old spin (`:270-272, 295-313`) | **measured below** |
| `sys_lwcond` | real signal/broadcast, per-object buckets, 1 ms poll cap (`ppu_sysprx.cpp:497-799`) | signal/signal_all/signal_to are no-ops; wait = unlock, `Sleep(1)`, relock, timeout ignored (`ppu_sysprx.cpp:344-369`) | correctness and latency gap; MotorStorm imports all four |
| `sys_lwmutex` | CAS + `WaitOnAddress` (`PS3_LWM_FAST`) | semaphore, 2 kernel calls per lock/unlock pair (`ppu_sysprx.cpp:182-324`) | CPU cost only |
| guest loads/stores | `VM_FAST` early-out, `preserve_most` slow paths, `/GS-` + AVX2/MOVBE for lifted code | inline loads only while no read diagnostic is armed (`ppu_loader.cpp:1596-1608`); every store out of line with hooks (`:1997`) | see section 5, measurement validity |
| indirect calls / HLE | `PS3_ICALL_FAST` + 64 KB front cache; `PS3_HLE_CACHE` | env/diagnostic gates plus a hash probe per `bctrl`; uncached host→guest resolve per HLE call (`ppu_hle.cpp:294`) | CPU cost; unmeasured for MotorStorm |
| SPURS | 7–11 kernel threads, lanes, optional parallel lanes beyond `maxContention` | 1 coordinator + `nspus` slot workers, `active[wid] < maxContention` enforced (`cellSpurs.c:1745-1821`) | MS is closer to hardware; see section 4 |
| RSX/Present | render thread, 3 parities, `PRESENT_VSYNC=0`, kick-woken FIFO idle | synchronous on the FIFO thread, vsync Present, `Sleep(4)` | not on MotorStorm's critical path (section 5) |
| profiling | `PS3_PROF_MAIN` main-thread sampler with hitch ring, `FRAMEREC`, `HLESTAT`, `LANEPROF` | `PS3_FTRACE`, `PS3_SAMPLE`, `PS3_POLLTOP`, `PS3_TRACE` | MS lacks per-frame main-thread CPU attribution |

Licence: the upstream runtime is the MIT-licensed ps3recomp. Nothing was copied. Any port must keep attribution and be re-implemented against MS's own structures.

## 4. Runtime switch compatibility matrix

None of these names exists in MS or `port/` (grep, VERIFIED).

| Switch | UP implementation | Behaviour | Default (toml) | Guest-visible | MS equivalent | Risk / relevance to MotorStorm |
|---|---|---|---|---|---|---|
| `PS3_FAST_HOST` | `infamous-recomp/main.cpp:198,225,980-988`; `rsx_d3d12_backend.c:11582,14151` | process ABOVE_NORMAL, EcoQoS off; FIFO, render and VCACHE threads ABOVE_NORMAL | off (1). Any value, even `0`, enables it | no | none (only guest-priority <256 → ABOVE_NORMAL, `sys_ppu_thread.c:486-487`) | low; can starve the desktop. Low relevance: MS threads are not CPU-starved (2.2 of 12 CPUs busy) |
| `PS3_FAST_RUNTIME` | `spu_channels.c:800`, `spu_workload.c:943`, `rsx_d3d12_backend.c:13548` | skips SPU diagnostics/counters (dep notes, PUTLLC counters, lockguard) | off (1) | no | none (MS has different diagnostics) | low; not portable as-is |
| `PS3_PCORE` (+`PS3_PCORE_MIN`) | `ppu_loader.cpp:3858-3916` | `SetThreadSelectedCpuSets` to the highest EfficiencyClass, then priority; main HIGHEST | **on** (1) | no | none | medium; this machine is not hybrid-checked. Main is not preempted in the trace (cpu ≈ non-wait share) → low |
| `PS3_SPURS_PCORE` | `cellSpurs.c:2948-2963,4030-4036,4095-4104` | P-cores + ABOVE_NORMAL for wid 0 lanes/kernel; needs `PS3_PCORE≠0` | off (1) | no | none | low |
| `SPURS_LANE_OVERCOMMIT` | `cellSpurs.c:3043-3062` (used 4439) | runs more lanes of one workload than its `maxContention` | **on** (1) | **yes**: exceeds hardware contention | none; MS enforces `active<maxcont` (`cellSpurs.c:1771`) | **high**: the upstream comments record jobIndex races and a deadlock. Do not port |
| `SPURS_SEQ_LANES` | `cellSpurs.c:4421-4438` | for `maxContention≤1`, visits every virtual SPU lane so all WWS per-SPU rows advance | **on** (1) | yes | the slot model already rotates a wid over slots with fixed `spu_num` (`cellSpurs.c:1758-1799,1815`) | low; behaviour already covered |
| `SPURS_PAR_LANES` / `SPURS_PAR_SPUS` | `cellSpurs.c:1995-3171` / no reader | experimental parallel lanes "beyond the hardware" / dead switch | none / "0" | yes / n.a. | none | high / none |
| `SPURS_SPIN_US`, `SPURS_IDLE_WAIT_US` | `cellSpurs.c:4116-4249` | kernel idle spin then HR-timer naps woken by a kick event | 500 / 250 | timing | 1 ms timed CV in the coordinator (`cellSpurs.c:1751`) | low: MotorStorm kicks WWS through `cellSpursReadyCountStore` (developer build `JobArrayContainer::SetReadyCount` `0x2F07B0`; retail callers `0x726548`/`0x726638`), whose API unlock wakes the coordinator at once (`cellSpurs.c:510-514`) |
| `PS3_MAIN_CORE`, `PS3_FIFO_CORE` | `ppu_loader.cpp:3957-4172` | reserve a whole physical core (affinity enforcer thread) | on / off (1, 1) | no | none | medium; skipped below 20 logical CPUs anyway (this machine has 12) |

MotorStorm's SPU work (VERIFIED from `stdout.log`): one SPURS instance with `nSpus=5`. The four `Wws_Job` workloads (no name, EvoDefault, EvoHigh, LibMP3) are each added with `minContention=1, maxContention=1` (raw attribute `+0x24 = 1`), plus a taskset (22,553 `CreateTask` in a 125 s run).

## 5. The 75 ms garage frame: current understanding

Data: the four T18 traces (`PS3_FTRACE` 30–120 s, `MIN_US=200`) and `performance.json`; window 50–118 s; 875–900 normal frames per run. Scripts: `frame_phase.py`, `usleep_cost.py`, `thread_busy.py`, `thread_cpu.py`.

| Main thread per frame (median) | OFF4 | ON2 | Status |
|---|---|---|---|
| frame interval | 74.8 ms | 74.9 ms | VERIFIED |
| CV back-off (lr `0x94CCA8`) | 26.5 ms in 6 waits | 24.7 ms in 5 waits | VERIFIED |
| all traced waits | 29.1 ms | 27.5 ms | VERIFIED |
| silent stretch from last CV wait to the flip request | 21.3 ms | 21.5 ms | VERIFIED duration |
| remaining silent time between waits | ~24 ms | ~26 ms | VERIFIED duration, content unknown |

- **Main is CPU-busy when not waiting.** Host thread 19312 is the process's first thread (alone at t=0; the guest main thread has no `host thread started` line), averaging 0.61 cores over 52–118 s. Main's non-wait share is 61%. So the silent ~46 ms per frame is execution or spinning, not blocking. INFERRED mapping, VERIFIED numbers.
- **The `0x10CE8F40` Present spinner is on main** (INFERRED by elimination). HOTREAD fires inside the PPU `vm_read32` path. The only PPU thread with significant CPU is 19312; every other guest PPU thread has ≤0.02 cores, and the AsyncRenderThreads are not in the top 8. The spin (`0x50C818`, first call of `DisplayATG::Present`) waits for render-command job completion. At ~15 HOTREAD lines × 200,000 reads per frame, it is consistent with the 21 ms tail.
- **Critical-path reconstruction:**

| Stage | Duration | Blocking dependency | Overlaps with |
|---|---|---|---|
| main frame code | ~24 ms (VERIFIED total, contents unknown) | main CPU | SPU jobs, RSX drain of frame N-1 |
| CV waits for job batches | ~27–29 ms in 5–6 waits (VERIFIED) | SPU WWS jobs → `JobBatchHandler` poll (usleep 200) → CV gate poll (usleep 250) | main is blocked |
| Present spin on render-command jobs | ~21 ms (VERIFIED duration, INFERRED content) | SPU render-command jobs | main is blocked (spinning) |
| flip request → RSX drain → D3D12 encode → Present | 29–43 + 7 ms (VERIFIED) | runs on the RSX thread | **the next guest frame**: no guest wait on ref, labels, flips or GPU in normal frames (no `0x513Cxx` throttle or `0x72E5C0` ref sleep, no SEMA/GPU waits) |

- **Why removing ~14 ms of RSX preparation did not help (VERIFIED):** RSX work runs on another thread and overlaps the next guest frame. The guest frame is bounded by main's own code plus about 50 ms of waiting on SPU-side job completion. RSX was never on the critical path.
- **Unknown, and needed to go further:**
  - SPU execution time per job batch and per workload (the trace has no SPU spans: WWS policy modules never block on a channel for ≥200 µs);
  - dispatch-to-start latency;
  - what main computes in its ~24 ms.
- **Measurement-validity caveat (VERIFIED):**
  - Every T17/T18 perf run set `RSX_RTVIS=06A1E400,0x800,max=400` (manifests).
  - That sets `vm_inline_ok = 0` (`ppu_loader.cpp:1596-1608`), so every PPU load in those runs went through the diagnostic out-of-line `vm_read32`, including the hot-poll detector.
  - The 13 FPS baseline is therefore a diagnostic-configuration number. Main's ~24 ms of compute and the spin loops are probably slower than in a plain build (magnitude unmeasured).

### Long gaps (corrects T18)

- **All stalls are main waiting on the RSX `ref` (VERIFIED, static plus trace):**
  - Mechanism: `0x72E1E0` polls `[[toc+0x5AB8]]+8` (the control `ref`) against the target at `+0x98`, with `usleep(30)` and a timeout. Called from `0x72E5BC` after a `0xFEED` marker store.
  - Where it appears: every garage-entry stall in all four runs (38–41 s, ~0.5–0.9 s each) and both ON-only gaps (ON2 100.4–101.9 s, 2,837 sleeps; ON3 104.6–107.5 s, 5,460 sleeps).
- **ON-only gaps = `vp_vb_grow` (VERIFIED):**
  - Each ON gap starts right after `[VPVB] per-frame vertex buffer grown: 393216 -> 1048576 verts (512 MB, x2 parity)` (ON2 at 99.4 s, ON3 at 103.4 s).
  - Inside the gap there are no drains, no vblank beats and no presents, and the 1 s RSX heartbeat skips (99.4→101.6 s, 103.4→107.3 s).
  - The FIFO thread is inside the grow. It stays under the 3,000 ms `fc-watchdog` threshold, so no report.
  - **T18's statement that OFF1 also grew at 99 s is wrong:** OFF1's only VPVB line is the initial 192 MB allocation.
- **Root cause (VERIFIED by benchmark, `vpvb_grow_bench.c` → `vpvb_grow_bench_run1.txt`):**
  - `vp_vb_grow` (`rsx_d3d12_backend.c:5995-6027`) copies the current parity out of the old mapped UPLOAD buffer, which is write-combined.
  - A grow only follows a frame that overflowed, so the copy is always a full 96 MB parity.
  - On this machine that copy takes **3.3–4.1 s** (~25 MB/s); create + map of the 512 MB buffer takes 36–72 ms.
- **Trigger:**
  - Normal frames emit 305,607 vertices in all four runs, so the switches do not inflate vertex use.
  - Only the single 790-draw frame in each ON run reached the 393,216 cap (kind 17).
  - Whether that frame is tied to `PS3_VP_VCACHE`/`PS3_TEX_SNAPSHOT_SHARE` is still unproven (HYPOTHESIS: guest content timing).
  - The overflowing frame also drops its excess draws (by design, `vp_vb_budget.h`).

## 6. T22

- Not launched; no results exist (`generated/runs` has no `perf-t22` run; the T22 owner session confirmed this).
- The prepared `generated/analysis/t22/run_t22_diag.ps1` also sets `RSX_RTVIS` (`:72`) and `PPU_SPINBT`, so it inherits the out-of-line load overhead.
- `PPU_SPINBT` should still confirm the "spinner is main" inference above.

## 7. Three highest-value candidates

**C1. Remove the write-combined readback from `vp_vb_grow` (generic D3D12 backend fix; strongest evidence).**
- Source: `ps3recomp-t17` and `307b08a`, `libs/video/rsx_d3d12_backend.c` `vp_vb_grow` (`:5995-6027` / `:5941-5973`), bind at `:6778-6780`, recorder base `:8207-8245`.
- Change: do not `memcpy` from `vp_vb_mapped`.
  - Keep the old buffer (and `old_cap`) as this frame's replay buffer.
  - Bind it at `:6778` for the replay that follows.
  - Release it after the next `render_frame`'s `wait_for_gpu`.
  - New frames record into the new buffer.
  - The diagnostic readers at `:5629`, `:6925`, `:7162` must use the replay mapping for that one frame.
- Guest-visible: no; only host timing.
- Falsifiable hypothesis: a frame that overflows the per-frame VP buffer stalls the FIFO thread for ≤100 ms instead of 1.5–4 s. In a run with a grow, the heartbeat gap at the grow is ≤1.1 s and no `0x72E5C0` sleep run exceeds 200 ms after it. Reproducible offline: the benchmark's create+map path (36–72 ms) vs copy path (3.3–4.1 s).
- Regression tests:
  - extend the header-only `vp_vb_budget.h` model with a "retire after next idle" state (`tests/`, no GPU);
  - a D3D12 backend test that grows mid-frame and checks the replayed vertices come from the old buffer (WARP device).
- Effort: small (one function, one bind site, one release site). Risk: lifetime of the old resource; it must survive until the GPU fence for that frame.
- Related cheap mitigation (config, not a fix): raise the initial capacity above 393,216 (`MAX_VERTICES`) so the garage never grows. This costs upload memory.

**C2. Sub-millisecond `sys_timer_usleep` accuracy (generic, measured; already switchable).**
- Source: `runtime/syscalls/sys_timer.c:263-313` (HR-timer default; the `PS3_USLEEP_SPIN=1` spin path exists).
- Evidence:
  - Benchmark (`sleep_bench.c` → `sleep_bench_run1.txt`, 12 CPUs, `timeBeginPeriod(1)`): the HR timer returns after ≥506 µs for any request of 1–250 µs; the spin path is exact.
  - Traces: `usleep(200)` at `0x4AF6D0` costs 561–566 µs per call, `usleep(250)` at `0x94CCA8` costs 565–573 µs, garage `usleep(30)` at `0x72E1E0` costs ~525 µs.
  - Flag-detection latency for a poller: 379 → 115 µs (back-off) and 419 → 97 µs (`JobBatchHandler`).
- Hypothesis: with exact sub-ms sleeps, main's CV-wait total per frame drops by ≥2 ms (about 6 waits × ~0.6 ms saved on the chained `JobBatchHandler` → gate polls). The 0.5–0.9 s ref-wait stalls lose their 17× inflation of `usleep(30)`.
  - If FPS (gaps excluded) rises by less than the OFF-OFF spread of 0.02, the latency chain is not on the critical path and the hypothesis is rejected.
- Trade-off: v0.17 deliberately removed the spin because `JobBatchHandler` then held a whole core (CHANGELOG, `tools/test_timer_usleep.py`). A generic compromise would spin only for requests ≤ the timer floor and only up to a per-thread duty budget. Needs design review.
- First step needs no code change: an A/B with `PS3_USLEEP_SPIN=1` (needs launch approval).

**C3. Real `sys_lwcond` signal and timed wait (generic correctness fix, also latency).**
- Source: `runtime/ppu/ppu_sysprx.cpp:344-369`.
  - Signals are no-ops.
  - Every wait is unlock, `Sleep(1)` (~1–2 ms), relock, so waits have 1–2 ms latency.
  - The timeout argument is ignored and `ETIMEDOUT` is never returned.
- MotorStorm imports `sys_lwcond_create/wait/signal/signal_all` (NID check, VERIFIED). Which threads use them is not traced: lwcond is HLE, not a syscall.
- Hypothesis (weaker link to the 75 ms): producers that main waits on lose ≥1 ms per handoff. Falsify by adding an HLE call counter per lwcond site (or `HLESTAT`-style) first; if garage frames make <10 lwcond waits per frame, drop the priority.
- Implementation: per-lwcond waiter queue with a host condition variable keyed by lwcond EA, signal/signal_all/signal_to wake, honour the µs timeout via `lv2_usec_deadline`. Upstream `ppu_sysprx.cpp:497-799` is a design reference only.
- Tests: host unit test for signal-before-timeout, timeout returns `ETIMEDOUT`, `signal_to` the right waiter, mutex re-acquired with recursion count restored.

Not ranked:
- `SPURS_LANE_OVERCOMMIT`/`PAR_LANES`: exceed hardware contention.
- `RF_*` frame overlap: not on the critical path.
- Process/thread priority switches: main is not starved.

## 8. Offline tests and benchmarks run

| Item | Result |
|---|---|
| `perf_audit/sleep_bench.c` (built with the project's clang-cl 23.1.3 via `build_bench.cmd`) | HR-timer floor 506 µs for 1–250 µs requests; spin path exact; SRW CV 1 ms timeout mean 1.44 ms; detection latencies as above (`sleep_bench_run1.txt`) |
| `perf_audit/vpvb_grow_bench.c` (D3D12, default adapter, no game data) | 3 reps: 512 MB create 9.6–42.7 ms, map 24.7–29.8 ms, **96 MB copy from the old UPLOAD buffer 3,321–4,109 ms**, first touch of 416 MB 78–80 ms (`vpvb_grow_bench_run1.txt`) |
| Trace analyses on the T18 runs | `frame_phase.py`, `usleep_cost.py`, `thread_busy.py`, `thread_cpu.py` (outputs quoted above) |

No MotorStorm process was running during the benchmarks (checked with `tasklist`). Another Claude session was active on the machine, so the absolute times may carry some noise; the 40× gap between the copy path and the no-copy path does not depend on it.

## 9. Risks and unresolved questions

- The SPU side of the critical path (~50 ms of main waiting) is unattributed: job execution time vs dispatch latency vs completion polling. This is the largest unknown.
- Main's ~24 ms of compute is unprofiled. MS has no per-frame main-thread sampler.
- Every measured number includes `RSX_RTVIS` out-of-line loads. A clean baseline needs a run without read diagnostics.
- Whether the 790-draw overflow frame depends on the T18 switches (n=2 per arm).
- C1 must keep the old buffer alive exactly until the GPU has finished that frame. C2 trades CPU for latency.

## 10. Recommended next task (needs approval)

1. Implement C1 in an isolated worktree off `3b38721` (or `307b08a`), with the header-model test and a WARP backend test. Build in a new, uniquely named build folder. No launch.
2. With launch approval: one run without `RSX_RTVIS`/`PPU_SPINBT`, as a clean baseline, plus one run with `PS3_USLEEP_SPIN=1`. Both use `PS3_FTRACE` to test C2.
3. Add a SPURS policy-module run span to ftrace (`spurs_pm_worker`, `cellSpurs.c:1713-1743`: who = slot, a = image, b = wid), plus the time from the ready-count store to slot start. This attributes the ~50 ms of SPU-bound waiting before choosing further SPU work.

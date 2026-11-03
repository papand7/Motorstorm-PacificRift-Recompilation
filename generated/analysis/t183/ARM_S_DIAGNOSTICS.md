# T183 diagnostic arm S

One launch of arm S with the T183 runner, 2026-11-03. The frame is 70.4 ms. Of that, 25.2 ms is the Havok wait, 24.3 ms is post-Havok PPU work and 11.9 ms is the Wws spin.

- **Havok:** the tasks are compute-bound on the host. They are 97 % on-CPU and pick up within about 35 µs. Scheduling delay is not the cause.
- **PPU functions:** the run couldn't rank them, because the game exe never starts the sampler (section 5).
- **Strongest new lead:** the frame thread spends 5.9 ms per frame inside `cellSpursCreateTask`.

## 1. Executable

`build/motorstorm-t183/MotorStormPacificRiftRecomp.exe`:
- SHA-256 `c32cd09dd02447a6a4791af69a84c4aa653639f31ee5d3d8129a1324d6119b97`, 410,976,256 bytes;
- code `ps3recomp-t183` `766d3575`, as built for T183;
- not rebuilt or changed.

The runner copy `exe_r` has the same hash (manifest `exe_sha256`).

## 2. Preflight

All checks passed before the launch. VERIFIED.

| Check | Result |
|---|---|
| Session | `query session`: `>console … Active`; not RDP |
| Exe hash | runner pin = build = `exe_r` = `c32cd09d…9b97` |
| Game data | EBOOT.BIN `218cd8aa…94af`, PARAM.SFO `7cc3a4bd…608e`, EBOOT.elf `bbb7fe25…b287` |
| Free VRAM | runner 7,605 MiB at launch (≥ 6,000) |
| GPU workloads | no llama-server, Ollama or EA/Epic processes; the runner's open-app check at launch: only `leoffice`. Godot was open at the earlier manual check and had closed by launch |
| Arm S flags | `PS3_SAMPLE=2`, `PS3_SAMPLE_MAIN=1`, `PS3_SAMPLE_TOP=25`, `PS3_SPU_TASK_STATS=1000`, `SPURS_BUSY_MS=1000`, `PS3_SC_WAIT_MS=1000`, `PS3_HLE_WAIT_MS=1000`, on top of T182 B. Absent: ICALL_FAST, TASK_POOL, TASK_QUIET, VP_DIRECT, D3D12 debug, dumps |
| Outputs, limits | run dir `generated/runs/*-t183-Ss1`, runtime dir `t183/ab/runtime-s1-*`; PT config `t183/ab/cpath_sites.cfg`; timeout 205 s; stop at race + 75 s; warm T183 shader cache |
| One arm | the runner launches one arm per call; `launches_used.jsonl` was absent before |

**Preflight gap** (found afterwards): the check confirmed that the flags were set, not that the exe acts on them. See section 5.

## 3. Launch count

**1.** `run_t183.py launch S s1`, run `20261103-060252-t183-Ss1`:
- wall 114.6 s; race loaded at 38.8 s;
- the controller stopped it at race + 75 s, as intended. The wrapper reports `exited_error` (exit 1) because the controller stopped the process; T182 B ended the same way.

There were no retries, and B, C and other arms were not launched. `launches_used.jsonl` has one line.

## 4. Race FPS and frame times

Frames are `[PT]` tid 1 frames over the last 55 s, 781 frames with every phase marker present. Tool: `tools/arm_s_t183.py`. VERIFIED.

**Frame:** mean 70.40 ms (14.2 fps), median 69.91, p95 76.92, p99 84.26.

| Phase | ms | sd |
|---|---:|---:|
| ref throttle | 0.03 | 0.62 |
| before Havok | 0.81 | 0.13 |
| **Havok wait** `0x30B710` | **25.16** | 3.39 |
| **after Havok → first ExecutePushBuffer** | **24.28** | 1.62 |
| push-buffer emit `0x50D868` | 5.73 | 0.71 |
| gap | 2.44 | 0.31 |
| **Wws spin** `0x50C818` | **11.91** | 1.23 |

For comparison, the T182 timed arms ran at 68.4 ms. Arm S is 2 ms slower, plausibly from the four stats flags; that cost was not measured. `PS3_SAMPLE` never ran, so it did not slow the frames (section 5). The RSX is still off the path: 3,079 `[rsx-frame-perf]` lines, with `other_ms` about 35 of 72 ms, which is idle.

## 5. Top PPU functions: BLOCKED

`PS3_SAMPLE` printed nothing, not even `[samp] sampling every`. VERIFIED from the source:
- `ps3_sampler_start()` (`runtime/ppu/ppu_loader.cpp:743`) is called only from `runtime/ppu/tests/boot_main.cpp`;
- the game host in `port-t161` never calls it.

So no run of the game exe has ever sampled. RACE_FPS_CRITICAL_PATH.md §6 says "No new sampler code was needed"; that statement is wrong.

What the run does show about the 24.3 ms post-Havok window:

| Fact | Value | Label |
|---|---|---|
| Frame thread CPU (host thread with the most CPU, `cpu.jsonl`) | 38.1 ms per frame | VERIFIED |
| Frame thread blocked in syscalls and HLE (`[sc-wait]` + `[hle-wait]`, tid 1) | about 37 ms per frame, mostly `sys_timer_usleep` 21.5 ms (42 per frame) and `sys_event_queue_receive` 7.7 ms (12 per frame) | VERIFIED |
| Task creation placed by stderr order between `[PT]` markers (`tools/arm_s_place_t183.py`) | 15 tasks per frame created **after Havok**: raycast `308733018` ×5 and animation `406081863` ×10. Solver ×5.08 and collide ×5.08 are created inside the Havok wait | VERIFIED |
| `cellSpursCreateTask` on tid 1 | 284 calls/s, **297 µs per call, 84 ms/s = 5.9 ms per frame** | VERIFIED |
| Share of that in the post-Havok window | about 15/25 of the calls, so roughly 3.5–4.5 ms | PARTIAL: placed by order, not timed |
| Traced sites inside the window | JobBatch wait `0x4AACA0` and PVS `0x5F74B0` used up their 4,000-span limit before the race (2 usable frames). `0x222368` runs once per frame before Havok | VERIFIED |

The rest, about 20 ms, is PPU work on the frame thread that has no attribution. Whether one hotspot or many small ones dominate is unknown. Only a sampler can answer that.

## 6. Havok: CPU vs wall

From the `[spu-task-stats]` delta over the same 55 s, divided by the mean frame. On-CPU share is `cpu_cyc/fn_tsc`, and pickup is `run_ns − fn_ns`. VERIFIED.

| Image | runs/frame | ms per run | task ms/frame | on-CPU | pickup µs/run | MFC % of task | getllar/run | putllc fail | DMA gets/run |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| w1 solver `341580667` | 5.08 | 10.54 | 53.5 | 97.0 % | 30 | 10.9 % | 6,323 | 17.4 % | 610 × 339 B |
| w2 collide `491898574` | 5.08 | 10.73 | 54.5 | 97.5 % | 40 | 21.6 % | 477 | 4.9 % | 3,122 × 280 B |
| w3 raycast `308733018` | 5.00 | 0.55 | 2.8 | 96.7 % | 42 | 8.5 % | 12 | 0.5 % | 90 |
| w4 animation `406081863` | 10.00 | 0.53 | 5.3 | 96.9 % | 27 | 7.4 % | 19 | 2.9 % | 169 |
| **All four** | 25.1 | | **115.7** (112.5 on-CPU) | | 0.84 ms/frame in total | 18.2 ms/frame | | | |

How the 25.2 ms wait splits:

| Part | ms | Label |
|---|---:|---|
| Lifted SPU code running (w1 + w2, five parallel tasks each, one wave after the other) | about 21.3 | PARTIAL: the waves run in sequence by inference. Ten concurrent tasks would finish in about 11 ms, and they are 97 % on-CPU |
| of which MFC/atomic emulation inside the tasks | about 3.5 (solver 1.15, collide 2.32) | VERIFIED as `mfc_ns` |
| Creating the 10 tasks on tid 1 inside the wait | about 3 (10 × 0.30) | PARTIAL |
| Host pickup delay | about 0.07 | VERIFIED |
| Remainder (wake latency, `usleep` 0.5 ms tick) | about 1 | HYPOTHESIS |

**Classification: mainly compute, as executed by the lifted SPU code.** Host scheduling and descheduling are small: on-CPU 97 % and pickup about 35 µs. Lock contention is measured but bounded, because solver PUTLLC fails 17 % and all MFC work, retries included, is 11 % of solver time. Busy-wait in the solver is suspected but not separated: 6,323 GETLLAR per run is one every 1.7 µs, which looks like lock-line polling. The loop body between polls counts as task compute, so the size of that spin is unknown (HYPOTHESIS). This fits T158's result that codegen didn't move solver time. Sharing a core with an SMT sibling would also look like compute; that was not measured.

## 7. Wws: CPU vs wall

From `[spurs-busy]`, instance `0x1003F180`, 5 lanes, last 20 windows. VERIFIED unless labelled.

| wid | busy ms/s per lane | runs/s | runs that called `selectWorkload` |
|---|---:|---:|---:|
| 1 EvoDefault | 281–285 | 643–677 | about 440 |
| 2 EvoHigh | 50–52 | 284–328 | about 118 |
| 0 | 8 | 140–159 | 18 |
| 3 LibMP3 | 0.3–1.2 | 22–60 | 0 |

- Lane busy ≈ lane thread CPU: about 24 ms per frame each from `cpu.jsonl` (23.2–23.8). When a lane runs a policy module it is on-CPU, not descheduled.
- The lanes are idle about 66 % of the time.
- wid 1 keeps each lane busy about 20 ms per frame. That equals the push-buffer emit + gap + spin span (5.7 + 2.4 + 11.9 = 20.0 ms). It fits Wws job work saturating all 5 lanes from push-buffer emission to the end of the spin. **HYPOTHESIS**: this run has no per-frame PM timestamps (`PS3_FT_SPURS_PM` spans need the critical-path trace, which was off).
- **Classification of the 11.9 ms spin: probably Wws compute on the lanes (lifted Wws AOT), not starved lanes.** PARTIAL. Scheduling latency on the lanes was not measured in-frame.

## 8. Thread scheduling

Host CPU per frame, from `cpu.jsonl` over the last 14 samples (VERIFIED):

| Thread | CPU ms per frame |
|---|---:|
| frame thread | 38.1 |
| render thread | 32.4 |
| 5 SPURS lanes | 23.2–23.8 each |
| one other thread | 12.4 |
| all live threads | 217 |
| short-lived Havok task threads (missing from the live list) | 112.5 |

- Process total is about 330 ms per frame, about 4.7 of 12 logical CPUs on average.
- During the waves, about 5 task threads, the render thread and lanes are runnable together, which can reach about 12 threads on 6 cores / 12 SMT. The tasks still show 97 % on-CPU.
- Task pickup is small, but task **creation** is not: one host thread per run (`dispatch HIT (async) … spawning thread`). The 297 µs per `cellSpursCreateTask` call includes that, the context build and log lines.
  - The cost isn't split further: HYPOTHESIS.
  - The T183 bench caps logging at about 0.2 ms per frame, so logging is a minor part.

## 9. Critical-path timeline

All on tid 1, in sequence. The render thread and the RSX run alongside the whole frame and are off the path.

| Step | ms | Concurrent work |
|---|---:|---|
| ref throttle + before Havok | 0.8 | |
| Havok wait | 25.2 | create w1 ×5 → w1 solver 10.5 ms on 5 threads → create w2 ×5 → w2 collide 10.7 ms on 5 threads |
| post-Havok PPU | 24.3 | about 15 task creations (≈ 4 ms, PARTIAL); w3 raycast and w4 animation run (0.55 ms per task); about 20 ms of unattributed PPU work |
| push-buffer emit | 5.7 | Wws lanes busy (HYPOTHESIS) |
| gap | 2.4 | Wws lanes busy (HYPOTHESIS) |
| Wws spin | 11.9 | Wws lanes busy (HYPOTHESIS) |
| **Total** | **70.4** | |

Measured savings bounds:
- Task creation, if it dropped to zero: ≤ 5.9 ms per frame of tid 1 time; all of it is on the serial path.
- MFC emulation, if it were free: ≤ 3.5 ms of the Havok wait.

No other bound is measured.

## 10. Ranked opportunities

1. **Task creation on the frame thread: 5.9 ms per frame, measured, all serial.**
   - `PS3_SPU_TASK_POOL=1` (T156, parked workers) is already in this exe, off by default, and passes its tests. It removes the per-run thread spawn, which is the likely main part of the 297 µs.
   - It changes no guest-visible semantics.
   - Evidence: VERIFIED cost, HYPOTHESIS on how much the pool recovers.
2. **The unattributed ~20 ms of post-Havok PPU work.** It is the biggest single block, but it can't be targeted until a sampler runs in the game exe.
   - The fix is the missing call to `ps3_sampler_start()` in the game host: a diagnostic-only change, which this brief did not authorise.
3. **Havok waves 1-2: about 21 ms of on-CPU lifted SPU execution.**
   - MFC is ≤ 3.5 ms of it.
   - The rest is either real solver/collide work or a lock-line poll in the solver; an SPU-side probe is needed to tell which.
   - Physics behaviour must not change, so only a faster execution of the same code qualifies.

Wws is not ranked: it is a probable compute limit with no measured breakdown.

**Answer to the success criterion:** race FPS is limited mainly by **compute**, not by scheduling:
- lifted Havok SPU code, about 21 ms;
- unattributed hot PPU execution, about 20 ms;
- Wws on the lanes, about 12 ms (probable).

The one measured scheduling overhead is per-task creation, 5.9 ms.

## 11. Uncertainties

- The PPU function ranking is BLOCKED, because the sampler isn't wired into the game exe.
- Wave order (w1 then w2) is inferred from wall time against on-CPU time and T156 naming, not timed per wave.
- The phase placement of task creation is by stderr order. The 284 CreateTask calls/s against 356 `built` lines/s is not explained; some builds may be re-runs.
- The 297 µs per create is not split into thread creation, context build and logging.
- The solver GETLLAR rate suggests a lock-line poll, but the poll time is not measured.
- Wws lane activity is not tied to frame phases.
- SMT sibling contention was not measured.
- Arm S runs 2 ms slower than T182 B; that is from the stats overhead and from different runs.

## 12. Recommended next experiment

One launch, B + `PS3_SPU_TASK_POOL=1` only (no ICALL_FAST, no QUIET), with `PS3_HLE_WAIT_MS=1000` and `PS3_SPU_TASK_STATS=1000`, compared against arm S. This is arm C minus two flags, so it needs a runner arm change.

| Possible result | Next step |
|---|---|
| CreateTask time falls and the frame drops by up to about 5.9 ms | Make the pool the default after a stress run |
| CreateTask time doesn't fall | The cost is inside create, not the spawn; split it with a host timer |
| The frame doesn't move | The creation time overlaps; drop item 1 |

Separately, wiring `ps3_sampler_start()` into the game host (off unless `PS3_SAMPLE` is set) is the prerequisite for item 2. It needs a build and its own authorisation.

## Files

- `tools/arm_s_t183.py`: phases, task-stats deltas, SPURS/syscall/HLE waits, thread CPU.
- `tools/arm_s_place_t183.py`: task creation by phase.

Logs stay private under `generated/runs/20261103-060252-t183-Ss1` and `generated/analysis/t183/ab/runtime-s1-20261103-060252`.

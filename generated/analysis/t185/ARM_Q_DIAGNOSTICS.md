# T185 Arm Q: diagnostic run results

One authorized launch of T185 arm Q. No optimizations were implemented. Labels: VERIFIED, PARTIAL, HYPOTHESIS, BLOCKED. Impact classes (section 11): A means directly measured, B means a strong hypothesis, C means unverified.

## 1. Executable

- `build/motorstorm-t185/MotorStormPacificRiftRecomp.exe`, SHA-256 `ee2d6925d74e12e82555a84f91144e89a25eba7001f2a75c331ab5c26565019f`. The runner copy `generated/analysis/t185/ab/exe_r/` has the same hash.
- Code commit `ddda809a` (`ps3recomp-t185`), report commit `a57bfec`. The exe was not rebuilt or modified.

## 2. Preflight (all passed, nothing bypassed)

| Check | Result |
|---|---|
| Session | `>console` active (`query session`); `TerminalServerSession` False |
| Exe hash | matches the pin, in both build and runner copy |
| Game data | EBOOT.BIN `218cd8aa…`, PARAM.SFO `7cc3a4bd…`, EBOOT.elf `bbb7fe25…` |
| Free VRAM | 7,570 MiB (minimum 6,000); GPU 2 % busy before launch |
| Free RAM | 34.9 GB (minimum 16) |
| Conflicting processes | none (only LeOffice is open, which is allowed) |
| Other launchers or game instances | none (runner check) |
| Timeout and stop | wrapper `--timeout 205`, `TIMEOUT_S = 200`, `RACE_STOP` 75 s for each arm |
| Arm selection | the runner takes exactly one arm per call (`launch Q q1`); it has no loop over arms, `MAX_LAUNCHES = 3` |
| Storage | 16 GB free on C:; a launch needs about 0.46 GB of HDD copy plus at most 1.5 GB of cache growth |

## 3. Launch count

**1.** `launches_used.jsonl` has one entry: `{"tag": "Qq1", "at": "2026-11-03T07:45:44"}`. There were no retries, and arms N and L were not launched.

## 4. Runtime

- Run directory: `generated/runs/20261103-074545-t185-Qq1` (private).
- Wall time 114.6 s, host CPU 429.6 s (3.75 cores on average), peak working set 674 MB.
- The controller stopped the run at race entry + 75 s. The game process exits with code 1 at that stop, as T184 arm P did.
- No device-removed, Present-timeout or FIFO-resync lines.
- Log volume: 233,549 stderr lines and 22,794 `CreateTask` stdout lines.

## 5. Frame phases

Last 55 s of the run, 801 joined race frames. Tool: `generated/analysis/t183/tools/arm_s_t183.py` with `T183_TAG=Qq1 T183_SERIES=t185`.

| | Mean (ms) | Median (ms) | sd | T184 P |
|---|---:|---:|---:|---:|
| Frame | **68.63** (14.57 fps) | 68.23 | 3.64 (se 0.13) | 68.51 |
| ref | 0.07 | 0.01 | | |
| before | 0.80 | 0.77 | | |
| havok | 24.68 | 24.20 | 3.77 | 25.0 |
| after (post-Havok) | 22.96 | 22.83 | 1.40 | 23.0 |
| emit | 5.73 | 5.74 | | |
| gap | 2.43 | 2.43 | | |
| spin (`0x50C818`) | 11.94 | 11.69 | | 11.7 |

**Instrumentation overhead.** Frame time differs from T184 P by +0.12 ms, which is within one standard error. That is not a same-exe control, because arm N was not run, so the overhead is **not measurable** from this run. It is at most a few tenths of a ms if the exe change is neutral (HYPOTHESIS).

Host load:
- the process used about 4.7 of 12 logical CPUs (320.7 ms of thread CPU per frame);
- the whole system was 59.9 % busy;
- the CPU is not saturated.

## 6. PPU sampler validation (VERIFIED)

- **Setup.** The map loaded 53,278 PPU and 15,674 SPU entries. The `.pdata` self-check passed (`func_00010200 … start MATCHES`). It sampled every 2 ms, and all four phase sites were accepted.
- **Sample count.** One 10 s report: 4,556 samples, 4,552 (99.9 %) of them resolved to guest functions. The 55 s window holds 6 reports and 27,317 tid-1 guest samples.
- **Independent check.** The sampler's phase shares match the `[PT]` frame phases:

  | Phase | Share of samples | × 68.6 ms | `[PT]` phase |
  |---|---:|---:|---:|
  | havok | 34.7 % | 23.8 ms | 24.7 |
  | post | 33.3 % | 22.9 ms | 23.0 |
  | spin | 19.0 % | 13.0 ms | 11.9 |
  | emit | 11.7 % | 8.0 ms | 8.2 (emit + gap) |

  The samples are real guest-PC samples tied to the right phases.
- **Limitation 1: wall time, not CPU time.** When the thread is in host code (a syscall, `usleep`, a runtime helper), the sample goes to the innermost guest frame (`samp_stack_guest`). So a share is wall time, including blocked time, attributed to the guest function that called the host code.
- **Limitation 2: helpers can't be separated.** For the same reason, runtime helpers (`vm_read32`, the VMX lane helpers, `lv2_syscall`) cannot be split from guest code at sample level.
- **Limitation 3: truncated tail.** Only the top 40 rows of each report are kept, so the post phase's ranked rows cover 61 % of its samples.

## 7. Top PPU functions (tid 1, race window)

ms/frame = (function's samples in the phase ÷ the phase's samples) × the phase's ms (`tools/phase_rank_t185.py`). No symbols exist; the descriptions come from the lifted code (`generated/ppu-t173-staging/ppu_recomp_*.cpp`) and earlier reports.

| # | Address | Samples | Share | Phase: ms/frame | Lifted code / evidence | Likely responsibility |
|---|---|---:|---:|---|---|---|
| 1 | `0x0050C818` | 5,193 | 19.0 % | spin 11.94 | 93 lines, no syscall; polls `[r3+0x44C]`/`[r3+0x2560]` (T152) | frame-end busy wait for SPU Wws jobs (VERIFIED in T152) |
| 2 | `0x004B63F0` | 2,161 | 7.9 % | post 3.88, emit 1.57 | `stwcx` spin, then sc 141 `sys_timer_usleep` | guest wait primitive (T121/T149) |
| 3 | `0x0070D1C8` | 1,801 | 6.6 % | havok 4.69 | 113 lines, half-float compares and `fdiv`; calls `0x70C5F0`, `0x70C430` | numeric helper that tid 1 runs during the Havok window (PPU work, not waiting; HYPOTHESIS about what it computes) |
| 4 | `0x0002FB60` | 1,772 | 6.5 % | post 2.91, havok 1.34 | VMX: 7 `vmaddfp`, `vrsqrtefp`, 2 indirect calls | vector math (normalize/transform) |
| 5 | `0x00A482D0` | 1,172 | 4.3 % | havok 3.04 | 524 lines, one register-number `lv2_syscall`, 12× `0xA314D8` | job/semaphore manager in the Havok window (HYPOTHESIS: Havok-side job queue) |
| 6 | `0x00A499F8` | 1,162 | 4.3 % | havok 3.03 | 1,188 lines, `ppu_timebase_now` ×5, one syscall | same family as #5 |
| 7 | `0x00B500A0` | 1,091 | 4.0 % | post 2.75 | VMX 4-wide `vmaddfp` transform plus scalar FP min/max | vector transform / bounds (HYPOTHESIS: culling or bounds) |
| 8 | `0x00A48A18` | 528 | 1.9 % | havok 1.38 | 1,143 lines, timebase ×6, one syscall | same family as #5 |
| 9 | `0x006F69E0` | 441 | 1.6 % | havok 0.92 | 1,954 lines, sc 144; byte/half/word copies | serialization or copy routine |
| 10 | `0x00BCACE8` | 421 | 1.5 % | post 1.06 | 378 lines, FP and VMX, 4 indirect calls | game-engine math |

Also from the lifted code:
- `0x00A4C590` (havok 1.08 ms) is an sc 130 event-queue-backed counting semaphore wait.
- `0x00322D78` and `0x00323228` issue sc 141 sleeps.
- `0x00A4C7B8` issues sc 138 (`sys_event_port_send`).

**What fills the post-Havok 22.96 ms (PARTIAL).** No single function dominates:
- waiting in `0x4B63F0`: 3.9 ms;
- three vector/FP functions (`0x2FB60`, `0xB500A0`, `0xBCACE8`): 6.7 ms;
- `0x8CE850` (a 14-line wrapper calling `0x414858`): 0.9 ms;
- the remaining 39 % (about 9 ms) is a flat tail of functions under 0.2 ms each.

So it is **several functions plus a long flat tail of game-engine code**, with about 17 % of it waiting. There is no SPURS synchronization in that phase, and it is not rendering preparation (emit is a separate phase).

**Main-thread blocking (VERIFIED, `[sc-wait]` tid 1, per 1 s):**
- `sys_timer_usleep` (sc 141): 329.9 ms over 672 calls, **0.491 ms per call**;
- event-queue receive (sc 130): 99.2 ms over 180 calls;
- total: 429 ms/s, which is **29.4 ms per frame blocked** in syscalls;
- the spin phase is pure busy-polling (no syscall), so these 29.4 ms fall inside the before/havok/post/emit windows (56.2 ms): about half of tid 1's non-spin time is spent asleep.

## 8. Task creation latency (VERIFIED)

Source: `[spu-create-prof]` over 54 one-second windows.

| Stage (`libs/spurs/cellSpurs.c`) | µs per call | ms per frame |
|---|---:|---:|
| Total (mean / p50 / p95 / max) | **265.9** / 260.7 / 375.2 / 858.4 | **5.28** |
| `log` (stdout `printf`) | **249.1** (94 %) | **4.95** |
| `dispatch` (`spu_workload_dispatch_async`) | 13.3 | 0.26 |
| `trace` (`getenv("SPURS_TASKSET_TRACE")`) | 2.3 | 0.05 |
| `book` (mark running, `ts_lock`, exit, add) | 0.5 | 0.01 |
| `slot` (`spurs_taskset_take_slot`) | 0.4 | 0.01 |
| `elf` | 0.2 | 0.00 |
| `args` | 0.1 | 0.00 |
| unattributed `rest` | 0.1 | 0.00 |
| lock-line wait (inside slot + book) | **0.1** (0.2 waits per call) | 0.00 |

- There were 15,925 calls, 19.9 per frame, all on tid 1.
- The `[hle-wait]` count for NID `0xBEB600AC` independently shows 300 calls/s and 83.8 ms/s on tid 1, which is 5.75 ms per frame.

`dispatch` sub-stages (20,060 calls, including non-CreateTask dispatches): mean 13.3 µs, of which `fp` 5.5, `log` 4.2, `submit` 3.1, `job` 0.5; lock wait 0.

**Answer:** gameplay costs 262–266 µs against about 4 µs offline because of the **unbuffered stdout `printf`** into the runner's pipe (249 µs per call). It is **not** lock contention: 0.1 µs per call. This adds **4.95 ms of tid-1 critical path per frame**. `PS3_SPU_TASK_QUIET=1` (T185) removes the line; the saving is unmeasured until arm L runs.

## 9. Global lock-line contention

1. **Mutex.** It is a single process-wide spinlock, `g_lockline` (`runtime/spu/spu_coherency.c` `spu_lockline_lock`/`unlock`: an `_InterlockedExchange` spin). It protects reservation state and the coherence-context list for **every** guest address (VERIFIED, code).
2. **Users.** SPU GETLLAR/PUTLLC (`runtime/spu/spu_channels.c` `spu_mfc_atomic`), PPU coherent stores and reservations (`runtime/ppu/ppu_loader.cpp`), `libs/sync/cellSync.c`, `libs/video/cellGcmSys.c`, `libs/spurs/spurs_taskset.c` and `cellSpurs.c`. In total, 41 call sites take the same lock (VERIFIED, code).
3. **Acquisition rate.** The profiled lines total about 37,000 GETLLAR and 2,000 PUTLLC per frame, roughly **570,000 acquisitions per second**. Of these, 32,912 GETLLAR per frame come from one Havok poll line (VERIFIED, `[spu-llar-prof]`).
4. **Wait time.**
   - PPU task creation: measured at 0.1 µs per call (VERIFIED, negligible).
   - SPU threads: **not instrumented**. The probe is armed only on create-path threads, so SPU-side acquisition time and the protected-section time can't be separated in this run (BLOCKED in this run).
   - A rough upper bound: 570,000 × about 50–100 ns (a 128-byte copy and compare) is 3–6 % of one core held under the lock (HYPOTHESIS).
5. **Unrelated addresses.** Yes, they share the lock. The Havok solver line `0x16218E80`, the SPURS kernel lines `0x1003F180`/`0x10040200`, the animation line `0x12F17B80` and PPU coherent stores all serialize on one lock (VERIFIED, code).
6. **Havok polling and the lock.** Every unchanged poll takes and releases the global lock: 32,600 per frame. Whether that delays other lines' holders is not measured (B).
7. **Unnecessary serialization.** Architecturally yes: independent cache lines serialize on one lock. Measured impact on the PPU critical path: negligible. Impact on SPU tasks: unmeasured (B/C).

## 10. Havok ticket lock

Source: `[spu-llar-prof]`, delta over the last 55 s, image `341580667` (Havok solver).

| Line `0x16218E80` | Per frame | Per run (5.13 runs/frame) |
|---|---:|---:|
| GETLLAR | 32,912 | 6,416 (`[spu-task-stats]` reports 6,632) |
| unchanged | **99 %** | |
| poll episodes | 109.5 | 21.3 |
| iterations per episode | mean about 300, **max 3,694** | |
| PUTLLC on the line | 124.4 | 24 |
| **polling wall time** | **34.38 ms** | **6.7 ms of the 10.48 ms run (64 %)** |

- The solver task's function time is 53.74 ms/frame at 98.7 % on-CPU. So the polling is **host CPU burned in a busy loop**: about 0.5 of a core continuously (34.4 / 68.6).
- The collide image `491898574` polls the same line too: 1,364 GETLLAR/frame, 98 % unchanged, 1.62 ms/frame.
- Image `1297305682` episodes (16 ms/frame on `0x10040200`, `max_iters=1`) are **not** spins. They are single GETLLARs that stay open until the next atomic, and are excluded.
- **LS address mapping (PARTIAL).** The profile is per line, not per PC. The static T185 analysis found exactly one GETLLAR loop without PUTLLC or event wait in this image, at LS `0x1781C`. A 99 % unchanged line with about 300 polls per episode matches that loop, but a per-PC counter would be needed to confirm it.
- **Share of the 25 ms Havok wait (B).** On SPU threads, 64 % of solver run time is spent waiting for a ticket. That means the solver tasks are largely **serialized by the guest's own ticket lock**, and the poll cost is the symptom.
  - Whether the 24.7 ms PPU Havok window would shrink depends on why the lock is held so long: lock-holder work slowed by recompiled SPU code, or by the global lock. Neither is measured.
  - The polling itself does not starve the CPU (60 % system busy).

## 11. Confirmed bottlenecks and their class

| Issue | Class | Measured |
|---|---|---|
| Havok solver tasks spend 64 % of their run time polling one ticket line | **A** (time) / B (critical-path effect) | 34.4 ms/frame of SPU thread time |
| tid 1 blocked in guest sleep and wait syscalls; `usleep` returns after 0.49 ms on average | **A** (blocked time) / B (how much is avoidable latency) | 29.4 ms/frame |
| Frame-end busy wait for SPU Wws jobs (`0x50C818`) | **A** | 11.94 ms/frame |
| `cellSpursCreateTask` stdout logging on tid 1 | **A** | 4.95 ms/frame (249 µs/call) |
| Single global lock-line lock for all addresses | **A** (structure and rate: 570,000 acquisitions/s) / C (SPU wait cost) | PPU wait 0.1 µs/call |
| Post-Havok work is a flat profile of game code (no single hotspot) | **A** | top 3 compute functions 6.7 ms, tail about 9 ms |
| Per-call `getenv` in CreateTask | A | 2.3 µs/call, 0.05 ms/frame (minor) |

## 12. Unresolved hypotheses

- **Ticket-lock hold time (B).** The ticket lock is held long because the holder's SPU code runs slowly under recompilation, or because the holder's own atomics wait on the global lock. Needs a per-PC counter and a lock-hold timer.
- **Excess wake latency (B).** tid 1's 672 `usleep` calls per second return after 491 µs on average. If the requested sleep is 250 µs (T121), each hand-off detection is late by about 0.24 ms. That would put up to about 11 ms/frame of wait latency in the havok and post windows. The requested argument per call wasn't logged.
- **Havok-window PPU work (B).** tid 1 runs `0x70D1C8` (4.7 ms) and the `0xA48xxx`–`0xA49xxx` family (7.5 ms) during the Havok window. Part of this is real PPU work on the critical path, and part is semaphore/wait code. The sampler can't split running from blocked.
- **Generic PPU VMX cost (C).** VMX float ops are lowered to per-lane scalar loops with flush and fix (`runtime/ppu/ppu_vmx.h` `vmx_vmaddfp` uses `fmaf` per lane; the build has no `-mfma`). That may make the vector-heavy post-Havok functions (`0x2FB60`, `0xB500A0`, `0xBCACE8`) several times slower than they need to be. Not measured.
- **Diagnostic overhead (C).** Unknown without arm N.

## 13. Battlefield 1943 reuse

All of the following are in the shared `ps3recomp` runtime, not MotorStorm code.

- **Atomic reservations and the lock-line lock** (`spu_coherency.c`, `spu_channels.c`): one global spinlock and pure busy-poll GETLLAR loops. Any game that uses SPURS, the Havok PS3 job queue or SPU ticket/mutex primitives gets the same serialization and burned cores. A per-line (hashed) lock and a reservation-wait for unchanged GETLLAR polls would carry over directly.
- **Thread wake latency** (`lv2_syscall` `sys_timer_usleep`, event queues): guest spin-then-sleep wait primitives are common in PS3 engines, so host sleep granularity becomes frame time.
- **SPURS task creation** (`cellSpurs.c`): unconditional logging on a hot path. Rule: no unbuffered I/O on per-task paths.
- **PPU VMX lowering** (`ppu_vmx.h`): per-lane scalar emulation affects any VMX-heavy PPU code (Frostbite-era engines use VMX heavily) (C).
- **Diagnostics**: the phase-tagged sampler, the create profile and the LLAR profile are generic and reusable as they are.
- **Vulkan compute**: nothing in this run bears on it.

## 14. Recommended next optimization (not implemented)

1. **First, and cheapest: quiet the CreateTask logging.** Measured 4.95 ms/frame directly on tid 1's critical path; zero semantic risk; `PS3_SPU_TASK_QUIET=1` already exists.
2. **First structural change: reservation-aware waiting for unchanged GETLLAR polls.** For example, after N unchanged reads of a line, block the SPU host thread until that line is written (a write notification under the existing coherence path), then return the same data the poll would have read.
   - The guest still sees exactly the same values and ordering. No change to synchronization semantics, but it does change scheduling, so it needs an opt-in flag and a design review.
   - It targets the largest measured cost (34.4 ms/frame of SPU thread time) and is fully generic.
   - Pair it with a **hashed per-line lock** in `spu_coherency.c`, after per-thread wait counters show SPU-side contention.

## 15. Recommended next experiment

**Arm L** (already prepared: N + `PS3_SPU_CREATE_PROFILE=1` + `PS3_SPU_TASK_QUIET=1`), one launch:
- it measures what quiet logging buys per call and per frame;
- it gives a run without sampler or LLAR profiling, which bounds this arm's instrumentation overhead against Q.

After that, an offline change (needs authorization) to add:
- a per-PC GETLLAR attribution to confirm LS `0x1781C`;
- SPU-thread lock-line wait counters;
- a per-call `usleep` requested-versus-actual counter;

and then one more diagnostic arm.

## Files

- **Private run:** `generated/runs/20261103-074545-t185-Qq1/`.
- **Private analysis outputs:** `generated/analysis/t185/ab/analyze_q1.txt`, `phases_q1.txt`, `phase_rank_q1.txt`, `launch_q1.txt`.
- **Tool added:** `generated/analysis/t185/tools/phase_rank_t185.py`.

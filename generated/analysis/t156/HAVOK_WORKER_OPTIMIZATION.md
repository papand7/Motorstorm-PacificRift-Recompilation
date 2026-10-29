# T156: persistent SPU task workers and Havok execution costs

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. No game launch. Everything below is offline; synthetic speed-ups do not establish an in-game FPS change. Timeline and census: `HAVOK_CRITICAL_PATH.md`; game plan: `GAME_AB_PLAN.md`.

## 1. Result

- **`PS3_SPU_TASK_POOL=1`** (opt-in) replaces host thread creation per SPU task run with parked workers. On a model of the Havok chain calibrated to T154's in-game timeline, it removes **0.32–0.44 ms of a 16.7–18.1 ms chain at light host load** (5 runs × 200 frames, sd ≤ 0.04 ms). Under full CPU load it removes **11–14 ms p50 and about 120 ms p99**, where newly created threads wait milliseconds to run.
- **The pool is correct by test:** identical outputs to thread-per-task in Havok-shaped dependency waves, no queueing, no stale per-thread state, no lost wakeups, clean shutdown, and 20,000-run exactly-once stress. Three seeds, 2,020 checks each.
- **The large remaining cost is the lifted execution of the solver and collide images** (≈ 16.5 of the 18.9 ms chain).
  - The concrete next step is a `--chain-chunks` build of the task images: −83 % trampoline exits on the solver (T136), 5.2 → 1.1 ns per transfer on Bink.
  - It needs the MFC/atomic split from `PS3_SPU_TASK_STATS` in one diagnostic run first (§7).

## 2. Baseline

ps3recomp `e8e972a` (T154 = T153 checkpoint `2a764e1` + `PS3_SPU_WWS_STATS`). Game configuration T154 arm BA (Wws AOT on). Host: Ryzen 5 9600X (12 logical CPUs), clang-cl 23.1.3.

## 3. Proven sources of host overhead per task run (VERIFIED offline; production code paths)

Production `spu_workload_dispatch_async` → `CreateThread(256 MB reservation, detached)`, then on the new thread:
1. `SetThreadStackGuarantee`;
2. `calloc` of a 256 KiB local store, ELF load;
3. a 268,816-byte `spu_context` built on the fresh stack (`spu_run_lifted_job_abi`: context init and the LS copied in), then the lifted entry;
4. thread exit, which drops the stack from the reserver sets and releases the 256 MB reservation.

`tools/bench_spawn.c` (`logs/bench_spawn.txt`), unloaded host:

| Step | p50 | p95 | p99 |
|---|---|---|---|
| `CreateThread` call, 256 MB reservation + guarantee | 24.4 µs | 32.8 µs | 39.8 µs |
| caller → new thread running (previous thread already gone) | 54 µs | 81 µs | 106 µs |
| same, while earlier threads are still exiting (detached, as in the game) | 2.1 ms | 7.9 ms | 18.4 ms |
| hand-off to a parked worker: call / caller → worker running | 0.3 / 0.5 µs | 1.6 / 4.9 µs | 1.9 / 9.0 µs |
| `calloc` 256 KiB + touch + free | 1.7 µs | 1.8 µs | 1.9 µs |
| one dispatch log line, unbuffered `fprintf(stderr)` to a file | 2.7 µs | 3.1 µs | 3.9 µs |

The fingerprint of the task image is already memoised (`PS3_SPU_FP_CACHE`, default on), so it is not a per-run cost. The four log lines per task run (two on the PPU's creating path) cost about 3 µs each, and are left unchanged.

## 4. Implementation (`031bbb5`)

- **`runtime/spu/spu_task_pool.h`** (header-only, static functions; only `spu_workload.c` includes it in the runtime):
  - one SRW lock for the idle list and counters, one condition variable and job slot per worker;
  - submit takes an idle worker, or creates a new pooled thread with the same 256 MB reservation. **It never queues**, so every run starts at once and the run concurrency is exactly thread-per-task's. Havok's tasks wait on each other inside a run, and a bounded pool could deadlock them.
  - Wake under the lock, predicate re-checked under the lock: no lost wakeup, and no use-after-free of a worker that finishes and retires between unlock and wake.
  - Idle cap 32 (excess workers exit).
  - `spu_task_pool_shutdown(wait_ms)`: idle workers exit at once, busy ones after their run, later submits are refused.
  - A thread-creation failure returns 0 and runs nothing.
- **`spu_workload_dispatch_async`:**
  - the task is marked running and its r3 captured on the PPU before the hand-off, as before;
  - with the switch on, the run goes to the pool, except the cri image 22, whose EXIT handling counts per host thread;
  - a refused submit falls through to the unchanged thread-per-task path.
- **Fresh state per run:** after every pooled run the worker's stack leaves the lock-line reserver sets (as at thread exit), and `spu_channels_thread_reset` restores a new thread's per-thread SPU state:
  - resident-slot cursor and last AOT answer;
  - ftrace and Wws-stats job state;
  - trampoline, pc history, task-stats slot.

  The resident-slot cursor became a file-scope thread local so it can be reset; thread-per-task behaviour is unchanged. The halt `jmp_buf` is already saved and restored around every run.
- **Trace kinds 38/39 and 34.b** (`PS3_CRITICAL_PATH_TRACE`); **`PS3_SPU_TASK_STATS`** (`756c1e1`). See `HAVOK_CRITICAL_PATH.md` §5.

What the brief's requirements map to:
- **Concurrency limit:** unchanged (no queue).
- **CPU oversubscription:** never above thread-per-task's thread count; parked workers do not run.
- **Dependencies and ordering:** the guest's own (SPURS bitsets, the taskset exit path) are untouched.
- **DMA and memory visibility:** the hand-off is a lock release/acquire, and the payload test checks it.
- **Shutdown, wakeups, stale state:** tested (§5).
- **Fallback:** a refused submit uses the old path. Cancellation of a submitted run is not supported, as before: an SPU task run is never cancelled host-side.

## 5. Correctness (VERIFIED)

| Test | Coverage | Result |
|---|---|---|
| `tools/test_spu_task_pool.py` → `runtime/spu/tests/test_spu_task_pool.c`, seeds 1, 7, 12345 | Havok-shaped frames (150 per seed, 15 runs each): wave 1 from the main thread with random PPU delays, wave 2 submitted by each wave-1 run from its worker, wave 2 waiting inside the run for published wave-1 chunks, wave 3 after all wave-2 exits; outputs vs a serial reference and **pool vs thread-per-task identical**; dependency order checked per chunk | **2,020 / 2,020 per seed** |
| same | 100 rounds of 2–16 mutually waiting tasks (a queueing pool would deadlock); peak 16 in flight | pass |
| same | 2,000 sequential runs on one worker: thread_init once, after_run every run, **no run saw its predecessor's thread-local state**; negative control without the reset **detects it** | pass |
| same | 200 × 64 KiB payload written by a run, visible after its completion flag | pass |
| same | idle cap (8 → 2 workers); creation failure (not taken, nothing ran, no worker counted); shutdown with a busy run (it completes, all workers exit, later submit refused) | pass |
| same | 20,000 runs from 4 submitters with random delays: **every run executed exactly once** | pass |
| same | pins: switch exactly `"1"`, image 22 excluded, task marked running before the hand-off, refused submit → old path, reset hooks | pass |
| `tests/test_spu_task_stats.py` (real SPU runtime) | guest memory, LS, MFC/atomic state **byte-identical** unset / on / malformed; exact counts of GET, list GET, PUT, GETLLAR, PUTLLC success + failure, PUTLLUC, tag updates | 9 / 9 |
| `tools/test_cpath_trace.py` | kinds 34/38/39 pinned, numbers kept | 0 failures |
| Full suite | §9 | see §9 |

Randomised delays (spin, yield, `Sleep(0/1)`) run inside every task and between submissions in all frame and stress tests.

## 6. Offline performance (PARTIAL; `tools/bench_waves.c`, `logs/agg_waves.md`)

**Model.**
- The "PPU" creates wave 1 (5 tasks) one by one, with 0 or 250 µs of its own work between creations.
- The tasks drain a shared queue of 50 µs chunks: 37.5 ms of work, wave 1's measured Σ.
- Each wave-1 exit submits a wave-2 task from its worker (42.5 ms of work).
- The PPU then creates wave 3 (5 × 0.2 ms).
- Every run does the production prologue: 256 KiB LS `calloc`, 92 KiB ELF copy, 268,816-byte stack context.

**Method.** The pool is the runtime header; thread-per-task is the production `CreateThread` call. 5 runs × 200 frames per cell, after 10 warm-up frames. Values are the mean ± sd of each run's p50/p95.

**Calibration.** With a 250 µs gap the model gives a wave-1 start spread of 1.04 ms (game 1.09) and a wave-3 span of 1.35 ms (game 1.39).

| Metric | light load, gap 0: thread / pool | light load, gap 250 µs: thread / pool | 12 busy threads, gap 250 µs: thread / pool |
|---|---|---|---|
| Thread creation / hand-off on the caller (p50 / p95) | 10.8 / 64.4 µs → **1.4 / 2.4 µs** | 9.7 / 56.2 → **1.5 / 2.9 µs** | 12.5 / 47.6 → 2.0 / 227 µs |
| Dispatch latency, submit → task running (p50 / p95) | 93 / 183 µs → **4.8 / 9.4 µs** | 64 / 175 → **5.0 / 13.9 µs** | 3,983 / 10,111 → **4.0 / 735 µs** |
| Wave 1 span p50 | 7.643 ± 0.010 → 7.521 ± 0.005 ms | 8.101 → 8.030 ms | 17.04 → 15.07 ms |
| Wave 2 span p50 | 8.676 → 8.544 ms | 8.670 → 8.545 ms | 19.76 → 15.95 ms |
| Wave 3 span p50 | 0.413 → 0.211 ms | 1.347 → 1.210 ms | 6.74 → 1.22 ms |
| **Chain p50** | **16.698 ± 0.038 → 16.262 ± 0.006 ms (−0.44)** | **18.082 ± 0.012 → 17.764 ± 0.005 ms (−0.32)** | **43.2 ± 2.2 → 31.7 ± 3.0 ms (−11.4)** |
| Chain p95 / p99 | 16.84 / 17.70 → 16.35 / 16.99 ms | 18.33 / 19.71 → 17.94 / 19.69 ms | 56.0 / 191.7 → 43.7 / 64.8 ms |
| Completion → PPU sees it (p50) | 0.20 → 0.17 µs | 5.6 → 23.7 µs (*) | 288 → 91 µs |
| Process CPU per frame | 98.0 → 97.0 ms | 99.7 → 98.6 ms | dominated by the load threads |

(*) With a 250 µs gap the model's PPU is still inside its last gap when the pooled wave 3 has already finished. That is an artefact of the model, not a notification latency.

**Heavy load, no gap:** chain 43.0 → 29.1 ms; dispatch latency 4,262 → 3.7 µs p50.

**Without the production prologue** (`logs/agg_waves_noprologue.md`) the light-load savings are the same (−0.43 / −0.34 ms). So the gain is the thread lifecycle, not the stack faults of the 263 KB context.

**Stability.** The light-load deltas are 10–70 × the run-to-run sd. Under heavy load the sd is 1.5–3 ms, and the delta is still 4–8 × larger.

**Not measured offline:** memory synchronisation cost inside the Havok tasks (MFC/atomic). That is what `PS3_SPU_TASK_STATS` measures in game (arm D).

## 7. Remaining bottlenecks and the concrete next optimisation

1. **Lifted execution of the solver and collide images (≈ 16.5 ms of the chain).**
   - Static census (`HAVOK_CRITICAL_PATH.md` §6): 1,282 / 2,575 block exits through the drain trampoline, 16,212 / 26,146 register-file stores through `ctx`, small MFC footprint.
   - **Proposal C (`--chain-chunks` for the task images):** configure the game build with `-DPS3RECOMP_SPU_LIFTER_ARGS=--chain-chunks`. The relocatable Wws modules are lifted separately with `--reloc` and are unaffected.
     - The lifter, runtime support (`SPU_CHAIN`, budget, interrupt guard) and a regression test (`test_spu_chain.c`) exist since T136.
     - Before any launch: (a) lift and compile solver and collide with race flags (T136 did the solver: rc 0); (b) run `test_spu_chain` and the SPU suite; (c) build exe C.
     - Then A/B C against P on the same route with `havok_timeline.py`. HYPOTHESIS on gain: if block transfers are a large part of the dynamic mix, each 5.2 → 1.1 ns.
   - **After that:** a lifter register cache (keep `ctx->gpr` in locals inside a chunk), which removes the dominant register-file traffic.
2. **The PPU's serial task creation** (0.29 ms per task, ≈ 2.3 ms of chain time in waves 1 and 3). This is guest code, so not changeable here. Kind 38 will show the host share in game.
3. **MFC/atomic time inside the tasks:** unknown until arm D. If PUTLLC failures or GETLLAR polling are large, the lock-line path (T140, `spu_lockline_lock`) is the target, not the computation.

## 8. Integration-ready commits (ps3recomp, `agent/t156-havok-worker-optimization`)

| Commit | Switch | Default | Evidence | Revert |
|---|---|---|---|---|
| `031bbb5` PS3_SPU_TASK_POOL + trace kinds 38/39 | `PS3_SPU_TASK_POOL=1`; `PS3_CRITICAL_PATH_TRACE` (existing) | off | §5, §6 | unset the switch; `git revert` |
| `756c1e1` PS3_SPU_TASK_STATS | `PS3_SPU_TASK_STATS=<ms>` | off | `test_spu_task_stats.py` | unset |

**Off-path cost when nothing is set:**
- per task run: one `ps3_ft_on()` load, one `spu_task_pool_enabled()` load, one `spu_task_stats_now()` call;
- per MFC channel write: one thread-local load.

## 9. Runtime switches

| Switch | Values | Effect |
|---|---|---|
| `PS3_SPU_TASK_POOL` | exactly `1` | persistent workers for asynchronous SPU task runs (not image 22); anything else: thread per task, with a one-line warning if set to another value |
| `PS3_SPU_TASK_STATS` | `<ms>` | per-image task-run and MFC counters to stderr at most every `<ms>` |
| `PS3_CRITICAL_PATH_TRACE` | existing | adds kinds 38/39 and kind 34.b |

The name `PS3_SPU_TASK_POOL` follows the runtime's `PS3_SPU_*` convention and says what it covers: every asynchronous SPURS task run, not only Havok's. The brief suggested `PS3_HAVOK_WORKER_POOL`.

**Full suite and exe:** see §10.

## 10. Full suite and exe (VERIFIED)

- **Suite:** `tools/run_all_t156.cmd --jobs 3` on `ps3recomp-t156-havok-worker` at `756c1e1` gives **138 PASS / 43 SKIP / 2 FAIL** (`logs/suite_t156.txt`). The two failures, `test_rt_pool_srv_layout` and `test_vpc_watch`, are the known base failures; T153's base was 137/43/2, and the extra PASS is `test_spu_task_pool`. The suite's rewritten `scratch/ppu_conformance*` files were restored afterwards.
- **Separate tests:** `tests/test_spu_task_stats.py` 9/9 and `tests/test_spu_reloc_job.py` 91 PASS (same as T154). These `tests/*.py` are not part of `run_all`.
- **Exe:** `build/motorstorm-t156/MotorStormPacificRiftRecomp.exe`, built with `tools/build_t156.cmd` (log `logs/build_t156.txt`, rc 0):
  - size 411,172,864 bytes;
  - SHA-256 `04e64386829877c79fa86d6b0a4127cae6147deb8d360500fa324d41e2b68e3f`.
- **Not launched.** The game A/B (`GAME_AB_PLAN.md`) needs authorisation; the runner's sha pin must be set to this hash with `prepare w` first.

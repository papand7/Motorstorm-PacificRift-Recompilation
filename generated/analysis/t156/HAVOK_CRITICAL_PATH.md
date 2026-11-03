# T156: the Havok SPU critical path

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. No game was launched by T156. In-game numbers come from T154's four authorised runs (exe `e8386a74…`, `t154/ab/runtime-*/cpath.txt`), re-read by `tools/havok_timeline.py` (log `logs/havok_timeline_t154.json`).

## 1. Baseline

| Item | Value |
|---|---|
| ps3recomp | `agent/t156-havok-worker-optimization` from **`e8e972a`** (T154 = T153 checkpoint `2a764e1` + `PS3_SPU_WWS_STATS`) |
| Root | `agent/t156-havok-performance-report` from `334e173` (T154 report) |
| Game configuration | T154 arm BA: T153 COMMON + PERF + T150 + `PS3_SPU_WWS_STATS` + `PS3_SPU_WWS_AOT=1`, exe built with `MSPR_WWS_AOT=ON` |
| Havok images | wave 1 `0x145c1b7b` = solver (image `341580667`, lift `spu_45c1b7bf…`); wave 2 `0x1d51c6ce` = collide (`491898574`, `spu_d51c6ceb…`); wave 3 `0x1266e45a` = raycast; wave 4 `0x18345147` = animation (T136 names) |

## 2. Timeline of one simulation frame (VERIFIED, T154 BAr1/BAr2, 217 chains each, medians)

| Wave | Who creates the tasks | tasks | start spacing | start spread | longest task | Σ task time | Σ/5 (ideal with 5 lanes) | span | end spread |
|---|---|---|---|---|---|---|---|---|---|
| 1 solver | PPU main thread, one `cellSpursCreateTask` after another | 5 | 0.29 ms | 1.09–1.10 ms | 8.59–8.61 ms | 39.3–39.5 ms | 7.85–7.90 ms | 8.99–9.12 ms | 0.96–0.99 ms |
| 2 collide | each wave-1 exit (taskset exit path, on the exiting task's thread) | 5 | 0.13 ms | 0.95–0.97 ms | 8.77–8.79 ms | 42.1 ms | 8.41–8.43 ms | 8.78–8.82 ms | **0.04–0.05 ms** |
| 3 raycast | PPU, after all wave-2 runs exited | 5 | 0.30 ms | 1.20 ms | 0.79–0.82 ms | 1.8 ms | 0.36 ms | 1.37–1.39 ms | 0.70 ms |
| **chain (wave-1 first start → wave-3 last end)** | | | | | | | | **18.9–19.0 ms** | |

Reading the columns:
- **Wave 1 is fixed work per task.** The end spread equals the start spread, so a task that starts 1.1 ms late ends 1.1 ms late.
- **Wave 2 drains a shared queue.** All five tasks end within 50 µs whatever their start, so its span is the shared work (≈ 8.4 ms) plus a little.
- **Wave 3 is creation-bound.** Its tasks run 0.15–0.8 ms, but the PPU creates them 0.30 ms apart, so 1.2 of its 1.4 ms are the creation sequence.
- **The chain is 18.9 ms in game against 17.5 ms of PPU Havok wait** (T154). The PPU starts waiting after it has created wave 1.

The spans do not add: wave 2 starts while wave 1 is still finishing. That is why the table gives per-wave spans and a separately measured chain.

## 3. Where the 18.9 ms go

| Part | ms | How established | Status |
|---|---|---|---|
| Lifted SPU execution: the solver's 7.9 ms share + collide's 8.4 ms share + raycast's longest task | **≈ 16.5** | Σ task time / 5 lanes, T154 trace | VERIFIED as an upper bound of computation plus whatever MFC/atomic time the tasks contain (split: BLOCKED, needs `PS3_SPU_TASK_STATS`, arm D) |
| Creation spacing of waves 1 and 3 (PPU, 0.29–0.30 ms per task) | ≈ 2.3 of chain time (1.1 + 1.2) | start spread, T154 trace | VERIFIED as time; its host share is below |
| Host dispatch per created task (thread creation, hand-off) | 0.011 ms p50 / 0.064 ms p95 on the creating thread | `bench_waves`, production dispatch pattern, light host load | PARTIAL (offline) |
| Thread start + first-run stack faults per task | 0.06–0.09 ms p50, 0.18 ms p95 (light load); **4 ms p50 / 10 ms p95 with all 12 logical CPUs busy** | `bench_waves` dispatch latency, `bench_spawn` | PARTIAL (offline) |
| Wave handoffs (exit → successor running) | < 1 ms (T154); wave 2 starts 0.13 ms after each wave-1 exit | T154 trace | VERIFIED |
| Completion → PPU sees it | 0.2 µs p50 offline; T154: SPURS handoffs in µs | `bench_waves`, T154 §2 | VERIFIED (T154) / PARTIAL |

**The PPU's creation spacing is mostly guest time (HYPOTHESIS).** Offline, the host dispatch path costs 11 µs p50 per task (64 µs p95) on the creating thread, against 290 µs of spacing in game. So at least about 75 % of the spacing is the PPU's own code between `cellSpursCreateTask` calls.
- Supporting evidence: the offline model with 250 µs of PPU work per creation reproduces the game. Wave-1 start spread is 1.04 ms (game 1.09) and wave-3 span 1.35 ms (game 1.39).
- In-game proof needs kind 38, which times every dispatch on the caller's thread (§5).

**Thread-per-task under a busy host.** With all 12 logical CPUs busy, a newly created thread waits about 4 ms to run (p50). A parked thread that is woken runs in about 4 µs. The in-game spacing (0.29 ms) shows the light scene is not in that regime.

## 4. How much of the 17.5 ms can be removed

| Mechanism | Removable | Status |
|---|---|---|
| Host thread creation, start and stack faults (`PS3_SPU_TASK_POOL=1`) | **0.3–0.45 ms per chain** at light host load (offline, model calibrated to the game's chain); 11–14 ms (p50) and 120 ms (p99) when every CPU is busy | PARTIAL; in game BLOCKED (arm P) |
| PPU creation spacing (guest code between `CreateTask` calls) | none without changing guest code; out of scope | — |
| Lifted solver/collide execution (≈ 16.5 ms) | the only large lever; size unknown until the MFC/atomic split (arm D) and a `--chain-chunks` arm are measured | HYPOTHESIS |

**So persistent workers recover only a small part of the Havok wait** (≈ 2–3 % at the game's measured load). The wait is the lifted execution of the two physics images.

## 5. Instrumentation added for the game run (opt-in, read-only)

| Switch | Records |
|---|---|
| `PS3_CRITICAL_PATH_TRACE` (existing) | kind 34 task run, **b = dispatch → pick-up µs** (T156); **kind 38** = dispatch on the caller's thread (thread creation or pool hand-off), b = task id \| path << 8; **kind 39** = lifted entry call → return, b = pick-up → entry µs (local store, ELF load, task context) |
| `PS3_SPU_TASK_STATS=<ms>` | per image: runs, run / entry host time, longest entry, MFC GET/PUT commands and bytes, list commands, GETLLAR, PUTLLC and failed PUTLLC, PUTLLUC, tag updates, host time inside MFC requests |

Together they give every row of the brief's Phase A list, per task:
- guest submission and host dispatch (38);
- waiting to execute (34.b);
- AOT entry and execution (39);
- DMA and synchronisation inside execution (task stats: MFC/atomic counts and time);
- completion bookkeeping (34.t1 − 39.t1);
- PPU resume (existing kinds 1/2 of the frame thread and the `0x30B710` site span).

`tools/havok_timeline.py` reads kinds 34/38/39 when present.

## 6. The lifted Havok images (static census, `tools/spu_census.py`, `logs/spu_census.txt`)

| | solver (wave 1) | collide (wave 2) | solver with T136 `--chain-chunks` |
|---|---|---|---|
| lifted functions / statements | 959 / 20,361 | 1,766 / 32,861 | 983 / 23,846 |
| block exits through the drain trampoline | **1,282** | **2,575** | **217** |
| brsl calls (`spu_drain_call`) / indirect branches | 255 / 10 | 529 / 118 | 255 / 10 |
| LS loads / stores | 3,886 / 2,077 | 5,890 / 3,483 | inline `_ls` group forms |
| float ops / shuffles-rotates | 2,066 / 3,835 | 2,300 / 5,506 | same |
| MFC commands / tag waits / atomic-status reads / decrementer reads | 83 / 56 / 16 / 36 | 77 / 45 / 30 / 19 | same |

What the census shows:
- **The MFC footprint is small.** There are 83 command sites against 20,000 statements. The SSE vector and LS paths are already in the base (T136 commits `47e7538`, `28691bf`, `0af0496`, `29df355`).
- **The largest remaining generated-code mechanism is block transfers through the trampoline.** Each block exit returns to the drain loop and costs about 5 ns (T136, Bink chainbench).
- **`--chain-chunks` is the fix for that.** It is in the tree (`a049a8f`) but not enabled in any build (`PS3RECOMP_SPU_LIFTER_ARGS` unset). It removes 83 % of the solver's trampoline exits, and T136 measured 5.2 → 1.1 ns per transfer on Bink.
- **Next:** guest registers live in `ctx->gpr` memory (16,212 assignments in the solver), and a lifter register cache is the step after that.

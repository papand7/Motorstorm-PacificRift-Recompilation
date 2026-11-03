# T123: SPU execution and DMA performance (2026-10-28, offline)

No build, no launch, no merge or push. No other agent's worktree was modified. No RSX, D3D12, audio or guest-timing change.

## 1. Base
- Worktree `ps3recomp-t123`, branch `agent/t123-spu-execution-performance`.
- Base **`b84ed80`** (`agent/t106-ab-maxcont-default`, the tree in `ps3recomp-t109`).
- Ancestry, all VERIFIED with `git merge-base --is-ancestor`:
  - T109's tip `4a1ee48`;
  - T106 `8f41c5c` (four races) and T104 `d7fc0a9`;
  - plus the guest maxContention default.
- This is the exact source of the T106 C/D A/B exes.
- It does **not** contain T113, T119, T121 or T122. Their merge base is `8ea1437`. No merge was made.

## 2. Existing T106/T109 status (VERIFIED in the T106 A/B, `t106/ab/AB_RESULTS.md`)

| Feature | Activation | Measured |
|---|---|---|
| Five lanes (guest maxContention) | default since `b84ed80`; `PS3_SPURS_GUEST_MAXCONT=0` restores 1 | 4.55 → 7.17 fps |
| WWS relocatable AOT (31 modules) | needs `MSPR_WWS_AOT` at build time (`port-t106aot`, not in `port/`). Once built it is on; `PS3_SPU_WWS_AOT=0` disables it | 7.15 → 7.43 fps; SPU busy lanes 1.68 → 0.48 |
| `PS3_SPURS_READY_LEVEL=1` | opt-in | never run |
| `PS3_SPU_WWS_AOT_VERIFY=1` | opt-in; was on in arm D | about 0.5 ms/frame (T106) |
| Havok/animation tasks | already lifted whole-ELF images (`spu_workloads.c`), run by `spu_workload_dispatch_async` | not an AOT target; already native |

## 3. SPU critical path with five lanes and AOT (T106 run D1; no new tracing; `tools/spu_window.py`, `tools/task_phases.py`)

Per frame (D1 race window, 491 frames): median T 129 ms = ref 80 + PRE 40.6 + emit 5.9 + gap 2.8 + spin 0.

| Finding | Class |
|---|---|
| The frame is **RSX-bound**: the frame thread waits 80 ms per frame in the ref throttle | VERIFIED (T106) |
| **WWS jobs are off the critical path:** spin 0, 0 jobs outstanding at spin entry, 0.48 SPU lanes busy | VERIFIED |
| **All 25 async SPU tasks per frame run inside PRE.** The last SPU line before the first ExecutePushBuffer is an animation task end in **491/491 frames** (482/483 in C1, 483/483 in B2) | VERIFIED (order) |
| They are the Havok taskset `0x16209480` in 4 waves: 5 × solver `341580667`, 5 × collide `491898574`, 5 × raycast `308733018`, then 10 × animation `406081863` (2 × 5). Waves after the first start from the previous task's exit (`[taskset] start task … after task N exited`) | VERIFIED (log order) |
| SPU CPU per frame: wid1 50 ms (212 runs, 150 polled), wid2 14 ms, wid0 3.4 ms, wid3 0.3 ms; each lane about 13.7 ms | VERIFIED (CPU, not wall) |
| Frame thread: `sys_timer_usleep` 110 ms per frame (210 calls, 523 µs each; T121's overshoot) | VERIFIED |
| **Once T119/T122 remove the RSX bound,** the frame becomes PRE + emit + gap ≈ 50 ms. PRE is then the critical path: the Havok wave chain, the WWS kicks inside it, and the frame thread's wake latency | HYPOTHESIS (direct consequence of the phase order) |

## 4. AOT dispatch
- AOT engaged on every Wws job in D (64 `[spu-reloc] … AOT` lines, no refusals). Interpreter fallbacks (`[spu-int]`) are the interrupt vector of image `1297305682` only (first-N log). VERIFIED.
- WWS jobs no longer delay the frame (spin 0). Shaving AOT dispatch overhead (register state, LS access, ABI) **cannot shorten the frame now**. Not changed. VERIFIED by the phase data.
- Arm D ran with `PS3_SPU_WWS_AOT_VERIFY=1`, a resident re-hash safety net (~0.5 ms/frame). A production arm can leave it off, but that is a safety decision, not an optimization. HYPOTHESIS on the size.

## 5. DMA
- The race DMA/MFC path is inline (T109) and runs on lanes that are 0.48 busy with spin 0. No DMA cost is on the frame critical path. HYPOTHESIS: there is no per-DMA timing, and adding it would be high-volume tracing.
- MFC list stall/resume (`[mfc-list]`) appears only in the WWS PM's interrupt path; it is first-N capped, so there is no rate.
- **Nothing changed** (tag waits, ordering and reservation handling untouched).
- Per Havok task the ELF load into a fresh `calloc`'d 256 KB LS costs about **41 µs** (calloc + 150 KB copy + free, `logs/bench_task_dispatch.txt`). It runs in parallel across a wave's 5 threads: about 0.1 ms per wave, 0.5 ms per frame. HYPOTHESIS that it is worth a change; not done.

## 6. Scheduling
| Item | Finding | Class |
|---|---|---|
| Per-task fingerprint | `spu_workload_dispatch_async` FNV-1a-hashes the whole task ELF, byte-serial, on the dispatching thread, before `CreateThread`: 58–111 µs per task, **2.0 ms per frame**, 0.55 ms before a 5-wide wave's last task can start | VERIFIED (bench with the race's sizes and order) |
| Thread per task | `CreateThread` (256 MB reservation) → body: **45 µs**, 175 per second | VERIFIED (bench) |
| Kick discovery | the game kicks Wws workloads with inline atomics: only **32** `cellSpursReadyCountStore` calls in the whole D1 run. The coordinator finds such a kick only on its 1 ms timed wait or the next completion wake. Replica at `timeBeginPeriod(1)`: kick→run p50 **0.68 ms**, p90 1.5 ms, p99 2.1 ms | VERIFIED (replica); how many kicks sit on PRE's path is a HYPOTHESIS |
| Shared condvar | the coordinator and 5 workers share `si->wake`, so every admission and completion is a WakeAll: 2.0 empty worker wakes per run (5,400 per second at D1's rate), but **no measurable CPU or latency cost** (`logs/bench_spurs_wake.txt`) | VERIFIED. **Not changed** |
| Un-kicked polling | wid1: 150 of 212 runs per frame are polled runs (legacy admission, T109). It costs CPU; a fix is the opt-in `PS3_SPURS_READY_LEVEL=1`, untested | VERIFIED count; impact HYPOTHESIS |
| Kernel time | D1 process: 2.64 cores in the race, **0.96 of them kernel** (C1: 4.02 / 1.19). The source is not identifiable without ETW | VERIFIED number; source HYPOTHESIS |

## 7. Implemented
1. **`6b8700b` — exact fingerprint memo (default on; `PS3_SPU_FP_CACHE=0` restores the old path).**
   - `runtime/spu/spu_fp_cache.h`: 16 slots, each a private copy of the hashed bytes plus the hash *of that copy*.
   - A hit needs the same (address, size) and `memcmp` equal, so the stored value is what a fresh hash computes. Any byte change misses.
   - Used by the 3 dispatch paths. `spu_workload_fingerprint` is unchanged.
   - Guest-visible behaviour is identical (the same image resolves to the same lifted entry).
2. **`e48f279` — `PS3_SPURS_KICK_WAKE=1` (opt-in, default off).**
   - `spu_coherency.c` gains `g_spu_coh_line_hook` (NULL by default), called from both notify paths.
   - `ppu_loader.cpp` calls it on stwcx/stdcx commits to unreserved lines (reserved lines already notify). Weak/alternatename default for fixtures that link the loader alone.
   - `cellSpurs.c` publishes each live instance's line 0. A commit there wakes that instance's coordinator.
   - The admission rules, readyCount handling, the 1 ms poll and every guest write are unchanged; only *when* the pass runs moves.
   - Kept opt-in because it changes host scheduling timing and has not run in game.

## 8. Synthetic benchmarks (synthetic bytes, no game data)

| Benchmark | Before | After |
|---|---|---|
| Fingerprint, 25 race-order tasks per frame (`bench_task_dispatch.c`) | 2.000 ms | 0.040 ms (warm-cache hits; a cold `memcmp` is slower, still ≪ FNV) |
| 5-wide wave of 150 KB tasks, last start delay | 553 µs | 11 µs |
| Inline kick → run, replica at `timeBeginPeriod(1)` (`bench_spurs_wake.c`, 3 runs) | p50 667–701 µs, p99 2.1 ms | p50 6–7 µs, p99 0.2 ms (the rest waits for a free lane); same CPU |
| Inline kick → done, real `cellSpurs.c` (stress §6, default 15.6 ms timer) | median 15.0–15.5 ms | 58–68 µs |

## 9. Correctness and concurrency tests (`logs/`)
- **Baseline** (untouched `b84ed80`, `suite_base.txt`): 25 PASS / 8 SKIP (POSIX-only) / 0 FAIL, the same as T109.
- **`test_spu_fp_cache`** (new): PASS.
  - Covers first/last/middle-byte edits, undo, size changes, eviction (48 keys over 16 slots), oversize bypass.
  - 8 readers racing an in-place editor: 0 wrong of 32,000.
  - A mutant without the `memcmp` fails it.
- **`test_spurs_kick_wake`** (new): PASS.
  - Runs the T106 stress (2 seeds × one/guest) with the switch off and on; every section passes in both.
  - New stress §6: inline kicks stored as `ppu_stwcx32` does, ~380 extensions, each job exactly once, peak ≤ lanes.
- **Full suite on the final tree** (`suite_final.txt`): **27 PASS / 8 SKIP / 0 FAIL** (the baseline's 25 + the 2 new tests).
  - An earlier run (`suite_new.txt`) caught `test_spu_program_pipeline` failing on `6b8700b`; fixed in `044f766`.
- **SPURS/SPU concurrency set with `PS3_SPURS_KICK_WAKE=1`** (`suite_kickwake.txt`; stress, concurrency, maxcont, diag TLS, LR race): **5/5 PASS**, with "kick wake on" confirmed in every stress run.
- **TU compiles** (`tools/tu_t123.py`: exact compiler, flags, defines and includes from `build/motorstorm-t109/build.ninja`, retargeted):
  - `spu_workload.c`, `spu_coherency.c`, `cellSpurs.c`, `ppu_loader.cpp`: all rc=0;
  - **no new warning kinds** (`logs/tu_summary.txt`).
- **Interpreter/AOT equivalence:** not affected. No lifted, interpreter or AOT code changed.
- **Audit** (`--staged`): the same 25 inherited BLOCK items. None in T123 files.

## 10. Integration dependencies
- **T119/T122 first.** While RSX is the bound (80 ms ref wait), neither change can raise fps. They pay off once PRE is the critical path.
- **T121 `PS3_USLEEP_SPIN=2`** is complementary: the frame thread notices finished SPU work only at the end of a usleep.
- **AOT build block:** `MSPR_WWS_AOT` stays in `port-t106aot`. The A/B needs the AOT exe as in T106 D.
- **Shared files:**
  - `cellSpurs.c` (T106/T109);
  - `ppu_loader.cpp` (T109 `PS3_SC_WAIT_MS`);
  - `spu_workload.c`.
- **VERIFIED (`git log`):** T113/T118/T119/T120/T121/T122 have no commits to these files since their merge base `8ea1437`.
- Their branches also lack the T104/T106/T109 SPU series. Integration means replaying `1e5d534..e48f279` onto them, as T109 did onto T108. HYPOTHESIS: conflict-free; not tried.

## 11. Runtime A/B plan (needs build and launch authorization)
- **Build:** one AOT exe from the T123 tip, configured like `t106/ab/build_t109_aot.cmd` (`port-t106aot`), into `build/motorstorm-t123-aot`. Pin its SHA-256.
- **Runner and settings:** T106's `run_aot.py` route; race entry + 90 s; window +10..+80 s; `ab_fps.cfg`. Renderer, shader cache, textures, resolution and maxContention (guest 5) are identical in every arm.
- **Environment in all arms:** `SPURS_BUSY_MS=1000 PS3_SC_WAIT_MS=1000 RSX_FRAME_PERF=12,10 PS3_SPU_WWS_AOT=1 PS3_SPU_WWS_AOT_BASES=4000`.
- **Arms:**
  - **A:** the five-lane baseline, `PS3_SPU_FP_CACHE=0`;
  - **B:** A + `PS3_SPURS_KICK_WAKE=1` (scheduling);
  - **C:** B with the memo on (default; AOT + task-dispatch).
- **Order:** A B C C B A.
- **Repeat on the integrated T119/T122 tree.** That is the configuration where PRE can be critical.
- **Measures:**
  - fps, interval p50/p95/p99, and PRE/emit/spin (`ab_analyze.py`);
  - async-task order and per-frame counts (`task_phases.py`);
  - `[spurs-busy]` busy/runs/polled per lane;
  - tid 1 `sc141` ms and calls per frame;
  - process and kernel cores (`performance.json`);
  - RSX `other_ms`.
- **Validity gates:**
  - 21 jobs per frame;
  - 25 tasks per frame in PRE;
  - no new NOSYS / spu-depth / watchdog / VPVB lines;
  - `kick wake` arms: coordinator still polls (runs > 0 for every workload).
- **Expected (HYPOTHESIS):**
  - no fps change while RSX-bound;
  - PRE −1 to −2 ms (memo), and −0.5 to −1 ms per kick on PRE's path (kick wake), after T119/T122.

## 12. Commits (`agent/t123-spu-execution-performance`)

| Hash | Content |
|---|---|
| `6b8700b` | SPU dispatch: exact fingerprint memo + `test_spu_fp_cache` |
| `044f766` | fix to `6b8700b`: memo moved below the `---- dispatch` marker. `test_spu_program_pipeline` compiles the span above it as an excerpt and failed 3 cases; the excerpt is byte-identical to `b84ed80` again |
| `e48f279` | SPURS: opt-in `PS3_SPURS_KICK_WAKE` + stress §6 + `test_spurs_kick_wake` |

Private tools and logs: `generated/analysis/t123/tools/`:
- `spu_window.py`, `task_phases.py`;
- `bench_task_dispatch.c`, `bench_spurs_wake.c`;
- `tu_t123.py`;
- `run_suite_t123.*`.

## 13. Remaining limitations
- No in-game measurement of either change. **No fps claim.**
- The replica and fixtures model the protocol, not MotorStorm's Wws PM. The number of inline kicks on PRE's critical path is unknown.
- **Not done** (measured or estimated, not worth the risk now):
  - a task thread pool (45 µs spawn per task, about 1 ms per frame, parallel) changes per-thread TLS lifetimes;
  - reusing a task's LS (41 µs per task).
- Kernel time (0.96 cores) is unexplained without ETW. The un-kicked polling cost needs the `READY_LEVEL` arm.
- The memo's benchmark hit rate is warm-cache. In game, images may be cold in cache (still a `memcmp`, not a serial multiply chain).

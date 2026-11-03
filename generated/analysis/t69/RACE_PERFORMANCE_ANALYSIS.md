# T69: Race performance, offline bottleneck analysis

2026-10-26. Offline only: no launch, no game build, no merge, no push. No worktree was modified (`ps3recomp-t62` status is empty after the read-only `git apply --check` runs). T68's work was not touched.

## Result

- **Most likely bottleneck (MEDIUM confidence):** the WWS `Wws_Job` workload EvoDefault (wid 1) is the per-frame critical path.
  - Its job bodies (vehicle physics, renderable, visibility and similar jobs) run in the **SPU interpreter**.
  - They run on **one host lane**, because the game registers the workload with `maxContention = 1`.
  - The coordinator's 1 ms pickup cadence adds latency on top of that.
  - PPU main is not CPU-bound: it waits on this path for most of the frame.
- **SPU physics (Havok) is not the cause.** It is lifted, fixed at 5 steps per frame, and its 124 dispatches/s scale *with* the frame rate rather than driving it (VERIFIED).
- **Rendering submission is not the limit at 5 fps.** The inferred render thread uses about 0.16 cores, roughly 32 ms per frame.
- **What is missing to confirm:** which host thread is the 80 % thread, and the per-workload and per-job busy time in the race. §6–8 give a ready patch and a run plan to measure both.

## 1. Available evidence

| Source | What it gives |
|---|---|
| T64C `generated/runs/20261026-140153-t64c-loadrace-stall` | `performance.json` (per-TID CPU every 5 s, unnamed host threads), `stderr.log` (`[THREAD n] … hosttid=` for every PPU thread, SPU dispatch lines, PM poll lines, `rsx-hb`), RSXI frame 4985 |
| Garage `20261025-102805-garage-capture-probe` | same counters, used as a comparison at 9.9 fps |
| T25 perf A/B (`analysis/t25/PERFORMANCE_FINDINGS.md`) | garage only: main waits, RSX CPU per frame, SPURS kick→pick latency and PM residency per workload |
| T33 (`analysis/t33/SPU_JOB_COST_ANALYSIS.md`) | WWS job bodies run in the interpreter; main's gates depend on wid 1/2; interpreter vs lifted microbenchmarks |
| T37/T59/T60 | WWS module inventory, AOT design, tests |

**No per-job, per-workload or per-host-thread-role data exists for the race.** Script: `tools/race_evidence.py <run> [t]` → `logs/race_evidence_t64c.txt`, `logs/race_evidence_garage102805.txt`.

**Instrumentation active in T64C that inflates the absolute numbers** (it does not explain the drop from 32 to 5 fps):
- `PS3_TEX_SNAPSHOT=1`: about 11 ms/frame of RSX CPU in T25's garage;
- RSXI armed;
- `CELLMARK_DUMP` every 60 frames;
- the PT tracer with `sc=all`;
- `SPURS_LFQ_TRACE`;
- 1,589 unbuffered stderr lines/s.

## 2. CPU threads and SPU jobs (T64C race window 155.0–204.7 s)

**Frame rate (VERIFIED):** frames 4736 → 4986 = **5.03 fps**, 256–267 draws/frame.

**Process CPU (VERIFIED):** 2.19 cores busy, of which 0.69 cores are kernel time.

| Host TID | Cores | Identity | Status |
|---|---|---|---|
| 19848 | **0.76** | non-PPU host thread; idle (≤ 0.01) through menus and loading, busy only from the race | identity INFERRED (see below) |
| 13124 | 0.32 | process main thread = **PPU main** (`ppu_run` runs on it; `port/main.cpp`) | VERIFIED |
| 19244 | 0.16 | non-PPU host thread; active through boot, menus and loading at 0.1–0.2 cores | INFERRED: frame-clock / RSX thread |
| 2532, 16712, 13000 | 0.15, 0.08, 0.06 | non-PPU host threads | unknown (other SPURS lanes, or SPU threads) |
| 10380 fios mediathread, 4648 JobBatchHandler | ≤ 0.03 | PPU | VERIFIED |

- **Not a PPU thread (VERIFIED).** None of 19848, 19244, 2532, 16712 or 13000 appears in the run's 29 `hosttid=` lines, so no guest PPU thread is the 80 % thread.
- **PPU main waits about two thirds of the frame (INFERRED).** Its CPU is 0.32 cores, about 64 ms busy per 200 ms frame. This matches T25's garage pattern: busy 48 ms, waiting 27 ms, plus a 23 ms Present spin.
- **The garage shows the same shape (VERIFIED).** At 9.9 fps:
  - one non-PPU thread at 0.72 cores;
  - PPU main at 0.42;
  - a second non-PPU thread at 0.40, which matches T25's 31 ms/frame "RSX CPU" at about 620 draws.

**SPU dispatches in the race (VERIFIED):** 6,250 async dispatches = 125.7/s.

- **Mix:** `406081863` ×2500, `341580667` ×1250, `491898574` ×1250, `308733018` ×1250.
  - These are the Havok images: animation, simulate/solver, collide and ray-cast (T30 #6).
  - All are lifted (`dispatch HIT`), on taskset `0x16209480`.
- **Exactly 5.00 simulate steps per frame** in the race (1250/250), the garage (1050/210) and T36 (65–70 steps at 13–14 fps).
  - The Havok work per frame is constant, so the higher dispatch rate is a *consequence* of the frame rate, not its cause.
  - Each dispatch creates a fresh host thread with a 256 MB stack reservation (`spu_workload.c:1495`), so these TIDs are short-lived and cannot be the 0.76-core thread.
  - The `hkSpuUtil Helper` PPU thread (7752) never appears in the top threads.

**WWS (VERIFIED):**
- **Four `Wws_Job` workloads,** all `minC=1 maxC=1`: wid 0 "no name", wid 1 EvoDefault, wid 2 EvoHigh, wid 3 LibMP3.
- **The policy module is lifted; the job bodies are interpreted.** The PM is image 1297305682. The T62 exe has no WWS AOT (`spu_reloc.h` is absent; `121686d` is not an ancestor of `c529ab0`). T64C logs `[spu-smc] microstep img=1297305682 pc=0x051A8/0x15D20/0x16060 … handing to the interpreter` (log capped at 8 lines).
- **About 963 PM runs/s in the race, versus 297/s in the garage.** This is counted from `[spurs-pm] poll #1` lines (47,852). The rate is close to the coordinator's 1 ms pass rate (`cellSpurs.c` `SleepConditionVariableSRW(…, 1, …)`).

**Other paths (VERIFIED):**
- **LFQueue `PushBody` HLE:** 9,910 calls, mean 8.8 µs, which is under 0.2 % of a core.
- **FIOS SPU task (taskset `0x10483480`):** about 180 `WAIT_SIGNAL` cycles/s, below its boot rate of about 300/s.

**Dispatch, execution or completion.** Execution and pickup on the wid 1 lane are the candidates.
- Garage T25: wid 1 kick→pick takes 2.35 ms median (p95 11.7 ms) and a PM run takes 0.78 ms median.
- Consistency check (HYPOTHESIS): 963 runs/s × 0.78 ms ≈ 0.75 cores, about the 19848 load. The garage median is not the race mean.
- Completion back to PPU (JobBatchHandler poll → `SetCondition` → main's `usleep(250)` retry) cost about 1.1 ms/frame in the garage (T33 §4). That is minor.

**Rendering is not the limit at 5 fps (INFERRED):** if 19244 is the render thread, it does about 32 ms of work per frame.

## 3. Most likely bottleneck

**WWS wid 1 (EvoDefault): interpreted job execution on a single lane, plus coordinator pickup latency, with PPU main waiting on its batch gates.**

**Confidence: MEDIUM.**

**For:**
- One non-PPU thread at 0.76 cores, appearing only in the race.
- PPU main mostly waiting.
- PM runs at about 960/s.
- T33 proved that main gates on wid 1, at 37 ms/frame in the garage.
- Interpreted job bodies are VERIFIED.
- The interpreter is 33–36× slower than lifted code on integer/shuffle work and about 2× on float (T33 §5).

**Against, or not yet proven:**
- The identity of 19848 is inferred.
- No per-job split exists, so it is unknown whether `vehiclephysics`, `renderablejob`, `groundrush*` or the visibility jobs dominate.
- The split between compute and pickup latency in the race is unmeasured.

**Original computation versus emulator overhead.**
- **Original work:** what the jobs compute, the 5 Havok steps per frame, and the single-SPU contention of each workload. All of that is game design.
- **Emulator overhead (HYPOTHESIS, on the scale T33/T37 measured):**
  - interpreting job code, about 3–35× per instruction;
  - the 1 ms coordinator pass with its idle back-off;
  - a new thread per Havok task;
  - unbuffered logging.

**Side note (HYPOTHESIS).** At a constant 5 steps per frame, simulated time advances in proportion to the frame rate, so the race at 5 fps runs in slow motion. Raising the frame rate restores game speed. The step count must not be changed.

## 4. WWS AOT applicability (T37/T59/T60)

| Question | Answer | Status |
|---|---|---|
| Are the race's job modules covered? | All **31** retail WWS modules are lifted. The 145 functions are the fuzz-tested leaf set, not the coverage. They include vehiclephysics (7 hand-offs, in rodata tails), renderablejob (61), spuconstraints, spuxform, groundrush ×3, occjob, pvsjob, octreequery, screenrush, trailsupdate, the particle modules and LibMP3. Havok is not WWS; it is already lifted. | VERIFIED (static); which modules run in the race is BLOCKED |
| Do runtime identity and load address match? | Identification uses GUID + entry offset + 16 entry bytes + a full-span hash at the run-time base read from LS `0x1320`. The base comes from a slot allocator, so race bases are unknown. | design VERIFIED; bases BLOCKED (T60 §7 trace) |
| Would AOT replace the interpreted path? | Yes. The hook in `spu_indirect_branch` at the PM's `bisl` (0x3210 → return 0x3214) is the same path T33 saw hand off to the interpreter. Anything that does not match falls back to the interpreter. | VERIFIED (tests: 18/18 fallback cases byte-identical) |
| Is the overwrite verification sufficient? | Sufficient for an A/B with `PS3_SPU_WWS_AOT_VERIFY=1`: an overlapping GET drops the slot, and VERIFY re-hashes on non-DMA writes. Not covered: a write into a resident span **while a job is running**. | PARTIAL |
| Do missing artifacts block testing? | **Yes.** `generated/spu_raw/wws_reloc` does not exist, so an `MSPR_WWS_AOT=ON` configure stops with FATAL_ERROR until `tools/lift_wws_reloc.py --ctor` is run. Also, **the T62/T64C exe line does not contain the series at all.** | VERIFIED |
| Does it port to the race build line? | `git diff af37553 121686d` applies cleanly to `ps3recomp-t62` (`c529ab0`), and the T69 patch applies on top of it (scratch copy, `logs/apply_checks.log`). | VERIFIED (apply only; not compiled together) |

**Expected gain (HYPOTHESIS).** The T37 synthetic jobs run 2.7–9.6× faster (SSE4.1). If wid 1 compute is about 150 ms/frame, that leaves about 15–55 ms. The frame would then move toward the next limits: PPU main busy (about 64 ms in T64C) and pickup latency.

## 5. Ranked optimisation candidates (all keep guest semantics)

| # | Candidate | Benefit | Evidence | Behaviour | Complexity | Risk |
|---|---|---|---|---|---|---|
| 1 | **WWS job AOT** (T59 series onto the T62 line, lift, CMake patch, opt-in A/B) | high: the 0.76-core path, 3–10× per job | medium (interpretation VERIFIED; share of the race HYPOTHESIS) | byte-identical on synthetic and retail leaf functions; game-level unverified | medium (exists; integration plus 2 runs) | medium; VERIFY=1 first |
| 2 | **Immediate re-pick on the lane:** when a PM run returns and its workload is still kicked, select again at once instead of waiting for the next 1 ms coordinator pass. The real SPURS kernel re-selects on the SPU immediately. | medium (T25: kick→pick 2.35 ms median against a 0.78 ms run) | medium (garage); race BLOCKED | admission rules, `maxContention` and ready-count semantics unchanged; only host latency changes | low–medium (`spurs_pm_worker` / kernel loop, T24-owned) | medium: SPU-vs-PPU timing shifts, which earlier titles were sensitive to |
| 3 | Throttle the `[spurs-pm] poll` log, which prints on every run because its counter is thread-local per run (about 960 unbuffered writes/s) | small (a few % of a core plus less FILE-lock contention) | VERIFIED (code, counts) | log only | trivial (in the T69 patch) | none |
| 4 | Persistent host worker pool for async SPU tasks instead of `CreateThread` per task (125/s, 256 MB reservations) | small | static | must keep the dispatch-time taskset/taskid capture and the task-exit order | medium | low–medium |
| 5 | Render-thread cost (about 32 ms/frame at 5 fps; `PS3_TEX_SNAPSHOT` about 11 ms in the garage) | none now; the floor after 1–2 | T25 | n/a | T68 area, not touched | — |

**Rejected:** frame skipping, fewer AI, fewer Havok steps per frame, a changed simulation rate, a higher `maxContention` than the game requested, `LBP_SPU_SERIAL`, and `PS3_USLEEP_SPIN` (T25: +4.9 % for +1.26 cores).

## 6. Missing evidence

1. **Host TID → role for non-PPU threads,** above all 19848 and 19244. The runtime does not name SPURS lanes, the coordinator or the frame clock.
2. **Per-workload busy time, run count and polled runs in the race,** to confirm wid 1 at about 75 % and separate compute from idle.
3. **Per-job module cost and load bases in the race** (`PS3_FTRACE_SPUJOB=3214:1320`, kinds 26–28). This needs the T59 series in the build.
4. **Kick→pick latency in the race** (T25 kinds 24/25, which are on the perf line, not the T62 line).
5. **PPU main busy/wait breakdown in the race,** which bounds the gain after candidate 1.
6. **Havok task host durations** (not logged).

## 7. Minimal instrumentation for a future authorised run

**Build:** the T62 line + `t69_race_perf_instrumentation.patch`. Optionally add the T59 series `af37553..121686d`, compiled with AOT **inactive**, for item 3.

**Optional port line.** `port/` is not under git and is unchanged here. At the top of `frame_clock` in `port/main.cpp`, add:
```c
fprintf(stderr, "[thread-role] hosttid=%lu role=frame-clock\n", GetCurrentThreadId());
```

**Environment (run A):**
```
SPURS_BUSY_MS=1000
RSX_HEARTBEAT_MS=1000
PS3_FTRACE=<private path under generated/>   PS3_FTRACE_SPUJOB=3214:1320   (only with the T59 series)
```

**Leave out, for clean timing:**
- `PS3_TEX_SNAPSHOT`, RSXI, `CELLMARK_DUMP` and `PS3_TRACE_FILE`/`sc=all`;
- `SPURS_LFQ_TRACE`;
- every `vm_inline_ok` trigger;
- `TEX_SAVE`.

**Route and limits:** the same menu route and `PAD_FILE` as T64C, `--timeout ≤ 210`, private HDD roots.

**Read:**
- `[thread-role]` joined with `performance.json` TIDs;
- `[spurs-busy] wid=1 busy_ms` per 1000 ms window. Confirmed if it is ≥ 600 while the frame rate is about 5;
- `job_report.py` per-module share.

**Run B (only after A):** the same build, plus `PS3_SPU_WWS_AOT=1 PS3_SPU_WWS_AOT_VERIFY=1 PS3_SPU_WWS_AOT_BASES=<bases from A>`. Gate on kind-29 results ∈ {1, 2, 8} and on equal per-module completion counts. Compare fps and wid 1 busy time (T60 §8).

## 8. Isolated patch and offline results

**`patch/t69_race_perf_instrumentation.patch`** (sha256 `81f3e9b4…d238`, generated by `tools/make_patch.py` from copies; never applied to a worktree). Diagnostics only: it reads and writes no guest state.
- **`libs/spurs/cellSpurs.c`:**
  - `SPURS_BUSY_MS=<ms>` enables `[thread-role]` lines for the PM lanes and the coordinator;
  - per-workload host busy time, runs and polled runs around `spu_run_policy_module`, printed by the coordinator every `<ms>`.
  - Off by default: one cached `getenv`, no timing calls.
- **`runtime/spu/spu_channels.c`:** the `[spurs-pm] poll` log is gated on a process-wide count (first 16, then every 65,536th). The value returned to the PM is unchanged.

**Offline results (VERIFIED):**

| Check | Result |
|---|---|
| `git apply --check` on `ps3recomp-t62` `c529ab0` | OK (`logs/apply_checks.log`) |
| AOT series, then T69 patch, on a scratch copy | both apply |
| `clang-cl -fsyntax-only`, T62 build flags (`tools/syntax_check.py`, `logs/syntax_check.log`) | 0 errors in both files. `cellSpurs.c` +8 warnings, all of the `-Wunsafe-buffer-usage` / declaration-after-statement / `getenv` kinds already present 861 times; `spu_channels.c` +0 |

**Not done:** no unit test (diagnostic-only output, no behaviour change to test), no compile or link of the game, no run.

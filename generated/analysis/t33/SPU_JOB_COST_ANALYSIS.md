# T33: SPU job execution cost and the EvoHigh dependency

Offline only. No game launch, and no changes to scheduling, maxContention or coordinator admission.

- **Trace inputs:** the T25 runs A (`generated/runs/20261025-183416-perf-t25-ab1-a`, default usleep) and B (`…-183635-perf-t25-ab2-b`, `PS3_USLEEP_SPIN=1`). Window: garage, 67–118 s.
- **Source:** `ps3recomp-t25-perf` @ `991337d`, plus the MotorStorm PM lift (`generated/spu_raw/wws_job_pm`) and the developer build symbols (`generated/analysis/c38/rv/symbols.txt`).
- **New code:** branch `agent/t33-jobcost` @ `0568549` (worktree `ps3recomp-t33`). Local commit only, not merged or pushed.

## Answers

| # | Question | Finding | Label |
|---|---|---|---|
| 1 | Which job functions dominate wid 1 / wid 2 | No per-job data exists in the T25 traces. What is verified: **every Wws job body runs in the SPU interpreter** (§1). Per-job instrumentation is ready for one authorised run. | BLOCKED (per-job); VERIFIED (interpreted) |
| 2 | Is wid 2 (EvoHigh) on main's critical path | Yes, about 8 ms/frame of main's gate waits (§2). **This corrects T31 §2**, which also found wid 1 not frame-critical. wid 1 is the larger dependency, about 37 ms/frame. | VERIFIED (run B) |
| 3 | What the back-off waits for | Job-batch completion conditions: `ConditionVariableLightImpl` gates set by `JobManagerBase::HandleBatchCompletions` on the JobBatchHandler thread. One gate follows wid 1 and two follow wid 2. Present spins on the render-command job count (§3). | VERIFIED (gate↔workload); HYPOTHESIS (which jobs) |
| 4 | Are the ~4 ms sleeps guest-required | Each episode is many guest `usleep(250)` retries merged by ftrace; it is not one 4 ms sleep. Episode length is set by the SPU producer (guest semantics). The host stretches each 250 µs sleep to about 560 µs, adding about 1.1 ms/frame of wake latency (§4). | VERIFIED |
| 5 | Expensive translations or memory ops | The interpreter costs **33–36× lifted** on integer/shuffle code and about 2× on float-heavy code. Exact float helpers cost 10–16 ns/op with SSE4.1 and 4–5 ns with AVX2. LS loads and stores are cheap (§5). | VERIFIED (microbenchmarks) |
| — | LV2 queue timeout patch | **Not prepared.** The subsystem is owned by T28 (`agent/t28-event-queue` @ `11c76d8`). Its proposal `tests/proposals/t28_queue_wait.inc` already has a monotonic deadline, timeout-is-not-a-spurious-wake handling, sub-ms waits and ECANCELED, with tests `tests/test_t28_event_queue*.cpp` and `tools/test_t28_event_queue.py`. A second patch would duplicate it. | — |

## 1. Wws job bodies are interpreted (VERIFIED)

- **Only the PM itself is lifted.** The MotorStorm PM (image `0x4D535052` = 1297305682) has lifted functions only in LS `0xA00`–`0x3700`, 240 entries. `0x3FEC0` is an unlifted stub.
- **No job-code lift is registered.** The only registered overlay (`generated/overlays/spu38790`) belongs to taskset image 283218738, not to Wws jobs.
- **Job code falls through to the interpreter.** Job code is DMA'd to LS `0x4000+` and entered from the PM's `bisl` at `0x31A8` (r0 = `0x3214`). `spu_lookup` misses, so `spu_indirect_branch` → `spu_smc_microstep` → `spu_interp_run_until` (`spu_channels.c:2175–2330`) runs the whole job.
- **Both runs show the hand-off** at job PCs in the PM image: `[spu-smc] microstep img=1297305682 pc=0x051A8 / 0x051F0 / 0x15D20 / 0x16060 … handing to the interpreter`. The log is capped at 8 lines, so the real frequency is not visible.
- **13 job modules are named.** The developer build lists `occjob`, `pvsjob`, `squishandordervisjob`, `groundrushjob`, `groundrushvisibilityjob`, `groundrushsquashjob`, `vehicledeformation`, `renderablejob`, `generatefogtable`, `octreequery`, `vehiclephysics`, `spuconstraints` and `spuxform` (`find_jobs.py`).
  - The retail bytes differ from the developer build (no head matches).
  - The retail `renderablejob` sits at EBOOT.elf file offset `0xFCF280` (size `0xF6D0`).
  - The logged PCs are not renderablejob code, so they belong to other modules.
- **This conflicts with AGENTS.md** ("AOT translation … do not replace gameplay with an interpreter").

## 2. Main's SPU dependencies (VERIFIED)

Per-gate figures from main's back-off at lr `0x94CCA8` (`gate_link.py`, `gate_fill.py`), in ms/frame:

| Gate (r31) | A | B | Producer | Evidence (B) |
|---|---|---|---|---|
| `0x17FF8CEC` | 14.4 | 14.9 | wid 1 | wait ends ≤ 700 µs after a wid 1 run end in 100 % of cases (baseline 25 %); wid 1 busy for 99 % of the wait |
| `0x16A799EC` | 4.8 | 3.3 | wid 2 | ends ≤ 300 µs after a wid 2 run end in 86–91 % of cases (baseline 5 %); wid 2 busy for 75–96 % of the wait |
| `0x173F181C` (A) / `0x173F171C` (B) | 4.1 | 4.5 | wid 2 | same as the gate above |

- **Present spin.** The silent tail before each flip (`present_link.py`) is 22–23 ms/frame.
  - wid 1 runs back-to-back for about 45 ms before each flip, and the stretch ends at the flip (median 0.0 ms, p95 0.1 ms).
  - wid 1 is active at 97 % of flips.
- **Total.** wid 1 blocks main for about 37 ms/frame and wid 2 for about 8 ms/frame.
  - Faster wid 1 job code should shorten the frame almost one-for-one. HYPOTHESIS on the ratio.
- **Why T31 got this wrong.** It pooled all gates, used a 50 µs window and missed the Present spin, which has no syscall.

## 3. What the waits synchronise on

- **Gate releases.** `SetCondition(true)` on each gate comes from `HandleBatchCompletions` on JobBatchHandler (tid 12, which polls with a 200 µs guest sleep, lr `0x4AF6D0`). The chain is: SPU job batch completes → handler poll → `SetCondition` → main's next 250 µs retry.
- **No direct SPU data dependency.** Main does not read SPU output directly. It waits on batch-completion flags.
- **Present** spins on `rs+0x2560 != rs+0x44C`, the completion count of render-command jobs.
- **Which jobs.** Which job ids feed each gate is BLOCKED until one `PS3_FTRACE_SPUJOB` run. The Present dependency is renderablejob or command jobs (HYPOTHESIS).

## 4. The "~4 ms sleeps"

- **They are merged retries.** ftrace merges consecutive sleeps within 300 µs into one span, so the "4 ms" spans are runs of guest `usleep(250)` retries.
- **The SPU producer sets their length.** In B, the gate wait for wid 1 got longer (206 vs 170 ms/s of wait) while the host latency fell. The wait is bound by the producer.
- **Host share.** Each guest 250 µs sleep costs about 560 µs in A and about 260 µs in B.
  - From the last SPU run end to main's wake: A 425–732 µs median, B 154–226 µs.
  - The extra latency is about 1.1 ms/frame over the three gates.
- **Existing fix.** T24's `a0dee0a` ("precise short usleep on Windows") gives B-like latency without spinning a core.

## 5. Microbenchmarks (deterministic, no program bytes)

Setup: Clang `-O2 -ffp-contract=off`. This machine, 5 repeats, best kept. Results are bit-identical across paths (checked).

- **`tests/bench_spu_interp_step.py`** runs one 14-instruction loop × 2 M iterations three ways: interpreted without the lookup, interpreted with the per-step `spu_lifted_lookup` (a hash shaped like `spu_lookup`, 200 k entries), and SPULifter output.

| Mix | interp, no lookup | interp + lookup | lifted | ratio |
|---|---|---|---|---|
| float (3 of 14 are fma/fm/fa), `-msse4.1` | 9.6–10.0 ns/insn | 10.3–11.0 | 4.8–5.1 | 2.1× |
| float, `-msse4.1 -mavx2` | 10.0 | 10.5 | 4.7 | 2.2× |
| integer/shuffle (renderablejob is 3.2 % float statically) | 4.5–5.1 | 5.1–5.7 | 0.15–0.16 | **33–36×** |

- **`tests/bench_spu_helper_ops.c`** gives ns per op (dependent chains, normal-range inputs):

| Op | SSE4.1 (production default) | AVX2 |
|---|---|---|
| fa / fm / fma | 10.6–11.6 / 10.3–11.0 / 16.1–18.1 | 4.1 / 3.9 / 5.0 |
| a, shufb, rotqby, selb, ceq | inline, < 0.1 | same |
| stqd + lqd + a | 0.4–0.5 | 0.4 |

- **The per-step lookup** is 6–12 % of interpreter time. It is exactly removable with a per-image bitmap of lifted entry addresses.
- **Float helpers.** The exact float helpers cost 30–100× an integer op. `PORT_SPU_AVX2` is `OFF` in the T25 build (`CMakeCache.txt`), so lifted SPU code uses the slow path. `spu_interp.c` is built in the runtime library with SSE4.1 only.
- **Memory ops are not a cost.** LS loads and stores are not significant. GET calls `spu_overlay_note_get`, which hashes the full 12 KB span only when a GET's size equals a registered span (`0x3000`); this is rare.

## 6. Instrumentation (ready, off by default)

- **Knob.** `PS3_FTRACE_SPUJOB=3214` (with `PS3_FTRACE`). When off, the cost is one load and a branch in `spu_indirect_branch`.
- **Span kinds.**
  - Kind 26 `SPU_JOB` covers each job body, from the branch with r0 = `0x3214` to the drain reaching `0x3214`: `a` = FNV-1a 32 of the 64 entry bytes, `b` = entry LS | wid << 24.
  - Kind 27 carries the job's interpreted instruction count, from a new per-thread total added at each interpreter return, not per step.
- **stderr.** It logs the first 64 jobs with 32 code bytes each.
- **Files.** `runtime/spu/spu_jobspan.h`; hooks in `spu_channels.c` and `spu_drain.c`; `spu_interp.c`; kinds in `include/ps3emu/ps3_ftrace.h`.
- **Test.** `tools/test_spu_jobspan.py` passes with 5 wiring checks and 16+1+2 harness checks, no SKIP. `tools/test_ftrace_spurs.py` still passes.
- **Report.**
  - `job_report.py <run> 67 118 --eboot generated/decrypted/EBOOT.elf` prints per-job runs, total/median/p95 time, share of the workload, interpreted instructions and ns/insn. It also maps each id to its EBOOT offset.
  - `job_report.py --selftest` passes.
- **Known limits.** A job that leaves without returning to `0x3214` stays open until its lane's next return. The `0x1DF` wid byte follows the `SPU_BUSY` convention and has not been checked under policy mode.
- **Existing test that won't link here.** `tests/test_spu_fnms_zero_extended.py` fails to link on this machine (duplicate Win32 stubs), same as on the `991337d` baseline, so it is not a regression. The new benchmark covers interpreter-vs-lifted equality instead.

## 7. Proposed improvements (ranked)

1. **AOT-lift the 13 Wws job modules** and register each by content fingerprint (`spu_overlay_register_region_fingerprint`, as for `spu38790`). This brings the port in line with AGENTS.md.
   - Expected gain: most of wid 1's ~45 ms/frame of SPU time, since the code is integer-heavy (33×/insn here). wid 1 drives about 37 ms/frame of main's blocking. HYPOTHESIS until a job-span run gives per-job instruction counts.
   - Next steps: (a) one authorised `PS3_FTRACE_SPUJOB` run (ids, EAs, hot jobs); (b) lift the hottest first; (c) offline differential test of lifted vs interpreted on captured LS snapshots.
2. **Build lifted SPU code with `PORT_SPU_AVX2=ON`** (needs an AVX2 CPU; bit-identical per ps3recomp #369). fa/fm/fma run 2.7–3.6× faster. This matters once (1) lands.
3. **Integrate T24's precise usleep `a0dee0a`.** It removes about 1.1 ms/frame of completion-chain latency. No scheduling change.
4. **Interim, exact:** a lifted-entry bitmap to drop the per-step lookup (≤ 12 % of interpreter time). Not worth it if (1) lands.

Do not change maxContention, admission or the gates; the waits are producer-bound.

**Coordination.** Items 1, 2 and 4 touch T24 SPU code (`ps3recomp-t24-spu`, `agent/t24-spu`). The T33 branch is a proposal for that owner and changes nothing on their branch. Integration needs their review.

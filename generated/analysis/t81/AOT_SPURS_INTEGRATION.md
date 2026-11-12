# T81: WWS AOT + five-SPU concurrency integration (offline)

> T81B update below supersedes the original no-fix/no-build conclusions.

No game builds, no MotorStorm launches, no merges, no pushes. The T70G (`ps3recomp-t70g` @ `88feeb5`) and T79 (`ps3recomp-t79` @ `d248709`) worktrees are clean and unchanged. All four exe pins are unchanged (`4a07bfc9…`, `2709eafd…`, `ae7ed7be…`, `5a1b49c3…`).

## Verdict

- **Integration (VERIFIED):** isolated source revision **`5b3b6bf`** on branch `agent/t81-aot-spurs`, worktree `ps3recomp-t81`. It combines the corrected T70G job-span tracer, WWS AOT and the T79 SPURS max-contention controls. Both features are off by default and independent.
- **Five-lane slowdown (VERIFIED offline, cause found):** cache-line contention on three process-global **diagnostic** variables that every lane writes on its hot path. It is not the interpreter algorithm, not the tracer, and not CPU saturation.
  - Making the three per-thread in a diagnostic build removes the slowdown completely when lanes are on separate cores.
  - The remaining factor is SMT sibling sharing (6 cores / 12 threads).
- **No fix applied (as briefed).** The fix is a proposal for a separate authorization (§4.3). Until it lands, arms C and D carry the same per-job penalty that C5 showed.

## 1. Integration

| Item | Value |
|---|---|
| Base | T70G `88feeb5` (corrected job-span start; parent `bdf8224`) |
| Commits | `6c6f679` = cherry-pick of T79 `01d9205` (ninth-argument maxContention handler, `PS3_SPURS_GUEST_MAXCONT`); **`5b3b6bf`** = cherry-pick of T79 `d248709` (contention bytes under the lock-line lock, `CELL_SPURS_MAX_SPU` bound, backed-SP check, `test_spurs_wws_concurrency`) |
| Patches | `patches/0001-…` (sha256 `3117a578…`), `patches/0002-…` (`5540b338…`) |
| Conflicts | **none**. T70G touches `ps3_ftrace.h`, `spu_jobspan.h` and jobspan tests; T79 touches `cellSpurs.c/.h`, `ppu_sysprx.cpp` and SPURS tests. The file sets are disjoint. |
| Tree check | `git diff d248709 HEAD` = exactly T70G's 6-file diff; `git diff 88feeb5 HEAD` = exactly T79's 7-file diff (VERIFIED) |
| Not integrated | no renderer, GPU-sync (T77), depth-export (T75) or loading changes |

The five integration items:
1. Guest maxContention argument: SP+112 handler, `6c6f679`.
2. Runtime override: `PS3_SPURS_GUEST_MAXCONT=1`, same commit.
3. Lock-line correction: `5b3b6bf`.
4. Concurrency safety: `5b3b6bf` (bound, backed SP).
5. T70G opener: `88feeb5`.

WWS AOT (`spu_reloc`, `spu_wws_job_enter`, constructor registration) is untouched.

## 2. Independent controls (VERIFIED)

| Arm | AOT | Contention | Environment |
|---|---|---|---|
| A | off | 1 | neither switch |
| B | on | 1 | `PS3_SPU_WWS_AOT=1`, `_VERIFY=1`, `_BASES=4000` |
| C | off | 5 | `PS3_SPURS_GUEST_MAXCONT=1` |
| D | on | 5 | B + `PS3_SPURS_GUEST_MAXCONT=1` |

- **Separate code:** `PS3_SPURS_GUEST_MAXCONT` is read only in `cellSpurs.c` (`spurs_guest_maxcont_enabled`). The `PS3_SPU_WWS_AOT*` variables are read only in `spu_channels.c` (`spu_reloc_read_env`). Neither references the other.
- **Defaults:**
  - AOT registers only when `PS3_SPU_WWS_AOT=1` (`test_spu_reloc_job`: "generated constructor registers only when PS3_SPU_WWS_AOT=1").
  - Contention is 1 unless the override is set (`test_spurs_wkl_maxcont` default mode; C1 runtime: guest 5 → applied 1).
- **Cross-checks:**
  - `test_spurs_wkl_maxcont` with all three AOT variables set: PASS. Default mode still 1, guest mode 5 (`logs/cross_maxcont_with_aot_env.log`).
  - `test_spu_reloc_job` with `PS3_SPURS_GUEST_MAXCONT=1`: 0 failures (`logs/cross_reloc_with_maxcont_env.log`).
- **Harness:** `run_t81_ab.py dryrun` for the four arms gives exactly the table above (`logs/dryrun_4arms.log`). B and D refuse to run without bases.

## 3. Five-lane slowdown investigation

### 3.1 Benchmark

`bench/bench_wws_lanes.c` + `bench/run_bench.py`, run through `tools/run_t81.cmd`. Logs: `bench/bench_results.txt`, `bench/snapdiff_runtime.txt`.

- **Setup:**
  - N host threads (lanes), each with its own `spu_context`, run a synthetic Wws job (no game bytes; `test_spu_reloc_job`'s float+switch module, 56 070 SPU instructions).
  - Each job goes through the real `spu_indirect_branch` → drain → interpreter or lifted-module path, with the same PM return/code-base words as MotorStorm (0x3214 / 0x1320).
  - 200 jobs per lane, best of 3.
- **Variables:** interpreter or AOT; tracing off or on (`PS3_FTRACE` + `PS3_FTRACE_SPUJOB=3214:1320`); 1/2/3/5/6 lanes; affinity none, `spread` (one lane per physical core) or `pack` (SMT siblings); 0/3/7 spinning threads standing in for PPU/RSX.
- **Control:** a `cpu` mode runs a pure integer loop with no shared state.
- **Diagnostic builds:** temporary copies, never committed:
  - `nolastpc`: drops the per-step `g_spu_interp_last_pc = ctx->pc`.
  - `tlsdiag`: that, plus `spu_trace_call`'s ring and `spu_depth_guard`'s ring made `__thread`.

### 3.2 Results (Ryzen 5 9600X, 6 cores / 12 threads)

| Configuration | Interpreter ns/insn | vs 1 lane | AOT µs/job | vs 1 lane |
|---|---|---|---|---|
| real, 1 lane | 7.53 | – | 152.8 | – |
| real, 5 lanes, one per core | **18.39** | **2.44×** | **288.5** | **1.89×** |
| real, 5 lanes, unpinned | 19.56 | 2.60× | 268.2 | 1.76× |
| real, 6 lanes, one per core | 21.87 | 2.90× | 352.1 | 2.30× |
| nolastpc, 5 lanes, one per core | 12.92 | 1.76× | – | – |
| **tlsdiag, 5 lanes, one per core** | **7.40** | **0.98×** | **150.1** | **0.98×** |
| tlsdiag, 6 lanes, one per core | 7.40 | 1.03× | 151.4 | 0.99× |
| tlsdiag, 5 lanes, unpinned | 7.87 | 1.07× | 157.3 | 1.05× |
| tlsdiag, 5 lanes + 3 spinners | 9.06 | 1.23× | 204.3 | 1.36× |
| tlsdiag, 2 lanes on SMT siblings | 18.09 | 2.53× | 230.0 | 1.54× |
| cpu control, 1 → 6 lanes (any affinity) | 22.1–22.4 µs | ≤ 1.01× | | |
| tracing on vs off (1 lane / 5 lanes) | 7.77 vs 7.51 / 18.7 vs 18.4 | +3 % / +2 % | 160.8 vs 149.9 / 267.9 vs 268.2 | +7 % / 0 % |

The real 5-lane interpreter factor (2.44×) matches C5's in-game ×2.5 ns/insn (pvsjob 9.14 → 22.56).

### 3.3 Attribution

| Suspect | Finding |
|---|---|
| **Cache-line contention** | **Cause (VERIFIED).** A snapshot of the bench exe's writable sections around 200 single-lane jobs, symbolized with the link map, names the process-global words the job path writes:<br>• `spu_depth_guard`'s `s_ring`/`s_n` (`spu_drain.c` ~378): ~2 000 writes per job in AOT, one per lifted call/drain site; 2 per job interpreted.<br>• `spu_trace_call`'s `s_trace`/`s_trace_i` (`spu_interp.c` 375): ~2 000 per job interpreted, one per `brsl`.<br>• `g_spu_interp_last_pc` (`spu_interp.c` 434): one per interpreted instruction (net value unchanged, so it is invisible in the diff but visible in the code).<br>All three are always-on diagnostics. With five lanes, every write takes the line from another core. Making them per-thread restores 1-lane cost at 5 and 6 lanes. |
| Shared interpreter state | Only the three diagnostics above. Dispatch tables and the function registry are read-only on this path; step counts are already per-thread (`t_spu_interp_steps_total`). |
| Atomics | `g_ps3_ft.n` (4 `fetch_add` per job, tracing only), `mfc_submit._pn` (3 per job), log-once counters: negligible (the tlsdiag runs keep them and scale flat). |
| Lock contention | None measurable on the job path: tlsdiag is flat to 6 lanes, and it still takes the MFC/DMA locks. |
| Memory allocation | Nothing allocates on the job path (no heap words change; tlsdiag is flat). |
| Trace recording | ≤ 7 % at 1 lane, ~0 at 5 lanes. **Not** the cause. |
| Host CPU saturation | Not with 5 lanes on 6 cores (the control is flat). 3 extra busy threads cost +23 % (interpreter) and +36 % (AOT) even with tlsdiag. |
| **SMT sharing** | Second factor (VERIFIED). Two interpreter lanes on sibling threads cost 2.5× even with tlsdiag, AOT 1.5×. The real process (5 lanes + PPU main + RSX + audio + others on 12 threads) cannot keep every lane on its own core. |
| Scheduler wakeups | Not exercised by this bench (no coordinator). C5 shows 4 065 coordinator passes/s: HYPOTHESIS, minor. |

**Conclusion:** the measured 1.6–2.7× per-job slowdown comes from shared diagnostic state in the SPU runtime (both the interpreter and the AOT/drain path), compounded by SMT when lanes share cores. It is not the interpreter itself and not the T70G instrumentation.

## 4. Concurrency correctness

| Check | Evidence | Status |
|---|---|---|
| Five simultaneous WWS jobs | bench: 5–6 lanes × 200 jobs, interpreter and AOT, every lane's output equal to the single-lane reference; `test_spurs_wws_concurrency` (five lanes, real coordinator and MFC path) | VERIFIED |
| Job identity | bench traced: every kind-26 span carries the job's entry id (one id, 1 010 spans at 5 lanes); `test_spu_jobspan` 12 PASS | VERIFIED |
| Exactly one start and completion per job, **with concurrent workers** | bench traced: per lane exactly 201 spans (+1 reference on lane 0) = jobs run, **0 LOST**, in interpreter and AOT, pinned, unpinned and with spinners. The T70G span state is per host thread (`static __thread spu_jobspan_state`), so lanes cannot interfere. | VERIFIED (synthetic job) |
| No duplicate claims, no missing completions | `test_spurs_wws_concurrency` ×3: 900 jobs each exactly once, default and guest modes | VERIFIED (manufactured PM) |
| DMA atomics | same test: PUTLLC retries under peer and PPU writes; line-0 readyCount swap under the lock-line lock | VERIFIED (manufactured PM) |
| Guest-memory visibility | same test: each result visible before its completion bit | VERIFIED |
| Workload switching | same test: 3 rounds × 2 workloads, plus two instances | VERIFIED |
| Audio workload progress | no offline equivalent (LibMP3 is game code); runtime C5 kept it running in every second (193/193) | PARTIAL (runtime only) |
| AOT / interpreter parity | `test_spu_reloc_job` 85 PASS (run/state/fuzz/scenario), with and without `PS3_SPURS_GUEST_MAXCONT=1` | VERIFIED |
| Guest-state equivalence | `test_spurs_wws_concurrency`: contention 1 and 5 leave byte-identical guest state; `test_spu_jobspan_path`: tracing on and off identical in 12 scenarios; `test_spu_reloc_job` state mode: fallbacks equal a build without AOT | VERIFIED |

### 4.3 Proposed fix (not applied; needs authorization)

Make the three diagnostics per-lane. They are host-side observability only, so the change does not touch guest-visible state or game semantics:
- `spu_depth_guard`'s ring: `SPU_THREAD_LOCAL`.
- `spu_trace_call`'s ring: `SPU_THREAD_LOCAL`.
- `g_spu_interp_last_pc`: drop the per-step store, or move it into `spu_context`. `lv2_register.c` (lines 840 and 925) prints it from another thread in two diagnostics, so it cannot simply become TLS.

Expected effect (bench): interpreter and AOT per-job cost flat up to 6 lanes on separate cores. It needs its own tests (a 5-lane timing regression in the bench) and its own build.

## 5. Offline validation (logs `logs/suite_*.log`, `tools/run_suite.py` under `tools/run_t81.cmd`)

| Test | Result |
|---|---|
| `test_spu_jobspan` (T70G) | 12 PASS, 0 failures |
| `test_spu_jobspan_path` (T70G) | 63 PASS, 0 failures; architectural state identical with tracing on and off (12 scenarios) |
| `test_spu_reloc_job` (WWS AOT: parity, state equivalence, fuzz, residency) | 85 PASS, 0 failures |
| `test_spu_lifter_reloc` (WWS relocatable lifter) | 13 PASS, 0 failures |
| `test_spurs_wkl_maxcont` (T79, default and guest) | PASS |
| `test_spurs_wws_concurrency` (T79, default and guest) | PASS 3/3 |
| `test_spurs_scheduler` (POSIX fixture via `tools/run_posix_fixture.py`) | PASS (exit 0) |
| `test_ppu_trace` | PASS |
| `test_spu_chain_chunks`, `test_lifter_dedupe`, `test_lifter_header_name` | PASS |
| Lane bench checks (§3/§4) | all cells: outputs equal the reference; all traced cells: spans OK, 0 lost |
| Exact-flag compile (`build/motorstorm-t70g-aot` commands redirected to `ps3recomp-t81`): `spu_channels.c`, `spu_drain.c`, `cellSpurs.c`, `ppu_sysprx.cpp` | exit 0. Warning-line counts 1915 / 171 / 1228 / 429 vs 1913 / 171 / 1228 / 429 before; only the existing `-Weverything` classes (`logs/compile_tus.log`) |
| `audit_public.py --staged` | the same 25 baseline items as T70H (byte-identical list); none in the 13 changed files |

**Skipped:**
- POSIX-only fixtures, which SKIP by design on this host: `test_spu_interpreter_handoff`, `test_spurs_queue_size`, `test_spurs_taskset_size`, `test_spurs_task_exit_code_initialize`, `test_spu_context_registries`, `test_spu_machine_status`.
- `spu_lift_selftest`: needs the PS3 SDK SPU compiler (BLOCKED).
- `test_spu_fnms_zero_extended`: its UBSan fixture does not link with this Windows toolchain. It fails the same way on the untouched T70G tree (`logs/suite_spu_fnms_zero_extended_on_t70g.log`), and its files are unchanged since `bdf8224`. Pre-existing, unrelated.

## 6. Remaining risks

1. **Contention penalty is still in the source** (§3). C and D will show per-job slowdowns like C5 (interpreter ~2.4×, AOT ~1.9× at 5 lanes). D's gain over B is therefore uncertain: B1's WWS is 50 ms/frame on one lane, so the ideal ÷5 is impossible.
2. **SMT:** with 6 cores and 5 lanes plus the PPU/RSX threads, sibling sharing remains even after the fix (interpreter ×2.5, AOT ×1.5 for paired lanes).
3. **The bench is synthetic:** one job module with no game bytes. Magnitudes on real modules differ, but the 5-lane interpreter factor matches C5.
4. **Manufactured PM:** the concurrency tests reproduce the WWS PM's atomic shapes, not its pipeline or GETLB interrupts. The PPU-side job-list producer audit remains BLOCKED (T79 §11.4).
5. **Tracer on the real PM:** proven per thread with a synthetic job. A host thread that switched SPU contexts mid-job would record LOST (by design). Not observed in SPURS, where each lane is one thread.
6. **No exe yet:** the exe-level checks (flag diff, AOT markers, 31/31 reloc lifts, maxContention string) wait for the authorized build.

## 7. Exact build procedure (needs authorization; not run)

1. `generated\analysis\t81\build\configure_aot_t81.cmd`: new private dir `build\motorstorm-t81-aot`, `PS3RECOMP_DIR=ps3recomp-t81`, `MSPR_WWS_AOT=ON`, `PORT_SPU_AVX2=OFF`, private `port-t70\`, no shared generator steps. This is T70G's configure script with only the two paths changed.
2. `generated\analysis\t81\build\build_aot_t81.cmd` (`cmake --build build\motorstorm-t81-aot --parallel 2`).
3. `py -3 -I generated\analysis\t81\build\ninja_diff_t81.py`: every object's rule, source, DEFINES, FLAGS and INCLUDES must equal T70G's after path mapping.
4. As in T70H: exe inspection, WWS reloc verification (31/31), the T70G opener byte check (`t70/t70h/find_opener_bytes.py`), and the strings `maxContention guest=%u applied=%u` and `PS3_SPURS_GUEST_MAXCONT`.
5. `py -3 -I generated\analysis\t81\ab\run_t81_ab.py prepare build\motorstorm-t81-aot\MotorStormPacificRiftRecomp.exe` pins it into `t81\ab\exe-t81\` + `exe_pin_t81.json` (refuses without the AOT CMake cache and the T79 marker).

## 8. Four-arm runtime plan (each launch separately authorized)

Same exe, `run_t81_ab.py launch <arm>` with the T70 controller: fresh private HDD copy, no driving or input, no TEX_SAVE, no RSX_RT_READBACK, ftrace armed at race entry (`329D90:8EE8C:3`) with T70G job spans, 205 s session cap, `--timeout 210`, race entry rejected after 172 s.

| Order | Arm | Command | Reference |
|---|---|---|---|
| 1 | A: AOT off, contention 1 | `launch A` | A1″ / C1 |
| 2 | B: AOT on, contention 1 | `launch B 4000` | B1 |
| 3 | C: AOT off, contention 5 | `launch C` | C5 |
| 4 | D: AOT on, contention 5 | `launch D 4000` | – |

**Per run:**
- `ab_report.py`, with all T70F gates unchanged. On this exe the "returns attributed" gate can pass (T70G opener).
- `t70f/identity.py`: 14–15 manifest ids, 0 PM ids.
- `t79/tools/t79_overlap.py`: peak workers per wid; C and D must exceed 1.
- stdout: `guest=5 applied=1` (A/B) or `applied=5` (C/D).
- B/D: `[spu-reloc] … resident re-hash on`, 0 MISMATCH.
- Havok 5.00 ± 0.05; draws > 200.
- Fixed-cadence runs per flip equal A's.
- LibMP3 progress in every second.

**Comparisons:**
- Contention effect: C vs A and D vs B.
- AOT effect: B vs A and D vs C.
- Interaction: D vs B·C/A.
- Tool: `t79/tools/t79e_compare.py`.

**Recommendation:** authorize the §4.3 diagnostic-state fix and its build *before* spending launches on C and D. Otherwise C and D measure the known contention defect again.

## T81B — Diagnostic contention removal

This update supersedes the earlier “no fix applied”, “no exe yet” and proposed
cross-thread last-PC handling statements. Worktree `ps3recomp-t81`, branch
`agent/t81-aot-spurs`, starting at `5b3b6bf`; no other agent worktree/pin changed.
No MotorStorm launch, merge or push. The full build is authorized by the T81B
request conditional on offline correctness, and is separate from runtime launch.

### Audit and implementation (VERIFIED from source)

| State | Writers | Readers and purpose | Ownership/control-flow result |
|---|---|---|---|
| `g_spu_interp_last_pc` | `spu_interp_run_until`: per loop and fast-path return | Two `lv2_register.c` done reports | Both call `spu_run_interp_job` synchronously on their own host thread. That inline helper directly calls the interpreter; it neither spawns nor joins a worker. The callers print before returning/terminating. TLS preserves their own result, even after the helper's stack context is gone. Not a live cross-thread snapshot. |
| `g_spu_interp_steps` | Three interpreter return paths | Same two done reports and the adjacent speed report | Made TLS with the PC: diagnostics only. The tracer uses the separate already-TLS `t_spu_interp_steps_total`, unchanged. |
| `spu_trace_call` ring/index | `spu_trace_call`, invoked by interpreted `bisl` | `spu_trace_dump`, called on conditional halt/assert in `spu_interp_step` | Same-thread error history; keep the always-on 32-entry circular writer and env-gated dump. No correctness decisions read the ring. |
| `spu_depth_guard` ring/index | Guard called from SPU_DRAIN and `spu_drain_call` | Same guard's overflow report | Same-thread last24 drain sites. Halt still tests `ctx->host_depth` against the configured limit, never the ring. |

All four diagnostic globals/rings above now use `SPU_THREAD_LOCAL`. The depth
limit cache also uses TLS; the default2000 and startup environment setting are
unchanged. The process-wide report limiter remains global, with an atomic
exchange ONLY after the depth limit trips, preserving one report while all
affected workers still halt. No shared hot-path lock/atomic, per-instruction
allocation, instruction implementation, DMA, guest state, scheduler or AOT
selection change. `spu_interp.h` supplies consistent TLS declarations to all
consumers. Existing ring order/capacity/wrapping and halt output are retained.

Search covered the complete T81 source, linked port/port-t70 and tools. There
are no readers of these values after worker termination, nor consumers in an
external crash thread in the linked source. The ring dump itself is the assert
diagnostic. Therefore no process-wide aggregation is needed. TLS starts zero
on host thread creation, persists across jobs on that worker (as history did),
has no retained context pointers and is released by the host runtime on exit.
It is host-thread history, not a new per-context registry. Debug settings should
be configured before worker creation. The earlier T81 proposal's assumption
that lv2's PC readers were cross-thread was incorrect.

### Performance (VERIFIED synthetic measurements; not game FPS)

Same T81 float/switch synthetic module, real MFC/dispatcher/drain,56070
interpreted instructions/job.200 timed jobs/lane, best of3 repetitions. Original
is an immutable `git archive 5b3b6bf`; fixed source differs only by this fix and
regressions. Same compiler/flags, harness and lifted module for both variants.
Every timed job checks its output and expected execution result; every traced
repetition validates per-lane span counts/identity and zero LOST.

Host: AMD Ryzen5 9600X,6 physical cores/12 logical processors, Windows
10.0.26200, Clang23.1.3 x64. Windows processor-topology masks are
`03,0C,30,C0,300,C00`. `spread` pins workers to logical0,2,4,6,8 (five distinct
cores); `pack` uses0,1,2,3,4 (two SMT sibling pairs plus a fifth lane).
One lane uses logical0. Affinity failures are fatal; no assumed successful pin.
No spinner threads in this requested matrix. Clock/power/background scheduling
were not controlled; best-of3 is not a confidence interval.

Times are **microseconds per job**, per-lane mean for the selected repetition:

| Affinity | Engine | Trace | Original 1 lane | Original 5 lanes | Fixed 1 lane | Fixed 5 lanes |
|---|---|---|---:|---:|---:|---:|
|spread|interp|0|403.4|1019.5|395.1|506.3|
|spread|interp|1|419.2|1021.2|411.9|423.6|
|spread|aot|0|151.4|282.6|155.7|162.5|
|spread|aot|1|160.2|294.4|159.9|167.6|
|pack|interp|0|412.5|1089.4|393.6|696.0|
|pack|interp|1|418.4|1152.9|398.1|705.5|
|pack|aot|0|149.5|248.3|156.1|222.1|
|pack|aot|1|160.8|264.2|162.5|224.8|

Separate-core five-lane interpreter improves1019.5→506.3us (trace off) and
1021.2→423.6us (trace on); AOT282.6→162.5us and294.4→167.6us. Fixed
single-lane AOT is about3% slower in this sample, within uncharacterized host
noise. Fixed five-lane interpreter still costs1.28× its single-lane cost with
trace off and1.03× with tracing: do NOT claim perfectly flat scaling or that all
remaining slowdown was eliminated. SMT remains visible (fixed interpreter
696–706us/job; AOT222–225us/job). The verified process-global hot writes are
removed, and their large multi-lane penalty is reduced. No race FPS prediction.

Raw data/topology/builds: `t81b/benchmark-v3/`, `host_topology.json`. Earlier
benchmark-v1/v2 attempts are excluded: the added harness check initially assumed
result0, then incorrectly expected warm-up INSTALLED to persist; actual valid
results are interpreter DISABLED6 and warmed AOT RESIDENT1. Their guest outputs
were already correct. The final matrix checks those real enums and passes all
32 cells. No runtime mismatch was hidden or fixed by changing SPU execution.

### Correctness and regressions (VERIFIED within the fixtures)

-16 original/fixed final-state comparisons are byte-identical: all128 GPRs,
 full256KiB LS, PC/status and guest DMA outputs, for each engine/affinity/lane/
 trace configuration. Fixed AOT/interpreter states and trace on/off states also
 match. `t81b/state_parity.json` pins hashes. Intermediate full-state snapshots
 are not taken after every instruction; output/result is checked after every job.
-All16 traced matrix cells pass on every repetition: one correct entry identity,
 lane0 has202 records (reference+warmup+200 jobs), other lanes201,1006 at five
 lanes,0 LOST. No duplicate/missing traced jobs. No interpretation-cost change:
56070 instructions/job in all interpreter cells.
-T79 stress repeated3 times, both default and guest modes:900 jobs once each,
 peak5/lane-mask1F; PUTLLC retries, visibility before completion, maxContention
1/5 byte-identical results, workload switching, two instances, busy shutdown and
 priority changes pass. No assertion of identical cross-lane DMA interleaving;
 per-job semantics/output and publication gates pass the real MFC fixtures.
-New diagnostic regression runs3 fresh processes ×5 workers: fresh TLS, own
 last PC/count, exact ordered last32 call pairs, same-lane depth history,
 exactly one process-wide report, five correct halt returns and unchanged main
 thread diagnostics. `logs/diag_final.log`.
-T70G jobspan12 and path63 checks pass (including trace-state parity across12
 scenarios); WWS AOT85 and lifter13 pass. T79 maxContention, scheduler, T81
 integration cross-controls and inherited chain/chunk/lifter/PPU tests pass.
-Additional SPU instruction/helper checks:70 helper +17 numeric checks,
200000 shuffle vectors, XSWD and interpreter selftest pass. RI10 decoding29
 forms, LS-inlining2 tests and program-pipeline12 tests pass.
-All affected TUs compile with exact baseline flags into private objects.
 Public audit: same25 pre-existing findings, byte-identical baseline/staged
 lists; no new finding. This is not a clean public-release audit.

Baseline limitations separately preserved: SDK-dependent `spu_lift_selftest`
cannot run without SPU_GCC/HOST_CC. The existing fnms UBSan fixture fails to link
with duplicate Windows API stubs; reproduced from untouched5b3b6bf. POSIX-only
handoff/ILH, queue/taskset-size, context-registry, machine-status, LS-alias,
SDCRZ, SMC and ELF-flag wrappers report SKIP on this host. No newly failing
applicable correctness gate remains. Logs are new under `t81b/logs/`; prior
T81/T70G/T79 logs and executable pins are preserved.

### Commit and full build

Fix: **`a80b794f628973e403e4fd3833814a0c474bf095`**,6 files, no unrelated
source changes. Existing5b3b6bf parent and corrected T70G job-span opener remain.

Configured via `build/configure_aot_t81.cmd`; built via
`build/build_aot_t81.cmd` under vcvars64 and project Clang23.1.3. Command:
`cmake --build build/motorstorm-t81-aot --parallel 2`, then resumed the same
private build with `--parallel 6` after verifying more than32GiB free RAM.
The two-worker invocation was deliberately stopped, not a compiler failure;
completed private objects were retained. No compiler flag changed. New private build directory,
private port-t70 recipe, existing generated inputs read-only, no shared generator
steps. All308 object entries have exactly T70G's rule/source/DEFINES/FLAGS/INCLUDES
after path mapping (`logs/ninja_diff.log`). Compiler version and complete build
output are retained. Compile-time MSPR_WWS_AOT=ON supplies capability; runtime
AOT and guest max-contention override remain OFF by default.

Build result:

```json
{
  "source": "a80b794f628973e403e4fd3833814a0c474bf095",
  "command": [
    "cmake",
    "--build",
    "build/motorstorm-t81-aot",
    "--parallel",
    "6"
  ],
  "compiler": "clang version 23.1.3 (https://github.com/llvm/llvm-project 0d261d1ca552c95a8f007e061c787ac7132fbcbc)\nTarget: x86_64-pc-windows-msvc\nThread model: posix\nInstalledDir: <repo>\\build\\llvm\\clang+llvm-23.1.3-x86_64-pc-windows-msvc\\bin\nBuild config: +alloc:rpmalloc\n",
  "returncode": 0,
  "elapsed_s": 498.3303380012512,
  "flags_match_t70g": true,
  "no_launches": true,
  "elapsed_resume_s": 434.04513907432556,
  "resumed_from": "<repo>\\generated\\analysis\\t81\\t81b\\build_attempt_parallel2.json",
  "parallelism_reason": "48GiB host, >32GiB available; compiler flags unchanged",
  "exe": "<repo>\\build\\motorstorm-t81-aot\\MotorStormPacificRiftRecomp.exe",
  "sha256": "fb29e6f289a2d583de261b6db88160ab7af469ab8199bc29cab9d4b7fdc4803b"
}
```

Post-build inspection/pin:

```json
{
  "source": "a80b794f628973e403e4fd3833814a0c474bf095",
  "executable_sha256": "fb29e6f289a2d583de261b6db88160ab7af469ab8199bc29cab9d4b7fdc4803b",
  "pin": "<repo>\\generated\\analysis\\t81\\t81b\\ab\\exe-t81b-a80b794\\MotorStormPacificRiftRecomp.exe",
  "modules_verified": 31,
  "corrected_opener_occurrences": 1,
  "diagnostics_in_tls": true,
  "runtime_AOT_default": false,
  "guest_contention_override_default": false,
  "four_arm_dryruns": "PASS",
  "launches": 0,
  "wrapper": "<repo>\\generated\\analysis\\t81\\t81b\\ab\\run_t81b_ab.py"
}
```

### Runtime readiness — no launches authorized/performed

The existing four arms will use ONE new immutable T81B executable. A:no AOT,
contention1; B:AOT1 with VERIFY1/BASES4000, contention1; C:AOT off with
PS3_SPURS_GUEST_MAXCONT1; D:B plus that override. Fresh HDD, no driving,
205-second session cap,210-second host timeout, no TEX_SAVE and no
RSX_RT_READBACK remain enforced by the inherited harness. Each launch still
requires separate authorization; T81B stops at build and offline verification.
Dry-run commands for the new pin (do not replace `dryrun` with `launch` without
separate authorization for that arm):

```
python -I generated/analysis/t81/t81b/ab/run_t81b_ab.py dryrun A
python -I generated/analysis/t81/t81b/ab/run_t81b_ab.py dryrun B 4000
python -I generated/analysis/t81/t81b/ab/run_t81b_ab.py dryrun C
python -I generated/analysis/t81/t81b/ab/run_t81b_ab.py dryrun D 4000
```

No physics, AI, rendering, T70G or T79 implementation was changed.

## T81C — Integrate verified T82 AOT fix (build + offline only; 0 launches)

Records: `t81c/postbuild.json`, logs in `t81c/logs/`, patch in `t81c/patches/`.

### Integration diff (VERIFIED)
- Worktree `ps3recomp-t81c`, branch `agent/t81c-aot-spurs-t82`, HEAD `0ab0d16` =
  cherry-pick of T82 `0b0b89b` onto T81 `a80b794`, no conflicts. T81/T82 worktrees untouched.
- `diff a80b794..0ab0d16` == `diff 88feeb5..0b0b89b` (T82: 7 files +943/−3:
  `spu_lifter.py`, `spu_channels.c`, `spu_drain.c`, `spu_reloc.h`, switch tests);
  `diff 0b0b89b..0ab0d16` == T81's diff (13 files). No T83/T84/rendering change;
  `build.ninja` vs B1: 309 entries, 0 differences after path mapping.

### Lift (VERIFIED)
- All 31 modules regenerated into `generated/spu_raw/wws_reloc_t81c`: 95/95 files
  byte-identical to the T82B lift (`wws_reloc_t82`); `verify_wws_reloc` PASS.
- vs original `wws_reloc`: only renderablejob `spu_recomp.c`; 0xA650 now
  `spu_indirect_branch` (ret_reg −1, ib_plain +1), all 12 cases kept; PM's 14 link
  returns unchanged (reclassified: none). Manifest `a084eee5…d298`, register.c `d347d562…082a`.

### Offline validation (VERIFIED; `t81c/regress.txt`)
PASS: reloc_job, switch_linkret, jobspan, jobspan_path, lifter_reloc, diag_tls
(five-lane TLS), wkl_maxcont and wws_concurrency (default+guest), SPURS scheduler 8/8
(POSIX runner), ppu_trace 6/6, chain_chunks, ls_inline, program_pipeline, disasm_ri10,
mfc_resume, lifter_dedupe, lifter_header_name.
- Five-lane bench, corrected lift (`bench_switch_lanes.py`, `logs/lanes_t81c.log`):
  RESULT PASS — AOT 0 interpreted insns/job (interp 403), outputs = reference,
  spans 1/job/lane, 0 lost, 1 id; interp == AOT final state (1 and 5 lanes).
- Negative controls: T81 lifter → 1 `SPU_RET_REG`, bench aborts at the PM-return
  detector; `test_spu_switch_linkret --old-tree ps3recomp-t81`: old lift unwinds
  (336 interpreted), new lift 0.
- Baseline (unchanged, not caused by T81C): `test_spu_fnms_zero_extended` link failure;
  `lift_selftest`/`spu_lift_selftest` need PS3 SDK; `spu_disasm_audit` needs images.
  Skipped: the POSIX-only fixtures listed in `regress.txt`.

### Build and executable (VERIFIED)
- `build/motorstorm-t81c-aot` (`configure_t81c.cmd`, `build_t81c.cmd`), clang-cl 23.1.3 +
  lld-link, Release `/O2 /Ob2`, AVX2 off: rc 0, 312/312, 0 FAILED.
- Exe SHA-256 `e423f9d42a0d255079d99f55e9ed4cb0a89e3422fea7f999dd7648f7b70bf469`,
  pinned `t81c/ab/exe-t81c/` (`exe_pin_t81c.json`). Existing pins (t70d, t70g, t79,
  t81b, t82b) re-hashed: unchanged.
- `inspect_t81c_exe.py`: 31/31 module sig+hash in image, ctor `.CRT$XCU`, 31 register
  fns, gates PASS. Corrected job-span opener: 1 occurrence. Strings present:
  `maxContention guest=%u applied=%u`, `PS3_SPURS_GUEST_MAXCONT`, `PS3_SPU_AOT_PROF`.
- Object identity (`obj_cmp_t81c.sh`, llvm-objdump per function):
  module objects + register vs T82B identical (32/32); vs T81B only
  `…eEE40_spu_func_0000A650` (20→16 insns); renderablejob obj `294cc4be…5f43`.
  Runtime vs T81B: identical except T82's `spu_channels` (AOT profiler, `spu_indirect_branch`)
  and `spu_drain` (`spu_drain_call`, `spu_irq_regs_maybe_restore`); vs T82B `spu_channels`
  identical and `spu_drain` differs only in `spu_depth_guard` (T81 TLS fix). Byte diffs elsewhere are
  path/anonymous-namespace hashes only.
- Defaults: AOT needs `PS3_SPU_WWS_AOT=1`; guest contention needs
  `PS3_SPURS_GUEST_MAXCONT=1`; profiler/tracer env-only. All off by default.

### Four-arm plan (dry-runs PASS, `logs/dryrun.log`; each launch needs authorization)
Same exe; inherited T70 harness (205 s session cap, `--timeout 210`, fresh HDD, no
input, no TEX_SAVE/RSX readback, all gates kept).
```
py -3 -I generated/analysis/t81/t81c/ab/run_t81c_ab.py dryrun A        # AOT off, contention 1
py -3 -I generated/analysis/t81/t81c/ab/run_t81c_ab.py dryrun B 4000   # AOT on,  contention 1
py -3 -I generated/analysis/t81/t81c/ab/run_t81c_ab.py dryrun C        # AOT off, contention 5 (guest)
py -3 -I generated/analysis/t81/t81c/ab/run_t81c_ab.py dryrun D 4000   # AOT on,  contention 5 (guest)
```
Report grid (len20/21) and race (len76) frames separately with
`t82/t82b/phase_matched.py` and `burst_timeline.py`, plus `ab_report.py`,
`t70f/identity.py`, `t79/tools/t79_overlap.py`.

**Recommended first arm: B** — it reproduces T82B's configuration on the integrated
exe (expect ~0 renderablejob interpreted insns, grid p50 ≈ 73–74 ms) and isolates any
T81 regression before D tests contention 5 with AOT. (HYPOTHESIS until run.)

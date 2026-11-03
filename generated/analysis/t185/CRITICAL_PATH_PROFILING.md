# T185 Critical-path profiling: offline instrumentation and the next experiment

This was an offline task; **no game launches** were made. The instrumented exe built and passed offline validation. All new diagnostics are off by default, and none changes guest state in the tests. The next run is prepared but not executed.

| Item | Value |
|---|---|
| Exe | `build/motorstorm-t185/MotorStormPacificRiftRecomp.exe` |
| SHA-256 | `ee2d6925d74e12e82555a84f91144e89a25eba7001f2a75c331ab5c26565019f` |
| Size | 411,003,904 bytes |
| Code | `ps3recomp-t185` `ddda809a`, branch `agent/t185-critical-path-profiling`, base T183 `766d3575` |
| Game host | `port-t185` = `port-t161` + the diff in the appendix (private copy, as `port-t161`) |
| Lifted code | `generated/ppu-t173-staging`, unchanged; no relift |

Labels: VERIFIED (measured or tested here), PARTIAL, HYPOTHESIS, BLOCKED.

## A. Task creation (`cellSpursCreateTask`)

### Execution path (VERIFIED, code)

`libs/spurs/cellSpurs.c`, all on the calling PPU thread (tid 1 in the race):

| # | Stage (profile name) | Work | Locks / syscalls |
|---|---|---|---|
| 1 | `args` | 8 `vm_read32` of the argument and LS pattern; null and init checks | none |
| 2 | `slot` | `spurs_taskset_take_slot`: first clear bit of the enabled bitset, set it | **global lock-line spinlock** (`spu_lockline_lock`), `spu_coh_notify_write` walk of all registered SPU contexts |
| 3 | `book` | `s_tasks[]` fields; `vm_write32` of the id; `spu_taskset_mark_running`; `spu_taskset2_set_exit`; `spurs_taskset_add_task` (10 guest writes + 2 bitset updates) | `ts_lock` (spin with `Sleep(0)`); lock-line lock ×3 more; `vm_write32` takes it again for reserved lines |
| 4 | `log` | `printf("[cellSpurs] CreateTask(...)")` | stdout lock; **stdout is unbuffered** (`setvbuf(stdout, NULL, _IONBF, 0)` in `main.cpp`), so one synchronous `WriteFile` to the runner's pipe per call. No SPURS or lock-line lock is held |
| 5 | `trace` | `getenv("SPURS_TASKSET_TRACE")` | CRT environment lock and a linear scan, **every call** |
| 6 | `elf` | `spu_elf_image_size` (header walk) | none |
| 7 | `dispatch` | `spu_workload_dispatch_async`, split by `who=dispatch` into the four stages below | |
| 7a | `fp` | fingerprint (cached by `spu_fp_cache`) and registry scan | none (cache) |
| 7b | `job` | `malloc` of the job; `spu_taskset_mark` again; r3 capture | `ts_lock` |
| 7c | `log` | `dispatch HIT` line to stderr (already gated by `PS3_SPU_TASK_QUIET`), one-time context dump | stderr lock |
| 7d | `submit` | pool handoff (SRW lock and condition-variable wake) or `CreateThread` | pool lock |

The worker thread then builds the task context and prints the `[taskset] built` line with `fflush` (T183 gated that line). That happens on the worker, not inside the call.

### Overhead sources

The offline fixture runs the real `cellSpursCreateTask` with a stubbed dispatch (VERIFIED):

| Condition | Mean per call | Breakdown |
|---|---:|---|
| Uncontended | **3.8–3.9 µs** | `trace` 2.8–2.9 µs (the `getenv`); `log` 0.7–0.9 µs (stdout to a pipe, in the fixture); everything else about 0.1 µs |
| Another thread holding the lock-line lock half the time | 6.6–6.9 µs | `slot` grows to about 3 µs, all of it `lockwait` |

In game a call takes **262 µs** (T184 arm P). The call's own work is about 4 µs of that.

So the in-game cost comes from the live environment. The candidates, all HYPOTHESIS until measured:
- lock-line lock contention with the five Havok solver tasks that poll it (section C);
- stdout writes blocking on the runner's pipe;
- the `getenv` in a process with a large environment, while other threads also call `getenv`;
- the pool or `CreateThread` handoff.

The T183 bench measured only stderr writes to a file. That bench and this fixture both exclude the runner's pipe.

### Instrumentation (`PS3_SPU_CREATE_PROFILE=1`)

`runtime/spu/spu_stage_prof.h` is header-only. Each call times its stages with QPC on the stack and folds them into one aggregate under one SRW lock. At most one line per window (`PS3_SPU_CREATE_PROFILE_MS`, default 1000, at least 10) is printed after that lock is released:

```
[spu-create-prof] who=create seq=N window_ms=W calls=C mean_us= p50_us= p95_us= max_us= args= slot= book= log= trace= elf= dispatch= lockwait= lockwait_n= rest=
[spu-create-prof] who=dispatch ... fp= job= log= submit= lockwait= lockwait_n= rest=
```

- Stage values are microseconds per call over the window.
- p50 and p95 come from a log2 histogram with 4 sub-buckets per octave, accurate to within about 9 %.
- `lockwait` is the contended wait inside `spu_lockline_lock` on this thread during the call. It lies inside `slot` and `book`.
- The probe is read only after the lock's first exchange has failed, so the uncontended path is unchanged (one exchange).
- Off: one load per call.

### Logging findings

| Question | Finding | Label |
|---|---|---|
| Why 23,294 CreateTask lines in T184 P | Arm P did not set `PS3_SPU_TASK_QUIET`. Even with it set, T183's quiet gated only the four task-run lines, not the `printf` in `cellSpursCreateTask` | VERIFIED |
| Synchronous console output | Yes: stdout is unbuffered in the game host, one write per line | VERIFIED (code) |
| Global stdout lock | Yes, the CRT stream lock for the `printf` | VERIFIED (CRT behaviour) |
| Frequent flushes | stdout: every call (unbuffered). stderr: the `[taskset] built` line on the worker `fflush`es | VERIFIED |
| Contention between guest and SPU threads | Possible on the stdout and stderr stream locks: workers print to stderr, and the frame thread prints to both | HYPOTHESIS |
| Output while holding SPURS locks | No: the `printf` runs after every lock-line and `ts_lock` section | VERIFIED (code, test pin) |
| Share of the 5.2 ms per frame due to logging | Not known offline. Arm Q's `log` stage measures it | BLOCKED until run |

### Changes made

- **`PS3_SPU_TASK_QUIET=1`** now also caps the CreateTask stdout line: the first 64 are kept, and the rest are not formatted.
  - Error and warning lines (`REJECT`, `no free task id`) stay unconditional.
  - Default behaviour is unchanged.
- **The `cellSpursCreateTask` and `spu_workload_dispatch_async` bodies** move into `create_task_impl` and `dispatch_async_impl`, behind thin wrappers. With the profile off, the wrapper is one load and a tail call.
- **`spu_coherency.c`**:
  - the contended path was restructured with the same spin, pause and yield;
  - the probe was added;
  - a no-op default is provided through `/alternatename` for fixtures that link `cellSpurs.c` alone.

**Remaining unknowns:** the in-game split of the 262 µs. In particular, how much is lock-line wait and how much is pipe-blocked output. Arm Q answers that.

## B. PPU sampling in the game host

### Original defect (VERIFIED)

- `ps3_sampler_start()` was called only from `runtime/ppu/tests/boot_main.cpp`.
- The game host (`port-t161/main.cpp`) never called it, so the linker stripped the sampler from the game exe.
  - The T183 exe contains none of its strings (`[samp] sampling every`, `pdata self-check`, `[samp] map:`).
  - The T185 exe contains all of them.
- Three further defects, now fixed:
  - **No stop function.**
  - **Deadlock hazard:** `GetModuleHandleExA`, which takes the loader lock, ran while the target thread was suspended.
  - **Low sample rate:** a whole-process thread snapshot per sample capped a "1 ms" sampler at about 35 samples/s (measured offline).

### Changes

| Where | Change |
|---|---|
| `port-t185/main.cpp` | `ps3_sampler_start()` right before `ppu_run`, on the thread that runs guest tid 1, after `ppu_recomp_register` and the HLE/syscall setup; `atexit(sampler_stop_at_exit)` for a guest `sys_process_exit`; `ps3_sampler_stop(2000)` after `ppu_run` returns |
| `ppu_loader.cpp` | `ps3_sampler_stop(wait_ms)`: flag, join, final report; safe twice, before a start, or unset. One sampler per process. While a thread is suspended: only the RIP lookup, stack scan and phase read; module lookup after the resume. `PS3_SAMPLE_MAIN`: one open handle, no snapshot per pass |
| `ppu_loader.cpp` + `ppu_trace.cpp` | `PS3_SAMPLE_PHASES=<fn>:<enter>[:<exit>],...`: PT's entry and exit of traced `fn=` sites on guest tid `PS3_SAMPLE_PHASE_TID` (default 1) set the current phase, noted before PT's per-site log limits. Each sample is counted per phase |

**Invalid contexts:** the sampler reads host thread contexts and the host stack only, never a `ppu_context`. A thread that exits between snapshot and suspend fails `OpenThread` or `SuspendThread` and is skipped.

**Error handling:** a crash ends the process and the thread with it; there is no report then. The runner's timed kill at race + 75 s also skips the final report. The periodic reports (0.5, 1, 2, 4, 8 s, then every 10 s) are what that run reads.

### Exact runtime flags

| Flag | Meaning |
|---|---|
| `PS3_SAMPLE=<ms>` | period; 0 or a non-number means 5 |
| `PS3_SAMPLE_MAIN=1` | any value: only the boot thread, stack-walk credit to the nearest lifted return address |
| `PS3_SAMPLE_TOP=<n>` | 1–64 ranked functions; each report then starts from zero. The brief's `PS3_SAMPLE_TOP=1` ranks one function; the semantics are kept as they were |
| `PS3_SAMPLE_PHASES` | as above; for this game `72E1E0:pre,30B710:havok:post,50D868:emit,50C818:spin:tail` (each is a `fn=` site in `cpath_sites.cfg`) |
| `PS3_SAMPLE_PHASE_TID` | guest tid of the phase thread, default 1 |

### Output format

```
[samp] --- report at t=<ms>ms ---         (or: --- final report at t=<ms>ms (stop) ---)
[samp] <total> samples, <guest> in guest code (<pct>%)
[samp] phase none=<n> pre=<n> havok=<n> post=<n> emit=<n> spin=<n> tail=<n>
[samp]   <pct>%  func_<8 hex>  (<samples>)  ph=<phase>:<n>,...
[samp] host <pct>%  <module>  (<n>) ...   [samp] tid ... guest= ntdll= other= ...   [samp] rva 0x... (host RVAs)
```

**Names:** the lift has no symbols, so functions are reported by guest address (`func_XXXXXXXX`). The source mapping is the lifted file holding `func_XXXXXXXX` in `generated/ppu-t173-staging/ppu_recomp_*.cpp` (private). No names are invented.

### Offline validation (VERIFIED)

`tools/test_sampler_lifecycle.py` builds the real `ppu_loader.cpp` with a synthetic `function_table` and drives the game host's sequence: start ×2, busy guest functions in phases `havok` then `post`, stop ×2. Its pins also check the `main.cpp` start/atexit/stop order and both PT phase notes. 20 checks pass:

| Check | Result |
|---|---|
| Unset | no thread, no output, stop a no-op |
| On | exactly one extra thread (also after a second start); gone after stop; final report printed once |
| Resolution | in the suite run: hot function 601 samples, warm 304; the unused function 7 (under 1 %; the known extent caveat for host code right after a lifted body; the test allows 5 %) |
| Phases | hot tagged `havok` only, warm `post` only; a note from guest tid 2 did not move the phase |

**Remaining limitations:**
- Not run in game yet, so runtime sampling of the real frame thread is UNVERIFIED until arm Q.
- Each sample suspends tid 1 for a few µs, about 500 a second at `PS3_SAMPLE=2` with `timeBeginPeriod(1)`. That is a small, unmeasured slowdown, and the reason for control arm N.
- Phase `emit` covers ExecutePushBuffer and the gap until the spin.
- Linker identical-code folding can merge trivial lifted bodies; a hot empty stub means "some trivial function".

## C. Havok solver synchronization (image `341580667`, lift `spu_45c1b7bf…`)

Read-only static inspection of the lifted source. The lifted source and addresses are private; LS addresses are given.

| LS site | Shape | Classification |
|---|---|---|
| `0x174D4` → `0x17518` | GETLLAR, read a counter word, clamp a claim (byte field), PUTLLC; on failure branch back through a trampoline (`g_spu_trampoline_fn`, a return to the drain loop) | **work-queue claim** (atomic fetch-and-add style), retry on contention |
| `0x1778C` | GETLLAR, `ahi +1` on a halfword, PUTLLC, retry | **ticket take** |
| `0x1781C` | GETLLAR, `rotqby` + `ceqh` against the taken ticket, `goto 0x1781C` while unequal: **no PUTLLC, no event wait** | **ticket-lock wait: busy poll of an unchanged line** |
| `0x17638` / `0x176C8` | GETLLAR, conditional PUTLLC; else `rdch SPU_RdEventStat` (blocks for the lock-line-lost event) | event-driven wait (efficient form) |
| `0x17954`, `0x17E60`, `0x17F38`, `0x17C88` | GETLLAR, PUTLLC, retry on failure | atomic updates |

**Instructions:** MFC command `0xD0` (GETLLAR) and `0xB4` (PUTLLC) written to `MFC_Cmd` through `spu_wrch`, status from `MFC_RdAtomicStat`. There are 8 GETLLAR and 6 PUTLLC sites.

- **Is it waiting for another task, on an unchanged value?** The `0x1781C` loop re-reads the line until the "now serving" halfword equals its ticket. That is a lock held by another solver task.
  - VERIFIED as code shape.
  - HYPOTHESIS that it dominates: the T183 counts are 6,323 GETLLAR against 100 PUTLLC per run, which fits most GETLLARs being this poll.
- **Unnecessary host synchronization (HYPOTHESIS):** every poll iteration takes the **process-wide** lock-line spinlock (`spu_lockline_lock`), registers the reservation (`spu_coh_reserve`) and copies 128 bytes twice. Five solvers polling contend for the same lock that:
  - the lock holder needs for its own atomics and DMA coherence;
  - the PPU needs for `cellSpursCreateTask` (section A) and reserved-line stores.

  That can lengthen the lock holder's critical section, which is what the waiters wait for. Offline, one poll iteration costs about 1.0 µs uncontended (`test_spu_llar_profile`: 117 iterations in 0.12 ms, including `spu_wrch` issue), against tens of ns on hardware.
- **Reservation tracking cost:** not separable offline; it is inside T183's `mfc_ns`, 10.9 % of solver task time. HYPOTHESIS that it is more than necessary.

**No change** was made to synchronization, atomics, reservations, ordering or physics.

**Opt-in counter `PS3_SPU_LLAR_PROFILE=1`** (`spu_channels.c`):
- A GETLLAR whose 128 bytes equal the same context's previous snapshot of that line counts as "unchanged".
- A run of unchanged GETLLARs on one line by one thread is a spin episode, timed by QPC. The episode ends when the data changes, another line is taken, or a PUTLLC is issued.
- Cumulative per (image, line), top 12 lines every second:

```
[spu-llar-prof] seq= t_ms= img= line=0x.. getllar= unchanged= putllc= episodes= spin_iters= spin_ms= max_iters=
```

Read-only: it compares the line copy and snapshot the GETLLAR already made, changes neither, and prints after the lock is released. A reused pool worker starts with no open episode.

`tests/test_spu_llar_profile.py` checks it (VERIFIED):
- exact counts for a scripted ticket-lock poll (A: `getllar=123 unchanged=117 putllc=3 episodes=3 spin_iters=117 max_iters=39`; B: no spin);
- the state hash is identical unset, on and malformed.

**Follow-up measurement:** run Q gives per-line spin time per frame for the solver. Compare it with the solver's 10.5 ms per task. If spin dominates and the lock is contended mostly by the spinners, the candidate is a cheaper but semantically identical GETLLAR on an unchanged reserved line (section D, #1). That needs a correctness design (a seqlock-style read) and its own authorization.

## D. SPU execution efficiency (static, solver and collide lifts)

Counts in the lifted sources (VERIFIED, `grep` of `spu_recomp.c`):

| Construct | Solver `45c1b7bf` | Collide `d51c6ceb` | Cost per use |
|---|---:|---:|---|
| Cross-group transfers through the trampoline (`g_spu_trampoline_fn = …; return`) | 210 | 302 | return to `spu_drain_call`, which per transfer does lockstep and task-step checks and an interrupt check |
| Lifted calls (`host_depth++ … spu_drain_call`) | 255 | 529 | a depth guard and a drain loop per call |
| `SPU_CHAIN` / `SPU_CHAIN_BACK` | 826 / 336 | 1,744 / 698 | per transfer: 4 global and field tests incl. a volatile `event_status` read; backward ones also a budget |
| `spu_wrch` / `spu_rdch` (MFC issue is 6 `spu_wrch` calls per command) | 619 / 114 | 569 / 104 | out-of-line calls with a channel switch |
| LS 128-bit reads / writes | 3,574 / 1,911 | 5,541 / 3,203 | inline: mask plus 4 × `memcpy` + `bswap` |
| `spu_shufb` | 1,311 | 1,666 | inline (SSSE3 path) |

Measured context (T183/T184): solver and collide tasks are 97 % on-CPU at about 10.6 ms each. MFC time is 10.9 % (solver) and 21.7 % (collide, 3,190 DMA GETs of about 280 B per run) of task time.

Top three candidates; none is confirmed as the dominant cost:

1. **GETLLAR poll cost under the global lock-line lock (solver).** HYPOTHESIS.
   - Bound: solver MFC time is 1.15 ms of 10.5 ms per task, but the wait it causes is the lock-hold time, which cheaper polls could shorten.
   - Measure first with `PS3_SPU_LLAR_PROFILE` (run Q).
2. **MFC command issue (collide).** VERIFIED that it is a measurable share: 21.7 % of collide task time, about 2.3 ms per task, is MFC.
   - Each DMA is 6 out-of-line `spu_wrch` calls plus queueing for small (≈280 B) GETs.
   - A fused "issue on `MFC_Cmd` write" fast path keeps the semantics; the potential is ≤ 2.3 ms per collide task, an upper bound.
3. **Cross-group trampolines and per-call drain.** HYPOTHESIS: 510 + 784 sites. Their per-transfer cost is not measured; an SPU-side sampler or step counter would be needed.

The LS access helpers and `shufb` are already inline and SIMD-friendly. No inefficiency was confirmed there.

## E. Validation

| Check | Result | Label |
|---|---|---|
| Build `tools/build_t185.cmd` (private), recipe of T183 with `ps3recomp-t185` + `port-t185` | rc 0, 312 steps; no source newer than the configure step | VERIFIED |
| Exe | `ee2d6925…019f`, 411,003,904 bytes; contains the sampler, create-profile and llar-profile strings; T183 exe has no sampler strings | VERIFIED |
| Full suite `run_all_t185.py --jobs 4` through `env_t169.cmd` | **162 PASS, 2 FAIL, 43 SKIP**, including `test_ppu_lift` (1,533 PPU conformance checks), `test_spu_event_lr_race`, `test_cpath_trace`, `test_vm_store_fast`, `test_icall_fast` | VERIFIED |
| Failure 1: `test_spu_task_pool` | source pin looked for the body in `spu_workload_dispatch_async`, which moved into `dispatch_async_impl`. Pin updated (in `ddda809a`); rerun: 3 seeds × 2,020 checks, 0 failures | VERIFIED |
| Failure 2: `test_spurs_kick_wake` | flaky timing assertion (`on × 2 < off` median); **fails on the unchanged T183 tree too** (T183: 2 of 4 runs pass, T185: 2 of 5, same session). Wake effect visible every time (p90 15.8 ms off vs 0.1 ms on) | VERIFIED as pre-existing |
| New: `test_create_task_profile` | 21 checks: real `cellSpursCreateTask`, 30,000 calls: same task ids, **guest-memory hash** and dispatches unset vs profile on; every stage named; stages + rest = mean; lockwait 0 uncontended, > 0 and inside slot + book contended; quiet → 64 lines with the same hash; wrong values warn once | VERIFIED |
| New: `test_sampler_lifecycle` | 20 checks (section B) | VERIFIED |
| New: `tests/test_spu_llar_profile.py` (not in the suite, like `test_spu_task_stats.py`) | 12 checks (section C) | VERIFIED |
| `tests/test_spu_task_stats.py` | 0 failures | VERIFIED |
| Off by default | each switch: unset → nothing printed, no thread, same state (the three tests) | VERIFIED |
| Code audit `--tree` on a copy of the 14 changed and new files | passed. The whole tree has 25 items, the same as base `766d3575` (pre-existing `scratch/`, `runtime/spu/tests/out_*`) | VERIFIED |
| Suite rewrites of `scratch/ppu_conformance*` | restored | VERIFIED |
| Commits | code `ddda809a` (`ps3recomp-t185`); this report: see the root-t185 log | |

**Unresolved correctness concerns:**
- The sampler has run in game on no build yet, so its suspend cost on tid 1 is unmeasured.
- `PS3_SPU_LLAR_PROFILE` adds a QPC and a 128-byte compare per GETLLAR, about 6,300 per solver task. That is a diagnostic slowdown of the very loop it measures, a few percent of a task by the offline cost. So arm Q's frame time is not a performance number.

## F. Prepared next runtime experiment (not executed)

The runner is `generated/analysis/t185/ab/run_t185.py`, generated by `tools/make_runner_t185.py` from `run_t183.py`. It is pinned to `ee2d6925…`, has a cap of 3 launches and launches one arm per invocation. `prepare`, `envcheck` and `dryrun Q` passed, with 7,585 MiB VRAM free; nothing was launched and there is no lock file. Stops, cache and PT configuration are as T183: race + 75 s, a 205 s timeout, the warm shader cache copied from T183, and `cpath_sites.cfg`.

| Arm | Env (all = T184 arm P: T183 S + `PS3_SPU_TASK_POOL=1`) | Purpose |
|---|---|---|
| **Q** (primary) | P + `PS3_SAMPLE=2 PS3_SAMPLE_MAIN=1 PS3_SAMPLE_TOP=40 PS3_SAMPLE_PHASES=72E1E0:pre,30B710:havok:post,50D868:emit,50C818:spin:tail` + `PS3_SPU_CREATE_PROFILE=1` + `PS3_SPU_LLAR_PROFILE=1`; quiet **off** | ranked tid-1 guest functions by phase, especially `post`; per-stage CreateTask cost incl. `log` and `lockwait`; solver spin time per line |
| N (control) | P without `PS3_SAMPLE*`, no T185 flags | frame time with no new instrumentation. Q − N bounds the instrumentation overhead; N − T184 P (68.5 ms) the exe change |
| L (logging A/B) | N + `PS3_SPU_CREATE_PROFILE=1` + `PS3_SPU_TASK_QUIET=1` | per-call stages with quiet against Q's: what quiet removes from the 262 µs; frame time against N for what it buys |

Analysis:
- `tools/analyze_t185.py <tag>`: create/dispatch stages per call and per frame, llar deltas per frame, samples summed over the race window with phase splits.
- `T183_SERIES=t185 T183_TAG=<tag> tools/arm_s_t183.py` (updated): frame phases, task stats and thread CPU.

Q alone answers the two questions:
- which guest functions fill the ~20 ms `post` phase;
- what part of the 5.2 ms/frame of task creation is logging (the `log` stages) against lock wait and handoff.

N and L only separate instrumentation and logging effects from frame time. Each launch needs its own authorization.

## Files

| File | Where |
|---|---|
| `CRITICAL_PATH_PROFILING.md` (this report) | `root-t185/generated/analysis/t185/` |
| `tools/analyze_t185.py`, `tools/make_runner_t185.py`, `tools/run_all_t185.py` | same |
| `t183/tools/arm_s_t183.py`, `arm_s_place_t183.py` | updated: `T183_SERIES` |
| `build_t185.cmd`, `port_main_t185.patch`, `run_t185.py`, build and suite logs | private: main tree `generated/analysis/t185/`. The audit blocks `.cmd` and `.patch` under `generated/`; the runner holds local paths |

## Appendix: game-host change (`port-t161/main.cpp` → `port-t185/main.cpp`)

```diff
--- port-t161/main.cpp
+++ port-t185/main.cpp
@@ -407,6 +407,12 @@
 #include "port_cpu.h"
 #endif
 
+#ifdef _WIN32
+void ps3_sampler_start(void);            /* ppu_loader.cpp: PS3_SAMPLE=<ms>, a no-op when unset */
+int  ps3_sampler_stop(unsigned wait_ms); /* ppu_loader.cpp (T185): ends the sampler, last report */
+static void sampler_stop_at_exit(void) { ps3_sampler_stop(2000); }
+#endif
+
 static void harness_guest_caller(uint32_t opd, uint64_t a0, uint64_t a1,
                                  uint64_t a2, uint64_t a3, uint64_t a4,
                                  uint64_t a5, uint64_t a6, uint64_t a7)
@@ -471,8 +477,21 @@
     printf("\n[boot] dispatching entry OPD 0x%08X (stack top 0x%08X)\n\n",
            entry, STACK_TOP);
 
+#ifdef _WIN32
+    /* T185 PS3_SAMPLE=<ms> (runtime/ppu/ppu_loader.cpp): the PPU sampler. Started here, on the
+     * thread that runs the guest's boot thread, after the lifted function table is registered
+     * (ppu_recomp_register) so samples resolve to guest functions. Nothing starts unless PS3_SAMPLE
+     * is set. A guest sys_process_exit ends in exit(), so the stop is registered with atexit too;
+     * stopping twice is harmless. */
+    ps3_sampler_start();
+    atexit(sampler_stop_at_exit);
+#endif
+
     int rc = ppu_run(entry, STACK_TOP);
     printf("\n[boot] ppu_run returned %d (entry function unwound)\n", rc);
+#ifdef _WIN32
+    ps3_sampler_stop(2000);
+#endif
 
     /* A title that called sys_process_exit never reaches this line: that path
      * ends in the host exit(). Getting here means the entry function returned
```

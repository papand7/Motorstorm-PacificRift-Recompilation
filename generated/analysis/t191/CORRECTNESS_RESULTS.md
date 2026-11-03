# T191 correctness results

Tree `ps3recomp-t191` (T189 `a26240c5` plus the T191 change). All offline, Windows 11, clang 23.1.3. No game launched. Log: `generated/analysis/t191/logs/test_spu_ib_fast.txt`.

## Differential harness

`py -3 tools/test_spu_ib_fast.py --seeds 4 --iters 20000` (under `generated/analysis/t169/tools/env_t169.cmd`). Result: **32 checks reported PASS, 0 FAIL; `test_spu_ib_fast: 0 failure(s)`**.

Every case runs the same context state through the full resolver (context A, switch off) and the fast path (context B, switch on), twice (B's second run is a cache hit), and requires:
- the same stub called, the same number of times, seeing the same `pc`, `resident_task`, `reloc_delta`, a register the iret restore writes, and `int_enable`;
- the **whole `spu_context`** (every register, flag, code slot, delta, the saved interrupt file; the local store by checksum) identical afterwards.

| Suite | Checks | Covers |
|---|---:|---|
| `directed` | 4,148 | ordinary fill then hit (counters: first branch is one fill, the next three are three hits); unregistered, `+1`/`+2` misaligned, high-bit (`0x7A000000 \| pc`, masks to a valid target), beyond-LS and pc 0 targets; overlay switch none/resident/evicted/back/unknown id; image switch among 4 images and the 0 wildcard; code-slot owner, first-slot-wins, relocatable slot (delta), unrecognized owner, slots cleared; policy mode ordinary, exit-to-kernel, select-workload; taskset syscall address; job-return address; image 23; interrupt-return restore (resume pc matches / differs / interrupts disabled); `resident_task` cleared below the task region; task-region branches; a function registered at run time (epoch moves; the next branch refills, the rest hit); an unrelated registration (older entries refilled); 2,000 contexts re-created at the same address |
| `directed --tasks` | 4,156 | the same with a taskset task entry registered |
| `random` x 4 seeds x {plain, `--tasks`} | 80,001 each (640,008) | 20,000 random steps each: target (registered, grid, misaligned, high bits, arbitrary, service addresses), image, wildcard / image 23, overlay, `resident_task`, policy mode, pending iret with random resume pc and enable, random code slots (owner / unrecognized / relocatable / cleared), TaskInfo ELF in LS, context re-creation (1 in 64). Each seed asserts that hits, fills and resolver fallbacks all occurred (coverage, so the suite cannot pass by never using the cache) |
| `threads` | 2 | 4 host threads at once, own contexts, shared registry; each case compared with a reference made single-threaded with the switch off |
| `stackreset` | 7 | a registered one-way stack-reset entry with a live host frame: the check runs on the fast path and unwinds identically |
| `envinit` | 10 | `PS3_SPU_IB_FAST` unset / `0` / `yes`: off; `1`: on; with each of `SPU_POLLTRACE`, `SPU_IBCOV`, `SPU_OVERLAY_TRACE_IMAGE`, `SPU_JOBTRACE`, `YDKJ_POLTRACE`, `PS3_SPU_PCWATCH` set: off with the `ignored` log line |

Seeds are fixed (`random <seed> <n>`); the first failing iteration and its RNG state are printed for replay.

## Negative controls (each is a textual mutation of `spu_channels.c`, built and run through the suite; all must fail it)

| # | Mutation (a disabled invalidation or a skipped transition) | Detected |
|---:|---|---|
| 1 | cache key omits the resident overlay | yes |
| 2 | cache key omits the image id | yes |
| 3 | fast path ignores policy mode | yes |
| 4 | fast path ignores a pending interrupt return | yes |
| 5 | skips the `resident_task = 0` clear | yes |
| 6 | relocatable code slots dispatched without the delta (`link_base` ignored) | yes |
| 7 | code-slot owners ignored | yes |
| 8 | registry epoch not compared (invalidation off) | yes (the refill-after-registration counter checks) |
| 9 | stack-reset check skipped | yes |
| 10 | task-region ownership not consulted although registered | yes |

**10 of 10 detected.** The mutants are built from the same source tree by `tools/test_spu_ib_fast.py` (patterns must match exactly once or the test fails).

Note on #8: with an append-only registry, a stale-epoch entry cannot return a different function, so control 8 is caught by the mechanism check (a first branch after a registration must refill), not by a wrong dispatch. That is stated in `CACHE_COHERENCE.md`.

## Sanitizers (`generated/analysis/t191/tools/run_sanitizers.py`)

| Sanitizer | directed | random seed 3 `--tasks` (20,000) | threads |
|---|---|---|---|
| AddressSanitizer | 4,148 checks, 0 failures | 80,001, 0 | 2, 0 |
| UndefinedBehaviorSanitizer | 4,148, 0 | 80,001, 0 | 2, 0 |

ThreadSanitizer is not available for Windows targets; concurrency is covered by the 4-thread differential only (the fast path shares no mutable state across threads).

## Existing suite (no regressions)

`generated/analysis/t169/tools/env_t169.cmd py -3 generated/analysis/t188/tools/run_all_t188.py ps3recomp-t191` (log `logs/suite_run.txt`): **162 PASS, 43 SKIP, 3 FAIL.**
- T189 had 161 PASS: the extra one is `test_spu_ib_fast`.
- The 3 failures are the known set: `test_t169_profile` and `test_t169_rt_reinterp` (fail identically on the T183 base on this machine) and `test_spurs_kick_wake` (a flaky timing assertion; it passed in the other run of this same tree).
- `test_spu_jobspan` (which pins the first lines of `spu_indirect_branch`), `test_spu_reloc_job`, `test_spurs_*` and `test_spu_*` pass with the switch off.
- A first suite run overlapped a second one I started by mistake, and the overlap made `test_d3d12_shader_cache` fail once; it passes in the clean run. I could not stop the stray first run (the stop was denied), so I waited for it to end and reran.

## Not covered

- The existing runtime tests were not rerun with `PS3_SPU_IB_FAST=1`.
- The `PS3_FTRACE_SPUJOB` tracing path is checked per branch but the differential never turns tracing on.
- Policy-mode and relocatable branches are tested only as "same result as the resolver", since both arms run the resolver.
- No lifted program, no homebrew SPU program.
- POSIX builds were not run.

# T191 implementation

Branch `agent/t191-spu-fast-dispatch` (worktree `ps3recomp-t191`), from T189 `a26240c5`. Local only: not pushed or merged. No game launched. T187-T190 branches and T190's prepared executable and A/B environment are untouched.

Code commit: `32203ae6` (see also `NEXT_STEPS.md`).

## Source changes

| File | Change |
|---|---|
| `runtime/spu/spu_channels.c` | **+~125 lines, no line of the resolver edited.**<br>1. `g_spu_registry_epoch`, bumped by `spu_register_function` (release ordering).<br>2. Before `spu_indirect_branch`: the thread-local cache `t_ibc[512]`, `spu_ib_fast_init` (reads `PS3_SPU_IB_FAST`), `spu_ib_fast_try`, and test hooks `spu_ib_fast_set / _flush / _stats / _reset_stats`.<br>3. One hook block in `spu_indirect_branch`, right after the job-span tracing block (so the existing `test_spu_jobspan` ordering checks still hold) |
| `tests/test_spu_ib_fast.c` | differential harness (directed, seeded random, threads, stack reset, env init, benchmark driver) |
| `tools/test_spu_ib_fast.py` | builds the harness against the real SPU runtime, runs the suites and the ten negative controls |
| `tools/bench_spu_ib_fast.py` | interleaved A/B benchmark, hit rates, multi-thread scaling, default-path cost |

## Feature flags

| Flag | Where | Effect |
|---|---|---|
| `PS3_SPU_IB_FAST=1` | environment, read once at the first indirect branch | enables the cached dispatch. Unset, `0`, or any other value: the resolver exactly as before |
| diagnostic variables (`SPU_OVERLAY_TRACE_IMAGE`, `SPU_IBCOV`, `SPU_POLLTRACE`, `YDKJ_POLTRACE`, `SPU_JOBTRACE`, `LBP_HLE_JOBDONE`, `SPU_JOBEXEC`, `SPU_JOBEXEC_DUMP`, `PS3_SPU_PCWATCH`) | environment | with `PS3_SPU_IB_FAST=1` the fast path is switched off for the process and logs `[spu-ib-fast] PS3_SPU_IB_FAST=1 ignored: <var> is set` |
| `-DSPU_IB_FAST_STATS` | compile time of `spu_channels.c` | hit and fill counters (thread-local). Off in normal builds: the hit path has no counter |
| `PS3_FTRACE_SPUJOB` | existing | checked per branch: tracing on means resolver |

On success it logs once: `[spu-ib-fast] PS3_SPU_IB_FAST=1: cached dispatch for ordinary indirect branches`.

It is independent of T187's `PS3_SPU_MFC_FAST` (different branch, different code) and of T189's `PS3_VM_STORE_INLINE` / `PPU_INLINE_STORES`. It needs **no relift and no change to lifted code**: it sits inside the library function every lifted dispatch site already calls, so it benefits every title built against the library, current lifts included. (Lifts that select `spu_indirect_branch_mt` at compile time do not reach it.)

## Default behaviour

- The resolver is textually unchanged. With the switch off the hook is one load of a `volatile int` and a predicted branch (measured: within +-3 % of the same harness with the hook removed, `PERFORMANCE_RESULTS.md`).
- `test_spu_jobspan.py`, which pins the order of the first lines of `spu_indirect_branch`, passes unchanged.
- The full existing suite is unchanged (`CORRECTNESS_RESULTS.md`).

## Build identifiers

- Compiler: clang 23.1.3 (`build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc`) through `generated/analysis/t169/tools/env_t169.cmd` (the `cc_shim`), `-O2 -msse4.1 -ffp-contract=off`, on Windows 11.
- No game executable was built from this tree. A game build needs nothing beyond the library change; the in-game A/B plan is in `NEXT_STEPS.md`.

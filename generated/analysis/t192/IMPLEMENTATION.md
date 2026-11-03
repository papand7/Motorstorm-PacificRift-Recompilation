# T192 implementation

Branch `agent/t192-spu-reloc-dispatch` (worktree `ps3recomp-t192`), from T191 `32203ae6`. Local only: not pushed or merged. No game launched. T187-T191 branches, T190's prepared executable (`build/motorstorm-t190`) and its A/B environment are untouched. Code commit: `cc386f42`. Reports: branch `agent/t192-spu-reloc-dispatch-report` (worktree `root-t192`, from T191 reports `982fbfe`).

## Source changes (`runtime/spu/spu_channels.c`, about +190 / -25 lines; the resolver text is unchanged)

1. **Relocatable slots are served** (Phase C). In `spu_ib_fast_try`: a slot with `link_base != 0` and a positive owner builds the key `(pc - lsa + link_base) | SPU_RELOC_KEY_BIT`, mode `-3`, and the delta `lsa - link_base`; on a hit or a fill the delta is written to `ctx->reloc_delta` (the one state write the resolver makes on this path). Lookup, fallback and miss behaviour are the resolver's. A non-positive owner, a lookup miss and every state T191 refused still go to the resolver.
2. **Fallback counters** (Phase A), under `-DSPU_IB_FAST_STATS` only: `t_ibr[]`, `spu_ibf_pre`, probe classification, flush/report/atexit; test API `spu_ib_fast_reasons / _totals / _thread_flush / _report / _test_trace`.
3. **Eligibility cost** (Phase D): the hook reads the mode once into a local (`int fm = g_spu_ib_fast`), instead of three volatile loads. `spu_ib_fast_try` is ordered cheapest-first (tracing, service addresses, image 23, task region, negative overlay, slots).
4. **Negative `resident_ovl`** is refused (`d_other`): it would alias the cache's owner-mode keys (a latent T191 corner; no known producer).
5. **Knob** `PS3_SPU_IB_FAST_RELOC=0` restores the T191 behaviour (relocatable slots refused), for A/B isolation and as a field fallback.

`tests/test_spu_ib_fast.c`, `tools/test_spu_ib_fast.py`, `tools/bench_spu_ib_fast.py` are extended (see the other reports). `spu_indirect_branch_mt` is untouched.

## Feature flags

| Flag | Effect |
|---|---|
| `PS3_SPU_IB_FAST=1` | as T191; now also serves relocatable slots |
| `PS3_SPU_IB_FAST_RELOC=0` | with the above: relocatable slots refused (T191 behaviour). Log line says so |
| diagnostic variables | as T191 (fast path off, log line) |
| `-DSPU_IB_FAST_STATS` | compile time: counters and the exit report |
| `PS3_FTRACE_SPUJOB` | tracing on: every branch is `d_trace` |

Unset or any other value of `PS3_SPU_IB_FAST`: resolver exactly as before. No relift, no change to lifted code; no game-specific address or table anywhere (`GENERALIZATION.md`).

## Phase D result (what was and was not done)

| Question | Finding |
|---|---|
| Redundant eligibility checks | the mode word was loaded three times (volatile): one load now. `ps3_ft_spujob_ret()` is evaluated in the resolver's trace block and again in `try` (two compares); sharing it would edit the resolver's first lines, which `test_spu_jobspan` pins, so it was left |
| Repeated ownership lookups | one scan of 4 slots, skipped when the four `image_id`s are all 0 (an OR of four loads) |
| Expensive epoch read | acquire load = a plain `mov` on x86 and read once per branch after the slot scan; nothing to remove |
| Cheap rejection | policy mode / `irq_saved` are rejected by two loads before `try` is called (already so in T191) |
| Negative cache for permanently ineligible states | **not built.** Ineligibility is decided by a handful of loads of fields already in L1; a negative entry would need its own probe (hash, compare, epoch) that costs at least as much, and it would need invalidation on every context-field change. The measured floor of the rejection cost is about 0.4 ns (~7 %) in policy mode (`PERFORMANCE_RESULTS.md`) |
| Repeated cache misses on invalid targets | an unresolved target costs the lookup (the cache cannot hold "not found": a later registration would have to invalidate it) and then the full resolver. Measured: within noise of the resolver (`unres`, 1.01x) |

## Build identifiers

clang 23.1.3 (`build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc`) through `generated/analysis/t169/tools/env_t169.cmd`, `-O2 -msse4.1 -ffp-contract=off`, Windows 11, 12 logical CPUs. No game executable was built from this tree.

## Commands

```
generated\analysis\t169\tools\env_t169.cmd py -3 ps3recomp-t192/tools/test_spu_ib_fast.py --seeds 4 --iters 20000
generated\analysis\t169\tools\env_t169.cmd py -3 generated/analysis/t192/tools/run_sanitizers.py
generated\analysis\t169\tools\env_t169.cmd py -3 ps3recomp-t192/tools/bench_spu_ib_fast.py --t191-tree ps3recomp-t191 --rounds 7 --iters 4000000 --threads 1,2,4,8
generated\analysis\t192\tools\run_suites_t192.cmd      (existing suite: switch off, then PS3_SPU_IB_FAST=1)
```

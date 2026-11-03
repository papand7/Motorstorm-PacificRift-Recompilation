# T191 offline performance results

**Offline microbenchmark only. No game launched. No FPS claim.** A synthetic dispatch speedup says nothing about a frame until an authorized in-game A/B (`NEXT_STEPS.md`).

## Method

`py -3 tools/bench_spu_ib_fast.py --rounds 7 --iters 4000000 --threads 1,2,4,8` (log `logs/bench_spu_ib_fast.txt`). The harness calls `spu_indirect_branch` directly in a loop, landing on a stub that returns, so each number is the dispatch plus the stub call and loop (the same in both arms). One harness process per (arm, pattern, thread count), interleaved A B per round, 7 rounds; the median is shown with min-max. Machine: 12 logical CPUs, Windows 11, otherwise idle, clang 23.1.3 `-O2 -msse4.1`. Latency builds have no counters; the hit rates come from a second build with `-DSPU_IB_FAST_STATS`.

- **A** = full resolver (switch off). **B** = `PS3_SPU_IB_FAST=1`.

## Dispatch latency, hit rate, scalability

| Pattern | Threads | A ns/branch (min-max) | B ns/branch (min-max) | B/A | Hit rate |
|---|---:|---|---|---:|---|
| stable (one target) | 1 | 6.39 (6.12-6.53) | 4.51 (4.38-5.28) | **0.71x** | 100.00 % |
| stable | 2 | 6.44 (6.30-9.67) | 4.46 (4.42-4.48) | 0.69x | |
| stable | 4 | 6.51 (6.48-8.63) | 4.68 (4.56-4.80) | 0.72x | |
| stable | 8 | 10.94 (8.98-11.76) | 6.79 (6.36-8.09) | 0.62x | |
| random (200 targets) | 1 | 15.02 (14.91-15.28) | 13.85 (13.75-14.28) | **0.92x** | 99.99 % |
| random | 2 | 15.07 (14.93-15.18) | 13.85 (13.78-14.29) | 0.92x | |
| random | 4 | 15.32 (15.20-16.10) | 14.12 (14.01-14.96) | 0.92x | |
| random | 8 | 18.25 (17.62-18.84) | 15.80 (15.55-15.95) | 0.87x | |
| overlay replaced on every branch | 1 | 17.52 (17.38-17.75) | 12.92 (12.79-13.27) | **0.74x** | 100.00 % |
| overlay | 2 | 18.15 (17.58-19.71) | 13.30 (13.07-14.03) | 0.73x | |
| overlay | 4 | 18.76 (17.79-19.32) | 13.66 (13.32-14.33) | 0.73x | |
| overlay | 8 | 21.82 (21.09-22.18) | 15.06 (14.79-15.18) | 0.69x | |
| cache miss + fill on every branch (epoch moves each time) | 1 | 10.30 (10.13-10.81) | 7.13 (6.77-7.23) | **0.69x** | 0 % (1,000,000 fills) |
| **relocatable code slot** (refused) | 1 | 6.39 (6.22-6.66) | 8.09 (8.00-8.23) | **1.27x (slower)** | not eligible |
| **policy mode** (refused) | 1 | 6.07 (5.93-6.14) | 6.62 (6.58-6.68) | **1.09x (slower)** | not eligible |

Reading it:
- **Hit latency**: about 1.9 ns saved per branch on a 6.4 ns call (stable), 4.6 ns on 17.5 ns (overlay swap). In the random pattern the saving is the same ~1.2 ns; the larger base comes from the stub's indirect-call misprediction, which both arms pay.
- **Miss latency**: a miss that resolves and fills (7.1 ns) is still below the resolver (10.3 ns), so a cold or thrashing cache does not hurt; the penalty only exists for branches the fast path **refuses**.
- **Invalidation overhead**: bumping the epoch makes every thread's entries unusable; the cost is exactly the "miss + fill" row above, paid once per key per thread after a registration. Registrations happen at start-up, not per branch.
- **Scalability**: B/A is flat from 1 to 8 threads (0.62-0.72x stable). No cache line is shared between threads; the 8-thread rows are slower in absolute terms in both arms (probably the 12-logical-CPU machine's SMT and the harness; not investigated).
- **Regressions with the switch on**: refused branches pay the eligibility check then the resolver: **+9 % for policy mode (0.55 ns), +27 % for relocatable slots (1.7 ns)**. A title whose dispatches are mostly of those kinds would get slower with the switch on, not faster.

## Native instruction count

Static, from `clang -S` (`logs/` keeps the assembly in `generated/analysis/t191/asm/`): the hit path of `spu_ib_fast_try` was about 90 instructions before the empty-slots shortcut (counted by hand from the assembly of that build; 33 of them were the four-slot scan) and is roughly 60 after it (estimate, not re-counted), plus about 11 in the hook and the `spu_check_stack_reset` call. I did not count executed instructions of the full resolver (no instruction-count facility on this machine without a tracer), so there is **no measured instruction-count ratio**; the ns figures above are the evidence.

## Memory overhead

12 KB (512 x 24 B) of thread-local storage per host thread, allocated with the thread whether or not it dispatches. Nothing is allocated on the heap and nothing is shared.

## Default path (switch off): regression check

Same harness with the hook cut out of the resolver (Z) vs the shipped resolver with the switch off (A), 1 thread, 7 rounds:

| Pattern | A ns | Z ns | A/Z |
|---|---|---|---:|
| stable | 6.39 | 6.99 | 0.914x |
| random | 15.02 | 15.10 | 0.995x |
| overlay | 17.54 | 16.78 | 1.045x |
| policy | 6.25 | 6.60 | 0.947x |

The differences go both ways (A is faster on stable and policy), so they are code-layout noise of +-5-9 %, not a cost of the hook; the hook is one load and a predicted branch. **No measurable regression to the default resolver; not zero either, below the noise floor of this benchmark.**

## Correctness regressions

None: `CORRECTNESS_RESULTS.md`.

## What this does not show

- Whether MotorStorm's dispatches are eligible. Unknown until the in-game hit counters run. If most are Wws relocatable-slot or policy-mode branches, the switch costs time.
- Any effect on a frame. The largest dispatch saving measured, 4.6 ns, needs on the order of millions of ordinary indirect branches per frame to reach 1 ms.

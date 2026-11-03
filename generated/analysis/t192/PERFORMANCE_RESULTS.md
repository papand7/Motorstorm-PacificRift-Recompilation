# T192 offline performance results

T192 code `cc386f42`, T191 code `32203ae6`.

**Offline microbenchmark only. No game launched. No FPS claim.** A synthetic dispatch saving says nothing about a frame; the largest saving below, about 5 ns per branch, would need on the order of a million ordinary indirect branches per frame to reach 5 ms, and the number of branches a frame actually executes is unmeasured (`NEXT_STEPS.md`).

## Method

`py -3 ps3recomp-t192/tools/bench_spu_ib_fast.py --t191-tree ps3recomp-t191 --rounds 7 --iters 4000000 --threads 1,2,4,8`, run under `generated/analysis/t169/tools/env_t169.cmd` (clang 23.1.3 `-O2 -msse4.1 -ffp-contract=off`, Windows 11, 12 logical CPUs, nothing else running; the existing test suite was **not** running at the same time). Raw output: `generated/analysis/t192/logs/bench_spu_ib_fast.txt` (private, untracked); reproduced in full below.

One harness process per (arm, pattern, thread count); the arms are interleaved inside each round. All arms run the **same harness source** (`tests/test_spu_ib_fast.c bench`), same patterns, same stub, same loop; only the runtime linked differs. The harness calls `spu_indirect_branch` on a stub that does nothing, so a number is dispatch + stub call + loop. Tables give the median ns per branch over 7 rounds with the standard deviation in parentheses, the median of the per-round ratios, and the worst per-round ratio.

| Arm | What |
|---|---|
| A | full resolver (T192 tree, switch off) |
| T | T191 fast dispatch (the T191 tree's runtime, `32203ae6`, switch on) |
| B | T192 extended fast dispatch (switch on) |
| N | T192 with `PS3_SPU_IB_FAST_RELOC=0` (relocatable slots refused) |
| S | T192 built with `-DSPU_IB_FAST_STATS` (counters), switch on |
| Z | T192 with the hook cut out of the resolver; T0 = T191 runtime, switch off |

Patterns: `stable` (one target), `random` (200 targets), `overlay` (resident overlay swapped each branch), `jreloc` (one intra-slot target of a relocatable slot), `kreloc` (8 intra-slot targets), `xrepl` (slot replaced by another owner at the same address every branch), `wws` (job-style: install a module, 15 intra-slot branches, a branch out, then a replacement at the other of two bases), `unres` (invalid target: the resolver's miss path, **~2.3 us per branch**, so 1/50 of the iterations), `policy` (policy mode), `fill` (registry epoch moves before every branch). `stable`, `random`, `overlay` and `fill` are the T191 patterns unchanged; `jreloc` is redefined (explicit intra-slot target) and the other relocatable patterns are new, so only the former are comparable with the T191 report. Their T191 values reproduce (T/A stable 0.70 vs 0.71, random 0.92 vs 0.92, overlay 0.76 vs 0.74, fill 0.66 vs 0.69, jreloc 1.28 vs 1.27).

## Results at a glance (1 thread, B = T192 vs A = resolver, median of ratios)

| Metric | Result |
|---|---|
| Stable-target latency | 4.71 vs 6.50 ns, **0.73x** (T191: 0.70x) |
| Relocatable intra-slot latency | one target 5.45 vs 6.49 ns **0.84x**; 8 targets 12.64 vs 14.29 **0.89x**. T191 was **slower** than the resolver here: 1.28x / 1.05x |
| Slot replacement latency | other owner at the same address each branch: 5.63 vs 6.67 **0.84x** (T191 1.26x); job-style (`wws`) 11.91 vs 13.39 **0.89x** (T191 1.10x) |
| Resolver fallback latency | policy mode 6.32 vs 5.92 ns **1.07x** (worst round 1.10x), the eligibility floor; invalid target 1.01x. T191: policy 1.08x, invalid target 1.09x (layout noise on the 2.3 us miss path) |
| Cache hit / miss rate (stats build) | 99.99-100 % hits for every cacheable pattern; `fill` 0 % by construction (1,000,000 fills); `policy` and `unres` never reach the cache |
| Fallback reasons | `FALLBACK_COUNTERS.md`; here: all `policy` branches are `d_policy`, all `unres` branches `d_unresolved` |
| Invalidation overhead | epoch bump before every branch (miss + fill): 6.91 vs 10.29 ns, **0.68x**; a cold or thrashing cache is cheaper than the resolver |
| Memory overhead | 12 KB thread-local per host thread (512 x 24 B), unchanged from T191; the stats build adds ~0.4 KB TLS and ~0.2 KB global |
| Multi-SPU scaling | B/A flat from 1 to 8 threads: stable 0.71-0.75, overlay 0.68-0.71, relocatable 0.81-0.90 (no cache line is shared) |
| Instrumentation overhead | stats build S vs B: +2.3 ns on stable (+50 %), +0.7 on random (+5 %), +2.0 on relocatable (+36 %), +2.3 in policy mode; the normal build has no counter code |

## What changed against T191, and what did not

- **Relocatable slots went from a regression to a gain**: B/T 0.66 (jreloc), 0.84 (kreloc), 0.67 (xrepl), 0.81 (wws), 0.65-0.66 over 1-8 threads for jreloc.
- **Plain hits are about 0.2 ns (+4 %) slower than T191** (B/T stable 1.04, worst round 1.06; at 2 and 8 threads the spread, sd up to 0.5 ns, hides it). The cost is the relocatable-mode branch on the hit path. Overlay hits are faster than T191 (B/T 0.90), random is unchanged (0.99). This is a composition trade-off, not a free improvement.
- **Policy mode keeps a ~7 % eligibility cost**; it is the same in T191 and T192 (T/A 1.08x). A negative cache was evaluated and rejected (`IMPLEMENTATION.md`).
- Variance: sd <= 0.2 ns at 1-4 threads; at 8 threads (12 logical CPUs, SMT) sd reaches 0.5-1.2 ns in every arm, and worst-round ratios there (up to 1.19x B/T on stable) are noise of that size, not a regression. The worst single-round B/A ratio anywhere at 1 thread is 1.10x (policy) and 1.01x (invalid target); the worst on a cacheable pattern is 0.93x (jreloc).

## Default path (switch off)

Hook removed (Z) vs the shipped resolver with the switch off (A) vs the T191 runtime with the switch off (T0), 1 thread, 7 rounds (table below, last section). A/Z is 0.97-1.01 on `stable`, `random`, `overlay`, `jreloc`; 0.93 on `policy` and 0.86 on the `unres` miss path; every value is within layout noise and **none exceeds +1.2 %**, so there is no measurable regression of the default path. (The hook with the switch off is one load of the mode word and a predicted branch.) As in T191, "not zero either": below the noise floor of this benchmark.

## Full output

```
cpu count 12; rounds 7; iters/thread 4000000; T192 tree <repo>\ps3recomp-t192; T191 tree ps3recomp-t191
A=resolver T=T191 fast B=T192 fast N=T192 reloc off S=T192 stats build Z=no hook T0=T191 switch off

| pattern | thr | A ns (sd) | T ns (sd) | B ns (sd) | N ns (sd) | S ns (sd) | B/A | T/A | B/T | worst B/A round | worst B/T round |
|---|---:|---|---|---|---|---|---|---|---|---|---|
| stable | 1 | 6.50 (0.07) | 4.52 (0.05) | 4.71 (0.03) | 4.70 (0.04) | 7.05 (0.02) | 0.73x | 0.70x | 1.04x | 0.74x | 1.06x |
| stable | 2 | 6.48 (0.09) | 4.55 (0.08) | 4.76 (0.08) | 4.75 (0.06) | 7.24 (0.09) | 0.74x | 0.71x | 1.05x | 0.76x | 1.10x |
| stable | 4 | 6.49 (0.04) | 4.75 (0.08) | 4.86 (0.07) | 4.86 (0.05) | 7.30 (0.05) | 0.75x | 0.73x | 1.03x | 0.78x | 1.08x |
| stable | 8 | 9.81 (0.57) | 6.85 (0.47) | 6.81 (0.50) | 6.98 (0.55) | 11.13 (1.06) | 0.71x | 0.70x | 0.99x | 0.75x | 1.19x |
| random | 1 | 14.51 (0.02) | 13.40 (0.03) | 13.29 (0.01) | 13.26 (0.02) | 13.95 (0.04) | 0.92x | 0.92x | 0.99x | 0.92x | 0.99x |
| random | 2 | 14.48 (0.61) | 13.48 (0.28) | 13.30 (0.09) | 13.36 (0.20) | 14.08 (0.14) | 0.92x | 0.93x | 0.99x | 0.94x | 1.00x |
| random | 4 | 14.68 (0.07) | 13.63 (0.10) | 13.54 (0.21) | 13.57 (0.06) | 14.32 (0.22) | 0.92x | 0.93x | 0.99x | 0.98x | 1.05x |
| random | 8 | 17.51 (0.29) | 15.21 (0.41) | 15.82 (0.75) | 15.69 (0.34) | 17.23 (0.44) | 0.91x | 0.87x | 1.04x | 1.02x | 1.10x |
| overlay | 1 | 16.29 (0.08) | 12.39 (0.20) | 11.14 (0.22) | 11.13 (0.01) | 13.62 (0.02) | 0.68x | 0.76x | 0.90x | 0.72x | 0.95x |
| overlay | 2 | 16.22 (0.08) | 12.41 (0.10) | 11.14 (0.13) | 11.19 (0.05) | 13.78 (0.19) | 0.69x | 0.77x | 0.90x | 0.70x | 0.91x |
| overlay | 4 | 16.44 (0.20) | 12.69 (0.10) | 11.45 (0.07) | 11.40 (0.04) | 14.17 (0.12) | 0.69x | 0.77x | 0.90x | 0.70x | 0.91x |
| overlay | 8 | 20.21 (0.80) | 14.56 (0.30) | 14.31 (0.36) | 14.22 (0.35) | 17.41 (0.64) | 0.71x | 0.73x | 0.98x | 0.75x | 1.02x |
| jreloc | 1 | 6.49 (0.08) | 8.31 (0.04) | 5.45 (0.21) | 5.36 (0.07) | 7.42 (0.09) | 0.84x | 1.28x | 0.66x | 0.93x | 0.72x |
| jreloc | 2 | 6.55 (0.04) | 8.31 (0.13) | 5.38 (0.06) | 5.34 (0.17) | 7.56 (0.19) | 0.82x | 1.27x | 0.65x | 0.85x | 0.66x |
| jreloc | 4 | 6.66 (0.05) | 8.56 (0.31) | 5.66 (0.64) | 5.54 (0.06) | 7.82 (0.25) | 0.84x | 1.29x | 0.65x | 1.12x | 0.86x |
| jreloc | 8 | 10.49 (0.93) | 12.79 (0.93) | 8.09 (0.64) | 7.80 (0.71) | 11.60 (1.00) | 0.85x | 1.26x | 0.66x | 1.08x | 0.77x |
| kreloc | 1 | 14.29 (0.06) | 14.96 (0.04) | 12.64 (0.03) | 12.53 (0.02) | 13.37 (0.02) | 0.89x | 1.05x | 0.84x | 0.89x | 0.85x |
| kreloc | 2 | 14.27 (0.08) | 14.98 (0.07) | 12.46 (0.24) | 12.37 (0.26) | 13.58 (0.10) | 0.87x | 1.05x | 0.83x | 0.92x | 0.88x |
| kreloc | 4 | 14.60 (0.30) | 15.35 (0.33) | 12.80 (0.18) | 12.71 (0.17) | 14.13 (0.48) | 0.87x | 1.05x | 0.83x | 0.90x | 0.85x |
| kreloc | 8 | 16.85 (0.34) | 18.90 (0.87) | 14.95 (0.32) | 14.66 (0.30) | 17.05 (0.54) | 0.88x | 1.11x | 0.79x | 0.91x | 0.82x |
| xrepl | 1 | 6.67 (0.12) | 8.39 (0.09) | 5.63 (0.04) | 5.61 (0.04) | 7.51 (0.08) | 0.84x | 1.26x | 0.67x | 0.85x | 0.68x |
| xrepl | 2 | 6.78 (0.15) | 8.46 (0.07) | 5.56 (0.03) | 5.56 (0.04) | 7.70 (0.17) | 0.82x | 1.24x | 0.66x | 0.83x | 0.67x |
| xrepl | 4 | 6.98 (0.02) | 8.71 (0.04) | 5.85 (0.22) | 5.81 (0.10) | 7.91 (0.66) | 0.84x | 1.25x | 0.67x | 0.92x | 0.74x |
| xrepl | 8 | 10.15 (1.21) | 13.04 (0.81) | 8.30 (0.73) | 8.48 (0.59) | 12.00 (1.25) | 0.81x | 1.29x | 0.65x | 0.93x | 0.79x |
| wws | 1 | 13.39 (0.05) | 14.73 (0.04) | 11.91 (0.05) | 11.91 (0.20) | 14.34 (0.25) | 0.89x | 1.10x | 0.81x | 0.90x | 0.82x |
| wws | 2 | 13.45 (0.09) | 14.75 (0.86) | 11.95 (0.06) | 11.94 (0.07) | 14.19 (0.05) | 0.89x | 1.10x | 0.81x | 0.89x | 0.82x |
| wws | 4 | 13.68 (0.11) | 15.13 (0.12) | 12.27 (0.30) | 12.26 (0.05) | 14.67 (0.12) | 0.90x | 1.11x | 0.81x | 0.94x | 0.85x |
| wws | 8 | 16.79 (0.69) | 19.10 (0.92) | 14.47 (0.43) | 14.42 (0.20) | 18.02 (0.76) | 0.86x | 1.11x | 0.76x | 0.93x | 0.85x |
| unres | 1 | 2293.72 (7.76) | 2498.07 (12.90) | 2311.03 (8.74) | 2310.93 (9.76) | 2501.24 (9.66) | 1.01x | 1.09x | 0.92x | 1.01x | 0.93x |
| policy | 1 | 5.92 (0.04) | 6.38 (0.09) | 6.32 (0.15) | 6.49 (0.17) | 8.63 (0.05) | 1.07x | 1.08x | 0.98x | 1.10x | 1.02x |
| fill | 1 | 10.29 (0.20) | 6.80 (0.04) | 6.91 (0.12) | 6.99 (0.20) | 9.98 (0.04) | 0.68x | 0.66x | 1.02x | 0.70x | 1.05x |

Hit and fill counts (stats build, 1 thread, iters/4):
| pattern | hit | fill | hit share |
|---|---:|---:|---:|
| stable | 999999 | 1 | 100.00 % |
| random | 999935 | 65 | 99.99 % |
| overlay | 999957 | 43 | 100.00 % |
| jreloc | 999999 | 1 | 100.00 % |
| kreloc | 999992 | 8 | 100.00 % |
| xrepl | 999998 | 2 | 100.00 % |
| wws | 999991 | 9 | 100.00 % |
| unres | 0 | 0 | 0.00 % |
| policy | 0 | 0 | 0.00 % |
| fill | 0 | 1000000 | 0.00 % |

Default path, switch off (no hook Z vs T192 A vs T191 T0), 1 thread:
| pattern | Z ns (sd) | A ns (sd) | T0 ns (sd) | A/Z | T0/Z | worst A/Z round |
|---|---|---|---|---:|---:|---:|
| stable | 6.70 (0.07) | 6.49 (0.03) | 6.23 (0.06) | 0.969x | 0.930x | 0.976x |
| random | 14.47 (0.04) | 14.51 (0.05) | 14.74 (0.04) | 1.003x | 1.018x | 1.011x |
| overlay | 16.07 (0.03) | 16.26 (0.05) | 16.18 (0.09) | 1.012x | 1.004x | 1.017x |
| policy | 6.37 (0.08) | 5.92 (0.06) | 6.11 (0.15) | 0.929x | 0.959x | 0.934x |
| jreloc | 6.87 (0.10) | 6.44 (0.05) | 6.38 (0.05) | 0.951x | 0.932x | 0.970x |
| unres | 2685.17 (4.62) | 2304.28 (14.30) | 2505.82 (13.09) | 0.856x | 0.931x | 0.871x |
```

## What this does not show

- Whether a game spends its dispatches in eligible states: that needs the in-game counters (`NEXT_STEPS.md`). A title whose time is in policy-module code, interrupt returns or registered-task regions gets no benefit and pays the ~0.4 ns eligibility cost per branch.
- Any effect on a frame. No FPS or frame-time claim is made.
- Instruction counts: not measured (no tracer on this machine); ns figures are the evidence.

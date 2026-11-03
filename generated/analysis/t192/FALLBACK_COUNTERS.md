# T192 Phase A: fallback-reason counters

Offline only. No game launched. Code: `agent/t192-spu-reloc-dispatch`, commit `cc386f42` (from T191 `32203ae6`, reports `982fbfe`).

## What is counted

Compile-time opt-in: `-DSPU_IB_FAST_STATS` (the normal build contains no counter code; `SPU_IBF_COUNT` expands to nothing). Run-time: `PS3_SPU_IB_FAST=1` as before. Counters are per host thread (thread-local arrays, plain increments, no atomics on the branch path).

**Primary reasons: mutually exclusive and complete.** Every branch that reaches the fast-path hook with the switch on is counted in exactly one, the first that applies in this order. The harness asserts `sum(primary) == branches` after every directed and random run.

| Counter | Meaning |
|---|---|
| `hit` | served from the cache |
| `fill` | cache miss, resolved by the fast path, entry filled |
| `d_policy` | policy mode (SPURS kernel services, Wws job entry/stats) -> resolver |
| `d_irq` | pending interrupt return (`irq_saved`) -> resolver |
| `d_trace` | job-span tracing active (`PS3_FTRACE_SPUJOB`) -> resolver |
| `d_service` | pc is the taskset syscall (0xA70) or the job-return address -> resolver |
| `d_image23` | image 23 (CRI policy hack) -> resolver |
| `d_task` | task transition: pc in the task region with task registrations or `resident_task` set -> resolver |
| `d_reloc_off` | relocatable slot with `PS3_SPU_IB_FAST_RELOC=0` (the T191 behaviour) |
| `d_unrecognized` | slot owner id is non-positive (unrecognized overlay) -> resolver refuses the dispatch |
| `d_unresolved` | invalid target: no lifted function for the key (unregistered, misaligned, stop synthesis, interpreter fallback) -> resolver |
| `d_other` | negative `resident_ovl` (would collide with the cache's owner-mode keys) |

**Probe classes: exclusive among the non-hit probes.** `p_cold + p_conflict + p_image + p_owner + p_epoch == fill + d_unresolved` (asserted).

| Counter | The probed entry... |
|---|---|
| `p_cold` | was empty |
| `p_conflict` | held another pc (direct-mapped collision) |
| `p_image` | held the same pc, another image |
| `p_owner` | held the same pc and image, another overlay / slot-owner mode |
| `p_epoch` | matched everything, but from an older registry epoch |

The requested "image mismatch", "overlay or code-slot ownership mismatch" and "registry epoch mismatch" are these three classes; "cache miss" is `fill + d_unresolved`.

**Overlapping observations: independent of the primary reason, counted per branch.** They answer "how much of the traffic is in state X", including branches that were then served: `o_policy`, `o_irq`, `o_slot` (pc inside a code slot), `o_slot_reloc` (...that is relocatable), `o_overlay` (resident overlay set), `o_task_resident`, `o_task_registered`, `o_task_pc` (pc >= 0x3000). They are not additive.

"Relocatable slot" is therefore reported twice on purpose: `o_slot_reloc` (how many branches were in one) and, only when the knob refuses them, `d_reloc_off`.

## Aggregation and reporting

Per-thread counters are added to process totals (relaxed atomic adds) only every 4096 branches of a thread, in `spu_ib_fast_report`, and at process exit. `atexit` prints one line, `[spu-ib-fast-stats] branches=N hit=... fill=... d_policy=...` (only non-zero counters). Nothing is logged per branch. A thread that ends without a flush loses fewer than 4096 branches of counts; a process killed without `atexit` prints nothing (limitation: see `NEXT_STEPS.md`).

Test API: `spu_ib_fast_reasons(out)` (this thread's cumulative counters), `spu_ib_fast_totals`, `spu_ib_fast_report`.

## Verification

- `tests/test_spu_ib_fast.c reloc`: 32 `expect_reason` call sites, each running one branch on the resolver and the fast path and asserting the primary reason moved by exactly one and the right counter (hit, fill, each `d_*`).
- Random runs (16 runs, 1,280,056 checks) assert the partition identities at the end of each run, and that the reloc mix exercised slots, unrecognized owners, tracing, the knob and epoch misses.
- A negative control drops the probe classification; the identity check catches it.

## Instrumentation overhead (measured separately)

`PERFORMANCE_RESULTS.md`, columns B (normal build) and S (stats build), 7 rounds, 1 thread, ns per branch:

| Pattern | B | S | S - B |
|---|---:|---:|---:|
| stable | 4.71 | 7.05 | +2.3 (+50 %) |
| random (200 targets) | 13.29 | 13.95 | +0.7 (+5 %) |
| overlay swap | 11.14 | 13.62 | +2.5 (+22 %) |
| relocatable stable | 5.45 | 7.42 | +2.0 (+36 %) |
| policy mode | 6.32 | 8.63 | +2.3 (+37 %) |

The stats build is for counting runs only; it is not meant for timing. The normal build carries none of this. The observation block reads about ten context fields per branch; that is the price of exact overlapping observations (a sampled variant would be cheaper but not exact).

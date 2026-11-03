# T193 counter definitions

Every counter counts **branches that reached the fast-path hook of `spu_indirect_branch` with `PS3_SPU_IB_FAST=1`** in a `-DSPU_IB_FAST_STATS` build. Branches with the switch off, and dispatches that never call `spu_indirect_branch` (static calls, `spu_indirect_branch_mt`), are not counted. All counters are unsigned 64-bit; cumulative values wrap modulo 2^64 and deltas are computed modulo 2^64 (at 10^9 branches/s a counter wraps after ~585 years; tested with a forced wrap).

## Primary outcomes (mutually exclusive, complete)

`branches = hit + fill + d_policy + d_irq + d_trace + d_service + d_image23 + d_task + d_reloc_off + d_unrecognized + d_unresolved + d_other`. A branch is counted once, at the first rule that applies, in this order. A fast-path hit is never also a fallback.

| Counter | Brief name | Definition |
|---|---|---|
| `hit` | fast-path hits | served from the cache |
| `fill` | (miss served) | cache miss, the fast path looked it up, filled the entry and dispatched |
| `d_policy` | policy-mode fallbacks | `policy_mode` set -> resolver |
| `d_irq` | interrupt-related fallbacks | interrupt return pending (`irq_saved`) -> resolver |
| `d_trace` | other | job-span tracing on |
| `d_service` | other | taskset syscall address or job-return address |
| `d_image23` | other | resolver-only image |
| `d_task` | task-transition fallbacks | pc in the task region with task state |
| `d_reloc_off` | other | relocatable slot with `PS3_SPU_IB_FAST_RELOC=0` |
| `d_unrecognized` | other | slot owner unrecognized (resolver refuses the code) |
| `d_unresolved` | invalid-target fallbacks | no lifted function for the key (unregistered, misaligned, stop synthesis, interpreter) |
| `d_other` | other | negative `resident_ovl` |

Derived in every line: `miss = fill + d_unresolved` (cache misses = probes that did not hit), `hit_plain = hit - s_hit_reloc - s_hit_slot` (ordinary stable-target hits: pc not in a code slot).

"Other resolver fallbacks" in the brief = `d_trace + d_service + d_image23 + d_reloc_off + d_unrecognized + d_other`.

## Hit / fill subsets (T193)

| Counter | Subset of | Definition |
|---|---|---|
| `s_hit_reloc` | `hit` | relocatable-slot hits |
| `s_hit_slot` | `hit` | hits in a plain (non-relocatable) code slot owned by another image |
| `s_fill_reloc` | `fill` | relocatable-slot fills |

## Probe classes of the misses (exclusive among misses)

`p_cold + p_conflict + p_image + p_owner + p_epoch = fill + d_unresolved` (= `miss`).

| Counter | Brief name | The probed entry ... |
|---|---|---|
| `p_cold` | | was empty |
| `p_conflict` | | held another key (direct-mapped collision) |
| `p_image` | ownership mismatch (image) | same key, other image |
| `p_owner` | ownership mismatch (overlay / slot mode) | same key and image, other overlay / owner mode |
| `p_epoch` | registry epoch invalidations | matched, but filled before the last registration |

These overlap with the primary outcomes by construction (each miss is a `fill` or a `d_unresolved` **and** one probe class); they never overlap each other.

## Overlapping observations (not additive)

`o_policy`, `o_irq`, `o_slot`, `o_slot_reloc`, `o_overlay`, `o_task_resident`, `o_task_registered`, `o_task_pc`: state of the context at the branch, counted independently of the outcome. With `PS3_SPU_IB_STATS_OBS=N` (N > 1) they are a 1-in-N per-thread sample (systematic, every Nth branch); multiply by N for an estimate. `obs_period` in every line says which.

## Line fields

`[spu-ib-stats] v=1 kind=<interval|checkpoint|final|exit|...> seq=<n> mono_ns=<host monotonic ns> t_ms=<since configure> dt_ms=<since previous line> thr_live=<registered threads alive> thr_seen=<ever> thr_exited=<exited> consistent=<0|1> obs_period=<N>` then `cum.<counter>=` for all counters and `cum.branches`, `cum.miss`, `cum.hit_plain`, then the same with `dlt.` (difference to the previous line), then `end=1`.

`consistent=1`: the snapshot was taken while no flush was in progress or started (all cross-counter identities hold exactly). `consistent=0` (after 4096 failed retries): the values are still valid counts, but cross-counter sums may be off by at most one thread's in-flight flush; `branches` is always the sum of the primaries read.

Line invariants checked by `tools/test_spu_ib_telemetry.py`: `seq` contiguous, `mono_ns` non-decreasing, primary sum = `branches` (cum and dlt), probe sum = `miss`, `hit_plain` split, `dlt = cum - previous cum` (mod 2^64) for every counter.

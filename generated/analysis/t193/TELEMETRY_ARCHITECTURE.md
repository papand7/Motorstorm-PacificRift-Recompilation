# T193 telemetry architecture

Offline only; no game launched. Code: `agent/t193-spu-dispatch-telemetry` (worktree `ps3recomp-t193`), commit `72e1001d`, from T192 `cc386f42` (reports `fa01e0a`). Everything below is under `-DSPU_IB_FAST_STATS`; the normal build contains none of it, and dispatch is the T192 code path in both builds.

## Phase A: audit of the T192 counters (at `cc386f42`)

| Question | T192 answer (VERIFIED by reading `spu_channels.c`) |
|---|---|
| Where incremented | `spu_ibf_pre` (called from the hook for every branch with the switch on): observations `o_*`, primary `d_policy` / `d_irq`. `spu_ib_fast_try`: every other primary reason, the probe classes |
| Thread-local? | yes: `static SPU_TLS t_ibr[]`, `t_ibr_sent[]`, plain increments |
| Registration / termination | none. A thread is not known to the counters |
| Survive thread exit? | **no**: counts were added to the totals only every 4096 branches of a thread; the remainder (up to 4095) was lost at exit, and a thread that ran fewer than 4096 branches contributed **nothing**. This runtime starts a host thread per SPURS task run (project memory: ~290 task creations/s in a race), so in a game the loss could be large |
| Process-exit reporting | `atexit` registered by `spu_ib_fast_init` (switch on via environment): flushes the exiting thread and prints one `[spu-ib-fast-stats]` line. Nothing during the run; a killed process prints **nothing** |
| Exclusive counters | the 12 primary reasons (`hit` .. `d_other`), each branch in exactly one; the 5 probe classes among non-hit probes |
| Overlapping | the 8 `o_*` observations |
| Does counting change dispatch? | no: the macros only increment; `spu_ib_fast_try` returns the same value with or without them. T192's differential ran on the stats build only, so the shipping (no-stats) build had not itself been compared against the resolver; T193 adds that run |
| Totals consistent? | per thread yes (asserted by the T192 harness). Across threads: the flush added counters one at a time with no protocol, so a reader concurrent with a flush could see a torn set (harmless in T192 because the only reader ran at exit) |

## T193 design

```
SPU host thread (one writer per shard)                 any thread at a flush point / checkpoint
 spu_indirect_branch -> hook -> spu_ibf_pre            spu_ibr_emit (try-lock, never waits on a branch)
   first branch: spu_ibr_register                        snapshot g_ibr_tot (seqlock-style, bounded retries)
     calloc 64-B-aligned shard, FlsAlloc/pthread key     deltas = snapshot - last snapshot (mod 2^64)
   n[reason]++ (plain)                                    one line -> fputs + fflush (stderr or PS3_SPU_IB_STATS_FILE)
   every 4096 branches: spu_ibr_flush_point
     flush shard -> g_ibr_tot (relaxed adds,
       fbeg/fend bracket)
     interval due?  -> emit (only if the lock is free)
 thread exit: FLS / pthread-key callback
   flush shard, live--, exited++, free
```

- **Per-thread shards.** Counters live in a heap shard per host thread (64-byte aligned and padded: an earlier unaligned version showed 1.5x false-sharing slowdowns at 8 threads, `PERFORMANCE_RESULTS.md`). Only the owner writes or reads its shard; nobody reads a shard concurrently.
- **Totals.** `g_ibr_tot[]`, updated only by flushes (relaxed atomic adds), read only by reporters (relaxed atomic loads inside the snapshot protocol). No lock on the branch path; the flush is one bracket increment, up to 28 adds and one more increment, every 4096 branches.
- **Thread exit.** Windows `FlsAlloc` callback / POSIX `pthread_key_create` destructor receives the shard pointer (no TLS access inside the callback), flushes it and frees it. Counts of exited threads are therefore exact. If the key or the allocation is unavailable, the thread counts into a thread-local fallback shard that is flushed at ticks only (old behaviour; reported through `thr_seen` not increasing).
- **Reporter without a thread.** Interval lines are written by whichever SPU thread reaches a due flush point and wins a non-blocking try-lock. No telemetry thread exists. Consequences: lines appear only while the fast path is dispatching (idle periods produce no line; the next line's `dt_ms` covers the gap), and the interval granularity is "the first flush point after the deadline". Explicit checkpoints (`spu_ib_fast_report_now`) write a line at any time, including when no SPU thread is active.
- **Exit.** The `atexit` handler writes a `kind=exit` line, then the unchanged T192 summary line, then closes the reporter for good (interval 0, file closed, further emits refused): threads that keep dispatching during CRT shutdown must not touch stdio. (Found by the exit test: without this the process crashed in 4 of 6 runs after the exit line.)

## Interfaces

| Interface | Meaning |
|---|---|
| `PS3_SPU_IB_STATS_INTERVAL_MS=N` | interval lines every N ms (0 / unset: checkpoints and exit only) |
| `PS3_SPU_IB_STATS_FILE=path` | append lines to this file (64 KB buffer, flushed after every line); unset: stderr |
| `PS3_SPU_IB_STATS_OBS=N` | overlapping observations every Nth branch per thread (1 default = exact, as T192; 0 off). Primary reasons and probe classes are always exact |
| `int spu_ib_fast_report_now(const char* kind)` | checkpoint: flush the caller, write one line, flushed before return (waits at most 200 ms for another reporter) |
| `int spu_ib_fast_telemetry_configure(unsigned ms, const char* path)` | reconfigure at run time, repeatedly; closes the previous file |
| `spu_ib_fast_totals`, `spu_ib_fast_threads`, `spu_ib_fast_thread_flush` | programmatic access |
| test hooks | `spu_ib_fast_test_bias` (2^64 wrap), `spu_ib_fast_register_atexit_for_test`, `spu_ib_fast_set_obs_period` |

Requires `PS3_SPU_IB_FAST=1` (counters exist only on the fast-path hook) and a `-DSPU_IB_FAST_STATS` build. Fast dispatch and telemetry are both off by default.

## Generality

Nothing refers to a title, an image id, an address or a job layout: the reporter counts the generic reasons of the generic dispatcher. Host-specific parts are isolated: FLS vs pthread keys, `SwitchToThread` vs `sched_yield`, `QueryPerformanceCounter` (via the existing `spu_host_ns`). POSIX paths compile from the same source but were not run here.

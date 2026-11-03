# T193 interval reporting

## Use

```
build with -DSPU_IB_FAST_STATS
PS3_SPU_IB_FAST=1                         fast dispatch on (counters live on its hook)
PS3_SPU_IB_STATS_INTERVAL_MS=1000         interval lines (0 / unset: checkpoints and exit only)
PS3_SPU_IB_STATS_FILE=<path>              append to a file; unset: stderr
PS3_SPU_IB_STATS_OBS=64                   optional: sample the overlapping observations 1 in 64 (cheaper)
```

All four are read once, at the first indirect branch (`spu_ib_fast_init`), and logged with the existing `[spu-ib-fast]` start line. At run time: `spu_ib_fast_telemetry_configure(ms, path)` and `spu_ib_fast_report_now(kind)`.

## Line (one per report, `[spu-ib-stats]` prefix, key=value, ends with ` end=1`)

Real example (offline harness, 4 threads, 50 ms interval; truncated):

```
[spu-ib-stats] v=1 kind=interval seq=0 mono_ns=79390068279100 t_ms=51.012 dt_ms=51.012 thr_live=4 thr_seen=4 thr_exited=0
consistent=1 obs_period=1 cum.branches=225276 cum.miss=14183 cum.hit_plain=113118 cum.hit=169177 cum.fill=8 cum.d_policy=41916
... cum.s_hit_reloc=56059 cum.s_hit_slot=0 cum.s_fill_reloc=4 dlt.branches=225276 ... end=1
```

Fields: `COUNTER_DEFINITIONS.md`. `cum.*` cumulative since process start, `dlt.*` since the previous line (modulo 2^64), `mono_ns` the host monotonic clock (QueryPerformanceCounter via `spu_host_ns`, joinable with other `mono_ns`-stamped logs of the runtime), `t_ms` since the reporter was first configured, `dt_ms` since the previous line.

## When a line is written

| Kind | Trigger |
|---|---|
| `interval` | the first flush point (every 4096 branches of any dispatching thread) after the deadline, if no other reporter holds the try-lock; deadline = previous interval line + interval |
| any name | `spu_ib_fast_report_now(kind)` (tests use `final`, `idle`, `round`, ...) |
| `exit` | the `atexit` handler, followed by the unchanged T192 `[spu-ib-fast-stats]` summary |

The reporter has no thread: while nothing dispatches through the fast-path hook, no interval line appears; the next one covers the gap (`dt_ms`). Interval jitter is bounded by the time a thread takes for 4096 branches (microseconds while dispatching heavily).

## Durability

Each line is formatted into a local buffer and written with one `fputs`, then `fflush` before the reporting call returns. With a file, the 64 KB stdio buffer holds whole lines and `fflush` hands each to the OS; a process killed afterwards (TerminateProcess, SIGKILL) cannot take back data the OS already has.

**Verified (offline):** 3 of 3 forced terminations (Python `Popen.kill` = TerminateProcess on Windows) of a process with 4 dispatching threads and a 50 ms reporter, killed as soon as 6 lines were present: all 6 complete lines intact, every invariant held, no partial trailing line, no exit line (as expected). **Not claimed:** that a line being written at the instant of termination survives; the parser accepts only lines ending in ` end=1`. A machine crash or power loss (OS cache not on disk) is outside the test.

With stderr the same holds for whatever stderr is redirected to (the game runner already redirects stderr to a file).

## Cost (details `PERFORMANCE_RESULTS.md`)

Writing a line takes the reporting thread microseconds once per interval. Measured: a 1000 ms or 10 ms interval adds no measurable cost (within +-2 % of the same build without an interval); even 1 ms stays within a few percent.

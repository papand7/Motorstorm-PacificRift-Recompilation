# T193 concurrency and thread lifecycle

## Rules

| Datum | Writers | Readers | Synchronisation |
|---|---|---|---|
| shard `n[]`, `sent[]`, `tick`, `obs_left` | its own host thread | its own host thread (and its exit callback, which runs on that thread) | none needed |
| `g_ibr_tot[]` | flushers (any thread) | reporters | relaxed atomic adds / loads inside the fbeg/fend bracket |
| `g_ibr_fbeg`, `g_ibr_fend` | flushers | reporters | relaxed + release fence / release; acquire loads + acquire fence |
| reporter state (`last[]`, `seq`, file, interval) | reporter holding the try-lock | same | try-lock (`__atomic_exchange`, acquire / release); the branch path never takes it |
| `thr_live`, `thr_seen`, `thr_exited` | registration / exit callback | reporters | relaxed atomics |

No non-atomic datum is read by another thread. The snapshot protocol makes cross-counter identities exact whenever `consistent=1`; with a bounded retry count it never blocks a flusher.

## Lifecycle

| Event | What happens |
|---|---|
| thread's first counted branch | shard allocated (64-B aligned), registered with the FLS / pthread key; `thr_live++`, `thr_seen++` |
| every 4096 branches | flush; maybe an interval line |
| thread exit | callback: flush, `thr_live--`, `thr_exited++`, free the shard |
| host thread id reused by the OS | irrelevant: shards are found through TLS / FLS of the running thread, never by id |
| reconfiguration | under the try-lock; file closed and reopened; counters and `seq` continue |
| process exit (`exit()`) | `kind=exit` line, T192 summary, reporter closed for good (threads still dispatching cannot write any more) |
| forced termination | nothing runs; completed lines are already with the OS |
| key or memory unavailable | thread-local fallback shard, flushed at ticks only (counts of that thread's last < 4096 branches may be lost at its exit) |

## Tests (`tools/test_spu_ib_telemetry.py`, log `logs/test_spu_ib_telemetry.txt`)

| Test | Result |
|---|---|
| 64 threads created and destroyed one after another (OS thread-id reuse), then 16 at once, 20,000-40,015 branches each, reporter at 1 ms | final line: exactly 1,922,136 branches (the sum of every thread's count) of 80 exited threads; `thr_live=0 thr_seen=80 thr_exited=80`; 202 interval lines, **203 of 203 snapshots consistent**, all invariants |
| 6 reconfigurations (file switched, interval on / off) with 4 threads per round | 29 lines across the files; `seq` and totals continuous; final total exact (486,036) |
| checkpoint with no SPU thread ever active | two all-zero lines, `thr_seen=0` |
| totals pushed to 2^64 - 2000, then more branches | 7 counters wrapped; every delta exact (5000 branches per run) |
| normal `exit()` while 4 threads dispatch with a 1 ms reporter | `kind=exit` line and the T192 summary present, exit code 0. Before the "close for good" fix the process crashed in 4 of 6 runs after the exit line (threads writing to stdio during CRT shutdown); after it, 10 of 10 clean |
| forced termination (x3) | see `INTERVAL_REPORTING.md`: completed lines intact |
| ASan / UBSan over `tele_threads`, `tele_overflow`, `tele_reinit`, `tele_idle` | clean |
| negative controls (telemetry mutants) | 4 of 4 detected: exit callback without flush; reporter not advancing its snapshot; relocatable hits counted as slot hits; flush without marking counts sent |

ThreadSanitizer does not exist for Windows targets; the race-freedom argument is the table above (no plain datum is shared), plus the consistency results under 16 concurrent writers.

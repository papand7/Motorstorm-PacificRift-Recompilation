# T31: SPURS scheduling and runtime correctness

Offline only. No launches, runtime code or branch changes. The inputs are the two T25 runs (`generated/runs/20261025-183416-perf-t25-ab1-a` = A, `…-183635-perf-t25-ab2-b` = B; exe `104ff753…`, `PS3_FTRACE_SPURS=1`). The window is the garage, 67–118 s. Source: `ps3recomp-t25-perf` @ `991337d` (`libs/spurs/cellSpurs.c`, `runtime/spu/spurs_policy.c`, `runtime/spu/spu_channels.c`, `runtime/syscalls/sys_event.c`).

Scripts (this folder, `python <script> <ftrace.txt|run_dir> 67 118 [wid]`):
- `spurs_lat.py`: splits kick→pick time into waiting for the workload's own run and the coordinator's delay.
- `spurs_runs.py`: run contents (polls) and how a kick during a run is handled.
- `pick_delay.py`: kicks that arrive while the workload is idle, with lane occupancy at the kick.
- `spurs_frame.py`: per-frame workload busy and queue time against frame time.
- `wait_episodes.py`, `spurs_couple.py`: whether guest waits end just after a workload's run ends, against a randomly shifted baseline.

## 1. Why jobs wait longer than they execute (VERIFIED)

The MotorStorm2 instance (`ea 0x1003F180`, nSpus 5) has four workloads. wid 0–2 are `Wws_Job` (none / EvoDefault / EvoHigh). All four are added with **maxContention = 1** (log: `AddWorkloadWA … maxC=1`). The game sets that value, so the coordinator correctly admits at most one run per workload (`cellSpurs.c:1789`).

| wid 1 (EvoDefault) | A | B |
|---|---|---|
| kick→pick median / p95 / p99 µs | 2349 / 11675 / 16544 | 2760 / 12694 / 14984 |
| kicks arriving while its own run is active | 93 % | 94 % |
| wait for that run to finish, median / p95 µs | 2517 / 11798 | 2950 / 12740 |
| pick after the workload frees, median / p95 / p99 µs | 9 / 34 / 276 | 9 / 34 / 163 |
| run time median / p95 / p99 µs | 780 / 4249 / 11150 | 765 / 4769 / 11706 |
| lane busy share | 60 % | 62 % |

- The long kick→pick tail is time spent queued behind the workload's own previous run. Kicks fall into long runs more often than short ones (length-biased sampling), so the median wait (2.5 ms) is above the median run time (0.78 ms).
- Each kick is real work. Runs that follow a kick during a run always do work (polls ≥ 1, 0 % empty). The running policy module does not pick up a job appended mid-run; that is the lifted original Wws code, i.e. native behaviour.
- Kicks that arrive while the workload is idle: only 1 (wid 1) and 3–4 (wid 2) per 51 s wait ≥ 300 µs. wid 2's apparent 2 ms p95 disappears once occupancy is counted from the pick rather than the run start (a kick lands in the ~5 µs between pick and start).
- **The coordinator, workers and locks add about 10 µs.** Coordinator polling, worker availability, lock contention and queue order are not the cause.

## 2. Is workload 1 frame-critical? (PARTIAL: no direct evidence)

> **Superseded by T33** (`generated/analysis/t33/SPU_JOB_COST_ANALYSIS.md` §2): split by gate and including the Present spin, wid 1 blocks main for about 37 ms/frame and wid 2 for about 8 ms/frame (VERIFIED, run B). The back-off episodes are merged 250 µs retries, not single 4 ms sleeps.

- No guest thread's waits end on wid 1 completions more often than the shifted baseline does: main's syscall and usleep waits in A are 29 vs 36 and 61 vs 67.
- The per-frame wid 1 kick count does not track frame time (corr 0.01 / −0.05). The correlation with busy time (0.92) mostly reflects frame length: about 45 ms of wid 1 work per 75 ms frame.
- The wid 1 lane is 60 % busy, so it is not saturated.
- Main's spinlock back-off at lr `0x94CCA8` (23–25 ms/frame) more often ends just after a **wid 2** run ends: within 300 µs in 44 % of cases vs a 5.6 % baseline in B; within 700 µs, 31 % vs 13 % in A. wid 1 is weaker: 28 % vs 9 % in B, about baseline in A. HYPOTHESIS: EvoHigh (wid 2), not EvoDefault, is the SPU dependency on main's critical path. Each back-off is one ~4 ms usleep, so the PPU sleep granularity (T24/T25) costs more than SPU scheduling.
- Main's once-per-frame LV2 receive (lr `0xA48ED4`, 1.2–2.0 ms) is an infinite wait inside a guest counting semaphore (`func_00A4C590`, `r5 = 0`). It is not tied to any SPURS run end and not to a timeout.

## 3. Source review of the remaining items

| Item | Finding | Label |
|---|---|---|
| Coordinator polling | API kicks (Store, Swap, CAS, WakeUp) wake the coordinator immediately through `spurs_api_unlock`. Worker completions do too. The 1 ms CV timeout (`:1770`) only matters for inline guest ready-count writes and idle polls. | VERIFIED |
| Worker wakeups | One shared CV with WakeAll wakes all 5 workers and the coordinator on every pick and every finish. Pick→start is about 5 µs. This costs CPU only, not latency. | VERIFIED |
| Idle speculative runs | Workloads that were not kicked still run with exponential back-off (`:1798`). In 51 s: wid 0 had 13.4k runs with no work, wid 3 had 6.6k, each about 15 µs, about 1.2 % of lane time. The real kernel does not do this. It is harmless here and never delayed a kick (§1). | VERIFIED, non-native |
| Event flags | `cellSpursEventFlagAttachLv2EventQueue` and its Detach are no-ops. PPU waits use a CV woken by the lock-line commit hook (`ef_line_committed`). No event-flag wait appears in main's measured waits. | VERIFIED (source); unused on the hot path |
| LV2 queue timeout (`sys_event.c:483–507`) | (a) A timeout of 1 ms or more is truncated to whole milliseconds, and each spurious or stolen wake restarts the full timeout (there is no deadline). (b) A timeout under 1 ms returns ETIMEDOUT immediately without waiting; this is deliberate, against 15.6 ms timer granularity. (c) In that path a cancelled, empty queue returns ETIMEDOUT instead of ECANCELED. None of these is on MotorStorm's frame path (§2). | VERIFIED (source) |
| Completion and visibility | The ready-count decrement, `CURCONT` and the signal clear are written under the lock-line lock and notify reservations (`ef_line_end`). API stores are serialised with the coordinator by `si->lock`. No defect found. | VERIFIED (source) |

## 4. Recommendation (ranked)

1. **Do not change SPURS admission or scheduling.** maxContention = 1 is the game's value, and the scheduler adds about 10 µs. Changing it would break native semantics and gain nothing.
2. **Make Wws job execution faster instead.** wid 1 is about 45 ms and wid 2 about 21 ms of lifted SPU work per frame, with 4–12 ms single runs in the tail. Next step, offline: job-level spans inside the Wws policy module (job descriptor EA and image per `loadCommands` fetch), to find the long jobs, then profile their lifted SPU code. This is T24 territory, so coordinate before changing anything.
3. **Confirm whether wid 2 is frame-critical** with a job-level trace in a future approved run (main back-off end vs wid 2 job completion EA).
4. **Fix the LV2 receive timeout correctness (low priority).** Use a QPC deadline across wakes, return ECANCELED in the sub-ms path, and add a deterministic test. This is runtime code; offer it to the T24 owner, since it is not frame-relevant for MotorStorm.
5. **Optional CPU-only clean-up:** per-slot worker CVs instead of the shared WakeAll; limit idle speculative runs to workloads seen kicked by inline writes. Small benefit, owner review needed.

No runtime code was modified, so no coordination with the T24 owner was required for this deliverable. Items 2, 4 and 5 are proposals for them.

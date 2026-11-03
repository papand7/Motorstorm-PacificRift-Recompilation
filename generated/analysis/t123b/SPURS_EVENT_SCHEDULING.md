# T123B: SPURS event-driven scheduling and CPU efficiency

Private analysis. Offline only: no game build, no launch, no merge or push.

## 1. Base

| | |
|---|---|
| Worktree / branch | `ps3recomp-t123b` / `agent/t123b-spurs-event-scheduling` |
| Base | `e48f279` (T123 tip: `6b8700b`, `044f766`, `e48f279` on `b84ed80`); clean at creation |
| T123 worktree | untouched |
| Commits | see §12 |

## 2. Scheduler architecture (VERIFIED, `libs/spurs/cellSpurs.c`)

- One **coordinator** thread per SPURS instance (`spurs_kernel_thread`) and one persistent **worker** per configured SPU (`spurs_pm_worker`). They share `si->lock` (SRW) and one condition variable `si->wake`.
- Coordinator pass (under `si->lock` + the workload registry lock): for each free lane, round-robin over 16 workloads; eligible = enabled bit, `wklState1 == 2`, lane priority ≠ 0, `curcont < maxContention`, PM resolved. Admission is `spurs_admit_decide` (`spurs_admit.h`):
  - legacy (default): kicked (readyCount ≠ 0 or signal bit) → admit and consume one ready unit; **un-kicked → admitted anyway every 2^idle passes (idle ≤ 4)**, so a PM can poll its own state;
  - `PS3_SPURS_READY_LEVEL=1`: SPURS1 level rule, un-kicked never run.
- Periodic wait: `SleepConditionVariableSRW(&si->wake, 1 ms)`. Every wake (timeout, lane return, API call, admission's WakeAll) runs a pass and advances `pass_no`, the backoff clock.
- Worker: waits on `si->wake` for `slot->busy`, runs the PM unlocked, then under the lock decrements `active`, writes `wklCurrentContention`, clears busy and **WakeAll**s (coordinator + all other workers).
- T123 kick wake (`PS3_SPURS_KICK_WAKE=1`): a commit to the instance's line 0 calls `spurs_kick_line_hook` → WakeAll on `si->wake`, **without the lock**.

## 3. Wakeup-path inventory

Every way previously unavailable work becomes admissible, and what wakes the coordinator.

| Source | Where it is written | Periodic | T123 kick | T123B event |
|---|---|---|---|---|
| Guest atomic kick on line 0 (readyCount1 +0x00, idleSpuCount +0x10, maxContention +0x50, signal1 +0x70): PPU `stwcx/stdcx` | `ppu_loader.cpp` → `spu_coh_notify_write` (reserved) / `ppu_commit_line_hook` (unreserved) | 1 ms poll | hook | hook → generation, no loss |
| Same from SPU `PUTLLC` / `PUTLLUC` (a PM kicking another workload) | `spu_channels.c` → `spu_coh_notify_write` (always) | poll | hook | hook |
| Plain PPU store / SPU DMA `PUT` to line 0 | `VM_WRITE_COH`, `spu_dma.h`: notify **only if the line is reserved** | poll | hook only if reserved | hook if reserved, else **fallback** |
| Guest write to `wklState1` (+0x80) / `wklEnabled` (+0xB0), line 1 | inline guest code | poll | **poll** | **fallback** |
| HLE `ReadyCountStore/Swap/CompareAndSwap`, `WakeUp`, `SetMaxContention`, `SetPriorities`, `Add/RemoveWorkload` | `spurs_api_unlock`: WakeAll **under `si->lock`** | immediate | immediate | immediate (poke under lock) |
| Lane return (frees a lane / contention) | worker, under `si->lock` | immediate | immediate | immediate (poke) |
| Legacy backoff poll of an un-kicked workload | time / pass driven | 1 ms pass | 1 ms pass | **1 ms pass kept** while a free lane has one |
| `PS3_SPURS_READY_LEVEL` re-admission (`rc + idle > contention`) | line 0 + lane return | as above | as above | as above |
| Stop / start failure | `stopping` under lock + WakeAll | immediate | immediate | immediate (poke) |

- VERIFIED by reading. **HLE API calls were already event-driven** (the lock-protected WakeAll in `spurs_api_unlock`). Note `cellSpursWakeUp` wakes through it too.
- **T123 does not cover every source**: line-1 state/enable writes, plain stores to an unreserved line 0, and backoff polling all still need a timed pass. So the periodic check cannot be removed. **The T123B design is a hybrid.**
- **T123 lost-wake window** (VERIFIED by reading): the hook WakeAlls without `si->lock`. A kick that commits after the pass has read line 0 but before the coordinator re-enters its wait has no waiter, and waits for the 1 ms tick. The tick bounds the delay to ~1 ms, so it is never a hang.

## 4. Confirmed polling costs (fixture, VERIFIED)

`tests/test_spurs_event_sched.c` at `timeBeginPeriod(1)`, no observer thread (`logs/perf/`, `logs/perf_summary.md`):

- Coordinator 1 ms pass ≈ 1,000 wakes/s per instance ≈ **15 Mcyc/s of process CPU** (level A idle 19.9 Mcyc/s at 932 passes/s, vs 5.6 at 240 passes/s): ~20 k cycles per wake including the kernel. The coordinator thread itself is 2–3 Mcyc/s. So **≈0.5 % of one core per instance**.
- **The larger idle cost is the legacy backoff**: one idle, un-kicked workload is run ~190–220 times/s (≈20 Mcyc/s, half of the 40 Mcyc/s legacy idle). That is the "polled runs" T123 counted in game (wid1 150 of 212 runs per frame).
- Shared CV: 60–72 % of worker wakes find no work (every admission and lane return WakeAlls 5 workers). T123 measured no latency or CPU cost from it.

## 5. Event-notification correctness

Mode C (`PS3_SPURS_EVENT_SCHED=1`, commit `c57d792`). The coordinator waits on `si->gen` with `WaitOnAddress`:

```
lock(si->lock)
loop:
  seen = si->gen_seen                      # value the last pass started from
  unlock; WaitOnAddress(&si->gen, &seen, timeout); lock
  si->gen_seen = load(si->gen)             # snapshot BEFORE the pass reads line 0
  pass (reads readyCount/signal/state, admits)
```

Producers: `spurs_sched_poke` = `atomic_add(gen)` then `WakeByAddressAll(&gen)`. They are the line-0 hook (under the lockline lock, after the store is visible), `spurs_api_unlock` and lane return (under `si->lock`), and stop/start failure.

- **No lost wake (VERIFIED by reasoning and test).** A producer either bumps `gen` before the snapshot, so the pass sees its store (store precedes bump, both seq-cst), or after it, so `gen ≠ seen` and the next `WaitOnAddress` returns at once (it compares the value atomically with the waiter registration). This closes the T123 window of §3. The test's strict arm (100 ms fallback, `LOST_MS=50`) found 0 kicks over 50 ms in 3 seeds × 1,100 kicks.
- **Multiple producers:** a counter, not a flag, so concurrent bumps are never merged into a lost state (4–6 producer threads, exactly-once, no order or context errors).
- **Wraparound:** only equality is compared; the test starts at `0xFFFFFF00`, PASS.
- **Shutdown:** `stopping` is set, then WakeAll for the workers and a poke for the coordinator. 20 `Finalize` calls during sleep: worst join 0.15–0.34 ms.
- **No lock-order change:** the hook still never takes `si->lock`. It only touches the atomic counter and the kernel wait queue.
- **Spurious wakes are harmless:** a hook-only pass (no lane, API or timeout event) admits only *kicked* workloads and does not advance `pass_no`, so legacy backoff is still clocked about once per ms, not per commit.
- **Timed checks kept (hybrid):** `timeout = need_poll ? 1 : fallback_ms` (default 4 ms, 1–100). `need_poll` is set while a free lane skipped an un-kicked eligible workload in legacy mode. A counted pass is also forced once ≥ 1 ms has passed, so a storm of hook pokes cannot starve backoff. Sources the hook cannot see (§3: line 1, unreserved plain stores) are found by the next timed pass.
- **Self-pokes:** coordinator and worker bookkeeping (`t_spurs_sched_self`) skip the hook, so the scheduler's own `wklCurrentContention` and readyCount writes do not wake it.
- **Not changed:** admission rules, contention accounting, PM execution, `sys_timer_usleep`, EF and taskset waits (already event-driven, §6).

## 6. Optimizations

| # | Change | Switch | Status |
|---|---|---|---|
| 1 | Scheduler counters, latency histograms, per-thread cycle CPU, one `[spurs-sched] spurs=… mode=… wakes/s … kick_admit_us p50/p95/p99 … done_pass_us … timeout_kicked …` line per interval | `PS3_SPURS_SCHED_STATS=<ms>` (cached getenv; when off, one cached branch per site) | `46fc26e`, VERIFIED |
| 2 | Event-driven or hybrid coordinator wait (§5) | `PS3_SPURS_EVENT_SCHED=1`, `PS3_SPURS_EVENT_FALLBACK_MS` | `c57d792`, VERIFIED (fixture) |
| 3 | Worker efficiency: in mode C a lane return pokes the coordinator instead of WakeAll on the shared CV. Admission still WakeAlls, because workers wait for their own `slot->busy` | part of 2 | VERIFIED: empty worker wakes 59–72 % → 20–22 % (legacy/contention), 72 → 45 % (level) |
| 4 | Commit-storm guard: hook-only passes do not advance the backoff clock | part of 2 | VERIFIED: 383 vs 207,000–210,000 polled runs/s (B) |
| – | Per-worker CV or slot futex (would remove the remaining admission WakeAll) | not done | HYPOTHESIS: small. T123 measured no cost from empty wakes |
| – | SPU→PPU completion (phase 5): EF waits already wake through `g_spu_line_commit_hook` and taskset waits through `s_sig_cv`. Polls are only fallbacks (2 ms and 1000 ms) | none | VERIFIED by reading. `sys_timer_usleep` untouched (T121 owns it) |

Defaults are unchanged: with no switch set, the code paths are the T123 ones (pins in `tools/test_spurs_event_sched.py` and `tools/test_spurs_kick_wake.py`).

## 7. Stress results

`tests/test_spurs_event_sched.c`. Each section checks exactly-once, order, context and the lost-wake bound.

| Section | What it checks | Result |
|---|---|---|
| timing / producers | 300 kicks single, 600 from 4–6 threads, maxcont 1–2 | PASS all arms; 0 over-LOST in 156 section runs |
| rapid | 960 back-to-back kicks | all done in 2–3 ms |
| spurious | 300 ms hook + poke storm, no work | level strict: 0 runs; legacy: A 333/s, B ~208,000/s, **C 383/s** |
| uncovered | plain store to an unreserved line 0 (no hook) | found by the timed pass: C ~0.5–1 ms (legacy, need_poll), ~2 ms (level, 4 ms fallback), 98 ms (strict 100 ms) |
| shutdown | 20 Finalize calls during sleep | worst join 0.15–0.34 ms |
| wraparound | gen from `0xFFFFFF00` | PASS |
| idle | 1 s, no work | §9 |

- Suite (`generated/analysis/t123b/tools/run_suite_t123b.py`, `logs/suite_*.txt`): see §12 for the per-mode counts. In default mode, the only FAIL was the T123 kick-wake publish pin, stale after the guard gained the event switch. It was fixed in `c57d792` and the test reran PASS. `test_spurs_wws_stress` (3 seeds × 40 rounds) and `test_spurs_wws_concurrency` PASS.
- The intermittent `test_spurs_wws_stress` failure ("per-lane rows sum 297 want 309", reproduced as 81/213 with all switches off) was a **test race**, not a scheduler bug: `pred_done` returns when the last job is marked done, before that run's per-lane row PUT. VERIFIED by reading; fixed in `77aeaf6` (drain `inflight`).
- Game-flag TU compile of `cellSpurs.c` (`logs/tu_final.txt`): rc=0, 897 → 901 warnings, the same kinds.

## 8. Performance comparison (fixture, 3 seeds, balanced ABC/CBA, `logs/perf_summary.md`)

Synthetic fixture only. **These are not game FPS.**

| Load | Arm | kick→done p50/p95/p99 µs | >500 µs /400 | producers p95 µs | coord CPU Mcyc/s |
|---|---|---|---|---|---|
| legacy | A periodic | 6 / 1055 / 1194 | 85 | 552 | 8.8 |
| legacy | B kick | 7 / 28 / 59 | 1 | 28 | 11.6 |
| legacy | C event | 7 / 26 / 41 | 1 | 23 | 11.5 |
| level | A | 6 / 1060 / 1405 | 85 | 970 | 7.2 |
| level | B | 7 / 28 / 66 | 1 | 27 | 9.1 |
| level | C | 8 / 29 / 42 | 1 | 25 | 2.5 |
| D contention (6 producers, 20 µs jobs) | A | 7 / 1065 / 1491 | 86 | 589 | 8.8 |
| D | B | 7 / 31 / 52 | 1 | 92 | 11.5 |
| D | C | 7 / 29 / 46 | 1 | 90 | 11.1 |

- VERIFIED: B and C both remove the ~1 ms tail. C equals or beats B on p99 and cannot lose a wake (B can: §3).
- Process CPU per section (median Mcyc, timing + producers): legacy A 763, B 332, **C 260**; D A 1400, B 913, **C 791**.

## 9. CPU changes (idle 1 s, no observer)

| Load | Arm | passes/s | polled PM runs/s | process Mcyc/s |
|---|---|---|---|---|
| legacy | A / B / C | 1017 / 1161 / 1073 | 189 / 219 / 201 | 39.4 / 45.1 / 38.4 |
| level | A / B / C | 932 / 933 / **238** | 0 | 18.8 / 18.8 / **5.5** |
| level, strict (100 ms) | C | 10 | 0 | 0.6 |

- VERIFIED: with the level rule, C cuts idle scheduler CPU by about 3.4× (about 30× with a 100 ms fallback). With legacy admission (the game default), **C keeps the 1 ms passes by design**, because backoff polling needs them. The idle cost there is the polled PM runs.
- So C alone is expected to save little CPU in game. The bigger lever is `PS3_SPURS_READY_LEVEL=1` + C, whose game safety is still T123's open question. HYPOTHESIS until the A/B.

## 10. Integration dependencies

- Touched files: `libs/spurs/cellSpurs.c`, `tests/test_spurs_event_sched.c`, `tools/test_spurs_event_sched.py`, `tools/test_spurs_kick_wake.py`. None of T113/T118/T119/T120/T121/T122 (merge base `8ea1437`) touch SPURS, coherency or the loader. T121 changes only `runtime/syscalls/sys_timer.c`. VERIFIED (`git diff --stat`).
- Builds on T123 (`e48f279`: kick hook, `spurs_admit.h`). T106 (stats) and T109 (lanes) are not changed.
- Preferred order: renderer chain T119 → T121 → T122 (independent), then T123, then T123B (fast-forward on T123). No conflicts expected. Merge only after the race A/B.

## 11. Race A/B procedure (prepared, NOT run; needs authorization for build and launch)

1. One build with T123 + T123B. AOT, fp cache, 5 lanes and renderer identical for all arms. Game window visible.
2. Arms, all with `PS3_SPURS_SCHED_STATS=1000`:
   - A: no switches
   - B: `PS3_SPURS_KICK_WAKE=1`
   - C: `PS3_SPURS_EVENT_SCHED=1`
   - optional C+L: C + `PS3_SPURS_READY_LEVEL=1`
3. Order A B C C B A, ≥ 60 s of steady race each; collect `[rsx-frame-perf]`, `[spurs-sched]`, `performance.json`.
4. Compare:
   - frame ms p50/p95 and RSX `other_ms`;
   - `kick_admit_us` p95/p99 and `wakes/s`;
   - `admit_polled`/s: **check B for commit-storm amplification**;
   - `timeout_kicked` in C: > 0 means a producer the hook does not see;
   - coordinator and worker Mcyc/s.
5. Keep C only if frame time is not worse than A or B, there are no stalls or hangs, and EF or taskset behaviour is unchanged.

## 12. Commits (`ps3recomp-t123b`, `agent/t123b-spurs-event-scheduling`, local only)

| Commit | Content |
|---|---|
| `46fc26e` | `PS3_SPURS_SCHED_STATS` instrumentation |
| `c57d792` | opt-in event-driven coordinator, stress test + driver, kick-wake pin update |
| `77aeaf6` | test fix: drain in-flight runs before the per-lane row check; kick-wake test clears the event/stats switches |

Audit `--staged`: only the 25 inherited items (`logs/audit_c1.log`, `logs/audit_c2.log`).

Suite per mode (before `77aeaf6`): default 27 PASS / 8 SKIP / 1 FAIL, event 27/8/1, kick 28/8/0. Both FAILs were `test_spurs_kick_wake`: in default mode a stale pin, fixed in `c57d792`; in event mode the test's arms inherited `PS3_SPURS_EVENT_SCHED`, fixed in `77aeaf6`. After the fixes, kick-wake passes twice and `wws_stress` (3 seeds x 40) passes in default and event modes.

## 13. Remaining risks

- **B (T123 kick) amplifies legacy backoff polling** with the guest's line-0 commit rate (~208,000 PM runs/s in the storm test, against 333/s for A). If the game commits often, B costs CPU; C does not. Fixture VERIFIED; game impact HYPOTHESIS.
- In legacy mode C keeps 1 ms passes while backoff candidates exist, so the idle saving needs READY_LEVEL. PARTIAL.
- Producers the hook does not see (line-1 writes, unreserved plain or DMA stores) wait for the fallback (≤ 4 ms by default, vs ≤ 1 ms in A). The A/B's `timeout_kicked` measures this. HYPOTHESIS that it is rare.
- `WaitOnAddress` is Windows 8+ only (`synchronization.lib`); other hosts would need a futex port.
- No runtime FPS claim: all numbers come from the fixture.

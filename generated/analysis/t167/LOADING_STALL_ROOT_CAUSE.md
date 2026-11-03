# T167: why arm A never reached the race

Failed run: `20261030-142400-t167-AA1`, exe `b2a720e2…`, ps3recomp `8a12a61`. Reference: `20261030-122501-t162-AA1`, exe `5098e7e3…`, ps3recomp `69489f2`. Logs only, plus offline probes. No game launched.

## Result

**The game was not stuck and did not repeat a load. Its SPURS scheduling slowed about 15 times at 120 s, and the load ran out of time.**

| Finding | Status |
|---|---|
| The page requests are not a retry loop | VERIFIED |
| The SPURS coordinator's rate collapsed at 120 s, in this run only | VERIFIED |
| A minimized or hidden window loses `timeBeginPeriod(1)`; a Windows flag prevents it | VERIFIED offline |
| The host timer going coarse caused this collapse | HYPOTHESIS, strongly supported |
| What changed on the host at 120 s | UNKNOWN |
| Async compilation or other T167 code caused it | Excluded (`T162_T167_EXECUTABLE_DIFF.md`) |
| RDP reconnect caused it | Not established, uncontrolled variable |

## Page requests are not repeats

The 120 page requests of A are exactly the first 120 of T162 A1's 127, in the same order (names truncated to 12 characters by the controller). The repeated `split_vehicle`, `characters`, `animations` triples are one per rider, and T162 A1 issues them too.

| Point in the sequence | T167 A1 | T162 A1 |
|---|---|---|
| First page more than 2 s apart (index 84) | 128.28 s | 120.29 s |
| Page 120, last rider's animations | 182.20 s | 124.62 s |
| Next page (`gui/pausemenu`) | not reached | 131.41 s |
| Race entry | not reached by 205 s | 135.09 s |

So rider pages took about 62 s instead of 6 s. T162 A1 then needed 6.8 s to the next page. At the same slowdown, that alone would take about 70 s, past the cap.

Not recorded by existing logs: full asset names, destination addresses and contents. That matters little here, because the sequence is the same in both.

## Earliest divergence

`ev/timeline_t167_A1.txt`, `ev/timeline_t162_A1.txt` (`tools/load_timeline_t167.py`). Up to 110 s both runs match window by window. Then, between 119.5 and 120.5 s on the render heartbeat clock:

| Counter, per second | Before | After | Same in T162 A1 at that point |
|---|---:|---:|---|
| Main SPURS: wakes | 1,387 | 96 | keeps rising with load |
| of which timeouts | 926 | 65 | |
| Second SPURS (idle): wakes, all timeouts | 236 | 65 | |
| `[spurs-busy]` runs per kernel | 24 | 2–3 | |
| Render frames | 32 | 32 | |
| `sys_timer_usleep` mean | 3.08 ms | 3.07 ms | |
| Present results | success | success | |

`tools/spurs_collapse_scan_t167.py` over 68 runs since 20 Oct: this is the only run with a collapse after the start of a run (`ev/spurs_collapse_scan.txt`). Rates fall in startup windows of 7 others, which is the first window being partial or a later race raising the median.

## Mechanism

- The coordinator waits at most 1 ms (`WaitOnAddress`, `libs/spurs/cellSpurs.c:2029`). 65 timeouts per second is 15.4 ms per wait, the default Windows tick. VERIFIED from logs and source.
- `sys_timer_usleep` uses a high-resolution waitable timer (`runtime/syscalls/sys_timer.h`), so it stayed unchanged. This explains why only SPURS slowed, and why guest frames kept 32 FPS.
- Host CPU fell to 0.26 cores: the work was waiting, not contending.
- `probe/probe_timer_res.c`, 4 s per phase, no game code:

| Window | `Sleep(1)`, default | `Sleep(1)`, `IGNORE_TIMER_RESOLUTION` |
|---|---:|---:|
| Visible | 1.8–2.1 ms | 1.3–1.8 ms |
| Minimized | 15.3–16.0 ms | 1.4–1.8 ms |
| Hidden | 3.7–16.0 ms | 1.3–1.4 ms |

Results: `ev/probe_timer_cover.txt`, `ev/probe_timer_ignore.txt`; the ranges include two earlier runs whose output was not saved, one of which showed the 3.7 ms hidden reading. The covered-window phase was inconclusive: it read 1.22 ms while a previous phase's state still lingered, and "restored" stayed coarse once. Windows applies these states with a delay, so one short probe can't settle occlusion.

## What is still unproven

- The exe has no direct measurement of its own timer. `RSX_TIMER_DIAG=1` now provides it for the next run.
- The trigger at 120 s. Present kept succeeding, and `present_occluded` stayed at 780, so a plain minimize looks less likely than occlusion or another state change. The only Windows events near the run are the reconnect at 14:24:16, 104 s before the collapse. No Windows event was logged at 14:26:00.

## Rejected causes

| Hypothesis | Evidence |
|---|---|
| Repeated identical loads | Same sequence as a run that succeeded |
| Normal slow load | Rate fell 15 times in one second; no other run does this |
| Cache invalidation, guest-memory tracking | No code in that area changed; FIOS HDD hashes match T162; nothing logged a change at 120 s, though these have no dedicated counters |
| Shader compilation | 25 compiles, 284 ms in total, last at frame 1623 (about 50 s), on the render thread |
| Device removal, Present failure, watchdog | None logged |

## Fix (ps3recomp `61d32fd`)

`PS3_KEEP_TIMER_RES=1` in ps3recomp: requests `PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION` at window creation. Opt-in. It keeps the 1 ms resolution the port already asks for; guest timing logic is unchanged. Not tried in the game.

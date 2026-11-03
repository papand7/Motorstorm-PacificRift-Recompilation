# T121: PPU runtime and HLE performance (2026-10-27, offline)

No build, no launch, no merge or push. No other worktree modified.

## 1. Base
- Worktree `ps3recomp-t121`, branch `agent/t121-ppu-runtime-performance`.
- Base `2562ba8` is the tip of `agent/t113-black-race-repair`, which contains the T113 rendering fixes. It is also the base of T119 and T120.
- The base does **not** contain T106's guest maxContention commit (`b84ed80`) or T109's SPU work. Their merge base with T113 is `8ea1437`.

## 2. Method
- No new tracing. Inputs are existing T106 A/B data:
  - `generated/runs/20261027-135959-t106-ab-B2`: `performance.json`, with per-thread `GetThreadTimes` per 5 s sample;
  - `PS3_SC_WAIT_MS=1000` lines, giving time inside lv2 syscalls per thread and number;
  - `[rsx-frame-perf]`.
- Race window: 165–235 s (entry 153.9 s + 10 s).
- The CPU and wall quantities below are never added together.
- Synthetic host benchmarks: `tools/bench_usleep.c` and `tools/bench_mode1_long.c`, output in `logs/bench_usleep.txt`.

## 3. Critical path

| Thread (B2, maxContention on) | Cores busy in the race | Role |
|---|---|---|
| host 1072 | **0.93** | RSX thread. PARTIAL: identified by correlation; it is idle until race entry, then busy. Matches T106's "RSX busy 130 of 134 ms". |
| host 21736 = guest tid 1 (main/frame thread) | 0.30 | about 41 ms CPU per 136 ms frame, including the 12.5 ms guest busy spin |
| 5 × spurs-pm | 0.36 each | SPU lanes |

- **VERIFIED:** with maxContention, the frame is RSX-bound (vertex expansion, owned by T119). tid 1 waits 45 ms per frame in the ref throttle.
- **VERIFIED:** without maxContention (as in this base, T106 arm A), the frame is SPU-bound. Wws work runs on one lane; tid 1 sleeps 138–148 ms per frame.
- **So:** PPU compute, HLE dispatch and memory translation are not on the critical path in either configuration. T106 already found memory translation is inlined (VERIFIED). Making them faster cannot shorten the frame now.
- **The PPU-side term on the critical path is wake latency.** tid 1 waits through the game's `LockFreeMutex` back-off (spin, then `sys_timer_usleep(250)`, at 0x4B63F0). Every hand-off from SPU or RSX to tid 1 is detected only at the end of a sleep.

## 4. Confirmed hotspots
1. **usleep overshoot (VERIFIED).**
   - In the race, tid 1 makes 1264 `sc141` calls per second, for 657 ms/s, a mean of **520 µs** per call where 250 µs is requested.
   - tid 12 averages 535 µs per call at 1834 calls/s.
   - On this host the per-thread high-resolution timer fires on a 0.5 ms tick: usleep(100/250) has p50 515–517 µs, and usleep(1000) has p50 1517 µs.
   - Each hand-off is therefore about a quarter-tick later on average than with an exact sleep (~260 µs vs ~125 µs mean residual).
2. **`PS3_USLEEP_SPIN=1` is wrong for long sleeps (VERIFIED offline).** It is exact below 1 ms, but at or above 1 ms it creates a non-high-resolution timer per call, which takes about **15.5 ms** for any 1–10 ms request.
   - T25's garage A/B with it still gave 13.10 → 13.74 FPS, at +1.26 cores, and reached the garage 25 s later.
   - Whether the long sleeps caused that slower boot is a HYPOTHESIS: the game process may raise the timer resolution.
3. **Not hotspots (VERIFIED from logs):**
   - Syscall dispatch: mutex calls `sc102/104` cost 0.3–0.5 µs each, 70–760 per second per thread.
   - Production logging: about 170 lines/s, all SPU dispatch messages (not mine).
   - lwcond: none appears in the race.

## 5. Implemented
**`9dfe2ca`: `PS3_USLEEP_SPIN=2` (opt-in; the default is unchanged).**
- Sleeps on the per-thread timer for `usec − PS3_USLEEP_TAIL_US` (default 600), then yield-spins (`SwitchToThread`) to the QPC deadline.
- Never returns early and lands at the requested time.
- The spin is bounded by the tail. Requests no longer than the tail are pure spin, the same as mode 1 for MotorStorm's 200/250 µs polls.
- No change to guest-visible semantics: usleep still waits at least the requested time and returns `CELL_OK`. It moves closer to lv2's real precision; it does not shorten guest time.

## 6. Synthetic results (`logs/bench_usleep.txt`, `logs/test_timer_usleep.txt`)

| Request | Default (HR timer) p50 | Mode 1 | Mode 2 p50 | Mode 2 CPU / wall |
|---|---|---|---|---|
| 250 µs | 517 µs | 250 µs (spin) | 250.1 µs | ~1.0 (spin) |
| 1 ms | 1517 µs | 15.5 ms | 1000.3 µs | 0.36–0.44 |
| 4 ms | – | 15.5 ms | 4000.4 µs | 0.06–0.12 |
| 10 ms | ~10.2 ms | 15.5 ms | 10000.5 µs | 0.00–0.08 |

## 7. Regression
- `tools/test_timer_usleep.py`: default mode (never early, no held core, one timer per thread) plus a fresh-process mode 2 run: PASS. Mode 2 also passed 10/10 repeated runs.
- `test_gcm_sync_trace`, `test_lwcond_layout`: PASS.
- TU `runtime/syscalls/sys_timer.c` with the exact T113 build.ninja flags (`tools/tu_t121.py`): rc=0, 137 warnings vs 136 on base. The one extra is `getenv`, a kind the file already has.
- Public audit `--staged`: the same 25 inherited items, none in T121 files.

## 8. Runtime A/B plan (needs build and launch authorization)
- One exe built from `9dfe2ca`. T106's bounded race-entry workflow (`t106/ab/run_ab.py` route, entry + 90 s) with `ab_fps.cfg`.
- Accounting env in every arm: `SPURS_BUSY_MS=1000 PS3_SC_WAIT_MS=1000 RSX_FRAME_PERF=12,10`.
- Arms:
  - **A:** default;
  - **B:** `PS3_USLEEP_SPIN=2`;
  - **C:** B on the maxContention tree, once integrated. With the RSX bound, a smaller gain is expected there.
- Order A B B A, as in T106.
- Metrics:
  - FPS, interval p50/p95/p99;
  - the PRE/emit/spin split (`ab_analyze.py`);
  - tid 1 `sc141` count and ms, from which mean per-call = overshoot;
  - per-thread CPU and process cores from `performance.json`;
  - SPU busy lanes and RSX `other_ms`.
- **Expected (HYPOTHESIS):** a gain only in the SPU-bound configuration, at a cost of up to about +0.5–1.3 cores.

## 9. Integration dependencies
- maxContention `b84ed80` (T106) is the larger, measured +57% gain, and is not in this base.
- The RSX vertex-expansion bound belongs to T119.
- Both decide how much mode 2 can show.
- No conflicts expected (VERIFIED with `git log`): T106 (`b84ed80`), T109, T118, T119 and T120 have no commits to `sys_timer.c` or its test since their merge base with `2562ba8`.

## 10. Commits
- `9dfe2ca` on `agent/t121-ppu-runtime-performance`.

## 11. Limitations
- Thread 1072's identity as the RSX thread is a correlation, not a log line.
- The number of wait hand-offs per frame on the critical path is unknown, so the frame gain is unquantified.
- lwcond is still a `Sleep(1)` poll with no-op signals (HYPOTHESIS: off the race path; no lwcond activity in the race logs).
- HLE NID lookup cost was not measured, because no evidence puts it on the critical path.
- No FPS claim is made.

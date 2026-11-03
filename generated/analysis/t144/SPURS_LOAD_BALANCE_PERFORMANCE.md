# T144 — SPURS job scheduling and load-balance performance

Worktree `ps3recomp-t144s`, branch `agent/t144-spurs-load-balancing`, base T134 tip `b1ded1e`
(five lanes with guest maxContention, T123/T123B opt-ins, `PS3_CRITICAL_PATH_TRACE`). T136's SIMD
work (`78fcf2b`) is **not** in this base. No game launch: real-game numbers come from existing
T106/T70 runs. Synthetic numbers come from `tests/test_spurs_load_balance.c` and are kept apart.

Artefacts (`generated/analysis/t144/spurs/`): `tools/lanes_per_sn.py` → `logs/lanes_per_sn.json`
(game, per lane); `logs/lb_seed1.txt` (synthetic suite, 10 arms × 7 reps, median shown);
`tools/lb_summary.py` (tables); `tools/run_suite_t144.cmd` → `logs/suite/` (regressions);
`tools/tu_t144.cmd` (game-flag TU compile).

## 1. Guest scheduling model

VERIFIED (T106 B1 stdout, HLE source):

| wid | name | PM | maxContention | priorities sn0..7 |
|---|---|---|---|---|
| 0 | "no name" | Wws_Job `0x00FFCC80` (11520 B) | 5 | 8 ×8 |
| 1 | EvoDefault | same | 5 | 8 ×8 |
| 2 | EvoHigh | same | 5 | 8 ×8 |
| 3 | LibMP3 JobList | same | 1 | 8 ×8 |

- All priorities equal and nonzero: no lane affinity, no priority ordering between workloads.
- The guest publishes readiness with `ReadyCountStore(wid=1, 5)` and `(wid=3, 1)`; the Wws PM itself
  claims jobs from the guest job list atomically (lockline), so job order and barriers live in
  guest memory, not in the scheduler.
- HLE: one coordinator per instance, one persistent worker per lane. Eligibility = enabled,
  state 2, priority ≠ 0, contention < maxContention, PM resolved. Admission: legacy (one ready unit
  consumed per admission, idle workloads polled with backoff) or level (`PS3_SPURS_READY_LEVEL=1`,
  the SPURS1 rule: admit while readyCount > contention). `selectWorkload` keeps a PM running until it
  returns to the kernel. PM contexts are resident per (wid, lane): no reload on re-admission.
- Guest-required: maxContention, readyCount, signal bits, the job-list barriers. Implementation
  overhead: coordinator pass latency, the herd wake of every worker, the 2^idle poll backoff.

## 2. Per-lane profiling (real game, existing runs)

VERIFIED, `[spurs-busy]`, race window (75 s), instance `0x1003F180`:

| run | lanes | util per lane | runs/s per lane | mean run | total busy | max/mean |
|---|---|---|---|---|---|---|
| T106 A1 | 4 reported | 0.77 / 0.05 / 0.004 / 0.06 | 931 / 234 / 160 / 153 | 824 / 228 / 26 / 405 µs | 0.89 | 3.46 |
| T106 B1 (5 lanes) | 5 | 0.318–0.320 | 478–490 | 650–668 µs | 1.60 | 1.00 |
| T106 B2 | 5 | 0.326–0.328 | 490–496 | 657–668 µs | 1.64 | 1.00 |
| T106 D1 (5 lanes + AOT) | 5 | 0.092–0.093 | 515–528 | 175–180 µs | 0.46 | 1.00 |

- B1 per-second lane busy p5/p50/p95 ≈ 110/344/385 ms; per lane wid1 ≈ 225 ms/s, wid2 ≈ 82, wid0 ≈ 11.
- Dispatch latency, queue depth, wakeup latency in the game: not measured (no launch). The new
  `dispatch_us` and `lane_reselect` fields of `PS3_SPURS_SCHED_STATS` collect them in the A/B (§9).

## 3. Bottleneck classification

- **Distribution: not the bottleneck** (VERIFIED). Five lanes are balanced to 1 % (max/mean 1.00).
- **Readiness/dependencies: the bottleneck** (PARTIAL). Lanes are 68 % idle (91 % with AOT) while
  run counts stay ~480–520/s per lane: the lanes wait for jobs, not the jobs for lanes. Whether the
  idle time is guest dependency (PPU producing work late) or dispatch latency needs the §9 A/B.
- **SPU throughput: not the bottleneck** (VERIFIED, D1): AOT cut run time 3.7× with no change in
  run rate.
- **Host oversubscription** (VERIFIED synthetic): with 24 spinning threads on 12 CPUs every
  scheduler loses 10–1000× (makespans 0.09–2.4 s); host scheduling dominates.

## 4. Implemented optimizations

`libs/spurs/cellSpurs.c`, all behind `PS3_SPURS_LANE_HANDOFF=1` (exactly `"1"`; default off,
default path unchanged apart from the refactor):

1. **Per-lane wake**: each lane slot has its own CV; the coordinator wakes only the lane it
   admitted (`WakeConditionVariable(&slot->wake)`) instead of `WakeAll` on the shared CV. Stop and
   start-failure paths wake every lane (`spurs_wake_lanes`).
2. **Returning-lane reselect** (level rule only): a worker that finishes a run re-runs the same
   eligibility + `spurs_admit_decide` + commit under the registry lock and admits itself, without
   waiting for a coordinator pass. Same cursor, same checks, no `pass_no` advance; the coordinator is
   still poked unconditionally. Under legacy admission it is disabled: it made one lane drain the
   consumed ready units serially (lanes/phase 4.7 → 2.8 in the first run).
3. Refactor: `spurs_lane_eligible` / `spurs_lane_commit` shared by coordinator and reselect.
4. Stats: `lane_reselect` and `dispatch_us p50/p95/p99` (admission → PM start) in
   `PS3_SPURS_SCHED_STATS`.

No change to guest memory layout, admission rules, maxContention, priorities or SPU floating point.

## 5. Correctness tests

`tools/test_spurs_load_balance.py` (source pins + 10 arms; `tests/test_spurs_load_balance.c`):
scaling 1–5 lanes, bursty, empty queues, simultaneous wakeups, rapid chain changes, restart,
strict missed-wake (100 ms fallback, a transition > 50 ms fails), 4 concurrent producers,
oversubscription. Every job executes once, barrier order is checked, checksums (FNV over results
and execution counts) must match across all non-strict arms.

- VERIFIED: seed 1, 7 reps, 10 arms — PASS, checksums identical, no strict-arm lost wake.
- Regression (`logs/suite_t144s.txt`, `logs/suite/`): load_balance, event_sched, admit, wkl_maxcont,
  wws_concurrency, cpath_trace, sc_wait_acct PASS; 4 POSIX-only fixtures SKIP. kick_wake and
  wws_stress failed once ("inline kicks … not done after 2 s", mode one, seed 2) while a TU compile
  ran in parallel (286/353 s vs ~95 s normally). Rerun on an idle machine (`logs/suite_rerun.txt`):
  both PASS on t144s and on the base `ps3recomp-t134` (VERIFIED). The default path is a code move
  only (eligibility/commit factored out, unchanged), so HYPOTHESIS: the 2 s bound in those tests is
  load-sensitive, not a regression.
- Game-flag TU compile of `cellSpurs.c`: rc 0, warnings 982 → 993, no new kinds.

## 6. Synthetic performance results (not game results)

Makespan medians, 7 reps (`logs/lb_seed1.txt`). l/ph = lanes active per barrier phase.

| case | periodic | handoff | event (T123B) | event+handoff | event+level | event+level+handoff |
|---|---|---|---|---|---|---|
| 1 lane 20×10×50 µs | 11130 | 11170 | 10165 | 10186 | 10812 | 12201 |
| 5 lanes 20×10×50 µs | 5376 (4.06 l/ph) | 7420 (3.39) | 2450 (4.94) | 2598 (4.94) | 2680 (4.84) | 4504 (4.61) |
| 5 lanes 10×10×400 µs | 10319 | 10308 | 8558 | 8264 | 8640 | 8851 |
| 5 lanes 40×5×20 µs | 3624 | 4451 | 1490 | 1505 | 1698 | 2094 |
| strict 5 lanes 40×5×20 µs | — | — | 2642 (strict event) | 1868 (strict event+handoff) | | |
| worker wakes, 5 lanes short | 115 (42 % empty) | 58 (0 %) | 81 (2 %) | 87 (0 %) | 73 (2 %) | 60 (0 %) |

Scaling 1→5 lanes (short jobs): periodic 2.07×, event 4.15×, event+level 4.03×.
Bursty kick→done p50/95/99: periodic 378/1766/2262 µs, event 83/403/458, event+handoff 93/309/435.

Findings:

- VERIFIED: the per-lane wake removes empty worker wakes in every arm (42 % → 0 % periodic).
- VERIFIED (one seed): in the strict level/event configuration handoff cuts makespan 2642 → 1868 µs
  (−29 %) and wakes 180 → 110; level 5021 → 2869 µs in the strict section.
- VERIFIED (one seed): **handoff is slower elsewhere**: periodic 5-lane short jobs 5376 → 7420 µs,
  event+level 2680 → 4504 µs, with fewer lanes per phase. HYPOTHESIS: the closing lane's reselect
  takes the newly released work before the coordinator spreads it, and without the herd wake idle
  lanes are no longer woken opportunistically.
- The largest measured gain is T123B's event scheduler (5-lane short jobs 5376 → 2450 µs,
  bursty p99 2262 → 458 µs), which T144 does not change.

Conclusion: the success criterion is met only **PARTIALLY**: lower sync overhead (no empty wakes)
and a strict-mode throughput gain, but a net regression in the default-like arms. The switch stays
opt-in and off; recommend the event scheduler for the A/B and handoff only as a measured arm.

## 7. Remaining serialization

- Guest: readyCount 5 for EvoDefault and 1 for LibMP3, maxContention 1 for LibMP3, job-list
  barriers. These are the guest's rules and are kept.
- HLE: legacy readyCount consumption (one unit per admission) is an implementation artefact that
  serializes admissions; the level rule removes it, but its game safety is still open (T123).
- One registry lock per instance for coordinator, reselect and stats (contention not measured in game).
- Coordinator pass latency in periodic mode (removed by T123B event mode).

## 8. Dependencies on T123B / T134 / T136

- T123B: event scheduler and stats reused; handoff composes with it (all event arms pass).
- T134: base; critical-path trace unchanged.
- T136 (not in base): shortens SPU job time (fingerprint cache, AOT, chunking). With lanes 68–91 %
  idle, it is HYPOTHESIS that shorter jobs move the frame; it may make dispatch latency a larger
  fraction of each run. No T136 code duplicated; SPU floating point untouched.

## 9. Controlled runtime A/B plan (not run; needs authorization)

Same build, race, T106 controller (race entry + 90 s), 2 runs per arm, `SPURS_BUSY_MS=1000`,
`PS3_SPURS_SCHED_STATS=1000`, `RSX_FRAME_PERF=12,1,100000`:

| arm | env |
|---|---|
| A | defaults |
| E | `PS3_SPURS_EVENT_SCHED=1` |
| EL | E + `PS3_SPURS_READY_LEVEL=1` |
| ELH | EL + `PS3_SPURS_LANE_HANDOFF=1` |

Measure: race FPS and frame-time spread (`t122/ab/ana_t122.py`), per-lane util (`lanes_per_sn.py`),
`dispatch_us`, `lane_reselect`, empty wakes, `[gpu-sync]`, and visual/gameplay equivalence of the
race. Accept ELH only if it beats EL on FPS with equal behaviour.

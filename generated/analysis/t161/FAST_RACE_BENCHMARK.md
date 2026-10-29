# T161: MotorStorm fast race benchmark harness

2026-10-29. Sections 1–10 were written offline; §11 records the authorised V1/V2 runs (one build, three launches). No merge, no push. Other agents' worktrees untouched. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## 1. Result

**Validated (§11):** fast pacing saves 22.5 s (race entry 137.3 s vs 159.8 s; V2 123.8 s). Heavy scene 3.83 FPS over frames 600–711. The 85 s race load runs at 0.15–0.27 cores with no CPU, I/O, mutex or SPURS limit; the main thread's sub-2 ms `sys_lwcond_wait` waits are the unmeasured remainder.

- **Race entry is 145–150 s** in the six logged A/B runs (T154 ×4, T158 ×2). One run (C1) took 165 s because of a slow boot.
- **The single largest avoidable cost is our own controller.** It holds every menu press for a fixed 6.5 s settle, but pages load 0.1–0.5 s after each press, so about 21 s per run is waiting. A tested pacing policy cuts it to about 6.5 s. Expected race entry: about 124–129 s (HYPOTHESIS until one launch confirms it).
- **The race load is 85 s at only 0.1–0.3 CPU cores.** The main thread spends 38 s of it inside the game's load-by-path routine `0x536A30`, and the wait behind it is invisible to the existing `[sc-wait]` accounting. ps3recomp now has `PS3_HLE_WAIT_MS`, which attributes it (lwmutex, lwcond, cellFs, cellSpurs). Nothing in the load was changed without that evidence.
- **The heavy scene becomes measurable.** With a 124 s entry, race frame 600 arrives at about 172 s, leaving about 100 heavy frames before the 200 s cap. At 145 s, C0 got 22 heavy frames and C1 got none.
- **Checkpointing is not feasible** with this runtime (§5). Guest threads live on host stacks inside AOT-lifted code, so no resumable state exists to save.
- **Persistent shader cache:** 6.0 s of compiles occur in race frames 0–39 and 500–599, outside both measurement windows. Warming it saves about 3 s before the heavy window, but it must be pinned as part of the cache state (§3).

## 2. Startup timeline (Phase 1)

Tool: `tools/startup_timeline_t161.py <run_dir> <runtime_dir>`. Outputs are `logs/timeline_*.json` for the six runs. Phases are cut at controller events (GUI page loads, presses, loader markers). Per phase it reports duration, RSX passes/s, process CPU cores from `performance.json`, SPURS busy and the top guest-thread waits.

The table is for C0r1. The other five runs agree within ±0.5 s per phase, except C1's boot.

| Phase | Stage (brief term) | s | CPU cores | Notes |
|---|---|---|---|---|
| exe start → first GUI page | executable, SPURS, rendering init | 8.7 | — | C1: 16.4 s. Host variance (fresh exe on first launch; cause not verified) |
| boot GUI → Sony logo | resource loading (fonts, gamesave, FIOS cache open) | 10.6 | | original game init |
| logos + intro → main menu | scene transitions | 7.4 | | fixed-length logo screens; intro skipped with the game's own button |
| main menu → race loader (4 Cross) | controller pacing | **27.6** | | 4 × 6.5 s settle. Each page loads ≤ 0.5 s after its press (VERIFIED, `controller.log`) |
| load screen → track | race setup | 0.5 | | |
| track world | resource loading | 19.3 | 0.1–0.3 | a single `0x536A30` call from `0x3944FC` lasts 19.4 s |
| environment | resource loading | 10.2 | 0.1–0.3 | |
| vehicles, first batch | vehicle loading | 16 | 0.1–0.3 | `0x536A30` calls of 0.5–1.5 s, one per `split_vehicl` page |
| gap → characters | vehicle / character loading | 26.5–28 | 0.1–0.3 | |
| characters + rest → PostLevelLoad | | 11 | | |
| PostLevelLoad → race entry | race setup | 7 | | |
| **race entry** | | **145.4–149.8** | | C1 165.5 |

- **Shader preparation does not dominate startup.** It is 0.3 s before the race (VP and PSO misses, `[rsx-frame-perf]`, `tools/pso_miss_t161.py`, `logs/pso_miss.json`).
- **Dominant stages:**
  1. the race asset load, 85 s (55 → 140 s);
  2. controller pacing, 27.6 s;
  3. boot to menu, 27 s, which is original initialisation.

**Why the load is slow (PARTIAL).**
- During the load, process CPU is 0.09–0.29 cores and SPURS is idle (0.01 busy). The loading screen renders at about 32 passes/s on tid 28.
- PT function spans (`fn=536A30` in the existing trace config) put the main thread inside `0x536A30` for 37.9 s of the window (73 calls).
- `0x536A30` takes a path argument (STATUS.md).
- In the same window `[sc-wait]` shows the main thread blocked for about 0 ms. It only times lv2 syscalls. Every HLE import goes through `ps3_hle_call` and was never timed, including sys_lwmutex/lwcond, cellFs*/AIO, cellSpurs* and cellSync*.
- **Candidates** (HYPOTHESIS, not distinguishable from the existing logs):
  - (a) the FIOS media threads deliver data at the cache-fill rate (3.9 MB/s with 1.6 s pauses, `docs/FIOS_SEQUENTIAL_READ_ANALYSIS.md`);
  - (b) `sys_lwcond_wait` is a poll. It does an unconditional `Sleep(1)` and `signal` is a no-op (`ppu_sysprx.cpp:345-369`), so a producer/consumer handshake over lwcond advances at most once per host ms per hop;
  - (c) cellSpurs event-flag 2 ms polls.
- cellFs itself has no delay or rate limit: reads and AIO are synchronous `fread`s (`ppu_fs.cpp:451-523`, `:902-945`).

## 3. Acceleration techniques (Phase 2)

| Technique | Assessment | Expected saving | Status |
|---|---|---|---|
| **Adaptive menu pacing** (controller only; same route, same Cross inputs, ≤ 9 presses, none after the loader) | Settle 1.5 s, confirm 6 s, up to 2 re-sends per step if a screen dropped the press | **≈ 21 s** (offline model 26.5 → 6.5 s) | implemented, tested offline; runtime unverified |
| Attribute the race-load wait (`PS3_HLE_WAIT_MS`) | prerequisite for any load fix | — | implemented in ps3recomp, suite-tested |
| Fix whatever the attribution shows: an lwcond wake instead of the `Sleep(1)` poll, or FIOS pacing | keeps the game's own sync; a runtime-only change with a regression test | 0 to tens of seconds of the 85 s (HYPOTHESIS) | needs the diagnostic launch first |
| Persistent shader/PSO cache (`RSX_SHADER_CACHE=2/3`, already in the runtime) | 6.0 s of compiles in race frames 0–39 and 500–599, 0.25 s in the light window, 0.07 s in the heavy | about 3 s earlier heavy window; smoother warmup; no startup gain | available; a cache-state decision |
| Warm FIOS cache (`cache.dat` holding the race assets) | game-produced state, not fabricated, but it differs from the current pinned 459 MB snapshot and its effect on the load is unknown | unknown | not done; needs the attribution first |
| Skipping logos, intro or loader stages | forbidden: original initialisation | — | rejected |
| Boot variance (8.7 vs 16.4 s first GUI) | host-side (AV scan or cold file cache of a new exe, unverified) | ≈ 8 s on a cold exe | mitigation: one discarded warm-up launch per new exe, or require A-A pairs |
| Redundant initialisation | none identified in the logs: every phase is a game step | — | — |

## 4. Implemented improvements (Phase 5)

**ps3recomp `agent/t161-fast-race-benchmark`** (worktree `ps3recomp-t161`): HLE import wait accounting.
- `include/ps3emu/sc_wait_acct.h`:
  - a second table of the same shape, keyed by NID;
  - `scwa_report_ex(…, hle)` prints `[hle-wait] window_ms=W tid=T total_ms=X nid2A6D9D51=a.ams/n …`;
  - `PS3_HLE_WAIT_MS=<window>` turns it on;
  - `PS3_HLE_WAIT_MIN_US` (default 20) skips calls shorter than that, so the 12 slots per thread go to waits.
  - The `[sc-wait]` output is byte-for-byte unchanged.
- `runtime/ppu/ppu_hle.cpp`:
  - one guard in `ps3_hle_call`, built before the first early return, so every dispatch path is counted (ctx handlers, the NID table, lifted PRX exports).
  - It costs one cached getenv when off and times nothing.
  - Not covered: the GCM FIFO-full callback (`ppu_register_function`, not an HLE import) and spins inside lifted code.
- Tests:
  - `tests/test_sc_wait_acct.c` gains an HLE section (format, NID key folding, defaults);
  - `tools/test_sc_wait_acct.py` pins the hook: present, off by default, constructed before the first early return, one accumulation site.

**Private tools** (`generated/analysis/t161/tools/`):
- `nav_policy_t161.py`: `NavPolicy` (pure logic) plus a route simulator. `test_nav_policy_t161.py` covers:
  - baseline 26.5 s vs 6.5 s;
  - a slow screen recovered by one retry;
  - a dropped press;
  - a never-ready screen ending in nav_manual after 3 presses;
  - the 9-press bound;
  - no press before the menu or inside the loader;
  - no press while the signature keeps changing;
  - the generated runner keeps the T158 route, caps and environment.
- `make_runner_t161.py` writes `ab/run_t161.py`: the T158 runner with nav() driven by `NavPolicy`. Arms:
  - N = T158 pacing;
  - F = fast pacing;
  - H = fast pacing plus `PS3_HLE_WAIT_MS=1000` on an exe from `ps3recomp-t161` (not built).
- `bench_t161.py`: one-run summary.
  - Windows by race-frame index: warmup 0–39, light 40–499, transition 500–599, heavy 600–hi.
  - Per window: FPS, p50/p95/p99, draw calls, passes, drain/record/other, compile ms, and a `complete` flag.
  - `[sc-wait]` and `[hle-wait]` totals over a host-time span (by the `[rsx-hb]` clock).
  - `test_bench_t161.py` checks it on a synthetic log.
- `startup_timeline_t161.py`, `pso_miss_t161.py`.

## 5. Checkpoint feasibility (Phase 3): not feasible (VERIFIED from the runtime design)

| Required state | Where it lives in ps3recomp | Restorable? |
|---|---|---|
| Guest PPU memory | `vm_base` (main and RSX local) | yes, a byte copy |
| PPU registers | `ppu_context` per thread | only at a call boundary, see below |
| **PPU call stacks** | **host stacks**: lifted functions call each other as C functions, so every guest thread sits several host frames deep inside lifted code or an HLE handler (for example `WaitForSingleObject` in lwmutex) | **no**: host frames of AOT code cannot be serialised or rebuilt |
| SPU state and local stores | host threads running AOT SPU code, or drain hops; LS is restorable, the host position is not | no, except between tasks |
| SPURS queues and event flags | partly guest memory, partly host (coordinator threads, CVs, `ef_line_committed` hooks, workload tables in `cellSpurs.c`) | would need a full serialiser for the HLE SPURS |
| DMA state | MFC queues are synchronous in AOT SPU code | yes between tasks only |
| Guest timers | QPC since first use, scaled to 79.8 MHz (`sys_timer.c:89-106`, SPU decrementer) | needs an offset knob (none exists) |
| RSX resources and command state | D3D12 resources, PSOs, descriptor heaps, texture caches keyed by guest address, FIFO walker position | rebuildable only by replaying, which is the load itself |
| Game resource handles | cellFs `FILE*` positions, the FIOS cache files, Win32 semaphores per lwmutex address, waitable timers, WASAPI | partly |
| Host runtime mappings | NID tables, lifted-function maps (static), per-process PSO tables | static parts yes |

- Saving guest RAM alone is therefore insufficient: no instant exists where all ~28 guest threads are at a resumable boundary.
- A checkpoint would need a resumable execution model (continuation-style lifting or an interpreter fallback). The first is a large redesign; the second is forbidden by AGENTS.md.
- **Recommendation:** no checkpointing. Accelerate the real startup (§3) instead.

## 6. Measurement framework (Phase 4)

- **Index:** race frame 0 = first `[rsx-frame-perf]` with ≥ 200 draws, grouped by `gframe` (heavy frames span several RSX passes).
- **Windows:**
  - light 40–499 (460 frames);
  - heavy 600–699 (100 frames, the most the 200 s cap allows with fast pacing).
  - Warmup 0–39 and transition 500–599 are excluded because they hold the 6 s of compiles. A window counts only if `complete`.
- **Per window:**
  - FPS and p50/p95/p99 (`bench_t161.py`);
  - SPU time (critical-path kind 39 task entries, `[spurs-busy]`);
  - PPU waits (`[sc-wait]` + `[hle-wait]`, Havok wait `0x30B710` via `phase_sites_t158.py`);
  - RSX CPU (drain/expand/record/other);
  - CPU utilisation (`performance.json`, `race_util_t158.py`);
  - draw calls and passes.
  - **GPU time is not measurable:** `wait_ms` is 0 and the backend has no timestamp queries (BLOCKED, needs a D3D12 timestamp feature).
- **Validation on existing data:** `bench_t161.py` on C0r1 reproduces T158's light-scene numbers exactly (21.39 FPS, p50 46.1 ms, p99 62.2 ms; `logs/bench_C0r1.json`). The heavy window is incomplete there (22 frames, 3.6 FPS).
- **Variance control:**
  - fresh hash-verified HDD copies per launch (already done);
  - a pinned shader cache state (cold = `RSX_SHADER_CACHE=1` as now; or a warm level-2 directory seeded by a discarded launch and hashed before each launch);
  - one discarded warm-up launch for a new exe;
  - A-A-B-B order, or at least an A-A pair (T154 A-A spread 1.0 %);
  - compare by race-frame index only.

## 7. Offline test results

| Test | Result |
|---|---|
| ps3recomp suite `run_all_t156.cmd --jobs 3` on `ps3recomp-t161` | **139 PASS / 43 SKIP / 2 FAIL**, the same two known base failures (`test_rt_pool_srv_layout`, `test_vpc_watch`) as T158 at `7a88b53` (`logs/suite_t161.txt`). VERIFIED |
| `test_sc_wait_acct` (incl. the HLE section, run in the suite) | PASS, 0 failures |
| `ppu_hle.cpp` syntax check with the project clang 23 | clean |
| `test_nav_policy_t161.py` | 0 failures (26.5 → 6.5 s in the model) |
| `test_bench_t161.py` | 0 failures |
| `bench_t161.py` on C0r1 vs `race_ab_t158.py` | identical light-scene FPS and percentiles |

## 8. Expected savings

| Item | Saving | Label |
|---|---|---|
| Fast menu pacing | ≈ 21 s (race entry ≈ 124–129 s) | HYPOTHESIS until launched; model VERIFIED |
| Warm shader cache | ≈ 3 s to the heavy window (none to race entry) | measured compile time; effect HYPOTHESIS |
| Race-load wait fix | 0 to tens of seconds of the 85 s load | HYPOTHESIS, needs `PS3_HLE_WAIT_MS` data |
| Cold-exe boot | ≈ 8 s on the first launch of a new exe | host, mitigated by a warm-up launch |

## 9. Proposed controlled runtime validation (needs authorisation)

1. **V1, no build, 2 launches.** `ab/run_t161.py` with the existing T158 C1 exe (SHA-256 `2a040320…1f08`), arm F then arm N, both under the T158 caps (205 s session / 210 s host).
   - Pass criteria for F:
     - race entry ≥ 15 s earlier than N;
     - no `nav_manual`;
     - draw calls per race frame match N at frames 0/300/460;
     - heavy window 600–699 `complete`.
2. **V2, one build plus 1 launch.** Build `ps3recomp-t161` with the C1 SPU configuration as `build/motorstorm-t161-h`, then run arm H.
   - Use `bench_t161.py --wait-span 55:140` to attribute the 85 s load wait per thread and import.
   - Any fix (lwcond wake, FIOS pacing) follows as a separate task with its own regression test and A/B.

## 10. Commits

- **ps3recomp `agent/t161-fast-race-benchmark`:** `2115697`: HLE wait accounting plus tests (§4).
- **root `agent/t161-fast-race-benchmark`:** this report and `tools/*.py`. `logs/` (timelines, suite log, bench output) is gitignored and stays private.
- Run data, `ab/` runtime directories and `stderr.log` excerpts stay private and untracked.

## 11. Authorised runtime validation (V1: 2 launches, V2: 1 build + 1 launch)

Three launches in total, run one after another. Each had a fresh private HDD, the exe SHA-256 checked before launch, a 195 s game timeout (well inside the 205 s / 210 s caps) and no retries. The renderer, SPU and performance environment is the T158 arm B set in every arm.

| Run | Exe SHA-256 | Arm | Run dir (private) |
|---|---|---|---|
| V1A | `2a040320…1f08` (T158 C1) | F: fast pacing (1.5 s settle, 2 retries) | `runs/20261029-213249-t161-fast-FV1A` |
| V1B | `2a040320…1f08` (T158 C1) | N: T158 pacing (6.5 s settle, 0 retries) | `runs/20261029-213607-t161-fast-NV1B` |
| V2 | `d835db8b…f928d6` (`ps3recomp-t161` 2115697 + C1 SPU args) | H: F plus `PS3_HLE_WAIT_MS=1000`, PT `hle=*` ≥ 2 ms, critical-path window 40–140 s | `runs/20261029-215320-t161-fast-HV2` |

### 11.1 V1: fast menu pacing, PASS (VERIFIED)

| Host s | V1A fast | V1B original | V2 (fast + instrumentation) |
|---|---|---|---|
| Main menu | 38.28 | 37.81 | 26.97 |
| Navigation (first Cross → load screen) | **7.93** | **27.82** | 6.58 |
| Race load (load screen → race_loaded) | 87.15 | 90.10 | 85.28 |
| Race entry (race frame 0) | **137.28** | **159.82** | **123.84** |
| Race frames captured | 0–652 | 0–559 | 0–711 |

- **Saving:** 22.5 s to race entry (pass threshold 15 s); navigation alone 19.9 s.
- **Route:** identical in every run. Four Cross presses (festival → ticket-s → motorsto → loadscre), 0 `nav_retry`, 0 `nav_manual`, no press after the load screen appeared.
- **Correctness:**
  - draw mismatches 6/560 frames (vertex 65, upload 1), the T158 level;
  - error counts identical in all three runs (fc-watchdog 26, stall 50, GCM_STALL 3, spu-smc 8, `[fs] open FAIL` 6 for the known missing files).
- **Boot variance:** V1A/V1B boots were about 11 s slower than T158 and V2 (game logo 33 s vs 24 s). Pacing doesn't apply before the main menu, so this is host variance.

| FPS (race frames) | V1A | V1B | V2 |
|---|---|---|---|
| Light 40–499 | 21.72 (p50 45.4 / p95 51.3 / p99 57.1 ms) | 20.20 (45.7 / 57.7 / 140.9) | 21.85 (45.0 / 49.8 / 63.1) |
| Heavy 600–699 | 3.76, 53 frames, **incomplete** | not reached | **3.83, 112 frames (600–711), p50 259.7 / p95 274.2 / p99 281.1 ms** |

- **Heavy coverage:** V1 missed the heavy window because of the slow boot. Only V2 (fast pacing plus a normal boot) covered frames 600–699.
- **Instrumentation overhead:** V2's load (85.3 s) and light FPS match V1A, so no overhead was measurable.

### 11.2 V2: race-load attribution (load screen 35.4 s → race_loaded 120.7 s)

**Off by default (VERIFIED).** `scwa_hle_window_ms()` returns 0 unless `PS3_HLE_WAIT_MS` is set, and the guard then stores `t0 = 0` and does nothing.

**Process and per-thread CPU** (kind 32 cycle counts and `performance.json`; this is CPU time, not elapsed):

| Phase (s) | Process | Main thread | Async SPU tasks | `0x536A30` |
|---|---|---|---|---|
| Track 35.9–55.4 | 0.20 cores | 0.06 | 0.00 | one call 19.45 s (site `0x3944FC`) |
| Environment 55.4–65.3 | 0.19 | 0.05 | 0.00 | 0.3 s |
| Vehicles 65.3–81.4 | 0.25 | 0.11 | 0.00 | 16 calls, 0.3–1.6 s each |
| Gap 81.4–108.2 (26.8 s) | **0.15** | **0.01** | 0.00 | none |
| Characters 108.2–116.7 | 0.27 | 0.12 | 0.00 | 5 × 0.1 s |
| Whole load | 0.27 (21.9 CPU s / 82 s) | | | 27 calls ≥ 0.1 s, 37.3 s |
| Race, for comparison | 2.45 | 0.47 | 1.88 | |

**Elapsed waits** (per-thread sums; many threads wait at once, so they overlap and must not be added together):

| Category | Measured | Verdict |
|---|---|---|
| 1. File I/O / FIOS | `cellFsRead` 84 ms over 2,967 calls; FIOS threads idle in `sc141` / `sc130` | not the limit |
| 2. lwcond polling | worker threads 3–9: `sys_lwcond_wait` ~87 s each (all ≥ 2 ms calls are 2.0–2.5 ms `Sleep(1)` polls from lr `0x66BB70`) | idle workers; main thread see below |
| 3. Mutex | `sys_lwmutex_lock` ≥ 2 ms: 4 calls, 39 ms in total | not the limit |
| 4. SPURS sync | `cellSpursEventFlagWait` 3.9 s (tid 6); no SPU tasks ran (0.00 cores) | not the limit |
| 5. Guest computation | main thread 0.01–0.12 cores, process 0.15–0.27 cores | not the limit |

**Main thread during the track load** (19.45 s inside `0x536A30`):
- CPU about 6 %;
- `sys_timer_usleep` about 10 % (240 calls per s, 0.42 ms each);
- imports ≥ 2 ms 0.6 % (457 of the main thread's PT HLE events are `sys_lwcond_wait`, at lr `0x66BB70`);
- **about 83 % not directly measured.**

**Missing measurement (VERIFIED gap).** `[hle-wait]` keeps 12 NID slots per thread, and slots are never released. The main thread filled all 12 with boot imports by 1 s. Every later main-thread import, including `sys_lwcond_wait`, went to `dropped` (700–850 per s during the load, against 80 per s in the race). The PT tracer saw only calls ≥ 2 ms. The main thread's sub-2 ms waits are therefore not measured.

**Bottleneck classification:**
- **(6) wait latency with no busy producer: VERIFIED.** No CPU, I/O, mutex or SPURS work explains the 85 s. The process stays at 0.15–0.27 cores throughout, and the 26.8 s gap has no load call and 0.01 main-thread cores.
- **The main thread blocked in sub-2 ms `sys_lwcond_wait` polls (lr `0x66BB70`): HYPOTHESIS, strong.** The dropped rate matches 1–1.3 ms polls. The long-call distribution is cut off at the 2 ms threshold. In ps3recomp's HLE, `lwcond_signal` is a no-op, so each wake costs a poll.
- **Still unknown:** which event the main thread waits for, and who produces it.

**Next measurements** (each needs authorisation):
1. Free or reset `[hle-wait]` slots per window, or raise `SCWA_SLOTS`; alternatively, PT `hle_min_us=200` for the main thread only.
2. Log the lwcond id and the signaller's tid and time in `sys_lwcond_signal`, to identify the producer the main thread waits on.

### 11.3 Recommended next startup optimisation

1. **Adopt fast pacing** (`NavPolicy` 1.5 s / 2 retries) for all race benchmarks. Saving: 22.5 s, VERIFIED.
2. **Find the race-load producer.** Use the two measurements in §11.2, then make a real `sys_lwcond_signal` / wait wake in place of `Sleep(1)` polling, but only once it is shown to be on the critical path. A wake can't fix the 26.8 s gap if no producer is running then. Expected saving 0 to tens of seconds (HYPOTHESIS).
3. **Warm the shader cache** (§3), about 3 s to the heavy window.

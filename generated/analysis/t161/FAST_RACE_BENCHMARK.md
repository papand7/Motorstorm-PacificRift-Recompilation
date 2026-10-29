# T161: MotorStorm fast race benchmark harness

2026-10-29. Offline only: no MotorStorm build, no game launch, no merge, no push. Other agents' worktrees untouched. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## 1. Result

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

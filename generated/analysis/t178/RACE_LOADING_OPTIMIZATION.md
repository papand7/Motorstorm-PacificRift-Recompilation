# T178: race loading optimization

Status: **PARTIAL**. No load-time improvement was implemented or measured in this task. The analysis is from existing game logs. T178 adds one off-by-default probe, because the largest remaining wait cannot be classified without a game run. No game was launched.

Target status:

| Target | Status |
|---|---|
| Under 20 s | Supported: wake measured 20-22 s, plus a projected shader saving. Needs a run of the T177 build |
| Under 10 s | No supporting evidence |
| 2-5 s warm | No supporting evidence |

## 1. Baseline and methodology

| Arm | Load screen to race entry | Evidence | Label |
|---|---|---|---|
| Poll | 85-90.8 s (the brief's about 95 s was not reproduced) | T161 runs | VERIFIED |
| `PS3_LWCOND_WAKE` | 20-22 s; race entry 122.7 s to 41.9 s | T161, 2 + 2 runs, older build | VERIFIED |
| T177 gate (`heavy_draws=200`) | Never run in game | | BLOCKED |

- **Sources:** T161 wake runs `20261029-232606-t161-fast-BV4B` (traced), `20261030-065514-...-DD1`, `070151-...-DD2`, `065154-...-CC1`; poll-arm CPU trace `t161/ab/runtime-V2-20261029-215319/cpath.txt`.
- **Tools:** `tools/phase_waits_t178.py` gives per-phase wait budgets by thread. `tools/load_cpu_t178.py` gives per-phase CPU from the critical-path trace.
- **Limits:** phase clock is about ±1 s. Main-thread CPU comes from a poll-arm trace, because that is the available trace. Async SPU task threads never register with the tracer, so their CPU is missing from all traces.

## 2. Ranked bottlenecks

Shares of the 22 s wake-arm load. They overlap, because main waits include producer time.

| # | Bottleneck | Time | Reducible? | Label |
|---|---|---|---|---|
| 1 | FIOS mediathread waiting on SPU task 0 (event flag `0x10484D80`), which main waits on through lwcond | about 7.3 s | Unknown: compute against latency unresolved; at most about half of the track-phase wait is SPU compute | PARTIAL |
| 2 | Main `sys_timer_usleep` | about 8.5 s (3.44 in the asset stages, about 5.1 after PostLevelLoad) | Guest-requested; part probably follows producers. What the late polling waits for is unidentified | PARTIAL |
| 3 | Main guest CPU | about 5.6 s (poll arm) | Unknown; functions unattributed | PARTIAL |
| 4 | PSO and VS misses in first race frames | 2.85 s | Yes: `RSX_SHADER_CACHE=3`, projected about 17.6 s total | VERIFIED cost, HYPOTHESIS saving |
| 5 | FIOS thread hops | at most about 1-3 s | Spinning is not justified (lag 0.01 ms) | PARTIAL |
| 6 | Storage reads | 84 ms over 2,967 `cellFsRead` calls | No | VERIFIED |
| ? | Warm FIOS cache | Could remove decompression; `cache.dat` grows 459 MB to 1.94 GB per session, all runs start fresh | Highest-value untested option | HYPOTHESIS |

**The "about 8 s" of main-thread time is now split:** 3.44 s guest-requested `sys_timer_usleep` (about 200 µs requested, 0.24 ms measured, near the floor) plus about 4.6 s guest CPU. Which functions: unknown, needs a profile run.

## 3. Critical-path timeline

Main thread (tid 1) in wake run V4B, seconds. CPU column is the poll-arm V2 trace.

| Phase | Wall | lwcond | usleep | Other | Main CPU (V2) |
|---|---:|---:|---:|---:|---:|
| Track | 5.10 | 2.49 | 1.13 | 1.48 | 0.97 |
| Environment | 1.38 | 0.84 | 0.24 | 0.30 | 0.54 |
| Vehicles | 4.34 | 1.61 | 0.71 | 2.02 | 1.74 |
| Gap | 1.07 | 0.57 | 0.21 | 0.29 | 0.34 |
| Characters | 3.71 | 1.78 | 1.15 | 0.78 | 1.02 |
| **Sum** | **15.6** | **7.29** | **3.44** | **4.87** | **4.61** |
| PostLevelLoad to entry | about 6.4 | | about 5.1 (9,833 calls) | | 0.95 |

Chain: main → scheduler (tid 9) → mediathread (tid 6) → SPU task 0 on taskset `0x10483480` → event flag → back.

The main thread's 7.29 s of lwcond splits into 4.24 s of tid 6 event-flag waits in those phases, then FIOS CPU and hops. At race entry the render thread is saturated (`rsx-drain` 2.56 CPU-s of 3.0 s), matching the shader misses.

## 4. Changes and commits

| Commit | Worktree, branch | Change |
|---|---|---|
| `b352450d7a805e7b42047982898a06670a4d31d8` | `ps3recomp-t178-load`, `agent/t178-race-loading-optimization`, base T177 `b86a1073` | `PS3_LOAD_PROBE=<window_ms>`: observe-only signal-to-resume latency, task work and parked time, event-flag waits |

The opt-out is not setting the variable. Its only effect when off is a cached check of that setting at each hook.

**Deliberately not changed:** adaptive wake, `heavy_draws`, usleep length, SPU backoff, and the coordinator. Each candidate fails on evidence:

- **Shortening usleep:** it changes guest timing, and the sleeps are already near the floor.
- **Spinning on hops:** lag is 0.01 ms.
- **Event-flag wake path:** waits end with `waits=0`, so through the condition variable rather than the 2 ms timeout, and one phase averages 0.3 ms per operation, which argues against a 1 ms floor.
- **`spu_dma.h` repeat-transfer `Sleep(1)`:** noted as a candidate, unproven. The probe's `work_ms` against `work_mcyc` will show it.
- **Coordinator:** `admit_polled` shows no correlation with event-flag means.

**T177 gate evaluation:** kept. Replay on runs D1, D2 and C1 (VERIFIED on logs; the gate itself has not run in game):

- Maximum draws per guest frame before the race: 107, 60, 61. Loading screen: 3. Race: about 1,800 or more.
- Heavy starts 15 guest frames after the first heavy frame, with exactly one transition and no light run in the race.
- A threshold of 200 has wide margin, so no replacement signal is justified.
- Caveat: after a heavy race, the next load polls until 64 light frames (about 2 s). Unobserved.

## 5. Offline before and after

Synthetic, and not a load-time claim.

| 4-hop hand-off, `test_lwcond_wake` | µs/op |
|---|---:|
| Poll | 4,638.9 |
| Wake | 25.5 |
| Gate, loading | 25.5 |
| Gate, heavy | 4,323.9 |

These measure the T177 code on this tree. T178 changes no wait path, so it has no before/after of its own.

## 6. Correctness and regression

| Check | Result | Label |
|---|---|---|
| `test_load_probe` | PASS. Off: touches no table. On: every wake counted once, 8 concurrent waiters lose no count, tables bounded, drops counted | VERIFIED |
| Full suite through `env_t169.cmd`, T178 | 124 pass, 3 fail, 43 skip, 0 timeout | VERIFIED |
| Full suite, base `b86a1073` | 123 pass, 3 fail, 43 skip, 0 timeout | VERIFIED |
| Failure lists | Identical: `test_rt_pool_srv_layout`, `test_spurs_wws_concurrency`, `test_vpc_watch`. Pre-existing here. The extra pass is `test_load_probe` | VERIFIED |
| `test_lwcond_wake`, `test_spurs_event_sched` | PASS | VERIFIED |
| Isolated build | rc=0, `build/motorstorm-t178-load`, exe sha256 `9b15f78562cde066db435f3e8c22d91c08108403aad6dee9bde5a94f7ba21384` | VERIFIED |
| Standalone public audit (`--tree`, copy of the five changed files) | Passed | VERIFIED |
| Commit hook | Not in effect for ps3recomp worktrees; for this report see the root commit | VERIFIED |
| Probe overhead in game | Unmeasured; a diagnostic build arm only. Fixed tables, relaxed counters, no blocking | HYPOTHESIS |

Inherited risk: this base contains the T173 jump-table fix, which has not been validated at runtime.

## 7. Remaining bottlenecks

- **Event-flag wait:** compute or latency. If mostly compute, parallelism or a warm cache is the route. If latency, fix the wake path.
- **Main CPU:** about 5.6 s, functions unknown.
- **Late usleep polling:** about 5.1 s after PostLevelLoad. What it waits for is unidentified.
- **Warm FIOS:** never measured.
- **SPU task CPU:** missing from traces. The probe's `work_mcyc` covers it.

## 8. Minimal in-game A/B (not run, needs authorization)

Prerequisites: `query session` shows a local console session, Godot closed, and `nvidia-smi --query-compute-apps` empty. At last check Ollama and LeOffice, Epic and EA apps were on the GPU list. The T177 runner uses the T177 exe and generates arms from `root-t177/.../tools/make_runner_t177.py`; a T178 arm needs this exe added. Runs stop at race + 45 s.

| # | Launches | Setup | Decides |
|---|---:|---|---|
| 1 | 1 | T178 exe: `PS3_LWCOND_WAKE=1:poll_ms=100:stats_ms=1000:heavy_draws=200`, `PS3_LOAD_PROBE=1000`, tracer `profile=`, `PS3_SC_WAIT_MS`, `PS3_HLE_WAIT_MS` | Event-flag compute or latency, main CPU functions, late usleep target |
| 2 | 2 | T177 poll against T177 W (`heavy_draws=200`) | Baseline; gate's load time, FPS, CPU |
| 3 | 1 | W + `RSX_SHADER_CACHE=3`, warm (needs a preceding fill, which arm 4's first run can provide) | Shader saving |
| 4 | 2 | W twice on one HDD copy (runner change needed) | Warm FIOS |

That is about 6 launches, without repeats. Do run 1 first: its result may add a T178 arm to compare.

Measure: load screen to race entry and first playable frame, race FPS, CPU cores, peak RAM and VRAM, `[lwc-wake]` counters including `gated=`, `[load-probe]` lines, last `[rsx-hb]` against session end, and any crash, hang or render regression.

Pass: W load within 10 % of unguarded wake, W light-race FPS within 1 % of poll, warm shader saving at least 2 s, no crash, hang, missing asset or SPURS stall. Probe conclusions need the same load shape as earlier wake runs.

## 9. Expected against measured

| Claim | Kind |
|---|---|
| Poll 85-90.8 s, wake 20-22 s | Measured in game, older build |
| Main-thread budget, event-flag waits, storage | Measured from logs |
| Gate margin at 200 draws | Log replay, gate not run |
| Fixture 4,638.9 to 25.5 µs/op | Measured, synthetic |
| Load about 17.6 s with warm shader cache | Expected (T116 ratio) |
| Warm FIOS gain | Expected, size unknown |
| T178 load-time gain | **None: nothing implemented changes loading** |
| Under 10 s, 2-5 s warm | No supporting path |

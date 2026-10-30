# T167: controlled game A/B

**BLOCKED: arm A produced no race data and arm B was not launched. Phases 3 and 4 have no answer.** The earlier six-arm proposal is replaced by this authorized two-arm plan.

## Executable

`build/motorstorm-t167/MotorStormPacificRiftRecomp.exe`, pinned copy `ab/exe_g/`
SHA-256 `b2a720e243ecd297e4b86c3d312f249be9720c13bd545533e9ae0e2f55e5b6ae`, ps3recomp `8a12a61`.

## Settings

Both arms: `run_t167.py` (from `tools/make_runner_t167.py`), T162 arm A's environment and route, fresh private HDD per launch, 205 s game cap, 210 s host cap, `RSX_GPU_PROF=60`, `RSX_WAIT_DIAG=1`, `RSX_SHADER_COMPILE_DIAG=1`. `RSX_PRESENT_INTERVAL` unset in both.

| Arm | Added |
|---|---|
| A | `RSX_GVF_ASYNC=0`, fetch off |
| B | `RSX_GVF_ASYNC=1`, `RSX_GPU_VERTEX_FETCH=1` |

Sequencer: `tools/ab_seq_t167.py`, one launch per arm, no retries.

## Phase 1: VERIFIED

- Suite: 144 PASS, 43 SKIP, 2 FAIL. Both failures are inherited (`test_rt_pool_srv_layout`, `test_vpc_watch`).
- Rebuild rc=0. `validate_t167 correct` and `compile`: 0 failures. `nopso_regress`: 0 failures.
- Source trees and executable at `8a12a61`, hash above verified. Dry run passed for both arms. Public-source audit passed.

## Phase 2: what happened

| Time | Event |
|---|---|
| 14:15:48 | Session disconnected (event 24) |
| 14:23:58 | Sequencer found `disconnected`; A launched |
| 14:24:16 | Session reconnected over RDP (event 25), about 16 s into A |
| 14:27:26 | A ended at the 205 s cap, exit 0. Sequencer stopped; B not launched |

Post-check failures: no `race_entry` marker, 0 race frames, session changed during the launch.

## Arm A measurements (frontend and load only)

| Metric | Value |
|---|---|
| Race entry | not reached in 205 s |
| Most draws in a frame | 60 |
| `rsx-frame-perf` lines | 6,737 |
| `wait_ms` above 50 | 5 |
| `GcKernel::Present() Timeout` | 0 |
| Debug-layer messages, FIFO resyncs | 0, 0 |
| Host CPU | 53 s, 0.26 cores (T162 A1: 238 s, 1.22 cores) |

Light- and heavy-scene FPS, race compile and PSO stalls, and frame pacing: no data. These numbers say nothing about async compilation.

## A did not reach the race

**VERIFIED:** same route inputs and timing as T162 A1 (all 4 presses, `nav_ok`) and matching HDD hashes. Page loads match to about 100 s. T162 A1 then finished loading and entered the race at 135 s. T167 A1 instead kept reloading `split_vehicle`, `characters` and `animations` pages until about 182 s, with SPURS nearly idle.

Investigated in `LOADING_STALL_ROOT_CAUSE.md`. No launch of this executable has reached a race yet.

## Phase 4

| Question | Answer |
|---|---|
| Eliminates shader stalls | unknown |
| Preserves draw output | unknown in game; offline validation passes |
| Improves race pacing | unknown |
| New graphical defects | unknown |
| PSO still the dominant stall | unknown in game; T162 A1 showed up to 2.1 s |

## Next

Loading cause: `LOADING_STALL_ROOT_CAUSE.md`. Answer: the load was the same as T162's but ran about 15 times slower from 120 s, and the host timer going coarse is the leading explanation.

New request: `NEXT_GAME_TEST_REQUEST.md`. The generated runner and sequencer now use it: 240 s game cap, 245 s host, 100 heavy frames, race entry by 175 s. The phase tables above describe the launch that ran, with the 205 s and 210 s caps. The next optimization stays open until valid A/B data exists; PSO creation on the render thread is the candidate.

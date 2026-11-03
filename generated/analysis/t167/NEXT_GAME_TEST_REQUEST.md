# T167: next game test request

**Requested, not authorized. Nothing has launched since arm A.**

## Request

Two sequential launches, one per arm, with the existing executable. No new build.

| | |
|---|---|
| Executable, both arms | `ab/exe_g/MotorStormPacificRiftRecomp.exe` |
| SHA-256 | `b2a720e243ecd297e4b86c3d312f249be9720c13bd545533e9ae0e2f55e5b6ae` |
| ps3recomp | `8a12a61` |
| Launch | `py -3 tools/ab_seq_t167.py run --sha <above>` |
| Maximum launches | 2, no retries |
| Caps | 240 s game, 245 s host, or race entry + 150 s |
| HDD | Fresh private copy per launch |
| Route | T162's, unchanged; no manual driving |

The executable predates `PS3_KEEP_TIMER_RES` and `RSX_TIMER_DIAG`, so neither is available. The run avoids the trigger through session state and rejects a collapse by its SPURS rate. A build with those switches is needed only if a collapse recurs.

## Environment

Both arms: T162 arm A's environment plus `RSX_GPU_PROF=60`, `RSX_WAIT_DIAG=1`, `RSX_SHADER_COMPILE_DIAG=1`. `RSX_PRESENT_INTERVAL` unset.

| Arm | Fetch | Async compile |
|---|---|---|
| A | off | `RSX_GVF_ASYNC=0` |
| B | `RSX_GPU_VERTEX_FETCH=1` | `RSX_GVF_ASYNC=1` |

## Session

Disconnect before starting, and **stay disconnected until both launches end, about 9 minutes**. The sequencer waits for a disconnected or local session, samples it every second and stops on any change. Reconnecting can't be prevented, only detected, and it spends the launch.

Windows state: don't minimize or cover the game window if using the local console instead. The sequencer can't see that with this executable; the SPURS check is what catches its effect.

## Stop on first failure

A failed A prevents B. A failure is any of: hash mismatch, session change, a second game process, unexpected exit, `GcKernel::Present() Timeout`, controller error, device removal, Present failure, FIFO resync, missing artifact, no race entry by 175 s, under 500 race frames, under 100 heavy frames, over 1% of frames in the 84 ms mode, or a SPURS rate collapse.

## Counters

`[rsx-frame-perf]` (frame time, `wait_ms`, draws), `[gpu-prof]`, `[wait-diag]`, `[shader-compile]`, `[spurs-busy]`, `[spurs-sched]`, the `[gvf]` totals, and CELLMARK dumps for a visual check.

84 ms mode: `wait_ms` above 50 with a `[wait-diag] why=drain` line, counted per arm. Isolated 62 ms frames are not the mode. Disconnected runs have had 0 slow frames, so it isn't expected.

## Valid A/B

Both arms pass the guard, in the same session class, on the same hash. Then compare race entry, compile counts and durations, PSO stalls, render-thread blocking, frame-time percentiles, light- and heavy-scene FPS, draw counts and errors.

One launch per arm shows no variance, so only large differences count. Race entry alone doesn't prove async compilation fixes T162's timeout: that needs B to pass the whole window with no timeout and with the `[shader-compile]` lines showing `async=1`.

`RSX_PRESENT_INTERVAL=0` remains a separate, later test.

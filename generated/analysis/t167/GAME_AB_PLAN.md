# T167: proposed game validation

**Not authorized. Nothing here has run.**

## Executable

`build/motorstorm-t167/MotorStormPacificRiftRecomp.exe`
SHA-256 `b2a720e243ecd297e4b86c3d312f249be9720c13bd545533e9ae0e2f55e5b6ae`
ps3recomp `8a12a61` (detached `ps3recomp-t167-exe`), T162's recipe: `port-t161`, PPU staging lift, WWS AOT, Havok `--chain-chunks`. One exe for every arm.

## Runner

Generate `run_t167.py` from `t162/tools/make_runner_t162.py`: same route, inputs and T161 arm C environment, with `RSX_GPU_PROF=60`, `RSX_WAIT_DIAG=1`, `RSX_SHADER_COMPILE_DIAG=1` on every arm. The runner isn't written yet.

## Arms, in order

| # | Arm | Session | Environment added | Purpose |
|---:|---|---|---|---|
| 1 | R1 | remote | none (interval 1) | Mode present? |
| 2 | R0 | remote | `RSX_PRESENT_INTERVAL=0` | Wait gone? |
| 3 | R1b | remote | none (interval 1) | Mode still present, bracket |
| 4 | F0 | remote | `RSX_PRESENT_INTERVAL=0`, `RSX_GPU_VERTEX_FETCH=1` | Timeout gone? |
| 5 | F0b | remote | same as F0 | Repeat |
| 6 | L | local console or disconnected | `RSX_GPU_VERTEX_FETCH=1` | Clean timing, normal Present |

Six launches at most; stop earlier on any stop condition. Arm 6 needs the session state changed by someone at the machine.

## Bounds

- Expected race entry: 145–165 s in T158. A 195 s cap gave T162 A1 only 62 heavy frames.
- Host cap: 310 s per launch (T105's session length), so about 31 minutes at most. This is the harness's cap only, not a game timeout.
- Capture windows: light scene race frames 40–499, heavy scene from frame 600, race entry frame and the transition frame.
- Stop at race entry + 150 s.

## Stop on error

`run_guard_t167.py pre` before each launch (`--allow-remote` for arms 1–5), and `post` after. Any failure ends the sequence: unexpected exit, game timeout, `GcKernel::Present() Timeout`, controller error, device removal, FIFO resync, missing race frames or markers, hash mismatch. Arms 1 and 3 pass `--max-slow-pct 100`, because they are expected to show the mode. The post check needs `--min-heavy-frames 100`.

## What counts as proof

**84 ms resolved:** arm 1 or 3 has over 1% of frames with `wait_ms` above 50, and arm 2 has 0, with `[wait-diag]` showing no drain above 50 ms. If neither arm 1 nor 3 enters the mode, the result is **inconclusive**, since 6 of 23 remote runs never did.

**Compile no longer causes the timeout:** arms 4 and 5 both reach 100 heavy frames with no timeout; `[shader-compile]` shows fetch programs on the worker (`async=1`) and render-thread VS compile at the race-entry frame near the CPU path's 798 ms; worst frame no longer than A1's 3.17 s plus 10%.

**Report as well:** frame time, fence wait, GPU time, Present, compile calls, unique variants, hit rate if logged; visual check of the 12 CELLMARK dumps, since they aren't byte-comparable between runs. Arm 2 also needs a check for visible tearing or pacing changes.

## Known gaps

- If arm 4 or 5 still times out, PSO creation is the next suspect, and the plan ends there without more launches.
- Arms 1–5 can't give clean performance numbers for fetch: only arm 6 can, and one launch shows no variability.

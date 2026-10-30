# T167: fixes

ps3recomp `8a12a61` on `agent/t167-gpu-wait-shader-stall`, one local commit over `69489f2`. Not merged or pushed. Defaults unchanged with fetch off and no switches set.

| Switch | Default | Does | Evidence |
|---|---|---|---|
| `RSX_WAIT_DIAG=1` (`RSX_WAIT_DIAG_MS`, default 20) | off | `[wait-diag]` per blocked wait, at most 4000 lines: guest frame, tid, reason, line, fence wanted and completed, blocked time, time since Present | Located the drain |
| `RSX_SHADER_COMPILE_DIAG=1` | off | `[shader-compile]` per real compile, at most 4000 lines: stage, source kind, length, ms, result, thread, frame, hash. No source text | Compile tables |
| `RSX_PRESENT_INTERVAL` | unset = 1 | `0` or `auto` (0 only in a remote session). Logs `[present] interval=… remote_session=…` and warns when interval 1 runs remotely | 595/595 to 0/595 slow frames |
| Fetch prologue | only with `RSX_GPU_VERTEX_FETCH=1` | `[loop]` and `[branch]` so fxc doesn't unroll; skips inputs only when `rsx_vp_analyze_inputs` is exact | 466 to 65 ms |
| `RSX_GVF_ASYNC` | on when fetch is on; `0` = sync | Fetch programs compile on one worker (`vs_compile_async.h`, 256 slots). The draw takes the CPU path until ready; compile failures stay on the CPU path | Render-thread compile 192–195 to 43–45 ms; frames identical |

## Deliberately not done

- Interval 0 isn't the default: it changes presentation, and is unverified in the game. It's not a timing change for the simulation, and quality is unaffected, but it needs the validation in `GAME_AB_PLAN.md`.
- No timeout was raised and no watchdog touched. Timing, physics and `RSX_GPU_VERTEX_FETCH`'s default are unchanged.
- No disk cache or PSO worker: PSO stalls exist on both paths, and moving them is a larger, separate change.

## Trade-offs

- A program compiling in the background costs both compiles, because the fallback draw needs its CPU-path shader.
- Frames using fallback draws cost CPU expansion for that time: `heavy` ran 30,739 fetch draws async against 33,376 sync over the same frames. Output stayed identical.
- `RSX_PRESENT_INTERVAL=0` runs uncapped when the game does not pace itself: the synthetic bench reached over 4,000 FPS.

## Tools

`generated/analysis/t167/tools/`: `validate_t167`, `compile_summary_t167`, `vs_compile_bench_t167`, `rdp_natural_exp_t167`, `frame_modes_t167`, `run_guard_t167`, `test_run_guard_t167`, `nopso_regress_t167`, `run_all_t167`. In ps3recomp: `probe_present_pace.c`, `test_vs_compile_async.c`, `test_vs_compile_async.py`.

# T132: MotorStorm: Pacific Rift frame timing, 60 FPS and frame pacing

Static analysis and offline tests only. No full build and no game launch. Supporting notes: `native_timing_notes.md` (guest code, with disassembly dumps `dis_*.txt`, `scan_imports.txt`, `floatscan.txt`) and `host_timing_notes.md` (port runtime).

## 1. Base commit
- Worktree `ps3recomp-t132`, branch `agent/t132-frame-timing`. It is based on `2562ba8` ("D3D12: read guest fragment programs through END"), which is the common base of T120, T121, T122 and T131.

## 2. Original frame loop (VERIFIED unless marked)
Names come from the developer build `c38/rv/resourceviewer.elf`, matched to the retail build by masked signatures.
- **Main loop `0x82358`** (main thread, tid 1):
  - Calls `Timer::Step` (`0x435F28`) on the app timer at app+0x130 (call at `0x82D0C`).
  - Reads dt from app+0x140.
  - Updates and renders, then loops via `0x82D7C`.
- **Present:** `DisplayATG::Present 0x5226A8` → `0x522950` → `GcKernel::Present 0x72E518`.
  - `0x72E1E0` first polls RSX `ctrl->ref` for the previous frame's target, using `usleep(30)` with a 4 s timeout. The CPU therefore runs at most one frame ahead of the RSX.
  - Then `_cellGcmSetFlipCommand` (`0x7515B4`) runs and the u64 frame counter at gcm+0xA0 is incremented.
- **There is no CPU frame limiter.** `Timer::SleepTilMinStepInterval` exists only in the developer build and has no callers there. The main loop makes no sleep or time call.

## 3. Simulation frequency
- **The step is fixed and does not depend on real time (VERIFIED).**
  - `TimeMode::updateValues 0x435B50` sets the fixed step to `n·1e6/refresh × rate`. The game's TimeMode (`0x185B8`, used at `0x4825C` and `0x1FAA60`) has:
    - refresh 59.94 Hz (50 Hz on 576-line output),
    - `FixedTimeStepFromRefresh = 2`,
    - `StepMode = 0` (fixed), rate 1.0.
  - So dt = 33,333 µs (1/30 s; 40,000 µs on PAL) on every frame. There is no measured delta, clamp or accumulator.
- **Consequence (VERIFIED by the arithmetic):** game speed = presented frames per second / 30.
  - At the port's measured 11.7–13.2 fps in the garage (perf_t15), the game runs at about 40–44 % speed.
  - Above 30 fps it would run faster than real time.

## 4. Physics and AI timing dependencies
- **VERIFIED:** `ms2Physics::Update(dt)` (`0x8CF1C0`, vtable slot 7) makes one Havok step per call with the frame dt (`0x30B710`; skipped if dt < 1e-5).
- **VERIFIED:** `0x31BA20` turns dt into 60 Hz ticks: `ticks += (int)(dt·60 + frac)`, with the remainder carried at +0x11C. That gives two ticks per 1/30 s frame.
- **PARTIAL:** no physics substep loop was found, but the virtual caller was not traced.
- **PARTIAL:** float constants in the code:

  | Constant | Sites |
  |---|---|
  | 1/30 (`0x3D088889`) | 34 |
  | 30.0 | 32 |
  | 60.0 | 15 |
  | 1/60 | 5 |
  | 1/120 | 4 |
  | 59.94 | 1 |

  This fits code tuned for a 30 Hz step. Not every site has been attributed; AI, animation and camera uses are unclassified.

## 5. RSX, vblank and flip synchronization (VERIFIED in code)
- GCM init sets flip mode 2 (VSYNC) at `0x736AC0`. The first Present switches it to HSYNC (`0x7370E0(0)`).
- **Vsync is gated on the GPU.**
  - When TimeMode.vsync is set, Present pushes NV406E `SEMAPHORE_OFFSET` = label **0x48** and `SEMAPHORE_ACQUIRE` = v ahead of the flip. It then resets a vblank counter (0x12C5EAC+4) and toggles v.
  - The vblank handler **`0x522448`** (installed by `cellGcmSetVBlankHandler` at `0x737488`) increments the counter. Once the counter reaches the threshold `*(0x11478BC) = 1` (initial data, only read), it writes label 0x48 = v.
  - So each flip lands on the first vblank after its Present.
- **HYPOTHESIS:** the gate allows up to 59.94 flips/s. Retail's 30 Hz therefore comes from a frame cost above 16.7 ms, not from any limiter. A runtime write to the threshold has not been excluded.
- **Port behaviour (VERIFIED in code):**
  - The vblank clock is exactly 59.94 Hz with no drift (`include/ps3emu/vblank_clock.h`).
  - **ACQUIRE does not block unless `GCM_SEMA_ACQUIRE=1`** (`libs/video/cellGcmSys.c`, NV406E case). By default the label-0x48 gate is ignored, so flips are not held to a vblank. This does not matter at 13 fps. Once the port exceeds 59.94 fps, it lets the fixed-step game run faster than hardware ever could.
  - `cellGcmSetFlipMode` is stored but never read.

## 6. Guest timing API analysis
| API | Use | Effect on gameplay |
|---|---|---|
| `sys_time_get_system_time` (`0x435EC4`, `0x435F4C`) | Timer/TimeMode µs clock | Measures time only. dt is fixed under StepMode 0. |
| timebase frequency (syscall 147), mftb (`0x435E60`) | hi-res timer and profiling | none found |
| `sys_timer_usleep(30)` (`0x72E26C`, `0x72E43C`) | RSX ref poll | Pacing and latency only. T121's 0.5 ms overshoot applies. |
| `sys_timer_sleep(1)` (`0x72F018`) | teardown | none |
| vblank handler `0x522448` | releases the flip gate | Caps display rate, and through it game speed |
| `cellGcmGetLastFlipTime`, `GetFlipStatus`, `GetVBlankCount`, `SetWaitFlip`, `SetFlipHandler` (registration) | not imported or not called | n/a |

- **Port clocks (VERIFIED, from code):**
  - Timebase 79.8 MHz with no rounding drift.
  - `sys_time_get_system_time` uses an anchor separate from the timebase, so the two differ by a constant offset. It also has a startup init race and a multiply that overflows after about 51 h. These are minor; they are in `runtime/ppu/ppu_sysprx.cpp`, which was not changed here.
- **Comparison with T121:** usleep overshoot (p50 ≈ 517 µs) adds latency to every RSX poll, but it cannot change dt.

## 7. Feasibility of independent 60 FPS rendering
- **A. Original cadence (baseline).**
  - One simulation step per presented frame, at a fixed 1/30 s.
  - Correctness requires the port to reach 30 fps and to honour the label-0x48 gate.
  - Exactly 30 fps on hardware also depends on the frame cost; see the hypothesis in section 5.
- **B. 30 Hz simulation with 60 Hz rendering: not available inside the game.**
  - Simulation and rendering are coupled in one main loop: Step → update → Present.
  - There is no separate render clock and no interpolation state.
  - It would need one of the following:
    - Engine-level hooks: run the render half again with interpolated transforms, camera and skinning. The authoritative state boundaries have not been identified yet.
    - RSX-level frame generation: interpolate VP constants per draw between consecutive frames. This is fragile because of draw matching, particles and UI.
  - Neither should be built before the port runs at 30 fps.
  - **Not implemented.** Plain frame duplication would not be real 60 fps.
- **C. 60 Hz simulation: parameterised, but unverified.**
  - Setting `FixedTimeStepFromRefresh` to 1 would make dt 1/60. The physics and tick converter are dt-driven.
  - The 34 sites using a 1/30 constant could contain frame-count assumptions, for example in AI, animation, timers and input.
  - This changes gameplay, so it is not authorized and was not done.
- **Practical ceiling today:** about 13 fps against a 30 fps target. Pacing and timing are not the bottleneck. CPU, SPU and GPU cost is (T106, T119, T121, T122, T123).

## 8. Frame pacing findings (host)

| # | Finding | Status | Detail |
|---|---|---|---|
| 1 | Flip-pending race | VERIFIED (code) | `s_flip_pending` was read and then cleared without an atomic, so a flip set in between was lost. **Fixed** (see section 9). |
| 2 | Frame clock wakes on `Sleep(4)` | VERIFIED (code) | `port/main.cpp:227`. Vblanks land 0–5 ms late. `ps3_vblank_clock_wait_us` exists but nothing calls it. **Proposed:** a high-resolution waitable timer until the earlier of the next vblank and the next drain. `port/` is outside git, so this was not changed. |
| 3 | Duplicate present call | PARTIAL (code) | The outer drain's `fc != last_flip` branch (`main.cpp:257-261`) presents without taking `s_flip_pending`, so the next beat presents again. After first content that second call is empty, but it double-counts `ppu_boot_frames_presented`. **Proposed:** call `cellGcm_take_flip_pending()` in that branch. |
| 4 | One thread for vblank ticks, drains and presents | VERIFIED (code) | `Present(1,0)` with 2 FLIP_DISCARD buffers and the DXGI default latency of 3. There is no waitable object, and `wait_for_gpu` runs at the start of `render_frame`. A vsync block delays the next vblank tick. HYPOTHESIS: on a 60 Hz monitor this gives a two-tick burst about every 16.7 s, and a backlog whenever render plus present takes ≥ 16.68 ms. **Candidate (coordinate with T122):** present off the beat thread, or use latency 1 with a non-blocking waitable check. |
| 5 | `max_burst` = 240 | VERIFIED (code) | Up to 4 s of catch-up in one burst. Handler calls collapse to one, so lowering it to about 8 only reduces host work. Not changed. |

## 9. Implemented corrections
- `f3f9376`:
  - `libs/video/cellGcmSys.c`: `cellGcm_take_flip_pending` now uses an atomic exchange, and `cellGcm_take_flip_pending_synced` uses a compare-exchange from 1 to 0. Win32 uses Interlocked; other builds use `__atomic`.
  - The translation unit compiles with the project's clang-cl flags (`tools/tu_t132.py`). Its warning count and kinds are identical to the base.
  - No change to guest-visible semantics.
- **Not changed:** guest time, physics constants, dt, AI, waits, and the `GCM_SEMA_ACQUIRE` default (see section 13).

## 10. Offline tests
- **New:** `tests/test_frame_timing_gate.c`, added to `.github/workflows/linux.yml`. 18 checks PASS (`logs/test_frame_timing_gate.txt`). It covers:
  - 59.94 Hz vblanks under 60, 120 and 144 Hz host loops, a `Sleep(4)` loop and a 1 ms loop;
  - with the gate, at most one flip per vblank for a 5 ms frame;
  - without the gate, the flip rate follows the host loop (more than twice the vblank rate);
  - a 40 ms frame is unaffected by the gate;
  - no drift over one hour;
  - catch-up after a 10 s stall is bounded, and the schedule restarts.
- **Existing tests re-run:** `test_vblank_clock` (17 PASS) and `test_frame_beat` (26 PASS), built with LLVM 23 clang.
- **Not covered:** pause/resume, flip-callback ordering under the real drain, and present-queue depth. Those need the D3D12 bench (T122 `bench_submit_sync`).

## 11. Integration dependencies
- **T121** touches only the usleep path in `sys_timer.c`. No conflict.
- **T122** and **T120** touch `rsx_d3d12_backend.c` (fences, `wait_for_gpu`). Any present or latency change from finding 4 must be coordinated with T122.
- **T123b:** its own changes edit `cellGcmSys.c` (an SRW lock and `cellGcm_drain_hook`). Expect a textual merge near `s_flip_pending` but no semantic overlap. T123b sits 23 commits behind `2562ba8`.
- No branch touches `vblank_clock.h`, `frame_beat.h`, `cellVideoOut.c` or `port/main.cpp`.
- T106, T109 and T113 have no overlap with these files.

## 12. Runtime validation plan (not executed; needs authorization)
1. **Default run** with `PS3_FTRACE_SYNC=1` and `PS3_VIDEO_STATS`. Record:
   - guest Present count (entries to `0x72E1E0`) per second, which equals the simulation steps per second;
   - FIFO flips per second;
   - D3D12 presents per second, splitting non-empty from empty presents;
   - vblank ticks per second;
   - frame-time median, p95 and p99.
2. **Same run with `GCM_SEMA_ACQUIRE=1`.** Confirm that label 0x48 is released by `0x522448`, that there is no wedge, and that the flip rate stays at or below the vblank rate.
3. **Read `0x11478BC` at runtime** (threshold) and the TimeMode at app+0x108 (`FixedTimeStepFromRefresh`, StepMode), to confirm the static values.
4. **Measure game speed:** race-timer seconds per wall-clock second compared with guest Present/s ÷ 30. They should agree.
5. **Vary the host monitor** between 60 and 144 Hz and compare vblank-tick variance before and after the `Sleep(4)` → waitable-timer change.
6. **Test input latency** with a pad-trigger timestamp against the first frame that changes.

## 13. Remaining risks
- **The game runs too fast if the port overtakes hardware.** With the acquire non-blocking by default and a fixed dt, a fast host would run gameplay above 1×. Once the port nears 30 fps, the MotorStorm launch configuration should enable `GCM_SEMA_ACQUIRE=1`. Validate this per step 2 of section 12 first: it could wedge if label 0x48 is never released.
- **The 30 Hz cap on hardware is a hypothesis.** If the threshold is 2 at runtime, the gate itself caps at 29.97 fps.
- **Unclassified 1/30 sites** block any assessment of option C.
- **Option B needs an engine-level split of state boundaries.** That has not been done.
- **The audit fails on the base tree.** `audit_public.py --staged` reports 25 items that are already present at `2562ba8` with nothing staged (for example `scratch/ppu_conformance.cpp`). None involve T132 files.

## 14. Local commits
- `f3f9376`: cellGcm: take the pending flip atomically; test the guest frame-timing gate. Branch `agent/t132-frame-timing`. Not pushed or merged.

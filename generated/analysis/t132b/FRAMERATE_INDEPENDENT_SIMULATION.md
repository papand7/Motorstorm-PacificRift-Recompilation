# T132B: MotorStorm: Pacific Rift frame-rate-independent game speed

Static analysis, translation-unit compiles and synthetic tests only. **No full build and no game launch.** Supporting files:
- `main_loop_callgraph.md`: a 34-step annotated table, plus the scripts and maps in `tools/` and this folder.
- `../t132/FRAME_TIMING_60FPS.md`
- `../t132/native_timing_notes.md`

## 1. Base
- Worktree `ps3recomp-t132b`, branch `agent/t132b-framerate-independent`.
- Based on T132 `f3f9376`. Its ancestry from `2562ba8` is verified, and the atomic pending-flip fix is preserved.

## 2. Native main loop: one iteration of `0x82358`
The body runs from `0x82560` to `0x82D7C`. Everything runs on the main thread (tid 1), in this order (VERIFIED unless marked).

| # | Call site / function | Role | Per tick or render |
|---|---|---|---|
| 1 | online poll; particles `GameParticleSystem` (app+0x170) with dt; world step `0x238570`; `evo::kernel::frameStart 0x436420` | housekeeping, visual particles | per tick (particles advance by dt) |
| 2 | BeginFrame `0x3463F8` → `RenderSystemATG::Begin 0x50D4B8` | opens the frame's command buffer | render |
| 3 | **input at `0x82804`**: `0x19AC0` → `0x1C2CA8` → `0x729250` → `0x72B530` (from the `FpPadThread 0x72ADF0` ring) | sampled once per iteration | **per tick** |
| 4 | **state update at `0x82824`**: race `0x6CC98` (garage `0x41488`) → **World::Update `0x216008`**. This steps the world clock (`0x209B20`; world dt clamped to 0.04 s), runs the vehicles (`0x214250`) and **`ms2Physics::Update 0x8CF1C0`** (one Havok step) | **simulation tick** | **per tick** |
| 5 | visibility kick, scene slot 0x34 = `0x331240` (`pvsjob` SPU); Ms2Online and NP; pause request; **Ms2Audio update `0x7C9F70`** | SPU dispatch, audio | visibility goes with render; audio once per tick |
| 6 | per-view render loop, ms2Rendering (app+0x40) slots 0x3C, 0x44, 0x40, 0x74. Slot 0x44 = `0x34CDE8` handles post-effects and the **exposure readback `0x4C3778`**. It waits on PVS through `0x45CAA8` → `0x5F74B0` and submits through `ExecutePushBuffer 0x50D868` | scene preparation, RSX commands | render (some slots advance visuals with dt) |
| 7 | GUI `0x810D8`, dialogs `0x32508` | UI | render |
| 8 | EndFrame `0x346A40` → `DisplayATG::Present 0x5226A8` → `GcKernel::Present 0x72E518` → **ref poll `0x72E1E0`** (frame N−1) → flip `0x7515B4` | submission, GPU back-pressure | render |
| 9 | **`Timer::Step` at `0x82D0C`** (fixed 1/30 s); `CleanupPerFrameJobMemory 0x4AAF70`; isDone `0x82D6C` | timing | **per tick** |

- SPU completion waits inside the frame are `JobBatch::Wait 0x4AACA0`, PVS completion and the Havok step.
- `cellSpursEventFlagWait` is reached only from audio and Edge decompression.

## 3. Simulation/render boundaries
- **No single call separates simulation from rendering (VERIFIED).** The simulation tick itself is one call (`0x82824`). Input, audio, pause, `Timer::Step` and isDone must also run exactly once per tick.
- **Render-side calls take dt (VERIFIED).** These are particles, scene slots 0x30/0x34, rendering slot 0x3C, the trails time, and the world/render time ratio at World+0x708. Rendering twice per tick would advance them twice.
- **No simulation code reading GPU results was found (PARTIAL; the search was not exhaustive).**
  - The exposure readback is reached only from post-effects and lags one frame without waiting.
  - Occlusion reports are issued in Present.
  - `ref` is used only for pacing.
- **Rendering cannot be skipped alone.** The visibility kick (step 5) feeds the render loop's waits.
- **Shared state (HYPOTHESIS, strong):** the renderer reads the transforms this iteration's update wrote, directly, with no snapshot. The alternating command buffers double-buffer GPU commands, not game state.
- **The GPU wait comes only in Present, for frame N−1 (VERIFIED).** The next update therefore overlaps host GPU work.

## 4. Timing architecture
| Clock | Definition here |
|---|---|
| Simulation time | Guest steps × 1/30 s (`Timer::Step`; World clock dt clamped to 0.04 s). Advances only when an iteration completes. |
| Host real time | QPC microseconds (`ps3_vblank_now_us`). Decides when a step may start. |
| Presentation time | The 59.94 Hz vblank clock and the D3D12 present. Unchanged. |
| Guest system time | `sys_time_get_system_time` and the 79.8 MHz timebase. Unchanged: never scaled, frozen or faked. |

## 5. Scheduler implementation: `8dff95e`
- **`include/ps3emu/sim_pacer.h`**, header-only:
  - Step n may start at `t0 + n·(1e6/30) µs`, computed from n, so there is no drift.
  - A late step starts immediately, which gives bounded catch-up.
  - Past `max_lag` the pacer counts an **overload**, adds the gap to `lost_us`, and restarts the schedule.
  - `pause`/`resume` exclude paused time.
  - Stats kept: steps, held time, late steps, overloads, lost time.
- **Hook in `libs/video/cellGcmSys.c`**, at the end of the guest's flip import `_cellGcmSetFlipCommand` (NID 0x21397818, called at `0x7515B4`).
  - This is a port-owned API, not an engine hook at a guessed address.
  - Once the frame is queued, the guest thread is held on a per-thread high-resolution waitable timer (no busy-wait) until its next step is due. The finished frame presents at once; only the **start of the next step** is delayed.
  - The drain's internal flips are not paced.
- **Configuration:**
  - `PS3_SIM_PACE=1` enables it. **The default is off; the original mode is unchanged.**
  - `PS3_SIM_PACE_HZ` sets the rate (default 30).
  - `PS3_SIM_PACE_LAG_MS` sets the catch-up bound (default 200).
  - `PS3_SIM_PACE_STATS=1` prints a stderr line every 150 steps.
  - The environment is read once.
- **`cellGcm_sim_pace_pause(int)`** is exported for the host, for example on window deactivation. It is not yet wired up, because `port/` is not under git.
- **Not changed:** dt, physics constants, the step count, guest timers, SPU scheduling, VSync and `GCM_SEMA_ACQUIRE`, which remains a diagnostic.
- **Rate choice:** the TimeMode's dt is 33,333 µs, so pacing at exactly 30.000 Hz gives 1.000× speed. Pacing at the display's 29.97 Hz would give 0.999×.

## 6. Guest timing semantics
- The pacer only delays the main thread between iterations. Back-pressure of this kind also occurs on hardware: the ref poll at `0x72E1E0` blocks in the same place.
- No guest-visible time value changes.
- **Risk (HYPOTHESIS):** while the main thread is held, guest vblank handlers are delivered only when another guest thread pumps (`ppu_gcm_pump`). This matters only with `GCM_SEMA_ACQUIRE=1` (label 0x48). Check it at runtime.

## 7. High-FPS behaviour (VERIFIED by synthetic tests; not yet measured at runtime)
- With the pacer on, host capacities of 60, 120, 144 and 1000 fps all give **299–301 steps per 10 s (1.0×)**. Unpaced they run faster than real time.
- **The pacer does not use VSync as the regulator.** It works whatever the present mode or monitor refresh.

## 8. Low-FPS behaviour
- **Architectural blocker (VERIFIED).** One iteration is input, then one simulation tick, then render, then Present. The simulation cannot advance without an iteration, and an iteration cannot finish without Present. Present waits for the host RSX to complete frame N−1.
- **A GPU-bound host therefore slows the simulation.** The pacer cannot add steps. It reports instead: late steps, overloads, and lost real time.
- **Staged route to decoupling (not implemented):**
  1. **Host render skip.** When behind, let the drain complete `ref`, labels and flips for a frame without executing its D3D12 draws, so the guest's ref poll returns at CPU speed.
     - The simulation does not read GPU results (PARTIAL), so gameplay should be unaffected.
     - The exposure readback (`0x4C3778`) and render-to-texture inputs would go stale for skipped frames. That is visual only, but unverified.
     - This touches the D3D12 backend and the drain, which are owned by **T122/T119**.
     - It must not add a `wait_for_gpu` on render-target size changes (1259–1265 × 708–712).
  2. **Guest render skip** (skipping steps 5–7 when behind): needs hooks at `0x82824`… `0x346A40` and the visibility kick. Not allowed until verified.
- **When the CPU itself is the bottleneck** (simulation plus SPU above 33 ms), full speed is impossible and is reported as overload.

## 9. Overload policy
- **Behind by no more than `max_lag` (200 ms = 6 steps):** run iterations back to back to catch up. The policy is bounded, so it cannot spiral.
- **Behind by more:** restart the schedule at now, increment `overloads`, and add the gap to `lost_us`. The game runs slower than real time for that span, and the stats line says so.
- **No steps are dropped.** The guest decides when to step; only the promise to catch up is given up.

## 10. Interpolation feasibility
- **Pause is an existing render-only frame (VERIFIED).** `App::SetPaused 0x2F218` sets dt to 0, World::Update skips physics, and rendering continues.
  - This is the strongest evidence that a guest iteration with dt = 0 renders without simulating.
  - Particles, trails and audio would also freeze, and pause flags are guest-visible. So it is not usable as is.
- **The engine has no previous/current state (VERIFIED).** The only history is the motion-blur matrices (`worldviewprevious`, `viewProjectionMatrixPrevious`). A 60 Hz presentation would need:
  - a snapshot of vehicle, wheel and camera transforms at the end of `0x82824`;
  - a second render pass with dt = 0 for the time-driven visuals and interpolated transforms;
  - no repeat of input, audio or `Timer::Step`.
- **Deferred:** this needs verified addresses for the vehicle and camera transform storage, and a hook to re-enter the render half. Photo mode and replay (`ViewObtainerPhotoMode`, `ViewObtainerReplay`, `VehicleRecorder`) are worth tracing as existing render-without-simulation paths.

## 11. Offline tests
| Test | Checks | Kind |
|---|---|---|
| `tests/test_sim_pacer.c` (new) | 32 PASS (`logs/test_sim_pacer.txt`) | scheduler only |
| `tests/test_frame_timing_gate.c` (T132) | 18 PASS | vblank gate model |
| `test_vblank_clock` | 17 PASS | vblank clock |
| `test_frame_beat` | 26 PASS | flip/vblank beat ordering |

`test_sim_pacer` covers:
- 10 s at 15, 20, 30, 60, 120, 144 and 1000 fps capacity.
- Late host wakeups (+517 µs).
- Variable frame times of 10–40 ms.
- A 150 ms stall, fully caught up.
- A 2 s stall: one overload, with lost time between 1.76 and 2.0 s.
- Pause and resume, with no burst.
- One hour at 60 fps: 108000 ± 1 steps.

**Boundary convention:** count the flips that land at or before the end of the span. The first flip anchors the schedule.

**Not covered offline:**
- Guest simulation determinism and vehicle state.
- Input ordering under pacing.
- SPU completion under pacing.
- Flip-callback ordering with the real drain.

These need the game. The tests built here are scheduler-only.

`cellGcmSys.c` compiles with the project's clang-cl flags (`tools/tu_t132b.py`). The 5 extra warnings are of kinds already present in the file (getenv deprecation, Windows.h case).

## 12. Runtime validation (needs authorization)
**Matrix:** default vs `PS3_SIM_PACE=1` (with `PS3_SIM_PACE_STATS=1`), each with VSync as is and with `GCM_SEMA_ACQUIRE=1`, on 60 Hz and 144 Hz monitors, in the garage and in a race.

**Measure:**
- steps/s (`[sim-pace]` lines, and entries to `0x72E1E0`);
- flips/s;
- non-empty vs empty presents per second;
- vblanks per second;
- race-timer seconds per wall-clock second;
- frame time median, p95 and p99;
- held time, overloads and lost time;
- input-to-frame latency.

**Pass:** at 30 fps capacity or more, the race timer advances 1.00 ± 0.01× wall clock. Below 30 fps, the overload and lost-time stats match the shortfall.

## 13. Performance
- **Per flip:** one QPC read, an uncontended spin lock, one waitable-timer wait, and one cached getenv.
- No polling, no GPU synchronization, no guest memory copies and no new D3D12 work.
- **Added latency:** at most one step (33 ms), and only when the host is ahead. Waking ~0.5 ms late does not accumulate.

## 14. Integration conflicts
| Branch | Overlap |
|---|---|
| T123b | Its own `cellGcmSys.c` edits (SRW lock, `cellGcm_drain_hook`) are in other regions. Expect a textual merge. |
| T122, T119, T120 | Edit `rsx_d3d12_backend.c`. Not touched here. Stage 1 render skip (section 8) must be designed with T122. |
| T121 | usleep only. No conflict. |
| T106, T109, T113, T123 | No overlap in these files. |

## 15. Local commits
- `f3f9376` (T132): atomic pending flip, plus the frame-timing gate test.
- `8dff95e` (T132B): opt-in `PS3_SIM_PACE` real-time pacer, plus tests.

Neither has been pushed or merged.

## 16. Remaining blockers
1. **Low-FPS independence needs the host render skip** (section 8, stage 1). It touches T122-owned code, and the claim that the simulation never reads GPU output must be confirmed at runtime.
2. **60 Hz presentation needs transform snapshots and a dt = 0 render pass.** The engine has no such state; the addresses are not yet verified.
3. **The pacer is unvalidated in the game:**
   - Bink, loading screens and frontend cadence under 30 Hz pacing;
   - vblank-handler delivery while the main thread is held.
4. **Host pause wiring** (`cellGcm_sim_pace_pause`) belongs in `port/main.cpp`, which is outside git.
5. **The public audit fails on the base tree** (25 items already present). None are in T132/T132B files.

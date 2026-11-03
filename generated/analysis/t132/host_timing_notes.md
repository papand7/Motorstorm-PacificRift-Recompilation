# T132 host frame-timing review (read-only)

Tree: `ps3recomp-t132` @ 2562ba8; port `port/main.cpp` + `port/frame_clock_watchdog.h` (untracked).
Method: source reading only. Nothing was built or run. Labels follow AGENTS.md.

## 1. Vblank cadence
- VERIFIED (code): `include/ps3emu/vblank_clock.h:29-41`. The deadline for tick n is t0 + n*1001000/60 us, recomputed from n each time, so the rate is exactly 59.94 Hz (the value `libs/video/cellVideoOut.c:102` reports) and does not drift. Host time comes from QPC via `ps3_vblank_now_us` (:66-72, split multiply, exact).
- Catch-up (`:49-57`): every due tick fires on that poll, up to `max_burst`. The port passes 240 (`port/main.cpp:229`), which is 4.0 s of backlog fired back-to-back. Past 240, t0 resets to now and loses the backlog. The reset then makes "tick 0" due at once, so 241 fire together (`tests/test_vblank_clock.c:63-65`).
- The frame-clock loop (`port/main.cpp:225-267`) calls `Sleep(4)` with `timeBeginPeriod(1)` (`:420`). Each beat therefore lands 0-5 ms after its deadline, plus however long the previous iteration spent in present/drain. `ps3_vblank_clock_wait_us` exists but nothing uses it.
- `cellGcmTickVBlank` (`cellGcmSys.c:928-933`) does `s_vblank_count++` (plain, not atomic) and sets a pending bit. Because pending is a bitmask, a burst of N ticks collapses to one vblank-handler call with the latest count. The count itself stays tied to wall time.

## 2. Order: present -> vblank -> flip completion
- `ps3_frame_beat` (`frame_beat.h:38-44`): take_flip -> present -> TickVBlank -> TickFlip -> drain. Flip completion happens only on a beat, so it is tied to vblank. It also requires that the drain has reached the flip marker (`gcm_flip_executed_take`, `cellGcmSys.c:149-155`) and that status is WAITING (`:946-955`).
- The guest sees DONE and the handlers only when some guest thread runs `ppu_gcm_pump` (`cellGcmSys.c:880-925`). That happens at an HLE call (`runtime/ppu/ppu_hle.cpp:279`) or in syscall 141/142 (`ppu_loader.cpp:3240`). There is no dedicated interrupt thread.
- `cellGcmSetFlipMode` (`:748-752`) only stores `s_flip_mode`. Nothing reads it, so HSYNC and VSYNC behave the same. MotorStorm calls SetFlipMode(2) and later (1) (docs/RSX_GARAGE_DISPLAY_PATH.md:31-32).
- `cellGcmSetWaitFlip` (`:755-771`) polls with Sleep(1) up to 64 times. MotorStorm does not import it.
- HYPOTHESIS: in present-gate "clear mode" (`include/ps3emu/present_gate.h`, `rsx_d3d12_backend.c:8655-8710`), the ticker present DEFERs and the real `render_frame` + Present runs at the next display clear inside the drain. That happens after the beat has already completed the flip. The frame_beat ordering (present before completion) therefore does not hold in clear mode.

## 3. Guest clocks
- VERIFIED (code): `PS3_TIMEBASE_FREQ` is 79,800,000 (`runtime/syscalls/sys_timer.h:29`). `ppu_timebase_now` (`sys_timer.c:89-106`) uses a QPC delta from a lazily set t0 with a split multiply, so it has no rounding drift.
  - Bug (low): the t0 init race is not benign. A second thread can store a later t0, and the timebase steps backwards once at startup. Fix: `InterlockedCompareExchange64`.
- `sys_time_get_system_time` (`runtime/ppu/ppu_sysprx.cpp:66-77`) has its own separate anchor, so mftb/79.8 and system time differ by a constant offset. On PS3 both count from boot.
  - Init race: `s_freq` is set before `s_base`, so another thread can read base 0 and get raw QPC uptime, a one-off forward jump.
  - `(delta*1e6)/freq` overflows after about 51 h at 10 MHz.
  - Fix: one shared anchor and the split multiply.
- `sys_time_get_current_time` on Windows returns QPC uptime, not wall time (sys_timer.c, after `sys_time_get_timezone`). POSIX returns CLOCK_REALTIME.
- `cellGcmGetLastFlipTime` (`cellGcmSys.c:3383`) returns QPC **ns**, stamped when the flip is requested (`:3209`, `:3316`). libgcm expects system-time us at completion.
- `cellGcmGetVBlankCount` (`:4221-4225`) runs `s_vblank_count++` on every query.
- Neither of the last two is imported by MotorStorm (`generated/analysis/EBOOT.imports.json`). MotorStorm's cellGcmSys imports include SetFlipMode, SetFlipHandler, SetVBlankHandler, SetFlipImmediate and _cellGcmSetFlipCommand. Both are framework bugs.
- `ps3_qpc_us` (`cellGcmSys.c:1765`) uses the integer `f/1000000`, which is wrong unless the QPC frequency is a multiple of 1 MHz. It is diagnostics only.
- Several "NID:" comments in cellGcmSys.c are stale. For example SetFlipMode is commented 0xA53D12AE but registered as 0x4AE8D215. Registration (`generated/ppu/ppu_hle_nids.cpp`) is correct.

## 4. D3D12 present
- Swapchain (`rsx_d3d12_backend.c:1018-1030`): FLIP_DISCARD with FRAME_COUNT=2 (`:96`). There is no ALLOW_TEARING flag, no frame-latency waitable object and no SetMaximumFrameLatency (DXGI default 3).
- `Present(1, 0)` (`:8368`) always waits for vsync.
- `render_frame` begins with a full `wait_for_gpu()` (`:6735`), and `move_to_next_frame` waits on a fence (`:1690-1715`). There is no CPU/GPU overlap.
- All of this runs on the frame-clock thread, which also ticks vblank and drains the FIFO. The clear-mode present also runs on that thread, inside the drain.
- Present sources:
  - beat (`main.cpp:190-194`)
  - outer `take_flip_pending` (`:241-245`)
  - outer `fc != last_flip` (`:257-261`)
  - before the first flip, every loop pass (`:262-265`)
  - display clear inside the drain (`rsx_d3d12_backend.c:8698`)
- Empty batches: `rsx_d3d12_backend_present` skips render/Present after first content (`:10685`, `:10737`). Before that, every 4 ms pass does a vsync Present.

## 5. Bugs / pacing problems
1. PARTIAL (code): duplicate present calls. When the outer drain (`main.cpp:247`) reaches a flip, the `fc != last_flip` branch (`:257-261`) presents it but leaves `s_flip_pending` = 1. The next beat or outer `take_flip` presents again for the same flip.
   - After first content the second call is an empty batch, so no Present happens. It still counts twice in `g_frames_presented` / `ppu_boot_frames_presented` and costs a call.
   - Fix: in that branch call `cellGcm_take_flip_pending()`.
2. HYPOTHESIS: vsync double-throttle and backlog spiral. The guest clock is 59.94 Hz and the host Present(1) waits for monitor vblank.
   - On a 60.00 Hz monitor the phase slips one frame every ~16.7 s, so one beat blocks a full refresh, then 2 ticks fire back-to-back.
   - If render + present takes >= 16.68 ms, the beats never catch up and run back-to-back until the 240 reset.
   - Measure vblank/s and Present ms with PS3_VIDEO_STATS / PS3_FTRACE.
3. Sleep(4) polling adds 0-5 ms of jitter to every vblank and flip completion.
   - Fix (safe): sleep until min(`ps3_vblank_clock_wait_us`, drain cadence) on a CREATE_WAITABLE_TIMER_HIGH_RESOLUTION timer (as `sys_timer_thread_hr_timer`).
4. Fix candidate (moderate): stop blocking the beat on host vsync.
   - Present(0) with ALLOW_TEARING when supported, or SetMaximumFrameLatency(1) plus the waitable object checked without blocking.
   - Guest-visible semantics are unchanged: completion still waits until the frame has been consumed.
5. Fix candidate: `max_burst` 240 -> a small number (e.g. 8) with a resync. Handlers already coalesce, so the guest sees the same count jump while the host does fewer drains and presents during a burst. Needs a test update in `test_vblank_clock.c:63`.
6. `cellGcm_take_flip_pending` (`cellGcmSys.c:160-165`) does a non-atomic read then clear. A direct-path flip (`:3198`) from a guest thread can be lost. Use InterlockedExchange.
7. Framework (not imported by MotorStorm): GetVBlankCount mutates the count; LastFlipTime has the wrong units and the wrong event; SetFlipMode is ignored.

Tests:
- `tests/test_vblank_clock.c`, `tests/test_frame_beat.c` and `libs/video/tests/test_gcm_vblank_count.c` are built only in `.github/workflows/linux.yml:368-378` (gcc). There is no Windows runner.
- Others: `tests/test_timer_usleep_win32.c` (`tools/test_timer_usleep.py`, clang), `tools/test_present_gate.py`, `libs/video/tests/test_gcm_flip_status.c`.
- Local runners: `generated/analysis/t122/tools/run_suite_t122.cmd` (vcvars + LLVM 23 + cc shim) and `generated/analysis/t121/tools/tu_t121.py`.

## 6. Branch overlap (vs 2562ba8)
- T121 (`9dfe2ca`): `runtime/syscalls/sys_timer.c` (+PS3_USLEEP_SPIN=2 timer + spin tail; default HR timer measured ~517 us for usleep(250)), `tests/test_timer_usleep_win32.c`, `tools/test_timer_usleep.py`. Touches the usleep path, not timebase/system time.
- T122 (3 commits): `rsx_d3d12_backend.c` +126 (RSX_GPU_SYNC counters, `wait_for_gpu_at`, move_to_next_frame signals a fresh fence value, present_fence +1), `include/ps3emu/gpu_sync_stats.h`, bench/tests. It overlaps the fence and present code; it does not change Present or the swapchain.
- T120 (`agent/t120-visual-fidelity`, `235b3e6`): `rsx_d3d12_backend.c` +93 (RT window sampling, adds one wait_for_gpu), `rsx_rt_window.h`, tests. It does not touch timing.
- T123b: based 23 commits behind 2562ba8, so a raw diff shows reverts. Its own changes vs the merge-base 8ea1437 include `cellGcmSys.c` (SRWLOCK around SPU block list, `cellGcm_drain_hook`), `rsx_d3d12_backend.c` (+389), SPU runtime. It does not touch vblank_clock/frame_beat/sys_timer.
- None of the branches touch `vblank_clock.h`, `frame_beat.h`, `port/main.cpp` or `cellVideoOut.c`.

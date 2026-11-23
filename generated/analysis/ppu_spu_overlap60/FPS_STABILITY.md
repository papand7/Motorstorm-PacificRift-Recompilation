# FPS_STABILITY: the periodic 50-160 ms race hitches (2026-11-20)

Private, offline. Labels VERIFIED / PARTIAL / HYPOTHESIS.

## 1. What the hitches are (VERIFIED, Kksr77 critical-path trace, `tools/spikes77.py`)
- 825 race frames, median 22.2 ms; 6 frames >= 40 ms (45-177 ms), about one every 127 frames (~2.8 s).
- In those frames the extra time is ONE contiguous main-thread block of 48-157 ms that is not a traced wait (JobBatch, Havok semaphore, GcKernel poll are as in a normal frame). SPU work does not grow.
- Every thread's CPU falls in those 250 ms windows (main 91 -> 76 %, rsx 47 -> 36 %, SPU lanes 37 -> 28 %): the main thread is blocked, and the rest idle behind it.

## 2. Cause (VERIFIED)
- `[hle-wait]` for the main thread in the race shows, every 2-4 s, one HLE call blocking 43-62 ms in `sys_lwmutex_lock` (NID 0x1573DC3F) or 65-157 ms in `cellPadGetInfo` (NID 0x3AAAD464). NIDs computed from the names (SHA-1 + PS3 suffix).
- The racing-wheel backend (`libs/input/pad_wheel_dinput.h`, `PWH_ENUM_MS 2000`) runs DirectInput `EnumDevices` synchronously inside the pad poll every 2 s while no wheel is attached. The pad poll runs on the game's main thread (cellPadGetInfo) and on other game threads (0x3AAAD464 on tids 20 and 23, i.e. while they may hold a game lwmutex that the main thread then waits on).
- Runs: Kksr50 (exe 6425564b, before the wheel code): 0 main-thread windows with a >= 40 ms pad/lwmutex stall. Kksr61 / Kksr77 (33253d9d) and Kksr87 (ppucc2): 30 / 39 / 31.
- Offline reproduction (`tools/test_wheel_poll_latency.c`, this PC, no wheel attached): synchronous scan 4 stalls in 7 s of 167, 65, 65, 65 ms.

## 3. Fix (isolated: `D:\motorstorm\ps3recomp-padfix`, `tools/patch_wheel_async.py`)
- `PAD_WHEEL_ASYNC_SCAN=1`: the scan (enumerate, choose, open) runs on its own thread every 2 s while no wheel is open; the result is installed under the existing wheel lock only if no wheel was opened, the settings did not change and the pad layer was not released. `pad_wheel_poll` never calls DirectInput's enumeration on a game thread. Opt-in; the synchronous scan stays the default. Game-visible behaviour is unchanged: the pad state and its timing contract (a wheel appears within ~2 s of being plugged in) are the same; only the host thread that does the scan changes.
- Offline tests: latency test with =1: 441 calls, slowest 0.06 ms, 0 calls > 2 ms (VERIFIED). Existing wheel suite (`port-vkgame/tools/build_wheel_tests.cmd` with FW = the patched copy): rc=0 (VERIFIED).
- Not tested: a real wheel plugged in and out with =1 (hardware).

## 4. Expected effect (MODELLED, not measured)
- Removes ~1 hitch every 2-3 s (each 45-160 ms). In Kksr77, frames >= 40 ms: 6 of 825; the 1-s fps dips (fps_1s_p5 ~29-35) and frame-time p99/max should improve. Mean fps changes little (~60 ms per ~2.8 s, about 2 %).
- Race validation: one exe from the patched tree, A/B by env only (PAD_WHEEL_ASYNC_SCAN=0 vs 1), ABBA, >= 3 valid runs each; measure frame-time p99/max, over34 %, fps_1s_p5, `[hle-wait]` stalls >= 40 ms on tid 1.

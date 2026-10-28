# Native-audio startup regression (run `20261023-100017-audio`)

The silent-audio runs `ind` and `sse2` reach the garage request. The native-audio run
froze at about 104 s and never did.

## Earliest verified divergence (VERIFIED)

About 31 s into the run, roughly 2.5 s after the first Bink decode at 28.7 s, the
native-audio run enters Bink's 4:1 skip.

| Run | Presents/s | Decoded/s | Displayed/s |
|---|---|---|---|
| audio, 31–39 s | 7–8 | 28–32 | 7–8 |
| silent runs, same interval | ~30 | ~30 | ~30 |

The audio run recovers to 1:1 at 40–48 s. Its decode rate at video start is 28–29/s,
against 30/s silent.

In the 60–70 s ftrace window, the main thread waits much longer in Bink's
`DoFrameAsyncWait` (`usleep`, lr `0xC704EC`) with native audio:

| Run | Waiting | Per frame |
|---|---|---|
| audio | 115.9 ms | 132.5 ms |
| `ind` | 6.8 ms | 18.6 ms |

Bink Audio Thread mutex waits are also larger.

## Freeze at ~104 s (VERIFIED symptoms)

- The vstat CSV stops at 2255 decoded frames and 2525 flips. The `rsx-hb` heartbeat stops.
- The guest logs 26 `Gc ERROR: GcKernel::Present() Timeout!`:
  - its Present counter climbs from 2526 to 2551;
  - "Last Reference Passed" stays at 2526;
  - RSX GET stays at offset `0x11068`.
- No runtime message accompanies it:
  - no walker diagnostic;
  - no `[D3D12] FENCE STUCK` or `wait_for_gpu STUCK`;
  - no device-removed report.
- Audio and SPU threads keep running. Main tid 1 polls `usleep` at lr `0x72E5C0`. Process
  CPU drops.

## Synchronization review (code reading, `port/main.cpp`, `cellGcmSys.c`, `rsx_d3d12_backend.c`, `cellAudio.c`)

VERIFIED (code reading):
- **`s_gcm_fifo_lock` cannot deadlock.** Only the frame-clock thread takes it
  (`cellGcm_rsx_process_fifo`), so there is no second owner.
- **`s_ref_pub_lock` cannot block a guest thread.** Guest threads only `TryAcquire` it
  (`cellGcm_ref_on_poll`). The frame clock's blocking acquire can wait only for a guest
  holder's bounded publish.
- **The guest vblank and flip handlers are deferred** (`GCM_PENDING_SET`). The frame clock
  does not run guest code.
- **Semaphore ACQUIRE does not block** unless `GCM_SEMA_ACQUIRE=1`.
- **Fence waits are bounded at 2 s and logged** (`wait_for_gpu`, `move_to_next_frame`).
  Neither logged, so the stall is not in a fence wait.
- **The frame clock takes no audio lock.** `s_audio_mutex` is used only by `cellAudio.c`'s
  mixer and API. WASAPI is event-driven with a 10 ms bounded wait.
- **`IDXGISwapChain::Present(1, 0)` has its HRESULT ignored.** A device removal there is
  not reported unless a later fence wait runs.

Unlogged places where the frame clock can block (HYPOTHESIS; not distinguished yet):
1. DXGI `Present` blocking on frame latency or the compositor;
2. `DispatchMessage` in the window pump: a modal loop, or a cross-thread `SendMessage`;
3. a non-terminating FIFO walk;
4. a blocking call inside the D3D12 driver during the drain.

No specific synchronization defect is verified, so no correction was made. The 4:1
skip's cause is also open. Native audio makes the guest's Bink audio thread do real work,
and its mutex waits rise (HYPOTHESIS: contention with the main thread's frame loop).

## Diagnostic added: frame-clock watchdog

- **Code:** `port/frame_clock_watchdog.h`, wired into `frame_clock` in `port/main.cpp`.
- **Off by default.** `PS3_FC_WATCHDOG_MS=N` (minimum 500) starts a checker thread.
- **What it reports:** after N ms without frame-clock progress, it prints the stage and a
  host stack of up to 24 frames as `module+offset`:
  - `[fc-watchdog] frame clock no progress for N ms in stage=sleep|beat|present|drain|pump`
  - one report per stall, at most 8 per run.
- **Effect on the frame clock:** it stores a stage and does an interlocked increment per
  step. It does not touch guest state or recover anything.
- **Test:** `port/tests/test_frame_clock_watchdog.cpp` PASS, built with clang-cl
  `/W4 /WX`.
- **Exe:** `build/motorstorm-int/MotorStormPacificRiftRecomp.exe`
  `f25903bca47a32a13820d42f5f1dcab70fccf712e4c8ff8b7ab977ff390f7cb8`. A copy plus the
  `.map` is in `build/motorstorm-int-fcw-f25903bc/`. The previous exe `611ad702…969ba8` is
  kept in `build/motorstorm-int-8b62438/`.
- **Resolving offsets:** use `MotorStorm.map` for the exe. Release, no PDB.

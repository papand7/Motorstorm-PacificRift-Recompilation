# Presentation stops at frame 1733 (offline, 2026-10-23)

Run `generated/runs/20261023-150148-garage-render/`, stderr line numbers below. Source: ps3recomp-int `c874771`, port `port/main.cpp`. MotorStorm was not launched.

## Final sequence (VERIFIED from the log)

| stderr line | ~s | Event |
|---|---|---|
| 3302 | 29 | `sys_ppu_thread_create tid=28 name="AsyncRenderThread" entry=0x01088970` (after the skipped intro) |
| …5690 | 30–45.8 | heartbeat every second, last `[rsx-hb] ms=45125 frames=1733 draw_frames=1334 last_draws=3`; `[vstat]` every 2 s (32.9 presents/s, 32.9 flips/s); RSXI frames 1361–1381 are this thread's loading screen |
| 5696 | 45.8 | `[WAIT] ppu_thread_join(tid=28)`: a guest thread waits for the render thread to end |
| 5718–5720 | 45.8 | tid 28 calls `sys_ppu_thread_exit(status=0xBABE)` and returns normally |
| 5863 | 45.9 | `[RSX] CLEAR_SURFACE new mask=0x3` (depth+stencil, no colour), decoded by the drain |
| 5968, 5987 | 45.9 | texture binds decoded at record time: format `0xB4` (unit 11, `0x0077B080` 256×1) and `0xB0` (unit 13, `0x06FF0000` 1024×2048, in tile 6, pitch 4096); both refused as "unsupported format" |
| 6046 | 46 | `[RSX] CLEAR_SURFACE new mask=0x2` (stencil) |
| — | 46–210 | no `[rsx-hb]`, `[vstat]`, `[shader]`, `[RSXI]` or `Present failed` line; FIOS reads (fd 5, 3, 4) and SPU dispatches continue to the end; no `[fc-watchdog]` report |

`[CLEAR_SURFACE new mask]` and `[tex] unsupported format` print once per new value, so later RSX activity is invisible, not absent.

## What continued after frame 1733

| Activity | After 45.8 s | Evidence |
|---|---|---|
| Guest RSX command submission | **yes**, at least briefly | clears and texture binds decoded at 45.9–46 s |
| Drain (command processor) | **yes** | those lines are printed by the drain |
| Frame-clock thread | **yes** | no `[fc-watchdog]` report with a 3 s threshold |
| Backend replay (`render_frame`) | **no** | `render_frame` has no early return and prints the heartbeat at most once a second; none after 45.8 s |
| Host Present | **no** | `[vstat]` prints only from the present path; no line |
| Shader translation | **no** | translation happens only during a replay; no `[shader]` line |
| Guest flip requests | **UNKNOWN** | not logged |
| Window messages | yes | the pump runs in the frame-clock loop |
| GPU fence completions | no work submitted, so nothing to wait on | — |
| FIOS, SPU | **yes**, to 210 s | `[fsread]`, `[spu_workload]` |

## Cases

| Case | Status |
|---|---|
| A. The guest stopped requesting presentation | **open**. The loading-screen thread ended; whether the guest thread that took over issues flips is not recorded. |
| B. The guest submits work and the runtime stopped processing it | **refuted** for the drain: commands were decoded after the stop. |
| C. Commands processed, host presentation stopped | **open, with a concrete mechanism** (below). |
| D. The guest intentionally waits on loading | **possible**: the guest joined its loading-screen thread while FIOS and SPU work goes on. A frontend that draws nothing until loading completes would look like this. |
| E. A thread or queue blocked without an error | no new block found. A SPURS `EventFlagWait` on `0x0140F000` has been blocked since about 28 s, but the same wait is in every run since 2026-10-22, including runs that kept presenting (report capped at 24 s). Not a GPU deadlock: no GPU work is outstanding. |

## The mechanism behind case C (VERIFIED in code; whether it fired here is UNKNOWN)

**1. Presents become clear-driven.** `rsx_d3d12_backend_present` (`rsx_d3d12_backend.c:7796`) is what the port calls on every guest flip (`port/main.cpp:117`, `present_guest_frame`). Once the backend has presented at a frame-boundary clear (`s_clear_presents > 0`), it **returns immediately** (`:7810`).

**2. A clear-boundary present needs all of the following** (`d3d12_clear`):
- a **colour** clear of a **display** surface;
- at least one recorded non-clear draw targeting the display (`:6267`);
- a guest flip since the last present;
- a batch of at least a quarter of the largest frame seen.

**3. The batch is reset only by that path or by a replay.** Records past `MAX_DRAWS` (2048, `:65`) are dropped silently at every record site (e.g. `:6237`).

So suppose the guest's new renderer:
- never colour-clears a display buffer (it composites full-screen without a clear), or
- renders its frames into a surface that is not a registered display buffer (`current_rt_off`, `:3481`).

Then the runtime never replays or presents again, and once the batch fills, later display draws are dropped too. That would match every verified row above.

The old 2026-10-21 run (older build, no intro skip) also ended its `AsyncRenderThread` (tid 29, stderr 49058). That run built cube-map programs afterwards (stderr 49592), which happens only in a replay. So the frontend's next stage did replay there. The cause of the difference is UNKNOWN.

**Not fixed.** The frame-boundary policy is shared by every title, and it is not shown that flips arrived, so the defect is not proven. The new diagnostic decides it.

## Why the frame-clock watchdog stayed silent (VERIFIED, `port/frame_clock_watchdog.h`)

- It watches the **host frame-clock thread**: the stage marks `sleep`, `beat`, `present`, `drain` and `pump` in `port/main.cpp:225–266` bump its progress counter.
- After `PS3_FC_WATCHDOG_MS` without progress it reports where that thread is stuck.
- The thread kept cycling (`Sleep(4)`, drain, pump), so there was nothing to report. It works as designed.
- The runner's GPU-watchdog stop (`GcKernel::Present() Timeout`) is a guest message. The guest never printed it.

## New diagnostic: `PS3_PRESENT_PROGRESS_MS` (ps3recomp-int `c874771`)

`include/ps3emu/present_progress.h`. It is off by default and never stops or delays anything. After N ms without a real Present (then at doubling intervals, at most `PS3_PRESENT_PROGRESS_MAX` lines, default 8), it prints the deltas since the last Present:

| Counter | Hook |
|---|---|
| `flips` | the 3 `s_flip_request_count++` sites in `cellGcmSys.c` |
| `drain_moves` | drain passes that moved `get` |
| `ticker_calls` | `rsx_d3d12_backend_present` calls |
| `replays` | `render_frame` entry |
| `presents` | the swap-chain `Present` |
| `gate.clear_mode`, `gate.no_display_draw`, `gate.no_flip`, `gate.small_batch` | the four early returns above |
| `batch=n/2048` (`FULL` when full) | the backend batch |
| `fs_reads` | `cellFsRead` |
| `spu_dispatches` | async SPU workload dispatches |

It is silent before the first Present. Test: `tools/test_present_progress.py` (20 harness and 14 source checks).

**Reading the first report:**

| Report | Meaning |
|---|---|
| `flips=0`, `drain_moves>0` | case A or D: the guest stopped flipping |
| `flips>0`, `gate.clear_mode>0`, `replays=0` | case C: the runtime swallowed the flips. Check `gate.no_display_draw` and the batch (`FULL` means draws are being dropped) |
| `flips>0`, `replays>0`, `presents=0` | replays happen, but no display content reaches a Present |
| `drain_moves=0` and flips pending | the drain is stuck on the guest command stream |

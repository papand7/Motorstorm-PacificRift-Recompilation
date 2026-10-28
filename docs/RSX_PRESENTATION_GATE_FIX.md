# RSX presentation gate: guest flips present again after clear boundaries stop (2026-10-23)

ps3recomp-int commit `25cbff4` (on top of `c874771`). Exe `build/motorstorm-int-gate-a757cb88/` (SHA256 `a757cb88ab8b125d00b0ac6ad29453f6e1409b81cfe44c2aad9bc1c7498b7677`). **Not run** (MotorStorm was not launched).

## Verified defect (run `20261023-172442-present-stall`)

In the 6 s after the loading-screen `AsyncRenderThread` exits:
- `flips=+40`, `drain_moves=+41`, `ticker_calls=+40`;
- `gate.clear_mode=+40`, every other gate 0;
- `replays=0`, `presents=0`;
- `batch` 721 → 985 of 2048.

The guest keeps flipping and submitting; the runtime drops every flip.

## Previous behaviour

| Path | Rule |
|---|---|
| Ticker (`rsx_d3d12_backend_present`, called by `port/main.cpp` for each guest flip, before the next drain) | presents the batch, **until** the first clear-boundary present; afterwards it returns at once, forever |
| Display colour clear (`d3d12_clear`, `rt == 0`, colour bits set) | presents the batch if it has a display draw, a flip arrived since the last present, and the batch is ≥ 1/4 of the largest frame seen |
| Depth/stencil clear (mask without `0xF0`) or offscreen clear | an ordered record in the batch, never a frame boundary |
| Batch full (`MAX_DRAWS` = 2048) | the record is dropped, silently |

**Why clear mode exists:** when the drain runs past a flip (ring wrap, backlog catch-up, or a flip made outside the stream), the batch holds the head of the next frame. A ticker present then showed a partial frame (the "blink"); the clear that starts the next frame is the reliable boundary.

**The defect:** the latch never expires. Once a title has presented at a display colour clear, a renderer that stops colour-clearing its display buffer is never shown again. MotorStorm's next renderer clears only depth/stencil (masks `0x3`, `0x2`). Its draws then pile up toward 2048 and are then dropped without a message (about 12 s after the stall began, by the run's rate).

## RSX semantics used

- **A flip is a command in the stream.** libgcm's `cellGcmSetFlip` writes the flip into the command buffer. The RSX executes it in order, and the display then scans out the named buffer. The frame ends there.
  - The runtime models this: `_cellGcmSetFlipCommand` queues a `0xFEAD01xx` marker (`cellGcmSys.c:120`).
  - The drain stops at that marker unless it is badly backlogged (`cellGcmSys.c:1951–2001`), and the ticker runs before the next drain (`port/main.cpp:241`).
  - So at a flip the batch normally holds exactly the finished frame.
- **A clear is not a frame boundary.**
  - `CLEAR_SURFACE` writes the bound surface: colour and/or depth/stencil. It says nothing about scan-out.
  - A depth/stencil clear is part of the frame being built.
- **MotorStorm's flips are FIFO markers (INFERRED):** one drain stop per flip (`drain_moves` 41 against `flips` 40).

## Correction

- **New `include/ps3emu/present_gate.h`:** header-only and platform-independent. It holds the existing decisions, unchanged, plus one new rule:

  > The ticker defers to the clear **only while display colour clears keep arriving**. After `PG_CLEAR_LAPSE_FLIPS` (2) consecutive guest flips with no display colour clear at all, the flip presents the batch again. The next display colour clear re-arms clear mode. A flip already consumed by a present (either path) is never presented twice.

- **Why 2 flips, not 1:** a title that clears every frame can still see one ticker call between a flip and the next frame's clear.
- **What 2 costs at the transition:** the first flip after the lapse is deferred, so the next present replays two frames' records, in order.
- **Changes in `libs/video/rsx_d3d12_backend.c`:**

  | Where | Change |
  |---|---|
  | `d3d12_clear` | `ps3_pg_display_clear` replaces the inline gate, same conditions and order; any display colour clear resets the lapse counter |
  | `rsx_d3d12_backend_present` | `ps3_pg_ticker`: defer (`PP_GATE_CLEAR_MODE`, as before) or present (`PP_FLIP_PRESENT`, and the flip is marked consumed). The replay below is the existing ticker path: the batch replays if it holds records, and presents only if it holds a display draw |
  | Batch overflow | all 6 record sites go through `batch_room()`, which counts each drop (`PP_BATCH_DROP`) and prints `[d3d12] batch full ... N draw record(s) dropped so far` at N = 1, 2, 4, … (at most 64 lines a run). `MAX_DRAWS` stays 2048 |
- **`present_progress.h`:** two new fields, `flip_presents` and `dropped`. The report line keeps its prefix, so the existing stop regex still matches.

**Unchanged:**
- titles that colour-clear the display at least once every 2 flips (the harness compares old and new policies on such sequences: identical presents);
- titles that never flip;
- boot before the first clear present;
- depth/stencil clear handling;
- the Bink intro path, as long as it colour-clears the display at least once every 2 flips (not re-verified; the next run plays the shortened intro);
- the guest-visible flip status and handler (`cellGcmSys.c` untouched).

## Backlog limit (`MAX_DRAWS` = 2048)

| Question | Answer |
|---|---|
| What is the limit? | Deliberate sizing: per-draw constant slots (`VP_CB_STRIDE · MAX_DRAWS · 2`) and SRV descriptors scale with it. It is not a diagnostic |
| Silent drop? | Yes, before this change. Now counted and reported |
| Should the queue drain at guest flips? | Yes. With the fix, MotorStorm's sequence keeps the batch at about two frames (harness: at most 16 records with 8-record frames, none dropped) |
| Raised? | No |

## Tests

- **`tools/test_present_gate.py`** (9 source checks) runs `libs/video/tests/test_present_gate.c` (19 checks). The harness feeds the real header synthetic sequences:

  | Sequence | Result |
  |---|---|
  | Boot | flips present |
  | Colour clear every frame | identical to the old policy |
  | Two display clears per flip | identical to the old policy |
  | Late ticker after a clear present | no partial frame |
  | The run's case | old: 40 flips swallowed, 256 dropped; new: presents resume after one flip, 0 dropped, order kept |
  | Draw → depth / stencil / depth+stencil clear → flip | flips present |
  | Draw → colour clear → flip | stays in clear mode |
  | Flips with no new draws | no duplicate present |
  | Alternating display buffers | one present per flip |
  | Clear → flip → clear transitions | no loss or repeat |
  | No-flip title | unchanged |
  | Full batch | drops counted |

- **`tools/test_present_progress.py`:** updated for the new gate locations and the two new fields.
- **Test runs:** Windows (source checks; the harnesses need a C compiler) and WSL (with the harnesses) both pass.
- **Not covered:** the real D3D12 backend. It is Windows/GPU-only, and there is no backend integration harness. The next run is the integration check.

## Expected impact (to confirm by `NEXT_PRESENTATION_VALIDATION.md`)

- **After `AsyncRenderThread` exits:**
  - presents resume about one flip later;
  - `[rsx-hb]` and `[vstat]` lines continue;
  - the shaders of the next renderer are translated (translation happens only at replay).
- **Garage:** a visible garage is not implied; the game may still be loading.
- **Brightening:** the loading-screen brightening is unaffected. It is guest data (`LOADING_SCREEN_FADE_TRACE.md`).

## Risks

- **A title that colour-clears the display less often than every 2 flips**, and whose drain runs past flips, now gets ticker presents in between. Partial frames can then reappear.
- **A batch with only offscreen work:** the ticker in flip mode replays it without presenting, as the ticker path always did before clear mode.

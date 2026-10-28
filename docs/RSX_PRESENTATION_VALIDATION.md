# RSX presentation validation: from guest flip to presented image (offline, 2026-10-23)

## Update after run `20261023-200314-garage-display-path`

**VERIFIED:**
- Presents stopped at guest flip 1639, because the garage's display draws were dropped before reaching the batch (`vertex_buffer_full`, `RSX_DRAW_REJECTION_AUDIT.md`).
- The gate behaved correctly: with no display-targeted record, it withheld Present.

**Changed:**
- **New stage, "draw rejected":** counted per reason (`[draw_acct] reasons=`), with truncation and buffer growth.
- **Upload buffer:** now grows, so later frames keep their display draws. The gate and Present path are unchanged.

**Still needed at runtime:**
- `present_success` rising after the handoff;
- a captured garage frame with `present attempted=1 ok=1`.

---

## Update after run `20261023-190803-garage-present`

**Measured (VERIFIED):**
- 1,757 Present attempts, all `S_OK`. The last one was at guest flip 1650 (≈48 s).
- After that, 66 flips replayed 554-record garage batches with no display draw, so `replayed_no_present` went 2 → 67 and nothing was presented. The GPU completed the work.
- The gate stayed in BOOT.

**Gate audit (`RSX_GARAGE_DISPLAY_PATH.md` §6):**
- BOOT is the ticker-presents mode used before any display colour clear has presented. With the intro skipped it is expected for the whole run.
- It does not suppress anything. The Present is withheld because `has_display = 0`: no recorded draw targets a registered display buffer.
- No mode change or Present is forced.

**Added stages:**

| Stage | Before | Now |
|---|---|---|
| Guest draw issued but not recorded (INLINE_ARRAY, immediate vertices, empty BEGIN/END) | not visible | `PS3_DRAW_ACCT_MS`: `groups.*`, `unrecorded_display_groups`, `event=unrecorded_display_group` |
| Draw callback returned without a record | not visible | `callbacks.recorded/merged/dropped`, `dropped_display`, `event=dropped_display_draw` |
| Guest display-buffer memory at the flip | not visible | `PS3_DISPMEM_PROBE`: `[dispmem]` when the flipped buffer's guest bytes change |
| Transfer-engine activity | NV3089 only, sampled 1 in 64 | `NV3089_GATE` latched (no gap), `PS3_XFER_TRACE` for subchannels 1–6, `GCM_OBJDBG` for bindings |

---

ps3recomp-int `9bad862` (on top of `25cbff4`). Exe `build/motorstorm-int-diag-346f4e9e/` (SHA256 `346f4e9ea63dc6917f3a53919641733a14e72c17deefbc76d1bd2d3b64116b92`). **Not run.** MotorStorm was not launched.

## The stages of a frame, and what proves each

| Stage | Where | Evidence before `9bad862` | Evidence now |
|---|---|---|---|
| Guest flip requested | `cellGcmSys.c` flip marker or direct flip; `s_flip_request_count` | `[present-progress] flips=` (only during a stall) | `[present_diag] guest_flips=` |
| RSX command processed | FIFO drain, `drain_moves` | `[present-progress]` | unchanged |
| Gate decision | `present_gate.h`: boot, defer, flip, clear | `gate.clear_mode` (stall only) | `gate.boot/defer/flip/clear=` |
| Batch replayed | `render_frame()` | `[rsx-hb] frames=` (the backend frame counter); **this is all the last run showed** | `replayed=` |
| Replayed without Present | `s_present_this_frame = has_display = 0`: no draw targets a display buffer | not visible | `replayed_no_present=` |
| Render target completed | GPU work of the replay | RSXI snapshots (after a GPU wait) | unchanged |
| Present submitted | `IDXGISwapChain::Present` called | `[vstat] presents=` (every 2 s) | `present_attempts=` |
| Present succeeded | Present's HRESULT ≥ 0, not `DXGI_STATUS_OCCLUDED` | failures only (`[D3D12] Present failed`, first 8) | `present_success=`, `present_occluded=`, `present_failed=`, `last_hresult=`; `event=flip_mode_present ok=1` |
| GPU completed | the fence signalled after Present has passed | not visible | `fence_present=` vs `fence_completed=`, `gpu_done=` |
| Frame capture completed | RSXI frame finished after its Present | `frame_end` (written before Present) | `present` event, then `events.jsonl.part` → `events.jsonl` |

## What run `20261023-180259-present-gate` showed, and did not

- **VERIFIED:**
  - after the loading-screen render thread exited (47.4 s), the backend frame counter went from 1744 to 1763: batches were replayed;
  - garage programs were translated and built at replay.
- **NOT SHOWN:** that any of those replays called `Present`, or that one succeeded. `rsx_d3d12_backend_present` replays a batch with no display-targeted draw **without** a Present (`has_display = 0`), and the frame counter advances either way.
- **Evidence that this is the likely case: older build, VERIFIED for that build.**
  - The earlier garage capture (run `20261022-064218-fast-garage-capture2`, exe `7770ec7a…`) recorded `"present":0` for all its garage frames (4608, 4668, 4728).
  - Each held 554 records, and not one draw targeted a display buffer (`0x00010000`, `0x00394000`).
  - The end-of-frame backbuffer snapshot was all zero.
  - See `GARAGE_RENDER_PIPELINE.md`.
- **Prediction for the next run (HYPOTHESIS):** after the handoff, `replayed_no_present` climbs while `present_success` stays flat, and no `event=flip_mode_present` line appears. The `[present-progress]` stall reports then follow, every 3, 6 and 12 s.

## Renderer handoff semantics (offline tests)

| Property | Test | Result |
|---|---|---|
| Queued draws replayed exactly once; no duplicate present | `test_present_gate.c` (flips with nothing new, clear → flip → clear) | PASS |
| Flips not suppressed for lack of a colour clear | `test_present_gate.c` (loading screen → depth/stencil-only renderer) | PASS |
| Depth/stencil-only clears stay ordered records | `test_present_gate.c` + source check | PASS |
| Display-buffer switching | `test_present_gate.c` (alternating buffers) | PASS; the backend presents one swapchain whatever guest buffer is flipped, and now records the guest buffer per present and per captured frame |
| Colour clears do not duplicate frames | `test_present_gate.c` | PASS |
| Draw order, no silent loss | `test_present_gate.c` (order kept, drops counted) | PASS |
| Not unconditional presentation | `test_present_gate.c`; `test_present_diag.c` (a replay with no display draw is not a present) | PASS |
| Bink intro compatibility | the old and new policies give identical presents for a colour clear every frame (the intro's pattern) | PASS offline; runtime not re-verified |
| Present-result diagnostics | `test_present_diag.c`: S_OK, failure, occluded, handoff event only after success, bounded output, fence | PASS |
| Capture completion, metadata and cancellation | `test_present_diag.c` (selection); `test_rsx_inspect.py` (`.part` frame reported as cancelled, `present` event) | PASS |

## New switches (all off by default)

| Switch | Effect |
|---|---|
| `PS3_PRESENT_DIAG_MS=<ms>`, `PS3_PRESENT_DIAG_MAX` (default 64, max 1024) | periodic `[present_diag]` summary, plus the handoff event |
| `RSXI_EVENT=flip_mode`, `RSXI_PRE_COUNT`, `RSXI_PRESENTED` | event-driven capture (`GARAGE_FRAME_CAPTURE.md`) |
| `NV3089_GATE_MAX` | caps the existing `NV3089_GATE` blit trace |
| runner `--env VAR={run_dir}/...` | per-run paths in the environment |

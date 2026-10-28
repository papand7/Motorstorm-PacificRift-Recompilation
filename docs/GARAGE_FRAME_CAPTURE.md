# Garage frame capture (offline, 2026-10-23)

## Update: capture independent of the present gate

**Run `20261023-190803-garage-present` captured no garage frame (VERIFIED).** Its "main" phase waited for the gate's first FLIP replay. The gate stayed in BOOT the whole run (`gate.flip=0`), so only the pre frame 1595 was taken, and the manifest stays `capturing`. Why BOOT is expected: `RSX_GARAGE_DISPLAY_PATH.md` §6.

**`RSXI_EVENT` now names the event that opens "main"** (`include/ps3emu/rsxi_trigger.h`):

| Value | Opens "main" at | Needs a gate FLIP? |
|---|---|---|
| `flip_mode` | the gate's first FLIP replay (unchanged) | yes |
| `no_present` | the first replay with no display draw, i.e. an offscreen-only batch (the garage) | no |
| `present` | the first replay that will call Present | no |

`no_present` with `RSXI_PRESENTED=1` would never capture, so presented-only is cleared and a line says so.

**Capture categories, kept separate in each frame:**

| Field | Meaning |
|---|---|
| header `category` | `offscreen_replay` (no display draw, no Present) or `host_present`, decided before Present |
| `present` event | `attempted`, `hresult` and `success` after Present returned. An offscreen replay records `attempted=0` and is never labelled presented |
| `pass` and `end` snapshots | every offscreen render target the replay wrote, after its pass and at the end of the frame. Copied inside the frame's command list and read back after one fence wait. Each snapshot carries guest offset, size and DXGI format; `rt_pool` adds slot and resource pointer |
| `bb` snapshot | the D3D12 backbuffer (the host display surface) |
| take/event/frame | the replay number is `frame`; the reason is `take` + `event`. Completion is still the `.part` → `events.jsonl` rename |

`rsx_inspect.py` reports `event` and `category` per frame. A test covers an offscreen replay with `attempted=0`.

**Limits:**
- 2×AA guest surfaces (`0x3148`, pitch 10240) are stored and snapshotted at 1280×720, without their multisample layout (`RSX_GARAGE_DISPLAY_PATH.md` §3).
- Guest display buffers are not GPU resources in this backend; `PS3_DISPMEM_PROBE` samples their guest memory instead.
- Snapshot BMPs remain raw render-target bytes with no correction.

---

ps3recomp-int `9bad862`. **Not run.**

## Why run `20261023-180259-present-gate` captured nothing (VERIFIED)

1. **Trigger.** The runner wrote `rsxi.trigger` 1 s after `loadscreen_renderer_exited`, and the backend began frame 1763 (`[RSXI] triggered at frame 1763`).
2. **Kill.** That replay was translating and compiling the garage's first cube-map programs (each `pso_ready` 50–100 ms apart). The first cube outcome was a **stop line**, and the runner breaks on a stop line at once. It does not wait for a pending capture; it waits only when the stop is the target milestone. So the process was killed mid-frame.
3. **Empty file.** `frames/f001763/events.jsonl` was 0 bytes: the frame header was still in the stdio buffer. There was no `frame_end`, and the inspector reported `no frame_end (partial frame)`.
4. **Status.** The capture was never marked complete (manifest `capturing`). The old format did not misreport it, but an empty `events.jsonl` was indistinguishable from a file still being written.

## Changes (`9bad862`)

- **Event-based selection** (`RSXI_EVENT=flip_mode`, `include/ps3emu/rsxi_trigger.h`):
  - **pre:** `RSXI_PRE_COUNT` frames once the trigger file exists. Arm it during the loading screen to get the outgoing renderer's frame for comparison.
  - **main:** `RSXI_COUNT` frames, every `RSXI_STRIDE`-th, starting at the first replay the present gate ran on a guest flip (`PG_TICK_FLIP`). That replay is the renderer handoff, whatever its time or frame number.
  - With `RSXI_PRESENTED=1`, only replays that call Present count.
- **Metadata per frame:**
  - the header gains `take` (pre/main), `flip_replay`, `guest_flip` and `display_buf`;
  - a `present` event gives `attempted`, `hresult`, `success` and `fence`;
  - the manifest's frame list adds `take`, `presented` and `present_hresult`.
- **Atomic finalization:**
  - events are written to `events.jsonl.part`, flushed after the header;
  - the rename to `events.jsonl` happens only in `rsxi_frame_close`, after the frame's Present returned;
  - `manifest.json` was already written via a temporary file and a rename.
- **Cancellation:** a frame cut short stays `.part`. `rsx_inspect.py` reports it as cancelled, `complete: false`, and the status as `inconsistent` if the manifest claimed complete.
- **Readback:** unchanged. Snapshots are copied inside the frame's command list, and the writer waits on the GPU fence once (`wait_for_gpu`) before mapping. The game stalls only on captured frames, about 40–60 ms each with `passes` snapshots in the 2026-10-22 capture.
- **Images:** BMPs are the raw render-target bytes (R8G8B8A8 → 24-bit). No brightness, gamma or tone correction is applied. A diagnostic view, if needed, must be a separate file.

## Plan for the next run (`NEXT_PRESENTATION_VALIDATION.md`)

| Capture | Trigger | Purpose |
|---|---|---|
| 1 "pre" frame | `rsxi.trigger` written 6 s after `garage_archive_read` (≈ 41 s, loading screen still up) | the loading-screen frame for comparison |
| 6 "main" frames, stride 30 | the first gate flip replay after that (the handoff, ≈ 47 s), presented or not (`RSXI_PRESENTED=0`) | the next renderer's passes and the backbuffer; each frame records whether Present was attempted and succeeded |

**Why `RSXI_PRESENTED=0`:** the garage frames may never call Present (`RSX_PRESENTATION_VALIDATION.md`). Capturing only presented frames could then capture nothing. With 0, the frames show what the garage renderer produced, and the `present` event says whether it reached the swapchain.

**Stop:** the target `garage_capture_complete` (the last main frame finalized). The runner stops at the target only once the RSXI manifest says `complete`.

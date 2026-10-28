# Garage render pipeline: render targets, the display buffer, texture formats (offline, 2026-10-23)

MotorStorm was not launched for this analysis. It continues `GARAGE_RENDERING_PIPELINE.md` (the loading side).

**Evidence:**
- the RSXI capture of run `20261022-064218-fast-garage-capture2` (exe `7770ec7a…`, an older build): frames 4608, 4668 and 4728 are complete; 4788 was cut short;
- run `20261023-180259-present-gate` (exe `a757cb88…`): the first garage replays, with no capture.

Labels: **VERIFIED** (in a capture or log), **INFERRED**, **HYPOTHESIS**.

## Display buffers (VERIFIED, both runs)

`SetDisplayBuffer(id=0, offset=0x10000)` and `(id=1, offset=0x394000)`, both 1280×720, pitch 5120. The backend treats a draw as "display" only when its colour surface is one of these offsets (`current_rt_off` → `cellGcmOffsetIsDisplay`).

## One garage frame (VERIFIED, frame 4608; 4668 and 4728 identical in structure)

554 records: 543 draws and 11 clears. The frame header says `"present":0`: the replay ran, but the backend did **not** call Present.

| Ops | Colour target (raw offset) | Size | Draws | Reading |
|---|---|---|---|---|
| 0–200 | `0x06FF0000` | 1024×2048 | 198, all `fp 0x047A6B41` (1 instruction) | shadow-map pass (INFERRED: one-instruction fragment program, large target; the same address is later sampled as format `0xB0`, DEPTH24_D8) |
| 201 | `0x00ED0000` | 1280×720 | clear | |
| 202–513 | `0x00750000` + MRT `0x01650000` | 1280×720 | 311 | main scene into two targets (G-buffer-like); 7 cube-map programs belong here (INFERRED from the 2026-10-23 run) |
| 514–519 | `0x077F0000`, `0x079D0000`, `0x0243AB00` | 640×360 | few | half-resolution passes |
| 520–528 | `0x00750000`, then a chain 320×180 → 160×90 → 80×45 → 40×22, then `0x022C0500`, `0x022C1600` | | few | down-sample / luminance chain and two full-size composites (INFERRED) |
| 529–552 | `0x01650000` | 1280×720 | 23 | final full-size passes (snapshot non-zero 0.75) |
| 553 | `0x06A57000` | 320×180 | 1 | |

- **No draw targets `0x10000` or `0x394000`.** The end-of-frame backbuffer snapshot is all zero (VERIFIED).
- **Offscreen vs final:** every pass above is offscreen. The cube-map draws are part of the scene pass into `0x00750000`/`0x01650000`, not a presented frame.
- **Screen copy (VERIFIED):**
  - `fp 0x047A6B41` samples a 1280×720 A8R8G8B8 linear texture (`0xA5`) at `0x01DD0000`;
  - no render target exists there, so the backend binds its screen-copy fallback (`[SCREENTEX] bound frame copy`, `screen_copy_fallback`): the previous presented frame;
  - in frame 4608 there are 200 such units, in 4728 none (the capture does not show why).
  - Whether `0x01DD0000` holds guest-written data (CPU or SPU) is UNKNOWN; `EMPTYTEX=1` in the next run reports it if the guest memory is empty.
- **How the image reaches the display buffer: UNKNOWN.**
  - **HYPOTHESIS:** an RSX 2D-engine transfer (NV3089 scaled image) from the final surface into the display buffer, or a draw this capture's 554 records did not hold.
  - With the D3D12 backend an NV3089 blit is a CPU copy in guest memory. The surfaces were rendered on the GPU, so it copies zeros, and it never reaches the swapchain. The GPU composite hook (`rsx_d3d12_composite_from_offscreen`) has no remaining caller.
  - No `[NV3089] SKIPPED` or `[GCM2D-UNH]` line appeared, so any blit used a 32-bit format, which is copied silently.
  - The next run traces blits after the trigger (`NV3089_GATE`, at most 400 lines).
- **Resource states:** not checked by this analysis. No D3D12 error was logged, but the debug message queue was off (`D3D12_IQ=1` would show transition errors). The backend has one swapchain and does not mirror guest display memory, so a guest display-buffer change involves no host synchronization.

**Consequence (HYPOTHESIS, to confirm with `[present_diag]`):** with the corrected gate, every garage flip replays the batch, so the offscreen targets are rendered. But `has_display = 0`, so no Present follows: the window keeps its last presented image (the brightened loading screen), or turns black on a resize or occlusion. This would explain the "white, then black" report without any GPU failure.

## Texture formats `0xB0` and `0xB4` (offline)

The RSX format byte is the base format OR `0x20` (`CELL_GCM_TEXTURE_LN`, linear rather than swizzled) OR `0x40` (`CELL_GCM_TEXTURE_UN`, unnormalized coordinates).

| Value | Decoded | Guest resource (VERIFIED) | Backend | Needed by the garage |
|---|---|---|---|---|
| `0xB0` | `0x90` DEPTH24_D8, linear | unit 13, `0x06FF0000`, 1024×2048: the target of the 198-draw shadow pass | refused: "the unit keeps its previous bind". The backend renders that pass into a colour RT and keeps no depth resource for the address | probably (shadowing) |
| `0xB4` | `0x94` X16, linear | unit 11, `0x0077B080`, 256×1: a one-row lookup table | refused, same message | UNKNOWN (a 256-entry LUT, e.g. a tone or fade curve) |

**Not implemented:**
- **`0xB0`:** sampling a depth surface needs the pass's depth buffer as a shader resource, plus the RSX depth-texture read rules (compare or raw depth). It is not a format conversion.
- **`0xB4`:** the header calls X16 "float16 single channel". The libgcm name suggests a 16-bit unsigned value. The channel replication when sampled is not established here.

Both warnings stay. A unit that keeps its previous bind samples the wrong texture, and that renders plausibly wrong, not blank. These two formats do not explain a frame that is never presented.

## Fade constant `c[59].w` (`LOADING_SCREEN_FADE_TRACE.md`)

The value runs past 0 on the loading screen. The guest resets it at each transition (0.985 → … → explicit 0). It belongs to the loading-screen renderer, which has exited by the time the garage renders. It is not a cause of missing garage presents. Nothing was changed.

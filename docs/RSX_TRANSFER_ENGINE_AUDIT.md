# RSX transfer-engine audit (offline, 2026-10-23)

Covers ps3recomp-int `cellGcmSys.c` (FIFO walker: `gcm_2d_method`, `nv3089_blit`) as of the `9bad862` successor commit. MotorStorm was not launched.

## Subchannel layout

**The game's layout (VERIFIED from its own statically linked libgcm builders in `generated/ppu/ppu_recomp_003.cpp`):**

| Builder | FIFO headers | Subchannel → class |
|---|---|---|
| `func_00732DD8` | `0x6184`, `0x630C` | 3 → NV3062 (surface 2D) |
| `func_00732E9C` (called from `0x0072D560`) | `0xA304`, `0xA400` | 5 → NV308A (image from CPU, inline) |
| `func_007330A4` | `0x2184`, `0x230C`, `0x2310` | 1 → NV0039 (memory to memory) |
| `func_00733468` | `0x6184`/`0x6300`/`0x630C` + `0xC184`/`0xC198`/`0xC2FC`/`0xC400` + SET_OBJECT handle `0x313371C3` | 3 → NV3062, 6 → NV3089 (scaled image) |

**Callers:**
- `func_007330A4` (NV0039) and `func_00733468` (NV3089) have **no direct call site** in the lifted code and **no function descriptor** in `EBOOT.elf`; no big-endian occurrence of either address.
- The inline-transfer builder is called.
- Commands built inline elsewhere, or by SPU code, were not searched; the SPU lifted output is not readable from this account.

**Backend routing:**

| Subchannel | Backend | Matches the game? |
|---|---|---|
| 0 | NV4097 (3D) | yes |
| 1 | **NV4097** by default (`GCM_SUBCH1_2D=1` routes it to the 2D path). Added because other titles bind 3D there | **no**: libgcm binds NV0039 there. An NV0039 copy would execute as NV4097 state (`0x030C..0x0328` is blend, colour-mask and stencil state), and the copy would not happen. Latent: MotorStorm's NV0039 builder has no caller |
| 2, 3 | NV3062: `0x0184/0x0188` DMA, `0x0300` format, `0x0304` pitch, `0x030C` offset | yes (3) |
| 4, 5 | NV308A, or NV309E when `0x0300` (SET_FORMAT) was seen on that subchannel | yes (5 = NV308A; 4 = NV309E) |
| 6, 7 | NV3089: `0x0184` src DMA, `0x0198` surface, `0x0300` format, `0x0304` operation, `0x0308/0x030C` clip, `0x0310/0x0314` out point/size, `0x0318/0x031C` du/dx dv/dy, `0x0400` in size, `0x0404` pitch/origin, `0x0408` in offset, `0x040C` in point (trigger) | yes (6) |
| 7 (`0xE9xx`, `0xEBxx`) | driver flip and user command, handled before the 2D path | yes |

`SET_OBJECT` binds are not tracked, so the routing is fixed by subchannel. `GCM_OBJDBG=1` logs each subchannel's handle. It is in the prepared run.

## Per engine

| Engine | Implementation | Status |
|---|---|---|
| **NV3089** scaled image | point-sampled CPU copy in guest memory; 32-bit formats only (`3`, `7`, `8`, `0xD`); clip honoured; NV309E swizzled destination for format 3 | **Guest memory only.** With the D3D12 backend, the source is not read back from GPU render targets and the destination is not pushed to any D3D12 surface or the swapchain. `nv3089_engine_read`/`_wrote` serve only the platform-neutral draw engine, and `rsx_live_draw_*` only `RSX_LIVE_DRAW`. Method `0x02FC` (SET_COLOR_CONVERSION), which the game's builder emits, is ignored; it matters only for dithering or format conversion. No filtering (scaled blits are point-sampled). Other formats are skipped loudly (`[NV3089] SKIPPED`) |
| **NV0039** memory to memory | **not implemented** (subchannel 1 → 3D) | missing, see above |
| **NV3062** surface | state only (DMA, format, pitch, offset) | correct for what is stored. `0x0308` (source offset) is not stored; it is only used by NV3062-to-NV3062 copies, which are not implemented |
| **NV308A** image from CPU | `0x0304` point, `0x0308` size out, colour words `0x0400..0x07FC` written to guest memory (`vm_write32`) | correct for its use here (the game patches fragment-program constants in local memory, `[GCM2D] inline write dst=0xC074B2E0`; draws re-read FP constants from guest memory) |
| **NV309E** swizzled surface | `0x0300` format and `0x0304` offset; used as the NV3089 destination | format 3 only |

## Instrumentation defects (fixed)

| Defect | Effect | Fix |
|---|---|---|
| The `NV3089_GATE` trigger file was re-checked only every 64th blit, and `open_gate` was recomputed each time | after the file appeared, up to 63 blits went untraced, and with fewer than 64 blits after the trigger the trace never opened | `include/ps3emu/trace_gate.h`: polled by time (every ≤ 10 ms) and latched. Every blit after opening is traced until `NV3089_GATE_MAX`, and the gate prints when it opens and when its budget truncates the trace |
| A degenerate blit (zero size or pitch) returned before the trace | invisible | traced first, then discarded |
| Methods on other transfer subchannels (1, 3, 4, 5) had no gated trace (`GCM2D-UNH` covers only unrouted methods, first 8) | no record of which engines ran after a handoff | `PS3_XFER_TRACE=<file>` (`PS3_XFER_TRACE_MAX`, default 2000): every method on subchannels 1–6 after the trigger, with the route it takes (`3d` or `2d`) |

## Not changed

**Routing subchannel 1 to NV0039, implementing NV0039, or giving NV3089 GPU synchronization:**
- The game is not shown to use any of them. Its builders for NV0039 and NV3089 have no callers.
- Subchannel-1-as-3D is relied on by other titles.
- A correct fix needs `SET_OBJECT` tracking plus a GPU copy path, and the next run's `GCM_OBJDBG` and `PS3_XFER_TRACE` lines are the evidence that would justify it.

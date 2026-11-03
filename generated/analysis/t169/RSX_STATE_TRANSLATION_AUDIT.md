# T169: RSX state translation audit

For each confirmed defect: (1) guest request, (2) what the backend does, (3) why they differ. Questions 4–6 are in `RENDERING_PERFORMANCE_CORRELATION.md`. Capture: B3 f002192.

| State | (1) RSX asks | (2) Backend default | (3) Why | Fix available |
|---|---|---|---|---|
| Texture gamma | ADDRESS [23:20] | No decode | Guest-FP path compiled without transfers | `RSX_COLOR_XFER` bit 1 |
| sRGB output | PACKER = 1 | No encode | Same | `RSX_COLOR_XFER` bit 4 |
| Filter, wrap, LOD | Per unit | Root signature's static samplers (a debug-font workaround on unit 0) | Dynamic samplers were added opt-in | `RSX_GUEST_SAMPLERS` |
| Mips | 9–11 levels | Level 0 | Chain upload added opt-in | `RSX_TEX_MIPS` |
| Depth write, compare | Per draw | Writes on, LESS_EQUAL | Key held only the test enable | `RSX_DEPTH_STATE` |
| Stencil | 885 draws | None | Same | `RSX_DEPTH_STATE`/`RSX_STENCIL_EXACT` |
| Antialias 3 | 2 samples | 1 | Pool is single-sample | `RSX_MSAA` |
| MRT B..D blend/mask | Per target | Target A's | Opt-in | `RSX_MRT_STATE` |
| Texture window | 2556×718 within a 2560-wide surface | Whole target | Opt-in; 0.2 % coordinate offset | `RSX_RT_WINDOW` |
| Self-sampling | Target read while written | Same resource | Opt-in | `RSX_RT_FEEDBACK` |
| `0xBF` over A8R8G8B8 | Bytes read as two halves | Unorm R, G | SRV follows the surface format; no RGBA8↔R16G16F view exists | **None: needs a decompiler decode** |
| CONTROL0 enable clear | Disabled unit sampled (5 bindings) | Sampled normally | Not checked by the path | None; effect unknown |

**No defect found (VERIFIED by reading and tests):** sampler cache keys, sampler binding, per-unit gamma mask, FP16 and 32-bit export bypass.

**Render-target formats:** `rsx_surface_dxgi` maps FP16, FP32 and X32 correctly and everything else to RGBA8. Scene and MRT1 are `0x3148` A8R8G8B8, as RGBA8 with the guest word's bytes converted at copy points.

**Draw processing:** 928 host records from 630 distinct FIFO offsets, the largest packet giving 33 records. This repeats T168's point: one packet can expand to many records, so same-offset records aren't duplicates. The 15 decal draws are distinct boxes with distinct stencil refs. Multipass is legitimate here.

**Early depth:** D3D12 does early-Z automatically unless the shader writes depth or kills. With writes wrongly on, blended draws change later depth tests. No separate early-depth control was found or needed.

**Diagnostic added:** `RSX_VISUAL_DIAG=1`, one `[vis-draw]` line per draw (FIFO offset, target, zeta, FP, each unit's words) and one `[vis-work]` per guest frame. Combine with the existing `RSX_GPU_PROF`, whose counters already cover barriers, copies, PSO and resource creation, SRV creation, waits, CPU and GPU time per pass. I didn't duplicate them. PSO keys and resource IDs are in RSXI.

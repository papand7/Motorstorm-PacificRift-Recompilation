# T165: vehicle black surfaces, root cause

2026-10-30. **Status: PARTIAL. The cause is established for the tested frame, but not yet checked on the start-grid view of the screenshot, and no default has changed.**

## Result

**Colour transfers off (`RSX_COLOR_XFER` unset) are the main cause of the crushed-black vehicle surfaces (VERIFIED on one matched race frame).** The guest requests sRGB texture decode and sRGB output. The default D3D12 path applies neither, so lighting runs on gamma-encoded values.

| Evidence | Result | Label |
|---|---|---|
| Guest request, baseline frame f002192 (B3) | All 570 draws on the scene target `0x00750000` (format `0x3148`) have `srgb_output=1`, `host_xfer=none`. Every vertex-program group has texture gamma on (mask 7 = RGB, alpha excluded) on some unit | VERIFIED |
| Those draws include the vehicles | The player quad and rider are fully visible in the pass snapshot at op 547, and every earlier draw on that target has this state | VERIFIED |
| Same frame with `RSX_COLOR_XFER=7` (X1, `frame_001`, identical camera and pose) | Front tyre near-black 58.1 % to 24.9 %, left tyre 64.8 % to 31.0 %, sidewall and knobble detail returns. Whole-frame clipped white 6.5 % to 2.9 % | VERIFIED |
| Texture binding | `noslot=0`, `stale=0`, `evict_other=0` across B3 and X1; no null texture bound in draws before op 586 | VERIFIED |
| Sign expansion (bit 0x2) | 0 draws request it, so only bits 0x1 and 0x4 matter here | VERIFIED |

**Why it goes black:** RSX computes `encode(decode(t)·L)`, ours `t·L`. For dark albedo in shade, the missing encode is the larger effect, so values collapse toward 0. A near-black tyre has no room to recover on screen.

**Corrections to the earlier report:**
- "No capture contains a vehicle draw" was wrong as evidence. My parsers rejected any RSXI line with bare `-nan` (in VP c38) and dropped about 95 % of draws ("22 draws" was really 485 in one frame). Fixed. The T145 race frames were never checked for vehicles with the fixed parsers.
- "Shaded 2–4× too dark, lit up to 2× too bright" holds only in direction. Measured median X luma against B: 0–8 → 13, 16–32 → 27, 64–128 → 62, 192–250 → 210. Dark tones lift and clipping falls, but mid-tones fall too (cliff shade 108.6 → 70.7, helmet 106.1 → 61.7). The model is not quantitatively confirmed.

## What is not proven

| Item | Status |
|---|---|
| Grid view of the screenshot (several back-lit vehicles) under X | No X capture of it: X1's RSXI frame was cut by the 195 s cap with no snapshots. The matched frame is the player quad close up, also at the race start. HYPOTHESIS that the distant grid behaves the same |
| A single named defective draw | No per-draw image exists (RSXI snapshots are per pass, and the origin test gave one value for all draws because c0–c3 are view-projection). Attribution is the group above, not one op |
| Bodywork reported as black | In B3 the nearest quad's paint is **not** black. Black is confined to tyres, dark parts and, in the screenshot, small back-lit vehicles |
| Bits 0x1 and 0x4 separately in game | Not run: the launch allowance is used up. Separately verified on WARP only |
| Hardware reference | No PS3 image compared; correctness rests on the guest registers and the transfer definitions |

## Separate defects (not fixed)

| Defect | Evidence | Label |
|---|---|---|
| Blocky rectangular patches on the sand | Absent at op 547, present in the end-of-frame target and final image, in both arms. Candidate: ops 569–583, `fp 0x022C20C1`, 15 boxes of 18 vertices, cull front (3), depth func 4, blended | Timing VERIFIED; the draw is a HYPOTHESIS |
| Unit 0 filtering | Guest asks min 4, mag 2, wrap, mips on 552 bindings; the host uses `point_clamp`, while the same request on units 1–4 gets `linear_wrap`. The default host sampler ignores the guest here | VERIFIED mismatch; effect on ragged edges untested |
| Washed-out sand | Sand left 213.0 → 210.0 and sand right 193.0 → 191.7: X barely changes it, so sand brightness has another cause. T166's area | VERIFIED |
| Blue rectangle | Not seen in the captured frames | not established |

## For T166

Enabling transfers fixes dark crush and most clipping on rocks and foliage, but not the sand. Don't implement a competing transfer path: `RSX_COLOR_XFER` already exists.

## Commits

ps3recomp `b1eb158` (diagnostic only, unchanged). Root: this report on `agent/t165-vehicle-render-report`.

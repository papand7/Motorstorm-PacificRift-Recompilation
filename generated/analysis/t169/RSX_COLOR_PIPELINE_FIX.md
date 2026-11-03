# T169: RSX colour pipeline

**Update (runtime):** D1 and F1 ran with no correction active, because `RSX_VISUAL_PROFILE` never reaches the game's D3D12 path. See `GAME_VALIDATION_PLAN.md`. Runtime status here stays unverified.

**Implemented:** no new transfer code. `RSX_VISUAL_PROFILE` bit 0x01 turns on the existing per-draw `RSX_COLOR_XFER=7`. **Default unchanged.** Forcing it globally isn't needed: each draw's transfers come from its own registers.

| Bit | Does | Follows | Non-requesting state |
|---|---|---|---|
| `0x1` | sRGB decode after filtering, per unit and lane | ADDRESS gamma bits [23:20] (`rsx_texture_gamma_mask`) | Mask 0: linear texture stays linear |
| `0x2` | Sign expansion | ADDRESS bit 12 | 0 requests in B3 |
| `0x4` | sRGB encode of RGB, all MRT exports, in the shader | SHADER_PACKER, half exports, integer surface (`rsx_fp_srgb_output_enabled`) | FP16 surfaces and 32-bit exports bypass it |

**Offline-validated (WARP):**
- Alpha is excluded by the mask and the encode (T110 tests).
- FP16 bloom targets `0x14B` and 32-bit exports get no encode (`test_rsx_framebuffer_srgb`).
- `test_t169_visual_ab_warp`: with captured words and a stand-in light of 0.25, baseline mean 17.75 against 34.0 with both corrections and mips; the result equals `encode(decode(level 2) * 0.25)` within 1.5/255.

**Intermediate targets, from B3 (VERIFIED):** the guest's own reads show no double conversion by design:
- `0x00750000` is read raw at composite (ops 921, 932) and with gamma at unit 2 in the decal pass, as requested per bind.
- **MRT1 is read raw and squared.** `fp_0074B181` computes `mean(t1)^2 * 16`, an approximate decode. This is the strongest evidence that MRT1 is meant to be encoded, and it matches the rule that the packer covers every export.

**New defect found, by the same missing encode (VERIFIED arithmetic, B3 op 547 snapshot):**

| Input to bloom/exposure | Mean luminance | Geometric mean |
|---|---|---|
| Scene colour (`t1 × 16`) | 2.06 | 1.52 |
| Baseline `x²·16` | 0.32 | 0.18 |
| With sRGB output | 2.46 | 1.79 |

See `TERRAIN_OVEREXPOSURE.md` for what this does.

**Not established:**
- **Blending:** the encode is before the blend unit, matching T110's implementation and, from my memory of RPCS3, its shader-side approach. I didn't re-check RPCS3's source. HYPOTHESIS until a PS3 reference.
- Bits 0x1 and 0x4 apart in the game.
- Final presentation: `0x148` display target with `srgb_output=0` (ops 932–933) gets no conversion. The composite reads encoded scene data, so this is consistent, but unverified on hardware.

**Game-validated:** only T165's one matched frame.

# T169: visual defect matrix

2026-10-30. **No game launch.** Evidence: the existing T165 capture B3 frame f002192 (exe `performance_next/ab/exe_n`, sha256 `0304156b…49b3`, ps3recomp `a049b1e`, switches: texture residency only), T145, T133, T120, plus new offline tests. New code: ps3recomp `agent/t169-visual-fidelity-recovery`, based on `b1eb158`.

**T166 doesn't exist:** no branch, worktree, report or commit. Its supposed scope is covered here.

**Default renderer:** `RSX_COLOR_XFER`, `RSX_GUEST_SAMPLERS`, `RSX_TEX_MIPS`, `RSX_MSAA`, `RSX_DEPTH_STATE`, `RSX_STENCIL_EXACT`, `RSX_MRT_STATE`, `RSX_RT_WINDOW`, `RSX_RT_FEEDBACK`, `RSX_ZETA_EXACT` and `RSX_FP_PRECISION` are all off. Implementations existed already, mostly unproven in game. So the screenshot's renderer ignores most guest state.

The capture has 928 draw records, and I parsed 1,183 of 1,183 lines.

| Symptom | Guest asks (B3) | Host does by default | Label | Implementation | Missing validation | Regression risk |
|---|---|---|---|---|---|---|
| Dark tyres, dark parts | sRGB output on 570 scene draws, texture gamma | Neither | **Mismatch VERIFIED**; effect on one matched frame (T165) | `RSX_COLOR_XFER=7` | Bits apart, grid view, PS3 reference | Mid-tones fall |
| Overexposed terrain, too-bright frames | Bloom program reads MRT1 as `x*x*16`, so MRT1 must be gamma-encoded | MRT1 unencoded | **Input error VERIFIED (8.5× low)**; link to `c33` HYPOTHESIS | `RSX_COLOR_XFER=7` | `c33` in a controlled A/B | T165's X1 single `c33` sample doesn't confirm it |
| Grain | Mip filter on 1,949 of 2,463 sampled uploads, bias -0.797 | Level 0 only; unit 0 point/clamp | **Mismatch VERIFIED**; fixture effect VERIFIED; game untested | `RSX_TEX_MIPS=1` + `RSX_GUEST_SAMPLERS=15` | Game | +29.6 % texture bytes |
| Ragged edges | Antialias 3 (2 samples) on scene; AA enable set | 1 sample | **Mismatch VERIFIED** (T133, B3); game untested | `RSX_MSAA=1` | Game; hardware sample order | Touches RT pool, needs samplers |
| Blocky terrain patches, box faces | 15 decal boxes: compare GREATER, no writes, stencil | LESS_EQUAL, writes on, no stencil | **Mismatch VERIFIED**; inverted coverage VERIFIED on a fixture; **link to the patches is a strong HYPOTHESIS** | `RSX_DEPTH_STATE=1` | Game | 904 of 928 draws change state |
| Streaks inside the boxes | Decal maps 8×8/16×16 B8, clamp | Linear **wrap** | **Mismatch VERIFIED**; 252/255 error past the edge on a fixture; link HYPOTHESIS | `RSX_GUEST_SAMPLERS=15` | Game; unit 11 words (not captured) | Low |
| Object velocity lost | Full-screen velocity op 915 tests stencil `NOTEQUAL` | No stencil: wipes vehicle velocity written by ops 597–914 | **VERIFIED** from snap18 against snap19 | `RSX_DEPTH_STATE=1` | Game | **Exposes the next row** |
| Velocity texture misread | `0x01650000` (A8R8G8B8 surface) sampled as `0xBF`, Y16_X16_FLOAT | Reads R and G as unorm | **Mismatch VERIFIED, not fixed** | None | Needs a shader decode | Could smear vehicles once op 915 is fixed |
| Encoded depth filtered | Depth-as-colour with nearest filter on unit 4 | Linear wrap (2 sampled bindings) | **Mismatch VERIFIED** | `RSX_GUEST_SAMPLERS=15` | Game | Low |
| Blue rectangle | Unknown | Unknown | **Not reproduced** | None | See `BLUE_RECTANGLE_ANALYSIS.md` | None |

**Corrections to earlier work:**
- T165 said "552 bindings" for the unit 0 mismatch. That counted bound units. Units the shaders really sample: **501 point/clamp against a mip filter** in the 612 draws whose shaders are available.
- T165's B3-against-X1 table didn't control exposure, so its falling mid-tones may be partly `c33`. Its near-black change isn't explained away by that, but its size isn't settled.
- My `draws_t165.py` parser replaced `nan` inside JSON strings too. `tools/rsxi_parse_t169.py` doesn't, and counts rejected lines. Its test passes.

**Blind spot:** 316 draws (8 programs) have no shader dump in any capture I checked, so their sampled units are unknown. RSXI's unit mask `C03F` also omitted units 6–13.

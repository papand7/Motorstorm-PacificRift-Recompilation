# T169: terrain overexposure

**Update (runtime):** D1 and F1 ran with no correction active, because `RSX_VISUAL_PROFILE` never reaches the game's D3D12 path. See `GAME_VALIDATION_PLAN.md`. Runtime status here stays unverified.

**Status: PARTIAL.** A verified defect feeds the game's auto-exposure wrong data, and its direction fits the symptom. The final link has no controlled game measurement, and T165's single X1 sample doesn't confirm it. No exposure multiplier or tone mapper was added.

## The original pipeline (VERIFIED from B3 draws and shaders, T113)

| Stage | Ops | What |
|---|---|---|
| Scene | 0–547 | Every draw multiplies by VP `c33.x`; MRT0 colour, MRT1 `colour/16` |
| Bloom/luminance chain | 590–595 | `fp_0074B181`: `mean(MRT1)² × 16`, downsampled to 10×5 FP16 |
| Exposure target | 922 | 16×16 FP16 `0x07EBA600` with Rec.709 weights |
| CPU | `func_004C3778` (T75/T113) | Reads it; `c33 = 1 + S(K/gm − 1)`, IIR; next frame |
| Composite | 932 | Scene, velocity blur, `+ tex6` additive |

**So exposure and bloom exist in the original.** They aren't assumed, and no tone-map curve shows up in the composite's body as far as I read it.

## The defect

With sRGB output off, MRT1 holds linear `colour/16`, then the guest squares it. On B3's op 547 snapshot: scene geometric mean **1.52**, baseline input **0.18** (**8.5× too low**), corrected input 1.79.

`K/gm` rises when the measured luminance falls, so the game raises `c33`, and every scene draw is brighter. It happens before compositing, which fits T113's stage A.

## Evidence against a clean conclusion

| `c33.x` | Run | Note |
|---|---|---|
| 1.40, 2.48 | B3 (same run, 120 frames apart) | Baseline |
| 2.79 / 3.06 | B2 / B1 | Baseline |
| 1.45 | X1, `RSX_COLOR_XFER=7` | **One sample**, different moment |
| 1.04–1.15 | T113 arm B, settled | Baseline, older build, other scene |

Baseline values go as low as X1's. So this neither proves nor refutes the mechanism. T165's sand barely changed (213 → 210), but its `c33` at those frames is unknown, and that comparison is what the plan's arm must control.

**Also not ruled out:**
- `h2 × (16 − 16·t2.w)` scales the bloom input by unit 2's alpha.
- Sand albedo and sun `c40` (4.5, 4.24, 3.95) may legitimately clip. Bright sand may be correct; there's no PS3 reference.
- T113's transient: `c33` pinned at 35.3 when a sample reads zero.
- The blown-out flyover frame (T145 D1 `frame_002`) shows white sky and blue-tinted fronds. Blue-tinted because R and G clip first? Not checked.

## Evidence gap

One bounded run logging `c33` over time per arm. `GAME_VALIDATION_PLAN.md` arm C against arm A.

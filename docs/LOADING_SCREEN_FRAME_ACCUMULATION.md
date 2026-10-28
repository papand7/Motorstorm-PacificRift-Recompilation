# Garage loading screen: does it brighten by framebuffer accumulation? (offline, 2026-10-23)

**Answer: no (VERIFIED for the three captured frames).** The image is the same picture multiplied by one gain per frame. The gain:
- grows linearly with the frame count;
- is applied **before** the 8-bit store.

Blending onto retained back-buffer contents cannot produce this. Since textures, fragment constants and blend state do not change, the varying input must reach the fragment programs through the **vertex stage** (INFERRED). Its values were not recorded; the next capture records them.

Data:
- run `generated/runs/20261023-150148-garage-render/rsxi/` (frames 1361, 1371, 1381: 10 presented frames apart, about 0.3 s);
- tool `ps3recomp-int/tools/rsxi_frame_gain.py` (`c874771`).

## The three draws (identical in all three frames, VERIFIED)

Per draw, the program, the 16 recorded fragment constants, the blend key and the texture checksums are identical in all three frames. The number of non-zero vertex constants (22) is identical too; their values were not recorded.

| Op | Program | Geometry | Texture 0 | Role (INFERRED) |
|---|---|---|---|---|
| 0 | `fp 0x02537E81`, VP hash `0xFF398E97` | 6 indices (2 triangles), viewport 1280×720 | `0x05188580` 1280×720 A8R8G8B8 (also on unit 1), checksum `0xDC970AC1` | the full-screen artwork |
| 1 | `fp 0x02538941`, VP hash `0xF69565E0` | 6 indices, full screen | `0x05088580` 1024×1024 A8R8G8B8, `0xB96B9AAE` | a tiled overlay (the shader samples it at `floor`/`frac`-wrapped 8×8 cells) |
| 2 | `fp 0x02537E81`, VP hash `0xFF398E97` | 256 indices | `0x04E88580` 2048×1024 B8, `0x1F116DC5` | single-channel atlas (text or emblem) |

All three:
- write the display buffer (`rt=0`), with no colour clear recorded in the frame;
- have depth test and write off;
- use blend `0x0122418B`, i.e. straight alpha (`RSX_BLEND_STATE_INVESTIGATION.md`);
- write all channels (`cmask=15`).

**What the fragment programs compute** (from the captured HLSL, `rsxi/shaders/`):
- `0x02537E81`:
  - `rgb = lerp(tex0.rgb · col0.rgb, tc1.rgb, tc1.w)`, `a = tex0.a · col0.a`, with a threshold on `tex1.x` around 0.9;
  - `col0` is saturated (≤ 1). `tc1` (TEXCOORD1) is not clamped.
- `0x02538941`: `rgb = lerp(tex0.rgb, tc1.rgb, tc1.w)`, `a = tex0.a`.
- Both blend the texture toward a vertex-supplied colour `tc1.rgb` by a vertex-supplied weight `tc1.w`, which is a fade.

## Measurements (`rsxi_frame_gain.py`, every 7th pixel)

| Frame | Mean R/G/B | White (all ≥ 250) |
|---|---|---|
| 1361 | 150.59 / 123.03 / 61.87 | 4.7 % |
| 1371 | 156.16 / 128.34 / 66.91 | 6.0 % |
| 1381 | 160.67 / 132.73 / 71.45 | 6.9 % |

The white shares differ slightly from the earlier run report (3.9 / 4.8 / 5.7 %), which used a 640×360 downscale.

| Test | Result |
|---|---|
| Per-channel ratio 1361→1371, unclipped samples ≥ 40 | p10/p50/p90 = 1.0972 / **1.1040** / 1.1088, equal for R, G and B |
| Same, 1361→1381 | 1.2018 / **1.2083** / 1.2154 |
| Same ratio on channels of pixels whose *other* channel is already 255 | 1.1038 and 1.2083 |
| Per-pixel step ratio d2/d1 | p50 **1.0** (p10 0.75, p90 1.14) |
| Prediction `min(255, g · frame1361)` against measured, 1371 | 156.14 / 128.33 / 66.89 vs 156.16 / 128.34 / 66.91 |
| Same, 1381 | 160.95 / 132.96 / 71.71 vs 160.67 / 132.73 / 71.45 |

**Representative pixels** (R, G, B):

| Pixel (y, x) | 1361 | 1371 | 1381 |
|---|---|---|---|
| (100, 100) | (255, 255, 72) | (255, 255, 79) | (255, 255, 87) |
| (600, 200) | (255, 255, 97) | (255, 255, 107) | (255, 255, 117) |
| (200, 1100) | (148, 76, 35) | (163, 84, 39) | (179, 92, 42) |
| (700, 640) | (12, 1, 0) | (13, 2, 0) | (14, 2, 0) |

The gain rises by about 0.104 per 10 frames: ×1.104, then ×1.208. That is linear in frames, not converging.

## Which scenario fits

| Scenario | Prediction | Fits? |
|---|---|---|
| 1. Correct PS3 blending of these draws | straight alpha over the previous contents; any change comes from the inputs | consistent only if an input changes; textures and fragment constants do not, so the vertex stage would |
| 2. Current D3D12 blending | the same state (12 harness checks) | no translation difference found |
| 3. Wrong framebuffer persistence (accumulation) | `dst' = a·S + (1−a)·dst`. Steps shrink geometrically (d2/d1 = (1−a)ⁿ < 1), every channel converges to its own S ≤ 255, and a channel cannot keep growing after another channel of the same pixel reached 255 unless it is still below S at the same rate | **refuted**: d2/d1 ≈ 1, the gain is uniform, and channels next to saturated ones grow by the same ratio |
| 4. Wrong alpha handling | changes how much of `src` mixes, but cannot raise any value above the larger of src and dst | refuted for the same reason |
| 5. Wrong render-target initialisation | affects the first frame only, or areas no draw covers | no: the gain is uniform over the drawn picture |

**The remaining explanation (INFERRED):** a pre-store multiplier greater than 1 that grows each frame. The fragment programs can only produce one through `tc1`. For example, `rgb = (1−w)·X + w·T` with `T ≈ 0` and `w < 0` gives a gain of `1 − w`. That is a fade weight past its end value. Whether the guest intends this, or a translation error makes it so, is UNKNOWN:
- possible translation errors: a vertex-program clamp, the D3D12 branch-base bug fixed in `c874771`, or a wrong constant;
- or the guest's own fade timer simply running on.

**The black frames of 2026-10-21** (exactly zero) are not explained by this capture.

## Needed from the next capture (`NEXT_RENDER_DIAGNOSTIC_RUN.md`)

- `guest.vp_consts` (`RSXI_VP_CONSTS=64`) on these three ops in successive frames. If one constant ramps, the guest drives it.
- `shaders/vp_FF398E97.hlsl` and `vp_F69565E0.hlsl` (new `vshader` events): how `o[8]` (TEXCOORD1) is computed, and whether the program branches.
- `BLENDDBG=1`: the raw blend words.

Still missing after that: the vertex attribute data. Only constants and programs are captured, so a ramp carried in per-vertex data would show as "constants unchanged".

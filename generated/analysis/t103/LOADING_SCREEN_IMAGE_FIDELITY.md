# T103: loading-screen brightness, colour accuracy and sharpness (2026-10-27, offline, no launch)

Worktree `ps3recomp-t103`, branch `agent/t103-loading-image-fidelity`, based on `95a906d` (the T96I/T100 base).
Inputs: RSXI capture `generated/runs/20261023-172442-present-stall/rsxi/f001340…f001360` (garage loading screen), T65 `LOADING_SCREEN_WHITEOUT.md`, `whiteout/FINDINGS.md`, T63/T96I/T98 dumps, built `build/motorstorm-t96i/MotorStormPacificRiftRecomp.exe`.

## Results

- **No renderer brightness defect. VERIFIED.** The loading screen brightens because of the guest's own unclamped fade, `gain = 0.5·t`, which runs for as long as the load lasts (T65, exact to 0.1 %). The format, gamma, blend and swap-chain path below is faithful.
- **The loading artwork reaches the backbuffer at exactly 1:1. VERIFIED.** There is no scaling, no texel offset and no filter blur inside the renderer.
- **Two sharpness-related defects were found outside the artwork path**:
  - DPI-unaware window. Fixed.
  - Guest sampler state is ignored. A diagnostic was added; no fix yet.
- **A third cause of softness is the review images themselves.** Some are downscaled.

## 1. Loading-screen path (VERIFIED: RSXI f1340 and source)

| Stage | Original (RSX) | Host (D3D12) |
|---|---|---|
| Producer | `AsyncRenderThread` loop `0x329048`, every 30 ms (T65 §1) | same guest code (AOT) |
| Type | 3 textured quads straight to the display buffer. No offscreen RT, video or post-FX | `guest_fp` PSO, DrawInstanced, target = swap-chain backbuffer |
| Op 0 artwork | unit 0, `0x05188580` 1280×720, fmt `0xA8` (A8R8G8B8, linear, pitch 5120, 1 mip), remap `0xAAE4` | upload slot, R8G8B8A8, csum `0xDC970AC1` |
| Op 1 emblem | unit 0, 1024² fmt `0x88` (swizzled A8R8G8B8) | upload |
| Op 2 text | unit 0, 2048×1024 fmt `0xA1` (B8 glyph atlas), remap `0x56FF` | upload |
| VP | `FF398E97`/`F69565E0`: pos = `v0.xy` (clip space), `zw = c467`, tc0 = `v8`, tc1 = `c59` | same; posscale/offset x/y identity |
| FP | `02537E81`/`02538941`: `rgb = X + tc1.w·(0 − X)`, FP16, no saturate | same HLSL |
| Blend | `0x0122418B` straight alpha | same |
| RT | rt 0, fmt 328 (A8R8G8B8), 1280×720 | `DXGI_FORMAT_R8G8B8A8_UNORM` (not `_SRGB`) |
| Gamma | no SET_SHADER_PACKER sRGB output and no ADDRESS gamma bits, so no conversion | `rsx_fp_srgb_output_enabled`/`rsx_texture_gamma_mask` are applied only when the guest asks |
| Present | 720p display buffer | swap chain 1280×720 R8G8B8A8_UNORM, FLIP_DISCARD, SDR, no colour-space call |

## 2. Brightness

- **VERIFIED: no defect.** Each item below was checked:
  - **Colour space:** no sRGB view or format anywhere on the path, and no HDR swap chain. The sRGB packer and texture gamma are applied only on guest request.
  - **Channel order:** ARGB→RGBA is correct; the artwork is orange (mean RGB 154/126/65).
  - **Blend:** straight alpha.
  - **Gain law:** fully explained by `c59.w`. The predicted f1350/f1340 gain ratio (1.0971) matches the measured one (1.0972), with no accumulation (T65).
- **Measurements (`tools/bb_stats.py`):**

  | Frame | Mean RGB | Luma p50 | Clipped (any channel = 255) | Guest gain `1 − c59.w` |
  |---|---|---|---|---|
  | f1340 | 154.0/126.4/65.0 | 122 | 38.8 % | 1.561 |
  | f1360 | 163.2/135.2/74.2 | 144 | 44.7 % | 1.865 |

- **HYPOTHESIS:** the visible cause is load duration. The PS3 would show gain ≈ 1 if its load finished within about 2 s of the fade completing. That is the domain of T64 (load speed), not this task.
- **No correction made.** A clamp, gamma change or multiplier would alter original semantics, and AGENTS.md and the brief forbid it.

## 3. Sharpness

### 3a. The renderer does not soften the artwork (VERIFIED, `tools/runlen2.py`, `tools/run2_map.py`)

- **Test:** exact runs of 2 equal pixels in unclipped pixels of f1340, grouped by screen phase modulo 4.
- **Columns:** shares 0.386 / 0.201 / 0.386 / **0.027**.
- **Rows:** shares 0.384 / 0.199 / 0.390 / **0.027**.
- **Spatial spread:** uniform over the whole artwork (`run2_map.py` grid).
- **Interpretation:** this is the signature of a 4×4 block-compressed origin. Equal pairs almost never cross an `x % 4 = 3` or `y % 4 = 3` block boundary.
- **What it proves:**
  - The source's block grid lands on the screen grid with zero offset and no resampling.
  - Any linear filtering at a sub-texel offset would have destroyed these exact equalities.
  - A point-sampled magnification would show its own period instead.
- **Conclusion:** the softness and blockiness present in the backbuffer are in the original texture data.

### 3b. Display stretch of a DPI-unaware process (defect VERIFIED, fixed. Relevance on this PC: PARTIAL)

- **Defect:** the exe has an embedded manifest without `dpiAware`, and no source calls a DPI API.
  - On a scaled display, Windows renders the 1280×720 client at 96 DPI.
  - DWM then stretches it bilinearly, so the screen is soft while dumps stay sharp.
  - `test_win_dpi` confirms the process starts unaware (`before=0`).
- **Fix:** `c2e9eec`. `win_dpi.h` provides `ps3_win_declare_dpi_aware()`, which sets per-monitor v2 awareness with a system-aware fallback. It is called in `create_window` before `AdjustWindowRect`.
  - Log line: `[D3D12] DPI awareness: …`.
  - Opt-out: `PS3_DPI_UNAWARE=1`.
  - Effect: the window becomes physically smaller on scaled displays, at 1 swap-chain pixel per screen pixel.
- **This PC:** the monitor reports **96 DPI (100 %)** (`tools/dpi_probe.c`). The registry `AppliedDPI = 144` is stale. So this defect does **not** explain softness on the current display; it does on any display scaled above 100 %.
- **Also soft, not a defect:** resizing or maximising the window. FLIP_DISCARD with the default `DXGI_SCALING_STRETCH` and no `ResizeBuffers` stretches 1280×720 bilinearly to the window. A 720p game shown at 1080p must be scaled somewhere; the PS3/TV scaler does the same.

### 3c. Guest sampler state ignored (defect VERIFIED, effect on loading screen not visible; diagnostic added)

- **Defect:** the guest-FP root signature (`rsx_d3d12_backend.c` ≈1300) uses 16 *static* samplers:
  - unit 0 is POINT/CLAMP (a dbgfont workaround);
  - units 1–15 are LINEAR/WRAP.
- **What is ignored:** NV4097 `SET_TEXTURE_FILTER`, `ADDRESS` and `CONTROL0` (min/mag/mip filter, LOD bias, anisotropy, wrap modes). All three loading draws sample unit 0, so they are point-sampled whatever the guest asked for.
- **Effect at 1:1 (3a): none.** Point and linear sampling are identical at texel centres.
- **Where it can matter:** scaled sprites and text (emblem, glyph atlas: aliasing rather than blur), and in-game mips and anisotropy (race scenes).
- **Diagnostic:** `26f262e`. RSXI draw records now include `filter`, `address`, `control0` and `host_sampler` per unit. Nothing is written unless RSXI is active.
- **Proper fix (not done):** a dynamic sampler table, which means a root-signature change in the shared VP path. It overlaps T102 (descriptor/perf) and T100. Do it only after the new RSXI fields show which guest states disagree.

### 3d. Review images (VERIFIED)

- T96I `frame_034_small.png` and T98 `frames/png/*.png` are **640×360**, half the 1280×720 backbuffer. Judging sharpness from them shows a 2× downscale.
- Use the `.bmp` dumps (1280×720) instead.

## 4. Changes, tests and builds

| Commit | Files |
|---|---|
| `c2e9eec` DPI awareness | `libs/video/win_dpi.h` (new), `libs/video/tests/test_win_dpi.c` (new), `rsx_d3d12_backend.c` (+7) |
| `26f262e` RSXI sampler words | `rsx_d3d12_backend.c` (+18 −3) |

- `tools/run_t103_tests.cmd`: `test_win_dpi` reports `before=0 mode=2 after=2`, **0 failures** (`logs/test_win_dpi.txt`).
- `tools/tu_t103.cmd` (exact flags from T96's `tu_t96.cmd`): `rsx_d3d12_backend.c` rc=0 and `cellGcmSys.c` rc=0 (`logs/tu/`). No new warning classes; the getenv/C99 warnings match the existing code.
- `tools/test_d3d12_rsxi_hooks.py`: passed. `tools/test_rsxi_geom.py`: 0 failures (the occlusion part is skipped without vcvars).
- `audit_public.py --staged`: no T103 file flagged. The 25 BLOCK items are files already in the tree.

## 5. Remaining uncertainties

- **HYPOTHESIS:** what the original artwork looks like at gain 1. The source PSARC asset was not extracted. The 1:1 proof (3a) does not need it, but a colour comparison does.
- **UNKNOWN:** the guest's actual filter words for the loading units. These come from the new RSXI fields at runtime.
- **PARTIAL:** whether the user's display or window was scaled when the softness was seen.

## 6. Integration order

1. **T100 first.** It covers race display and composition and is not touched here. The DPI change touches only `create_window`, and the RSXI change only the record and JSON.
   - T100 (`agent/t100-black-race-display` `729caed`, base `95a906d`) confirmed it touches only: the include list, OffRT `gf_used`, `off_rt_find`, the per-replay `used` reset, and the CELLMARK_DUMP checks.
   - It does not touch `create_window`, RSXI texture records, `vp_root_sig` or the samplers, so no overlap.
   - The `#include` lists may need a trivial merge.
2. **T102 next**, then T103. T102 (`agent/t102-renderer-performance` `1e5d534`, on T99 `db2aa90`, tree = `95a906d`) confirmed it only touches:
   - the VP strip/fan/indexed expanders;
   - the index base helpers;
   - the `vp_get_fp_pso` eviction and its prepass reuse;
   - the RSX_FRAME_PERF wrappers.

   It does not touch `vp_root_sig`, the samplers, `create_window` or RSXI texture records, so no textual conflict is expected. T102 also says its prepass PSO reuse stays valid if a later sampler fix changes the PSO key.
3. **The dynamic-sampler fix (3c) is a separate future task.** It changes `vp_root_sig`, which T102 may also change, so coordinate with T102 before starting it.

## 7. Runtime validation (when authorised)

1. Build `agent/t103-loading-image-fidelity` on top of T100/T102. Keep the T94-style runner and its loading-screen RSXI arming (`--capture-rsx`, draw-gated, about 3 frames during the loading window).
2. Check the stdout line `[D3D12] DPI awareness: per-monitor v2`.
   - On a display scaled above 100 %: the window client is 1280×720 *physical* pixels.
   - A screen grab of the client should equal the `.bmp` dump pixel for pixel (`bb_stats.py` on both).
3. In RSXI `events.jsonl`, read the loading draws' `tex[].filter/address/control0` against `host_sampler`. Decode the min/mag filter as `(filter >> 16) & 7` and `(filter >> 24) & 7`.
   - Record every unit where the guest asks for linear but the host uses `point_clamp`, or the guest asks for clamp but the host uses `linear_wrap`.
4. Run `runlen2.py` (with and without `--rows`) on the dump. Expect phase-3 share < 0.05 again.
5. For brightness, compare `1 − c59.w` against the backbuffer gain. No other change is expected; any difference is a new defect.

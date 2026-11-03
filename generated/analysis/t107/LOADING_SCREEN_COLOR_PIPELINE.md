# T107: loading-screen brightness and colour-pipeline correctness (2026-10-27, offline, no launch)

Worktree `ps3recomp-t107`, branch `agent/t107-color-pipeline`, from T103's tip `26f262e`. New commit **`ec5cdb3`**. Not merged or pushed.
Inputs:
- RSXI garage loading capture `generated/runs/20261023-172442-present-stall/rsxi/` (f1340/f1350/f1360);
- T65 `LOADING_SCREEN_WHITEOUT.md`, T103 `LOADING_SCREEN_IMAGE_FIDELITY.md`, T100 `BLACK_RACE_DISPLAY_ROOT_CAUSE.md`;
- decrypted `generated/decrypted/EBOOT.elf`.

## Results

1. **The host colour path is exact and linear. VERIFIED.** BC3 decode, then the guest's multiply, then 8-bit output to the backbuffer. No sRGB conversion anywhere, no double gamma, and the dump/screenshot path doesn't add one either (§3).
2. **The D3D12 guest-FP path ignores all three of the guest's colour transfers. Defect VERIFIED in code.** These are sRGB output (`SET_SHADER_PACKER` 0x1FEC), texture gamma (ADDRESS bits 23:20) and sign expansion (ADDRESS bit 12). The live draw engine applies them; D3D12 doesn't. `rsx_commands` even dropped 0x1FEC.
   - **MotorStorm does write the packer (VERIFIED):** six code sites write 1 or 0 (§4).
3. **Whether the loading draws request a transfer is still open. HYPOTHESIS.** The only capture predates the new fields, and static analysis can't settle it: the packer state is left over from whichever renderer ran last.
   - **If they request gamma + packer**, our output is too bright and clips twice as much. Texel 128 at gain 1.561 gives 200 here against 157 on hardware, and 92/256 texel values clip here against 46/256. That is exactly "bright and washed out" (§5).
   - **If they request nothing**, T65 stands: the brightening is the guest's unclamped fade multiplied by how long the load takes.
4. **No rendering correction was made.** Instead, a diagnostic was added and wired into RSXI, plus `RSX_XFER_LOG` (off by default). One bounded run decides which case applies (§8).
5. **Correction to T103 (VERIFIED):** format `0xA8` is **DXT45 (BC3), linear-flag variant**, not A8R8G8B8. `0x88` is DXT45 too. This is what explains T103's 4×4 block grid.

## 1. Loading-screen path (VERIFIED: RSXI f1340, source)

| Stage | Op 0 artwork | Op 1 emblem | Op 2 text |
|---|---|---|---|
| Guest texture | `0x05188580` 1280×720 **fmt 0xA8 = DXT45** (LN), pitch 5120 = 320 blocks × 16 B, 1 mip, remap `0xAAE4` (identity) | `0x05088580` 1024² **fmt 0x88 = DXT45** | `0x04E88580` 2048×1024 **fmt 0xA1 = B8** (LN), remap `0x56FF` |
| Host decode | block rows copied, no conversion (`rsx_texture_decode`) | same | byte copy |
| Host resource / SRV | `DXGI_FORMAT_BC3_UNORM`, 4-component mapping identity | `BC3_UNORM` | `R8_UNORM`; crossbar → A = texel, RGB = 1 (white glyphs) |
| Sampling | unit 0 static POINT/CLAMP (T103 §3c); 1:1 at texel centres | | |
| VP | pos = `v0.xy` clip space; tc1 = `c59` = (0,0,0, 1 − 0.5t) | | |
| FP `02537E81` / `02538941` | `h1 = tex·saturate(col0)`; `rgb = h1 + tc1.w·(0 − h1) = h1·(1 − w)`; FP16, no saturate | | |
| Render target | **none**: drawn straight into the display buffer (rt 0, surface `0x148` = A8R8G8B8 + Z24S8), half exports (`fp_exp32 = 0`) | | |
| Blend `0x0122418B` | RGB `SRC_ALPHA`/`INV_SRC_ALPHA` (straight alpha); A `INV_DEST_ALPHA`/`ONE`; ADD | | |
| Backbuffer | swap chain `R8G8B8A8_UNORM` (not `_SRGB`), FLIP_DISCARD, SDR, no `SetColorSpace1` (default G22/P709); cleared to the guest's clear colour 0 | | |
| Dump | `render_targets[fi]` bytes → BMP (BGR), before `Present` | | |

**Transfer function, end to end:** `out8 = round(255 · clamp(BC3(texel) · col0 · (1 − c59.w)))`, blended over black. sRGB conversion points on the host: **none**. On the guest: as requested by the packer and ADDRESS gamma, which are unknown for these draws.

## 2. Gamma, sRGB and swap chain audit

| Item | Result | Class |
|---|---|---|
| sRGB texture views / formats | none on the path (`BC3_UNORM`, `R8_UNORM`) | VERIFIED |
| sRGB render-target writes | backbuffer and offscreen RTs are `_UNORM`; no `_SRGB` RTV anywhere | VERIFIED |
| Shader-side gamma | the D3D12 guest-FP compile (`vp_get_fp_pso` → `rsx_fp_decompile_shadow_ex`) passes no gamma masks, and nothing calls `rsx_fp_apply_srgb_output` | VERIFIED (**defect**, §4) |
| Double conversion | impossible: zero conversions on the host | VERIFIED |
| Swap-chain colour space / HDR | SDR UNORM, no colour-space call; values are display-referred like PS3 scan-out | VERIFIED |
| Screenshot / dump gamma | none (the gain-ratio test, §3) | VERIFIED |
| `cellVideoOut` gamma | no gamma API is implemented, and the game imports none that is used here (colour space reported RGB) | PARTIAL (no import audit beyond this) |

## 3. Pixel evidence that the host path is linear (VERIFIED)

- **Test:** `tools/gain_ratio.py` takes the same static artwork in f1340 (guest gain 1.5611) and f1360 (gain 1.865) and computes the median `v1360/v1340` per input level (`logs/gain_ratio.txt`).

  | v1340 | 64–79 | 96–111 | 128–143 | 160–175 | 192–207 |
  |---|---|---|---|---|---|
  | measured | 1.1944 | 1.1942 | 1.1955 | 1.1941 | 1.1942 |
  | linear prediction | 1.1947 | 1.1947 | 1.1947 | 1.1947 | 1.1947 |
  | prediction if sRGB-decode → gain → sRGB-encode | 1.0919 | 1.0873 | 1.0849 | 1.0834 | 1.0823 |

  - The measured ratio is flat and equals g2/g1. Bins below 64 are biased by 8-bit quantisation.
  - Any gamma stage on the host, including in the dump, would show the third row.
- **Block structure:** `tools/bc3_linearity.py` (`logs/bc3_linearity.txt`). **99.8 %** of unclipped aligned 4×4 blocks have ≤ 4 distinct colours (86 % exactly 4).
  - This is a DXT5 palette passed through a per-pixel function with no filtering.
  - (The block-spacing sub-test can't separate linear from gamma at these contrasts; it is reported but not used.)
- **Caveat:** this proves what *our* pipeline does. What the PS3 does depends on the guest state in §4.

## 4. Proven defect: guest colour transfers ignored by the D3D12 guest-FP path

| Guest state | RSX meaning (framework rule) | Live draw engine | D3D12 before `ec5cdb3` | D3D12 after |
|---|---|---|---|---|
| `SET_SHADER_PACKER` 0x1FEC ≠ 0 | linear→sRGB on RGB of half exports to an integer surface (`rsx_fp_srgb_output_enabled`, RPCS3 `framebuffer_srgb`) | applied | **method dropped** | stored, recorded, reported; not applied |
| ADDRESS gamma [23:20] | sRGB→linear per post-remap lane (`rsx_texture_gamma_mask`) | applied | ignored | recorded, reported; not applied |
| ADDRESS bit 12 (`UNSIGNED_REMAP_BIASED`) | x·2−1 (`rsx_texture_expand_mask`) | applied | ignored | recorded, reported; not applied |

- **MotorStorm uses the packer (VERIFIED, `tools/scan_methods.py`, `t107_dis.py`; `logs/scan_methods.txt`, `logs/disasm_packer_sites.txt`).** The call is `bl 0x7573D8(ctx, 0x1FEC, v)` with:
  - `0x512898` (v=0) and `0x512B04` (v=1) in the state-reset function `0x512728`, chosen by the byte at `[obj+0xAC]`;
  - `0x5C5884`/`0x5C5AB0` (v=0) and `0x5C5A1C`/`0x5C5C58` (v=1) in `0x5C5798`, each paired with `0x0A74` (depth-test enable) set to the same value.
- **Loading loop `0x329048` (T65 disassembly):** it never writes 0x1FEC, so the loading draws inherit whatever packer value was last set. That makes it runtime state. **UNKNOWN offline.**
- **ADDRESS gamma for the loading textures: UNKNOWN.** The address word is built at runtime; the only capture predates T103's `address` field.

## 5. Regression fixtures (`libs/video/tests/test_color_xfer.c`, 26 checks, 0 failed)

- **Packer decode:** 0x1FEC reaches `rsx_state` through `rsx_process_method` and through a FIFO packet. Before the change it was dropped.
- **Loading state as captured:** half exports, surface `0x148`, units `0xA8`/`0x88` with `0xAAE4`, and `0xA1` with `0x56FF`.
  - With packer 0 and no gamma bits, **nothing is requested**, so the current path is exact (texel 128 × 1.5611 → 200 both ways).
- **The same draws with the guest asking:**

  | Texel 128, gain 1.5611 | Output |
  |---|---|
  | current D3D12 | **200** |
  | gamma + packer (expected on RSX) | **157** |
  | packer only | 229 (current too dark) |
  | gamma only | 86 (current too bright) |
  | texel values clipped: current vs gamma + packer | **92 vs 46 of 256** |
  | gain 1, gamma + packer | 128 (round trip) |

- **Exclusions verified:** 32-bit exports and FP16 surfaces bypass the packer; unbound units don't count; float formats ignore gamma bits.
- **Source pins (`tools/test_d3d12_color_xfer.py`, 13/13):** the packer is stored and copied per draw; RSXI carries the new fields; `RSX_XFER_LOG` is opt-in and read once; `rsxi_on_draw` reads no environment.
  - It also pins that the guest-FP path still applies no transfer, so `"host_xfer":"none"` stays truthful. Update this pin with the correction.

## 6. Change (`ec5cdb3`: +362 −3, 6 files; rendering unchanged)

- **`rsx_commands.[ch]`:** `NV4097_SET_SHADER_PACKER`, `rsx_state.shader_packer`.
- **`rsx_color_xfer.h` (new, header-only):** `rsx_color_xfer_eval()` evaluates sRGB output plus per-unit gamma and expand lanes with the engine's own functions.
- **`rsx_d3d12_backend.c`:**
  - `D3D12DrawRecord.g_shader_packer`, set in `rec_guest_extra`;
  - `dr_color_xfer()`;
  - RSXI draw events gain `shader_packer`, `srgb_output`, `host_xfer`, and per-unit `gamma_mask`/`expand_mask`;
  - `RSX_XFER_LOG=<n>`: off by default; at most n lines `[XFER] fp=… packer=… srgb_output=… ctrl=… surface=… color=… tN(fmt addr gamma expand) -- not applied`, distinct by program and request.
- **Cost when off:** one u32 copy per recorded draw plus one cached `getenv`.

## 7. Sharpness (kept separate from brightness)

| Cause | Finding | Class |
|---|---|---|
| Source mip / LOD bias | 1 mip on all three textures; bias irrelevant | VERIFIED |
| Scaling / display resolution | backbuffer 1280×720 = viewport = artwork; 1:1 (T103 §3a) | VERIFIED |
| Half-pixel offset | none: the zero-offset 4×4 grid shows no resampling | VERIFIED (T103) |
| Final blit sampler | none: the loading draws target the swap-chain buffer directly; no composite pass | VERIFIED |
| Format conversion | BC3 copied bit-exact, decoded by the GPU. NV vs D3D BC3 interpolation rounding is ≤ 1 LSB | VERIFIED / PARTIAL (rounding not measured) |
| Inherent | the artwork *is* DXT5. Its 4×4 block softness is in the original data | VERIFIED |
| Window/DPI, static samplers, 640×360 review PNGs | T103's findings, not repeated here | T103 |

## 8. Runtime validation plan (not run)

- **Build:** the T107 tip on top of T100 `729caed` (for `CELLMARK_DUMP_PRESENT_ONLY`). One bounded session, using the T94-style runner and the 20261023 loading-screen RSXI arming.
- **Environment:**
  - `RSXI=1 RSXI_COUNT=3 RSXI_STRIDE=10 RSXI_MINDRAWS=1 RSXI_SNAP=targets`;
  - `RSX_XFER_LOG=32`;
  - `CELLMARK_DUMP_PRESENT_ONLY=1`;
  - no `TEX_SAVE` (it is broad).
- **Captures, all at Present boundaries:** RSXI `end` snapshots are taken in presenting replays (`"present":1` in the frame event).
- **Per-stage checks:**
  1. **Original texture:** confirm the source with RSXI `csum` per unit (artwork `0xDC970AC1` in the old run). A colour reference needs the PSARC asset (BC3 → PNG) offline; not needed for the decision.
  2. **Host upload:** `tex[0].native.kind = upload_slot`, view `TEXTURE2D`, and the format from §1.
  3. **Pre-composition:** none exists; the loading draws write the display buffer (`rt = 0x00000000`).
  4. **Final backbuffer:** `snap00_end_…bmp`. Run `bc3_linearity.py`, and `gain_ratio.py` between two frames with their `1 − c59.w`.
- **Decision, read from the loading draws' `shader_packer` / `srgb_output` / `tex[0].gamma_mask` and the `[XFER]` lines:**
  - **All zero:** no colour defect on the loading screen. Close T107 on T65's conclusion (load duration, T64).
  - **Packer ≠ 0 and/or gamma ≠ 0:** the defect is proven on screen, and the correction below follows. Pass criterion after the fix: the per-level ratio between two frames follows the "gamma model" row of §3 and the fixture values of §5 (texel 128 @ 1.5611 → 157).
- **Also note any `[XFER]` lines from garage or race passes.** The same gap affects them.

## 9. Correction prepared, not applied

- **Change:** in `vp_get_fp_pso`, when `dr_color_xfer` reports a request:
  - compile with gamma and expand masks, through a non-buffered entry point equivalent to `rsx_fp_decompile_buffered_shadow_color_expand_ex`;
  - apply `rsx_fp_apply_srgb_output` before the alpha-test wrap;
  - add `srgb_output` plus a hash of the masks to the `VPFPEntry` key.
- **Why held back:**
  - The loading-screen relevance is unproven.
  - It changes every draw that asks, in garage and race, with no runtime check.
  - It touches `vp_get_fp_pso`, which T102 changed (eviction, prepass reuse).
- **HLSL compatibility needs checking:** the D3D12 FP text is post-processed (`_po.c0` / `PSOut` forms), and `rsx_fp_apply_srgb_output` expects a final `return …;\n}\n`.

## 10. Integration guidance for T105

- **Merge order:** T100 → T102 → T103 (`c2e9eec`, `26f262e`) → T107 (`ec5cdb3`).
- **Expected conflicts:**
  - The `#include` block of `rsx_d3d12_backend.c` (T100 and T103 also add lines there): trivial.
  - Otherwise T107 touches only:
    - `rec_guest_extra` (beside T103's lines);
    - `rsxi_on_draw` (beside T103's sampler fields);
    - the record struct;
    - one handler in `rsx_commands.c`.
  - None overlaps T102's expanders or PSO eviction, or T100's OffRT code.
- **Rendering is byte-identical with the diagnostics off.** No PSO key, HLSL or present gating changed.
- **Tests to rerun after the merge:** `python tools/test_d3d12_color_xfer.py`, `python tools/test_d3d12_rsxi_hooks.py`.

## Offline results

- **`test_color_xfer.c`:** 0 failures (`logs/test_color_xfer.txt`).
- **`test_d3d12_color_xfer.py`:** 13/13.
- **Existing renderer tests on `ps3recomp-t107`:**
  - `test_d3d12_rsxi_hooks`, `test_d3d12_texture_source_order`, `test_rsxi_frame_gain`: passed.
  - `blend_state`, `depth_state`, `shader_trace`, `zeta_pool`, `rsxi_geom`: 0 failures, but their C parts were skipped (no compiler on PATH) (`logs/py_suite.txt`).
- **`test_geom_expand.c`** (links the changed `rsx_commands.c`): 24 PASS, 0 FAIL.
- **TU compile** (`tools/tu_t107.cmd`, T103/T96 exact flags): `rsx_d3d12_backend.c`, `rsx_commands.c` and `cellGcmSys.c` all rc=0 (`logs/tu/`). No new warning categories against T103.
- **`audit_public.py --staged`:** no T107 file flagged. The 25 BLOCK items are files already in the tree (same as T103).

## Tools and logs (`generated/analysis/t107/`)

- **Tools:**
  - `tools/scan_methods.py`: EBOOT emitters of 0x1FEC and TEX ADDRESS.
  - `tools/t107_dis.py`, `tools/t107_xref.py`: capstone disassembly and xref.
  - `tools/gain_ratio.py`, `tools/bc3_linearity.py`, `tools/bc3_lib.py`: pixel tests.
  - `tools/make_tu_cmd.py` → `tools/tu_t107.cmd`.
- **Logs:**
  - `logs/scan_methods.txt`, `logs/disasm_packer_sites.txt`, `logs/disasm_512728.txt`, `logs/xref_packer.txt`;
  - `logs/gain_ratio.txt`, `logs/bc3_linearity.txt`;
  - test and TU logs.

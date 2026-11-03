# T133: grainy rendering and RSX image quality

Date 2026-10-28. Worktree `ps3recomp-t133`, branch `agent/t133-rsx-image-quality`. Not merged or pushed. No game build or launch. No other worktree modified.

## 1. Base commit

- **Base: `169e618`**, the T120 tip.
  - Contains T113 `2562ba8` (FP span through END, exposure fix) and T120's opt-in `RSX_RT_WINDOW` / `RSX_DEPTH_STATE`, which are needed for the Phase 5 A/B.
  - With every switch unset, behaviour is T113's.
- **Commits:**
  - `4a74174`: T115 `17b16cb` cherry-picked (`-x`), applied cleanly. It adds `RSX_TEX_MIPS=1`.
  - `816a4af`: T133's own changes.
- **Not taken:**
  - T115B `65d2695` (exact cache hash, CONTROL3 pitch). It is a cache-staleness fix, not a grain source.
  - T116/T117/T119/T122.

## 2. Screenshot classification

The screenshot is not attached to the brief. I used the T113 race capture I (`t113/runtime-I-20261027-182926`, frame f006502, `png/frame_049`, full-resolution crops in `t133/crops/`). It shows the same symptoms.

| Symptom | Observation (1280×720 crops) | Class |
|---|---|---|
| Sea speckle | single-pixel dark/light dots, densest in the distance (minified) | texture minification aliasing (§5); NaN export as a secondary hypothesis (§7) |
| Bright surf | flat white band, no texture detail | exposure / shore blend / depth state, not grain (§8) |
| Palm/foliage stipple | stair-stepped, broken leaf edges | alpha cutout on a point-sampled, single-level unit (§6), plus no 2× MSAA (§9) |
| Grainy sand/vegetation | high-frequency texel noise at a distance | minification aliasing (§5) |

## 3. Root-cause hypotheses (ranked)

1. **No mip chains.** VERIFIED as a state mismatch; visual effect HYPOTHESIS. 3,001 of 8,645 race texture bindings per frame advertise 9–11 levels with a mip min filter, but D3D12 uploads level 0 only, so every minified texture aliases.
2. **Unit 0 is point/clamp** in the static root signature (a debug-font workaround). VERIFIED as a state mismatch. It is applied to 664 unit-0 bindings, 607 of which ask for LINEAR_MIPMAP_NEAREST (the cutout masks also WRAP and bias −0.797). Those include the mask of all 80 alpha-cutout (foliage) draws.
3. **2× MSAA dropped.** VERIFIED. The scene is AA mode 3 (DIAGONAL_CENTERED_2, pitch 10240), and the host renders it single-sampled, so edges and cutouts get no coverage AA.
4. **FP precision modifiers ignored** (FX12/FX9 clamps). VERIFIED in the code; race usage is unknown (HYPOTHESIS).
5. **NaN → 0 on export** giving dark dots. HYPOTHESIS.

## 4. Verified RSX state (capture I, frame f006502, 665 textured draws)

- **Filters:** min LINEAR_MIPMAP_NEAREST on 3,668 bindings, LINEAR on 3,103, LINEAR_MIPMAP_LINEAR on 946, NEAREST on 927. Mag LINEAR except the NEAREST lookups.
- **Anisotropy:** CONTROL0[6:4] = 1× on every binding. The game does not use anisotropic filtering.
- **LOD:** bias −0.797 (`FILTER` 0x…3F34) on 3,225 bindings, 0 on the rest. LOD range 0..15 or 0..0.
- **Alpha:** alpha test is off on all 665 draws (`alpha` 0x000700). Cutouts are shader `KIL`: 30 FPs, 80 draws on scene RT `0x00750000` and the shadow RT `0x0B830000`. Each discards when unit-0 alpha is below 0.5.
- **Kill-on-alpha:** CONTROL0[3:2] = 0 everywhere.
- **Sampled formats:** DXT1/DXT23 chains of 256²–1024², 9–11 levels.
- **Tools:** `t133/tools/tex_tally.py`, `cutout_tally.py`.

## 5. Texture filtering findings

- **Single level.** VERIFIED (code and T115): resources, copies and SRVs use `MipLevels = 1`. Fix: `RSX_TEX_MIPS=1` (T115), now on this base. `test_tex_mips` passes 48/48 and `test_t115_warp` 24/24 here.
- **Fixed samplers.** VERIFIED: without `RSX_GUEST_SAMPLERS` unit 0 is MIN_MAG_MIP_POINT/CLAMP and units 1–15 are trilinear/WRAP with LOD 0..∞. That ignores the guest's mip mode, bias, LOD range and wrap, and clamps tiling unit-0 UVs. Fix: `RSX_GUEST_SAMPLERS=15` (T110, already in base), audited:
  - the decode matches RPCS3 (bias s4.8, LOD 4.8, aniso table);
  - the captured unit-0 words decode to MIN_MAG_LINEAR_MIP_POINT, WRAP, bias −0.797, LOD 0..15 (checked in the T133 test).
- **Not issues here:** convolution filters (1 binding, approximated as linear, PARTIAL), MIRROR_ONCE_BORDER (unused), cubemaps (T115 verified).
- **Texture gamma (`gamma_mask` 7 on DXT colour) and sRGB output:** handled in the shader (T110 WARP-verified). No grain link found.
- **Compressed decode:** DXT1/23/45 block copies (T107/T115). No defect found.

## 6. Alpha / dithering findings

- **No deliberate stipple found.** HYPOTHESIS that none exists: the race uses neither alpha test nor kill-on-alpha. Alpha to coverage is unknown because `0x1D7C` was never decoded; it is now recorded as RSXI `aa_ctl`.
  - Cutouts are hard `KIL` at alpha < 0.5, which is original behaviour and is kept.
- **The D3D12 path adds the noise.** VERIFIED offline (`test_t133_image_quality`):
  - With the captured state, the old unit-0 point/clamp single-level path's coverage flips 0/8 ↔ 8/8 pixels under a 3-texel shift, so it shimmers as the camera moves.
  - With guest samplers plus the chain, every phase samples level 2 (alpha 0.25 in this fixture) and gives stable coverage.
  - What the game looks like with this fix is HYPOTHESIS until the runtime A/B.

## 7. Shader precision findings

- **OPDEST [23:22] precision was ignored.** VERIFIED in the code.
  - RSX clamps FX12 to [−2, 2], FX9 to [−1, 1] and FP16 to ±65504 (RPCS3 `ClampValue` ranges).
  - Fix: `RSX_FP_PRECISION=1` clamps after the result scale and before saturate. With it off, the HLSL is byte-identical.
  - RPCS3 exempts some opcodes (NRM/MIN/MAX/EX2/LG2/…), which this fix does not reproduce. PARTIAL.
- **Usage in race shaders is unknown:** the RSXI HLSL dumps lose the bits. RSXI now writes per-FP `prec` counts and the raw `.ucode`, so the next capture decides it.
- **Precision of `h` registers:** they are computed at FP32. That is more precise than the hardware, so it cannot add grain. Not changed.
- **Derivatives:** 0 DDX/DDY in the 183 race FPs. 26 SampleLevel and 2 SampleBias sites, handled per T110.
- **NaN:** T113's IEEE strictness makes the export guard write NaN as 0. Whether RSX writes 0 is unknown; dark sea dots from it are a HYPOTHESIS.

## 8. Water and shoreline

- **Ocean speckle:** the sea/sand draws sample DXT1 1024² chains on units 0–3 at level 0. Unit 0 is also point-sampled. HYPOTHESIS: the speckle is normal/specular minification aliasing, addressed by mips plus guest samplers.
- **Surf brightness is not a filtering effect.** T120 found:
  - the shore draws (`fp_07200641`, ops 484–497) wrote depth with writes off, and lost their bound zeta;
  - MRT1 (the luminance source) blend is unverified.
  - `RSX_DEPTH_STATE=1` and T120 item #8 are the candidates. **Not tested at runtime**; it is arm D in §14.
- T113's span fix and exposure fix are untouched (`test_fp_span` and `test_exposure_writeback` pass).

## 9. MSAA / resolve

- **VERIFIED:** scene surfaces are SET_SURFACE_FORMAT antialias 3 (2 samples, pitch 10240). The host target is 1280×720 with 1 sample. The game's post pass reads a 2528×711 "sample" texture, which `RSX_RT_WINDOW` maps onto the host pixels, so no coverage AA exists.
- **Faithful fix (NOT implemented):**
  - render to a 2-sample target, honouring `aa_ctl` (alpha to coverage, sample mask);
  - expose the two samples as a 2×-wide texture where the guest samples the surface, with a custom resolve copy instead of `ResolveSubresource`.
  - It needs the guest sample positions (diagonal), touches the RT pool, the T120 windows and T122's synchronisation, and needs an integrated build to validate. Documented as a dependency.
- **No FXAA/TAA was added.** The game has no temporal AA pass in the captured frame.

## 10. Implemented corrections

All are opt-in. Unset, the renderer behaves as T113/T120.

| Switch | What | Source | Status |
|---|---|---|---|
| `RSX_TEX_MIPS=1` | upload guest mip chains | T115 (cherry-pick) | VERIFIED offline |
| `RSX_GUEST_SAMPLERS=15` | guest filter, wrap, LOD, bias, border | T110 (in base) | VERIFIED offline, now with race words |
| `RSX_FP_PRECISION=1` | FX12/FX9/FP16 result clamps | T133 | VERIFIED offline (WARP); race effect HYPOTHESIS |
| RSXI `aa_ctl`, `prec`, `.ucode` | evidence for §6/§7/§9 | T133 | diagnostic |

## 11. Offline tests

- **`test_t133_image_quality.c`** (WARP, debug layer on, 0 errors): **35/35**.
- **`tools/test_image_quality.py`:** 5 pins plus the build/run.
- **Suite** `t133/tools/run_suite_t133.cmd ps3recomp-t133`: **38/38 PASS** (`logs/suite_t133.txt`). This includes T113/T120 and T115's `c_tex_mips` 48/48 and `c_t115_warp` 24/24.
- **TU:** `rsx_d3d12_backend.c` compiles with **0 errors**. Warnings 3003 → 3040 with no new class (T115 contributes most).
- **Audit:** `--staged` reports the **25 inherited BLOCKs** (runtime/spu test images, scratch); none in a T133 file (`logs/audit_staged.log`).

## 12. Performance (no runtime measurement)

- **Mips:**
  - CPU on a texture cache miss: about +3–9% re-upload (T115 bench). Hits are unchanged.
  - VRAM: about +33% per chained texture.
  - No new `wait_for_gpu`; uploads stay in the existing replay.
- **Guest samplers:** descriptors are an append-only cache and are never rewritten. Each draw re-binds its sampler tables only when they change.
- **Precision clamp:** at most one `clamp` per instruction with a non-FP32 precision, and only when on. It is compiled once per PSO.
- **RSXI writes:** capture-time only.
- **No changes to the dynamic-resolution path** (1259–1265 × 708–712).
- **The 4.56 FPS figure was not reproduced or affected:** there was no launch.

## 13. Integration conflicts

- **T115/T115B:** T133 carries T115's commit. Integrate T115 once and drop the duplicate.
  - T115B builds on T115 and touches the same uploader; expect textual conflicts in `vp_upload_tex_slot`.
- **T116 (shader/PSO cache):** the on-disk FP key must include `rsx_fp_precision_clamp_on()` and the mip view levels.
- **T117:** must keep T113's END-based span. The RSXI dump calls `fp_span` (pinned).
- **T119:** compact vertex layout untouched.
- **T122:** no new barriers or waits from T133. The MSAA work (§9) would need T122 review.
- **T120:** the base. No T120 code changed. `rsx_commands.*` and the RSXI line gain fields next to T120's `mrt_regs`.

## 14. Runtime validation plan (needs authorization)

- **Build:** one exe from `816a4af`.
- **Route and capture:** the T113 runner (`t113/run_t113.py`) on the same route, at the same race capture time, with RSXI on and frame PNG/BMP dumps.
- **Run order:** A B C D E E D C B A.

| Arm | Env |
|---|---|
| A | none (T113/T120 default) |
| B | `RSX_TEX_MIPS=1` |
| C | B + `RSX_GUEST_SAMPLERS=15` |
| D | C + `RSX_RT_WINDOW=1 RSX_DEPTH_STATE=1` |
| E | D + `RSX_FP_PRECISION=1` |

**Checks:**
- **Arm A RSXI:**
  - `aa_ctl` values (alpha to coverage on foliage?);
  - `prec` counts per FP (which race FPs use FX12/FX9);
  - `mrt_regs`.
- **Grain metric:** for fixed crops (sea, sand, palms), the high-frequency energy (pixel minus 3×3 mean) and frame-to-frame cutout flicker, A against C.
- **Surf:** band luminance, and exposure `c[33]`, A against D against E.
- **Performance:** `[rsx-frame-perf]` `tex_ms`/frame time, `[tex-mips] create_fallback=0`, and the `[samplers]` heap.

**Fidelity:**
- Changes from B/C/D/E count as fidelity fixes only where they follow the recorded guest state.
- There is no PS3 reference capture, so no parity claim.

## 15. Local commits

- `4a74174`: T115 mip chains (cherry-pick of `17b16cb`).
- `816a4af`: T133 precision clamps plus the RSXI `aa_ctl`/`prec`/ucode records.

## Summary

- **Fixed (opt-in, offline-verified):**
  - mip chains plus guest samplers. They address the two verified texture-state mismatches behind the minification grain and the foliage cutout shimmer;
  - FP precision clamps.
- **Unverified:**
  - the in-game visual result of all of these;
  - whether race shaders use FX12/FX9;
  - alpha to coverage;
  - the surf brightness (a T120 depth/MRT question);
  - missing 2× MSAA (found, not implemented).

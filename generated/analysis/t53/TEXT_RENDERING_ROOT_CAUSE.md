# T53: MotorStorm B8 font atlas and shader diagnosis

2026-10-26. Offline only: no launch, build of MotorStorm, renderer edit, merge or push. **Stopped before runtime execution.**

Inputs read:
- T44, T45, T46 (`Motorstorm01/t46-worktree/.../t46`), T49 (`t49-worktree/.../t49`) and T50.
- T52 does not exist.
- T24 renderer `ps3recomp-t24-render` @ `419e887`: clean and unchanged since T49.

Worktree:
- `Motorstorm01/t53-worktree`, branch `agent/t53-text-root-cause` (from `f9f33d1`).
- Local commit `8d3eddb`, synthetic C test only; `audit_public.py --tree` passed.
- Retail-derived artifacts stay private in this directory.

## Bottom line

- **The shader and the B8 remap are eliminated as the cause of invisible text.** This rests on retail microcode with RSX semantics, not only the native HLSL.
- **No rendering correction for the invisibility can be proven from RSX semantics alone.**
- The fault lies upstream of the shader, in one of:
  - glyph raster/packing (atlas bytes)
  - upload staleness
  - glyph geometry and vertex alpha
  - composition
- All four need runtime evidence.

## Confirmed findings

| # | Finding | Evidence | Status |
|---|---|---|---|
| 1 | **Retail FP microcode found.** SHO object in `MS2.PSARC:/global.rpk` (SHO header +0x6BCD1, ucode +0x6BD71). It has 27 instructions and its constant slots match fp `02537E81`'s HLSL line for line. A second SHO with the same header sits at +0x6C517 (variant, not decoded). | `find_fp_ucode.py`, `fpdis.py`, `fp_retail_disasm.txt` | VERIFIED (original) |
| 2 | **Runtime constants identified.** All 541 atlas-sampling draws and all 897 non-atlas draws of this FP, across 5 frames in 2 runs, carry identical constants. The game patches slot 9 (retail 1 → 0); slot 4 is 0. That disables both predicated paths (`MULXC RC.w`/`RC.x`). Export is fp16 (`fp_exp32=0`), so the output is H0. | RSXI `fp_consts` | VERIFIED (runtime) |
| 3 | **Retail output alpha.** Under RSX semantics (H/R aliasing, fp16/fx12 precision, condition codes), the retail program outputs alpha = `tex0.a × col0.a`. With CONTROL1 `0x56FF` (1,1,1,cov) and with native `0x1000` (cov,cov,cov,cov), alpha = fp16(coverage) for **all 256 bytes**. The `0x1000` mapping changes only RGB (coverage-darkened fringes). | `rsx_fp_interp.py` → `interp-results.txt` (PASS) | VERIFIED (offline, retail ucode) |
| 4 | Blend for every candidate: key `0x0122418B` = SRC_ALPHA / INV_SRC_ALPHA, ADD (alpha INV_DEST_ALPHA / ONE). Non-zero output alpha would be visible. | `rsx_blend_key` decode | VERIFIED (code + runtime key) |
| 5 | **B8 pipeline in T24 code:** `0xA1` → R8 class, linear, 1 B/texel, row 2048, face 2,097,152 B. Decode is byte-identical. Pitched linear B8 drops row padding. Remap `0x56FF` → (A←byte, RGB=ONE) = D3D12 `0x116D`. Forced `0x1000` gives identical alpha and different RGB for 255 of 256 values. | `tools/t53/test_b8_pipeline.c` compiled against T24 `rsx_texture_layout.c`: **ALL PASS** | VERIFIED (offline) |
| 6 | The upload calls `rsx_texture_layout()` without the guest pitch. Harmless here (pitch 2048 = width) but latent for padded B8. | `vp_upload_tex_slot`, T24 ~3204 | VERIFIED (code) |
| 7 | **Stale-upload candidate stands.**<br>- `tex_csum` (T24 :3128) samples only columns 0–3 of each atlas row.<br>- The recorded `0x1F116DC5` equals the all-zero value.<br>- It cannot see glyph writes, so a first upload taken before rasterization would never be refreshed. | T50 test, T46 | VERIFIED blind spot; staleness HYPOTHESIS |
| 8 | No lossless B8 capture exists:<br>- T50 and T52 implemented none.<br>- `RSXI_SNAP=textures` is limited to `0x85` (T24 :6036).<br>- `TEX_SAVE` reads later guest memory with sparse stats.<br>- `tex_snapshot.h` already keeps full-hash record-time generations, but these are not persisted per draw. | code, T49 | VERIFIED |

## Eliminated hypotheses

- **Shader zeroes B8 alpha.** Eliminated for the recorded constants, by retail ucode under RSX semantics (finding 3).
- **The `(R,R,R,R)` vs `(1,1,1,R)` mapping causes invisibility.** Alpha is identical (findings 3 and 5). It is a real RGB fidelity bug, but not the cause.
- **Predicated kill/threshold paths.** Disabled by the runtime constants (finding 2).
- **Blend state, viewport, colour mask, draw order relative to icons.** Same state as the visible icons (T45, T49, finding 4).
  - Still open: the native scissor for the op33 strip, which isn't independently recorded (T49).
- **B8 decode, row footprint, upload format (R8_UNORM).** Correct (finding 5).

## Exact remaining evidence gaps (pipeline order)

1. A non-space glyph's raster bitmap is non-zero. Check at `0x586CF8`: S+0x84..0x90 plus the bitmap rows.
2. Packed atlas ROI equals that bitmap, after the row-copy loop that follows `0x586D38`. Also: is A+0 the same as `0xC4E88580`?
3. The **consumed** atlas bytes (record-time snapshot) and the **GPU** slot contents, compared byte-for-byte, with the upload generation (stale-cache test).
4. One glyph quad's v0/v3(colour, **alpha**)/v8 UV, plus VP constants 59 and 467 (unknown, not zero).
5. Destination pixel before and after the matching draw, read only after the fence completes.

## Minimal correction

- **For invisibility: none proven.**
- Proven from RSX semantics but cosmetic: for B8, use `rsx_remap_to_d3d(ctrl1, 0x81)` (= `0x116D` here) instead of fixed `0x1000` at T24 :3768 and :6828. Fixes RGB fringes only. **T24 owner decision; not applied.**
- If gap 3 shows staleness: make the `tex_csum` stride co-prime with the pitch, or periodically full-hash large textures. Gated on evidence.

## Minimal future capture (owner instrumentation; needs authorization)

One bounded menu run on the T44 exe (garage path optional), one label/glyph, one op-25-type draw. Nothing forced.

| Hook | Record |
|---|---|
| PT ret `0x586CF8` | codepoint, r3, S+0x84/88/8C/90, ≤64 bitmap rows (raw) |
| PT after row copy (`0x586D38` loop exit) | A+0/+18/+1C, G+4/+6/+8/+C, packed ROI (raw) |
| Backend, atlas upload (T24) | raw 2 MiB `.bin` of the selected source; full SHA-256; snapshot generation, hit or fallback; tex_csum; upload generation |
| Backend, R8 readback of the slot after fence (T24) | raw 2 MiB `.bin`, byte compare |
| Backend, draw record | per-unit SRV mapping and resource; one batch's vertex bytes (v0/v3/v8); VP c59/c467 |
| Backend, after draw | 16×16 destination ROI before and after (fenced) |

**Decision rules:**
- zero bitmap → font/raster
- wrong ROI → packing
- CPU ≠ GPU → upload/cache
- `col0.a = 0` or degenerate UVs → geometry/alpha
- otherwise → composition

## Offline test results (re-runnable)

- `tools/t53/build_test.cmd <renderer-root>` → **ALL PASS** (17 checks).
- `python rsx_fp_interp.py ../c38/global.rpk 0x6bd71` → **PASS** (256/256). Default constants (slot 9 = 1) also leave alpha unchanged.
- T50 `test_atlas_csum.py` → PASS (checksum blind spot).

Artifacts here: `find_fp_ucode.py`, `fpdis.py`, `rsx_fp_interp.py`, `fp_retail_disasm.txt`, `interp-results.txt`.

**Uncertainties:**
- The decoder and interpreter cover only the opcodes this program uses. Field layout follows RPCS3/nouveau, not Sony documentation.
- The fx12 clamp is approximated.
- Retail ucode identity rests on the instruction and constant match, not on a load-path trace.

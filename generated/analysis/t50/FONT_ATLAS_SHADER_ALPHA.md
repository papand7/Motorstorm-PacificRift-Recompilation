# T50: Font atlas and shader alpha verification

Phases 1 and 3 are done offline. **Stopped before the live capture; authorization requested.**
- No launches, builds, backend edits, merges or pushes.
- Sources:
  - `ps3recomp-307b08a/libs/{video,font}`
  - T36 RSXI capture `runs/20261026-061327-t36-first-race/rsxi` (frame f004569)
- Scripts (both pass): `t50/sim_fp_02537E81.py`, `t50/test_atlas_csum.py`

## Result

**Leading cause (PARTIAL):** a stale texture-cache upload. The backend decides whether to re-upload the atlas from a sparse checksum, and that checksum cannot see glyphs being added.

| # | Finding | Status |
|---|---|---|
| 1 | `tex_csum()` decides whether `vp_upload_tex_slot` re-uploads (`rsx_d3d12_backend.c` ~2925). For the 2 MB atlas its step is `nbytes/1024` = **2048 = the row pitch**, so it only reads **columns 0–3 of each row**. | VERIFIED (code + test) |
| 2 | Glyphs written anywhere at x ≥ 4 leave the checksum unchanged, so a stale GPU copy is kept forever. The offline test filled 1.57 M texels and got the same checksum as an empty atlas. | VERIFIED (offline) |
| 3 | The recorded atlas checksum at f004569 is `0x1F116DC5`, **exactly the all-zero value**. This is consistent with an empty first upload, but it only proves that columns 0–3 are zero. | VERIFIED value; implication HYPOTHESIS |
| 4 | Remaining gap: whether the first upload happened before glyph rasterization. That needs the capture below. | HYPOTHESIS |

The shader is not the cause (VERIFIED in the offline model):
- In the emitted HLSL of fp `02537E81`, output alpha = atlas alpha × vertex alpha.
- Byte 0 gives alpha 0, 0.5 gives 0.5, 1.0 gives 1.0.
- An icon ARGB texel passes through unchanged.
- The `cc0` kill path is never taken.

## Atlas data path (VERIFIED from code and RSXI unless marked)

| Item | Value |
|---|---|
| Glyph source | The game imports `cellFontRenderSurfaceInit`, `RenderSurfaceSetScissor` and `RenderCharGlyphImage` (NID 0x88BE4799). The HLE uses stb_truetype and writes coverage bytes with `vm_write8(buf + y*wbyte + x*psize)`. **Unverified:** whether the surface buffer is the atlas itself or a staging buffer copied later. |
| Guest memory | Offset `0x04E88580`, location 1 (local), resolved EA `0xC4E88580` |
| Size / pitch | 2048×1024, pitch 2048, 1 mip, format 0xA1 (B8 linear), remap `0x56FF` |
| Snapshot | `PS3_TEX_SNAPSHOT=1` copies linear B8 textures of 64 KB or more at record time. The cache checksum runs on that copy, with the same blind spot. |
| Upload | `vp_upload_tex_slot`: `DXGI_FORMAT_R8_UNORM`, `CopyTextureRegion` from an upload buffer (RowPitch 2048, already 256-aligned, no padding), then a COPY_DEST → PIXEL_SHADER_RESOURCE barrier. Upload slot 6 for both units in f004569. |
| Lifetime | Cached per (offset, w, h, fmt). Re-uploaded only if `tex_csum` changes; `TEX_NOCACHE=1` forces it. |
| SRV | R8_UNORM with `Shader4ComponentMapping = 0x1000`, i.e. (R,R,R,R), hard-coded for B8 (lines 3449 and 6508). **This ignores CONTROL1.** |

**Secondary fidelity bug (VERIFIED, not the invisibility cause):**
- CONTROL1 `0x56FF` means RGB = 1 and A = byte.
- The backend instead gives RGB = byte, so text RGB becomes vertex colour × coverage. Anti-aliased edges come out darker; glyph interiors are unaffected.
- The model shows the two mappings give the same alpha.

## Existing data

- No trace contains atlas pixel bytes.
  - RSXI keeps only render-target BMPs.
  - No `[TEXB8]` line appears in any run.
- The checksum is the only content evidence, and it is blind to everything at x ≥ 4.

## Minimal capture (needs authorization)

**Run A: observation only, existing switches, no build.**
- Exe: the T44/T45 build, SHA-256 `96d9dee1…dbc22`.
- Settings: private HDD, intro skip as in T36, RSXI trigger at the garage, one bounded run.
- `TEX_SAVE=1`
  - At each atlas (re)upload it logs `[TEXB8] off nz/total min max`, sampled every 17 bytes across the whole atlas. B8 dumps are lossless single-channel BMPs.
  - Side effect: it also writes up to 8 ARGB BMPs to the working directory.
- PT HLE hooks: `cellFontRenderSurfaceInit` (r4 buffer, r5 widthByte, r6 pixelSize, r7 w, r8 h) and `cellFontRenderCharGlyphImage` (r5 surface; count plus first and last timestamps).
- `vm_inline_ok` triggers stay unset.

**Decision rule:**
- `[TEXB8] nz=0` at the single upload, glyph renders into `0xC4E88580` (or a copy into it) afterwards, and no second upload: **stale cache confirmed**.
- `nz > 0` at upload: the cache is ruled out. Next would be blend or vertex alpha (Run B).

**Run B (only if needed; needs a build and the T24 renderer owner):**
- A diagnostic-only backend hook that writes, at each atlas upload:
  - the raw 2 MB guest bytes (`.bin`)
  - a full FNV/SHA hash
  - a readback of upload slot 6
  - the SRV descriptor and mapping
- Plus a dump of one op-25 vertex's `col0` alpha.

`TEX_NOCACHE=1` would be a decisive A/B check, but it changes rendering behaviour, so it is excluded unless you explicitly approve it.

## Proposed correction (not applied; T24 renderer owner)

1. Make the `tex_csum` stride co-prime with the row pitch, or periodically fully hash large textures, as `rsx_draw_engine.c` already does with `ENG_TEXHASH_FULL_EVERY`.
2. Secondary: derive the B8 SRV mapping from CONTROL1 (`rsx_remap_to_d3d`) instead of the fixed `0x1000`.

Neither is a colour or alpha tweak; both restore the guest-specified data and swizzle.

## Uncertainties

- Atlas timing (empty first upload) is unproven.
- Whether the surface buffer is the atlas itself or a staging copy is unknown.
- The shader model reproduces the emitted HLSL, not RSX half-register hardware semantics.
- Vertex `col0` alpha for text was not captured.

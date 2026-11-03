# T61: invisible MotorStorm text, root cause and fix

2026-10-26. Offline only: no launch, no game build, no merge, no push. Shared worktrees are untouched (`ps3recomp-t24-render` @ `419e887` is clean).

## Bottom line

- **First failing stage: A/B. The glyph image never exists, so the atlas stays empty.** The cause is our HLE `cellFontRenderCharGlyphImage`, not the renderer. Evidence: original code + offline reproduction (VERIFIED).
- **Fix:** commit `166c973` on `agent/t61-font-null-surface` (worktree `ps3recomp-t61`, base `419e887`). Touches `libs/font/cellFont.c` (+26/−1) and the font tests. No renderer, shader, blend, remap or exposure change.
- **Not claimed fixed at runtime.** That needs the capture in §6.

## 1. Original code path (VERIFIED, EBOOT sha256 `bbb7fe25…`)

Disassembly is in `logs/disasm_586C44_586D94.txt`; stub NIDs were resolved from the import tables (`logs/stub_nids.txt`).

| Address | Call | Arguments |
|---|---|---|
| `0x586C44` | `cellFontBindRenderer` (66A23100) | font = obj+0xC, renderer = r19+0xCC |
| `0x586C74` | `cellFontSetupRenderScalePoint` (4D19C631) | f1 = f2 = s |
| **`0x586C9C`** | **`cellFontRenderSurfaceInit` (90B9465E)** | **buffer = `li r4,0` (NULL)**, widthByte = 4s, pixelSize = 1, w = h = 4s |
| `0x586CBC` | `cellFontRenderSurfaceSetScissor` (B422B005) | 0, 0, 4s, 4s |
| `0x586CF4` | `cellFontRenderCharGlyphImage` (88BE4799) | x = y = 2s, metrics = S+0x9C, transInfo = S+0x84 |
| `0x586D34` | pack (`0x584C20`) | size from transInfo +0x8C/+0x90 |
| `0x586D90…` | memcpy (`0x756518`) per row | dst = A+0 + (G+6)·A+0x18 + G+4; **src = [S+0x84] + row·[S+0x88]**; n = [S+0x8C]; rows = [S+0x90] |

- The renderer config at CreateRenderer (`0x5848C4`) also passes buffer NULL with all sizes 0, so the library owns the renderer buffer.
- **These are the only `RenderSurfaceInit` and `RenderCharGlyphImage` call sites in the EBOOT** (full BL scan). Every glyph of every label goes through this NULL-buffer path.
- The game therefore needs libfont to rasterize into a library-owned buffer and to return it in `CellFontImageTransInfo.Image`.
  - That this is the firmware's semantics is inferred from the game's dependency on it. No Sony documentation was consulted (PARTIAL).

## 2. Defect (VERIFIED, `libs/font/cellFont.c` @ `419e887`, identical on every T24/perf branch)

- `cellFontRenderCharGlyphImage` (`:612–688`) writes coverage only when `buf_ea != 0`, and reports `Image = buf_ea ? … : 0`. Its own comment reads "a surface with no buffer … draws nothing".
- So the game's row copy reads from guest EA 0 + row·4s, which is below `VM_MAIN_MEM_BASE` 0x10000, and fills each glyph's ROI with zeros.
- This matches the recorded atlas checksum `0x1F116DC5`, which equals the all-zero value (T53 finding 7).
- The existing test `test_font_render_surface.c` asserted this behaviour (`TRANS+0 == 0 /* no buffer */`).

## 3. Stage evidence

| Stage | Evidence | Status |
|---|---|---|
| Font files / open | Byte-identical originals (T49) | VERIFIED (T49) |
| **A. Glyph raster** | HLE draws nothing for the NULL-buffer surface the game uses, and returns Image = 0. Reproduced offline: on the base tree, 0 of 112 ROI pixels covered. | **VERIFIED: first failing stage** |
| B. Placement | The game copies from transInfo.Image, so with Image = 0 it copies zeros. After the fix, the ROI is 112/112 covered, interior value 255. | VERIFIED (offline) |
| C. CPU→GPU upload | `tex_csum` (`rsx_d3d12_backend.c:3128`) samples 4 bytes per 2048-byte row. Glyphs added later at x ≥ 4 may not trigger a re-upload. | HYPOTHESIS (§7 risk 1) |
| D/E. Geometry, alpha, composition | Not reached. T53 already eliminated the shader, blend and remap. | UNKNOWN until runtime |

**Phase 1 (lossless B8 renderer capture) was not implemented.** The first failing stage was proven upstream of the renderer from original code plus an offline reproduction, so renderer instrumentation was not needed to establish it. Adding it would overlap the T24 renderer owner. It remains the tool for stage C if §6 step 3 fails.

## 4. Patch (`cellFont_fix.diff`)

- **`:640–656`.** Applies when the surface buffer is NULL and widthByte and pixelSize are > 0:
  - It uses the bound renderer's guest buffer, sized widthByte × height (allocated with `sys_heap_memalign(0,128,…)`, growing when needed).
  - It zeroes that buffer for each glyph, then runs the existing raster, clip and transInfo code unchanged. Image and Surface now point into that buffer.
- **`:62`.** `RendererSlot` gains `buf_ea, buf_size`.
- **`:439` and `:229`.** The buffer is freed by `cellFontDestroyRenderer` and `cellFontEnd`.
- A surface that has its own buffer is unchanged: same pixels, same Image, no allocation (tested on both trees).

## 5. Offline tests (`logs/`; clang through `scratch/t59/suite/cc.cmd`)

| Test | Base `419e887` (copy) | Fix `166c973` |
|---|---|---|
| **new** `test_font_null_surface_atlas.c` | **7 FAIL**: Image = 0, ROI 0/112, no buffer | **0 failures** (20 checks) |
| `test_font_render_surface.c` | pass (asserts Image = 0) | pass (asserts Image is in the renderer buffer at the glyph box) |
| `test_font_initialize_with_revision.c` | pass | pass (heap stub added) |
| `test_font_open_file_abi.c` | pass | pass (heap stub added) |
| `tools/test_font_hle_nids.py` | n/a | 3/3 PASS |

- The new test replays `0x586C44–0x586D90` with a synthetic one-glyph TrueType font, so no font file is needed. It checks:
  - ROI coverage at 20 px and 10 px;
  - a code with no glyph;
  - a dirty heap leaving no stray bytes;
  - buffer reuse and freeing;
  - the own-buffer path unchanged.
- **Unrelated textures, icons and UI geometry:** no renderer file changed, and `libs/video` is untouched. The only behaviour change is the NULL-buffer case, which previously drew nothing.
- **Audit:** `audit_public.py --staged` exits 1 with 25 items, identical output to the `af37553` baseline. The new files are not flagged.

## 6. Minimal runtime validation (needs authorization)

1. Build the port against `ps3recomp-t61`. Don't set any `vm_inline_ok` triggers, and use a private HDD root.
2. Boot → intro → `garage-viewer-character` → CROSS, UP, CROSS → `mainmenu`. Within 30 s of the last input (the idle dim), take a draw-gated capture of the menu and garage frames.
   - **Pass:** labels are visible (user-confirmed screenshot) and the text candidates draw over the same atlas.
3. **If text is partial or missing:** rerun the same path with `TEX_NOCACHE=1`.
   - Complete text then means stage C (sparse-checksum staleness) is proven. The follow-up is to use the `tex_snapshot` full hash in the cache check. This is a renderer-owner change, not applied here.
   - Still missing means geometry or composition: use the T53 §"Minimal future capture" hooks.

## 7. Remaining risks

1. **Stale atlas upload (stage C)** is plausible if glyphs are added after the first bind. Test it with step 3 above.
2. The firmware semantics come from the game's usage, not documentation. The layout of the image inside the buffer may differ from Sony's, but the game reads only Image, stride, width and height.
3. The renderer buffer is per renderer and unsynchronized. That is safe for the game's single atlas-updater call path; concurrent rendering on one renderer was not assessed.
4. Glyph boxes that extend outside the scissor still report the unclipped box. This is pre-existing behaviour, unchanged.
5. The B8 RGB mapping `0x1000` vs `0x116D` (T53) remains a cosmetic fringe issue and was deliberately not changed.

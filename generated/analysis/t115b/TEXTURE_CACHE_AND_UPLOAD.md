# T115B: D3D12 texture-cache correctness and upload performance

Date: 2026-10-27. Worktree `ps3recomp-t115b`, branch `agent/t115b-texture-cache`.
No full game build, no game launch, no merge, no push. Other agents' worktrees untouched.

## 1. Base commit and ancestry

- VERIFIED: T115B `65d2695` sits on T115 `17b16cb`, which sits on T110 `e3b961d`.
  The full chain is T94 `8ea1437` → T105 `36d0fb7` → T108 `6b1a7e4` → T110 `e3b961d` → T115 `17b16cb` → T115B `65d2695`.
- VERIFIED: the T115 worktree was clean. A new worktree was created anyway, so that T115 `17b16cb` stays fixed as arm A.
- VERIFIED: T113 (`74fd084`, from `19d6b6d`) and T116 (`30b817b`) both branch from `e3b961d`. T111 (`d2a65f9`) branches from `6b1a7e4`.

## 2. Confirmed original defects

| # | Defect | Status / evidence |
|---|---|---|
| D1 | `tex_csum` reads 4 bytes every `nbytes/1024` bytes (for spans over 4096 B), so a change between sampled words leaves the old texture bound. | VERIFIED, `test_tex_cache` check 1. Changing one A8R8G8B8 texel (256²), one DXT1 block (512²), or one byte of mip level 4 in a DXT45 chain is MISSED by the old rule. Exhaustive single-byte flips: the old rule misses 93.8% of them at 64 KiB and 98.4% at 256 KiB. |
| D2 | Cubes are validated on face 0 only: both the lookup and the stored checksum read `vm_base + off` over `src_bytes`. | VERIFIED. A change on face 3 (DXT1 256² cube), or on face 5 level 8 (DXT23 ×9 cube), is MISSED. |
| D3 | The checksum loop condition `i + 3 < n` never reads the last 1–3 bytes. | VERIFIED. A change to byte 14 of a 15-byte B8 texture is MISSED. |
| D4 | The D3D12 uploader ignores the CONTROL3 row pitch: it calls `rsx_texture_layout`, not the pitched variant. | VERIFIED. The garage RSXI capture (`runs/20261023-205211`) has `0xA5` 1279×719 with pitch 5120 (row data is 5116 bytes) bound with `src=upload` 2190 times. Read at 5116 bytes per row, every row y starts y×4 bytes early, so the image is sheared. On WARP, the unpitched upload has 718 of 719 rows wrong. |
| D5 | A cube's stored checksum is taken after the decode, not before (the 2D path takes it before). | VERIFIED by reading the code. An SPU write during the decode can leave a torn cube that never re-uploads. Fixed as part of D2. |
| D6 | An upload abandoned after the resource is created (Map failure) leaves the old key and checksum on a new, empty resource. | VERIFIED by reading the code; not reproduced. Under RSX_TEX_CACHE the slot's hashes are now voided before the upload. |
| D7 | `TEX_CSUM`'s 32-bit FNV collides with probability about 2^-32 per compare. | HYPOTHESIS that this matters in practice; superseded by the exact hash. |

Other padded linear textures in the capture never reach the uploader: the `0xBA` W16Z16Y16X16F 4×1 (pitch 64), 20×11 (pitch 192) and 10×5 (pitch 128) all resolve to `null_srv` or `rt_exact` (VERIFIED). The `0xA8` (DXT45 linear) entries have pitch equal to their block-row size, and the shared layout ignores pitch for compressed formats.

## 3. Implemented fixes

Everything sits behind one switch, `RSX_TEX_CACHE`, which is off by default. Unset gives T115 behaviour exactly: tex_csum and no pitch (pins `pin_off_identity`, plus 81,312 pitch-0 plans that are bit-identical).

- **`RSX_TEX_CACHE=1` (arm B):**
  - exact per-subresource validation;
  - CONTROL3 pitch honoured;
  - a changed texture is re-uploaded whole.
- **`RSX_TEX_CACHE=2` (arm C):** as 1, but only the changed subresources (face × level) of a kept resource are decoded and copied.

Files:
- `libs/video/rsx_tex_cache.h` (new): `rsx_texcache_hash`, `_spans_make`, `_hash_spans`, `_diff`, `_mode_parse`.
- `rsx_tex_mips.h`: adds `rsx_texmip_plan_make_pitched` and `rsx_texmip_level_read_bytes`. `rsx_texmip_plan_make` is now its pitch-0 wrapper.
- `rsx_d3d12_texmips.h`: adds `_fill_ex` and `_copy_ex`, which take a dirty mask. The old names are wrappers.
- `rsx_d3d12_backend.c`:
  - `vp_upload_tex_slot` gains a `gpitch` parameter;
  - pitch is part of the cache key;
  - exact lookup;
  - hashes are taken before the decode;
  - hashes are voided while an upload is in flight;
  - mode-2 dirty skipping;
  - `[tex-cache]` counters;
  - `tex_src_span` takes the pitch, so the draw-time snapshot covers the same span.

## 4. Cache invalidation design

- **Choice (VERIFIED offline): hash every byte of every subresource on each first bind per replay.**
  - Full-content hashing is the only candidate that is correct without new hooks.
  - Dirty-page tracking (`GetWriteWatch`/guard pages) would need `vm_base` reallocated with `MEM_WRITE_WATCH` in the runtime's memory core. It would also have to cover PPU stores, SPU DMA (host memcpy), RT readback (T113) and the HLE writers. Not done: that is outside the renderer, and nothing tracks writes today (VERIFIED: `vm.h` reserves the space and commits regions, with no write-watch flag).
  - Write-generation counters would need every guest writer instrumented. Rejected for the same reason.
  - Hybrid (dirty pages plus a hash): a later optimization. It needs the dirty-page layer first.
- **Hash:** four interleaved lanes of `(h ^ word) * odd`, with a bijective final mix.
  - A change confined to one aligned 8-byte word always changes the hash. This is proved by bijectivity and checked exhaustively at 11 sizes: every single-byte flip is caught.
  - Wider changes collide only by chance. 200,000 random one-word and 200,000 two-word changes were all caught.
  - The hash is not keyed and is not adversary-resistant (HYPOTHESIS: irrelevant for guest texture data).
- **Spans:**
  - Each span covers exactly the bytes `rsx_texture_decode` reads: face f at `f × face_stride`, level l at `lv[l].offset`.
  - A pitched linear level ends at its last row's last texel. A guard-page fixture shows that hash and decode stop there, while `face_bytes` would have read 12 bytes into a NOACCESS page.
  - Interior row padding *is* hashed, so a padding-only write causes a spurious re-upload. That is conservative and correct.
- **Coverage:**

  | Source of change | Covered? |
  |---|---|
  | CPU, SPU, RT-readback and HLE writes | Yes: they are all host writes to guest memory, and the check reads content (VERIFIED by design). |
  | A reused allocation (same key, new content) | Yes, as a content change. |
  | Mip-chain changes | Yes (per-level span). |
  | Cube faces | Yes (per-face spans). |
  | Pitch changes | Yes (key). |
  | Snapshot textures | Face 0 is hashed from the snapshot, as before. |

- **Not covered (PARTIAL, pre-existing):** a texture rewritten *between two draws of the same replay* is still uploaded once per replay (the `used` fast path). Only the existing draw-time snapshot (`PS3_TEX_SNAPSHOT`) handles that.

## 5. Row-pitch corrections

- VERIFIED. The shared `rsx_texture_layout_pitched` applies pitch only to linear (LN bit), non-compressed textures, and only when the pitch is larger than the row. Pitch now reaches the D3D12 decode.
- The decode reads rows at the pitch and writes them tight at the 256-aligned upload pitch, so padding never becomes pixels.
- Exact output, against an oracle decode of the same image packed tight, for:
  - `0xA5` 1279×719 at pitch 5120 and 13×7 at pitch 64;
  - B8, G8B8 and A1R5G5B5 (2→4 bytes), all at 13×5;
  - W16Z16Y16X16F 4×1 at pitch 64 and 20×11 at pitch 192.
- Pitch is ignored, as intended, when it is below the row, for swizzled textures, and for compressed textures.
- On WARP, the 13×7 and 1279×719 uploads read back bit-exact. Negative control: unpitched, 718 of 719 rows are wrong.

## 6. BC2/BC3 validation (WARP, D3D12 debug layer on, 0 errors)

All VERIFIED (`test_t115b_warp`, 38/38). The fixtures are synthetic solid blocks: alpha names the level, colour names the block or face.

- **BC2 and BC3 64×64 ×7 (2×2 and 1×1 levels are one block):** SampleLevel(l) returns the right level for all 7 levels. Also checked:
  - hardware LOD 3;
  - guest bias +1 and −1 → levels 4 and 2;
  - guest min LOD 5 and max LOD 1;
  - a non-mip filter → level 0;
  - NEAREST_MIPMAP_LINEAR at LOD 2.5 → alpha halfway between levels 2 and 3.
- **BC1/BC2/BC3 24×20 ×5 (NPOT; levels 12×10, 6×5, 3×2 and 1×1):** every level samples the block the RSX layout puts at the sampled texel.
- **BC2 and BC3 cubes 16×16 ×5:** all 6 faces × 5 levels. Negative control: a BC3 cube with the old stride (8 bytes/block) reads wrong faces.
- **Mode-2 partial update of a BC3 cube:**
  - one (face 2, level 3) change dirties only that subresource and records 1 copy;
  - afterwards all 30 subresources read their current colour.
  - Negative control: with nothing dirty (what the old rule decided), the GPU keeps sampling the stale level.

## 7. Performance results (offline, SYNTHETIC; `bench_tex_cache.c`; no FPS claims)

- **Setup:** 81 textures, 653 subresources, 18.5 MB of upload buffers. One resource and one buffer per texture in every arm, created once.
- **Pass:** each frame looks up every texture once. Writes go into write-combined memory.
- **Arms:** A = T115 `17b16cb` with mips on; B = `RSX_TEX_CACHE=1`; C = `=2`.

Each run is 201 frames. Run 1 is shown below; run 2 is in `logs/bench_tex_cache_run2.txt`.

| Workload | Arm | Median µs/frame | p95 | Max | Converted MB/frame | STALE lookups |
|---|---|---|---|---|---|---|
| static | A | 57 | 64 | 93 | 0 | 0 |
| static | B | 463 | 530 | 620 | 0 | 0 |
| static | C | 472 | 565 | 634 | 0 | 0 |
| animated (4 whole rewrites) | A | 65 | 77 | 211 | 0.19 | 0 |
| animated | B | 468 | 543 | 627 | 0.19 | 0 |
| animated | C | 477 | 658 | 914 | 0.19 | 0 |
| small (16 one-word writes) | A | 94 | 216 | 597 | 0.11 | **11,755** |
| small | B | 1830 | 3647 | 5196 | 3.57 | 0 |
| small | C | 1685 | 3635 | 5861 | 2.92 | 0 |

- **VERIFIED (synthetic):**
  - Exact validation costs about 0.46–0.58 ms (median, runs 1 and 2) per replay for 18 MB of texture source (about 30–40 GB/s here; the data may be partly cache-resident).
  - Arm A is cheap because it reads about 4 KiB per texture. With small writes it re-uploads 3.68 textures per frame where B re-uploads 14.66, so about 75% of the changed textures stay stale. A stale texture stays bound until a later write happens to hit a sampled word: 11,755 stale lookups over 201 frames.
- **Mode 2:** converts 18% fewer bytes in the small workload. Most bytes sit in single-subresource linear textures and in level 0, which is about 75% of a chain. The time gain is within noise: PARTIAL benefit.
- **HYPOTHESIS:** in-game validation cost is 0.5–2 ms per replay, and it multiplies with early replays (`vp_flush`). This needs runtime counters (`[tex-cache] hash_ms`).
- **Redundant work identified, not yet removed:**
  - every kept texture is re-hashed every replay;
  - a changed level 0 is re-converted whole for a one-texel change.
  - The next safe step needs write tracking (§4) or row-band dirty regions; neither is done.

## 8. Resource lifetime analysis

- **VERIFIED (pin `pin_sync` plus mutation):** `vp_upload_tex_slot` has exactly one call site. It runs in `render_frame`'s per-draw SRV loop, after the `rfp_at(RFP_GPU_DRAIN); wait_for_gpu();` at the top of `render_frame`. Every early replay goes through `render_frame` as well. The GPU is therefore idle when:
  - a slot's persistent upload buffer is rewritten (Map with an empty read range, partial or full);
  - a replaced resource and its buffer are released (recreate or level fallback).
- **VERIFIED by reading the code:**
  - Within one replay, only a slot with `used == 0` can be evicted, so no SRV written earlier in that replay names a released resource.
  - Per-draw SRV windows are rewritten every replay.
  - The RSXI capture reads slots only after its own `wait_for_gpu()`.
- **VERIFIED on WARP:**
  - A kept multi-level cube transitions ALL_SUBRESOURCES PSR→COPY_DEST, takes a copy of one subresource, and transitions back. The untouched subresources keep their contents.
  - The debug layer reports 0 errors.
- **Views:** the slot SRV covers `mp.levels`; per-draw views cover `rsx_texmip_view_levels` (T115, unchanged).
- **Render-target aliases:** zeta, RT-exact, screen-copy and sub-viewport sources are resolved *before* the upload path and are unchanged.
- **Synchronisation cost:** the texture path issues no GPU waits of its own.

## 9. Regression results

| Test | Result |
|---|---|
| `test_tex_cache` (new) | 63/63 |
| `test_t115b_warp` (new, WARP + debug layer) | 38/38 |
| `test_t115b_pins` (10 pins, 15 mutations) | 25/25 |
| `test_tex_mips` (T115) | 48/48 |
| `test_t115_warp` (T115) | 24/24 |
| `test_t115_pins` (T115; 3 pins re-pointed to the renamed calls, same checks) | 20/20 |
| T110 sampler tests: `test_sampler_xlate` 2199, `test_t110_warp` 88, `test_t110_pins` 27 | PASS |
| Renderer suite on the T115B tree (`logs/suite_t115b.txt`) | 35/35 PASS |
| Renderer suite on the T115 tree | identical on every inherited test; the 3 T115B-only entries are absent there |
| `rsx_d3d12_backend.c` TU, exact project line | rc 0. Warnings 2960 → 2999, no new warning class (`-Wunsafe-buffer-usage` +33, `-Wimplicit-int-float-conversion` +4, `-Wdeclaration-after-statement` +1, `-Wdeprecated-declarations` +1) |
| `audit_public.py --staged` | the same 25 inherited BLOCK items as T115/T109, none new |
| `audit_public.py --tree` on the changed files | passed |

Negative controls that are each caught:
- broken invalidation: the old rule, an empty dirty mask, `tc_dirty_ok = 1`, a dropped pitch key;
- broken mip offsets: T115's control;
- broken cube stride: the legacy BC3 stride;
- broken row pitch: the unpitched decode and upload;
- broken lifetime assumption: removing the drain fails `pin_sync`;
- broken hash: the step-sampling `tex_csum` fails the exhaustive check.

## 10. Integration requirements

- **VERIFIED (`git merge-tree`, read-only):** T115B merges textually clean with T113 `74fd084`, T116 `30b817b` and T111 `d2a65f9`.
  - T113 changes `rtrb_on` (3 lines) and `rsx_commands.c`.
  - T116 changes the shader/PSO paths (`vp_get_vs`, `vp_get_fp_pso`, init).
  - T111 does not touch `libs/video`.
  - None of them touches the texture upload code.
- **Semantic interaction with T113 (HYPOTHESIS, a reason to integrate):**
  - T113 makes CPU-read render-target writeback the default, which writes rendered pixels into guest memory.
  - A texture later bound at such an address through the upload path (no live RT match) changes in bulk or in part. The old rule can miss partial changes; `RSX_TEX_CACHE=1` cannot.
- **Plan (not executed; no merge authorized):**
  1. Integration branch from T113 `74fd084`.
  2. Cherry-pick T115 `17b16cb`, then T115B `65d2695`. Both apply without conflict per merge-tree.
  3. Run `run_suite_t115b.py` plus T113's `test_exposure_writeback`, `test_rt_readback` and `test_t113` pins on the result.
  4. TU-compile with the exact project line.
  5. T116 last, or independently: no overlapping hunks.
- T110 guest samplers and colour transfer, T113 composition, and presentation are unchanged. No shader, PSO, geometry or SPU code is touched.

## 11. Runtime validation plan (NOT RUN; needs authorization)

**Route:** garage, which is reproducible with correct visuals; race frames are still black or white.

**Fixed across arms:**
- the same build of the T115B tree;
- `RSX_TEX_MIPS=1`, `RSX_GUEST_SAMPLERS` as in T115 arm C;
- the T109/T106 SPURS defaults;
- the same input script and RSXI trigger frames (as in runs `20261023-205211` and `-220434`);
- a visible window (`present_diag` occlusion note).

**Arms:**

| Arm | Settings |
|---|---|
| A | `RSX_TEX_CACHE` unset (T115 path) |
| B | `RSX_TEX_CACHE=1` |
| C | `RSX_TEX_CACHE=2` |

Three runs each, in interleaved order.

**Measure:**
- `[rsx-frame-perf]` frame time: median, p95, worst;
- the FPF `tex_us` and `[tex-cache]` lines: hits, misses by cause, hash_ms, decode_ms, resident_mb, peak_mb, creates, evicts;
- RSXI `src=upload` per frame;
- D3D12 debug-layer errors (debug build run);
- texture correctness: compare RSXI frame dumps A vs B at the same frames.

**Expected:**
- B differs from A at least at the `0xA5` 1279×719 binding (sheared vs correct) and wherever a stale texture was being reused.
- **Pass criteria:**
  - no new debug-layer errors;
  - B's frame time within the measured `hash_ms`;
  - `miss changed` > 0 only where the guest wrote.
- **Rollback:** unset the switch.

## 12. Commit hashes

| Commit | Content |
|---|---|
| `65d2695` (T115B, `agent/t115b-texture-cache`) | `rsx_tex_cache.h`; changes to `rsx_tex_mips.h`, `rsx_d3d12_texmips.h` and `rsx_d3d12_backend.c`; tests `test_tex_cache.c`, `test_t115b_warp.c`, `bench_tex_cache.c`, `tools/test_t115b_pins.py`; T115 pins re-pointed. |
| `17b16cb` (T115) | Arm A base. |

Private tools and logs are under `generated/analysis/t115b/`:
- `tools/`: `patch_backend.py`, `patch_t115_pins.py`, `make_tu.py`, `tu_t115b.cmd`, `build_tests.cmd`, `run_suite_t115b.{py,cmd}`;
- `logs/`: `tu/`, `bin/`, `suite_t115b.txt`, `bench_tex_cache_run{1,2}.txt`, `audit_staged.txt`, `audit_tree.txt`;
- `audit_stage/`.

## 13. Remaining limitations

- Off by default; nothing has been measured in game (PARTIAL until the §11 A/B runs).
- Validation re-reads every kept texture every replay. Write tracking in the memory core would remove that; it is not done and needs runtime ownership.
- Mode 2's gain is small (−18% bytes converted in the small-update workload, time within noise). Sub-level (row-band) updates are not implemented.
- Interior row padding is hashed (spurious re-uploads possible); the last-row padding is not read.
- A texture rewritten between draws of one replay is uploaded once (pre-existing; snapshot mode covers video planes only).
- The level-fallback path (device refuses the chain) re-uploads every replay (pre-existing in T115, now counted under `miss shape`).
- The resident-memory counter counts upload-buffer bytes. The DEFAULT-heap texture allocation is similar but not reported by `GetResourceAllocationInfo`.
- Volume textures and linear compressed pitches other than the block row are not exercised (none in the garage captures).
- The `0xBA` float textures with padded pitch never reach the uploader in the garage captures (they resolve to `null_srv`/`rt_exact`), so their GPU path is untested.

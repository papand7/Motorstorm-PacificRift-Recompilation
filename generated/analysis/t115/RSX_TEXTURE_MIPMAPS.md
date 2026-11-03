# T115: RSX texture mipmaps, uploading and texture performance

Date 2026-10-27. Worktree `ps3recomp-t115`, branch `agent/t115-rsx-texture-mipmaps`. Commit **`17b16cb`**, not merged or pushed. No game build or launch.

## 1. Integration base and commits

- **Base:** `e3b961d`, the T110 tip. Chain: T94 `8ea1437` → T105 `36d0fb7` → T108 `6b1a7e4` → T110 (`3c1eb4d` samplers, `2692ec0`, `9ca3877`, `089d17a`, `e3b961d`).
  - VERIFIED: `git merge-base --is-ancestor` shows 3c1eb4d and T108 are in the base.
  - T113 (`19d6b6d`, the black-screen work) sits on top of T110 and is **not** included.
  - T109/T106 SPU work is not in this base. T115 touches no SPU code.
- **T115 commit:** `17b16cb`. One commit, all behind `RSX_TEX_MIPS=1`.
- **Other worktrees:** none touched. The T114 Phase 0 notes for the geometry worker are in `generated/analysis/t114/PHASE0_NOTES.md`.

## 2. Original texture pipeline (VERIFIED, code reading)

Bind, record, then replay:

1. **Bind:** `d3d12_bind_texture` stores `cur_texs[u]`: off/raw, w/h, fmt (LN/UN kept), `mips = format>>16`, cube = bit 2, pitch = CONTROL3, loc, filter/address/control0/border.
2. **Record:** each draw record copies `tex[u]`. `vp_record_tex_snap` optionally snapshots the guest bytes; by default only linear B8/G8B8 of 64 KB and up.
3. **Replay:** `render_frame` (after `wait_for_gpu()`) calls `vp_upload_tex_slot(off,w,h,fmt,cube,mips)` per unit. Inside it:
   - **Cache:** 96 slots. Key = bound offset + w/h/fmt/cube. `used` means already bound this frame. Otherwise a sparse FNV checksum (`tex_csum`, at most about 1024 samples) decides between re-upload and reuse.
   - **Layout and decode:** `rsx_texture_layout` (format class, swizzle, rows), then `rsx_texture_decode` (de-Morton, ARGB→RGBA, BE swap, DXT block-row copy) into a per-slot persistent UPLOAD buffer. One `CopyTextureRegion` per face, then barriers.
   - **Default SRV:** written at heap 1+slot.
4. **Per draw:** `srv_write_ex` writes the draw's own SRV (with the CONTROL1 remap). The sampler is fixed, or comes from `RSX_GUEST_SAMPLERS` (T110).
5. **Single level everywhere (VERIFIED):** the resource, the copy and both SRVs used **`MipLevels = 1`**. The only mip-aware code was the cube face stride.
6. **Shared helpers already existed:** `rsx_texture_mip_chain` and `rsx_texture_cube_face_stride` in `rsx_texture_layout.c`, used by the Vulkan, Metal and live-draw backends, but not by D3D12.

## 3. RSX format compatibility matrix (D3D12 VP path)

| Guest format (base = fmt & 0x9F) | Host | Single level | Mip chain (T115) |
|---|---|---|---|
| 0x85 A8R8G8B8, swizzled or linear | RGBA8 | VERIFIED (earlier screens) | **VERIFIED**: offline per-texel, all levels; WARP 64² ×7 |
| 0x86 DXT1 | BC1, block copy | VERIFIED | **VERIFIED**: offline layout; WARP 64² ×7 down to the 1×1 one-block level |
| 0x87 DXT23 / 0x88 DXT45 | BC2 / BC3 | VERIFIED (T107, BC3 artwork) | **PARTIAL**: offline layout and per-block decode; no GPU sample |
| Cube (bit 2) | 6-slice TextureCube | PARTIAL: old stride wrong for DXT23/45 cubes | **VERIFIED** for A8R8G8B8 (WARP, 6 faces × 5 levels); DXT1 stride equals the old one |
| 0x81 B8 | R8 (RRRR) | VERIFIED (T107 text) | PARTIAL: generic layout, no fixture |
| 0x8B G8B8, 0x8C/0x8D HILO | R8G8 (HILO_S8 read as unorm) | PARTIAL | PARTIAL |
| 0x82/83/84/97/9D packed 16-bit | unpacked to RGBA8 | PARTIAL | PARTIAL |
| 0x9E D8R8G8B8 | RGBA8, alpha forced to 1 | PARTIAL | PARTIAL |
| Depth/float (X16, Y16_X16, *_FLOAT, X32, DEPTH24_D8) | R16 / R16G16 / F16 / F32 | PARTIAL | PARTIAL; depth-compared units view level 0 only |
| Linear with CONTROL3 pitch ≠ packed row | rows read as packed | **PARTIAL**: the D3D12 uploader never passes the pitch (pre-existing). The T107 artwork's pitch 5120 equals the packed width, so it is unaffected | Levels below 0 are packed at their own width (shared helper). Whether RSX keeps the level-0 pitch for linear levels is a HYPOTHESIS. No multi-level linear texture appears in the captures |
| Volume / 3D | none | UNSUPPORTED: TEXTURE2D only | UNSUPPORTED |
| Any other byte | R8 fallback | UNSUPPORTED | UNSUPPORTED |

## 4. Mip-chain layout findings

**Captured data (VERIFIED, garage RSXI captures `runs/20261023-205211-…` and `-220434-…`):**
- 26.7–31.4% of bindings advertise more than 1 level: 12,305 bindings.
- Levels advertised: 9 (×7573), 10 (×3486), 11 (×1183), 8, 12, 13, 3.
- **Only swizzled 2D/cube formats carry chains:**
  - 0x86 DXT1: 11,270, including the 256² ×9 cubes;
  - 0x88 DXT45: 893;
  - 0x87 DXT23: 132;
  - 0x85: 10.
- Every linear (0x20) texture has 1 level.

**Layout used (shared helper; matches the layout the Vulkan and Metal backends already use):**
- levels are packed back to back, each at its own width, with no per-level alignment;
- compressed levels are counted in 4×4 blocks, with a minimum of one block;
- swizzled levels are each Morton-ordered within themselves;
- each cube face is a complete chain, 128-byte aligned;
- the count is clamped to the halvings down to 1×1, and 0 is read as 1.

**Bug found (VERIFIED offline):** the old D3D12 cube stride used 8 B per block for every compressed format. That is half the RSX stride for DXT23/45 cubes, so faces 1–5 read the wrong data. The captured cubes are all DXT1, where the result is identical, so no captured texture was affected. With the switch on, the shared stride is used.

## 5. Implemented decoding changes

- Only a new header, `libs/video/rsx_tex_mips.h`. `rsx_texture_layout.c` is unchanged.
- **Switch:** `rsx_texmip_mode_parse` accepts exactly "1".
- **`rsx_texmip_plan_make`:**
  - levels, the guest span of face 0, the face stride, and clamped/refused flags;
  - switch off gives 1 level plus the old span and the old cube stride (kept verbatim as `rsx_texmip_legacy_cube_stride`);
  - a chain past 4 GB keeps level 0 (fail closed);
  - no levels are generated.
- **`rsx_texmip_view_levels`:** the whole chain only if min filter (`FILTER[18:16]`) ≥ 3 and the unit is not depth-compared; otherwise level 0. RSX samples level 0 for a non-mip filter.

## 6. D3D12 resource and upload changes (`rsx_d3d12_backend.c`, `rsx_d3d12_texmips.h`)

1. **Resource:** `td.MipLevels = mp.levels`.
2. **Footprints:** come from `GetCopyableFootprints`, which supplies the row pitch, the 512-B placement and the one-block rounding of BC levels below 4×4. Each level's decoded row and row count are checked against its footprint.
3. **Upload:** the buffer is sized from the footprint total. It stays persistent per slot, as before.
4. **Fill and copy:** `rsx_texture_decode` fills every level and face; then one `CopyTextureRegion` per subresource (`mip + face*levels`).
5. **Barriers and lifetime:** barriers are unchanged (ALL_SUBRESOURCES). The upload still happens during replay, after `wait_for_gpu()`, and a slot used this frame is never re-uploaded, so it gets the same lifetime guarantees as before.
6. **Fallback:** if the footprint or the resource is refused, the texture drops to level 0, counted as `create_fallback`. A texture is never dropped.
7. **SRVs:** the slot SRV covers all levels. The per-draw SRV uses `srv_write_lv(..., rsx_texmip_view_levels(...))`.
8. **Counters:** `[tex-mips] uploads multi levels src_mb clamped refused create_fallback views full/level0`, printed at the 1st, 2nd, 4th … multi-level upload only.

## 7. Sampler compatibility (T110 guest samplers)

VERIFIED on WARP, through the backend's mapping (pinned: `gs_xl_desc` equals the test's `xl_desc`):
- NEAREST_MIPMAP_NEAREST with derivative LOD 3 selects level 3;
- guest bias +1/−1 (`FILTER[12:0]`, s4.8) selects level 4/2;
- `CONTROL0` min LOD 5 selects 5, and max LOD 1 selects 1 (4.8 fixed point, /256; same as RPCS3 `decode_fxp<4,8>`);
- NEAREST_MIPMAP_LINEAR at LOD 2.5 blends levels 2 and 3, within ±2/255;
- a non-mip min filter gives level 0 at LOD 3.

**Without `RSX_GUEST_SAMPLERS`:** the fixed samplers are MIN_MAG_MIP_LINEAR with MaxLOD = ∞ (unit 0 is POINT), so a mip-filtered unit then samples the chain trilinearly regardless of the guest's mip mode or LOD range. The view policy still keeps non-mip units on level 0. Arm C (below) is the faithful configuration.

**Not tested:** anisotropy (mapped by T110; not exercised here), border, and the convolution filter (treated as linear, as in T110).

## 8. Texture-cache correctness

- **Key:** bound offset, w, h, full fmt byte (LN/UN), cube, and now the level count. A level-count change recreates the slot's resource. Sampler state is correctly not part of the key, and the CONTROL1 remap is applied per draw in the SRV. Pitch and location are not in the key (pre-existing; PARTIAL).
- **Invalidation:**
  - The sparse checksum now spans the whole uploaded chain, and so does the draw-time snapshot (`tex_src_span`). A snapshot of the wrong size misses and falls back to live memory, as before.
  - PARTIAL (pre-existing, probabilistic): about 1024 samples over the span. Level 0 is about 75% of a chain, so a change confined to small levels is caught only if a sample lands in it. An SPU-written or streaming texture whose changes fall between samples is still reused stale; this is unchanged from the base.
- **Render-to-texture:** RT and zeta sources are resolved before the upload path (`tex_rt`, `tex_zeta`) and are unchanged. RT-pool views stay single-level.
- **Lifetime:** unchanged (see §6).

## 9. Performance measurements (SYNTHETIC; `bench_tex_mips`, Ryzen host, write-combined destination; `logs/bench_tex_mips.txt`)

80-texture set shaped after the garage captures; 62 of them have chains. 3 runs × 41 passes:

| | median µs | p95 µs | max µs | written MB |
|---|---|---|---|---|
| A miss, single level | 4014 / 4185 / 4061 | 5110–5558 | 5927–6192 | 13.76 |
| B miss, chain | 4136 / 4296 / 4409 | 5565–5681 | 5942–6676 | 15.03 (+9%) |
| A hit, checksum | 58.5–61.5 | 62–69 | 65–80 | 0 |
| B hit, checksum | 59.2–60.1 | 70–72 | 80–116 | 0 |

- **Cost of correctness:** about 3–9% more CPU on a full re-upload, and 1.063× the guest bytes read. In this set, chain textures are small next to the single-level screen-sized ones. Each DXT chain adds 33% over its own level 0.
- **Cache hits:** the per-frame cost of a cached texture is unchanged.
- **GPU side:** upload time and GPU memory were not measured on real hardware. Each chain adds about 1/3 of its level 0 in VRAM. No FPS claim.
- **Phase 6 optimizations:** not started. They come after runtime validation of correctness.

## 10. HD texture / mod compatibility (design only; T111 owns the modding framework, and none of its files were touched)

- An override can enter after `rsx_texmip_plan_make`, by replacing the plan, the source and the DXGI format.
  - It must keep the original key: bound offset, w/h/fmt, levels.
  - It must supply its own complete chain (DDS) or explicitly request generated mips for the mod asset only.
- BC7 needs a new `dxfmt` case. The footprint code is format-agnostic through `GetCopyableFootprints`.
- Budget and fallback: if the override fails to load or exceeds its budget, the original guest path is used unchanged.
- Original textures never get generated mips (VERIFIED by design: the plan only clamps).

## 11. Regression tests

All results are in `logs/`. The suite is `tools/run_suite_t115.cmd ps3recomp-t110 ps3recomp-t115` → `logs/suite_t115.txt`.

- **`libs/video/tests/test_tex_mips.c`: 48 checks, 0 failures.**
  - Switch off: 33,792 plans equal the old uploader (all 256 format bytes × 11 sizes × 6 counts × cube).
  - Layouts of 14 chains, the clamp, count 0, cube strides including the DXT23/45 bug, and 4 GB bounds.
  - Per-texel decode of swizzled A8R8G8B8 chains (16×8, 128², 4×32) and per-block decode of DXT45 chains.
  - The view policy.
  - Negative controls, all caught: level-0 pitch on every level, 128-aligned levels, no block minimum, swizzled levels read linearly.
- **`libs/video/tests/test_t115_warp.c`: 24 checks, 0 failures**, on WARP with the debug layer on and 0 debug-layer errors. Includes negative controls: 128-aligned offsets sample wrong levels, and the old single-level resource returns level 0 for levels 1–6.
- **`tools/test_t115_pins.py`: 7 pins and 13 mutations, 0 failures.**
- **Suite:**
  - T115 tree: 31/31 PASS.
  - Base tree: identical on every inherited test. The new T115 tests are absent from the base, so it shows 2 FAIL and 1 ABSENT for them.
  - `test_t110_pins` still passes on T115.
- **TU compile:** `rsx_d3d12_backend.c` with the exact project line (`tools/tu_t115.cmd`, from T110 / `build.ninja`) gives rc 0 for both base and T115. Warnings 2929 → 2960; no new warning class (`logs/tu/*/classes.txt`).

## 12. WARP pixel results

The read-back colour identifies the level the GPU sampled:

| Case | Expected | Result |
|---|---|---|
| SampleLevel(l), l = 0..6 | colour of level l | 0..6 ✔ for both 0x85 and DXT1 |
| Hardware LOD | 3 | 3 ✔ |
| Bias +1 / −1 | 4 / 2 | 4 / 2 ✔ |
| Min LOD 5 / max LOD 1 | 5 / 1 | 5 / 1 ✔ |
| Non-mip filter | level 0 | level 0 ✔ |
| Mip-linear at LOD 2.5 | (L2 + L3) / 2 | ✔ |
| Cube | 30 face × level colours | 30 ✔ |

## 13. Runtime validation plan (NOT run; needs explicit authorization)

- **Exe and route:** one exe built from `17b16cb` (plus the T109 SPU commits if the integrator wants the T106 frame rate). The T106 runner (`t106/ab/run_ab.py` pattern): a fresh hash-manifested HDD, the T105 controller route, stop at race entry + 90 s.
- **Common env for every arm:** `RSX_FRAME_PERF=12,10`.
- **Hold identical across arms:** SPURS, AOT, VP/geometry and PSO settings.

| Arm | Env |
|---|---|
| A | none |
| B | `RSX_TEX_MIPS=1` |
| C | B + `RSX_GUEST_SAMPLERS=15` |
| D | C + any later cache optimization (none exists yet) |

Run order A, B, C, C, B, A.

- **Checks:**
  - race entry, and `[present_diag]` successes (keep the window visible);
  - the `[tex-mips]` totals: `create_fallback` should be 0, `refused` 0, and `views full` > 0;
  - `[samplers]` heap overflow;
  - debug layer off;
  - `tex_ms` and `frame` from `[rsx-frame-perf]`;
  - process VRAM (DXGI QueryVideoMemoryInfo, or Task Manager dedicated);
  - garage frame dumps for distant-surface aliasing, compared A vs C.
- The black/white race display is unresolved (T113), so race frames cannot validate texture appearance. Use garage and loading frames.

## 14. Public-source audit

- `python ../tools/audit_public.py --staged` in the worktree reports the 25 BLOCK items inherited from the base tree, the same count recorded for T109. None concerns a T115 file (`logs/audit_staged.txt`).
- `--tree` on a copy of the 7 changed files (`audit_stage/`) passes (`logs/audit_tree.txt`).

## 15. Known limitations

- **Linear pitch:** a linear texture's CONTROL3 pitch is still ignored by the D3D12 uploader (pre-existing). The lower-level pitch rule for linear chains is a HYPOTHESIS.
- **Formats:** volume/3D textures are unsupported. HILO_S8 sign is unsupported.
- **Cache:** the checksum is sparse, so dynamic textures can be reused stale (pre-existing).
- **Fixed samplers:** without `RSX_GUEST_SAMPLERS` they ignore the guest mip mode and LOD range on mip-filtered units.
- **Coverage gaps:** BC2/BC3 chains are not GPU-sampled in a fixture, and anisotropy and border with mips are untested.
- **Not measured:** GPU upload cost, VRAM and FPS.
- **Opt-in:** all of it is behind `RSX_TEX_MIPS=1`. It is off by default because it is not validated at runtime.

## 16. Commit hashes and commands

- `17b16cb` (ps3recomp-t115). Base `e3b961d`.

```
cmd /c generated\analysis\t115\tools\build_warp.cmd          (test_tex_mips + test_t115_warp)
cmd /c generated\analysis\t115\tools\run_suite_t115.cmd ps3recomp-t110 ps3recomp-t115
py -3 generated\analysis\t115\tools\make_tu.py && cmd /c generated\analysis\t115\tools\tu_t115.cmd
py -3 ps3recomp-t115\tools\test_t115_pins.py
clang -std=gnu17 -O2 -I libs/video -I include libs/video/tests/bench_tex_mips.c libs/video/rsx_texture_layout.c   (in ps3recomp-t115)
```

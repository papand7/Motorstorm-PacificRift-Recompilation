# T163 â€” character rendering and texture fidelity

Worktree `ps3recomp-t163`, branch `agent/t163-character-rendering`, base `59fcab5` (the T155/T157 renderer
line, same base as T162). Offline only: no game build, no game launch. Existing captures were the only
runtime evidence.

## 1. Character rendering architecture

| Stage | Where | Evidence | Label |
|---|---|---|---|
| Animation, skeleton, ragdoll | PPU, Havok Animation/Behavior (`hkSkeleton`, `hkxSkinBinding`, `hkbCharacterBoneInfo`, `numBonesPerVertex`, `ragdollToAnimationSkeletonMapper` strings in `EBOOT.elf`) | string scan | VERIFIED that Havok is linked. Whether Havok jobs run on SPU: HYPOTHESIS, unchecked |
| Matrix palette upload | PPU â†’ RSX vertex constants: 4 rows per bone from c[64] (3 rotation rows + translation row, w = 0/0/0/1) | garage draw op 448, frame 1740, `vp_consts` 64..89 | VERIFIED |
| Skinning | **RSX vertex program**, not PPU/SPU | below | VERIFIED (garage) |
| Race rider path | not captured: race captures contain only one indexed VP (`158A5048`), a single `a0.x` table lookup after `o[0]`, not skinning | `scan_vp_skinning_t163.py` | PARTIAL |

The garage skinned VPs are `81429E77`, `EF8280B7` and `F2ECC442` (24 captures each, garage-display-path run):
- v7 = bone indices: `floor(v7.xyz * c467.y) * c467.z`, then `ARL a0.xyz`;
- v0 = position: row k of `c[64+a0.b]..c[66+a0.b]` Ã— `pos[k]`, plus `c[67+a0.b]` Ã— `pos.w`;
- v1.xy = two weights, the third is `c467.x âˆ’ w0 âˆ’ w1`;
- v2 = normal and v9 = tangent, multiplied by the rotation rows only, then `rsqrt`-normalised;
- skinned â†’ c[256..259] (model) â†’ c[0..3] / c[4..7] (view-projection) â†’ `o[0]`.

No SPU skinning (Edge Geometry or similar) appeared: no SPU image has skinning strings.
The SPU scan covered `generated/spu_raw` only, so this is a HYPOTHESIS for other SPU images.

## 2. Defects found

| # | Class | Finding | Label |
|---|---|---|---|
| D1 | 1 Geometry / vertex decoding | `rsx_fetch_attrib` (the D3D12 backend's fetch) fills components an enabled array does not supply (size < 4) from the constant attribute register. `rsx_vertex_decode_element` (the compact path in the same repo) and RPCS3's `RSXVertexFetch.glsl` use (0,0,0,1). The skin VP reads `pos.w` for the translation row, so a size-3 position takes its w from the register. | Divergence VERIFIED. Visible effect: HYPOTHESIS. It needs the register for attr0 to have w â‰  1, and no capture records attribute formats or `vertex_data4f`. |
| â€” | 2 Skinning | ARL floor, relative reads `(base + aN.c) & 511` with addr_swz/addr_reg_sel, palette row order, 3-weight blend, normal transform: all match an independent reference. | VERIFIED no defect (test) |
| â€” | 1 Bone-index precision | UB `k/255` scaled back Ã—255 in float32 floors to k for all 256 k. S1 `x/32767` round-trips exactly. | VERIFIED no defect |
| â€” | 4 Shader translation | VEC+SCA same-instruction hazard (SCA reading the temp the VEC half just wrote): 0 candidates in the 49 unique captured VPs. RPCS3 also emits them in sequence. | VERIFIED absent in captures |
| â€” | 3/5/6 Texture, material, transparency | The rider in the T16 garage capture (`introskip/t16_view/f002064_bb.png`) has coherent geometry: no spikes, collapsed limbs or stretched triangles. The frame is too dark and old (pre-T147 exposure fixes) to judge textures, lighting or alpha. | Not evaluable; no defect claimed |

Semantic differences from RPCS3. These are not changed: RPCS3 is not hardware proof, and none of them is shown
to affect characters.
- **ARL target register.** Ours writes `a[D0.addr_reg_sel]`; RPCS3 writes `a[D0.dst_tmp]`.
  - They agree whenever an ARL's two fields match.
  - The captured skin VP reads the register it loaded, so the game agrees in practice (HYPOTHESIS).
- **ARL conversion.** Ours uses floor (NV_vertex_program); RPCS3 uses an int cast, which truncates.
  - They differ only for negative fractional indices.
- **S1 decode.** Ours is `x/32767`; RPCS3 is `(x+0.5)/32767.5`.
- **CMP decode.** Ours is `x/1023`, `z/511`; RPCS3 is `(x<<5)/32767`.
  - Both differences are below 1e-3 relative.
- **Non-indexed constant reads at 468 and above.** RPCS3 returns 0; ours reads the 512-entry cbuffer.

## 3. Correction implemented

`6fbbc05` (ps3recomp, `agent/t163-character-rendering`):
- `RSX_VTX_PARTIAL_0001=1` (opt-in; only the exact value `1` enables it) makes `rsx_fetch_attrib` fill the
  unsupplied components with (0,0,0,1). It is a shared layer (D3D12, Vulkan, Metal, null backends), not
  character-specific.
- Disabled arrays still read the register in both modes. The default is unchanged.

## 4. Tests

| Test | Result |
|---|---|
| `tools/test_t163_vp_skinning.py` (new): synthetic NV40 palette program â†’ `rsx_vp_decompile` â†’ `vp_eval` on the CPU vs a pure-Python reference; a0 and a1; indices UB256 and UBÃ—255; 48 vertices Ã— 100 bones per case | 16/16 PASS; max error 0 (position), 1.1e-16 (normal) |
| Negative control: decompiler with `addr_swz` forced to 0 | 4 FAIL as expected (position error 2.6); file restored byte-identical (sha `4e1cf185â€¦` = base) |
| `tools/test_t163_partial_fill.py` + `libs/video/tests/test_t163_partial_fill.c` (new): 6 types Ã— sizes 1â€“4 Ã— 4 vertices; unset / `=1` / `=2` | 3/3 PASS: default = register fill, opt-in = compact decoder bit-for-bit |
| `test_vp_branch_base`, `test_vp_expand`, `test_vp_fetch_plan`, `test_vp_fallback`, `test_vp_flush`, `test_t101_pins` | PASS |
| `test_rsx_immediate_vertices` | SKIP (POSIX fixture) |
| `test_d3d12_shader_cache` | flaky: T163 5 runs gave 2 PASS / 3 FAIL with no message; base `59fcab5` PASS. It compiles only `rsx_fp/vp_decompiler.c` + its test, all byte-identical to base, so not T163 (same WARP flakiness seen in T148). |
| `audit_public.py --staged` | 25 BLOCKs, all on already-tracked SPU test outputs and `scratch/`. None on T163 files. |

Logs: `generated/analysis/t163/logs/`.
Analysis tools (root, untracked scope `t163/tools/*.py`):
- `scan_vp_skinning_t163.py`: ARL and relative-read census of captured VPs;
- `scan_vp_dualissue_t163.py`: VECâ†’SCA hazard scan.

## 5. Remaining issues

- No capture records vertex attribute formats or `vertex_data4f`, so D1's impact on MotorStorm is unproven.
  The capture's `vp_consts` list also stops at 64 entries, so c467 (index scale and rows per bone) is unknown.
- No VP microcode is captured (HLSL only). ARL `dst_tmp` versus `addr_reg_sel` cannot be checked against the
  game's programs.
- No race-scene rider capture, so the race skinning path is unconfirmed.
- Texture, material and alpha fidelity for riders need a current, correctly exposed garage or race capture.

## 6. Proposed runtime validation (needs authorisation)

1. Bounded garage capture with RSXI. For the draws using VP `81429E77`/`EF8280B7`/`F2ECC442`, log:
   - attr 0/1/2/7/8/9 type, size and stride;
   - `vertex_data4f[0]`;
   - c464â€“c467 (extend `vp_consts` past 64 entries);
   - the VP ucode words of every ARL.
2. If attr0 has size 3 and register w â‰  1, A/B the garage with `RSX_VTX_PARTIAL_0001=1` and compare the
   rider's silhouette and position (crop the rider; frames aren't byte-deterministic).
3. A race capture with riders in view, to find the race skin VPs and rerun `scan_vp_skinning_t163.py`.
4. Only after 1â€“2 show a visible difference, propose `RSX_VTX_PARTIAL_0001` as the default.

## 7. Commits

| Repo | Commit | Content |
|---|---|---|
| ps3recomp `agent/t163-character-rendering` | `6fbbc05` | opt-in fill, two new tests, C fixture |
| root | `46508ca` | report + `t163/tools/*.py` |

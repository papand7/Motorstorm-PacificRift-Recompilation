# T162: vehicle rendering and texture fidelity (offline)

2026-10-30. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. Offline only: no game launch, no full build, nothing merged or pushed.

Owner check: `ListAgents` showed 3 peers, and there was no `t162` branch, worktree or report. T162 was claimed with:
- worktree `ps3recomp-t162`, branch `agent/t162-vehicle-rendering`, from T157 `59fcab5` (the renderer the game runs). T147's visual integration `d76e08e` is **not** an ancestor of it;
- this directory.

T142, T144, T159 and the Vulkan tree were not touched.

## 1. Answer

1. **No existing capture shows a vehicle (VERIFIED, BLOCKED for per-draw vehicle work).**
   - The garage capture `runs/20261025-102805-garage-capture-probe` is the rider-select view: rider, dome, UI.
   - The race RSXI sets (T145 A1/B1/D1, T113 G/I) record 22–24 draws of the start flyover.
   - T153 already noted "no vehicle is in view".
   - No vehicle draw, sub-mesh or vehicle texture can be named from data.
2. **What could be established: the lit-material pipeline that vehicles share.** It was traced from the captures (§2) and checked against the RSX semantics. The garage rider and the race programs use the same material family:
   - DXT diffuse on unit 0;
   - a 256²×9 DXT1 environment cube on unit 14, read with **`TXL` at a LOD the program computes** (gloss);
   - a 32² irradiance cube on unit 15;
   - a D24 shadow map with depth compare on unit 13;
   - LUTs on units 10–12;
   - 3 colour exports (colour, motion vectors, a third target).
3. **Three default-renderer departures from the guest's state affect exactly these materials (VERIFIED state mismatch; the visual effect on a vehicle is HYPOTHESIS until a capture shows one).**

   | # | Defect in the default renderer | Evidence | Existing fix (opt-in) |
   |---|---|---|---|
   | D1 | **Env reflection LOD is lost.** The material programs ask for level *n* of the 9-level env cube; the default uploads 1 level, so every reflection is mirror-sharp whatever the material's gloss | 17 garage and 26 race programs use `TXL` on unit 14 (all 26 race `TXL`s) (`SampleLevel(rsx_samp[14], …, h.w)`). Reproduced on WARP: LOD 1..8 all read level 0 (§4, `test_t162_vehicle_reflection`) | `RSX_TEX_MIPS=1` (T115), verified here end to end for the DXT1 cube + decompiled `TXL` |
   | D2 | **Unit-0 diffuse is point-sampled and clamped.** The guest asks for `LINEAR_MIPMAP_NEAREST`, wrap/wrap, bias −0.80, with 7–11 levels. Effect: blocky magnified texels, aliasing, and tiling UVs clamped to the edge (stretched streaks) | race lit-material draws: unit 0 34/34 wrap + mip filter (`material_state_t162.py`) | `RSX_GUEST_SAMPLERS=15` (T110) + `RSX_TEX_MIPS=1` |
   | D3 | **sRGB textures are lit in gamma space.** Units 0, 2, 14 and 15 carry gamma mask 7 | as T145 | `RSX_COLOR_XFER=7` (T145) |

   All three fixes exist in `ps3recomp-t162` and are off by default. None is in the T153/T157 benchmark preset. None has ever been run in game together.
4. **One new decoder defect was fixed: `SRC2.abs` (DWORD3 bit 18) was dropped** (VERIFIED from the ISA layout and a negative control).
   - It affects MAD/LRP/DP2A with |src2|.
   - The race corpus has **0** uses (151 programs), so all 151 decompile byte-identically before and after (2D and cube-mask forms). The change is default-on, and the captured output is unchanged.
5. **No arbitrary colour, UV, material or geometry change was made.** No default renderer behaviour changed for any captured program.

## 2. Lit-material pipeline (from captures)

**Garage:** `runs/20261025-102805-garage-capture-probe/rsxi`, exe `motorstorm-int-nm-307b08a`, 4 frames, 619–637 draws each. **Race:** `t145/ab/runtime-D1-20261028-183730/rsxi` (exe `f7f9366`, 151 fragment ucode dumps) and `t113/runtime-I-…`.

| Item | Observed | Status |
|---|---|---|
| Programs | Garage: the `0x04D7…`–`0x04D8…`, `0x0647…`, `0x0649…`, `0x0673…`, `0x067F…`, `0x0681…` and `0x06FE…` families, 31 MRT programs. Race: `0x070B0701`, `0x07200641`, `0x02B9EF81` with cubes bound, plus `0x070C…`/`0x070D…`/`0x070F…`/`0x0710…`/`0x07B5…` with `TXL` on unit 14 | VERIFIED |
| Unit 0 | DXT1/DXT3/DXT5/A8R8G8B8, 7–11 levels, `L_MIP_N`, wrap, bias −0.80, sRGB on DXT3 | VERIFIED (race) |
| Units 2–3 | DXT1 10–11 levels (detail and normal/spec), same sampler | VERIFIED |
| Unit 13 | `0xB0` D24, 1024×2048 shadow map, depth compare (`compare 6`). Garage: 198 null SRVs only while `0x06FF0000` is itself the depth target (the shadow pass, so no self-read). Off-pass draws read it as `zeta` | VERIFIED |
| Unit 14 | DXT1 cube 256², 9 levels, `L_MIP_N`, clamp, sRGB; read by `TXL` with a LOD from the program | VERIFIED |
| Unit 15 | DXT1 cube 32², 1 level (irradiance), `TEX` | VERIFIED |
| Units 10–12 | `0xBA` fp16 LUT 4×1, `0xB4` X16 256×1 (crossbar `0x02EE` → `(0,0,0,X)`), `0x9F` Y16X16F 32×512 (`0x29E4` → `(X,Y,0,1)`) | VERIFIED |
| Remaps | `0xAAE4` identity, `0x56FF` B8→`(1,1,1,B)`, `0xA9FF` B8→`(B,B,B,1)`, `0x29E4`, `0x02EE`; all decode as the crossbar encodes them (`rsx_texture_component_remap`) | VERIFIED |
| Formats | 0x81, 0x85, 0x86, 0x87, 0x88, 0x9F, 0xA1, 0xA5, 0xA8, 0xB0, 0xB4, 0xBA, 0xBF. **None refused** by `VP_TEX_FMT_OK`. No HILO8 normal maps. DXT cubes are all DXT1, so the legacy DXT3/5 cube-stride bug is not hit | VERIFIED |
| MRT1 `0x01650000` | Motion vectors: program `0x04D7D4C1` writes `(pos − prev_pos)` packed. All zero in the static garage camera, which is correct | VERIFIED |
| Fragment opcodes (race) | 0 unhandled. `abs` on SRC0/SRC1/SRC2: 0 uses. 26 TXL, 2 TXB, 29 KIL, 50 result-scale | VERIFIED |
| RSXI `fp_*.hlsl` dumps show cube units as `rsx_tex[14]…xy` | These come from a generic decompile without the cube mask (`rsx_d3d12_backend.c:8048`); the PSO path passes `dr_cube_mask` | VERIFIED (dump artefact, not a defect) |

Areas the brief lists that these captures cannot settle:
- vehicle geometry and sub-meshes, LOD transitions, vertex attributes, vehicle UVs;
- render-target feedback on vehicles, alpha on vehicle glass and decals.

These are **BLOCKED** until a capture contains vehicles.

## 3. Root causes and corrections

| Item | Layer | Root cause | Correction | Status |
|---|---|---|---|---|
| D1 reflection LOD | texture upload | default `MipLevels = 1` (T110 D2); `TXL` LOD clamps to 0 | `RSX_TEX_MIPS=1` (existing, T115). Not changed here; verified for this exact path (§4) | fix VERIFIED offline; game BLOCKED (needs approval) |
| D2 unit-0 sampler | sampler | `gs_fixed_desc` unit 0 = point/clamp, used whenever `RSX_GUEST_SAMPLERS` is unset | `RSX_GUEST_SAMPLERS=15` (existing, T110). Unchanged | VERIFIED offline (T110/T115); game BLOCKED |
| D3 gamma | shader / texture | sRGB fetch and export ignored by default | `RSX_COLOR_XFER=7` (existing, T145) | VERIFIED offline (T145); game BLOCKED |
| D4 `SRC2.abs` | FP decoder | `decode_src(w3, 0, …)` | `decode_src(w3, w3 & FP_SRC2_ABS, …)`, default-on: an ISA decode, not a heuristic; captured output unchanged | **fixed, VERIFIED offline** |

**Not changed, and why:**
- **The default mips, samplers and gamma.** Making them default needs a game A/B ("no unverified default changes"). T147 integrated them but its garage/race A/B never ran.
- **Whether RSX adds the `FILTER` LOD bias to a `TXL` LOD.** Not established. The env-cube unit's bias is 0 in every capture, so it does not matter here.

## 4. Offline tests (`ps3recomp-t162`; `generated/analysis/t162/tools/build_t162.cmd`)

| Test | Result |
|---|---|
| `libs/video/tests/test_t162_fp_src2_abs.c` (CPU; synthetic NV40 programs) | **9/9 pass.** Negative control: the same test against `59fcab5`'s decoder fails 3/9 (`MAD \|src2\|`, `MAD −\|src2\|`, `LRP \|src2\|`) |
| `libs/video/tests/test_t162_vehicle_reflection.c` (WARP, D3D12 debug layer on). Synthetic `TXL R0, f[TEX0], {lod}, TEX14` through `rsx_fp_decompile_ex` with cube mask `1<<14`. DXT1 256²×9 cube built from the RSX layout (stride 43,776). Uploaded via `rsx_texmip_plan_make` / `rsx_d3d12_texmip_*`. Captured guest sampler words | **13/13 pass:** TextureCube decl + `.xyz` `SampleLevel`; `RSX_TEX_MIPS=1` reads level *l* at LOD *l* on all 6 faces (fixed and guest sampler); guest `L_MIP_N` at LOD 2.25 reads level 2 alone while the fixed trilinear sampler blends 2/3; **default (1 level): LOD 1–8 read level 0 on 48/48 samples**; 0 debug-layer errors |
| Corpus: `tools/fp_corpus_t162.c` over the 151 race ucode dumps, old vs new decoder, `rsx_fp_decompile` and `_ex(0xC000)` | **151/151 byte-identical**, 0 failed decompiles (`logs/corpus_*.txt`, private) |
| Full suite `tools/run_all_t162.cmd --jobs 6 ps3recomp-t162` | see §7 |
| `tools/audit_public.py --staged` (ps3recomp commit) | see §7 |

## 5. Remaining limitations

- **No vehicle has been observed (BLOCKED).** D1–D3 are verified as state mismatches on the materials vehicles share, not as pixels on a vehicle.
- **The shadow map and depth compare (unit 13) are not audited at pixel level.** The garage floor is black in the old capture (`img/g_rt0075_x4.png`). Its cause is unknown (HYPOTHESIS: exposure, as T105, or shadowing).
- **Cube `TXP` ignores the sign of w** (`rsx_fp_decompiler.c:1169`). It only differs from RSX for w < 0. No captured cube fetch uses `TXP` (all `TXL`/`TEX`). Not changed.
- **`RSX_GUEST_SAMPLERS` ignores anisotropy when the mip filter is NEAREST** (T110 D8). The lit materials use `L_MIP_N` with anisotropy field 0, so they are not affected.
- **T147's integrated visual branch is not under T157/T162.** Its runtime-unverified switches would be validated on this branch's exe instead.

## 6. Proposed runtime validation (NOT AUTHORISED; needs explicit approval)

| Item | Proposal |
|---|---|
| exe | a new build of `agent/t162-vehicle-rendering`. That is T157 `c535cc0`/`59fcab5` + `SRC2.abs`; it would get a new sha256. **Not built** (no full build in T162) |
| arms | A = the T157 benchmark env. V = A + `RSX_TEX_MIPS=1 RSX_GUEST_SAMPLERS=15 RSX_COLOR_XFER=7` |
| scenes | (1) Garage **vehicle select**: one RSXI capture (`RSXI_SNAP=targets`, ~4 frames), plus `RSXI_SNAP=passes` with ucode. (2) Race at race-entry + 40 s, camera behind the player vehicle. Same frame indices in both arms |
| order | A → V → A → V, 4 launches |
| pass criteria | 0 debug-layer errors. Vehicle reflections show gloss-dependent blur in V. Unit-0 texture tiling continuous, with no clamp streaks. Overlay text identical. FPS within A's spread (HYPOTHESIS: mip chains add about a third to texture upload bytes) |
| data kept | private under `generated/analysis/t162/runtime-*` |

## 7. Commits, suite and audit

| item | result |
|---|---|
| ps3recomp | `684d8bd` on `agent/t162-vehicle-rendering` (worktree `ps3recomp-t162`, base T146 tree). Not merged, not pushed |
| root report | branch `agent/t162-vehicle-rendering-report` (worktree `root-t162`, from `main` `4bdeed3`); hash in the follow-up commit |
| new tests | `test_t162_fp_src2_abs` 9/9 PASS (3/9 FAIL on the base decoder). `test_t162_vehicle_reflection` 13/13 PASS on WARP, 0 debug-layer errors |
| corpus | 151/151 race FP programs byte-identical HLSL, base vs. fix, for both the legacy and cube-mask calls (the race corpus has no `abs` source) |
| full suite (`run_all_t162`, `--jobs 6`) | 137 PASS / 43 SKIP / 3 FAIL. `test_rt_pool_srv_layout` and `test_vpc_watch` are the known T157 failures. `test_spurs_wws_concurrency` is intermittent: 2 of 3 serial reruns PASS. It is a SPURS test and doesn't involve the decompiler. T157 baseline was 138/43/2 |
| public audit | `--staged` on the ps3recomp index: 25 BLOCKs, all pre-existing tracked files (`runtime/spu/tests/out_*`, `test_workload_image.h`, `scratch/ppu_conformance.cpp`). The 3 changed files audited alone (`--tree` copy) pass. Root `--staged`: 13 BLOCKs, all `private/generated directory` path policy (8 new files plus 5 inherited `generated/analysis` files on `main`), 0 content hits; same as the T163 report commit |

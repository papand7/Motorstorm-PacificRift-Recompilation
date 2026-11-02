# T176: RSX visual fidelity

Code: ps3recomp branch `agent/t176-rsx-visual-fidelity`, commit `5ccbb116`, base `b282e262` (T171). Offline only: no game launch, merge, push or PPU relift.

## Result

Guest polygon offset was ignored by the D3D12 backend. It is now honoured behind `RSX_POLY_OFFSET=1`, **off by default**.

| Claim | Status |
|---|---|
| The backend ignored the guest's polygon offset | VERIFIED (source) |
| The correction produces the GL-defined depth on RTX 5060, AMD iGPU and WARP | VERIFIED (hand-built fixture) |
| The game's executable contains code that sends these methods | VERIFIED (static scan) |
| The game calls that code at runtime, and with which values | **UNVERIFIED** |
| Any visible improvement in the game | **HYPOTHESIS: none can be claimed** |

## 1. Visual defect inventory

Paths: `A` = `generated/analysis`, `R` = `root-t169/generated/analysis/t169`, `S` = `docs/STATUS.md`. "Fixed" means fixed in the named branch or switch. No PS3 reference exists, so nothing is confirmed against original hardware.

No single tree holds all fixes. `b282e26` (T171) lacks `66b5478` (T169 velocity decode), `684d8bd` (T162) and `6fbbc05` (T163). T172's changes are uncommitted in `ps3recomp-t172`.

| Area | Item | State | Switch or evidence |
|---|---|---|---|
| Lighting, materials | Black main pass | Fixed, on | `RSX_RT_READBACK`, `RSX_FP_SPAN`; S:73-79 |
| | Vehicle materials | Fixed, off | `RSX_COLOR_XFER=7`; R/ARM_C_CORRECTED_RESULTS.md:37 |
| | Specular and environment | Fixed, off | `RSX_TEX_MIPS=1` |
| | `SRC2.abs` | Fixed, T162 branch | `684d8bd` |
| | Rider skinning | No offline defect, race unconfirmed | `RSX_VTX_PARTIAL_0001`, off; A/t163 |
| | Garage compositing | Fixed, on; floor black cause unknown | A/t162/VEHICLE_RENDERING_FIDELITY.md:90 |
| | `0x0243AB00` flat green, T171 VB stripes | Open | |
| Shadows, depth | Guest polygon offset ignored | **Fixed here, off** | This report |
| | Depth and stencil state | Fixed, off | `RSX_DEPTH_STATE`, `RSX_STENCIL_EXACT`; 904/928 draws differ |
| | Shadow compare inversion | Fixed, on; race shadows inconclusive | S:1060, `c7bab5f` |
| | Terrain patches, class 1 | Fixed, off, uncommitted | `RSX_DEPTH_VOLUME`; A/t172 |
| | Terrain patches, class 2 dark squares | Open, cause unknown | A/t172:54-67 |
| | Far-vehicle slivers | Open | R/NEXT_VISUAL_CORRECTNESS_PLAN.md:5 |
| Render targets | RT feedback | Fixed, off | `RSX_RT_FEEDBACK`, `RSX_RT_WINDOW` |
| | Reinterpretation | Fixed, off, T169 branch; semantics HYPOTHESIS | `RSX_RT_REINTERP`, `66b5478` |
| | Alpha and blend | No track defect; independent MRT blend off | `RSX_MRT_STATE` |
| Textures | Mips and samplers | Fixed, off | `RSX_TEX_MIPS`, `RSX_GUEST_SAMPLERS=15` |
| | Anisotropy | Not used by the game | A/t133/RSX_IMAGE_QUALITY.md:39 |
| | Tyre tracks | Fixed, on, T171 only | `RSX_SHADER_WINDOW`, `b282e26` |
| | Font invisible text | Suspected; B8 remap fix not applied | A/t53/TEXT_RENDERING_ROOT_CAUSE.md |
| Post-processing | Bloom and exposure | MRT1 8.5× low; clipped white 18.9→0.18 % with a bundle, no single-switch run | |
| | Motion blur | Partial; velocity semantics M1 or M2 unresolved | |
| | MSAA | Fixed, off, never run in game | |

Superseded claims: T171's "speckle unexplained" by the `66b5478` decode; T162's "no capture contains vehicle" by T165; T169's decal link by T172's two-class split.

## 2. Root-cause evidence

**Source, VERIFIED.** Before this change `libs/video` had no polygon offset method handling and no `DepthBias` assignment. Guest values were dropped at `rsx_process_method`.

**Executable, VERIFIED static.** Instruction-level scan of the private ELF:
- One writer sends a 2-word header (count 8, method `0x0A78`), so scale and bias arrive together. It has one direct caller.
- That caller's parent also writes FILL_ENABLE (`0x0A68`).
- The parent is referenced only from one function-pointer table slot, with no direct `bl` callers, so it looks like a virtual method (HYPOTHESIS: a set-depth-bias method).
- 99 SPU images contain no literal headers for these methods.

**Runtime, not established.** Existing RSXI captures didn't record these registers. Static reachability doesn't show that the game calls the code. Links to shadow acne, decals or far-vehicle slivers are HYPOTHESIS.

Why this one was selected: the other open fundamentals don't have sufficient cause evidence (class 2 squares, slivers) or need runtime proof before activation (`RSX_DEPTH_STATE`). This is the only one with a verified omission, defined semantics and a test independent of game assets.

## 3. Selected correction

Honour NV4097 polygon offset with GL semantics, `offset = factor*m + units*r`, as a general RSX/D3D12 mapping. There is no game, shader or draw rule. The flag only gates the effect; the diagnostics run either way, so a future run shows whether the game uses it.

## 4. Implementation details

| File | Change |
|---|---|
| `libs/video/rsx_poly_offset.h` (new) | `rsx_po_map`: factor to `SlopeScaledDepthBias`, units to `DepthBias`. Rounds, clamps, treats non-finite as 0. A Z16 unit is 256 host steps, because host depth is always D24 |
| `libs/video/rsx_commands.[ch]` | Methods `0x0A68`, `0x0A78`, `0x0A7C` stored raw in `rsx_state` |
| `libs/video/rsx_d3d12_backend.c` | Distinct pairs interned (255 slots), slot in `cull` bits [15:8], so a change selects another pipeline. `vp_get_fp_pso` applies it. RSXI raster record gains `poly_offset` |
| `libs/video/tests/test_t176_poly_offset_warp.c`, `tools/test_t176_poly_offset.py` (new) | Tests |

Log line, once per new pair and also with the flag off: `[rsx-poly-offset] slot= scale= bias= surface= depth_bias= slope= applied=`.

Limits:
- Only the guest-FP pipeline path applies the offset.
- POINT and LINE enables are not handled; that path draws solid-fill triangles.
- Fractional units round to a host step, and a Z16 target's slope is measured on D24.
- After 255 distinct pairs, new pairs get no offset; a single `table full` line is logged.
- The zeta format is read per draw and slots hold the mapped values, so a guest pair on Z16 and Z24 takes two slots. The log shows the surface of a slot's first use only.

## 5. Before/after offline rendering comparison

Hand-built fixture with depth readback and the debug layer on, **not game ucode or a game capture**. The "no offset" and "fill disabled" arms measure the previous behaviour; other "Before" cells follow from no offset being applied and were not drawn separately. Results were identical on all three adapters.

| Arm | Before (ignored) | After | Expected (GL) |
|---|---|---|---|
| Coplanar, units -4, LESS | Rejected (measured) | Passes, -3.50 steps | -4 r, ±1 tolerance |
| Coplanar, units +4, LEQUAL | Passes (not drawn) | Rejected | Pushed away |
| Fill disabled, units -4, LESS | Rejected | Rejected | No effect |
| Z16 unit | No offset | -255.50 steps | 256 host steps, ±1 |
| Factor -2 on slope | No offset | shift -0.001953 | -0.001953 |

No before/after game image exists, as launches weren't authorized.

## 6. RTX, WARP and AMD correctness

`test_t176_poly_offset`, debug layer on:

| Adapter | Failures | Debug-layer errors |
|---|---|---|
| NVIDIA GeForce RTX 5060 | 0 | 0 of 0 messages |
| AMD Radeon(TM) Graphics | 0 | 0 of 0 messages |
| Microsoft Basic Render Driver (WARP) | 0 | 0 of 0 messages |

## 7. Performance impact

**Not measured with a benchmark.** No existing baseline was changed. From the code:
- Flag off: one extra branch per draw record, plus interning for pairs when the game enables fill. No extra pipelines, because the slot stays 0.
- Flag on: one extra pipeline for each draw state and distinct pair in use, compiled on the existing path. Cost depends on how many pairs the game uses, which is unknown.

## 8. Regression-test results

Run through `generated/analysis/t169/tools/env_t169.cmd`.

| Run | Result |
|---|---|
| Full suite | PASS 123, FAIL 3, SKIP 43, TIMEOUT 0 |
| `test_t176_poly_offset` | PASS: 8 pins and state checks, 5 mapping checks, 8 checks on each of 3 adapters |
| `test_depth_state`, `test_d3d12_depth_state`, `test_stencil_exact`, `test_shader_window`, `test_t171_track` | PASS |
| Backend `clang-cl /Zs` | Exit 0. A full game build was not made |

| Failure | Status |
|---|---|
| `test_rt_pool_srv_layout`, `test_vpc_watch` | Inherited: also fail in the T169 baseline and T171 |
| `test_spurs_wws_concurrency` | Known flaky, in SPURS code this change doesn't touch. Reruns: pass, pass, fail (mode guest in the suite). Not investigated |

The suite's `scratch/ppu_conformance.cpp` and `ppu_conformance_run.bat` rewrites were restored and aren't in the commit.

## 9. Remaining visual defects

1. Class 2 dark squares: cause unknown.
2. Far-vehicle slivers.
3. Velocity semantics, M1 or M2.
4. `RSX_DEPTH_STATE` and `RSX_RT_REINTERP` can only be defaulted together.
5. Forced depth writes; RT feedback not default.
6. `0x0243AB00` flat green, T171 VB stripes.
7. `RSX_COLOR_XFER` has no single-switch run.
8. No rider capture from a race.
9. Shoreline with depth state, CONTROL0-disabled units being sampled, stencil gaps.
10. No PS3 reference.
11. Fixes spread across unmerged branches, so no tree shows them together.

## 10. Recommended next graphics improvement

**Integrate the verified fixes into one tree, then isolate the class 2 dark squares.** T172's capture plan needs a small RSXI addition for per-box surfaces and unit 1 texture contents. Integration comes first because defects measured on a partial tree can be artefacts of what's missing, and it needs no launch.

## 11. Proposed in-game validation procedure

Requested, not authorized. It requires a new game build of this branch, with its SHA-256 recorded, and a local (non-RDP) session with other GPU workloads closed.

| Item | Value |
|---|---|
| Launches | 2, same exe, sequential, no retries |
| Arm A | `RSX_POLY_OFFSET=0` |
| Arm B | `RSX_POLY_OFFSET=1` |
| Route | Same automatic route and vehicle, fresh private HDD, stop at race + 45 s |
| Capture | Matching race clocks, RSXI with `poly_offset`, `[rsx-frame-perf]` |

Decisions:
1. Arm A with no `[rsx-poly-offset]` line, and no enabled `poly_offset` in RSXI: the game doesn't use it in that scene. Stop; the flag has no value there.
2. Lines present: record pairs and draws, compare shadow, decal and far-vehicle regions between arms at matched clocks.
3. Stop on effective-line mismatch, watchdog, crash, PSO failure or session change.

Keep the flag off unless arm B shows an improvement with no new defect and no frame-time regression.

## Optional enhancements (proposal, not implemented)

These change the original look, so each needs its own default-off switch, and all come after correctness.

| Enhancement | Note | Order |
|---|---|---|
| Higher internal resolution | Needs RT scaling; readback, zeta-as-colour and projection windows depend on guest size | 3 |
| MSAA | Switch exists, never run in game | 1 |
| Anisotropic filtering | The game doesn't request it; a forced override is simple but can affect data textures | 2 |
| Shadow filtering | Needs race shadows confirmed first | 4 |
| Texture filter overrides | Same data-texture risk as anisotropy | 5 |
| Ultrawide | Needs projection changes in guest constants, and frustum culling is the game's own | 7 |
| HDR output | Exposure and bloom must be correct first | 6 |
| Draw distance | Guest-side game logic, likely outside RSX; highest risk | 8 |

## Audit results

- Code commit `5ccbb116`: made **before** an audit ran, because the audit script isn't in the ps3recomp repo and my command didn't stop on that error. Checked afterwards: `audit_public.py --tree` on a copy of its 6 files passed. That repo has no commit hook in effect here.
- This report: the standalone audit and the root commit hook were run separately; see the final reply.

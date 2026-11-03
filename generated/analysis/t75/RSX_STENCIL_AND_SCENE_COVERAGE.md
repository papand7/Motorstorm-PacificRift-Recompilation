# T75: missing race geometry and RSX depth/stencil reconstruction

2026-10-26. Offline only: no launch, no full game build, nothing merged or pushed, no shared worktree modified. T70, T73 and T74 were not touched.

**Inputs:**
- the T72 RSXI frame f005625 (`generated/runs/20261026-160135-t72-exposure-readback`). T71 f004425 has the same structure.
- backend source `ps3recomp-t62` @ `c529ab0`, which is the base of the T64C exe.

## Result

**Stencil is not the cause: VERIFIED.**
- The D3D12 guest-FP pipeline never enables stencil, so no draw can be stencil-rejected on the host.
- The 0-sample quarter-res draws 212–221 use stencil func ALWAYS on the guest anyway.

**Root cause of the missing lower scene: VERIFIED mechanism. Its one unverified input, the op-210 control word, is PARTIAL.**
- **Op 210** is a depth-rebuild pass. It samples the main zeta `0x00ED0000` as ARGB8, reassembles 24-bit depth into `r1.z`, writes colour 0, and runs with guest depth test on, write on, func ALWAYS into the quarter-res zeta `0x0B920000`.
- On RSX, `r1.z` replaces the fragment depth only with SET_SHADER_CONTROL depth export (0xE).
- **The D3D12 backend never passes those bits to the decompiler.** Its own comment says "The depth export bits aren't recorded, so they stay off", at `rsx_d3d12_backend.c:2328-2341` @ `c529ab0`.
- **What op 210 writes instead:** the quad's constant depth. The VS `EEA3E622` outputs z = c467.z = 0 and w = 1, so the window z is **0.5** everywhere.
- **Why 212–221 fail:** these depth-tested (LEQUAL) draws sit at window z ≈ 0.998, so every fragment fails, giving **0 samples**.
  - They lie on screen: their bboxes span NDC y −0.3 to below −1 across x −1 to +1.4 (`t75/water_vis.py`).
- **Why that empties the lower scene:**
  - the quarter-res layer `0x0B830000`, copied by op 223 into `0x0BA10000`, stays empty;
  - the luminance pass op 236 adds `0x0BA10000`.rgb to the scene term and weights the scene by 16·(1−alpha). This is VERIFIED from the FP, and the empty layer leaves luminance 0 wherever terrain is absent, the T72 rows 6–15.
  - The layer is also sampled by op 243 and by the overlay draws 226–235 (unit 5), so it is the likely lower-scene fill of the final image (PARTIAL).

**Correction:** `ps3recomp-t75` @ **`595bd3a`** (branch `agent/t75-depth-export`, on top of the T68 camera fix `dfb9e2f`).
- **Depth export:** passed to the decompiler, so the existing `r1.z` → SV_Depth path runs.
- **Depth state:** the guest depth compare function and write mask are honoured.
- **Stencil:** not changed (§4).
- **Offline checks:** the TU compiles with 0 errors and an identical warning set; all backend tests match the base, with the depth-state test extended to 22/22 PASS.
- **Runtime effect:** unvalidated, a HYPOTHESIS until one authorized run.

**CPU exposure (§3):** VERIFIED structure. c33.x is built from the geometric mean of the G samples, and a single zero sample pins it at the 35.3 cap. Restoring coverage lowers exposure only if all 5 sample points become non-zero.

## 1. Original RSX state vs. D3D12 (relevant draws, f005625)

Values come from the RSXI `guest` record: depth `{test, write, func low byte}` and stencil `{test, func, ref, mask}`. Low byte n of a function means GL `0x0200+n` (3 = LEQUAL, 5 = NOTEQUAL, 7 = ALWAYS).

| op | target / zeta | FP | guest depth | guest stencil | host before (c529ab0) |
|---|---|---|---|---|---|
| 197–208 terrain | `0x750000`+MRT `0x1650000` / `0xED0000` | `07A9CEC1` | test, write, LEQUAL | off | LEQUAL, write ALL, no stencil |
| **210** depth rebuild | `0x0B830000` 640×360 / `0x0B920000` | `0B027F41` (tex0 = zeta `0xED0000` as ARGB8) | test, **write, ALWAYS** | off | **LEQUAL**, write ALL, **no depth export** |
| **212–221** quarter-res layer | `0x0B830000` / `0x0B920000` | `02B9EC81` | test, write, LEQUAL | **test, ALWAYS**, ref 64, mask 255 | LEQUAL, write ALL, **stencil off** |
| 223 copy | `0x0BA10000` | `02FF05C1` (tex0 = `0x0B830000`) | off | off | off |
| 225 | `0x750000` / `0xED0000` | `022CD841` | test, **write off**, LEQUAL | **test, NOTEQUAL**, ref 128, mask 128 | LEQUAL, **write ALL**, **stencil off** |
| 226–235 overlay | `0x750000` / `0xED0000` | `02B9EF81`, blend `0x0122418B` | test, **write off**, LEQUAL | off | LEQUAL, **write ALL** |
| 236 luminance | `0x02195900` | `0074B181` (tex1 MRT1, **tex2 `0x0BA10000`**) | off | off | off |

**Items 1–14:**
- **Depth test enable, function, write mask (1–3):** recorded in `g_depth` (`:8634`). The pipeline used only the enable bit (`dr_depth_key`, `:2114`); the function was fixed at LESS_EQUAL and writes at ALL (`:2632-2635`). **Mismatch, VERIFIED** (ops 210, 225, 226–235).
- **Stencil enable, function, reference, read mask (4–7):** decoded in `rsx_commands.c:582-600` and recorded in `g_stencil`. The pipeline has `StencilEnable = FALSE` always. **Mismatch, VERIFIED.**
- **Stencil write mask (`0x032C`), the three stencil ops and back-face/two-sided state (`0x0348`–`0x0364`) (8–11):**
  - The ops are decoded into `rsx_state` (`stencil_op_fail/zfail/zpass`) but never reach the D3D12 record.
  - Write mask and back-face state are **not decoded at all** by `rsx_commands.c`. Only the separate live-draw/draw-engine path reads them (`rsx_draw_engine.c:290-300`).
  - Their guest values for these draws are **not captured** (BLOCKED offline).
- **Depth/stencil format (12):** the host is always D24_UNORM_S8_UINT, matching guest Z24S8 `0xED0000`. `0x0B920000` is assumed Z24S8; its format was not captured.
- **Clears (13):**
  - The host clears depth/stencil to 1.0/0 (`:6569`, `:6907`). The T68 order mapping gives guest scene depth 1.0 (PARTIAL).
  - `0x0B830000` is colour-cleared at op 211, after op 210, so depth is not cleared there. The rebuild owns it.
- **Transitions (14):** op 210 samples `0xED0000` and writes `0x0B920000`, a different zeta, so there is no feedback. RSXI `bind_rt` reports `depth_cleared`/`state_before` normally. Nothing abnormal.
- **SHADER_CONTROL depth export:** recorded by `rsx_commands.c:869` (`state->shader_control`). The D3D12 record kept only bit 0x40 (`fp_exp32`). **Mismatch, VERIFIED in source.**
  - Whether op 210's control word has 0xE set is **PARTIAL**. It was not logged, but the program computes `r1.z` = dot(floor(tex·255+0.5), (2⁻⁸, 2⁻¹⁶, 2⁻²⁴)) and exports colour 0, which is meaningful only as a depth export. The guest also runs it with depth write on and ALWAYS.

## 2. Missing scene coverage (Phase 2)

| candidate | finding | label |
|---|---|---|
| depth/stencil state | Depth export missing on op 210, so the quarter-res zeta is 0.5 and draws 212–221 are depth-rejected (z ≈ 0.998 > 0.5). Stencil cannot reject on the host. | **VERIFIED** (mechanism); control word PARTIAL |
| render-target setup | `0x0B830000` and `0x0B920000` bound 640×360, viewport 640×360, no unresolved target | VERIFIED, not a cause |
| missing submissions | All draws recorded and executed; `dropped=0` (T68/T71 accounting) | VERIFIED, not a cause |
| clipping / transforms | Quarter-res and overlay draws project on screen with the game camera (c0–c3 of each draw, VS `32481FD3`/`158A5048` are world-space): NDC y −0.3 to −1+, z 0.98–0.998, w > 0 for nearly all corners | VERIFIED, not a cause |
| primitive assembly | prim 8 (QUAD_STRIP) expanded natively; the same geometry in 226/227 rasterises (2370/979 samples) | VERIFIED, not a cause |
| compositing | The overlay 226–235 changed only 1848 px, at white terrain edges. FP `02B9EF81` discards under an albedo threshold and blends, so it is not the lower-scene fill. The luminance pass consumes the quarter-res layer `0x0BA10000` (VERIFIED from FP `0074B181`); its role in the final image is inferred. | PARTIAL |
| terrain chunks 197–201/203 | Off-screen or behind the camera (T72 §6): 199/200 VERIFIED, the rest PARTIAL | not the lower-half cause |
| legitimate visibility | Rejected: the geometry is on screen and fails only the depth test | VERIFIED |

**Op 225** (0 samples) has w ≤ 0 on 6 of 14 vertices and y = −100000 (a sky/stencil volume). It is unexplained and is not needed for the lower half.

## 3. CPU exposure consumption (Phase 3)

Source: `func_004C3778` (lifted `ppu_recomp_010.cpp:43503`), checked against the ELF disassembly. Full write-up: `t75/cpu_exposure.md`.

1. **Sample read (VERIFIED):** only G, the `lhz` half at +2 (0x4C38A4). R is never read. Points come from a `vector<float2>` at [this+0x1A4..0x1A8] (5 at runtime). The code that fills it is untraced.
2. **Combination (VERIFIED):** geometric mean gm = 2^(mean log2 Gᵢ) (0x4C38C8–0x4C3A2C); target = clamp(K/gm, Emin, Emax) with K, Emin, Emax at [this+0xBC/0xC0/0xC4].
3. **Zero handling (VERIFIED):** there is no CPU clamp. A zero sample becomes log2 = −127, so a single zero drives the target to Emax. Only a NaN output is replaced, with 1.0.
4. **Smoothing (VERIFIED):** a fixed rate R=[this+0xD0] when rising and 0.375·R when falling, per call, with no frame time.
5. **c33 (VERIFIED structure):** c33.x = 1 + S·(s−1), with S=[this+0xB8], sent at 0x4C3AE4. y, z and w are never written (stale stack).
6. **Parameter values (HYPOTHESIS):** the parameters are set from data. K=0.3, S=0.7, Emin=0.1, Emax=50 reproduce the GPU formula and the cap **35.3 = 1 + 0.7·49**. The garage first frame gives R = 0.070 exactly; the T71/T72 ramps fit about 0.08, a 20% gap that is unexplained.
7. **Prediction (HYPOTHESIS):**
   - With the current pattern (one lit, four zero samples), c33.x stays pinned at 35.3, and it still does with four lit samples and one zero.
   - With all 5 samples at about 0.67, c33.x falls to about 0.61 over about 200–300 frames.
   - So restoring coverage lowers exposure **only if every sample point becomes non-zero**.

## 4. Correction: `ps3recomp-t75` @ `595bd3a`

`git diff dfb9e2f..595bd3a`: 2 files, +141/−36, in `libs/video/rsx_d3d12_backend.c` and `tools/test_d3d12_depth_state.py`.

**What changed:**
- **Draw record:** a new `g_zexport = shader_control & 0xE`, set where `g_depth` is set, and 0 without state.
- **`dr_depth_key`:**
  - bit 0 is the test;
  - with the test on, bit 1 is the write mask and bits 8–15 the function's low byte;
  - bits 16–19 are the depth-export bits.
  - Depth-test-off draws keep key 0 when not exporting, so they get no new pipelines.
  - The pipeline cache was already keyed on this value.
- **`rsx_cmp_d3d`:** maps RSX `0x0200`–`0x0207` (or the low byte) to D3D12 NEVER..ALWAYS. A non-RSX value keeps the old LESS_EQUAL.
- **Pipeline:** the guest function and write mask when the test is on. Test off still means no test and no write.
- **Decompiler control word:** `0x40` | `(depth key >> 16) & 0xE`. The decompiler's existing depth-export path (`rsx_fp_decompiler.c:1357-1366`, unit-tested in `test_fp_decompiler.c:426-448`) then emits `SV_Depth = saturate(r1.z)`.
- **Programs that don't export depth compile to byte-identical HLSL**, because their control word is unchanged.

**Not done, deliberately:**
- **Stencil.** It is not causal here. A faithful translation also needs the stencil write mask and the two-sided/back-face registers, which the `rsx_commands.c` state does not decode, and the guest values for these draws were not captured. A partial stencil would be speculative. This is the next item if a later capture shows stencil-dependent loss.
- **No special cases:** no MotorStorm addresses, shaders, draw IDs or exposure values. No depth or stencil test was disabled. The camera code is unchanged (it is the `dfb9e2f` base).

**Behaviour change for other titles (expected and RSX-correct):**
- draws with depth write off no longer write depth;
- non-LEQUAL functions now apply;
- the state's reset function (1, LESS) maps to LESS rather than LEQUAL.

## 5. Offline regression

Logs are in `t75/tu/`.

| check | base `dfb9e2f` | T75 `595bd3a` |
|---|---|---|
| `rsx_d3d12_backend.c` TU (project clang-cl 23.1.3, exact `build.ninja` flags, `vcvars64`, objects in `t75/tu/`) | 0 errors, 2597 warnings | **0 errors, 2597 warnings, an identical set** (only line numbers move) |
| 19 `tools/test_*.py` that read the backend | 12 pass / 7 fail | **identical** per test (the 7 are pre-existing: zeta_pool, draw_rejection, present_diag, rsxi_geom, rt_readback, rt_vis_trace, xfer_diag) |
| `test_d3d12_depth_state.py` (updated) | — | **22/22 PASS**: key layout, all 8 functions, mask, depth export in key and control word, distinct cache keys, ALWAYS rebuild, GREATER, test-only draw, depth-off pair |
| new test run on the base backend | **FAILS** (3): no `g_zexport`, no control-word bits, no `rsx_cmp_d3d` | — |
| old test run on the T75 backend | — | fails only on its fill anchor; the asserted "always LESS_EQUAL with writes" behaviour is intentionally replaced |
| `audit_public.py --staged` | 25 pre-existing items | the same 25; none in the changed files |

**Not run:** a full exe build and a GPU replay (the backend needs a device).

## 6. Remaining uncertainties

1. **Op 210's SHADER_CONTROL value.** It was not logged. The program's form (`r1.z` depth, colour 0, depth write ALWAYS) strongly implies 0xE (PARTIAL). The run below checks it.
2. **How the overlay 226–235 (FP `02B9EF81`) and op 225 combine with the restored layer.** Partly read from the shaders; not replayed.
3. **Stencil write mask, ops and two-sided state are uncaptured.** If op 225 or the overlays rely on stencil written by 212–221 (ref 64), stencil is the next correctness gap (needs decode plus capture).
4. **The new depth function and mask apply to every guest-FP draw.** Draws that relied on the forced LESS_EQUAL/write behaviour would now render as on RSX, which could reveal other latent defects.
5. **Whether exposure drops.** Per §3, all 5 G samples must become non-zero; one remaining zero keeps c33.x at 35.3 (HYPOTHESIS).

## 7. Recommended runtime validation (NOT run, needs authorization)

**Needs one build authorization:**
- a private copy of the T64C build directory, re-pointed at `ps3recomp-t75` (`PS3RECOMP_DIR`);
- `port/CMakeLists.txt` unmodified;
- the exe hash recorded.

That exe also contains the T68 camera fix, so it serves as Run B.

**Then one launch:**
- **Base:** the `t72/run_t72.py` configuration with the new exe and its hash, a fresh private HDD, the Kanaloa Bay / Light Fantastic / ATV route, no driving, 205 s cap and `--timeout 210`, WWS AOT off, no `TEX_SAVE`, no `RT_CLEARDBG`.
- **Remove** `VP_NOFIXPROJ` (to validate the camera fix).
- **Keep:**
  - `RSX_RT_READBACK=1`, `RSX_RT_READBACK_WATCH=07EBA600`, `RSX_RT_READBACK_LOG=160`;
  - `RSXI_RTS=00750000,01650000,0B830000,0BA10000,02195900,07EBA600,00ED0000,07B78D80`;
  - `RSXI_OCC=160-260`, `RSXI_GEOM=8`, `RSXI_VP_CONSTS=512`.
- **Add:**
  - `RSX_PSO_WATCH_FP=0x0B027F41` (logs op 210's pipeline depth state: expect enable 1, write 1, func 8 = ALWAYS);
  - `RSX_SHADER_TRACE=1` with `RSX_SHADER_TRACE_MAX=256`.

**Measure:**
1. occlusion of ops 210 and 212–221 (expect > 0 for 212–221) and of 225–235;
2. the `0x0B830000`/`0x0BA10000` snapshots: non-black in the lower half;
3. the `0x07EBA600` snapshot: rows 6–15 with G > 0;
4. CPU samples, via the `[rtrb] watch`/probe lines at +0x52A/+0x552/+0x592/+0x5EA;
5. `c33.x` across the 3 frames (expected to fall below 35.3 if §3 holds);
6. terrain colour and texture detail in `0x750000` and the backbuffer;
7. the reflection `0x07B78D80`;
8. no `[VPFB]`, Present-timeout, device-removed or fatal lines, and frame time compared with T72.

**Not executed. A build and a launch each need separate authorization.**

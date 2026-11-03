# T68: black race scene, targeted runtime diagnosis

2026-10-26. One bounded run, 180 s of the 210 s cap: navigation and race intro only, no driving.

**Constraints kept:**
- Nothing merged or pushed.
- No shared worktree or shared HDD modified.
- No rebuild and no second run.

## Result: root cause **VERIFIED**; correction made, **not yet run-validated**

The main scene is black because the D3D12 backend **replaces the game's camera**.
- `vp_record_cb`'s "garbage-projection fallback" (written for vkcube) treats any c0.x outside (0, 8) as garbage.
- It then overwrites c0–c15 with a fixed camera.
- MotorStorm's race view-projection has **c0.x = −1.24474**. That is a valid matrix: c0.x is negative whenever the camera's right vector points down −x.
- Under the substitute camera, every visible terrain triangle faces away from the viewer.
  - The scene pass (cull BACK) **culls all of them**.
  - The water reflection (cull FRONT) keeps them. That is why the reflection "works".

STATUS.md:810 already recorded this defect in the garage (c0.x = −0.60048), with the note "must not fire on a valid matrix whose c0.x is negative". It was never fixed, and T63/T64C/T68 ran without `VP_NOFIXPROJ=1`.

## 1. Runtime timeline and capture identifiers

- **Run:** `generated/runs/20261026-144038-t68-main-scene-diag`, plus the controller log `t68/runtime-20261026-144038/`.
- **Exe:** the T64C exe `162afb4a…` (`ps3recomp-t62` @ `c529ab0`, which includes the T61 font fix). WWS AOT off.
- **HDD:** fresh private copies `t68/hdd0|hdd1`.
- **Env:**
  - `RT_CLEARDBG=2`, `PS3_DRAW_ACCT_MS=5000`;
  - `RSXI_SNAP=passes` (3 frames, mindraws 200), `RSXI_RTS` (7 targets), `RSXI_OCC=160-260`, `RSXI_GEOM=8`, `RSXI_VP_CONSTS=512`;
  - PT `fn=734680` (SetZStencilClearValue), sampled.
  - No `TEX_SAVE` and no `DEPTH_OFF`.

| t (s) | event |
|---|---|
| 44.6–65.2 | nav steps 1–4 (each CROSS gated on its page load) |
| 65.6 | LOAD RACE START (`0x892C4`) |
| 149.4 | PostLevelLoad `0x8C2A0` |
| 154.5 | `0x8C848` |
| 174.5 | RSXI trigger (marker + 25 s) |
| 180.0 | capture complete, so the controller stopped. Frames **f004849, f004850, f004851** |

All three frames are identical in structure and outcome. Numbers below are from f004849.

## 2. Main-scene pass snapshots (`RT_CLEARDBG=2`, magenta on bind)

| after op | target | content |
|---|---|---|
| 196 | `0x07B78D80` reflection | 52.8 % geometry, 47.2 % magenta |
| **208** | **`0x00750000` scene (MRT0)** | **100 % magenta**: no colour write at all |
| 221 | `0x0B830000` quarter-res terrain | 100 % magenta |
| 235 | `0x00750000` after water | 100 % magenta |
| 236 | `0x02195900` luminance of MRT1 | 100 % magenta, so MRT1 `0x01650000` is also unwritten |
| 243 | `0x01650000` after fp `0074CE81` | 99.7 % black (that fullscreen pass writes 0) |
| end | backbuffer | 24 % magenta (the composited scene) plus the HUD |

## 3. Draw-drop accounting (VERIFIED)

- **`draw_acct`:** `callbacks.dropped=0`, `dropped_display=0`, `unrecorded_display_groups=0` throughout.
- **RSXI:** `dropped_events=0`, no batch-full.
- **Ops 197–208:** recorded, then executed with `DrawInstanced` (645–696 vertices each, `pso=guest_fp`, RTV slot 15 + MRT slot 16, `target_unresolved=false`).
- No draw was rejected or skipped, and every pipeline was available.

## 4. Depth/stencil state comparison

| | reflection 5–196 | scene 197–208 |
|---|---|---|
| guest depth | off | test LEQUAL, write off, zeta `0xED0000` (Z24S8) |
| host PSO | off | on, LEQUAL, write **ALL** (the T67 defect (a), still present) |
| stencil | off | off |
| cull | FRONT (`0x404`) | BACK (`0x405`), front face CW |

**Depth clear value:**
- SetZStencilClearValue is called 11 times per frame, in the order 3×`FFFFFF40`, 1×`FFFFFF00`, then 7×`00000000` (1084 calls; the first 200 fully logged).
- That matches the frame's 3 shadow depth clears, then the op-3 scene-zeta clear, then 7 colour clears.
- So the scene depth is cleared to **1.0** (order-based mapping; PARTIAL).
- Fragment z under the substitute camera is ≈ 0.0101 (`vpx` z-lane is 1/0). That would pass LEQUAL against 1.0.

**Depth is therefore not the rejector.**

## 5. Magenta-clear observations

- `0x750000` and MRT1 stay magenta after ops 197–208, so no colour write reached either target.
- **Occlusion:** ops 197–208 pass **0 samples**, in all three frames.
- The query path works: the fullscreen ops 210 and 223 pass exactly 230400 = 640×360.
- Magenta plus 0 samples plus valid PSO and targets means the fragments never reach the output merger. That points to rasterisation, culling or clipping, not the shader, not the MRT/MSAA setup, and not depth (§4).

## 6. MSAA and shader findings

- **The vertex program `CEED7030` reads c0–c3.** The `[VPFB]` log shows: `fallback proj on draw slot 5..10 (c00=-1.24474 vs_idx=11)`, and `vs_idx` 11 is `CEED7030`.
- **The captured c0–c3 are the fallback's constants, for both passes:** (1.358,0,0,0) (0,2.414,0,0) (0,0,0.010101,1) (0,0,−0.010101,0). These are the hard-coded values in `rsx_d3d12_backend.c`.
- **Evaluating the VS on the captured vertices (RSXI_GEOM samples) with these constants:**
  - every on-screen sample triangle in ops 201/203/204/205/208 and their reflection twins 9/11/12/13/16 has the **same window-space winding**;
  - the rest have w ≤ 0 (behind the substitute camera);
  - the two passes use opposite cull faces, so the reflection keeps exactly what the scene culls.
- **MSAA / 0x3148:** a single-sample 1280×720 host target is bound with both RTVs. That is not the cause (0 samples reach it). The 2×AA layout remains unmodelled.
- **The fragment shader is unchanged** between the two passes. No zero-output evidence.

## 7. First confirmed point of image loss

**Op 197**, the first draw into `0x750000` + `0x01650000`. Its projection constants have already been replaced in `vp_record_cb` (`rsx_d3d12_backend.c:3633-3647` at `c529ab0`). Everything downstream is black or magenta because it inherits this.

## 8. Root cause (VERIFIED)

`int garbage = !(c00 > 0.0f && c00 < 8.0f);` treats a valid negative c0.x as an unset projection. The backend then substitutes a fixed camera, which RSX never does. Under that camera the race terrain is back-facing for the scene pass's cull mode, so nothing rasterises.

## 9. Correction (isolated worktree, not merged)

- **Location:** `ps3recomp-t68` (branch `agent/t68-vp-fallback`, base `c529ab0`), commit **`8654a4d`**.
- **Change:** a new header `include/ps3emu/vp_fallback.h`, `ps3_vp_c00_is_garbage()`.
  - Only non-finite values, 0, or |c0.x| ≥ 8 select the fallback; the sign is the camera's.
  - The backend calls it in place of the old test.
  - `VP_NOFIXPROJ` and `VP_FIXPROJ` are unchanged, and the gate still applies only to programs that read c0–c3.
- **Tests:**
  - `tools/test_vp_fallback.py`: 5 source checks PASS.
  - `libs/video/tests/test_vp_fallback.c`: 18 cases, including the game's −1.24474 and −0.60048, ±0, ±8, ±1e30, ±NaN and ±Inf. Built with MSVC `/W4 /WX`: 0 failures.
  - `tools/test_rt_clip.py` still passes.
- **Not done:**
  - A full compile of `rsx_d3d12_backend.c`. MSVC rejects the project's existing GCC atomics, and clang-cl is not installed. The edit is one include plus one expression.
  - No rebuild and no run.
- **Audit:** `tools/audit_public.py --staged` reports the same 25 pre-existing items, none new.
- **Not touched:** depth/stencil state, shaders, brightness, physics and WWS. No forced depth-off.

## 10. Uncertainties and next steps

- **Visual result after the fix: unverified.** It needs one approved run with a rebuilt exe. Expect the garage-like issues to surface next:
  - primitive restart: the 65535 indices visible in op 197 `index.first`;
  - the PSO ignoring the guest depth write mask and stencil (T67 (a));
  - the RT feedback hazard on water (T67 (b)).
- **A matrix whose c0.x is exactly 0** (camera at exactly 90° yaw) still triggers the fallback. Removing the fallback entirely would match RSX, but it is kept for vkcube; that is the owner's call.
- The clear-value-to-op mapping relies on call order (PARTIAL).
- The quarter-res terrain ops 212–221 also pass 0 samples. It is consistent that they use the same camera, but their VS constants were not evaluated.
- Why the race frame has no shadow-pass draws: open (T67).

**Tools:**
- `t68/analyze.py`: NaN-tolerant; output `analysis_20261026-144038-t68-main-scene-diag.txt`.
- `t68/run_t68.py` and `test_ctl_t68.py` (13/13 PASS).

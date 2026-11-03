# T71: camera-fix validation

2026-10-26. One authorized launch (Run A). No build, nothing merged or pushed, no shared worktree, HDD or build directory modified.

## Result

- **Offline: VERIFIED.**
- **Run A: camera fix VERIFIED.** With the game's own camera, the race geometry rasterises: the horizon, sky band and terrain silhouettes now reach the scene targets and the backbuffer.
- **A fully visible race: PARTIAL.** The scene output is saturated to pure white or black, with no texture or shading detail (§5).
- **Run B: not authorized.**

## 1. Source revisions and isolated changes

- **Known-working T64C line:**
  - Source: `ps3recomp-t62` @ **`c529ab0`**. That is `307b08a` plus the T61 font fix, cherry-picked as `c529ab0`.
  - Build: `build/motorstorm-t62-font-c529ab0`. Its CMake `PS3RECOMP_DIR` is `ps3recomp-t62`, compiled with clang-cl 23.1.3, Release.
  - Exe sha256 `162afb4a…` (VERIFIED). It is the same file as `t64/exe/`.
- **Integration:**
  - Worktree `ps3recomp-t68`, branch `agent/t68-vp-fallback`, HEAD **`dfb9e2f`**.
  - It is `c529ab0` plus 3 commits:
    - `8654a4d`: the fix;
    - `c8c76ea`: the header rewritten as one expression, to clear a `-Wdeclaration-after-statement` warning;
    - `dfb9e2f`: the test runner links libm only off Windows.
  - `git diff c529ab0..dfb9e2f`: 4 files, +126/−2:
    - `include/ps3emu/vp_fallback.h` (new);
    - `libs/video/rsx_d3d12_backend.c` (one include, plus the `garbage =` line and its comment);
    - `libs/video/tests/test_vp_fallback.c`;
    - `tools/test_vp_fallback.py`.
  - No WWS, depth/stencil, primitive-restart, water-feedback or other renderer changes.
- **The camera rule:**
  - The fallback now fires only when c0.x is non-finite, 0, or |c0.x| ≥ 8.
  - The game's c0.x values (race −1.24474, garage −0.60048) are therefore kept unmodified.
  - `VP_NOFIXPROJ` (never substitute) and `VP_FIXPROJ` (always substitute) are unchanged.
  - No new camera approximation was introduced.

## 2. Build and toolchain

- **Toolchain:** the project uses `build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/clang-cl.exe` with the MSVC 14.51 SDK (`vcvars64`).
- **Translation-unit compile:**
  - I compiled the full `rsx_d3d12_backend.c` with the exact `build.ninja` flags and include set, writing the object to `t71/tu/`. The shared build directory was not touched.
  - Base `c529ab0`: 0 errors, 2597 warnings.
  - T71 `dfb9e2f`: **0 errors, 2597 warnings**, an identical warning set.
  - Logs: `t71/tu/base.log`, `t71/tu/t68.log`.
- **Full exe build:** not done. It needs authorization.
  - It would use a private copy of the T64C build directory, re-pointed at `ps3recomp-t68` (`PS3RECOMP_DIR`).
  - `port/CMakeLists.txt` stays unmodified.

## 3. Offline tests

| test | result |
|---|---|
| `test_vp_fallback.c` (18 cases), built with project clang and MSVC `/W4 /WX` | 0 failures |
| `tools/test_vp_fallback.py` (5 source checks plus the harness) | PASS |
| all 18 existing `tools/test_*.py` that read the D3D12 backend, base against T71 | identical, all exit 0 |
| `audit_public.py --staged` | the same 25 pre-existing items, nothing new |
| `t71/test_ctl_t71.py` (controller replay of T64B/T64C, env, cap, HDD, exe pin) | 13/13 PASS |

## 4. Runtime authorization requirements

**A rebuild is not needed for the first validation.**
- The T64C exe already honours `VP_NOFIXPROJ=1`, which disables the substitution.
- For every camera with a valid c0.x, the patched rule behaves the same as `VP_NOFIXPROJ=1`: the game's constants are kept. That includes MotorStorm's race camera, the only `[VPFB]` value seen in T68.
- So this option validates the camera fix without a build.

**Run A (authorized and run once, see §5):** `py -3 generated/analysis/t71/run_t71.py launch`
- **Same as T68:**
  - T64C exe (pinned hash);
  - the private HDD `t71/hdd0|hdd1`, already prepared;
  - the transition-aware controller, Kanaloa Bay / Light Fantastic / ATV;
  - 205 s hard cap with `--timeout 210`;
  - WWS AOT off, no `TEX_SAVE`, no driving.
- **Changed from T68:**
  - add `VP_NOFIXPROJ=1`;
  - remove `RT_CLEARDBG`, so the real image is captured.
- **Capture:**
  - RSXI `passes`, 3 frames, mindraws 200, triggered 25 s after the PostLevelLoad marker;
  - `RSXI_OCC=160-260`, `RSXI_GEOM=8`, `RSXI_VP_CONSTS=512`;
  - `CELLMARK_DUMP` backbuffer screenshots.
- Dry run checked before the single launch.
- **Success checks:**
  1. no `[VPFB]` line, and the captured c0–c3 are not the 1.358/2.414/0.0101 values;
  2. occlusion > 0 for the scene draws;
  3. `0x750000` and `0x01650000` contain terrain and sky;
  4. the backbuffer shows the race;
  5. `0x07B78D80` (the reflection) is still rendered;
  6. no watchdog, Present-timeout or fatal lines.

**Run B (later, optional):** build an exe from `dfb9e2f` and repeat Run A without `VP_NOFIXPROJ`. It needs a separate build-and-launch authorization.

## 5. Runtime evidence (Run A)

**The session:**
- **Run:** `generated/runs/20261026-152501-t71-camera-validate`; controller log in `t71/runtime-20261026-152500/`.
- **Exe and environment:**
  - T64C exe `162afb4a…` (the dry run checked the hash);
  - `VP_NOFIXPROJ=1`, `PS3_DRAW_ACCT_MS=5000`;
  - WWS AOT off, no `TEX_SAVE`, no `RT_CLEARDBG`;
  - fresh private `t71/hdd0|hdd1`.
- **Timeline:**
  - depth surface matched at 2:45;
  - the controller stopped at 179.7 s on the "LoadRace returned: race-state checkpoint (no driving)" stop;
  - RSXI capture complete at 185.3 s. Frames **f004425–f004427**, all three consistent.
- **Termination:** `exited_error` (exit 1), the same as T68: a controller stop, not a crash. Well under the 205 s cap.
- **Analysis:** `t68/analyze.py`, output `t71/analysis_20261026-152501-t71-camera-validate.txt`.

| # | criterion | result | evidence |
|---|---|---|---|
| 1 | camera constants intact | **VERIFIED** | Op 197/204 VS `CEED7030` c0 = (−1.21579, 0.10326, 0.76344, 0.763427) and c3 = (1007.97, 24.08, 63.14, 63.33): the game's own matrix. The reflection (op 5) has the same c0 and c2, a negated c1 and its own c3, so the mirror is correct. The 1.358/2.414/0.0101 substitute is gone. |
| 2 | no fallback overwrite | **VERIFIED** | 0 `[VPFB]` lines in stdout (T68 logged 6). |
| 3 | scene draws pass samples | **VERIFIED** (6 of 12) | Ops 202/204/205/206/207/208 pass 4594 / 346667 / 7844 / 24522 / 3110 / 35796 (T68: all 0). Ops 197–201 and 203 still pass 0, and so do the quarter-res terrain ops 212–221. |
| 4 | main RTs contain terrain and sky | **PARTIAL** | `0x750000` after op 208 is 50 % `ffffff` and 50 % `000000`: a white sky band above a straight horizon, plus white terrain patches bottom-left and right. MRT1 `0x01650000` (after op 242) has **422533 white px, exactly the sum of the samples passed by ops 202–208**. So every white pixel is terrain-draw output, saturated, and the black is unwritten clear colour. No texture or shading detail. |
| 5 | backbuffer shows the race | **PARTIAL** | The final image shows the same horizon, terrain silhouettes, bloom gradient at the horizon, and the "Press ⊗ to Skip" HUD (`bb_frame_073`, `snap09`). The T68 backbuffer was black plus the HUD. Recognisable as a race view, not yet as Kanaloa Bay. |
| 6 | reflection still OK | **PARTIAL** | `0x07B78D80` is still rendered: 57 % coverage, with 192 draws including small objects (occlusion > 0 for ops 160–196). It now uses the game's mirrored camera, so it differs from the T67/T68 image, which used the substitute camera. It is also saturated white. |
| 7 | no new GPU crash or timeout | **VERIFIED** | No Present-timeout, device-removed, fatal or watchdog-stall report. `draw_acct callbacks.dropped=0` and `dropped_display=0` throughout. |

**Depth clear:**
- The same per-frame SetZStencilClearValue pattern as T68: `FFFFFF40`, `FFFFFF00`, then `00000000`.
- The zeta snapshot `0x00ED0000` is ~100 % zero as colour, because zeta-as-colour is not meaningful.

## 6. Screenshots and captures

In `t71/snaps/`, converted from the private RSXI and CELLMARK dumps:
- `f4425_snap02_pass_op0208_rt_00750000.png`: the scene after the terrain draws (horizon plus terrain silhouettes, white or black);
- `f4425_snap01_pass_op0196_rt_07B78D80.png`: the reflection under the real camera;
- `f4425_snap09_end_op9999_bb_00000000.png`: the final backbuffer;
- `f4425_snap06_pass_op0242_rt_01650000.png`: MRT1;
- the other per-pass snapshots;
- `bb_frame_*.png`: CELLMARK backbuffer screenshots (74 taken; the last 6 and every 12th converted).

Raw BMPs are under the run directory (`rsxi/frames/f004425–7`) and `runtime-20261026-152500/frames/`.

**Evidence stopped there:** the environment's geometry is visible, so no driving and no gameplay.

## 7. Remaining renderer issues (not addressed in T71)

**New from Run A:**
- **Saturated scene output** (pure white or black) in `0x750000`, MRT1 and the reflection. HYPOTHESIS: a fragment-output or constant-scale issue (the `tc6.y`/lighting term, or HDR encoding). Not related to the camera, and nothing was changed.
- **6 of 12 terrain draws and all quarter-res terrain draws pass 0 samples** under the real camera. HYPOTHESIS: candidates are primitive restart (65535 indices), depth, or legitimately off-screen. Unproven.

**Already known:**
- **Primitive restart:** index 65535 appears in the op-197 strips.
- **Depth/stencil state:** the PSO forces depth write ALL, LEQUAL and no stencil (T67 (a)).
- **Water feedback:** a render-target feedback hazard (T67 (b)).
- **No shadow-pass draws in the race.**
- **Other known issues:** the loading-screen whiteout, ATV icon transparency, and about 5 fps (WWS).

## 8. Recommended next task

1. **Run B** (needs separate approval): build an exe from `dfb9e2f` and repeat the Run A path without `VP_NOFIXPROJ`. Expect the same images as Run A.
2. **An offline task on the saturation:**
   - evaluate VS `CEED7030` and fp `07A9CEC1` with the captured Run A constants and geometry (RSXI_GEOM/VP_CONSTS are already in f004425);
   - find out why the output clamps to white, and why ops 197–201/203 pass 0 samples. Also check primitive restart.
3. Then fix depth/stencil state and the water feedback hazard, each as its own isolated task.

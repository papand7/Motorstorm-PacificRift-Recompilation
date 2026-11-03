# T147: unified RSX visual fidelity integration

- Worktree `ps3recomp-t147-visual-integration`, branch `integration/t147-unified-rsx-visuals`.
- Base: T145 `f7f9366`. Tip: **`d76e08e`**. Local commits only; nothing was pushed.
- The game was **not launched**, so every result in this report is offline. Runtime status is labelled per feature.
- Per-feature status: [VISUAL_FEATURE_MATRIX.md](VISUAL_FEATURE_MATRIX.md).

## 1. Inventory

Visual branches considered:

- **Already in the T145 base chain** (T113 → T120 → T133 → T137 → T141 → T142 → T145): T103, T107/T108 (diagnostic), T110, T113, T115 (`4a74174`), T120, T133, T137, T141, T142, T145.
- **Side lines:**
  - T115B (`65d2695`)
  - T117 (`fd97181`)
  - T144 (`121879f`, `c31aa83`)
- **Performance lines, out of scope (T146):** T116, T119, T122, T143.
- T146's incomplete integration branch was not merged or touched.

## 2. Commit mapping

| T147 commit | Source | Method |
|---|---|---|
| `f3561cd` | T115B `65d2695` | `cherry-pick -x`, clean |
| `505804e` | T144 `121879f` | `cherry-pick -x`, clean |
| `c0ff81f` | T144 `c31aa83` | `cherry-pick -x`, clean |
| `f986282` | T117 `fd97181`, decompiler half only (`rsx_fp_decompiler.c`, `tests/test_fp_decompiler.c`) | manual apply |
| `d76e08e` | conflict resolution T113 × T117 (`libs/video/tests/test_fp_span.c`) | new |

T115 `17b16cb` was already in the base as `4a74174`, so its cherry-pick was aborted with no change.

## 3. Integrated corrections

Every correction from the T145 chain is included, plus:

- T115B exact texture cache with CONTROL3 row pitch (`RSX_TEX_CACHE`)
- T144 exact guest stencil (`RSX_STENCIL_EXACT`)
- T117's refusal to translate a fragment program with no END

Defaults are unchanged: only `RSX_FP_SPAN` and `RSX_RT_READBACK` are on, as before T147.

## 4. Conflict resolutions

1. **T117 backend 16 KiB window vs T113 `fp_span()`.**
   - T113 already reads through END, up to 64 KiB, at every fragment-program walk.
   - T117's backend half is therefore superseded and was not applied. Only its decompiler half was taken.
2. **`test_fp_span` section 2.** T113's test expected the legacy 4096-byte read to emit a truncated head that fxc rejects (X3004).
   - With T117, the decompiler returns -1 instead. `RSX_FP_SPAN=0` now fails the draw cleanly.
   - The test now pins the combined behaviour: `n_old < 0`, and the bx2 scan finds nothing.
   - The span path (the actual fix) is unchanged and still checked to compile.
3. **T116 and T143** (performance) conflict with the T147 tip in `rsx_d3d12_backend.c` (`git merge-tree`, non-destructive). Not picked; handed to T146 (§10).

## 5. Test results

**Suite** (`tools/run_suite_t147.cmd`, log `logs_suite.txt`): **54 PASS / 1 FAIL**.
- The suite covers:
  - the T145 suite
  - T115B pins, T144 stencil-exact, RT clip and SRV layout, FP shadow-compare, FP alias
  - the C tests for the texture cache, the fp decompiler, and the WARP tests for T115B, T137, T141, T144 and T145
- The one FAIL is `test_rt_pool_srv_layout` ("pool evicts only surfaces unused this frame"). It **fails identically on T145**, so it predates T147 and is not an integration regression.

**Real-backend harnesses** (`tools/run_arms.sh`, log `logs_arms.txt`, `runs/arms/`):
- Harnesses: T137, T141, T142, T144, T145.
- Presets: A, B, C, D, D_xfer7, and D with GBV.
- Result: all rc=0, with **0 debug-layer and 0 GBV errors**. The only warning is the benign ClearRenderTargetView clear-value message (id 820).

**Own-checker arms:**
- T145 arms with `wpos_check`: 0 failures.
- T142 arms with `sampling_check`: 0 failing arms.
- On the preset arms, C, D, D_xfer7 and D_gbv pass the sampling check, and the shader-window identity holds.
- A and B "fail" those two checkers, as expected: they leave `SHADER_WINDOW` and `RT_WINDOW` off, and those checkers expect them on.

## 6. Build results

| Item | Value |
|---|---|
| Source commit | ps3recomp `d76e08e` (T147 tip); lifted PPU from `generated/ppu-hooked-staging`; SPU on |
| Script | `generated/analysis/t147/build_t147.cmd` (options as `t145/ab/build_b.cmd`) |
| Compiler | clang-cl, LLVM 23.1.3 (`build/llvm`); MSVC vcvars64 (VS 18); Ninja; Release |
| Result | **success**: 280/280 steps, exit 0. Warnings only. Log: `build_t147.log` |
| Exe | `build/motorstorm-t147/MotorStormPacificRiftRecomp.exe`, 379.2 MB |
| SHA-256 | `1abedc92a62e97cf201dc3176c203ec043a869f28e199495163ce4488d611553` |
| Switches enabled at build time | none. Every feature is a runtime environment switch (see §8) |

## 7. Remaining defects (all untested in game unless stated)

- **RT windows:**
  - Two different RT window sizes requested in one frame are logged but not fixed.
  - Right and bottom edges are correct only with `RSX_RT_WINDOW=1` (plus T142).
- **WPOS and fragment programs:**
  - WPOS is mirrored without `RSX_SHADER_WINDOW=1`.
  - FP `SRC2.abs` is not decoded.
- **Water:** the bright surf band and the dark water dots are unresolved, with no verified cause (HYPOTHESIS only).
- **Colour transfer:** `RSX_COLOR_XFER=7` has never run in game.
- **MSAA, stencil and scissor:**
  - No 4× MSAA.
  - Alpha-to-coverage and sample order are unknown.
  - Back-face stencil uses the front values.
  - Scissor is ignored.
- **Performance:** the race is guest-bound at about 5 FPS, which is out of scope here.
- **Pre-existing test failure:** `test_rt_pool_srv_layout` (see §5).

## 8. Preset configurations (`presets/*.cmd`)

Each preset first clears the `RSX*`, `GCM_*`, `PS3_*`, `VP_*`, `D3D12_*`, `RACE_*`, `CELLMARK*`, `FP_*` and `RSXI*` variables. It then sets every switch explicitly and sets `T147_PRESET`.

| Preset | Switches on (all others 0) |
|---|---|
| A_conservative | `RSX_FP_SPAN=1`, `RSX_RT_READBACK=1` (= current defaults) |
| B_texture | A + `RSX_TEX_MIPS=1`, `RSX_TEX_CACHE=1`, `RSX_GUEST_SAMPLERS=15` |
| C_shader_rt | A + `RSX_GUEST_SAMPLERS=15`, `RSX_RT_WINDOW`, `RSX_RT_FEEDBACK`, `RSX_ZETA_EXACT`, `RSX_MRT_STATE`, `RSX_SHADER_WINDOW` |
| D_full | B + C + `RSX_DEPTH_STATE`, `RSX_STENCIL_EXACT`, `RSX_MSAA`, `RSX_FP_PRECISION` |
| D_full_xfer7 | D + `RSX_COLOR_XFER=7`, kept separate because it is unverified at runtime |

**Bounded game A/B plan (not executed; needs launch authorization):**
- Run the T147 exe once per preset (A → B → C → D → D_xfer7) on the same route, with a draw-gated capture at fixed frames:
  - garage / emblem screen
  - race start
  - race + 60 s, where the water and surf are visible
- Compare each preset with A. Accept a feature only on an objective capture difference against the RSXI reference, not on looks.

## 9. Dependencies

- **Feature dependencies:**
  - T142 behaviour requires `RSX_RT_WINDOW` or `RSX_MSAA`.
  - `RSX_GUEST_SAMPLERS` needs base bit 1 (15 includes it).
  - Offline tests of units other than 0 need `RSX_GUEST_SAMPLERS=15`.
  - `RSX_STENCIL_EXACT` works without `RSX_DEPTH_STATE`.
- **Toolchain:**
  - LLVM 23.1.3 in `build/llvm`
  - VS 18 vcvars
  - Python 3.14
  - Windows SDK `d3dcompiler` (for the fxc checks)
  - WARP and the D3D12 debug layer with GBV (`D3D12_DBG=1 D3D12_GBV=1`)
- **Private inputs (not committed):**
  - `generated/ppu-hooked-staging`
  - `generated/decrypted/EBOOT.elf`
  - `port/spu`
- **Missing:** no in-game validation for any T147-added feature.

## 10. Handoff to T146

- Rebase the performance work onto the T147 tip **`d76e08e`**, not onto T145.
- **Merge status against `d76e08e`:**
  - T119 (`693169a`), T122 (`2b639c2`) and T132B (`8dff95e`) merge cleanly.
  - T116 and T143 conflict in `libs/video/rsx_d3d12_backend.c`.
- **T116 cache key:** the shader/PSO cache key must include:
  - the T120 depth key
  - T133 precision
  - mip levels (T115)
  - the T137 MSAA byte
  - the T141 colour mask
  - the T144 stencil-exact state
- **Known test failure:** `test_rt_pool_srv_layout` fails on both T145 and T147, so treat it as a known failure, not a regression.
- **T122 wrapper:** T122's `ResourceBarrier` counter and `wait_for_gpu` macro need one combined wrapper if T143 also wraps those methods.

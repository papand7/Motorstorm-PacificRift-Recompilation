# T142: render-target texture sizing and sampling

- **Date:** 2026-10-28.
- **Scope:** offline only. No MotorStorm build or launch, no merge, no push. No other agent's worktree or report was edited.
- **Labels:** VERIFIED (measured or read in code) / HYPOTHESIS.
- **Paths:** relative to the workspace.

**Setup:**
- **Ownership (Phase 0):** `ListAgents` showed no other session. There was no `t142` branch, worktree or report, so the task was unassigned.
- **Worktree:** `ps3recomp-t142`, branch `agent/t142-rt-texture-sampling`.
- **Base:** `07b453f`, the T141 tip. It contains T113, T120 (`235b3e6`, `169e618`), T137 and T141.
- **Commits:** `a5171d6` (fix and pins) and `e9f3237` (real-backend regression).

## 1. Original defect and reproduction

### Defect (VERIFIED)

1. With `RSX_RT_WINDOW=1` (T120), a texture that covers part of an offscreen target is sampled from a box copy of its declared size: a window.
2. Each target keeps **one window size per frame**. `win_get` (and `xwin_get` for `RSX_MSAA`) returns NULL for a second size in the same frame, and the caller then binds the **whole** surface.
3. Every *set* texture unit over the target asked for a window, including units the fragment program never fetches.
4. RSX keeps unit state until the guest changes it, so a pass normally still carries an earlier pass's bindings on its other units. MotorStorm's scene size moves every frame (1259–1265 × 708–712), so those stale units declare **last frame's** size.
5. When such a unit is processed first, it claims the window at the stale size. The unit the program actually reads then gets NULL and binds the 1280×720 surface.
6. The result is exactly the T120 #1 symptom that the window was meant to remove:
   - a 1280/W stretch;
   - the never-drawn right columns and bottom rows pulled in;
   - no clamp at the texture's own edge;
   - feedback reads (T141) at the wrong texel.

### Reproduction (VERIFIED)

The test is `libs/video/tests/test_t142_backend.c`: the real `rsx_d3d12_backend.c` with the project's flags, WARP or hardware D3D12, the debug layer, and RSXI end-of-frame snapshots of frame 5 at 1260×708.

| Arm (base `07b453f`) | Magenta-tinted texels in the identity read | Identity read ≠ scene | Clamp at the texture edge | Feedback |
|---|---|---|---|---|
| `RSX_RT_WINDOW=1`, point, with or without feedback, with GBV | 29,040 | 514,486 px | wrong in `nowin` / `win_nogs` | 27,650 px wrong |
| linear | 29,040 | 235,410 | – | – |
| `RSX_MSAA=1`, antialias 3 | 29,040 | 260,112 | 339,536 tinted in the clamp pass | – |
| no window (`nowin`, reference) | identical to the windowed arms | | | |

Every windowed arm on the base gives the same result as having no window at all.

### Second instance in an existing harness (VERIFIED)

- T137's own `test_t137_msaa_backend`, built from the T141 tree, presents a backbuffer that differs from its source target: 57,211 px (`m_win`) and 46,249 px (`m_ms_fb`).
- With the fix it matches exactly (0 px).
- T141's harness avoided the defect deliberately, by rebinding unit 0 to a dummy texture; its own comment describes the mechanism.

## 2. Exact source-level cause (VERIFIED)

`libs/video/rsx_d3d12_backend.c`, the draw-record unit loop (`for (int _u ...)`, off-RT branch):
- `rtwin_get(rt, …)` was called whenever `rtwin_on()` and `rsx_rt_window_of()` held, with no test of `dr->fp_units`.
- The `RSX_MSAA` branch called `xwin_get(rt, …)` the same way.
- `win_get` / `xwin_get` keep one `RtWin` per target, and a second size in a frame returns NULL (silently).
- The fetched-unit information already existed: `fp_units_of()` uses `rsx_fp_texture_units()`, which scans the translated program's TEX/TXP/TXB/TXL/TXD/TEXBEM/TXPBEM instructions up to its END.
- The zeta-as-colour path already used it: unfetched units over a depth surface return early with a NULL view.
- The colour and MSAA paths did not.

**Relevance of unfetched units:**
- Such a unit is never sampled. On RSX its stale state has no effect on what the program reads. Its only influence here was the backend's per-frame window bookkeeping.
- It is not discarded: it still binds the whole resource exactly as before, so descriptors, transitions and RT-readback sampling notes are unchanged.
- `fp_units == 0xFFFF` (program not locatable) still treats every unit as fetched, which is the previous behaviour.

## 3. Corrected behaviour

### Fix (`a5171d6`)

- Only a unit the program fetches may claim a window.
  - Colour path: `rtwin_on() && _fetched && rsx_rt_window_of(...)`.
  - `RSX_MSAA` path: an unfetched unit reads the whole sample image (`_mr = 0`) instead of claiming `xwin`.
- A second size among fetched units is now logged: `[rtwin] 0x… a second size WxH in one frame …`.
- **Opt-in status:** behaviour changes only with `RSX_RT_WINDOW=1` or `RSX_MSAA=1`, both of which are already opt-in. No new switch was added.

### Expected behaviour per Phase 2 case

| Case | Behaviour | Status |
|---|---|---|
| Several units on one target, one fetched | the fetched unit's declared size decides the window; the others bind the whole resource and are not read | VERIFIED (test) |
| Different sizes, only one fetched | as above (the defect case) | VERIFIED |
| Different sizes, **both fetched**, in one frame | each should get its own window. **Not implemented:** the second size still binds the whole target, now logged | limitation (§7) |
| Same target, point and linear | each identity read equals the target exactly at texel centres | VERIFIED |
| Draw samples its own render target | T141's feedback copy, of the window when the read has one; middle region = 2 × pre-pass value | VERIFIED |
| Target modified between reads | the window is refreshed by write generation; the read after the modification sees it, the read before does not | VERIFIED |
| MSAA (antialias 3) and non-MSAA | the sample-image window follows the fetched unit; T137's paths are unchanged | VERIFIED |
| Edge clamping | coordinates past 1 repeat the window's last column; requires `RSX_GUEST_SAMPLERS` (§4) | VERIFIED |

## 4. Test results

### Regression: `test_t142_backend` (`e9f3237`)

- Run with `t142/tools/run_arms.sh`; checked by `t142/tools/sampling_check.py`; log in `logs/arms_base_fix.txt`.
- **Base `07b453f`:** 7 of 7 windowed arms **FAIL**.
- **Fix:** 7 of 7 **PASS**: point, linear, point + feedback, linear + feedback, MSAA, GBV + feedback, and the no-guest-samplers arm.
- Checks in each passing arm: 0 tinted texels, identity reads exact, 0 stale-read errors, clamp exact, feedback exact.
- **Debug layer:** 0 errors in all arms, base and fix. The 32 perf warnings ("clear values do not match") are identical in both.
- **GPU-based validation:** 0 errors.
- **Baseline issue, reported separately (VERIFIED, pre-existing):** without `RSX_GUEST_SAMPLERS`, units 1–15 sample WRAP (`rsx_d3d12_backend.c` default samplers), so the guest's clamp and filter are not honoured on those units (`win_nogs`). That is T133's switch, not this defect.

### Existing harnesses, T141 tree vs T142

| Harness | Result |
|---|---|
| T141 `test_t141_backend` (`win_fb`, `all`) | identical snapshots (3 of 3); feedback middle 221,056 px = 128 in both |
| T137 `test_t137_msaa_backend` (`m_win`, `m_ms_fb`) | RT_A, RT_B and RT_D identical. The backbuffer **changes from wrong to exact** (§1). |

### Renderer suites (`logs/renderer_suites.txt`)

Identical results on T141 and T142:
- 0 failures in each of:
  - `test_rt_window` (2 new T142 pins; its WARP test 21/21);
  - `test_blend_feedback`;
  - `test_msaa`;
  - `test_d3d12_blend_state`;
  - `test_d3d12_color_xfer`;
  - `test_d3d12_depth_state`;
  - `test_d3d12_rsxi_hooks`;
  - `test_d3d12_shader_trace`;
  - `test_d3d12_texture_source_order`;
  - `test_depth_state`;
  - `test_fp_shadow_compare`;
  - `test_fp_span`.
- **Baseline failures, on both trees:**
  - `test_d3d12_zeta_pool` and `test_fp_alias`: their harness does not build with this clang (`_CRT_DEPRECATE_TEXT` errors).

### Public audit

`audit_public.py --staged` before each commit: the 25 inherited items only, none in a T142 file.

## 5. Performance implications

- The fix adds one bit test per texture unit per draw.
- Fewer resources churn: a stale unit no longer creates or retires a window at an old size.
- Reads that were whole-surface now copy the window: 1260×708 instead of 1280×720, about 3% fewer bytes. Feedback copies in the harness went from 24 to 23 MiB over 8 frames.
- The scene still resizes about once per frame. Windows are retired without a GPU wait (T120), so this is unchanged.
- **No GPU synchronization added.**

## 6. Interaction with T120 and T141 (VERIFIED in code and tests)

- **T120:** the fix restores the intended window behaviour; T120's coordinates, clamp and refresh by write generation are unchanged.
- **Zeta windows:** were already protected by the fetched-unit rule.
- **T141 feedback:**
  - `RSX_RT_FEEDBACK` already required a fetched unit, and with a window it copies the window.
  - Previously a stale-unit claim could leave the feedback read without a window, so it took the whole-target `fbwin` copy and read at the stretched texel (`H feedback` 27,650 px wrong on the base).
  - Now it reads at its own pixel (0 wrong).
  - T141's dummy rebinding in its harness is no longer needed; it was left untouched.

## 7. Remaining limitations

- **Two fetched sizes of one target in one frame:**
  - Each would need its own window: a small set of windows per target, keyed by size, with per-unit selection at replay. That is not implemented.
  - The second read still binds the whole target, and is now logged.
  - Whether MotorStorm does this is **HYPOTHESIS** (T120's captures show one size per frame for the scene targets). The validation in §8 counts the log line.
- **`fp_units` depends on the FP span** (T113's END-based scan, or T117's 16 KiB window).
  - A truncated program would hide a later TEX. That unit would then lose its window, which is the pre-T120 behaviour (whole target), not something worse.
  - T120 notes that T117 must be reconciled before integration.
- **Default samplers:** units 1–15 WRAP without `RSX_GUEST_SAMPLERS` (T133).
- **Depth read as depth with a sub-window:** still not windowed (T120 limitation, unchanged).
- **No in-game verification:** nothing was built or launched.

## 8. Proposed bounded runtime validation (needs authorization)

1. **Build:** the T142 tip (`e9f3237`), with the T141 A/B recipe.
2. **Common switches:** `RSX_TEX_MIPS=1 RSX_GUEST_SAMPLERS=15 RSX_DEPTH_STATE=1 RSXI=1`; route and capture time as in T113/T141; race entry + 90 s.
3. **Arms**, in the order A B B A:
   - **A:** `RSX_RT_WINDOW=1 RSX_RT_FEEDBACK=1` on the **T141** exe;
   - **B:** the same on the **T142** exe.
4. **Measures:**
   - the `[rtwin]` lines: window sizes per target, and any `second size` line (§7);
   - RSXI `window` fields of the scene readers (ops 544, 555, 594–598) against their declared texture sizes;
   - T120's right-edge metric on the backbuffer: left-neighbour repetition at x ≥ 1250;
   - debug-layer errors;
   - FPS (expected unchanged).
5. **Expected (HYPOTHESIS):** any A frame in which a stale unit claimed the scene window shows whole-target binding on that frame's scene readers; B shows none.

## 9. Integration order (do not merge here)

- T113 → T120 → T137 → T141 → **T142**. All of them are ancestors of T142, and T142 adds no conflicts with them.
- **T117** (`agent/t117-fp-ucode-window`) already conflicts textually with the T141 tip in `rsx_d3d12_backend.c` and `tools/test_t110_pins.py` (`git merge-tree`). T142 adds no new conflict file.
  - It should be reconciled before or with T142, because T142's rule relies on `fp_units` seeing the whole program.

## 10. Files

- **Source:**
  - `libs/video/rsx_d3d12_backend.c`;
  - `tools/test_rt_window.py`;
  - `libs/video/tests/test_t142_backend.c`.
- **Tools** (`generated/analysis/t142/tools/`):
  - `bb.cmd`, `build_backend_test.py`, `tu_flags.cmd`: the build with the project flags, adapted from T141;
  - `run_arms.sh`, `sampling_check.py`;
  - `patch_t142.py`.
- **Logs:** `logs/arms_base_fix.txt`, `logs/renderer_suites.txt`, `logs/audit_c*.txt`. Runs are in `runs/`.

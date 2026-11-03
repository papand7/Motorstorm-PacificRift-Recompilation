# T169: regression validation

**Result: no new failure traces to T169 code. `test_spurs_kick_wake` is a flaky test, not a regression (see the end of this file).** Rendering results: `D2_F2_GAME_RESULTS.md`.

## Preflight for D2 and F2 (ps3recomp `774c81d`)

Logs: `logs/preflight2/`, not committed.

| Check | Result | Label |
|---|---|---|
| Build | rc 0; Release, clang-cl 23.1.3, `/O2 /Ob2 /DNDEBUG`; exe sha256 `02b5c83c…a23a6f` | VERIFIED |
| `test_t169_profile` with negative control | 0 failed | VERIFIED |
| `test_t169_visual` and WARP D3D12 fixtures | rc 0; 0 failed | VERIFIED |
| Full suite, 166 entries | PASS 120, FAIL 3, SKIP 43, TIMEOUT 0 | PARTIAL |
| `audit_public.py --tree` on the changed ps3recomp files | Passed | VERIFIED |
| Runner dry run, D and F | Hash OK; switches as requested; only the known `SRC_EXE` name hit | VERIFIED |

**Suite failures:**
- `test_rt_pool_srv_layout` ("pool evicts only surfaces unused this frame"): inherited, same on `b1eb158`.
- `test_vpc_watch` ("the environment is read once", and its fixture lacks `<time.h>`): inherited, same on `b1eb158`.
- `test_spurs_kick_wake`: new in this suite. It fails 3 of 3 alone on `774c81d`, and 1 of 1 alone on `001a56f`, which passed it earlier today. No file it builds differs between those commits.

**Why the SPURS failure didn't block launches:** the test asserts that wake-on halves the median of wake-off. Wake-on is unchanged (53 → 56 µs), but the wake-off median fell from 8,550 to 53 µs, with the p90 still near 16 ms. So the machine's baseline changed. Why it changed is unknown (HYPOTHESIS: timer resolution held by another process). The test itself remains failing, not fixed.

## Earlier validation (`001a56f`)

Code: ps3recomp `001a56f` on `b1eb158`. Logs: `logs/` in the main checkout (`visual.txt`, `warp.txt`, `suite.txt`, `suite/`, `backend_syntax.txt`, `build.txt`), not committed.

| Check | Result | Label |
|---|---|---|
| `test_t169_visual` (WARP, debug layer on, pins) | 138 checks, 0 failed | VERIFIED |
| Existing WARP fixtures: t110 88, t133 35, t137 warp 49, t137 logic 27, t141 41, t144 191, t145 35, t115 24, sampler_xlate 2199, tex_mips 48 | All rc 0 | VERIFIED |
| `test_decal_depth` fixture (`tools/decal_depth_fixture_t169.c`, untracked by the root `.gitignore`) | 8 pixels covered either way, on opposite sets; PS invocations 16/16 | VERIFIED |
| `test_rsxi_parse_t169.py` | Passes | VERIFIED |
| Backend syntax check | rc 0 | VERIFIED |
| Full tools suite, 165 scripts | PASS 120, FAIL 2, SKIP 43, TIMEOUT 0 | PARTIAL |
| Full executable build | rc 0 | VERIFIED: links only |
| `tools/audit_public.py --tree` on the changed ps3recomp files | Passed | VERIFIED |
| Corrections in game | D1 and F1 ran at baseline; profile not applied | BLOCKED |

**Suite limits:**
- It ran before the final edits to `rsx_visual_profile.h` and the test. The backend hooks were already in. `test_t169_visual` and the build ran after those edits; the suite wasn't repeated.
- Both failures also occur on base `b1eb158`, so this work didn't cause them: `test_rt_pool_srv_layout` ("pool evicts only surfaces unused this frame") and `test_vpc_watch` ("the environment is read once"). Neither is fixed.
- The 43 skips are mostly POSIX or Metal tests, so those paths weren't exercised.

**Build:** `build/motorstorm-t169/MotorStormPacificRiftRecomp.exe`, 410,805,760 bytes, sha256 `766c45916524b85ff5343807c6bd467f8ec0e07097aba9fa9ab37b3d17f70491`. The backend object was compiled at 15:01:39, after the commit at 15:01:11 and after the last source edit. Never launched.

**Preflight rerun on the final source, before the game runs:** suite PASS 120, FAIL 2 (the same two), SKIP 43, TIMEOUT 0; `test_t169_visual` and all WARP fixtures rc 0; exe hash re-verified. Audit: `--staged --private-reports` (what the hook runs) passes; strict `--staged` has 50 findings, all the path rule on generated reports (30 T169, 20 from T138, T139 and T165), none on content; `--tree` on the ps3recomp files passes.

**Regression found by the game runs:** `RSX_VISUAL_PROFILE` has no effect in the game (`GAME_VALIDATION_PLAN.md`). The test passed because it pins source text, not behaviour. Not fixed.

**Not covered:** real-GPU behaviour, frame time, memory in game, sand boxes, tyres, grain and edges in the actual scene, and any bit combination beyond the fixtures. `GAME_VALIDATION_PLAN.md` covers these, pending approval.

## Vehicle isolation update (ps3recomp `542420e`)

**Suite:** PASS 121, FAIL 3, SKIP 43. **WARP fixtures:** 10 of 10 pass. Backend-level `test_t169_rt_reinterp`, `test_t169_profile` and `test_t169_visual` pass.

**`test_t169_rt_reinterp` (new, real backend on WARP):** tagged pixel values through the velocity chain.

| `RSX_DEPTH_STATE` | `RSX_RT_REINTERP` | Pixel R,G | Meaning |
|---|---|---|---|
| 0 | 0 | 0, 0 | Wiped: the old renderer |
| 1 | 0 | 1, 56 | **The defect:** kept, read as bytes |
| 1 | 1 | 128, 64 | **Corrected:** x 0.50048828, y 0.25 |
| 0 | 1 | 0, 0 | Wiped: zero stays zero |

**Failures:**
- `test_rt_pool_srv_layout`, `test_vpc_watch`: inherited.
- `test_d3d12_shader_cache`: **new, one failure, cause unknown.** Its child exe returned non-zero with no output in the suite, then passed 10 of 10 repeats (2 plain, 8 in the suite's environment). It doesn't build the backend, and the text checks on the backend passed. PARTIAL as unrelated.

### `test_spurs_kick_wake`: flaky test, not a regression

**Classification: flaky; no regression VERIFIED.** Harness: `tools/spurs_kick_matrix_t169.py`, interleaved, 14 runs, High performance power scheme. `libs/spurs`, `runtime`, `tests` and the two test scripts show no diff between the three revisions.

| Revision | Condition | Runs | Failed | Off median, range (us) | On median, range (us) |
|---|---|---|---|---|---|
| `774c81d` current | idle | 4 | 3 | 53-15401 | 40-60 |
| `001a56f` earlier pass | idle | 3 | 3 | 50-69 | 42-60 |
| `b1eb158` baseline | idle | 3 | 3 | 53-63 | 42-60 |
| current / baseline | 1 ms timer held | 1 / 1 | 1 / 1 | 56 / 55 | 46 / 47 |
| current / baseline | all cores loaded | 1 / 1 | 0 / 0 | 13870 / 6948 | 49 / 44 |

- **Why it flips:** the test asserts `on * 2 < off` on the median across four sections. With the wake off, latency is bimodal: about 50 us or about 7-16 ms. The median can land on either mode with the same code.
- **The wake still works:** on-median stayed 40-60 us and on p90 at most 135 us. Off p90 reached about 7-16 ms in at least one section of every run.
- **Environment:** every revision fails idle and the two loaded runs pass, so load pushes off towards the slow mode. Timer resolution doesn't decide it: holding 1 ms failed, and 15.6 ms both passed and failed. The final idle run and the later suite run (off 6842 us) passed on current code, so what sets the mode when idle is **unresolved**.
- **Thresholds unchanged.** Comparing p90 would match what the wake improves, but that's a test change for its own review.

## Velocity validation preflight (ps3recomp `542420e`, exe `59019e06...ba08`)

**No new deterministic regression.** Suite: PASS 122, FAIL 2, SKIP 43. Failures: inherited `test_rt_pool_srv_layout` and `test_vpc_watch`. WARP fixtures: 10 of 10. `test_t169_rt_reinterp`: 0 failures. Public audit passed. `RSX_RT_REINTERP` reads as on only for exactly `1`.

- **Build:** incremental in `build/motorstorm-t169` from a clean `542420e` worktree, pinned as `ab/exe_c`. The `774c81d` exe stays pinned as `ab/exe_t`.
- **`test_spurs_kick_wake`:** PASS this run (off 11084 us, on 51 us). Still classified flaky: the pass doesn't change that.
- **`test_d3d12_shader_cache`:** PASS this run. Its one earlier failure remains unexplained.
- **Coverage gap found in game:** the test passes while the game's velocity readers are refused, since the fixture binds no cube unit. A green `test_t169_rt_reinterp` doesn't show the correction reaches the game.

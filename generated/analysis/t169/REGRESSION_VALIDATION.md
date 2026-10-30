# T169: regression validation

**Result: no new failure traces to T169 code. `test_spurs_kick_wake` is new on this machine but also fails on the earlier commit that passed it, so it isn't this change.** Rendering results: `D2_F2_GAME_RESULTS.md`.

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

**Not covered:** real-GPU behaviour, frame time, memory in game, sand boxes, tyres, grain and edges in the actual scene, the `0xBF` smear risk with `RSX_DEPTH_STATE`, and any bit combination beyond the fixtures. `GAME_VALIDATION_PLAN.md` covers these, pending approval.

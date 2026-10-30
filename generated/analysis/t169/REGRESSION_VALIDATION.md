# T169: regression validation

**Result: the opt-in code passes every offline check that ran. No game run exercised it, so nothing here shows the game is fixed.** Defaults are unchanged: with `RSX_VISUAL_PROFILE` and `RSX_VISUAL_DIAG` unset, no switch is set by the new code.

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
| Game launch, in-game debug layer, FPS | **Not run; none authorised** | BLOCKED |

**Suite limits:**
- It ran before the final edits to `rsx_visual_profile.h` and the test. The backend hooks were already in. `test_t169_visual` and the build ran after those edits; the suite wasn't repeated.
- Both failures also occur on base `b1eb158`, so this work didn't cause them: `test_rt_pool_srv_layout` ("pool evicts only surfaces unused this frame") and `test_vpc_watch` ("the environment is read once"). Neither is fixed.
- The 43 skips are mostly POSIX or Metal tests, so those paths weren't exercised.

**Build:** `build/motorstorm-t169/MotorStormPacificRiftRecomp.exe`, 410,805,760 bytes, sha256 `766c45916524b85ff5343807c6bd467f8ec0e07097aba9fa9ab37b3d17f70491`. The backend object was compiled at 15:01:39, after the commit at 15:01:11 and after the last source edit. Never launched.

**Not covered:** real-GPU behaviour, frame time, memory in game, sand boxes, tyres, grain and edges in the actual scene, the `0xBF` smear risk with `RSX_DEPTH_STATE`, and any bit combination beyond the fixtures. `GAME_VALIDATION_PLAN.md` covers these, pending approval.

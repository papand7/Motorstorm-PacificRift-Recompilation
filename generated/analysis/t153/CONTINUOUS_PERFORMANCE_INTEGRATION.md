# T153: continuous performance integration (checkpoint 3)

Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. The authorised game A/B (14 launches) was run on 2026-10-29; its results are in §8 and `UNIFIED_GAME_AB_RESULTS.md`. The matrix is in `PERFORMANCE_MATRIX.md`.

## 1. Trees and hashes

| Item | Value |
|---|---|
| base (known-good checkpoint) | `ps3recomp-t153-base`, detached at T146 `80fe5de`, with `port-t153-base` (= `port/`) |
| integration worktree | `ps3recomp-t153-performance-integration`, branch `integration/t153-continuous-performance` (local only, not pushed or merged) |
| integration commits | `80fe5de` → `8796394` (T150 `b513c55`) → `0380cb5` (T150 `dd0beee`) → `31abdae` (T151 `eda5223`) → `2a764e1` (T152 `aca2ebd`) |
| integration port | `port-t153` = `port/` + T150 `alloc_guest_vm` `MEM_WRITE_WATCH` flag (`patches/t150_wwatch_port.patch`) + T151 `PS3_FRAME_CLOCK_KICK` (`patches/t151_frame_clock_kick.patch`, root `407dea1`) |
| build | `tools/build_t153.cmd base\|int` (Ninja Release, clang-cl 23.1.3, `generated/ppu-hooked-staging`, SPU on, HLE NIDs generated); both `rc=0` |
| base exe | `build/motorstorm-t153-base`, sha256 `7a335d77b9b624d813edd76c72d2d84ec49ac9790c41b83a3f928610932e535f` (preserved, also pinned as `t153/ab/exe_a`) |
| integration exe, checkpoint 1 (T150+T151, at `31abdae`) | sha256 `38adde9894aa66b6a2a928218a6268e8dc1cd084c5fd32e0e041faae02a81a67`, preserved as `t153/ab/exe_i_cp1/` |
| integration exe, checkpoint 2 (+T152, at `2a764e1`) | `build/motorstorm-t153`, sha256 `bade0abb2283d5c4a08da8f648e1961dbc9253606af6d5ba74c860e93ba19a57` (`rc=0`; contains the `[icall-fast]` log string), pinned as `t153/ab/exe_i` for arms Z, B, C, D and E |

Builds are not bit-reproducible across source paths, so the hash identifies an exe, not a source state.

## 2. Integrated optimizations (all opt-in; every default is T146's)

| Commit | Owner | Switch | Tests | Offline evidence | Risks | Reversion |
|---|---|---|---|---|---|---|
| T150 `b513c55` + `dd0beee` | T150 | `PS3_TEX_SNAPSHOT_WWATCH=1` (+ `PS3_TEX_SNAPSHOT_STATS`) | `test_tex_snapshot_wwatch`, `c_tex_snapshot` (65), GPU harness | snapshot capture 53.05 → 1.78 ms/frame (both 0.10) (PARTIAL, synthetic) | a host write path that bypasses the watched reservation | unset the switch; `git revert 8796394 0380cb5`; drop the port hunk |
| T151 `eda5223` | T151 | `RSX_VP_FAST_FETCH=1` | `test_vp_fetch_plan`, `test_vp_expand`, GPU harness (16 configs) | draw callbacks 10.5 → 6.85 ms (compact + epoch) (PARTIAL, synthetic) | an attribute format outside the plan (falls back per attribute) | unset; `git revert 31abdae` |
| T151 root `407dea1` | T151 | `PS3_FRAME_CLOCK_KICK=1` | `test_frame_clock_kick_t153.py` (8 PASS) | ≈ 1.7 ms mean saved per fence wait (HYPOTHESIS for the game) | a lost kick costs one 4 ms tick (the wait is bounded), not a hang | unset; drop the port hunk |
| T152 `aca2ebd` | T152 | `PS3_ICALL_FAST=1` | `test_icall_fast` (13 scenarios, full vs fast transcripts identical) | hot indirect call 15.2 → 5.9 ns, 2048/65536 targets 35 → 27 ns (PARTIAL, micro-bench) | a probe switch the fast path does not know (it refuses on 20 listed ones) | unset; `git revert 2a764e1` |

## 3. Verification review (§4, §5, §6)

**T150 write-watch (VERIFIED by test and review).**
- Guest stores, host `memcpy`/DMA and SPU writes into the reservation mark the page. `GetWriteWatch(RESET)` advances that page's generation, so the next lookup misses and the texture is rehashed. `test_tex_snapshot_wwatch` covers PPU, host and SPU-style writes, aliases (two textures on one page), an RT written by the GPU and then sampled (RT feedback keeps its own invalidation), concurrent writes during a lookup, and release and reuse.
- **Epoch behaviour:** the T122 epoch check stays first. Write-watch only adds the `wgen` comparison after a valid epoch, and never skips a hash the epoch requires.
- Outside a watched reservation (the harnesses), the first lookup fails (state -1), and from then on the store hashes exactly as before. The GPU harness confirms this pixel for pixel.

**T151 fast fetch (VERIFIED).** It covers compact, full (fat) and dynamic (per-draw stride) layouts: `test_vp_fetch_plan` and `test_vp_expand`, plus the `dpfat`/`dpcomp`/`dpperf`/`dpvis`/`dpgbv` arms.

**T151 kick (VERIFIED by test and review).**
- Notifications are not lost: it is an auto-reset event, so a kick before the wait wakes the next wait.
- Fence waits terminate: the wait is bounded at 4 ms, as `Sleep(4)` was.
- FIFO order is unchanged: the work after the wait runs in the old order (vblank, beats, flip, drain, pump).

**T152 icall fast path (VERIFIED by test and review).**
- The five switches the full path reads but the probe list omits (`PS3_NULL_CALL`, `PPU_OPD_RECOVER`, `PPU_NOOP_BAD_VCALL`, `PPU_VCALL_BT`, `PPU_STUCKMAX`) only gate the null, unregistered and garbage-target paths and the stuck-loop guard. All of those come after the registered-target `return`, and the fast path hands those cases to the full path untouched.
- The registry generation is bumped after the insert, so a cached entry is never served stale.
- Unlike the full path, the fast path does not re-pin r2 under `PPU_TOCFIX`, but that switch is in the refusal list.

## 4. Conflicts

- **ps3recomp:** none. The T150 snapshot hunks, the T151 VP section and the T152 `ppu_loader.cpp` hunks are disjoint, and every cherry-pick applied cleanly (`-x` records the source commit).
- **port:** the two root port changes (the `VirtualAlloc` flag and the frame-clock loop) were merged by hand into `port-t153`, because they touch different functions.

## 5. Tests

| Run | base `80fe5de` | integration (T150+T151) |
|---|---|---|
| full suite (`run_all_t153.cmd --jobs 6`, `logs/suite_run.txt`) | 134 PASS / 43 SKIP / 2 FAIL | 136 / 43 / 2 |

- **Per test:** every test present in both trees has the same verdict. The two extra passes are the new `test_tex_snapshot_wwatch` and `test_vp_fetch_plan`.
- **Known failures (in both trees, inherited from T146, not regressions):** `test_rt_pool_srv_layout`, `test_vpc_watch`.
- **Under load:** `test_spurs_kick_wake` and `test_spurs_wws_stress` passed this time. T151 saw `test_spurs_kick_wake` fail under load only. Rerun timing tests alone (`--jobs 1`) before treating a failure as real.
- **Frame-clock kick:** `test_frame_clock_kick_t153.py ps3recomp-t153-performance-integration`: 8 PASS.
- **T152 (`2a764e1`):** `test_icall_fast` and `test_ppu_lift` (1533 checks) PASS. Full suite on `2a764e1` (`logs/suite_run2.txt`): 137 / 43 / 2, the T150+T151 result plus `test_icall_fast`, with the same two known failures. The GPU harnesses run no PPU indirect calls, so T152 is covered by its own test and arm E.
- **GPU harness** (`tools/harness/t153/correct.sh`, from `t153/`):
  - 7 real-backend harnesses built from the integration tree;
  - 16 configs, each run off (`RSX_NONE=1`), on and rerun_on (`RSX_VP_FAST_FETCH=1 PS3_TEX_SNAPSHOT_WWATCH=1`), with the D3D12 debug layer, GBV on two configs and RSXI byte comparison.
  - Result (VERIFIED): 48 runs, no errors or corruption, and the same inherited clear-value perf warnings off and on. All 32 on and rerun_on arms are byte-identical to off (`logs/correct.txt`).

**Runner and baseline tracking (§9):**
- `tools/run_all_t153.cmd [--only a,b] [--jobs N] <tree>...` runs every `tools/test_*.py` plus the WARP and C tests of each tree, and prints a per-tree SUMMARY and FAILED list.
- To separate regressions from baseline failures, run it on `ps3recomp-t153-base` and the integration tree together and diff the per-test verdicts (`logs/v_*.txt`).
- `correct.sh` adds the GPU validation.
- Neither runs during timing work. Restore `scratch/ppu_conformance*` afterwards (the suite rewrites them).

## 6. Pending and staged

- **T147 visual correctness (staged, not integrated).** Two commits from tip `d76e08e` are not in the base:
  - `f986282`: the RSX FP decompiler refuses a program with no END inside the window. Its `merge-tree` dry run is clean.
  - `d76e08e`: `test_fp_span.c`. It conflicts with the base's `test_fp_span.c`.

  The rest of T147 is already in the base (`git cherry` equivalents; `1dff0eb` is present by content). These are visual and shader-acceptance changes, so they go in as a separate checkpoint with their own tests and a game visual check, never together with a performance change.
- **T148 `373040c`:** NP/RPCN, RE workbench and capture tools; nothing performance-related to integrate.
- **T152:** further work in the T152 worktree is uncommitted (`ppu_loader.cpp`, `spu_coherency.c`, `ppu_lifter.py`). It is not integrated until it is committed with tests.

## 7. Policy status

- Every default is T146's; nothing was promoted from synthetic results.
- Each optimization has its own switch, so the A/B can isolate it (arms B, C and E in the matrix).
- The known-good checkpoint is the base tree plus `7a335d77`.

## 8. Game A/B (authorised, done 2026-10-29; `UNIFIED_GAME_AB_RESULTS.md`)

All 14 launches (A, P, Z, B, C, D, E × 2) were valid.

| Arm | A | P | Z | B | C | D | E |
|---|---|---|---|---|---|---|---|
| FPS | 6.41 | 7.27 | 6.50 | 7.27 | 7.13 | 7.20 | 7.17 |

- **The preset gives +13 %.** T150, T151 and T152 add nothing measurable on top of it: they are correct and neutral.
- **Fastest verified configuration:** P, or B (preset + write-watch). Every default stays as it is.
- **Limit:** the PPU frame thread, whose roughly 64 ms of running time includes about 30.7 ms of busy-spin at `0x50C818` waiting for SPU Wws job completion. No integrated change reduced that spin. Wws AOT and T152's inline stores are not in the integration exe.

## 9. Next step

Integrate T152's `MSPR_WWS_AOT` (root `9cd7ef2`) into a port copy and verify it offline. Then request authorisation for B vs B + `PS3_SPU_WWS_AOT=1`, 2 runs each.

# T167: offline validation

Source: ps3recomp `8a12a61`, except that the binaries below were built just before its final edit, which swapped two adjacent lines (`pp_present()` and a diagnostic timestamp). All runs were synthetic on the real D3D12 backend in an RDP session, sharing the machine with other agents. No game launched. Logs are private under `ev/`.

## Correctness

| Check | Result |
|---|---|
| `validate_t167 correct`: heavy, light, seam × async, sync, 4 MB ring, async rerun, against CPU path, by SHA-256 | **VERIFIED:** 0 failures, 6/6, 6/6, 4/4 frames identical |
| Fetch-off frames against T162 fetch-off frames | **VERIFIED:** identical in all 3 cases |
| D3D12 debug layer on all arms | **VERIFIED:** no message |
| `nopso_regress_t167`: forced pipeline failures × cpu, sync, async, 4 MB ring, spill | **VERIFIED:** 57 checks, 0 failures; `nopso = cpu_drawn`, `lost = 0`, so no missing draws |
| Forced fallback really draws | **VERIFIED:** `FP_OFF` changes output; the mixed case differs from both |
| Variant isolation, no stale reuse, compile failure | **VERIFIED:** `test_vs_compile_async`: states, one hand-over, full table, sticky failures. Identical frames with vertices rewritten every frame |
| WARP fetch shader output | **VERIFIED:** `test_gvf` 0 failures, fetch bit-identical |
| No compile failures | **VERIFIED:** 0 in all compile runs and on 34 real programs (benchmark variants) |
| Fence order, resource lifetime, RT dependencies, upload visibility | **PARTIAL:** no code in those paths changed, `test_gpu_sync` and suite pass, identical frames |
| Presentation order, guest RSX refs | **PARTIAL:** Present call changed only in its interval; frames match with the default. Interval 0 output was not compared |

## Suite

`run_all_t167` on the uncommitted tree: 143 PASS, 43 SKIP, 3 FAIL.

- `test_present_progress` was mine, a pin on the old `Present` line. Fixed; it now passes alone, and so do `test_present_diag`, `test_race_present_probe`, `test_vs_compile_async`. The suite was not rerun in full after the fix.
- `test_rt_pool_srv_layout` and `test_vpc_watch` also fail on T162: known, not from T167.

## Before and after, offline

| Metric | T162 | T167 | Source |
|---|---:|---:|---|
| VS compile, game programs, mean ms | 466.4 | 65.3 | real programs, 3 repeats |
| Worst VS compile ms | 989.0 | 128.0 | real programs |
| Total VS compile, 34 programs, ms | 15,858 | 2,220 | real programs |
| Render-thread compile, mixed, ms | 192–197 (T167 sync arm) | 43–45 | synthetic |
| Compile calls / unique, mixed | 9 / 9 | 9 / 9 | synthetic |
| Duplicates | 0 | 0 | synthetic |
| Cache hit rate | not measured | not measured | |
| GPU per pass, mixed, ms | 18.95 (18.94–18.95) | 18.93 | synthetic |
| CPU draw cost, mixed, ms | 142.6 (142.5–154.3) | 141.6 (141.3–142.2) | synthetic |
| CPU fence wait p50, few draws, ms | 93.4–93.7 (interval 1) | 0.0 (interval 0) | synthetic, RDP |
| Frame wall p50, many draws, ms | 92.9–94.7 (interval 1) | 17.3–17.7 (interval 0) | synthetic, RDP |
| Present p50, ms | 0.20 (interval 1) | 0.10 (interval 0) | synthetic, RDP |

T162 binaries for the bench predate T162's final commit by minutes, before its fallback fixes. The prologue was the same. The new prologue shows no GPU cost: `race` passes differ by 0.01 ms, within noise at that size. The T162 column of the fence, wall and Present rows is T167's binary at interval 1, because T162 has no switch.

**No game figure exists for any of these.** The 84 ms is not proven fixed in the game, and the timeout is not proven gone.

## Harness

`test_run_guard_t167`: 24 checks, 0 failures. Each stop condition on synthetic directories: unexpected exit, wrong termination, `GcKernel::Present() Timeout`, controller errors, device removal, Present failures, FIFO resync, missing race frames, missing markers, hash mismatch, slow-mode share. Real T162 B1 stops; real A1 stops only on too few heavy frames.

## Continuation: source `61d32fd`

Run on the tree committed as ps3recomp `61d32fd`. No game launched. The game exe was not rebuilt: `ab/exe_g` is still `b2a720e2…` from `8a12a61`, so it has neither `PS3_KEEP_TIMER_RES` nor `RSX_TIMER_DIAG`.

| Check | Result |
|---|---|
| `run_all_t167` (`ev/suite_t167c.txt`) | 145 PASS, 43 SKIP, 2 FAIL. The two are `test_rt_pool_srv_layout` and `test_vpc_watch`, inherited from T162. This is the full rerun the earlier section lacked |
| `validate_t167 correct` | 60 PASS, 0 failures |
| `validate_t167 compile` | 6 PASS, 0 failures |
| `nopso_regress_t167` | 57 PASS, 0 failures |
| `test_host_timer_res` | 0 failures. Minimized: `Sleep(1)` 15.72 ms by default, 1.91 ms with `PS3_KEEP_TIMER_RES=1` |
| `test_vs_compile_async` | 0 failures, includes the opt-in pin for `RSX_ASYNC_COMPILE_DIAG` |
| `test_run_guard_t167` | 34 PASS, 0 failures, plus the two real runs: T167 A1 rejected with 3 reasons, T162 A1 accepted |
| `test_ab_seq_t167` | 7 PASS, 0 failures |

`correct` covers async on and off; frames match the CPU path. The new diagnostics were pinned and compiled but `[vca]` and `[timer-res]` lines have not been read from a game. These are synthetic or host-level results: none shows that the load is fixed in the game.

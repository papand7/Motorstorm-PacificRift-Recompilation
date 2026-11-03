# T193 correctness results

Tree `ps3recomp-t193`, code commit `72e1001d`; offline, Windows 11, clang 23.1.3 via `generated/analysis/t169/tools/env_t169.cmd`. No game launched. Logs (private, untracked): `generated/analysis/t193/logs/`. All runs below used the final code (run by `generated/analysis/t193/tools/run_final_t193.cmd`).

## Dispatch differential (T192 harness, unchanged semantics)

`py -3 ps3recomp-t193/tools/test_spu_ib_fast.py --seeds 4 --iters 20000` (stats build): **50 PASS, 0 FAIL**: directed 4,148 + 4,156, `reloc` 125, 16 random runs = 1,280,056 checks, threads, stackreset, environment checks, **17 of 17 dispatch negative controls detected**. Identical to T192.

**New: the shipping build.** The same differential on a build **without** `-DSPU_IB_FAST_STATS` (counter assertions compiled to no-ops through `SCHK`, the context comparison unchanged), from `tools/test_spu_ib_telemetry.py`: directed 4,148 + 4,156, `reloc` 125, threads, stackreset, 8 random runs = 640,028 checks: **all pass**. So telemetry does not alter dispatch: both builds produce the resolver's exact context on every checked branch, and the reason counters in the stats build agree with the expected classifications.

## Telemetry tests

`py -3 ps3recomp-t193/tools/test_spu_ib_telemetry.py --iters 20000`: **27 PASS, 0 FAIL** (details `CONCURRENCY_AND_LIFECYCLE.md`, `INTERVAL_REPORTING.md`): lifecycle and id reuse (80 threads, exact totals), 203/203 consistent snapshots under 16 concurrent writers, idle checkpoints, 2^64 wrap, 6 reconfigurations, 3 forced terminations with intact lines, `exit()` during reporting, 4/4 telemetry negative controls, and the stats-off differential above.

## Sanitizers (`generated/analysis/t193/tools/run_sanitizers.py`)

ASan and UBSan, each over `directed`, `directed --tasks`, `reloc`, three random runs (incl. `--reloc`), `threads`, `stackreset`, `tele_threads` (32 + 8 threads), `tele_overflow`, `tele_reinit`, `tele_idle`: **24 runs, 0 failures, no report**. No ThreadSanitizer on Windows.

## Existing suite

`generated/analysis/t193/tools/run_all_t193.py ps3recomp-t193` (the T192 wrapper, which lets `PS3_SPU_IB_FAST*` through; logs `suite_off/`, `suite_on/`). The suite now has 209 tests (new: `test_spu_ib_telemetry`).

| Run | PASS | SKIP | FAIL |
|---|---:|---:|---|
| switch off (default) | 164 | 43 | `test_t169_profile`, `test_t169_rt_reinterp` |
| `PS3_SPU_IB_FAST=1` | 163 | 43 | `test_t169_profile`, `test_t169_rt_reinterp`, `test_spurs_kick_wake` |

Known environmental failures, not regressions: the two `test_t169_*` renderer tests fail with the switch off as well (T192 showed them failing identically with the switch on and off when run alone, and passing in some runs); `test_spurs_kick_wake` is the known flaky timing assertion. With the switch on, `test_spu_ib_fast`, `test_spu_ib_telemetry`, `test_spu_jobspan`, `test_spu_reloc_job`, `test_spurs_wws_concurrency` and `test_spurs_wws_stress` pass.

The suite's own tests build without `-DSPU_IB_FAST_STATS` (only `test_spu_ib_fast` and `test_spu_ib_telemetry` build the stats variant), so "relevant tests with telemetry enabled" are those two; the stats variant was not applied to the other runtime tests.

## Not covered

- POSIX (pthread-key) path: compiles from the same source; not run.
- A killed process mid-`fputs`: not provoked deliberately; partial lines are rejected by the parser by design.
- No lifted program, no game.

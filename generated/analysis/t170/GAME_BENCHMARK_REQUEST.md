Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** One game launch for T170 (arm A).

# Game benchmark request

**Authorized for three launches; stopped after one.** Arm A ran; its post-launch guard failed (FIFO resync after a guest crash), so arms B and C were not launched. See `GAME_BENCHMARK_RESULTS.md`. Arms B and C need the crash explained first.

| item | value |
|---|---|
| exe | `build/motorstorm-t170/MotorStormPacificRiftRecomp.exe` |
| SHA-256 | `f46eb9910d7eb01974fbe43d33b2ad163bd5811eae29a7e60c1c96e1aa80d9c1` |
| source | ps3recomp `fda8c9bc24cd1accde47f5e38e36465b5d190a36`; `port-t161` and `generated/ppu-hooked-staging` as in `tools/build_t170.cmd` |
| scene | T165/T169 route: same flyover skip, into the race |
| launches | **3**, one per arm, no repeats without a new request |
| cap | 205 s game, 210 s host (as T169) |
| frames | at least 500 race and 100 heavy frames, else invalid (`run_guard_t167.py`) |
| profiler overhead | +0.5 ms in the bench; `RSX_PERF_DEEP=1` in all arms |

## Effective environment

All arms: T165/T169 `ENV_LEAN` and `TEXRES` (`RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1 RSX_TEX_BUDGET_MB=1024`), `RSX_PERF_DEEP=1`. **`D3D12_DBG` must be absent.** `RSX_DEPTH_STATE` unset.

| arm | adds |
|---|---|
| A | `RSX_VP_FAST_FETCH=0 RSX_FP_SCAN_MEMO=0 RSX_VP_PARALLEL=0`: write-combined fix only |
| B | `RSX_VP_FAST_FETCH=1 RSX_FP_SCAN_MEMO=1 RSX_VP_PARALLEL=0` |
| C | B + `RSX_VP_PARALLEL=3` |

## Stop conditions

`run_guard_t167.py` pre and post each launch: hash mismatch, remote session, unexpected exit, `GcKernel::Present() Timeout`, device removal, Present failures, FIFO resync, no race entry, too few frames, too many 84 ms frames. Also stop if another game process is running; one was seen on this host during T170 (not launched by T170), and it would contaminate timings. Keep the window visible: a hidden window can collapse SPURS timing.

## Expected evidence

`[perf-deep]` p50/p95 per stage, GPU timestamps, peak and GPU memory; race captures at a matched time for A, B and C, compared for correctness, including vehicles; arm C's sync behaviour; A vs TT3 (91.6 ms) and the critical path recomputed from the results.

## Before launching

The runner is `tools/make_runner_t170.py` (writes the private `ab/run_t170.py`); summaries come from `tools/summary_t170.py`. `PS3_KEEP_TIMER_RES` is absent from this branch because T167 is not merged, so the timer caveat above applies.

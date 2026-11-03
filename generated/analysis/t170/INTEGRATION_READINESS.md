Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# Integration readiness and target assessment

| change | RTX heavy saving | integrated heavy | confidence | risk | complexity | status |
|---|---|---|---|---|---|---|
| Write-combined read fix | 18.3 ms (25%) | 4.7 ms (8%) | high in bench | very low | 1 line | always on |
| Fast fetch + memo | further 14.5 ms (27%) | further 19 ms (34%) | high in bench | low | moderate | opt-in |
| Parallel expansion | none | further 18.5 ms (49%) | high in bench, **never in game** | **moderate: guest ordering** | moderate | opt-in, off by default |
| `RSX_PERF_DEEP` | +0.5 ms | not measured | high | low | small | opt-in |
| Constant-bank reuse | none | not tested | | | | rejected, removed |

## 30 FPS target

**Not shown.** Bench floor on the RTX is 40 ms, above 33.3 ms, and the game has work the bench lacks. A game heavy frame near 50-60 ms from the 91.6 ms baseline is a **HYPOTHESIS**, to be replaced by a measurement. 60 FPS has no path yet.

## Ranked next steps

1. Game run of `GAME_BENCHMARK_REQUEST.md`: nothing else matters as much.
2. Measure upload-heap bandwidth per adapter to settle why parallel helps only one GPU.
3. Integrate GPU vertex fetch (T162/T167) for discrete GPUs.
4. Attribute light-scene `other` (22 ms) and the 84 ms mode.
5. CBV deduplication and SRV creates: small.

## Test state

Full suite at `fda8c9b`: 146 pass, 43 skip, 2 fail. Both failures are inherited: `test_rt_pool_srv_layout` and `test_vpc_watch` fail the same way in the T169 logs. No new deterministic regression. `test_t170_perf` passes.

Three source pins were reworded for changed spellings of unchanged behaviour (`test_shader_window`, `test_d3d12_shader_cache`, `test_tex_snapshot_epoch`); each still requires exact lines.

## Not done

- No game validation of anything here.
- No Radeon 890M run.
- No game GPU timestamps for heavy frames.
- Not merged with T162 or T167.

Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# Benchmark results

**Synthetic, not game numbers.** `bench_draw_path` drives the real backend with the game's largest vertex format (`BENCH_VTX_GAME=1`) and T169's non-debug flags. Interleaved arms, 3 repetitions (2 on the integrated GPU), median of the last 20 frames; quiet host. These draws are all clipped, so GPU load is near zero: this measures CPU cost.

Arms: `base` = `542420e` backend, `off` = this branch with no switch (write-combined fix only), `ffm` = fast fetch + memo, `par3` = ffm + 3 workers.

## Wall ms per frame

| scene | adapter | base | off | ffm | par3 | best vs base |
|---|---|---|---|---|---|---|
| light 2,000 draws | RTX | 20.8 | 15.7 | 11.7 | 12.0 | -44% |
| heavy 6,900 | RTX | 72.9 | 54.6 | **40.1** | 40.3 | -45% |
| vertex 6,900, constants per draw | RTX | 72.5 | 54.5 | 39.5 | 39.7 | -46% |
| shader 6,100, 200-instruction FP | RTX | 86.4 | 70.3 | 35.7 | 35.8 | -59% |
| light 2,000 | integrated | 16.9 | 16.3 | 10.1 | **7.0** | -59% |
| heavy 6,900 | integrated | 61.4 | 56.7 | 37.7 | **19.2** | -69% |

Savings are not additive, so each column is a measured combination.

RTX heavy worker scaling: 39.9 (none), 39.8 (1), 40.2 (2), 40.3 (3), 40.5 (5). Neither GPU predicts a Radeon 890M.

`RSX_PERF_DEEP=1` overhead: 40.4 vs 39.9 ms (+0.5 ms, within run spread).

Scene coverage: texture, sync, feedback and shadow scenes are covered by existing tests and fixtures for correctness, **not by this benchmark**. Real capture replay does not exist. Earlier runs on a busy host differed by up to 30 ms between batches and are not used here.

## Correctness

| check | result |
|---|---|
| Vertex bytes (`RSX_VP_VB_HASH=1`), 24 replays, game and float formats, vs serial | identical for fast fetch, memo, 1/3/8 workers |
| Pixels, game format, 6 frames, 2,000 draws, vs `542420e` | identical for all arms; control arm differs 6/6 |
| Pixels, float format | identical, but **its control did not differ**, so this one is weak evidence |
| Debug layer via DBWIN, 12 frames, on-screen | 0 errors, 0 corruption in bench processes; 4 arms |
| WARP fixtures (T169 set) | 0 failed |
| Full suite | see `INTEGRATION_READINESS.md` |

An earlier pixel run was invalid: the clipped geometry left frames blank, so they matched trivially. `BENCH_VTX_GAME=2` and `BENCH_PIX_CTRL` were added to fix that. Vertex hashes and the debug-layer and WARP runs predate a small later edit (join moved after the replay count, profiler helper, readback flag placement); pixels and the suite were rerun after it.

## Reproduce

```
cd generated/analysis/t170
cmd //c 'harness\b.cmd final'; cmd //c 'harness\bb.cmd'
REPS=3 sh tools/perf_suite_t170.sh sf
sh ev/run_px.sh
sh tools/vbhash_t170.sh vh_game 8 6100 8 64
```
Raw: `ev/perf_rtx.txt`, `ev/perf_more.txt`, `ev/px_final.txt`.

# T171: performance impact

Status: **no regression shown, but no valid FPS comparison.** Another task's work contaminated arm B.

## Contamination

T170's test suite (`run_all_t170.py`, tests such as `test_spurs_kick_wake` and `test_spurs_wws_stress`) started at 20:45:07, about 85 s into arm B, and overlapped arm B's whole race window. The D3D12 message log shows foreign test processes from then on, including GPU-based validation startups. Arm A (20:40-20:43) had none.
Every arm B timing below is therefore an upper bound on the cost, and the gap can't be attributed to the correction. The two authorized launches are used, so this can't be rerun under T171.

## Race frames before the capture trigger

| Window | Arm A | Arm B (contaminated) |
|---|---|---|
| All: frames, FPS | 348, 9.41 | 280, 7.58 |
| All: p50 / p95 / p99 / max ms | 57.6 / 155.7 / 651.6 / 2667 | 71.8 / 245.9 / 2269.6 / 3057 |
| Light (first 15 s, about 1,900 draws): FPS, p50 ms | 12.40, 47.8 | 8.74, 51.4 |
| Light, 3 s buckets at about 1,830 draws: FPS | 21.3-21.5 | 19.6 (6-9 s bucket) |
| Heavy (15-37 s, about 5,600 draws): FPS, p50 ms | 7.37, 134.4 | 6.79, 144.6 |
| Heavy, about 7,300 draws: FPS, rf_ms | 6.1-6.9, 86-99 | 5.7-6.2, 100-102 |

The lower "light" bucket differs in content (61 frames under 1,200 draws in A, 1 in B), so it isn't compared.

## Counters

| Counter | Arm A | Arm B |
|---|---|---|
| Identical early frame (records, draws, verts) | 1453, 1845, 90,479 | 1453, 1845, 90,479 |
| Session PSO misses, ms | 147, 5,574 | 144, 6,394 |
| Race PSO misses | 129 | 128 |
| Compile or PSO failures | 0 | 0 |
| Watchdog `Present() Timeout` | 0 | 0 |
| Longest frame | 2.67 s | 3.06 s |
| Warning 679 (shader output without RTV) | 147 | 82 |
| Warnings 820 / 821 (clear values) | 424 / 1,275 | 1,038 / 1,497, mixed |

- **VERIFIED:** the correction adds no PSO misses and doesn't change the draw count of the identical frame.
- The debug-message log aggregates by message id, so arm B's 820/821 counts mix in the foreign processes and can't be attributed to the game.
- `ERROR 1358` (GPU-based validation, 2 occurrences) is logged under a foreign test pid in arm B, not the game's. The game doesn't enable GBV, and arm A has no such error.
- Structurally the fix adds no draws, copies, barriers or sync.

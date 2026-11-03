Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# Performance baseline

**VERIFIED: T169's 127-132 ms heavy figure is inflated by the D3D12 debug layer.** Its runs set `D3D12_DBG=1` (`t169/tools/make_runner_t169.py`, `VALID`), and the backend enables the layer whenever the variable exists, at any value. `cmd` is 9-10 ms in non-debug game runs and 50-60 ms in T169's (`ev/runs_table.txt`). The bench reproduces the effect: the layer alone moved `cmd` from 3.4 to 39.6 ms.

Do not time with `D3D12_DBG` set, including `D3D12_DBG=0`.

## Game: last runs on record, not re-measured (no launches authorized)

Medians per guest frame; stages overlap, so they do not sum.

| run | scene | wall | expand | rf | record | tex | pso | cmd | wait | other |
|---|---|---|---|---|---|---|---|---|---|---|
| perfnext TT3 (exe 0304156b), no debug layer | heavy 6,777 records | **91.6** | 53.2 | 27.1 | 23.0 | 4.2 | 8.8 | 10.1 | 0.1 | 4.3 |
| perfnext TT3 | light 1,735 records | 49.05 | 13.9 | 8.9 | 5.2 | 1.0 | 1.4 | 2.7 | 0.0 | 22.2 |
| T169 AVA, debug layer on | heavy 6,108 records | 132.3 | 43.6 | | 72.4 | 5.0 | 7.8 | 59.5 | 0.1 | |
| EE4 / T162 DD, 84 ms mode | light | 91-92 | 11-20 | | | 0.9-1.0 | 1.1-1.2 | 1.8-2.1 | 56-66 | |

The non-debug cost of T169's visual flags in the game is **unmeasured**. Peak working set on record: 647-707 MB.

Reproduce: `py -3 tools/baseline_t170.py <run dir>`, `py -3 tools/runs_table_t170.py`.

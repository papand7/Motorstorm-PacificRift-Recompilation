Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# Shader and PSO

`RSX_FP_SCAN_MEMO=1` (opt-in): an exact-byte memo of fragment-program walks (1,024 slots, up to 16 KiB). Bench `pso` 8.7 -> 0.2 ms at 6,900 draws, and 24.3 -> 0.3 ms with 200-instruction programs. Bench hits 2,069,999, misses 1. **VERIFIED in the bench.** Game `pso` is 8.8 ms, so a similar saving is expected but **unmeasured**.

- Bytes are compared on every hit, so a changed program cannot return a stale result. A randomized test compares memo and walk for every result, including after one-byte changes.
- `FP_KDBG` disables it.
- No draw is skipped and no shader substituted; compile behaviour is unchanged.

Asynchronous compilation belongs to T167 and is not merged here. Remaining idea: PSO lookup is a linear scan; low priority now that `pso` is 0.2 ms in the bench.

Two old source pins were updated to the memo's spelling of the same predicate: `test_shader_window.py` (`wk`), `test_d3d12_shader_cache.py` (`fsz`). Neither was loosened: each still requires one exact line.

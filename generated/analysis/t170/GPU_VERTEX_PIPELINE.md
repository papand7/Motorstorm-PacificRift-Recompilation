Commits: ps3recomp `fda8c9b` (branch `agent/t170-major-performance`, on T169 head `542420e`), reports on `agent/t170-performance-report`. Host: Ryzen 5 9600X, 50 GB, RTX 5060 (driver 32.0.16.1088), integrated AMD Radeon (driver 32.0.21042.62, selected by `CELLMARK_IGPU=1`). **Not a Radeon 890M: none is available here.** No game launched for T170.

# Vertex pipeline

## Done, on this branch

| change | switch | heavy bench effect | correctness |
|---|---|---|---|
| Constant c[0] read from the CPU copy, not write-combined memory | always on; same value | RTX 72.9 -> 54.6 ms, **VERIFIED bench** | pixels identical |
| Fast fetch extended to half-float and CMP, the game's largest format class | `RSX_VP_FAST_FETCH=1` (opt-in) | with memo, RTX 54.6 -> 40.1 ms | vertex bytes and pixels identical |
| Parallel expansion | `RSX_VP_PARALLEL=<n>` (opt-in, needs fast fetch) | RTX none; **integrated AMD 37.7 -> 19.2 ms** | vertex bytes and pixels identical |

`RSX_VP_FAST_FETCH` existed since T151 and was validated, but no game run ever enabled it. Generic-fetch attributes stay serial.

## Why parallel helps one GPU only

On the RTX, wall time is flat at 39.8-40.5 ms from 1 to 5 workers. On the integrated GPU, expand falls from 30.2 to 4.5 ms. **HYPOTHESIS:** the RTX path is limited by write bandwidth into the upload heap (131.9 MB per frame in the bench). The upload-heap bandwidth of each adapter has not been measured directly, so the cause is open.

## Guest-visible ordering of parallel jobs

Jobs read guest memory after the draw callback returns, so they are joined at every sync-epoch bump, before a drain publishes `get`, at each replay and before buffer growth. Pinned in `tools/test_t170_perf.py`. This has **never run in the game**, so its interaction with real guest sync is unverified.

## GPU vertex fetch

T162's GPU fetch is not on this branch (it branches from T169, and T162/T167 are separate). Not integrated in T170. It is the next candidate for discrete GPUs because it removes the upload writes that appear to set the RTX floor. It would need T162's staged rollout and CPU fallback.

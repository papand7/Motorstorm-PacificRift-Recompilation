"""T143: put the final-round numbers into the report (one-shot edit)."""
p = 'RSX_GPU_PIPELINE_PERFORMANCE.md'
s = open(p, encoding='utf-8').read()
R = [
('`e2f9435`, and `FINAL_COMMIT` (see §4).', '`e2f9435`, `efae357` (see §4).'),
('| `FINAL_COMMIT` |', '| `efae357` |'),
('passes after `FINAL_COMMIT`.', 'passes after `efae357`.'),
("""### 2.3 Bench, measured (1800 draws, iGPU arm `igpu`, `prof` = profile on, no T143 switch; two runs each)
| ms per frame (mean / p95) | prof | `RSX_BIND_DEDUP` | `RSX_SRV_REUSE` | both |
|---|---|---|---|---|
| render_frame CPU (`cpu_rf`) | 3.75 / 4.69 | 3.66 / 4.62 | 2.61 / 3.40 | **2.46 / 3.16** |
| pre-pass (`cpu_pre`) | 3.31 / 4.17 | 3.29 / 4.18 | 2.16 / 2.85 | 2.11 / 2.71 |
| SRV window fill (`cpu_srv`) | 1.38 / 1.78 | 1.37 / 1.74 | 0.52 / 0.72 | 0.49 / 0.66 |
| replay loop (`cpu_loop`) | 0.29 / 0.41 | 0.23 / 0.33 | 0.31 / 0.41 | 0.22 / 0.31 |
| submit / present | 0.03 / 0.09 | 0.03 / 0.09 | 0.03 / 0.09 | 0.03 / 0.08 |
| GPU total / GPU loop | 4.40 / 3.87 | 4.39 / 3.85 | 4.40 / 3.86 | 4.40 / 3.85 |
| GPU waits (`cpu_wait`) | ≈0 | ≈0 | ≈0 | ≈0 |
| harness: guest draw callbacks | 8.6 | 8.7 | 8.8 | 8.7 |
| harness: frame wall p50 | 13.3 | 13.3 | 12.3 | 12.1 |
""", """### 2.3 Bench, measured (final code `efae357`, 1800 draws, `logs/perf/{race,igpu}`; two interleaved runs per arm, mean of both)
`prof` = profile on, no T143 switch.

| ms per frame (mean / p95) | prof | `RSX_BIND_DEDUP` | `RSX_SRV_REUSE` | both |
|---|---|---|---|---|
| **RTX 5060:** render_frame CPU (`cpu_rf`) | 3.71 / 4.35 | 3.59 / 3.94 | 2.22 / 2.57 | **2.17 / 2.51** |
| RTX: pre-pass (`cpu_pre`) | 3.33 / 3.86 | 3.28 / 3.61 | 1.87 / 2.18 | 1.88 / 2.19 |
| RTX: SRV window fill (`cpu_srv`) | 1.57 / 1.80 | 1.54 / 1.61 | 0.43 / 0.47 | 0.42 / 0.45 |
| RTX: replay loop (`cpu_loop`) | 0.21 / 0.27 | 0.15 / 0.18 | 0.20 / 0.23 | 0.14 / 0.16 |
| RTX: harness frame wall p50 | 16.9 | 16.8 | 15.4 | 15.4 |
| **2-CU iGPU:** render_frame CPU (`cpu_rf`) | 3.51 / 4.39 | 3.68 / 4.61 | 2.41 / 3.17 | **2.40 / 3.23** |
| iGPU: SRV window fill (`cpu_srv`) | 1.29 / 1.68 | 1.42 / 1.83 | 0.48 / 0.66 | 0.49 / 0.70 |
| iGPU: replay loop (`cpu_loop`) | 0.27 / 0.37 | 0.23 / 0.33 | 0.27 / 0.40 | 0.22 / 0.34 |
| iGPU: GPU total (timestamps) | 4.38 / 4.65 | 4.41 / 4.70 | 4.36 / 4.63 | 4.37 / 4.63 |
| GPU waits (`cpu_wait`), submit | ≈0, 0.03 | ≈0, 0.03 | ≈0, 0.03 | ≈0, 0.03 |

The harness's guest draw callbacks (the record path that T119 owns) take 8.6–14 ms per frame in every arm.
"""),
('RTX 5060 rounds (900 and 1800 draws) give the same ratios: `cpu_rf` 2.21 → 1.29 ms at 900 draws, and 5.1 → 2.6–4.0 ms at 1800 draws. The RTX rounds are noisier (GPU clocking: GPU totals of 0.22 and 0.37 ms between identical runs), so the iGPU round is quoted.',
 'An earlier RTX round at 900 draws (`logs/bench/r3`) gives `cpu_rf` 2.21 → 1.29 ms. A pre-final RTX round (`logs/perf_pre_final/race`) was noisy (GPU totals of 0.22 and 0.37 ms between identical runs) and is not quoted. In the final worst-case round, one run each of `prof` and `dedup` had a system stall (p95 52–77 ms), so only their first runs are compared.'),
('| 1 | CPU command recording | race 9.7–13.8 ms; bench 3.75 ms, of which the replay loop itself is only 0.29 ms (≈160 ns per draw). The cost is in the pre-pass. |',
 '| 1 | CPU command recording | race 9.7–13.8 ms; bench 3.5–3.7 ms, of which the replay loop itself is only 0.21–0.27 ms (≈120–150 ns per draw). The cost is in the pre-pass. |'),
('Measured at 31–46 ns each, i.e. **0.9–1.4 ms per 1800-draw frame**', 'Measured at 30–40 ns each, i.e. **0.8–1.15 ms per 1800-draw frame**'),
('2. **Per-draw SRV creation: 0.9–1.4 ms per frame (bench, VERIFIED)', '2. **Per-draw SRV creation: 0.8–1.15 ms per frame (bench, VERIFIED)'),
('but they cost only ≈0.07 ms per frame (VERIFIED, bench: the loop takes 0.29 → 0.22 ms)',
 'but they cost only ≈0.05–0.07 ms per frame (VERIFIED, bench: the loop takes 0.21 → 0.15 ms on the RTX, 0.27 → 0.23 ms on the iGPU)'),
('| render_frame CPU, iGPU arm, mean / p95 | 3.75 / 4.69 ms | 2.46 / 3.16 ms | −34% / −33% (VERIFIED, bench) |\n| render_frame CPU, RTX, 900 draws, mean | 2.21 ms | 1.29 ms | −42% (VERIFIED, bench) |\n| replay-loop CPU (bind dedup alone) | 0.29 ms | 0.23 ms | −0.07 ms (VERIFIED, bench) |\n| GPU time | 4.40 ms | 4.40 ms | unchanged (VERIFIED: no GPU work changed) |\n| worst case (every draw changes program and textures) | — | — | dedup neutral (loop 0.40 vs 0.40 ms); reuse still −1.4 ms |',
 '| render_frame CPU, RTX 5060, 1800 draws, mean / p95 | 3.71 / 4.35 ms | 2.17 / 2.51 ms | **−42% / −42%** (VERIFIED, bench) |\n| render_frame CPU, 2-CU iGPU, 1800 draws, mean / p95 | 3.51 / 4.39 ms | 2.40 / 3.23 ms | −32% / −26% (VERIFIED, bench) |\n| render_frame CPU, RTX, 900 draws, mean | 2.21 ms | 1.29 ms | −42% (VERIFIED, bench) |\n| replay-loop CPU (bind dedup alone) | 0.21 ms | 0.15 ms | −0.06 ms (VERIFIED, bench) |\n| GPU time (timestamps) | 4.38 ms | 4.37 ms | unchanged (VERIFIED: no GPU work changed) |\n| worst case (every draw changes program and textures) | 3.74 ms | 2.45 ms | dedup neutral (loop 0.24 vs 0.27 ms); reuse still −1.3 ms |'),
('arms dedup / reuse / both / rerun: CMP_BENCH.', 'arms dedup / reuse / both / rerun: **18/18 identical** (5 snapshots each).'),
('GPU-based validation): CMP_T141.', 'GPU-based validation): **identical** (all-features and GBV feedback arms).'),
('clobbers the bindings): CMP_T137.', 'clobbers the bindings): **identical** (both arms).'),
('bench and T141 feedback arms identical.', "bench and T141 feedback arms identical. The final round's bench GBV \"off\" arm never reached its RSXI frame; the rerun pair (`logs/rerun_gbv.txt`, `logs/cmp_snaps_final2.txt`) is identical."),
('  - T143 tree: SUITE_FINAL.', '  - T143 tree (final): **41 PASS, 0 FAIL** (`logs/suite_final.txt`).'),
('It runs 31 source pins', 'It runs 30 source pins'),
]
for a, b in R:
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
assert 'FINAL_COMMIT' not in s and 'CMP_' not in s and 'SUITE_FINAL' not in s
open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('ok')

# T193 performance results

T193 code `72e1001d`, T192 code `cc386f42`. **Offline microbenchmark only; no game launched; no FPS claim.**

## Method

`py -3 ps3recomp-t193/tools/bench_spu_ib_telemetry.py --t192-tree ps3recomp-t192 --rounds 7 --iters 4000000` under `env_t169.cmd` (clang 23.1.3 `-O2 -msse4.1 -ffp-contract=off`, Windows 11, 12 logical CPUs). Same harness source (`tests/test_spu_ib_fast.c bench`, T192 patterns), linked against the T192 or T193 runtime; one process per (arm, pattern, threads), arms interleaved per round; median ns per branch (sd over 7 rounds), median of per-round ratios, worst round. Run twice: run 2 (machine quiet, the reference below) after the test suites; run 1 directly before them was noisier (sd up to 3 ns on `policy`, `wws`); both are reproduced in full. Raw logs: `generated/analysis/t193/logs/bench_spu_ib_telemetry{,_2}.txt` (private).

| Arm | Build | Switch | Telemetry |
|---|---|---|---|
| A2 / A3 | T192 / T193 normal | off | - (default path) |
| B2 / B3 | T192 / T193 normal | on | compiled out |
| S2 / S3 | T192 / T193 `-DSPU_IB_FAST_STATS` | on | counters, no interval |
| O3 | T193 stats | on | observations sampled 1 in 64 (`PS3_SPU_IB_STATS_OBS=64`) |
| I3 / J3 / K3 | T193 stats | on | interval reporter 1000 / 10 / 1 ms, to a file |

## Results (run 2, 1 thread unless stated)

| Metric | Result |
|---|---|
| Fast-path hit latency (stable) | B3 4.65 vs B2 4.60 ns (1.007x): unchanged from T192 |
| Relocatable hit latency (jreloc) | B3 5.42 vs B2 5.67 ns (0.95x): unchanged (within noise) |
| Resolver fallback latency | invalid target (unres) 2589 vs 2727 ns (0.95x); policy-mode below |
| Policy-mode latency | B3 6.97 vs B2 7.15 ns (0.98x); vs resolver A3 6.50: still the ~7 % T192 eligibility cost |
| **Telemetry disabled overhead** | B3/B2 0.95-1.01 on every pattern at 1 thread, 1.00-1.01 at 2-8 threads; default path A3/A2 0.92-1.01. **None measurable**: the normal build compiles no telemetry code |
| **Telemetry enabled overhead** vs normal build (S3/B3) | +1.3 to +3.4 ns per branch: stable 1.57x (+2.7 ns), jreloc 1.62x (+3.4), random 1.10x, overlay 1.25x, policy 1.33x (+2.4); `fill` 2.37x (+9.6 ns, see below) |
| ... vs T192's stats build (S3/S2) | stable 1.02x, wws 1.03x, random / overlay / kreloc 1.06-1.07x, policy 1.08x (+0.6 ns), jreloc 1.15x (+1.2 ns: the extra relocatable sub-counter and the shard pointer), `fill` 1.62x |
| ... with sampled observations (O3/B3) | stable 1.30x (+1.5 ns), jreloc 1.31x (+1.8), policy 1.13x (+0.9), random 0.98x, overlay 1.09x: about half the enabled cost |
| **Reporting interval overhead** (I3, J3, K3 vs S3) | 1000 ms: 0.84-1.02x; 10 ms: 0.96-1.01x; 1 ms: 0.91-1.01x (medians). **Not measurable.** Single worst rounds up to 1.67x (jreloc J3, sd 2.07 ns in that cell) are noise of that size. 18,889 reporter lines were written during these runs |
| **Multi-thread scalability** | S3/S2 1.03-1.12x at 2-8 threads (stable, jreloc); B3/B2 0.99-1.01x. An earlier T193 build with unaligned heap shards measured S3/S2 1.47x (stable) and 1.53x (jreloc) at 8 threads (false sharing between adjacent shards; that log was overwritten by the rerun, numbers kept from the console); fixed by 64-byte aligned, padded shards |
| Counter consistency | `CORRECTNESS_RESULTS.md`: 203/203 snapshots consistent with 16 concurrent writers; exact totals over 80 threads; invariants on every line of every test |
| Memory | per host thread: one shard, 464 B padded to 512 B, in a 576 B heap block (stats builds only); globals about 0.5 KB; plus the unchanged 12 KB cache |

### Unexplained: `fill` in the stats builds

The `fill` pattern (the harness increments the registry epoch before every branch, so every branch is a miss and refill) costs +3.3 ns in T192's stats build and +9.6 ns in T193's (S3 16.6 vs S2 10.3 ns); with observations sampled (O3) it is 11.2 ns, so about 5.5 ns of it is the observation block in this pattern only (in `stable` the same block costs about 1.2 ns). HYPOTHESIS, not investigated: a memory-disambiguation or store-forwarding interaction between the harness's non-atomic store to the epoch and the observation loads of globals near it. The pattern is synthetic (real titles register functions at start-up, not per branch), the normal build is not affected (B3/B2 1.01x), and `PS3_SPU_IB_STATS_OBS` removes most of it.

## Assessment

- Disabled: zero cost, so shipping builds are unaffected.
- Enabled: 1-3 ns per counted branch. At an assumed 10 million fast-path branches per second summed over SPU threads, that is 10-30 ms of host CPU per second (1-3 % of one core) of overhead, enough to bias a timing A/B, small enough for a counting run. Therefore: counting runs use the stats build with `PS3_SPU_IB_STATS_OBS=64`; timing A/Bs use the normal build (`GAME_PROFILING_PROTOCOL.md`).
- Reporting: free at any useful interval.

## Run 2 (reference)

```
cpu count 12; rounds 7; iters/thread 4000000
| pattern | thr | A2 ns (sd) | A3 ns (sd) | B2 ns (sd) | B3 ns (sd) | S2 ns (sd) | S3 ns (sd) | O3 ns (sd) | I3 ns (sd) | J3 ns (sd) | K3 ns (sd) | B3/B2 | A3/A2 | S3/S2 | S3/B3 | O3/B3 | I3/S3 | J3/S3 | K3/S3 | worst B3/B2 | worst J3/S3 |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stable | 1 | 6.90 (0.82) | 6.57 (0.41) | 4.60 (0.12) | 4.65 (0.34) | 7.13 (0.30) | 7.30 (1.19) | 6.12 (0.22) | 7.23 (0.13) | 7.28 (0.04) | 7.37 (0.22) | 1.007x | 0.948x | 1.021x | 1.573x | 1.302x | 0.994x | 1.001x | 1.014x | 1.209x | 1.020x |
| stable | 2 | 7.01 (0.32) | 6.93 (0.16) | 4.75 (0.10) | 4.75 (0.16) | 7.46 (0.11) | 7.84 (0.63) | 6.41 (0.61) | 8.17 (0.43) | 7.58 (0.38) | 7.74 (1.32) | 1.004x | 0.959x | 1.059x | 1.607x | 1.356x | 0.969x | 1.006x | 1.013x | 1.077x | 1.047x |
| stable | 4 | 7.17 (0.44) | 6.86 (0.47) | 4.92 (0.55) | 4.89 (1.60) | 8.13 (0.77) | 8.55 (0.57) | 6.35 (0.10) | 7.78 (0.33) | 7.73 (0.47) | 7.94 (0.29) | 1.012x | 0.973x | 1.030x | 1.580x | 1.294x | 0.934x | 0.969x | 0.946x | 1.441x | 1.023x |
| stable | 8 | 12.32 (2.10) | 12.18 (2.59) | 8.00 (0.98) | 8.67 (0.85) | 13.45 (1.35) | 13.31 (1.41) | 10.42 (1.33) | 11.95 (1.73) | 12.75 (1.60) | 12.08 (1.39) | 1.013x | 0.989x | 1.045x | 1.644x | 1.224x | 0.844x | 0.960x | 0.912x | 1.225x | 1.118x |
| jreloc | 1 | 6.82 (0.26) | 6.81 (0.17) | 5.67 (0.26) | 5.42 (0.08) | 7.62 (0.24) | 8.84 (0.10) | 7.25 (0.47) | 8.69 (0.09) | 8.87 (2.07) | 8.94 (1.03) | 0.952x | 1.000x | 1.154x | 1.622x | 1.314x | 0.979x | 1.010x | 1.006x | 1.007x | 1.667x |
| jreloc | 2 | 6.77 (0.07) | 6.79 (0.09) | 5.51 (0.11) | 5.43 (0.87) | 7.57 (0.11) | 8.47 (1.22) | 7.13 (0.10) | 8.51 (0.13) | 8.41 (0.23) | 8.46 (0.15) | 0.986x | 1.000x | 1.117x | 1.548x | 1.315x | 1.006x | 0.993x | 0.992x | 1.471x | 1.039x |
| jreloc | 4 | 6.99 (0.70) | 7.50 (0.45) | 5.62 (0.08) | 5.67 (0.11) | 8.60 (0.62) | 8.87 (1.10) | 7.42 (0.58) | 8.85 (0.92) | 8.72 (0.53) | 8.83 (0.17) | 1.009x | 0.987x | 1.043x | 1.572x | 1.332x | 1.020x | 0.983x | 1.002x | 1.023x | 1.145x |
| jreloc | 8 | 10.73 (0.82) | 10.48 (0.83) | 8.99 (0.59) | 8.85 (0.39) | 11.94 (0.61) | 13.74 (0.94) | 10.70 (0.89) | 13.06 (0.55) | 13.72 (0.96) | 13.16 (0.76) | 0.990x | 0.977x | 1.097x | 1.548x | 1.257x | 0.986x | 0.982x | 0.951x | 1.156x | 1.219x |
| random | 1 | 14.72 (0.25) | 14.67 (0.05) | 13.62 (0.13) | 13.73 (0.09) | 14.11 (0.21) | 15.04 (0.18) | 13.51 (0.02) | 15.07 (0.27) | 15.01 (0.13) | 15.26 (0.12) | 1.003x | 0.996x | 1.064x | 1.104x | 0.984x | 1.005x | 1.003x | 1.008x | 1.020x | 1.012x |
| overlay | 1 | 17.11 (0.04) | 17.09 (0.79) | 11.97 (0.17) | 11.84 (0.08) | 13.76 (0.44) | 14.85 (0.15) | 12.86 (0.30) | 14.88 (0.11) | 14.85 (0.03) | 15.05 (0.14) | 0.982x | 0.998x | 1.073x | 1.252x | 1.089x | 1.000x | 1.001x | 1.014x | 1.015x | 1.009x |
| kreloc | 1 | 13.85 (0.61) | 13.73 (0.03) | 12.25 (0.04) | 12.36 (0.07) | 13.69 (0.12) | 14.66 (0.09) | 14.03 (0.12) | 14.65 (0.16) | 14.72 (0.17) | 14.86 (0.05) | 1.007x | 0.991x | 1.069x | 1.188x | 1.136x | 1.005x | 1.005x | 1.014x | 1.013x | 1.031x |
| wws | 1 | 13.26 (0.06) | 13.42 (0.09) | 11.59 (0.27) | 11.65 (0.27) | 14.36 (0.14) | 14.71 (0.21) | 13.39 (0.12) | 14.70 (0.31) | 14.70 (0.14) | 14.82 (0.51) | 0.994x | 1.011x | 1.029x | 1.286x | 1.153x | 1.004x | 0.999x | 1.011x | 1.053x | 1.026x |
| policy | 1 | 6.72 (0.32) | 6.50 (0.91) | 7.15 (1.01) | 6.97 (0.55) | 8.77 (0.44) | 9.39 (0.38) | 7.88 (0.07) | 9.43 (0.05) | 9.42 (0.64) | 9.55 (0.18) | 0.980x | 0.968x | 1.082x | 1.331x | 1.126x | 1.004x | 1.005x | 1.013x | 1.000x | 1.162x |
| unres | 1 | 2725.51 (34.35) | 2539.55 (20.69) | 2727.41 (27.77) | 2588.78 (49.74) | 2537.35 (46.91) | 2729.95 (22.97) | 2717.73 (58.74) | 2737.22 (48.18) | 2773.71 (47.45) | 2764.25 (26.66) | 0.947x | 0.924x | 1.074x | 1.057x | 1.048x | 1.008x | 1.019x | 1.013x | 0.965x | 1.048x |
| fill | 1 | 10.46 (0.17) | 10.38 (0.21) | 6.97 (0.04) | 7.02 (0.34) | 10.25 (0.14) | 16.62 (0.33) | 11.16 (0.24) | 16.26 (0.64) | 16.40 (0.70) | 16.74 (0.30) | 1.012x | 0.995x | 1.621x | 2.367x | 1.602x | 0.994x | 0.998x | 1.013x | 1.126x | 1.078x |

reporter lines written by the I3/J3 runs: 18889
```

## Run 1 (before the suites; noisier)

```
cpu count 12; rounds 7; iters/thread 4000000
| pattern | thr | A2 ns (sd) | A3 ns (sd) | B2 ns (sd) | B3 ns (sd) | S2 ns (sd) | S3 ns (sd) | O3 ns (sd) | I3 ns (sd) | J3 ns (sd) | K3 ns (sd) | B3/B2 | A3/A2 | S3/S2 | S3/B3 | O3/B3 | I3/S3 | J3/S3 | K3/S3 | worst B3/B2 | worst J3/S3 |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stable | 1 | 7.12 (0.51) | 6.86 (1.04) | 4.79 (0.09) | 4.71 (0.06) | 7.68 (1.27) | 7.75 (0.24) | 6.22 (0.13) | 7.56 (0.32) | 7.67 (1.30) | 7.63 (0.56) | 1.006x | 0.963x | 1.000x | 1.621x | 1.310x | 0.983x | 0.961x | 1.005x | 1.041x | 1.527x |
| stable | 2 | 7.17 (0.80) | 6.88 (0.04) | 4.89 (0.13) | 4.91 (0.70) | 7.80 (1.61) | 7.91 (0.47) | 6.56 (0.73) | 7.77 (0.48) | 7.76 (0.17) | 7.89 (0.26) | 1.008x | 0.953x | 1.041x | 1.605x | 1.336x | 0.972x | 1.001x | 1.013x | 1.420x | 1.078x |
| stable | 4 | 8.23 (0.99) | 7.89 (1.71) | 5.28 (1.13) | 5.37 (0.30) | 9.16 (0.56) | 9.53 (0.67) | 7.90 (1.30) | 8.67 (0.63) | 8.61 (0.87) | 10.09 (1.65) | 0.984x | 0.959x | 1.047x | 1.741x | 1.437x | 0.953x | 0.914x | 1.004x | 1.102x | 1.151x |
| stable | 8 | 12.43 (0.66) | 11.57 (0.46) | 7.76 (0.56) | 8.24 (0.51) | 12.67 (0.80) | 12.31 (0.92) | 10.54 (1.11) | 12.76 (1.24) | 13.20 (0.52) | 12.64 (1.93) | 1.052x | 0.949x | 0.991x | 1.507x | 1.256x | 1.063x | 1.056x | 1.066x | 1.209x | 1.120x |
| jreloc | 1 | 7.01 (0.14) | 6.90 (0.66) | 5.47 (0.16) | 5.54 (0.49) | 7.79 (0.30) | 8.99 (0.19) | 7.16 (0.22) | 9.00 (0.36) | 8.90 (1.03) | 9.34 (1.08) | 1.011x | 0.994x | 1.144x | 1.585x | 1.287x | 1.014x | 0.999x | 1.016x | 1.190x | 1.349x |
| jreloc | 2 | 7.03 (1.27) | 7.02 (1.04) | 5.50 (0.07) | 5.54 (0.08) | 7.91 (0.75) | 8.65 (0.95) | 7.21 (1.15) | 8.78 (1.14) | 8.94 (0.23) | 8.84 (0.27) | 0.996x | 0.996x | 1.094x | 1.561x | 1.327x | 1.009x | 1.008x | 1.029x | 1.016x | 1.061x |
| jreloc | 4 | 7.51 (0.65) | 7.84 (0.70) | 6.04 (0.62) | 6.02 (0.46) | 8.58 (0.59) | 9.06 (0.91) | 8.40 (0.92) | 9.98 (1.45) | 9.36 (0.71) | 10.23 (1.10) | 0.974x | 1.010x | 1.052x | 1.520x | 1.326x | 1.019x | 1.000x | 1.045x | 1.067x | 1.216x |
| jreloc | 8 | 11.47 (0.99) | 11.84 (0.77) | 8.83 (0.34) | 8.74 (0.34) | 13.24 (1.56) | 13.73 (1.16) | 11.90 (0.83) | 14.88 (0.85) | 13.78 (0.52) | 13.88 (0.45) | 1.008x | 1.010x | 1.025x | 1.571x | 1.348x | 0.974x | 1.015x | 1.002x | 1.046x | 1.062x |
| random | 1 | 14.92 (0.23) | 15.05 (0.71) | 13.78 (0.55) | 13.78 (0.21) | 14.30 (0.10) | 15.31 (0.35) | 13.76 (0.14) | 15.30 (0.15) | 15.24 (0.21) | 15.90 (0.81) | 1.000x | 1.010x | 1.071x | 1.117x | 0.996x | 0.989x | 0.998x | 1.020x | 1.020x | 1.014x |
| overlay | 1 | 17.18 (0.22) | 17.35 (0.27) | 11.82 (0.15) | 11.92 (0.52) | 13.71 (0.28) | 14.88 (0.70) | 12.82 (0.09) | 14.86 (0.13) | 15.08 (0.27) | 15.13 (0.21) | 1.009x | 1.016x | 1.090x | 1.239x | 1.073x | 1.001x | 1.011x | 1.014x | 1.103x | 1.058x |
| kreloc | 1 | 13.89 (0.19) | 13.83 (0.12) | 12.27 (0.39) | 12.19 (0.10) | 14.18 (1.34) | 14.66 (0.26) | 14.00 (0.49) | 14.71 (0.53) | 15.03 (0.97) | 15.19 (0.29) | 0.994x | 0.996x | 1.041x | 1.205x | 1.148x | 1.001x | 1.028x | 1.038x | 1.004x | 1.144x |
| wws | 1 | 17.58 (6.12) | 16.20 (2.53) | 13.34 (1.70) | 13.84 (1.43) | 17.19 (2.12) | 19.13 (2.20) | 16.91 (1.49) | 19.65 (4.31) | 18.86 (3.78) | 19.96 (3.50) | 0.983x | 1.008x | 1.051x | 1.356x | 1.254x | 1.023x | 0.995x | 1.043x | 1.037x | 1.427x |
| policy | 1 | 12.58 (2.64) | 11.62 (3.07) | 11.21 (3.01) | 12.45 (2.00) | 14.74 (1.38) | 16.07 (1.02) | 13.68 (2.16) | 15.83 (2.04) | 17.03 (1.57) | 15.89 (2.33) | 1.049x | 0.876x | 1.112x | 1.309x | 1.099x | 0.978x | 1.029x | 1.034x | 1.178x | 1.171x |
| unres | 1 | 3222.39 (396.47) | 3815.32 (1003.04) | 2904.19 (610.97) | 2762.70 (1331.38) | 2574.28 (1095.15) | 2810.14 (467.28) | 2770.16 (597.04) | 2784.99 (647.10) | 2900.30 (505.16) | 2900.27 (300.76) | 0.996x | 1.141x | 1.073x | 0.991x | 0.987x | 0.996x | 1.009x | 1.012x | 1.390x | 1.125x |
| fill | 1 | 10.58 (0.10) | 10.53 (0.16) | 6.99 (0.09) | 7.04 (0.08) | 10.14 (0.45) | 16.37 (0.09) | 11.05 (0.07) | 16.20 (0.08) | 16.24 (0.07) | 16.61 (0.16) | 1.010x | 0.989x | 1.612x | 2.329x | 1.575x | 0.991x | 0.990x | 1.016x | 1.034x | 1.012x |

reporter lines written by the I3/J3 runs: 13596
```

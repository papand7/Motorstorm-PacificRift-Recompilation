# T162 — game A/B results

2026-10-30. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

**Result: no frame-matched comparison exists (BLOCKED). GPU fetch failed in game: both B launches ended on the game's own `GcKernel::Present() Timeout` as the race started, 0 race frames. Both A launches passed the same point.** Do not integrate or enable it. No improvement percentage can be stated; the synthetic 30 % and the 15–20 % hypothesis remain untested in game.

All five approved launches are used. Same exe (`5098e7e31f8dd17f2c05d56e0263faeeec93ac2b5cdd8807f7b9a9fdd24c8573`, ps3recomp `69489f2`), hash checked before each, fresh HDD copy, no retries. Old texture config: no texture change in this exe, so nothing here is a combined speedup.

## Runs

| Launch | Config | End | Race entry | Race frames | Light FPS (p50 / p95 / p99 ms) | Heavy FPS (frames) | Frames with GPU wait > 50 ms |
|---|---|---|---|---|---|---|---|
| D 12:15 | counters | 195 s cap | 134 s | 573 | 10.81 (91.8 / 101.9 / 178.0), not a performance figure | none | 634 of 4,023 |
| A1 12:25 | fetch off | 195 s cap | 134 s | 661 | **22.13** (44.8 / 49.8 / 57.6) | 3.74 (61, incomplete) | 0 of 4,701 |
| B1 12:28 | fetch on | **Present Timeout, about 180 s** | none | 0 | none | none | 1,828 of 1,855 |
| A2 12:31 | fetch off | 195 s cap | 136 s | 566 | **10.81** (92.4 / 98.9 / 174.1) | none | 1,555 of 2,463 |
| B2 12:34 | fetch on | **Present Timeout, about 180 s** | none | 0 | none | none | 1,833 of 1,861 |

Data: `tools/ab_summary_t162.py` over the five run directories (`generated/runs/20261030-*-t162-*`).

## Failure 1: Present Timeout when the race starts (VERIFIED in B, cause HYPOTHESIS)

VERIFIED, same in B1 and B2:
- The race load finished normally (loader 85.3 and 85.6 s; A: 85.8 and 84.8 s).
- The last frame logged is gframe 1855 / 1861, at about 176 s. The frame clock then stops, and the runner stops on the game's error about 4.5 s later.
- `[fc-watchdog]` reports no progress for 2,000 ms with the stack inside `D3DCOMPILER_47`.
- `Gpu Get` equals the start of the last kicked push buffer: the RSX never finished that buffer.
- `[gvf]` at the end: 789 draws, `nopso=0`, `lost=0`, `cpu_ms` 3,457 and 3,575.

A1 and A2 survive the same frame in 2.24 and 2.38 s (51 pipeline misses, about 1.3 s of compile). Their longest frame in the race is 3.17 s, at the heavy transition.

HYPOTHESIS: the fetch path compiles its vertex shaders synchronously on the RSX thread, and the bigger fetch shaders push the first race frame past the game's timeout. `RSX_SHADER_CACHE=1` is memory only, so every launch compiles cold. Not proven: no per-shader compile time was logged, and the game's threshold was not measured.

This is not a fallback failure: `nopso` and `lost` are 0. The offline tests did not catch it; they don't reproduce a race-start compile burst against the game's timeout.

## Failure 2: the host has an unexplained 84 ms GPU-wait mode (VERIFIED, cause unknown)

Some launches spend frames at 92 ms (`wait_ms` about 84) even when the frame has only 10 draws, instead of 31 ms. A1 and A2 ran the same exe and config, and got 22.13 and 10.81 FPS in the light scene. The mode decides the result, so the runs are not comparable.

| When | Runs | Frames in the mode |
|---|---|---|
| 06:51–07:01 | T161 C1, D1, C2, D2 | 0, 0, 0, 0 |
| 11:37–11:50 | Texture E3, T3, E4, T4 (no T162 code) | 1,576; 137; 1,762; 1,117 |
| 12:15–12:37 | T162 D, A1, B1, A2, B2 | 634; 0; 1,828; 1,555; 1,833 |

So the mode is not caused by GPU fetch alone: it appears without any T162 code. B1 and B2 were in it almost from the start, so B's boot was slower (`gamesave` at 30 s; A: 19–22 s) and its race load finished about 43 s later. Whether fetch makes the mode more likely can't be separated from two launches. The mode also explains why D and A2 never reached the heavy scene. Closing SSX, EA and Epic didn't cure it (A2: `others=[]`, host load 3 %). The session is RDP, and I did not check whether it already was during the clean T161 runs.

## §7 metrics

Only the fetch-off arm has race data. Medians per guest frame:

| Metric | A1 light | A2 light | A1 heavy |
|---|---|---|---|
| Draws | 2,004 | 2,006 | 6,926 |
| Vertices | 100,828 | 100,968 | 411,187 |
| Vertex upload MB | 24.6 | 24.7 | 100.4 |
| CPU vertex expansion ms | 12.0 | 13.9 | 46.5 |
| Draw recording ms | 4.6 | 4.1 | 199.9 |
| Texture recording ms | 1.1 | 0.9 | 180.1 |
| RSX processing (drain) ms | 14.4 | 16.1 | 242.6 |
| GPU fence wait ms | 0.0 | 62.8 | 0.1 |

- **GPU-fetch coverage:** 789 draws in each B launch, all before the race. Coverage on race content is unknown. CPU fallback 0, `nopso` 0.
- **FIFO resyncs:** 0 in all five.
- **D3D12 validation:** not measured. The game runs don't enable the debug layer, so the 0 messages in their logs is no evidence. The debug-layer evidence is offline only.
- **Guest progression:** no B race, so nothing to match. A1 and A2 match each other in the light scene (draws within 0.1 %).
- **PPU RSX, Wws and Havok waits, GPU time:** logged in the A runs but not compared, since there is no B counterpart.

## Rendering comparison: BLOCKED

Snapshots are taken at race entry + 30 s. A1 and A2 have 12 each, B has 0. Rider, terrain, vehicles, shadows, HUD, glyphs, transparency and multi-pass are not compared in game. The offline snapshots (12 of 12 identical) are the only evidence.

## Remaining bottlenecks (A1, the clean run)

- Heavy: 258 ms per frame, of which 180 ms is texture recording and 46.5 ms CPU vertex expansion. Vertex expansion is 18 % of the frame, which caps what fetch can remove there; texture recording is the larger target.
- Light: 44.8 ms per frame, of which 14.4 ms is RSX processing (12 ms expansion). The rest is outside the RSX drain.

## Conduct

The brief says to stop at the first safety or correctness failure. **B1 was one, and A2 and B2 still ran.** `seq_t162b.sh` only stopped on a controller error or on no heavy frames in A1, and B1 exited with rc 0. The launch count stayed within five. A2 and B2 did add data: they show that the failure repeats and that the wait mode occurs in the fetch-off arm.

## Recommendation

Do not merge or enable by default. `RSX_GPU_VERTEX_FETCH` stays off. Before any new launch, which needs fresh approval:

1. Find the 84 ms wait mode. Without that, no A/B is comparable.
2. Fix the compile stall in code: log per-shader compile time, then stop fetch-shader compiles from blocking the RSX past the game's timeout. A disk cache (`RSX_SHADER_CACHE=2`) alone would still leave a cold first launch failing, if the hypothesis holds.

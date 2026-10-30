# T165: game test results

**Allowance used: 4 of 4 launches. No further launch without new approval.** One launch at a time, no other game or launcher running, 195 s game cap unchanged.

Exe for all: `performance_next/ab/exe_n`, sha256 `0304156bac3e6553b23cbb3ea24763c90f33b4c3aae01ac725ddf2a8ad3449b3`. Environment: arm T of T3 (`RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1 RSX_TEX_WWATCH=1 RSX_TEX_BUDGET_MB=1024`) plus RSXI. Runner: `tools/make_runner_t165.py`.

**Deviations from `GAME_TEST_PLAN.md`:** race entry varies from 136 to 183 s, so the runner presses CROSS at race entry +4 and +7 s to skip the flyover and triggers RSXI at +10 s instead of +30 s.

| Run | Arm | Capture settings | Race entry | Ended by | Capture |
|---|---|---|---|---|---|
| B1 | baseline | `VP_CONSTS=512 GEOM=16`, debug layer on | 166.6 s | game's 4 s `GcKernel::Present() Timeout` during capture | partial frame 3500, 910 draws, no snapshots. 0 D3D12 errors |
| B2 | baseline | **same as B1 (my error)** | 180.7 s | same timeout | partial frame 1976, 374 draws |
| B3 | baseline | `VP_CONSTS=48 UNITS=C03F GEOM=1`, no debug layer | 153.2 s | same timeout, during the second frame | **complete f002192** (934 records, 56 snapshots, 3.4 s) + partial f002312 |
| X1 | `RSX_COLOR_XFER=7` | as B3 | 182.6 s | 195 s cap | partial f002948, 1,072 draws, no snapshots; `frame_000`, `frame_001` dumps |

- **B2 was wasted:** my patch to the generator failed and I launched without checking it. The planned arms S and D never ran.
- **The stall is caused by the capture, not the renderer.** RSXI's per-frame writing can exceed the game's 4 s watchdog, and the same line ends the harness.
- **Slow GPU-wait mode:** frames with `wait_ms ≥ 80`: B3 1,246 of 2,246, X1 1,321 of 2,943, in both arms. No performance conclusion is drawn.
- **X1:** 48 `[XFER] ... applies it` lines, 0 shader or PSO failure lines. Draw counts can't be compared because the frames differ.

## Matched comparison: `frame_001`, B3 against X1

The same camera and vehicle pose, by inspection. Regions are hand-placed (`tools/compare_xfer_t165.py`). Luma is 0–255; near-black means max channel ≤ 16; clipped means min channel ≥ 250.

| Region | B luma | X luma | B near-black % | X near-black % | B clipped % | X clipped % |
|---|---|---|---|---|---|---|
| front tyre | 36.5 | 55.4 | 58.1 | 24.9 | 0.5 | 0.4 |
| left tyre | 49.3 | 63.4 | 64.8 | 31.0 | 4.7 | 3.4 |
| quad frame+fairing | 103.4 | 101.1 | 14.1 | 7.7 | 16.1 | 11.3 |
| rider jacket+legs | 81.3 | 58.8 | 12.1 | 22.1 | 4.9 | 0.6 |
| helmet | 106.1 | 61.7 | 6.1 | 9.3 | 1.4 | 0.0 |
| sand left | 213.0 | 210.0 | 0.0 | 0.0 | 5.2 | 3.5 |
| sand right | 193.0 | 191.7 | 0.0 | 0.0 | 0.9 | 0.7 |
| cliff shade | 108.6 | 70.7 | 0.1 | 0.0 | 0.0 | 0.0 |
| lit bank | 155.9 | 106.6 | 0.0 | 0.0 | 13.6 | 0.0 |
| palm | 141.3 | 78.1 | 0.0 | 0.0 | 0.0 | 0.0 |
| whole frame | 136.2 | 116.7 | 5.1 | 3.2 | 6.5 | 2.9 |

Observations:
- **Tyres:** clearly lifted, with sidewall detail back.
- **Rider's jacket and legs:** darker, and near-black rises, so X isn't a uniform lift. Whether that matches the PS3 is unverified.
- **Foliage and lit bank:** white blow-out is gone, colour returns.
- **Sand:** barely changes, and its rectangular patches remain.
- **HUD and sky:** not in this frame, so unchecked.
- **Flyover `frame_000`:** 47.5 % clipped against 35.3 % (not confirmed as a pose match).

## Arm S (samplers)

Not run. Unit 0's mismatch was established from registers instead (see the root-cause report).

# ROADMAP_TO_60FPS (needs about -7.7 ms/frame)
| Candidate | Evidence | Modelled saving | Correctness risk | Required validation | Status |
|---|---|---|---|---|---|
| ppucc2 (PPU codegen) | -2 ms compute; +1.3 fps n.s. | ~0.9 ms (serial share) | low | more runs, per-function attribution | keep opt-in |
| Cut serial PPU compute (5.92 ms SPU-idle) | overlap77 | only removed work counts | exact codegen only | per-function sampler | main lever |
| JobBatch hand-off latency | 2.2-2.4 ms summed | <= ~1 ms | low-medium | wait-site metrics | HYPOTHESIS |
| Wws --fast-lower | lift reading | <= 0.3 ms | low | whole-job replay harness | BLOCKED |
| Earlier submission / PPU-SPU reorder | none | unknown | high | read/write-set analysis | BLOCKED |

Exact levers found sum to ~2-3 ms of the 7.7 ms needed. Combined ppucc2 + SPU model not built: no SPU candidate exists, so it would only repeat the serial 0.9 ms.

## Answers
1. About 5.9 ms serial PPU compute + 11 ms of waits bound by hand-off latency and lane contention.
2. 7.2 ms of compute already overlaps SPU work; saving there just extends the next wait.
3. vehiclephysics (2.9 ms), then renderable (1.85 ms, behind PVS).
4. Unproven; needs read/write sets.
5. Unproven; same.
6. Not shown on average; scheduling wake latency untested.
7. None strong; hand-off latency is the best HYPOTHESIS.
8. Only partly; gains stay serial-share limited.
9. Reduce serial PPU compute (ppucc2-style) and hand-off latency, measured by wait site.
10. Per-function attribution of PPU time, read/write sets, ETW scheduling trace, a whole-job Wws replay harness.

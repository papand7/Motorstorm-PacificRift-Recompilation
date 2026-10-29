# T150: RSX frame cost breakdown (renderer CPU per race frame)

Labels: VERIFIED (measured), PARTIAL (measured once, or synthetic), HYPOTHESIS (inferred), BLOCKED (needs a game run).

## Before: T149 race runs (T146 unified runtime, one run each)

**Sources:**
- `[rsx-frame-perf]` (`RSX_FRAME_PERF=12,1,100000`): medians of the last 400 frame-clock passes, via `t150/ab/ana_t150.py`.
- `PS3_CRITICAL_PATH_TRACE` spans over host 175–240 s:
  - `TEXSNAP` (kind 18) gives KB hashed and copies;
  - `DRAIN` (7) and `RSX_RECORD` (33) give spans.

| ms per frame-clock pass | P0: T146 defaults | P1: performance preset |
|---|---:|---:|
| `wall_ms` | 133.5 | 86.6 |
| `drain_ms` (FIFO walk incl. draw callbacks) | **118.9** | 18.9 |
| ↳ `expand_ms` (draw callbacks minus early replays and VS compiles) | **112.2** | 15.7 |
| ↳ ↳ texture snapshot (trace: 45% of wall time in `TEXSNAP` spans) | **≈ 69** | ≈ 1.3 |
| ↳ ↳ vertex expansion and the rest (fat 256-byte vertices in P0, compact in P1) | ≈ 43 | ≈ 14 |
| `rf_ms` (render_frame) | 14.0 | 9.7 |
| ↳ `record_ms`: tex / pso / cmd | 10.4: 1.6 / 1.5 / 6.4 | 6.0: 1.4 / 1.6 / 3.0 |
| `submit` + `wait` + `present` | ≈ 0.4 | ≈ 0.3 |
| `other_ms` (frame-clock thread idle, vblank, pump) | 4.3 | **54.3** |

**What the snapshot cost is (VERIFIED from the P0 trace):**
- About 7,000 captures per second, each of the same **2 MiB** (`a = 0x800` KB), with **0 copies**: one linear B8/G8B8 texture that never changes, captured on about 1,065 draws per frame.
- That is about 14 GB/s, or about 2.1 GB hashed per frame.
- The hash is the whole cost:
  - no copies;
  - no allocations, since the buffer is kept;
  - no locks, because capture runs on the drain thread only;
  - address translation is `vm_base + off`;
  - the layout plan per unit falls inside the T119 `cb_rest` stage.
- The `TEXSNAP` span is per draw and does not nest inside another `TEXSNAP`, so there is no double counting. It is nested inside `expand_ms` and inside `DRAIN`, and is counted once here.

**P1:**
- The renderer works about 29 ms (drain + rf) of an 87 ms pass and is idle 54 ms.
- The guest's ref wait (26 ms, T149) is that 29 ms being serial with the guest frame, not RSX saturation.

## After: synthetic, race-shaped (`tests/bench_tex_snapshot.c`; not a game measurement)

**Workload:**
- 1,065 captures per frame of a 2 MiB unchanging texture, in 22 sync epochs per frame;
- plus a 256 KiB texture rewritten each frame by another thread and captured 40 times.

**Method:** 31 frames × 7 repetitions, idle machine, medians.

| Arm | capture ms/frame (median / p90, stdev of rep medians) | MB hashed/frame | copies/frame | writer µs/frame |
|---|---:|---:|---:|---:|
| off (T146 default) | 53.05 / 53.94 (0.20) | 2140.2 | 1.00 | 6.0 |
| epoch (T122) | 1.18 / 1.29 (0.003) | 46.5 | 1.00 | 2.4 |
| write-watch (T150) | 1.78 / 2.02 (0.009) | 0.5 | 1.00 | 27.3 |
| epoch + write-watch | **0.10** / 0.14 (0.001) | 0.5 | 1.00 | 25.7 |

- 0 stale captures in every arm. The writer pays about 20 µs per frame (64 pages × about 0.33 µs for the first store after a reset).
- **Offline, the off arm costs 53 ms against about 69 ms in game** (P0); the game's cache contention plausibly accounts for the gap.

## Expected in game (HYPOTHESIS until the A/B in `RSX_SNAPSHOT_PERFORMANCE.md` §12)

| Arm | snapshot ms/frame | drain ms/frame |
|---|---:|---:|
| A T146 defaults | ≈ 69 | ≈ 119 |
| B + epoch | ≈ 1.3 | ≈ 50 |
| C + write-watch | ≈ 2 | ≈ 52 |
| D + both | ≈ 0.1 | ≈ 50 |

**After the snapshot, the next renderer costs:**
1. Fat vertex expansion (about 43 ms) in the default configuration; `RSX_VP_COMPACT` (T119, opt-in) cuts it to about 14 ms.
2. Command recording (`cmd`, 3–6 ms).
3. Texture and PSO binding (about 1.5 ms each).

**FPS:** none of this alone reaches 30 FPS. In P1 the renderer is idle 54 ms per pass, and the frame is gated by the PPU frame thread's own compute (56 ms) plus the serial RSX work (T149).

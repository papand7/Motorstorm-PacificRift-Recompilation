# T164: performance

**Synthetic results only. They say nothing about in-game FPS.** The batched path removes the per-draw bottleneck in these workloads: frame wall time fell 8x to 32x on both GPUs, with draw counts and frame hashes unchanged.

## Build and setup

| Item | Value |
|---|---|
| Source | ps3recomp `c631d2a033e8379ad174cd80f4604f4fc69de1bb`, branch `agent/t164-vulkan-batching`, from `f11ecd4` |
| Host | `build/t164-vulkan/ps3recomp_host.exe`, SHA-256 `11a96cdd1c1e102f62f164ae713bf66aa638a83318de5aa25cacff3bd85b8804` |
| Toolchain | clang-cl LLVM 23.1.3, Ninja, Release, Vulkan-Headers v1.4.341 |
| RTX 5060 | Driver 32.0.16.1088, `PS3RECOMP_VK_DEVICE=0` |
| Radeon iGPU | Driver 32.0.21042.62, `PS3RECOMP_VK_DEVICE=1` |
| Runs | 5 repeats x 30 frames, `tools/run_bench_t164.py`, `logs/bench.json` (private) |
| Disturbance | No game or `ps3recomp_game` process seen before or after. Not sampled during the runs |

The host was built before the commit from the same files; `ninja -n` reports no work to do on that tree.

## Workloads

| | Definition |
|---|---|
| A | 2,000 draws, one target, no textures |
| B | 6,900 draws: three offscreen passes (3,000, 2,000, 1,400) then 500 textured draws on the display that sample those targets |
| C | 2,000 textured draws over 16 textures, a target change every 50 draws, one texture rewritten every 100 draws |
| D | 200 cycles per frame of clear, 5 draws, sample that target; a CPU readback every 25 cycles (8 per frame) |

## Results

Values are median [min..max] of 5 runs. Stats on. Peak GPU memory is what the backend allocates, not the driver's total. Validation errors come from the validated correctness and 30-frame runs; the timed runs have no layer.

### RTX 5060

| Workload | Path | Draws/frame | Queue submits/frame | CPU GPU-wait ms/frame | Recording ms/frame | GPU execution ms/frame | Frame wall ms | Peak GPU memory MiB | Validation errors |
|---|---|---|---|---|---|---|---|---|---|
| A | reference | 2000 | 2001.17 | 97.42 [96.31..98.50] | 17.20 [16.69..18.00] | 12.30 [12.10..12.34] | 149.1 [145.7..149.4] | 20.5 | 0 |
| A | batched | 2000 | 1.07 | 0.98 [0.95..1.13] | 1.38 [1.27..1.57] | 0.19 [0.19..0.22] | 6.4 [5.9..7.3] | 148.4 | 0 |
| B | reference | 6900 | 6904.37 | 346.68 [337.23..348.70] | 73.40 [60.20..75.44] | 42.00 [41.52..42.27] | 551.4 [520.1..559.8] | 21.5 | 0 |
| B | batched | 6900 | 2.07 | 0.96 [0.93..1.04] | 4.28 [4.23..5.50] | 0.74 [0.71..0.77] | 17.0 [16.8..21.1] | 181.2 | 0 |
| C | reference | 2000 | 2033.23 | 100.95 [100.26..106.18] | 16.16 [15.27..18.62] | 12.70 [12.61..13.00] | 158.3 [155.4..169.3] | 21.0 | 0 |
| C | batched | 2000 | 1.07 | 1.65 [1.62..1.67] | 1.34 [1.32..1.59] | 0.86 [0.85..0.87] | 11.7 [11.4..13.4] | 148.7 | 0 |
| D | reference | 1200 | 1417.17 | 70.35 [69.47..71.72] | 11.23 [10.68..11.41] | 7.65 [7.60..7.68] | 112.7 [109.4..114.8] | 21.1 | 0 |
| D | batched | 1200 | 8.07 | 5.52 [5.49..5.61] | 1.32 [1.31..1.34] | 3.57 [3.54..3.65] | 14.0 [13.9..14.2] | 84.7 | 0 |

| Workload | Wall ratio (median) | Passes/frame ref -> batched | Barriers/frame ref -> batched | Fence waits/frame batched | Queue submit ms/frame ref -> batched | Submit-to-done latency µs ref -> batched |
|---|---|---|---|---|---|---|
| A | 23.4x | 2000 -> 1 | 2004 -> 6 | 1.1 | 25.36 -> 0.035 | 48 -> 969 |
| B | 32.4x | 6900 -> 5 | 6907 -> 17 | 1.1 | 98.90 -> 0.075 | 50 -> 4036 |
| C | 13.5x | 2000 -> 55 | 2036 -> 124 | 1.1 | 24.63 -> 0.064 | 49 -> 1600 |
| D | 8.0x | 1200 -> 400 | 1420 -> 837 | 9.1 | 18.64 -> 0.258 | 49 -> 609 |

### Radeon iGPU

| Workload | Path | Draws/frame | Queue submits/frame | CPU GPU-wait ms/frame | Recording ms/frame | GPU execution ms/frame | Frame wall ms | Peak GPU memory MiB | Validation errors |
|---|---|---|---|---|---|---|---|---|---|
| A | reference | 2000 | 2001.17 | 102.74 [101.13..108.99] | 27.26 [25.69..28.66] | 10.01 [9.94..10.12] | 152.7 [148.7..162.7] | 20.7 | 0 |
| A | batched | 2000 | 1.07 | 3.35 [3.32..3.46] | 1.37 [1.35..1.39] | 2.06 [1.94..2.07] | 8.2 [8.1..8.3] | 148.6 | 0 |
| B | reference | 6900 | 6904.37 | 354.39 [345.36..365.50] | 93.49 [88.00..101.12] | 32.87 [32.68..33.01] | 528.9 [516.1..550.1] | 21.7 | 0 |
| B | batched | 6900 | 2.07 | 2.63 [2.48..2.75] | 3.59 [3.57..3.98] | 4.60 [4.49..4.66] | 16.6 [16.4..17.5] | 181.4 | 0 |
| C | reference | 2000 | 2033.23 | 99.68 [98.23..104.93] | 23.30 [23.23..25.96] | 10.71 [10.67..10.82] | 154.8 [153.2..165.9] | 21.2 | 0 |
| C | batched | 2000 | 1.07 | 4.29 [4.17..4.45] | 1.22 [1.21..1.23] | 2.86 [2.72..2.99] | 14.5 [14.3..14.6] | 148.9 | 0 |
| D | reference | 1200 | 1417.17 | 72.13 [68.86..73.02] | 15.35 [13.08..16.09] | 6.65 [6.58..6.66] | 111.0 [103.2..113.7] | 21.2 | 0 |
| D | batched | 1200 | 8.07 | 5.21 [5.19..5.28] | 0.87 [0.86..0.93] | 3.87 [3.85..3.90] | 13.7 [13.7..14.3] | 84.9 | 0 |

| Workload | Wall ratio (median) | Passes/frame ref -> batched | Barriers/frame ref -> batched | Fence waits/frame batched | Queue submit ms/frame ref -> batched | Submit-to-done latency µs ref -> batched |
|---|---|---|---|---|---|---|
| A | 18.6x | 2000 -> 1 | 2004 -> 6 | 1.1 | 15.04 -> 0.019 | 51 -> 3185 |
| B | 31.9x | 6900 -> 5 | 6907 -> 17 | 1.1 | 53.75 -> 0.036 | 51 -> 5233 |
| C | 10.7x | 2000 -> 55 | 2036 -> 124 | 1.1 | 13.77 -> 0.019 | 49 -> 4071 |
| D | 8.1x | 1200 -> 400 | 1420 -> 837 | 9.1 | 9.40 -> 0.092 | 50 -> 555 |

Submits exclude present's own submit, which is one per frame in both paths. The fractions come from run start and end.

## Reading the numbers

- **The old cost was overhead, not rendering.** In reference mode the fence wait took 49-51 µs per operation (median `wait_ms / fence_waits`) and 63-67% of the wall time in A and B. That is why two very different GPUs score nearly the same there.
- **D gains least, as expected.** Its 8 readbacks per frame are real CPU waits and stay. Its 200 target cycles per frame also keep passes and barriers high.
- **What remains in a batched frame is mostly outside these counters.** On RTX A, wait and recording total about 2.4 of 6.4 ms. The rest includes host scene generation, engine work and present's readback. It wasn't broken down further.
- **GPU execution isn't like for like.** Reference sums timestamps per operation, batched per batch, both top-of-pipe to bottom-of-pipe. The drop reflects far fewer render pass begins and ends, but treat it as coarse.

## Costs of batching

- **Memory:** peak rises from about 21 MiB to 85-181 MiB. Most of it is arena blocks.
- **Latency:** submit-to-done rises from about 50 µs to 0.6-5.2 ms. A batch holds thousands of draws, and any CPU read must wait for that much work.
- **Descriptors:** every bench draw allocates a set (`desc_reused=0`) because constants change every draw. A dynamic UBO offset would remove that; not done.

## `RSX_VK_STATS` overhead

| GPU | Path | Stats on, ms/frame | Stats off, ms/frame | Difference |
|---|---|---|---|---|
| RTX 5060 | reference | 551.4 [520.1..559.8] | 497.3 [475.7..499.1] | +10.9% |
| RTX 5060 | batched | 17.0 [16.8..21.1] | 14.9 [14.8..15.0] | +14.2% |
| Radeon iGPU | reference | 528.9 [516.1..550.1] | 451.7 [427.1..484.2] | +17.1% |
| Radeon iGPU | batched | 16.6 [16.4..17.5] | 17.1 [16.7..17.5] | -3.0% |

**Stats aren't cheap: 11-17% in three of the four cases**, so the tables above are stats-on figures. With stats off, workload B's ratio is 33.4x on RTX and 26.4x on the iGPU. The stats-off runs came after the rest in a fixed order rather than interleaved, so drift can't be excluded; the iGPU's -3.0% is within its range. Only workload B was measured with stats off.

## Not measured

- Any in-game frame rate, CPU contention with SPU or PPU threads, or real shader loads.
- D3D12: see `VULKAN_D3D12_PARITY_PLAN.md`.
- Presenting to a window: the host is headless on Windows and reads each frame back.

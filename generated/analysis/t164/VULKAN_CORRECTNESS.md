# T164: correctness

**Result: VERIFIED for the synthetic host scenes on both GPUs. Not verified in the game: no game was launched.**

Tool: `tools/run_correctness_t164.py`. Results: `logs/correctness/results.json` (private). Hash of the tested host: see `VULKAN_PERFORMANCE.md`.

## Method

Each scene ran three times per GPU, 4 frames where the scene is multi-frame:

| Mode | Settings |
|---|---|
| Reference | Batching off |
| Batched | `RSX_VK_BATCHED_SUBMIT=1` |
| Small batches | Batched with `RSX_VK_BATCH_DRAWS=3`, which forces a flush between draws and exercises the ring |

A row passes only with the expected exit code, validation layer proven loaded, no validation error or warning, and no "nothing to check". Frames are compared by FNV-1a over the frame's bytes (`RSX_VK_FRAME_HASH=1`), not by storing images. Scenes also make their own pixel checks.

## Results

| | RTX 5060 | Radeon iGPU |
|---|---|---|
| Scenes passed | 24 of 24 | 24 of 24 |
| Frame hashes identical in all three modes | 24 of 24 | 24 of 24 |
| Frames compared per mode | 105 | 105 |
| Validation messages | 0 | 0 |

Scenes: default, `--draw`, `--depth`, `--tex`, `--tex-io`, `--quads`, `--shader`, `--mip`, `--rtt`, `--depthtex`, `--mrt`, `--mrt-a`, `--cube`, `--depthbounds`, `--split-present` (1 frame), `--feedback`, `--stencil` (16 cases), `--mip-aniso-guest`, `--mip-aniso` with `PS3_ANISO=16`, `--mip-aniso` unset (negative control: exit 3 as designed), `--bench=a|b|c|d`.

**Draws are not dropped.** Bench draw counts match in all three modes on both GPUs: 8,000 / 27,600 / 8,000 / 4,800 over 4 frames.

| Bench | Submits, reference | Batched | Small batches |
|---|---|---|---|
| A | 8,009 | 6 | 2,670 |
| B | 27,627 | 10 | 9,202 |
| C | 8,139 | 6 | 2,670 |
| D | 5,673 | 34 | 1,634 |

**Longer run.** `tools/run_longval_t164.py`: all four workloads, batched, 30 frames, under validation, both GPUs: exit 0, layer loaded, 0 messages, full draw counts (`logs/longval.json`).

**Other builds.** Default configuration (Vulkan off) `ps3recomp_runtime` builds. `test_rsx_draw_engine` passes all checks; `test_color_feedback_engine` 45 checks, 0 failures (`tools/check_default_t164.cmd`). These tests use POSIX `setenv`, so on Windows they were built with a test-only shim, `tools/posix_env_shim.h`, not in the source commit.

## Stencil

`--stencil` draws through the real program path, 16/16 on both GPUs: equal, write mask, compare mask, less, greater, incr, decr clamp, invert, zero, incr wrap, fail replace, zfail replace, depth-fail keep, clear value, render target change, plus the base case.

## Anisotropy

`--mip-aniso` with `PS3_ANISO=16` shows the expected change; without it the scene's mismatch check fires, so that scene can tell the difference. `--mip-aniso-guest` covers the guest register decode, with **no separate negative control**.

## Limits of this evidence

- Hash equality proves both paths produce the same bytes, not that the bytes match a real PS3. There is no hardware reference here.
- The hash comparison was not mutation-tested with a deliberately broken path. Bench C's frames change frame to frame in every mode, which shows only that the hash responds to content.
- Two-sided stencil is not covered.
- Reference output was not re-compared with a T163 build. Only opt-in counters were added to that path.
- Scene-level validation of the reference path is 4 frames. Only the batched path had the 30-frame run.
- `NV406E_SET_REFERENCE` and semaphores aren't connected on this path, so guest-visible sync is untested. See `VULKAN_D3D12_PARITY_PLAN.md`.
- Synthetic scenes share one thread and one process, with no game-style shader or asset load.

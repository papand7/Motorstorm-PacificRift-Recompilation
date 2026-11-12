# Internal resolution scale (RSX_RES_SCALE): MotorStorm at 1080p

2026-11-05. Vulkan game build (`ps3recomp-vkgame`, `port-vkgame`). Opt-in: unset = unchanged. Nothing committed.

## What it does

`RSX_RES_SCALE=<s>` (`1.5` = 1080p from the 720p guest frame; ratios n/d with n <= 16, d <= 8, s >= 1)
renders every colour and depth target at s times its guest size. The display image and window are
1920x1080 at 1.5. MotorStorm's 2560x720 2x-horizontal AA scene becomes 3840x1080.

- The engine stays in guest units. The Vulkan backend converts at its boundary
  (`libs/video/rsx_vulkan_backend.c`, helpers after `vk_eng_obj`):
  - **Targets:** created at `rsx_rs_len` (rounded up); the guest size is kept in `gw/gh`.
  - **Viewport:** rounded outwards to whole host texels.
  - **Scissor and depth-rect clears:** edges rounded outwards.
  - **Colour windows and depth snapshots:** taken at the host size.
- **Guest memory stays at guest resolution:**
  - readbacks (synchronous, asynchronous, depth) take the host texel at each guest pixel's centre;
  - writes into a target (NV3089) and creation seeds repeat each guest texel over the host texels
    whose centres it covers.
- **GPU reinterpretation** (`RSX_GPU_REINTERP`, MotorStorm's per-frame depth-as-ARGB8 and
  colour-as-Y16X16F of the 2560x720 scene):
  - the engine's guest-size texture is remade once at the host size;
  - the compute pass runs over all host texels.
- **WPOS:** the shader-window key gains the scale (bits [23:20], [30:28]; `libs/video/rsx_shader_window.h`).
  - The helper divides the host FragCoord by aa x scale, continuously.
  - Under a scale it applies with `RSX_SHADER_WINDOW` off too: the FragCoord as before, in guest units.
- **Shadow compare with unnormalized coordinates:** divided by the guest size
  (`libs/video/rsx_fp_decompiler.c`).
- **Polygon offset:** the slope term is multiplied by the scale.
- **Window:** per-monitor DPI-aware under a scale (or `PS3RECOMP_VK_DPI_AWARE=1`). Unaware, the
  1920x1080 client area on the 150 % desktop was clamped to 1711x941 and stretched by the compositor.
- **Fullscreen:** `PS3RECOMP_VK_FULLSCREEN=1` now gives a borderless window over the monitor on Windows;
  the flag was ignored before. **Not yet run in game.**

## Tests

`libs/video/tests/test_rsx_res_scale.c` (`generated/analysis/vksync/tools/build_res_scale_test.cmd`):
59 checks, 0 failed. It covers:
- parsing;
- extents and edges;
- centre mapping both ways over 7 ratios and 4096 pixels (each guest pixel's centre texel maps back to
  it; every host texel maps inside the guest extent, the last partial one clamped);
- WPOS key and helper text, unchanged at 1x;
- the rewrite.

Regressions at scale 1: `test_rsx_draw_engine` and `test_shader_window_engine` pass.
`test_shader_window_engine` under `RSX_RES_SCALE=1.5` differs only in its exact 1x text expectations, by
design.

## Races (MSPR_PATCH=drs: no dynamic resolution, so the scene is drawn at full size)

| Run | Exe | Scale | Result |
|---|---|---|---|
| Kk44 | fe394f8a | 1.5 | race whole and correct (pictures); a dark band over the bottom ~5 % of the frame. p50 38.2-38.7 ms, GPU ~8 ms a frame, VRAM peak 1.83 GB |
| Kk45 | fe394f8a | 1 | comparison: no band. p50 37.6-37.9 ms, VRAM peak 0.98 GB |
| Kk46 | 03a8df66 | 1.5 | viewport rounded outwards: band gone (bottom rows measured like scale 1). Timings unusable (outside load, 62 % CPU with no game running) |
| Kk47 | c3e350d3 | 1.5 | DPI-aware window: swapchain 1920x1080. Race correct. p50 33.0-34.2 ms (30 fps cap), GPU ~9 ms a frame, VRAM peak 2.33 GB |

- **VERIFIED:** 1.5x renders the race correctly, with no crash, at about +0.7 ms a frame against scale 1
  in consecutive runs (Kk44/Kk45). The GPU (RTX 5060) has room.
- **Cause of the band (VERIFIED by the fix):**
  - a guest pass with an odd height covers half a host row less than its image (179 rows -> 268.5 of
    269), and the undrawn row spread up through the game's downsample and blur chain;
  - rounding the viewport to whole texels removed it.
- **Not yet checked:** menus, other tracks and weather, photo mode, split screen. Visual differences that
  scaling can bring: half-texel blur offsets tuned for 720p, 1-pixel lines and points thinner.

## Use

`RSX_RES_SCALE=1.5 MSPR_PATCH=drs` (and `PS3RECOMP_VK_FULLSCREEN=1` for the whole screen).
On this 2560x1440 monitor `RSX_RES_SCALE=2` would match it pixel for pixel; not yet run.

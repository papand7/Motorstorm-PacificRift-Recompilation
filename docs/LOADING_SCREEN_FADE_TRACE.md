# Loading-screen fade constant c[59].w (offline, 2026-10-23)

Data: run `20261023-172442-present-stall` (RSXI frames 1340/1350/1360, `shaders/vp_*.hlsl`, `fp_*.hlsl`). MotorStorm was not launched for this analysis.

## What is established

| Finding | Status |
|---|---|
| Both loading-screen vertex programs copy `c[59]` to TEXCOORD1. They are 5 instructions, with no branch, at start slot 0 | VERIFIED |
| The fragment program outputs `rgb = X + w·(tc1.rgb − X)` with `tc1.rgb = 0`, i.e. gain `1 − w`. No saturate on `tc1`. Its registers are fp16 on the RSX, which is enough range here | VERIFIED |
| `c[59] = (0, 0, 0, w)`, w = −0.561099, −0.712928, −0.865221. Predicted gains 1.0971 / 1.1942; measured 1.0972 / 1.1949 | VERIFIED |
| The D3D12 translation is faithful. The value comes from the guest's command stream | VERIFIED |
| Δw = −0.1518 per 10 frames. At the measured 32.9 presents/s that is −0.500 per second. No round per-frame step fits (1/60 = 0.0167, 1/30 = 0.0333) | VERIFIED (numbers), INFERRED (time-driven) |
| Extrapolated back:<br>w = 0 at frame ≈ 1303 (≈ 33.3 s);<br>w = 1 at frame ≈ 1237 (≈ 31.3 s), right after `loadscreen_page_read` (frame 1227, 31.26 s) | INFERRED |
| Reading: **a 2-second fade-in from black.** At w = 1 the output is fully `tc1.rgb` (black); at w = 0 the artwork is unmodified. It should stop at w = 0. Instead it keeps running, and the screen brightens toward white | INFERRED |
| Presentation suppression did not cause it. The ramp runs while presents are steady at 32.9/s (frames 1237–1716); the stall starts only after the thread exits | VERIFIED (timeline) |
| Host time. A 0.5/s rate against host wall time matches a 2.0 s duration. Nothing suggests a guest time base running fast or slow | INFERRED |

## Open: why the fade does not stop

**Not identified offline: the guest function that writes `c[59]`.**
- The lifted PPU code holds 86 literals of the method `0x1EFC` (`SET_TRANSFORM_CONSTANT_LOAD`) in 17 files.
- The slot is passed in a register; no literal 59 appears near them.
- No guest code was changed.

| Candidate | Status | Test |
|---|---|---|
| The guest clamps the fade (`min(t/2, 1)`), and a lifted float operation (`fsel`/compare) loses the clamp | HYPOTHESIS | PPU float conformance for `fsel` and `fcmpu` paths; find the writer first |
| The fade stops on a state change (load progress, an event, a frame/flip callback) that does not arrive | HYPOTHESIS | the writer's caller chain |
| The guest's own fade really overshoots (no clamp intended), and the PS3 shows the same | HYPOTHESIS, unlikely: the image would wash out on hardware too | reference capture on hardware or RPCS3 (not available here) |
| Wrong host time input | not supported by the 0.5/s rate | — |

**Do not clamp `c[59].w`, change the shader or adjust timing:** none of the above is verified.

## New diagnostic: `RSX_VPC_WATCH=<slot>` (`libs/video/rsx_commands.c`)

- Off by default.
- Prints one `[vpc-watch]` line each time the w lane of that vertex constant is written with a new value: the vec4, the raw bits and the write ordinal. Repeated uploads of the same value are silent.
- At most `RSX_VPC_WATCH_MAX` lines (default 32, clamped to 1..4096), then one cap line.
- Test: `tools/test_vpc_watch.py` (4 source checks, plus 6 harness checks in WSL).

**What it answers in the next run:**
- the value at the first upload;
- whether w starts at 1;
- whether the rate is constant;
- whether w is ever held or reset (e.g. at the renderer transition).

**Finding the writer** needs a guest-side trace in a later run. The runtime already has the tools:
- `PPU_WWATCH=<EA>` with `PPU_WWATCH_LEN` and `PPU_WWATCH_MAX`, over the game object or command-buffer range that receives `c[59]`, prints the guest function, `lr`, tid and a stack;
- `PPU_WVAL=<bits>` with `PPU_WVAL_LO`/`PPU_WVAL_HI` catches stores of an exact value.

The `[vpc-watch]` timeline supplies the exact bits and timing these need. Prepared, not part of the next run's goals.

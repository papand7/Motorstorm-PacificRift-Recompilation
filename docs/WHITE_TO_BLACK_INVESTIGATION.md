# White-to-black investigation (offline, 2026-10-23)

**Symptom (2026-10-21 run, no skip, older build):** after the intro, an artwork screen with the MotorStorm emblem appears (`generated/frames/menu-long-20261021/frame_023.bmp`). Over ~25 s it brightens toward white (frames 24–30), then every present is black (31–34). The run `menu-noscr-20261021` (`SCREEN_AS_TEX=0`) shows the same curve.

No exposure or rendering parameter was changed.

## Offline measurements (VERIFIED, from the saved frames)

| Frames | Mean luma | Pure-white pixels |
|---|---|---|
| 23 | 24.7 | 0.0 % |
| 24 | 130.4 | 8.9 % |
| 26 | 175.9 | 40.9 % |
| 28 | 189.3 | 52.5 % |
| 30 | 196.0 | 58.0 % |
| 31–34 | 0.0 | — (every byte 0) |

1. **The brightening is one scalar gain applied to the same image.**
   - Each frame is a tight monotone function of the previous one. The spread of the output for a fixed input is 4–12 levels out of 255, and black stays black.
   - The gain is identical in all three channels: 24→26 R/G/B ×2.72/2.72/2.73, 26→28 ×1.63/1.62/1.63.
   - The gain shrinks frame to frame, so the image converges as it saturates.
2. **The black frames are exactly zero:** max 0, one unique value. That is what a cleared target, no draw, or NaN/Inf written to a UNORM target produces. It is not a dim image.
3. **Frame 22 → 23** is a content change (the screen switches), not part of the ramp.

## Hypotheses

| Hypothesis | Status | Evidence |
|---|---|---|
| Auto-exposure / luminance adaptation running away | **Leading, open** | A per-frame scalar gain, equal in R, G and B, growing and converging, then zero, is what an exposure multiplier diverging to Inf (Inf·0 = NaN → 0) looks like. The game has a luminance pass: `fp 0x0074C781` has Rec.709 weights (RSXI `smoke1`). |
| Measured luminance never reaches the guest | open (sub-case) | The luminance chain (`fp 0x0074D0C1` 640×360, `fp 0x007400C1` 320×180 from RT `0x01DD0000`) renders into D3D12 resources only. No backend path writes render-target pixels back to guest memory (all readbacks in `rsx_d3d12_backend.c` are diagnostic dumps). A CPU or SPU read of that result would see stale guest memory. |
| Occlusion-query feedback | **new candidate, open** | The game issues ZPASS `GET_REPORT`s into main memory from boot (`0x14100–0x14130`). The runtime always answers `0xFFFF`. A pixel-count-driven measurement would always read "65535 passed". Which queries run on the artwork screen is unknown: only the first 6 reports were logged. `RSX_REPORT_TRACE` now logs each distinct one. |
| Missing or wrong shader constants | open | Could feed the exposure. The RSXI draw events record up to 16 non-zero fragment constants per draw. Comparing them across the ramp separates "the guest's constant ramps" from "the GPU-side value ramps". |
| Incorrect shader translation | weakened | There are no compile, PSO or decompile failures in either run (VERIFIED). A semantic error is not excluded, but a fixed mistranslation would not give a time-varying gain. |
| Gamma / colour-space error | **eliminated as the cause of the ramp** | A gamma error is a fixed curve; the observed gain changes every frame. |
| Render-target format or channel mismatch | **eliminated** | The gain is equal in R, G and B and the image structure is preserved. |
| Render-target initialisation (garbage) | **eliminated for the ramp** | Each frame is a clean function of the previous one. It may still apply to the black frames (cleared or never drawn). |
| Texture sampling / addressing | **eliminated for the ramp** | The content and its geometry are unchanged; only the gain moves. |
| GPU synchronisation | unlikely | The ramp is smooth and monotone; races give erratic frames. |
| Frame presentation (frame-copy fallback) | **eliminated** | `SCREEN_AS_TEX=0` gives the same curve (2026-10-21). A failed `Present` was not checked then; it is logged now. |
| Depth/stencil state | unlikely | It cannot produce a uniform scalar gain. |
| Resource lifetime / descriptors | unlikely for the ramp | It would swap content, not scale it. Possible for the black frames. |
| The game intentionally fades to black | open | It is possible after a white flash; a capture shows whether the final pass draws with zero constants or does not draw. |

**Consistency note:** the same post-FX chain runs during the intro (the luminance programs are built then), and the intro did not white out. Adaptation may be bypassed during movie playback (HYPOTHESIS). This does not contradict the leading hypothesis.

## What a capture must show (see `RSX_FRAME_CAPTURE_PLAN.md`)

| Question | RSXI evidence |
|---|---|
| Does the guest submit valid commands? | `draw` events: the program, targets and viewport are the same across ramp frames |
| Does the shader produce the wrong output? | `pass` snapshots of `0x01DD0000` and the 640×360 / 320×180 luminance targets, with content hash and non-zero fraction |
| Does the render target hold valid data? | the scene target is normal while the backbuffer is bright, so the gain is applied late |
| Does the presented image go white or black? | `end` backbuffer snapshot |
| Is the black frame intentional? | the last pass's constants and draw count in a black frame (draws present with zero constants = a guest fade; no draws = nothing submitted) |
| Where does the gain come from? | the fragment constants of the tone-map/present programs (`0x0074C781`, `0x02193941`) across ramp frames: ramping means the guest computes it; constant means the GPU side does |

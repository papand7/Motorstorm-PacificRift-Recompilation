# T171: terrain transparency root cause

Status: **mechanism VERIFIED from existing captures; on-screen result in the game NOT VERIFIED** (no launch authorized).

## Mechanism

RSX WPOS follows `SET_SHADER_WINDOW` (method `0x12D0`: height 720, bottom origin). The host read SV_Position (top-left origin) unless the opt-in `RSX_SHADER_WINDOW=1` was set, and no T169 run set it.
The track draw's scene lookup (see the reconstruction report) was therefore vertically mirrored: tracks showed the opposite part of the screen, such as sky and trees in the ground and a vehicle or rider near the horizon. That is the "see-through". Nothing is transparent and no terrain is missing.

## First incorrect draw

Ops 1110-1112 in D1 f005110, FIFO `0x00252BB4`, fp `0x022CD841`.
Snapshot op0982 has no tracks; snapshot op1112 has them with the wrong content. The defect begins during the track draw, not before it and not in compositing.

## Numeric proof (`tools/mirror_check_t171.py`, private)

Over the 5,025 pixels changed between op0982 and op1112:

| Prediction for the track pixels | Luma correlation |
|---|---|
| Mirrored scene through the guest window | **0.814** |
| Mirrored scene across the full surface | 0.732 |
| Guest-correct lookup (own pixel) | -0.078 |

Mean luma was 252 before the draw and 162 after it.

## Correction

`RSX_SHADER_WINDOW` becomes default-on (`=0` restores the old read). The T145 remap applies only to programs reading WPOS: `0x022CD841`, `0x07200641`, `0x070B0701`. Changed files: `libs/video/rsx_shader_window.h`, one comment and one log field in `libs/video/rsx_d3d12_backend.c`.
T145 already verified in game that these programs remap with no PSO failures or new debug-layer messages, but its captured phase held no tracks.

## Ruled out

- Blending: off on the track in both guest and host.
- Terrain discard: opaque terrain is drawn before the tracks.
- Stencil rejection: see the depth/stencil audit.
- Output alpha: irrelevant with blending off (fixture).

## Remaining uncertainties

1. **PARTIAL:** VB `frame_006` (race clock 00:06.66) shows blocky bottom patches with trees, sky and a banner, dark blue and red stripes on the right, and a horizontal cut near y about 650. A simple mirror of the same frame does not predict them and an affine search was inconclusive (best correlation 0.63). They may be a stale copy, another WPOS draw reading `0x0243AB00`, or something else. Whether the fix removes them needs a capture.
2. **HYPOTHESIS:** the vertex stream of ops 1111/1112 holds y=-100000, w about 100030 values, possibly unused ring slots. Not established as a cause.
3. The "fragments" seen with `RSX_DEPTH_STATE=1` remain unexplained; stencil refs do not explain them.
4. The T145 "foam over foreground beach" artifact occurs with and without the switch.
5. Water and surf also change under the new default. This is correct by guest semantics, but the shoreline needs checking in game.
6. No PS3 reference exists.

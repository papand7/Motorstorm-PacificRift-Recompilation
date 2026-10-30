# T171: terrain transparency root cause

Status: **mechanism VERIFIED, including in the authorized runs. Track correction PARTIAL in game: one visible defect is gone, but no close-up tracks or arm B intermediates were captured. Rectangular patches NOT fixed.**

## Runtime A/B results (arm A off, arm B on)

| Question | Result | Status |
|---|---|---|
| Is the mirror present with the fix off? | Arm A `f005564`, ops 1876-1887, cmd `0x0024FC8C`: 6,538 changed pixels correlate **0.865** with the mirrored scene and -0.239 with their own pixel; `wpos_remap=0` | VERIFIED |
| Does the correction reach the game? | Arm B remapped `0x022CD841`, `0x07200641`, `0x070B0701` and **`0x071CE2C1`** (window `0x12D0`, h=720, bottom), 0 compile or PSO failures | VERIFIED |
| Tyre tracks at 3.0 and 4.1 s | Arm A shows dark blue and red vehicle fragments in the track behind the rider's helmet at 2.99-6.09 s. Arm B shows a pale sand-toned track there at 3.06 and 4.09 s | VERIFIED visually at this one location |
| Sky and trees in tracks | Not seen in either arm at these clocks, where tracks are thin and far away. Removal is not directly observed | PARTIAL |
| Water and surf | No visible regression; surf and foam look alike at matched clocks. Camera pacing differs slightly, so there is no pixel comparison | PARTIAL |
| Shoreline alignment | No visible shift beyond that camera difference | PARTIAL |
| Rectangular patches | **Present in both arms**: blocky sand patches on the far ground at 0.7 s and near the track ahead at 3.0-4.1 s. Not caused by this mirror alone | VERIFIED |
| VB-style trees and stripes at the bottom | Not seen in either arm, but VB's clock of 6.66 s is past arm B's last frame | Open |
| Other regressions | None seen. No vehicle speckle in arm B (depth state off) | Within the frames captured |
| Consistency of all WPOS programs | All four remap the same way, but arm B's capture has no WPOS draw, so per-draw state and intermediates exist only for arm A (`wpos_remap=0`) | PARTIAL |

Corrections to the earlier text:
- There are **four** WPOS programs, not three. `0x071CE2C1` (one blended draw, op 1927 in arm A) was not in the earlier list.
- The `SET_SHADER_WINDOW` method is `0x1D88`; `0x12D0` is its value.

## Mechanism

RSX WPOS follows `SET_SHADER_WINDOW` (method `0x1D88`, value `0x12D0`: height 720, bottom origin). The host read SV_Position (top-left origin) unless the opt-in `RSX_SHADER_WINDOW=1` was set, and no T169 run set it.
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

`RSX_SHADER_WINDOW` becomes default-on (`=0` restores the old read). The T145 remap applies only to programs reading WPOS: `0x022CD841`, `0x07200641`, `0x070B0701`, `0x071CE2C1`. Changed files: `libs/video/rsx_shader_window.h`, one comment and one log field in `libs/video/rsx_d3d12_backend.c`.
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

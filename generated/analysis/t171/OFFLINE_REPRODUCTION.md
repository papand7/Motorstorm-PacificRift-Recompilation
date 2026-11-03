# T171: offline reproduction

`libs/video/tests/test_t171_track_warp.c`, run by `tools/test_t171_track.py`, D3D12 WARP with the debug layer on. **19 checks, 0 failures.**
It is a hand-assembled fixture modelled on the verified state, not the game's ucode and not a recorded RSX command sequence. It contains no game data.

Terrain and sky are distinct colours; a track relights the terrain it reads.

| Arm | Result | Shows |
|---|---|---|
| Correct | relit 32/32 | fixed lookup reads own pixel |
| Correct, alpha 0 | relit 32 | alpha irrelevant with blending off |
| Correct, later object | object 32 | later object survives |
| **Old WPOS text** | **sky 32** | **defect reproduced** |
| Stale copy beneath | 32 | stale feedback is distinguishable |
| Blend by alpha 0 | terrain 32 | blend-factor control |
| Write mask 0 | terrain 32 | colour-mask control |
| Depth writes on | relit 32, object 0 | depth-write control |
| GREATER | terrain 32 | depth-function control |

The T145 fixture also passes (35/35).

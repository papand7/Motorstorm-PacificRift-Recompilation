# T171: tyre-track rendering reconstruction

Source: ps3recomp base `542420e`, fix `b282e26` (branch `agent/t171-tire-track-depth-fix`); root base `61fd020`.
Evidence is private, from existing T165 and T169 runs: D1 frame `t169/ab/runtime-D1-20261030-171539/rsxi/frames/f005110`, B3 frame `t165/ab/runtime-B3-20261030-125807/rsxi/frames/f002192`, and the VB frames. No game was launched for T171.

## VERIFIED: the draw

Tracks are not a conventional alpha decal. They are an opaque relighting draw that re-reads the scene under it.

| Item | Value (D1 f005110, baseline RSX state) |
|---|---|
| Ops | 1110-1112, one packet, FIFO `cmd_offset 0x00252BB4`, call_ret 0 (main ring) |
| Programs | fp `0x022CD841`, vs `0x0A76013E` |
| Geometry | prim 6, counts 256/256/204; index u16 at main `0x008E4880`, restart 0xFFFF; a0 at main `0x8080B680`, stride 32, 4 floats, world y about 14.15 |
| Targets | colour `0x00750000` (viewport 1272x715), MRT1 `0x01650000` (read from the B3 draw, not rechecked in D1), zeta `0x00ED0000` |
| Units | u0 `0x02410000` and u1 `0x02425580` 128x128 fmt 0x85; u2 `0x00750000` 2544x715 fmt 0xA5 (the scene it writes); u3 `0x06EE5580` 512x512 fmt 0x86 |

The shader computes `r1.xy = position.xy * c5.xy + c5.zw` from WPOS, samples unit 2 there and relights the result with the normal maps on units 0 and 1.
c5 = (1/1272, -1/715, 0.000195, 1.00699), and 1.00699 = 720/715, so the guest lookup is v = (720 - WPOS.y)/715.

## VERIFIED: frame order (D1)

1. Opaque scene: ops up to 982.
2. Low-resolution pass `0x0B830000`: 984-1106; `0x0BA10000`: 1108; `0x0243AB00`: 1109.
3. **Tracks: 1110-1112.**
4. 30 decal boxes, fp `0x022C20C1` (GREATER, no writes, stencil): 1113-1142.
5. Blended water, surf and foliage: 1143-1243, then bloom and later passes.

In B3 the same fp is op 568, one draw, also after the opaque and low-resolution passes.

## HYPOTHESIS / PARTIAL: where the geometry comes from

The executable holds `DeformationManager`, `PathDeformer`, `PointDeformer`, `SplatterDeformer`, `deform_path_1d.dds`, `deform_shape_2d.dds`, `DeformationMipCopy`, `deformationMap`, `ground2_deform`, `NonDeformableTrack` and Havok `hkpTyremarksInfo`.
The link from these to fp `0x022CD841` is a HYPOTHESIS. A lis/addi scan and a literal search found no code references, so the PPU creation path is not traced, and SPU involvement is unknown. The rendering fix does not depend on it.
No PS3 reference capture exists; guest behaviour is read from guest state and ucode.

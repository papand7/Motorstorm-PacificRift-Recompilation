# T169 Phase 4: next visual correctness plan

1. **Settle Question B.** Add an alpha-preserving snapshot of `0x01650000` and capture a fast-moving frame, then compare against a PS3 or RPCS3 reference. Decide between M1 and M2 from that, not from image cleanliness.
2. **Validate blur at speed.** Current evidence is one slow vehicle.
3. **Far-vehicle slivers and terrain patches.** Offline first, from an existing capture: compare the depth values and draw order of a sliced vehicle and the terrain over it. They occur with depth state on and off, so start with terrain or decal order and clipping.
4. **Make `RSX_RT_REINTERP` and `RSX_DEPTH_STATE` default only together** and only after 1 and 2, because depth state without the decode speckles vehicles.
5. **Check the intermittent preflight failures:** the missing `[visual-active]` line in the reinterp scenes and `test_spurs_wws_concurrency`.
6. **Repeat the performance comparison** with several runs per arm, since one run can't attribute the difference recorded in `RENDERING_PERFORMANCE_CORRELATION.md`.

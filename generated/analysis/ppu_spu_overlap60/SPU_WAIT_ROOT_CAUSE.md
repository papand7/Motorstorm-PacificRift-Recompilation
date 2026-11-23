# SPU_WAIT_ROOT_CAUSE: why ~2 ms less PPU compute became ~2 ms more waiting

1. VERIFIED: ppucc2 raised main usleep time ~2 ms/frame (11.1-11.7 vs 8.7-10.4); the frame improved ~0.7 ms (not significant, p=0.13).
2. VERIFIED (Kksr77): 7.22 of 13.14 ms/frame of main compute runs while SPU work is active (overlapped). Only 5.92 ms is serial.
3. MODELLED: frame is about the sum over segments of max(PPU part, SPU part). Cutting PPU time inside an overlapped segment only lengthens the next wait by the same amount. Only serial compute shortens the frame. If the 2 ms saving followed the compute split (55% overlapped), ~1.1 ms was absorbed by waits and ~0.9 ms was real, close to the +0.7 ms seen. HYPOTHESIS: the saving's actual distribution was not measured (needs per-function attribution of the ppucc2 delta).
4. VERIFIED: the waits are bound by SPU-side latency.
   - vehiclephysics 2.91 ms: 1.65 is hand-off (JobBatchHandler usleep(200) polls, ~550 us on the host timer), 1.43 is execution.
   - renderable 1.85 ms: lane contention behind pvsjob (first job starts 1.46 ms after the wait begins).
   - Havok: ~12 short waits, no long wave.
5. Not shown: lane throughput (Wws lanes 1.54 of 5 busy), interpreter residue (0 steps), Havok (0.27 ms gain gave no fps), CPU saturation (see CPU_SCHEDULING_ANALYSIS.md).
6. Late submission: PARTIAL. Kick order is guest-controlled; no proof any kick can move.

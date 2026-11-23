# FRAME_DEPENDENCY_GRAPH (private, offline, 2026-11-19; no race run)
Source: Kksr77 trace (exe 33253d9d, Fix 2 on, stats/hooks off, 825 frames, 24.23 ms), `tools/overlap77.py`, plus roadto60_next/CURRENT_CRITICAL_PATH.md section 8.

## Chain (order VERIFIED; durations VERIFIED from trace unless noted)
main compute -> kick vehiclephysics batch 1 -> wait 0x94CC80 -> hand-off gap -> batch 2 -> wait -> Havok waves (0xA4C590, ~12 short waits) -> PVS kick -> renderable kick -> wait (lane contention behind PVS) -> GcKernel poll -> Present/EndFrame.

## Main-thread time (disjoint, ms/frame)
| Segment | ms |
|---|---:|
| JobBatch waits | 7.65 |
| Havok semaphore | 2.10 |
| Havok polls | 0.43 |
| GcKernel ref poll | 1.00 |
| Compute (guest + runtime), remainder | 13.14 |
Union of all waits 11.08; compute 13.14; total 24.23.

## Overlap split (VERIFIED from spans; "SPU active" = any Wws or Havok job running, not necessarily the one waited on)
| | total | SPU active | SPU idle |
|---|---:|---:|---:|
| main waiting | 11.08 | 7.79 | 3.30 |
| main compute | 13.14 | **7.22** | **5.92** |
SPU runs something for 15.0 of 24.2 ms.

Reading: 5.92 ms of compute is truly serial (SPU idle). 7.22 ms of compute already runs beside SPU work. 3.30 ms of waiting has no SPU job running (hand-off / wake latency).

## Where the serial compute sits (tools/serial77.py, VERIFIED from spans; gaps labelled by the NEXT wait)
| next wait | compute ms/frame | serial (SPU idle) | gaps/frame |
|---|---:|---:|---:|
| JobBatch 0x94CCA8 | 6.20 | 3.00 | 4.9 |
| semaphore 0x18715C | 2.46 | 1.36 | 6.4 |
| Havok poll a48364 | 1.83 | 0.83 | 2.3 |
| Havok poll a49ad4 | 0.86 | 0.43 | 4.3 |
| GcKernel poll 72e5c0 | 0.97 | 0.30 | 0.4 |
So ~3.0 ms of serial compute is the prep before JobBatch kicks (vehicle physics/visibility/occluders) and ~1.4 ms is before the 0x187118 waits. These are the first places to attribute with the per-function sampler; the sampler run in RACE_VALIDATION_PLAN step 1 should bucket by these gaps.

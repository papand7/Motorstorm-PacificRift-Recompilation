# EXECUTIVE_SUMMARY: MotorStorm PR 1.00 Vulkan, critical path at ~30 ms/frame

Offline investigation, 2026-11-17. No race, build, commit or production change. Details: CRITICAL_PATH.md, SPU_JOB_ANALYSIS.md, PPU_DEPENDENCIES.md, OPTIMIZATION_CANDIDATES.md, NEXT_RACE_PLAN.md. Tools in `tools/`, numeric outputs in `out/`.

## What prevents 60 fps (VERIFIED unless marked)
- The race frame is one serial chain on the guest main thread. It computes ~9.2 ms of lifted guest code plus ~1.1 ms of runtime. A further 1.1 ms of runtime is harness-only route trace hooks.
- It waits ~19 ms for work it kicked itself:
  - JobBatch waits 10.3 ms (vehicle physics 3.3, visibility/PVS 3.2, occluders and small batches ~3.8);
  - Havok semaphore 0xA4C590 3.4 ms;
  - the Present spin on renderable jobs 4.1 ms. The trace said ~0.2 ms only because that spin is a guest loop the syscall trace cannot see;
  - other ~1.2 ms.
- During the simulation phase the SPUs sit mostly idle (≈0.9 Wws jobs + 1.3 Havok tasks running on average): the waits are dependency waits, not capacity waits.
- In the render phase the 5 lanes are saturated 48 % of the time, mostly by renderable jobs.
- SPU work costs ~85 thread-ms per frame on a 6-core / 12-thread host (game ~4.9 cores busy). Even perfect overlap could not fit 60 fps without making SPU work much cheaper.
- "0xA4C590 = visibility semaphore" is a mislabel. 0xA4C590 is Havok's and the physics wrapper's semaphore. Visibility waits in `Vis::Wait` 0x45CAA8 -> `PVSComputerImpl::WaitForCompletion` 0x5F74B0 through `JobBatch::Wait`.

## Why previous optimisations did not show
1. **Too small a share.** PPU codegen covered 6.9 % of main-thread samples, worth ~0.65 ms (modelled). Vehicle-physics natives act on 0.93 ms of SPU execution per batch. Both are below the ±1.5 ms run noise.
2. **The sped-up part is not where the time is.**
   - Havok: a recorded race HK2 run replays in 0.42-0.50 ms, but the mean in-race HK2 run takes 3.32 ms. MFC emulation is 18 %; host contention alone doubles replay time under full load (measured); the rest is unexplained (HYPOTHESIS). Natives give only 1.05-1.13x on the whole task (measured).
   - renderablejob: ~62 % of its time is the SPU **interpreter**, which the natives never touch (modelled from 3,799 jobs, R^2 0.82).
3. **Hop latency around every JobBatch.** Every JobBatch is completed (and, PARTIAL, submitted) by the guest JobBatchHandler thread. It polls with usleep(200), which the port turns into ~0.54 ms (host timer). That adds ~0.5 ms per serial batch, as much as the vehicle-physics SPU work itself.
4. **Measurement noise and artifacts.**
   - Disturbed runs (11.6-24.7 fps with the same exe/env).
   - Route PT hooks never turned off in races (+1.1 ms main thread).
   - `[main-cyc]` is dominated by on-CPU spin-waits.
   - The only critical-path trace (Kksr36) is heavily PT-distorted and covers the race intro, not driving.

## Three strongest remaining exact opportunities
1. **C1: JobBatchHandler poll fidelity.** Honour usleep(200) on that guest thread.
   - Modelled saving: 1.0 ms/frame (measured hop components, instrumented frames), 1.9-3.0 ms extrapolated to uninstrumented frames.
   - Restores PS3-like timing; no semantic change. Cost: one spinning logical CPU.
   - Confidence: medium.
2. **C2: remove the renderablejob interpreter fallback.**
   - Modelled: 17-20 SPU-ms/frame removed; 0.9-1.3 ms mean frame-tail reduction in intro frames. The effect on the 4.1 ms driving Present spin is BLOCKED until the miss sites are known.
   - Mechanism HYPOTHESIS: relocated-entry rejoin miss, or mid-block interrupt resume. infamous2's engine takes interrupts only at dispatch points; agent report, code read.
3. **C3: turn route trace hooks off at race entry in measurement runs.**
   - Measured: 1.11 ms/frame of main-thread CPU.
   - Not a production gain, but it removes a bias from every A/B.

Combined C1+C2 modelled: 1.5-4 ms/frame (~29.5 -> ~26-28 ms). No candidate is modelled anywhere near 13 ms.

## What can be tested offline now
- C1:
  - the usleep(200) accuracy and CPU cost on an isolated runtime copy (unit test pattern of `tests/test_timer_usleep_win32.c`);
  - the hop model by rerunning `tools/decomp.py`/`batch_hops.py` with a changed poll period.
- C2:
  - the renderable lift/rejoin hypothesis: whether `spu_lifted_lookup` resolves relocated keys for interpreter rejoin, using the FNREC 12E40 job-entry snapshots and the rj harness;
  - interpreter vs lifted cost per step in replay.
- Havok contention: parallel replay (done: 2.0x mean slowdown at 12 copies).

## Missing evidence
- Driving-frame critical path without PT logging (BLOCKED, R1).
- Renderable AOT miss pcs and reasons (BLOCKED, R1 `PS3_SPU_AOT_PROF`).
- Per-boundary in-race timing of Havok tasks.
- Exact proof that the JobBatchHandler performs submissions (PARTIAL).
- PPU read/write sets for any reordering (BLOCKED).

## Is a 13 ms main thread supported by current evidence?
**No.**
- Its own compute is ~10 ms (production) and is spread thinly.
- The waits are genuine dependencies on SPU work. That work costs ~85 thread-ms per frame on a host with ~6 physical cores.
- The exact, evidence-backed candidates total ~1.5-4 ms.
- Reaching ~13 ms would need architectural change: frame pipelining/overlap of sim and render, which is excluded here. Alternatively, several-fold cheaper SPU execution overall: interpreter removal, MFC/atomic/contention overhead, Havok and renderable work. Plus a large PPU codegen gain, applied together.

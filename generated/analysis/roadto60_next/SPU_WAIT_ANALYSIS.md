# SPU_WAIT_ANALYSIS: the ~12 ms of main-thread waits on SPU work (Phase 3)

Private, offline. Labels VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED / MODELLED. All race numbers come from existing logs (`out/metrics_ksr47_67.*`).

## 1. Size and split (VERIFIED totals, BLOCKED per-site split)

| Wait | Candidate (Kksr61/63/64) | Other Fix-2-on exes (Kksr50/54/57/59) | Pre-Fix-2 (Kksr48/52/56/58) |
|---|---:|---:|---:|
| JobBatch waits (sc141, tid 1), ms/frame | 8.6 / 10.0 / 9.6 (median 9.6) | 8.4 / 9.3 / 9.1 / 8.1 (median 8.7) | 8.2 / 8.3 / 8.5 / 8.5 |
| Havok semaphore (sc130), ms/frame | 2.92 / 2.84 / 2.94 | 3.59 / 3.51 / 3.36 / 3.46 | 3.81 / 3.92 / 3.66 / 3.84 |
| fps | 40.0 / 38.0 / 36.0 | 39.5 / 38.0 / 35.4 / 36.7 | 32.6 / 31.0 / 31.3 / 27.6 |

All of these ran with `PS3_SPU_TASK_STATS=1000`, which adds ~1.2 ms to each HK2 run and ~0.4 ms to each HK1 run. The Havok row is therefore an upper bound for production.

## 2. A. Havok (stages 1 and 2)

| Item | Finding | Label |
|---|---|---|
| Stage times in race (stats on) | candidate HK1 1.55-1.59, HK2 2.91-3.00, HKd 0.42-0.44, HKc 0.29-0.32 ms/run; plain-lift exes HK1 1.65-1.74, HK2 3.35-3.64 | VERIFIED |
| Chained execution gain in race | HK2 −0.45 ms/run (−13 %), HK1 −0.12 ms/run (−7 %). The main thread's Havok wait fell by ~0.55 ms/frame (2.9 vs 3.5) | VERIFIED (n = 3 vs 4, different exes, stats on) |
| Chained gain on replays (bit-exact, 4/4) | HK2: plain 2.33-2.37 ms, chain 1.93-2.15, chainfast (`--fast-lower`) 1.82-1.94 (4 recordings, best of 40, interleaved; host loaded by bf1943). HK1: chain 1.04x, chainfast 1.06x over chain (havok_gap) | VERIFIED |
| Stats overhead | 1.17 ms per 5,000-DMA run (QPC + shared atomics on every MFC channel write) | VERIFIED (microbench, havok_gap) |
| MFC DMA emulation, stats off | 89-95 ns/DMA (1 thread) and 135-167 ns/DMA (5 threads), with the production `PS3_SPU_MFC_FAST=1`. HK2 issues ~5,000 → ~0.7-0.8 ms/run | VERIFIED (microbench, `out/mfc_lean_bench_fast.txt`) |
| Atomic reservations | per HK2 run: ~450 GETLLAR, 180 PUTLLC, ~7 failed (4 %). With `MFC_FAST` (16 lock-line stripes) they are part of the 135-167 ns above | VERIFIED |
| SPURS / channel synchronisation | tasks are dispatched to a host thread pool (`PS3_SPU_TASK_POOL=1`); pickup ~7 µs (criticalpath60) | VERIFIED pre-Fix-2 |
| Interpreter fallback / rejoins | 0 interpreted instructions in all Havok images before and after Fix 2 | VERIFIED (spu_rejoin60) |
| Worker completion imbalance | not measurable without per-run spans. A wave ends with its slowest of ~4.6 runs | BLOCKED (Test B: ftrace kinds 34/39) |
| Can chained Havok go further exactly? | yes, a little. (1) `--fast-lower` (exists only in ps3recomp-spuopt's lifter): HK2 replay 1.04-1.11x over chain, bit-exact on 4/4 recordings; it drops only the LS diagnostic gates (`SPU_LS_WATCH`, `SPU_SMC_WATCH`) inside groups. (2) MFC lean path (§5). Together ≈ 0.1-0.2 ms per HK2 run, **≤ ~0.2-0.3 ms/frame** on the wave | MODELLED |
| The existing HK2 natives (hand5/gen5) | on the chain-chunks + fast-lower lift they add ≤ 1-2 % whole-task (hand5 1.85-1.87 vs the same exe with `PS3_SPU_NATIVE=0` 1.82-1.86 ms) | VERIFIED (`out/hk2_replay_phase4.txt`) |

**Interpretation (HYPOTHESIS):** in the candidate, the ~0.55 ms/frame saved on the Havok wait did not shorten the frame within noise. The main-thread JobBatch wait rose by about as much (median 9.6 vs 8.7 ms/frame), so the Havok chain is only partly binding. Once the main thread reaches the next wait earlier, it waits longer for the same Wws jobs. If that holds, Havok compute is not the next lever: the vehicle-physics, PVS and occluder jobs are. Test A without stats and Test B decide this.

## 3. B. SPU paths: interpreter, rejoin, dispatch, register sync, helpers, LS access

| Path | State in the candidate | Label |
|---|---|---|
| Interpreter fallback | only renderablejob was ever interpreted. Fix 2 (rejoin), the corrected lift (no fake return at 0xA650) and C-A (drain resume) remove the amplification, its source and the remaining unwinds. Residual transition overhead was ≤ 0.6 SPU-ms/frame before C-A and the lift fix | VERIFIED (spu_rejoin60), residual MODELLED |
| Failed rejoins | C-A: 0 unwinds, 0 misses, 0 interpreted on the synthetic test (157/157). No race count with the candidate | VERIFIED offline; race BLOCKED |
| Repeated indirect-branch resolution | `PS3_SPU_IB_FAST` (T191/T192) exists, opt-in, unit-tested, never raced. No count of indirect branches per job | not measured |
| Redundant register sync / reload after LS access | this is what `--fast-lower` removes (the per-access diagnostic gate forces reloads). Havok gains 4-11 %. Not available for the Wws reloc lifts in the vkgame lifter | VERIFIED for Havok replays |
| Helper calls on MFC channels | ~10 out-of-line `spu_wrch` / `spu_rdch` per DMA. spuopt has a channel-entry inlining tool (`spuopt/tools/channel_entry_inline.py`); never raced | not measured here |
| LS access | see register sync | |
| Dispatch lookups | Wws jobs enter through `spu_wws_job_enter` (identifier + body-hash check per job; 112 + ~40 + ~40 jobs/frame) | cost not measured (BLOCKED) |

No branch-handling generalisation is proposed. The only generalisation with correctness evidence, C-A, is already in the candidate.

## 4. C. Visibility (PVS) and vehicle physics

| Job | SPU work | Main wait | Where the delay comes from | Label |
|---|---|---|---|---|
| vehiclephysics (2 batches × 16-23 jobs, ~0.21 ms each) | 5.7 SPU-ms/frame | 3.3 ms/frame pre-Fix-2 (0x413784) | per blocking batch (pre-Fix-2 hops): submit 0.33 + exec 0.93 + completion 0.21 + wake 0.15 ms. About half is handler/wake latency. With Fix 2 on, Fix 1 (faster handler) did not reduce total JobBatch waits | hop split VERIFIED pre-Fix-2; Fix-2 split BLOCKED |
| PVS / pvsjob (112 jobs, ~0.1 ms each) | 10.7-10.9 SPU-ms/frame | 3.2 ms/frame pre-Fix-2 (Vis::Wait → 0x5F74B0) | the span (~3 ms) is lane throughput: 11 SPU-ms on 5 lanes → ≥ 2.2 ms even if perfectly packed. Computation, not hand-off, dominates. Per-job split (lifted compute / MFC / PM job load) unknown; no native exists | PARTIAL |
| occluders (4 waits) | small | 0.76 ms pre-Fix-2 | hop-dominated (exec 0.33 ms of a 0.9 ms wait) | VERIFIED pre-Fix-2 |
| groundrushsquash | 8.3-8.5 SPU-ms/frame | no wait site identified | competes for lanes | BLOCKED |

Whole-job latency, not isolated functions, decides. The PVS wait is bounded below by (PVS SPU-ms) / 5 lanes ≈ 2.2 ms. A PVS gain therefore needs the PVS jobs themselves to get faster: lifted compute, MFC, or PM per-job overhead. No offline whole-Wws-job replay harness exists (spu_rejoin60: BLOCKED). That is the largest tool gap.

## 5. Offline experiment done here: MFC lean path (see OFFLINE_RESULTS.md)

The `PS3_SPU_MFC_LEAN=1` switch in `ps3recomp-rt60` gives:
- −12 ns/DMA (1 thread, −13 %) and −15 ns/DMA (5 threads, −10 %);
- a bit-exact result on a differential test (5 seeds × 2 MFC modes, identical hashes of the 64 MB guest window, LS and all channel answers).

Modelled frame effect: HK2 ~5,000 DMA × 15 ns ≈ 0.075 ms/run, HK1 ~0.025 ms. Spread across all Wws jobs (~125k DMA/s) ≈ 2 ms/s of SPU-thread CPU. Critical path **≈ 0.1 ms/frame**. Below noise; not worth a race on its own.

## 6. What can and cannot go (don't assume all 12 ms can go)

- **Irreducible on this design** (guest semantics): the main thread waits for SPU work it has just kicked.
  - The SPU execution itself: PVS span ≥ ~2.2 ms; vehicle-physics exec ~0.9 ms × 2; Havok wave ≈ the longest run, ~1.8 ms stats-off for HK2 + ~1.2 ms for HK1, partly overlapped by PPU solver work.
  - The guest's `usleep(250)` wake quantum (~0.15 ms mean per blocking wait).
  - Taken together, roughly 6-8 ms/frame (MODELLED).
- **Recoverable exactly**:
  - (a) faster SPU jobs, compute or MFC: each 10 % on PVS/vehicle/Havok ≈ 0.4-0.6 ms;
  - (b) hand-off latency (handler poll, Fix 1), which did not show with Fix 2 on;
  - (c) whatever stats/instrumentation cost the tested arms paid (≈ 1-1.5 ms/frame of the Havok wait, MODELLED; not a production gain but a measurement correction).
- **Unknown**: the Present-spin share and the per-site JobBatch split. Test B measures both.

## 7. UPDATE after Test A / Test B (2026-11-19)

- Stats-off waits (Test A, VERIFIED): JobBatch 8.8-9.1 ms/frame, Havok 1.9-2.2 ms/frame. **SPU-related main-thread waits ≈ 11 ms/frame** plus the Present spin of ~1.5 ms (PARTIAL).
- Havok: the chained lowering lowers the Havok wait by 0.27 ms/frame (4/4 vs 4/4 separation) with **no frame change**. Further Havok work (`--fast-lower`, MFC lean) is deprioritised.
- Per-site JobBatch split and Havok waves: still **BLOCKED**, because Test B's trace window ended before race entry.
- SPU work in race (Kksr76): renderable 13.2, pvs 12.8, groundrushsquash 9.0, vehiclephysics 8.2 SPU-ms/frame. 0 interpreted steps in every module except spuconstraints (1.6 steps/job). Interpreter, rejoin and fallback paths are exhausted (VERIFIED).
- New evidence for a lowering candidate (VERIFIED by reading the lifts): the Wws relocatable lifts (`generated/spu_raw/wws_reloc_t81c/*/spu_recomp.c`, e.g. 2,465 `spu_ls_read128(ctx, ...)` in `ms_10aa3f4480ef`) use the generic LS accessors. Each carries the `SPU_LS_WATCH` gate (`spu_context.h:42-52`), a load plus a branch to an out-of-line call that the compiler must assume clobbers state. That is exactly what `--fast-lower` removes for Havok (+4-11 % whole-task on top of chain-chunks, bit-exact). `--fast-lower` and `--chain-chunks` do not exist for `--reloc` lifts in the vkgame lifter.

## 8. UPDATE: per-site releasers (Kksr77, Fix 2 on, stats and hooks off)

- SPU-related main waits: 7.65 (JobBatch) + 2.10 (Havok semaphore) = **9.75 ms/frame**, plus 0.43 of Havok polls. The Present spin is ~0.
- **Vehicle physics (2.91 ms/frame) is hand-off bound.** Two dependent batches of 16 jobs run back to back on all 5 lanes: 0.80 + 0.63 ms of execution. Around them: 0.29 ms before batch 1, **0.87 ms between the batches**, and 0.49 ms after batch 2 (780 waits). Every hop goes through the JobBatchHandler's `usleep(200)` poll, which lasts ~550 µs on the host timer.
- **The renderable wait (1.85 ms/frame) is lane contention.** Its first job starts 1.46 ms after the wait begins, while pvsjob occupies 2.76 and screenrush 0.82 of the 5 lanes. PVS speed or lane throughput matters here; hand-offs do not.
- **The Havok semaphore (2.10 ms/frame)** is ~12 short waits per frame (~120 µs each), mostly ended by Havok SPU events mid-task. No single long wave remains.
- **Occluders (generatefogtable), trailsupdate, groundrushsquash and occjob** are hop-dominated: kick + tail ≥ execution.
- Hand-off time summed over the JobBatch sites ≈ **2.2-2.4 ms/frame** (vehicle 1.6, occluders 0.4, others ~0.3). PARTIAL.

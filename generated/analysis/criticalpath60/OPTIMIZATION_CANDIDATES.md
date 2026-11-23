# OPTIMIZATION_CANDIDATES (Task 8 screening)

Private, offline. Nothing was implemented, raced or committed. "Saving" is per race frame on the main-thread critical path.
Kinds: **measured** (offline measurement), **modelled** (computed from traces), **hypothetical**. Labels VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## Table

| # | Candidate | Evidence | Critical-path saving | Confidence | Correctness risk | Validation |
|---|---|---|---|---|---|---|
| C1 | **JobBatchHandler poll fidelity.** Honour guest tid 12's `usleep(200)` (0x4AF6C8) as ~200 us instead of the host timer's ~540 us, e.g. extend the existing spin-tail mode to that thread or call site (today `PS3_USLEEP_SPIN_MAIN_ONLY=1` restricts it to tid 1) | handler 1,748-1,803 sleeps/s at 959-975 ms/s asleep (Kksr23/43 sc-wait, VERIFIED); every JobBatch completion is signalled by tid 12 (15,613/15,613, VERIFIED); exposed hop latency in instrumented intro frames: pre 0.89 + completion 0.78 = 1.67 ms/frame (`out/decomp_ksr36.txt`) | **modelled 1.0 ms** (1.67 x (1 - 0.22/0.56)) in instrumented frames; **1.9-3.0 ms extrapolated** to uninstrumented frames, where more batches block (JobBatch waits 10.3 vs 5.5 ms) | medium. The completion hop is VERIFIED; the submission hop is PARTIAL | low for semantics: usleep is never shorter than requested and the handler runs as on a PS3 (~0.22 ms/poll). Cost: about one more logical CPU spinning; SMT pressure on SPU lanes. Behaviour: any guest code that polls batch completion non-blockingly sees it sooner (PS3-faithful) | (1) unit test: usleep(200) on that thread lands in [200, 260] us and is never early; (2) offline: rerun `tools/decomp.py`/`batch_hops.py` on the next trace; (3) race A/B (NEXT_RACE_PLAN R2/R3) |
| C2 | **renderablejob interpreter fallback.** Find and remove the AOT misses: 47k interpreted SPU instructions per job | kind-27 steps vs duration, n = 3,799, R^2 0.82, 11.1 ns/step (VERIFIED correlation); only renderable has steps; module code unmodified at entry (64 snapshots, VERIFIED) | **modelled 0.9-1.3 ms mean** tail reduction in intro frames (median ~0); 17-20 SPU-ms/frame and ~0.3-0.6 host core freed. Driving frames, where the Present spin is 4.1 ms: BLOCKED | medium for the size of the cost, low for the mechanism (HYPOTHESIS: rejoin misses relocated entries, or interrupt resume lands mid-block) | low if the fix is a lifter/runtime lookup change validated bit-exactly; keep the SMC/microstep path | `PS3_SPU_AOT_PROF=5` in R1 names image/pc/reason; then the rj harness + FNREC 12E40 snapshots; mutation test as in spunat3 |
| C3 | **Turn route PT hooks off at race entry in measurement runs** (create the existing `PS3_TRACE_OFF_FILE` once `race_entry` is seen) | `ppu_trace_enter/ret` 1.11 ms/frame on the main thread (m2, VERIFIED); no `[PT] off` line in any Kksr race (VERIFIED); production sets no trace file | **measured cost 1.11 ms/frame** of main-thread CPU in every measurement (not a production gain) | high | none (harness only) | R1 records `[PT] off:`; compare main-thread runtime share |
| C4 | Havok HK2/HK1 in-race overhead (MFC emulation, lock-line, contention), not arithmetic | HK2 3.32 ms/run in race vs replay of a 0.46-volume recorded run 0.42-0.50 ms; MFC 18 %; 12-way host contention doubles replay time (measured) | hypothetical ≤0.8 ms (MFC ceiling) + unknown contention share; shortens the HK2 wave | low | medium (atomics/coherence) | needs per-boundary in-race timing (BLOCKED); striped lock-line idea from infamous2 (agent report) |
| C5 | PPU codegen (fast-mem frame + vmx-locals) on the covered functions | 1.45x race-weighted on 6.9 % of samples | modelled 0.65 ms; whole-program build raced once with no visible gain | low | low (gated, tested) | race A/B with ≥3 runs per arm; below noise for a single pair |
| C6 | vehiclephysics/renderable/Havok function natives (existing) | 1.6-2.7x on functions, ~1.05-1.13x whole Havok task (measured) | modelled ≤0.5 ms (vehiclephysics), ≤0.5 ms (Havok) | low | low (gates pass) | already gated; not worth a race on its own |
| C7 | Main-thread wake quantum (guest usleep(250)) | SetCondition -> wake 143-149 us mean per blocking wait | ~0.7-1.5 ms | n/a | **not exact**: needs usleep to return early | rejected |
| C8 | Reordering independent PPU work into waits | PPU_DEPENDENCIES.md | hypothetical ≤1 ms | very low | high | BLOCKED (needs dependency tracing) |

## Overlap between candidates (checked, not summed blindly)
- C1 acts on JobBatch waits in SIM and on the Vis wait. C2 acts on the EMIT/Present tail. They do not overlap in time, so savings add only if each wait stays blocking after the other change. Faster earlier phases push the main thread into the same later waits sooner, so C1 savings partly become a longer Present spin unless C2 shortens the renderable tail. **Combined modelled range: 1.5-4 ms/frame** (from ~29.5 ms to ~26-28 ms, ~34-38 fps). This is not a 60 fps path.
- C3 is a measurement correction and is excluded from game savings. It also makes C1/C5 effects easier to see.
- C4 and C6 overlap (both shorten Havok waves) and saturate at the HK2 wave length.

## Candidates above ~1.5 ms modelled
Only C1 in its uninstrumented extrapolation (1.9-3.0 ms), and C1+C2 together. Both depend on R1 to confirm their size in driving frames.

## Limits
- All main-thread timing models use the Kksr36 intro trace, whose main thread is slowed ~7 ms/frame by PT logging. Uninstrumented sizes are extrapolated from m2 aggregates.
- C2's cost per step is a regression slope, not a measurement of the interpreter on these jobs.
- No FPS claim is made. Every saving above needs a quiet-PC race A/B.

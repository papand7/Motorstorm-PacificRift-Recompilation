# SUMMARY: spu_rejoin60 (MotorStorm PR 1.00, Vulkan, offline, 2026-11-18)

Private. No race, commit, merge, push, or shared-tree edit was made.

**Reference repos (read-only):**
- `refs/infamous2-port` @ a97168801f59ccee04209772985148920d92b527
- `refs/ps3recomp-sp00nznet` @ de4f090328ea08bef6b2f15caec0b85e343a7ece

**Deliverables:** FIX2_ROOT_CAUSE.md, SPU_TRANSITION_PROFILE.md, NATIVE_SPU_INTERACTION.md, REJOIN_OPPORTUNITIES.md, OFFLINE_RESULTS.md, RACE_VALIDATION_PLAN.md. Tools are in `tools/`, outputs in `out/`.

## Answers

1. **Why Fix 2 improves FPS so much.** VERIFIED.
   - The 1.00 builds use a stale Wws lift (`generated/spu_raw/wws_reloc`). In it, renderablejob's jump-table `bi $r2` at LS 0xA650 is lifted as a function return. The framework fixed this in commit 58c45dfb, and the fixed lift `wws_reloc_t81c` exists, but the 1.00 build recipe still points at the old directory.
   - That fake return unwinds every host frame of the job. The drain's resume probe looks up the raw pc, never the relocatable key.
   - The returns into the lost frames (0xDFA0, among others) then miss. Before Fix 2, the interpreter's per-instruction rejoin probe had the same raw-pc blind spot, so it ran the rest of the job: 79k instructions/job, 22.7 SPU-ms/frame at the 0xDFA0 site alone in R1.
   - Fix 2 makes that probe relocation-aware. Renderable dropped from 1299-1361 to 536-572 us/job, and from 27-30 to 10-13 SPU-ms/frame. This is the job the Present spin waits for. Main-thread JobBatch and Havok waits per frame are unchanged, so the frame gain (~5.5 ms) sits outside them. Attributing it to the Present spin is PARTIAL: no sampler run has Fix 2 on.
2. **Which critical jobs benefit most.** Only renderablejob (VERIFIED). Every other Wws module, and all Havok tasks, had 0 interpreted instructions before and after.
3. **Are other expensive interpreter-fallback paths present?** No (VERIFIED for instruction counts, MODELLED for host time). After Fix 2 the whole transition overhead is <= ~0.6 SPU-ms/frame, spread over all lanes:
   - Wws PM interrupt shims: ~0.5 ms;
   - unwinds: ~238/frame, ~0.1 ms;
   - renderable: 30 interpreted instructions/job.
4. **Can it be extended safely?** Yes, with a small gain.
   - C-A, `PS3_SPU_DRAIN_RESUME_RELOC=1` in `ps3recomp-rj60`, default off, applies the same slot -> owner -> link-key mapping to the drain's resume probe. infamous2 does the same.
   - Result: 0 unwinds, 0 misses, 0 interpreted instructions; byte-identical at 4 bases (157/157 PASS; existing 91 + 48 PASS).
   - Synthetic cost: -0.23 us per unwind chain. Modelled race effect: ~0.05-0.1 SPU-ms/frame.
   - Candidate exe built: `build/motorstorm-vkgame-100-rj60`, 8b6d0d4a....
   - Build hygiene: point the 1.00 recipe at `wws_reloc_t81c` (C-L), which fixes the switch at its source.
5. **Are previous natives now more effective?**
   - groundrush, vehiclephysics, Havok: no (VERIFIED). Their jobs were never interpreted, so Fix 2 does not change their reach.
   - renderable natives 0x6870 / 0x8140: now reachable for the whole job. Their value is BLOCKED: there is no call count per job.
6. **Three strongest remaining opportunities.** None of them is a rejoin path.
   1. Havok HK2: 3.3 ms/run on-CPU in race vs 0.42-0.50 ms replayed; the main thread waits 3.5 ms/frame on the Havok semaphore. HYPOTHESIS >= 1.5 ms.
   2. JobBatchHandler hop latency (Fix 1): MODELLED 1-3 ms; race A/B inconclusive.
   3. pvsjob and vehiclephysics compute behind the Vis (3.2 ms) and vehicle-physics waits. PARTIAL.
7. **The next change most likely to save >= 1.5 ms/frame.**
   - Of the measured ones: the controlled Fix 1 A/B (RACE_VALIDATION_PLAN, arm F), because it is the only exact change with a modelled >= 1 ms.
   - The largest unexplained cost is HK2's in-race 6.5x. That needs a per-boundary in-race profile of one HK2 run before any change.
   - C-A is not a >= 1.5 ms candidate. It is exact cleanup, plus the instrumentation run that fills the missing Fix-2-on profile.
8. **Evidence still missing for a path to 60 FPS.** BLOCKED until races:
   - a Fix-2-on race with `PS3_SPU_AOT_PROF` and the main-thread sampler (Present spin share);
   - a driving-frame critical-path trace with Fix 2;
   - per-boundary timing inside in-race HK2/HK1 runs;
   - per-function call counts in renderable / pvs / groundrushsquash;
   - a whole-Wws-job replay harness (does not exist);
   - a repeated A/B of Fix 1.

   With Fix 2, a frame is ~25.3 ms. About 12 ms of it is waits on SPU work, and ~10 ms is main-thread compute. The evidenced exact candidates add up to ~1-3 ms, so neither 16.7 ms nor 13 ms is supported by current evidence.

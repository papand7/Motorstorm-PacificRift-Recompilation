# ROADMAP_TO_60FPS: ranked by real critical-path savings (2026-11-19)

Private. Labels VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED / MODELLED. No FPS improvement is claimed without race evidence.

## Where the frame is

| | ms/frame | Label |
|---|---:|---|
| Candidate race frame (3 valid runs, stats on) | 25.0-27.8 (36-40 fps) | VERIFIED |
| Target | 16.7 (60 fps) | |
| Gap | **8.3-11.1** | |
| JobBatch waits (SPU Wws jobs + hand-offs) | 8.6-10.0 | VERIFIED |
| Havok semaphore wait | 2.8-2.9 (stats-inflated; stats-off estimate ~1.5-2.5) | VERIFIED / MODELLED |
| Guest PPU compute | ~9.2 | PARTIAL (pre-Fix-2 sampler, same PPU lift) |
| Runtime under the guest | ~1.1 | PARTIAL |
| Present spin + GcKernel poll + fios | ~3-4.5 (remainder) | HYPOTHESIS |
| GPU time (overlapped), 1.5x scale + FSR + pack | ~14 (84 % of a 60 fps frame) | VERIFIED |

60 fps needs roughly −9 to −11 ms of main-thread frame interval. In MODELLED terms:
- The waits contain ~6-8 ms of SPU execution the guest genuinely waits for (PVS span ≥ 2.2 ms, vehicle exec ~1.9 ms, the Havok waves, the renderable tail).
- Only part of that comes back by making those jobs faster.
- The main thread's own ~10 ms of compute is untouched by any SPU work.

So 60 fps is **not reachable from SPU-side work alone**. It needs both:
- the SPU jobs on the chain made substantially faster;
- the PPU frame compute reduced.

The GPU then becomes a co-limiter at the current graphics settings.

## Ranked steps (by expected real critical-path saving, with what gates each)

1. **Test A: decide the current build (one authorization, 8 races).**
   - Expected: 0 to +0.6 ms. The Havok wait already fell 0.55 ms/frame under stats, but the frame did not move within noise.
   - Also gives the first stats-off wait budget, which corrects every earlier number by the ~1.2 ms/HK2-run harness cost.
   - Gate: ≥ 3 valid runs per arm, permutation p ≤ 0.05, and a difference above the noise floor.
2. **Test B: one profiling race on the faster build.**
   - No saving by itself. It decides ranks 3-6: the per-site JobBatch split, the Havok wave critical path, the Present spin, and lane occupancy.
   - Without it, nothing below is sized.
3. **PVS job speed** (largest SPU block behind a main-thread wait; 10.7 SPU-ms/frame; throughput-bound on 5 lanes):
   - modelled −0.2-0.3 ms per 10 % of PVS SPU time, ceiling ~1-1.5 ms;
   - prerequisite: a **whole-Wws-job record/replay harness**, the missing tool. Then lowering (`--fast-lower`-style for reloc lifts), MFC/PM per-job overhead, natives only with bit-exact gates. BLOCKED.
4. **Vehicle-physics and occluder batches**: exec plus hops, 2-4 blocking waits per frame. Size with Fix 2 unknown; ≤ 0.5-1 ms. Test F (Fix 1) answers the hop part directly.
5. **Present spin / renderable tail**: the renderable natives (0x6870 / 0x8140) are now reachable. The worth depends on the spin size from Test B; up to ~1-2 ms if the spin is still ~3 ms (HYPOTHESIS).
6. **Havok fast path bundle**: `--fast-lower` port + MFC lean. Both are exact and offline-validated; ≤ 0.2-0.3 ms/frame. Do it only if Test B puts the Havok wave on the binding chain.
7. **PPU frame compute** (~9-10 ms, the largest single block):
   - outside the SPU scope of this pass, but required for 60;
   - earlier PGO and whole-program attempts showed no race gain (criticalpath60 §2);
   - needs a fresh main-thread profile with Fix 2. Test B's sampler gives the top functions. Then function-level PPU work with transcript-exact gates (perfbench `ppu` suite).
8. **GPU budget**: at 60 fps the GPU frame (14 ms) leaves ~2.7 ms of headroom at 1.5x scale + FSR + pack. This is a graphics-settings question (identical in all A/Bs); no code change is proposed.

## Not on the roadmap (not exact)

The following are excluded:
- more SPU lanes than the guest's SPURS configuration;
- returning from guest `usleep` early;
- skipping or approximating Havok, visibility or vehicle physics;
- render pipelining;
- frame generation as an FPS claim.

## Immediate next authorized actions, in order

1. The user closes `bf1943.exe` and all builds.
2. The user fixes `build_all_100_next.cmd` (`wws_reloc` → `wws_reloc_t81c`); this is a shared tools file.
3. The user appends `'Kksr68'..'Kksr75'` to `run_vk.py` ORDER.
4. The user authorizes Test A, then runs BUILD_AB_PLAN §5 and evaluates it with `ab_compare.py`.
5. Then, separately: Test B (NEXT_PROFILE_PLAN), then Test F (Fix 1).

## UPDATE after Test A / Test B (2026-11-19)

- Test A: no detectable difference (39.96 vs 39.67 fps). Stats-off frame budget:
  - 25.0 ms/frame;
  - JobBatch waits 8.8-9.1;
  - Havok 1.9-2.2;
  - Present spin ~1.5;
  - the rest ~12.5 (guest compute + runtime + harness PT hooks ≤ 1.1).
- 60 fps still needs −8.3 ms. The re-ranked path:
  1. **Rerun Test B with a race-relative trace window** (NEXT_PROFILE_PLAN, Rerun section). This is still the gate for sizing the JobBatch waits.
  2. **Wws relocatable-lift fast lowering** (OPTIMIZATION_CANDIDATES "A"): build the lifter option and a whole-Wws-job replay harness offline. Modelled 0.3-0.8 ms.
  3. Fix 1 A/B (Test F): low prior.
  4. PPU frame compute (~11 ms incl. runtime): the sampler shows no hot function (top ≤ 2 %), so gains must come from broad codegen or runtime overhead (indirect calls, HLE dispatch, memory helpers). Size it with an m2-class sampler on the current runtime.
- Measurement hygiene for all later timing races:
  - stats off;
  - PT hooks really off (no `PS3_TRACE_FILE`, or a working off file);
  - quality gate.

## UPDATE after Kksr77 (Fix-2-on driving trace)

Frame 24.2 ms (41 fps):
- main compute ~13.0;
- JobBatch waits 7.65 (of which hand-offs 2.2-2.4, vehicle execution 1.4, renderable lane queueing 1.5);
- Havok semaphore 2.1;
- GPU reference poll 1.0;
- Havok polls 0.4.

Re-ranked path to 60 fps (need −7.5 ms):
1. **Test F: Fix 1** (handler poll fidelity). MODELLED ~0.8-1.2 ms. Exact; already in the exe.
2. **PVS and renderable lane throughput**: faster pvsjob/renderable compute. Ceiling ~0.5-1 ms. Needs a whole-Wws-job replay with DMA inputs (not available yet).
3. **PPU frame compute (~13 ms)**: the largest block and now the dominant one. A precise main-thread profile on the current runtime is needed: m2-class sampler, hooks off.
4. **GPU reference poll (1.0 ms)**: GPU pacing at 1.5x scale + FSR. Settings, not code.

Even 1+2 together (~2 ms) leave ~22 ms. 60 fps requires cutting PPU compute roughly in half. No exact evidence for that exists yet.

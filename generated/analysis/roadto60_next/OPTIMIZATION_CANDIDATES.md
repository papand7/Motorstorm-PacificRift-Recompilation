# OPTIMIZATION_CANDIDATES (Phase 5): ranked by modelled effect on frame completion

Private, offline. "Modelled frame saving" means the change in the main thread's frame interval, not SPU-ms. Isolated speedups are converted through the measured wait each job releases.
Labels: VERIFIED, PARTIAL, HYPOTHESIS, BLOCKED, MODELLED. No row is a race-proven FPS gain.

| # | Candidate | Evidence | Modelled frame saving | Correctness risk | Validation status |
|---|---|---|---|---|---|
| 1 | **Candidate build** 33253d9d (corrected Wws lift `wws_reloc_t81c` + Havok `--chain-chunks` + drain resume C-A), against 714690f6 | Race, stats on: Havok wait 2.84-2.94 vs 3.36-3.59 ms/frame on other Fix-2 exes. HK2 −0.45, HK1 −0.12 ms/run. JobBatch wait rose ~0.9 ms (median). Replays: chain 1.10-1.22x HK2, bit-exact 4/4. C-A 157/157 PASS. Corrected lift = an earlier validated lift (31/31) | 0-0.6 ms (the Havok wait drop may be absorbed by the next JobBatch wait). HYPOTHESIS | very low: validated lifts; C-A guest-exact by construction | **Ready for Test A**. Kksr60-67 gave 3 valid candidate runs and 0 valid baseline runs: no verdict |
| 2 | **Fix 1**: `PS3_USLEEP_SPIN_LR=4AF6D0` (JobBatchHandler `usleep(200)` honoured: 0.55 → 0.22 ms poll) | Race: polls 1,800 → 4,770/s (VERIFIED). Main JobBatch wait −2.0 ms/frame with Fix 2 **off**. With Fix 2 **on**: 9.17/8.41 vs 8.36/9.29, i.e. no change (n=2) | was 1-3 ms (criticalpath60); now **0-1 ms** with Fix 2. PARTIAL | low: never early; costs one logical CPU spinning | Test F plan (BUILD_AB_PLAN §9), after Test A |
| 3 | **PVS job speed** (112 jobs, 10.7 SPU-ms/frame; the Vis wait is ≥ PVS-SPU-ms / 5 lanes) | Throughput-bound span ~3 ms (pre-Fix-2). No native; lifted compute / MFC / PM per-job overhead split unknown | each −10 % of PVS SPU time ≈ −0.2-0.3 ms; the ceiling of the throughput part is ~1-1.5 ms if PVS ran 2x faster. MODELLED | depends on the method (lowering / MFC: exact; natives: need bit-exact replays) | **BLOCKED**: needs the Test B split and a whole-Wws-job replay harness (does not exist) |
| 4 | **Vehicle-physics / occluder hop + exec** | Pre-Fix-2: per blocking batch, hops 0.69 ms vs exec 0.93 ms. Fix 1 did not move the total with Fix 2 | ≤ 0.5-1 ms; split unknown with Fix 2. HYPOTHESIS | — | BLOCKED until Test B |
| 5 | **Havok `--fast-lower`** (lifter option only in ps3recomp-spuopt; port it to an isolated copy and lift the 4 Havok images with `--chain-chunks --fast-lower`) | HK2 replay 1.82-1.94 vs chain 1.93-2.15 ms (4 recordings, best of 40). HK1 1.06x over chain. 4/4 bit-exact (`havok_gap/out/verify_lowerings.txt`, `out/hk2_replay_phase4.txt`) | ~0.1 ms/run HK2 → **≤ 0.1-0.2 ms/frame**. MODELLED | low: same instructions. LS diagnostics (`SPU_LS_WATCH`, `SPU_SMC_WATCH`, `SPU_WWS_PROBE`) are blind inside groups | replay-verified; no exe built |
| 6 | **MFC lean path** `PS3_SPU_MFC_LEAN=1` (ps3recomp-rt60, this pass) | −12 ns/DMA (1 thread, −13 %) and −15 ns (5 threads, −10 %). Bit-exact differential 10/10 PASS (OFFLINE_RESULTS §4) | HK2 −0.06-0.075 ms/run, all Wws ~2 SPU-ms/s → **~0.1 ms/frame**. MODELLED | low: guest-affecting steps byte-identical; only diagnostics skipped; off when any DMA diagnostic env is set | implemented in the copy, opt-in, default off; no exe; no race |
| 7 | **Renderable natives** 0x6870 / 0x8140 (1.66-1.93x isolated) | Now reachable for the whole job (Fix 2). No per-job call counts | unknown; bounded by the Present-spin share (unmeasured after Fix 2) | bit-exact gates exist (spunat2/3) | BLOCKED: Present-spin size and call counts (Test B gives the spin) |
| 8 | **Wws PM per-job overhead** (`spu_wws_job_enter` identifier + body-hash check, PM interrupt shims ~0.5 SPU-ms/frame, DMA lists) | spu_rejoin60 R1 counts; no per-job timing | ≤ 0.2-0.5 ms (spread over lanes). HYPOTHESIS | medium for the shims (C-I), low for the cache | not started |
| 9 | Existing HK2 natives (hand5/gen5) | ≤ 1-2 % whole-task on their own lowering (VERIFIED) | ~0 | — | **dropped** |
| 10 | Recipe hygiene: `build_all_100_next.cmd` → `wws_reloc_t81c` | the recipe still says `wws_reloc`; the cache hides it (VERIFIED) | 0 (prevents a silent regression on a fresh configure) | none | do before any rebuild (shared tools folder; user edit) |
| 11 | Measurement: `PS3_SPU_TASK_STATS=0` in A/B runs | stats cost 1.17 ms per 5,000-DMA run (VERIFIED microbench) | not a game gain; removes ~1-1.5 ms/frame of harness cost from the tested arms (MODELLED) | none | built into the Test A plan |
| — | More SPU lanes, shorter guest `usleep` (main wake quantum), returning from usleep early, skipping or approximating Havok/visibility | | | **not exact** (changes SPURS SPU count or guest timing semantics) | rejected |

## Strongest exact candidate

**#1, the candidate build.** It is the only change with evidence on its critical path (Havok wait −0.55 ms/frame). It is ready for a controlled A/B.

**No single exact candidate with ≥ 1.5 ms of modelled frame saving is evidenced today.**
- Fix 1's earlier 1-3 ms model is contradicted by the Fix-2-on race data (PARTIAL).
- The two offline-validated exact changes (#5, #6) together model at ~0.2-0.3 ms.
- The plausible ≥ 1.5 ms items (#3 PVS speed, #4 vehicle hops, the unmeasured Present spin) need Test B before any implementation.

## For the strongest offline-validated change (#6): the full record

- **Bottleneck**: every SPU DMA passes ~20 env-gated diagnostic blocks and an unconditional POISON-DMA payload scan in `mfc_do_transfer` (`ps3recomp-vkgame/runtime/spu/spu_dma.h:201-834`). HK2 issues ~5,000 DMA per run.
- **Code path**: `spu_wrch(MFC_Cmd)` → `mfc_channel_write` → `mfc_submit` → `mfc_do_transfer`.
- **Experiment**: `ps3recomp-rt60/runtime/spu/spu_dma.h` (`mfc_lean_on`, `mfc_do_transfer_lean`), opt-in `PS3_SPU_MFC_LEAN=1`. The existing path is the fallback, and the default.
- **Tests**: `generated/analysis/roadto60_next/tools/mfc_lean_bench.c diff` (bit-exact, 5 seeds × 2 MFC modes) and `bench` (1 and 5 threads).
- **Critical-path effect**: ~0.1 ms/frame (MODELLED). Not worth a race on its own. Bundle it with #5 for a "Havok fast path" arm only if Test B shows the Havok wave on the chain.
- **Regression risks**:
  - POISON-DMA and the full `[sync-PUT]` row bytes are no longer printed when the switch is on;
  - a future diagnostic variable added to `mfc_do_transfer` but not to the `mfc_lean_on` exclusion list would be silently skipped under the switch.

## UPDATE after Test A / Test B (2026-11-19): re-ranking

| # | Candidate | New evidence | Modelled frame saving | Status |
|---|---|---|---|---|
| 1 | Candidate build 33253d9d | Test A: −0.29 fps (p = 0.70, floor 2.35). Havok wait −0.27 ms/frame, frame unchanged | 0 (measured) | **done: no detectable difference.** Keep it as the base (correct lift, 0 interpreter residue) |
| A | **Wws relocatable-lift fast lowering** (`--fast-lower` semantics for `--reloc` lifts of pvsjob, vehiclephysics, groundrushsquash, renderable: restrict LS pointer, no per-access `SPU_LS_WATCH` gate, pure float fix-ups) | Wws jobs = ~50-57 SPU-ms/frame. The lifts use gated LS accessors (VERIFIED). The same transformation gave +4-11 % whole-task on Havok, bit-exact on 4/4 recordings. pvsjob is throughput-bound behind Vis::Wait. vehiclephysics sits behind 2 blocking waits | if Wws jobs speed up 5-10 %: ~2.5-5 SPU-ms/frame; critical path **~0.3-0.8 ms**. MODELLED | **strongest next exact candidate.** Needs: the lifter option in an isolated copy, a whole-Wws-job replay/diff harness (missing), then a race arm |
| 2 | Fix 1 | unchanged (no effect with Fix 2 on, n=2) | 0-1 ms | Test F still pending |
| 3/4 | PVS / vehicle hops split | unchanged | | still BLOCKED (Test B rerun) |
| 5/6 | Havok fast-lower / MFC lean | the Havok wait no longer binds (1 above) | ≤ 0.1 ms each | **deprioritised** |
| 7 | Renderable natives | renderable job time 539 µs/job. The Present spin is now ~1.5 ms | ≤ ~0.5 ms | low priority |
| 11 | Harness: PT route hooks active in Test A/B | `[PT] config ... hooks=1` in all of Kksr68-76; no off file | not a game gain; removes ≤ 1.1 ms from measurement | make the trace-off effective (write `trace_off_<tag>`) or drop `PS3_TRACE_FILE` for timing races |

**Strongest next exact candidate: A (Wws relocatable-lift fast lowering).** It acts on the SPU work that stands behind the largest main-thread wait (JobBatch, ~9 ms/frame). Its mechanism is verified exact on Havok. It is still below the 1.5 ms preference when modelled.
**No ≥ 1.5 ms exact candidate is evidenced.** The per-site split from a corrected Test B is still the gating measurement.

## UPDATE after Kksr77 (Fix-2-on driving trace): strongest exact change

**Fix 1, `PS3_USLEEP_SPIN_LR=4AF6D0`** (exists in the candidate exe, default off). It honours the JobBatchHandler's guest `usleep(200)`: never early, a ~218 µs poll instead of ~550 µs.

| | |
|---|---|
| Evidence | Kksr77: 2.2-2.4 ms/frame of hand-off latency on JobBatch waits. Vehicle physics alone: 0.29 kick + 0.87 gap between batches + 0.49 tail per frame, all gated by the handler poll. Race mechanism VERIFIED (polls 1,800 → 4,770/s, Kksr49/53) |
| Modelled saving | each handler hop's wait scales by ~0.4 (218 vs 545 µs), ~0.16 ms saved per hop; ~4 hops/frame on vehicle + 2 on occluders + small sites → **~0.8-1.2 ms/frame** (MODELLED) |
| Correctness risk | low: exact semantics (usleep never returns early); one more logical CPU spinning |
| Validation | Earlier Fix-2-on A/B (Kksr50/54 vs 51/55, n=2, stats on) showed no change. That is within the ±1-1.3 ms run noise, so it neither confirms nor rules out ~1 ms. **Test F (BUILD_AB_PLAN §9, 8 runs ABBA, stats off, hooks off) is the deciding measurement** |

Next after it:
- **PVS job speed**: it releases lanes for the renderable wait (1.85 ms/frame, 1.46 ms of it queueing). Ceiling ~0.5-1 ms; no exact method validated yet. The Wws fast lowering showed no gain.
- **Havok**: 12 short semaphore waits, ~2.1 ms/frame. The chained lowering already cut 0.27 ms; little is left per wave.

No other exact candidate models ≥ 1.5 ms.

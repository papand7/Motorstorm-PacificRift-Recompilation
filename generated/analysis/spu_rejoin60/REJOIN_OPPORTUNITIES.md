# REJOIN_OPPORTUNITIES (Tasks 3, 5, 6)

Private, offline. In the table:
- **Measured** means race logs or an offline run.
- **Modelled** means arithmetic on measured counts and costs.
- **Hypothetical** means no evidence yet.

## 1. Candidates

| # | Candidate | Evidence | Expected saving | Correctness risk | Offline validation | Status |
|---|---|---|---|---|---|---|
| C-A | **Relocation-aware drain resume** (`PS3_SPU_DRAIN_RESUME_RELOC=1`, `spu_drain.c` + `spu_reloc_slot_probe` in `spu_channels.c`, ps3recomp-rj60). A callee that host-returns on a lifted entry inside a resident relocatable slot resumes in the drain instead of unwinding (`spu_restart_dispatch`). It is the same lookup `spu_indirect_branch` would do; infamous2 does the same, slot-first (`engine/runtime/spu/spu_drain.c:693-718` @ a97168801f59) | R1: 238 restarts/frame, all at relocatable-slot entries (job-exit `entry+0xAC` in 8 modules; renderable switch cases). The relevant misses follow from them (FIX2_ROOT_CAUSE §1) | measured on the synthetic module: −1.6 µs/job for 7 unwinds, ~0.23 µs per unwind chain; renderable interpreted steps 30 → 0 (MODELLED from the synthetic). Modelled race: **~0.05–0.1 SPU-ms/frame**, critical path ≤ ~0.05 ms | Low: guest-exact by construction. Guest state lives in ctx and relocatable lifts keep no host-local guest state (`--reloc` cannot be combined with `--chain-chunks`). Resuming vs unwinding changes only which host frame runs the same guest instructions. This is the policy already used for non-relocatable images (`spu_drain.c` comment above `spu_drain_call`). Host depth stays bounded: a frame is popped when its return pc is reached, and the job ends at the PM's return | `tests/test_spu_drain_resume_reloc.py`: 157 PASS / 0 FAIL. 4 bases × 4 switch combinations; byte-identical to the interpreter; resume on → 0 restarts, 0 misses, 0 interpreted. Modules A/B unaffected. Existing suites 91 + 48 PASS | **Implemented, default off; exe built (8b6d0d4a…); race not run** |
| C-L | **Use the re-lifted Wws AOT dir** `generated/spu_raw/wws_reloc_t81c` (lifter fix `58c45dfb`) instead of the stale `wws_reloc` in the 1.00 build recipe | `diff -rq`: one line differs (renderablejob 0xA650 `SPU_RET_REG` → dispatch); same sig and body hash. Used by T106–T161 | removes the renderable switch unwinds at the source (13.8/frame) plus their misses and ~30 steps/job. Does **not** remove the job-exit unwinds, which C-A also covers. MODELLED ≤ 0.05 SPU-ms/frame | Very low: an earlier validated lift (T82B run-validated; 31/31 `verify_wws_reloc` PASS against this EBOOT, t106). It is a build input, not env-switchable | the diff; C-A's synthetic test covers the same semantics at runtime | **Recommended hygiene**: build-recipe change only. Not built here |
| C-I | PM interrupt shim misses: 0x3FEC0 save/restore (922/frame, 349 ns) and 0xA2C vector (461/frame, 401 ns, 2 steps), plus iret unwinds 225/frame | R1 measured | ≤ 0.5 SPU-ms/frame if the shim ran lifted. MODELLED; spread over lanes | Medium. The shim is runtime-generated code at the top of LS: lifting it needs a verified per-PM stub signature, or a faithful `--const-bi`-style lift (infamous2 option). The register-preservation contract must stay exact (`spu_drain.c:238-314`) | needs an interrupt-heavy synthetic job; existing irq tests | Hypothetical gain, not implemented |
| C-F | `PS3_SPU_IB_FAST=1` (T191/T192, existing, opt-in, tested): an indirect-branch cache that also covers relocatable slots | its unit tests PASS (t192 logs) | unknown: no race result found, and no count of indirect branches per job | low (tested coherence contract) | existing | not measured in a race: worth one A/B arm, but no evidence of ≥ 1.5 ms |
| C-D | Interpreter decode/dispatch speed (per-step rejoin hash probe, `spu_interp.c:433`) | 30 interpreted steps/job after Fix 2 | ~0 | – | – | **dropped**: nothing left to speed up |
| C-G | Generalising Fix 2 to other dispatch probes: `spu_dispatch` (`spu_interp.c:536-547`) and the microstep | `spu_dispatch` is only used by a self-test (cp60). It calls a probe hit without setting `reloc_delta`, which is a latent hazard with Fix 2 on | 0 in game | would be a latent bug if `spu_dispatch` were ever used | – | not needed. Noted as a hazard: fix it before `spu_dispatch` gets any caller |

## 2. Other relocation and dispatch targets examined (Task 3)

- **Indirect branches and function-pointer dispatch:** `spu_indirect_branch` already resolves relocatable slots, with link key and `reloc_delta` (`spu_channels.c:3796-3810`). The T191 cache covers it as an option.
- **LS branch tables:** the only mis-lifted table is renderable 0xA654 (C-L). It is the only `SPU_RET_REG` in all 31 modules (scan of `wws_reloc/*/spu_recomp.c`).
- **Overlays:** non-relocatable overlay slots are unchanged by C-A (the probe returns 0 for them).
- **Job entry/exit:** the job-exit unwind (`ila $r0,entry+0xAC; a $r0,$r0,$r126; br body` … `bi $r0`) happens once per job in 8 modules (C-A). `lift_jobmods.manual_link_targets` seeds `entry+0xAC` as an entry precisely so that this return can resume. Its own docstring describes the restart it was meant to avoid, but the resume probe never looked in the relocatable slot.
- **Unresolved targets:** none in R1.

**Can Fix 2 be generalised safely?**
- Yes, to the drain resume probe (C-A). It is the same proven mapping (slot → owner → link key), and it only acts where the dispatcher would dispatch.
- Nothing else uses a raw-pc probe inside relocatable slots on a game path.
- No relocation handling was generalised beyond `owner > 0 && link_base != 0` slots.

## 3. Critical path with Fix 2 (Task 5): which SPU work now controls the main thread

- **Fix 2 on, per frame (VERIFIED from `[sc-wait]`, Kksr50/54, 25.3/26.3 ms):**
  - JobBatch waits (main-thread usleep spin) 8.4/9.3 ms;
  - Havok semaphore 3.6/3.5 ms;
  - the rest, ~13–14 ms, is main-thread compute (~9.2 guest + ~1.1 runtime, from criticalpath60) plus whatever remains of the Present spin (not measured with Fix 2).
- **SPU work per frame, Fix 2 on (VERIFIED, `out/wws_window_ksr48_54.txt`, `out/ab_metrics_ksr47_59.txt`):**
  - Havok HK2 3.35–3.6 ms/run × ~4.7 runs per frame (~16 SPU-ms/frame), on-CPU 98.7 % of its run time, MFC 18.7 %;
  - HK1 1.65–1.74 ms × 4.7;
  - renderable 10–12.6 SPU-ms/frame;
  - pvs 10.7–10.9;
  - groundrushsquash 8.3–8.5;
  - vehiclephysics 5.7.
- **Jobs that release main-thread waits, by evidence:**
  1. Havok HK2/HK1 waves → semaphore 0xA4C590 (3.5 ms/frame wait).
  2. vehiclephysics batches → JobBatch 0x413784 (3.3 ms before Fix 2; criticalpath60). About half of that is handler and wake hops (Fix 1).
  3. pvsjob → Vis::Wait (3.2 ms).
  4. renderable → Present spin (reduced by Fix 2, size now unmeasured).
  5. groundrushsquash: no wait site identified (BLOCKED).

None of the rejoin candidates acts on items 1–3. C-A/C-L act on item 4 by ≤ 0.1 ms. **Isolated CPU savings ≠ critical-path savings:** C-A's ~0.1 SPU-ms/frame is spread across lanes, and the critical-path share is smaller still.

## 4. Three strongest remaining opportunities (ranked by evidence for ≥ 1.5 ms, not by ease)

1. **Havok HK2's in-race cost: 3.3 ms/run on-CPU vs 0.42–0.50 ms replayed.** The main thread waits 3.5 ms/frame on the Havok semaphore.
   - Measured split: MFC 0.61 ms/run, 3194 GET / 441 GETLLAR / 172 PUTLLC per run; contention 2.0x under 12 parallel replays.
   - The remainder (~1.5 ms/run) is unexplained.
   - Needed next: a per-boundary in-race profile of one HK2 run (time between channel ops), or a whole-task replay under race-like contention.
   - Potential: > 1.5 ms if the wave shortens. HYPOTHESIS.
2. **JobBatchHandler hop latency (Fix 1, `PS3_USLEEP_SPIN_LR=4AF6D0`).**
   - MODELLED 1.0–3.0 ms.
   - Race: control 32.6/31.0 vs Fix 1 33.1/37.3; Fix 2 39.5/38.0 vs both 38.0/40.0. Inconclusive at 2 runs per arm.
   - It needs the controlled repeated A/B in RACE_VALIDATION_PLAN.
3. **pvsjob / vehiclephysics compute on the Vis and vehicle-physics waits** (10.7 and 5.7 SPU-ms/frame, waits 3.2 and ~1.6 ms of exec).
   - Natives for these exist only for vehiclephysics, and are small.
   - The PVS jobs have no native.
   - Critical-path share is PARTIAL; a driving-frame trace with Fix 2 is needed.

**None of the three is a rejoin or interpreter path.** That class of overhead is exhausted after Fix 2 (SPU_TRANSITION_PROFILE §3).

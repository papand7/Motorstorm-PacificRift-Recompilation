# T189: next architecture steps and the proposed in-game experiment

## 1. Proposed next controlled in-game experiment (needs authorization; not run)

**Question:** do inline guest stores (arm B) reduce MotorStorm's frame time, and does promotion on top (D) add anything in game?

| Item | Plan |
|---|---|
| Builds | Two exes from the T189 tree, T183 recipe (about 11 min each, `build_t183.cmd` pattern), port `port-t161`.<br>**Exe-B:** the existing lift's TUs compiled with `-DPPU_INLINE_STORES` (root port option `MSPR_PPU_INLINE_STORES=ON` from T152 root `20c3123`, or a compile definition in the T189 build script). No relift.<br>**Exe-D:** the same plus the lift rewritten by `ppu_regpromo.py <tu> <out> --inline-stores` (stand-alone pass, about 25 min, ESTIMATE). |
| Arms | **P:** T184 arm P env on Exe-B **without** `PS3_VM_STORE_INLINE`. This is the store-gate negative control: stores still out of line, plus the one-byte gate.<br>**B:** the same exe with `PS3_VM_STORE_INLINE=1`.<br>**D:** Exe-D with `PS3_VM_STORE_INLINE=1` (optional, lower priority). |
| Order | P, B, P, B (4 launches), then D, D if B shows a gain |
| Reference | P on Exe-B should match T184 arm P (68.51 ms) within noise, apart from the gate cost |
| Metrics | Frame time (mean, median, p95) from `[rsx-frame-perf]`. Post-Havok PPU time and frame-thread on-CPU time from the `[PT]` join (T183 `frame_join_t183.py`). The `[vm-gates]` banner (pages inline). The count of out-of-line stores, if `PS3_VM_STATS`-style counters exist; otherwise not measured |
| Accept | Frame time down by more than the P-to-P spread, race reached, identical progress and frame content (draw-gated capture), no new `[spu-coh]`/reservation anomalies |
| Expected | **Unverified.** Offline: 1.48× on the real store-heavy function, about 1.0× on short call-dense real functions. Post-Havok PPU is about 23 ms of the 68 ms frame (T186). Even a large PPU gain does not reach 33.3 ms alone, because Havok SPU (25 ms) and Wws (20 ms) stay |
| Independence | Do not combine with T187's `PS3_SPU_MFC_FAST` in the same arms. That A/B is separate and pending |

## 2. Compiler work, in priority order

| # | Change | Why | Validation |
|---|---|---|---|
| P1 | **Port option + default policy for inline stores**: make `MSPR_PPU_INLINE_STORES` part of the current port build and document `PS3_VM_STORE_INLINE` | The validated gain needs no relift; the remaining work is build plumbing | `test_vm_page_gates`, the four-arm bench, then the in-game A/B above |
| P2 | **Promotion profitability gates** in `ppu_regpromo.py`:<br>(a) promote only functions or regions whose loops contain no context-mode statements;<br>(b) cap promoted GPRs at the host's callee-saved count, choosing the most-used ones;<br>(c) loop-scoped promotion: load at the loop entry, write back at the loop exits | Real code lost the gain to spills and prologue saves (`REGISTER_PROMOTION_COMPARISON.md`) | The same difftest (12 seeds × variants, mutants) and the four-arm real-runtime bench; accept only if real-function D/B rises above 1.0 |
| P3 | **Real-runtime benchmark in the public framework**: link `ppu_loader.cpp` in `ppu_difftest` builds (as `bl4.cmd` does privately) | The fixture's cheap writer misled D/B | Transcript equality, as now |
| P4 | **Drain/TLS cost**: one `g_trampoline_fn` TLS address per function, not per `DRAIN_TRAMPOLINE` (5,984 `__dyn_tls_on_demand_init` sites in one TU) | A per-call fixed cost in all titles | Lifter conformance plus difftest |
| P5 | **`fmadd` without the CRT `fma()` call** (an FMA3 path behind a CPU check) | T152: 126 calls in one FP kernel | `test_ppu_lift` FP cases plus difftest FP edge values |

## 3. SPU (`SPU_CODEGEN_AUDIT.md`)

S1 (a correct cached fast dispatch inside `spu_indirect_branch`, with an eligibility word and generation invalidation) is the next SPU task. Before it:
- an SPU hop-transcript test;
- then S2 (SPU promotion profile) on an SPU difftest;
- then S3 (exact float fast path) with an exhaustive edge-case table.

## 4. Runtime (`RUNTIME_SYNCHRONIZATION.md`)

- Wait for T187's A/B.
- Then the reservation park for same-line spinners, as an opt-in switch with an LR-event torture test.

## 5. Targets

- **30 fps (33.3 ms)** stays the practical target. Today: about 68 ms (T184 arm P).
- No FPS change is claimed from T189: every speedup here is offline.
- Reaching 33.3 ms needs all three frame segments to shrink:
  - post-Havok PPU (inline stores, P2, P4);
  - Havok SPU (S1–S3, the reservation park);
  - Wws (S1–S3).

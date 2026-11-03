# T187: next phase plan

Order is by expected value over cost. Each step keeps the flag opt-in, and each must pass
`tools/test_ppu_promote.py` (≥3 fuzz seeds, plain and traced, plus `--mutant` failing) before benchmarking.

| # | Step | Why (evidence) | Gate |
|---:|---|---|---|
| 1 | **Shared cold spill per function.** Trace hooks jump to one out-of-line spill-all block instead of one inline block per label | 69 % of the static growth (`PERFORMANCE_RESULTS.md` §3) | fuzz verify plus traced verify; `.text` on chunk 006 |
| 2 | **Reload liveness.** After a sync, reload only registers that are live-in (backward liveness on the same CFG) | 17 % of the growth; it also helps call-dense code (k_calls, k_icall) | same, plus k_icall ≥ 1.0× |
| 3 | **Pressure-aware selection** instead of a fixed cap: loop-weighted reference counts, a limit of about 8 for locals live across helper calls, unlimited for call-free regions | k_regs 0.89× uncapped vs k_cr 1.47× at cap 8 | no kernel below 0.98× |
| 4 | **CTR (then XER.CA) as locals** | `bdnz` stores CTR on every iteration (k_arith disassembly) | the same differential, with CTR included in the hash (already hashed) |
| 5 | **One authorized MotorStorm A/B:** relift with `--promote-regs` (plus steps 1–3), arms base vs promo, `[rsx-frame-perf]` frame time and the `[PT]` post-Havok phase (T183 join tool) | the first in-game evidence. **Requires explicit launch authorization.** About 11 min per isolated build (`build_tNNN.cmd` recipe) | frame time with variance over ≥3 runs per arm |
| 6 | **SPU port of the contract** (`spu_lifter.py`, locals within dispatch groups, sync at channel ops) | T186 item 4 | **coordinate with the SPU sync owner first**; not before their MFC change lands |

**Recommended immediate action:** steps 1 and 2. Both are generic, offline and low-risk, and they can be
validated with the existing harness.

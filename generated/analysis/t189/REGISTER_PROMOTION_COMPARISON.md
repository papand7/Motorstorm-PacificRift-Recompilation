# T189: four-arm PPU comparison. Do inline stores make register promotion effective?

| Arm | Inline stores | Register promotion |
|---|---|---|
| A, baseline | off | off |
| B, stores | `-DPPU_INLINE_STORES` + `PS3_VM_STORE_INLINE=1` | off |
| C, promotion | off | `--promote-regs --promote-store-sync` (T188's best out-of-line policy) |
| C2 | off | `--promote-regs` (default drop-clean policy) |
| D, combined | on | `--promote-regs --promote-inline-stores` |

All arms are built from one lifted source with the game's lifted-TU compiler flags, and every arm's transcript is checked identical before timing (`CORRECTNESS_RESULTS.md`). Median of interleaved processes. Every comparison is within one run.

## Answer

| Workload | Promotion alone (C/A) | Promotion on top of inline stores (D/B) | Verdict |
|---|---:|---:|---|
| Synthetic loop kernels (fixture runtime) | 1.00–2.49× | **1.08–3.32×** | inline stores unlock promotion: struct 1.00× → 2.07×, transform 1.01× → 1.53×, fpdot 1.10× → 2.16× |
| Real store-heavy function `func_0096B648`, **real T189 runtime** | 1.02× | 1.02× | the gain is the inline stores (B/A 1.48×); promotion adds about nothing |
| Real function `func_002D0D94`, real runtime | 1.04× | 0.96× (cv 10.5 %) | no measurable promotion gain |
| 13 robust of 17 timed real TU `000` functions (short paths, fixture runtime) | 0.99× geomean | 0.98× | neutral. B/A is 0.97× here (the fixture's cheap writer, below) |
| 17 robust of 21 timed real TU `003` functions (short paths, fixture runtime) | 0.99× | 1.03× | neutral. B/A is 0.95× here (cheap writer) |

**Conclusion (VERIFIED offline):**
- Out-of-line store calls are a barrier to promotion. Removing them lets promotion keep loop state in host registers, a large effect in loop kernels.
- In the real lifted game functions measured against the real runtime, the barrier was not the only limit. Their hot paths gain from inline stores themselves (1.48×). Promotion on top gives 0.96–1.02×.
- The effects are **not additive**:
  - kernels: D/A exceeds B/A × C/A in some cases (struct: 1.07 × 1.00 vs 2.22);
  - real code: D/A ≈ B/A.

**Recommendation:** ship **inline stores (B)** as the first in-game candidate. Keep promotion opt-in for loop-dominated titles until an in-game A/B (B vs D) shows a gain.

## Why the fixture and the real runtime disagree on D/B (VERIFIED)

The fixture's out-of-line `vm_write*` is a bare `bswap` + `memcpy`. The real runtime's is about 30 instructions (T186: a 5-global gate, the SPU reservation-bitmap test, a `/GS` cookie), plus the call.
- **Fixture:** arm A's stores are cheap, so B gains little, and D's gain is mostly promotion: loop state stays in registers once no call clobbers it.
- **Real runtime:** B already removes the expensive part, and what promotion would save is a smaller share of the remainder.

Both runtimes give identical guest results. The real-runtime numbers are the ones to trust for store cost.

## Spills and instruction counts (static, VERIFIED)

T152's three real functions (llvm-objdump; x64, ctx-field operands, stack operands, prologue pushes):

| Arm | x64 | ctx operands | stack operands | pushes | object bytes |
|---|---:|---:|---:|---:|---:|
| A | 18,669 | 2,583 | 47 | 19 | 119,310 |
| B | 19,480 | 2,567 | 41 | 21 | 115,544 |
| C | 21,201 | 2,686 | 1,718 | 24 | 133,094 |
| C2 | 21,989 | 1,188 | 3,963 | 24 | 136,893 |
| D | 22,743 | 1,227 | 3,805 | 24 | 133,681 |

- Promotion trades `ctx` operands for stack spills. In D, ctx operands drop 2.1× but stack operands rise 80×.
- In the real functions those spills sit in the hot loops often enough to cancel the gain. In the kernels they do not.
- Inline stores alone change neither count much.

**What would make promotion pay on real code (next):**
- **Register pressure:** the pass loads every live guest register into a local, and real functions use 20–30 GPRs. Remedies:
  - promote only the registers used in the hottest region (a loop-scoped promotion that writes back at the loop exit);
  - or cap the number of promoted GPRs per function at the host's callee-saved count.
- **Call-dense real code:** keep promotion off in functions whose loops contain calls (a static profitability gate).

Both are pass-level heuristics with no semantic risk; the same difftest validates them. See `NEXT_ARCHITECTURE_STEPS.md`.

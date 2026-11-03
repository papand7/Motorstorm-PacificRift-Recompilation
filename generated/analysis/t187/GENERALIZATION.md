# T187: generalization (Phase D)

## Why the pass is not MotorStorm-specific (VERIFIED by construction)

- It reads no addresses, symbols, NIDs or game tables. Its only input is the lifter's text grammar.
- Refusals are syntactic, and they fall back per function to the unchanged lowering.
- The sync points are defined by the ABI between lifted code and the runtime (`ctx` passed, `return`,
  trampoline), not by the ABI of a guest program. The pass makes no assumption about callee-saved registers.

## Non-MotorStorm workloads used

| Workload | Origin | Size | Result |
|---|---|---|---|
| 12 synthetic kernels | `tests/promote/kernels.s` (hand-written, public) | 18 functions, 448 insns | verified, benchmarked |
| Random programs, seeds 1–4 | the fuzzer in `test_ppu_promote.py` | 4 × 658 functions, about 19k insns each | verified, plain and traced |
| PPU conformance suite | `tools/test_ppu_lift.py` (default path only) | 1,533 checks | unchanged |

**BLOCKED:** no second real PS3 title or homebrew ELF is available locally. Real-world generality beyond
MotorStorm's static coverage (chunk 006: 291/291 functions with registers promoted, 0 refused for safety) is
not measured.

**Suggested next inputs** (public, license-clean):
- PSL1GHT samples built with a PPU toolchain. None is installed here, which is why `ppc_asm.py` exists.
- The ps3recomp project template's test ELFs, if any ship with a PPU build.

## Fallbacks

| Case | Behaviour |
|---|---|
| Any refusal rule hit | the function is emitted exactly as lifted; the stats line counts the reason |
| `--promote-regs` absent | the whole output is byte-identical to the pre-T187 lifter |
| Register pressure high | `--promote-max-regs N` promotes only the N most-referenced registers |
| Need to inspect | `py -3 tools/ppu_promote.py in.cpp out.cpp` on any generated chunk; header comment per function |

## Limitations

1. **Every call does a full sync and a reload of all registers.** Call-dense code gains little, and indirect
   dispatch loses about 3 % (synthetic).
2. **Register pressure beyond the callee-saved x64 set** costs time (k_regs 0.89×). The static cap helps but
   costs CR-heavy code. A pressure-aware selection is needed.
3. **Code size:** +35 % `.text` uncapped, +8.5 % at cap 8, on a MotorStorm chunk. Mostly cold trace-spill blocks.
4. **Diagnostics:** store-watch dumps (`g_active_ctx` from inside memory helpers) can show stale GPRs between
   sync points. Traces stay exact.
5. **Not covered:** LR, CTR, XER, FPRs, VRs, and SPU code.
6. **No exception path:** if a runtime helper ever unwinds through lifted code, `ctx` would be stale. No such
   path exists today (HYPOTHESIS; audit before default-on).
7. **No in-game measurement yet:** all performance numbers are synthetic or static.

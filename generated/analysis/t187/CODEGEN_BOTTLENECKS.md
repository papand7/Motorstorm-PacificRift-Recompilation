# T187: codegen bottlenecks (generic)

**Method.** Static x64 counts come from `llvm-objdump -d` over objects built with the game's flags
(`/O2 /Ob2 -std:c++20 -fno-strict-aliasing -fwrapv`, clang-cl 23.1.3). The MotorStorm sample is the existing
lifted code in `generated/ppu-t173-staging` (private; numbers only). No game was launched.

| # | Bottleneck | Evidence | Label |
|---:|---|---|---|
| 1 | **Guest GPRs/CR live in `ctx` memory.** `ctx` escapes and stores are opaque calls, so every register use is a load and every result a store | Chunk 006: 239,890 of 634,498 x64 instructions (38 %) have a memory operand. Base `k_regs` has 164 ctx-relative accesses in a 97-instruction guest function | VERIFIED |
| 2 | **CR kept in memory**, including fused compare+branch. Each `cmp` does read-modify-write on `ctx->cr` | `k_cr` (CR-heavy loop): promoting CR+GPRs alone gives 2.28× (0.34 → 0.15 ns per guest instruction) | VERIFIED (synthetic) |
| 3 | **Opaque memory helpers clobber the host's volatile registers.** Any local live across a guest load/store must sit in one of about 8 callee-saved x64 registers | Promoted `k_regs` (≈20 live): 186 `%rsp` stack accesses replace 164 ctx accesses, and it runs 0.89× | VERIFIED |
| 4 | **CTR in memory.** `bdnz` loads, decrements and stores `ctx->ctr` on each iteration | Disassembly of the promoted `k_arith` loop: everything is in registers except the CTR store | VERIFIED |
| 5 | **Per-label trace hooks.** Each `PPU_TR_BB` is a load and branch on `g_ppu_trace_mask`. With promotion, each also carries a spill block | Of the static growth on 13 hot MotorStorm functions: cold spill blocks 69 %, reloads after calls 17 %, sync spills ≈14 % | VERIFIED (static) |
| 6 | **Call-dense guest code.** Each call is a full sync: spill the dirty set, reload all | `k_icall` 0.94–0.97×, `k_calls` 1.11×. The hot MotorStorm functions are call-dense (Havok, Wws) | VERIFIED (synthetic); the game share is a HYPOTHESIS |
| 7 | **SPU: the same `ctx` pattern on `spu_context`**, plus dispatch through `SPU_IB` | T186 item 4 (`tools/spu_lifter.py:1177`, `spu_context.h`) | PARTIAL (T186; not re-measured) |

**Not bottlenecks for this work:**
- **Host FP exactness:** untouched. No native FP substitution was made.
- **Memory ordering:** fences and reservations are not promoted.

**Ranking for codegen work:**
- (1)+(2): done as a prototype.
- Then (5) shared cold spill and (6) reload liveness: both cheap.
- Then (3) pressure-aware selection.
- Then (4) CTR.
- Inlining the store fast path (T186 item 5) would shrink (3), since a local survives a non-call.

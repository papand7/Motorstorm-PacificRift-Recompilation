# T188 Phase A: ps3recomp code-generation architecture audit

Labels: VERIFIED (measured or read in code), PARTIAL, HYPOTHESIS, BLOCKED. Estimates are marked ESTIMATE and kept apart from measurements.
Tree: ps3recomp `766d3575` (T183 code), worktree `ps3recomp-t188`, branch `agent/t188-codegen-architecture`. MotorStorm lift used for validation: private `generated/ppu-t173-staging` (3.6 GB, 80 TUs). Host: the game build's compiler and flags (clang-cl 23.1.3, `/O2 /Ob2 -fno-strict-aliasing -fwrapv /EHsc -std:c++20`).

## 1. PPU pipeline, end to end (VERIFIED)

1. **Decode.** `tools/ppu_disasm.decode(word, addr)` gives mnemonic + operand text.
2. **Lift.** `PPULifter.lift_function` (`tools/ppu_lifter.py`) emits one C statement (text) per guest instruction via `_translate`. Every architected register is a field of `ppu_context`, so every statement reads and writes `ctx->gpr[n]`, `ctx->fpr[n]`, `ctx->cr`, `ctx->xer`, `ctx->lr`, `ctx->ctr`.
3. **Text post-passes.** Callee-save snapshots (`_cs_N`), `_fuse_cr`, the `--trace-hooks` hooks (`PPU_TR_BB` at every label, `PPU_TR_RET` after every call), and the fall-through trampoline.
4. **Chunking.** About 600 k lines per `.cpp`. Static helpers (`ppc_rlw64`, inline loads, ...) are in every chunk's prelude and the header.
5. **Host compile.** clang-cl with the flags above, linked with the runtime (`runtime/ppu/ppu_loader.cpp`: `vm_read*`/`vm_write*`, `ps3_indirect_call`, `ps3_hle_call`, `lv2_syscall`).
6. **Execution.**
   - A direct call is `ctx->lr = ret; func_X(ctx); DRAIN_TRAMPOLINE(ctx);`.
   - A tail call or fall-through sets the TLS `g_trampoline_fn` and returns.
   - `bctr`/`bctrl` go through `ps3_indirect_call(ctx)`.
   - `sc` is `lv2_syscall(ctx)`; an import stub is `ps3_hle_call(nid, ctx)`.

The SPU pipeline (`tools/spu_lifter.py`) has the same shape: `ctx->gpr[0..127]` as 128-bit values, `spu_*` helpers, and `spu_rdch`/`spu_wrch`/`spu_stop`/drain hops that take `ctx`. See `SPU_NEXT_STEPS.md`.

## 2. What the host compiler already does, and what it cannot (VERIFIED, disassembly)

- **It does:** inlines the static helpers, folds constants, keeps a value it has just computed within one statement, and turns the inline-load gate into one compare chain. Each guest access does one `bswap`.
- **It cannot keep guest registers in host registers**, for two reasons:
  1. `ctx` is passed to every callee, so after any call every field may have changed.
  2. Guest memory is reached through `uint8_t*` under `-fno-strict-aliasing`, so every guest store, inline or out of line, may alias `ctx`.

  Every lifted statement therefore loads its operands from `ctx` and stores its result back. In the disassembly of a real function (`func_00C78A20`), `ctx->gpr[1]` is reloaded from `[rsi+0x8]` after each `vm_write64`, and the CR field update is a load, `and`, `or` and store of `[rsi+0x400]`.
- **Real TU `ppu_recomp_006.cpp`** (759 functions, 74,581 guest statements), static:

  | Metric | Value |
  |---|---:|
  | x64 instructions per guest instruction | 8.43 |
  | `ctx`-field memory operands per guest instruction | 1.55 |
  | Calls per guest instruction (cold paths included) | 0.50 |

- **Call targets in that TU, by static site count:** `vm_read32` (7,376, slow path), `__dyn_tls_on_demand_init` (5,984, the TLS guard of `g_trampoline_fn` in each `DRAIN_TRAMPOLINE`), `ppu_trace_bb` (4,833, cold), `vm_write64` (2,908), `vm_write32` (2,585), `ppu_trace_ret` (1,844), direct `func_*` (1,561), out-of-line VMX helpers (`vmx_vmaddfp` 1,204, `vmx_vaddfp` 829).

## 3. Where guest state must be synchronized (VERIFIED, runtime read)

| Boundary | Why the context must be exact there |
|---|---|
| `func_X(ctx)`, `DRAIN_TRAMPOLINE`, `ps3_indirect_call`, `ps3_hle_call`, `lv2_syscall`, any helper taking `ctx` | The callee reads and writes registers through `ctx`. |
| `return` and the trampoline return | The caller or trampoline target reads `ctx`. |
| `PPU_TR_*` hooks, when tracing is on | The tracer reads `ctx`. |
| Out-of-line `vm_read*`/`vm_write*`, `ppu_stwcx32` | **Not a boundary for registers.** They do not receive `ctx`. Their only `ctx` access is through the TLS `g_active_ctx`, and every such use in `ppu_loader.cpp`, `spu_raw.c`, `cellGcmSys.c` and `cellAdec.c` is a diagnostic (watch, dump or log). The one functional use, the store-conditional re-validation, reads `reserve_addr`/`reserve_value`, which are not promoted. |
| Exceptions | No C++ exception crosses lifted PPU frames. The one `longjmp` (`sys_ppu_thread.c:571`, thread exit) is taken inside an HLE call, where `ctx` has already been synced. Guest page faults are committed and resumed by a vectored handler and do not touch `ctx`. |
| Other threads | No thread writes a running thread's registers. The sampler and crash handlers read them (diagnostic only). |

## 4. Fast-path infrastructure that exists but is not emitted (VERIFIED)

- **T152 page gates and inline guest stores** (`dcd62dc` on `agent/t152-ppu-recompiler-performance`; −31 % on a store-heavy lifted function offline) were never merged. They are absent from `766d3575` and from the lift: every guest store is still an out-of-line call.
- **`PS3_ICALL_FAST`** is in the tree (runtime switch, off by default). T153 measured no in-game gain.
- **SPU `SPU_IB_DISPATCH` / `spu_indirect_branch_mt`** (`runtime/spu/spu_dispatch_mt.c`) is never selected: the lifter emits `spu_indirect_branch(ctx)` by name (T186).
- **The lift is built with `--trace-hooks`.** That costs a global test per label and per call, plus the cold call sites.

## 5. The three highest-value generic changes

Estimates are ESTIMATE; measurements are in `PERFORMANCE_BENCHMARKS.md`.

| # | Change | Complexity | Correctness risk | Expected impact (ESTIMATE) |
|---|---|---|---|---|
| 1 | **Guest-register promotion with lazy CR/XER**: GPR, FPR, CR, XER, LR and CTR in C locals per function, synced at the boundaries in §3. CR stays a local, so the host compiler folds compare-then-branch and drops dead CR rebuilds; that is lazy CR materialization without a separate CR model. | Medium: one text-level pass (~700 lines) on the lifter's output, no relift of instruction semantics | Medium: a missed boundary loses state. Mitigated by the dataflow design (dirty/valid invariant) and differential execution with mutants (`DIFFERENTIAL_TESTS.md`) | Large on loop code with few calls. Small or none on call-dense code while stores are out-of-line calls |
| 2 | **Inline guest stores in the standard header** (T152 O4, with page gates), ported to the current runtime | Low–medium: the header block exists; the runtime gating has to be re-applied on top of T187's `spu_coherency.c` | Medium: reservation coherence (T152 has a 300 k-op differential) | T152: −31 % on a store-heavy function. It also removes the call that limits #1 |
| 3 | **Cheaper call boundaries**: hoist the `g_trampoline_fn` TLS guard (one TLS address per function, not per drain), emit direct tail calls inside an image, and lift release builds without `--trace-hooks` | Low | Low–medium | 3–8 % on call-dense code (HYPOTHESIS: unmeasured) |

**Choice for Phase B:** #1, the brief's first preference, supported by the evidence:
- Loop kernels: up to 2.13×.
- Real functions: see `PERFORMANCE_BENCHMARKS.md`.

The first attempt showed why #2 matters. With out-of-line stores, eager reloads after every call made real code 44 % larger (static). The final design reloads lazily and drops clean locals at store calls (`OPTIMIZED_CODEGEN_DESIGN.md` §4).

## 6. No new IR (decision)

- The lifter's output is already a sequence of C statements, with labels, `goto`s and a fixed vocabulary of boundary calls. A statement-level CFG over that text supports the dataflow promotion needs (dirty, valid, next use before a sync), and the host compiler does SSA, register allocation and CR bit folding.
- This can be adopted incrementally: a lifter flag (`--promote-regs`), or a rewrite of an existing lift's `.cpp` files (`tools/ppu_regpromo.py in out`). No instruction is relifted.
- An IR becomes worthwhile when an optimization needs instruction-level semantics the C text does not expose, for example SPU float range proofs or cross-function register allocation (`FUTURE_RECOMPATIBILITY.md`).

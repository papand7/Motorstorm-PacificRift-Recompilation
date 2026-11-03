# T188: future recompilation compatibility

## Other titles

- **Nothing in the pass or the tests refers to a game.**
  - The pass recognises the lifter's generic vocabulary only: `ctx->field`, labels, `goto`, `return`, calls that take `ctx`, the `PPU_TR_*` hooks and the `vm_write*` names.
  - The tests use synthetic programs built from PowerISA encodings.
  - The MotorStorm lift was only used as a private validation workload.
- **Any title lifted by this `ppu_lifter.py` can use `--promote-regs`.** An older lift can be rewritten without relifting: `py -3 tools/ppu_regpromo.py <tu.cpp> <out.cpp> --stats`, applied per TU.
- **Workload dependence** (see `OPTIMIZED_CODEGEN_DESIGN.md` §8):

  | Title profile | Expected effect |
  |---|---|
  | Loop-heavy (physics, decompression, culling, skinning) | Gains most |
  | Call-dense or store-dense, with out-of-line stores | About neutral, per the measurements |

  Measure per title with the stand-alone pass on a few hot TUs before relifting everything.
- **SSX and other candidates:** the same constraints apply. One title-specific check is needed: a port that overrides lifted functions with strong symbols (`--weak`) is unaffected. Weak definitions are matched and rewritten like any other.

## Lift formats and older lifters

- The pass accepts the formats of the T173-era staging lift (on the same line as `PPU_TR_ENTER`, weak attributes, callee-save snapshots) and of the current lifter.
- Anything it does not parse is left unchanged and counted by reason (`--stats`).

## Host CPUs and compilers

- **Host CPUs:** the output is portable C/C++ with no x64 intrinsics. Gains come from the host compiler's register allocation, so on AArch64 (31 GPRs) they should be at least as large as on x64 (HYPOTHESIS; unmeasured).
- **Compilers:**
  - clang-cl 23 is the measured compiler.
  - The pass emits no GNU extensions beyond those the lifter already uses (`__builtin_expect`, statement expressions).
  - MSVC `cl` is untested.

## Build configurations

- **Debug builds:** promoted locals are visible in a host debugger. `ctx` is exact at every call, return and enabled hook. Out-of-line `vm_*` diagnostics that read `g_active_ctx` may see older register values: use an unpromoted lift for those investigations.
- **Release builds:** independent of build type and of `--trace-hooks`. With tracing off, the hooks cost what they did before: one test.

## Extending the architecture

| Future pass | How it plugs in |
|---|---|
| Inline stores (next milestone) | Switch the pass's store policy (`--promote-inline-stores`) when TUs are built with `PPU_INLINE_STORES` |
| VMX registers (`vr[]`) | Add 128-bit keys. The lifter's VMX helpers take `&ctx->vr[n]` pointers, which are address-taken: they need either by-value helpers or the memcpy-operand rule extended to vector helpers |
| FPSCR | Needs the FP helpers that take `ctx` to take the FPSCR by pointer first |
| Cross-function promotion (callee-save registers kept in host registers across direct calls) | Needs a calling convention for lifted functions beyond `void f(ppu_context*)`. That is the point where a real IR, or a lifter-level ABI change, becomes worthwhile |
| SPU | An ISA profile for the same pass (`SPU_NEXT_STEPS.md`) |

**Tests to keep:** `tools/test_ppu_regpromo.py` (unit, differential, mutants). Any change to the lifter's boundary vocabulary (a new helper that takes `ctx`, a new hook) must keep passing it. A new hook macro that hides `ctx` in its definition, and does not show it in its arguments, would be a missed boundary: the convention is that `ctx` is always written out at the call site.

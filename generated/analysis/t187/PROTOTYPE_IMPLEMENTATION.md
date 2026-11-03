# T187: prototype, PPU register + CR promotion (Phase B)

**Build ID:** ps3recomp worktree `ps3recomp-t187-codegen`, branch `agent/t187-codegen-regpromo`.
- Commit `2b0a11ef077fbb8737e8252eeef6472c123e0704`.
- Base `ddda809a` (T185 head).
- Not pushed or merged.

## What it is

An opt-in post-pass over each lifted PPU function. It is generic: there are no addresses and no game knowledge,
and it reads only the lifter's own output grammar.

| File | Lines | Role |
|---|---:|---|
| `tools/ppu_promote.py` | 268 | The pass: refusal rules, CFG, may-dirty dataflow, spill/reload placement, `--promote-max-regs` cap, CLI on existing sources |
| `tools/ppu_lifter.py` | +23 | `--promote-regs`, `--promote-max-regs N`; hook before the closing `}` of each function; prints stats |
| `tools/ppc_asm.py` | 262 | Small PowerPC assembler for test inputs; every word is checked by `ppu_disasm.decode` |
| `tools/test_ppu_promote.py` | 376 | Fuzzer, differential verify (plain and traced), `--mutant` control, offline bench, static counts |
| `tools/test_ppu_promote_pass.py` | 105 | 21 unit checks (refusals, spill sets, back edge, r1, CR, cap) |
| `tests/promote/{kernels.s,harness.cpp,vmstub.c}` | 714 | 12 benchmark kernels, harness, out-of-line memory helpers that mirror `ppu_loader.cpp` |

## Usage

```
py -3 tools/ppu_lifter.py <elf|bin> ... --trace-hooks --promote-regs [--promote-max-regs 8]
py -3 tools/ppu_promote.py lifted.cpp lifted_promoted.cpp     # same transform on an existing source
```

Without the flag, the output is byte-identical. Kernel image, lifted with HEAD `ddda809a` and with
`2b0a11e`: `lifted.cpp` md5 `ed3c0101…` both, `ppu_recomp.h` md5 `4bddc1dc…` both.

## Emitted shape (inspectable)

```
void func_X(ppu_context* ctx) {
    /* T187 promote-regs: 9 register(s) in locals, synced at calls/returns */
    uint64_t _pr3 = ctx->gpr[3]; ...  uint32_t _prcr = ctx->cr;
loc_..: do { if (__builtin_expect(g_ppu_trace_mask & 4u, 0)) { ctx->gpr[3] = _pr3; ...; ppu_trace_bb(ctx, 0x..u); } } while (0);
        _pr3 = _pr9 | _pr9;                    // body: locals instead of ctx->gpr[N]
        ctx->gpr[3] = _pr3; ...                // spill of the may-dirty set
        ctx->lr = ..; func_Y(ctx); DRAIN_TRAMPOLINE(ctx); ...
        _pr3 = ctx->gpr[3]; ...                // reload all promoted
```

## Refusals (function kept as lifted)

- address of a promoted register;
- non-literal register index;
- computed goto;
- goto to an unknown label;
- label sharing a line with code;
- a promoted write before, or a use or goto after, a sync token in one line;
- `++`/`--` on a register;
- a statement split over lines;
- a `_pr` name clash.

**Coverage, MotorStorm chunk 006** (generated code, no launch): 291 of 759 functions promoted. The other 468 have no
GPR or CR use (stubs and thunks), so the pass refused none for safety reasons.
Coverage elsewhere: fuzz 658/658, kernels 18/18.

## Not done (deliberately)

- **Not promoted:** LR, CTR, XER, FPR and VR.
- **Not made default.**
- **No SPU change:** coordinated by not touching `runtime/spu` or `spu_lifter.py`.
- **No game rebuild or launch.**

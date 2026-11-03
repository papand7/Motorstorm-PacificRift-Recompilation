# T188 Phase B: implementation

Branch `agent/t188-codegen-architecture` (ps3recomp, worktree `ps3recomp-t188`, from `766d3575`); code commit `f209ad24`. Reports: root branch `agent/t188-codegen-architecture-report`. Local only: not pushed or merged. No game launch and no relift of the game.

## Modified and new files

| File | Change |
|---|---|
| `tools/ppu_regpromo.py` (new) | The promotion pass, stand-alone CLI (`in.cpp out.cpp [--stats]`) |
| `tools/ppu_lifter.py` | New flags `--promote-regs`, `--promote-inline-stores` and `--promote-store-sync`, applied in `_function_def_lines`. Header: opt-in `PPU_COLD_CALLS` slow-path thunks (`vm_read*_cold`/`vm_write*_cold`; without the macro they are inline forwarders, so the code is unchanged) |
| `tools/ppu_difftest.py` (new) | Encoders, assembler, random-program generator, kernels, fixture runtime, variant build/run |
| `tools/test_ppu_regpromo.py` (new) | Unit checks, the 12-seed differential, mutants |
| `tools/bench_ppu_regpromo.py` (new) | Kernel/random benchmark (time, variance, static x64, ctx/stack operands, object size, compile time) |

No runtime source changed (`runtime/`, `libs/`). No instruction lowering changed.

## Feature flags (all off by default)

| Flag | Where | Effect |
|---|---|---|
| `--promote-regs` | lifter | Guest GPR/FPR/CR/XER/LR/CTR in locals per function. Store policy default: clean locals dropped at out-of-line store calls |
| `--promote-inline-stores` | lifter | With the above: keep clean locals across stores, for TUs built with `PPU_INLINE_STORES` |
| `--promote-store-sync` | lifter | With the above and out-of-line stores: write back before each store call, so no local is live across one |
| `ppu_regpromo.py in out [--store-sync\|--inline-stores]` | stand-alone | The same pass on an existing lift TU, without relifting |
| `-DPPU_COLD_CALLS` | compile the lifted TUs | Slow paths of inline loads/stores call `preserve_most` thunks (clang; x86-64 or AArch64). Other compilers: no effect |

The original backend is unchanged: without `--promote-regs` the lifter output is byte-identical (checked by the test). Without `PPU_COLD_CALLS` the header's thunks inline to the previous code.

## Before/after generated code (synthetic kernel `k_sum`, our own guest code)

Baseline (lifter output, loop body):

```c
loc_00010024:
    ctx->gpr[6] = vm_read32(ctx->gpr[3] + 0x0);
    ctx->gpr[4] = ctx->gpr[4] + ctx->gpr[6];
    { int64_t a = (int32_t)ctx->gpr[6]; int64_t b = (int64_t)0x80; uint32_t cr_val = ((a < b) ? 8 : (a > b) ? 4 : 2) | ((ctx->xer >> 31) & 1u); ctx->cr = (ctx->cr & ~(0xFu << 24)) | (cr_val << 24); }
    if ((!((ctx->cr >> 27) & 1))) goto loc_00010038;
    ctx->gpr[4] = ctx->gpr[4] + (int64_t)(1);
loc_00010038:
    ctx->gpr[3] = ctx->gpr[3] + (int64_t)(4);
    if ((--ctx->ctr != 0)) goto loc_00010024;
```

Promoted:

```c
    _pctr = _pg5; _pcr = ctx->cr; _pxer = ctx->xer;      /* loaded once, on the loop entry edge */
loc_00010024:
    _pg6 = vm_read32(_pg3 + 0x0);
    _pg4 = _pg4 + _pg6;
    { int64_t a = (int32_t)_pg6; int64_t b = (int64_t)0x80; uint32_t cr_val = ((a < b) ? 8 : (a > b) ? 4 : 2) | ((_pxer >> 31) & 1u); _pcr = (_pcr & ~(0xFu << 24)) | (cr_val << 24); }
    if ((!((_pcr >> 27) & 1))) goto loc_00010038;
    _pg4 = _pg4 + (int64_t)(1);
loc_00010038:
    _pg3 = _pg3 + (int64_t)(4);
    if ((--_pctr != 0)) goto loc_00010024;
    ...
    { ctx->gpr[0] = _pg0; ctx->gpr[1] = _pg1; ... ctx->cr = _pcr; ctx->lr = _plr; ctx->ctr = _pctr; return; }
```

The disassembly for this loop is in `PERFORMANCE_BENCHMARKS.md` §3.

## Test results (VERIFIED)

| Test | Result |
|---|---|
| `test_ppu_regpromo` | 0 failures: unit checks, 12 seeds × 4 variants identical (830,453 boundary states), 3/3 mutants detected |
| Existing lifter tests | all pass: `test_ppu_lift` (1,533 conformance checks), `test_ppu_branches`, `test_ppu_lifter_chunks`, `test_lifter_dedupe`, `test_lifter_header_name`, `check_ppu_scaffold`, `test_ppu_trace`, `test_ppu_jumptables`, `test_ppu_cs_restore`, `test_ppu_fallthrough` |
| Full suite (`run_all_t188.py ps3recomp-t188`, log `generated/analysis/t188/logs/suite_run.txt`) | 160 PASS, 43 SKIP, 3 FAIL. `test_spurs_kick_wake` is the known flaky timing check. `test_t169_profile` (6 failures) and `test_t169_rt_reinterp` (5 failures) are D3D12/WARP renderer tests; they fail identically when rerun alone on the unmodified T183 base `766d3575`, so the cause is the machine (GPU/WARP state), not T188 |

## Fallback

A body the pass does not understand is emitted exactly as before, and the reason is counted (`--stats`, `lifter.promote_stats`). Reasons are listed in `OPTIMIZED_CODEGEN_DESIGN.md` §6.

On the MotorStorm lift, TUs `000` and `006`: every function with a register access was promoted (2,778 + 299). The 940 left unchanged touch no register.

## Pass cost

- `ppu_recomp_000.cpp` (38 MB): about 15 s per TU in Python. The whole 3.6 GB lift is about 25 min single-threaded (ESTIMATE). It is parallel per TU.
- Lifted text grows 1.44–1.47× (TU `006`: 5.68 MB → 8.16–8.36 MB), from the sync statements.
- Compile time and object size: `PERFORMANCE_BENCHMARKS.md` §4.

## Known limitations

- **Benefit is workload-dependent.**
  - Loop kernels: up to 2.13×.
  - Real game functions on synthetic inputs (short paths): about neutral to slightly negative, depending on the store policy (`PERFORMANCE_BENCHMARKS.md`). This is why it is opt-in and why it is measured per title.
- **Out-of-line stores limit it.** Inline stores (the next milestone) are where the larger gain is expected.
- **Diagnostics:** readers of `g_active_ctx` inside `vm_*` (watchpoints, dumps) see older register values under promotion.
- **Not promoted:** VR/FPSCR (helpers take pointers or `ctx`).
- **Text growth** raises compile time; this is measured.

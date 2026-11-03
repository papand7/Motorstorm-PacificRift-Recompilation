# T187: performance results (Phase C), **synthetic and static only**

No game was launched, so **there is no FPS or in-game claim.** §1 and §2 are synthetic; §3 and §4 are static
measurements of MotorStorm's lifted code. They are kept separate.

## Method

**Host:** Ryzen 5 9600X (6C/12T), Windows 11. Bench process pinned to core 2 at HIGH priority. Other workloads idle.

**Builds:** the same guest image is lifted with the default lowering and with `--promote-regs`
(± `--promote-max-regs N`), using the game's compiler flags and `--trace-hooks` (trace mask 0 at run time).
Memory helpers are out of line in a separate TU (`vmstub.c`), as in the game.

**Runs:**
- Each round runs `harness.exe bench 15 1`: 2 warm-ups, then 15 timed calls per kernel; the round's median is kept.
- 7 rounds, with the base/promo order alternated per round.
- Reported: the median of the round medians, and the round-to-round standard deviation in %.
- ns per guest instruction = time / (n × dynamic guest instructions per n, from the `;@ per_n` annotations).

**Commands** (from `ps3recomp-t187-codegen`, `<W>` = `generated/analysis/t187/scratch`):

```
py -3 tools/test_ppu_promote.py --fuzz 0 --bench-rounds 7 --reps 15 --out <W>/bench1 --json <W>/bench1/res.json
py -3 tools/test_ppu_promote.py --fuzz 0 --bench-rounds 7 --reps 15 --max-regs 8  --out <W>/benchcap8  --json ...
py -3 tools/test_ppu_promote.py --fuzz 0 --bench-rounds 7 --reps 15 --max-regs 12 --out <W>/benchcap12 --json ...
```

## 1. Runtime, synthetic kernels (speedup = base ms / promo ms; sd % base/promo)

| Kernel | Covers | Base ms | Uncapped | sd % | Cap 8 | sd % | Cap 12 | ns/guest insn, base → uncapped |
|---|---|---:|---:|---|---:|---|---:|---|
| k_arith | ALU loop | 0.335 | **1.28×** | 0.6/0.1 | 1.23× | 0.5/1.5 | 1.24× | 0.09 → 0.07 |
| k_memsum | load/modify/store | 0.305 | 0.95× | 5.4/3.3 | 1.08× | 4.8/3.5 | 1.04× | 0.21 → 0.22 |
| k_copy | memory copy | 0.303 | 1.00× | 4.1/0.5 | 1.01× | 5.6/3.0 | 1.00× | 0.30 → 0.30 |
| k_struct | struct field updates | 0.079 | **1.54×** | 0.8/0.1 | 1.35× | 1.1/0.3 | 1.53× | 0.08 → 0.05 |
| k_bsearch | branchy search | 2.469 | 1.13× | 0.2/0.2 | 1.07× | 0.2/0.2 | 1.12× | 0.25 → 0.23 |
| k_cr | CR fields and logic | 1.818 | **2.28×** | 0.5/0.0 | 1.47× | 0.4/0.5 | 2.28× | 0.34 → 0.15 |
| k_calls | direct calls (sync) | 0.184 | 1.11× | 23.8/0.0 | 1.15× | 1.8/0.0 | 1.11× | 0.10 → 0.09 |
| k_fib | recursion | 1.054 | 1.24× | 0.8/0.6 | 1.27× | 3.7/1.3 | 1.22× | 0.43 → 0.35 |
| k_icall | indirect dispatch | 0.970 | **0.97×** | 0.5/0.1 | 0.94× | 0.6/0.4 | 0.97× | 0.51 → 0.53 |
| k_regs | 20 live registers | 0.226 | **0.89×** | 4.8/0.8 | 1.01× | 3.9/2.3 | 0.81× | 0.27 → 0.30 |
| k_atomic | lwarx/stwcx. | 0.471 | 1.12× | 0.3/0.2 | 1.11× | 0.2/0.8 | 1.12× | 0.94 → 0.84 |
| k_sys | syscall boundary | 0.127 | 1.02× | 0.1/0.0 | 1.02× | 1.3/1.4 | 1.02× | 0.16 → 0.16 |

The base columns of the three runs agree within 9 %. Speedups above about 1.05× are outside the measured
spread (VERIFIED, synthetic).

**Regressions, explained:**
- **k_regs** (VERIFIED by disassembly): about 20 locals live across opaque memory-helper calls, but only about
  8 callee-saved x64 registers exist. 186 `%rsp` stack accesses replace 164 ctx accesses. Cap 8 cures it; cap 12 makes it worse.
- **k_icall** (HYPOTHESIS, not dissected): every indirect call is a full sync with a reload of all registers.
- **k_memsum, uncapped** (PARTIAL): within its 5 % spread.

**The cap is a trade-off, not a fix:** cap 8 halves the k_cr gain (2.28× → 1.47×).

## 2. Static, synthetic kernels (x64 instructions per function: base / uncapped / cap 8)

k_arith 106/184/182 · k_cr 213/308/280 · k_struct 397/487/457 · k_regs 519/684/510 · k_icall 257/295/273 ·
k_calls 217/231/231.

**Static size moves against speed:** k_arith grows 74 % in x64 instructions and runs 1.28× faster. The growth is
cold trace-spill code. Instruction count is not a proxy for speed here.

**Build cost, kernels:**
- lift 0.79 → 0.69–1.2 s;
- compile 0.31 → 0.32–0.35 s;
- peak compiler memory 90.4 → 90.9 MB;
- `.text` 12,720 → 15,660 B uncapped (14,114 B cap 8, 14,890 B cap 12).

**Fuzz image (658 functions):** lift 1.6 s, compile about 6 s, peak 225–280 MB for promoted; per-run detail in `fz*/res.json`.

## 3. Static, MotorStorm lifted code (private source `generated/ppu-t173-staging`, numbers only)

Command:

```
py -3 generated/analysis/t187/tools/ms_static_t187.py ps3recomp-t187-codegen generated/analysis/t187/ms_static [8]
```

Chunk `ppu_recomp_006.cpp`, 759 functions, about 76,939 guest instructions:

| | Base | Promoted (uncapped) | Promoted (cap 8) |
|---|---:|---:|---:|
| Functions promoted | — | 291 (468 have no registers) | 291 |
| Pass time | — | 1.28 s | 1.35 s |
| Source bytes | 5,759,232 | 10,214,617 (+77 %) | 7,507,448 (+30 %) |
| Compile time | 25.4 s | 36.1 s (+42 %) | 28.1 s (+9 %) |
| Peak compiler memory | 581 MB | 657 MB (+13 %) | 584 MB (+1 %) |
| `.text` | 2,844,977 | 3,853,024 (+35 %) | 3,085,830 (+8.5 %) |
| x64 instructions | 634,498 | 805,545 | 682,612 |
| x64 per guest instruction | 8.25 | 10.47 | 8.87 |
| x64 instructions with a memory operand | 239,890 | 401,496 | 278,723 |

The compile times come from separate runs and vary by about ±15 % (the first base run took 19.2 s).

**13 T185 hot functions, as one TU** (static only; attribution with `generated/analysis/t187/tools/attrib_t187.py`):

| Variant | x64 | Memory operands |
|---|---:|---:|
| Base | 52,484 | 19,682 |
| Promoted | 63,187 (+20 %) | 29,560 |
| … without the cold trace-spill blocks | 55,759 | 22,791 |
| … and without the reloads after calls | 53,989 | 22,188 |
| Promoted, cap 8 | 55,568 (+6 %) | 22,149 |

Attribution of the +10,703 instructions: cold spill blocks 69 %, reloads 17 %, sync spills 14 %.

**What this does and doesn't say:**
- Static memory-operand counts include the cold blocks, so they say nothing about dynamic loads and stores.
- Whether the hot paths of these functions get faster is **unmeasured (BLOCKED: needs an in-game or replay run)**.

## 4. Correctness failures

0 across all runs; the mutant control fails as intended. See `CORRECTNESS_RESULTS.md`.

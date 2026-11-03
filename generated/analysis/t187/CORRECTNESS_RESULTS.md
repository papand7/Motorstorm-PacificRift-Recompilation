# T187: correctness results

Build `2b0a11e` (`ps3recomp-t187-codegen`). Host: Ryzen 5 9600X, Windows 11, Python 3.14.7, clang-cl 23.1.3,
the game's lifted-code flags. The reference for every comparison is the **original lowering** of the same guest
image, built into the same harness.

## Method

`tools/test_ppu_promote.py` builds one guest image from:
- `tests/promote/kernels.s`;
- N seeded random programs. The fuzzer covers arithmetic, rotates/masks, compares into random CR fields, CR
  logic, forward and backward branches, `bdnz`, loads and stores of every width, calls, indirect calls,
  `lwarx`/`stwcx.` and syscalls.

It lifts the image twice with `--trace-hooks`, once in the default mode and once with `--promote-regs`, compiles
both, and runs every entry with 3–4 seeds. Fuzz entries start from a random GPR, CR, CTR and XER state.

| Mode | Compared per run |
|---|---|
| `verify` | r3, FNV hash of all GPRs, CR, CTR, LR, XER, FNV hash of 1 MB scratch and the guest stack |
| `verify trace` | the same, plus a running hash of GPRs and CR at **every** trace hook (BB, call, return), plus the hook count |

The trace mode catches a stale register at any intermediate point, not only at exit.

## Results

| Run | Command (from `ps3recomp-t187-codegen`) | Guest fns / insns | verify | verify trace | Label |
|---|---|---|---|---|---|
| seed 1 | `py -3 tools/test_ppu_promote.py --fuzz 160 --seed 1 --no-bench --out <W>/fz1 --json <W>/fz1/res.json` | 658 / 19,560 | 676 runs, 0 differ | 676, 0 | VERIFIED |
| seed 2 | same, `--seed 2` (`fz2`) | 658 / 19,180 | 676, 0 | 676, 0 | VERIFIED |
| seed 3 | same, `--seed 3` (`fz3`) | 658 / 18,812 | 676, 0 | 676, 0 | VERIFIED |
| cap 8, seed 4 | `... --fuzz 160 --seed 4 --no-bench --max-regs 8 --out <W>/fzcap8` | 658 | 676, 0 | 676, 0 | VERIFIED |
| kernels (bench builds) | `--fuzz 0` (`bench1`, `benchcap8`, `benchcap12`) | 18 / 448 | 36, 0 each | 36, 0 each | VERIFIED |
| **mutant (negative control)** | `... --fuzz 0 --no-bench --mutant --verify-timeout 30 --out <W>/mutant2` | 18 | **FAIL**: timed out (a loop diverged) | **FAIL**: crash 0xC0000005 | VERIFIED: the test detects missing spills |

`<W>` = `generated/analysis/t187/scratch` (private).
`--mutant` deletes every spill line (`ctx->gpr[N] = _prN;` for N≠1, and `ctx->cr = _prcr;`) from the promoted
source.

**Note on a test bug fixed during T187:** the first mutant run reported nothing, because the hung harness
outlived the shell `timeout`. The driver now treats a verify timeout as FAIL (`--verify-timeout`, default 120 s).

## Regression of the default path

| Test | Result |
|---|---|
| `py -3 tools/test_ppu_lift.py` | `[ppu-conformance] 1533 checks passed, 0 FAILED, 0 skipped` |
| `py -3 tools/test_ppu_lifter_chunks.py` | PASS |
| `py -3 tools/test_ppu_promote_pass.py` | 21 PASS, 0 failures |
| default lift, HEAD `ddda809a` vs `2b0a11e` | `lifted.cpp` and `ppu_recomp.h` byte-identical (md5) |
| `py -3 tools/audit_public.py --tree <copy of changed files>` | passed |

## Limits

- **PARTIAL:** no MotorStorm code was *executed* promoted. The game was not launched, as instructed.
  MotorStorm coverage is static (compile plus refusal stats) only.
- **HYPOTHESIS:** the fuzzer's grammar is the lifter's output on fuzzer-generated code. Lifter constructs that
  appear only in real games (jump-table `switch`, HLE stubs, VMX blocks) are not executed by these tests. They
  are guarded only by the refusal rules and by compiling chunk 006 cleanly.
- **Not covered:** FP and VMX state is not promoted, so not tested here. Exceptions out of helpers are not
  exercised.

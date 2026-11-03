# T188: differential testing framework and results

## 1. Framework (`tools/ppu_difftest.py`, public, generic)

1. **Guest programs** are real PowerPC instruction words. Every encoding is checked against `ppu_disasm`. Programs come from:
   - **random programs** from a seed (`random_program(seed, nfuncs, body)`), reproducible;
   - **hand-written kernels** (`KERNELS`, used by the benchmark).
2. **Lifting** uses the real `ppu_lifter.PPULifter`: the same instruction lowering, callee-save pass, trace hooks, trampolines, HLE stubs and function table as a game lift.
3. **Variants** come from one lifted source:

   | Variant | What it is |
   |---|---|
   | `base` | The baseline lowering |
   | `promo` | Promotion, clean locals dropped at store calls |
   | `promo_keep` | Clean locals kept across stores |
   | `promo_sync` | Dirty locals written back before each store call |
   | `promo_nofpr` | Promotion without FPRs |

   Build options apply to every variant: inline stores (`PPU_INLINE_STORES`, T152's gate shape) and cold-call thunks (`PPU_COLD_CALLS`).
4. **The fixture runtime** is deterministic and local to the test:
   - guest memory, out-of-line `vm_read*/vm_write*`, and `ppu_stwcx32/ppu_stdcx64` (compare-and-store on the big-endian word);
   - `ps3_indirect_call` through the lifted function table, `ps3_hle_call`, `lv2_syscall`, and the trace functions.
   - Every entry that receives the context logs an FNV hash of the **complete** register state (GPR, FPR bits, CR, XER, LR, CTR, FPSCR). The callees then clobber state the way real callees do: return values, volatile GPRs, CR, CA, CTR, FPRs.
5. **Transcript per seed:** the final state hash, a hash of all guest memory, the event-log hash and the event count. Every variant must match the baseline byte for byte, for each trace mask (0, and 7 = all hooks on).
6. **Mutants:** three deliberately broken passes run on 3 seeds each: a write-back that drops a register, a reload that drops one, and a return that skips its write-back. Each must be detected. This shows the framework can see synchronization errors.

## 2. Coverage

| Area | How |
|---|---|
| Arithmetic/logical | add/subf/and/or/xor/nor/andc, the shifts (slw/srw/sraw/srawi with CA), rlwinm/rlwimi/rldicl, cntlzw, extsw/extsb, mullw/mulld, neg, addi/ori/addic(.)/subfic |
| Carry/overflow | addc/adde/addze/subfc/subfe (CA in and out), `addo.` (OV/SO), mtxer with random values (SO feeding later compares) |
| Record forms / CR | 20 % of ALU ops with Rc=1; cmpw/cmplw/cmpd/cmpld/cmpwi/cmplwi to random fields; crand/cror/crxor/mcrf/mfcr/mtcrf |
| Conditional branches | forward bc (true/false/always) on random CR bits, forming multi-block diamonds and chains |
| Loops | counted `mtctr`/`bdnz` loops (loop-carried registers, the loop-header rule) |
| Register dependencies | random register choice from a pool of 22 GPRs and 14 FPRs, so chains cross blocks and calls |
| Memory | lwz/stw/lbz/stb/lhz/sth/ld/std, unaligned lwz, update forms (lwzu/stwu: RA write-back), indexed (lwzx), byte-reversed (lwbrx/stwbrx: raw-store coherence macros) |
| Endianness/alignment | big-endian guest memory in the fixture, unaligned accesses, byte-reversed forms |
| Atomics/reservations | lwarx/addi/stwcx./mfcr, which succeeds; stwcx. with no reservation, which fails; CR0 result captured |
| FP edge cases | fadd/fsub/fmul/fdiv/fmadd/fmsub/fmr/fneg/fabs/frsp/fcmpu, lfd/stfd. The inputs include ±0, ±∞, NaN, a denormal, DBL_MAX-scale values and random values |
| Calls and callbacks | direct `bl` to later functions (a DAG); HLE imports (`ps3_hle_call`, which clobbers state); syscalls (`sc`); indirect `mtctr`+`bctrl` through the function table; tail calls through the trampoline |
| Sync boundaries | each of the above logs the full state it sees; trace hooks with mask 7 log the state at every block, call return and function entry |
| Exceptions | no C++ exception crosses lifted frames (audit §3). Guest faults: the fixture exits on an out-of-range access, so both builds must fault identically (none occurred) |

## 3. Results (VERIFIED)

`py -3 tools/test_ppu_regpromo.py --seeds 12` uses 8 functions × 70 body items per program.
- Even seeds have trace hooks on and run with masks 0 and 7.
- Seeds ≡ 0 (mod 3) use inline stores; seeds ≡ 1 (mod 4) use the cold-call thunks.

| Seed | Variants | Boundary events | Hooks | Stores | Cold calls | Result |
|---|---|---:|---|---|---|---|
| 1 | base, promo, promo_keep, promo_sync | 21,544 | off | out of line | on | identical |
| 2 | 〃 | 281,158 | on (0, 7) | out of line | off | identical |
| 3 | 〃 | 2,244 | off | inline | off | identical |
| 4 | 〃 | 68,491 | on | out of line | off | identical |
| 5 | 〃 | 11,898 | off | out of line | on | identical |
| 6 | 〃 | 21,477 | on | inline | off | identical |
| 7 | 〃 | 16,471 | off | out of line | off | identical |
| 8 | 〃 | 159,223 | on | out of line | off | identical |
| 9 | 〃 | 22,822 | off | inline | on | identical |
| 10 | 〃 | 155,520 | on | out of line | off | identical |
| 11 | 〃 | 42,962 | off | out of line | off | identical |
| 12 | 〃 | 26,643 | on | inline | off | identical |

- **830,453 boundary states compared** per variant, and all match.
- **Mutants:** all 3 detected.
- **Unit checks** (lazy load, call write-back/reload, loop-invariant hoist, 4 fallback reasons, the FPR memcpy rule, hook guard, determinism, the lifter flag being equal to the stand-alone pass, refused bodies unchanged): all pass.
- **The benchmark compares transcripts first** (`bench_ppu_regpromo.py`): 18/18 kernel and random cases identical (`PERFORMANCE_BENCHMARKS.md`).
- **Real MotorStorm functions** (private, `generated/analysis/t188/tools/real_bench.py`): 24 sampled loop-bearing functions per configuration from TU `000`, run in pointer mode (registers and data point into a data window) over 4 seeds. 0 mismatches. 7 functions faulted identically in both builds and were not timed. Per-configuration tables are in `PERFORMANCE_BENCHMARKS.md`.

## 4. Limits

- This is sampling, not proof. Random programs avoid backward branches other than counted loops, recursion, and `mtctr` inside loops, so that they terminate.
- VMX is not generated: VR is not promoted, and the lifter's VMX helpers are unchanged.
- Multi-threaded interleavings are not covered. Promotion changes no memory access, so it cannot change guest-visible ordering, but `g_active_ctx` readers on other threads would see older registers (audit §3).
- The fixture's callees are synthetic. The real runtime's HLE functions receive a synced `ctx` by construction, which is the property tested.

**Reproduce:** `py -3 tools/test_ppu_regpromo.py [--seeds N --first S --funcs F --body B --keep DIR]` with clang-cl on PATH or in `CXX`.

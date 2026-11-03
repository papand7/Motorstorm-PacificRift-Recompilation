# T188: performance benchmarks

All offline. No game launch. Baseline and variant are built from the same lifted source, with the same compiler (clang-cl 23.1.3) and the same flags as the game's lifted TUs (`/O2 /Ob2 /EHsc -std:c++20 -MD -fno-strict-aliasing -fwrapv`), on the same machine (Ryzen 5 9600X) in alternating processes (A B A B …). The machine was **not idle**: Blender, Edge, LeOffice and other agent sessions were running. The alternation spreads that load over both builds, and the coefficient of variation (cv) is reported per case.

## 1. Methodology

| Metric | How |
|---|---|
| Execution time | `best_ms` = best of `reps` repetitions inside one process; median and min over `runs` processes per build. Kernels: 200 program runs per repetition. Real functions: 5,000 calls per repetition |
| Variance | cv = stdev/mean of the per-process values |
| Native instructions per guest instruction | **Static**: x64 instructions (llvm-objdump) / guest instructions of the same functions, cold paths included. Dynamic instruction counts were not available (no hardware counter access on this host); the hot-loop instruction count is given for the reference kernel (§3) |
| Guest-state memory accesses | Static count of memory operands `[reg + disp < 0x440]` off a non-stack register (the `ppu_context` fields), and of stack operands (spills) |
| Binary size / compile time | Object size of the lifted TU; wall time of compiling that TU alone |
| Correctness | Every timed pair first prints identical transcripts (`DIFFERENTIAL_TESTS.md`) |

Commands:
- `py -3 tools/bench_ppu_regpromo.py --runs 5 --reps 9 --random 2` (public, synthetic);
- `generated/analysis/t188/tools/real_bench.py 000 --n 24 --reps 5 --runs 3 --iters 5000 [--inline|--sync|--cold]` (private, real lifted functions);
- `generated/analysis/t188/tools/make_variants.py 006` + `objstats.py` (private, a whole real TU, static).

## 2. Synthetic kernels (generic, VERIFIED)

Final pass. Stores are out of line (the stock header) or inline (T152's gate shape). "promo" uses the default store policy: clean locals dropped at store calls; `promo_keep` when stores are inline.

| Kernel | Stores | Base ms med (cv) | Promo ms med (cv) | Speedup | x64/guest (static) | ctx operands | Stack operands |
|---|---|---|---|---:|---|---|---|
| sum (load, add, compare, branch) | out of line | 2.160 (0.1 %) | 1.013 (0.1 %) | **2.13×** | 5.7 → 6.0 | 31 → 21 | 0 → 2 |
| transform (load, rotate, xor, store) | out of line | 1.109 (0.1 %) | 0.964 (0.0 %) | **1.15×** | 5.2 → 5.5 | 25 → 18 | 0 → 0 |
| chase (dependent loads) | out of line | 1.141 | 1.106 | 1.03× | 5.6 → 5.5 | 29 → 21 | 0 → 0 |
| fpdot (lfd, fmadd, fcmpu) | out of line | 0.920 | 0.886 | 1.04× | 9.5 → 10.0 | 44 → 23 | 2 → 12 |
| calls (loop around a call) | out of line | 0.374 | 0.374 | 1.00× | 6.0 → 6.3 | 33 → 31 | 0 → 0 |
| branchy (compare chains, cror) | out of line | 1.863 | 1.851 | 1.01× | 5.4 → 5.3 | 34 → 23 | 2 → 2 |
| struct (read-modify-write) | out of line | 1.531 | 1.597 | **0.96×** | 7.2 → 7.5 | 31 → 19 | 0 → 0 |
| random 1001 (8 functions, calls/HLE/sc) | out of line | 16.24 | 16.13 | 1.01× | 9.5 → 9.9 | 2011 → 1761 | 2 → 406 |
| random 1002 | out of line | 11.08 | 11.05 | 1.00× | 10.1 → 10.0 | 2041 → 1695 | 4 → 394 |
| sum | inline | 2.172 | 1.024 | **2.12×** | 9.2 → 9.1 | 31 → 18 | 0 → 6 |
| transform | inline | 1.115 | 0.850 | **1.31×** | 9.4 → 9.8 | 25 → 15 | 0 → 3 |
| chase | inline | 1.150 | 1.112 | 1.03× | 9.0 → 9.2 | 29 → 18 | 0 → 2 |
| fpdot | inline | 0.918 | 0.879 | 1.04× | 13.4 → 13.2 | 44 → 19 | 2 → 13 |
| calls | inline | 0.374 | 0.374 | 1.00× | 10.3 → 10.9 | 33 → 30 | 0 → 0 |
| branchy | inline | 1.876 | 1.838 | 1.02× | 8.5 → 8.2 | 34 → 19 | 2 → 8 |
| struct | inline | 1.735 | 1.403 | **1.24×** | 11.7 → 12.2 | 32 → 16 | 0 → 10 |
| random 1001 | inline | 16.12 | 16.03 | 1.01× | 11.0 → 11.7 | 2026 → 1666 | 5 → 534 |
| random 1002 | inline | 10.95 | 10.96 | 1.00× | 11.5 → 11.7 | 2057 → 1616 | 7 → 589 |

Same benchmark, out-of-line stores, `--promote-store-sync` (a later run, so absolute times differ; the speedups are within-run):

| Kernel | Speedup | ctx operands |
|---|---:|---|
| sum | **2.32×** | 31 → 23 |
| transform | 1.00× | 25 → 24 |
| chase | 1.03× | 29 → 23 |
| fpdot | **1.12×** | 44 → 28 |
| calls | 1.00× | 33 → 33 |
| branchy | 0.99× | 34 → 26 |
| struct | 1.00× | 31 → 26 |
| random 1001 (event hashing off: boundaries dominate) | **0.96×** | 2011 → 1974 |

The random rows in the main table were measured with the fixture still hashing state at every event; the sync row above was measured without it. The cv was ≤ 1.8 % in every case. Object size and compile time of these small TUs were unchanged (3–68 KiB, 0.23–0.48 s).

**Reading:**
- Time drops when a loop keeps guest registers and the CR in host registers (sum, transform, struct with inline stores).
- Call-dense code is neutral: the boundaries need the stores the baseline does.
- The random programs are dominated by their HLE/syscall/indirect-call boundaries and are about neutral.
- Static x64/guest barely changes and is not the measure: the hot loops shrink while sync code is added on cold edges.

### How the loop-header rule was arrived at (VERIFIED, same benchmark)

| Pass version | calls | branchy | sum |
|---|---:|---:|---:|
| Eager reload after every boundary (first version) | — | — | — (real TU static: +44 % instructions) |
| Lazy reload, may-dirty at all merges | **0.51×** | 0.99× | 2.13× |
| Must-dirty at merges | 1.00× | **0.97×** | 2.04× |
| **Final**: loop header = back-edge dirt only; may at other merges | 1.00× | 1.01× | 2.13× |

## 3. Before/after disassembly: `sum` hot loop (stores out of line, VERIFIED)

| Build | Loop body (x64 instructions) | Notes |
|---|---:|---|
| Baseline | 44 | `ctx->gpr[3]` loaded and stored per iteration (`[rsi+0x18]`). CTR decremented in memory (`dec qword ptr [rsi+0x410]`). CR rebuilt via `[rsi+0x400]` load/and/or/store. XER loaded (`[rsi+0x418]`) |
| Promoted | 29 | r3, r4, CR, XER and CTR in registers. The compiler even replaced `bdnz` by a pointer compare (`cmp rbx, 0x203e80`). The CR field update is register-only. No `ctx` access in the loop |

Excerpt (promoted, CR update and loop branch):

```
or   ebp, r12d          ; XER.SO bit kept in r12
and  eax, 0xf0ffffff    ; CR field 1 cleared, in a register
shl  ebp, 0x18
or   ebp, eax           ; new CR, never stored inside the loop
add  rdi, rdx           ; r4 += ...
add  rbx, 0x4           ; r3 += 4
cmp  rbx, 0x203e80      ; CTR loop turned into an end-pointer test
jne  loop
```

Baseline, same work:

```
mov  r10d, dword ptr [rsi + 0x418]   ; XER from ctx
mov  r9d,  dword ptr [rsi + 0x400]   ; CR from ctx
...
mov  dword ptr [rsi + 0x400], r10d   ; CR back to ctx
mov  rcx, qword ptr [rsi + 0x18]     ; r3 from ctx
add  rcx, 0x4
mov  qword ptr [rsi + 0x18], rcx     ; r3 back
dec  qword ptr [rsi + 0x410]         ; CTR in memory
```

## 4. Real MotorStorm lifted code (private validation workload)

### 4.1 Execution time, 24 sampled loop-bearing functions of TU `000` (VERIFIED)

The functions are seeded and sampled. They run in pointer mode with synthetic inputs, and **most take their short paths** (about 20–150 ns per call), so prologue/epilogue and early exits are what is measured, not the loops' steady state. 17 of the 24 ran; 7 faulted identically in both builds on the synthetic pointers. 0 transcript mismatches in every configuration.

| Store lowering / policy | Geomean promo vs base | Min | Max |
|---|---:|---:|---:|
| Out of line, drop clean (default) | 0.987× | 0.93 | 1.02 |
| Out of line, `--promote-store-sync` | **0.997×** | 0.97 | 1.12 |
| Inline stores, keep | 0.977× | 0.82 | 1.02 |
| Out of line, drop clean, `PPU_COLD_CALLS` | 0.962× | 0.66 (cv 22 %, load noise) | 1.07 |
| Out of line, sync, `PPU_COLD_CALLS` | 0.995× | 0.95 | 1.04 |
| Inline, keep, `PPU_COLD_CALLS` | not run (stopped: cold calls had shown no gain) | | |

**Cause of the short-path cost (VERIFIED, disassembly of `func_001B4820`):**
- The promoted build saves 8 GPRs in the prologue instead of 3, and its frame is larger.
- Values held across out-of-line store calls, or across the cold slow-path calls, need callee-saved registers, and the prologue pays for them on every entry, including entries that exit early.
- `--promote-store-sync`, which keeps no local live across a store call, removes most of that.
- The `preserve_most` slow-path thunks (`PPU_COLD_CALLS`) did not help here.

### 4.2 Whole TU `ppu_recomp_006.cpp`, static (VERIFIED; 759 functions, 74,581 guest instructions)

| Build | x64/guest | ctx operands/guest | Stack operands | Object | Compile |
|---|---:|---:|---:|---:|---:|
| Baseline, stores out of line | 8.43 | 1.55 | 6,957 | 4.18 MB | 25.3 s |
| Promoted (default policy) | 10.46 | 2.11 | 83,735 | 5.02 MB (+20 %) | 34.5 s (+36 %) |
| Promoted, `--promote-store-sync` | 9.87 | 2.09 | 46,153 | 4.77 MB (+14 %) | 31.5 s (+25 %) |

Lifted source: 5.68 MB → 8.36 MB (default) / 8.16 MB (sync). Static counts include the cold blocks the pass adds: write-backs inside each trace-hook guard at every label, and edge loads. They are not execution cost. Compile time and object size are real costs.

## 5. Conclusions (labels)

- **VERIFIED:** promotion is exact on every test, and it speeds up loop code without calls by 1.15–2.13× (synthetic kernels).
- **VERIFIED:** on the sampled real game functions with synthetic inputs, promotion is neutral at best (0.997× with `--promote-store-sync`), because their measured paths are short and call-dense.
- **HYPOTHESIS:** in game the gain depends on how much frame time is spent in long call-free loops. Even the best real-code configuration does not support T186's projected 20–27 fps from improved PPU code generation. **No FPS gain is claimed.**
- **30 fps** stays the practical target; nothing here supports 60 fps.

## 6. Proposed in-game A/B (needs authorization; not run)

1. Rewrite a copy of the lift with `ppu_regpromo.py ... --stats` and the sync policy (about 25 min, ESTIMATE). Build with the T183 recipe (about 11 min).
2. A/B on the same runner as T187: arm P (T184 env) on the baseline exe against arm R (the same env) on the promoted exe, P R P R.
3. Metrics: frame time, the PPU main thread's on-CPU time from `[PT]`/sampler, and `[rsx-frame-perf]`.
4. Accept R only above P-to-P noise, with identical race progress and frame content.

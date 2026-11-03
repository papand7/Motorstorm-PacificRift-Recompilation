# T189: performance results (all offline; no game launch)

**Method.**
- Arms A/B/C/C2/D as in `REGISTER_PROMOTION_COMPARISON.md`, built from the same lifted source with the game's lifted-TU flags (clang-cl 23.1.3, `/O2 /Ob2 /EHsc -std:c++20 -MD -fno-strict-aliasing -fwrapv`).
- Processes are interleaved A B C C2 D per round. Each process reports the best of `reps` repetitions; the median over rounds is shown, with cv = stdev/mean over rounds.
- Every arm's transcript is identical before it is timed.
- The machine was not idle (other sessions, Blender, Edge). Interleaving spreads that load over all arms.

Labels:
- **VERIFIED offline speedup:** measured time, low cv.
- **Static:** instruction and operand counts.
- **Unverified projection:** anything about the game.

## 1. Synthetic kernels (public, `tools/bench_ppu_fourarm.py --runs 5 --reps 9 --random 2`; fixture runtime)

| Kernel | A ms (cv) | B/A | C/A | C2/A | D/A | D/B |
|---|---|---:|---:|---:|---:|---:|
| sum | 2.328 (0.2 %) | 1.15× | 2.49× | 2.50× | **3.82×** | 3.32× |
| transform | 0.890 (1.6 %) | 0.99× | 1.01× | 0.97× | **1.51×** | 1.53× |
| chase | 1.065 (0.4 %) | **0.91×** | 1.03× | 1.03× | 1.04× | 1.14× |
| fpdot | 0.836 (0.4 %) | 1.00× | 1.10× | 1.05× | **2.17×** | 2.16× |
| calls | 0.295 (0.1 %) | 1.00× | 1.00× | 1.00× | 1.00× | 1.00× |
| branchy | 1.758 (1.1 %) | 1.04× | 1.00× | 1.00× | 1.23× | 1.18× |
| struct | 1.440 (0.1 %) | 1.07× | 1.00× | 0.93× | **2.22×** | 2.07× |
| random 1001 | 0.228 (0.5 %) | 1.03× | 1.03× | 1.21× | 1.28× | 1.24× |
| random 1002 | 0.109 (0.6 %) | 1.01× | 0.98× | 1.07× | 1.09× | 1.08× |

The cv was ≤ 3.9 % in every cell.

Static x64 per guest instruction, A → B → C → D (`sum`): 5.7 → 8.5 → 5.9 → 8.2. The inline fast paths add static instructions while time drops; static count is not the measure.

## 2. Real MotorStorm lifted functions against the real T189 runtime (VERIFIED; private `generated/analysis/t189/tools/bl4.cmd`, `run_bl4.py`)

- Harness: T152's `bench_lifted.cpp` (T152 inputs: a 16 MiB data window), linked with the real `runtime/ppu/ppu_loader.cpp` of T189, with `PS3_VM_STORE_INLINE=1`.
- 5 interleaved rounds × 3 repetitions × 2 calls.
- The final guest state hash was identical in all four arms.

| Function | A ms/call | B/A | C/A | D/A | D/B | cv max |
|---|---:|---:|---:|---:|---:|---:|
| `func_0096B648` (16/32-bit loads and stores) | 154.9 | **1.48×** | 1.02× | **1.51×** | 1.02× | 4.7 % |
| `func_002D0D94` (CR/branch heavy, memory walk) | 568.9 | 1.05× | 1.04× | 1.01× | 0.96× | 10.5 % |

- `func_000C9678` (T152's third function) crashes the real runtime on these inputs in **every** arm, so it was excluded.
- On the fixture runtime it exits early (cv 67–113 %), and was not used there either.

The 1.48× matches T152's own −31 % measurement of `func_0096B648`.

## 3. Real functions, fixture runtime, short paths (VERIFIED; private `real_fourarm.py`, pointer-mode inputs)

| Sample | Timed (robust, cv ≤ 5 %) | B/A | C/A | C2/A | D/A | D/B | Mismatches |
|---|---|---:|---:|---:|---:|---:|---:|
| TU `000`, 24 functions with loops | 17 (13) | 0.97× [0.93, 1.01] | 0.99× [0.98, 1.00] | 1.00× [0.92, 1.06] | 0.95× [0.81, 1.03] | 0.98× | 0 |
| TU `003`, 24 functions with loops | 21 (17) | 0.95× [0.87, 1.00] | 0.99× [0.91, 1.12] | 0.98× [0.82, 1.15] | 0.98× [0.82, 1.15] | 1.03× | 0 |

- **Regression found:** in this fixture, inline stores cost 3–5 % on short paths. The fixture's out-of-line writer is a bare `bswap`+`memcpy` (about 8 instructions), so the inline gate (one global, one table byte, the in-page check) is not cheaper than the call there. The real writer is about 30 instructions plus the call (T186), as §2's real-runtime result shows.
- **UNVERIFIED:** whether short real paths gain or lose with the real runtime. The in-game P-vs-B arms settle it (`NEXT_ARCHITECTURE_STEPS.md` §1).

## 4. Size and compile time (VERIFIED)

| Sample | A obj / compile | B | C | D |
|---|---|---|---|---|
| T152's 3 functions | 119,310 B / 0.73 s | 115,544 B / 0.74 s | 133,094 B / 0.87 s | 133,681 B / 0.85 s |
| TU `000` sample (24 functions) | 215,784 B / 0.96 s | 213,418 B / 1.08 s | 240,002 B / 1.10 s | 263,269 B / 1.31 s |
| TU `003` sample (24 functions) | 170,866 B / 0.81 s | 165,765 B / 0.80 s | 187,985 B / 0.86 s | 197,679 B / 0.94 s |

- Inline stores do not grow objects: fewer call relocations offset the inline fast paths.
- Promotion grows them 10–22 %, and compile time 6–36 % (T188 measured +25–36 % on a whole TU).

## 5. Summary

| Claim | Status |
|---|---|
| Inline stores speed up a real store-heavy game function 1.48× against the real runtime | VERIFIED offline |
| Inline stores unlock promotion in loop code (D/B up to 3.3×) | VERIFIED offline, synthetic |
| Promotion on top of inline stores helps real game functions | **Not shown:** D/B 0.96–1.03× |
| Default backend unchanged | VERIFIED: byte-identical x64 |
| Any FPS change | not measured; needs the in-game A/B |

# T158: `--chain-chunks` validation for the Havok task images

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. No game was launched. All timings are offline, from the function-level harness on synthetic states; they are not game FPS.

## 1. Sources and builds

| Item | Value |
|---|---|
| ps3recomp | `agent/t158-spu-aot-codegen`, worktree `ps3recomp-t158-spu-aot`, from **`756c1e1`** (T156 tip; ancestry `756c1e1` → `031bbb5` → `e8e972a` (T154) → `2a764e1` (T153), VERIFIED with `git merge-base --is-ancestor`). Runtime unchanged by T158; one test commit `7a88b53` |
| Root | `agent/t158-spu-aot-report`, worktree `root-t158`, from `97c5f13` (T156 reports) |
| Port | `port-t158`, a copy of `port-t156` |
| C0 exe | `build/motorstorm-t156/MotorStormPacificRiftRecomp.exe` (ps3recomp `756c1e1`, no lifter arguments), 411,172,864 bytes, SHA-256 `04e64386829877c79fa86d6b0a4127cae6147deb8d360500fa324d41e2b68e3f` |
| C1 exe | `build/motorstorm-t158-c1/MotorStormPacificRiftRecomp.exe`, 410,777,600 bytes, SHA-256 `2a0403201a3571d708e2be33338571f5bf3f965b4261b07baa3106e5eb851f08` |
| C1 build | `tools/build_t158.cmd c1` = the T156 recipe (`MSPR_WWS_AOT=ON`, T81C reloc lift, staging PPU lift, SSE4.1, `PORT_SPU_AVX2=OFF`) plus `-DPS3RECOMP_SPU_LIFTER_IMAGE_ARGS=<image>=--chain-chunks` for the four Havok images only (log `logs/build_c1.txt`, rc 0) |

`--chain-chunks` is applied per image, not globally, so Bink and the other 22 task images keep their T156 lift. The Wws job modules are `--reloc` lifts and cannot take `--chain-chunks` (the lifter refuses the combination).

## 2. The option changes exactly the Havok code (VERIFIED)

- A fresh C0 generation (`build_spu_workloads.py`, no arguments) is byte-identical to the T156 build's `generated_spu` for all 26 images, and `spu_workloads.c` (the registry, SHA-256 `fc10916d…59f2`) is identical in C0 and C1.
- C1 changes exactly four `spu_recomp.c` files:

| Image | Role | C0 `spu_recomp.c` SHA-256 | C1 `spu_recomp.c` SHA-256 |
|---|---|---|---|
| `spu_45c1b7bf…` (341580667) | wave 1, solver | `837dfac9…337b` | `ec5eeebf…9be4` |
| `spu_d51c6ceb…` (491898574) | wave 2, collide | `8666947d…f829` | `3c0d580f…f5f6` |
| `spu_266e45a8…` (308733018) | wave 3, raycast | `868765fa…8e3f` | `3ac9de21…347a` |
| `spu_83451471…` (406081863) | wave 4, animation | `481586bb…77bc` | `9c91cee4…8b1f` |

Full hashes are in `HAVOK_CODEGEN_PROFILE.md` §1.

## 3. Static effect

| Image | C0 block exits through the trampoline | C1 block exits through the trampoline | C1 chained transfers (of which backward) | brsl call brackets (unchanged) | C1 groups | `.text` C0 → C1 (race flags) |
|---|---|---|---|---|---|---|
| solver | 1,270 | 108 | 826 (336) | 255 | 90 | 2,006,483 → 1,908,166 B (−4.9 %) |
| collide | 2,562 | 120 | 1,744 (698) | 529 | 169 | 2,721,227 → 2,599,844 B (−4.5 %) |
| raycast | 2,263 | 118 | 1,468 (677) | 502 | 144 | 2,710,252 → 2,547,134 B (−6.0 %) |
| animation | 1,181 | 41 | 877 (263) | 194 | 88 | 1,507,989 → 1,475,078 B (−2.2 %) |

- Sizes are of the build's own objects (`llvm-size`), so the result is not "larger code is faster": C1 is smaller.
- What a chained transfer still does: store the guest pc, check `SPU_CHAIN_OK` (chaining armed, lockstep off, no pending interrupt with volatile `event_status`, context not flow-traced), count the step; a backward transfer also spends the group's budget of 256, so a guest loop still returns to the drain every 256 iterations.
- Chaining is active in the game configuration (VERIFIED from source): `g_spu_chain_on` is armed on the first hop unless `SPU_NO_LS0_END`, `SPU_EXITTRACE`, `SPU_STEPTRACE`, `SPU_JOBDRAIN`, `SPU_PCHIST`, `SPU_NO_CHAIN`, `SPU_TAILRET=1` or a stack-reset entry is registered. None is set by the T154/T156 runner environment, and no game or runtime code registers a stack-reset entry.

## 4. Differential correctness (VERIFIED offline)

Harness: `tools/hvkdiff/` (`hvkdiff.c`, `hvk_ref.c`), lifts from `tools/hvk_lift_pair.py`, built by `tools/hvk_build.py` with the race flags (`clang -O2 -msse4.1 -fno-strict-aliasing -fwrapv -DSPU_USE_DISPATCH_MT`) and the real SPU runtime.

**How it works.**
- Every call target of each image (109 / 160 / 139 / 98 functions) is entered from random states:
  - the image's own ELF segments in LS;
  - a random work area above the image: mixed-magnitude floats, zeros, small integers, pointers, raw bit patterns (NaN, inf, denormal);
  - random registers, pointer arguments into the work area, a stack, r0 = a sentinel return address.
- The **reference** is the runtime's SPU interpreter (`spu_step`, independent of the lifter's control flow).
- It refuses cases outside the isolated-function model: channel access (DMA, mailboxes, decrementer), stop / conditional halt, a pc outside the code, an indirect jump to an unlifted address, a return not to the innermost link, and stores into the image's code (self-modification, which the interpreter would follow and lifted code by design does not).
- Each accepted case runs through `spu_run_with_halt` as C0 and as C1.
- **All 128 registers and the whole 256 KiB LS must equal the interpreter's**, and the C0 and C1 step counts must be equal.

**Result** (`logs/hvkdiff_diff.txt`, 3 seeds × 40 cases per function):

| Image | cases tried | accepted | functions covered | SPU instructions executed | drain hops C0 → C1 | mismatches |
|---|---|---|---|---|---|---|
| solver | 13,080 | 5,174 | 63 of 109 | 7.88 M | 574,759 → 5,910 (−99.0 %) | **0** |
| collide | 19,200 | 8,386 | 99–101 of 160 | 12.96 M | 856,614 → 10,280 (−98.8 %) | **0** |
| raycast | 16,680 | 6,949 | 76–77 of 139 | 0.70 M | 45,422 → 7,328 (−83.9 %) | **0** |
| animation | 11,760 | 5,044 | 69–71 of 98 | 14.26 M | 1,067,412 → 9,242 (−99.1 %) | **0** |
| **total** | 60,720 | **25,553** | | **35.8 M** | | **0** |

Step counts were equal in every case.

**Coverage.**
- Covered: branch targets, conditional branches, function entry and return, calls, computed branches to lifted entries, float and SIMD operations (`fa`/`fm`/`fma`/`fi`/`frest`/`frsqest`, shuffles, rotates) including NaN / infinity / denormal operands, unaligned addresses (LS access masks to quadwords like the hardware).
- Excluded by construction: the DMA, atomic and job-completion paths, which are channel operations.
- `--chain-chunks` does not change those statements: a `spu_wrch`/`spu_rdch` is lifted identically in C0 and C1. The chained transfer around it is covered by the existing `test_spu_chain.c` fixture, which has an MFC DMA per iteration of a chained loop and an interrupt raised inside a chained loop.
- One LS base per image: the four Havok images are absolute (non-relocatable) lifts, so "multiple LS bases" does not apply to them.

**Investigated and explained during development (not lifter defects).**
- An earlier harness version reported a few mismatches in both C0 and C1 against the interpreter.
- Each was a case whose random pointer stored into the function's own code (for example LS 0x0F690 from pc 0x0F6D8). The interpreter then executes the modified instruction; the static lift executes the original.
- After the code-store refusal was added, all 12 runs show 0 mismatches.

**The harness detects chaining errors** (`tools/hvk_mutants.py`, `logs/hvk_mutants.txt`; one edit in the hot solver group `0x7C48`):

| Mutant | Result |
|---|---|
| m1: backward chained jump to the wrong label | caught: register mismatch and step-count difference |
| m2: chained conditional inverted | caught: mismatches, step differences, then a runaway case crashes the process |
| m3: one `a` replaced by `sf` | caught: register mismatches, then a crash |
| m4: a chained transfer that skips its step count | caught: 604 step-count differences |

**Runtime fixture test.**
- `tools/test_spu_chain_runtime.py` (new, `7a88b53`) builds and runs `runtime/spu/tests/test_spu_chain.c`, which had no driver and so ran in no suite.
- It covers base / chain / ind variants through the real drain: forward and backward transfers, nested loops, calls, an indirect branch, an interrupt inside a chained loop, a DMA per iteration, a job ending at LS 0, a stop.
- Result: **353 / 0 plain, 348 / 0 diag**. The lifter output is deterministic.

The full regression suite is in `SPU_AOT_OPTIMIZATION.md` §6.

## 5. Performance (PARTIAL: offline, synthetic states)

Paired C0/C1 timing of the same accepted cases (`logs/hvk_bench_c0c1.txt`, seeds 11–13, 20 cases per function, best of 9 alternating C0/C1 runs per case, the measured fixed cost of one `spu_run_with_halt`, about 0.93–1.17 µs, subtracted):

| Image | C0 ns / SPU instruction | C1 ns / SPU instruction | C1 / C0 time, all cases (mean, range over 3 seeds) | C1 / C0, cases ≥ 20,000 SPU instructions |
|---|---|---|---|---|
| solver | 1.65 | 1.11 | **0.670** (0.627–0.731) | 0.363 (0.233–0.577) |
| collide | 0.70 | 0.46 | **0.660** (0.563–0.736) | 0.580 (0.460–0.719) |
| raycast | 2.06 | 1.83 | **0.888** (0.879–0.894) | no long cases |
| animation | 0.94 | 0.62 | **0.647** (0.578–0.753) | 0.500 (0.474–0.533) |

Reading the numbers:
- Five collide harnesses in parallel, one per core like a five-task wave (seeds 11–15, `logs/hvk_bench_parallel5.txt`): C1 / C0 = 0.51–0.72 overall and 0.40–0.69 on long cases. C0 slows more than C1 under parallel load.
- Absolute ns per instruction moves by up to ±50 % between sessions with CPU clocking (solver C1 measured 1.11 and later 0.73). The ratios are paired within a run and stay put.
- Raycast's short accepted cases leave the remaining fixed cost visible, hence its higher ns per instruction and smaller gain.
- The cause is the drain hop (`HAVOK_CODEGEN_PROFILE.md`): in C0, 35–73 % of samples are the drain loop and the per-hop hooks. In C1 those fall below 2 %.

## 6. What this establishes

- VERIFIED offline: `--chain-chunks` changes exactly the four Havok modules, keeps every guest-visible register and LS byte and every step count identical to the interpreter on 25,553 cases, and removes 84–99 % of drain hops.
- PARTIAL: on the translated Havok functions it cuts execution time by **about a third** (C1 / C0 ≈ 0.65–0.67 for solver, collide and animation; 0.89 for raycast).
- HYPOTHESIS for the game: applied to the ≈ 16.5 ms of lifted solver/collide execution per physics frame (T156), that is ≈ 5–6 ms less per frame (range 4.4–7.2 ms over the solver and collide seed range 0.563–0.736).
  - Not included: the DMA/atomic time inside those tasks, which the harness cannot see, and the real operand and branch mix.
  - Only the authorised A/B (`GAME_AB_PLAN.md`) can establish the in-game effect.

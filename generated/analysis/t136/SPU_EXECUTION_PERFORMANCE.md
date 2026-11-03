# T136: SPU execution-engine performance (2026-10-28, offline)

No game build, no launch, no merge or push. No other agent's worktree modified. No change to DMA, MFC, reservations, channels, SPURS scheduling (T123B) or the RSX/D3D12 renderer.

- Worktree `ps3recomp-t136`, branch `agent/t136-spu-execution-performance`, base **`e48f279`** (T123 tip; the T123B branch shares it).
- Commits: `6bec559`, `25b304c`, `78fcf2b` (§5).
- Private tools and logs: `generated/analysis/t136/{tools,logs}`.

## 1. SPU execution architecture (VERIFIED from source and `build/motorstorm-t109-aot`)

| Path | What runs it | Notes |
|---|---|---|
| Whole-image lifted tasks (Havok solver `341580667`, collide `491898574`, raycast `308733018`, animation `406081863`, 22 more images) | `tools/spu_lifter.py` → `generated_spu/spu_<sha>/spu_recomp.c`, dispatched by content fingerprint (`spu_workload_dispatch_async`, T123 memo) | Lifted **without lifter args**: no `--chain-chunks` (`PS3RECOMP_SPU_LIFTER_ARGS` unset in every `build/*/CMakeCache.txt`). Each basic block is a C function; every direct transfer to another block returns to the drain loop (`g_spu_trampoline_fn`, `spu_drain_call`) |
| WWS job modules (31, relocatable AOT, T109) | `generated/spu_raw/wws_reloc_t81c`, `--reloc` | `--reloc` cannot be combined with `--chain-chunks` (lifter refuses) |
| WWS policy module | `generated/spu_raw/wws_job_pm` | small, branchy, few float ops |
| Interpreter (`spu_interp.c`) | fallback | only the interrupt vector of image `1297305682` in race runs (T123). Uses the same `spu_helpers.h` |
| Registers | `ctx->gpr[128]` in memory, host-LE words | every instruction is a `ctx->gpr[n] = spu_op(...)` store |
| LS access | `spu_ls_read128/write128`: mask, 4 × bswap32, one diag-gate branch | already inlined and lean (0.3 / 0.5 ns) |
| DMA / atomics / channels / SPU→PPU notify | `spu_wrch`/`spu_rdch` → `spu_dma.h`, `spu_channels.c`, `spu_coherency.c` | synchronous inside the block; **not touched** (T135 owns reservation coherency) |
| Instruction semantics | `runtime/spu/spu_helpers.h`, header-only, always inlined | dispatch per ISA: NEON > AVX2 > SSE (x86 perm) > scalar |

**Compiler and ISA level of the race build (VERIFIED, `build.ninja`):** lifted SPU TUs get `/O2 -O2 -msse4.1 -fno-strict-aliasing -fwrapv`. **`PORT_SPU_AVX2` is OFF**, so every helper with only a NEON/AVX2 vector form ran its scalar per-lane form in game.

## 2. Interpreter / AOT coverage

- Wws jobs: AOT on every job (T123, 64 `[spu-reloc] … AOT`, no refusals). VERIFIED (T106 D run).
- Havok tasks and the other 22 task images: statically lifted, native. VERIFIED (registered in `spu_workloads.c`).
- Interpreter: one interrupt vector only. VERIFIED (T123 log scan). Its helper calls share this milestone's speedups.
- T131 could not prove a complete identity match against the LS snapshot. This milestone needs no identity: it changes instruction semantics helpers used by every path, not module dispatch.

## 3. Ranked instruction-level bottlenecks

Static counts (`tools/opfreq.py`; `logs/opfreq_havok.txt` for the 4 Havok images, `logs/opfreq_wws.txt` for 31 WWS modules) × measured ns per op (`logs/ops_median.md`, median of 3 × best-of-15, ordinary normal operands, clang-cl, race flags).

| Rank | Op(s) | Static uses (Havok + WWS) | Before | After | Class |
|---|---|---|---|---|---|
| 1 | `fm` | 2,359 + 1,766 | 5.19 ns | 2.42 | VERIFIED (bench) |
| 2 | `cwd` | 2,009 + 2,822 | 2.95 | 0.28 | VERIFIED |
| 3 | `fma` / `fms` / `fnms` | 1,955 + 1,869 (+ fms) | 6.75–6.91 | 4.33–4.45 | VERIFIED |
| 4 | `fa` / `fs` | 2,473 + 1,111 | 6.49 / 6.63 | 3.27 / 3.34 | VERIFIED |
| 5 | direct block transfers (trampoline hops) | 7,316 + 8,089 sites | ~5 ns per hop (Bink chainbench, `docs/UPSTREAM_INTEGRATION.md`) | not changed (build option, §5.4) | PARTIAL |
| 6 | `fi` | 330 + 224 | 3.66 | 1.25 | VERIFIED |
| 7 | `csflt` | below the top 60 | 2.95 | not changed | VERIFIED cost, low use |
| – | `lqd`/`stqd`, `shufb`, `rotqby*`, `shlqbyi`, `selb`, `a`/`ai`, `fcgt`, `frest` | the bulk of instructions | 0.14–1.1 | already vector/lean; not changed | VERIFIED |

Static-mix model (`tools/static_estimate.py`, unmeasured ops 0.3 ns, hops and calls 5 ns): changed ops were **43–56 % of the estimated execution cost**, and the new code is **18–24 % cheaper** (solver 24.1 %, collide 18.1 %, raycast 20.3 %, animation 22.3 %, WWS 18.8 %). This is HYPOTHESIS-grade: static counts, not a dynamic profile.

## 4. Native implementation evidence

- `spu_cwd` on x86 called `spu_cwd_ref`, the 16-byte scalar loop: only the NEON branch had a vector form. `cbd/chd/cdd/cwx` already used the SSE compare-and-blend `spu__x_gen`. VERIFIED (source).
- `spu_fa/fs/fm/fma/fms/fnms`: vector forms existed for NEON and AVX2 only. Under `-msse4.1` they were `SPU__SF_V2/V3` per-lane loops: a double fast path plus exact integer fallback, about 25 instructions and several branches per lane. VERIFIED (source and bench).
- Code size (`logs/tu_lifted_final.txt`, real lifted TUs, race flags, `.text`):
  - solver 1.32 → 2.01 MB, collide 1.97 → 2.72, raycast 1.90 → 2.71, animation 1.04 → 1.51;
  - WWS modules 1.12 → 1.39 and 0.46 → 0.56;
  - the opt-in AVX2 build of the solver is 1.886 MB (and byte-identical before and after T136), so inline vector float costs about the same with AVX2.
- `fma` library calls in the lifted objects: 0 before and after.
- No new warning kinds: +12 per lifted TU, all existing kinds; runtime TUs rc=0 with identical counts.

## 5. Optimization details

1. **`6bec559`: x86 `cwd`.** `spu_cwd(a, i7) = spu_cwd_pos(a + i7)` under `SPU_X86_PERM`, the tested SSE generate-control. 2.95 → 0.28 ns.
2. **`25b304c`: SSE4.1 vector single-precision arithmetic.** A port of the AVX2 path to 128-bit:
   - lanes 0,1 / 2,3 widen to two `f64x2` (exact), with the same operation;
   - range, zero and 24-bit-boundary checks run on the doubles' 32-bit halves gathered with `shufps`, so no SSE4.2 64-bit compare is needed;
   - same lane rules and the same exact per-lane fallback (`noinline, cold`);
   - explicit intrinsics, so nothing is contracted;
   - like the AVX2/NEON forms, it relies on round-to-nearest MXCSR. VERIFIED: no runtime or port code changes MXCSR (grep for `_controlfp`, `_mm_setcsr`, `fesetround`, `_MM_SET_*`);
   - dispatch order NEON > AVX2 > SSE4.1 > scalar. AVX2 builds are unchanged. `-DSPU_SCALAR_FLOAT` restores the scalar path.
3. **`78fcf2b`: SSE4.1 `fi`.** The 33-bit fixed-point magnitude becomes a 32-bit difference plus borrow (`_mm_mullo_epi32`, `_mm_max_epu32`, `_mm_blendv_epi8`). 3.66 → 1.25 ns. The loop stays as `spu_fi_ref`.
4. **Not changed, recommended (build configuration):**
   - **`--chain-chunks` for the non-reloc task images.** VERIFIED offline on the solver (private lift, `generated/analysis/t136/chain/solver2`): direct trampoline sites **1,282 → 217**, and it compiles with race flags (rc=0, `.text` 1.92 MB). The runtime support (`SPU_CHAIN`, budget, interrupt guard) is in the tree and was validated on Bink (5.2 → 1.1 ns per transfer, `test_spu_chain.c`). Activating it changes the lift of every task image, so it needs a game build and an A/B. HYPOTHESIS on gain.
   - **`PORT_SPU_AVX2=ON`:** the AVX2 forms are 0.2–0.8 ns faster than the new SSE4.1 forms and `cflts`/`csflt` 2–4× faster, but the exe then requires AVX2. The target (Radeon 890M, Zen 5) has it. That is a distribution decision, not made here.
5. **Investigated, not changed:**
   - LS access (already one load + bswap + gate, 0.3/0.5 ns);
   - `shufb`/rotates (already `pshufb`);
   - register spills: registers live in `ctx->gpr` by design. Keeping them in host registers needs a lifter register cache, as in `docs/BINK_PERFORMANCE_BACKLOG.md` `--cache-regs` (out of scope, high risk);
   - `csflt`/`cflts` (low use).

## 6. Differential test results (`logs/test_spu_exec_sse_final.txt`, `logs/suite_new.txt`)

| Test | Coverage | Result |
|---|---|---|
| `test_spu_float_neon.c` (now also x86 SSE4.1) | 4M random quadwords (ordinary, bottom/top of range, extended range, ±0, exponent-0 fractions, cancellation pairs); 2M fma boundary cases (2.4M lanes rounded onto a 24-bit boundary, 5.6M exact sums); 2M zero-lane cases (6.8M lanes with a zero operand); `fma(1,1,-2^-60)`; `dfa` stays round-to-nearest | **bit-identical**: SSE4.1 arm, AVX2 arm, scalar arm (`SPU_SCALAR_FLOAT`) |
| `test_spu_gen_controls.c` (new) | cbd/chd/cwd/cdd/cbx/chx/cwx/cdx; every signed 7-bit immediate; random and edge words incl. 32-bit wraparound; junk lanes | 128,809,660 cases, 0 mismatches |
| `test_spu_fi.c` (new) | 12M random + 12M edge-field quadwords (exponent 0/1/2/127/254/255, base/step/Y extremes, signs, ignored-bit junk) | 96M lanes, 0 mismatches; 9.8M normalised, 980k underflow to +0 |
| Mutants (`generated/analysis/t136/mutant`) | (1) TwoSum boundary check removed, (2) zero result keeps its sign, (3) fa gap limit 29 → 39 | (1) 525,651 and (2) 208,189 mismatches: **caught**. (3) not caught: an equivalent mutant (truncation hides double rounding at those gaps); production keeps 29, the same as the scalar/AVX2/NEON paths |
| `test_spu_helpers.c` (unit vectors) | ISA vectors incl. cwd/shufb layouts | 70/70 on T123 and T136 trees |
| Lifted-style kernels (`tools/bench_kernel.c`) | xform, recip (frest+fi+fnms+fma), scalar store, dot | output checksums identical base vs new |
| Regression suite (`tools/run_suite_t136.py`) | the T123 set + `test_spu_exec_sse` + LS-inline/alias, sdcrz, smc, disasm, interpreter, SPURS stress/concurrency, chain-chunks, program pipeline | **30 PASS / 11 SKIP (POSIX-only or no fixture) / 0 FAIL** |

- Reservations and SPURS wakeups: no file on those paths changed (`git diff --stat e48f279..78fcf2b`: `spu_helpers.h`, 3 tests, 1 driver). The SPURS stress, concurrency, kick-wake and LR-race tests pass.

## 7. Performance comparisons (offline, synthetic data; not game FPS)

Per op (ns, `logs/ops_median.md`):

| | fa | fs | fm | fma | fms | fnms | fi | cwd |
|---|---|---|---|---|---|---|---|---|
| race build before (SSE4.1 scalar) | 6.49 | 6.63 | 5.19 | 6.77 | 6.91 | 6.75 | 3.66 | 2.95 |
| **T136 (SSE4.1)** | **3.27** | **3.34** | **2.42** | **4.33** | **4.45** | **4.43** | **1.25** | **0.28** |
| AVX2 build (`-mavx2`, before) | 3.02 | 3.11 | 2.18 | 3.63 | 3.62 | 3.67 | 3.43 | 3.00 |

- Pessimistic "mixed" operands, where ~2/3 of quadwords hold an exponent-255 or denormal-pattern lane: fa/fs/fm ±3 %, **fma family +11 % (6.6 → 7.4 ns)**, because of wasted vector work before the exact fallback. Zeros are not in this class (they stay on the vector path).

Lifted-style kernels (ns per iteration, median of 3 runs × best of 25; `logs/bench_kernel.txt`):

| Kernel | Before | After | Change |
|---|---|---|---|
| xform (lqd, 4 shufb, fm + 3 fma, stqd) | 36.7 | 27.1 | −26 % |
| recip (frest, fi, fnms, fma, fm, fs) | 42.0 | 30.6 | −27 % |
| dot (2 lqd, fm, 2 rotqbyi + fa, fcgt, selb) | 35.4 | 18.4 | −48 % |
| scalar store (cwd, lqd, shufb, stqd) | 9.0 | 2.3 | −75 % |

- Instructions per second: the xform kernel is 14 SPU instructions per iteration, about 0.38 → 0.52 G SPU instr/s per host core. HYPOTHESIS for real code: the ctx-memory register model and hop overhead dominate elsewhere.
- Cache behaviour: hot loops gain size but stay far below L1i. Total `.text` +23–52 % (§4) is a whole-image figure. Not measurable offline. PARTIAL.
- Memory bandwidth: unchanged (no LS or DMA path changed).

## 8. Realistic game impact and runtime validation plan

**Estimate (HYPOTHESIS):**
- T106 D1, per frame: SPURS lane busy 68 ms of CPU over 5 lanes (13.7 ms each), and 25 Havok tasks in 4 waves inside PRE (40.6 ms wall).
- If the static-mix model holds, lifted SPU execution gets about 15–24 % cheaper. That is roughly 10 ms of SPU CPU per frame across the lanes, and a few ms off each Havok wave.
- **No FPS change is expected while the frame is RSX-bound** (80 ms ref wait, T106/T123).
- After T119/T122 remove that bound, PRE becomes the critical path. The upper bound is then about 20 % of PRE's SPU-execution share (≤ ~8 ms of 40.6 ms); the realistic gain is lower, because PRE also holds dispatch, DMA and the frame thread's waits.
- No FPS claim is made from these numbers.

**Runtime A/B (prepared, not run; needs authorization):**
1. Build the AOT exe like `t106/ab/build_t109_aot.cmd`, once from `e48f279` (A) and once from `78fcf2b` (B). Renderer, shader cache, lanes (guest maxContention 5), `PS3_SPU_FP_CACHE` and the T123/T123B switches are identical in both.
2. Optional C: B configured with `-DPS3RECOMP_SPU_LIFTER_ARGS=--chain-chunks` (task images). Optional D: B with `PORT_SPU_AVX2=ON`.
3. Same race and seed, window visible, order A B B A (then C, D), ≥ 60 s steady race each. Env `SPURS_BUSY_MS=1000 RSX_FRAME_PERF=12,10 PS3_SPU_WWS_AOT=1`.
4. Measure:
   - fps and frame interval p50/p95/p99;
   - PRE/emit/spin (`ab_analyze.py`);
   - Havok wave durations (`task_phases.py`);
   - `[spurs-busy]` busy ms per lane;
   - process CPU (`performance.json`).
5. Validity gates: 21 jobs and 25 tasks per frame; no new NOSYS, spu-depth, watchdog or `[spu-int]` lines; identical race outcome; physics visually unchanged. Bit-exactness is covered offline, so any behavioural difference is a failure.

## 9. Integration dependencies

- Files: `runtime/spu/spu_helpers.h`, `runtime/spu/tests/{test_spu_float_neon,test_spu_gen_controls,test_spu_fi}.c`, `tools/test_spu_exec_sse.py`. **No other agent branch changes `spu_helpers.h`** since its merge base (VERIFIED, `git log`).
- No overlap with:
  - T123B (`cellSpurs.c`);
  - T121 (`sys_timer.c`);
  - T119/T122 (renderer);
  - T131–T133 (no SPU runtime commits).
- Order: independent. It applies on T123 (`e48f279`) alongside T123B. The A/B is most informative after T119/T122 (see §8).
- `--chain-chunks` and `PORT_SPU_AVX2` are build switches in `port*/CMakeLists.txt` / cache; neither is changed here.

## 10. Remaining limitations

- No dynamic SPU profile: the ranking and the 18–24 % figure come from static counts × per-op cost (HYPOTHESIS). The race's real operand mix (how many lanes hit the exact path) is unmeasured.
- Code size grows (+23–52 % `.text` per lifted image). It is measured; the I-cache effect is not measurable offline.
- The fma family is ~11 % slower on quadwords with extended-range or denormal-pattern lanes (rare in normal float data; unmeasured in game).
- The SSE path, like the existing AVX2/NEON paths, assumes round-to-nearest MXCSR on SPU host threads (true today; nothing changes it).
- `--chain-chunks`, AVX2 and a lifter register cache remain the larger levers; all need a game build to validate.
- T131's LS-snapshot identity question is unaffected and still open.

# T158: SPU AOT code generation for the Havok tasks — result and next optimisation

2026-10-29. Offline only; no game launch, no push, no merge. T157's worktree was not read or modified. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## 1. Result

1. **`--chain-chunks` is the optimisation, and it is ready for a controlled game A/B.**
   - Enabled for the four Havok images only (C1), it keeps every guest-visible register, LS byte and step count identical to the interpreter on 25,553 random cases.
   - It removes 84–99 % of drain hops and cuts the translated functions' execution time by about a third: C1 / C0 = 0.670 solver, 0.660 collide, 0.647 animation, 0.888 raycast (`SPU_CHAIN_CHUNKS_VALIDATION.md` §4–5).
   - It needs no runtime change: it is a build configuration of the existing T136 lifter option.
2. **HYPOTHESIS for the game:** ≈ 5–6 ms less translated solver/collide execution per physics frame (4.4–7.2 ms over the measured range) out of ≈ 16.5 ms. The DMA/atomic share is not in that estimate. A synthetic result is not an FPS claim.
3. **No further code-generation change is justified yet.**
   - The one candidate the profile pointed at, hoisting the static part of the chain guard (`--chain-hoist`), was implemented and verified (0 mismatches, `test_spu_chain` 523/0 and 518/0 with a fourth variant).
   - It measured −0.0 to −2.3 % (C2 / C1 = 0.983–0.991 mean per image), within run-to-run noise.
   - Per the brief it is **not committed**. The patch and its test are kept privately in `patches/` as evidence.
4. **The next lever is guest-register caching in the lifter.** In C1, 31–41 % of samples sit in the lifted statement bodies (register traffic through `ctx->gpr`) and only 12 % in block transfers (`HAVOK_CODEGEN_PROFILE.md` §3–4). Details in §4.

## 2. Arms and how to build them

| Arm | What | Build | Exe |
|---|---|---|---|
| C0 / A | T154 Wws AOT configuration, standard SPU lift (T156 exe, all T156 switches off by default) | `t156/tools/build_t156.cmd` (ps3recomp `756c1e1`) | `build/motorstorm-t156`, SHA-256 `04e64386829877c79fa86d6b0a4127cae6147deb8d360500fa324d41e2b68e3f`, 411,172,864 B |
| C1 / B | same sources plus `--chain-chunks` for the four Havok images | `t158/tools/build_t158.cmd c1` (ps3recomp `756c1e1`; `7a88b53` adds only a test) | `build/motorstorm-t158-c1`, SHA-256 `2a0403201a3571d708e2be33338571f5bf3f965b4261b07baa3106e5eb851f08`, 410,777,600 B |
| C2 (offline only) | C1 plus `--chain-hoist` | not built as an exe (not justified) | — |

**Integrating C1 elsewhere.** Configure any port build with:

```
-DPS3RECOMP_SPU_LIFTER_IMAGE_ARGS=spu_45c1b7bf045ac567a973f2b5c1fc62c90cbddebd5a1292296e07fc969a775177=--chain-chunks;spu_d51c6cebd3c35dfadd1c9fddaaa61c6721bd7913112fc1cb24933c8705c2683f=--chain-chunks;spu_266e45a8fd8d59f18fba05552cbaf9074e346188660a29f9fe5f62d9e15fef98=--chain-chunks;spu_83451471f1c85a7dea41d41c2d7936a04eb693d7269e25a24d405ad1a569a7cc=--chain-chunks
```

- It touches only the SPU generation step, so it combines with any runtime branch, including T157's RSX work, without a merge.
- It needs a fresh configure: generation runs at configure time.
- Revert by configuring without the variable.
- Runtime kill switch: `SPU_NO_CHAIN=1` makes every chained transfer a drain hop again (same lift, same results).

## 3. The candidate that was measured and dropped: `--chain-hoist`

**What it does.**
- `SPU_CHAIN_OK` reads three globals per transfer (`g_spu_chain_on`, `g_yz_lockstep_on`, `g_pm_flow_ctx`). They change only at start-up or under a diagnostic.
- The variant read them into a group-local `_spu_cg` on group entry and after every statement that runs runtime code (calls, channels, stop, indirect dispatch).
- It kept per transfer: the volatile pending-interrupt test, the pc, the step count and the backward budget.

**Verification.**
- C1-vs-C2 differential: 12 runs, 25,553 cases, 0 mismatches, equal steps (`logs/hvkdiff_diff_c1c2.txt`).
- Hops: identical apart from the single arming hop of the first run in each process.
- `test_spu_chain.c` with a `hoist_` variant: 523 / 0 plain, 518 / 0 diag, and hoist took exactly the chained variant's hops in every fixture.

**Benchmark** (`logs/hvk_bench_c1c2.txt`):

| Image | C2 / C1 time, mean (range) | long cases |
|---|---|---|
| solver | 0.990 (0.980–1.004) | 1.002 |
| collide | 0.984 (0.977–0.993) | 0.989 |
| raycast | 0.983 (0.959–0.996) | – |
| animation | 0.991 (0.990–0.993) | 0.992 |

**Decision.** Not a significant removable cost. Not committed (no speculative code, no extra maintained mode). Kept as `patches/chain_hoist.diff` plus `patches/test_spu_chain_hoist.py`.

## 4. Remaining bottlenecks and the most promising next compiler-level optimisation

| Mechanism (C1) | Evidence | Lever |
|---|---|---|
| Guest registers in memory: each SPU instruction stores its result to `ctx->gpr` and reloads its operands | 31–41 % of samples in statement bodies outside helpers; ≈ 14 of 60 x64 instructions in the hot loop | **lifter register cache**: within a `--chain-chunks` group, keep live guest registers in C locals (SSA values) and write them back only at group exits, calls, channel accesses and halts. Clang then allocates them to xmm registers. A design already exists: `docs/BINK_PERFORMANCE_BACKLOG.md` (`--cache-regs`, opt-in, `--chain-chunks` groups only). It is not implemented in this lifter |
| Exact single-precision emulation (SSE4.1: widen to double, range checks, cold fixes) | float statements 16–24 %, fallbacks 10–22 % (synthetic upper bound) | **`PORT_SPU_AVX2=ON`** (existing build option, bit-identical per T136 tests): 0.2–0.8 ns per float op faster, but the exe then requires AVX2. A distribution decision; offline-measurable on this harness by building it with `-mavx2` |
| Chain guard, pc and step per transfer | 12 % of samples; hoisting the global loads saved ≤ 2 % | none worth doing now |
| Calls (`brsl` bracket: host call, `spu_drain_call`, `spu_img_restore` out of line) | not visible in these leaf-heavy cases; 255 / 529 static sites | measure in game first (`PS3_SPU_TASK_STATS` arm D), then consider an inline fast path for the common "no pending trampoline" return |
| DMA / atomics | not measurable offline | arm D |
| Per-hop diagnostic hooks in `SPU_DRAIN` (`spu_pchist_tick`, `spu_tailret_enabled`): 12–27 % of C0 time | hit only images that still hop (Wws reloc modules, Bink) | a default change to core dispatch; outside the Havok scope, so not done here. Candidate for a separate, measured Wws task |

**Why the register cache is next.**
- It is the only mechanism in C1 above 30 % of time.
- It benefits every function of every chained image.
- It keeps exact semantics, since it changes only where values live between statements.

**Risks.**
- Every exit path (chain fallback, budget exit, calls, channel ops, `spu_halt` longjmp) must write back.
- The interrupt test must see consistent state.

**Implementation sketch.**
- Lifter: per group, a liveness pass over the group's chunks and a `--cache-regs` emitter.
- Verify with this harness, which compares all 128 registers and LS against the interpreter, plus a mutant set for missed write-backs.
- Size of the prize (HYPOTHESIS): up to the 31–41 % body share of C1 time on these functions.

## 5. Integration-ready commits

| Repository / branch | Commit | Content |
|---|---|---|
| ps3recomp `agent/t158-spu-aot-codegen` | `7a88b53` | `tools/test_spu_chain_runtime.py`: driver for the existing `test_spu_chain.c` (no suite ran it); plain 353 / 0, diag 348 / 0 |
| root `agent/t158-spu-aot-report` | `3ea876b` (this hash note: follow-up commit) | the four T158 reports and `tools/*.py` (harness drivers, runner generator) |

- The C1 configuration needs no code commit (§2).
- The harness C sources (`tools/hvkdiff/*.c`), the lifted copies, the PDB/exe builds and the profiles stay private and untracked: they contain or derive from lifted game code.

## 6. Regression results

- Full suite on `ps3recomp-t158-spu-aot` (`7a88b53`): see `logs/suite_t158.txt` and §7.
- Separate Python tests (not in `run_all`):
  - `tools/test_spu_chain_chunks.py`: 10 / 10 OK;
  - `tools/test_spu_chain_runtime.py` (new): PASS;
  - `tools/test_spu_chain_hoist.py` (private, dropped arm): PASS.
- Wws jobs outside Havok: C1 leaves every Wws module and the other 22 task images byte-identical (§2 of the validation report), and the runtime is unchanged. So no Wws regression is possible from this change offline. In game the Wws time is still measured (`GAME_AB_PLAN.md`).

## 7. Suite

- `t156/tools/run_all_t156.cmd --jobs 3` on `ps3recomp-t158-spu-aot` at `7a88b53`: **139 PASS / 43 SKIP / 2 FAIL** (`logs/suite_t158.txt`, rc 0). VERIFIED.
- The two failures, `test_rt_pool_srv_layout` and `test_vpc_watch`, are the known base failures (T156 at `756c1e1`: 138 / 43 / 2 with the same two).
- The extra PASS is the new `test_spu_chain_runtime`.
- The suite's rewritten `scratch/ppu_conformance*` files were restored afterwards; the tree is clean.

# Bink decode performance backlog

> **Unresolved blocker (2026-10-23): the intro is silent.** Audio is not a decode-performance item, and performance work is paused for it. Every MotorStorm run so far used the runner's `FIRST_FRAME_AUDIO=silent` sink, which opens no Windows audio device. The runner now uses native audio, and ps3recomp-int `8b62438` fixes `cellAudioOutGetDeviceInfo` and adds level and device statistics. Audible output is NOT verified; it needs one authorized run and user confirmation. See `PS3_AUDIO_FAILURE_ANALYSIS.md` and `PS3_AUDIO_IMPLEMENTATION.md`.

**Goal.** Decode the intro faster than 29.97 fps in every stretch, with margin. Any stretch that loses two frames switches the native player to 4:1 until it catches up or resyncs (`BINK_FRAME_PACING_ANALYSIS.md`).

**Where it stands.**
- Run average: 28.42 fps.
- Slowest 256-frame block: 26.34 fps (texsnap).
- Host drift on identical code: up to 12.5 % within a day.

**What that requires.**
- Breaking even on average needs +5.5 %.
- Holding 1:1 through the slowest block needs about +14 % on the same host state; more if the host is in a slower state.

**Profile.** Bink SPU thread, texsnap run, 20 s at 200 Hz, 96.6 % busy:

| Group / symbol | Share | Role |
|---|---:|---|
| `grp_12BB4` | 15.6 % | coefficient symbol handlers |
| `grp_10200` | 15.3 % | 8x8 IDCT |
| `grp_122E8` | 14.8 % | coefficient symbol handlers |
| `grp_CB40` | 8.0 % | UNKNOWN |
| `grp_F530` | 7.2 % | IDCT variant |
| `grp_8708` | 5.7 % | UNKNOWN |
| `grp_12108` | 5.5 % | coefficient bit reader / dispatch |
| `grp_40C4` + `func_40C4` | 7.5 % | UNKNOWN |
| `spu_indirect_branch` + `spu_lookup` + `spu_drain_call` | 6.5 % | indirect-branch dispatch and trampoline |

The ranking matches the earlier lsfwd profile.

**How things were measured.**
- Bench: `generated/profile/bench/ibr/`. It runs the lifted Bink image through the real runtime drain, resolver and lookup on the intro's own bitstream (frame 900, 1800 calls, 5 repetitions).
- Variants are interleaved round by round (`ab.ps1`, 8 rounds, thermal stop at 358 K).
- Every variant must reproduce the state hashes `trace=B44D3D70 ls=A664900C`, IDCT `B61EC94F` / `93B5C2E7`.

## Ranked candidates

| # | Candidate | Measured or expected benefit | Confidence | Effort | Regression risk |
|---|---|---|---|---|---|
| 1 | **SSE2 forms of the plain word ops** (`a sf ai sfi and or xor andi ori xori ceq cgt clgt ceqi cgti clgti selb shli rotmi`). **DONE** (ps3recomp-int `0eae6a4`; see `UPSTREAM_INTEGRATION.md`) | Measured: coef −8.1 % (8/8 rounds), IDCT 101F8 −15.6 % (8/8), F530 −11.1 % (7/8). Weighted by the profile, about 6 % of frame decode time from the measured kernels; the unmeasured groups add unknown, likely similar gains. | High for the kernels; MEDIUM for the in-game effect | Small (done) | Low: exact `_ref` semantics, random-operand equivalence test on gcc, clang and clang-cl |
| 2 | **Lifter register caching**: keep SPU registers in host locals within a group, write back at exits and calls. 18–23 % of the hot groups' instructions are loads or stores to `ctx->gpr`. | Expected: large (tens of %); not measured | Medium (HYPOTHESIS since RESEARCH.md; now quantified) | Large: lifter change, all images | Medium: every exit, call, channel and interrupt must write back |
| 3 | **Remaining partial register-file stores**. **EXHAUSTED** (2026-10-23; see `UPSTREAM_INTEGRATION.md`, "Backlog #3"). After #1 the three hottest groups have 0 partial stores into `ctx->gpr`, and a data-flow pass finds 0 redundant full stores. What is left is 16 `movw` (two `shlhi` sites, `CB40`) and 16 `movb` (one `ceqbi`, `8708`). | Estimated ≤ 0.3 % of frame decode; not implemented | High | Small | Low |
| 4 | **Guarded direct dispatch at hot `bi` sites**. **SUPERSEDED and DONE** as group-local indirect dispatch plus group joining (2026-10-23; `SPU_DISPATCH_OPTIMIZATION.md`). The earlier ceiling (coef −3.5 %) kept the cross-group hop back to the dispatcher. Joining the handler groups `122E8`/`12BB4` into `12108` and dispatching `bi` over the group's own chunk starts removes both hops. | Measured: coef −13.7 % (8/8), IDCT not slower. Estimated 3–5.5 % of frame decode. | High on the bench; MEDIUM in game | Done (opt-in per image) | Low: guarded by every resolver rule, kill switch `SPU_NO_CHAIN_IND=1` |
| 5 | **Resolver lookup cache** (`spu_lookup` per thread, keyed by address and image, invalidated by registry size) | ≤ 2.4 % (the whole `spu_lookup` share), likely about 1 % | Medium | Small | Low (pure function of the registry) |
| 6 | PPU completion poll (`usleep(10)` measured at about 530 µs) | ≤ 0.8 %: the SPU is idle at most 3.4 % per frame | High | Small | Medium: guest timing. **Not recommended.** |
| 7 | Host flip/present path | 0 % on decode (it runs on another thread, and decode N+1 is already in flight) | High | — | — |

**Not candidates:**
- changing the 66 ms / 3-skip / 725 ms constants;
- frame duplication or faking;
- skipping decode work;
- a host Bink decoder.

These are all excluded by the milestone rules.

## Expected effect of #1 on a run (SUPPORTED HYPOTHESIS)

- With frame decode time down about 6 % (more if the unmeasured groups gain too), the texsnap host state would give about 30.2–31 fps average, against 28.42.
- At that rate lsfwd (30.01 fps) is the closest precedent: 0 resyncs, 17.8 unique fps, but still about 50 s of 4:1, because individual blocks fell below 29.97 and the surplus repays lateness slowly.
- Full-intro 1:1 is not expected from #1 alone. That needs #2 or #3 on top.
- Host drift (±12 %) can hide or exaggerate any single-run result. A run should be read through `tools/analyze_bink_pacing.py`: decode per stretch, resyncs and catch-ups. Do not judge it from the averages.

## Plan for #2: lifter register caching (Gate 1 FAILED 2026-10-23, see below)

**Why.** #3 is exhausted (see the table above). The remaining register-file cost is not redundancy, it is location: every SPU register lives in `ctx->gpr` memory.
- Hot groups, current SSE2 build: 15–20 % of instructions are `ctx->gpr` loads or stores (`12BB4` 111 ld / 236 st of 1973; `10200` 319 / 357 of 3341; `122E8` 384 / 462 of 5574; `F530` 262 / 318 of 3068).
- Stores equal the lifted definitions (data-flow: none dead), because every chain edge has a return path that must see the whole register file.
- Clang already forwards most reads inside a block (`12BB4`: 393 C reads → 111 loads). The remaining loads sit at labels reached from both the entry switch and a chain edge, on the loop-carried path.

**Design (lifter, `--chain-chunks` groups only, new opt-in flag `--cache-regs`, default off).**
1. Per group, compute the registers the group reads or writes. Declare `u128 r<N>` locals and load them at function entry from `ctx->gpr`; clang drops the ones it does not need.
2. Emit `r<N>` in place of `ctx->gpr[N]` in group bodies.
3. Write back at every point where the register file becomes observable. The written set is the group's def-set, a static superset; storing an unchanged value is harmless because the registers belong to this SPU thread.
   - the `SPU_CHAIN` / `SPU_CHAIN_BACK` not-OK path (trampoline return: interrupts, lockstep, flow trace, budget);
   - every `return` (indirect branch, `SPU_RET`, stop, halt, default switch case);
   - before every helper that receives `ctx`: direct `spu_func_X(ctx)` calls, channel read/write, DMA/MFC, `spu_drain_call`, `spu_indirect_branch`; plus reload of all cached registers after it, since a callee may change them.
4. LS diagnostic cold path (`spu_ls_read_diag` reads `ctx->gpr[0]`): write back `r0` inside the `diag != 0` branch only, so production stays free.
5. Nothing else changes: chain checks, budget, interrupt test (`event_status` volatile read), LS restrict contract, trampoline, resolver ownership rules, Bink scheduling.

**Risks.**
- Register pressure: x86-64 has 16 XMM registers, and the hot groups touch 40–120 SPU registers. Clang spills to the stack, and a spilled cached register costs about the same as today plus a write-back. The measurement must include stack spills (`dis_stores.py` stack counts) and the write-back size.
- Prologue cost per group entry (loads of the live-in set), significant if hops are frequent. Mitigation: load lazily per entry label using lifter liveness, not all at function entry.
- A missed observation point is a silent register-file divergence. This is the main correctness risk.

**Validation gates, in order. Stop at the first failure.**
1. **Bench prototype, no lifter change.** A script rewrites the bench copy of the five bench groups (`12BB4`, `122E8`, `12108`, `10200`, `F530`) as in steps 1–4.
   - It must reproduce `trace=B44D3D70 ls=A664900C`, IDCT `B61EC94F` / `93B5C2E7`.
   - Interleaved A/B against SSE2, 8 rounds.
   - Proceed only if coef and IDCT each gain ≥ 8 % in 8/8 rounds. That corresponds to about the ≥ 5 % frame target, given about 60 % of decode time in these groups.
2. **Lifter implementation** behind `--cache-regs`, with tests:
   - golden-output test of a small group (entry, chain, chain-back, call, channel, indirect exit);
   - a differential C test that runs the same lifted program cached and uncached over random register/LS inputs, including the forced not-OK chain path (pending interrupt, `g_spu_chain_on = 0`) and budget exhaustion, comparing register file, LS, pc and steps;
   - the existing SPU suites (`test_spu_helpers`, `test_spu_int_neon`, `test_spu_ls_alias`), Windows tools, WSL.
3. **Whole-image bench** with the regenerated Bink image: same hashes, A/B.
4. Only then, with authorization, **one paired runtime test**.

**Expected effect (HYPOTHESIS).** Removing most hot-path `ctx->gpr` loads and moving stores to exits could give 5–15 % on the hot groups, i.e. 3–9 % of frame decode. Store forwarding already hides part of today's cost (unlike the partial stores #1 removed), so the low end is plausible. Gate 1 decides.

### Gate 1 result (2026-10-23): FAILED

- State hashes are exact in all modes.
- IDCT gains +10 to +15 % (8/8 rounds).
- Coefficient decode loses 57–63 % (0/8). Its handlers are straight-line code between frequent group exits, so write-back at the exits removes nothing, and 70–80 live `u128` values spill.
- Whole-frame estimate:
  - group-wide caching: −18 %;
  - IDCT groups only: +2.5 %.
- Gates 2–4 are not started.
- Details: `UPSTREAM_INTEGRATION.md`, "Backlog #2, Gate 1".


## Cross-group dispatch (backlog #4, DONE 2026-10-23, ps3recomp-int `6637de6`)

- Profile: `SPU_DISPATCH_PROFILE.md`. Design, tests and measurements: `SPU_DISPATCH_OPTIMIZATION.md`.
- ps3recomp-int adds `spu_lifter.py --chain-indirect` and `--join-groups`, opt-in per image through `PS3RECOMP_SPU_LIFTER_IMAGE_ARGS`. MotorStorm enables both for the Bink image only.
- Bench (8 rounds, hashes identical): coef 5044 → 4353 ns (−13.7 %, 8/8); IDCT not slower.
- Fused group: 9457 instructions (+11 % over its three parts), fewer spills.
- Estimate (ESTIMATED): about 3–5.5 % of frame decode. With #1 that projects to about 31 fps average and about 29.0 fps in the slowest block. That is still below 29.97, so full-intro 1:1 is not expected yet.
- Not measured: `CB40`, `8708` and `40C4` (21 %), and any in-game run.
- Still open, unchanged: occasional skipping (4:1 stretches), limited headroom, a possible missing present at about 60.863 s, and direct flip vs FIFO-ordered flip.
- Next: one bounded, authorized intro run, read with `tools/analyze_bink_pacing.py`. The largest unprofiled share is `CB40`/`8708`/`40C4`; extend the bench to them before choosing the next candidate.

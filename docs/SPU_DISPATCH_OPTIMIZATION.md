# SPU cross-group dispatch optimization (2026-10-23)

The profile is in `SPU_DISPATCH_PROFILE.md`. All measurements here are offline, in the private bench `generated/profile/bench/ibr/` (intro bitstream, frame 900, 1800 calls × 5 repetitions, `ab.ps1` interleaving 8 rounds). **No MotorStorm launch.**

**Result: the gate passed.** The production change is local dispatch of computed jumps inside a chunk group, plus joining the Bink coefficient handler groups into their dispatcher's group:
- coefficient decode **13.7 % faster** (8/8 rounds);
- IDCT not slower;
- state hashes identical everywhere.

## Candidates (bench; positive = faster coef median against the SSE2 baseline, 8 rounds, all hashes identical)

| | Candidate | Prototype | coef | Verdict |
|---|---|---|---:|---|
| A | One combined chain gate (drop two volatile loads per chained hop) | `cg` | +3.0 % | Below the gate. The chained path is cheap (part C). |
| B | `musttail` jump for direct cross-group transfers instead of a drain hop | `xd` | +2.8 % | Below the gate. It still pays the group epilogue and prologue. |
| C | B + guarded switch at `bi` sites over known same-image targets | `xdi` | +10.6 % / +9.7 % | Passes. Needs per-site target lists. |
| D | B + C + A | `xdicg` | +11.2 % | Little over C. |
| E | Fuse `12108` + `122E8` into one group | `fu` | +2.5 % | Alone it only removes the direct return hop. |
| F | E + local `bi` dispatch over the group's own chunk starts | `fui` | +12.8 % (sd 0.4) | **Best.** No target lists: the group is the target set. |
| F′ | F + `12BB4` joined | `fu3i` | +12.5 % (sd 0.7) | Same on the bench, which hardly exercises `12BB4` (2.3 % vs 15.6 % in game). Chosen, because in game `12BB4 → 122E8` is a cross-group hop. |
| — | Resolver lookup cache (backlog #5) | not built | ≤ 3.8 % (the whole `spu_lookup` share) | Below the gate even at its ceiling. |
| — | Global register caching | — | — | Excluded (Gate 1 failed; not revived). |

IDCT was neutral in every prototype (±2 %, noise). The IDCT groups make no cross-group transfers and are not touched.

## Production design (ps3recomp-int `6637de6`)

**Lifter (`tools/spu_lifter.py`).**
- `--join-groups ADDRS`: the listed call targets do not start a group.
  - A join also bridges a gap in the image, but only when the chunk before the gap ends in an unconditional terminator (`br`, `bra`, `bi`, `iret`, `stop`, `stopd`; not a resuming stop).
  - Both Bink joins need this: `0x122D8–0x122E8` and `0x12BA8–0x12BB4` each follow a non-resuming `stop`.
- `--chain-indirect --image-id N` turns every non-return `bi $rN` in a group (no E/D bits) into:
  ```c
  { ctx->pc = rN; if (--_spu_budget && SPU_CHAIN_IND_OK(ctx, N)) switch (ctx->pc) { case S: ctx->steps++; goto loc_S; ... default: break; }
    g_spu_trampoline_fn = spu_indirect_branch; return; }
  ```
  - The cases are the group's own chunk starts.
  - Excluded from the cases:
    - LS 0;
    - the resolver's reserved addresses `0x0`, `0x9C0`, `0x9D0`, `0xA00`, `0xA70`, `0x3FF00`;
    - **every address after a `brsl`, `brasl`, `bisl` or `bisled`**. These are the only pcs a nested drain can be waiting for. `drain_ret_pc` is zeroed after a nested drain returns, so the guard alone cannot exclude them.
- Without these flags, output is byte-identical. All 26 MotorStorm SPU images and `spu_workloads.c` were regenerated and compared with `build/motorstorm-int`.
- With them, only the Bink image changes: 47 → 45 groups, 6 local-dispatch sites, header unchanged.

**Runtime.**
- `SPU_CHAIN_IND_OK` (`spu_context.h`) requires all of the following. These are every condition under which `spu_indirect_branch` would do something other than `spu_lookup(pc, image)` and jump:
  - `g_spu_ib_local_on` and `SPU_CHAIN_OK` (chaining armed, no lockstep, no pending interrupt, not flow-traced);
  - `image_id == N`;
  - no `policy_mode`, `resident_ovl`, `resident_task` or `irq_saved`, and all four `resident_code` slots empty;
  - `pc & LS_MASK != drain_ret_pc`.
- The remaining resolver steps are handled as follows:
  - The `0x9C0` / `0x9D0` / `0xA70` services, `0x3FF00` and LS 0 are never listed.
  - The image-23 and image-2 hacks are keyed on other image ids.
  - The `pc < 0x3000` `resident_task` clear is a no-op when `resident_task` is already 0.
  - `spu_check_stack_reset` cannot fire, because a stack-reset registration clears `g_spu_ib_local_on`.
  - A listed target is a chunk of this group, so `spu_lookup` would return its stub.
- `g_spu_ib_local_on` (`spu_drain.c`) is armed with `g_spu_chain_on` in `spu_task_launch_check`. It stays off under any of these:
  - `SPU_NO_CHAIN_IND=1`, the kill switch;
  - any resolver-observing diagnostic: `SPU_IBCOV`, `SPU_POLLTRACE`, `SPU_OVERLAY_TRACE_IMAGE`, `SPU_JOBEXEC`, `SPU_JOBTRACE`, `SPU_IRQTRACE`, `YDKJ_CRI_CHAIN`, `YDKJ_POLTRACE`;
  - any taskset task entry or ELF registration (`spu_channels.c`), which turns it off for good;
  - a stack-reset entry registration.
- MotorStorm registers no task entry or ELF.
- A hit counts a step and spends the per-invocation back-edge budget, so a dispatch loop still returns to the drain every 256 transfers.

**Build.**
- `-DPS3RECOMP_SPU_LIFTER_IMAGE_ARGS=<image>=<arg>;...` (`cmake/PS3RecompSPU.cmake`) → `build_spu_workloads.py --lifter-image-arg` → `spu_program_pipeline.py`.
  - The pipeline rejects unknown image names.
  - It passes `--image-id` (the pipeline id, Bink = `456415131`) to every lift.
  - It records the arguments in provenance.
- The private game config `generated/upstream/build_int_chain.cmd` sets `--chain-indirect` and `--join-groups=0x122E8,0x12BB4` for `spu_b34579b4…`.

## Correctness (VERIFIED)

**Bench, production lift** (`prod.c` from the pipeline, working-tree runtime objects).
- `trace=B44D3D70 ls=A664900C`, IDCT `B61EC94F` / `93B5C2E7`, steps 1422385.
- The same in every configuration: default, `BENCH_CHAIN=0` and `=1`, budget 2, `SPU_NO_CHAIN_IND`, `SPU_POLLTRACE`, `SPU_NO_CHAIN`.

**`runtime/spu/tests/test_spu_chain.c`.**
- Lifts every fixture three ways (base, chain, ind) and requires identical registers, LS, guest memory, pc, srr0, status and steps.
- New programs:
  - a 2000-round dispatch loop: `bi` to a local handler and to a joined handler, an exit `bi` to another group, a loop head after a call;
  - a callee joined into its caller that returns through a copied link register.
- Also covered:
  - flow-trace and interrupt runs;
  - a field-by-field guard test;
  - budget bounds on the hop count;
  - a task-registration run.
- Results: 353/353, diag 348/348, gcc and clang (WSL).

**Mutants (all caught).**
- No after-call exclusion; no budget; no step count; no image check; no `SPU_CHAIN_OK`; no return-pc check; no task-registration disable; diagnostic env ignored (caught in diag mode); no `irq_saved` check.
- The gap-bridging terminator check, caught by `tools/test_spu_chain_chunks.py`.

**Suites.**
- `tools/test_spu_chain_chunks.py`: 10/10.
- Windows `tools/test_*.py`: 87/87.
- WSL: 84/87, the same three known failures as before (`test_loaded_image_memory`, `test_sail_boot_callback`, `test_sysmodule_unload_module_ex`).
- CI compiles the third lift (`linux.yml`, `macos.yml`).

## Performance (VERIFIED on the bench; `ab_prod.txt`, 8 interleaved rounds, thermal stop 358 K)

| vs `sseN` (current lift) | median | rounds faster | per-round range |
|---|---:|---:|---|
| coef | **+13.7 %** (5044 → 4353 ns) | 8/8 | +12.6 … +20.5 % |
| IDCT `101F8` | +3.2 % | 8/8 | +1.0 … +8.1 % |
| IDCT `F530` | +2.3 % | 5/8 | −3.6 … +8.5 % |

- `prod` has a coef CV of 0.2 %.
- `fu3i` (hand prototype) measured +12.4 % in the same run; the production lift matches it.
- The IDCT code is byte-identical, so the IDCT gain is a side effect (cache or layout), not counted.

**Code size and spills** (`objmetrics.py`, clang-cl).

| | instructions | spill st / ld | frame |
|---|---:|---:|---|
| `12108` + `122E8` + `12BB4` (separate) | 939 + 5574 + 1973 = 8486 | 107 / 56 | 0xD0 / 0xC0 / 0xB8 |
| fused `12108` | 9457 (+11 %) | 96 / 28 | 0xD0 |
| object file | 2 410 545 → 2 417 623 bytes (+0.3 %) | | |

No pathological growth. Spills went down, because two prologues and epilogues and the default re-dispatch paths are gone.

## Whole-frame estimate (ESTIMATED, not measured in game)

- Coefficient-stage groups are 35.9 % of in-game Bink SPU time. With their share of the 6.5 % dispatcher time, that is about 41 %.
- 13.7 % of 41 % gives at most about 5.6 % of frame decode; likely **3–5.5 %**, because the bench under-represents `12BB4`, and `CB40`, `8708` and `40C4` (21 %) are untouched and unmeasured.
- Projection from the texsnap run:
  - average 28.42 × 1.06 (SSE2, #1) × 1.04 ≈ **31 fps**;
  - slowest block 26.34 × 1.06 × 1.04 ≈ **29.0 fps**, still below 29.97.
- Full-intro 1:1 is therefore **not** expected from this alone; host drift (up to 12.5 %) dominates single runs.

## Untested paths

- `CB40`, `8708`, `40C4` and the other four local-dispatch sites in the Bink image (groups `BF90`, `7F04`, `13114`, `10998`) are not exercised by the bench.
- Channel and DMA operations inside the fused group are not exercised by the coef/IDCT kernels (the C test covers DMA and interrupts in fixtures).
- One in-game run (`ind`, 2026-10-23, see `UPSTREAM_INTEGRATION.md`): no regression; gain not measurable against host drift. The other 25 SPU images are unchanged.

## Known video issues (unchanged, still open)

- Occasional skipping: 4:1 stretches when a block falls below 29.97.
- Limited headroom: see above.
- A possible missing present at about 60.863 s.
- Direct flip vs FIFO-ordered flip.

Nothing here changes the frame clock, flip ordering, the skip thresholds (66 ms / 3 / 725 ms) or audio resync.

## Next step

One bounded, authorized intro run (texsnap settings, `PS3_VIDEO_STATS`). Read it through `tools/analyze_bink_pacing.py` against the previous run: decode rate per 256-frame block, resyncs, 4:1 time.

# T191 Phase A: SPU indirect-branch dispatch audit

Tree `ps3recomp-t191` (T189 `a26240c5`). All findings VERIFIED by reading the code and by the differential tests in `CORRECTNESS_RESULTS.md`. No game launch.

## 1. The path, end to end

| Stage | Where | What happens |
|---|---|---|
| Decode and lift | `tools/spu_lifter.py` | `bi`, `bisl`, `bid`, `bie`, `iret` set `ctx->pc` and end the lifted function by returning to the driver (`g_spu_trampoline_fn = spu_indirect_branch`, `SPU_RET`, `SPU_DRAIN`) or by calling `SPU_IB_DISPATCH(ctx)`. Direct `br`/`brsl` to a known target are statically linked and never reach the resolver |
| Target address | `spu_indirect_branch` entry | `pc &= SPU_LS_MASK` (0x3FFFF). Real `bi` also ignores bits 0-1; the resolver does not mask them, so a misaligned target simply misses the registry (same result in the fast path) |
| Dispatch selection | `spu_context.h` `SPU_IB_DISPATCH` | `spu_indirect_branch` (full resolver, MSVC-built library), or `spu_indirect_branch_mt` when the lifted TUs define `SPU_USE_DISPATCH_MT` |
| Full resolver | `spu_channels.c` `spu_indirect_branch` | the long chain in section 2, then `spu_lookup` and a tail call |
| Existing fast dispatch | `spu_dispatch_mt.c` `spu_indirect_branch_mt` | `musttail` wrapper for the stack-growth problem only (comment at top). Does `resident_ovl` then `image_id` lookups and tail-calls; everything else it forwards to the resolver. **Not equivalent** (section 3) |
| Tasks and jobs | `spu_workload.c`, `spurs_policy.c`, `spu_reloc.h` | contexts are stack locals reused per run; `policy_mode` marks a SPURS policy module; relocatable Wws jobs are recorded in `ctx->resident_code[]` with a `link_base` |
| Overlays and LS replacement | `spu_channels.c` `note_get`, `spu_overlay_*` | every DMA into LS that matches a registered overlay source or signature sets `ctx->resident_ovl` or fills a `ctx->resident_code[]` slot. **The resolver never reads LS bytes to choose a function that is registered.** Only misses read LS (stop synthesis, WWS signature match, null-job handling) |
| Miss and errors | end of the resolver | `spu_halt`, SMC micro-step, interpreter rejoin (`SPU_INTERP_UNLIFTED`), job-return halts. All stay in the resolver |

## 2. What the full resolver does, in order, and how each step classifies

Classes: **E** required on every branch; **T** required only during a state transition; **C** cacheable with a defined validity condition; **U** unsafe to bypass.

| # | Step (spu_channels.c) | Depends on | Class | Fast path |
|---|---|---|---|---|
| 1 | `pc &= SPU_LS_MASK` | pc | E | done before the hook |
| 2 | job-span tracing: `ps3_ft_spujob_ret()`; at `pc == jr` end the span, in policy mode begin one | tracing knob, r0 | T (only when `PS3_FTRACE_SPUJOB` is on) | knob nonzero: resolver |
| 3 | `PS3_SPU_WWS_STATS` hooks | policy mode, stats on | T | policy mode: resolver |
| 4 | `spu_wws_job_enter`: validate and select a relocatable job module at a registered PM's job entry | policy mode, module registry | T (job entry) | policy mode: resolver |
| 5 | interrupt-return register restore (`spu_irq_regs_maybe_restore`): at the first enabled dispatch at `srr0`, restore all 128 GPRs and possibly `longjmp` | `irq_saved`, `int_enable`, pc | T, **U** | `irq_saved`: resolver |
| 6 | SPURS kernel services at the two reserved addresses (exit to kernel, select workload) | policy mode, pc | T | policy mode: resolver |
| 7 | taskset syscall HLE at `0xA70` | pc, LS word `0x27C4` | T, U | pc `0xA70`: resolver |
| 8 | image-23 CRI hack, `SPU_IBCOV`, `SPU_POLLTRACE`, `YDKJ_POLTRACE`, `SPU_OVERLAY_TRACE_IMAGE`, `SPU_JOBTRACE`, `LBP_HLE_JOBDONE`, `SPU_JOBEXEC` | env, image, pc | diagnostics / title hacks | image 23: resolver. Any of the env vars at startup: fast path off for the process |
| 9 | `if (pc < 0x3000) resident_task = 0` | pc | T (state write) | replicated exactly |
| 10 | task ownership for `pc >= 0x3000`: read `TaskInfo.elf` from LS `0x2794`, match registered ELFs, may `longjmp` to the driver | LS bytes, task registry, `resident_ovl`, `host_depth` | U | any task registration or a set `resident_task`: resolver |
| 11 | code slots `resident_code[0..3]`: first slot containing pc owns it; with `link_base` look up `pc - lsa + link_base` under the relocation key and set `ctx->reloc_delta`; `-1` (unrecognized) refuses to dispatch | slots | C (non-relocatable owner); T (relocatable: writes `reloc_delta`) | owner without link base: cached under that owner. Relocatable or unrecognized: resolver |
| 12 | `resident_task` lookup, then resident overlay lookup, then image lookup (`spu_lookup(pc, id)`) | `resident_ovl`, `image_id`, registry | **C** | cached |
| 13 | job-return address `0x3FF00` outside policy mode: log and `spu_halt` | pc | T | pc `0x3FF00`: resolver |
| 14 | `!fn` handling: synthesised `stop`, unlifted-LS guard, interpreter rejoin, WWS overlay signature match, WWS job fallback, null-job return, `pc == 0` job end, `[wws-jobentry]` probes | LS bytes, image, env | T, U | a miss is never cached: resolver |
| 15 | job/overlay probes when `fn` is found (`SPU_JOBEXEC`, `LBP_HLE_JOBDONE`) | env | diagnostics | env: fast path off |
| 16 | `spu_check_stack_reset(ctx, fn)`: if the resolved function is a registered one-way stack-reset entry and a host frame is live, `longjmp` to the driver | `host_depth`, registrations, fn | **E** (when entries are registered) | called by the fast path, same arguments |
| 17 | tail call `fn(ctx)` | | E | same call |

Measured cost of the chain with the switch off (hook removed vs shipped): within +-3 %, i.e. the chain is about 4.5 ns of a 6.6 ns call including the harness stub (`PERFORMANCE_RESULTS.md`).

## 3. What the existing `spu_indirect_branch_mt` omits

It performs steps 1, 12 (overlay, image only) and 17. It **skips**:
- 2-4: job-span tracing and the whole relocatable-job entry validation in policy mode;
- 5: the interrupt-return register restore;
- 9-10: `resident_task` maintenance and task/TaskInfo ownership;
- 11: code slots, therefore relocatable Wws job code is dispatched at the **wrong address** (no `link_base` translation, no `reloc_delta`) and unrecognized-overlay refusal is skipped;
- 13: the job-return halt;
- 16: the stack-reset check.

It also changes which function wins: slots first, then task, then overlay, then image in the resolver; overlay then image here. That confirms T189's finding. `spu_indirect_branch_mt` was not touched and is not used by T191.

## 4. Conclusion

An ordinary branch is one on which steps 2-11, 13 and 15 are provably no-ops and step 12 is the only thing that decides the target. That is checkable from fields of the context and a few process-global flags, in a handful of loads. Step 12 is a pure function of `(pc, owner image, resident overlay)` and the append-only function registry. See `FAST_DISPATCH_DESIGN.md`.

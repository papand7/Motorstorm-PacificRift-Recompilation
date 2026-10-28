# SPU dispatch profile: Bink coefficient decode (2026-10-23)

This covers how lifted SPU code moves between translated blocks, and what those transitions cost in the Bink decoder. All of it is offline: private bench `generated/profile/bench/ibr/`, the intro bitstream at frame 900, 1800 calls × 5 repetitions. No game launch.

Source locations are at ps3recomp-int `0eae6a4` (before this milestone's change).

## A. Execution model (VERIFIED from source)

**Lifting (`tools/spu_lifter.py`, `--chain-chunks`, which MotorStorm uses).**
- `find_spu_functions` splits an image into chunks: a new chunk at every branch target and after every unconditional transfer.
- `merge_chunk_groups` (344) runs contiguous chunks into a group. A new group starts at a `brsl`/`brasl` call target, an entry point, after a gap, or at the 4000-instruction cap.
- `lift_chained` (1208) and `lift_group` (565) emit, per group:
  - one `static void spu_grp_X(ctx, entry, ls)`. Its prologue is `SPU_LS_GROUP_ENTRY(ls)` (`spu_context.h:605`), `_spu_budget = SPU_CHAIN_BUDGET` if the group has back edges, then `switch (entry)` to a label per chunk. The default case re-dispatches through `spu_indirect_branch`.
  - one registered stub per chunk: `spu_func_S(ctx) { spu_grp_X(ctx, S, ctx->ls); }`. This stub is what `spu_lookup` returns and what the drain calls.

**Transfers and how they are lowered.**

| Kind | Lowering | Returns to the dispatcher? |
|---|---|---|
| Direct, same group (`_chain_edge`, 544) | `SPU_CHAIN` (forward) or `SPU_CHAIN_BACK` (`tgt <= src`, spends budget): store pc, check `SPU_CHAIN_OK`, `steps++`, `goto` label (`spu_context.h:926–940`) | Only when the check fails or the budget is spent. LS 0 never chains. |
| Direct, other group or ungrouped | `{ ctx->pc = T; g_spu_trampoline_fn = spu_func_T; return; }` (1021, 1136; fall-through 658) | Yes: one drain hop. |
| Computed `bi $rN`, `biz`/`binz`… | `ctx->pc = rN; g_spu_trampoline_fn = spu_indirect_branch; return;` (1048–1050, 1096) | Yes: drain hop plus the full resolver. The `spu_indirect_branch_mt` fast path (`spu_dispatch_mt.c`) is not used at these sites. |
| Return `bi $r0`, link-register return | `SPU_RET` / `SPU_RET_REG` (1046–1047): host return to the `brsl` caller | Host return, no hop |
| Call `brsl` / `brasl` | `host_depth++; spu_func_T(ctx); spu_drain_call(ctx, ret); host_depth--; spu_img_restore` (1003) | Nested drain loop until pc == ret |
| Indirect call `bisl` | `spu_indirect_branch(ctx); spu_drain_call(ctx, ret)` (1071) | Nested drain loop |
| `iret` | `ctx->pc = ctx->srr0` → resolver (1053) | Yes |
| Channels `rdch` / `wrch` (MFC DMA, events, mailboxes, tag waits) | `spu_rdch` / `spu_wrch` calls inside the block (951, 958; `spu_channels.c:923`, `:1155`) | No. A blocking read waits in place. |
| `stop` | `ctx->status = …; spu_stop(ctx); return;` (746–797) | Ends the run, or resumes for lv2 stops `0x100`/`0x110`/`0x111` |
| Unresolved direct target | stub that routes through `spu_indirect_branch` | Yes |

**The dispatcher.**
- `spu_run_with_halt` (`spu_channels.c:203`) is the top-level driver; `spu_drain_call` (`spu_drain.c:417`) is the loop. Per hop (`g_spu_trampoline_fn` set) it does:
  1. a return check: if the trampoline is the resolver and pc == `return_pc`, return to the caller;
  2. set `drain_ret_pc`;
  3. `spu_lockstep_step` (`spu_context.h:902`);
  4. `spu_task_step` (892): SPURS launch check, the `g_spu_recent` ring, step count;
  5. take a pending interrupt (`spu_take_interrupt`, `spu_drain.c:302`; IRET restore at 261);
  6. call `fn(ctx)`.
- With no trampoline, it re-looks-up pc or calls `spu_restart_dispatch` (`spu_channels.c:117`).

**The resolver.** `spu_indirect_branch` (`spu_channels.c:2343–2830`) runs these steps in order:
1. LS mask;
2. IRET register restore;
3. policy-module services `0x9C0` / `0x9D0`;
4. taskset syscall `0xA70`;
5. YDKJ image-23 hack;
6. env diagnostics (`SPU_IBCOV`, `SPU_POLLTRACE`, `YDKJ_POLTRACE`);
7. taskset ownership: `pc < 0x3000` clears `resident_task`; above it, `spu_taskset_resident_image` reads LS `0x2794` and may adopt a task or `longjmp`;
8. resident code slots, then the resident task, then the resident overlay, then `spu_lookup(pc, image_id)` (1578, hash chain);
9. job-return and unlifted fallbacks (`0x3FF00`, interpreter);
10. image-2 job hacks;
11. `spu_check_stack_reset`;
12. `musttail return fn(ctx)` (2826; the runtime is built with clang-cl, so the tail call is real).

**When chaining is on, and what it skips.**
- `spu_task_launch_check` (`spu_drain.c:68`) arms `g_spu_chain_on` once, unless a step diagnostic, `SPU_PCHIST`, `SPU_NO_CHAIN` or tail-return mode is set. Registering a stack-reset entry clears it for good (`spu_channels.c:1664`).
- `SPU_CHAIN_OK` additionally requires:
  - lockstep off;
  - no pending enabled interrupt (`event_status` read volatile);
  - the context not being flow-traced.
- A chained transfer skips only the `g_spu_recent` / `g_spu_pch` post-mortem rings.
- The budget (`SPU_CHAIN_BUDGET` 256 per group invocation) sends a looping group back through the drain every 256 back edges.

**State synchronised at boundaries.**
- All SPU state lives in `ctx`: `gpr[128]`, pc, channels, MFC queue, event state, steps. LS is reached through the group's restrict `ls`.
- Groups keep nothing in host registers across a boundary, so no write-back is needed at any exit. This is why register caching failed (Gate 1).
- Runtime intervention is needed only at:
  - hops (lockstep, interrupts, task-launch, stack-reset, post-mortem rings);
  - the resolver's rules above;
  - channel operations, which are runtime calls inside the block.

## B. Bink transition profile (VERIFIED, bench, 7200 coefficient calls, hashes identical)

Instrumented copy (`trinst.py` → `b_trc.exe`, summary `tran.py tr_coef.txt 7200`).

| Per coefficient call | Count |
|---|---:|
| Chained in-group transfers (no drain) | 726.1 |
| Direct cross-group drain hops | 32.5 |
| Indirect `bi` (drain + full resolver) | 30.5 |
| `SPU_RET` | 1.0 |
| Chain fallbacks (check failed) | 0 |
| Budget exhaustions | 0.031 |
| Group entries | 63.1 |
| **Total transfers** | **≈ 790** |

Chaining already carries 92 % of transfers. What remains is 63 hops per call, all between groups.

**Hottest pairs (per call).**
- 12108 → 12108 chain: 545.8
- 122E8 → 122E8 chain: 176.0
- 12108 → ? via `bi` at LS `0x122D0`: 28.1
- 122E8 → 12108, direct cross-group: 28.1
- 12BB4 → 12BB4 chain: 4.4
- 122E8 → ? indirect: 2.4
- 12BB4 → 122E8, direct cross-group: 2.4
- 120A8 → 12108, 12108 → 122E8, 122E8 return: 1.0 each

The `bi` at `0x122D0` (the coefficient-symbol dispatch) reaches 4 targets, all in `grp_122E8`:

| Target | Hits over 7200 calls |
|---|---:|
| `0x126C4` | 125340 |
| `0x1244C` | 49172 |
| `0x122E8` | 14564 |
| `0x12774` | 13368 |

So the hot pattern is about 28 round trips per call: `12108 —bi→ 122E8 handler —direct→ 12108`. Each round trip is two drain hops, one full resolver pass and two Win64 group prologue/epilogue pairs.

**Static transfer sites per group.** `ind` includes each group's default case.

| Group | Entries | chain | back | xgrp | ind | other |
|---|---:|---:|---:|---:|---:|---|
| 122E8 | 32 | 41 | 9 | 4 | 2 | ret 1, stop 1 |
| 12BB4 | 12 | 8 | 4 | 4 | 1 | |
| 10200 (IDCT) | 6 | 6 | 1 | 0 | 1 | ret 1 |
| F530 (IDCT) | 5 | 5 | 1 | 0 | 1 | ret 1 |
| 12108 | 8 | 8 | 2 | 2 | 2 | stop 1 |
| CB40 | 49 | 53 | 12 | 21 | 1 | call 3 |
| 8708 | 67 | 75 | 28 | 19 | 1 | call 19 |
| 40C4 | 38 | 54 | 14 | 0 | 1 | call 6, ret 1 |

- The IDCT groups make no cross-group transfers.
- CB40, 8708 and 40C4 (21 % of in-game decode time) are not exercised by the bench. Their transitions are unmeasured.

**Where the coefficient stage's time goes.** RIP sampling (`BENCH_SAMPLE_COEF=1`, `riphist.py`). The sampler slows coef from 5 to 21 µs, so the shares are indicative.

| Where | Share |
|---|---:|
| Group bodies | 86.2 % |
| — 12108 | 49.2 % |
| — 122E8 | 34.7 % |
| — 12BB4 | 2.3 % |
| `spu_lookup` | 3.8 % |
| `spu_indirect_branch` | 3.6 % |
| `spu_drain_call` | 2.8 % |
| Stubs and wrappers | 2.1 % |
| `spu_irq_regs_maybe_restore` | 0.7 % |
| `spu_depth_guard` | 0.2 % |
| **Dispatcher total** | **≈ 13 %** |

- Of 5.04 µs per call, that is about 0.65 µs of dispatcher, or about 10 ns per hop (63 hops).
- Group bodies also absorb the prologue/epilogue cost of each re-entry (part C).
- The in-game texsnap profile agrees: resolver + lookup + drain = 6.5 % of all Bink SPU time.

## C. Is chaining effective? (VERIFIED from asm, `g12108_sse.dis`, `objmetrics.py`)

- **The chained hop is cheap: about 12 instructions.**
  - Store pc.
  - Load and test `g_spu_chain_on` and `g_yz_lockstep_on` (volatile, so they are reloaded every hop).
  - Compare `int_enable`, then test events.
  - Load and compare `g_pm_flow_ctx`.
  - `incl steps`, then jump.
  - A single combined gate (`cg`, which drops two loads) measured only +3.0 % coef. The chained path is not the bottleneck.
- **A group re-entry is expensive.**
  - Every `spu_grp_*` prologue saves 5 GPRs and 9 XMM registers (xmm6–14, Win64 callee-saved), checks the /GS cookie, publishes `ctx->ls`, sets the budget and walks a compare tree on `entry`.
  - The epilogue undoes all of it. Frames are `0xB8`–`0xD0`.
  - A cross-group hop pays epilogue + drain + stub + prologue; an indirect hop also pays the resolver. A `musttail` direct cross-group jump (`xd`) still pays the full epilogue and prologue.
- **No inlining across groups** (separate static functions reached through registered stubs). Branch prediction across the drain's indirect `fn(ctx)` call is untested; the resolver's `musttail` jump is one more indirect branch per hop.
- **Conclusion.** Within a group, chaining already works: 92 % of transfers, 0 fallbacks, 0.03 budget exits per call. The remaining cost is concentrated in the 61 cross-group and indirect hops per call, and specifically in the dispatch→handler→dispatcher round trip between 12108 and 122E8.

## Known limits of this profile

- One bitstream position (frame 900) and two stages (coefficients, IDCT).
- CB40, 8708 and 40C4 are not exercised.
- Channel operations and DMA are not exercised by the coef/IDCT kernels.
- The in-game composition differs: 12BB4 is 15.6 % of in-game decode but only 2.3 % here.

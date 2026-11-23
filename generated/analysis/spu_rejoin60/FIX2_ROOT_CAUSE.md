# FIX2_ROOT_CAUSE: what PS3_SPU_INTERP_REJOIN_RELOC changes and why it was worth ~6 fps

Private, offline, 2026-11-18. Labels: VERIFIED (read in code or measured), PARTIAL, HYPOTHESIS, BLOCKED.
Line numbers refer to `ps3recomp-vkgame` (dc3a2ba6 plus its uncommitted changes, the runtime of the main exe `build/motorstorm-vkgame-100-next`, SHA-256 714690f6…) unless another file is named.

## 1. The chain, step by step (VERIFIED)

The trigger is a stale lift, not the interpreter.

1. **The trigger is a switch that is lifted as a function return.**
   - renderablejob (image 1296695296) dispatches a C `switch` through a jump table at LS 0xA654: `ila $r88,0xA654; lqx; rotqby $r2`, then `brz` into a one-instruction `bi $r2` block at 0xA650.
   - In the lift that every 1.00 build uses since the 1.00 twin build (`generated/spu_raw/wws_reloc`, dated 2026-10-26 14:57), that block is `SPU_RET_REG(ctx, 2)` (`wws_reloc/ms_10aa3f4480ef_eEE40/spu_recomp.c:7645`). `SPU_RET_REG` is a host `return` that publishes r2 as the pc (`runtime/spu/spu_context.h:1098`).
   - Table words read from the module (`spu_raw/wws_modules_v100/…eEE40.bin` at 0xA654): 0xAA64, 0xAA38, **0xAA10**, 0xA1E8, 0xA9E4, 0xA9BC, 0xA994, 0xA96C, **0xA944**, ….
   - The framework fixed this classifier at 21:41 the same day: commit `58c45dfb`, "SPU lifter: a switch entered by a conditional branch is a dispatch". Its message says that re-lifting changes one line, in renderablejob only. **The 1.00 builds were never pointed at a re-lifted directory.**
     - `generated/spu_raw/wws_reloc_t81c` (used by T106–T161) differs from `wws_reloc` by exactly that one line (`diff -rq`). Its manifest has the same module sig and body hash.
     - Every `build/motorstorm-vkgame-100-*` CMake cache, including `100-next` and `100-cp60`, has `MSPR_WWS_AOT_DIR=…/wws_reloc`.
2. **The drain cannot resume at the case label, so it unwinds every host frame.**
   - `func_0000AF88` calls `A120` inside a call bracket (`spu_drain_call(ctx, 0xAFBC)`). A120 runs the switch and host-returns with pc = case label (0xAA10, 0xA944).
   - The drain's resume probe (`runtime/spu/spu_drain.c:487-489`) asks `spu_lookup(pc, resident_ovl)` and then `spu_lookup(pc, image_id)` for the **raw** pc. A relocatable lift is registered under `(link-base address) | SPU_RELOC_KEY_BIT` with the module's own image id. The dispatcher resolves it that way (`spu_channels.c:3796-3810`), but this probe never asks for that key, so it always misses.
   - It then calls `spu_restart_dispatch` (`spu_drain.c:500-507` → `spu_channels.c:161-167`). That longjmps to `spu_run_with_halt` case 2 (`spu_channels.c:308-315`): `host_depth = 0` and the case label is re-dispatched. **Every host frame of the job is gone.**
3. **Every later return into a lost frame is an AOT miss.**
   - 0xAFBC (AF88's continuation) and **0xDFA0** (the return point of `func_0000DF98`'s call to AD50) are mid-function addresses with no lifted entry.
   - `spu_indirect_branch` finds nothing and hands the pc to `spu_smc_microstep` (`spu_channels.c:4219-4232`).
   - 0xAFBC begins with `br`, so the microstep handles it (0 steps). 0xDFA0 begins with `ori`, which is not in the microstep set, so the microstep hands it to `spu_interp_run_until(ctx, pc, drain_ret_pc)` (`spu_channels.c:3340-3345`).
4. **Before Fix 2, the interpreter never rejoined.**
   - Its rejoin probe runs **once per interpreted instruction** (`spu_interp.c:433`), as `spu_lifted_lookup(ctx, pc)`. That was `spu_lookup(pc, ctx->image_id)`: the raw pc under the PM's image id. Inside a resident relocatable slot it can never hit.
   - So the interpreter ran to the job's return to the PM (0x3214, registered under the PM image), which is the first pc where the raw probe hits: **the rest of the job ran interpreted.**
5. **What Fix 2 changes.**
   - `spu_lifted_lookup` (`spu_channels.c:2246-2271`, CP60 diff) resolves a pc inside a resident relocatable slot the same way the dispatcher's slow path does.
   - The interpreter therefore stops at the next lifted entry: usually a few instructions later, at the next branch target or call target. `spu_smc_microstep` then re-dispatches through `spu_indirect_branch` (`spu_channels.c:3351-3358`), which publishes `reloc_delta` from the same slot.

**Fix 2 does not remove the trigger.** The switch still unwinds the frames (step 2) and the returns still miss (step 3). Fix 2 caps each miss at the next lifted entry instead of the job's end.

## 2. Measured effect (VERIFIED, race logs; tools in `tools/`, outputs in `out/`)

R1 (Kksr47, Fix 2 off, `PS3_SPU_AOT_PROF=5`), driving window 67.6–117.6 s (`out/aotprof_r1_rates.txt`):

| site (image 1296695296 = renderablejob) | per frame | steps per event | host time |
|---|---:|---:|---:|
| miss 0xDFA0 (run-to-end interpretation) | 9.13 | 166,414 | 2.49 ms each = **22.7 SPU-ms/frame** (0.63 s/s) |
| restart 0xAA10 / 0xA944 (switch cases) | 9.14 / 4.66 | – | – |
| miss 0xAFBC, 0x12760, 0x12A60, 0xACF4, 0xECA4, 0x10390 | 4.7–9.1 each | 0–139 | 30–110 ns each (0x12A60: 3.8 µs) |
| all other images' misses, total | – | ~0 | < 15 ms/s (Wws PM interrupt shims, §SPU_TRANSITION_PROFILE) |

The counts line up: restart 0xAA10 and misses 0xAFBC and 0xDFA0 each have n = 20,792 in the cumulative table.

`[wws-stats]` per-module deltas over race entry + 10 s .. end (`out/wws_window_ksr48_54.txt`; cp60 exe 6425564b, same exe in every arm):

| arm | renderable jobs/frame | µs/job | interpreted instructions/job | jobs with steps | renderable SPU-ms/frame | fps |
|---|---:|---:|---:|---:|---:|---:|
| control Kksr48 / 52 | 20.9 / 21.7 | 1299 / 1361 | 79,177 / 71,683 | 70 / 69 % | 27.2 / 29.5 | 32.6 / 31.0 |
| Fix 2 Kksr50 / 54 | 18.8 / 22.1 | 536 / 572 | 32.9 / 27.7 | 72 / 70 % | 10.1 / 12.6 | 39.5 / 38.0 |

- Every other Wws module has 0 interpreted steps in all four runs (spuconstraints 1.7/job). Their µs/job is unchanged within noise.
- Main-thread waits per frame are about the same in both arms (`out/ab_metrics_ksr47_59.txt`): JobBatch usleep 8.2/8.3 vs 8.4/9.3 ms; event queue (Havok semaphore 0xA4C590) 3.8/3.9 vs 3.6/3.5 ms.
- The frame-time drop (30.7/32.3 → 25.3/26.3 ms) therefore lies outside those waits. It is consistent with a shorter Present spin at 0x50C818, which waits for the renderable jobs. PARTIAL: there is no Fix-2-on sampler run, so the spin was not measured directly.

## 3. Answers

- **Why the interpreter was entered.** A stale lift turns renderablejob's switch `bi $r2` into a host return. The drain's raw-pc resume probe cannot resume inside a relocatable slot, so the host stack unwinds. The return points of the lost frames are not lifted entries, so they miss. VERIFIED.
- **What kept it there.** The interpreter's per-instruction rejoin probe used the raw pc and PM image, which never matches a relocatable lift. VERIFIED.
- **What Fix 2 changes.** It makes that probe relocation-aware. It **removes interpreter instructions**: 79k → 30 per job, −99.96 %. It does not shorten transitions; the restart and the misses still happen on 70 % of jobs. VERIFIED.
- **Which jobs and branch patterns benefit.** Only renderablejob: the A120 switch (cases 0xAA10, 0xA944) inside nested call brackets. No other module had interpreted steps. VERIFIED.
- **Why the gain was so large.**
  - It removes ~17 SPU-ms/frame (27–30 → 10–13). That is ~760 µs of interpretation per job at ~15 ns per instruction (R1: 2.49 ms per 166k steps), from the job that the Present spin waits for. The render phase was lane-saturated (criticalpath60 `out/lanes_ksr36.txt`).
  - FPS +6–7 (VERIFIED in four A/B runs plus a 2+2 confirmation: off 31.3/27.6, on 35.4/36.7).
  - The attribution to the Present spin is PARTIAL (see §2).

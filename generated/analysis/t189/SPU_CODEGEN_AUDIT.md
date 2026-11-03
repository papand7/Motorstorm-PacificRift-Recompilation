# T189 Workstream 2: SPU code-generation audit and plan

Labels: VERIFIED (read in code or measured), HYPOTHESIS, ESTIMATE. **No SPU code was changed in T189** (reason in §2).

## 1. Current lowering (VERIFIED: `tools/spu_lifter.py`, `runtime/spu/spu_channels.c`, T186 §4)

| Area | What is emitted | Cost |
|---|---|---|
| Registers | `ctx->gpr[0..127]` (128-bit unions) read and written per instruction; `ctx` escapes to channel/stop/drain calls | T186: 2.4 ctx operands per SPU instruction, a 6.7 KB frame, 7,220 spill operands in one solver group; about 19 x64/SPU instruction (static) |
| Indirect branch | `spu_indirect_branch(ctx)` by name at every `bi`/`bisl`/`iret`/return site (10 emission sites in `spu_lifter.py`, lines 660–1316); the lifter's own `SPU_IB_DISPATCH` macro (`:104-107`) is never used | about 700 lines of resolver per hop (§2) |
| Group exits | TLS `g_spu_trampoline_fn` plus a return to `SPU_DRAIN` | 40–60 instructions per hop (ESTIMATE, T186) |
| Float | bit-exact helpers (`spu_helpers.h:1028-1130`) | 10–14× a native SSE op (T186 bench) |
| Channels | `spu_rdch`/`spu_wrch` out of line; MFC through `mfc_for()` (T187 fast path, A/B pending) | |
| LS access | masked address, `movdqu`, `pshufb` | cheap |

## 2. Why the existing fast indirect dispatch must not just be switched on (VERIFIED)

`runtime/spu/spu_dispatch_mt.c` (`spu_indirect_branch_mt`) was written for one title's stack-growth problem. On a lookup hit it tail-calls the function directly. It does **not** perform these parts of the full resolver (`spu_channels.c:3071-3600`), which are functional, not diagnostic:

| Full-resolver step | Effect if skipped |
|---|---|
| `spu_wws_job_enter` (relocatable job modules, when any are registered) | job modules not validated or rebased (`reloc_delta`) |
| `spu_irq_regs_maybe_restore` | interrupt return without the register restore the hardware contract requires |
| SPURS kernel-service addresses for policy modules | only partly covered by `special` |
| Taskset resident-image tracking (`resident_task`, the `longjmp` resume) | a resumed task could resolve to the wrong ELF |
| `resident_code[]` slot ownership, including relocatable lifts | a co-resident image at the same LS address could shadow the owner |
| Job-return halt (`SPU_JOB_RETURN_LS`) and the synthesised-`stop` exit | only reached on a miss, so not affected |

Selecting `-DSPU_USE_DISPATCH_MT` today would therefore change behaviour in titles that use relocatable jobs, interrupts or tasksets. It must not be enabled as-is.

The resolver also contains title-specific special cases (`image_id == 2`, `22`, `23`, fixed LS offsets). A generic fast path must not encode them; it has to be **invalidated by** them.

## 3. Prioritized SPU plan

| # | Change | Generic design | Validation | Complexity / risk | Expected (ESTIMATE) |
|---|---|---|---|---|---|
| **S1** | **Correct fast dispatch.** At the top of `spu_indirect_branch`: a per-thread direct-mapped cache of `(pc, image_id, resident_ovl, resident_task, code-slot generation) → fn`, used only when a cheap *eligibility word* is zero. Each functional special case above sets a bit in that word when its state becomes active (relocatable PMs registered, an IRQ save pending, policy-mode kernel-service PCs, `pc ≥ SPU_TASKSET_TASK_LO`, any `resident_code` slot covering `pc`, any tracing switch). A miss or an ineligible hop runs the full resolver unchanged and fills the cache. The cache is invalidated by a generation counter bumped wherever `spu_lookup`'s registry, `resident_ovl`, `resident_task` or `resident_code` changes. **Hit-path invariant:** identical to the full resolver's final `fn(ctx)` | low–medium / medium | (a) a transcript test: the resolver run on recorded hop sequences (pc, ctx state) with and without the cache must call the same `fn` and leave the same ctx; (b) the existing SPU suites; (c) a negative control that mutates a resident slot mid-run and must miss | 2–5× per hop (ESTIMATE, from T152's PPU icall cache: 15 → 6 ns). Frame share unmeasured |
| S2 | **SPU register promotion**: the T188 pass made ISA-generic, with an SPU profile (128 × 128-bit keys; boundaries `spu_rdch/wrch/stop/halt`, the drain hop and the resolver; member access `._u32[n]` kept on the local union) | shares the scanner, dataflow and emitter with PPU | an SPU difftest (random SPU programs from the SPU encoders, deterministic channel fixture, register hash at every channel op/stop/hop, LS hash) plus mutants | medium / medium | ctx traffic 2.4 → under 1 per instruction. Gains concentrated in long register-only groups. **T188/T189 caution:** on PPU the gain only appeared in call-free loops |
| S3 | **Exact float fast path** (T186 candidate: MXCSR RZ+FTZ+DAZ, range check, exact fallback) behind `SPU_FLOAT_FAST`, with the fallback unchanged | host-specific (SSE4.1/FMA3) behind an abstraction | a formal edge-case table (±0, denormals, exponent 255, saturation beyond FLT_MAX, NaN encodings) plus 10⁷ random vectors against the exact helpers | medium / high | 1.3–2.2× per float op (T186 offline) |
| S4 | **Group-exit cost**: one TLS address per group; `SPU_CHAIN_OK` read once per group entry | generic | difftest hop transcript | low / low–medium | 20–40 instructions per hop |
| S5 | **SIMD lowering of `shufb`** (about 12 x64 today) via a single `pshufb` plus a constant-pattern fast path when the pattern register is a known constant (`fsmbi`/`cwd`/`ila` patterns) | generic, compile-time | per-instruction conformance (`test_spu_exec_sse`) | low–medium / low | static; workload-dependent |

**Order: S1 first.** It is the smallest independently testable change, it removes the largest per-hop cost, and it needs no relift (runtime only). S2 needs the SPU difftest built first. S3 needs the exhaustive edge-case table.

**Not proposed:** replacing exact float operations with native arithmetic (not exact), or enabling `spu_indirect_branch_mt` as-is (§2).

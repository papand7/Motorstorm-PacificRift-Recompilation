# T188 Phase C: SPU code-generation, next steps (design; not implemented)

No SPU change was made in T188. The PPU prototype was finished and validated first. Its in-game effect is still unmeasured, so following the brief, the SPU work below is a concrete design for the next task.

## 1. Current SPU lowering (VERIFIED: `tools/spu_lifter.py`, T186 §4)

- **Registers.** `ctx->gpr[0..127]` are 128-bit unions in memory. `ctx` escapes to `spu_rdch`/`spu_wrch`/`spu_stop`/`spu_drain_call`, so every result is stored. T186 measured 2.4 `ctx` operands per SPU instruction and a 6.7 KB frame with 7,220 spill operands in one solver group: about 19 x64 instructions per SPU instruction (static).
- **Control flow.**
  - In-group `goto`s are guarded by `SPU_CHAIN_OK` (4 globals plus a step count).
  - Group exits write the TLS `g_spu_trampoline_fn` (40–60 instructions per hop, ESTIMATE).
  - Every indirect branch calls the full resolver `spu_indirect_branch(ctx)`; the `SPU_IB_DISPATCH`/`spu_indirect_branch_mt` fast path is never selected.
- **Float.** Bit-exact helpers cost 10–14× a native SSE op (T186 bench). An exact range-checked candidate gives 1.3–2.2×.

## 2. What carries over from the PPU pass, and what does not

**Shared without change** (ISA-agnostic in `ppu_regpromo.py`):
- the C statement scanner and the statement CFG;
- the dirty/valid/next-use dataflow, with the dirty ⊆ valid invariant;
- the edge write-back/reload emitter and the loop-header rule;
- the differential harness pattern: transcripts hashed at every runtime entry that receives the context, plus mutants.

**SPU-specific**, as an ISA profile:

| Item | PPU | SPU |
|---|---|---|
| Keys | 70 scalar fields | `gpr[0..127]`, 128-bit (`spu_reg` / `__m128i`): 128 keys, so masks are wider (Python ints, no change) |
| Boundaries | calls, drains, HLE, syscalls, hooks | `spu_rdch`/`spu_wrch` (channels: MFC, mailboxes, events), `spu_stop`/`spu_halt`, the drain hop, `spu_indirect_branch`, lockstep/interrupt checks that read `ctx` |
| Local-store access | — | **not a boundary**: LS is `ctx->ls` memory, not registers |
| `return` | to the caller | to the drain loop: write back at every exit, as on PPU |
| Partial-register access | — | `ctx->gpr[N]._u32[0]` etc.: rename the base and keep the member access (`_psN._u32[0]`). The local is a union, so this stays defined |
| Opaque calls | `vm_write*` | helpers that are out of line (`spu_fma` variants if not inlined, `spu_shufb` if not inlined) |

Make the pass's ISA a profile: a key table, the boundary regexes and the hook table. Don't fork it. The SPU must not inherit PPU assumptions: SPU has no CR/XER, the drain hop semantics differ, and an SPU group spans many guest functions.

## 3. Proposed SPU milestones, in order

| # | Change | Generic? | Complexity | Risk | Expected (ESTIMATE) |
|---|---|---|---|---|---|
| S1 | **Emit the existing fast indirect dispatch**: `spu_lifter.py` emits `SPU_IB_DISPATCH(ctx)` (resolving to `spu_indirect_branch_mt` with `-DSPU_USE_DISPATCH_MT`), behind a lifter flag | yes | low (the runtime exists) | medium: the target cache must observe overlay/image reloads | indirect hops from about 700 resolver lines to a table lookup. In-game share unmeasured |
| S2 | **SPU register promotion**: the profile from §2. Only the registers a group touches are promoted, by the same analyses | yes | medium | medium (channels and drain hops) | ctx traffic 2.4 → under 1 per instruction (ESTIMATE). Fewer spills. Groups that are 90 % register work gain most |
| S3 | **Exact float fast path**: T186's range-checked candidate behind `SPU_FLOAT_FAST`, with the fallback unchanged. FMA3 variant only behind a CPU check | yes | medium | medium-high (bit-exactness): needs a formal edge-case table plus random vectors, not sampling alone | 1.3–2.2× per float op. Frame effect unknown until the dynamic float share is measured |
| S4 | **Cheaper group exits**: one TLS address per group, and `SPU_CHAIN_OK` read once per group entry, not per `goto` | yes | low | low–medium | fewer hop instructions (ESTIMATE 20–40 per hop) |

**Validation design for S1–S4:**
- An SPU difftest analogous to `tools/ppu_difftest.py`: random SPU programs from the encoders in `spu_disasm`, lifted, baseline vs variant, with a fixture that implements channels deterministically, hashes the 128 registers at every channel op, stop and hop, and compares LS at the end. Plus mutants.
- The existing SPU suites (`test_spu_exec_sse`, `spu_lift_selftest.py`, the rpcs3 oracle extracts where present).

## 4. Sharing infrastructure without equating the ISAs

- **Share:** the text scanner, CFG, dataflow, emitter, and the difftest skeleton (program builder, build/run/compare, mutants, benchmark driver).
- **Keep separate:** instruction encoders and decoders, fixtures (PPU HLE/syscalls vs SPU channels/MFC), boundary vocabularies, and float semantics (PPU IEEE double with FPSCR vs SPU single-precision truncation/saturation).

## 5. Next implementation milestone (proposal)

1. **T189 = PPU inline stores in the standard pipeline** (Audit §5 #2), measured together with `--promote-regs`.
   - Offline: T188's benchmark shows promotion keeping more of its gain when stores are inline (transform 1.15× → 1.31×, struct 1.00× → 1.24×).
2. **Then S1 + S2 on SPU**, with the SPU difftest built first.
3. **An in-game A/B** of `--promote-regs` (one relift of the PPU TUs with the stand-alone pass, then a rebuild of about 11 min) needs authorization. See `PERFORMANCE_BENCHMARKS.md` §6.

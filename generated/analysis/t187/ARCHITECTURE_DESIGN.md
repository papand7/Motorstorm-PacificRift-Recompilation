# T187: generic PPU/SPU codegen redesign (Phase A)

Scope: the code that ps3recomp's lifters emit (`tools/ppu_lifter.py`, `tools/spu_lifter.py`), not runtime
libraries. MotorStorm is only the test case. Nothing here depends on a game address.
Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## 1. Where the current lowering stands

Each guest function becomes one C++ function `void func_X(ppu_context* ctx)`. Every guest register access is a
field access, `ctx->gpr[N]` or `ctx->cr`, and every guest load or store calls `vm_read*`/`vm_write*`.
Two facts mean the host compiler can't keep guest registers in host registers (VERIFIED, by disassembly, see
`CODEGEN_BOTTLENECKS.md`):

1. **`ctx` escapes.** It is passed to every callee and published in `g_active_ctx`.
2. **Every guest store is an opaque call.** `vm_write32` lives in another TU and is not inlined by LTO.

So after each store the compiler must assume any `ctx` field changed: it reloads registers and writes every
result back immediately. The same holds for SPU code (`spu_context`, T186 item 4).

## 2. Target design: layered state ownership

| Layer | Owner | Lives in | Visible to outside code |
|---|---|---|---|
| L0, architectural state | `ctx` | memory | always, at sync points |
| L1, function-local working state | lifted function | host locals (`_prN`, `_prcr`) | never; synced to L0 at sync points |
| L2, block-local temporaries | lifted block | already locals today (`a`, `b`, `cr_val`) | never |

**The contract**, as implemented in the T187 prototype (`tools/ppu_promote.py` docstring):

* **Sync point:** any statement that hands `ctx` to other code (a guest call, `DRAIN_TRAMPOLINE`,
  `ps3_indirect_call*`, `ps3_hle_call`, `lv2_syscall`, a ctx-taking helper), every `return` or trampoline
  hand-off, and the end of the function.
* **Before a sync point:** store the locals that may differ from `ctx` (a forward may-dirty dataflow over
  labels and gotos).
* **After a sync point:** reload every local, since the callee may change any of them.
* **Trace hooks:** store the dirty set only on the cold, enabled path, so traced values stay exact.
* **r1 is written through**, so stack walks and crash dumps stay correct.
* **Never touched:** guest memory, memory ordering, reservations, LR, CTR, XER, FPRs, VRs.
* **Fallback:** anything the pass cannot prove safe keeps the original lowering for that whole function.

## 3. Interfaces

```
ppu_lifter.py  --(body lines per function)-->  [_fuse_cr]  -->  [_with_trace_hooks]  -->  promote pass
     |                                                                                   (ppu_promote.py)
     +-- --promote-regs [--promote-max-regs N]                                            |
                                                                    promote_or_keep(lines) -> (decls, body, ok)
```

* **Input:** the lifter's own text grammar. Statements are `;`-terminated lines, `loc_X:` labels sit alone on a
  line, and gotos have literal targets. The pass parses no C++. When a line breaks the grammar, the function
  is refused.
* **Output:** the same function with `_prN` locals, plus a comment header that names the promoted count.
  It can be checked with `py -3 tools/ppu_promote.py in.cpp out.cpp`.
* **Stats:** `[promote-regs] P/F functions promoted; kept as lifted: <reason>: n, ...`.

## 4. Dataflow

* The CFG has one node per body line. Edges are fallthrough plus `goto loc_X`. A `return` line is a sync node.
* **may-dirty** is a forward union. The entry is clean, a sync node makes it clean, and r1 is never dirty.
  Spill set = `dirty_in` at a sync node.
* **Reload set** = all promoted registers (conservative). The next phase can intersect it with
  live-in-after-call (§6).

## 5. Synchronization boundaries (generic, not game-specific)

| Boundary | Today (T187) | Rationale |
|---|---|---|
| guest call / indirect call / trampoline | full sync | the callee reads and writes any GPR (ABI not trusted) |
| syscall / HLE | full sync | handlers read r3..r10 and write r3 |
| guest load/store helper | **no sync** | the helpers read only `reserve_addr`, `lr`, `thread_id` (VERIFIED by reading `ppu_loader.cpp`); the store-watch diagnostics can see stale GPRs |
| `lwarx`/`stwcx.` | no sync | the reservation lives in ctx fields that are not promoted |
| trace hook | cold-path sync | exact traces, no cost when off |
| exception / longjmp out of a helper | **not covered** | a host exception thrown from a helper would leave `ctx` stale; the lifted runtime has no such path today (HYPOTHESIS, needs an audit before default-on) |

The SPU sync workstream (T186 items 1, 2 and 10: MFC, GETLLAR, the reservation bitmap) owns `runtime/spu/*`.
T187 touches none of it.

## 6. Migration strategy

1. **Opt-in per build:** `--promote-regs`. The default lowering is byte-identical to before (VERIFIED, md5).
2. **Per-function fallback:** a function is either fully promoted or exactly as lifted.
3. **Differential gate:** any new lowering must pass `tools/test_ppu_promote.py` (fuzz plus kernels, plain and
   with trace) and a mutant control that must fail.
4. **Size and pressure policy:** the `--promote-max-regs N` cap (T187), then a loop-weighted, live-range-aware
   selection (next phase).
5. **Reload liveness:** after a call, reload only registers that are live-in. This removes about 17 % of the
   static growth (measured, `PERFORMANCE_RESULTS.md` §3).
6. **Shared cold spill:** emit one out-of-line spill-all block per function for trace hooks, instead of one per
   label. That block is 69 % of the static growth.
7. **CTR, then XER.CA,** as locals. CTR is stored on every `bdnz` today.
8. **SPU:** the same contract over `spu_context` GPRs within a dispatch group. Its sync points are channel ops
   and dispatch exits. Coordinate with the SPU sync owner before touching `spu_lifter.py`.
9. **In-game A/B:** only with explicit authorization, and only after steps 4–6.

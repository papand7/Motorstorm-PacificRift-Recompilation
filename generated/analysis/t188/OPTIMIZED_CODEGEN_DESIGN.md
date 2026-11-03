# T188: optimized PPU code generation, design

## 1. Goal and scope

Keep guest registers in host-optimizable C locals inside each lifted function, and make the guest state in `ctx` exact wherever anything else can observe it. Generic, opt-in and deterministic. Unsupported code is left exactly as the lifter emitted it. No MotorStorm addresses, functions or heuristics.

Promoted fields:
- `gpr[0..31]` (`uint64_t _pgN`)
- `fpr[0..31]` (`double _pfN`)
- `cr` (`uint32_t _pcr`)
- `xer` (`uint32_t _pxer`)
- `lr` and `ctr` (`uint64_t _plr`, `_pctr`)

Not promoted: `vr[]`, `fpscr`, `vscr`, `reserve_*`, `cia`, `vrsave`.

## 2. Where it sits

- `tools/ppu_regpromo.py` is a pass over the C text of one lifted function. It is used in two ways:
  - `ppu_lifter.py --promote-regs` (plus `--promote-inline-stores` when the TUs are built with `PPU_INLINE_STORES`), applied in `_function_def_lines`;
  - stand-alone on an existing lift: `ppu_regpromo.py in.cpp out.cpp --stats`, without relifting.
- Without the flag, lifter output is byte-identical to before (`test_ppu_regpromo`: the flag path equals the stand-alone pass, and unchanged without it).
- **Host-independent.** The pass only produces portable C. Register allocation, SSA, CR bit folding and dead-store elimination are left to the host compiler. That works on any target clang or MSVC supports.

## 3. Statement model

1. A small C scanner splits the body into top-level items: labels (`loc_X:`) and statements (expression statements, `{...}`, `if/else`, `switch`, loops, `do/while`). Nested statements stay opaque text.
2. Each statement is classified:
   - **pure**: it does not pass `ctx` anywhere. Field references are renamed to locals.
   - **context mode**: it contains `ctx` other than as `ctx->field` (a call, a drain, an HLE/syscall dispatch, a helper taking the context). It runs unchanged against `ctx`.
   - **hook**: `PPU_TR_ENTER/RET/BB(ctx, ...)`. It is expanded to its header definition, `if (__builtin_expect(g_ppu_trace_mask & bit, 0)) { sync; ppu_trace_*(ctx, ...); reload; }`, so the sync only happens when tracing is on.
3. Per pure statement:
   - **use**: the fields it reads;
   - **defs**: the fields it writes (assignments, `++/--`, address taken);
   - **kill**: a field it defines unconditionally (a top-level `F = expr;`);
   - whether it can `return`, its `goto` targets, whether it falls through, and whether it makes an out-of-line store call (`vm_write*`, `ppu_st[wd]cx*`).
4. The CFG has statement granularity: `goto` edges, fall-through edges, and an exit node.

## 4. Dataflow (three analyses) and the correctness invariant

- **Dirty (forward):** the locals that may differ from `ctx`.
  - Defs make a local dirty; a context-mode statement makes everything clean, because it is preceded by a write-back.
  - At an ordinary merge: dirty on any incoming path means dirty.
  - At a loop header: only what is dirty on a back edge stays dirty. Anything else dirty on entry is written back once, on the entry edge, so it is not written back at every call inside the loop.
- **Next use before a sync (backward):** the locals read, on some path, before the next context-mode statement.
- **Valid (forward):** the locals known to hold the current value.
  - Locals are loaded lazily, at first use after a sync.
  - At a merge, a local stays valid if it is valid on some incoming edge and used before the next sync; the other edges reload it, so a loop-invariant value is loaded once.
  - With out-of-line stores, a clean local is dropped from the valid set at a store call and re-read from `ctx` (the default). `--promote-inline-stores` keeps it.
- **Invariant: dirty ⊆ valid.** Whatever is not valid is clean, so `ctx` holds its current value and a reload is always correct. Every merge adds its dirty set to the valid set, and an edge loads what its target needs valid.

Emitted synchronization:

| Where | Code |
|---|---|
| Before a context-mode statement | write back the dirty locals |
| After it, and on each of its `goto` edges | load what the target needs valid |
| Before every `return` in a pure statement, and at the end of the body | write back the dirty locals and those the statement defines |
| Each edge | write back what is dirty at the source but not at the target, then load what is valid at the target but not at the source |
| Pure statement | load the locals it needs that are not yet valid |
| Hook (inside the enabled branch only) | write back the dirty locals; reload the valid ones after the call |

Values are never reordered across a sync point, and no guest instruction text changes except the field-to-local renaming. At every boundary, `ctx` therefore holds exactly what the unpromoted body would have stored there.

## 5. Lazy CR materialization, for free

`_pcr` is an ordinary local:
- `cmpw` + `beq` becomes `_pcr = (_pcr & ~M) | (v << s); if ((_pcr >> b) & 1) goto L;`. The host compiler folds the bit test back onto the comparison and keeps `_pcr` in a register.
- The full 32-bit CR is materialized only where it is written back (calls, returns).
- XER SO, read by every compare, is a register value, not a load.
- No CR liveness model was needed in the lifter.

## 6. Fallbacks (the function is emitted unchanged)

- A register file accessed without a constant index (`ctx->gpr[i]`), or a register file referenced without an index.
- A label inside a nested statement, a `goto` to an unknown label, or a preprocessor line in a body.
- An existing identifier that clashes with a promoted-local name.
- An FPR whose address is taken for anything but a `memcpy` operand (possible pointer type-punning). That FPR alone stays in `ctx`.

On the MotorStorm lift, TUs `000` and `006`: every function that touches a register was promoted. The only functions left unchanged were the 940 that touch none (two-line trampolines).

## 7. Determinism, debug and release

- The output depends only on the input text. Masks are iterated in key order and worklists have a fixed order (`test_ppu_regpromo`: identical output on repeat).
- **Debug builds:** locals are visible to a host debugger. The `g_active_ctx`-based diagnostics (watchpoints, dumps from inside `vm_*`, crash handlers) can see register values older than the locals; this is documented, and those features should run on an unpromoted lift. Hooks traced with `g_ppu_trace_mask` still see exact state.
- **Release:** the flag is independent of build type.

## 8. Workload dependence (why opt-in)

| Code | Effect |
|---|---|
| Loops without calls | The largest gains: the CR and loop-carried registers stay in host registers |
| Call-dense code | Neutral after the loop-header rule: the boundaries need the same stores the baseline does |
| Store-dense code with out-of-line stores | Small or negative: a dirty value must survive each store call (a host register or a spill) and still be written back. Inline stores remove the call (`ARCHITECTURE_AUDIT.md` §5, item 2) |

A title whose hot code is short call-heavy functions will see little gain. One dominated by loops over game data (physics, culling, decompression, animation) gains most. Measure per title, which `tools/bench_ppu_regpromo.py` and the stand-alone mode make cheap.

# T191 cache-coherence contract

## Contract

1. **A cache entry holds no ownership state.** It maps `(pc, img, ovl)` to the function the registry gives for exactly those inputs. Ownership (`image_id`, `resident_ovl`, the code-slot owner) is re-read from the context on every branch and forms the key. Changing ownership changes the key, so it cannot reach a stale entry.
2. **An entry is valid only for the registry epoch it was filled in.** `g_spu_registry_epoch` is bumped, with release ordering, by every registry mutation (`spu_register_function`).
3. **Only provably ordinary branches use the cache** (`FAST_DISPATCH_DESIGN.md`). Branches whose target depends on anything else (local-store contents, task tables, relocation, policy state) never read or fill it.
4. **The cache is thread-local.** A context runs on one host thread at a time, so no entry is ever read while another thread writes it.

## Every way executable state or ownership can change

| Change | Where it happens | Effect on the fast path |
|---|---|---|
| DMA of code into LS (`GET`, `GETL`) | `note_get` and the `spu_overlay_*` / `spu_wws_*` marking code (`spu_channels.c` ~2280-2580) | writes `ctx->resident_ovl` or `ctx->resident_code[slot]` only. Both are inputs to the key (slots through the owner scan). **VERIFIED:** grep of all writers: they are in `spu_channels.c` and only touch the context |
| Direct LS writes (self-modifying code) | stores, `spu_ls_write*` | the resolver does not read LS bytes to pick a registered function, so a hit is unchanged by the write. Only misses read LS, and misses are not cached |
| Overlay load / eviction / replacement | as DMA above, plus "a GET into a resident span drops it" | same fields, same argument |
| Job replacement, relocatable job load | `spu_wws_job_enter`, `resident_code[].link_base` | the entry job validation runs only in policy mode (resolver). Relocatable slots are not cached (resolver) |
| Task switching | `image_id`, `resident_task` set by the policy/workload code; `TaskInfo` in LS | `image_id` is in the key. `resident_task` and the TaskInfo read are consulted only for `pc >= 0x3000`, and the fast path refuses that range whenever a task registration exists or `resident_task` is set |
| Runtime code registration | `spu_register_function` (append-only; nothing removes entries) | epoch bump. Entries from an older epoch are never used. Today an append cannot change an existing hit (first match in a chain wins, appends go last), so the epoch is defence in depth against a future unregistration; the tests check the mechanism (a first branch after a registration is a refill), not an observable difference |
| Stack-reset entry registration | `spu_register_stack_reset_entry` | read by `spu_check_stack_reset`, which the fast path calls on every dispatch with the resolved function, exactly as the resolver does |
| Context re-creation at the same address | `spu_context_init` on a stack local | the cache is keyed by values, not by context identity. A recreated context with different fields produces different keys. 2,000 recreations tested |
| Interrupt delivery / return | `irq_saved`, `srr0` | a pending iret is an ineligible branch (resolver) |
| Process-global modes | tracing knob, diagnostic env vars | tracing knob read per branch; env vars checked once at start (they are never changed during a run) |

## What is not proven

- Registry **removal** does not exist today. If one is added it must bump `g_spu_registry_epoch`; a test that registers, dispatches, removes and dispatches is then required.
- Epoch wrap-around (2^32 registrations) is not handled; the registry is bounded far below that (`SPU_FN_REGISTRY_MAX`).
- Dispatches that bypass `spu_indirect_branch` (statically linked direct calls, `spu_indirect_branch_mt`) neither use nor invalidate the cache. They do not need to: entries are values.
- The fast path assumes `spu_lookup` is a pure function of its arguments and the registry, which it is (its only side effect is a deduplicated log line).
- Not exercised in this offline work: a real lifted job that changes ownership mid-run under a policy module (policy mode is excluded), and the PS3_FTRACE_SPUJOB tracing path (it is checked per branch; the existing `test_spu_jobspan` covers the resolver side).

If complete invalidation could not be shown, the brief required restricting the fast path to verified stable ownership. That is what is done: ownership is never cached, and unstable ownership (policy mode, task region with registrations, relocatable slots, pending iret, tracing) is refused.

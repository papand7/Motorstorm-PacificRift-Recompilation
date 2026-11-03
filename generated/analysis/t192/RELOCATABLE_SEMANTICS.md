# T192 Phase B: relocatable SPU code slot semantics

Source audit of `runtime/spu/spu_channels.c`, `spu_reloc.h`, `spu_dma.h` at T191 `32203ae6`. Labels: VERIFIED = read in the code and exercised by the differential tests; PARTIAL / HYPOTHESIS as stated. No game launched.

## Slot state and who may write it

A slot is `spu_context.resident_code[4]` = `{lsa, size, source_ea, link_base, image_id}` (`spu_context.h`), one array per SPU context. VERIFIED by grep: the only writers outside `spu_context_init` are in `spu_channels.c`:

| Writer | Where it runs | Effect |
|---|---|---|
| `spu_overlay_note_get` | the SPU host thread, from the MFC GET path (`spu_dma.h`) | an overlapping GET clears a relocatable slot (`image_id = 0`, or `SPU_OVL_UNRECOGNIZED` for fingerprinted bodies); a GET that matches a registered overlay source installs a plain (non-relocatable) slot |
| `spu_wws_job_enter` | the SPU host thread, only from `spu_indirect_branch` **in policy mode** with a registered Wws PM | validates the module, evicts overlapped slots, installs `{lsa=base, size=span, link_base, image_id}` |
| `spu_indirect_branch` (resolver) | same thread | reads the slots; writes `reloc_delta` |

Both writers run on the context's own host thread, synchronously, between two branches. No other thread writes a context's slots. (PARTIAL: a PPU write into a running SPU's local store, or an SPU-to-SPU DMA into it, is not tracked by either writer. That is true of the resolver as well; see "what the cache cannot know".)

## Lifecycle, in order

1. **Slot allocation.** `spu_wws_job_enter`: a free slot (`image_id == 0`), else a relocatable slot in round-robin (`t_reloc_rr`); none -> `SPU_RELOC_NO_SLOT`, job interpreted.
2. **Code registration.** Generated TU registers the lifted functions under `SPU_RELOC_KEY_BIT | (link-base address)` for the module's image id (`spu_register_function`); registry is append-only; registration bumps `g_spu_registry_epoch` (T191).
3. **DMA loading.** The job manager GETs the module into the code buffer; `spu_overlay_note_get` clears any relocatable slot overlapping the range.
4. **Relocation.** There is no code patching. The lift is position independent (PC-relative, `lqr`/`stqr`); the load address enters only through `reloc_delta = lsa - link_base`, which the lifted code adds to every observable pc (`SPU_RA`).
5. **Entry-point selection.** `spu_wws_job_enter` (policy mode only): module identified by its 16 identifier bytes, entry offset and 16 entry bytes checked, body hash on first use at the base (`PS3_SPU_WWS_AOT_VERIFY=1`: every entry). A mismatch leaves the job to the interpreter.
6. **Execution.** Lifted functions run; every indirect branch calls `spu_indirect_branch`.
7. **Branches within the slot.** The resolver finds the slot containing `pc` (first match of 4), sets `reloc_delta = lsa - link_base`, and looks up `((pc - lsa + link_base) | KEY_BIT, owner)`.
8. **Job completion.** The job returns to the PM through a branch with `policy_mode` set (resolver path) or to `0x3FF00` (resolver path).
9. **Slot reuse.** The next `spu_wws_job_enter` finds the slot "already validated at this base" (resident), or evicts and reinstalls.
10. **Ownership change and invalidation.** By overwriting the slot fields (above). See `CACHE_INVALIDATION.md`.

## Which resolver operations are mandatory at every branch

For a branch with `policy_mode == 0`, `irq_saved == 0`, tracing off, pc not 0xA70 / 0x3FF00, image != 23, pc < 0x3000 or no task state, the resolver does, in order (read from the code):

| Resolver step | Needed per branch for an intra-slot branch? |
|---|---|
| mask pc | yes (kept) |
| job-span tracing | only when tracing: fast path declines |
| WWS stats / job enter | only in policy mode: fast path declines |
| interrupt-return restore | only when `irq_saved`: declines |
| policy kernel services, taskset syscall, image 23 | only at their addresses / states: declines |
| `resident_task` clear (pc < 0x3000) / TaskInfo ownership | clear is replicated; ownership read declines when tasks exist |
| **slot scan, `reloc_delta` write, lookup** | **yes, but it is a pure function of (slot fields, pc, registry)** |
| overlay / image lookup | not reached when a slot owns the pc |
| unrecognized-overlay refusal | declines (owner <= 0) |
| job-return at 0x3FF00 | declines |
| miss handling | declines (resolver) |
| `spu_check_stack_reset` | replicated before the tail call |

So the only per-branch effects of an ordinary intra-slot branch are: one write of `reloc_delta`, the tail call, and the stack-reset check. Everything else is a state transition that cannot occur on that branch, or is handled by declining.

## Can ordinary intra-slot branches bypass the full resolver? **Yes, with a stateless key.**

The cache stores no ownership. On each branch the live slot fields are read from the context and form the key: `(rel = pc - lsa + link_base | KEY_BIT, owner = image_id, mode = reloc)`. A cache hit means "the resolver's lookup, for this exact (relative address, owner), returned this function, and the registry has not changed since". The delta is recomputed from the live `lsa` and `link_base` and written on every hit. Consequences, all asserted by `tests/test_spu_ib_fast.c reloc`:

- the same module moved to another base hits and gets the new delta (not a cached one);
- the same address owned by a different module (same `lsa`, other `image_id`) is a different key: the old entry is not served;
- a changed `link_base` changes the key and the delta;
- eviction (`image_id = 0`), unrecognized owners, DMA clears, slot size boundaries and slot order are re-read each branch.

## "Does matching the code-slot address prove the code is unchanged?" **No, and neither does the resolver.**

The fast path trusts exactly what the resolver trusts: the slot metadata. Whether the bytes in local store still equal the lifted module is established at job entry (identifier bytes, entry bytes, body hash; `PS3_SPU_WWS_AOT_VERIFY=1` re-hashes per entry) and by DMA invalidation. `spu_reloc.h` itself states what is not caught: a write into the span that is not a DMA GET (an SPU store, GETLLAR, a PPU LS write) is caught only at the next entry with VERIFY on, and "a write while the job is running is not". The fast path adds no new exposure and removes none. Nothing in the runtime offers a per-slot generation counter; the ownership fields are the generation.

A true code generation counter (bumped by every write into a slot span) would be a new mechanism; it is not needed for equivalence with the resolver, and it would need a store hook the runtime does not have (`NEXT_STEPS.md`).

## What the fast path still sends to the resolver

Entry (`policy_mode`), exit through return/`0x3FF00`, ownership changes (policy mode or DMA, both occur between branches and are re-read), interrupt returns, tracing, task-region branches when task state exists, unrecognized owners, and every lookup miss (including targets that are unregistered or misaligned).

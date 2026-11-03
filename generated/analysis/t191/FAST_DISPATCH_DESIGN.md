# T191 Phase B: fast dispatch design

## Choice

A **thread-local, direct-mapped memo of the resolver's ordinary outcome**, guarded by an **eligibility test** that proves every other resolver step is a no-op, with the **unchanged resolver as the fallback** for everything else.

Alternatives rejected:

| Option | Why not |
|---|---|
| Enable `spu_indirect_branch_mt` | not equivalent (`DISPATCH_ARCHITECTURE_AUDIT.md` section 3) |
| A per-SPU (per-context) table | contexts are stack locals recreated per run; the table would be cold for every Havok-sized job |
| A global shared table | needs synchronization or a torn-entry protocol on every branch; the requirement is no global lock |
| Caching host function pointers inside the context | adds state that must be invalidated at each of the ownership writers |
| Caching the state-transition steps | they are state transitions; they must run |

## Mechanism (`runtime/spu/spu_channels.c`)

Hook: in `spu_indirect_branch`, right after the job-span tracing block, behind `g_spu_ib_fast != 0`. Off (the default): one load and a predicted branch.

```
if (g_spu_ib_fast > 0 && !(policy_mode | irq_saved)) {
    fn = spu_ib_fast_try(ctx)         // NULL when not provably ordinary, or a miss
    if (fn) { spu_check_stack_reset(ctx, fn); tail-call fn(ctx); }
}
... the unchanged resolver ...
```

`spu_ib_fast_try` returns NULL (resolver runs) when:
- the job-span tracing knob is on;
- `pc` is the taskset syscall address, the job-return address, or `image_id` is the CRI-hack image;
- `pc >= 0x3000` and any task entry / ELF is registered or `resident_task` is set (ownership is read from LS);
- the first code slot containing `pc` is relocatable or has a non-positive owner;
- the lookup misses (a miss is never cached).

Otherwise it computes the **key** `(pc, img, ovl)`:
- normal: `img = image_id`, `ovl = resident_ovl`;
- a non-relocatable code-slot owner contains `pc`: `img = owner`, `ovl = -2` ("owner mode"; the resolver ignores overlay and image then).

It looks the key up in a 512-entry direct-mapped table `{pc, img, ovl, epoch, fn}` (24 bytes, **thread-local**). On a hit with the current registry epoch it returns `fn`. On a miss it does what the resolver does (`ovl ? lookup(pc, ovl) : none`, then `lookup(pc, img)`; or the owner lookup) and fills the entry.

Like the resolver, the fast path also sets `resident_task = 0` for `pc < 0x3000` (a state write the resolver makes on every branch there).

## Properties

| Requirement | How |
|---|---|
| Opt-in, default resolver unchanged | `PS3_SPU_IB_FAST=1`, read once. Unset, `0`, or anything but `1`: off. The resolver code is not edited |
| Independent of T187 MFC and T189 inline stores | no shared code, flags or state; separate environment variable |
| No game addresses or assumptions | constants are the existing architectural ones (LS mask, taskset region, the two reserved service addresses, the CRI image id) already named in the resolver |
| Safe concurrency, no lock | the table is thread-local; the only shared read is the registry epoch (one acquire load) |
| Tracing and debugging functional | job-span tracing is checked per branch; the eight resolver-only diagnostic variables disable the fast path for the process with a log line; all other debug hooks are in code the fast path never replaces |
| Deterministic fallback | every non-ordinary branch and every miss runs the unmodified resolver on an unmodified context (the one `resident_task = 0` write is idempotent: the resolver makes it again) |
| Cache hits cost | no locks, no allocation, no logging. The cross-image report is emitted once, on the filling lookup (the resolver would repeat a deduplicated line) |

## Memory

512 x 24 B = 12 KB of TLS per host thread (the TLS block is allocated at thread creation whether or not the thread dispatches). With ~100 host threads that is ~1.2 MB, only when the binary contains the code; the table is zero-filled and untouched by threads that never dispatch.

## Known cost

When the switch is on and a branch is not eligible, it pays the eligibility work and then the resolver:
- policy-mode branches: about +3 %;
- relocatable-slot branches: about +30 % of a 6.3 ns call (1.7-2 ns);

see `PERFORMANCE_RESULTS.md`. The next step (`NEXT_STEPS.md`) caches the relocatable owner, which removes the second.

# T192 generalization

## Assumptions (all inherited from the resolver; none title-specific)

| Assumption | Source |
|---|---|
| 256 KB local store, pc masked with `SPU_LS_MASK` | architecture |
| Task-code region starts at LS 0x3000; syscall address 0xA70; job-return 0x3FF00; image 23 hack | existing resolver constants (SPURS ABI, one legacy title hack that the fast path simply refuses) |
| A relocatable module is a position-independent lift registered under `SPU_RELOC_KEY_BIT | link-base address` and published with `reloc_delta = lsa - link_base` | the generic `spu_reloc.h` contract, not a game layout |
| Registry append-only, at most 262,144 functions | `spu_register_function` |

No MotorStorm function addresses, Wws job-manager layout, Havok task shapes, code bases (0x4000 is only a test link base), program sizes or overlay lifetimes appear in the fast path or in the tests. The harness uses manufactured stubs registered under arbitrary image ids (4 images, 3 overlays, 2 slot owners, a wildcard) at synthetic addresses; "Wws-style" in the benchmark means only the shape *install a position-independent module, run a few intra-module branches, leave, replace it*, with synthetic keys.

## Workload shapes

| Shape | Behaviour with `PS3_SPU_IB_FAST=1` | Measured (`PERFORMANCE_RESULTS.md`, B/A) |
|---|---|---|
| Long-lived SPU program, a few stable targets | hit | 0.73x |
| Large jump table (200 targets) | hit while the working set fits 512 entries per thread (direct-mapped) | 0.92x |
| Overlay-heavy (resident overlay swapped each branch) | hit after first use of each (pc, image, overlay) | 0.68x |
| Frequently replaced relocatable jobs (new base / other owner each time) | hit: the key is base-independent, the delta recomputed | 0.82-0.89x |
| Job-style (install, 15 intra-slot branches, exit) | hit | 0.89x |
| Multiple concurrent SPUs | per-thread cache, no sharing; ratios unchanged up to 8 threads | 0.71-0.92x |
| Policy-module (SPURS kernel) code, interrupt return, tracing, task region with registered tasks | resolver; costs the eligibility check | 1.07x (policy) |
| Invalid / unregistered targets | resolver miss path | 1.01x |
| DMA-heavy programs | DMA only matters through `spu_overlay_note_get`, which already clears slots; nothing cached about it | covered by `reloc` / random tests |
| Different SPU task schedulers | any scheduler that moves a program between host threads or contexts is safe: no cache entry refers to a context | context re-creation tests |
| Future statically recompiled titles | works for any lift that dispatches through `spu_indirect_branch`; lifts using `spu_indirect_branch_mt` do not reach it | - |

## Host-specific assumptions (isolated and documented)

- Thread-local storage through `SPU_TLS` (`__thread` / `__declspec(thread)`); 12 KB per host thread, allocated with the thread.
- `__builtin_expect`, `__atomic_*` and (clang only) `musttail` tail calls; non-clang builds fall back to a plain call and return.
- x86: the acquire load of the epoch is a plain load; on weaker memory models it is still correct (acquire/release pair) but not measured.
- Windows was built and run; POSIX builds compile the same source and were not run here.
- The test harness builds with the repository's clang shim; sanitizers: ASan and UBSan only (ThreadSanitizer does not exist for Windows targets).

## Limitations

- Direct-mapped, no adaptive sizing; conflicting hot targets refill (`p_conflict`).
- The fast path is exact only relative to the resolver; it cannot detect guest writes into a slot that bypass `spu_overlay_note_get` (see `CACHE_INVALIDATION.md`).
- Relocatable slots only when the lookup resolves (registered key). Anything else keeps the resolver's behaviour including the interpreter fallback.
- Not tested with a real lifted program or with homebrew SPU code (none available offline in this workspace); not run in a game.

# T192 cache coherence and invalidation

Extends `generated/analysis/t191/CACHE_COHERENCE.md`. The T191 contract is unchanged: the cache is thread-local and holds no ownership state; the key is everything the resolver's lookup depends on, re-read from the context at every branch; the one thing a key cannot capture is the registry, covered by an epoch.

## Entry format and key modes (512 direct-mapped entries per host thread, 24 B each)

`{ key, img, ovl, epoch, fn }`; hash over `(key >> 2, img, ovl)`.

| Mode (`ovl`) | `key` | `img` | When |
|---|---|---|---|
| `>= 0` | pc | context image | pc not in a slot; `ovl` = resident overlay (0 none) |
| `-2` | pc | slot owner | pc inside a plain (non-relocatable) slot |
| `-3` (T192) | `(pc - lsa + link_base) \| SPU_RELOC_KEY_BIT` | slot owner | pc inside a relocatable slot |
| `< 0` as `resident_ovl` | - | - | refused (`d_other`): it would collide with the modes above |

`reloc_delta` is not in the entry. It is `lsa - link_base` of the live slot, written on every hit and fill, exactly where the resolver writes it (before the lookup; on a miss the resolver itself writes it).

## Invalidation events and ordering

| Event | Who | Effect on the cache | Ordering requirement | Test |
|---|---|---|---|---|
| Function registered (new image, overlay, relocatable key) | `spu_register_function` | `g_spu_registry_epoch` += 1 (release); entries of older epochs miss (`p_epoch`) | the epoch is bumped after the function is published, before any thread that observes the function can have cached a decision made without it; a thread reads the epoch (acquire) before its lookup and stamps the entry with that value, so a lookup racing a registration stamps an old epoch and refills | `reloc`: epoch-moved refill; shadowing test; `random --reloc` registers at run time |
| Registration shadows an older answer (a function for `(pc, overlay)` after the entry resolved `(pc, image)`) | same | same: dropped by the epoch | - | `reloc`: "shadow" (new overlay function is dispatched); negative control 15 |
| Epoch counter wrap | - | not reachable: the registry holds at most 262,144 functions (`SPU_FN_REGISTRY_MAX`), so the counter stays far below 2^32; an entry stamped 0xFFFFFFFF is dropped by the registration that wraps to 0 | - | `reloc`: forced wrap |
| Slot replaced (other owner, same address) | `spu_wws_job_enter` | none needed: owner is in the key | before the next branch (same thread) | `reloc`: same-address replacement, replacement back |
| Slot moved (other `lsa`, same module) | same | none needed: key is relative; delta recomputed | - | `reloc`: moved to another base |
| `link_base` changed | same | none needed: it is in the key and the delta | - | `reloc`: link base changed |
| Slot evicted / unrecognized | `spu_overlay_note_get`, `spu_wws_job_enter` | none needed: ownership is re-read; eviction changes which mode the branch is in | - | `reloc`: evicted, unrecognized, DMA |
| DMA GET overlapping a relocatable slot (code update) | `spu_overlay_note_get` | none needed (slot cleared first) | the DMA hook runs in the MFC GET path before the next branch of that thread | `reloc`: DMA over and outside the slot |
| Overlay becomes resident / evicted | `spu_overlay_note_get` | none needed: `resident_ovl` is in the key | - | T191 directed |
| Task switch / new job on the same host thread | policy / scheduler | none needed: `image_id` and `resident_task` are context fields in the key or force the resolver | `resident_task` cleared below 0x3000 exactly as the resolver does | T191 directed / random |
| Context destroyed and another created at the same address | runtime | none needed: nothing in the cache refers to a context | - | 2,000 re-creations |
| Host thread exits | OS | the TLS array dies with the thread | - | - |
| Tracing / diagnostic env var set | environment | fast path switched off (env) or declines per branch (tracing) | read once at the first branch / per branch | `envinit`, `reloc` (`d_trace`) |
| Self-modifying code, SPU store or PPU write into a slot span | guest | **not seen** (nor by the resolver) | - | not testable at this level; `spu_reloc.h` documents it |

Memory ordering: the cache is only ever read and written by its own thread. The only shared datum is the epoch. A release-add in the registrant and an acquire-load in the dispatching thread are enough; no lock is taken on a hit.

## What would break it (and the control that proves the test would notice)

17 negative controls (textual mutants of `spu_channels.c`, each must fail the suite; `CORRECTNESS_RESULTS.md`): key omits overlay / image; policy mode or irq ignored; `resident_task` clear skipped; delta not written on hit / on fill; slot link base ignored in the key; evicted slot still the owner; slot size ignored; negative overlay accepted; knob ignored; probe classification dropped; slot owners ignored; epoch not compared; stack-reset skipped; task ownership not consulted.

## Not mechanised, and why that is not a gap

No per-slot code generation counter exists in the runtime and none is added: equivalence with the resolver only needs the slot fields, which are read live. If the project later wants stronger protection against writes that bypass `spu_overlay_note_get`, it needs a store/DMA write-watch on slot spans (cost on every LS store) and that would benefit the resolver as much as the cache (`NEXT_STEPS.md`).

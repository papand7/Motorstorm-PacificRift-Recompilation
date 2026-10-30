# T171: depth and stencil audit

| State | Guest (ops 1110-1112) | Host default | Verdict |
|---|---|---|---|
| Depth test / func | on, LEQUAL | on, LEQUAL | matches |
| Depth write | **off** | **on** (default guest-FP PSO) | mismatch, not the cause of the mirror |
| Stencil | on, NOTEQUAL ref 128 mask 128 (ds_key `0x0004040202ED`) | no stencil by default | mismatch, no visible effect expected here |
| Cull | on, face 0x0405 | see `RSX_DEPTH_STATE` work | unchanged |

- **VERIFIED:** all opaque stencil refs in D1 are 0, 2, 30, 31, 32. Bit 7 is never set, so NOTEQUAL 128/128 passes everywhere on terrain and stencil cannot punch holes in the tracks.
- **VERIFIED in fixture:** with depth writes on, the track still relights (32) but a later object is rejected (0). So the host's forced depth write is a real, separate mismatch that this task does not fix.
- Its fix, `RSX_DEPTH_STATE=1`, stays off: T169 tied it to vehicle speckling, and that is still unexplained. T171 does not change depth state, so it cannot reintroduce the speckle. No depth bias was added.
- The GREATER control leaves terrain unrelit (32), so the fixture detects a wrong depth function.

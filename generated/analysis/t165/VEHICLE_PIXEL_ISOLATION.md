# T165: pixel isolation

**The per-draw offline experiments were not done (BLOCKED).** RSXI records state and pass images, not vertex data or textures sufficient to replay a vehicle draw, and no replay tool exists. A synthetic scene wouldn't count as vehicle evidence, so none is claimed.

| Experiment | Status | Finding |
|---|---|---|
| sRGB decode + encode on the real scene | **Done in game**: B3 vs X1, same frame | Changes the defective tyre pixels; near-black 58.1 % to 24.9 % |
| Decode and encode independently | Not run in game. WARP fixture only | Bits 0x1 and 0x4 behave as defined on a test scene |
| Missing textures | Done from state | None on the vehicle-bearing draws: `noslot=0`, no null before op 586 |
| Sign expansion | Done from state | 0 requests, rejected |
| Alpha test | Partly, from state | All main-scene draws captured show the same `alpha` register `0x000700`. Decoding that as "disabled" isn't verified |
| Sampler | Register decode only | Unit 0 mismatch verified; pixel effect untested |
| Replace textures, forced colour, blend, depth, cull, attributes, constants | BLOCKED | No replay harness or game launch available. Blend: main-scene draws before op 568 report blend off |

**Confirmed:** transfers change the defective pixels, in the requested direction at both ends of the range.
**Rejected:** missing textures and sign expansion on these draws.
**Open:** whether a further cause darkens the grid vehicles in the screenshot.

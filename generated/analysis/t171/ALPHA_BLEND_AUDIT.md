# T171: alpha and blend audit

| State | Guest (D1 f005110, ops 1110-1112) | Host | Verdict |
|---|---|---|---|
| Blend enable | off (key 0) | off | matches, VERIFIED |
| Colour write mask | 15 | 15 | matches, VERIFIED |
| Alpha test | off (`0x000700`) | off | matches, VERIFIED |
| Output alpha | written, no effect on colour with blending off | same | fixture: alpha 0 still relit, 32/32 |

The defect is not an alpha or blend fault, so no blend or alpha state changed and no global alpha rule was added.
Fixture negative controls confirm the fixture can see such faults: blending by alpha 0 leaves terrain (32), and write mask 0 leaves terrain (32).
Later blended water, surf and foliage (ops 1143-1243) were not altered in blend state. Two of those programs read WPOS (`0x07200641`, `0x070B0701`), so their lookup coordinate changes under the fix; their blend state does not.

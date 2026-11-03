# T171: texture alpha and formats

Track units in D1 f005110:

| Unit | Address | Size | Format | Role |
|---|---|---|---|---|
| 0 | `0x02410000` | 128x128 | 0x85 (addr 0x60010101) | normal map (from shader use) |
| 1 | `0x02425580` | 128x128 | 0x85 | normal map (from shader use) |
| 2 | `0x00750000` | 2544x715 | 0xA5 | the scene, `rt_exact` |
| 3 | `0x06EE5580` | 512x512 | 0x86 | use not established |

Blending and alpha test are off on this draw, so texture alpha cannot produce transparency here. The fixture's alpha 0 arm still relights (32/32). No decoding or format code changed, and alpha was not forced to 1.0.
Unit 2 is 2544 wide while the viewport is 1272; the window mapping in the lookup accounts for this (see the feedback report). Per-texel contents of units 0, 1 and 3 were not audited, because the mirror is sufficient to explain the verified numeric result.

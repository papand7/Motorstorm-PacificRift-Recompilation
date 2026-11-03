# T168: original visibility system

Static analysis of the retail code. No game was launched, so nothing here was observed at run time for this task.
Full evidence with SPU offsets: `vis/STATIC_VISIBILITY.md`. Addresses are retail EAs. Names come from the dev build (`c38/rv/resourceviewer.elf`).

## Result

- **VERIFIED (static):** the game culls per component on the SPU, in `pvsjob`, before any RSX command is built. `RenderableProxy::Render` and `ExecutePushBuffer` only skip empty lists.
- **VERIFIED (static):** the host stubs and hooks nothing on this path. The lifted `pvsjob` has 0 unsupported instructions and 0 interpreter handoffs.
- **PARTIAL:** no divergence that changes which components are selected was found, but it has not been compared against a hardware run, and per-run use of the lifted image was not checked.

## Order of tests before any RSX command

| # | Stage | Address | Culls? | Label |
|---|---|---|---|---|
| 1 | `ComputeOcclusion` per view | `0x3315F8` and others in `0x330A54` | builds planes only | VERIFIED |
| 2 | LOD reference setter, once per frame | `0x45BBC8` | no | VERIFIED call, PARTIAL name |
| 3 | Per view: wait for occluders, fetch planes, 24 kicks | `0x331DA0`–`0x331E28` | no | VERIFIED |
| 4 | `KickVisibility` → `Vis::Kick` → `Start` → builder | `0x457BB0`, `0x45CB30`, `0x5F69B8`, `0x5F61B8` | job per 304 components | VERIFIED |
| 5 | `pvsjob` | `0xFD3180` | **yes** | VERIFIED |
| 6 | `groundrushvisibilityjob` (ground-detail cells) | `0xFDAC00` | yes: sphere vs 6 planes | VERIFIED job, PARTIAL order |
| 7 | `Vis::Wait`, `Finalize`, `RenderableProxy::Render` | `0x45CAA8`, `0x5F74B0`, `0x482680` | count 0 skips the draw | VERIFIED |
| 8 | `ExecutePushBuffer`, `renderablejob`, FIFO CALL | `0x50D868` | no | PARTIAL-strong (not all 16 `fcgt` sites read) |

## `pvsjob` per-component tests, in order

| # | Test | Fail counter | Label |
|---|---|---|---|
| 1 | Hide mask `comp+0x2A` | +0x14 | VERIFIED |
| 2 | World OBB 8 corners vs 6 frustum planes | +0x04 | VERIFIED |
| 3 | LOD selection (never rejects) | none | VERIFIED |
| 4 | Screen size: perspective, or projected sphere at `0xE00` | +0x08 | VERIFIED |
| 5 | Occluder planesets: all corners behind all planes | +0x00 | VERIFIED |
| 6 | Visible (+0x0C), and Z-pass eligible (+0x10) | none | VERIFIED |

Output is three entry lists and three sort-key lists, 4 B per component each, plus a trailer at +0x1C80. This corrects T84's "24-byte records". Reading the lists as Unblended, Blended and ZPass is HYPOTHESIS (strong).

## Other systems

| System | Finding | Label |
|---|---|---|
| Occluders | Data-driven from world solids named `*_OCC`. Active in race: unknown. One read of `[r3+0x10]` at `0x5F5628` settles it | BLOCKED statically |
| GPU occlusion | **The game has none.** The "ZPASS" reports are frame timers: slots `0x14100`–`0x14130`, in `DisplayATG::Present` `0x5226A8`. The code reads only the timestamps at +0 and +0x10, and I re-read that code at `0x5228D0` myself. The value word at +8, which the host fills with 0xFFFF, is never read. No PPU code enables sample counting | VERIFIED; precompiled state packets can't be excluded, but nothing reads a result |
| Semaphore `0x522950` | Flip pacing, not occlusion. This corrects T84B | VERIFIED structure, HYPOTHESIS vblank |
| Terrain patches | No dedicated selection job found; world geometry appears to use ordinary scene lists | HYPOTHESIS |
| LOD | Selected inside `pvsjob` at `0x1448` from distance, scale, modifier and min LOD. Reads no time, frame rate or reports. Upstream setter callers not found | VERIFIED job, PARTIAL upstream |
| Shadow casters | Views 1–3 have their own frusta and `Vis`, and share the LOD reference. "Cascades" is PARTIAL; frustum construction not traced | VERIFIED structure |
| Reflection | Same kick path; whether it reuses view 0's PVS is unproven | HYPOTHESIS |
| ZCull | Regions are bound and the host only records them. It can only reject hidden fragments early, so the effect should be cost only | PARTIAL, reasoned |

## Host divergences

| Divergence | Effect | Label |
|---|---|---|
| Report value constant 0xFFFF | None: unread | VERIFIED |
| Report timestamp is host walker time | GPU-time statistic only | PARTIAL |
| ZCull not modelled | Cost only | PARTIAL |
| Near/far clip: see below | **Possible image difference** | HYPOTHESIS |

**Near/far clip (open).** Guest PSOs leave `DepthClipEnable` off, and the harness confirms a beyond-far quad is clamped to the far plane and can paint. `libs/video` doesn't handle `SET_ZMIN_MAX_CONTROL` (`0x1D78`). The retail builder at `0x736360` has no direct `bl` and no descriptor word pointing at it (`vis/tools/s23_zminmax.py`), so the game probably keeps the hardware default. As far as I recall, that default clips near/far, but I have no hardware or documentation evidence here. If so, the host would paint beyond-far geometry that RSX discards. This is about correctness, not cost. I did not change it: it would be an unverified default change.

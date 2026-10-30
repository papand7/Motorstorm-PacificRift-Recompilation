# T169: D2 and F2 game results

**Result: both launches were valid, and the corrected code ran in the game. F2 removes almost all terrain clipping. `RSX_DEPTH_STATE=1` damages the vehicles and doesn't remove the rectangular patches, so the F2 set can't become a default.** No PS3 reference exists, so "less clipped" isn't proof of PS3 fidelity.

| | D2 | F2 |
|---|---|---|
| Requested | `RSX_DEPTH_STATE=1` | `RSX_COLOR_XFER=7 RSX_GUEST_SAMPLERS=15 RSX_TEX_MIPS=1 RSX_ZETA_EXACT=1 RSX_RT_WINDOW=1 RSX_RT_FEEDBACK=1 RSX_DEPTH_STATE=1 RSX_MRT_STATE=1` |
| Effective line | `profile=0x0 xfer=0x0 samplers=0x0 mips=0 zeta_exact=0 rt_window=0 rt_feedback=0 msaa=0 depth_state=1 mrt_state=0` | `profile=0x0 xfer=0x7 samplers=0xF mips=1 zeta_exact=1 rt_window=1 rt_feedback=1 msaa=0 depth_state=1 mrt_state=1` |
| `[XFER]` log | `not applied` | `RSX_COLOR_XFER=0x7 applies it` |
| Run (private) | `20261030-175939-t169-DD2` | `20261030-180259-t169-FF2` |
| Race entry | Host 122.9 s | Host 121.6 s |
| Race frames | 501 | 457 |
| End | Controller stop, race entry + 45 s | Same |
| Timeout, device removal, FIFO resync | 0 | 0 |
| Validation errors (debug layer, no GPU-based validation) | 0 | 0 |
| Warnings #821 / #820 / #679 | 1506 / 501 / 141 | 1380 / 459 / 143 |
| Final `c33.x` | 0.946 | 0.491 |
| Peak working set sampled | 687 MB | 703 MB |

**Both:** ps3recomp `774c81d`, exe sha256 `02b5c83cbb15d61f9cfea46f50868ac4c4c95593fb60976cc862ccf010a23a6f`, console session, one launch each, no retries, 4 s watchdog unchanged. The `D3D12_DBG=1` listener ran in both. No RSXI: per-draw `RSX_VISUAL_DIAG` (2,000 lines) came from race entry + 25 s, and dumps were 16 slots at most, every 64 presents (8 written). The process exit code 1 is the controller's stop, as in D1 and F1.

**Counters, last `[visual-active]` line (cumulative; present 5760 for D2, 5504 for F2):**

| Counter | D2 | F2 |
|---|---|---|
| `fp_draws` | 1,793,513 | 1,512,000 |
| `depth_state` / `depth_differs` | 1,793,513 / 1,585,542 | 1,512,000 / 1,327,314 |
| `xfer_gamma` / `xfer_srgb` | 0 / 0 | 776,544 / 724,864 |
| `srgb_rewrites` / `srgb_refused` | 0 / 0 | 81 / 0 |
| `samp_new` / `samp_binds` | 0 / 0 | 17 / 447,034 |
| `mip_multi` / `mip_levels` | 0 / 0 | 297 / 2,841 |
| `win_draws` | 0 | 13,099 |
| `fb_draws` / `fb_copies` | 0 / 0 | 5,152 / 5,152 |
| `zeta_color_draws` | 0 | 7,220 |
| `mrt_draws` | 0 | 1,512,000 |
| `ms_draws` | 0 | 0 |

`mrt_draws` counts every draw under the switch, so it shows the switch is on, not that an MRT mask differed.

**Frames and timing:** see `RENDERING_PERFORMANCE_CORRELATION.md`. **Images and classes:** see `VISUAL_CORRECTION_EFFECTIVENESS.md`.

## Vehicle depth-state isolation (offline, no launch)

**Root cause: strong, but not confirmed in game.** `RSX_DEPTH_STATE=1` is correct and only triggers the defect. Honouring stencil on full-screen op 915 keeps object velocity that the old renderer wiped. The kept velocity then hits an older bug: format `0xBF` reads the RGBA8 velocity target as unorm bytes, so the final composite (`0x02193941`) jitters its blur taps by garbage vectors.

| Candidate | Finding | Label |
|---|---|---|
| Depth compare | Scene draws use only LEQUAL (874) and GREATER (15, the decal boxes) in the complete B3 frame; no EQUAL. LEQUAL draws keep the compare the host already used | **VERIFIED, ruled out** |
| Alpha-tested passes | Alpha test off on all 928 draws | **VERIFIED, ruled out** |
| Depth encoding | Host D24_UNORM_S8_UINT is unchanged by the switch | **VERIFIED, ruled out** |
| Depth writes | Velocity pass mixes write 0 and 1; no link to the speckle found. Not separately tested in game | PARTIAL |
| Missing stencil | The old missing stencil hid the bug: op 915 `NOTEQUAL 255` wiped the velocity written by ops 597-914 | **VERIFIED** from snapshots |
| Velocity misread | Stored as PK2H then UP4UB, read as `0xBF` without decode. Jitter median 4.72 px, p99 15.69 px; decoded 0.40 / 9.05 px | **VERIFIED** in state, shader logic, bytes and fixture; **HYPOTHESIS** as the game's cause |

**Evidence:** `tools/velocity_repro_t169.py` models one composite tap on captured B3 surfaces. Median Laplacian on tagged pixels: wiped 1.0, kept and misread 2.0, kept and decoded 1.50. Its contact sheet shows the same clean, speckled, clean split as D1, D2 and the corrected read. D1, D2 and F2 give 1.0, 2.0 and 5.4 on the matched vehicle region.

**Limits:**
- The model uses B3, not the 00:01.33 frame, with one tap at weight 1.
- It uses substitute noise instead of guest `0x02190000`, and y's high byte is missing from the BMP.
- The D1 RSXI frame stops at 2048 of about 4500 records, and D2 and F2 have no intermediate surfaces, so a direct D1/D2 comparison of op indices, shader output and transitions at the same race clock wasn't possible.
- Byte order is only self-consistent on the host, with no PS3 reference.
- The soft near sand in F2 may be the same mechanism: **HYPOTHESIS**. F2's darker vehicle and any link to the radial streaks aren't explained.

**Correction:** `RSX_RT_REINTERP=1` (ps3recomp `542420e`), default off. It keys on format and RT class, not on vehicles. **No executable was built with it.** Plan: `GAME_VALIDATION_PLAN.md`.

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

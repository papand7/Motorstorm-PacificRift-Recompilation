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

## Velocity correction validation: arms A, B, C

**Result: C did not fix the corruption, but C did not test the correction either. The decode ran on no draw, so the velocity-misread cause remains HYPOTHESIS.** The speckle does follow `RSX_DEPTH_STATE`: **VERIFIED** in game (A against B, one switch, same exe).

| Arm | Exe sha256 | ps3recomp | Switches on top of the F2 set | Run |
|---|---|---|---|---|
| A | `02b5c83cbb15d61f9cfea46f50868ac4c4c95593fb60976cc862ccf010a23a6f` | `774c81d` | `RSX_DEPTH_STATE=1 RSX_RT_REINTERP=0` | `20261030-192237-t169-AVA` |
| B | same as A | `774c81d` | `RSX_DEPTH_STATE=0 RSX_RT_REINTERP=0` | `20261030-192538-t169-BVB` |
| C | `59019e06b9a39074ea2d47e90dd3c41f0299d73463e610db2ce8fa030011ba08` | `542420e` | `RSX_DEPTH_STATE=1 RSX_RT_REINTERP=1` | `20261030-192837-t169-CVC` |

The `774c81d` exe has no reinterpretation code, so `RSX_RT_REINTERP=0` is inert in A and B. All arms: same route, fresh HDD, console session, no retries, no manual driving, stopped at race entry + 45 s. Only C's effective line has the `rt_reinterp` field, and it reads 1. Beyond F2: a lean RSXI capture (`RSXI_MAX_EVENTS=0`, `RSXI_RTS=01650000,01DD0000,00750000,022D0000`) at race entry + 38 s, in all arms.

### Why C decoded nothing

- **VERIFIED:** the log has `[rt-reinterp] fp=0x0074B441: text not rewritable` and the same for `fp=0x02193941`. `reinterp_draws=902`, `reinterp_refused=2`: those are the two programs that read velocity, keyed but compiled undecoded.
- **VERIFIED offline, using the real game programs:** with no cube unit, the rewrite succeeds on both, at any fetched unit. With cube mask `0x8000` or `0xC000` it finds nothing, because any cube unit changes the emitter's spelling of every fetch from `rsx_tex[1].Sample` to `rsx_tex1.Sample`, and `rsx_fp_apply_rt_y16x16f` only matches the first.
- **PARTIAL as the game's cause:** `dr_cube_mask` includes every bound cube unit, fetched or not, and this run logged masks `0x8000` and `0xC000` on other programs. The `[CUBE]` log stops after 4 lines, so the mask on these two compiles wasn't recorded.
- **Test gap:** `test_t169_rt_reinterp` has no cube unit bound. A fix would match both spellings and add that case. Not done here: it needs a new build, which isn't authorised.

### Matched frames

Dumps fall every 64 presents. A and B pair within 0.07 s of race clock. C runs about 0.8 s away, so its rows are only nearest neighbours. Median Laplacian (speckle) over the box `(520,480)-(760,660)` round the vehicle:

| Race clock A / B / C | A | B | C |
|---|---|---|---|
| 00.06 / 00.06 / none | 10.2 | 3.3 | |
| 02.39 / 02.46 / 01.33 | 5.4 | 1.7* | 5.5 |
| 04.49 / 04.56 / 03.69 | 5.5 | 2.9 | 5.4 |
| 06.59 / 06.66 / 05.79 | 6.0 | 4.3* | 4.5 |

*B's camera differs at these clocks (closer at 02.46, wider at 06.66), so these two values aren't like for like. The visual judgement below carries more weight than the numbers.

| Item | A (depth on) | B (depth off) | C (depth on, decode refused) |
|---|---|---|---|
| Vehicle body, materials | Speckled; dark; cyan frame mostly lost | **Clean**: blue frame, shock, tyre tread, suit stripes | Same as A |
| Motion blur | Not measured. Speckle's jitter hides any blur | Velocity wiped, so none expected; none seen | Same as A |
| Decals, rectangles | No large boxes seen | **Dark rectangles** in sky and sand | Same as A |
| Shoreline water | **Absent** | **Present** | **Absent** |
| Tyre tracks | Fragments | Clear tracks, with black stripes on the right at 06.66 | Fragments |
| Sand | Grainy | Finer | Same as A |
| Exposure (mean frame luma, 02.39 to 06.59) | 132–136 | 119–132 | 134–136 |

**New finding, HYPOTHESIS:** the shoreline disappears with depth state on. Whether B's water or A's sand is correct has no PS3 reference; earlier reports list terrain clipping as a depth-state concern, so this needs its own look. B's rectangles match the known wrong decal boxes.

### Velocity surfaces and `0xBF`

**BLOCKED: the correction couldn't be observed in the game.** Captures completed without a timeout, but on different frames: A f005488 (610 records), C f005399 (429), B f005512 (stopped at 2,048, black back buffer, no composite). `01650000` is 4.37 % nonzero in A, 3.98 % in C and 64.88 % in B at op 1996. These aren't matched scenes, so they say nothing about depth state. BMP snapshots also lack alpha, which holds y's high byte.

### Performance

Race frames before the capture trigger. No `wait_ms` near 84 in any arm.

| Window | A: n, FPS, p50, p95, p99 | B | C |
|---|---|---|---|
| All | 344, 9.3, 69.7, 156.7, 1115.8 | 352, 9.5, 79.7, 151.3, 937.6 | 359, 9.7, 64.9, 149.6, 513.2 |
| Light (under 2,000 draws) | 149, 15.5, 46.3, 54.3, 236.3 | 149, 15.5, 45.4, 51.6, 236.1 | 151, 15.5, 45.4, 52.9, 231.8 |
| Heavy (4,000 draws or more) | 152, 7.2, 129.9, 160.1, 232.9 | 160, 7.3, 126.7, 156.5, 233.2 | 148, 7.2, 130.8, 152.0, 236.4 |

| Measure | A | B | C |
|---|---|---|---|
| Median draws | 2,303 | 2,306 | 2,927 |
| PSO misses, ms | 127, 5258 | 127, 4852 | 127, 4893 |
| Frames of 500 ms or more | 4 | 4 | 4 |
| Warnings #821 / #820 / #679 | 1332 / 444 / 144 | 1338 / 446 / 144 | 1386 / 461 / 143 |
| Runtime errors, Present timeouts | 0 | 0 | 0 |
| Last working set | 720 MB | 714 MB | 701 MB |

- **Depth state:** no measurable frame-time cost; light and heavy windows agree within noise.
- **Decode overhead: not measured**, since no decoded shader ran. C shows only that the extra key and counters cost nothing visible.
- The p99 of the "all" window comes from a few load stalls; the 2.5 s maximum is in every arm.

### Remaining uncertainty

- The misread as the speckle's cause: untested in game. Byte order and the z and w lanes on real RSX have no reference, and a clean picture wouldn't prove them.
- Whether anything besides velocity contributes to A's speckle, such as `RSX_COLOR_XFER` interaction. D2 speckled without the rest of the bundle, so depth state alone is sufficient.
- Why the camera differs between arms with no input.

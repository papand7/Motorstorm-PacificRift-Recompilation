# T169 Phase 4: corrected Arm C results

Commit `66b5478` on `agent/t169-visual-fidelity-recovery` (`d2d9ef9` plus a counter move), not merged or pushed.
Exe SHA-256 `0cac21fe7cf88079c0107ae3adfb38c4dd6d7cbcd4de81627e457809a1d542c9`, build dir `build/motorstorm-t169p4`.
Run `20261030-202748-t169-GVG`, the single authorized Arm C launch. Config: `[visual] effective profile=0x0 xfer=0x7 samplers=0xF mips=1 zeta_exact=1 rt_window=1 rt_feedback=1 msaa=0 depth_state=1 mrt_state=1 rt_reinterp=1`, plus `RSX_RT_REINTERP_DIAG=0074B441,02193941` and `RSXI_NEED_FP=02193941,02FB4541`.

## Preflight

| Check | Result |
|---|---|
| Clean build | rc 0 at d2d9ef9; 66b5478 rebuilt incrementally in the same dir (one source file) |
| Suite, d2d9ef9 | 121 pass, 3 fail, 43 skip. New: `test_rsxi_geom`, **caused by this work**; the counter sat between `DrawInstanced` and `rsxi_after_draw`. Fixed by moving the counter, assertion untouched |
| Suite, 66b5478 | 121 pass, 3 fail, 43 skip: inherited `test_rt_pool_srv_layout`, `test_vpc_watch`, plus `test_spurs_wws_concurrency` once |
| `test_spurs_wws_concurrency` | 5 of 5 pass on rerun. Treated as intermittent, cause not established |
| `test_t169_rt_reinterp` in that same preflight | 2 failures: no `[visual-active]` line in two configs, pixels correct. 3 of 3 clean on rerun. Cause of the missing line not established |
| WARP tests, real-program test | 0 failures |
| Public audit (`--tree`, changed files) | passed |
| Harness dry run | exe hash OK, nothing scrubbed, session local |

## Run

Reached the race; controller stopped at race entry + 45 s (exit code 1, as in C). No stop condition fired: no timeout, device removal, FIFO corruption, target refusal or compile failure. Debug layer: the same three warning ids as A, B, C (821, 820, 679), no errors.

Capture: frame 5556, clock 05.16, 827 records, 14 snapshots, gated on both programs being drawn.

## Visuals (no same-position dumps exist; nearest clocks used)

Laplacian, median in the tight vehicle box `(520,480)-(760,660)`:

| Arm | Depth state | Decode | Values |
|---|---|---|---|
| A | on | no | 5.4 to 10.2 |
| B | off | no | 1.7 to 4.3 |
| C (old) | on | refused | 4.5 to 5.5 |
| **G (corrected)** | on | **executed** | **3.0, 3.0, 3.0** |

- **Vehicle: VERIFIED improved.** Rider, frame, tyres and suspension are clean and coloured at all three race dumps. A and C show dark speckle in the same parts. The only intended difference from C is the decode.
- **Terrain: unchanged**, 3.0 against 2.9 to 3.0. Frame luma 133.6 to 135.1 against 134.0 to 135.9 for C.
- **Far band:** 10.3 to 10.8 against 11.4 to 12.4 for C, slightly lower.
- **Velocity effects: PARTIAL.** Velocity is small at the slow speed captured; correctness isn't established.
- **Shoreline: not assessed**, no PS3 reference.

## Not fixed, in all arms

Far vehicles appear sliced into thin slivers above the sand, with flat rectangular patches on the terrain beside them. These also appear in B with depth state off, so `RSX_DEPTH_STATE` doesn't cause them. HYPOTHESIS: terrain or decal ordering, or depth for distant objects.

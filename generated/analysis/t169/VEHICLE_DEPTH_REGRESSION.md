# T169: vehicle speckle with RSX_DEPTH_STATE=1

Commit `66b5478` on `agent/t169-visual-fidelity-recovery` (`d2d9ef9` plus a counter move), not merged or pushed.
Exe SHA-256 `0cac21fe7cf88079c0107ae3adfb38c4dd6d7cbcd4de81627e457809a1d542c9`, build dir `build/motorstorm-t169p4`.
Run `20261030-202748-t169-GVG`, the single authorized Arm C launch. Config: `[visual] effective profile=0x0 xfer=0x7 samplers=0xF mips=1 zeta_exact=1 rt_window=1 rt_feedback=1 msaa=0 depth_state=1 mrt_state=1 rt_reinterp=1`, plus `RSX_RT_REINTERP_DIAG=0074B441,02193941` and `RSXI_NEED_FP=02193941,02FB4541`.

**VERIFIED: with depth state on and the velocity decode executing, vehicles are clean** (tight-box Laplacian 3.0, against 4.5 to 5.5 for refused C). So the speckle doesn't need a depth change to go away.

**PARTIAL:** the mechanism is inferred from one corrected run plus the earlier arms. Raw values read as large, wrong velocities would explain per-pixel blur offsets on vehicles. It wasn't traced pixel by pixel, and why depth state off (B) also looks clean wasn't established.

**Not investigated further, as the brief required that only if speckle remained:** compare function, depth writes, PSO keys, precision, aliasing, transitions, RT feedback, clipping, decal and water.

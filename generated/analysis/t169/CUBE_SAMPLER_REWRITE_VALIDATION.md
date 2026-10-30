# T169 Phase 4: cube sampler rewrite validation

Commit `66b5478` on `agent/t169-visual-fidelity-recovery` (`d2d9ef9` plus a counter move), not merged or pushed.
Exe SHA-256 `0cac21fe7cf88079c0107ae3adfb38c4dd6d7cbcd4de81627e457809a1d542c9`, build dir `build/motorstorm-t169p4`.
Run `20261030-202748-t169-GVG`, the single authorized Arm C launch. Config: `[visual] effective profile=0x0 xfer=0x7 samplers=0xF mips=1 zeta_exact=1 rt_window=1 rt_feedback=1 msaa=0 depth_state=1 mrt_state=1 rt_reinterp=1`, plus `RSX_RT_REINTERP_DIAG=0074B441,02193941` and `RSXI_NEED_FP=02193941,02FB4541`.

## Offline

| Check | Result |
|---|---|
| `test_t169_rt_reinterp`, 10 configs | 0 failures on d2d9ef9; on 66b5478, 2 counter checks failed once, then 0 failures in 3 of 3 reruns |
| Scene pixels | decoded (128,64), against raw unorm (1,56) when off |
| Sampled cube | blue 96 preserved in `cube_sampled` and `mixed` |
| Old matcher with cube bound (negative control) | refused, pixel (1,56), as the game ran before |
| Real programs on WARP | 60 of 60: output 0.500488, 0.250000 rewritten, 0.003922, 0.219608 plain |
| Masks tested | 0, 8000, C000, C001, 4010, each with both programs, 3 control and gamma variants, rewritten and plain |
| Other fetches in real programs | unchanged, 1 in `0x0074B441`, 13 in `0x02193941` |
| D3D12 debug layer, three scenes with `t.exe` | no errors or corruption; only the process-exit warning; counters 64 bound, 64 draws |

The first debug-layer attempt used the negative-control `old.exe` by mistake. It showed the expected refusal and isn't counted.

## In game

Cube mask `0xC000` is now confirmed in the corrected game run, not only in T165's frame. Separate-texture spelling, 1 fetch rewritten per program.

## Trap

RSXI `.hlsl` dumps decompile without the cube mask, so they show `rsx_tex[1]`, which isn't the compile path's text. Don't use them to prove the spelling.

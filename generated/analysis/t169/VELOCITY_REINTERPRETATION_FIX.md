# T169 Phase 4: velocity reinterpretation fix

Commit `66b5478` on `agent/t169-visual-fidelity-recovery` (`d2d9ef9` plus a counter move), not merged or pushed.
Exe SHA-256 `0cac21fe7cf88079c0107ae3adfb38c4dd6d7cbcd4de81627e457809a1d542c9`, build dir `build/motorstorm-t169p4`.
Run `20261030-202748-t169-GVG`, the single authorized Arm C launch. Config: `[visual] effective profile=0x0 xfer=0x7 samplers=0xF mips=1 zeta_exact=1 rt_window=1 rt_feedback=1 msaa=0 depth_state=1 mrt_state=1 rt_reinterp=1`, plus `RSX_RT_REINTERP_DIAG=0074B441,02193941` and `RSXI_NEED_FP=02193941,02FB4541`.

## Result

**Final classification: A. The decode executed and the corruption improved.**

## Cause of the refusal

VERIFIED. The emitter writes `rsx_tex[u]` unless a cube or volume unit is bound, then `rsx_tex<u>`. In game, cube units 14 and 15 are bound (mask `0xC000`), so the old matcher, which knew only `rsx_tex[u].Sample`, refused both velocity readers.

## Fix

- `rsx_rt_reinterp.h`: one scanner finds both spellings, skips comments and respects identifier boundaries. A partial decode is refused, with a reason.
- `rsx_d3d12_backend.c`: counters `reinterp_attempted/success/refused/compiled/bound/draws`. `reinterp_keyed` holds the old "draws" meaning. `reinterp_draws` now counts only draws that ran with decoded programs.
- Opt-in: `RSX_RT_REINTERP_DIAG=<hex,..>` (up to 4 programs, bounded lines) and `RSXI_NEED_FP=<hex,..>`. Defaults are unchanged.

## Question A: does the rewrite activate and execute? VERIFIED

| Proof | Game evidence |
|---|---|
| Programs encountered | `0x0074B441`, `0x02193941` |
| Attempted / success | 2 / 2, `reason=none`, cube mask `0xC000`, 1 fetch rewritten each |
| Compiled | 2, `pipeline ready` |
| Bound | 774, `tex_fmt=0xBF remap=0x29E4 filter=0x01012000 rt=0x01650000 dxgi=28` |
| Draws after `DrawInstanced` | 774 (387 per program) |
| Refused | 0 |

The earlier `requested=0, reason=not_requested` lines are the same programs compiled before the velocity target was bound. They are not refusals.

## Question B: does it reproduce PS3 behaviour? HYPOTHESIS

- Writers: `h0.xy` velocity, then `PK2H`, then `UP4UB`, exported as R=x_lo, G=x_hi, B=y_lo, A=y_hi into A8R8G8B8 target `0x01650000`. Reader: format `0xBF`, nearest, remap (comp0, comp1, 0, 1), uses `.xy` only.
- The rewrite (M1) is the pack round trip: x = half(G:R), y = half(A:B).
- A literal big-endian reading (M2) would give x' = half(A:R), y' = half(G:B), which looks scrambled but is not excluded.
- Partial evidence for the x pairing: in the end-of-frame target at clock 05.16, x = half(G:R) stays within about 0.001, while the swapped pair reaches 57408. Alpha is lost in the BMP snapshots, so M2 can't be tested directly.
- The cleaner image is not proof of the conversion. There is no PS3 or RPCS3 reference.

## Limits

- One launch, one seat, a slow vehicle in 16th place. Blur at high speed was not observed.
- Motion blur is not claimed correct.

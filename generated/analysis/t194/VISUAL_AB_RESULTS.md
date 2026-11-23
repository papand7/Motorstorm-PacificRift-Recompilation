# T194 visual A/B (2026-11-03)

Exe `build/motorstorm-t194` SHA-256 `37690ddefcff865c3aee422bfc728e4b0760d5f10fcf1f7439a4c13d87736fb1` (T190 tree `a26240c5`
+ zeta-exact default `762bafaf` + EXPERIMENTAL c38 seed `269372d4`). Runner `ab/run_t194.py` (generator
`tools/make_runner_t194.py`). All 8 launches from an RDP session; each stopped at race entry + 75 s; no Present timeout
or device-removed line in any run. Frame dumps: `CELLMARK_DUMP=16`, `EVERY=64`, `MINDRAWS=200`, `PRESENT_ONLY=1`.

| arm | env vs T190 P | run |
|---|---|---|
| P | `RSX_ZETA_EXACT=0 RSX_EXP_C38=0 RSX_SHADER_WINDOW=0` (old rendering) | Pp1 (no dumps), Pp2 |
| B | `RSX_COLOR_XFER=7 RSX_SHADER_WINDOW=1 RSX_RT_FEEDBACK=1 RSX_MRT_STATE=1` + zeta/c38 defaults on | Bb1 (no dumps), Bb2 |
| C | B with `RSX_EXP_C38=0` | Cc1 |
| F | B with `RSX_RT_FEEDBACK=0` | Ff1 |
| X | B with `RSX_COLOR_XFER=0` | Xx1 |
| Z | B with `RSX_ZETA_EXACT=0` | Zz1 |

Sheets: `sheet_p2_b2.png`, `sheet_round3.png` (`tools/sheet_t194.py`, mean luma per frame printed by the tool).

## Findings (one run per arm; by eye, frames are not time-aligned)

- VERIFIED (these runs): B removes P's washed-out, streaked race image. X looks like P (washed-out sand, white
  surfaces) while C, F and Z look like B, so `RSX_COLOR_XFER=7` carries most of the exposure fix.
- PARTIAL: B's ~6 s full-white race start (Bb2 frames 4-6) did not occur in C, F or Z. With one run each it is not
  known whether it is intermittent or needs c38 + RT feedback + zeta together.
- HYPOTHESIS: the c38 seed has no visible benefit on the track; C (c38 off) looks as good as B. Its intended target,
  the garage, is not on this route (main menu ~52 draws/frame, no `gui/garage` page; nav goes menu -> invitation ->
  ticket -> load screen -> track), so the c38 garage effect is BLOCKED here.
- Not measured: FPS. Heartbeat race rates varied 14.8-41.7 fps between runs of the same arm (Pp1 vs Pp2) over RDP.

## Round 4 (Bb3, Bb4, Gg1; Kk1 refused: the RDP session disconnected, `query session` showed no active session)

- PARTIAL: the white frames in B are intermittent. Bb2: white race start (frames 4-6); Bb3: clean start, white
  at 00:24 and a yellow-bloom frame at 00:26; Bb4: clean throughout (`sheet_b234.png`). The single leave-one-out
  runs (C/F/Z clean) therefore do not attribute it to any switch.
- VERIFIED (Gg1, arm B held 40 s at the main menu, no presses, `sheet_g1.png`, `g1_pick.png`): the main menu
  renders over its animated 3D backdrops (night festival beach, sunset vehicle scene, monster truck) with
  readable menu text and normal exposure. No `gui/garage` page loaded. Without Kk1 (c38 off) the c38 share of
  this look is unknown.

## Next (needs launch authorization)

- Kk1 (G with c38 off), from an active console or RDP session.

- Repeat B 2x to see if the white start recurs; if it does, C/F/Z leave-one-out again.
- A garage route (Garage menu entry) for c38.

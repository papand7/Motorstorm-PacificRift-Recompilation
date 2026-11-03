# T44: Main menu input-routing trace

One run, `generated/runs/20261026-065737-t44-menu-input/`.
- Configuration preserved in `t44/t44_trace.cfg` and `run_t44.py`.
- Exe SHA-256 `96d9dee1…dbc22`.
- No patches, no forced state.

## Deviations

- This boot skipped the garage, so the scripted controller never pressed anything. The **user's host keyboard** drove the menu.
- The run ended on a Present() timeout (~126 s), so there is no RSXI frame.
- Trace flaw: `sample=8` aliased with two page updates per frame, so mainmenu PageUpdate `0x57EA38` was never sampled. Use an odd sample next time.

## Timeline (PT seconds)

| t | Event |
|---|---|
| 26.57 | Intro skip, CROSS |
| 26.63 | `mainmenu` loaded (101CA880). Controlled: `1F5EDC` r3=0. Popup 101D39F0 not controlled. |
| 68.60 | Attract video after ~42 s idle; back to the menu at ~76 |
| 84.38 | CIRCLE 0x2000 → `57F450`, `57FA00` (item 101CE9D4) |
| 90.17 | CROSS → `57F1A4` → `options.gui` |
| 91.42 | Options input byte 7 = 1 → `57F1A4` → options-audio |
| 92.10 / 93.75 | CIRCLE → back → mainmenu reloaded |
| 97.45 / 98.18 | CROSS → options → options-audio |
| 110.5 / 111.31 | Back to mainmenu |

## Result

- **VERIFIED:** main-menu input is routed and handled. The handlers `57F1A4`, `57F450` and `57FA00` were reached, and page navigation works.
- The earlier "input not reaching page" hypothesis is refuted. The real defect is invisible text (see `t45/MENU_CONTROLS_AND_TEXT.md`).
- Every sampled page had opacity 1.0. Mainmenu's own opacity was not sampled.
- **PARTIAL:** input byte 7 = CROSS (accept) and byte 6 = CIRCLE (back), which corrects T41.
- **HYPOTHESIS:** why this boot skipped the garage.

No correction is justified on the input side.

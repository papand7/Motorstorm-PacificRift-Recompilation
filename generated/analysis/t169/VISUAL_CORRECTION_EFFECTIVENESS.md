# T169: visual correction effectiveness

**F2 is a combined test, so it proves no single correction.** The only per-switch evidence is D2 against D1 and F1, which isolates `RSX_DEPTH_STATE`. All comparisons are against no PS3 reference.

## Classes

A = verified in-game improvement, B = active with visual effect inconclusive, C = offline only, D = not working, E = unresolved.

| Correction | Class | Evidence | Limit |
|---|---|---|---|
| F2 bundle, terrain clipping | **A** | Clipped white 18.9 → 0.18 % and `c33.x` 0.95 → 0.49 on frames paired by race clock | Clipping only, not PS3 fidelity; includes the depth regression |
| `RSX_DEPTH_STATE=1` | **D** | 88 % of draws change state. Compared with D1 and F1 at race clock 00:01.33, the vehicle is speckled and its materials are lost; rectangular patches remain | Runs as coded, gives a wrong picture. Cause open |
| `RSX_COLOR_XFER=7` | **B** | 724,864 sRGB draws, 81 rewrites, 0 refused, log says `applies it` | The likely exposure driver (HYPOTHESIS); no single-switch run. `xfer_expand` stayed 0 |
| `RSX_GUEST_SAMPLERS=15` | **B** | 17 samplers, 447,034 binds | Terrain bands gone in F2; not attributable |
| `RSX_TEX_MIPS=1` | **B** | 297 multi-level uploads, 2,841 levels | Near sand looks soft; could be over-blur or just unclipped. Vehicle grain is worse |
| `RSX_ZETA_EXACT=1` | **B** | 7,220 zeta-as-colour draws | No separable effect |
| `RSX_RT_WINDOW=1` | **B** | 13,099 draws | No separable effect |
| `RSX_RT_FEEDBACK=1` | **B** | 5,152 draws, 5,152 copies | No separable effect |
| `RSX_MRT_STATE=1` | **B** | Switch on, keyed for all draws | Counter can't show a mask changed |
| `RSX_MSAA` | **C** | Not in F2; 0 multisampled draws | Edges remain aliased |
| `RSX_VISUAL_PROFILE` | **C** | Real-init pixel test; not used by D2/F2, as the brief required | Explicit switches ran in game |
| `0xBF` velocity misread | **E** | No fix. No smear stood out in dumps | See `REMAINING_VISUAL_DEFECTS.md` |

## Screenshot method

Dumps weren't compared by index. Pairs came from image similarity (normalised correlation on luma, 8×8 blocks), then were confirmed by the HUD race clock and position when visible. No guest-state or draw-sequence key exists for the dumps, so these are close matches, not identical frames.

| D2 / F2 | Correlation | Clock D2 / F2 | Status |
|---|---|---|---|
| 4 / 4 | 0.855 | 00:01.33 / 00:01.36 | Matched |
| 5 / 5 | 0.909 | 00:03.69 / 00:03.73 | Matched |
| 6 / 6 | 0.868 | 00:05.79 / 00:05.83 | Matched |
| 7 / 7 | 0.912 | 00:07.89 / 00:07.93 | Matched |
| 0 / 0, 1 / 1 | 0.856, 0.885 | No clock | Same flyover shot, unconfirmed timing |
| 2 / 2, 3 / 3 | 0.706, 0.661 | No clock | **Inconclusive**: camera differs |

D1 dump 4 and F1 dump 4 show the same clock 00:01.33 as D2 dump 4. D1 and F1 used the earlier exe `766c4591…`; between that exe and this one only the profile move, counters and tests changed.

## Metrics, matched frames

| Pair | Near-black % D2→F2 | Clipped white % | Mean luma | Lower-third luma | Edges % | Detail |
|---|---|---|---|---|---|---|
| 4 | 0.53 → 0.13 | 19.99 → 0.12 | 186.2 → 134.2 | 187.5 → 151.4 | 8.47 → 2.41 | 74.0 → 29.2 |
| 5 | 0.53 → 0.13 | 20.04 → 0.12 | 183.8 → 135.9 | 185.8 → 150.0 | 10.10 → 2.30 | 79.1 → 26.7 |
| 6 | 1.42 → 1.18 | 17.75 → 0.18 | 179.3 → 134.3 | 185.6 → 149.6 | 9.88 → 2.75 | 77.6 → 29.2 |
| 7 | 1.33 → 1.12 | 18.94 → 0.18 | 180.1 → 133.9 | 186.0 → 149.3 | 9.98 → 2.48 | 78.2 → 27.5 |

The edge and detail falls can't be read as less aliasing or less texture detail: D2's figures include hard contours from clipping.

**Vehicle region, clock 00:01.33 (x 540–740, y 450–680):**

| Arm | Mean luma | Near-black % | Saturated blue % | Median Laplacian (speckle) |
|---|---|---|---|---|
| D1 (no correction) | 154.3 | 28.6 | 2.27 | 1.0 |
| F1 (no correction, repeat) | 156.0 | 26.4 | 2.60 | 1.0 |
| D2 | 149.3 | 13.3 | 0.88 | 2.0 |
| F2 | 126.4 | 9.4 | 0.01 | 5.4 |

The D1 and F1 values agree, and D2 changes only `RSX_DEPTH_STATE`. So the depth-state link is strong, on one matched frame: **VERIFIED as a difference, cause HYPOTHESIS**.

## Observations

| Item | D1/F1 baseline | D2 | F2 |
|---|---|---|---|
| Vehicle materials | Clean: cyan frame, shock, tyres | Speckled, cyan and shock lost | Dark, speckled |
| Tyres | Black, tread visible | Speckled | Dark, speckled; no lift shown |
| Terrain exposure | Clipped | Clipped | Sand tones visible; sky and sea unclipped |
| Radial streaks | Present | Replaced by rectangles and thin lines in the race; pink bands remain in countdown dumps | Bands gone from the dumps; camera differs on 2 and 3 |
| Rectangular patches | Wedges | Present | Still faintly visible |
| Grain, near sand | Clipped, can't judge | Clipped, can't judge | Soft, without visible grain |
| Aliasing | Present | Present | Present; no MSAA |
| Shadows | Inconclusive | Inconclusive | Inconclusive: dark blotches visible, cause not traced |
| Blue rectangle | Not seen | `blue_scan`: 0 candidates | `blue_scan`: 0 candidates |

Crops and sheets stay private in `img/` (`d2_f2_pairs.png`, `d2f2_*.png`, `veh_sheet.png`). Numbers: `logs/d2f2_analysis.txt`. Tools: `tools/d2f2_analysis_t169.py`, `tools/d2f2_crops_t169.py`.

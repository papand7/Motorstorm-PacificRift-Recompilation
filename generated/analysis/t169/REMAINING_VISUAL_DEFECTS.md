# T169: remaining visual defects

**The next blocker is `RSX_DEPTH_STATE=1`: it speckles the vehicles, and it's in the F2 set.** Launching again needs new authorisation.

| Defect | Label | Next change |
|---|---|---|
| Vehicle speckle, lost materials with `RSX_DEPTH_STATE=1` | Difference **VERIFIED** on one matched frame; cause HYPOTHESIS (multi-pass or depth-equal vehicle draws now failing because of host depth precision or vertex variance) | Offline first: read the vehicle's `[vis-draw]` lines and depth state, then reproduce on a fixture. Then one run of F2 without depth state, which also separates the rest of the bundle |
| Rectangular patches | Present in baseline, D2 and F2. The depth-state decal hypothesis is **not supported**: `RSX_DEPTH_STATE` didn't remove them | Identify the draws by region; check stencil, since `RSX_STENCIL_EXACT` wasn't in F2 |
| Dark vehicle, tyres in F2 | Unresolved while speckle is present | Judge again without depth state |
| Soft near sand in F2 | Unresolved: possibly mip bias or level selection, or simply no longer clipped | Same-region comparison with mips off |
| Aliased edges | Present; `RSX_MSAA` not tested in game | Later arm |
| `0xBF` velocity misread | Mismatch VERIFIED, not fixed; no smear stood out | Decompiler decode |
| Shadows | Inconclusive | Region capture after depth state is solved |
| Blue rectangle | Not reproduced; 0 candidates in 16 dumps | User's reference, if any |
| PS3 fidelity | **BLOCKED**: no reference | A PS3 image or video of this route |

**Not in scope of these runs:** per-switch effects inside F2, GPU-based validation, GPU timestamps.

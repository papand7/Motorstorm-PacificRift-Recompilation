# T169: blue rectangle

**BLOCKED: not reproduced, and no cause claimed.**

`tools/blue_scan_t169.py` scanned 198 frame dumps and RSXI snapshots from T165 and T145: blocks at least 85 % saturated blue, regions filling their bounding box by at least 85 %. It gave 13 candidates. I viewed three representative ones (`logs/blue_candidates.png`); the other ten are delta images, surf strips and one further flyover frame, not viewed:

| Candidate | What it is |
|---|---|
| `snap18` of `0x01650000`, at (1064, 120) | **Vehicle velocity data** in the velocity pass, not a final image |
| B3 `frame_002`, at (600, 472) | The quad's real blue paint |
| D1 `frame_002`, at (928–952, 104–144) | Palm fronds tinted blue in a blown-out frame; not a rectangle |

**Leads, unproven:**
- The velocity surface does contain saturated blue. It's normally overwritten or only read as velocity. A composite or snapshot error that showed it would look blue, but no such frame was found.
- Small rectangular blue-and-white signs on the sand in T145 frames are real objects.

**To reproduce:**
1. The user's screenshot, or its time and scene (the captures don't include it).
2. Frame dumps every 1 s through the affected interval, not a sparse sample, since it's intermittent.
3. On first sight, an RSXI capture on the next frame, lean settings (`RSXI_VP_CONSTS=48 RSXI_UNITS=FFFF RSXI_GEOM=1`).
4. With that: find the first pass snapshot containing it, then its draw's FP, RT and clear colour.

Part of arm A in `GAME_VALIDATION_PLAN.md`; the same scan runs on its dumps.

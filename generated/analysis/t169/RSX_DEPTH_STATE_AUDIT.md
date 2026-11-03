# T169: RSX_DEPTH_STATE audit status

- `RSX_DEPTH_STATE=1` applied to every guest-FP draw in the corrected run (1,454,187), and differed from the old fixed state on 1,277,640 of them. VERIFIED.
- Depth state alone is not a safe default: without the decode, vehicles speckle (arms A and C). With it, they don't (arm G).
- Its correctness against RSX semantics is not established in full. No divergence was confirmed in this phase, because the speckle no longer calls for it. HYPOTHESIS only.
- Far-vehicle slivers and terrain patches occur with depth state on and off, so they aren't caused by this switch. Their cause is open, see `NEXT_VISUAL_CORRECTNESS_PLAN.md`.
- No vehicle-specific bypass, global depth disable or polygon offset was added. Defaults are unchanged.

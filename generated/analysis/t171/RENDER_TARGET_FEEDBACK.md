# T171: render-target feedback

- **VERIFIED:** the track draw samples the target it writes: unit 2 = `0x00750000` (control0 `0x80078000`), `rt_exact`.
- **VERIFIED by correlation:** the lookup's window scale matters. Prediction through the 1272x715 window fits better (0.814) than across the full surface (0.732), so `RSX_RT_WINDOW` affects edges. It stays opt-in; this task did not change it.
- **Separate risk, not fixed:** by default the host reads the bound RT through an SRV, which is undefined in D3D12. `RSX_RT_FEEDBACK` stays opt-in. Its effect on the track needs in-game evidence, and T171 adds no full-frame copy or GPU sync.
- With the fix the lookup lands on the draw's own pixel. The fixture's "stale copy beneath" control (32) shows a stale copy gives a visibly different result.
- **PARTIAL:** `0x0243AB00`, read by the water and surf programs, snapshots flat green in B3 and D1. Whether that is stale or merely unresolved in the snapshot is open, and it is one candidate for the VB patches.

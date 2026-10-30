# T165: fix status

**No rendering fix was made, because the failure mechanism is not proven on a vehicle.** No default, alpha, cull, depth or colour behaviour changed.

| Item | Status |
|---|---|
| Candidate correction | Existing opt-in `RSX_COLOR_XFER=7` (T110). General RSX behaviour, not vehicle-specific, and already in the `exe_n` source tree. Pixel-verified on WARP; in game it ran only in T145 D1, without a vehicle view |
| Also to test | `RSX_GUEST_SAMPLERS=15 RSX_TEX_MIPS=1` (T162 D2) |
| `RSX_VEHICLE_FIX` | Not added. It would only duplicate the switches above |
| Texture residency | Not touched. Another agent owns it; no handoff is needed yet |
| New code | Diagnostic only: `RSX_VEHICLE_DIAG` |

Make `RSX_COLOR_XFER=7` default only if `GAME_TEST_PLAN.md` arm X passes.

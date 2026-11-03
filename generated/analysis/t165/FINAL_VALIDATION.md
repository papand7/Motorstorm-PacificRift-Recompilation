# T165: final validation

Tree `ps3recomp-t165` at `b1eb158`, unchanged in this continuation.

| Check | Result |
|---|---|
| `test_t110_warp` | 88 checks, 0 failed |
| `tools/test_d3d12_color_xfer.py` | 0 failures |
| `tools/test_t110_pins.py` | 12 pins, 15 mutations, 0 failures |
| `tools/test_fp_shadow_compare.py` | 0 failures |
| Backend syntax check | exit 0 |
| `tools/test_t165_vehicle_diag.py` | SKIP on this rerun (no compiler on PATH); PASS earlier, on the same code |

**Debug layer:** B1, transfers off: 0 errors in a partial run. Transfers on: not run this time; T145 arm D reported no validation errors, on an older exe.

**Not run:** full test suite, full build, debug layer with `exe_n` and transfers on.

**Known failures:** none in the tests above. The `GcKernel::Present() Timeout` in B1–B3 comes from RSXI capture cost.

**Completion criteria**

| # | Criterion | State |
|---|---|---|
| 1 | Real defective draw identified | PARTIAL: the group, not one op |
| 2 | Failure reproduced or isolated | Done on one matched frame, game-level |
| 3 | RSX evidence | Done |
| 4 | Minimal correction | Exists, opt-in |
| 5 | Offline regressions | Pass, within the above |
| 6 | In-game correctness | **Not finished**: start-grid view and PS3 reference outstanding |

**Ready for integration:** yes as an opt-in only; not as a default.

**Further game testing required:** yes, with new approval. One launch with `RSX_COLOR_XFER=7`, no flyover skip, an RSXI-free run (dumps only) so the cap can't cut it, and frame dumps timed at race entry +30–40 s for the grid view; ideally a PS3 reference image of the same scene.

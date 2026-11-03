# T165: validation results

Tree `ps3recomp-t165`, commit `b1eb158`. Offline; no game launch.

| Check | Result |
|---|---|
| `tools/test_t165_vehicle_diag.py` (new): off unless exactly 1, go file, line limit, program filter, state unchanged | PASS, 0 failures |
| `test_t110_warp` (WARP pixels: samplers, texture gamma, sRGB output, blending, multiple units) | 88 checks, 0 failed |
| `tools/test_d3d12_color_xfer.py` | PASS, 0 failures |
| `tools/test_t110_pins.py` | 12 pins, 15 mutations, 0 failures |
| `tools/test_fp_shadow_compare.py` | PASS, 0 failures |
| `rsx_d3d12_backend.c` syntax check with the hook | exit 0 |
| Public audit, ps3recomp `--staged` | 25 BLOCKs, none on T165 files (the same count as T162/T163) |

**Not run:**
- The full suite and the full exe build. The only code change is the diagnostic, off by default.
- D3D12 debug-layer validation of T165 itself: no D3D12 call was added. It is required in the game plan's arm X.
- Before/after image comparison and vehicle regression: no fix exists, and no capture has a vehicle.
- Performance measurement: off, the hook is one branch per recorded draw.

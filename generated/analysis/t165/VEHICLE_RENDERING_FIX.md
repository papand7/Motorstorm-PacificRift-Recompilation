# T165: fix status

**The correction is the existing general opt-in `RSX_COLOR_XFER=7` (T110). No new renderer code and no default change.** A new switch would only duplicate it.

| Bit | Operation | Needed here |
|---|---|---|
| `0x1` | Texture gamma, per unit and channel mask from the guest's address register | Yes: requested on the vehicle-bearing draws |
| `0x2` | Sign expansion | Not requested in these frames; harmless, follows the guest |
| `0x4` | sRGB output from `SET_SHADER_PACKER` | Yes: 570 of 570 main-scene draws |

**Correctness:** the switch applies only what each draw's guest registers request (`dr_xfer_req`). Bloom targets (`0x14B`) with `srgb_output=0` get no encode, and alpha is excluded by mask 7. So it isn't a colour adjustment, and it isn't vehicle-specific.

**Blending:** output is encoded in the shader, before blending. I haven't confirmed that against PS3 behaviour for the blended draws.

**Performance:** not measured. It adds PSO variants. X1 logged no shader failures, but its runs were in the slow GPU-wait mode, so it gives no timing evidence.

**Risks:**
- The rider's dark clothing and the rock got darker, with no PS3 reference to confirm that's right.
- Sand brightness and blocky shadows stay broken.
- T145 arm C, combining the switch with `SHADER_WINDOW`, didn't reach the race (cause unknown).

**Regression tests:** no new test, since no code changed. The 88 WARP checks and `test_d3d12_color_xfer` already cover the transfers on and off.

**Not changed:** T167 synchronisation and shader compile, texture residency, T166 paths, sampler defaults.

**Default rule:** make it the default only after a grid view and a PS3 reference comparison pass.

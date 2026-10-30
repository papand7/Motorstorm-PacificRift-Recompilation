# T169: game validation plan

**Not approved and not run. Do not launch without a separate approval.** T165's proposed grid-view launch never ran; no result exists.

**Exe:** a build of `agent/t169-visual-fidelity-recovery`. Hash: see `INTEGRATION_READINESS.md` (the same tree's build).

**Common:** same route, one launch at a time, no other benchmark, **local session** (T167's remote `Present` mode invalidates timing), same shader-cache state per arm. Residency env of T165's arm T. `RSX_FRAME_PERF=12,1,100000`, `RSX_VPC_WATCH` on c33.x (T113), `CELLMARK_DUMP` frames every 1 s from race entry +30 s to +40 s **without RSXI**, so the 4 s watchdog can't end the run. No flyover skip. Cap 240 s. Stop on fatal, `GcKernel::Present() Timeout`, or the cap.

| Arm | `RSX_VISUAL_PROFILE` | Question |
|---|---|---|
| A | unset | Baseline, with `c33` log |
| C | `0x01` | Colour alone: does `c33` fall, do tyres lift, does sand change at controlled `c33`? |
| S | `0x06` | Samplers + mips: does grain go? |
| D | `0x80` | Depth state: **do the sand boxes and streaks go?** Do vehicles smear (`0xBF`)? |
| F | `0x1BF` | Everything but MSAA |
| M | `0x1FF` | Adds MSAA: edges |

**Launches requested: 6, one per arm, in that order.** If only 2 can be approved: **D and F**. D tests the strongest new hypothesis, F the combination.

**Evidence and pass conditions:**
- Sand rectangles gone in D and F against A, with T165's regions plus the grid view.
- `c33` time series per arm.
- Grain: same-region high-frequency energy, A against S.
- `tools/blue_scan_t169.py` over all dumps.
- FPS, `wait_ms`, PSO and compile counts from `RSX_FRAME_PERF`.
- Load must reach the race. T145's C1 didn't, cause unknown; retry once only if approved.

**One extra capture, if F succeeds:** RSXI at race entry +35 s, `RSXI_VP_CONSTS=48 RSXI_UNITS=FFFF RSXI_GEOM=1`, to record units 6–13 and the 8 undumped programs. Expect it to risk the watchdog.

**Still needed from the user:** a PS3 reference image or video of the same scene. Without it, darker mid-tones and bright sand can only be judged from the guest's registers.

**Default change rule:** make a bit default only after its arm passes and a PS3 reference doesn't contradict it.

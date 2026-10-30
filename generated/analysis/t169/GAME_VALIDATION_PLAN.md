# T169: game validation plan

## Result of the authorised launches (D1, F1): the corrections did not run

**BLOCKED: both launches ran at baseline, so no correction has been tested in the game.** `RSX_VISUAL_PROFILE` is applied in `d3d12_init`, and the game's D3D12 path never calls that function: `rsx_d3d12_backend_init` calls `init_d3d12` directly, and only the Vulkan and Metal backends call `rsx_draw_engine_init`. **VERIFIED:** neither run logged `[visual]` or `Backend init`, and F still logged `[XFER] ... not applied` despite `0x1BF`. The `test_t169_visual` pin only checks where the text sits in the source, so it couldn't catch this.

| | D1 | F1 |
|---|---|---|
| Requested flags | `RSX_VISUAL_PROFILE=0x80` | `RSX_VISUAL_PROFILE=0x1BF` |
| Effective flags | None | None |
| ps3recomp / root | `001a56f` / `4f2c44f` | same |
| Exe sha256 | `766c45916524b85ff5343807c6bd467f8ec0e07097aba9fa9ab37b3d17f70491` | same |
| Run | `20261030-171540-t169-DD1` | `20261030-171824-t169-FF1` |
| Race entry | Host 123.2 s, gframe 4594 | Host 129.6 s, gframe 4810 |
| RSXI (entry + 25 s) | f005110: 40 snapshots, events partial (2,170 lines) | f005360: no snapshots, events partial (1,676 lines) |
| End | `GcKernel::Present() Timeout` at the capture, about 154 s | Same, about 160 s |
| `[vis-draw]` lines | 1,902 | 0 |

**Common:** console session, `TerminalServerSession=False`, fresh HDD copies, no retries, no manual driving. Beyond the plan, both arms had `D3D12_DBG=1`, a `dbwin_d3d12_t169.py` listener (the backend's `D3D12_IQ` stops at 80 messages, before the race), and one RSXI frame last.

**What the runs do show (baseline, debug layer on):**

| Race, capture tail removed | Frames | FPS (mean) | p50 ms | p95 ms | p99 ms | Median draw calls | `wait_ms`≈84 |
|---|---|---|---|---|---|---|---|
| D1 | 232 | 11.4 | 48.2 | 153.9 | 1437 | 1,845 | 0 |
| F1 | 248 | 11.1 | 48.4 | 144.5 | 1535 | 1,845 | 0 |

- **Light scene:** no race frame was under 700 draw calls, so there is no light-scene figure. Heavy equals the whole table.
- **Comparisons:** the two rows are repeats, not a correction's cost. T165's B3 and X1 (p50 92 ms) ran in the remote `Present` mode, so they aren't a valid baseline.
- **Validation:** 0 errors and 0 corruption in both, without GPU-based validation. Warnings only: #821, #820 (clear values) and #679 (PS output without RTV).
- **`c33.x`:** ends at 1.13 (D1) and 1.18 (F1). Both overshoot during the countdown, to about 4.9 and 7.1.
- **Images:** `img/D1_F1_dumps.png` (private, dump indices 0–4, 64 presenting frames apart). Overexposed sand, ground streaks and rectangular patches appear in both, with the same scene at indices 0, 1 and 4.
- **Run-to-run variance:** index 2 and 3 differ a lot (pink against white bands, camera angle), with identical effective flags. Differences of that kind can't be credited to any correction.

**Not measured, because nothing was enabled:** decals, shadows, grain, exposure, tyres, op 915 and velocity under the corrections.

**Next launch:** needs new authorisation. The pinned exe can test both arms without a rebuild through explicit switches. D: `RSX_DEPTH_STATE=1`. F: `RSX_COLOR_XFER=7 RSX_GUEST_SAMPLERS=15 RSX_TEX_MIPS=1 RSX_ZETA_EXACT=1 RSX_RT_WINDOW=1 RSX_RT_FEEDBACK=1 RSX_DEPTH_STATE=1 RSX_MRT_STATE=1`. Before launching, require a log line proving they applied: `[XFER] ... applies it` for F. For D, move RSXI later or drop it to keep the run alive longer; it ended each run here.

## Original plan

Only the 2-launch fallback (D and F) was authorised and used. T165's proposed grid-view launch never ran; no result exists.

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

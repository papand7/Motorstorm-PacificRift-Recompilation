# T165: bounded game diagnostic plan (NOT AUTHORISED; needs approval)

> **Status 2026-10-30: all 4 launches used. Results are in `GAME_TEST_RESULTS.md`; this plan is kept as written.**

**Exe:** `performance_next/ab/exe_n/MotorStormPacificRiftRecomp.exe`, sha256 `0304156bac3e6553b23cbb3ea24763c90f33b4c3aae01ac725ddf2a8ad3449b3`. No rebuild is needed for steps 1–2: it already has RSXI and all the switches. Only step 3 needs a build, of `agent/t165-vehicle-render-fix`.

**Before launching:** run ListAgents and check that no `run_*.py` or `seq_*.sh` is running (T162, T164 and the residency benchmarks have priority).

**Common:** the T3 environment and route (arm T switches), one launch at a time, wall-clock cap 195 s, `D3D12_DBG=1 D3D12_IQ=1`. Race entry can slip past the cap in a slow boot, so a run with no grid frame is repeated once, not extended.

**Capture point:** race entry + 30 s through the existing go-file trigger, when the grid is in view (the screenshot was at about +34 s). `RSXI=1 RSXI_VP_CONSTS=512`, 2 frames, pass snapshots.

| Step | Arm | Added switches | Answers |
|---|---|---|---|
| 1 | B | none | Names the vehicle programs, textures and alpha/blend/depth/cull state. Black pixels in the `before`/`after` pass images tell which draw wrote them, and whether they are opaque |
| 2a | X | `RSX_COLOR_XFER=7` | **Decides the leading candidate:** same grid, shaded bodywork lifts and sand stops saturating |
| 2b | S | X + `RSX_GUEST_SAMPLERS=15 RSX_TEX_MIPS=1` | Ragged edges and clamp patches |
| 3 | D | B + `RSX_VEHICLE_DIAG=1`, `_GO` = trigger file, `_MAX=20000` | Vertex inputs, only if 1–2 leave it unexplained: colour register or missing components (T163 `RSX_VTX_PARTIAL_0001`) |

Maximum 4 launches, 13 minutes. Output stays private under `generated/analysis/t165/runtime-*`.

**Offline after step 1:** isolations A–F (solid colour, no texture, no alpha test, opaque, no depth/cull, attribute check) on the captured vehicle draws, without further launches where the ucode and textures in the capture suffice.

**Confirmed if:** X moves shaded and lit surfaces in the direction and rough size of the model table, with 0 new debug-layer errors and unchanged draw counts.

**Refuted if:** vehicles stay near-black in X. Then step 1's per-draw data picks the next suspect, starting with shadow-map contents, since the sand's blocky shadows are also unexplained.

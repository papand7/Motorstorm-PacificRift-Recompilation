# T84: why the race image is black

2026-10-26. Offline only: no game build, no launch, no merge or push. No executable pin, physics, AI, exposure value or shader was changed.

**Inputs:**
- RSXI race frames f005625–f005627 of the T72 run `generated/runs/20261026-160135-t72-exposure-readback`. That run used the T64C exe `162afb4a…` with `VP_NOFIXPROJ=1` (the game's own camera) and `RSX_RT_READBACK=1`.
- The T71 frame f004425 and the T68 frame f004849 have the same op structure.
- Retail ELF `generated/decrypted/EBOOT.elf`.
- Backend source at `c529ab0` (T64C), `dfb9e2f` (T68 camera fix) and `595bd3a` (T75).
- T76/T78 reports (read-only, `Motorstorm01/t36-worktree/generated/analysis/t76|t78`).

**Tools:** all in `t84/tools/`; their outputs are in `t84/logs/`.

| tool | what it does |
|---|---|
| `optable.py` | one line per op |
| `passes.py` | per-pass summary |
| `reproject.py` | projects draws through another draw's camera |
| `scan_sem_headers.py` | finds the PPU code that builds NV406E semaphore headers |
| `compile_tu.py` | compiles single TUs with the exact `build.ninja` flags |
| `warn_diff.py` | diffs warnings between two trees |
| `run_suite.py` | runs the offline test suite across trees |

## Verdict

1. **The current race-performance exes render a black race for a reason already fixed (VERIFIED).**
   - `ps3recomp-t70g` (`88feeb5`) and `ps3recomp-t81` lack the T68 camera fix (`8654a4d`/`dfb9e2f`), and the T70/T79/T81 harnesses do not set `VP_NOFIXPROJ`.
   - So the backend still replaces the race camera (c0.x = −1.245), and the main pass back-face-culls the whole scene, exactly as found in T68.
   - **Safe fix:** carry `dfb9e2f` into that line. It was runtime-validated in T71.
2. **With the game's camera, the scene is lost before it reaches the RSX: no draw is submitted for the lower half (VERIFIED).**
   - The main pass receives only:
     - 12 chunks of a 10 km backdrop terrain;
     - 10+10 foliage/fog-layer draws;
     - one 14-index water strip, which passes 0 samples.
   - It receives no near ground (GroundRush), no sea surface, no static objects and no vehicles.
   - 180 object draws exist only in the planar reflection, and 155 of the reflection's 192 draws would be inside the main camera's frustum.
   - The backend dropped nothing and the FIFO walker never resynced, so every submitted command was executed.
   - **This is "geometry never rendered", not depth rejection, wrong target, post-processing, exposure or presentation.**
3. **T75 is RSX-correct but does not restore coverage (REJECTED as the cause).**
   - Draws 212–221 write no colour (their FP never writes H0) into a target cleared to 0 just before.
   - Their depth/stencil target `0x0B920000` is not read by any later op.
4. **T72's exposure lock is a consequence of finding 2 (VERIFIED).**
   - The lower luminance rows are black because the scene there is unwritten.
   - A single zero G sample pins c33.x at 35.3, so everything that *is* drawn saturates to white.
   - No exposure change is justified.
5. **Why the game submits nothing for the main view is not yet established.**
   - Ranked candidates are in §5. The leading one is the game's SPU visibility system (`evo::pvs` `pvsjob`/`occjob`, `GroundRushVisJobs`), HYPOTHESIS.
   - New opt-in instrumentation, commit `aa6658f`, can discriminate the candidates in one bounded run (§8).

## 1. Verified rendering pipeline (f005625; `logs/optable_f5625.txt`, `logs/passes_f5625.txt`)

| ops | target (zeta) | draws | content |
|---|---|---|---|
| 0–4 | shadow `0x0B030000` 1024×2048, then `0x01650000` cleared | 0 | shadow pass is bound but has **no draws** (as in T67) |
| 5–196 | `0x07B78D80` 640×480, no zeta | 192 | **planar water reflection:** 12 backdrop terrain, plus 117 `0E74E41D`, 38 `94C50138` and 25 `2F867C86` object draws |
| 197–208 | `0x00750000`+MRT `0x01650000` (`0x00ED0000`) 1280×720 | 12 | **main pass, backdrop terrain only** (`CEED7030`/`07A9CEC1`) |
| 209–221 | `0x0B830000` (`0x0B920000`) 640×360 | 11 | op 210 `DepthDownsample` (FP `0B027F41`); ops 212–221 alpha-tested depth/stencil marks (FP `02B9EC81`, no colour output) |
| 222–223 | `0x0BA10000` | 1 | copy of `0x0B830000`, which is always 0 (see §3) |
| 225 | `0x00750000` | 1 | water strip (FP `022CD841`: refraction of `0x750000`, normal maps, sun, fog); 14 indices, **0 samples** |
| 226–235 | `0x00750000` | 10 | foliage/shore overlay (FP `02B9EF81`, alpha discard below 0.02, blended); 3,349 samples |
| 236–241 | `0x02195900` 320×180 FP16, then down to 10×5 | 6 | quarter-res HDR/luminance (FP `0074B181`: 4 MRT1 taps, squared ×16, plus `0x0BA10000`), then a downsample chain |
| 243 | `0x01650000` | 1 | depth-reconstructed motion vectors, written into MRT1 (FP `0074CE81`); all zero because the intro camera is static |
| 244–248 | 8×8, 320×180 | 4 | small feedback/bloom targets |
| 249 | `0x01DD0000` 1280×720 | 1 | scene colour plus blur weight (FP `0074B441`: `0x750000`, velocity) |
| 250 | `0x07EBA600` 16×16 FP16 | 1 | exposure surface, read by the CPU (`func_004C3778`) |
| 251–259 | bloom chain | 9 | |
| **260** | **display buffer** (`0x10000`/`0x394000`, alternating) | 1 | **final composite** (FP `02193941`: bloom `0x7F2B600`, velocity `0x1650000`, scene `0x1DD0000`) |
| 261–262 | display buffer | 2 | HUD |

**Present:**
- T71 frames presented with S_OK.
- T68/T72 frames returned `DXGI_STATUS_OCCLUDED` (`0x087A0001`): the window was covered.
- The backbuffer snapshot is 79 % non-zero. Presentation is not a cause.

**Where expected pixels disappear (first stage):**

| stage | finding | label |
|---|---|---|
| geometry never rendered | the lower half of `0x750000` is the unwritten clear colour after op 208 and after op 235 (snapshots), and no main-pass draw targets it except the 0-sample op 225 | **VERIFIED (first loss)** |
| depth-rejected | 212–221 are rejected only by the T75 export defect, and they carry no colour (§3); terrain chunks 197–201/203 project off-screen or behind the camera (T72 §6, reproduced in `logs/reproject_f5625.txt`) | not the cause |
| wrong target | ops 5–196 use a y-mirrored camera: c1 negated, eye y −45.50 against −8.40, so the mirror plane is at y = −26.95; this is a genuine reflection | REJECTED |
| lost in post | `0x750000` is already black below the horizon before any post op | REJECTED |
| mis-exposed | exposure saturates drawn pixels to white; it cannot turn unwritten pixels black | consequence, not cause |
| not presented | op 260 composites the expected targets into the display buffer | REJECTED |

**Camera (VERIFIED from VP constants):**
- Eye (296.42, −8.40, −449.71) (= c32), forward (0.767, −0.033, 0.641).
- The image is upright: a point 20 units below eye height at 200 units projects to row 475, below the horizon at row 357.
- The backdrop chunks span x and z about ±10 km and heights −114 to 4925.
- So everything below the horizon (rows ~357–720) should be sea at y ≈ −27 and near ground, and none of it is submitted.

## 2. T75 assessment

| item | result | label |
|---|---|---|
| SHADER_CONTROL depth export (0xE) for op 210 | needed: FP `0B027F41` writes only r1.z = A·2⁻⁸ + R·2⁻¹⁶ + G·2⁻²⁴; the host drops the bits (`c529ab0`), and T75 passes them to the decompiler | VERIFIED source; the guest control word itself is still not logged (PARTIAL) |
| host zeta→ARGB8 view feeding that math | `zconv` writes R=[15:8], G=[7:0], B=stencil, A=[23:16] (`rsx_d3d12_backend.c` ~4733 @ `595bd3a`), which matches the FP's (A,R,G) = depth high→low | VERIFIED |
| depth compare / write mask | T75 maps RSX 0x200–0x207 and the guest write mask; this is RSX-correct for all titles | VERIFIED (22/22 tests) |
| depth attachment / ordering | 210 rebuilds `0x0B920000` from `0x00ED0000`; 211 clears the colour; 212–221; 223 copies. No feedback. | VERIFIED |
| **does T75 restore coverage?** | **No.** FP `02B9EC81` (4 instructions: TEX, MUL, SLT, KIL) never writes H0, so it outputs 0 into a target cleared to 0 at op 211. `0x0B920000` is not sampled or bound by any later op. `02B9EF81` (226–235) reads units 0/11/13/15, **not** unit 5 as T75 stated. | **REJECTED** (relies on the decompiled listing) |

- **Recommendation:** keep T75 as a separate fidelity fix. Do not expect a visible race change from it.
- T75 is **not** integrated into T84.

## 3. T72 assessment

1. **Sample positions:** five points at G-half offsets +0x242, +0x52A, +0x552, +0x592 and +0x5EA of `0x07EBA600`, i.e. pixels (8,4), (5,10), (10,10), (2,11) and (13,11). Rows 10–11 correspond to 62–75 % of the screen height (VERIFIED, T72/T75).
2. **Source chain:** the samples come from `0x02195900` (op 236), downsampled to 10×5 (op 241), then exposure op 250. Op 236 computes 16·(4-tap mean of MRT1)² plus `0x0BA10000`.rgb. MRT1 is the scene /16, and `0x0BA10000` is always 0 (§2). So the luminance in a row is zero exactly where the scene is unwritten. The `0x02195900` snapshot is 29.9 % non-zero, all in the upper part (VERIFIED).
3. **Readback, timing, format:** the copy works; the G half is read via `lhz +2`; the surface is read one flip later. T72's decoded values match E = 0.3 + 0.21/G (VERIFIED, T72).
4. **c33:** the geometric mean of the G samples means one zero sample pins the target at Emax, giving c33.x → 35.3 (VERIFIED, T75 `cpu_exposure.md`). Without `RSX_RT_READBACK` (the default, and the T70/T81 harnesses) all five samples read 0.
5. **Conclusion:** the lower luminance rows are black because §1's scene content is never drawn. Clamping exposure would hide the symptom, so it was not done.

## 4. The missing scene, by element

Vehicle attribution follows T76/T78, which leave the vehicle → draw link unproved (PARTIAL). That does not matter here: the main pass contains **no** draw of any object vertex program.

| element | main pass | reflection | label |
|---|---|---|---|
| backdrop terrain (`CEED7030`) | 12 draws, 422,162 samples (white, exposure) | 12 draws | present |
| near ground / track (GroundRush) | **none** (the backdrop has no chunk below the horizon near the camera) | none | **missing** |
| sea surface | only op 225 (14 indices, w ≤ 0 on 6, **0 samples**; cause not established) | n/a | **missing**; op 225 PARTIAL |
| static objects (`0E74E41D`, `2F867C86`, `94C50138`) | **0 draws** | 180 draws at y −37…+3, shoreline (x 350–1145, z 8–486) | **missing in main** |
| vehicles | 0 object draws, so none | not attributable (T76/T78) | **missing** |
| sky | no separate sky draw; the white upper band is backdrop terrain | — | PARTIAL |
| foliage / fog layer | 226–235 drawn; 212–221 depth/stencil only | — | present |
| shadows | shadow target bound, 0 draws | — | missing (T67) |
| lighting / exposure | c33 pinned at 35.3 | same | consequence |

**Expected commands do not reach the backend.** The evidence is:
- `draw_acct`: `callbacks.recorded == groups.draw`, `dropped=0`;
- no `[cellGcmSys] FIFO resync` or unmapped-branch line in the T68/T71/T72/C5 logs;
- guest ZPASS reports always return 0xFFFF ("visible"), so GPU occlusion queries cannot hide anything.

## 5. Root-cause candidates, ranked by evidence

| # | candidate | evidence | label |
|---|---|---|---|
| 1 | camera substitution in the T70G/T79/T81 race line (no `dfb9e2f`, no `VP_NOFIXPROJ`) | `git merge-base`: `8654a4d` is not an ancestor of `88feeb5` or of the T81 head; T70 `arm_env` sets no `VP_*`; mechanism VERIFIED in T68 | **VERIFIED** (black in current runs) |
| 2 | **the game submits nothing below the horizon for the main camera** | §1, §4 | **VERIFIED location**; mechanism open |
| 2a | the game's SPU visibility (`evo::pvs::PVSComputer`/`OccluderComputer` = `pvsjob`/`occjob`, `GroundRushVisJobs`) marks main-camera components invisible | It explains objects, vehicles and ground vanishing together while the reflection keeps objects. The ELF's `OcclusionStatsViewer` classes components as visible / occluded / out of range / outside frustum, for Static/Dynamic/Vehicles. Possible host-side inputs: SPU interpreter numeric behaviour, or data the SPUs read that the host never produces. | **HYPOTHESIS (leading)** |
| 2b | the RSX runs ahead of PPU/SPU-written command data because NV406E ACQUIRE is a no-op by default (`GCM_SEMA_ACQUIRE` unset) | The game emits SemaphoreOffset+Acquire at `0x522950` (label 0x48, a sequence value) and at `0x346D1C`/`0x3507EC` (label 0x49 == 1). The latter two pair with an NV4097 back-end release on label 0x4A and a PPU spin, but `[RSX] first back-end release` was **never logged** in any run, so those two sites do not execute. **T84B:** `0x522950` guards the ZPASS occlusion-report double buffer, and visibility waits only on SPU job lists (§9.3). | **REJECTED for visibility (T84B)** |
| 2c | a legitimately empty race intro | sea and near ground are geometrically required; objects lie inside the main frustum (`reproject.py`: 155/192) | REJECTED |
| 3 | exposure pinned at 35.3 (white saturation) | consequence of 2 plus readback off by default | VERIFIED (secondary) |
| 4 | T75 depth export | correct, but feeds no visible output (§2) | REJECTED as cause |
| 5 | op 225 water strip has 0 samples | 6/14 vertices have w ≤ 0 and 8 triangles are degenerate; not reproduced offline (its VS needs attributes 8/10/11) | PARTIAL, minor |

## 6. Safe fixes

- **Established:** integrate the T68 camera fix (`8654a4d`, `c8c76ea`, `dfb9e2f`; 4 files, +126/−2) into the race-performance line. Alternatively set `VP_NOFIXPROJ=1` in its harness. This is required before any image from the T70G/T81 exes can be judged. It needs separate authorization; I did not do it.
- **Not established:**
  - no fix for candidate 2;
  - no exposure clamp;
  - no shader replacement;
  - no forced draws;
  - no `GCM_SEMA_ACQUIRE` default change;
  - T75 is not integrated.

**New diagnostic instrumentation** (off by default; behaviour unchanged):
- **Worktree:** `ps3recomp-t84`, branch `agent/t84-race-render-diag`, commit **`aa6658f`** on `dfb9e2f`.
- **Size:** 6 files, +371/−4.
- **Patch:** `t84/patches/0001-…patch`, sha256 `4e2f767c…`.

| switch / output | records |
|---|---|
| `GCM_SEMA_TRACE=<max>[@<flip>]` | every NV406E OFFSET/ACQUIRE/RELEASE and NV4097 0x1D6C/0x1D70/0x1D74: FIFO offset, CALL return, label offset/value, the label word at that moment, and the ACQUIRE outcome (satisfied, held or passed-unsatisfied) |
| `GCM_CALL_TRACE=<max>[@<flip>]` | per CALL: target, method words and BEGIN_END count; flags `empty` and `no-draw` |
| RSXI draw events | now carry `cmd_offset`, `call_ret` (main ring or CALLed list) and `shader_control` (depth-export bits); `optable.py` prints them |

**Already available, no build needed:**
- `RSX_RT_READBACK_PROBE=7EBA600:242/52A/552/592/5EA` for the five luminance samples;
- RSXI `bind_rt`, depth/stencil state, occlusion, snapshot coverage, `RSXI_VP_CONSTS` (c33) and present identity;
- `passes.py` for draw counts per pass.

## 7. Offline results

**Translation units:** the exact `build.ninja` flags of the T64C build, under `vcvars64` with clang-cl 23.1.3. Logs are in `t84/tu/` and `logs/tu_warning_diff.txt`.

| TU | base `dfb9e2f` | T84 `aa6658f` |
|---|---|---|
| `cellGcmSys.c` | 0 errors, 699 diagnostics | **0 errors**, 704 (+3 `getenv` deprecations, the file's existing idiom; +2 `-Wunsafe-buffer-usage` in the new header's `snprintf`) |
| `rsx_d3d12_backend.c` | 0 errors, 2596 | **0 errors**, 2596 (identical; line shifts only) |
| `rsx_commands.c` | 0 errors, 126 | **0 errors**, 126 (identical) |

**Test suite:** `tools/run_suite.py` ran 30 renderer tests in three trees. Logs are in `logs/suite/` and `logs/suite_summary.txt`.

| tree | PASS | SKIP (POSIX-only fixture) | FAIL |
|---|---|---|---|
| `ps3recomp-t68` (`dfb9e2f`, base) | 24 | 5 | 0 (`test_gcm_sync_trace` absent) |
| `ps3recomp-t84` (`aa6658f`) | **25**, including the new `test_gcm_sync_trace` (header harness plus 16 hook checks) | 5 | **0** |
| `ps3recomp-t75` (`595bd3a`) | 24, including `test_d3d12_depth_state` 22/22 | 5 | 0 |

- **Coverage:**
  - shaders: `fp_alias`, `fp_shadow_compare`, `shader_trace`;
  - depth state;
  - render targets: `rt_clip`, `rt_pool_srv_layout`, `rt_readback` (275 checks), `rt_vis_trace`, `zeta_pool`;
  - camera: `vp_fallback`, `vp_branch_base`;
  - RSXI: `rsxi_hooks`, `rsxi_geom`, `rsx_inspect`, `rsxi_frame_gain`;
  - presentation and transfer.
- **Skips:** `rsx_immediate_vertices`, `gcm_flip_stream`, `gcm_get_on_jump`, `gcm_get_on_release`, `gcm_report_trace` (they need POSIX linking).
- **Baseline note:** T75's 7 base failures do not reproduce under this environment (MSVC + LLVM + T17 cc shim); they were environmental.

**Public audit:** `audit_public.py --staged` reports the same 25 baseline items as T70H/T81, none in changed files (`logs/audit_staged.log`).

**Not run:** a full exe build and a GPU replay.

## 8. Proposed bounded runtime validation (each run needs separate authorization)

**Common to every run:**
- the T72 route and env, with RSXI on 3 race frames;
- `RSX_RT_READBACK=1` plus the probe above;
- a fresh private HDD, ≤ 205 s, `--timeout 210`, no driving;
- no `TEX_SAVE`, no `RT_CLEARDBG`, WWS AOT off.

| run | exe | change against T72 | question answered | success / readout |
|---|---|---|---|---|
| **V1** (no build) | T64C `162afb4a…` | add `GCM_SEMA_ACQUIRE=1 GCM_SEMA_ACQUIRE_MS=20` | candidate 2b: does honouring ACQUIRE bring back main-pass objects, ground or sea? | `passes.py` main pass > 23 draws, or object VS in 197–235; `[SEMA] … gave up` lines; frame time against T72 |
| **V2** (needs a build of `aa6658f`) | private build dir re-pointed to `ps3recomp-t84` | `GCM_CALL_TRACE=600@<race flip>`, `GCM_SEMA_TRACE=600@<race flip>`, RSXI | 2a vs 2b: are main-pass object lists CALLed but empty/unfilled, or never CALLed? | `[call] … empty/no-draw` between ops 196 and 197 means 2b-like; no CALLs there means submission was culled (2a) |
| V3 (after V2 points to 2a) | — | PT on the PVS consumer (needs RE of the `pvsjob` output, not done) | which visibility stage rejects | — |

**Separately:** integrating `dfb9e2f` into the T70G/T81 line (§6) is a prerequisite for using those exes for image checks.


---

# T84B: main-camera visibility (2026-10-26, offline)

Static analysis of the retail ELF (`generated/decrypted/EBOOT.elf`) with new read-only tools:

| tool | purpose |
|---|---|
| `t84/tools/elf.py` | ELF, RTTI and vtable helpers |
| `xref.py` | TOC-slot and lis/addi cross-references |
| `ppcdis84.py` | annotated disassembly |
| `vis_report.py` (+ `test_vis_report.py`) | summarizes a visibility trace |

Listings are in `t84/logs/t84b_*`. No build or launch was run, nothing was merged or pushed, and no pin changed.

## 9. Verdict (T84B)

- **The reflection and the main camera run the same visibility code (VERIFIED, static).**
  - Each frame loops over every active view and, for each view, over 24 scene-object lists, kicking one PVS computation per (list, view).
  - Every scene-list renderer family waits for its own view's result.
  - No renderer bypasses visibility, and no buffer is shared between views.
  - So the main view can only differ through its per-view data (camera block, per-view record, view registration) or its PVS result.
- **Visibility synchronization is SPU job-list completion, not an RSX semaphore (VERIFIED).**
  - The one remaining NV406E acquire, `0x522950`, guards the ZPASS occlusion-report double buffer.
  - The host answers every report with a constant 0xFFFF ("visible"), so that ordering cannot change visibility.
  - No ignored GPU/CPU sync operation lies on the visibility path.
- **Where main diverges is not measurable offline: it needs one bounded traced run, which needs no build (§9.6).**
  - Decision rule: if the main view's renderers wait but never call `ExecutePushBuffer`, its PVS result is empty.
  - The PVS counters (v2) then say whether components were out of range, outside the frustum or occluded.

## 9.1 Visibility pipeline (original guest addresses)

| # | stage | address / structure | label |
|---|---|---|---|
| 1 | per-frame loop over views × 24 scene lists | `0x331D14`–`0x331EB0` in `0x330A54`; view index = `[view+0x430]`; `li r6,1` (async) | VERIFIED |
| 2 | kick per (list, view) | `0x458558` → `Scene::KickVisibility` `0x457BB0`: `Vis = list+0x74[[view+0x430]]`; per-view record `r5` | VERIFIED |
| 3 | main-camera parameters | 0x200-byte PVS parameter block filled by `0x5F7B30` (via stub `0x756178`) from the view's camera object `[Vis+0]`: matrices from camera +0xB0, +0x30, +0xF0, +0x200 to block +0x40, +0x80, +0xC0, +0x100; frustum data from `0x4F3BA0` at block +0x140; component arrays from the scene list at block +0x1E4…+0x1F8 (count at +0x1E8) | layout VERIFIED; field meanings PARTIAL |
| 4 | `Vis::Kick` | `0x45CB30`: copies the block to `Vis+0x20` and the per-view record to `Vis+0x230`, then `PVS->Start` (slot +08) | VERIFIED |
| 5 | `PVSComputer` | RTTI `evo::pvs::PVSComputerImpl`, vtable `0x1042DA8`; constructor `0x5F6C30` (factory `0x5F7360`, created by the `Vis` constructor `0x45CEC8` at `Vis+0x228`); job module "pvsjob" (descriptor `0x108D578`), job list "PVS" | VERIFIED |
| 6 | job submission and SPU inputs | `Start` `0x5F69B8` → builder `0x5F61B8`: one job per 304 components; DMA list from block +0x1EC (64 B/comp), +0x1F0 (16 B/comp), +0x1F4, +0x1F8 (48 B/comp); per-job output 0x1CA0 = 32-byte counter header + 24 B/comp; list kicked through the job-manager vtable (+0x14) | VERIFIED structure |
| 7 | `pvsjob` execution | EA `0xFD3180` (0x27A0 B); 112 runs/flip in the race (T79) | runs VERIFIED; outputs not observed |
| 8 | completion and sync | `Vis::Wait` `0x45CAA8` → `PVS->Finalize` `0x5F74B0`: waits on the job list (vt +0x1C), then sums the 8 job counters into `*[Vis+0x220]`. The async callback `0x108A9B8` → thunk `0x933440` → `0x32DE28` is a bare `blr`, so nothing is lost if it is not delivered. | VERIFIED |
| 9 | PPU consumption | renderer families `0x944008`, `0x944218`, `0x944760`, `0x9449F0`, `0x944C00` and `0x944E98` (T76 scene-list families) plus `0x481B00` all call `Vis::Wait` | VERIFIED |
| 10 | render-list generation | e.g. `0x944C00`: list base `[Vis+0x260]`, count = `[[Vis+0x278]+0] + [[Vis+0x278]+4]`. **Count 0 skips the draw** (`0x944CAC` → `0x944DA0`). | VERIFIED |
| 11 | command-list submission | batches of ≤ 255 entries go to `RenderSystemATG::ExecutePushBuffer` `0x50D868` (context: +4 list, +0x10 entries, +0x24 view index), then `renderablejob`, then the FIFO | VERIFIED call; FIFO link per T76 |
| — | `occjob` | `evo::pvs::OccluderComputerImpl` vtable `0x1042D48`, constructor `0x5F5700` (module "occjob", list "Occluder", created from `0x348468` via factory `0x5F5B78`); `Run` `0x5F5618` returns immediately with no occluders. How its output feeds `pvsjob` was not traced. | PARTIAL |
| — | ground | "groundrushvisibilityjob" and the "GroundRushVisJobs" list are set up in `0x44D5E8` (`0x44F8DC`, `0x44FA04`); the per-frame kick was not traced | PARTIAL |

## 9.2 Main vs reflection

| question | answer | label |
|---|---|---|
| same visibility system? | yes: one loop, the same Kick/Start/Finalize/Wait path for every view | VERIFIED |
| reflection bypasses occlusion? | no structural bypass: `Start` is called with the same arguments (`r8=1`, async) for every view | VERIFIED (static) |
| different SPU jobs? | no: the same "pvsjob" list type per `Vis` | VERIFIED |
| buffers reused across views? | no: one `Vis` and one PVS computer (own job and output buffers) per (list, view) | VERIFIED |
| results stale or overwritten? | `Start` first waits for a batch still in flight (`0x5F6A10` → vt +0xC); `Finalize` zeroes and re-sums | VERIFIED code; runtime ordering unobserved |
| camera matrices correct? | GPU constants: yes, main c1 = −reflection c1 (§1). The PVS block is built on the PPU from the same camera objects, but its values were never observed. | PARTIAL |
| earliest divergence | between the per-view inputs (camera block, per-view record, view registration) and the visible count: **runtime only** | open |

## 9.3 Synchronization audit

- **`0x522950` (in `0x5219A0`):**
  - It is reached after a loop issuing NV4097 `GET_REPORT` (ZPASS, via `0x733880`, emitting header `0x00041800`); T72 logged report slots `0x14100`–`0x14130`.
  - It emits `SemaphoreOffset(0x48)` and `SemaphoreAcquire([0x12C5EAC+8])`, where that value is a 0/1 index flipped by `xori 1` right after.
  - **Semantics (VERIFIED structure): the RSX may not write the next report buffer until the CPU has released it.** The label-0x48 writer was not identified.
  - The host writes every ZPASS report as 0xFFFF regardless of order, so honouring this acquire cannot change visibility.
  - **Not a cause.** Host semaphore behaviour is left unchanged, as required.
- **`0x346D1C` / `0x3507EC`:** never executed in any run (§5, 2b).
- **SPU-side semaphores:** the T84 data-word hits (`0xFA0A74`, `0xFA0EB4`) are a table of `0x0008xxxx` constants inside the SPU ELF at `0xF98780`, not command headers. That is a false positive.
- **The visibility path's only sync** is `Finalize` waiting on its WWS job list, which the host completes (`pvsjob` 112/flip, T79).

## 9.4 Instrumentation (disabled by default, read-only)

| what | where | build? |
|---|---|---|
| visibility kicks per view, `Vis::Wait` per renderer family, `ExecutePushBuffer` batches/entries per view, PVS Start/Finalize, occluder runs, unblended "drew" / "exit" labels | `t84/vis_trace_v1.cfg` (`PS3_TRACE_FILE`), summarized by `t84/tools/vis_report.py` | **no**: the existing hooked T64C exe |
| the same plus the 8 PVS counters and the visible-count pair per view (on each Kick, the previous frame's values are still in place) | `t84/vis_trace_v2.cfg` | yes: ps3recomp-t84 |
| PT `[[rN+a]+b]` reads and `regs@ADDR=` per-site register lists | `runtime/ppu/ppu_trace.cpp` (generic; `docs/TRACING.md`) | yes |
| command-list CALLs (`empty` / `no-draw`), semaphore waits/releases, per-draw FIFO provenance | `GCM_CALL_TRACE`, `GCM_SEMA_TRACE`, RSXI `cmd_offset`/`call_ret` (`aa6658f`) | yes |
| `pvsjob`/`occjob`/`groundrushvisibilityjob` submitted and completed | existing `PS3_FTRACE_SPUJOB` job spans | no |

**Read-only guarantees:**
- PT has no write path. The new test asserts the guest result and the dereferenced memory are unchanged, and the existing `test_results_unchanged` still passes.
- The disabled-hook overhead is unchanged at about 0 %.
- Output is bounded: `limit=3000` per site, then every 256th visit, `max=150000`.

## 9.5 Offline results (T84B)

- **`ps3recomp-t84` commit `e32bcc5`** (on `aa6658f`; patch `t84/patches/0001-ppu_trace-…patch`): changes `runtime/ppu/ppu_trace.cpp`, `runtime/ppu/tests/test_ppu_trace.cpp` and `docs/TRACING.md`.
- **`ppu_trace.cpp` TU** (exact T64C flags): 0 errors, 524 → 561 warnings. All of them are more instances of categories the file already has (C++98-compat, unsafe-buffer, old-style cast, padding); see `logs/tu_warning_diff_t84b.txt`.
- **Suite** (`logs/suite_summary_t84b.txt`, 42 PPU, GCM, SPU and renderer tests):

  | tree | PASS | SKIP | FAIL | absent |
  |---|---|---|---|---|
  | `ps3recomp-t68` (base) | 30 | 11 | 0 | 1 |
  | `ps3recomp-t84` | **31** | 11 | **0** | — |

  - Per test the results are identical; the extra pass is the new `test_gcm_sync_trace`.
  - `test_ppu_trace` passes, including the new `test_registers_site_and_pointer`.
- **Skips (POSIX-only fixtures, both trees):**
  - `rsx_immediate_vertices`, `gcm_flip_stream`, `gcm_get_on_jump`, `gcm_get_on_release`, `gcm_report_trace`;
  - `ppu_dispatch_depth`, `spu_interpreter_handoff`, `spu_interpreter_ilh`, `spu_sdcrz`, `spu_smc_lqa_stqa`, `spurs_scheduler`.
- **Known baseline failure, unchanged:** `test_spu_fnms_zero_extended` (UBSan link, T81).
- **`test_vis_report.py`:** 5/5 PASS on synthetic v1 and v2 logs in the exact PT format.
- **All traced addresses are lifted entries or labels** in `generated/ppu` (`func_00458558`, `func_0045CB30`, `func_0045CAA8`, `func_0050D868`, `func_005F69B8`, `func_005F74B0`, `func_005F5618`, `loc_00944D80`/`loc_00944DA0`).

## 9.6 Recommended minimal runtime experiment (needs authorization; one launch, no build)

**Setup:**
- **Exe:** T64C `162afb4a…` (hooked), with the T72 route and env:
  - `VP_NOFIXPROJ=1`, `RSX_RT_READBACK=1`, RSXI on 3 race frames;
  - a fresh private HDD, ≤ 205 s, `--timeout 210`, no driving;
  - no `TEX_SAVE`, WWS AOT off.
- **Add:**
  - `PS3_TRACE_FILE=generated/analysis/t84/vis_trace_v1.cfg`;
  - `PS3_FTRACE_SPUJOB=3214:1320` with the race-entry arm.
- **Read:** `py -3 -I t84/tools/vis_report.py <run>/stderr.log`, plus `passes.py` on the RSXI frames.

**Decision table:**

| main view (index = `ExecutePushBuffer` +0x24 / `[view+0x430]`) | meaning | next step |
|---|---|---|
| never kicked | the view is not registered or active; upstream of PVS | trace view registration (`0x330A54` view list `r25`/`r19`) |
| kicked, its renderers wait, 0 `ExecutePushBuffer` entries while the reflection's are > 0 | the PVS result for main is empty | v2 build: counters out of range / frustum / occluded; then compare the PVS block with the RSXI VP constants |
| `ExecutePushBuffer` entries > 0 but no main-pass draws in RSXI | lost in `renderablejob` or the push-buffer path | `aa6658f` build: `GCM_CALL_TRACE` (`empty`/`no-draw`) |
| main renderers never wait | the main scene-list renderables are not in the render list | trace the render-list build (T76 `0x4E6FF8`) |

# T84C: V1 main/reflection visibility runtime trace (one launch, 2026-10-26)

## 10. Verdict

- **Visibility is not where the main view loses its geometry.** All 4 race views are kicked, waited on and hand non-empty lists to `ExecutePushBuffer` in every frame, so cases A, B and D are REJECTED.
- **Case C applies (VERIFIED for the counts, PARTIAL for the mapping):**
  - each frame the game calls `ExecutePushBuffer` 21 times with 419 entries in total;
  - the RSX receives only the 192-draw reflection: the shadow atlas gets 0 draws and the main pass gets only 12 backdrop + 11 overlay draws, with no object draws.
- **The earliest verified divergence is downstream of visibility:** between `ExecutePushBuffer` (`0x50D868`) and the RSX.
  - `0x50D868` does not emit draws itself. It takes a slot from an atomic counter at `rs+0x24E8` and fills a job block, so command generation goes through a separate (SPU) push-buffer stage.
  - Which view feeds which RSX pass cannot be proven from v1 data (see 10.3).

## 10.1 Run

- **Executable:** `generated/analysis/t64/exe/MotorStormPacificRiftRecomp.exe`, sha256 `162afb4a40fd8dc9f0f0ae60fe30eb0b2ebdb9dc785281a48c3bcd47882ab6b7`. The hash was checked against `EXE_SHA` before launch.
- **Runner:** `t84/run_t84c.py`, which is `t72/run_t72.py` with three changes:
  - the config below;
  - `RSX_RT_READBACK*` removed, since V1 doesn't need it;
  - `PS3_FTRACE=150:30:<rt>/ftrace.txt` added.
- **Environment otherwise as T72:**
  - `VP_NOFIXPROJ=1`, fresh private HDD (`t84/hdd0`, `t84/hdd1`), `--timeout 210`, controller cap 205 s;
  - same navigation, no driving, no manual input;
  - no `GCM_SEMA_*`, `GCM_CALL_TRACE` or `TEX_SAVE`; WWS AOT not set.
- **Trace config `t84/vis_trace_t84c.cfg` = `vis_trace_v1.cfg` + the T72 controller sites.**
  - Both are needed because only one `PS3_TRACE_FILE` is allowed and the controller depends on its PT sites.
  - The old exe has a single list of 12 registers, so `r31`, `[r3+0x10]` and `[r3+0x220]` (unused by the report) gave way to `[r5+0..8]` (page paths).
  - `sample=251` instead of 256, to avoid aliasing with the per-frame period.
  - One harmless `config-error`: a `;` inside a comment line splits it.
- **Traces:**
  - run dir `generated/runs/20261026-222857-t84c-vis-trace`;
  - controller files `t84/runtime-20261026-222856/`;
  - analysis `t84/logs/t84c_*.txt`;
  - tools `t84/tools/t84c_frames.py`, `t84c_lists.py`.
- **Timeline:**
  - main menu at 38 s;
  - `PostLevelLoad` marker `0x8C2A0` at 152.3 s;
  - first visibility kick at 157.68 s (none before the race; the garage doesn't use this path);
  - RSXI capture of frames 4936–4938 at 177 s; stop at 184.4 s; no process left behind.

## 10.2 Per-view evidence

The window 157.68–162.01 s (17 complete frames) is unsampled. `ExecutePushBuffer` stayed below the PT limit (1,959 calls), so its events are complete for all 96 race frames.

| view (`[view+0x430]`) | view object | kicks / frame | waits / frame (renderer site in `0x481B00`) | `ExecutePushBuffer` / frame | scene-list slots with entries |
|---|---|---|---|---|---|
| 0 | `0x18677460` (separate allocation) | 24 | 93: `482AA8`, `482D2C`, `482940` 24 each, `4827E4` 21 | 9–10 batches, 138–145 entries | 0–3 |
| 1 | `0x18BB6BF0` | 24 | 24 (`483024`) | 3 / 33 | 0–2 |
| 2 | `0x18BB7080` | 24 | 24 (`483024`) | 4 / 118 | 0–3 |
| 3 | `0x18BB7510` | 24 | 24 (`483024`) | 4 / 123 | 0–3 |

- **Every frame (all 96) has entries for all 4 views.** At capture time: view 0 has 145 entries in 10 batches; views 1–3 have 33 + 118 + 123.
- **Scene-list slots 4–23 are empty for every view.**
  - Slot 3 has 17 entries per frame in view 0 against about 75 in views 2 and 3.
- **Order within a frame:**
  - views 1 → 2 → 3, each through renderer site `483024`;
  - then view 0 through renderer sites `482AA8` (39) → `482D2C` (79) → `482940` (3) → `4827E4` (17).
- **View identity:**
  - **View 0 is the main camera (PARTIAL).** It is the only view with four renderer sites, it has its own allocation, and it has index 0.
  - **Views 1–3 (contiguous objects, stride `0x490`) are either shadow cascades or the reflection (HYPOTHESIS).** The RSX order is shadow atlas `0x0B030000` 1024×2048 (0 draws), then reflection (192), then main (12). That order matches "views 1–3 = cascades", with the reflection and main pass then both fed from view 0.
- **The `0x944xxx` renderer families (and `bb` sites `944D80`/`944DA0`) are not used in the race:** 0 hits.

## 10.3 Responsible subsystem and uncertainties

- **Responsible stage (PARTIAL):** `ExecutePushBuffer` → push-buffer job → FIFO CALL.
  - About 419 visible entries per frame turn into about 180 object draws, all in the reflection.
  - The shadow atlas and the main pass, which are fed by either views 1–3 or view 0, get none.
- **Unknown:**
  1. which renderer site (`482AA8`, `482D2C`, `482940`, `4827E4`, `483024`) binds which RSX target;
  2. whether a push buffer for the main pass or the shadow pass is built empty, built but never CALLed, or CALLed into a stale buffer;
  3. SPU job activity. This exe records no SPU busy/wait spans (`ftrace.txt`: kinds 1, 2, 7, 9, 10 only, 0 dropped) and has no `PS3_FTRACE_SPUJOB`. That `pvsjob` completes is inferred only from the non-empty `Finalize` results.
- **Not measured:** Havok steps per frame (no instrumentation in V1).

## 10.4 Correctness checks

| check | result |
|---|---|
| fatal errors / assertions / access violations | 0 / 0 / 0 |
| SPU job or DMA errors | none logged |
| race-entry | `0x8C2A0` at 152.3 s; vis from 157.68 s |
| trace duration | race 157.68–184.4 s, ~4.4–4.9 fps, 263–265 RSX draws per frame (`rsx-hb`), as in T72 |
| dropped records | PT 61,472 events < `max` 150,000 (no `ev=budget`); ftrace 0 dropped |
| sampling | per site, after 3,000 hits 1 in 251; kicks and waits complete only up to 162.01 s |

## 10.5 Recommendation

- **Command-list tracing first:** a T84 build with `aa6658f` (`GCM_CALL_TRACE`, per-draw provenance) plus `vis_trace_v2.cfg` (per-site registers).
  - It shows which FIFO CALL targets each renderer site produces, and whether the main or shadow push buffers are empty or never called.
- **V2 PVS counters are not needed for this question,** because the main view's visible lists are already non-empty.
- **Offline, before any build:**
  - map the five renderer sites in `0x481B00` to their RSX targets (surface setup calls before each wait);
  - reconstruct the job `0x50D868` queues (block fields at slot+0x198..0x1E8).


# T84D: scene entries to RSX command submission (offline, 2026-10-27)

## 11. Verdict

- **VERIFIED (static):** every race scene list reaches the GPU through the same path:
  1. `RenderableProxy::Render` (`0x482680`);
  2. `ExecutePushBuffer` (`0x50D868`);
  3. a "renderablejob" SPURS job that writes a 0x4000-byte output slot;
  4. a PPU `SetCallCommand` (`0x50E0FC`) to that slot in the main FIFO.
- **VERIFIED (static):** the PPU stores RET (`0x00020000`) into word 0 of the slot before it queues the job (`0x50D914`). It never reads the slot back.
- **VERIFIED (static):** nothing in the FIFO orders the CALL after the job. The only wait is the PPU spin at frame end (`0x50C818`, `[rs+0x2560]==[rs+0x44C]`), and it runs after all CALLs are emitted.
- **Earliest divergence that can be checked: HYPOTHESIS, not yet verified.** View 0's CALLs reach an empty slot that still holds RET. Either the host walker gets there before renderablejob has written it, or renderablejob writes nothing for those lists. This would match T84C: views 1–3 get draws, view 0 gets none. Nothing measured so far tells these two cases apart.
- **BLOCKED without a run:** which render target each view uses. It can't be derived statically.

## 11.1 Renderer sites (Phase 1)

The five sites are cases of a 6-way switch on the proxy kind `[this+0x58]` (jump table `0x482794`). They are not separate functions of `0x481B00`.

| site | kind | sub-block `[this+0x60]+` | view (`[[Vis]+0x430]`) | status |
|---|---|---|---|---|
| `0x4827E4` | 0 | +0x000 | 0 | VERIFIED |
| `0x482940` | 1 | +0x060 | 0 | VERIFIED |
| `0x482AA8` | 2 | +0x0C0 | 0 | VERIFIED |
| `0x482BE4` | 3 | +0x180 | – (0 hits in T84C) | VERIFIED |
| `0x482D2C` | 4 | +0x120 | 0 | VERIFIED |
| `0x483024` | 5 | +0x1E0 | 1–3 | VERIFIED |

- In each sub-block, +4 is the render system and +0x58 is the Vis.
- Lists are sent in batches of ≤ 255 entries through `[sub+4]->vt+0xB8` = `ExecutePushBuffer`. The context fields are: +0 kind, +4 list, +0x10 count, +0x24 view.
- Execution order is set by proxy registration order. It is not encoded in the sites (PARTIAL).
- Render target: PARTIAL. It comes from the render-context result stored at ctx+0x2C and is not derivable offline.

## 11.2 Push-buffer generation (Phase 2)

`rs` is the render system (`0x10CE69E0` in T84C).

| item | location | status |
|---|---|---|
| output slot | slot = atomic ++`[rs+0x24E8]`; EA = `[rs+0x24F0+4*(parity&1)]` + slot·0x4000 | VERIFIED |
| RET pre-store | `0x50D914`: word 0 of the slot = `0x00020000` | VERIFIED |
| job block | `[rs+0x2460]` + job·0x1F0, job = `[rs+0x44C]` (++ at `0x50E114`): +0xC0 slot, +0xCC list, +0xD0 count, +0x1E0 flags (kind), +0x1E4 → `rs+0x2560` (completion counter) | VERIFIED |
| DMA list | block 0x1F0; `rs+0x460` 0x2000; entry list; `[rs+0x2474]` (`[rs+0x2468]`·0x60) | VERIFIED |
| queue | `[[rs+0x2464]+4·job]` vt+0xC alloc, vt+0x14 submit; module "renderablejob", list "Renderable" (`0x511CD0`) | VERIFIED |
| completion | SPU increments +0x1E4 | HYPOTHESIS |
| PPU consumption | `SetCallCommand` (`0x757028` → `0x735BB0`, offset\|2) into `[0x12C5CAC+4]`, issued right after the job submit | VERIFIED |
| output length | not recorded on the PPU; only the walker can see it | VERIFIED |
| frame end | `0x5226A8` → `0x50C818` spin, counters reset, parity toggled; then GET_REPORT, flip, label-0x48 acquire (`0x522950`) | VERIFIED |
| other CALL sites | `0x50E5EC` (unmapped slot → CALL 0xFFFFFFFF, never seen), `0x4F72B4` (another system) | VERIFIED |

## 11.3 Instrumentation (Phase 3, disabled by default)

The changes are in `ps3recomp-t84`, branch `agent/t84d-pb-trace`, commit `9eae569` (+123/−5, 4 files). The patch is `t84d/patches/0001-…patch`, sha256 `f4b3f6a5…b8732a`. Nothing was merged or pushed.

- `GCM_CALL_TRACE=N@flip`:
  - each `[call]` line now also carries `head=` (the target's word 0 when the CALL was taken);
  - CALLs that are printed and empty are remembered, at most 64, with drops counted;
  - at each later flip they are re-read and reported as `[call-late] … written-after-call|unchanged`;
  - all of this only reads memory; walker state and guest memory are untouched.
- `t84d/pb_trace_t84d.cfg`: PT enter records for `0x50D868` (kind, list, count, view, slot, job, parity, done, bases), `0x757028`, `0x50C818`, `0x482680` and `0x5226A8`, plus the T72 race-entry controller sites.
- `t84d/tools/pb_report.py` joins batch → slot IO → `[call]`/`[call-late]` and reports these per (view, kind):
  - batches, entries;
  - calls, CALLs not seen;
  - draws, empty, no-draw;
  - late status;
  - a verdict.

## 11.4 Offline verification (Phase 4)

| gate | result |
|---|---|
| suite on `9eae569` (`t84d/tools/run_suite_t84d.cmd`) | 30 PASS, 11 SKIP (POSIX), 0 FAIL; identical per test to T84B. `test_d3d12_depth_state` run separately: PASS |
| `test_gcm_sync_trace` (C harness + 4 new hook checks) | PASS |
| `test_pb_report.py` | 13/13 PASS |
| TU `cellGcmSys.c` (T64C flags) | 0 errors; 685→699 diagnostics, all unsafe-buffer warnings in the header |
| `audit_public.py --staged` | the same 25 baseline BLOCK items as T84B, none in the changed files |
| tracing on/off parity | structural only: hooks read and never write, and are gated by env. Runtime parity not measured |

## 11.5 Build and pins

- `build/motorstorm-t84d-diag`: ps3recomp-t84 `9eae569`, otherwise the T64C configuration. 280/280 steps, rc=0, 0 FAILED (`t84d/logs/build_t84d.log`).
- Pin: `t84d/exe/MotorStormPacificRiftRecomp.exe`, sha256 `fb90538df09b28805b7206d3578a2b95e36b9ad9eb33856a918a8377f9b72db8`. It contains the `[call-late]` and `head=` strings.
- Existing exe pins under `generated/analysis` are unchanged (`t84d/logs/existing_pins_{before,after}.sha256`).
- `run_t84d.py prepare` copied the private HDD; `dryrun` passed preflight (`t84d/logs/dryrun_t84d.txt`). Nothing has been launched.

## 11.6 Smallest discriminating experiment (needs launch authorization)

**Run:** one bounded run, `python t84d/run_t84d.py launch`:
- the T84D exe;
- `PS3_TRACE_FILE=pb_trace_t84d.cfg`;
- `GCM_CALL_TRACE=20000@4700`, `GCM_SEMA_TRACE=4000@4840`;
- the T84C env (`VP_NOFIXPROJ=1`, fresh private HDD, `--timeout 210`, RSXI 3 race frames, no TEX_SAVE).

**Read:** `python t84d/tools/pb_report.py <run>/stderr.log`.

| view 0 result | meaning | next step |
|---|---|---|
| empty CALLs, `written-after-call` | host walker ran ahead of renderablejob (ordering) | host-side FIFO/job ordering |
| empty CALLs, `unchanged` | renderablejob produced no output for view 0 | SPU job input (entries, matrices, flags) |
| words but `no-draw` | job output without BEGIN_END | decode the slot methods |
| draws present | draws reach the backend | RSXI `call_ret` per pass / target |
| never CALLed | CALLs lost before the FIFO | context `[0x12C5CAC+4]` walking |

## 11.7 T84D runtime result (one launch, 2026-10-27, run `generated/runs/20261027-010225-t84d-pb-trace`)

Run: T84D exe `fb90538d…`, 184 s, stopped by the controller after the RSXI race capture (exit 2, the same stop as T84C); pins unchanged before launch. Report: `t84d/logs/pb_report_t84d.{txt,json}`.

**VERIFIED (runtime + static):**
- All 1925 `ExecutePushBuffer` calls (n=1..1925, none sampled out; t=158.6–184.2 s) were traced:

  | view | kind | batches | entries |
  |---|---|---|---|
  | 0 | 0 | 93 | 1627 |
  | 0 | 1 | 94 | 282 |
  | 0 | 2 | 328 | 3827 |
  | 0 | 4 | 376 | 7587 |
  | 1 | 5 | 282 | 3102 |
  | 2 | 5 | 376 | 11092 |
  | 3 | 5 | 376 | 11562 |

  Every batch had entries; the frame-end wait never started with jobs outstanding (4004 waits).
- **Every one of the 1925 `SetCallCommand` calls came from `0x50E5EC`** (`lr=0050E5F0`, `r4=0xFFFFFFFF`), none from the normal `0x50E0FC`. At `0x50E0C4..E8` the slot EA is looked up in the guest EA→IO table `[[0x1367100+0x34] + (EA>>20)*2]`. An entry > 0xFF means unmapped, so the code writes CALL `0xFFFFFFFF`.
- The output banks *are* IO-mapped: `MapMainMemory(0x17000000,0x300000)` → io `0x01A00000` and `(0x17400000)` → `0x01D00000` (stdout l.3177–3180). Only the HLE host tables get the entries (`populate_offset_table`).
- The guest copy of the tables is written only inside `cellGcmGetOffsetTable` (`gcm_publish_offset_tables`, `cellGcmSys.c:3139`). The game calls that once, from libgcm init `0x7368D8`, and caches the pointers at `0x1367100+0x34/+0x38`.
- The walker's CALL test is `(w&3)==2`, but `0xFFFFFFFF & 3 = 3`, so the word goes to "unknown word: skip" (`s_fifo_getoff += 4`, no log).

**Conclusion:** no renderablejob output is ever CALLed in this race, for any view. Earliest verified divergence: the guest-visible GCM offset table is stale (VERIFIED by the branch actually taken + HLE source), so all push-buffer CALLs are replaced by a word the walker silently skips.
- PARTIAL: that `GetOffsetTable` ran before these `MapMainMemory` calls is inferred from the stale lookup and the init call site; the call itself is not logged.
- Not measured: whether renderablejob wrote valid commands into the slots. It doesn't matter for this divergence, because the slots are never executed.

**Not observed (instrumentation gap, VERIFIED from source):**
- No `[call]`, `[call-late]` or `[sema]` lines appeared, in this run or in any earlier run.
- Push-buffer CALLs never reach the CALL hook (above).
- The `@flip` gates use `s_fifo_flips_reached`, which only advances on `GCM_FLIP_MARKER` (`0xFEAD01xx`) words.
- HYPOTHESIS: MotorStorm's flips don't advance it to 4700/4840, so even other CALLs and semaphores stay ungated.

**Consequences / hypotheses:**
- HYPOTHESIS: the draws seen for views 1–3 (rsx-hb `last_draws` 3 → 263) come from paths other than renderablejob push buffers. If so, view 0's black main pass and the views 1–3 output differ for reasons other than push-buffer ordering.
- The T84C "host walker runs ahead" hypothesis is moot: there is nothing to run ahead of.
- T85's F0 (the D3D12 projection fallback) remains a separate, competing explanation for whatever *is* drawn. Valid draws reaching the backend would not prove the push-buffer path responsible, and this result does not exclude F0 for the non-push-buffer draws.

**Smallest next check (offline first):**
- Make the guest offset table stay in step with the host tables. For example, publish on every `populate_offset_table` / `clear_offset_table`, as on hardware, where the table is live.
- Add a focused unit test: `GetOffsetTable` → `MapMainMemory` → guest `ioAddress[ea>>20]` == io>>20.
- Then one bounded run to see whether `0x50E0FC` is taken and whether view 0 draws appear.
- This is a framework behaviour change, so it needs separate authorization.

## 12. T84E: live guest GCM offset table (fix + isolated build; not launched)

Worktree `ps3recomp-t84e`, branch `agent/t84e-gcm-offset-table`, commit **`2dcf255009cefe3acf410bcf6f0ef485bd9f87f1`** on base `9eae569` (the T84D source, includes `8654a4d`). Not merged and not pushed. Patch: `t84e/patches/0001-GCM-keep-the-guest-offset-table-live-after-cellGcmGe.patch`.

### 12.1 Source change (`libs/video/cellGcmSys.c`, +40/−9; nothing else in the runtime)
- New `s_offset_tables_published`, set in `cellGcmGetOffsetTable` right after the existing `gcm_publish_offset_tables()`. The returned pointers are unchanged: they are still the fixed `inject+0x3000` (IO table, indexed by `ea>>20`) and `inject+0x5000` (EA table, indexed by `io>>20`).
- New `gcm_offset_table_mirror(ea_page, io_page)`: once the table has been published, it copies host `s_io_address_table[ea_page]` and `s_ea_address_table[io_page]` to the guest with `vm_write16`, as big-endian u16. Pages ≥ 4096 are skipped, so nothing is written past the 8 KB tables.
- `populate_offset_table` and `clear_offset_table` call it for every page they change. This covers `cellGcmMapMainMemory`, `cellGcmMapEaIoAddress(WithFlags)`, `cellGcmUnmapEaIoAddress`, `cellGcmUnmapIoAddress`, the Init window and the `cellGcm_syscall_iomap/iounmap` paths, because all of them go through these two helpers.
- `clear_offset_table` now rounds the page count up, `(size+0xFFFFF)>>20`, matching populate. Before, it truncated, so a size that is not a whole number of MB left its last page mapped.
- The four memset pairs in `cellGcmInit`/`cellGcmTerminate` are replaced by `gcm_offset_tables_wipe()`, which also writes `0xFFFF` to the guest table once it has been published.
- `0xFFFF` is still the invalid entry, which the title tests as `> 0xFF` at `0x50E0D8`. `ExecutePushBuffer` and all game code are untouched.

### 12.2 Offline results (VERIFIED)
- **New `tests/test_gcm_offset_table_live.c`** (runner `tools/test_gcm_offset_table_live.py`). It goes through the real `cellGcmSys.c` in MotorStorm's order: Init `(0x10000, 0x1A00000, 0x11200000)` → `GetOffsetTable` → `MapMainMemory(0x17000000)`/`(0x17400000)`, which returns io `0x01A00000`/`0x01D00000` → the *previously returned* table shows both directions → unmap → entries `0xFFFF`. It also checks:
  - byte-level big-endian entries;
  - that the title's own `lhz`/`>0xFF` lookup agrees with `cellGcmAddressToOffset`/`gcm_io2ea`;
  - boundaries at EA pages `0x16F/0x173/0x177` and the Init-window entries;
  - a snapshot of every unrelated entry;
  - `MapEaIoAddress`, remap reuse, and a `0x180000` iounmap that clears both pages;
  - IO page `0xFFF` with no overrun;
  - repeated `GetOffsetTable`, and Terminate followed by re-Init.
- Result: **PASS on `2dcf255`; FAIL on base `9eae569` (54 checks: the pools read `0xFFFF`)**, so the test reproduces the T84D defect.
- Renderer/RSX/GCM suite (`t84e/tools/run_suite_t84e.cmd ps3recomp-t84 ps3recomp-t84e` → `t84e/logs/suite_summary_t84e.txt`):

  | tree | PASS | SKIP | FAIL |
  |---|---|---|---|
  | base | 25 | 9 | 0 |
  | fix | 26 | 9 | 0 |

  The extra pass is the new test. The skips are the POSIX-only fixtures. `test_vp_fallback` and `test_gcm_sync_trace` PASS.
- POSIX GCM fixtures, linked on Windows with clang `-ffunction-sections -Wl,/OPT:REF -Wl,/FORCE:UNRESOLVED` (`t84e/logs/posix_fixtures/`): fix = base for io_alloc (PASS), flip_stream, get_on_jump, get_on_release, sync_trace (all rc 0).
  - `map_flags` asserts at `test_gcm_map_flags.c:29` on **both** trees (pre-existing).
  - `report_trace` needs arguments (rc 2 on both).
- TU compile with the T64C flags: exit 0 on both trees. Diagnostics 699 → 701; the two new ones are `-Wunsafe-buffer-usage` on the new array indexing (`t84e/logs/tu_warning_diff_t84e.txt`).
- Public audit `--staged`: same 25 pre-existing BLOCK items as the T84D baseline, none in the changed files (`t84e/logs/audit_staged_t84e.log`).

### 12.3 Isolated build and pin (VERIFIED)
- Configure `t84e/configure_t84e.cmd` uses the T64C cache options, with `-B build\motorstorm-t84e-fix` and `PS3RECOMP_DIR=…\ps3recomp-t84e`. Build `t84e/build_t84e.cmd` (`--parallel 6`) exited rc 0 with no `FAILED:` lines (`t84e/logs/build_t84e.log`).
- **Exe pin: `generated/analysis/t84/t84e/exe/MotorStormPacificRiftRecomp.exe`, SHA-256 `d18c51ef030312e5b92ba9784b158726a5ea1b5734fc05de31821a6272417cf5`**. It is identical to the build output (`t84e/logs/exe_t84e.sha256`).
- The 13 earlier pins are unchanged (`existing_pins_before/after.sha256`, with identical diff).
- Compared with the T84D build `motorstorm-t84d-diag`, after normalising the source paths: `ppu_hle_nids.cpp` (module/NID registrations), `hle_nid_sources.txt` and `CMakeCache.txt` are identical (`t84e/logs/registrations_t84d_vs_t84e.txt`).
- Only the T84E `cellGcmSys.c.obj` has `s_offset_tables_published` and `gcm_offset_table_mirror` (`t84e/logs/obj_fix_symbols.txt`).
- Camera behaviour is unchanged: `rsx_d3d12_backend.c` and `include/` are identical to `9eae569`, with the `8654a4d` fix and the `VP_NOFIXPROJ` switch.

### 12.4 Prepared bounded launch (NOT executed; needs authorization)
- `t84e/run_t84e.py` is cloned from T84D:
  - same race route, 210 s timeout, `pb_trace_t84e.cfg` (the T84D PT sites, including `0x757028` with lr/r4);
  - `VP_NOFIXPROJ=1` and `GCM_WORD_STATS=5`;
  - `GCM_CALL_TRACE`/`GCM_SEMA_TRACE` dropped.
- `prepare` is done (fresh hdd0 0 / hdd1 4 files, the same counts as T84D). `dryrun` passed the exe SHA check and launched nothing (`t84e/logs/dryrun_t84e.txt`).
- Launch: `py -3 t84e/run_t84e.py launch`.
- Check afterwards:
  - `py -3 -I t84e/tools/t84e_check.py <run> generated/runs/20261027-010225-t84d-pb-trace`, which was self-tested on the T84D run and reports "NOT restored", as expected;
  - plus `pb_report.py`.
- Pass criteria:
  1. `SetCallCommand` comes only from lr `0050E100` (`0x50E0FC`), with zero from `0050E5F0` (`0x50E5EC`);
  2. every normal-branch `r4` falls inside a logged `MapMainMemory`/`MapEaIoAddress` IO range;
  3. `[words]` reports `call>0`;
  4. there are no new FIFO-unmapped / resync / SPU / DMA / RSX / NOSYS / fatal lines compared with T84D;
  5. a race capture is taken, to look for nearby ground, objects and vehicles.

### 12.5 Status
- VERIFIED (offline): the guest table returned by `cellGcmGetOffsetTable` now follows every later map and unmap in both directions. This is the exact state in which T84D's lookup at `0x50E0C4` read `0xFFFF`.
- HYPOTHESIS, until the authorized run:
  - MotorStorm now takes `0x50E0FC` and the walker executes renderablejob CALLs;
  - those slots hold valid commands that complete before the frame-end spin;
  - view 0's near geometry appears.
- PARTIAL: T85's F0 (projection fallback) and the unmeasured slot contents are still separate risks.

### 12.6 T84E runtime result (the one authorized launch, 2026-10-27, run `generated/runs/20261027-064349-t84e-gcm-offset-fix`)

Run details:
- Preconditions checked: no MotorStorm process running; exe `d18c51ef…` hash verified; commit `2dcf255`; prepared HDD snapshot; `VP_NOFIXPROJ=1` and `GCM_WORD_STATS=5` set; `RSX_RT_READBACK` and `TEX_SAVE` not set.
- Launched once. The run ended at **152.2 s** with exit 2, `termination: stop_line` (**`Gc ERROR: GcKernel::Present() Timeout!`**, from the game's own GcKernel watchdog, stdout l.2589). This is before the RSXI race capture.
- Earlier pins are unchanged after the launch (`t84e/logs/existing_pins_postlaunch.sha256`).
- Logs: `t84e/logs/{launch_t84e.txt, check_t84e.txt, pb_report_t84e.{txt,json}, run_summary_t84e.md}`; runtime dir `t84e/runtime-20261027-064348/` (94 CELLMARK frames; `frame_093.png`).

**VERIFIED (runtime):**
- **The normal CALL branch `0x50E0FC` executes:** 79 of 79 `SetCallCommand` calls came from lr `0050E100`, and **none from `0x50E5EC`** (T84D: 1925 of 1925 from `0x50E5EC`).
- **CALL targets are mapped:** all 79 `r4` values lie inside the logged pool `0x01D00000+0x300000` (for example `01D00000`, `01D04000`, `01D08000`, …, 16 KiB slot stride), and the CALL words in the ring are `01D04002@00214E30`, `01D08002@00214E34`, `01D0C002@00221BD8`, `01D10002@00221BDC`.
- **The walker takes them:** its `[words]` window shows `call=5 ret=4` (T84D: 0). That window is at t≈147.5 s and reports `get=0x01D12660`, i.e. inside the 5th slot (`0x01D10000` + `0x2660`).
- **The SPU-built buffers carry RSX commands:** the walker returned from 4 slots and was 9.8 KB into the 5th. In that frame (flip 5748), D3D12 got draws it had never seen in T84D:
  - two `vertex_buffer_full` drops (prim 6, 256 indices, rt `0x07B78D80`; and a display draw), the first ever in these runs;
  - plus a `CLEAR_SURFACE`.
  
  Draw totals before the CALLs: `groups.draw=106397`, all recorded.
- **Error classes**, T84E / T84D: `fifo_unmapped_io`, resync, SEMA give-up, SPU, DMA, RSX error, NOSYS and fatal are all 0 / 0.
- **New failure:**
  - **No present after the CALLs start.** The last `[rsx-hb]` is at 146.4 s (emitted per present), and GcKernel reports "Last Reference Passed: 5749, Frame Present Counter: 5749" with `Gpu Get: offset 0x00010068` and kicked `0x11214180..0x112716e4`.
  - The main thread kept submitting batches (`0x50D868` n=79, up to t=152.18 s), so only 79 of the expected ~1900 batches ran.
  - Thread 28's exit (`0xBABE`) also happens in T84D, so it is normal.
- **No race frame was captured:** the last saved frame (`frame_093`) is still the "Festival – Race / LOADING" screen. **Whether near terrain, vehicles or scenery appear is therefore NOT determined**, neither positive nor negative.

**First verified downstream failure:**
- Within about 0.3 s of the first push-buffer CALL (147.89 s), the RSX stops completing frames. The walker was last seen inside CALL target slot 5 (`0x01D12660`), with no RET from it, and no flip or present follows.
- So the game's present watchdog fires about 4 s later.
- What the walker was doing at `0x01D12660` is **not observed**. The next `[words]` window (about 152.5 s) falls after the stop, and no park/resync/SEMA/bad-branch line was printed.

**HYPOTHESES (not tested; ranked):**
1. The walker reaches a slot before renderablejob has finished writing it. `0x50D868` emits the CALL before the SPU job runs; the only guard is the frame-end spin in `0x50C818`, which runs on the guest side, not on the host walker. A half-written slot (no RET yet, stale words, or a JUMP to an unfilled chunk) would stall or derail the walker. This is T84C's "walker runs ahead" hypothesis, which is now live again.
2. The walker is not stuck but very slow: the frame's geometry jumps (CPU-side vertex expansion overflowed its buffer), so the frame takes longer than GcKernel's 4 s timeout.
3. The slot contains an NV406E ACQUIRE on a label that nothing releases. Hardware would wait there as well.

**Smallest next discriminator (offline/instrumentation only; needs authorization):**
- At the stop, log the walker's current word, method and the next 8 words at its get (for example a one-shot dump on a GcKernel timeout or a `[words]` window of 1 s).
- Log the `rs+0x2560` completions against the CALLs consumed.
- This would decide between hypotheses 1–3 without changing behaviour.

### 12.7 Status after the run
- **VERIFIED:** the fix does what it should. The offset table is live, the normal CALL path executes, CALL targets are mapped and taken, and push-buffer commands reach the RSX/D3D12.
- **VERIFIED:** it also exposes the next defect. The RSX stalls inside the first push-buffer frame (no present after 147 s), so the race does not render at all in this build.
- **HYPOTHESIS:** walker/SPU ordering (1) is the most likely cause.
- **Not determined:** visual recovery of near geometry.

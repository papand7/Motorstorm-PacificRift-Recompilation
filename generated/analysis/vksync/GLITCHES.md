# Graphical glitches (2026-11-05, offline: the PC was in an RDP session, no launch possible)

User report: white/overexposed flashes, shimmer / soft image, water and camera shake, shadows or lighting wrong.

## White flashes: exposure target read before it is copied back (fix built, opt-in, not yet run)

- **Mechanism (VERIFIED in code and logs):** the auto-exposure (func_004C3778) reads a 16x16 FP16 target no
  draw samples; the engine copies it back to guest memory (`RSX_RT_READBACK`, `include/ps3emu/rt_readback.h`).
  A target is copied only after `min_orphan` (2) generations the GPU never sampled, then one present later
  (`RSX_RT_READBACK_ASYNC=1`). At race entry the target moves (Kk67: off 0x02903600 -> 0x07EBA600, first copy
  of the new one about 50 frames into the log window), so for its first frames the CPU reads memory the GPU
  never wrote. One bad sample drives the target to Emax and c33.x to 35.3 (T72/T75/T84): white until the
  game's exposure adapts back.
- **HYPOTHESIS:** this is the white race start (T194 Bb2, about 6 s) and the user's flashes.
- **Fix:** `RSX_RT_READBACK_EAGER=1` (off by default). A surface the GPU has not sampled since its identity
  began is copied from its first generation, synchronously while it is young (after finishing the queued
  async copies, to keep the GPU's write order); a surface the GPU samples falls back to the min_orphan rule.
  `ps3_rtrb_set_eager` / `ps3_rtrb_young` in the header, used in `rsx_draw_engine.c` (`eng_rtrb_present`).
  Edit scripts: `tools/edit_rtrb_eager.py`, `tools/edit_rtrb_eager_test.py`.
- **Tests (VERIFIED):** `tests/test_rt_readback.c`, 322 checks pass (`tools/build_rtrb_test.cmd`): parsing,
  the exposure chain (target selected from generation 1, young for 2; sampled level never; a target sampled
  once returns to the old rule), and the guest reading each frame's value from frame 1 on. Mutation (eager
  branch removed): fails. Engine regressions (`tools/build_res_scale_test.cmd`) unchanged; the
  RSX_RES_SCALE=1.5 shader-window run differs only in its 1x text, as before (RES_SCALE_1080P.md).
- Exe 544c6e86 (`.keep-544c6e86`; also has the SPU overlay entries of PERF_60FPS.md).
- **Next run:** Kk69 (Kk49's configuration, `RSX_RT_READBACK_EAGER=1`), stills over the first seconds of
  the race; the log's first `[rtrb] engine copy` of the new target should come at its first write.

## Shimmer / soft image

- Not a sampler bug (checked): the game's anisotropy (CONTROL0) and LOD bias reach the Vulkan samplers.
- The race drops to about 56 % resolution under 30 fps (dynamic resolution, viewportquality.xml), the main
  source of softness and shimmer. `MSPR_PATCH=drs` turns it off and has run in every race since Kk49.
- 2026-11-05, user approved: drs is the default (`port-vkgame/mspr_patch.h`, edit script
  `tools/edit_mspr_default.py`). Unset `MSPR_PATCH` gives drs and logs `[mspr-patch] on 0x04, by turns
  0x00 (default drs)`; any value replaces the list; `MSPR_PATCH=none` turns all off. Test
  `port-vkgame/tests/test_mspr_patch.c` (`tools/build_mspr_test.cmd`): 0 failures, the mutation
  (empty default) fails 2. Exe 2759935a (kept as `.keep-2759935a`), built from 544c6e86's tree plus this.
  The in-game default path is not yet run (PARTIAL: the patch itself is VERIFIED since Kk49). Queued as
  Kk85 (exe 20ba7377, `MSPR_PATCH` unset; `tools/add_arm_k81.py`): its log must show `(default drs)`.
  **VERIFIED in a race (Kk85, 2026-11-06):** `MSPR_PATCH` unset, log `[mspr-patch] on 0x04, by turns 0x00
  (default drs)`, race clean.
- `PS3_ANISO=16` (opt-in) sharpens distant ground further.

## Water / camera shake

- Seen with the 60 fps patches (`MSPR_PATCH=vfps`). The game ties these to its frame step. At the default
  30 fps lock they do not occur.
- 2026-11-05: the user asked for a fix (overriding the earlier simulation exclusion for this item). Static
  findings so far (decrypted EBOOT, RTTI vtables in `t132b/vtable_rtti.json`; helpers `tools/fdis.py`,
  `tools/vt_dump.py`, `tools/const_refs.py`, `tools/fixed_step_sites.py`):
  - Game timer (VERIFIED static): object fields +0x10 rate (60), +0x14 scale (1.0f), +0x18 vblanks per step
    (set to 2 at 0x18644/0x1FAAA8/0x346CB8/0x350790; the 60fps patch nops this store), +0x1C variable-step
    flag (the vfps patch forces it). Step period = interval * 1e6 / rate * scale (0x435B50).
  - Water: `BuoyancyAction` (applyAction 0x2F9DF0) and `WheelBuoyancyAction` (0x2F87C8) read the Havok step
    (`hkStepInfo.m_deltaTime`, +0x20) and keep it at this+0x28; their 0.98/0.99 constants are submersion
    thresholds, not per-step damping. The slowdown is not explained yet (HYPOTHESIS: per-step drag elsewhere).
  - Camera: `camerasystem::VehicleView` (0x431200) divides a delta by [ctx+0x10] and scales by 30;
    `XYZSplineSmooth` (0x432EB8) scales [ctx+0x10] by 1/30, so [ctx+0x10] is the step in 30 Hz frames.
    If the camera system sets it to a constant 1.0, the camera advances one 30 Hz frame per update at any
    frame rate (double speed at 60, jitter with vfps). Not yet known who writes it.
  - Fixed 1/30-per-call timers (VERIFIED static, minor): ViewObtainerCar blend 0x36B098 (0.8 s at 30 fps,
    0.4 s at 60), PhotoMode 0x36FA68/0x36FBE4, 0x3909E4, 0x416B10.
  - No fix is applied: which values are fixed per frame must be measured first (no blind physics edits).
- Measurement prepared (no rebuild; PT tracer reads only): `ab2/probe_fps.cfg` = route sites + the step
  values at the four functions above. Kk69 (30 fps, eager readback) and Kk70 (`MSPR_PATCH=drs,vfps`) load it;
  the runner keeps pending K arms launchable by tag (`K_BY_TAG`, `tools/add_k_by_tag.py`; Kk68 next, then
  Kk69, Kk70). Compare `[PT] ev=enter` values per function between the two runs; then patch only the sites
  whose step stays fixed, opt-in under the fps patches (default 30 fps unchanged).

- **Kk69/Kk70 measured (2026-11-05, `[PT] ev=enter` at 0x431200 and 0x2F9DF0):**
  - Kk69, default 30 fps lock: camera `[r5+0x10]` = 30.0 in all 1,747 calls, Havok step 1/30 in all 3,000.
    Camera and physics agree. But the gaps between camera calls (= frames) were 33 ms 58 %, 41 ms 31 %,
    49-91 ms 11 %: every frame advances the game 1/30 s, shown for an uneven 33-58 ms.
    **HYPOTHESIS:** this uneven pacing is the user's "camera shakes in normal driving" (2026-11-05 report);
    it goes away when every race frame fits in 33 ms (the performance work, PERF_60FPS.md).
  - Kk70, `vfps`: camera `[r5+0x10]` = 25.0 in all 1,864 calls (constant), while the Havok step varies
    0.034-0.040 s. Camera and physics disagree each frame: the vfps shake. Fix candidate: the writer of
    `[ctx+0x10]` should follow the step (1/dt), opt-in under vfps.

## Shadows / lighting

- Nothing found in the stills (Kk64-Kk67, one spot) or the logs. Needs a picture or a place in the race.
- **Shadow edges crawl while driving (user, 2026-11-05; VERIFIED cause, Kk78):** exe f72c31ab (base + the
  opt-in `RSX_SHADOW_CAP`, `ps3recomp-vkgame/libs/video/rsx_shadow_cap.h`, test `tests/test_shadow_cap.c`
  19 checks, a mutation fails 4), arm `tools/add_arm_k78.py`, capture `ab2/shadowcap_k78.bin` (private),
  read by `tools/shadow_cap.py`.
  - The game draws 3 cascades into the 1024x2048 atlas 0x0B030000 (tiles 1024x704, 1024x672, 1024x672),
    world-to-clip matrix in c0-c3 (columns), light view in c4-c7. The light view stays fixed (max 0.04 deg).
  - The game re-fits every cascade to the camera: in 66 updates over 443 frames the cascade's in-plane axes
    turned a median 1.2 deg (max 43 deg), its extent changed a median 1.0-1.4 % (max 42 %), and its offset
    moved by fractions of a texel (median sub-texel part 0.21-0.24; random is 0.25). So the shadow-map grid
    turns, resizes and slides under the world: edges crawl. It is the game's own math (it runs unchanged
    here), so the PS3 does the same (HYPOTHESIS: no PS3 capture).
  - Texel size now: cascade 0 0.08 x 0.06 world units, cascade 1 0.18 x 0.10, cascade 2 0.60 x 0.39.
  - Fix candidate (opt-in): fixed orientation and size per cascade and the offset snapped to whole texels,
    applied to the shadow pass and the scene's lookup alike. It costs some resolution (a fixed square must
    hold the turned box).
  - Kk78 ran at 52-56 ms frames: two BF1943 processes and Nightfire open (present wait 21 ms a frame).
- **Fix built, opt-in `RSX_SHADOW_STABLE=1` (2026-11-06; exe ec5ce88e = 20ba7377 + this, `.keep-ec5ce88e`; not yet run):**
  - VERIFIED from the Kk78 capture (`tools/shadow_lookup_scan.py`, test replay): each cascade's c0-c3 is
    S_i x L exactly (row directions equal the scene's light view in c4-c7, cos 1.000000); all 71 atlas readers
    in passdump_k79 read L from c4-c7; they look the cascade up in a 4x1 W16Z16Y16X16_FLOAT texture (unit 10,
    double-buffered 0x0077B380/0x0077B400): uv = (L.xy p) * lut.xy + lut.zw. The 4th entry is all zero.
  - The lookup is half precision while the shadow pass is float: the game's own scene lookup and its shadow
    map already disagree by up to about one texel, varying per update.
  - `libs/video/rsx_shadow_stable.h` + glue in `rsx_draw_engine.c` (after the per-draw vertex-constant copy):
    cascade draws get fixed axes across the light (frozen basis), a size that holds the game's box at any turn
    (its half-diagonal; ladder (1, 1.25, 1.5, 1.75) x 2^e, hysteresis 1.6) and offsets on a 2^-10 uv grid;
    readers get the matching c4-c7 rows 0/1 (origin on a 16-unit grid) and a host copy of the lookup whose
    values are all exact halves, so both sides agree to the bit. Atlas learnt from the first reader; a draw
    that does not fit (non-ortho matrix, other light view, unmatched entry) is left alone and counted in the
    `[shadow-stable]` line every 600 frames.
  - Cost: resolution. Cascade 0's y texel about 2.7x coarser than the game's best fit (a square that holds the
    61 x 25-unit box at any turn); x about the same.
  - Test (VERIFIED): `tests/test_shadow_stable.c` (`tools/build_shadow_stable_test.cmd`), 31 checks pass.
    Synthetic: box inside the tile (max 0.94), shadow pass vs reader 3.5e-4 texel, whole-texel moves (1.4e-4).
    Kk78 replay: 442/442 reader frames match, 1326 lookup entries matched, viewport-derived uv reproduces the
    game's lookup to 5.8e-7 uv, all rebuilt entries exact, frame-to-frame phase 1.5e-4 texel (game: median
    0.21-0.24), 8 size steps in 443 frames (13 at hysteresis 1.3, 2 at 2.0). Mutations: no snap fails 5,
    shadow-pass offset off by 0.002 fails 1.
  - **Next run:** Kk86 (`tools/add_arm_k86.py`): Kk71's configuration + the fix + `RSX_SHADOW_CAP` from 20 s
    (menu garage and race). Check the `[shadow-stable]` counts (readers skipped/failed should be 0), the
    capture with `tools/shadow_cap.py` (fixed axes, sub-texel part 0), and stills against Kk78.
  - **Kk86 result (2026-11-06), PARTIAL:** `[shadow-stable]` by frame 4004: 1,297,293 cascade draws, 1,336,890
    readers, 0 skipped, 87 lookup textures, 0 failed, 0 basis refreezes, 22 size steps. `shadow_cap.py` on
    `ab2/shadowcap_k86.bin` (1189 race frames), cascade block c0 per section: axes change 8/10/7 times (only at
    size steps; Kk78: 66 in 442 frames), and the 154/147/146 moves with fixed axes are whole texels (median
    sub-texel part 0.014/0.008/0.004; Kk78 has no fixed-axis moves at all). Race ran clean (frame p50 46 ms
    with the capture writing; Kk78 with its capture 54 ms).
    - **Open:** about 19 draws a frame read the atlas without the lookup texture (`atlas reads without lookup`
      11,365 by frame 4004). Those keep the game's own projection while the atlas is now drawn with ours, so
      their shadows may be misplaced. Identified in Kk87/Kk88, fixed in Kk89 (below).
    - **Not checked:** no stills were taken in Kk86 (no pass dump or snip in the arm), so the visual result
      against Kk78 is unseen.
  - **Atlas reads without the lookup (Kk87/Kk88, VERIFIED):** 7 fragment programs. 5 are dust/smoke into the
    640x360 target 0x0B830000 (fp 0x0B02DAC0, 0x0BD28880, 0x0B02E1C0, 0x0BDD2280, 0x0B02F800); 2 draw into the
    scene target 0x00750000 (fp 0x02B9EF80, 0x03D37040). Their vertex program computes the shadow coordinate
    itself: c4-c7 = light view L (as the lookup readers), c(45+i).xy = cascade i scale (U,V), c(49+i).xy =
    cascade i offset. Found with `RSX_SHADOW_STABLE_DUMP=<dir>` (Kk88, `ab2/sstdump_k88`) and
    `tools/sst_nolut_find.py`; every dump with tiles fits. 0x02B9EF80's only dump came before the race (0 tiles).
  - **Kk89 (exe 6af3aca9, `tools/add_arm_k89.py`), PARTIAL:** `eng_sst_vs_reader` rewrites those constants
    like the lookup readers. By frame 3390: 454,418 cascade draws, 647,300 readers (0 skipped), atlas reads
    without lookup 6,176 (rewritten 6,175, skipped 0). Two snips 20 s apart on the start grid
    (chat-pictures 1154c70f…, 3c9976eb…): palm shadows identical, no crawl at rest. Final (frame 4590):
    1,402,754 cascade draws, 2,345,563 readers (0 skipped), 13,665 without lookup (13,664 rewritten, 0
    skipped), 71 lookup textures (0 failed), 16 size steps. Exit as Kk86 (controller stop). NightFire was
    running during the race, so CPU numbers are not comparable. Moving race not yet judged by eye.

## Dust / smoke

- **Dust seen through the ground, from the vehicles (user, 2026-11-05):** the dust and smoke are drawn at
  quarter size (640x360, target 0x0B830000) and depth-tested (no depth write) against a small depth buffer
  0x0B920000. The pass's first draw fills it from the main depth 0x00ED0000 read as A8R8G8B8 (the dynamic
  resolution window, e.g. 1614x454). In the one dumped race frame (`ab2/passdump_m2` pass 037) that small
  depth matches the scene and the quad hides the dust behind it. A failing frame has not been captured.

- Kk79 (exe 37f18d28, `RSX_ENGINE_PASS_DUMP_ALPHA=1`, `ab2/passdump_k79`, run `generated/runs/20261105-221747-vk-Kk79`):
  the quarter-res dust buffer (pass 311, 0x0B830000) has clean alpha (no colour where alpha is 0, soft
  edges; colour blend 302/303, alpha 305/1 = coverage) and the composite (pipe 86) adds it as
  premultiplied "over". The hard-edged rectangles seen near the dust come from a different pass:
  pass 314, 32 full-res decal draws (pipe 146) that rebuild the ground position from the depth buffer
  read as A8R8G8B8, project it into a 16x16 B8 blob texture and blend alpha = c5.x - tex.z. They darken the
  ground by flat amounts (-7..-56 levels) that stop at hard box edges (VERIFIED, pass 310 vs 314 diff;
  e.g. present x 955). HYPOTHESIS: the blob unit wraps as BORDER with a white border colour, and the
  Vulkan engine sampler always used transparent black (tex.z = 0 outside the blob, full darkening to the
  box faces). Opt-in `RSX_TEX_BORDER=1` (exe 20ba7377, `rsx_tex_border.h`, test_tex_border 12/12) takes
  the guest's border colour; arm Kk80 checks it (log lines `[rsx engine] texture border colour`, and
  draws.txt now lists each texture's wrap/border words).

- **Camera shake fix built (2026-11-06, exe 340341ea, `tools/cam_patch_lifted.py` + `port-vkgame/main.cpp` MSPR_CAM):**
  - VERIFIED writers (Kk114, PPU_WVAL=0x41C80000): the camera rate [ctx+0x10] is copied every frame at
    0x003764F0 (from [obj+0xA58]) and 0x004295D0 (from [obj+0x3DC]); it is 25.0 under vfps, 30 at the lock.
  - Fix 1 (default on under vfps, `MSPR_CAM=0` off): the copies store 1/(world dt), noted at World::Update's
    clamp (fsel 0x002161C8, func_00216004/func_00216008). Kk115 log: `camera rate 25 -> 31.88 (world dt 0.031)`.
  - camerasystem::Shake (0x42E3F0) is active on every race update (Kk117); its offset grows with speed
    (Kk121: mean 0.0016 -> 0.005, max 0.02 world units). Fix 2: `MSPR_CAM_SHAKE=<0..1>` blends its two result
    stores (0x42EB54/5C, 0x42F330/40); default 0.3, 1 = the game's, 0 = skipped at entry.
  - Not yet confirmed by eye (the auto-driven runs are slow and short; a frame-jitter metric from the camera
    matrices was too scene-dependent to decide).

## Vehicle looks lower frame rate than camera/scene at 60 fps (2026-11-22, generated/analysis/vehfps)

- User report: at 60 fps (vfps, MSPR_CAM_MODE=1) the player's vehicle looks like it runs at a lower frame rate
  than the camera and scene; 30 fps fine. Logs: launcher/dev/MotorStorm/play/game_60fps.log (mode 1, shake x1)
  vs game_30fps.log (mode 0, shake x0.3).
- Instrumentation (env-gated, off by default): `RSX_VEHLOG=<skip>[:<max>]` in rsx_draw_engine.c (per frame:
  camera eye from c0-c3, world position + screen NDC of the nearest drawn objects, from the first rigid matrix
  the vertex program reads above c7 -- the vehicle is c256), `MSPR_DT_LOG=<n>` in main.cpp (world dt per step).
  Private exes linked from the ppucc2 objects with tools/shadow_link.py (build/vehfps-link/{diag,fix}).
  Arms Kveh60 (vfps, reached only ~35 fps on the loaded PC), Kveh60f/f2/fs/fx/fx2 (60fps lock = world dt 1/60
  every frame, the same frame-to-frame relation as real 60), throttle-only via vehfps/tools/drive_veh.py.
  Reports: vehfps/tools/vehlog_report.py, offset_jitter.py, ndc_jitter.py, ndc_pattern.py.
- VERIFIED: the guest's vehicle transform is NOT stepped at 30 Hz: at dt 1/60 the vehicle and the camera eye
  advance together on every frame (Kveh60f: |dT|/|dE| median 1.001, 0 of 938 frames with a still vehicle,
  lag-1 correlation of the eye-relative offset step 0.994).
- VERIFIED cause: the MSPR_CAM_MODE=1 shake hold. The shake is a camera-position offset; held for 2 frames and
  renewed at 30 Hz, it moves the near vehicle on screen in 2-frame steps while the far scene hardly moves.
  Vehicle screen-position second difference (NDC): shake off (Kveh60fs, MSPR_CAM_SHAKE=0) median 0.00012,
  x lag-1/lag-2 autocorrelation -0.00/-0.07; shake held x1 (Kveh60f2, same vehicle) median 0.00105 (~0.7 px,
  p99 ~4.5 px at 1280), autocorrelation -0.60/+0.37 = a 30 Hz step pattern.
- Fix (port-vkgame/main.cpp, `MSPR_CAM_SHAKE_SMOOTH`, default on, only while the mode-1 hold is active; `=0`
  restores the stepped hold): the applied offset walks linearly from the previous 30 Hz offset to the newest by
  world time since renewal. Kveh60fx/fx2 (exe fbb601fa): x autocorrelation -0.00/+0.00 and -0.01/-0.03 (pattern
  gone). PARTIAL: those runs drew other vehicles, so the amplitude is not matched (median 0.00101 / 0.00065).
- HYPOTHESIS: the remaining wobble is the game's full-strength shake (mode 1 uses x1, the 30 fps setting x0.3);
  MSPR_CAM_SHAKE=0.3 would match the 30 fps look. FSR 3.1 not tested (on in all arms).
- Needs an eye check at real 60 fps.

## Dark translucent boxes around vehicles (2026-11-22, Kbox1..Kbox12, ab2/passdump_box*)

- VERIFIED not FSR / res scale: pass dumps (engine render targets, before any upscale) show the boxes; Kbox11 (RSX_FSR off,
  RSX_RES_SCALE off) still shows them (they even darken a rock wall seen through the box silhouette). RSX_GPU_REINTERP=0
  (depth read through guest memory, Kbox6) shows the same boxes, so the depth-as-ARGB8 snapshot is not the cause.
- VERIFIED draws: the full-res pass after the scene (stencil 1, no depth write), 14-16 draws of one pipeline per frame
  (pipe 612/782 by run): t0 = scene depth read as A8R8G8B8, t1 = a 16x16 swizzled B8 map per vehicle (3 distinct maps,
  e.g. 0x08CEE380, 0x0944A600, 0x0826CC00), blend SRC_ALPHA/1-SRC_ALPHA, fragment alpha = c5.x(=1) - map.z. State
  (draws.txt now logs `df cull ff st`): depth GREATER, cull FRONT (back faces of a box), stencil NOTEQUAL ref 3,5,7.. (per
  vehicle), wrap 0x30303 = CLAMP_TO_EDGE (so RSX_TEX_BORDER never mattered). Diff pass N vs N+1 = hard-edged rectangles.
- The map is white (~0xFE) on the top/left but dark (down to 0x9E) along its right/bottom edges. Pixels whose rebuilt point
  is outside the map (geometry nearer than the box, seen through its silhouette) clamp to that dark edge: flat darkening
  over the whole silhouette. HYPOTHESIS (not checked against a PS3 capture): the original gives no darkening there.
- Fix (default on, `RSX_DECAL_EDGE=0` restores old behaviour): rsx_draw_engine.c uses BORDER + opaque white for a 16x16 B8
  unit with S/T CLAMP_TO_EDGE (predicate `rsx_decal_edge_unit`, rsx_decal_edge.h, tests/test_decal_edge.c 6/6).
  Kbox12 pass dump: rectangles gone, tyre-track decals and the in-map blob stay. Exe (private, includes the main session's
  uncommitted engine edits at 16:14): build/boxfix-link/fix, sha256 9b8109a9...71ba.
- Tools: RSX_DBG_B8=<n> logs the 16x16 B8 guest bytes and fragment constants; runner `vehfps/tools/runarm.sh <tag>`
  (RUN_VK_ANY_ORDER=1 bypasses the ORDER check in run_vk.py).
- 60 fps shake/shadow flicker: nothing found in these captures (single frames only; not investigated).

## Foliage / shadow jitter, lag and "low fps" report (2026-11-22, static analysis only, generated/analysis/shadowlag)

- No game was launched (launch queue is the main session's). Only existing private captures were re-read.
- VERIFIED (shadowlag/cadence.py on ab2/shadowcap_k78/k86/k121.bin, atlas 0x0B030000, cascade c0-c7 vertex constants of
  the depth-only shadow section, one sample per presented frame): the cascade fit does NOT update every frame and NOT on a
  fixed 4-frame tick. Gaps between changes (frames): k78 (no fix, 443 fr) 1:62 2:39 3:16 4:7 5:3 6-15:4 (mean ~2.4);
  k86 (SHADOW_STABLE, 1189 fr) 1:88 2:17 3:22 4:13 5:7 6:5 7+:~10; k121 (156 fr) 1:24 2:3 3:13 4:7 5-17:~9.
  So the shadow box is re-fit at irregular 1-8 frame intervals (game's own PPU logic, runs unchanged; HYPOTHESIS
  trigger = camera-motion/time threshold, not located). Atlas content between refits still redraws each frame
  (casters move), but the projection steps: with moving camera the grid snaps/slides, which reads as shadows "lagging" and
  stepping. Whether the lag is the game's: HYPOTHESIS yes (same math as PS3); our renderer adding a frame of delay is NOT
  excluded and NOT measured (needs RSX_TEX_SNAPSHOT/ZSNAP_ON_WRITE/VTX_* off arms, below).
- NOT MEASURED: foliage vertex-stream / wind constants cadence (needs RSX_VEHLOG-style constant log keyed by foliage vp hash).
- Proposed arms (to append at END of ORDER via K_BY_TAG, not yet added): static-camera, 300 frames, log per frame
  (a) hash of foliage-draw vertex constants + vertex buffer, (b) atlas hash; A = defaults, B = RSX_TEX_SNAPSHOT=0
  RSX_ZSNAP_ON_WRITE=0 RSX_VTX_GPU=0 RSX_SRV_REUSE=0 RSX_BIND_DEDUP=0 RSX_VK_LAZY_SYNC=0. If A and B agree -> game's own.
- No fix implemented (nothing safe to ship without the foliage measurement).

### Follow-up: RSX_FOLDUMP and arms Kfol_a / Kfol_b (2026-11-22, shadowlag)
- Built (opt-in, off by default): `RSX_FOLDUMP=<file>[:<frames>]` + `RSX_FOLDUMP_AFTER=<s since first draw>` in rsx_draw_engine.c
  (`eng_fd_draw`, called next to the RSX_VEHLOG hook): 56-byte record per draw (frame, zeta, pipeline, draw size, draw key, hash of the
  vertex constants the program reads above c7, hash of c0-c7, hash of the attribute-0 stream <= 256 KB). Reads only.
  Atlas records are the caster pass (zeta 0x0B030000); a hash of the atlas pixels is NOT taken (proxy = caster draw hashes).
- Private exe: build/shadowlag-link/fol/MotorStormPacificRiftRecomp.exe (ppucc2 objects + this file), sha256 bf51172d...3bf0,
  slot `sl` (ab2/exe_sl, exe_sl.sha256). Arms at the end of ORDER before Yy1: Kfol_a (defaults), Kfol_b (RSX_TEX_SNAPSHOT=0
  RSX_ZSNAP_ON_WRITE=0 RSX_VTX_GPU=0 RSX_SRV_REUSE=0 RSX_BIND_DEDUP=0 RSX_VK_LAZY_SYNC=0). No driver: the car waits on the grid.
  Several of those switches are D3D12-only or default off (SRV_REUSE, BIND_DEDUP: d3d12 backend; ZSNAP_ON_WRITE default 0); the
  ones that matter on Vulkan are VTX_GPU and LAZY_SYNC.
- Analysis: `py -3 generated/analysis/shadowlag/foldump_report.py ab2/foldump_a.bin` (share of draws whose constants/vertex data change
  between consecutive frames with an unchanged camera, per pipeline). Compare a vs b.
- Cascade slew NOT implemented: with RSX_SHADOW_STABLE the box offsets are whole texels, so refits move the box without moving
  the shadow content; smoothing the offset would reintroduce sub-texel crawl. Decide after the dump shows what actually steps.

## "Lighting waaay too bright / bloom turned up" (2026-11-22, generated/analysis/bright; no game launched)

- No PS3/RPCS3 reference frame exists (rpcs3cmp holds only thread timings; no RPCS3 captures). So "brighter than the real
  game" is NOT verified either way; below is what the pipeline does, from pass dumps box1/box10-12 and shots lt0.
- VERIFIED (decoded pipes of passdump_box1): scene programs write MRT0 = sRGB(colour x c33.x) and MRT1 = sRGB(colour x
  c33.x / 16) (RSX sRGB packer, both targets); luminance pass fp_0074B181 = t2 + 16(1-t2.a) avg4(MRT1)^2; exposure pass
  fp_0074C781 inline constants: G = sqrt(L), R = max(1 + 0.7(0.3/clamp(G, 0.006, 3) - 1), 0.1); the CPU (func_004C3778)
  reads G at texels (2,11)(5,10)(8,4)(10,10)+1, t = clamp(0.3/geo(G), 0.1, 50), rises at 0.07/frame, falls at 0.026/frame,
  c33.x = 1 + 0.7(t - 1). Bloom (fp 0x0074C340) = max(L - 8, 0) only, alpha = vignette 1 - saturate(r-0.5)^2; final
  composite (scene + bloom) x vignette, saturation 1, tint 1, 10% smoothstep contrast. No bloom/tonemap strength knob.
- VERIFIED: box12 race frame: bloom target 80x45 RGB = 0 (nothing above 8), so bloom adds nothing there; scene Y 0.53
  before post, 0.41 after (vignette/contrast). Exposure texels G at the CPU points 0.27-1.0 in box1/2/6/10/11/12, i.e.
  t = 0.3-0.5 and c33.x ~0.5-0.65 expected: the loop has headroom only down to c33.x = 0.37, so bright beach shots stay
  bright by design (the 0.7 strength). lt0 (FSR off, HDR arm): mean Y rises 0.23 -> 0.61, 16.9 % clipped, over 40 frames
  when the camera turns from rock to sand, then falls slowly (0.613 -> 0.569 in 15 frames): the game's asymmetric adaptation.
- VERIFIED not the cause: Windows HDR is OFF on the user's monitor; SDR swapchain is B8G8R8A8_UNORM (no double gamma);
  FSR 3.1 is fed and writes R8G8B8A8_UNORM with FFX_UPSCALE_FLAG_NON_LINEAR_COLOR_SRGB, at present after all post;
  lt0 without any FSR is as bright. RSX_SHOTS are taken before the upscaler (render-size frame), so shots cannot show FSR.
- HYPOTHESIS (to test): (a) exposure noise rectified by the asymmetric IIR: any momentarily low/stale/zero G sample
  (async/eager readback, MRT1 holes) lifts c33.x fast and it decays ~40 frames -> net over-exposure and white flashes;
  (b) scene inputs brighter than PS3 (vertex colour AO col0, shadow lookups, c10/c11 sun/ambient) -- the loop cannot
  compensate below 0.37.
- Diagnostic (off by default): `RSX_CONST_WATCH=<slot>[:<every flips>[:<max>]]` in ps3recomp-vkgame rsx_dispatch.c
  (engine path; the old RSX_VPC_WATCH in rsx_commands.c does not run under the engine): last value + x min/max per window.
  Exe build/bright-link/diag (ppucc2 objects + rsx_dispatch.c only), sha256 78997e1b...5d8b, slot `br` (ab2/exe_br, hardlink).
- Arms (visual-only, before Klt5t): Kbr1 launcher-like (FSR 3.1 balanced, 1.5x, HDR 0, 30 fps, no pack) + c33 log +
  shots + pass dump at 75 s; Kbr2 = Kbr1 with RSX_RT_READBACK_ASYNC=0; Kbr3 = RSX_RT_READBACK_EAGER=0.
  Run: `bash generated/analysis/vehfps/tools/runarm.sh br1` (br2, br3); report: `py -3 generated/analysis/bright/tools/br_report.py`.
  Decision: c33.x median 0.4-0.7 with no spikes -> exposure fine, look at scene inputs (b); spikes or median >= 1 in
  sunlit race -> (a), fix in the readback path (RSX_RT_READBACK_* arm that removes them).
- No fix implemented: cause not established. Needed for VERIFIED: an RPCS3 or PS3 capture of the same track/time.
- Kbr1-3 (exe diag, slot br) gave no data: only the `[const-watch]` init line. VERIFIED cause: the watch's windows were closed by
  the GCM flip methods 0xE920/0xE944 in rsx_dispatch_method, but under the draw engine the flip is a driver call
  (rsx_draw_engine_note_flip/present_buffer), never a FIFO method, so no window ever printed. Constant uploads do reach the
  engine (cellGcmSys fast path and walker both call rsx_draw_engine_method). Fix: windows now close on the slot's x-lane
  uploads after `<ms>` of wall time (`RSX_CONST_WATCH=33:500`); offline check (rsx_dispatch.c + a driver, no game) prints
  lines and br_report.py parses them. New exe build/bright-link/diag2 sha256 2b3e9164...c4ab, slot `brb`; arms Kbr4-6 =
  Kbr1-3 configuration on it, queued before Klt5t. Caveat: other programs may upload c33 for other uses; min/max then mixes.
- Kbr4-6 (exe diag2): c33.x median/spike windows: Kbr4 async+eager (+pass dump) 0.817 / 31.8 % (max 6.9);
  Kbr5 ASYNC=0 0.558 / 4.1 %; Kbr6 async, eager off 0.582 / 7.5 % (max 13.9). In Kbr4 c33 climbs smoothly for seconds
  (0.56 -> 3.2 in ~4 s, 30 uploads/s, one value per frame): the CPU kept reading G ~0.1, i.e. luminance ~100x too
  low, for seconds -- not one-frame noise. The sampled async copies (every 256th) were all "applied, conflicts 0,
  lag 1" and even the GPU's own texel (0,0) G was low (0.07-0.34 vs 0.67-1.2 in Kbr5). Root cause NOT established
  (HYPOTHESIS: copies left pending keep the CAS shadow from being retaken -- legacy only snapshots with no copy in
  flight; or GPU/CPU frame overlap the per-present wait hides).
- Fix candidate (ps3recomp-vkgame rsx_draw_engine.c, uncommitted; tests test_rtrb_async_ring.c new, test_rtrb_async_engine.c
  pinned to legacy, test_rsx_draw_engine.c all pass offline): RSX_RT_READBACK_ASYNC=1 now runs a bounded ring --
  RSX_RT_READBACK_MAX_LAG=<n> (default 1): copies queued n+ presents ago are finished and applied before new ones are
  queued (whole target from one frame, <= n frames old, shadow retaken every frame; waits only when the GPU is more
  than n frames behind); NaN/Inf copies and all-zero-after-non-zero copies are dropped, the previous copy stays (max 3
  in a row). Opt-out RSX_RT_READBACK_ASYNC_MODE=legacy. Diagnostic RSX_RT_READBACK_TRACE=<off hex>: one line per copy
  (frame, result, lag, G at the 4 CPU texels, rejected/waited counts).
  Exe build/bright-link/ring1 (rsx_dispatch.c + rsx_draw_engine.c over ppucc2 objects; includes other agents'
  uncommitted rsx_draw_engine.c edits), sha256 c8c91d71...3ff8, slot `rg`. Arms Kbr7 (ring, lag 1), Kbr8 (ASYNC=0),
  Kbr9 (legacy, diagnostic), all with trace of 0x07EBA600, before Klt5t. Pass: Kbr7 spikes ~4 % and median ~0.56 like
  Kbr8, frame-hist p90 near Kbr9's.

## In-cockpit camera, opt-in (2026-11-22, generated/analysis/cockpit)

- User request: an extra view from inside the cockpit (steering wheel visible). The other "project with interior" was not
  found: ms2006/, Desktop/motorstorm(2006) (only the 7z) and TDU (zips) have no cockpit/first-person camera code or notes.
- VERIFIED (static, 1.00): per-vehicle camera lists `/data/camera_config_files/<veh>_cams.txt` in MS2.PSARC (111 files):
  `CAMERA 1 CHASECAM <file>` (chase) and `CAMERA 2 FIXED_*` (cars) / `STABLE_*` (bikes, ATVs) = the "Bonnet fixed cam"
  (comment in the files), FORWARD/LEFT/RIGHT/REAR look directions. No CAMERA 3 anywhere. Loader 0x00373FD8 opens
  `data/camera_config_files/%s_cams.txt` (string 0x00E1C810) first; line parser 0x0037D640 accepts CAMERA 1..9, slot =
  base+372+group*480+n*48, group-0 count (0x924) = highest n (0x00374A34); SELECT cycle 0x00371948 walks 0..count-1.
- VERIFIED (static): car models carry interior meshes (`gen_interior_detail(_LOD1)`, `Cockpit_dials.dds` in buggy01,
  bigrig01, monster21, mudplugger01 LV01); bikes/ATVs have `handlebars(_LOD1)`. No seat/driver locator name in the
  vehicle rpk (BONNET/DOOR_*/WING_* are damage panels). Whether the steering wheel is a separate mesh: not determined.
- Implemented (opt-in): `MSPR_CAM_COCKPIT=1` (port-vkgame/main.cpp mspr_cam_cockpit_init) renames the list to `%s_camz.txt`
  in guest memory, only if `$PS3_VFS_OVERLAY/data/camera_config_files/buggy01_camz.txt` exists; the overlay is written by
  `py -3 -I generated/analysis/cockpit/tools/make_cockpit_overlay.py --out <overlay>` (original text + CAMERA 3 at an
  estimated driver's eye relative to CAMERA 2; `--car dy,dz,dpitch,focal`, `--bike ...`, `--x` to tune, no rebuild).
  Overlay: generated/analysis/cockpit/overlay (private, game-derived). Exe: build/cockpit-link (shadow_link.py, ppucc2
  objects + current main.cpp + rsx_draw_engine.c), sha256 2418c706ab6d840fa06fade9289b181659e616972f5473139834ce2490ef1265,
  staged ab2/exe_ck. Arm Kck1 (before Klt5t), visual only.
- HYPOTHESIS until Kck1: the game's file layer reads `*_camz.txt` from the overlay (as for gui/optionz.gui), the third
  camera joins the SELECT cycle, the rider mesh does not block the view, eye positions are right. Log line to look for:
  `[cam-cockpit] on` and `[vfs-overlay] ...camera_config_files/<veh>_camz.txt`.

## Far vehicles through terrain / far objects white (2026-11-22, generated/analysis/fardist; no game launched)

- The earlier agent on this issue left nothing in this file (nothing under analysis/distance about it either).
- VERIFIED (launcher play/settings.ini 19:38 + game.log 20:10): the user's session runs `lod = Ultra` -> MSPR_LOD_BIAS -2 and
  MSPR_CULL_SCALE 0.25 on EVERY viewportquality group, including vehicle (lodBias 0 -> -2, cullThreshold 0.015 -> 0.00375)
  and player (-2.5 -> -4.5). Groups are stored in the order object, dyn, world, vehicle, player (the [mspr-dist] lines).
  `textures = Off`, `pbr = Off`: the HD pack is NOT loaded, so (e) pack/PBR substitution is excluded for this session.
- VERIFIED: every existing capture (Kbox*, Klt*, Kbr*) ran at LOD Original (no MSPR_LOD_BIAS/CULL_SCALE). In them far ships are
  correct: lt17o intro shots (pack on) and the box12 race-start pass dump (pass 004, before FSR); no vehicle shows through
  terrain. So the report is not reproduced at LOD Original.
- VERIFIED (box12 / box1 dumps): scene pass depth LEQUAL, depth write on, D32_SFLOAT_S8 host depth, scene depth range
  0.970..1; depth pre-pass (pass 001) then colour (pass 004); sky last at z=1 without depth write. Fog = X16 256x1 LUT (t11,
  CLAMP_TO_EDGE) indexed by tc6.z, colour = lerp(colour, c18, lut): past the fog range an object takes the full fog colour.
  Vulkan engine pipelines clip at the far plane (depthClampEnable off). Nothing found that lets one draw ignore depth.
- HYPOTHESIS (main): both symptoms come from Ultra drawing objects the game culls at Original: opponents (vehicle group,
  4x smaller screen-size cull, 2 LODs finer) and far objects past the fog design range (fully fogged = c18 haze -> white).
  Not excluded: (a) RSX_POLY_OFFSET (no [po] data exists in any kept run), (c) a far-LOD draw with other depth state.
- Change (port-vkgame/main.cpp, default ON, opt-out `MSPR_DIST_GROUPS=all`): MSPR_LOD_BIAS/MSPR_CULL_SCALE reach only the
  object, dyn and world groups; vehicle and player keep the game's values (the setting text is about trees/buildings/objects).
  Group = kind-1 call count mod 5; the first 16 calls per kind are logged with the group. Original LOD is unaffected.
  Private exe build/fardist-link/fix (ppucc2 objects 48bcfa67 + main.cpp), sha256 193ab9a8...10b2, slot `fd`.
- Arms (visual-only, before Klt5t; tools/add_arms_fd.py), launcher-like (FSR 3.1 balanced, 1.5x, HDR 0, 30 fps, no pack,
  RSX_PO_LOG=1, shots from frame 1500 every 90): Kfd1 Ultra on all groups (= user) + pass dump at 75 s; Kfd2 Original + dump;
  Kfd3 = Kfd1 with RSX_POLY_OFFSET=0; Kfd4 Ultra with the new default groups + dump.
  Decide: artefacts in Kfd1 not Kfd2 -> Ultra (VERIFIED); gone in Kfd4 -> vehicle-group fix VERIFIED; gone in Kfd3 -> poly
  offset. White ships left in Kfd4 -> object/world cull past the fog range (game behaviour; then scale cull less).
  Compare passdump_fd1 vs fd2 draws.txt for draws Ultra adds (dt/dw/df) and the [po] lines in stderr.

## Vehicle shadows far away from the vehicles (user, 2026-11-23, Lighting Original, FSR 3.1 Performance, LOD Ultra)
- VERIFIED in code: none of RSX_SHADOW_TILES/WORLD/GRID/CASCADES runs in that setup (all hooks gated; game.log has no
  [shadow-*]/[lighting] lines; lighting=Original sets nothing).
- HYPOTHESIS (strongest, unrun): FSR 3.1 moving-object motion keys on (pipeline, vertex address, draw size), the same for
  every instance of one mesh. Each vehicle's ground blob shadow is a decal box drawn through ONE box mesh, so the first box of a
  frame matched the LAST box of the previous frame (another vehicle) and was replayed with that vehicle's transform: motion
  vectors across the track, FSR history (a shadow) pulled from there. The box is also blended without depth write, so it should
  not own motion at all.
- Fix rsx_tsr_objkey.h (RSX_FSR_OBJ_FIX, default on, 0 = before): n-th instance of a key matched with the n-th of last frame;
  blended / no-depth-write draws get no object motion. tests/test_tsr_objkey.c 38/38. Log "[tsr-obj] per frame: ... repeated-mesh
  instances, blended/no-depth skipped". Exe build/vehshadow-link/fix sha256 12d41a978b808a5dca805f381c5bc806747d93b9160aadce590c9d71aaa1a868
  (slot exe_vs, with the FSR DLLs). Arms Kvs1 (fix off) / Kvs2 (fix on), the user's settings, 24 shots at the race start.
- Not excluded until Kvs1 shows the symptom: the game's own cascade refits, the blob decal path itself (RSX_DECAL_EDGE).
- Kvs1/Kvs2 (2026-11-23): right exe (12d41a97), FSR 3.1 on, RSX_FSR_OBJ_FIX off/on read. No stats line: it printed every 1200
  frames from the first scene draw and the runs ended ~frame 1900 (Kvs1 never counts: the fix was off). FSR 3.1 dispatched only
  494 / 591 of the first 1800 frames (the rest menus/loads on FSR 1). Kvs2's shots (F9 at frame 1517) were still the intro
  fly-over; Kvs1's (1574) in the race, no far blob seen. Inconclusive.
- Kvs3 (fix off) / Kvs4 (fix on), exe fix2 9151979cc17f6f95ab723a1ba4c41f4601402da1e4a4de63b6f4196ce20c392b (slot exe_vs2, FSR DLLs):
  stats every 300 frames ("[tsr-obj] frame N: k of the last n frames had scene draws; ... repeated-mesh instances, skipped"),
  and RSX_SHOTS_EVERY=30 now also applies after F9 (one frame per 30 from the press; no RSX_SHOTS_FROM), so 24 shots cover
  ~24 s from the drive's F9. Drive with auto_drive.py <tag> 4 16 30 and RUN_VK_RACE_S >= 70 (F9 at race entry + 20 s, past the intro).

## Square dark boxes round vehicles still present in Enhanced (user, 2026-11-23)
- VERIFIED from existing shots (generated/analysis/shadowtiles/boxes/): the same flat hard-edged dark box silhouette appears in
  Kst1 (tiles only, original lighting, no FX; st1_sheet.png, large, follows the crashed buggy), Kst2 (st2_11_box_ac.png) and,
  fainter, in Kbr9 (no tile code at all, exe built after RSX_DECAL_EDGE, last frame at a wall). So it is NOT an Enhanced-only
  effect and not the screen-space shadows / AO / toe (Kst1 has no FX).
- VERIFIED in code/logs: nothing of the tile path touches the decal draw. Its pipeline (Kbox pass dump, pipe 782) binds only units 0
  (scene depth as A8R8G8B8), 1 (16x16 B8 map) and 11 (ramp), never the atlas, and its c4-c7 cannot pass the reader test; the
  RSX_DECAL_EDGE sampler rule does not depend on lighting or RSX_TEX_BORDER. The Kst runs pointed 623-751 readers a frame with 0
  unpointed and 0 casters left in the atlas.
- HYPOTHESIS (the decal itself, not our shadows): the decal darkens whatever is nearer than its box's back faces inside the
  silhouette; RSX_DECAL_EDGE fixed only the outside-the-map part. Not reproduced offline beyond the stills.
- Change: RSX_DECAL_SKIP (rsx_decal_skip.h; default on with RSX_LIGHTING=1, 1 force, 0 off) drops the vehicle ground decal draws
  (draw state blend + depth GREATER, no depth write, front-face cull, AND a 16x16 B8 unit; rsx_decal_edge.h
  rsx_decal_volume_state, test_decal_edge 13/13): Enhanced already shades vehicles (tile shadows, SS contact shadows, AO), so the
  blob is redundant (replace-not-blend). Original lighting untouched. Log "[decal-skip] frame N: x.x decal draws dropped per
  frame" (expect ~14-16 in a race with the field in view; 0 means the identification missed).
- Exe build/vehshadow-link/decal sha256 f0fb4a58d5e220de22c8bdbfb0bbb7470e07a252b252c00e9f1b4ddbf57b6486 (slot exe_vd; shared
  tree + this). Arms Kvd1 (Enhanced, decals kept) / Kvd2 (RSX_DECAL_SKIP=1), the user's Enhanced env + ZSNAP_ON_WRITE + TEX_BORDER,
  one shot per 30 frames from F9 (drive: auto_drive.py <tag> 4 16 30, RUN_VK_RACE_S >= 70).

## RSX_DECAL_SKIP for the original look (decision 2026-11-23; pair queued, NOT yet confirmed, default still off)
- Code: rsx_decal_skip.h. RSX_DECAL_SKIP=1 drops the vehicle ground decals, =0 keeps them, unset = on with RSX_LIGHTING,
  and off otherwise via the constant RSX_DECAL_SKIP_ORIGINAL_DEFAULT (set to 0). Flip that one constant to 1 only after the
  pair below confirms; the user's decision is default on, with RSX_DECAL_SKIP=0 as the off switch.
- Tests: test_decal_edge 13/13, test_tsr_objkey 38/38.
- Exe slot vdo (build/vehshadow-link/decal2), sha256 8bad15e3a18d44f552fbe00fee1806dbfab1098aec32d664dfe22a486197b8fb.
- Matched pair, original look (no RSX_LIGHTING, no tile vars), user's env, one shot per 30 frames from F9:
  Kvd1o keep (RSX_DECAL_SKIP=0), Kvd2o skip (RSX_DECAL_SKIP=1). Queued before Klt5t.
- To confirm before flipping (in the Kvd1o shots vs Kvd2o): the box goes, the game's own cascade shadow stays under each
  vehicle, and the contact shadow where the wheels touch the ground is not lost. Also grep "[decal-skip]" (expect ~14-16 drops
  per frame in Kvd2o, 0 in Kvd1o).

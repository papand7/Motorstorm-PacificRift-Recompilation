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

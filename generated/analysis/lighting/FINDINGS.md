# Enhanced lighting: survey, design, milestone 1 (2026-11-22)

## Survey (census of the race's decompiled fragment programs, generated/analysis/relight/census)
- VERIFIED: 81 of 215 census programs are shadowed and sun-lit (`_rsx_shadow13` + dot(N, unit constant));
  `tools/census_baked.py` + rsx_light.h rewrite exactly those 81 (1 dot in the sample program).
  Doc census: 13 more lit without shadow, 37 unlit. Not rewritten: those 50.
- VERIFIED (program e39db44ac569d19f, typical): colour = albedo(t0, sRGB) x saturate(vertex colour col0) x
  (ambient constant c10 + sun colour c11 x shadow13 x N.L(c9)); N from normal map t1 (tangent frame tc2/tc3);
  fog towards c12 by tc7.y; glow output t1 = colour x c13. t11 is a ramp sampled by tc7.z (fog/height), t13 shadow.
- VERIFIED: vertex colour col0 is read in 77 of 81 lit programs, always as saturate(col0), multiplied onto albedo.
  col1 in 24. No lightmap texture was identified among the units sampled (0-5 material, 10-12 lookups).
- HYPOTHESIS: col0 carries baked AO / vertex lighting (terrain, props). Ambient is one per-frame constant, not
  SH/cube. Needs an albedo-only screenshot (arm lt2) to confirm; some programs (foliage) may use col0 as tint.
- VERIFIED from the repo: rsx_pbr.h is NOT a lighting rewrite: it only bends the N.L normal with a texture-pack
  detail map (needs RSX_TEX_PACK; off by default). Coverage in a race with no pack is therefore 0 draws.
- Inputs available: world normal (the dot's argument, same space as the voted sun), sun direction (constant),
  shadow factor, albedo. Not available in-shader: world position / view vector (needs camera constants passed in:
  g_rsx_tsr.vp inverse), roughness/spec (t2/t3 per program, unidentified), AO.

## Design (one opt-in "enhanced lighting", original default)
M1 lighting rewrite -> M2 tonemap (game post pass / RSX_HDR check) -> M3 own cascaded sun shadows -> M4 GTAO ->
M5 SSR/probe reflections -> M6 height fog + sun shafts (compute, scene depth + sun) and dynamic local lights
(headlight/boost/explosion, screen-space deferred additive) -> M7 per-race sun (included in the enhanced mode, env
override RSX_SUN_FIXED). Cost guess at ~21% GPU load now: M1 ~0, M2 <0.2 ms, M3 1-2 ms, M4 ~1 ms, M5 1-2 ms,
M6 0.5-1.5 ms.
- Per-race sun: VERIFIED location = the voted unit constant (s_pbr.sun); the shadow light view (vp c4-c7 of the
  shadow pass) must move with it, so it needs our own shadows (M3) first; baked terms (col0) must be neutralised
  or the old light direction stays visible. Race start: timeline race_entry / first frame of the scene pass.
- Replace-not-blend: shadows (unit 13 lookup becomes ours), reflections, baked colour are removed in enhanced mode.

## Milestone 1 as built (env RSX_LIGHTING=1, extras RSX_LIGHTING_FILL=0.25, RSX_LIGHTING_BAKE=0)
Header ps3recomp-vkgame/libs/video/rsx_light.h (+ 12-line hook in rsx_draw_engine.c after the PBR block,
tests/test_rsx_light.c, passes). In-shader tests, no new constants: N.L gets a wrapped soft terminator;
t0 gets a hemisphere sky/ground fill on sun-turned and shadowed surfaces; BAKE=0 replaces saturate(col0) by white
(keeps alpha). No specular/Fresnel yet (needs view vector), no tonemap yet.
- BUILT: build/lighting-link/MotorStormPacificRiftRecomp.exe sha256
  f36c8b3d935135501c3b9930f727b2000470eb291f1a678391951189ed691466 (copied to vksync/ab2/exe_l).
- NOT VERIFIED: never run. run_vk.py's launch queue (ORDER, next = Kbox7) and process preflight blocked my
  launch; I did not bypass them. Arms Klt0/Klt1/Klt2 are queued in run_vk.py; run
  tools/runarm.sh lt0, lt1, lt2 once authorised. No screenshots, no fps numbers yet. Risk: HLSL compiles unchecked
  on GPU (the offline test only checks text); shaders compile synchronously (first-use stalls).

## Update: shader compile check + milestone 2 tone mapping (built, unrun)
- VERIFIED offline: all 83 shadowed census programs, after the rewrite, compile with the game's compiler path
  (glslang HLSL front end: build/vulkan-sdk/Bin/glslangValidator -D -S frag -e main -V); 0 failures
  (outputs in compile/). BAKE=0 variant not compiled separately (a one-token substitution).
- Tone mapping lives in the existing scene-effects pass (rsx_vk_scenefx.h / vulkan/rsx_vk_scenefx.comp, pass 2,
  end): after the 3D scene, before the game's first post-processing pass (its glow/bloom composite) and the HUD,
  so the HUD is untouched. The scene target is the guest's display-encoded LDR colour (clamped at 1): the pass
  decodes sRGB, applies exposure and the ACES fit normalised so the white point stays white, re-encodes. This
  is a filmic regrade, not true HDR tonemapping (no >1 scene values exist; that needs FP16 scene targets).
- Switches: RSX_LIGHTING=1 now turns the scene pass on with tone mapping only (AO/fog/shafts/clouds off unless
  set to 1; RSX_FX=1 keeps its old all-on behaviour). RSX_FX_TONEMAP (mix 0..1, default 1 under RSX_LIGHTING),
  RSX_FX_EXPOSURE 1.0, RSX_FX_WHITE 1.0.
- Lit programs rewritten by RSX_LIGHTING now vote for the sun (s_pbr.sun) without a texture pack, so the
  scene effects (fog scattering, shafts) get the real sun direction in the enhanced mode.
- Order vs RSX_HDR / FSR 3.1: RSX_HDR acts at present on the final SDR frame (inverse-tone stretch above
  knee 0.5), after this pass and the game's post/HUD: the two stack (HYPOTHESIS: highlights compressed by
  ACES then re-stretched; tune with RSX_HDR_KNEE). FSR 3.1 (RSX_FSR_MODE=3): the scene hook already runs on the
  scene target the TSR path hands on (the RSX_FX path notes the epilogue without jitter); the tonemap is
  per-pixel, so it does not disturb the upscaler's history (HYPOTHESIS until the runs).
- Exe: build/lighting-link/MotorStormPacificRiftRecomp.exe sha256
  035d2066100999c31285e29183f599d85710de286879591cc8fc225dc6974b6e (exe_l updated). Arm Klt3 =
  RSX_LIGHTING=1 + RSX_FX_TONEMAP=0 (isolates the tonemap against Klt1), queued at the end of ORDER.

## Plan: own sun shadows with a CPU saving (not implemented; 2026-11-22)
Goal: enhanced mode faster than the original. The port is CPU-bound in the drain, so the saving must come
from draws the drain never decodes or translates.
- Caster draws are already identifiable early (VERIFIED in code: eng_rts_classify: depth-only, no colour
  mask, z target = the atlas 0x0B030000 learnt from the first lookup reader). The 3 cascades are viewports
  in that one 1024x2048 atlas, drawn per cascade, so many objects are drawn up to 3 times.
- UNKNOWN (needed before committing): caster draws per frame and their share of drain time. No existing log
  has it. Step 0: a counter (RSX_LIGHTING_CASTSTAT: caster draws, vertices, drain ns inside them, per cascade
  viewport) and a non-visual-only arm against Klt0. Small code change; then an arm at the end of ORDER.
- Options, best look per ms first:
  A. Skip all game caster draws before vertex fetch/translation, and shade the sun shadow with
     screen-space shadows (ray-march the scene depth towards the sun in the scene-FX pass), plus our own
     low-res far shadow map drawn from cached static geometry. CPU: saves 100% of the caster cost. GPU:
     ~0.5-1 ms. Limits: off-screen occluders (handled by the cached far map), thin geometry.
  B. Collapse to 1 cascade: drop the near/mid cascade draws (those whose viewport is the near cascade
     rectangle) and refit the lookup to one stabilised cascade. CPU: saves ~2/3 of the caster cost.
     Look: blurrier near shadows; contact shadows from depth can make up for it.
  C. Static-geometry caching: capture world casters once (on race start / when the light moves) into
     GPU buffers, draw them ourselves each frame; only dynamic casters (vehicles, debris) go through the
     drain. Most work, best quality; vehicle detection needs the per-draw transform (skinned/moving).
  Recommended order: Step 0 -> B (cheap, measurable) -> A screen-space contact shadows -> C if needed.
- Expected saving: proportional to the caster share from step 0. If casters are e.g. 15-25% of drain draws
  (HYPOTHESIS, typical for 3 cascades), B saves ~10-17% of drain time and A ~15-25%.
- Lit-program cost: GPU ALU only (+~15 instructions per lit pixel); CPU: one string rewrite per new
  pipeline. Precompile: route the rewritten program through the existing async path used by RSX_TEX_PBR
  (g.be->shader_ready + eng_pbr_job: the original draws until the rewrite is translated on a worker) and the
  RSX_VK_WARM pipeline list, so first use does not stall. Today RSX_LIGHTING compiles synchronously.
- Timing validity: non-visual-only runs refuse while EA Desktop / Epic launcher processes run (run_vk.py
  preflight); the PC state currently blocks valid timings unless they are closed by the user.

## Built: Step 0 + async lit programs + option B (unrun; 2026-11-22)
- RSX_LIGHTING_CASTSTAT=1: every 300 frames "[lighting] casters per frame": atlas caster draws and engine
  ms per cascade tile (viewport translate, uv-per-world q), vs all draws, % of draw time, skipped draws and
  redirected readers. (RSX_DRAIN_PROF already had an "atlas" bucket, but only in >20 ms frames.)
- Lit programs: the RSX_LIGHTING rewrite now goes through the RSX_TEX_PBR async path (shader_ready +
  eng_pbr_job; original draws until translated, upgrades capped per frame), no first-use stall; the shader
  disk cache keeps them for later sessions. Fixed an undefined shift for jobs without a map unit.
- RSX_LIGHTING_CASCADES=1 (rsx_light_cascade.h, included by the engine before sink_end): caster draws of
  every cascade tile but the widest are dropped in sink_end before vertex decode/program translation; the
  4x1 lookup (host copy via eng_sst_lut_texture) and the c45-c47/c49-c51 vertex-constant entries (only when
  they equal this frame's lookup entries) all point at the widest tile. Off with RSX_SHADOW_STABLE.
  Risks (HYPOTHESIS): lookup entries may not be the only per-cascade state (depth range); readers whose
  constants were not matched keep the near tiles, which are now empty (no shadow there).
- Exe sha256 36fa9d8e0259aedd0d4b7620c06101d5ab0b5900669f18f25aecb85d838f82bd (exe_l updated).
- Arms (end of ORDER): Klt4 look (enhanced + one cascade + stats); Klt5t/Klt6t timing pair (original vs
  enhanced + one cascade, RSX_DRAIN_PROF + stats): `runarm.sh lt5t timing`, needs EA Desktop/Epic closed.

## Klt4 result and fix (2026-11-22)
- VERIFIED (Klt4 stderr): 3 cascade tiles in the atlas (viewport y 352 / 1040 / 1712, q 0.0098 / 0.0045 /
  0.0014 uv per world unit). Casters 742 draws, 1.69 ms of 14.92 ms draw time a frame (11.3%); 678 skipped.
  1878 lookup readers and 61.5 vertex-constant readers redirected, 0 failures. LOOK: no sun shadows near the
  camera (sign, palms) - the redirect was wrong, not just soft.
- Cause (HYPOTHESIS, strongest): the lookup was rewritten by "smallest |entry.x| wins, every non-zero entry
  replaced". A 4th entry (border / beyond-the-cascades, smaller scale than any tile) would win, so all
  readers looked at an unused, cleared part of the atlas. The shader does uv = lightpos.xy * L.xy + L.zw
  with L = lookup[index] (census 015678a40ae38f78), so the entry choice decides everything.
- Fix: each lookup entry is matched to a cascade tile by its x = that tile's q (the relation
  RSX_SHADOW_STABLE uses); only entries of the other tiles take the kept tile's entry; unmatched entries stay.
  Vertex-constant readers the same way. If the kept tile is missing from a reader's lookup, caster skipping
  pauses for 60 frames (the game's cascades drawn again) instead of leaving empty tiles. The first 6 lookups
  are logged ("[lighting] lookup frame ...") with all 4 entries and their tiles.
- The black boxes by the vehicles are also in Klt0 (original), so they are not from this change.
- Exe sha256 86c582d3471f7d4aae67aba77552dbd7769951b1615fc54cae1ca3c310dd568b (exe_l updated; the queued
  Klt5t/Klt6t timing pair now also runs it). Klt7 = Klt4's env on the fixed exe, at the end of ORDER.

## Own per-frame shadow fit (RSX_LIGHTING_CASCADES=2; built, unrun; 2026-11-22)
Design (rsx_light_cascade.h): keep the one-cascade CPU saving; the kept (widest) cascade's box is fitted to the
camera EVERY frame instead of following the game's 1-8 frame refits:
- axes e1/e2 = the frozen SST basis (refrozen only when the light moves >1 degree); size = the game's (ladder
  with hysteresis, changes rarely); centre = proj(cam) + D*proj(fwd) in the light plane, snapped to whole atlas
  texels (a world-fixed grid, so no crawl); camera = last frame's scene camera (c0-c3 of the scene draws,
  noted at the end of the scene), D learnt at each game refit.
- Both sides use that box in the same frame: casters of the kept tile get c0-c3 rows 0/1 = (U/kx)(e1.p - c1);
  every reader gets lookup entries (U, V, tile centre) and c4-c7 origin (-c1, -c2) (vertex-constant readers
  c45-c51 the same). Why this should not jump like RSX_SHADOW_STABLE: the old code kept the box position in
  the HALF-float lookup (needed a 16-unit snapped origin and exact halves, and re-centred at each game
  refit); here the lookup is constant (ladder scale, tile centre: exact halves) and the moving box origin is
  in the float vertex constants, with the casters computed from the same numbers. The earlier jump cause
  remained unexplained (GLITCHES.md), so this is HYPOTHESIS until Klt8.
- VERIFIED offline (tools/fit_model_check.py on captures k102/k109): the game's widest box centre fits
  cam + D*fwd with residual 0.05 of the box half size (k102 mean, max 0.26), D 217 +- 23 m; the near tiles fit
  worse (0.2-0.37), which is why only the widest is fitted. k109 has outlier refits (another scene's camera);
  the model ignores outliers (>0.6) and is used only while the residual average < 0.25; otherwise the game's
  own fit is left untouched (counted as "invalid").
- Log every 300 frames: "[lighting] own shadow fit: game refits per frame, box valid, box moved (fraction of frames; should
  approach 1 while driving: the shadow cadence becomes 1 frame), model D and residual".
- Exe sha256 b0a5bb64b073e930a6d805d115d6b224ffb6ffd31c0ef4e5c615434e3abc2ef0. Arm Klt8 (visual-only look arm:
  RSX_LIGHTING=1 + CASCADES=2 + CASTSTAT=1) is last before Yy1 (after Klt5t/Klt6t). Check: near shadows still
  present, no jump, the box-moved fraction in the log, then eyes on foliage shadow stepping.

## Plan notes: long shadow distance and LOD in the enhanced mode (not built)
- Long distance, layered: (b) screen-space sun shadows to the horizon (+ near contact shadows), then (a) own
  4096^2 atlas with 3 per-frame cascades (near ~100 m @ ~5 cm, mid ~350 m @ ~17 cm, far ~800 m @ ~40 cm)
  drawn by instancing the game's caster draws (one draw -> 3 cascades: CPU unchanged, GPU ~0.6-1 ms),
  (c) static far cache only if needed. Limit: the game submits casters only inside its own cascades
  (widest ~650-820 m wide, centre ~217 m ahead).
- Game controls to test for caster submission (DISTANCE.md): max shadow range 200.0 (MSPR_SHADOW_RANGE did not
  change cascade texel sizes), shadowFadeDistModifier (MSPR_SHADOW_FADE, consumer untraced, HYPOTHESIS: the
  fade-out distance), shadowCullThreshold (scaled by MSPR_CULL_SCALE). Next arm candidate: enhanced +
  MSPR_SHADOW_FADE=3 + MSPR_SHADOW_RANGE=600 with CASTSTAT, to see whether caster count / widest q change.
- LOD: when the enhanced-lighting PC setting exists (only after verification), it implies "lod" Ultra
  (MSPR_LOD_BIAS -2, MSPR_CULL_SCALE 0.25) unless lod is in pcs explicit_mask. Open: -2 on the default
  group biases (object 1.0, world 2.0, vehicle 0, player -2.5) brings world only to 0.0; whether that is the
  finest LOD everywhere depends on minimumLod/lodOverride (untested) -> measure with a LOD-selection counter
  or try -3/-4 and compare draw counts/frame time. CULL_SCALE also scales shadowCullThreshold, so more small
  casters are submitted: CPU cost to be measured against the one-cascade saving (CASTSTAT + RSX_DRAIN_PROF).

## Klt8 result, fixes, screen-space sun shadows (2026-11-22)
- VERIFIED (Klt8 log): casters 368 draws 1.18 ms of 11.76 ms draw time (10.0%); our box valid 0.92-1.00 of frames
  while racing but 0.0-0.3 in some windows: the model gate (residual average > 0.25; D 167-232 m, residual
  0.11-0.40) switched the fit off there. The 4922 failed redirects all fall in ONE 300-frame window (stderr line
  14590) where tiles 1 and 2 had nearly the same size (q 0.0214 vs 0.0222): the widest tile changed, the
  lookup did not hold the chosen tile, the fallback (game cascades for 60 frames) engaged; other windows 0.
- Fix 1 (anchored fit, no model gate): at each game refit the game's own centre and the camera are stored;
  every frame the centre = that anchor + the camera's translation since + D x the turn of the view
  direction (D only while the model fits). Always valid once the game has refitted; exact at refit frames.
- Fix 2: during a redirect failure (and 60 frames after) the box is not refitted either, so casters and
  readers never disagree; the failure count is now per window and the first 8 failures are logged with the
  lookup entries and tiles.
- New counters split "refitted" into moved / under a texel (camera moved < 1 texel: box stays, correct) /
  camera still, and "not refitted".
- (b) built: screen-space sun shadows in the scene-effects pass (RSX_FX_SSSHADOW, default on under
  RSX_LIGHTING; strength 0.45, contact ray 2.5 m, long rays from 300 m with length 0.12 x distance; 16 taps; only on
  surfaces facing the sun; RSX_FX_DEBUG=7 shows the term). GPU cost estimate 0.5-1 ms at 2560x1440, unmeasured.
- Exe sha256 e82d44d4958ddd1a694892e466cd1e69f2241bfb88364ac24e9fb02a05811f4f (exe_l updated).
- Arms, visual-only, queued BEFORE Klt5t: Klt9 (enhanced + CASCADES=2 + SSSHADOW + stats), Klt10 (= Klt9 with
  RSX_FX_DEBUG=7). runarm.sh now RUN_VK_RACE_S=90 (hard kill 224 s) and F9 at race entry +10 s for 8 s.
- LOD plan (not built, waits for the PC setting): the "Lighting: Enhanced" PC setting will imply lod=Ultra
  (MSPR_LOD_BIAS -2, MSPR_CULL_SCALE 0.25, which also scales shadowCullThreshold) unless pcs.explicit_mask has
  "lod". To check then: whether -2 reaches the finest LOD for every group (GroupSettings lodBias defaults
  object/dyn/world/vehicle/player 1.0/1.0/2.0/0.0/-2.5, so world needs -2 just to reach 0; a stronger bias
  or minimumLod may be needed), and the CPU cost (more caster draws through the drain).

## Klt9/Klt10: lost to a full disk (2026-11-22)
- VERIFIED: drive C: had 1.1 GB free (930 of 931 GB used). The shot files are 1 byte (the first buffered byte;
  every later write failed) and both runs' stderr stops at ~49 s (heartbeat frame 1452 / 1363) while the runs
  went on to ~66 s; so the race-time "[lighting]" lines were never written. The all-zero fit lines are the
  menu/garage windows before race entry (no shadow atlas yet: zeros are correct there). Klt8's race lines
  (written while there was space) were valid. No sign of a crash: Klt7 (good shots) ended the same way (exit 1
  at STOP). Nothing in this work touches the screenshot writer (vk_shot_write: plain fopen/fwrite of a BMP).
- Freed 1.4 GB losslessly: my shots lt0-lt4/lt7 BMP -> PNG, pixels verified equal (tools/bmp2png.py); broken /
  truncated BMPs kept as they are. C: now 2.3 GB free - still nearly full; the bulk is other data.
- Klt11 = Klt9 again (enhanced + per-frame fit + screen-space shadows + stats) with RSX_SHOTS_MAX 12 (~95 MB),
  queued before Klt5t. It needs >= ~1 GB free on C: when it runs (logs + shots).

## AO in the enhanced mode (built, unrun; 2026-11-22)
- The scene-effects AO (half resolution, depth-based, bilateral upsample) is now on by default under RSX_LIGHTING
  (RSX_FX_AO=0 turns it off). Strength 0.6 over the game's baked vertex AO, 0.85 when RSX_LIGHTING_BAKE=0 removes
  it; radius 1.2 m, power 1.3 (RSX_FX_AO_STRENGTH / _RADIUS / _POWER override).
- Composition: AO now runs after the screen-space sun shadow and darkens only the ambient share: full on surfaces
  turned from the sun or in screen-space shadow, 35% where the sun lights the surface directly (weight from the
  depth normal's N.L and the shadow term). Then fog, shafts, and tone mapping last, as before.
- Cost estimate (unmeasured): AO pass ~0.3-0.6 ms at half of 3840x1080, plus a normal reconstruction now shared
  with the screen-space shadows.
- Exe sha256 32e5df09de1579c76a997a4d292e7bcde92a494ff502447b1d66ee3dfd7a4537 in a new slot exe_l2 (exe_l left
  alone while Klt11 runs). Arm Klt12 (enhanced + per-frame fit + screen-space shadows + AO, 12 shots) queued
  before Klt5t.

## Brightness: enhanced was too bright (user, 2026-11-22) - measured and corrected (built, unrun)
Measured with tools/lumstat.py (luminance of the display-encoded image, HUD bands left out) on the saved shots:
| set | mean | p5 | p95 | clipped (any channel >= 250) |
|---|---|---|---|---|
| lt3 (lighting rewrite, NO tone mapping) | 136.7 | 39.6 | 215.5 | 2.5 % |
| lt1 (rewrite + first tone mapping) | 140.1 | 21.4 | 239.5 | 5.2 % |
| lt11 / lt12 (+ cascades, SS shadows, AO) | 131 | 16-17 | 231 | 2-2.6 % |
| lt0 (original) | 119.7 over a fade-in; settled frames ~170 | 22-25 | 252 | 21-25 % |
The shot sets are NOT matched moments (lt0 starts on the intro camera and fades in; races differ), and Klt11/12 ran with
RSX_RT_READBACK_ASYNC=1 (the spiking exposure mode), so these means cannot give a clean original-vs-enhanced difference.
The clean measurement is on the SAME frames: tools/tonecurve_sim.py applies the scene pass's curve to lt3's frames:
- VERIFIED: exposure 1.0 / white 1.0 (the old defaults) lifts the mean +29 (134.6 -> 163.7, +22 %) and clipping 1.6 -> 3.3 %.
  Cause: the ACES fit is made for scene-linear HDR; on this display-referred image it maps linear 0.18 to 0.33
  (sRGB 0.46 -> 0.61), a large mid-tone lift.
- New defaults exposure 0.5 / white 1.2: mean 131.2 (-3.4, slightly below the input), p5 42.9 -> 21.3 (deeper
  shadows), p95 209.6 -> 214.2, clipping 0.0 % - an S-curve: darker lows, mids kept, highlights held.
- Also reduced (HYPOTHESIS they raised the mean; not separable offline): sun-terminator wrap 0.35 -> 0.2 and its blend
  0.6 -> 0.35 (it lifted grazing light by up to +14 % of N.L), sky/ground fill 0.25 -> 0.15. AO (0.6 / 0.85) and
  the screen-space shadows only darken. The game's own exposure (c33) is untouched; its effect shows only with
  the launcher's RSX_RT_READBACK_ASYNC=0, so the new arms use it.
- Exe sha256 1867dca13ca54eca4123dac601cf25c630f17e1fc2ef5760a5b0850f51f5746f (slot exe_l3). Matched pair queued before
  Klt5t: Klt13 (enhanced) and Klt13o (original look, same exe, same settings, ASYNC=0, 12 shots each). Compare with
  `lumstat.py build/shots/lt13 build/shots/lt13o` (and `sheet.py` for side by side).

## Klt13 pair: tree shadows lost; and the "teleporting shadows" (built, unrun; 2026-11-22)
Klt13 (enhanced) vs Klt13o (original), same exe, READBACK_ASYNC=0, bands from tools/lumbands.py:
| | sky | middle | ground (left, sunlit+shade) | dark ground (<70) | ground std |
|---|---|---|---|---|---|
| original | 111.3 | 84.3 | 85.5 | 38.6 % | 39.6 |
| enhanced | 96.8 | 84.1 | 164.8 | 4.3 % | 48.7 |
- VERIFIED: the +21 % mean is the ground: the dappled palm shadows (39 % of ground pixels dark) are gone (4 %), the sand
  fully sunlit; the sky is already 13 % DARKER than the original. So the brightness was missing shadows, not the tone curve
  (exposure 0.5 stays; sky could take a little more).
- Cause (HYPOTHESIS, strongest; the Klt14 stats confirm it): the game culls small casters out of its wide cascades, so
  keeping the WIDEST alone leaves out nearby palms/foliage. New "sent / drawn" per-tile caster counts will show the
  per-cascade sets. Fix: RSX_LIGHTING_KEEP=0|1|2 keeps the nearest / middle (default) / widest cascade; Klt14 = middle,
  Klt15 = nearest. Beyond the kept box the old cascades are no longer drawn, so the screen-space shadow's long rays
  now start at 120 m (was 300).
- Readers the per-frame fit cannot follow are now counted and described ("atlas reader not followed by the fit ...").
Teleporting shadows (user): the GAME's centre steps are irregular: in capture k102 the widest cascade centre changes in
81 of 378 frames, median 0 m, max 307 m (k109: max 5231 m = scene change); our old anchored fit re-anchored at each
of those refits and used a D that moved. Now (rsx_light_cascade.h): the centre = eye + D x the low-passed view direction,
on the texel grid, from OUR camera pose only; D = median of the first 60 refits, slewed 1 % per sample; the box size is
latched per kept tile; the kept tile is latched while it is drawn; no fallback flips (a reader the fit cannot follow
is only counted; RSX_LIGHTING_STRICT=1 restores the old drop-the-box behaviour).
- VERIFIED offline on captures (tools/box_continuity_sim.py replays the algorithm on the real camera):
  | capture, cascade | our centre step mean / p95 / max | camera + turn | worst step / (cam+turn+texel) | spikes | game's own step max |
  | k102 widest (323 m) | 1.94 / 9.45 / 19.6 m | 0.86 + 1.28 mean | 1.79 | 0 | 307 m (81 of 378 frames move) |
  | k109 widest (410 m) | 2.23 / 4.85 / 16.4 m | 1.18 + 1.28 | 1.50 | 0 | 5231 m |
  | k102 middle (108 m) | 1.17 / 2.69 / 14.8 m | 0.86 + 0.40 | 1.18 | 0 | 88 m |
  The box never moves more than the camera's own move plus the turn of the (low-passed) direction; in game the log
  prints "[lighting] box continuity" per 300 frames and up to 20 "box step SPIKE" lines; RSX_LIGHTING_BOXLOG=<csv> writes
  every frame's centre, size, camera, direction for offline checks.
- Exe sha256 4cd0177a96c6e29e320908587a4bab5e96878963da7b87c835c4b58b9b0438cb (slot exe_l4). Arms before Klt5t:
  Klt14 (enhanced, KEEP=1, box log), Klt15 (KEEP=0, box log), both READBACK_ASYNC=0, 12 shots; compare to Klt13o with
  lumbands.py / sheet.py.

## World-anchored shadow window (built, unrun; 2026-11-22)
- Why shadows moved with the camera (VERIFIED in code and logs): the window centre was camera + D x view direction,
  so every turn moved it, and D was learnt from the game's refits. And the window was centred ~200 m AHEAD, so the
  ground within ~70 m of the camera was outside it: that is the lost near palm shadows (Klt14/15 dark ground 9-13 %).
- Now (rsx_light_cascade.h eng_lc_box): window origin = the camera's position projected on the frozen light axes,
  snapped to the world texel grid (multiples of one texel). No view direction, no D. The texel grid itself is
  world-fixed; a camera translation moves the window by whole texels (new texels revealed, existing ones keep their
  world position); a turn moves nothing. Sun change = basis refreeze (>1 degree) = the only mapping change.
- Kept cascade default is now the NEAREST (RSX_LIGHTING_KEEP=0); its casters are the only ones drawn in mode 2.
- Offline (tools/world_anchor_check.py on k102/k109): window bound |n - e1.cam/texel| max 0.50 (camera always inside, to
  the texel); pure turns: window unchanged in 18/18 and 7/7 frames; sun refreezes 0 in these captures; per-frame window
  steps are the camera's own texel crossings (median small; a few large steps at scene cuts, 188 texels in k102).
- Casters of moving objects are still drawn every frame at their current positions (user clarification): only the
  mapping is world-anchored.
- Not built yet: the separate original-look switch (RSX_SHADOW_WORLD) needs the same window applied to all three game
  cascades (the readers of each), not just the kept one; that generalisation is the next build.
- Exe sha256 3cea671c3091dd4f23491d46df28409699aeef45f463b538a2ea7e17dea9ed53 (slot exe_l5). Arms before Klt5t: Klt16
  (enhanced, world window, nearest kept, box log) and Klt16o (original, same exe, the matched baseline), 12 shots each.

## Default-on world-fixed shadows for the original look: status and the design needed (2026-11-22)
- NOT done in this pass: making the world-fixed mapping the default for the original look. Blocker, VERIFIED in code:
  the original look keeps the game's three cascades and rewrites each reader through the 4x1 lookup texture. The lookup
  entry is stored in half floats and must be exact for caster and reader to agree (rsx_sst_lut_entry), and a window origin
  that moves by texels breaks that. The enhanced one-cascade path avoids this by moving the origin into the receivers'
  float constants (c4-c7) with constant lookup entries (U, V, cx, cy); that trick needs ONE origin for all three
  cascades, which only works if their texel grids nest.
- Proposed design (next build): world mode uses a power-of-two scale ladder (each cascade's texel = 2^k world units, 2x
  steps; latched, changes only on a deliberate size step). Then the three texel grids nest, one shared origin
  c1 = snap(e1.cam, coarsest texel) is a multiple of every finer texel (world-fixed for all tiles), the lookup entries are
  constants (U_i, V_i, cx_i, cy_i), and the casters of each tile use the same formulas as the enhanced path. Cost: CPU
  unchanged (casters are drawn as the game sends them), the coarser ladder costs texel resolution up to 2x per step.
  Verification plan: world_anchor_check.py per tile (camera turn = zero change; translation = whole coarse steps only),
  then a look arm with the original look (no lighting env) against an original baseline (lt16o).
- The original-look path is untouched unless RSX_SHADOW_WORLD is set; it stays the default until a look run confirms.

## RSX_SHADOW_WORLD: all cascades world-fixed (built, unrun; 2026-11-22)
Klt16 vs Klt16o (coordinator): ground 101 vs 81, dark ground 25.5 % vs 63 %: palm shadows back but patchy and ending at a
visible edge (the nearest window ~64 m; nothing from there to the SS start at 120 m).
- New rsx_shadow_world.h (RSX_SHADOW_WORLD=1 alone = original look; RSX_LIGHTING_CASCADES=3 with the enhanced lighting):
  every cascade is drawn as the game sends it (no caster skipped: foliage and distance as the original), each into a
  world-fixed texel grid: power-of-two sizes (latched), one shared origin = camera on the coarsest grid, windows ahead
  of the camera by D_i (learnt per cascade) snapped to their own grid. Constant-structure lookup entries (dyadic: exact
  in half floats), origin in the readers' float c4-c7. A window move is whole texels on a world-fixed grid: static
  shadows never shift; only the sun (basis refreeze) moves the mapping. Moving objects drawn every frame as sent.
- With the original look the scene camera is taken from the scene draws without running any scene effect.
- VERIFIED offline (tools/sw_check.py replaying the algorithm on captures): k102 / k109: windows on their grid 0
  misaligned of 396 / 541 frames, lookup values exact in half 3564/3564 and 4869/4869, pure turns origin unchanged 18/18
  and 7/7, the game's own box centre inside our window 1188/1188 and 1269/1271 (so the game's cascade selection still
  lands in the right window). Sizes (k102): 128 / 256 / 1024 m, texels 0.125 / 0.25 / 1.0 m (the power-of-two floor makes
  the far cascade up to 2x coarser than the game's; near and middle about the game's).
- Not done: a fade band between cascades (edges as the original), foliage-sway sync (not investigated yet: our rewrite
  only touches rows 0/1 of the light matrix, the game's own animation constants are untouched), the CPU saving (gone in
  this mode: all casters drawn), brightness.
- Exe sha256 31d4cb30ec2b15fe92aec5ba59fe41e9cf73c87ea3a1d9efc104046c2136fdc4 (slot exe_l6). Arms before Klt5t: Klt17
  (enhanced + world shadows + SS shadows from 450 m), Klt17w (original look + world shadows only), Klt17o (original
  baseline, same exe); 12 shots each, READBACK_ASYNC=0.

## Plan: reflections, GTAO, colour grading (after the shadow work; not built)
Order: (0) world-fixed shadows default + foliage shadows + distance + brightness (in progress) -> (1) colour grading
(cheapest, also the brightness tool) -> (2) GTAO replacing the current AO -> (3) screen-space reflections.
All in the scene-effects pass (rsx_vk_scenefx.comp), under RSX_LIGHTING, each with its own switch, cost and shots.
1. Colour grading (RSX_FX_GRADE): after the tone curve, a 33^3 3D LUT (RGBA8 3D texture, trilinear) with a neutral
   default, a built-in "tropical" preset, and <play>/grading.cube (Adobe .cube, loaded at start, validated; falls back to
   neutral). Before the LUT: white balance (temperature/tint as a von Kries scale), saturation, contrast around mid-grey
   (RSX_FX_SATURATION / _CONTRAST / _WB_TEMP / _WB_TINT). Cost ~0.05-0.1 ms (one 3D fetch per pixel). Risk low: one
   descriptor + one texture; the HUD is untouched (the pass runs before it).
2. GTAO (RSX_FX_AO=gtao): horizon-based, 2 slices x 6 steps per pixel at half resolution, view-space normals
   reconstructed from depth (as now), cosine-weighted visibility, optional bent normal; denoise: 4x4 spatial bilateral
   (depth + normal weights) then temporal accumulation with the scene camera's reprojection (vk_tsr_mv data exists for
   FSR 3) and history clamping. Expected 0.4-0.8 ms vs ~0.3-0.6 ms now. HBAO+-style is not planned unless GTAO misses
   the budget: GTAO gives the better occlusion per ms; one AO stays.
3. Screen-space reflections (RSX_FX_SSR): half-res, hi-Z ray march (a depth min-mip chain built per frame, ~8-24 steps)
   from depth-reconstructed normals; reflectance from Fresnel (Schlick, F0 0.02 water/mud, 0.04 dielectrics, paint 0.05
   + clearcoat); roughness from the texture pack's PBR map where present (needs the material id or roughness written
   by the lit programs: an extra output or a G-buffer channel; the scene pass writes 4 targets today, contents not all
   identified), else a per-surface guess (water/mud by program hash, vehicles by their programs); fade at screen edges and
   for rays toward the camera; bilateral upsample + temporal reuse. Cost 1-2 ms. Risks: identifying water/mud/paint
   pixels (program-hash tagging into a mask target), and the game's own fake reflections (cube maps) must be dimmed
   where SSR hits, else double reflections.

## Colour grading (built, unrun; 2026-11-22)
- In the scene-effects pass after the tone curve (before the game's post-processing and HUD): white balance (linear
  light), saturation, contrast around mid-grey, then a 3D LUT (storage buffer, trilinear in the shader).
- RSX_FX_GRADE: off (default without RSX_LIGHTING) / neutral (default under RSX_LIGHTING: the controls, no LUT) /
  tropical (built-in 33^3: warm highlights, slightly teal shadows, +8 % saturation, soft S) / file (RSX_FX_GRADE_FILE,
  default grading.cube in the play folder; Adobe .cube, LUT_3D_SIZE 2..64, DOMAIN_MIN/MAX; an incomplete file falls back
  to neutral with a log line). RSX_FX_SATURATION, RSX_FX_CONTRAST (1.0), RSX_FX_WB_TEMP, RSX_FX_WB_TINT (-1..1, 0),
  RSX_FX_GRADE_STRENGTH (1.0). With all neutral the grading code is skipped.
- Offline preview of the same math (tools/grade_preview.py): build/shots/ltcmp/grade_tropical.png (left before, right
  tropical; mean luma 93.9 -> 95.2). Cost estimate ~0.05-0.1 ms (8 buffer reads per pixel), unmeasured.
- Exe sha256 b26ef77bc4e65d44277e53c0a3caac1d6058d7003971e9a25f3866857e91e352 (slot exe_l7). Arm Klt18 (Klt17's setup +
  tropical LUT) queued before Klt5t.

## RSX_SHADOW_WORLD "goes nuts while driving" (user, original look) - findings, and the world-tile design (2026-11-22)
- Hypothesis "the game redraws a cascade only when it refits it" is REFUTED (VERIFIED, tools/tile_presence.py):
  every cascade tile gets casters on every captured frame (k102 396/397, k78 442/443, k86 1189/1189 frames), while the
  game's matrices change only on 66-88 of those frames; per-frame atlas caster counts in the Kbr5 drain profile stay
  1100-1750 draws per frame while racing (no drop between refits), so the tiles are fully redrawn every frame.
- Remaining suspect (HYPOTHESIS, unverified): frame-boundary mismatch. Our per-frame box is keyed to the engine's frame
  counter (g.frames, bumped at present). If the game issues the next frame's shadow pass before the flip, those casters
  are rendered with the current frame's box and read with the next one: still when standing, wrong whenever the camera
  moves - exactly the symptom. Fix would key each tile's box to its own caster pass (set at the tile's first caster
  draw after a reader/scene draw) and give readers the box the tile was last rendered with. Not built: the user's new
  requirement rules out camera-following windows as the final design anyway. RSX_SHADOW_WORLD must stay off.
- Design under the new requirement (shadow at a world point depends only on the sun and the casters; nothing follows
  the camera or the vehicle):
  1. Static layer: ONE world-fixed shadow map per track, in tiles fixed in the light plane (frozen axes per sun), single
     resolution everywhere (no distance LOD, since a LOD switch is camera-dependent). Rendered once per race and again
     only on a sun change. Memory for a 3 x 3 km track: 25 cm texels = 144 M texels = 288 MB (D16) / 576 MB (D32); 50 cm =
     72 / 144 MB; tiles of 4096^2 (1 km at 25 cm) resident as they are needed, kept for the race.
  2. Dynamic layer: moving casters (vehicles, riders, debris, swaying foliage: classified per caster draw by whether
     its object constants change between frames; foliage sways through constants, so it is dynamic) drawn every frame
     into a world-fixed-grid map around the casters (12.5 cm texels, 256-512 m, 16-64 MB), composited with the static
     layer by min depth in the reader.
  3. Feeding: the game only sends casters inside its own cascades around the camera, so the static map can only be
     built from what the game sends. Capture each static caster draw's geometry once (world-space triangles: the RT
     shadow path, rsx_vk_rt.h vk_eng_rt_caster, already captures caster triangles each frame) into a persistent,
     de-duplicated GPU buffer, and render newly captured static triangles into the world tiles. Consequence: on the first
     pass through an area its static shadows appear as soon as the game first sends those casters (the game sends them
     ~100-600 m ahead), after which they are fixed for the race; a per-track disk cache could make even the first lap
     complete.
  4. Readers: the decompiler emits our own _rsx_shadow13 helper; in this mode it samples the world maps by world-light
     position instead of the game's atlas. The game's lookup is set to identity entries and c4-c7 rows 0-2 to our fixed
     world light space (including a FIXED depth row: the game's depth range changes at every refit), so the helper gets
     world-light coordinates directly; the caster matrices get the same rows.
  Costs (estimates): static render once per race and on sun change (~10-50 ms spread over frames); dynamic casters as
  today (CPU unchanged for those; static casters after capture no longer need translating: a CPU saving); reader cost
  +1 texture lookup; VRAM 100-650 MB by resolution. Applies to the original look too (no lighting rewrite needed).
  Work: phase 1 readers + fixed depth row + dynamic layer = all casters per frame into world grid; phase 2 static
  capture and world tiles; phase 3 disk cache. Several weeks; each phase verified offline on captures, then look runs.


## GTAO replaces the enhanced-mode AO (built, unrun; 2026-11-22)
- RSX_FX_AO=gtao is the default under RSX_LIGHTING (RSX_FX_AO=1 there means gtao too); RSX_FX_AO=old (or classic) keeps
  the 12-sample AO; RSX_FX_AO=0 off. Only rsx_vk_scenefx.comp / rsx_vk_scenefx.h (+ the two regenerated .spv.h) changed.
- Pass 0 (half res): horizon-based GTAO (Jimenez 2016 / XeGTAO integral), 2 slices x 6 steps per side (RSX_FX_AO_SLICES,
  _STEPS), world-space slices, the radius projected per axis (aspect-correct on the 2x-wide depth), capped at 15 % of
  the screen height, distance falloff over the outer 60 % (RSX_FX_AO_FALLOFF), a 3-degree tangent-plane bias,
  spatio-temporal noise (IGN + golden-ratio per frame). Normals from depth with the same NormalAt the SS shadows use.
  Optional bent normal (RSX_FX_AO_BENT 0..1, default 0): sky visibility of the bent vs the plain normal (Y up,
  HYPOTHESIS); RSX_FX_DEBUG=8 shows it. Defaults radius 1.5, power 1.5, strength as before (0.6 / 0.85 without bake).
- Pass 3 (new, half res): 4x4 bilateral (distance + normal weights, window alternating per frame), then temporal
  accumulation: the pixel's world point reprojected with the previous frame's camera and epilogue (the same
  VP_prev * inverse(VP_cur) reprojection rsx_vk_tsr_mv.comp makes for FSR 3, computed in the pass so it works without
  FSR 3), history rejected where the distance seen there differs by > 3 %, clamped to mean +- 1 sigma of the local
  samples (RSX_FX_AO_CLAMP), 1/n blend up to 8 frames (RSX_FX_AO_FRAMES; 1 = off). Visibility stays linear (0..2)
  through both filters; clamp + power in the composite. NaN guards for degenerate edge normals (would poison history).
- RSX_FX_TIME=1: GPU timestamps (AO passes, whole scene pass), averaged and logged every 600 frames ("[fx] gpu").
- VERIFIED: shader compiles (glslangValidator, both output formats) and passes spirv-val; exe links.
- VERIFIED offline (generated/analysis/gtao/tools/gtao_preview.py, numpy port, synthetic ray-cast scene, no game data;
  build/shots/ltcmp/gtao_synthetic.png left classic, right GTAO): open ground 1.000 (classic 1.000), wall crease 0.72
  (0.72), sphere contact 0.13 (0.35: GTAO much darker in real contact), open-ground noise std 0.049 raw -> 0.001 after
  the 4x4 filter. The first version read open ground as 0.93 (clamping noisy values before the filter + point-sampled
  grazing samples); both fixed before the build.
- Cost estimate (unmeasured): ~1.5x the classic pass's taps/ALU plus a ~37-load resolve -> ~0.5-0.9 ms at half of
  3840x1080. Klt19/Klt19c log the measured numbers.
- Exe build/gtao-link/MotorStormPacificRiftRecomp.exe sha256 0708eaa317e4d9da6aec0ea3d1e1acd26fa59833ea15bf68cb8a8fa7d807effa
  (slot exe_gt1; compiled from the tree as of 2026-11-22 ~21:00, so it also contains the other agents' in-progress
  draw-engine/backend edits: compare only Klt19 with Klt19c). Arms before Kbl2a: Klt19 (enhanced as Klt17 + GTAO +
  RSX_FX_TIME) and Klt19c (same exe, RSX_FX_AO=old), 12 shots each, READBACK_ASYNC=0.

## GTAO smear fix (Klt19 vs Klt19c, 2026-11-22; built, NOT run)
- Klt19 (GTAO, temporal 8) showed diagonal streaks across the sky and the top of the frame (build/shots/ltcmp/gtao_pair.png).
  Klt19c log confirmed "[fx] AO classic" (switch OK; the two arms' shots differ).
- Cause not proven. Changes: history rejected past 800 m (no AO, no history), AO fades out 500-800 m; depth test 3% -> 1%;
  history clamped to the min/max of the current 4x4 window (was mean +- sigma); temporal accumulation OFF by default
  (RSX_FX_AO_FRAMES=1; 8 turns it back on). Reprojection math checked against the FSR 3 motion-vector path (same
  VP_prev * inverse(VP_cur) and epilogue convention), not changed.
- Exe build/gtao-link2, slot exe_gt2, sha256 1647887c22401b62e70f5869132395a1f0d88fa12d9a6e10b438e9fc5b6859ce. Not
  queued. Verify spatial GTAO first (default now); enable temporal with RSX_FX_AO_FRAMES=8 only after the sky is clean.

## World-tile design implemented (RSX_SHADOW_TILES, 2026-11-22): see generated/analysis/shadowtiles/RESULTS.md
Phase 1 (dynamic world-fixed map + fixed light space/depth row + rewritten helper), phase 2 (static layer), phase 3 (disk
cache) built behind RSX_SHADOW_TILES / _STATIC / _CACHE, verified offline on the captures, unrun; arms Kst1, Kst2, Kst3, Kst3b.
RSX_SHADOW_GRID (rsx_shadow_grid.h, unfinished, never built into an arm: the game's per-cascade scissored clears would erase
earlier cascades in its single map) is superseded and stays off.

## Screen-space GI (RSX_FX_GI) and dynamic lights (RSX_FX_DYNLIGHTS) (built, unrun; 2026-11-23): see generated/analysis/gi/RESULTS.md
Both off by default, both read the RSX_SHADOW_TILES map with the readers' own mapping (tests/test_fx_st.c). Arms Kgi1/Kgi1o
(exe_gi1, 861c71a2...) and Kdl1/Kdl1o (exe_gi2, ada89447...), all with RSX_LIGHTING + RSX_SHADOW_TILES + _STATIC, before Klt5t.

## Ground too bright / near white (2026-11-23; tools/groundstats.py, groundtone_sim.py)
Ground = bottom 40 % of the frame, luma mean / p95 / % > 235 (the other port's JPGs are 1440p third-party images, kept local):
- reference port: kanaloa-race (beach) 92 / 158 / 0.4; cascade-falls-start 53 / 132 / 0.4; cascade crash 43; rain-god 111.
- ours original look: lt16o 80 / 207 / 0.9 (rising 69 to 98 over the run), lt17o 102 / 225 / 3.3 (sand clips). Launcher game (br7/br8, no
  RSX_LIGHTING, mix over varied moments) 100-116 / ~200 / 0.8-1.5.
- ours enhanced: gi1o 119 / 210, st2 121 / 195, gi1 126, lt17 (earlier tone curve, no world tiles) 55, lt19 76.
Causes: VERIFIED (sim, inverting the current curve on gi1o/st2): the ACES fit at exposure 0.5 / white 1.2 leaves sand mid-tones at the
input level (exposure 0.3 only gives -15 on mean), so the world-tile shadows' lifted ground (lt17 55 -> st2 121) is not countered; a
power on the tone-mapped linear is what moves the ground. p95 of ours (195-225) is far above the reference's 130-160: sand highlights are
near-white. HYPOTHESIS: the original look itself (lt17o 102, p95 225, 3.3 % clipped) is also brighter than the reference; it runs no
scene pass, so the fix there is not applied (an opt-in would need the pass enabled; RSX_FX_TONEGAMMA only acts where the pass runs).
Not the cause (checked in code, not measured): sRGB handling (decode/encode symmetric in Tonemap), ASYNC readback (br7 100 vs br8 116 are
different moments, per-shot spread 66-166).
Fix: RSX_FX_TONEGAMMA (default 1.4 under RSX_LIGHTING, 1.0 otherwise), power on the tone-mapped linear colour (gi4.w, rsx_vk_scenefx.comp
Tonemap). Sim on gi1o: ground 120 -> ~88 mean, p95 211 -> ~190; st2 121 -> ~89, p95 195 -> 170 (reference beach 92 / 158). Gamma 1.7 would
give 76/185. SPIR-V headers regenerated (glslangValidator -V, and -DOUT_RGBA16F for the 16 variant).
Exe build/tone-link/MotorStormPacificRiftRecomp.exe sha256 80cc08df7d4a478efc4ab9d7b1198865fe52cced307069ded7d40a26aa424ed0 (slot
exe_tg1). Arms Ktg1 (enhanced, gamma 1.4) and Ktg1o (same exe, RSX_FX_TONEGAMMA=1.0) before Klt5t, same BASE as Kgi1o. Not run.
Eye check: sand brightness vs the reference beach shot, shadows not crushed, sky not too dark. GTAO sky streaks are not from the tone path
(not investigated).

### Correction after Ktg1/Ktg1o (tg1o ground 55, tg1 49, sky 104 -> 84)
- Cause of the dark baseline: VERIFIED by build recipe (HYPOTHESIS for the pixels): exe_tg1 recompiled only rsx_vulkan_backend.c over the
  ppucc2 objects, without rsx_draw_engine.c / rsx_be_thread.c, so it had no RSX_SHADOW_TILES engine code (ground 55 = the Klt17 look).
  Arm env was identical to Kgi1o. The sim base (gi1o 120) was right for the full exe; the global gamma was the wrong lever (sky -20).
- Change: RSX_FX_TONEGAMMA default back to 1.0 (opt-in); it now applies to geometry only (weight 0 on sky, faded out where fog > 0.5),
  so the sky and the hot horizon haze are untouched.
- Exe build/tone-link2 (draw_engine + vulkan_backend + be_thread recompiled) sha256
  e654ae5519a1f3764a91023a4c1b6681db3d81aae4ffd2da889e95850ac935ff, slot exe_tg2. Arms Ktg2o (RSX_LIGHTING + TILES + STATIC +
  SSSHADOW_FAR 450 + RSX_FX_AO=old, gamma 1.0) and Ktg2 (same + RSX_FX_TONEGAMMA=1.35), before Klt5t. Not run. User-facing default unchanged.

### Ground at the source: RSX_LIGHTING_GROUND (Ktg2o/Ktg2: ground 122.3 / 113.9, upper area 92.6 / 75.3; gamma is the wrong lever)
- Sim on the real tg2o shots (tools/groundscale_sim.py, scale on lit-ish pixels): x0.85 -> ground 106 / p95 162; x0.75 -> 95 / 143;
  x0.70 -> 90 / 134 (base 122 / 191; reference beach 92 / 158).
- Change: _rsx_lt_fin (rsx_light.h) scales the colour of bright, sun-facing, up-facing fragments (weights: N.L, smoothstep(0.55,0.9,N.y),
  luma ramp 0.25..0.45) by RSX_LIGHTING_GROUND, default 0.75 (1.0 = off). Foliage/vehicles/sky are barely weighted (upper area expected ~unchanged;
  HYPOTHESIS until run). Shadows are dark so the luma ramp leaves them alone. Exposure 0.5 and gamma 1.0 unchanged; tests/test_rsx_light passes.
- Exe build/tone-link3 sha256 d2958e8c7f6537085a07f632ba7ac0cd36b1243ce86f59c1a20ab070ce55c0b6, slot exe_tg3. Arms Ktg3 (default 0.75) and
  Ktg3o (RSX_LIGHTING_GROUND=1.0) with the full shadow-tile settings + RSX_FX_AO=old + SSSHADOW_FAR 450, before Klt5t. Not run.

### Ktg3 result and the final-luma toe (RSX_FX_GROUNDTOE)
- Ktg3: ground 132.1 / p95 201.6 vs tg2o 122.3 / 190.9; Ktg3o produced no shots (spent). stderr shows the lit programs rewritten
  ("[lighting] fp ...: 2 dot(s) rewritten"), so the rewrite ran, but the scale's effect is NOT proven: the tg3 shots are from the race start
  (other moment than tg2o's mid-run shots), and the N.y / luma weights at _rsx_lt_fin could not be measured (no per-fragment counter; HYPOTHESIS:
  the sand's normal-mapped N.y or pre-tone luma sits outside the ramps). RSX_LIGHTING_GROUND is now default 1.0 (opt-in, kept).
- Robust lever instead: scene pass, after the tone curve, final-colour luma toe: col *= 1 - (1-s) * smoothstep(0.35, 0.60, luma) * geometry
  weight (0 on sky, faded in fog, blue-dominant pixels excluded). RSX_FX_GROUNDTOE default 0.65 under RSX_LIGHTING (1 = off; replaces the
  gamma knob in gi4.w). Log "[fx] ground toe scale X" at start. Sim on real shots (tools/groundtoe_sim.py, sky excluded): s 0.70 ->
  tg2o ground 98.8 / p95 134 (upper 91.1 vs 92.8), tg3 ground 102 / p95 141; s 0.60 -> 91 / 115. Reference beach 92 / 158.
- Exe build/tone-link4 sha256 977f4f3f5ef75ff05e1594490da31f87e57c24b77db3d516f6f0612ffd4368f8, slot exe_tg4. Arms Ktg4o (toe 1.0) and Ktg4
  (default 0.65), shots frame-indexed (FROM 1560, EVERY 6) in both, shadow-tile settings + AO old + SSSHADOW_FAR 450, before Klt5t. Not run.

### "Sun crazy bright over the hill, almost white" -- ORIGINAL look (launcher, no RSX_LIGHTING; 2026-11-23)
- The enhanced toe is not involved (no scene pass in the original look).
- Existing data (Kbr7 ring = launcher default, Kbr8 ASYNC=0, Kbr9 legacy; launcher-like env, shots every 90 frames from 1500; moments differ):
  exposure-target trace, share of copies with geomean G < 0.35 (dark sample -> the CPU raises exposure; t = 0.3/geo G, c33.x = 1+0.7(t-1)):
  ring 15.3 %, sync 2.5 %, legacy 27.0 %; c33.x median/p90 0.649/1.004 (ring), 0.634/0.827 (sync), 0.686/1.509 (legacy).
  Upper-half % > 235 per shot: ring 5-14 % for 5 consecutive shots (frames 1950-2310), sync <= 0.3 % over the same frames (max 7.5 % at
  the first shot), legacy up to 9.5 %.
- PARTIAL: the ring still gives the exposure loop more dark samples and a higher exposure tail than sync readback. Ring values are smooth,
  not garbage. Moments are not matched, so that is not proven to cause the hill blow-out (HYPOTHESIS). The game's own design is also a
  factor (VERIFIED in code earlier, GLITCHES.md): adaptation falls at 0.026/frame vs rising 0.07/frame, and c33.x cannot go below 0.37.
  After a dark view (uphill slope, shade) the crest toward the sun stays over-exposed for about a second. The reference port's
  caldera-ridge-big-rig.jpg also has 19 % of the frame > 235 (white sky), so a white sky can occur in the real game. No PS3 capture of
  this hill exists.
- No default changed (no matched evidence). Arms before Klt5t, launcher exe 8323b33b (slot exe_hs, copy; original look, launcher-like env,
  c33 watch + exposure trace, 60 shots every 15 frames from 1500 = race start + first hill): Khs1 (ring, launcher default), Khs1s
  (ASYNC=0), Khs1l (legacy). Decision: if Khs1 shows upper-half clipping / c33 spikes at the crest that Khs1s does not, switch the
  launcher to ASYNC=0 for the exposure target or add a ring guard. If both clip alike, it is the game's own adaptation; an enhanced-only
  highlight shoulder would be the lever.

### Sun glare halo (user screenshot, original look, exe 8323b33b): ZPASS occlusion counts
- The capture shows a large white-yellow glare blob around the sun, not a general exposure lift. Khs1/1s/1l did not face the sun
  (upper-half clip <= 7 %).
- VERIFIED in code: without RSX_ZPASS_COUNT (the launcher does not set it) every GET_REPORT ZPASS reads 0xFFFF ("fully visible";
  rsx_zpass_counter.h says MotorStorm uses these counts for the sun glare). The game therefore gets a maximum visibility count however
  much of the sun is hidden. HYPOTHESIS: 0xFFFF is far above the guest-pixel count the game expects for its sun quad, giving the oversized
  halo. Measured counts were also in host pixels (RSX_RES_SCALE targets are n/d larger per axis).
- Change (rsx_vulkan_backend.c): RSX_ZPASS_COUNT default ON (opt-out RSX_ZPASS_COUNT=0), and reports scaled to guest pixels (x d^2/n^2).
  tests/test_zpass_counter passes. Cost: a GET_REPORT now waits for the draws before it (a sync point, perf unmeasured). History: arm Cc1
  (early bring-up, 2026) with RSX_ZPASS_COUNT was "all white", for reasons not recorded; check for that.
- Exe build/zpass-link sha256 eda58653e0671236f2309e3ed8c8819adeda73b3f552d93c4bf13f53f031c17d (ppucc2 objects + draw_engine,
  vulkan_backend, be_thread from the shared tree), slot exe_zp. Arms Kzp1 (counts on) and Kzp1o (RSX_ZPASS_COUNT=0), original look,
  launcher-like env (ring readback), shots every 10 frames from 1500 (60 shots: GO + the Kanaloa run toward the sun), before Klt5t.
  Not run. Read stderr "[zpass] reports=... value=..." for the counts.
- Kzp1 result (coordinator): "[zpass] reports=2048 clears=0 enables=0 queries=0 value=0". The game never sends 0x17CC (ZPASS enable) or
  0x17C8 type 1 (clear) through the walker, so every report read 0 = sun always hidden (upper clip 2.2 % vs 5.1 % in Kzp1o). Frames
  were not white. VERIFIED (stdout): GET_REPORT type 1, 4 per frame at report offsets 0x14100/0x14110/0x14120/0x14130 (main memory,
  dma 0xFEED0001). The ELF holds no ori/addi immediate 0x17CC and no method header 0x000417CC; the enable path is unknown.
- RSX_ZPASS_COUNT is back to default OFF (opt-in) in the shared tree; the guest-pixel scaling stays.
- Diagnostic: RSX_REPORT_TRACE=<n> (cellGcmSys.c walker) prints the methods carried since the previous GET_REPORT (bulk vertex/
  constant/texture methods filtered) at the first n reports. Exe build/zpass-link2 sha256
  31ce8273a09dd3a41be5acf8949135b75ed80ae4aa3cd9c17da97d0ad584a48e (slot exe_zt); arm Kzt1 (original look, counts on, trace 400)
  before Klt5t. Next: read "[report-trace]" lines, find the enable/clear methods (e.g. 0x1D84/0x1D88 candidates), make the counter
  follow them, and check that the value varies with the sun in and out of view.
- Kzt1 (report trace, 400 GET_REPORTs): VERIFIED: the type-1 reports come in pairs per frame. 0x14100 or 0x14120 is issued right after
  SET_REFERENCE (0x0050, frame start; 2 walker methods before it). 0x14110 or 0x14130 comes after the post-processing chain (luminance
  fp 0x74B180, exposure 0x74C780, bloom 0x74C340, as the 2D inline constant uploads 0x6300/0xA400). The buffers alternate. No 0x17CC
  (count enable) or 0x17C8 (clear) is ever sent: the fast path hands both to the walker, which counted 0 of each in Kzp1. So the game
  never enables ZPASS counting. These reports are GPU frame-begin/frame-end timestamps; the value field is unused (HYPOTHESIS: timing
  for the game's DRS/perf logic).
  Conclusion: the sun glare does NOT come from occlusion queries. The Kzp1 vs Kzp1o clip difference (2.2 vs 5.1 %) was a moment
  difference. No counter change is needed. RSX_ZPASS_COUNT stays opt-in (it would only zero the unused value); no pair queued.
- Remaining candidate for the halo (HYPOTHESIS): the game's bloom, max(L - 8, 0) on MRT1 = colour x c33.x / 16, blurred from an 80x45
  target. It grows with the exposure c33.x, so a high c33 (exposure readback) when the sun enters the view widens the halo. Next
  evidence needed: a pass dump facing the sun (RSX_ENGINE_PASS_DUMP; bloom target contents and c33.x) on ring vs ASYNC=0.

### Hand capture of the sun glare (F9 pass dump), 2026-11-23
- New opt-in: RSX_ENGINE_PASS_DUMP_GATE=F9 (rsx_draw_engine.c, Windows). The pass dump of RSX_ENGINE_PASS_DUMP starts on the frame after
  F9 goes down (once per session) and writes every pass's targets (ppm) and passes.txt/draws.txt, up to RSX_ENGINE_PASS_DUMP_MAX passes.
- Exe launcher/dev/MotorStorm/play/MotorStormPacificRiftRecomp_sundump.exe (build/sundump-link) sha256
  868a6d3a51c794a933fad90ae37b5304e970d83e1265fb44885c600bea4372fe. Main play exe untouched (8323b33b). Output dir play/sundump/.

### Sun-glare dump analysis (play/sundump, first F9 = frame 2688; contact sheet build/shots/ltcmp/sundump_sheet.png)
- VERIFIED (passes.txt/draws.txt). Frame chain: scene MRT pass (A 0x00750000 + B 0x01650000, 2560x720) -> pass 271 (1260 draws,
  rewrites 0x01650000, which later passes read as Y16_X16_FLOAT, fmt 0xBF) -> 277 combine to 1280x720 (t0 scene, t1 0x01650000) ->
  278 16x16 exposure target (0x07EBA600) -> 279 640x360 -> 280 320x180 FP16 bright pass (2 draws) -> 281/284 160x90 and 80x45 ->
  285/286 80x45 blur -> 287 draw 0: the composite (t6 = 80x45 bloom, t5 640x360 pass 273 blurred highlights, t0 320x180, t2 scene,
  t3 32x32 B8). Draws 1-6 of 287 are the HUD.
- The halo is that bloom: pass 280 keeps only a thin horizon strip (bright sky/haze where the low sun is), the 80x45 blur spreads it,
  and 287 adds it (final - scene luma +32 inside the halo, 3.9 % of the frame above 20/255 bloom). It is not a sun sprite/lens flare
  (no such draws in 287) and not occlusion queries (earlier). Exposure is normal: c33.x 0.76-0.79 at t = 101-103 s, median 0.63-0.69
  in Kbr7-9, no spike. FSR is not involved (the dump is pre-upscale; the halo is already in pass 287).
- Not established: whether the bright-pass input (0x01650000 as packed FP16) is brighter than on a PS3. The RGB ppm drops one byte,
  so the dump could not decode it; RSX_ENGINE_PASS_DUMP_ALPHA would keep it. No PS3/RPCS3 frame exists for comparison. Status: the
  game's own bloom (VERIFIED as the mechanism), intensity vs PS3 HYPOTHESIS. No renderer change made.

### Sun Glare / Bloom option (RSX_BLOOM_SCALE), 2026-11-23
- rsx_bloom.h (new, header-only), hooked in rsx_draw_engine.c fragment translation. A program that samples exactly units 0..6
  (the final composite; the 80x45 bloom is unit 6, rgb = bloom, alpha = vignette) has every unit-6 sample routed through
  _rsx_bloom6 = float4(rgb * k, a). Other programs (scene, HUD, the bloom chain, exposure) are untouched. k = 1 or unset: no text
  change. Logs "[bloom] RSX_BLOOM_SCALE k" and "[bloom] composite fp: n unit-6 sample(s) scaled". Takes effect at start (restart setting).
  Test ps3recomp-vkgame/tests/test_rsx_bloom.c passes.
- PC Settings: "bloom" / "Sun Glare / Bloom" = Original (default, nothing set) / Reduced (0.5) / Off (0), Graphics page now 8 rows.
  pc_pages.h firsts moved: wheel 16, keys 24/32/37. PCF_COUNT 268 is within the 272 text-buffer limit. launcher settings.js +
  ui/app.js info + test_settings.js. test_pc_settings, test_pc_keys and node test_settings.js pass. The pcmenu page files must be
  regenerated (make_pcmenu.py) for the new table before this exe's menu is used.
- Offline (sundump frame 2688; build/shots/ltcmp/bloom_scale_sim.png, final ~= 0.84 scene + 0.9 bloom fitted per channel; no dust
  term): halo-area luma 184 -> 153 (0.5) -> 131 (0); halo pixels > 235 37.8 % -> 11.7 % -> 9.6 %; upper half > 235 2.95 % -> 0.90 % -> 0.74 %.
- Exe build/bloom-link sha256 033e7c640ba5ef24361d262763660118ee39c1443d3b501890314ee41b745dd9 (ppucc2 objects + draw_engine,
  vulkan_backend, be_thread, cellGcmSys, port pc_menu.cpp and main.cpp from the shared tree). Not run.
- RSX_ENGINE_PASS_DUMP_ALPHA=1 already exists and keeps the alpha byte, which would allow decoding the packed-FP16 target 0x01650000.

## GTAO sky smear, round 2 (2026-11-23; built, NOT run, default NOT changed)
- Klt19 (gt1) sky: streaks confirmed in gtao_pair.png; sky mean 139.7 (GTAO) vs 145.1 (old) at frame 1605 (lt19 vs lt19c,
  different shots). Not reproduced offline (no depth dumps); the sky there is not AO-composited unless its depth is below 1.
- Changes: AO history off beyond 350 m (AO fades 250-350 m; was 800 m); host drops history when the camera moves more than
  3 m in one frame (guards against scene-camera candidate changes in rsx_draw_engine.c); depth test 1%; history clamped to the
  window min/max. Temporal is still set to 8 in the Klt20 arm.
- Exe build/gtao-link3, slot exe_gt3, sha256 33be54da286eed9a6373b563c54099778686f07ada08c2b6e715942a6863b974.
- Arms queued (not launched): Klt20 (GTAO, temporal 8, Enhanced) and Klt20c (old AO, same exe), placed before Klt5t.
  The queue still has earlier unlaunched entries (Ktg3o, Khfa1 ...), so these run after them.

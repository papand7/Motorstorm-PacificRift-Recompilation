# Screen-space GI and dynamic lights in the enhanced mode (2026-11-23; built, NOT run)

Both live in the scene-effects pass (ps3recomp-vkgame/libs/video/rsx_vk_scenefx.h + vulkan/rsx_vk_scenefx.comp, SPIR-V
headers regenerated with build/vulkan-sdk glslangValidator, both output formats pass spirv-val). Engine side:
rsx_fx_lights.h (+ rsx_fx_shared.h, rsx_fx_st.h), 3 small hooks in rsx_draw_engine.c (include, scene_fx `sun` argument,
one call after eng_fx_draw). No new backend entry: scene_fx's `sun` pointer now points at an rsx_fx_sun_ext (sun first,
magic, extras), so other backends/builds are unchanged. Both features are off by default.

## World-tile shadows (user requirement)
- The scene pass reads this frame's RSX_SHADOW_TILES map (dynamic map + static store) with the readers' own mapping
  (TileSun in the shader, rsx_fx_st.h): VERIFIED offline, tests/test_fx_st.c, 120400 checks, 0 failed; worst difference vs
  the rewritten _rsx_shadow13 path 4.9e-4 map texel, 0 m depth, 1.2e-4 store texel (200 random suns/windows, points up to
  2 km out, float arithmetic). The shadow-tiles code itself is not changed (read only: s_st.m, view, store).
- GI: the bounce source is the scene colour the lit programs produced, i.e. already shaded with the world-tile shadow; the
  receiver's "how much is direct sun" (which decides how much of its colour is the ambient share the GI replaces) uses
  N.L x (1 - screen-space shadow) x TileSun. Dynamic lights use the same term for the albedo estimate.
- Without RSX_SHADOW_TILES the term is unknown (-1) and falls back to N.L x screen-space shadow. RSX_FX_DEBUG=9 shows it.

## 1. RSX_FX_GI=1 (screen-space GI)
- Pass 5 (one group): running averages of the sky and of the non-sky scene radiance (32x32 samples, EMA 0.05).
- Pass 4 (half res): visibility-bitmask GI (Therrien et al. 2023): 2 slices x 8 steps per side, radius 3 m (x1-3 with
  distance), thickness 0.75 m, 32 sectors per slice; covered sectors bring this frame's lit colour (cosine weighted),
  free sectors the sky average (up) or the scene average (down: off-screen ground). Divided by the open-sky reference
  (sky colour at 20 % saturation): an open flat surface gets exactly 1. Factor brightness clamped 0.25..1.6.
- Pass 6 (half res): 5x5 bilateral (distance + normal), history reprojected with the previous camera, rejected unless the
  same surface (1 % distance), never for sky or beyond 500 m, clamped to the window's min/max, blend 1/6.
- Composite: linear colour x mix(1, factor, strength x mix(1, 0.35, sunlit)); fades out 250-500 m. AO strength x0.6 while
  GI is on (RSX_FX_GI_AO). Switches: RSX_FX_GI_STRENGTH 1.0, _RADIUS, _STEPS, _SLICES, _THICK, _FRAMES (1 = no temporal),
  _FADE_START/_END, _SKYSAT, _GROUND, _MAX/_MIN, _AO; RSX_FX_DEBUG=10 shows factor x 0.5.
- Offline preview (tools/gi_preview.py, numpy port, synthetic scene, no game data) build/shots/ltcmp/gi_synthetic.png:
  shadowed wall front luma 107.4 -> 103.0 and its blue cast gone (factor 1.03/0.90/0.77: warm sand bounce), shadowed
  ground 115 -> 109 (occluded sky near the wall), sunlit ground unchanged, whole image 192.5 -> 191.5 (not brighter).
- Cost estimate (unmeasured): ~32 depth+colour taps + 64 sector ops per half-res pixel + a 25-tap resolve: ~0.6-1.1 ms at
  half of 3840x1080. The arms log "[fx] gpu ... scene pass" (RSX_FX_TIME); GI cost = Kgi1 minus Kgi1o.
- Exe build/gi-link/MotorStormPacificRiftRecomp.exe sha256 861c71a2b39e627d0395864cc6b0d519d64da508ae2a0e87c0658a1fa83d70aa
  (slot exe_gi1; ppucc2 objects + rsx_draw_engine.c, rsx_vulkan_backend.c, rsx_be_thread.c from the shared tree, so it also
  contains other agents' in-progress edits: compare only Kgi1 with Kgi1o).
- Arms (visual-only, before Klt5t): Kgi1 = RSX_LIGHTING + RSX_SHADOW_TILES + _STATIC + SSSHADOW_FAR 450 + RSX_FX_TIME +
  RSX_FX_GI=1; Kgi1o = the same without GI. 12 shots each, READBACK_ASYNC=0.

## 2. RSX_FX_DYNLIGHTS=1 (dynamic lights; HYPOTHESIS: the sources)
- No census of light constants exists for vertex/fragment programs; the lit census (relight/census) shows one sun +
  one ambient constant, no local lights (FINDINGS.md survey). So sources come from draws: every 3D scene draw blended
  additively (dst factor ONE, add) is a light candidate: centroid of up to 64 attribute-0 positions through the draw's
  own c0-c3 to clip space, back to the world with the scene camera; colour = mean vertex colour (attribute 3, UB or float;
  default warm 1.0/0.6/0.3); radius 3 m + 2.5 x half extent, <= 10 m; sources within 1.5 m merge (brighter, <= 2x);
  drop beyond 250 m; brightest 32 kept. Assumptions to check in the Kdl1 log (RSX_FX_DYNLIGHTS_LOG=1 prints the first 64
  sources and a summary every 300 frames): attribute 0 goes through c0-c3 alone; attribute 3 is RGBA byte order.
- Shading (pass 7 + composite): per 16x16 tile, the world box of 8x8 depth samples, lights whose sphere touches it -> a
  32-bit mask; per pixel diffuse N.L (slightly wrapped) x smooth window x 1/(1 + d^2/4), screen-space occlusion (6 depth
  taps towards the light; occluded 0.15), added as albedo-estimate x light (albedo = colour / mix(0.35, 1, sunlit)).
  Switches: RSX_FX_DYNLIGHTS_STRENGTH, _OCCLUSION, _GAIN, _RADIUS, _RANGE, _MAX; RSX_FX_DEBUG=11 shows the light.
- Cost estimate: CPU ~64 vertex reads per additive draw (count unknown); GPU cull ~0.02 ms, shading ~0.1-0.3 ms with
  lights on screen, ~0 without.
- Exe build/gi-link2/MotorStormPacificRiftRecomp.exe sha256 ada89447ed174b7938ba4e085bdcc4fb3ac665d916d247b974cdb946f99de09a
  (slot exe_gi2; same tree + the rsx_fx_st.h refactor). Arms Kdl1 (= Kgi1o + RSX_FX_DYNLIGHTS=1 + log) and Kdl1o
  (= Kgi1o on this exe), before Klt5t.

## Order in run_vk.py ORDER (unlaunched part)
Kst2, Kst3, Kst3b, Kgi1, Kgi1o, Kdl1, Kdl1o, Klt5t, Klt6t, ... (tools/add_arms_gi.py checks ORDER[:671] == launches_used).

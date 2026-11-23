# Screen-space reflections, Enhanced mode (RSX_FX_SSR=1; 2026-11-23; built, NOT run)

Files: ps3recomp-vkgame/libs/video/rsx_ssr_tag.h (new, engine side), rsx_draw_engine.c (4 small hooks),
rsx_vk_scenefx.h (vk_ssr_* functions + bindings 18-20), vulkan/rsx_vk_scenefx.comp (passes 8/10/9 + SsrApply);
both .spv.h regenerated with build/vulkan-sdk glslangValidator, both pass spirv-val.

## Material tags (stencil bits 0-1; HYPOTHESIS that the game leaves them free: it uses 0x40/0x80, t75)
- Every depth-tested draw with the guest stencil off gets ALWAYS / REPLACE / write mask 3; the per-draw reference is the
  tag (1 water, 2 mud, 3 paint) or 0 (depth-writing draws clear it). Non-depth-writing draws are touched only if tagged.
- Water: 6 blended programs of the Kanaloa sea/shore pass (passdump_box1 pass 016/018: ONE/INV_SRC_ALPHA, scene depth +
  env cube t14) plus any blended program with TextureCube t14. They write no depth: the surface is a plane at an
  estimated water level (highest ground under tagged water, pass 10) or RSX_FX_SSR_WATER_Y.
- Paint (per draw): opaque program reading env cube t14 with an explicit LOD AND unit 3 = 256x256 DXT5 (the texture every
  vehicle/rider program in box1 binds, no track program does). Mud: none identified (RSX_FX_SSR_MUD=<hashes>).
- RSX_FX_SSR_LOG=1 lists the classified programs; RSX_FX_DEBUG=12 shows tags, 13 the added reflection.

## Offline check (tools/ssr_preview.py, synthetic scene, analytic truth; game dumps have 8-bit depth and no camera)
- 32 steps: 139 hits, median error 0.01 px; misses are grazing rays onto sand (the level estimate is 5 cm low) and 4 on
  the post; 20 steps found 103 (default raised to 32). Image build/shots/ssr_prev/ssr_synthetic32.png.

## Build / arms
- build/ssr-link/MotorStormPacificRiftRecomp.exe sha256 2daff1f2a40e815a9ba22e838afa13b0652f3ad1c1fc7bd3c3527883b792f0db
  (slot exe_ssr1; shared-tree rsx_draw_engine.c / rsx_vulkan_backend.c / rsx_be_thread.c: contains other agents' edits).
- Kssr1 (GI arms' BASE + RSX_FX_SSR=1 + _LOG) vs Kssr1o (BASE), 12 shots each, queued before Klt5t.
- Cost estimate (unmeasured): hi-Z 5 levels ~0.1 ms, trace only on tagged half-res pixels ~0.2-0.6 ms, composite ~0.05 ms;
  RSX_FX_TIME scene-pass delta Kssr1 - Kssr1o.

## Kssr1 looked like Kssr1o: causes and fix (2026-11-23)
- The log line "lists: water 0, mud 0, paint 0, none 0" only counts the optional RSX_FX_SSR_*=<hashes> override lists.
  Classification did work: the Kssr1 stderr lists 4 water programs (fe796479, 066793e5, ea186b29 + shore) and 20+ env-cube programs.
- Main cause, VERIFIED from passdump_box1: the scene effects fire at the first small-target draw after the scene, which
  is the 640x360 dust layer (passes 012-014). The sea is drawn after that (passes 015-018), so SSR ran before any water
  existed and the water was then blended over it. Fix: RSX_FX_AFTER_WATER (on by default with RSX_FX_SSR) skips the dust
  layer as a trigger, so the effects run at the post chain (320x180), after the water.
- Paint is subtle by design: F0 0.05 plus clearcoat is about a 7 % mix at normal incidence. Possible extra misses, now handled:
  (a) the depth image had no SAMPLED usage without FSR3, so its stencil aspect may read 0. Fix: SAMPLED under
  RSX_FX_SSR. (b) Draws using the guest stencil were skipped. Fix: when the draw does a plain REPLACE that never
  compares bits 0-1, the tag rides on the guest reference.
- New log lines: "[ssr] draws so far: water/mud/paint/cleared ..." (after 3000 draws, then every 200000);
  "[fx] SSR frame: tracing|OFF (stencil view bound|missing)"; "[fx] scene effects wait past the dust layer".
- Exe build/ssr-link2/MotorStormPacificRiftRecomp.exe sha256 c979578b6a7f85ed766b535bcbcdd190a799fc6f6d58e2867b9181916a75ccde
  (slot exe_ssr2). Arms Kssr2 (BASE + RSX_FX_SSR=1 + _LOG) and Kssr2o (BASE + RSX_FX_AFTER_WATER=1: the same effect
  timing without SSR), 12 shots each, queued before Klt5t. Not run.

## Kssr2 "ghost" vehicles (pale blue, see-through AI quads): cause and fix (2026-11-23)
- Kssr2 log: water 6502 tagged draws but "guest stencil kept 1079087" against "cleared 193498". Most scene draws (vehicles
  included) use the game's stencil, and those were left untouched. So they never cleared our bits, and a water tag from
  an earlier frame stayed under a vehicle. The vehicle was then shaded as the water plane, about 100 % sky reflection
  at grazing angles. Paint 0 had the same cause (vehicle draws skipped), not design.
- Fixes: (1) bit 2 holds the frame parity. The engine flips it per scene-effects call and the backend counts its calls
  the same way, so a tag from an earlier frame reads as stale. The stencil write mask is now 0x07 (HYPOTHESIS: bit 2
  unused by the game). (2) The tag rides on guest-stencil draws whenever the guest test ignores bits 0-2 (ALWAYS, or
  a mask without them), fail/zfail keep, and pass keeps, replaces, or the write mask is 0. Draws that do not qualify are
  left alone. (3) Shader: a water-tagged pixel whose depth-buffer surface is nearer than the water plane is not water.
- Exe build/ssr-link3/MotorStormPacificRiftRecomp.exe sha256 0511a8ea634de6100bdae578bd07cbc6190be4c228397e62221e32c7385b1661
  (slot exe_ssr3). Kssr3 / Kssr3o (= ssr2 / ssr2o env) queued right after Klt23c. Not run.

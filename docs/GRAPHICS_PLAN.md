# Graphics enhancements: plan (2026-11-15)

User request: better lighting, volumetrics, volumetric clouds, better water and mud, new shaders,
"like BF1943 and Nightfire". Every effect is opt-in (PC Settings), the original look stays the default.

## Model: the BF1943 / Nightfire scene effects

Both ports run their own passes on the finished 3D scene, before the game's post-processing and HUD,
from inputs captured off the game's own draws:

- BF1943 (`1943 xbla/bf1943-recomp/thirdparty/xenia/src/xenia/gpu/vulkan/scene_fx.*`,
  shader `.../gpu/shaders/scene_fx.cs.glsl`): GTAO, height fog, volumetric light shafts through the
  game's shadow map, volumetric clouds and cloud shadows, sky scattering, RT sun shadows and RT GI,
  sea reflections. GLSL compute, built with glslangValidator.
- Nightfire (`Xbox Nightfire/dev/nightfire-recomp/sdk/runtime/gpu/vulkan.cpp`, HLSL strings compiled by
  DXC): GTAO, contact shadows, atmosphere (shafts and fog), bounce light, SSR, AgX/ACES tone mapping with
  auto exposure, RT AO, reflections and relighting.

## What MotorStorm's renderer already has

- The scene camera: c0-c3 of the scene draws (`eng_tsr_note`, `g_rsx_tsr.vp`), its inverse, near/far
  and field of view (`vk_tsr_mv`).
- The scene depth target (`g_rsx_tsr.depth`).
- The sun direction (`s_pbr.sun`, voted from the lit programs' constants; RELIGHT_PLAN.md).
- The game's sun shadow map: unit 13, 1024x2048 D24 at 0x0B030000 (RELIGHT_PLAN.md).
- RT sun shadows with ray queries (`rsx_vk_rt.h`), a PBR rewrite of the lit programs (`rsx_pbr.h`),
  compute pipelines from embedded SPIR-V (`vk_tsr_mv_init`).
- Spare GPU time: about 21% GPU load at 144 fps (Kk3046).

## Steps

1. **Hook** (in progress): one call per frame from the engine to the backend once the 3D scene is done
   and before the first post-processing or HUD draw, with the scene colour, depth, camera and sun.
   `RSX_FX_PASSLOG=<frame>` logs one frame's passes to find that point (Kk3054).
2. **GTAO** (port of the Nightfire/BF1943 pass).
3. **Atmosphere:** height fog, volumetric light shafts (ray-marched through the game's shadow map).
4. **Volumetric clouds** and cloud shadows (BF1943 pass 5), sky scattering.
5. **Water and mud:** replace the water and mud fragment programs (found by program hash, like the
   PBR rewrite): screen-space reflections, Fresnel, foam, wet ground.
6. **Lighting:** PBR on every lit program, ambient from the sky, RT AO and reflections on the RT scene.

Each step: a PC Settings switch, a measured cost, before/after screenshots.

## Enhanced lighting (2026-11-22): see generated/analysis/lighting/FINDINGS.md
One opt-in mode that replaces baked lighting, game shadows and reflections. Order: lighting rewrite (RSX_LIGHTING=1,
rsx_light.h, built, unrun) -> tonemap -> own cascaded shadows -> GTAO -> SSR/probes -> fog/shafts + dynamic lights ->
per-race sun (part of the mode, RSX_SUN_FIXED override). Tone mapping (ACES fit in the RSX_FX scene pass, before post/HUD) built behind RSX_LIGHTING, unrun. One-cascade shadows with near-cascade casters skipped (RSX_LIGHTING_CASCADES, CPU saving) built, unrun. rsx_pbr.h is only a detail-normal bend, not a lighting rewrite.
Enhanced mode, next after shadows (plan, see generated/analysis/lighting/FINDINGS.md): colour grading (3D LUT + grading.cube,
saturation/contrast/white balance), GTAO with spatial+temporal denoise replacing the current AO, screen-space reflections
(hi-Z, Fresnel, roughness from PBR maps or per-material guess). Each its own switch under RSX_LIGHTING.

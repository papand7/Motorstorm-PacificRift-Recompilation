# GTAO (RSX_FX_AO=gtao) results

## 2026-11-23: Klt24 cross-hatch and wedge, texel-centre depth fix (exe_gt4)

Evidence: Klt24 (gtao, RSX_FX_AO_FRAMES=8) and Klt24c (old) on exe_st6 `c9161d3b...`. Klt24 has a fine cross-hatch of short
dark vertical and horizontal dashes on the sand, and also on the sky dome (shot_001951). Near the crashed rider there is a
dark wedge with hard edges (shot_002041, shot_002131). Klt24c is clean.

Cause (VERIFIED offline, HYPOTHESIS for the game): `Gtao` point-sampled the depth at arbitrary uv (`textureLod`, nearest)
but rebuilt each position at that uv (`WorldAt(uv, d)`), not at the centre of the texel the depth came from. Every
position therefore sat up to half a texel off the surface. The half-res pixel's own uv lies exactly on a scene-texel
corner. Which texel its fetch picks depends on float rounding, and that is fixed per row and per column. On the 2x-wide
3840x1080 target, the "one pixel out" minimum step (taken in the larger axis) was under half a pixel vertically, so the
first samples stayed in or next to the centre texel. At those distances a half-texel offset reads as a high horizon. The
pattern is fixed per row and column and does not change between frames, so the 8-frame accumulation cannot remove it.
The existing gtao_preview.py could not show it, because it reads exact per-texel world positions.

Offline repro: `tools/gtao_texel_repro.py` (3840x1080, D24, crash camera 1.6 m up, pitched 28 deg, floor() point
sampling). Open-ground AO^1.5 after the 4x4 bilateral:
- old: mean 0.980, 1st percentile 0.374, 3.75 % of pixels < 0.85. These are full dark rows, identical for 1 and 8
  frames.
- new: mean 1.000, 1st percentile 1.000, 0 % < 0.85. The box contact shadow is kept.

Pickup rule matters. With GPU-style 1/256 subtexel rounding the rows vanish. On a side-sloped plane, though, a
consistent pick still gives a uniform -3.6 % bias that changes with the plane's depth gradient (old 0.964 vs new 0.994).
Because the bias follows each terrain triangle's gradient, it is a candidate (HYPOTHESIS) for the hard-edged wedge. It
is not reproduced as dark as in the shot, and a depth-writing proxy near the rider is not excluded.

Fix (rsx_vk_scenefx.comp, GTAO only; the classic AO path is unchanged):
- Each half-res pixel works at scene texel (2x+1, 2y+1) via texelFetch and that texel's centre.
- Every horizon sample is snapped to its texel and rebuilt at the texel centre. A sample that falls in the centre texel
  is skipped.
- The minimum step is one scene pixel along each slice's own direction.
- The normal comes from texel-centre neighbours (GtNormal).
- The distance stored for the filters is that of the same texel.
- The resolve's reprojection uses the same texel. History and the composite's upsample use the matching +0.75
  half-texel origin, so there is no drift on a still camera.
- Cost: the same number of fetches (texelFetch in place of textureLod).

Build: SPIR-V regenerated with glslangValidator -V (and -DOUT_RGBA16F); spirv-val passes for both. The exe was built
in build/motorstorm-vkgame-100-ppucc2 and copied to vksync/ab2/exe_gt4, sha256
`e81f0951c9549ac759ead9187f104997ca08978b7cdfd87ac0f08c118e15558e`.
Arms: Klt25 (gtao, 8 frames) and Klt25c (old AO), both on gt4; shots build/shots/lt25 and lt25c.
In-game result: not yet run.

## 2026-11-23: Klt26 (exe_gt4) result and the wedge (exe_gt5)

- VERIFIED (Klt26 shots): the cross-hatch on the sand is gone.
- The wedge remains, in Klt26 shot_001867 under the crashed rider. Its outline is a hexagon with hard edges, the shape
  of a box seen from outside. The sand inside it is a uniform x0.89 on all three channels (inside 136/126/97, outside
  154/145/117 RGB) with the same texture contrast.
- HYPOTHESIS (strong): this is the game's decal-volume "dark box" (vksync/GLITCHES.md: blended, depth GREATER, no
  depth write, front faces culled). It is not AO. A draw without a depth write cannot change the depth GTAO reads, and
  the same box appears in Kst1 with no FX at all. RSX_DECAL_SKIP dropped only volume draws with a 16x16 CLAMP B8 map,
  and the crashed rider's box got through.
- Change (rsx_decal_skip.h, rsx_decal_edge.h; Enhanced only, the original look is untouched): the skip now accepts any
  B8 blob map 8..64 texels a side with any wrap (`rsx_decal_skip_unit`; test_decal_edge 19/19). Decal-volume draws
  that are still kept are logged with their units (`[decal-skip] kept a decal-volume draw`, first 6), and so are near
  misses in draw state (`near-miss volume draw kept`, first 6). If the box persists, those lines identify it.
- Exe exe_gt5 sha256 `7c9ecca2baa8888dcbcc106014701f14722296db4d98fc946fb3f349bed9f0ac`; arms Klt27 / Klt27c.

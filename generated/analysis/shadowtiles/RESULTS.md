# World-fixed sun shadows (RSX_SHADOW_TILES), 2026-11-22

Design approved by the user (lighting/FINDINGS.md, "world-tile design"): the shadow at a world point depends only on the
sun and on the casters. Static layer (phase 2), dynamic layer (phase 1), readers through our own helper, fixed world
light space and depth row. Original shadows stay the default; everything here is behind RSX_SHADOW_TILES=1.

## Phase 1: readers, fixed light space and depth row, dynamic layer (built; unrun)
- Code (ps3recomp-vkgame/libs/video): rsx_shadow_tiles_core.h (pure mapping + helper rewrite), rsx_shadow_tiles.h (engine
  glue, included by rsx_light_cascade.h), rsx_vk_shadow_tiles.h (Vulkan: a SAMPLED depth target + a depth view, no copy);
  hooks: rsx_draw_engine.c (8 one-line call sites: xf, fp_alpha, bind_targets depth, viewport, scissor, helper rewrite,
  scene-camera switch, include), rsx_draw_engine.h (2 optional backend ops at the end of rsx_draw_backend),
  rsx_vulkan_backend.c (include + 2 vtable lines), rsx_light_cascade.h (mode flag + dispatch). Wiring: tools/wire_p1.py.
- Mapping: axes e1/e2/d frozen per sun; texel 0.125 m on a grid fixed in the world; depth = (d.p - z0)/4096 + 1/2 with z0
  fixed per sun/track; anchor o (64 m grid) fixed. Every caster draw of all three cascades goes, every frame, into ONE
  map of our own (4095 x 4095 host texels at RSX_RES_SCALE 1.5 = 512 m), window centre = camera position on a 64-texel
  grid, fixed per caster pass (pass = first caster after an atlas reader). 1-texel border kept at the far plane (lit).
  Readers: c4-c7 = (e1,-o1),(e2,-o2),(d/R, 1/2 - z0/R); every lookup entry (or c45-c51) = (2,2,0,0); unit 13 = the map;
  fp_alpha.yzw = (1/(2W), c - o); the rewritten _rsx_shadow13 samples a 2x2 bilinear compare at the casters' (u,v),
  lit outside the window, memoised over the game's PCF taps (they now land within 0.25 mm), receiver bias 0.02 m.
- VERIFIED offline (tests/test_shadow_tiles.c, 469 checks, 0 failed; replay of ab2/shadowcap_k78/k86/k102/k109/k121
  through the same functions; output phase1_offline.txt):
  | capture | passes | caster vs reader worst | fixed world points: texel phase / depth drift | pure turns, window unchanged | game box corners in window near / middle / far |
  | k78 | 443 | 2.7e-3 texel, 1.2e-4 m | 5.3e-5 texel / 0 m | 162 / 162 | 1.00 / 1.00 / 0.13 |
  | k86 | 1189 | 2.9e-3, 1.2e-4 | 1.7e-4 / 0 | 251 / 251 | 0.995 / 0.98 / 0.30 |
  | k102 | 397 | 2.3e-3, 1.2e-4 | 1.2e-4 / 0 | 18 / 18 | 1.00 / 0.90 / 0.01 |
  | k109 | 541 | 2.6e-3, 1.2e-4 | 1.7e-4 / 0 | 7 / 7 | 0.99 / 0.99 / 0.23 |
  | k121 | 156 | 2.4e-3, 1.2e-4 | 6.5e-5 / 0 | 0 / 0 | 1.00 / 1.00 / 0.02 |
  Residuals are float32 rounding of world positions ~1.5 km out. Readers recognised: all but 2 (k109 scene change).
  Game depth range inside the fixed row: always. Window moves are whole texels. Mutation: a window not snapped to the
  grid (camera-following) gives 0.5 texel phase drift and 400 failed checks; a depth-row offset of 1e-5 fails 2.
- VERIFIED offline: all 83 shadow-reading census programs (relight/census) compile after the helper rewrite with the
  game's glslang path (glslangValidator -D -S frag -e main -V), 0 failures.
- NOT VERIFIED: nothing has run. Limits: beyond the 512 m map there are no sun shadows (the game's far cascade reached
  ~800 m ahead; phase 2's static tiles fill that); every caster is drawn as the game sends it (no CPU saving yet); the
  game's own atlas readback/snapshot still happens (unused).
- Exe: build/shadowtiles-link/p1/MotorStormPacificRiftRecomp.exe sha256
  4a26a43060dc395254e5199c935a2be2508013592cbf29f564bb482980d268ff (ppucc2 objects + rsx_draw_engine.c,
  rsx_vulkan_backend.c, rsx_be_thread.c recompiled with generated/analysis/vehfps/tools/shadow_link.py), slot ab2/exe_st1.
- Arm Kst1 (visual-only, before Kbl2a): RSX_SHADOW_TILES=1, RSX_LIGHTING_CASTSTAT=1, 12 shots, READBACK_ASYNC=0, pass log
  passlog_st1.csv. After it: `py -3 tools/passlog_check.py passlog_st1.csv` and the "[shadow-tiles]" stderr lines
  (map made, anchor, per-frame stats: readers not pointed should be ~0, casters left in the atlas ~0).

## Phase 2: static layer (built; unrun) - RSX_SHADOW_TILES_STATIC=1 (with RSX_SHADOW_TILES=1)
- Code: rsx_shadow_tiles_static.h (caster classes + bake draw, included before sink_end_body), rsx_shadow_tiles.h
  (bake rows/origin per pass, toroidal region clears, merge before the first reader, store reset, unit-9 binding),
  rsx_shadow_tiles_core.h (store mapping, toroidal rectangles, region diff, helper with the static layer),
  rsx_vk_shadow_tiles.h + vulkan/rsx_vk_st_merge.frag (R16 store, MIN-blend merge and clear passes). Wiring
  tools/patch_glue_p2.py (engine: 3 call sites + 1 include; 2 more optional backend ops).
- Static = same object constants (the vertex constants above c7 the program reads) and vertex sample for 90 draws, not
  alpha tested (leaves stay dynamic). Such a caster is drawn once more, once, into a bake target (same window, 0.25 m,
  1023 m) and merged MIN into the store: R16, 12288^2 texels of 0.25 m (3072 m, 288 MB), toroidal relative to the
  anchor, resident region = 3072 m centred on the window; depth span 2048 m (3 cm steps). Rebake after 256 m of window
  travel (casters the bake window clipped). A baked caster that later changes (vehicle on the start grid) empties the
  store and never bakes again. Readers: dynamic map inside the window, static store towards its edge (32 m fade) and
  beyond it; lit outside the region. Census (Kfol_a dump, static camera): 58 % of caster draws static, 42 % change.
- VERIFIED offline (1086 checks, 0 failed, phase3_offline.txt): toroidal rectangles cover each texel once with the right
  source (200 cases); region clears = exactly the new region minus the old (300 brute-force cases); bake vs helper
  static lookup worst 9.7e-4 texel, 1.2e-4 m; points that stay in the region never cleared (17608 obs); capture replay:
  bake window always inside the region, fixed world points keep their store texel (0 of 695k changed). The rewritten
  helper with the static layer compiles for all 83 shadow-reading census programs (glslang, 0 failures).
- NOT VERIFIED: nothing has run; R16 blend support is checked at run time (off with a log if missing).
- Exe build/shadowtiles-link/p2, sha256 2640938104a22665b60167b2faf5233d94b42b37651f68170b75ab85ec05bc31, slot exe_st2.
  Arm Kst2 (visual-only): Kst1 + RSX_SHADOW_TILES_STATIC=1, pass log passlog_st2.csv.

## Phase 3: per-track disk cache (built; unrun) - RSX_SHADOW_TILES_CACHE=<dir> (with STATIC)
- rsx_shadow_tiles_cache.h: with the cache on the anchor is the world origin (track coordinates stay within ~0.9 km of
  it in all five captures, so float precision holds), so the toroidal store grid is identical every session; file per
  sun (st_<hash>.bin: basis, depth anchor, region, RLE R16 texels), used only if the basis matches to 1e-7. Saved on
  leaving a track (sun/anchor change) and every RSX_SHADOW_TILES_CACHE_SAVE_S (120; the arms use 40) while new casters
  baked (a readback: ~0.1-0.3 s hitch, HYPOTHESIS), loaded after a fresh anchor. Codec tested (50 random round trips,
  size errors refused). Limit (HYPOTHESIS): a caster that stood still all session and then vanished stays in the file.
- Exe build/shadowtiles-link/p3, sha256 ff8b6228203c38b489b8823429fc3125185cb7c94d0ef0e570f7a77b883dcc76, slot exe_st3.
  Arms Kst3 (fills cache/), Kst3b (starts from it), both visual-only, before Kbl2a.

## Phases 2/3 checked against the runs (2026-11-23)
- VERIFIED (logs, generated/runs/*Kst2*, *Kst3*, *Kst3b*): every arm reached only ~20 s of race (wall 70 s); the static
  store was emptied by "a baked caster changed" 142-193 frames (4.7-6.4 s) after the anchor in all three, again at
  frame 1802 in Kst3b. Cause: a key was static after 90 draws, i.e. ~1 s with three cascades, so the start grid's
  vehicles were baked, and each that drove off emptied the store. Kst3's only save ran 156 ms right after the anchor
  (period counted from process start) and holds a store with 0 covered texels (file 140 B: one far-plane run of
  12288^2); Kst3b loaded that empty store and emptied it again 142 frames later. Phase 3 never carried a shadow.
- VERIFIED (user's play/game.log, Enhanced, RSX_TEX_PBR=1): no "static layer" line: rsx_st_static_on() refused
  STATIC whenever RSX_TEX_PBR was set, silently. The user's Enhanced mode has run phase 1 only.
- UNEXPLAINED (HYPOTHESIS: merge/bake not reaching the store): Kst3's save followed >= 1 merge (dirty > 0) yet read
  back no covered texel. Kst4's probe (store read back every 30 s) and the save/load lines (covered texels) settle it.
- Fixes (ps3recomp-vkgame/libs/video): rsx_st_classify (core, pure): static only after 90 draws AND
  RSX_SHADOW_TILES_STATIC_S (20 s) unchanged; a key that changes once is a mover for the track; the caster table is
  reset when the sun moves. Reset log names what changed and how long it was still. STATIC allowed with RSX_TEX_PBR
  (the helper is written before the PBR rewrite picks a free unit; verify/pbr_static_cli: 83 shadow-reading census
  programs, 73 also PBR-rewritten, 0 PBR maps on unit 9, 0 glslang failures; eng_st_bind_extra never binds over a PBR
  map). Cache v2 (rsx_shadow_tiles_cache.h): files per sun x 4 slots, each with the content fingerprints of its
  casters; a file is used only when enough of the session's first caster keys are in it (rsx_st_cache_verdict:
  another track with the same sun is refused); depth anchor from the candidate; texels uploaded after the verdict,
  every baked key re-merged; saved on leaving a track, after 2 s without casters, and every CACHE_SAVE_S (default now
  0); a mover the file did not have keeps the file; RLE capacity no longer fails on dense stores; save/load log covered
  texels, ms and readback ms; RSX_SHADOW_TILES_PROBE_S diagnostic.
- Tests: test_shadow_tiles 862 synthetic checks, 1105 with the k78/k86/k102/k109/k121 replays, 0 failed
  (verify/offline_tests.txt): start-grid vehicle never static, old rule static after 30 frames, MOVED once then
  black, fingerprint set, verdicts (same track 60 % / 20 % known: used; other track: refused), dense RLE.
- Exe build/motorstorm-vkgame-100-ppucc2 sha256 1facc496990b214c3b12615964abc397b955b2bccf2abd1c30865dea2e19db20
  (shared tree, ninja; slot ab2/exe_st4). Arms (before Klt5t, tools/add_arm_st45.py), RUN_VK_VISUAL_ONLY=1
  RUN_VK_RACE_S=150: Kst4 (auto_drive.py st4 4 6 110; Enhanced + PBR + pack, probe 30 s), Kst5 (st5 4 6 110; fresh
  cache_st5, save every 45 s), Kst5b (st5b 4 1 110; starts from cache_st5). Shots every 90 frames from F9.
- Cache default in Enhanced: NOT yet (no non-empty store has been observed; save hitch at real coverage unmeasured).

## Kst4/Kst5/Kst5b read, and the mesh/instance fix (2026-11-23 evening)
- VERIFIED (logs): merges do reach the store (Kst4 probe 278464 texels at frame 2046). Store emptied by "baked caster
  changed (vertices)" twice in Kst4 and Kst5, each a 6-index quad (pipelines 1382/1384/1506) whose vertices were rewritten
  in place after 32-34 s; Kst5b's single emptying is the anchor's. Coverage stuck at 115573 texels (0.007 km2) in
  Kst4/Kst5/Kst5b: (a) 1569 of 3704 keys were "movers" because the game INSTANCES casters (one mesh, several constant
  sets per frame): foldump_a/b (still camera) 89 of 466 keys cycle 2-6 constant sets every frame; (b) the drive covered
  only 641/906/1065 m of window path (passlog, straight throttle and respawns), not the route.
- Fix: instance = (mesh, object constants, vertex sample), which never changes; motion is a mesh property told by its
  instances (a sampled new instance never drawn again, 3 samples in a row = mover), vertex rewrite = volatile; an
  instance is static after mesh known 20 s, instance seen 4 s / 24 frames, mesh >= 16 vertices/indices. Replay of
  foldump_a/b through the model: 60 movers + 15 volatile of 466 meshes (the AI field), 566 static instances.
  Tests: test_shadow_tiles 863 synthetic / 1106 with replays, 0 failed (instanced rock, instances entering/leaving view,
  8-frame cascade, start-grid vehicle -> mover ~1 s after GO, never baked; quads never static).
- Probe/stat lines now give window path, meshes, movers/volatile, instances, in the store, emptied by movers.
- Exe c9161d3b25060dc9840bcdae30b711990b64947f3c9ae432f3da02b46db478f0 (slot exe_st6). Arms Kst6 (probe 20 s) and Kst6o
  (static off), RUN_VK_VISUAL_ONLY=1 RUN_VK_RACE_S=200, auto_drive.py st6|st6o 4 6 160 (tools/add_arm_st6.py).

## Kst6 read; Kst7 classes and diagnostics (2026-11-23 night)
- VERIFIED (Kst6 log): 844 instances "in the store", every probe 0 covered texels; table saturated at 98304; 782 of
  4078 meshes movers/volatile (Kfol, camera still: 75 of 466). Emptyings: pipeline 1404, 393 indices, "mover" 27.1 s
  known (baked while the bot stood at a wall, camera then moved); pipeline 1404, 126 indices, "volatile" 43.8 s.
  Kst4/5 coverage (278464, then exactly 115573 in two runs) appears tied to the 6-index quads (HYPOTHESIS: only they
  ever rasterised into the bake target); cause of 0 coverage NOT found in code reading (bake path = main draw path,
  merge/readback verified by Kst4's non-zero probe). Kst6o's 3 "GcKernel::Present() Timeout" are at boot (Frame Present
  Counter 0, host 14-29 s, before any caster pass) and also occur in Kmr1/Kmr1o/Kssr1/Klt20c: unrelated.
- Kst7 rules (core rsx_st_mesh_*): mover evidence only with the camera still; 2 vanished samples in a row = unsure,
  never baked; a baked mesh turning unsure with the camera moving is logged and the store kept; one vertex rewrite =
  new content (kept), two within 10 s = volatile; meshes < 16 vertices/indices not tracked; instance 12 s; instance
  table rebuilt at 3/4 (baked or drawn in the last 150 frames kept). Tests 865 / 1108 with replays, 0 failed.
- Diagnostics: RSX_SHADOW_TILES_BAKECHECK=n ("bake check": bake target texels drawn and depth range, dynamic map,
  store covered before/after merge), RSX_SHADOW_TILES_CDUMP (constants of casters with the camera, 4 frames every 90).
- Exe c0fd8d8eba7913a5309b87ede67b640212980cb5c2e32cd8c57680551af0c4a5 (slot exe_st7); arms Kst7, Kst7o after Klt24c.

# ppucc2: main build + PPU lowering only (private)

- Tree: D:/motorstorm/ppucc2/ppu-v100-ppucc2 = generated/ppu-v100-twin (unchanged since 11-15) through
  generated/analysis/ppucc/tools/relift_twin.py `--fast-mem frame --vmx-locals auto` (ps3recomp-opt/tools passes;
  no gateless). Stats: 53278 functions, 2980 vxl, 4845 auto-plain (relift.log). Per-file SHA-256 (tree_sha256.txt)
  identical to generated/ppu-v100-ppucc. VERIFIED.
- Patch markers (tools/markers.py, markers.log): mspr_patch_on 8, mspr_dist_f 12, mspr_slice_ms 22, function count
  53278, equal per TU; the 42 patched lines are textually identical. VERIFIED.
- Gates: test_ppu_fastpath 12 seeds incl. variant vxl_auto_fm_frame, 0 failures (gate12.log). TUs 001 and 064
  (patched) compiled against ps3recomp-vkgame, rc=0 (sample_compile.log). Full build: all 78 PPU TUs compiled, 0 failed.
- Build: tools/build_all_100_ppucc2.cmd use build/pgo103/ms103.profdata -> build/motorstorm-vkgame-100-ppucc2/
  MotorStormPacificRiftRecomp.exe, SHA-256 602568226f0e0287a7d9665bfd8e42d8e0a3b1cecbc71921c958e988523dad6e,
  6m19s (warm LTO cache D:/motorstorm/ppucc2/lto-cache; cold first build 10m46s). Not run.
- vs main (build/motorstorm-vkgame-100-next, 33253d9d...): CMakeCache differs only in RECOMP_DIR and the LTO cache path.
  SPU_LIFT_REGCACHE is cleared: it was added to build_all_100_next.cmd at 11-19 09:15, after the main exe (04:07),
  and a first ppucc2 build with it lifted an extra cbf1b1a1 grp 0x8440 register cache (discarded). Generated SPU
  sources and ppu_hle_nids.cpp are byte-identical to main (only build-dir paths in logs/inventory differ). Env/runtime
  switch strings (556) and wheel strings (50) identical; PS3_SPU_INTERP_REJOIN_RELOC, PS3_SPU_DRAIN_RESUME_RELOC present.
  pcmenu copied from main. VERIFIED (static); runtime behaviour/perf UNVERIFIED.

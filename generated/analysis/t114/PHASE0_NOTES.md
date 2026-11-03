# T114 Phase 0 notes (paused: user switched this session to T115)

- Worktree `ps3recomp-t114`, branch `agent/t114-rsx-geometry-performance` at `e3b961d` (T110 tip).
  Chain: T94 `8ea1437` -> T105 -> T108 `6b1a7e4` -> T110 `e3b961d` -> T113 (black-screen WIP, NOT included).
  T109/T106 SPU work (`b84ed80`) is not in this base. No source changed.
- VERIFIED (offline, `bench_vp_expand`, rebuilt from base, bin in `bin/`): the current vpx path converts
  at 10-33 ns per expanded vertex (1/4/8 attrs). That gives 6-20 ms for 617k vertices, against an in-game
  `expand_ms` of 107 ms. Vertex conversion is therefore NOT most of `expand_ms`; per-draw overhead is
  suspected: about 53 us per draw x 2000 draws.
- Per-draw work inside `expand_ms` (`rfpf_expand_us` = draw callback - early replays - VS compiles):
  - `vp_get_vs`: FNV hash of the VP ucode on every draw.
  - `vp_record_cb`, run on every draw:
    - copies 8448 B of constants to write-combined memory;
    - runs `rsx_fp_extract_consts` over 4096 B of FP ucode;
    - calls `getenv("NO_ALPHATEST")`, `getenv("VP_NOFIXPROJ")` and `getenv("VP_FIXPROJ")` uncached
      (rsx_d3d12_backend.c:3858, 3984, 3985).
  - `vp_attrs_dbg`: calls `getenv("VP_ATTRS")` uncached on every indexed-tris draw (:8897).
  - `upload_tris_vp`: calls `getenv("VTX_DUMP")` uncached (:9110). The quads paths do the same per quad.
  - `vp_get_fp_pso`: linear search with a ucode hash; there are also several FP_* `getenv`s at
    :2710-2863. Check whether they run on the hit path.
  - `vp_make_room` / `vp_draw_want`: walk the strip a second time.
- HYPOTHESIS, ranked:
  1. Cache the uncached `getenv` calls. Byte-exact; Windows `getenv` is O(env size).
  2. Hash the VS and extract the FP constants only when the ucode or address changes.
  3. Indexed + compact upload (bench S4: 3-6x on conversion, but conversion is only about 10-20% of
     `expand_ms`).
  - The real split needs an `RSX_FRAME_PERF` run with per-component timers. No launch is authorized.

# Texture packs: dump, AI upscale, load in game (and PBR maps)

2026-11-05. Vulkan game build. All opt-in; nothing committed. Dumps and packs are game assets: they live
under `build/` (private) and must never be committed or uploaded.

## Pieces

| Piece | Where | Switch |
|---|---|---|
| Dump each distinct texture once | `libs/video/rsx_texture_pack.h`, hooked in `eng_texture_upload` (`rsx_draw_engine.c`) | `RSX_TEX_DUMP=<dir>` (`RSX_TEX_DUMP_MIN` 16, `RSX_TEX_DUMP_MAX` 20000) |
| Upscale + encode + PBR maps | `generated/analysis/vksync/tools/texpack.py upscale --dump D --pack P [--scale 4] [--pbr]` | offline |
| Load the pack | same header and hook | `RSX_TEX_PACK=<dir>` |
| PBR maps for the engine | `texpack.py pbr --pack P` (BC3 `<pack>/pbr/<key>.dds`: normal xy, roughness) | offline |
| PBR lighting from the maps | `libs/video/rsx_pbr.h` (shader rewrite), `rsx_texture_pack.h` (map loading), `rsx_draw_engine.c` (binding, sun estimate, worker upgrade) | `RSX_TEX_PBR=1` (`RSX_TEX_PBR_STRENGTH` 0.6, `RSX_TEX_PBR_UPGRADES` 2, diagnostic `RSX_TEX_PBR_AB=<frames>`) |

- **Key:** `<w>x<h>_<rsx format>_<hash>`. The hash is the engine's 64-bit hash of the guest bytes of
  every level.
- **Dump:**
  - formats RGBA8, BC1, BC2 and BC3, 2D only, fragment units only;
  - level 0 as the GPU receives it, before the unit's crossbar;
  - only a cache entry's first upload, so a texture rewritten every frame is not dumped again and again.
- **Load:**
  - **File:** `<pack>/<key>.dds`: DXT1/3/5 or 32-bit RGBA, with its own size and mip chain, created
    under the same crossbar and guest format.
  - **Sampler:** the LOD clamp is shifted by round(log2(size ratio)). The finest level stays reachable,
    and the coarsest moves down so distant views match.
  - **Unmipmapped guest textures:** sample the replacement's chain down to the guest size.
  - **Vertex units:** never take a pack texture.
- **Tool:**
  - Real-ESRGAN x4plus (realesrgan-ncnn-vulkan 20220424, BSD-3, downloaded to
    `build/thirdparty/realesrgan/`, zip SHA-256
    `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d`) on the RTX 5060; one batch run
    for all textures;
  - scales 2 or 3 are a Lanczos reduction of the 4x output; `--max-size` 4096;
  - alpha upscaled separately (Lanczos); normal maps (mean about (128, 128, 255)) renormalised;
  - full mip chain, BC1 (opaque) or BC3 (alpha) with a PCA-endpoint numpy encoder, or `--format rgba`.
- **`--pbr`:** writes `<pack>/pbr/<key>_n.png`, a tangent-space normal from luminance as height (Sobel),
  and `_r.png`, roughness from local contrast.
  - Slopes are per original texel (the upscaled image's gradient times the scale), at `--strength` 2.
  - `pbr --from-pack <pack> --strength <s>` remakes the maps from the pack's own `.dds` files. The first
    maps measured slopes per upscaled pixel, so they came out nearly flat (median |normal xy| 0.035,
    about 1 % of the light). Remade at strength 8: median 0.135, 275 maps (274 MB); the old ones are in
    `build/texpack/ms2_pbr_v1`.
  - `--blur <texels>` (default 0.5) smooths the height first. Kk67's maps (blur 0.5, strength 8) made
    the sand look hard and crinkled; the user wants it soft. `tools/pbr_preview.py` lights a pack
    texture offline with the race's sun, on vs off, for several settings (it matches Kk67's look at
    blur 0.5, k 2). Chosen: blur 2, strength 12, run at `RSX_TEX_PBR_STRENGTH=1.0` (median |xy| 0.124).
    The strength-8 maps are in `build/texpack/ms2_pbr_v2`.

## Tests

- `libs/video/tests/test_rsx_pbr.c`: 19 checks, 0 failed (the rewrite, the coordinate capture, free units).
  Census: 85 of 133 programs rewritten (73 of the 81 sun-lit), all 85 compile under glslang
  (`tools/build_pbr_test.cmd`), at the same compile time as the originals.
- `libs/video/tests/test_shader_spirv.c`: 34 checks, 0 failed (`tools/build_spirv_test.cmd`; now builds on
  Windows). New: threads asking for the same texts get the same words, and a hit returns while another
  thread translates (mutation: with the old single lock the hit waited 217 ms and the check fails).
- `libs/video/tests/test_rsx_texture_pack.c`: 35 checks, 0 failed. It covers:
  - the key;
  - DDS write and parse for 4 formats with 7-level chains, and a truncated file;
  - the LOD shift and sampler moves;
  - dump once per key and the minimum size;
  - pack listing and load.
- Engine regressions (`test_rsx_draw_engine`, `test_shader_window_engine`) pass. Script:
  `tools/build_res_scale_test.cmd`.
- Encoder (texpack.py, decoded by PIL):
  - BC1/BC3 colour PSNR 33.6 dB, BC3 alpha 60.2 dB on a 512x512 test;
  - RGBA exact;
  - Real-ESRGAN 220x220 -> 880x880 in about 2 s.

## In game

| Run | What | Result |
|---|---|---|
| Kk48 | dump race, RSX_RES_SCALE=1.5 (exe c131cfd4) | 372 textures (66 MB) in `build/texdump/ms2`: 84 at 512x512, 81 at 256x256, 39 at 1024x1024 and others. Contact sheet checked: colours, alpha and normal maps decode correctly |
| texpack.py | `upscale --scale 4 --max-size 2048 --pbr` | 363 replacements (9 too large for the cap), 688 MB, in 11 min (Real-ESRGAN 336 s on the RTX 5060). PBR maps for 275 colour textures |
| Kk49 | race with `RSX_TEX_PACK=build/texpack/ms2` | 256+ textures replaced (e.g. 1024x1024 for 256x256). Race correct in pictures; the ground visibly sharper than Kk47 at the same spot. GPU 9.56 vs 8.98 ms a frame (+0.6). VRAM peak 2.04 GB |

- **VERIFIED:** dump -> upscale -> load works end to end in the race, without wrong or misplaced
  textures.
- **Frame time:** Kk49 p50 40-47 ms vs Kk47 33-34 ms, but the PC was under outside load (SSX Tricky,
  84 % CPU with no game running).
  - The GPU difference is +0.6 ms.
  - The pack's CPU cost is one file load per texture's first upload.
  - A clean comparison is still to be done.
## PBR lighting (`RSX_TEX_PBR=1`)

- **How:** in each sun-lit pixel program, `dot(N, sun)` uses N bent by the pack's normal map at the albedo's
  coordinates (strength 0.6, scaled by roughness). The engine finds the sun as the constant direction most
  programs share, and binds the map on a free unit.
- **Stall fix:** the rewritten programs are new to every cache. Translated on the FIFO thread at race entry,
  they stopped Kk61 and Kk62 with `GcKernel::Present() Timeout` (stacks: NVIDIA compiler, then glslang).
  Now each pipeline is first built with its original program. The backend translates the rewritten one on
  a worker (`shader_ready`), and the pipeline swaps it in on a later use, at most 2 a frame.
  `rsx_hlsl_to_spirv` takes its cache lock only for lookup and insert, so hits never wait for the worker.
- **Trap:** rebuilding `rsx_shader_spirv.cpp` makes every SPIR-V cache file a miss (the build stamp is
  in the header), so race entry goes cold and times out (Kk63). Run `tools/build_spirv_rewarm.cmd`
  after such a rebuild: it re-translates every file from the key stored in it (262 files, 13 s).

| Run | What | Result |
|---|---|---|
| Kk61 | exe 000ad59d, PBR translated inline | Present timeout at race entry; stalled 2 s in the NVIDIA compiler |
| Kk62 | same, SPIR-V cache warm | got further, then the same timeout in glslang (new programs) |
| Kk63 | exe 2b6a1d66, worker | Present timeout: the whole cache was cold after the translator rebuild (0 disk hits) |
| Kk64 | exe 2b6a1d66, originals re-warmed, the 43 PBR programs cold | **race entry + 75 s, 0 stalls.** 64+ pipelines lit, 0 failed; 71 translations all on the worker (FIFO thread: 34 ms of SPIR-V). Race p50 39-44 ms vs Kk49 38-47 ms (outside load both times); one-time driver compiles 2.0 s spread over the race, worst entry frame 968 vs 636 ms |
| Kk65 | exe 2b6a1d66, maps remade (`--from-pack --strength 8`) | race entry + 75 s, 0 stalls, 0 timeouts; 64+ pipelines lit, 0 failed. Stills of a stopped quad (t=...420.9, phase unknown; t=...425.8, off) look the same; the camera moved about 1 px between them, which hides a few-percent change |
| Kk66 | exe 2c9357fe (new log: rewritten draws a frame, and those given a map), strength 2 | race entry + 75 s, 0 timeouts. Race frames 1767-2066: **579 rewritten draws a frame, 441 with a map** (76 %). Frames p50 238 ms late in the race: two Nightfire.exe started in the same minute (outside load), so no timing result |
| Kk67 | Kk66 with on/off every 300 frames | race entry + 75 s, 0 stalls, 0 timeouts, 0 failed. Race: 1468-1678 rewritten draws a frame, 1379-1421 with a map. **Stills of the stopped quad, on (t=...807.9) and off (t=...836.4): the sand shows clear relief only when on.** Ground local contrast 22.1/23.1 on vs 16.4/18.1 off (left/right); the difference follows the texture detail (correlation 0.72-0.77). Frames p50 62-83 ms with Nightfire x2, BF1943 and SSX running: no timing result. Pictures in `build/vksync-tests/pbr_kk67/` |

- **VERIFIED:** PBR on races without stalls, with cold PBR programs.
- **VERIFIED:** the maps reach the race (about 3/4 of rewritten draws get one), and at strength 2 the
  sand's relief is plainly visible on and gone off (Kk67).
- **PARTIAL:** at the default 0.6 (Kk65) the change is a few percent and was not visible in stills.
  The default strength is the user's call. Kk64's flat look came from the near-flat first maps.
- **Not measured:** the frame-time cost of PBR on vs off; Kk66 and Kk67 ran under heavy outside load.

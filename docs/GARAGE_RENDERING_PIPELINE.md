# Garage rendering pipeline: what happens after the archive read (offline, 2026-10-23)

No MotorStorm launch. Evidence:
- run `generated/runs/20261023-134457-garage-read/` (exe `8bc4932e…`);
- the 2026-10-21 no-skip run `generated/logs/menu-long-20261021-*` with frames `generated/frames/menu-long-20261021/`;
- the RSXI capture `generated/rsxi/smoke1/` (loading-emblem stage, frames 718 and 723);
- ps3recomp-int source.

Labels: **VERIFIED** (seen in a log, frame or capture), **INFERRED** (follows from code or order), **UNKNOWN**.

## Boundary (VERIFIED, garage-read run)

| Event | s |
|---|---|
| Intro closed (`[fs] close fd=6`, by `func_00667558+0x12B98`) | 30.88 |
| `/gui/loadscreen-garage.gui` fully read | 31.24 |
| `/worlds/track_garage.rpk` first read | 31.78 |
| `/worlds/track_garage.rpk` fully read (23,207,184 B) | 34.24 |
| Runner stop (target milestone, not a crash) | 34.26 |

At the stop, the game was reading `/env/Track0a_Garage_Sky1_driver.rpk` (archive 244,169,081 + 8,650,343 B stored). The last read was at 250,027,956 (5.9 MB into it).

## Stages after the archive read

| # | Stage | Guest side | Native side | Observable event | Instrumented | Seen at runtime | Silent failure possible |
|---|---|---|---|---|---|---|---|
| 1 | Sky package read | FIOS `func_00667558` | `cellFsRead` | `[fsread] fd=5` in [244,169,081, 252,819,424) | yes: `garage_sky_read_complete` (span_read) | partial (VERIFIED, 5.9 of 8.65 MB) | no (short reads are logged) |
| 2 | Remaining garage files | FIOS; loose probes `_ain/_cps/_gan_objects`, `.jump/.bin/.spvs/.gvl`, `default.gags` | `cellFsOpen` → ENOENT | `[fs] open FAIL … (by …)` | yes (`FS_CALLER=1`) | in the skip run, after the world read (VERIFIED) | no |
| 3 | SPU decompression | FIOS → SPU zlib (image `482286362`, entry `0xF98780`, STATUS 2026-10-21) | SPURS tasksets, LFQueue | FIOS wait `func_0065B460` completes; `[spu_workload]` lines | indirect only | for earlier members (VERIFIED); for garage members UNKNOWN | **yes**: a wrong decompressed block is not checked anywhere |
| 4 | Resource parsing (`.rpk`) | game code, address UNKNOWN | — | none | **no** | UNKNOWN | **yes** |
| 5 | Texture and mesh creation | game copies into RSX local/main memory (INFERRED) | guest memory only | none until a draw samples it | no | UNKNOWN | yes |
| 6 | GPU upload | — (PS3: RSX reads guest memory) | D3D12: `vp_upload_tex_slot` uploads from guest memory when a replayed draw samples it (checksum cache) | `TEXUP_DBG`, RSXI `tex` per unit | RSXI (per captured frame) | for the loading page and intro (VERIFIED); garage UNKNOWN | yes: a texture never written reads as zero or stale |
| 7 | Shader translation and compile | game binds a fragment program (`SET_SHADER_PROGRAM`) | `vp_get_fp_pso` (`libs/video/rsx_d3d12_backend.c`): decompile → `[CUBE]` patch → `D3DCompile` → PSO | `[CUBE] fp=` (before the compile, first 4); `[FP]` results on stdout (first 16/32) | **new**: `RSX_SHADER_TRACE` (`translated`, `compile_fail`, `pso_fail`, `pso_ready`, `bound`, `fallback`) | the cube programs `0x4D81101`, `0x4D81881`, `0x4D82241`, `0x4D82F81` in the 2026-10-21 run (VERIFIED, `[CUBE]` only); none in the garage-read run | before: a failed program drew with the fallback shader, with no line after the first 16; now `fallback` |
| 8 | Garage scene initialisation | game code | — | first cube-program draw (INFERRED proxy) | `first_cubemap_draw` (trace) | UNKNOWN | yes |
| 9 | Frontend loading-state transitions | GUI (`loadscreen-garage.gui`, `GotoGarage`) | — | page member read (VERIFIED); state change UNKNOWN | read only | page read (VERIFIED) | yes |
| 10 | First visible garage or menu frame | — | `Present` | heartbeat `draw_frames`, RSXI backbuffer | RSXI; **new**: a failed `Present` is logged | the emblem/artwork screen in the 2026-10-21 run (VERIFIED, frames 22–23) | before: a failed `Present` was ignored |

## Facts used above

- **No shader failures (VERIFIED):** 0 `PS compile FAIL`, 0 `PSO FAIL` and 0 `decompile fail` in the 2026-10-21 run (32 programs ready) and in the garage-read run (13). These lines are always printed for the first 16 failures.
- **First cube program (VERIFIED, 2026-10-21 run):** `[CUBE] fp=0x4D81101` at stderr line 49,592. That is after the `track_garage` loose probes (line 48,098–48,118). No cube program appears before the garage load.
- **`[CUBE]` meaning (VERIFIED, source):** it is printed while the HLSL is patched for cube samplers, before `D3DCompile`. It shows the translation was attempted, not that the program compiled, got a pipeline or drew. The old milestone name `garage_rendering_started` overstated this.
- **The post-FX chain exists from the intro on (VERIFIED):** `fp 0x007400C1` and `0x0074D0C1` (the luminance chain) are among the first pipelines built, at stdout line ~2540 of the 2026-10-21 run, during the intro. The RSXI capture `smoke1` shows `fp 0x0074C781` with the Rec.709 luma weights (0.2126, 0.7152, 0.0722) in c4, and present program `0x02193941`.
- **Occlusion queries (VERIFIED):** from boot the game issues `GET_REPORT type=1` (ZPASS) into main memory (`dma=0xFEED0001`, offsets `0x14100–0x14130`). The walker answers each with a fixed `0xFFFF` (`libs/video/cellGcmSys.c`); sample counts are not measured.

## First concrete defect

None identified at runtime. The leading candidate downstream is the white-to-black problem (`WHITE_TO_BLACK_INVESTIGATION.md`). Two diagnostic gaps are now closed:
- the shader lifecycle was invisible past the first 16/32 lines (`RSX_SHADER_TRACE`);
- `Present` failures were ignored.

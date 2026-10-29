# T157: unified performance status (T153 preset + T154 Wws AOT + T155 texture cache)

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. Game results: `HEAVY_SCENE_AB_RESULTS.md`. Next step: `NEXT_CRITICAL_PATH.md`. Nothing pushed or merged; no default changed.

## 1. Answer

- **The texture-cache fix removes the heavy-scene texture bottleneck in the game (VERIFIED, one valid B run):**
  - texture time per heavy frame falls 216 → 5.6 ms, with 0 dropped binds and 0 evictions;
  - heavy scene 2.35–3.29 → **7.44–7.60 FPS**.
- **Light scene: unchanged** by the switch.
- **Neither scene reaches 30 FPS.** Light is 14.4–19.8 FPS, limited by the PPU (Havok wait); heavy is 7.4–7.6 FPS, limited by RSX vertex expansion and recording.
- **`RSX_TEX_SLOTS=1024` alone is not acceptable.** It keeps a font atlas stale: "Press ⓧ to Skip" lost glyphs in both B runs. This is VERIFIED in game and reproduced offline.
- **Candidate B' fixes that offline:** `RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1`, which re-checks kept textures with an exact hash.
- **One B run also hit a first-ever FIFO desync, still unexplained.** Before B' can be considered for any default it needs its own authorised A/B.

## 2. Source commits

| Tree | Branch | Commits |
|---|---|---|
| ps3recomp integration | `integration/t157-performance` (worktree `ps3recomp-t157-performance`) | `c1512fb` (T155 = T154 `e8e972a` = T153 `2a764e1` + `PS3_SPU_WWS_STATS`, then `746ff2c`, `f514913`, `c1512fb`) → **`c535cc0`**, a merge of T156 `756c1e1` (`031bbb5` `PS3_SPU_TASK_POOL`, `756c1e1` `PS3_SPU_TASK_STATS`) → `59fcab5` (test only: partial-write mode of `test_t155_texslots`) |
| root reports | `agent/t157-performance-report` (worktree `root-t157`, from T155 report `8188dee`) | this report + `HEAVY_SCENE_AB_RESULTS.md`, `NEXT_CRITICAL_PATH.md`, `tools/*.py` |

**Ancestry and conflicts (VERIFIED).**
- T155 and T156 both branch from `e8e972a`.
- T155 touches `libs/video/rsx_d3d12_backend.c`, `libs/video/tests/test_t155_texslots.c` and `tools/test_t115_pins.py`.
- T156 touches only SPU runtime files, `ps3_ftrace.h` and its tests.
- No file overlaps, and the merge was clean.
- T156's switches stay off unless set (`PS3_SPU_TASK_POOL`, `PS3_SPU_TASK_STATS`), so T156 remains separately measurable and is **not** in the benchmark configuration.

## 3. Executables

| Use | Path | sha256 | Launched |
|---|---|---|---|
| T155 A/B (both arms) | `build/motorstorm-t155` (`c1512fb`), `t155/ab/exe_f` | `d8483b4a3ed18907b232ca2e8b18a648980a6f53f860241e5a6ffb6559ef1c6c` | 4× (T155 authorisation) |
| **T157 unified build** | `build/motorstorm-t157` (`c535cc0`, `MSPR_WWS_AOT=ON`, port `port-t155`, `tools/build_t157.cmd`; 312/312, rc 0) | **`959ebd3152c100f689ecafbc388e5b90ef3227a763dc14f189a7aa8f065aa629`** | **no** (needs approval) |

`59fcab5` changes only a harness test, so the game exe at `c535cc0` stands for the branch head.

## 4. Benchmark configuration (unchanged defaults)

| Layer | Switches | Status |
|---|---|---|
| T153 verified preset | `PS3_TEX_SNAPSHOT_EPOCH RSX_VP_COMPACT RSX_SHADER_CACHE RSX_SRV_REUSE RSX_BIND_DEDUP PS3_SPURS_EVENT_SCHED` = 1, + `PS3_TEX_SNAPSHOT_WWATCH=1` | VERIFIED (T153) |
| T154 Wws AOT | build `MSPR_WWS_AOT=ON` + `PS3_SPU_WWS_AOT=1` | VERIFIED (T154: race start 10.9 → 21.1 FPS) |
| T155 texture cache | `RSX_TEX_SLOTS=1024` | heavy +2.3–3.2× VERIFIED; **stale text: rejected as is** |
| T157 candidate B' | `RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1` | offline VERIFIED (below); game BLOCKED (needs approval) |
| T156 | `PS3_SPU_TASK_POOL`, `PS3_SPU_TASK_STATS` | in the code, off; separate A/B |

## 5. Offline regression (integration tree `c535cc0`/`59fcab5`)

| Set | Result |
|---|---|
| full suite (`tools/run_all_t157.cmd --jobs 6`, `logs/suite.txt`) | **138 PASS / 43 SKIP / 2 FAIL**. The 2 are the known `test_rt_pool_srv_layout` and `test_vpc_watch`. T155 alone was 137 PASS, and T156 adds its own passing tests. No new failure; `test_spurs_wws_concurrency` passed this time |
| GPU regression set with the D3D12 debug layer (`tools/harness/t157/correct.sh`: off = `RSX_NONE=1`, on = B'; 16 configurations × off/on/rerun: draw path fat/compact/preset/visual/GBV, descriptor reuse, RT window/feedback/zeta/MRT/depth, MSAA, shader window, RT sampling, stencil) | **32/32 on-arms identical to off on every captured pass; 48/48 runs with 0 debug-layer errors** (`logs/correct.txt`) |
| stale-texture set (`tools/harness/t157/correct_partial.sh`, debug layer on) | B (1024, sparse checksum) **stale on 4 of 8 passes**; B' identical to the never-reuse reference on 8/8 passes (×2); 0 errors |
| exact-hash cost (`tools/harness/t157/perf_texcache.sh`, 3 repeats) | heavy synthetic texture ms 3.53 (1024) → 4.45 (B', `RSX_TEX_CACHE=1`) / 4.47 (`=2`); light 0.53 → 0.56 |

Note: the suite rewrites `scratch/ppu_conformance*` in the tree it tests (known); those files are left uncommitted.

## 6. Status by scene (best valid runs, race-frame matched)

| Scene | FPS | p50 / p95 / p99 ms | Limit | Gap to 33.3 ms |
|---|---|---|---|---|
| light (race frames 40–499) | 19.78 (fast host) / 14.4–14.7 (after drift) | 49.5 / 57.8 / 80.4 (Ar1) | PPU frame thread: Havok wait 18.6 ms, RSX idle 21 ms | 17 ms |
| heavy (race frames 600+), B | 7.44–7.60 | 128 / 158 / 170 | RSX thread: expansion 67 ms, recording 34 ms; PPU waits 36 ms on RSX | 98 ms |

## 7. Open items

- **Br2 FIFO desync** (HYPOTHESIS; `HEAVY_SCENE_AB_RESULTS.md` §5.3). Reproduce it offline before any further B or B' run.
- **Heavy-scene visuals are not captured**, so the repair of the 3,500 dropped binds per frame is not visually confirmed (BLOCKED).
- **Host drift:** about 25 % after the first run, plus another project's GPU process. Future A/Bs need a quiet host and should keep the interleaved order.
- **Texture memory:** about 1 MB per kept texture. A byte budget and upload-buffer release are needed before anything targets the Radeon 890M (`NEXT_CRITICAL_PATH.md` §3).

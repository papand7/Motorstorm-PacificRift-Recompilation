# MotorStorm: Pacific Rift — next major performance optimization

2026-10-30. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. No merge, no push. Runtime launches in this task: only the authorised T161 C1→D1→C2→D2 comparison. The in-game A/B of the change below is prepared, not launched (§9).

## 1. Baseline environment and hashes

| item | value |
|---|---|
| host | AMD Ryzen 5 9600X (6 C / 12 T), 47.1 GB RAM, NVIDIA GeForce RTX 5060 (driver 32.0.16.1088) + Radeon iGPU, Windows 11 Pro 26200 |
| host load | SSX Tricky (another project) ran throughout at about 0.5 cores; load before each launch 8–18 % |
| baseline exe | T161 V5 `b1fdb0bd6253d11cd837bbc1a37db22a2dd2e9c5ad66d670e4aac24d3d8c01fc` (`build/motorstorm-t161-x`) |
| baseline ps3recomp | `agent/t161-fast-race-benchmark` `afdcabd` |
| baseline environment | T161 arm C = `ENV_LEAN` (T153 preset, `PS3_TEX_SNAPSHOT_WWATCH=1`, Wws AOT, Wws stats), `PS3_LWCOND_WAKE` unset |
| toolchain | clang-cl 23.1.3, MSVC 14.51, Release, Havok `--chain-chunks`, `MSPR_WWS_AOT=ON` |
| optimization branch | ps3recomp `agent/perf-next-tex-residency` (worktree `ps3recomp-perf-next`), see §5 |

**Baseline numbers (T161 arm C, 2 runs, VERIFIED):**
- race entry 124.0 / 121.4 s;
- light race scene (frames 40–499): 20.70 / 20.95 FPS; p50 47.4 / 46.9 ms, p95 53.1 / 53.8 ms, p99 62.9 / 66.2 ms;
- heavy scene (frames 600–690): 3.65 / 3.35 FPS; p95 304 / 317 ms, p99 342 / 353 ms; about 6,960 draws per frame;
- CPU in the light race: 2.87 / 2.96 cores; peak working set 645 / 642 MB.

## 2. Methodology

- **Phase 0, T161 (authorised, VERIFIED):** 4 sequential launches C, D, C, D. All of them used the same pinned exe, fast pacing, fresh HDD copies, race stop at entry + 150 s and the 195 s cap. Results are in `t161/FAST_RACE_BENCHMARK.md` §16. Frames are matched by race-frame index (`bench_t161.py`): light = frames 40–499, heavy = 600 to the last frame every run reached.
- **Phase 1, profiling:** no new launch. The ranking uses the already recorded per-pass RSX counters (`[rsx-frame-perf]`, `[tex-rec]`), guest wait sites (`phase_sites`), Havok wave timelines and SPU task statistics from T154–T158, plus the T161 runs above.
- **Offline validation:** the real D3D12 backend in the synthetic heavy-frame harness `test_t155_texslots` (the heavy frame shape: 6,900 draws as 4 passes, 300 textures). It runs with the D3D12 debug layer, RSXI per-pass snapshots compared against a re-upload-always reference, and timing repeats without the debug layer.

## 3. Ranked bottlenecks (top 5)

| # | bottleneck | scene | evidence | potential | correctness risk |
|---|---|---|---|---|---|
| **1** | **The 96-slot texture upload table overflows.** Each of the 4 passes evicts textures the next pass needs again: 227 evictions, 193 re-creations and 3,542 binds without a texture per frame. | heavy | `vp_upload_tex_slot` takes 208–218 ms of a 255–300 ms frame (T155 §3, T157 Ar1). The PPU then waits 223 ms per frame on the RSX reference throttle `0x72E1E0`. | **Heavy 3.3–3.6 → 7.4–7.6 FPS (2.1–2.3×), measured with `RSX_TEX_SLOTS=1024`** (T157 Br1, 1 run) | Sparse `tex_csum` misses partial writes (stale font atlas, VERIFIED in game). Memory is about 1 MB per kept texture. One unexplained FIFO resync in 2 runs (HYPOTHESIS). |
| 2 | Vertex expansion and upload: 244 B per vertex, 414k vertices and 101 MB per frame. `RSX_VP_COMPACT` covers only indexed strip and fan draws. | heavy (after #1) | 53 ms (now) → 67 ms per frame once #1 is fixed, of a 132 ms frame (T157 §3) | 30–50 ms per heavy frame, +30–60 % heavy FPS after #1 (HYPOTHESIS) | Vertex attribute formats and skinning (bone indices in attribute 7, constants from c[64]) |
| 3 | Havok SPU chain: the PPU main thread waits 17.5 ms per frame. 16.5 ms of the chain is lifted SPU execution (solver about 7.9 ms, collide about 8.4 ms). | light | T154 §1, T156 §2–3, T158 C1 | A few ms per frame through SPU codegen (register cache); `--chain-chunks` gave +6.1 % | SPU/PPU memory ordering |
| 4 | Record-side PSO lookup and command recording | heavy (after #1) | 27 ms per frame (commands 15.4, PSO 11.4) of `render_frame`'s 34 ms record (T157 §3) | 10–20 ms per heavy frame (HYPOTHESIS) | RSX state ordering |
| 5 | Load-time lwcond polling (1 ms `Sleep` per wait) | load | T161 §16: race entry 122.7 → 41.9 s with `PS3_LWCOND_WAKE` | **−66 % load time (VERIFIED)**, but −2.8 % light FPS and +0.9 cores | none found in 4 runs; kept opt-in |

Ignored, with reasons:
- GPU time: GPU wait is about 0 everywhere, so the GPU is not the bound.
- D3D12 submission and sync: one `ExecuteCommandLists` per pass, and `wait_for_gpu` at pass start is short because the GPU is idle.
- Shader and pipeline compiles: 0.25–0.3 s per 460-frame window, outside the measurement windows.
- Logging: the fast profile writes 920 lines/s.

**Largest single bottleneck: #1.** It costs about 70 % of every heavy frame, and #2 and #4 only start to matter once it is gone.

## 4. Selected optimization and rationale

**Texture residency for the heavy scene: a large indexed LRU texture table (T155 `RSX_TEX_SLOTS`), made exact and bounded.**
- **Why this one:** it is the only item whose speedup was already measured in game (2.1–2.3× heavy FPS). It is also a prerequisite: until it is fixed, every other heavy-scene fix is hidden behind 210 ms of texture churn.
- **Why it was not yet usable:** T157 rejected it as is.
  1. It made the sparse-checksum blind spot visible: a partly rewritten font atlas stayed stale.
  2. It keeps about 1 MB per texture, half of that in a CPU-side upload buffer that is never released.
  3. The exact hash that fixes 1 (`RSX_TEX_CACHE=1`) re-reads every byte of every kept texture at its first bind in each pass. In game that is 454 validations over 65.7 MB of guest data per heavy frame (T157 Br1 `[tex-rec]`).
- **This task adds the two missing pieces** (§5):
  - an exact zero-hash validation path from Windows write-watch generations;
  - a texture memory budget that releases upload buffers and LRU textures.
- Together with `RSX_TEX_SLOTS=1024` and `RSX_TEX_CACHE=1`, these form the configuration proposed for the in-game A/B (arm T, §9).

## 5. Implementation and changed files

**ps3recomp `agent/perf-next-tex-residency`** (worktree `ps3recomp-perf-next`, based on T161 `afdcabd`):

| commit | content |
|---|---|
| `bedd499`, `73cc5f7`, `b4bf4e2`, `dba180a` | cherry-picks of T155/T157 (`746ff2c`, `f514913`, `c1512fb`, `59fcab5`): `RSX_TEXREC_STATS`, the indexed LRU table `RSX_TEX_SLOTS`, and the partial-write test mode |
| **`a049b1e`** | **new:** `RSX_TEX_WWATCH`, `RSX_TEX_BUDGET_MB`, and the write-watched arena in `test_t155_texslots` |

Changed files: `libs/video/rsx_d3d12_backend.c` (+160 lines) and `libs/video/tests/test_t155_texslots.c`.

- **`RSX_TEX_WWATCH=1`.** Needs `RSX_TEX_CACHE=1|2` and the `PS3_TEX_SNAPSHOT_WWATCH=1` reservation, which is already in the benchmark preset.
  - Each kept slot stores the write generation that was harvested (`ps3_wwatch_gen`, shared with the T150 snapshot store) **before** its bytes were last hashed or decoded, plus the span that was covered (all faces and levels).
  - On a lookup, if no page of that span has a newer stamp, the slot is valid without hashing. Otherwise the slot takes the existing exact-hash path.
  - Sources from a draw-time snapshot, and lookups the write-watch can't answer, always hash.
- **`RSX_TEX_BUDGET_MB=<n>`.** Needs `RSX_TEX_SLOTS > 96` and `RSX_TEX_CACHE`. At every pass start, after `wait_for_gpu` and the per-pass reset of the slots' bound flags:
  - upload buffers of slots not re-uploaded for 8 passes are released, and re-created on demand;
  - while the textures' size estimate exceeds the budget, the least recently bound slot that the previous pass didn't bind is released.
- **Defaults:** all switches are off. Unset is the T161 code path byte for byte, apart from two unused struct fields and a static array.
- **Proposed arm T:** `RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1 RSX_TEX_WWATCH=1 RSX_TEX_BUDGET_MB=1024`.

**Root (private, `generated/analysis/performance_next/`):**
- `tools/harness/{correct_ww.sh, perf_ww.sh, common/*}`
- `tools/cmp_snaps_next.py`, `tools/perf_ww_summary.py`
- `tools/make_runner_next.py` → `ab/run_next.py`
- `tools/build_next.cmd`, the shell harness and `ab/` (exe, runner, sequence) are gitignored by the `generated/analysis/*/tools/*.py` rule and stay local; only the `.py` tools and this report are committed

## 6. Offline tests (VERIFIED)

**Correctness** (`tools/harness/correct_ww.sh`, D3D12 debug layer, RSXI snapshots of passes 8–15, `logs_correct_ww.txt`):
- 4 cases: full rewrites inside pass 2; partial rewrites that `tex_csum` never samples (the font-atlas shape); no rewrites; sparse binds (batch 64) so the budget evicts.
- 6 arms per case: `ref` (`TEX_NOCACHE=1`, re-upload at every pass), B', `ww`, `ww` + `RSX_TEX_CACHE=2`, `ww` + 16 MB budget, and a `ww` rerun.
- **24 / 24 runs rc 0 with 0 debug-layer errors or warnings and 0 dropped binds. 20 / 20 arms are identical to `ref` on 8 / 8 pass snapshots.**
- Write-watch: 5,400 checks per run, 4,900–5,400 answered without a hash, 0 unanswered.
- Budget arm: 146–300 upload-buffer releases, 29–200 re-creations, and in the sparse case 376 texture evictions (23.3 MB), all identical to `ref`.

**Timing** (`tools/harness/perf_ww.sh`, no debug layer, 3 interleaved repeats, median of frames 3+; `logs_perf_ww.json`):

| synthetic frame | 96 slots (baseline) | 1,024 slots, sparse | + exact hash (B') | **+ write-watch** | + write-watch + budget |
|---|---|---|---|---|---|
| heavy (6,900 draws, 300 textures): texture recording, ms | 262.2 | 3.15 | 4.30 | **1.80** | 1.80 |
| heavy: whole record step, ms | 269.8 | 10.3 | 11.7 | **8.9** | 8.8 |
| light (2,000 draws, 80 textures): texture recording, ms | 0.70 | 0.50 | 0.60 | 0.50 | 0.40 |

- Write-watch makes exact validation **58 % cheaper than the hash it replaces, and 43 % cheaper than the inexact sparse checksum**.
- The repeats spread by at most ±0.15 ms, except the 96-slot arm at about ±7 ms.

**Suite** (`run_all_t157` on `ps3recomp-perf-next`, `suite_perfnext.txt`):
- 141 pass / 43 skip / 2 fail.
- Both failures are pre-existing and unrelated: `test_rt_pool_srv_layout` gives the same `[FAIL]` on the T161 tree, and `test_vpc_watch`'s harness fails to compile because of a missing `<time.h>`.
- T161's third failure, `test_spurs_kick_wake`, passes here, which supports the T161 host-load HYPOTHESIS.

## 7. Before / after

**In game: BLOCKED.** The A/B launches need authorisation (§9). The numbers below are what exists so far.

| metric | baseline (T161 C, 2 runs) | `RSX_TEX_SLOTS=1024` only (T157 Br1, 1 run, other exe and host state) | expected, arm T | basis |
|---|---|---|---|---|
| heavy FPS | 3.50 (3.65 / 3.35) | 7.44–7.60 | **≈ 7.5 (+110 %)** | Br1, plus about −1.4 ms record for exact write-watch validation instead of the sparse check |
| heavy frame time avg / p95 | 286 / 310 ms | 131.7 ms avg | ≈ 130 ms avg | same |
| heavy RSX texture time | ≈ 210 ms | 5.6 ms | ≈ 4–6 ms | synthetic 1.8 ms; in game it also includes SRV writes |
| heavy PPU wait on the RSX throttle `0x72E1E0` | 223 ms | 35.6 ms | ≈ 35 ms | Br1 |
| light FPS | 20.83 | unchanged (T155/T157) | unchanged | the light scene is PPU-bound (Havok wait) |
| draw calls | 2,004 / ≈ 6,960 | unchanged | unchanged | no draw is skipped or added. 96 slots drop about 3,500 texture binds per heavy frame; 1,024 slots bind them |
| GPU memory | — | +143 MB dedicated, +127 MB private (233 kept textures) | ≤ budget (1 GB) for textures; upload buffers released after 8 idle passes | T157 §5, `[tex-budget]` |

Going from 3.5 to about 7.5 FPS is well above the 20–30 % target, but only for the heavy scene. The light scene and race entry don't change: the light scene is limited by the Havok wait, and race entry by the lwcond polling, which is kept opt-in (§3 #5).

## 8. Correctness checks

- **Exact texture contents.** The same bytes as a re-upload-always reference on every snapshot pass, including partial writes and sparse-bind eviction (§6). The write-watch check is stronger than the hash: it answers "no byte written", and anything it can't answer falls back to the hash.
- **Ordering.** The generation is taken before the bytes are read, so a guest or SPU write during the hash or decode is caught at the next lookup. Write-watch records PPU and SPU stores, host `memcpy` (SPU DMA, RT write-back) and file reads into the arena (T150 probe).
- **Lifetime.**
  - Resources are released only at pass start, after `wait_for_gpu` and before any slot is bound.
  - A slot bound in the current pass is never replaced.
  - Recreated upload buffers are only ever copied for subresources that were refilled (`RSX_TEX_CACHE=2` keeps its dirty mask).
- **Simulation and timing:** no guest-visible change. Texture slots never write guest memory or FIFO state.
- **Vertex attributes, constants, skinning, RSX push-buffer and SPU command buffers:** untouched by this change.
- **Fidelity.** Arm C's 96 slots leave about 3,500 binds per heavy frame with no texture. Arm T samples them, so heavy frames **will differ from the baseline**, and should, towards the correct image. The garage and the race must be checked visually from the CELLMARK dumps (12 per run). The "Press ⓧ to Skip" overlay is the known stale-atlas canary (T157).
- **Open risk (HYPOTHESIS):** T157's one FIFO resync in 2 `RSX_TEX_SLOTS` runs. Pass criterion: 0 resyncs in the A/B.

## 9. Limitations and next step

- **Limitations:**
  - The speedup is not yet measured in game for this exe.
  - The synthetic textures are 64–256 texels, while the game's average is about 145 KB per validation. The write-watch saving should therefore be larger in game, but that is a HYPOTHESIS.
  - The budget is enforced per pass, not per allocation.
  - The host was not idle (SSX at about 0.5 cores) for any measurement.
- **Prepared, needs authorisation:**
  - **Exe:** `build/motorstorm-perfnext-tex/MotorStormPacificRiftRecomp.exe`, from `tools/build_next.cmd` (T161 recipe, ps3recomp `a049b1e`), pinned by `ab/run_next.py prepare n` (SHA in §9a once built).
  - **Arms:** **E** = T161 arm C environment on the new exe (all new switches off; must reproduce C) and **T** = E + `RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1 RSX_TEX_WWATCH=1 RSX_TEX_BUDGET_MB=1024`.
  - **Order:** E1, T1, E2, T2: 4 sequential launches, no retries, hash checked before each.
  - **Runs:** fresh HDD copy per launch, fast pacing, race stop at entry + 150 s, 195 s game / 210 s host caps, GPU watchdog, 12 CELLMARK dumps.
  - **Instrumentation:** existing only: `[rsx-frame-perf]`, `[tex-cache]` / `[tex-budget]` counters, `performance.json`. Nothing new, and nothing in production defaults.
  - **Measures:** light (frames 40–499) and heavy (matched frames 600 to the last frame both arms reach) FPS, 1 % low, avg / p95 / p99 frame time; CPU cores per phase and top threads; draws; PPU waits at the RSX throttle; peak working set and private memory; FIFO resyncs.
  - **Pass criteria:**
    - route and race reached in all 4 runs;
    - E within the T161 C spread;
    - T: heavy FPS ≥ +20 % over E, light FPS within E's spread, 0 FIFO resyncs, 0 new error categories, the same draw counts;
    - no stale overlay glyphs or other visual regressions in the dumps;
    - texture memory within the budget.
- **After that:** bottleneck #2 (heavy vertex expansion, about 67 ms of the then 132 ms frame) becomes the largest. The next step is to extend compact vertex upload beyond indexed strips and fans.

### 9a. Prepared executable

- `build/motorstorm-perfnext-tex/MotorStormPacificRiftRecomp.exe` → `ab/exe_n`, **SHA-256 `0304156bac3e6553b23cbb3ea24763c90f33b4c3aae01ac725ddf2a8ad3449b3`**.
- Release, clang-cl 23.1.3, 312 / 312 build steps, 0 errors (`build_next.txt`), from ps3recomp `a049b1e`.
- Launch script: `ab/seq_et.sh`. It checks the hash before each launch and logs host load to `ab/seq_et.log`. **Not run.**

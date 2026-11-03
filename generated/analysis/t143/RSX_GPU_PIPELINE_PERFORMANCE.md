# T143: RSX/D3D12 GPU pipeline performance

Date: 2026-10-28.

- **Branch:** `agent/t143-rsx-gpu-pipeline-performance`, worktree `ps3recomp-t143-gpu`, based on `07b453f` (T141 tip; contains T113, T120, T133, T137, T141).
- **Worktree note:** `ps3recomp-t143` already existed: created at 13:42 on `agent/t143-rsx-performance-audit` (at `07b453f`, no commits, clean), plus empty `generated/analysis/t143/{logs,tools}` from 14:57. It was left untouched, and the new worktree uses a different path. No branch or worktree was deleted.
- **Scope:** offline only. No game build or launch, no merge, no push, no GitHub. A temporary detached worktree `ps3recomp-t143-base` (at `07b453f`, plus an untracked copy of the bench source) holds the base build of the bench; it was left in place (no worktree deletion) and can be removed with `git worktree remove --force ../ps3recomp-t143-base`.
- **Commits:** `e2f9435`, `efae357` (see §4).

Labels: VERIFIED / PARTIAL / HYPOTHESIS.

## 1. Baseline and methodology

**Renderer baseline: `07b453f`.** It is the newest tip that contains the fidelity work T120, T133, T137 and T141, and it is the common base of T142 and T144. The performance branches T119 (`693169a`), T122 (`2b639c2`) and T116 (`30b817b`) fork earlier, at `2562ba8`, and are not merged anywhere. They are treated as integration dependencies (§8), not as part of the baseline, because merging them was out of scope.

**Instrumentation (new, opt-in): `RSX_GPU_PROF=<frames per report>[,<max reports>]`.**
- **One record per `render_frame`.** Report 0 is the warm-up and is dropped from every figure below.
- **CPU, from QPC on the render thread:**
  - drain (the `wait_for_gpu` at frame start);
  - pre-pass (texture uploads, SRV windows, PSO lookups), with the SRV window fill timed separately;
  - replay loop (command recording);
  - post;
  - `Close` + `ExecuteCommandLists`;
  - `Present`;
  - next-frame fence wait;
  - total time in every GPU wait.
- **GPU, from four timestamp queries in the frame's main list:**
  - the timestamps are begin, loop start, loop end and end;
  - they are resolved before `Close` and read after the next frame's drain;
  - "GPU idle" is the queue gap from the last frame's end to this frame's begin, so it includes the present and any vsync wait.
- **CPU and GPU times are never mixed.**
- **Counts:** every D3D12 call of interest goes through a method-named macro wrapper, which adds a comma expression to `This`. The counted calls are draws, PSO, root signature, heaps, tables, CBVs, viewports, stencil reference, render targets, barriers, copies, resolves, clears, SRV/PSO/heap/resource creation, execute and waits.
- **Output:** one `[gpu-prof]` block per window, with mean/p50/p95/p99/max for each time and the mean for each count.
- **Overhead:** one flag test per wrapped call when off. With `RSX_GPU_PROF` on, `cpu_rf` is +0.1 ms (≈5%) against the same build with it off. Calls from several threads are counted unsynchronised, so counts are approximate.

**Workloads.**
1. **Real race data already on disk (no new run):**
   - T122's race `[rsx-frame-perf]` logs: `generated/runs/20261028-*-t122-ab-*/stderr.log`; arm NBE2 is quoted;
   - RSXI race captures `t113/runtime-{F..I}`.
2. **New harness `libs/video/tests/test_t143_bench.c`:** the real backend with the project's exact flags, shaped on those captures:
   - shadow-atlas pass: 1024×2048, three viewports;
   - scene pass: 1280×720, runs of G draws per program, 4 units from 24 textures changing every T draws, blend every third run, a full-target quad every 50 draws;
   - composite to the display, then present.
3. **Arms are interleaved (A B C D A B C D)**, 600 frames each, at two sizes:
   - 900 draws (capture size);
   - 1800 draws (T122 race size: 1608–1830 replayed draws per frame).
4. **Hardware:** Ryzen 5 9600X with an RTX 5060 (144 Hz vsync), and the 9600X's 2-CU RDNA2 iGPU (`CELLMARK_IGPU=1`).
5. **No Radeon 890M was available.** Every 890M statement is an estimate.

Tools are in `t143/tools/`:
- `run_arms.sh`, `perf_rounds.sh`, `perf_final.sh`: the bench arms;
- `summ.py`: tables;
- `correct.sh` + `cmp_snaps.py`: correctness arms and byte comparison;
- `rerun_fbase.sh`: determinism control;
- `run_suite_t143.cmd`/`.py`: the renderer suite;
- `bbt.cmd` + `build_backend_test.py`: harness builds.

Logs are in `t143/logs/`.

## 2. CPU/GPU timing breakdown

### 2.1 Race, measured (T122 logs, arm NBE2, 2026-10-28, RTX 5060; not re-run)
| per frame | value |
|---|---|
| frame wall | 200–214 ms (4.7–5.0 FPS) |
| guest draw callbacks (`draw_cb`/`expand`) | 46.9–50.0 / 41.2–46.2 ms (T122 base arm NB: ~102 ms expand) |
| render-thread `record_ms` | 9.7–13.8 ms: **cmd 5.0–5.6**, **PSO lookups 3.4–3.6** (1608–1830 lookups, ≈2 µs each), tex 0.9–5.5 |
| submit / GPU wait / present | 0.2–0.3 / 0.0–0.1 / 0.2–0.3 ms |
| GPU execution (T122 `[gpu-sync]`) | 3.3–4.8 ms on the RTX 5060; 11–18 ms on the 2-CU iGPU |
| other (render thread idle, waiting on the guest) | 136.8–150.5 ms |

**VERIFIED (T122 data):** the race is guest (PPU/SPU)-bound. The RSX thread is idle for most of the frame. GPU execution is 2–9% of the frame, and the GPU never stalls the CPU.

### 2.2 Race captures, measured (RSXI, `t113/runtime-F..I`, 12 frames)
| | value |
|---|---|
| draws per frame | 531–947 |
| pipeline-key changes | 49–140 (5–26% of draws) |
| viewport changes | 5–20 |
| target changes | 3–27 |
| distinct texture sets (16 units) | 16–115 per frame; 83–98% of draws repeat an earlier draw's set |

### 2.3 Bench, measured (final code `efae357`, 1800 draws, `logs/perf/{race,igpu}`; two interleaved runs per arm, mean of both)
`prof` = profile on, no T143 switch.

| ms per frame (mean / p95) | prof | `RSX_BIND_DEDUP` | `RSX_SRV_REUSE` | both |
|---|---|---|---|---|
| **RTX 5060:** render_frame CPU (`cpu_rf`) | 3.71 / 4.35 | 3.59 / 3.94 | 2.22 / 2.57 | **2.17 / 2.51** |
| RTX: pre-pass (`cpu_pre`) | 3.33 / 3.86 | 3.28 / 3.61 | 1.87 / 2.18 | 1.88 / 2.19 |
| RTX: SRV window fill (`cpu_srv`) | 1.57 / 1.80 | 1.54 / 1.61 | 0.43 / 0.47 | 0.42 / 0.45 |
| RTX: replay loop (`cpu_loop`) | 0.21 / 0.27 | 0.15 / 0.18 | 0.20 / 0.23 | 0.14 / 0.16 |
| RTX: harness frame wall p50 | 16.9 | 16.8 | 15.4 | 15.4 |
| **2-CU iGPU:** render_frame CPU (`cpu_rf`) | 3.51 / 4.39 | 3.68 / 4.61 | 2.41 / 3.17 | **2.40 / 3.23** |
| iGPU: SRV window fill (`cpu_srv`) | 1.29 / 1.68 | 1.42 / 1.83 | 0.48 / 0.66 | 0.49 / 0.70 |
| iGPU: replay loop (`cpu_loop`) | 0.27 / 0.37 | 0.23 / 0.33 | 0.27 / 0.40 | 0.22 / 0.34 |
| iGPU: GPU total (timestamps) | 4.38 / 4.65 | 4.41 / 4.70 | 4.36 / 4.63 | 4.37 / 4.63 |
| GPU waits (`cpu_wait`), submit | ≈0, 0.03 | ≈0, 0.03 | ≈0, 0.03 | ≈0, 0.03 |

The harness's guest draw callbacks (the record path that T119 owns) take 8.6–14 ms per frame in every arm.

Counts per frame:
- draws 1801;
- `SetPipelineState` 1802 → 157 with dedup;
- `RSSetViewports` 1805 → 9;
- SRV tables 1802 → 220 (both switches);
- `CreateShaderResourceView` 28,816 → 400;
- CBV sets 3604 in every arm: each draw has its own constant slot, so they never repeat;
- barriers 12, waits 1, resource creations 0.

An earlier RTX round at 900 draws (`logs/bench/r3`) gives `cpu_rf` 2.21 → 1.29 ms. A pre-final RTX round (`logs/perf_pre_final/race`) was noisy (GPU totals of 0.22 and 0.37 ms between identical runs) and is not quoted. In the final worst-case round, one run each of `prof` and `dedup` had a system stall (p95 52–77 ms), so only their first runs are compared.

### 2.4 Phase 1 items
| # | item | finding |
|---|---|---|
| 1 | CPU command recording | race 9.7–13.8 ms; bench 3.5–3.7 ms, of which the replay loop itself is only 0.21–0.27 ms (≈120–150 ns per draw). The cost is in the pre-pass. |
| 2 | GPU draw execution | race 3.3–4.8 ms (RTX), 11–18 ms (iGPU); bench 4.4 ms (iGPU), 0.2–0.4 ms (RTX) |
| 3 | PSO creation/switching | creation 0 per frame after warm-up (bench); race ≤2 misses per window (T116/T122). Switching: 1 per draw before, 157/1801 after dedup. Lookup 0.75 µs (bench) to 2 µs (race) each. |
| 4 | descriptor allocation/binding | 16 SRVs created per draw per frame. Measured at 30–40 ns each, i.e. **0.8–1.15 ms per 1800-draw frame**. That is the largest render-thread item that T143 can remove. |
| 5 | render-target transitions | state-tracked helpers (`off_rt_transition`, `zeta_transition`, `res_transition`); 12 barriers per bench frame, 79–90 per race frame (T122) |
| 6 | texture uploads | race tex 0.9–5.5 ms (snapshot hashing dominates: T122 `texsnap` 63 ms in the guest callbacks) |
| 7 | feedback snapshots | 5 per race frame, ≈17 MiB (T141 estimate); required for correctness |
| 8 | MSAA resolve/copy | 0 resolves, 8 window rebuilds per frame with `RSX_MSAA` (T137) |
| 9 | GPU fence waits | 0.00 ms in the race (T122) and ≈0.004 ms in the bench. The frame-start `wait_for_gpu` serialises CPU and GPU, but costs nothing while the GPU finishes first. |
| 10 | queue idle | race ≥ 95% of the frame (guest-bound); bench 8–9 ms (iGPU, vsync + harness) |
| 11 | clears | 3 RTV + 3 DSV per bench frame; the guest's own clears only |
| 12 | resource create/destroy | 0 per bench frame after warm-up. Race: 1 font-atlas re-creation per frame (2 committed resources, T122), and about 1 per frame with `RSX_RT_WINDOW` (T120 estimate). |

## 3. Ranked bottlenecks (render path; the guest-bound frame is outside T143)
1. **Guest draw callbacks (vertex expansion and upload), 41–102 ms per race frame.** VERIFIED (T122). Owned by T119 (`RSX_VP_COMPACT`, getenv caching, VS memo: 38 → 10 ms in its bench) and T122 (`PS3_TEX_SNAPSHOT_EPOCH`). Not duplicated here.
2. **Per-draw SRV creation: 0.8–1.15 ms per frame (bench, VERIFIED); estimated 0.8–1.2 ms per race frame (HYPOTHESIS, from the per-view cost × 26–29k views).** Removed by `RSX_SRV_REUSE`.
3. **PSO lookups: 3.4–3.6 ms per race frame (VERIFIED, T122 log).** Part of this is an uncached `getenv("FP_CONSTBUF")` per lookup, which T119's `a1875dd` already fixes (not duplicated). The rest is the ucode hash and three ucode scans per draw. A memo is possible but needs a proof that guest FP bytes cannot change during the pre-pass (§7).
4. **Texture lookups: 0.9–5.5 ms per race frame.** T122 epoch hashing / T115b cache.
5. **Redundant binding calls: about 1650 of 1800 PSO sets and 1796 viewport sets per frame are repeats,** but they cost only ≈0.05–0.07 ms per frame (VERIFIED, bench: the loop takes 0.21 → 0.15 ms on the RTX, 0.27 → 0.23 ms on the iGPU). Removed by `RSX_BIND_DEDUP`. The CPU win is small on these drivers; it may matter more on drivers with heavier state validation (HYPOTHESIS).
6. **GPU execution, 3.3–4.8 ms on the RTX.** Not a bottleneck at 60 FPS (16.7 ms budget). The 890M (16 CU RDNA3.5) is HYPOTHESIS-estimated between the RTX and the 2-CU iGPU's 11–18 ms. Barriers (79–90), feedback copies and resolves are small and are required (T141/T137).

## 4. Implemented changes
| commit | change |
|---|---|
| `e2f9435` | **`rsx_gpu_prof.h`** + backend integration: the `RSX_GPU_PROF` cost model (§1). **`rsx_bind_dedup.h`** + backend: **`RSX_SRV_REUSE=1`** and **`RSX_BIND_DEDUP=1`**, both opt-in ("1", read once). Tests: `tools/test_bind_dedup.py`, `libs/video/tests/test_bind_dedup.c`, the bench `libs/video/tests/test_t143_bench.c`. |
| `efae357` | The table/guest-sampler call order is kept as T110 pins it (`SetGraphicsRootDescriptorTable` directly followed by `gs_bind_draw`); the shadow resyncs after both. |

**`RSX_SRV_REUSE`.**
- While a draw's 16-unit window is filled, `srv_write_lv` only records each view: resource, format, component mapping, dimension and levels.
- `srvw_finish` then looks for an earlier window of the same replay with equal views. Windows are compared field by field, not just by hash. On a hit, the draw's table points at that window; on a miss, the 16 views are created in the draw's own window.
- **Correctness rules:**
  - every draw defaults to its own window;
  - a window with any unit unwritten is never shared, which keeps the old stale-slot behaviour;
  - the cache is emptied whenever any resource is created, since a new resource can reuse a freed one's address;
  - windows are never shared across replays;
  - the RSXI record reports the window actually bound.
- What a draw sees is identical: the same descriptor contents, read at the same time.

**`RSX_BIND_DEDUP`.**
- The replay's per-draw `SetPipelineState`, `OMSetStencilRef`, `RSSetViewports`+`RSSetScissorRects`, the SRV table and both CBVs are skipped when they equal what the replay last issued.
- **Safety rule:** every binding method in the backend advances a generation counter through its wrapper. A binding made anywhere else drops the whole shadow before the next comparison: MSAA/zeta helper draws, the restore block, root-signature changes, the retarget block. Only the replay's own call sites resync it.
- There are no hand-written invalidation lists to keep up to date.
- Guest draw order, blending, depth, stencil and shaders are untouched. No draws are merged, and no barrier, copy, snapshot or wait was removed.

## 5. Test results
- **`tools/test_bind_dedup.py`: 0 failures.** It runs 30 source pins, then a model command list: 20,000 draws × 3 seeds with random foreign bindings, giving identical state at every draw with the shadow on, ≈49% of calls skipped. It also tests the window cache (4096 draws, a resource-creation cut, field-sensitivity, a forced hash collision) and the report percentiles.
  - **Mutation check:** a shadow that ignores foreign bindings makes the test fail.
- **Correctness arms (`tools/correct.sh`, `logs/correct_final.txt`, `logs/cmp_snaps_final.txt`).** Every arm ran under the D3D12 debug layer with its message drain, and RSXI target/pass snapshots were compared byte for byte against the same build with no T143 switch.
  - **Bench** (900 draws; G=1 T=1; guest samplers + mips + `RSX_DEPTH_STATE`), arms dedup / reuse / both / rerun: **18/18 identical** (5 snapshots each).
  - **T141 harness** (render-target feedback, depth as colour, `RSX_RT_WINDOW`/`RSX_ZETA_EXACT`/`RSX_MRT_STATE`, GPU-based validation): **identical** (all-features and GBV feedback arms).
  - **T137 harness** (`RSX_MSAA`, guest samplers, feedback; `ms_util_draw` clobbers the bindings): **identical** (both arms).
  - **GPU-based validation** (`D3D12_GBV=1`): bench and T141 feedback arms identical. The final round's bench GBV "off" arm never reached its RSXI frame; the rerun pair (`logs/rerun_gbv.txt`, `logs/cmp_snaps_final2.txt`) is identical.
  - **Errors:** 0 debug-layer errors or corruption in every arm. Warnings are identical between off and on: id 820, clear value ≠ optimised clear value.
  - **The one mismatch** is T141's base arm (feedback reads with `RSX_RT_FEEDBACK` off). Three "off" runs give three different images (`logs/rerun_fbase.txt`): the draw samples its bound target, which is undefined, as T141 documents. That arm is nondeterministic at base, not changed by T143.
- **Frame-to-frame determinism:** reruns of the bench arms (off/off, on/on) were byte-identical.
- **Device removal:** unchanged paths. The bounded fence waits and removed-reason reports are untouched, and the profiler adds no wait (it reads timestamps only after the existing drain). Not exercised (PARTIAL).
- **Renderer suite (`run_suite_t143.cmd`, 81 drivers + C tests):**
  - T143 tree (final): **41 PASS, 0 FAIL** (`logs/suite_final.txt`).
  - Base `07b453f`: 80 PASS + 1 absent (`test_bind_dedup`).
  - `test_t110_pins` failed on the first T143 version and passes after `efae357`.
- **Compiler:** no new warning categories beyond the tree's pedantic set (padding, unsafe-buffer, declaration-after-statement). `-Wdisabled-macro-expansion` is silenced in the TU for the wrapper macros.

## 6. Performance comparisons
| measure | before | after (both switches) | |
|---|---|---|---|
| `CreateShaderResourceView` per 1800-draw frame | 28,816 | 400 | −98.6% (VERIFIED, bench) |
| render_frame CPU, RTX 5060, 1800 draws, mean / p95 | 3.71 / 4.35 ms | 2.17 / 2.51 ms | **−42% / −42%** (VERIFIED, bench) |
| render_frame CPU, 2-CU iGPU, 1800 draws, mean / p95 | 3.51 / 4.39 ms | 2.40 / 3.23 ms | −32% / −26% (VERIFIED, bench) |
| render_frame CPU, RTX, 900 draws, mean | 2.21 ms | 1.29 ms | −42% (VERIFIED, bench) |
| replay-loop CPU (bind dedup alone) | 0.21 ms | 0.15 ms | −0.06 ms (VERIFIED, bench) |
| GPU time (timestamps) | 4.38 ms | 4.37 ms | unchanged (VERIFIED: no GPU work changed) |
| worst case (every draw changes program and textures) | 3.74 ms | 2.45 ms | dedup neutral (loop 0.24 vs 0.27 ms); reuse still −1.3 ms |
| profiler overhead | — | — | +0.1 ms per frame when on; none measurable when off (base 2.11 vs off 2.08 ms) |

**Not a game result.** On the race's ~1700 replayed draws, the estimated saving is 0.8–1.2 ms of render-thread CPU per frame (HYPOTHESIS). The race is guest-bound at about 200 ms per frame, so **no FPS change is expected until T119/T122/T106-class guest work lands.** The saving only shows up once the RSX thread is on the critical path.

## 7. Correctness risks
- **SRV reuse.** It shares descriptors, not contents, so a draw reads the same resource at the same time as before. Residual risk: a resource destroyed and recreated at the same address *without* passing through `CreateCommittedResource` would defeat the cache-reset rule. No such path exists in the backend: placed resources and other allocators are not used (VERIFIED by search). A future allocator must advance `s_res_gen`.
- **Bind dedup.** Any new binding method, or a D3D12 call that resets bindings and is not wrapped, would escape the generation counter. The pin test lists the wrapped methods. `ExecuteBundle` and `ClearState` are not used. A command list `Reset` happens outside the loop, and the shadow is local to one loop.
- **Profiler.** Timestamps are read only after the existing frame-start drain, so it adds no synchronisation. With early replays, each replay is one record.
- **Not done, by design:**
  - no barrier, copy, feedback snapshot, resolve or fence wait was removed: none was proven unnecessary, and T141/T137 require the feedback copies;
  - no draw merging;
  - no PSO-lookup memo: the FP ucode hash is the only guard against the guest rewriting a program at the same address while the pre-pass runs.

## 8. Integration dependencies
| branch | `git merge-tree` with T143 | note |
|---|---|---|
| T119 `agent/t119-renderer-performance` | clean | Its getenv caching (including `FP_CONSTBUF` in `vp_get_fp_pso`) and compact path cut the dominant callback cost. It is the prerequisite for any race gain. |
| T142 `agent/t142-rt-texture-sampling` | clean | |
| T144 `agent/t144-rsx-stencil-fidelity` | 1 hunk | The `OMSetStencilRef` site. Resolution: keep T143's dedup wrapper and add T144's shared-buffer log inside the `if`. |
| T122 `agent/t122-d3d12-submission` | 5 hunks (base vs T122 is clean) | T122 defines its own `ResourceBarrier` counting macro (`s_gsy_barriers`) and `#define wait_for_gpu() wait_for_gpu_at(__LINE__)`. Resolution: one `ResourceBarrier` wrapper feeding both counters, and T143's timing moved into `wait_for_gpu_at`. The `RSX_GPU_SYNC` and `RSX_GPU_PROF` reports overlap and could later share one. |
| T116 `agent/t116-shader-pso-cache` | conflicts | They also conflict with base `07b453f` without T143 (T116 forks at `2562ba8`), so they are not caused by T143. |
| T120 / T133 / T137 / T141 | in base | Covered by the correctness arms above. |

## 9. Proposed controlled game A/B test (needs authorisation; not run)
- **Build:** the T143 tree plus T119 (clean merge) and T122's epoch (5 small hunks), in one scratch integration build. Without T119/T122 the race stays guest-bound and an A/B shows nothing.
- **Arms:**
  - **B:** no T143 switch;
  - **S:** `RSX_SRV_REUSE=1 RSX_BIND_DEDUP=1`;
  - both with `RSX_GPU_PROF=120` and `RSX_FRAME_PERF=12,1,100000`;
  - three runs each, interleaved, with T122's `run_t122ab.py` / `ana_t122.py` over the race window (entry +15 to +85 s).
- **Metrics:**
  - `record_ms` [cmd], `cpu_srv`, `cpu_rf` p50/p95;
  - `srv_create`/`srv_reuse` and `pso_skip`;
  - GPU total and idle;
  - FPS and frame-time spread.
- **Visual equality:** RSXI frames from each arm (`RSXI_SNAP=passes`) compared byte for byte.
- **Pass:** `cpu_srv` −60% or more, no RSXI pixel difference, and no debug-layer error in a short `D3D12_DBG=1` run.

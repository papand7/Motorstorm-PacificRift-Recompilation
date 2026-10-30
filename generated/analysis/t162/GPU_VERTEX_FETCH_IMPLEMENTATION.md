# T162 — GPU vertex fetch: implementation, validation, performance

2026-10-30. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. Offline only; no game launch.

## 1. Commits (ps3recomp `agent/t162-gpu-vertex-pipeline`, base `afdcabd`; not pushed, not merged)

| commit | content |
|---|---|
| `d1bec5b` | `RSX_VTX_STATS=<ms>`: read-only per prim × indexed × path counters and format signatures (`rsx_vtx_stats.h`, `test_vtx_stats.c`, `tools/test_vtx_stats.py`) |
| `a89cf5f` | `RSX_GPU_VERTEX_FETCH=1` (`rsx_gvf.h`, backend, decompiler mode, `test_gvf_plan.c`, `test_gvf_fetch.c`, `test_gvf_draw.c`, `tools/test_gvf.py`) |
| `8c68a76` | T119 VS-memo and xfer-diag source pins updated to the new code shape (mutation checks kept) |

Together they are integration-ready (head `8c68a76`). Every new switch defaults off. The tree touches no texture-residency, Wws AOT or physics code.

## 2. What was built (design: `GPU_VERTEX_FETCH_DESIGN.md`)

- **`rsx_gvf.h`** (header-only, no backend state):
  - span planning: same-location intervals merged, 16-aligned with 16 B slack;
  - per-attribute descriptor `{raw addr − start, stride, type, comps}`, plus the 16 constant registers;
  - linearity check per 1 MiB IO page;
  - divider refusal;
  - the 68,864-float conversion table built with `rsx_fetch_attrib`'s own expressions.
- **Decompiler:** `rsx_vp_decompile_gvf_ex` is input mode 2 of the same decompiler.
  - `VSInput { uint vid : SV_VertexID }`; `v[k] = gvf_fetch(k, vid)` for all 16 registers.
  - The program body is the same text.
- **Backend:**
  - `gvf_try_strip` runs on a copy of the primitive stream (restart, odd order, 256-index batch seams). It produces u32 guest indices, then plans, checks, makes room (the same early replay), looks up the VS and writes. The stream is committed only when the draw is taken. Any refusal returns before writing, and the CPU expander runs instead.
  - Records carry `gvf`/`gvf_ib`/`gvf_raw`/`gvf_cb`.
  - Replay binds CBV b1, SRV t20 and SRV t21, then calls `DrawIndexedInstanced`. gvf records never merge.
  - Ring: one UPLOAD buffer, 2 halves, following `vp_vb` parity and resets.
  - The VS variant uses a salted hash and its own memo.
- **Counters (`[gvf]`, every `RSX_VTX_STATS` period and at shutdown):** draws, corners, ib/raw MB, cpu ms, flushes, the fallback reasons (divider, span, sparse, big, empty, vs, room) and `nopso`.

## 3. Correctness (all VERIFIED offline)

| test | what | result |
|---|---|---|
| `test_gvf_plan.c` | spans, addresses, slack, refusals, table entries; 2,000 random layouts | pass |
| `test_gvf_fetch.c` | the decompiler's gvf prologue in a compute shader vs `rsx_fetch_attrib`. Random states, every type 0–7, sizes 0–4, odd strides and offsets, constant-register fill | **bit-identical** on RTX 5060, the Radeon iGPU (`D3D12_VENDOR=0x1002`) and WARP. Seeds 1–5: 6.3–6.9 M words per 400 states, 0 differences |
| `test_gvf_draw.c` via `correct_draw.sh` | the full backend on 3 workloads: heavy (6,956 draws/frame, 4 passes), light (2,004), seam (strips across batch seams and restart). Arms: CPU compact, fat, gvf, gvf with a 4 MB ring (forces 40–144 early replays), gvf rerun. MAIN page-swap resolver, CPU-fallback draws mixed in, per-frame vertex mutation | **every arm identical to CPU compact on every frame** (6/6 heavy, 6/6 light, 4/4 seam per arm). `nopso` = 0. All fallback reasons except divider, big and room exercised (span 124–414, sparse 492–1,697) |
| D3D12 debug layer | all `correct_draw` arms | 0 errors, 0 corruption, 0 warnings |
| `tools/test_gvf.py` | source pins: off = old path, old root signature, old VS memo/hash/decompile; order of copy → room → VS → write → commit; parity; resets; replay | pass |
| `tools/test_vtx_stats.py` | counters | pass |
| full suite (`run_all_t157`, `T157_SUITE=t162gvf`) | regressions | 141 pass / 43 skip / 4 fail, then 2 after `8c68a76` (§8) |

Missing components: each attribute starts from its `vertex_data4f` register and the supplied components overwrite it. This is covered by the fetch test (sizes 1–3, size 0 = 4, disabled and stride-0 arrays) and by the draw test.

## 4. Performance (synthetic, `bench_draw_path`, RTX 5060; 3 repeats, median (min–max), ms per frame)

| case | arm | callbacks (CPU vertex) | record | wall | GPU/pass | VB units MB |
|---|---|---|---|---|---|---|
| race2k (2,000 strips) | CPU compact | 14.95 (14.70–15.20) | 2.30 | 17.70 | 0.17 | 38.2 |
| | fat | 35.60 | 2.30 | 36.95 | 0.08 | 149.9 |
| | **gvf** | **9.40 (9.40–9.50) −37 %** | 2.30 | **12.10 −32 %** | 0.08 | 0 (ring: 16.5 raw + 2.3 idx + 1.0 CB) |
| race6k9 (6,956, 4 passes) | CPU compact | 60.20 (60.15–61.95) | 8.20 | 61.60 | 0.15 | 131.9 |
| | fat | 125.90 | 7.95 | 127.20 | 0.08 | 517.0 |
| | **gvf** | **41.25 (39.90–41.65) −31 %** | 8.65 | **42.95 −30 %** | 0.06 | 0.1 |
| mixed (heavy-shader, incl. CPU-fallback draws) | CPU compact | 90.65 (89.80–94.25) | 2.90 | 105.80 | 20.94 | 327.4 |
| | fat | 235.95 | 2.45 | 236.90 | 6.37 | 1112.0 |
| | **gvf** | **78.30 −14 %** | 2.75 | **96.80 −8.5 %** | 20.80 | 154.0 (fallback draws) |

- **Allocations:** none per draw. Per run: the ring (2 × 32 MB UPLOAD by default) and the 275 KB table, lazily on the first gvf draw. One extra VS and PSO per program actually drawn on the GPU path.
- **GPU time:** unchanged or lower in every case. Fewer bytes fetched outweigh about 20 ALU ops per attribute.
- **Remaining CPU per GPU-fetch draw:** the u32 index assembly plus the span copies take most of it. About 3.6 µs per draw of callback time lies outside the measured stages (HYPOTHESIS: call/bookkeeping overhead; not attributed).
- **Not measured:** in-game numbers (BLOCKED, `GAME_AB_PLAN.md`); an 890M (`GPU_VERTEX_FETCH_DESIGN.md` §7).

## 5. Known gaps

- **`nopso`: closed (`ee8b13c`, `69489f2`), VERIFIED offline.** A gvf record whose guest-FP pipeline fails is expanded at replay from its ring snapshot into fat vertices and drawn through the CPU path's fallback pipeline, in order, with no retry of the failed pipeline. `lost` counts only an out-of-memory refusal and is reported loudly. Results: `FINAL_VALIDATION.md`.
- Non-indexed draws, indexed TRIANGLES/QUADS and inline arrays stay on the CPU (under 1 % of indices in game).
- The `sparse` threshold (raw > 64 KB and > 2 × the compact record) is heuristic. The share it sends to the CPU in game is unknown until step 1 of the plan.

## 6. Reproduce

Private harness in `generated/analysis/t162/gpuvtx/harness/`:
- `correct_bench.sh` and `build_gvf_fetch.cmd`: the fetch test;
- `correct_draw.sh`: the matrix in §3;
- `perf_bench.sh` plus `perf_summary_t162.py runs/p`: §4.

Logs: `logs_correct_draw.txt`, `logs_perf_bench.{txt,json}`, `suite_t162gvf.txt`.

## 7. Next step

Request authorisation for `GAME_AB_PLAN.md`: 1 diagnostic launch, then 4 A/B launches.

## 8. Full suite (`run_all_t157 ps3recomp-t162-gpuvtx`, on `a89cf5f`)

- 141 PASS, 43 SKIP, 4 FAIL.
- **Pre-existing, also failing on the base:** `test_rt_pool_srv_layout`, `test_vpc_watch`.
- **Caused by T162 source shape, fixed in `8c68a76`:**
  - `test_t119_pins`: the memo is now reached through `vmo`;
  - `test_xfer_diag`: the optional `RSX_VTX_STATS` line in the draw wrappers.
  - Both pass after the fix, together with `test_gvf` (VERIFIED). The suite was not rerun in full after `8c68a76`, which changes only these two test files.

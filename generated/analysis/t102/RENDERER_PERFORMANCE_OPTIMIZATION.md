# T102: Renderer performance optimization

- **Worktree:** `ps3recomp-t102`, branch `agent/t102-renderer-performance`, based on T99 `db2aa90`. T99 sits on T96 `bd09877`, whose tree is identical to T96I `95a906d`.
- **Commit:** `1e5d534`. Not merged or pushed.
- **Scope:** offline only, with no game build and no launch. The T100, T101 and T96I worktrees were not touched.
- **Ownership:** the only peer is motorstorm01-8d (T101, the offscreen-draw audit). T100 owns the black-display investigation in `ps3recomp-t100`. No other performance agent was active.

## 1. Baseline evidence

T98 run `generated/runs/20261027-111836-t98-visible-race`, race window 206–298 s:

| Observation | Value | Status |
|---|---|---|
| Guest frame rate | 368 frames in 97.6 s, about 3.8 fps, about 263 ms per frame (T98) | VERIFIED |
| Slow render passes | Only the first race frame's two passes were ≥ 200 ms (359.5 ms and 1,158.2 ms, both in `record`). No other `[rf-phase]` line in 98 s | VERIFIED |
| Recurring shader/PSO compiles | They would show up as ≥ 200 ms passes, and there are none. So no cache thrashing at that scale | VERIFIED (upper bound only) |
| Early replays | One per guest frame, at about 393k of 393,216 vertices and about 930–967 records (`[VPVB]` #64, #128, #256) | VERIFIED |
| Process CPU | 2.8 cores busy in the race, against 0.25 before it (`performance.json` samples) | VERIFIED |
| Per host thread | Busiest threads at 75%, 70% and 33% of a core. **No thread is saturated** | VERIFIED |
| Which thread is the renderer (frame clock) | The runtime does not name host threads | BLOCKED |
| Split between guest PPU, SPU and renderer | — | BLOCKED. Needs a run with `RSX_FRAME_PERF` (T99, already in this branch) |

**Interpretation (HYPOTHESIS):**
- No host thread reaches 100% of a core.
- Each render pass after the first race frame takes under 200 ms, and there are two passes per 263 ms guest frame.
- So the frame time is probably set by threads waiting on each other in series, not by any single CPU-bound loop. Renderer CPU work is part of that chain, because the frame-clock thread both drains and renders.

## 2. Confirmed hot paths (recurring, per guest frame)

From the source, with T95 and T99 counts:

| Path | Cost before | Status |
|---|---|---|
| Strip/fan/list expansion, `read_vp_vertex` per expanded vertex | about 525k expanded vertices; every vertex calls `rsx_fetch_attrib` 16 times, even for slots that only copy the constant register; a strip converts each guest vertex up to 3 times (T94 batch: 309 written / 205 unique) | VERIFIED (code + T95) |
| Index fetch | `cellGcmResolveLocated` (a cross-TU call plus an IO-table lookup) per index, in both the count pass and the expansion | VERIFIED (code) |
| `vp_get_fp_pso` | twice per record per pass with identical arguments (prepass + draw loop). Each call: `getenv("FP_CONSTBUF")`, FP program-size scan, code hash, texture-unit scan, and a linear scan over up to 256 cache entries. A program that fails to compile is retried in **both** calls, every pass | VERIFIED (code) |
| `vp_get_vs` | per draw: hash up to the program's end bit, then a linear scan. Smaller than the 8 KB T99 assumed | VERIFIED (code). Not changed |
| `vp_record_cb` | 8,448 B of constants per record | not changed |

## 3. Optimizations implemented (`1e5d534`)

| # | Change | Where | Semantics |
|---|---|---|---|
| 1 | **Per-draw vertex cache** (`include/ps3emu/vp_expand.h`): each guest vertex is converted once per draw into a 256-entry direct-mapped cache in cacheable memory, then copied as 256 B into the upload heap for each use | `upload_strip_vp`, `upload_strip_vp_indexed`, `upload_tris_vp_indexed` | Byte-identical. A vertex depends only on (state, index), and guest memory is read within one draw callback. The cache is reset per draw, and no index value is reserved |
| 2 | **Per-draw attribute template:** slots that `rsx_fetch_attrib` fills from the constant register (`!enabled \|\| stride == 0 \|\| !vm_base`, the same condition) are filled once per draw; only the remaining slots are fetched per vertex | same | Byte-identical (pinned against `rsx_vertex_fetch.c`) |
| 3 | **Index base resolved once per draw:** `vp_idx_begin` / `vp_idx_at`, the same location and width rule as `read_guest_index` | indexed expanders + the exact-reservation count | Identical indices |
| 4 | **Pipeline lookup reuse:** the draw loop takes the record's prepass `vp_get_fp_pso` result if all of these hold: same pass (an epoch bumped at every prepass), no FP-cache eviction since (it bumps the epoch too), and the same `vp_gen`. Otherwise it calls `vp_get_fp_pso` as before. `s_vp_fp_last_uhash` is restored for the shader trace | `render_frame` prepass / draw loop | Same pipeline. One difference: a program that fails to compile is tried once per pass instead of twice (same NULL → fallback PSO). A guest rewrite of FP bytes between the prepass and the draw loop of one pass is now resolved by the prepass read |

Unchanged: quads (each vertex is already converted once per quad), non-indexed lists, triangle order, winding, restart handling, record format, shader inputs, draw ordering, early-replay behaviour, and VS lookup. Nothing is skipped, merged or reduced.

## 4. Offline measurements (SYNTHETIC: not game timing)

`bench_vp_expand` on a Ryzen 5 9600X: T94-shaped restart-every-5 u16 strips through the real `rsx_fetch_attrib`, into `PAGE_WRITECOMBINE` memory, best of 5. Log: `logs/bench_vp_expand.txt`.

| Expanded vertices (MB written) | 1 attr: S0 → S5 | 4 attrs | 8 attrs |
|---|---|---|---|
| 432,585 (106) | 10.7 → 4.5 ms (×2.39) | 13.5 → 6.6 (×2.04) | 16.1 → 12.5 (×1.29) |
| 525,279 (128) | 13.1 → 5.4 ms (×2.41) | 16.4 → 8.1 (×2.03) | 19.7 → 15.1 (×1.31) |
| 1,001,112 (244) | 24.7 → 10.1 ms (×2.45) | 31.4 → 15.4 (×2.03) | 37.4 → 28.8 (×1.30) |

**Other measured effects:**
- **Conversions:** 1.00 → 0.66 per expanded vertex on the T94 shape; 57.5% reuse over the randomized test streams.
- **Allocations:** none added. The cache is one static 64 KB block, and no heap allocation happens per draw or per vertex.
- **Bytes copied:** the bytes written to the upload heap are unchanged. Each cache hit adds a 256 B memcpy from L1/L2.
- **Pipeline lookups:** the draw loop's lookups drop from N to 0 per pass for records the prepass resolved, i.e. 1,400 of about 2,800 lookups per guest frame. Not benchmarked in isolation, because the lookup lives inside the backend TU.

## 5. Correctness tests

| Test | Result |
|---|---|
| `test_vp_expand` (new): 600 random states × streams (lists, strips, fans; u16/u32; restart on and off; indices colliding mod 256; MODULO/DIVIDE dividers; stride 0; every attribute type incl. unhandled), plus a per-draw reset case and an index-0xFFFFFFFF case; 18 source pins on the wiring and the reuse conditions | 0 failures |
| `bench_vp_expand`: S1, S2, S3 (re-expanded) and S5 byte-equal to S0 for 1/4/8 attributes | 0 failures |
| Renderer suite (42 tests, incl. T88 `test_d3d12_*`, T92 `test_rf_phase`, T95 `test_geom_expand`, T96 `test_vp_flush`, `test_prim_stream`, `test_draw_rejection`, T99 `test_rsx_frame_perf`) | **33 PASS / 9 SKIP (POSIX-only) / 0 FAIL** (`logs/suite_t102.txt`) |
| `rsx_d3d12_backend.c` with the project clang-cl flags | rc=0. No new warning kinds (`logs/tu/`) |
| `audit_public.py --staged` | the 25 pre-existing BLOCKs, none in T102 files |

## 6. Changed files

- `include/ps3emu/vp_expand.h` (new)
- `libs/video/rsx_d3d12_backend.c`
- `libs/video/tests/test_vp_expand.c` (new)
- `tools/test_vp_expand.py` (new)
- `libs/video/tests/bench_vp_expand.c`: S5, plus the 525k and 1M sizes

Tools: `t102/tools/edit_backend.py`, `edit_bench.py`, `make_scripts.py`, `tu_t102.cmd`, `run_suite_t102.py/.cmd`.

## 7. Remaining bottlenecks

1. **Unattributed, and the biggest unknown:** most of the 263 ms frame has no owner yet, and no thread is saturated. One run with `RSX_FRAME_PERF=12,10` decides whether the remaining time is in the drain, the passes or `other` (guest/SPU).
2. The first race frame takes about 1.5 s in `record` (first-use FP/PSO creation, HYPOTHESIS). A persistent DXBC/`ID3D12PipelineLibrary` cache would remove it on later runs (T99 candidate 2).
3. The 8,448 B of constants per record (about 12 MB per frame into write-combined memory), and the per-draw `vp_get_vs` hash. Not changed.
4. 256 B per expanded vertex. The indexed + compact layout (T99 S4) needs a separate correctness plan.

## 8. Expected runtime impact (UNVERIFIED)

**Estimate:**
- about 8–11 ms less expansion per guest frame (525k vertices, 1–4 attributes; synthetic);
- about 1,400 fewer pipeline lookups per guest frame (unmeasured);
- roughly 3–6% of a 263 ms frame, **if** these run on the critical path.

**Not claimed:** any FPS change. A game-FPS improvement is not established, and it may be small if the limit lies outside the renderer.

## 9. Integration order relative to T100

1. T100 first. It may change the display chain. T102 touches only the expanders, `vp_fp` eviction and the replay's PSO lookup sites, so the expected overlap is the `render_frame` prepass and draw loop.
2. Then rebase `agent/t102-renderer-performance` (which includes T99 `db2aa90`) and rerun `tools/test_vp_expand.py` + the suite.
3. One bounded A/B run (needs authorization): `RSX_FRAME_PERF=12,10`, a 300 s cap, T100+T99 against T100+T99+T102, comparing `expand_ms`, `pso` and guest fps.
4. T102 does not touch the black-display path. It can also be tested before T100, because its output is byte-identical.

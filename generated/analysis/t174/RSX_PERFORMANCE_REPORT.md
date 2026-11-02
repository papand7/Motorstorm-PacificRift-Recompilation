# T174: RSX/D3D12 performance investigation

**Result:** `RSX_VP_INDEXED=1`, opt-in, implemented in `ps3recomp` commit `e528406f` (branch `agent/t174-rsx-indexed-vertices`, based on T170 head `fda8c9b`). Nothing was merged or pushed, and the game was not launched.

**Main finding:** the gain depends on how much a draw reuses its vertices, and also on fast fetch. At the 1.5× reuse reference it saves 18% of heavy-frame time with fast fetch on the RTX and nothing without fast fetch. The game's real reuse has not been measured, so **no FPS gain is claimed**.

All benchmark numbers are synthetic (`bench_draw_path`, real backend, no debug layer). They are not game numbers.

## 1. Bottleneck evidence

| Finding | Evidence | Label |
|---|---|---|
| Heavy race frames are limited by the CPU/render thread in the normal mode, not by GPU waits | T170 arm A, one run, ≥5000 records: 11.2 FPS, p50 77.0 ms; expand 30.9, record 30.7 (tex 5.3, pso 15.5, cmd 9.9), fence wait 0.1, other 13.9 | PARTIAL (one run; no GPU timestamps for heavy frames) |
| Light frames are limited outside RSX | under 3000 records: other 28.9, expand 8.5; PPU/Havok per T154/T161 | PARTIAL |
| A separate mode with 84 ms GPU waits exists and is unexplained | T162/T167 | PARTIAL; not addressed here |
| Vertex writes to the RTX UPLOAD heap are slow: 5.29 GB/s, against 21.7–27.2 GB/s for cached memory | `upload_bw_t174.c`. AMD integrated GPU: 26.5 GB/s upload. 131.9 MB/frame is about 25 ms on the RTX. This settles T170's hypothesis | VERIFIED on this PC (older T151 measurement: writes cost 0.6 ms at 2000 draws; not reconciled) |
| T170's write-combining fix cut expand by 12–13 ms but `other` rose by about the same, so frame time did not improve | T170 vs T169, one run each | HYPOTHESIS |

Texture residency (TEXRES, tex 178–208 → 4.2 ms) is already done. Upstream ps3recomp v0.18.0 has indexed draws (`d682e9c4`, Metal/Vulkan equivalents), but only on the register-file draw engine and `rsx_live_draw.c`, not the game's VP path in `rsx_d3d12_backend.c`. They could not be reused directly.

### Candidates ranked

| # | Candidate | Benefit | Complexity / risk | Decision |
|---|---|---|---|---|
| 1 | Indexed compact records | fewer upload bytes, up to 15 ms (bench) | low; same triangles and order | **selected** |
| 2 | Validate T170 `RSX_VP_FAST_FETCH` + `RSX_FP_SCAN_MEMO` | pso 8.7 → 0.2, about 14 ms (bench) | already implemented; needs a game run | A/B below |
| 3 | PSO misses | 135 misses, 4.66 s in race | async compile belongs to T167 | not here |
| 4 | Parallel expansion (T170) | RTX: none (40.1 → 40.3), integrated: large | guest ordering risk | not on RTX |
| 5 | CBV dedupe | at most a few ms | untested | not now |
| 6 | FIFO decode | about 3.2 ms in total (T151) | | too small |
| 7 | GPU vertex fetch (T162) | | Present timeout in game | rejected |
| 8 | Culling (T168) | 0 provable no-effect draws | | rejected |

Sync waits (0.1 ms) offer nothing in the normal mode.

## 2. Selected optimization

The game VP path turns guest strips into triangle-list corners in the persistently mapped UPLOAD buffer. The vertex cache already converts each guest index once per draw, so repeated corners are only slow copies.

With `RSX_VP_INDEXED=1`, a strip or fan on a compact record is laid out at a 256-byte-aligned offset R as:

- the 256-byte template
- V unique vertices in first-use order
- C u16 indices

It is drawn with `DrawIndexedInstanced(C, 1, 0, R/256, 0)`. Triangles and their order are unchanged, and the primitive stays a triangle list, so no strip-cut value applies.

- **Switch:** exactly `1`, read once, off by default. Also needs `RSX_VP_COMPACT`. Forced off by `RSX_VP_PARALLEL>0`, `RSXI` and `VTX_POS`.
- **Fallback:** if the worst case (every corner new, over 65535 corners excluded) does not fit, the draw takes the unchanged corner path. The check uses `vpvb_room`, so budget counters and reservation accounting match the corner path.
- **Hash table:** 1024 entries; a collision writes the vertex again, costing bytes but changing nothing the shader sees.
- **Coverage:** indexed strips and fans only (over 99% of game indices). Other primitives use the old path.
- **Counters:** `upload_mb` counts bytes written. `[vp-indexed] draws= corners= verts= fallback=` prints every 64 presents.
- **Bench:** added opt-in `BENCH_QUADS_APART=1`. The default workload and existing baselines are unchanged.

## 3. Before and after

Median of the last 20 frames per run, 3 interleaved runs per arm, final binary, game vertex format. off = switch off, ix = on; plain = neither T170 option, ffm = fast fetch + memo.

**RTX 5060, heavy, 6900 draws**

| Reuse | Arm | wall ms | expand ms | upload MB/frame |
|---|---|---:|---:|---:|
| 2.93× (default grid) | off plain → ix plain | 53.5 → 38.5 (−28%) | 39.0 → 24.1 | 131.9 → 50.6 |
| 2.93× | off ffm → ix ffm | 38.9 → 24.0 (−38%) | 34.3 → 19.5 | 131.9 → 50.6 |
| 1.50× (`BENCH_QUADS_APART`) | off plain → ix plain | 54.2 → 53.8 (none) | 39.7 → 39.3 | 131.9 → 93.2 |
| 1.50× | off ffm → ix ffm | 38.9 → 31.8 (−18%) | 34.1 → 27.3 | 131.9 → 93.2 |

**RTX 5060, light, 2000 draws (wall ms)**

| Reuse | plain | ffm |
|---|---|---|
| 2.93× | expand 11.2 → 7.0 (wall: off plain median 31.0, noisy, range 15–31; earlier clean run 15.7 → 10.9) | 11.3 → 7.0 |
| 1.50× | 15.4 → 16.0 (slightly worse) | 11.4 → 9.4 |

**AMD integrated GPU, heavy (wall ms; build differs from final only by a local variable)**

| Reuse | plain | ffm |
|---|---|---|
| 2.93× | 53.5 → 38.7 | 33.7 → 22.1 |
| 1.50× | 53.2 → 53.9 | 33.5 → 31.9 |

Other measurements:

- **Switch off:** T174 off matches T170's binary in timing (53.4 vs 53.2 ms, 38.8 vs 38.9 ms).
- **Record and command costs:** `record`, `tex`, `pso`, `cmd` unchanged (RTX heavy cmd 4.3 plain, 2.7 ffm); the added `IASetIndexBuffer` does not show. Submit stays at 0.1 ms.
- **Allocations:** none per frame. Static only: 128 KB index scratch plus about 10 KB table (VERIFIED by code).
- **Fallbacks:** 0 in every arm.
- **Sync:** the bench does not exercise GPU waits, so no change is claimed.
- **Unexplained:** at 1.50× ffm saves 38.7 MB/frame, and 7.1 ms matches the 5.29 GB/s floor. At 1.50× plain saves the same bytes but no time. I did not find out why.
- **Rejected run:** one RTX shared-grid run was disturbed by outside load (off plain 71 ms) and was replaced. The light `off_plain` wall above also has an unexplained 31 ms cluster, though its `draw_cb` is stable.

## 4. Correctness and regression tests

| Check | Result | Label |
|---|---|---|
| `test_vp_indexed`: random streams through the real primitive stream, indexed bytes equal corner bytes, collisions, limits, generation wrap; wiring pins | pass (C part: 488767 checks, 0 failures) | VERIFIED |
| Pixels, RTX, 6 frames, both reuse levels: ix and ix+ffm against control | 6/6 identical | VERIFIED |
| Control: one changed position byte | `ctrl` differs 0/6; `ixctrl` equals `ctrl` on RTX | VERIFIED; the comparison can see a change |
| Pixels, WARP software adapter (temporary build, not committed), 3 frames | ix 3/3 identical | VERIFIED |
| **Pixels, AMD integrated GPU** | **ix differs in all frames**: 0.04% of pixels at 1.5× reuse, 0.42% at 2.93× reuse, scattered, delta up to 255. Repeatable | **see below** |
| Debug layer, RTX, both reuse levels | 0 errors; only the process-exit warning | VERIFIED (bench only) |
| Full suite | 123 pass, 43 skip, 3 fail | VERIFIED |
| WARP and backend fixtures (`warp_t169.py`) | 0 failed | VERIFIED |

**AMD difference.** A temporary build wrote indices 0..n−1 with no vertex reuse: AMD was then 3/3 identical. So the indexed draw and the record layout are correct, and the difference appears only when vertices are actually reused. WARP and RTX do not show it, and the written bytes are proven equal. The bench draws many coplanar overlapping triangles, so small differences may decide which triangle wins a pixel. The cause inside the AMD driver or hardware is HYPOTHESIS. Whether real game frames would show it is unknown. **Treat this as unresolved on that GPU**, and do not enable the switch there until game frames are compared.

**Suite failures.** `test_rt_pool_srv_layout` and `test_vpc_watch` are inherited from T170's baseline. `test_spurs_kick_wake` is a known flaky timing test unrelated to RSX; it also failed on an isolated rerun, so it is not cleared by that rerun. This run covers all 169 `tools/test_*.py` scripts (168 at `fda8c9b` plus `test_vp_indexed`). T170's report gives 146 pass, 43 skip, 2 fail, a total of 191, so its totals are not directly comparable; I did not find what the other tests were. The comparison that holds is the failure list: the same 2, plus the flaky test.

Existing pins (`test_t119_pins`, `test_rsxi_geom`, `test_vp_fetch_plan`) were not changed. They caught three wiring mistakes during this work, which were fixed in the code.

## 5. Expected relevance to race scenes

HYPOTHESIS until run. Game heavy frames show expand 28–31 ms, so this targets a real cost, but:

- **The real reuse is unmeasured.** T95/T99's fixture gives 1.5×, and T162 says 1.5–3×. `[vp-indexed]` gives the real figure in one run.
- **Without fast fetch, 1.5× reuse shows no time gain,** only 29% fewer upload bytes. Fast fetch has never been validated in the game.
- **Frame time may not follow.** T170's expand saving was offset by `other`, and light frames are limited outside RSX.
- **GPU vertex-shader invocations may fall** with reuse (unmeasured). That could matter in the 84 ms GPU-wait mode, whose link to this is unknown.

## 6. Integration risks

- The AMD integrated GPU pixel difference (section 4).
- Not combined with `RSX_VP_PARALLEL`, so it cannot stack with integrated-GPU parallel gains.
- Off under `RSXI`, so RSXI captures do not show indexed draws, and a capture run differs from a normal run.
- Indexed records are not yet tested with real game shaders, draw patterns or early replays; the bench debug layer run does not cover those.
- The new code sits in the hot path but behind a read-once switch. Switch-off identity is shown by pixels and timing on the bench, not in the game.
- The branch is based on T170's head, so integration depends on T170. T173's jump-table fix is needed for long runs because of the `0x00CB7FA8` crash.

## 7. Recommended runtime A/B validation

Run on the RTX 5060, with T173's fix, in a local session, without `D3D12_DBG`, after checking `nvidia-smi` for other GPU users. Same route, at least 3 interleaved runs per arm:

1. `RSX_VP_COMPACT=1` (control)
2. `+ RSX_VP_FAST_FETCH=1 RSX_FP_SCAN_MEMO=1`
3. `+ RSX_VP_INDEXED=1` (on 1)
4. `+ all` (on 2)

Measure:

- corners/verts from `[vp-indexed]`, and `fallback`
- p50/p95 of heavy and light frames, plus expand, `other`, record and wait
- `upload_mb`
- GPU-wait frames
- captured frames of the same scenes, compared by eye and by hash; a separate debug-layer run

Accept only if heavy p50 improves beyond run-to-run spread with no visual change and no debug-layer errors. Stop at reuse near 1.5× if arm 3 shows nothing against arm 1; then the choice is arm 4 only.

## Reproduce

Tools are in `generated/analysis/t174/tools/` (private; the commit hook accepts only `.py` tools, so `setup_t174.sh`, `perf_t174.sh`, `validate_t174.sh`, `diag_t174.sh` and `upload_bw_t174.c` stay untracked). Logs are in `ev/` and `runs/`, also untracked.

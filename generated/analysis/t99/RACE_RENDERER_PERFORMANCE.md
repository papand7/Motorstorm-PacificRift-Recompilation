# T99: Race renderer performance analysis

- **Worktree:** `ps3recomp-t99`, branch `agent/t99-renderer-performance`, based on T96 `bd09877`.
- **Commit:** `db2aa90`. Not merged or pushed.
- **Scope:** offline only, with no game build and no launch. T98's executable and run directory were not touched.
- **Ownership:** no other T99 existed. motorstorm01-8d (busy, T98) is the only peer.

## 1. Evidence from T96I (run `20261027-110231-t96i-race-present`)

| Observation | Value | Status |
|---|---|---|
| First race guest frame | pass 2126: 966 records, 338.7 ms, of which `record` 338.2. Early replay #1 at 392,982 vertices. Pass 2127: 445 records, 1,475.2 ms, of which `record` 1,474.3 | VERIFIED |
| GPU waits | `gpu-drain` 0.0 ms in both passes; `next-frame` 0.0; `submit` 0.4 / 0.7 ms | VERIFIED |
| Steady state | passes 2127 → 2137 between 202.97 s and 204.02 s: 10 passes, i.e. 5 guest frames (2 passes each) per second. No pass ≥ 200 ms after 2127 | VERIFIED (about 1 s of data) |
| Guest ref waits | 0 ms after the first frames | VERIFIED |
| Pacing set by the renderer? | **Not decided.** Each pass < 200 ms still allows up to about 400 ms of renderer time per guest frame. The frame-clock thread also delivers vblank and flip events, so a busy renderer can slow the guest without any ref wait | **BLOCKED** (needs the instrumentation below) |

## 2. Hot paths (Phase 1)

**The thread:** one frame-clock thread (`port/main.cpp` `frame_clock`) runs everything in series:
- the FIFO drain (method decode plus every draw callback);
- vblank and flip ticks for the guest;
- `render_frame()` passes;
- the window pump.

**Anything below can block presentation and delay the guest's vblank events.**

| Work | Where | First-use | Recurring per guest frame (about 1,411 records) |
|---|---|---|---|
| VS lookup `vp_get_vs` | draw callback (drain) | `rsx_vp_decompile` + `D3DCompile` per new VP | FNV-1a over the whole VP upload (up to 8 KB) plus a linear cache scan, **every draw**. Synthetic: 8.5 ms per 1,411 draws |
| Vertex expansion `upload_*_vp*` → `read_vp_vertex` | draw callback | — | 16 × `rsx_fetch_attrib` per **expanded** vertex, 256 B each into WC upload memory. Synthetic: 11–16 ms per 432k expanded vertices (≥ 393k per race frame) |
| Index decode `read_guest_index` | draw callback | — | 2–3 reads per index (count pre-pass plus expansion). Negligible |
| Record build, `vp_record_cb` | draw callback | — | 8,448 B of VP constants per record into WC: about 12 MB per frame |
| Early replay | draw callback → `render_frame` | — | one extra submit plus `wait_for_gpu` per 393k vertices. T96I: 0 ms wait, 0.4 ms submit |
| Texture bind `vp_upload_tex_slot` | `render_frame` prepass (`record`) | resource creation plus conversion | linear scan of 96 slots per unit, a sparse checksum once per texture per frame, and conversion when the guest bytes change |
| SRV writes | prepass | — | 16 descriptors per record |
| PSO lookup `vp_get_fp_pso` | prepass **and** draw loop (twice per record per pass) | FP decompile + `D3DCompile` + `CreateGraphicsPipelineState`, synchronous | FP hash plus a linear scan, twice per record |
| Command recording | `record` | — | per-record state, root constants, draws |
| GPU fence waits | `wait_for_gpu` at each pass, `move_to_next_frame` | — | 0 ms in T96I |
| Frame-end bookkeeping | `render_frame` tail | — | small (`tail` 0.1 ms) |

**Confirmed and hypothetical:**
- **VERIFIED:** the 1.8 s first race frame is spent in `record`, which contains texture binding, both PSO lookups and command recording. It is not GPU wait, buffer growth or copying.
- **HYPOTHESIS, the most likely:** the 1.47 s is first-use FP/PSO creation (synchronous `D3DCompile` + `CreateGraphicsPipelineState`) for race materials. First-use texture conversion is the second candidate.
- **HYPOTHESIS:** per-frame CPU work that scales with vertices (expansion plus WC writes) is about 15–40 ms per guest frame. That estimate is synthetic and excludes guest-memory cache misses. On its own it does not explain 200 ms.
- **UNKNOWN:** the steady-state split between drain, passes and other work (guest vblank handlers, sleep). That is what §3 measures.

## 3. Instrumentation (`db2aa90`, off by default)

**Usage:** `RSX_FRAME_PERF=<first N guest frames>[,<every K-th after>][,<max lines, default 400>]`, for example `RSX_FRAME_PERF=12,10`. It prints one stderr line per selected guest frame:

```
[rsx-frame-perf] gframe= pass= wall_ms= | passes= early= records= draw_calls= verts= upload_mb= | drain_ms= draw_cb_ms= expand_ms= flush_ms=
 vs=miss/calls miss_ms= | rf_ms= (in_drain) record_ms= [tex ms n= | pso ms n= miss= miss_ms= | cmd ms] submit_ms= wait_ms= present_ms= | other_ms=
```

| Field | Meaning |
|---|---|
| `gframe` | the guest-frame number, closed by a presenting pass that is not an early replay. `pass` is the old `frame=` |
| `early`, `records` | early replays and records per guest frame |
| `vs` / `pso` miss | count and duration (PSO miss comes from the existing miss counter; a VS miss is a new cache entry or a call of 1 ms or more) |
| `expand_ms` | draw-callback time minus early replays and VS compiles |
| `verts`, `upload_mb` | expanded vertices written, × 256 B |
| `record_ms` | split into tex, pso and cmd; plus submit, wait (GPU drain plus next-frame) and present |
| `drain_ms`, `other_ms` | the whole FIFO drain, and wall time minus drain minus passes outside the drain |

**Design:**
- QPC microseconds; fixed counters; a bounded number of lines; nothing written per draw.
- When off, each wrapped call costs one flag test.
- Wrappers are bound by object-like macros after each unchanged original; the draw wrappers are installed only when the variable is set. Existing bodies are byte-identical, so all existing pins pass.
- Phase timing reuses `rf_phase.h` through an unreachable `RF_PHASE_MS` threshold, so no `[rf-phase]` lines appear unless `RF_PHASE_MS` is set.
- Overhead when on: about 10 QPC reads per record, under 1 ms per guest frame (estimate).
- **Limit:** counters are plain fields. A guest-thread drain that overlaps a frame-clock pass can lose counts, but never alters rendering.

## 4. Vertex expansion (Phase 3; synthetic, `bench_vp_expand`)

**Workload:** 1,400 T94-shaped batches (256 u16 indices, restart every 5), through the real `rsx_fetch_attrib`, into `PAGE_WRITECOMBINE` memory, on a Ryzen 5 9600X. 432,585 expanded vertices from 286,993 unique vertices. Not game timing.

| Strategy | 1 attr (T94 batch) | 4 attrs | 8 attrs | Output |
|---|---|---|---|---|
| S0 current | 10.8 ms, 106 MB | 13.5 ms | 16.2 ms | — |
| S1 staged copy | ×0.95 | ×0.96 | ×0.96 | identical |
| S2 per-batch vertex cache | ×1.24 | ×1.22 | ×1.25 | identical (byte-checked) |
| S3 indexed (256 B unique + u16 IB) | ×1.33, 71 MB | ×1.22 | ×1.27 | equal after re-expansion |
| S4 indexed + compact attributes | ×5.9, 5 MB | ×2.8, 18 MB | ×1.7, 36 MB | needs VS input-layout changes |

**Theoretical amplification:**
- T94 batch: 309 vertices written for 205 indices / 204 unique (1.5×); a plain 256-index strip writes 762 (about 3× unique).
- 256 B per vertex against 12 B used for T94's float3 batch: 21×.
- About 100 MB+ uploaded per race guest frame, about 0.5 GB/s at 5 fps. That is well within WC bandwidth.

**Conclusion (synthetic):** an indexed path would save about 3–5 ms per guest frame, and a compact layout about 9 ms on top. **Unless the instrumentation shows `expand_ms` dominating, expansion is not the 5 fps cause.**

## 5. Ranked candidates

| # | Candidate | Expected benefit | Complexity | Correctness risk | Status of evidence |
|---|---|---|---|---|---|
| 1 | **Measure:** build `db2aa90` + one bounded launch with `RSX_FRAME_PERF=12,10`, a 300 s cap and no target | decides everything below | trivial | none (off by default) | needs authorization |
| 2 | Persistent shader/PSO cache (DXBC keyed by HLSL hash on disk + `ID3D12PipelineLibrary`) | removes the first-use compile stall (≤ 1.5 s per new material set) on later runs | medium | low: identical bytecode, no draw skipped | if `pso miss_ms` confirms |
| 3 | One PSO lookup per record per pass (keep the prepass result in the record), and skip VS hashing while the VP upload is unchanged (generation counter) | about 10 ms per guest frame (est.) | low | low | synthetic hashing cost measured |
| 4 | Per-batch vertex cache in strip/quad expansion (S2) | ×1.2 on expansion, about 2–4 ms per guest frame | low | very low (byte-identical output, testable offline) | synthetic |
| 5 | Grow the VP buffer when early replays recur | fewer submits; T96I shows 0 ms waits | low | low | low value now |
| 6 | Indexed draw path plus compact vertex layout | up to about 10–12 ms per guest frame, 20× less upload | high | medium–high (VS layout, record format, restart semantics) | defer unless `expand_ms` dominates |
| — | Asynchronous PSO compilation with draw skipping | — | — | **rejected:** it drops or defers draws | — |

Draw dropping, frame skipping and geometry reduction are not recommended.

## 6. Offline results

| Test | Result |
|---|---|
| `test_rsx_frame_perf` (new: selection, clamps, line format, 11 pins) | 0 failures |
| `bench_vp_expand` (synthetic, with correctness checks) | 0 failures; numbers above (`logs/bench_vp_expand.txt`) |
| Renderer suite (41 tests) | 32 PASS / 9 SKIP (POSIX-only) / 0 FAIL (`logs/suite_t99.txt`) |
| TU compile, `rsx_d3d12_backend.c` and `cellGcmSys.c`, project clang-cl flags | rc=0. No new warning kinds (3 more `deprecated-declarations`, 4 more `declaration-after-statement`) |
| `audit_public.py --staged` | the 25 pre-existing BLOCKs, none in T99 files |

## 7. Risk and next task

- **Instrumentation risk:** low. It is off by default, and the originals are unchanged.
- **Recommended next task (T100):** one build of `db2aa90` and one bounded launch with `RSX_FRAME_PERF=12,10`, `RF_PHASE_MS=200`, a 300 s session and no target. Then:
  - if `pso miss_ms` accounts for the first-frame stall, implement candidate 2;
  - in steady state, act on whichever of `drain_ms`, `expand_ms`, `record_ms` and `other_ms` dominates. If `other_ms` dominates, the limit is on the guest/PPU/SPU side, which is T89B territory, not the renderer.

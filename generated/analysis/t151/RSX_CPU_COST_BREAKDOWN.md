# T151: RSX CPU cost breakdown (renderer work outside texture-snapshot hashing)

Labels: VERIFIED (measured), PARTIAL (measured once, or synthetic), HYPOTHESIS (inferred), BLOCKED (needs a game run).

## 1. Sources

**In game (T149 race runs of the T146 exe, one run each; no game was run by T151):**
- `[rsx-frame-perf]` (`RSX_FRAME_PERF=12,1,100000`), medians of the last 400 frame-clock passes.
- Logs: `generated/runs/20261028-201735-t149-ab-p0r1` (P0, T146 defaults) and `…-202136-t149-ab-p1r1` (P1, performance preset).

**Offline (T151):**
- `libs/video/tests/bench_draw_path.c` (T119): the real backend TU with the game's flags on the host D3D12 device. A race-shaped frame of 2000 indexed `TRIANGLE_STRIP` callbacks of 256 u16 indices, with a restart every 5 indices and stride-28 vertices (float3, 2 × ubyte4, float2).
- `RSX_DRAW_SPLIT=1` gives the per-stage split inside the draw callback.
- Arms are interleaved, 31 frames each, and medians are taken over frames 6–31.
- Host: Ryzen 5 9600X with an RTX 5060.

## 2. Mapping the brief's 16 categories onto the existing counters

No new profiler was needed. These existing counters are all opt-in and are read once:
- `RSX_FRAME_PERF` (drain, draw callbacks, expansion, `render_frame` with record = tex / pso / cmd, submit, wait, present);
- `RSX_DRAW_SPLIT` (T119: entry, room, count, emit, post, fields, vs, extra, texsnap, cb_fp, cb_vp, cb_rest);
- `RF_PHASE_MS` (render_frame phases);
- `RSX_GPU_PROF` (T143);
- `PS3_CRITICAL_PATH_TRACE` (T134).

The timers are exclusive per stage: the split's early replays and VS compiles are subtracted, and its total equals `expand_ms` (T119, VERIFIED).

| # | Category | Counter | P0 game | P1 game | Offline (P1-like: compact + epoch) |
|---|---|---|---:|---:|---:|
| 1–3 | FIFO parsing, method decode, state updates (+ non-draw callbacks) | `drain − draw_cb` | ≈ 6.7 (incl. tex-snapshot binds) | **≈ 3.2** (of which tex snapshot ≈ 1.3) | not driven (the bench calls callbacks) |
| 4 | Draw preparation (entry, room, count, fields, extra, VS lookup, cb_*) | split minus emit | — | — | **1.6** |
| 5–6 | Vertex attribute decoding + conversion/expansion (emit) | split `emit` | ≈ 43 of `expand` 112 (rest = snapshot 69) | **≈ 14** of `expand` 15.7 | **9.2** |
| ↳ | attribute fetch + convert | no-fetch variant: emit 9.9 → 4.8 | | | **≈ 5.1** |
| ↳ | upload-heap writes (compact, 64 B/vertex) | no-write variant | | | **≈ 0.6** |
| ↳ | index read, strip assembly, vertex-cache lookups | remainder | | | ≈ 3.5 |
| 7 | Shader lookup/translation | `vs=` compiles, `miss_ms` | 0 per frame | 0 | 0 (VS memo hit) |
| 8 | PSO lookup / creation | `pso` (misses) | 1.5 (0) | **1.6 (0)**, n = 1983 | 1.1 (0), n = 2000 |
| 9 | Texture binding setup (excl. snapshot hash) | `tex` | 1.6, n = 15164 | **1.4**, n = 16656 | 0.6, n = 8000 |
| 10–13 | RT lookup/transitions, descriptors, barriers, command-list recording | `cmd` (= record − tex − pso) | 6.4 | **3.0** | 2.0 |
| 14 | Queue submission | `submit` | ≈ 0.1 | 0.1 | 0.1 |
| 15 | Host synchronization (GPU wait, frame fence) | `wait` | ≈ 0 | 0.0 | 0.0 |
| 16 | Other renderer work in `render_frame` | rf − record − submit − present | ≈ 3.4 | **≈ 3.4** | ≈ 0.3 |
| — | Present | `present` | — | 0.2 | 0.3 |
| — | Frame-clock idle (vblank, `Sleep(4)`, pump) | `other` | 4.3 | **54.3** | — |

**Counts and bytes per frame:**
- **P0:** 1803 records, 161 MB uploaded, 1 early replay.
- **P1:** 1983 records, 30.1 MB uploaded, 0 early replays.
- **Offline:** 2000 records, 613,797 expanded vertices, about 410,000 conversions, 38.2 MB (compact) or 150 MB (fat).
- Allocations in the draw path: none. The vertex cache and plan are static, and the upload heap is persistent (VERIFIED by code).

**Cannot be split further from these counters (BLOCKED, needs a game run):**
- RT lookup, descriptor allocation, barriers and command-list calls are one `cmd` timer.
- The P0/P1 "other `render_frame`" 3.4 ms needs `RF_PHASE_MS` in a game run; offline it is 0.3 ms.

## 3. Where the time sits (thread view, VERIFIED from code + P1)

- **The FIFO thread runs both stages.**
  - The drain (FIFO walk plus draw callbacks) and `render_frame` both run on `port/main.cpp`'s `frame_clock` thread. `rf_ms (in_drain 0.0)` means `render_frame` runs between drain passes, not inside them.
  - So, per guest frame, P1 does about 18.9 + 9.7 = **28.6 ms of serial RSX work** on one thread, and that thread is idle 54 ms.
- **Idle wait.** Between passes the thread sleeps a flat `Sleep(4)`, with `timeBeginPeriod(1)`.
  - The guest's spin on the RSX reference register already signals a "kick" event when the fence is not yet published (`cellGcm_ref_on_poll`).
  - The game's loop never waits on that event, so a fence the guest waits for is drained up to one tick late.
  - T24 audit item B5 named this; it was never implemented because `port/` was not tracked then.
- **P1 frame.** T149 found the P1 frame is gated by the PPU frame thread's own compute (56 ms) plus this serial RSX work; the guest's ref wait was 26 ms per frame. So any RSX work removed from the drain, or any idle latency removed, shortens that wait.

## 4. Top five renderer CPU costs outside the snapshot (before optimizing)

| Rank | Operation | P1 game ms/frame | P0 game ms/frame | Status |
|---|---|---:|---:|---|
| 1 | **Vertex emit:** attribute fetch/convert, index assembly, writes | ≈ 14 | ≈ 43 (fat 256-byte vertices) | VERIFIED (P0/P1 counters; split offline) |
| 2 | Other `render_frame` work (phases not yet split in game) | ≈ 3.4 | ≈ 3.4 | PARTIAL |
| 3 | FIFO walk, decode, state, non-draw callbacks (excl. snapshot) | ≈ 1.9 | — | PARTIAL (difference of counters) |
| 4 | Command recording (`cmd`: RT, descriptors, barriers, list calls) | 3.0 | 6.4 | VERIFIED |
| 5 | PSO lookup (no misses: 6–8 scans of the FP ucode per record) and texture bind setup | 1.6 + 1.4 | 1.5 + 1.6 | VERIFIED (counters); cause from code |

**Plus one serialization cost that is not CPU time:** the frame clock's `Sleep(4)` idle latency on fence waits. It is VERIFIED from code; its size in game is BLOCKED (model: 1.7 ms mean per wait, §5 of `RSX_CPU_ACCELERATION.md`).

**Inside emit (offline, compact):** fetch/convert ≈ 5.1 ms, then index/assembly/lookup ≈ 3.5 ms. Writes are only ≈ 0.6 ms. With fat records (the default) writes dominate: emit is 22.4 ms, and the fetch plan does not change it.

# T95: RSX Indexed Geometry and Vertex Expansion Audit

Offline only: no builds, launches, merges or pushes. Worktree `ps3recomp-t95`, branch `agent/t95-rsx-geometry-audit`, based on T94 `8ea1437` (T91 + T92). Commit `f4befa9` adds tests only; no backend change.

## 1. Verdict

- **No decoding defect found that inflates the vertex count (VERIFIED offline).** Draw word packing, index type and location, endianness, strip winding, fan and quad expansion, restart, and the per-frame reset all match NV4097 semantics and the independent reference.
- **The demand is inflated by the design (VERIFIED).** The VP path draws everything as a CPU-expanded triangle list, with no index buffer and no vertex reuse. Expanded vertices are about 3× the index count for strips and fans, 1.5× for quads, and 1× for lists. At 256 B per expanded vertex, every vertex costs 256 B whatever its attribute count.
- **786,433 expanded vertices is a plausible guest workload (HYPOTHESIS until T94's record).** It corresponds to about 262k strip indices (~1025 batches of 256), or 786k triangle-list indices (~3073 batches). That is an ordinary PS3 race frame (track, cars, shadow and reflection passes).
- **One accounting-only over-count (VERIFIED, small).** A strip or fan reserves an upper bound that ignores restarts: 9 extra vertices per restart index. It inflates `frame_want` (and so the grow size), but not the vertices actually written.

## 2. Path audited

`FIFO walker (cellGcmSys.c) → rsx_process_method (rsx_commands.c) → d3d12_draw_{arrays,indexed} → upload_*_vp[_indexed] → vp_reserve → vpvb_reserve`

| Item | Behaviour | Status |
|---|---|---|
| Packet header | type 0 incrementing, type 2 NI, count `[28:18]`, method `w & 0x1FFC` (`cellGcmSys.c` method loop); one `rsx_process_method` per data word | VERIFIED |
| DRAW_ARRAYS 0x1814 / DRAW_INDEX_ARRAY 0x1824 | `first = [23:0]`, `count = [31:24] + 1` (`rsx_commands.c:836-839, 892-895`); max 256 per word | VERIFIED |
| Incrementing 2-word 0x1824 packet | 2nd word goes to 0x1828 (unknown), so one draw. libgcm emits NI. | VERIFIED |
| Index DMA 0x1820 | `[3:0]` location (0 local), `[7:4]` type (0 u32, 1 u16) (`read_guest_index`, `rsx_d3d12_backend.c:8419`) | VERIFIED |
| Endianness | big-endian u16/u32 | VERIFIED |
| Topology | 5 list, 6 strip, 7 fan, 8 quads expanded; 1-4, 9 (quad strip), 10 (polygon) not wired: dropped, not reserved | VERIFIED |
| Strip winding | odd triangles `(p0, v, p1)`: same facing as D3D's `(v1, v0, v2)` | VERIFIED |
| Batch seams | `prim_stream.h` continues a strip/fan across batches of one BEGIN/END epoch | VERIFIED |
| Restart 0x1DAC/0x1DB0 | indexed strips/fans only; u16 with a value > 0xFFFF is inactive | VERIFIED |
| Degenerates | emitted like hardware assembles them (zero-area, culled by the GPU) | VERIFIED |
| CALL/RET | one return slot (`s_fifo_calloff`), RET consumes and clears it (`cellGcmSys.c:2388-2432`); NV40 has one level too. No replay path. | VERIFIED (source) |
| Semaphore ACQUIRE block | breaks before the packet is consumed; draws are not re-run | VERIFIED (source) |
| Frame accumulator | `vpvb_end_frame` (want reset) and `vp_vb_offset = 0` both happen only at `render_frame` (present and clear paths) | VERIFIED |
| Draws outside BEGIN/END | still passed to the backend | observed; not a source of inflation |

## 3. Expansion formulas (expanded vertices per BEGIN/END stream of n indices)

| Topology | Emitted | Reserved (`want`) | vs. index count |
|---|---|---|---|
| TRIANGLES | n | n | 1× |
| QUADS | 6·⌊n/4⌋ | same | 1.5× |
| TRIANGLE_STRIP / FAN | 3·Σ(Lᵢ−2) over restart segments | 3·(n−2) | ≤3× |
| restart over-reservation | — | +9 per restart index | accounting only |

A 256-index strip batch becomes 762 vertices, or 195 KB of upload. Per index, a strip costs 3 × 256 = 768 B against 2–4 B on the RSX.

## 4. Tests (`f4befa9`)

`libs/video/tests/test_geom_expand.c` + `tools/test_geom_expand.py`:
- the real decoder, `rsx_commands.c`, is linked;
- reference: per-epoch concatenation plus closed-form counts, written separately from `prim_stream.h`.

Result: 18 harness checks plus 10 source pins, **0 failures** (`logs/test_geom_expand.txt`). `test_prim_stream` and `test_rf_phase` still pass. Audit: the 25 BLOCKs already in the repo, none in the new files (`logs/audit.log`).

Cases covered:
- NI 256+44 split;
- incrementing packet;
- maximum word;
- zero-length packet;
- draw outside BEGIN/END;
- list with repeated indices;
- strip across 4 batches;
- fan;
- quads;
- stitched degenerates;
- restart (u16 0xFFFF, plus an inactive 0x1FFFF);
- u16 data declared u32;
- 520-strip overflow frame, then grow, then a fresh frame.

## 5. Amplification candidates

| Candidate | Input | Expected | Actual | Factor | Location | Test | Confidence |
|---|---|---|---|---|---|---|---|
| No vertex reuse (list expansion) | 256-idx strip | RSX: 256 index fetches | 762 expanded | ~3× | `upload_strip_vp[_indexed]` | strip cases | VERIFIED, by design |
| Restart upper bound in `want` | 254 idx, 50 restarts | 306 | want 756 | 2.5× of `want` only | `ps3_prim_stream_max_tris`, `prim_stream.h` | restart case | VERIFIED; affects grow size, not writes |
| Vertices of draws dropped by `batch_full` | draw after 2048 records | not uploaded | uploaded, no record | wasted space | `d3d12_draw_indexed_body`: upload before `batch_room()` | source | VERIFIED (source); same total demand |
| Wrong index format | u16 read as u32 | n | n | 1× | `read_guest_index` | format case | ruled out as count inflation |
| CALL/RET replay, stale frame want | — | — | — | — | walker / `vp_vb_budget.h` | frame case, pins | ruled out |

None explains 786k as a decode error. If T94 shows mostly strip batches, the 3× is the expected cost of the list expansion.

## 6. T94 comparison (record received)

T94 run `generated/runs/20261027-100335-t94-race-diag` (exe `133f60f9…a15cf`), first `vertex_buffer_full`:

`frame=2133 hdr=0x40141824 (NI, 5 batches) data_i=1 data=0xFF00AE92 first=44690 count=256 call_target=0 prim=6 indexed u16 local restart 0xFFFF idx_restarts=51 idx 4594..4797 head 65535,4594,4595,4596 want=768 used=393216 cap=393216 frame_want=590220 frame_short=1434 draws=967/2048`

| Check | Result | Status |
|---|---|---|
| Command genuine | header re-read matches; NI 0x1824, 2nd of 5 batches; not inside a CALL | VERIFIED |
| Decode | `0xFF00AE92` → first 44690, count 256 (the harness decodes the same word) | VERIFIED |
| Index format | u16; range 4594..4797 is tight and contiguous, not the scatter a wrong size gives | VERIFIED |
| Topology | 4-index strips between restarts: quads drawn as strips | VERIFIED (head + count) |
| Writes | 51 quads × 6 = **306** vertices (204 unique → 1.5×) | VERIFIED (fixture) |
| Reservation | 3·256 = **768** (continued stream: batch 0 ended mid-quad) | VERIFIED (fixture reproduces 768) |
| Buffer fill | `used` counts written vertices: 393,216 written by draw 967 | VERIFIED |
| Accumulation | `frame_want − frame_short − used` = 590,220 − 1,434 − 393,216 = **195,570** reserved but never written (restart over-reservation) | VERIFIED (arithmetic) |

Fixture: test case 10 in `test_geom_expand.c` rebuilds this batch (period-5 restart pattern continued across the batch seam) and gets want 768 and writes 306. Log: `logs/test_geom_expand.txt`.

What this means:
- **The overflow is real.** 393,216 vertices were actually written by roughly the middle of the frame (967 of 2048 records). Restart over-reservation never refuses a draw early: `got = min(want, room)`, and a strip writes until `o + 3 > got`.
- **`frame_want` is inflated by about 1.5×** on this content: 590,220 reserved against 394,650 needed (written plus short), so writes are 0.67 of the reservation. The T87B grow decision (`frame_want ≥ 786,433` → 1,048,576, the ceiling) therefore over-sizes the buffer. If the mix holds, the frame needs roughly 786,433 × 0.67 ≈ 525k written vertices (HYPOTHESIS: only half the frame has been seen).
- **No decode defect.** The real cost is the list expansion: 1.5× for these quads, plus 256 B per vertex, whatever attributes are used (this draw has a single float3 position, 24-byte stride).

## 7. Uncertainties

- The original command evidence for the first race frame isn't available yet, so the topology mix is unknown.
- Quad strip (9) and polygon (10) are dropped. That is missing geometry, not inflation.
- Hardware behaviour for draws outside BEGIN/END was not verified.

## 8. Correction (not made, kept separate)

Recommended:
- **Restart-exact `want` (now justified by T94):** count restarts in the batch before reserving. That drops this frame's reservation by about 1/3 and the grow target with it. It is an accounting fix only and changes no rendering.
- **The structural fix:** an indexed draw path (upload unique vertices plus a D3D12 index buffer) would remove the ~3× and the 256 B-per-index cost. It is a larger change, not a speculative decode fix.

Neither is a vertex cap or a draw skip.

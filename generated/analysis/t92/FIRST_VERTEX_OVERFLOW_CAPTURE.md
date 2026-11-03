# T92: capture of the first vertex-buffer overflow (offline, 2026-10-27)

- **Worktree:** `ps3recomp-t92`, branch `agent/t92-first-vb-overflow`.
  - Commit `0882c81` on `07db971` (T87B).
  - Patch: `t92/patches/0001-RSX_VBO_DIAG-one-record-of-the-first-vertex_buffer_f.patch`.
- **Ownership:** T88 is mine, and there is no T88B. T91 belongs to motorstorm01-3c, who was told before I started.
- **Not done:** no build, no launch, no merge, no push. The vertex budget and the drop behaviour are unchanged.
- **Diagnostic only:** `RSX_VBO_DIAG` is off by default.

## 1. Where each field comes from (Phase 1, VERIFIED from source)

| Field | Origin | Available before T92 at the overflow site? |
|---|---|---|
| Header offset | `cellGcmSys.c` walker → `s_state.fifo_cmd_off` (per header) | yes (`st->fifo_cmd_off`) |
| Header word, method, count | walker local `w`; `method = w & 0x1FFC`, `count = (w>>18)&0x7FF` | **no**; stored only under `GCM_STALL_MS` (`s_gsw`) → added `st->fifo_cmd_hdr` |
| Data index | walker inner loop `i` | **no** (only `s_gsw`) → added `st->fifo_cmd_data_i` |
| CALL return / target | `s_fifo_calloff` → `st->fifo_call_ret`; target is a local at the CALL | return yes; target **no** → added `st->fifo_call_target` |
| GET / PUT | `s_fifo_getoff` (equals the header offset during the data loop); PUT = `ctrl+0` | no → `cellGcm_diag_fifo()` |
| Guest index count, first | `rsx_commands.c` `DRAW_INDEX_ARRAY`/`DRAW_ARRAYS`: `[31:24]+1`, `[23:0]` → `count`, `first` args | yes |
| Topology | `st->primitive_type` (`SET_BEGIN_END`) | yes |
| Expansion factor | `upload_*_vp*`: strip/fan `ps3_prim_stream_max_tris(count)·3` (762/768 per 256), quads `count/4·6`, tris `count` | yes (`want`) |
| Expanded vertex stride | `VP_VERT_STRIDE` = 16 × float4 = 256 B | yes |
| Used, capacity, frame demand | `vp_vb_offset/256`, `s_vpvb.cap`, `s_vpvb.frame_want/short` (`vp_vb_budget.h`) | yes |
| Draw-record count | `s_d3d.draw_count` / `MAX_DRAWS` (`batch_room`) | yes |
| Frame identifiers | `s_d3d.frame_count`, `cellGcm_flip_request_count()`, `vp_parity` | yes |

The guest's own count is the draw word's count (at most 256). The backend's count is `want`, the expanded triangle-list vertices. The record prints both.

## 2. Source changes (`0882c81`, 6 files, +~430 lines)

- **`include/ps3emu/vbo_diag.h` (new, header-only):**
  - `RSX_VBO_DIAG=<n>` gives at most n frames (1..64) with a record; it is off when unset.
  - Per frame, it captures the **first** `vertex_buffer_full` and the **first** `batch_full`. Later refusals are counted.
  - A `frame_end` line reports the suppressed counts.
  - Fields that are not available print `na`.
  - Off cost is one load and a branch per refusal and per frame end, with no locks; the only writer is the walker thread.
- **`libs/video/rsx_commands.h`:** three diagnostic fields next to `fifo_cmd_off`.
- **`libs/video/cellGcmSys.c`:**
  - The walker sets `fifo_cmd_hdr`/`fifo_cmd_data_i` per header and per data word, and `fifo_call_target` at CALL/RET. These are plain stores.
  - Two read-only helpers: `cellGcm_diag_fifo(get, put)` and `cellGcm_diag_read_io(io, out)` (one word through `gcm_io2ea`, 0 if unmapped).
- **`libs/video/rsx_d3d12_backend.c`:**
  - `vp_reserve()` now takes the draw context from its 6 callers.
  - On `want && !got` it calls `vbod_capture()`, after the existing `da_fail`.
  - `batch_room()` captures the first `batch_full`.
  - `vbod_frame_end()` runs at both per-frame reset points (present `:~7300`, clear boundary `:~7880`).
  - `vbod_capture()` re-reads the header word and the data word from the command buffer, so a header changed after decode shows up. It also scans this draw's indices (≤ 256; min, max, restarts, first 4).
- **`tests/test_vbo_diag.c` (new) + `CMakeLists.txt`:** registered as `vbo_diag`.
- **Checks:**
  - Single-TU compile of `rsx_d3d12_backend.c` and `cellGcmSys.c` with the T64C build's flags: both OK.
  - New warnings are only the pedantic classes the tree already emits (`-Wunsafe-buffer-usage`, `-Wdeclaration-after-statement`, `-Wpadded`, `getenv`) (`t92/logs/tu_*`).
  - `audit_public.py --staged`: the same 25 pre-existing BLOCKs, none in changed files (`logs/audit_t92.txt`).

## 3. Expected log format

```
[vbo-full] RSX_VBO_DIAG=4: first vertex_buffer_full / batch_full of a frame recorded, at most 4 frame(s)
[vbo-full] reason=vertex_buffer_full frame=0 flip=0 parity=0 get=0x00001008 put=0x00001974 cmd_off=0x00001008 hdr=0x49601824 subch=0 method=0x1824 hdr_count=600 data_i=513 hdr_reread_match=1 data=0xFF020100 data_first=131328 data_count=256 data_matches_draw=1 call_ret=0x00000000 call_target=0x00000000 draw=strip indexed=1 prim=6 first=131328 count=256 idx_off=0x00100000 idx_dma=0x00000000 idx_min=256 idx_max=511 idx_restarts=0 idx_head=256,257,258,259 a0_off=na a0_stride=na a0_fmt=na want=768 got=0 used=393216 room=0 cap=393216 vert_bytes=256 frame_want=394746 frame_short=1530 vp_byte_off=100663296 draws=513/2048
[vbo-full] frame_end frame=0 at=present suppressed_vertex_buffer_full=86 suppressed_batch_full=0 frames_recorded=1/4
```

This sample is from the test (§4.2). A record is one line of fewer than 1000 characters.

**How to read it:**
- **Real geometry:**
  - `method=0x1824` with `data_matches_draw=1` and `hdr_reread_match=1`;
  - `cmd_off` inside a CALLed 16 KiB push-buffer slot (`call_target` in `0x01A00000`/`0x01D00000`+);
  - plausible `idx_min/max` against the attribute's buffer, and `a0_stride` > 0.
- **Misdecode:**
  - a header at an unexpected `cmd_off` (for example a slot tail or the main ring);
  - `hdr_reread_match=0`;
  - `data_matches_draw=0`;
  - `idx_max` far beyond any vertex buffer, or an absurd `hdr_count`.

## 4. Offline tests

`t92/tools/run_t92_tests.cmd` uses clang with `-Wall -Wextra -Werror` against the `ps3recomp-t92` headers.
- `test_vbo_diag`: **PASS, 44 checks** (`logs/test_vbo_diag.txt`).
- T88's `test_vb_overflow` against the same headers: **PASS, 28 checks** (`logs/test_vb_overflow_t92.txt`).

The test sends synthetic command streams through a walker that decodes the way `cellGcmSys.c` does: JUMP, CALL/RET, incrementing and non-incrementing headers, 11-bit count. Draws then go to a model of the indexed strip path that uses the real `vp_vb_budget.h` and `prim_stream.h`.

| § | Case | Result |
|---|---|---|
| 0 | Off by default, parsing, nothing printed when off | PASS |
| 1 | Valid indexed strips, 256 indices per word, a frame that fits prints nothing | PASS |
| 2 | One 600-batch NI header: **first refusal at batch 514** (`data_i=513`), the same as T88 §3; header offset, method, count, `want=768 got=0`, `used=room/cap`, `frame_want=394746` (762+513·768), `frame_short=1530`, `draws=513/2048`, index sample | PASS |
| 3 | Subsequent overflows suppressed (86) and reported at `frame_end` | PASS |
| 4 | Inside a CALL: `call_ret`, `call_target`, header in the slot | PASS |
| 5 | Re-arms per frame; `RSX_VBO_DIAG=2` caps 4 overflowing frames at 2 records | PASS |
| 6 | Draw-record boundary: the 2049th record is `batch_full` (header 2, word 1), `want=na`, 8 suppressed | PASS |
| 7 | Malformed: a header at an unexpected offset is reported as decoded; garbage indices show as a huge `idx_max`; a header rewritten after decode gives `hdr_reread_match=0` | PASS |
| 8 | Unavailable: state not fed by the walker, or an unmapped data word, prints `na` | PASS |
| 9 | All 43 keys present; bounded worst-case line length | PASS |

**Limit:** the backend's fill logic (`vbod_capture`) is mirrored in the test rather than linked, since the D3D12 TU needs a GPU. The header, the budget and the stream accounting are the real code.

## 5. Cross-check: T87B run (Phase 4)

Run `generated/runs/20261027-084130-t87b-race-stall`, using PT µs as the clock.

- **VERIFIED: the first race frame overflowed.**
  - `stderr.log:72506/72509` (≈203.15 s): the same pair as T84E/T86I.
  - The 256-index strip on `rt=0x07B78D80`, then the display quad, at `flip=4038`.
- **VERIFIED: the frame that `render_frame` was closing at the stall is the overflowed frame.** Snapshot at 204.18 s:
  - `op=render-frame`, `op_age_ms=1063`;
  - `vp_vb_offset=100663296`, which is exactly 393216 × 256, so the half is full;
  - `vb_cap=393216`, `frame_want=0`, `draw_count=974/2048`.

  `frame_want=0` with the old cap is only possible between `vpvb_end_frame` (`:6028`, resets demand) and `vpvb_grown` (`:6002`), so the thread was inside `vp_vb_grow`.
- **Growth finished at 205.62 s:** `[VPVB] 393216 -> 1048576 verts (512 MB)`.
- **The demand implied by that growth:** `vpvb_next_cap` = demand × 1.25, rounded to 64 Ki. Reaching the ceiling means the frame asked for **≥ 786,433 expanded vertices**, at least 2× the capacity and at least about 1024 full 256-index batches, with 974 records.
- **Correction to T88 §8:** it said that snapshot showed the parity base after a reset. That was wrong: `vp_vb_offset` is relative to the half, and it was full.
- **T91 (motorstorm01-3c)** found independently that the stalled `memcpy` is `vp_vb_grow`'s 96 MiB copy out of the write-combined UPLOAD mapping (`:5995`), not the atlas.
- **Causation:** not inferred from timing alone. The overlap is established from state, not proximity: the overflow forces the grow, and the grow's copy is the present thread's time. Whether the ≥ 786k demand is real geometry is exactly what `RSX_VBO_DIAG` decides.

## 6. Combining with T91

- T91 is `ps3recomp-t91` (`agent/t91-render-frame-stall`): `12fb461` `RF_PHASE_MS`, then `00bf2c4` `VPVB_GROW_AT_FRAME_END`.
- `git merge-tree --write-tree agent/t92-first-vb-overflow agent/t91-render-frame-stall` is clean, with no conflicts (tree `967a11f`, `logs/merge_tree_t91.txt`).
- **For one combined diagnostic build:**
  1. Make an integration branch from `00bf2c4`.
  2. Cherry-pick `0882c81`, or apply the patch.
  3. Run `test_vbo_diag`, T91's tests and the renderer suite (`t84/tools/run_suite.cmd`).
  4. Do one build into a new `build/` dir.
- **Launch environment:** existing T87B variables plus `RSX_VBO_DIAG=4`, `GCM_STALL_MS=1000`, and `RF_PHASE_MS=<T91 value>`.
  - Add `VPVB_GROW_AT_FRAME_END=1` only if the run should get past the grow stall. The `[vbo-full]` record is printed before either grow path runs, so it is captured either way.
- **Reading order:** `[vbo-full] reason=vertex_buffer_full` (first race frame), then the `frame_end` suppressed count, then `[VPVB] grown`, then T91's phase lines, then `[stall]`.

## 7. Status

- **VERIFIED:** field origins, instrumentation, tests, T87B overlap by state.
- **BLOCKED until one authorized build and launch:** whether the first race frame's ≥ 786k-vertex demand is valid geometry or a misdecode.

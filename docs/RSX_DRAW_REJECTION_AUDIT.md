# RSX draw rejection audit: why the garage's display draws were discarded (offline, 2026-10-23)

**Evidence:**
- run `20261023-200314-garage-display-path` (exe `089a684e…`), its `[draw_acct]` lines and 6 RSXI frames;
- source `ps3recomp-int/libs/video/rsx_d3d12_backend.c`.

No launch for this milestone.

## Root cause (VERIFIED)

The D3D12 backend expands every vertex-program draw on the CPU into a triangle list. The result goes into one upload buffer per frame, `vp_vb`, whose capacity was fixed at `MAX_VERTICES` = 393,216 vertices per frame-parity half. An indexed 256-index triangle strip becomes 762 vertices.

The garage's frames fill that buffer before their last draws:

| Captured frame | Draws | Expanded vertices asked for | Last recorded draw |
|---|---|---|---|
| 1740 | 541 | ≈ 393,555 | — |
| 1830 | 543 | ≈ 393,660 | op 552: a 256-index strip; native `start_vertex` 392,898, 318 of 762 vertices kept; `start + vertices` = **393,216** |

From then on, every upload helper computes `maxv = 0`:
- `upload_tris_vp*` sets `count = maxv - maxv % 3 = 0`;
- `upload_strip_vp*` sets `tris = 0`;
- `upload_quads_vp*` sets `quads = 0`.

The helper returns 0. The draw body then reaches `if (emitted && batch_room())` with `emitted == 0` and returns, recording nothing and reporting no error.

The display pass comes after the scene, so all of it is lost:
- the first drops were a 4-vertex fan, then triangles of 6, 256 ×4, 104 and 6 vertices;
- the frame carries no display-targeted record, so `has_display = 0` and Present is never called.

**Exact code before the fix:**
- `maxv = (MAX_VERTICES * VP_VERT_STRIDE - s_d3d.vp_vb_offset) / VP_VERT_STRIDE` in the six `upload_*_vp*` helpers;
- the silent `return` after `if (emitted && batch_room())` in `d3d12_draw_arrays_body` and `d3d12_draw_indexed_body`.

**Why this is a defect:**
- RSX has no per-frame vertex limit; it reads vertex arrays from guest memory as each draw executes;
- the old `s_drop_draws` counter and the `[VBFULL]` line covered only the triangle-list helpers, and only with `VBFULL` set;
- the strip, fan and quad helpers (the garage's draws) truncated and dropped with no trace at all.

**Not shown:** that all 12,405 drops share this cause. The accounting then had no reasons. The new reason counters answer this in the next run.

Ruled out by the same run:
- batch overflow (`[d3d12] batch full` never printed);
- inline-array and immediate vertices (0 groups);
- pipeline readiness: the same frames recorded 541–543 vertex-program draws with built pipelines just before the drops.

## Early-return inventory (draw path)

| # | Where | Condition | Garage? | Correct per RSX? | Caller told? | Reason now |
|---|---|---|---|---|---|---|
| 1 | `d3d12_draw_arrays_body` / `_indexed_body` | `!s_d3d.pipeline_ready` | no (pipelines ready) | backend limitation | no | `pipeline_unavailable` |
| 2 | arrays body | `!s_d3d.vb_mapped` | no | allocation failure | no (logged at init) | `vertex_buffer_unavailable` |
| 3 | both bodies | `count == 0` | not seen | yes: zero work | — | `zero_vertex_count` (zero work) |
| 4 | both bodies | `count > MAX_VERTICES` | no (≤ 256) | backend limit | no | `count_over_limit` |
| 5 | indexed body | `!vp_vb_mapped \|\| !vp_root_sig` | no | allocation failure | no | `vertex_buffer_unavailable` |
| 6 | arrays body (fixed function), indexed body `else` | primitive not converted (lines, points, …) | not seen | no: the primitive is valid | first 3 logged | `unsupported_primitive` |
| 7 | six `upload_*_vp*` | `!state \|\| !vm_base \|\| !vp_vb_mapped` | no | — | no | `vertex_buffer_unavailable` |
| 8 | six `upload_*_vp*` | vertex attribute 0 not enabled | not seen | **questionable**: a vertex program may take its position from another input | no | `position_attrib_disabled` |
| 9 | `upload_strip_vp*` | `count < 3`; quads `count < 4` | not seen | yes: zero work | — | `too_few_vertices` (zero work) |
| 10 | six `upload_*_vp*` | **upload buffer full (`maxv == 0`)** | **yes: the garage display pass** | **no** | **no** | `vertex_buffer_full` |
| 11 | six `upload_*_vp*` | buffer nearly full: the draw is truncated | yes (op 552) | no | no | counted as `truncated` |
| 12 | `upload_vertices_from_rsx` / `upload_quads_from_rsx` (fixed-function buffer) | full | not seen | no | no | `vertex_buffer_full` / `too_few_vertices` |
| 13 | `batch_room()` | `draw_count >= MAX_DRAWS` (2048) | no (554) | backend limit | logged (powers of two) | `batch_full` |
| — | merge paths | the draw extends the previous record | yes | yes | — | merge, not a drop |

The categories below are not separate returns in this backend:
- index-buffer failure: indices are read through `read_guest_index`, which has no failure path;
- render target not ready: targets are resolved at replay;
- texture binding: never rejects a draw.

## Correction (generic)

`include/ps3emu/vp_vb_budget.h` plus `rsx_d3d12_backend.c`:
- **Room:** every vertex-program upload asks `vp_reserve(want)` for its room. That calls `vpvb_reserve`, which also records what the frame asked for and lacked.
- **Growth:** at the start of `render_frame`, after `wait_for_gpu()` (GPU idle):
  - if the frame did not fit, `vpvb_end_frame` returns its demand plus 25 %, rounded to 65,536 vertices and clamped to `VP_VB_MAX_VERTICES` = 1,048,576 (512 MB of upload heap, allocated only when needed);
  - `vp_vb_grow` creates the larger buffer and copies the frame's already-uploaded vertices to the same parity offset, so records stay valid;
  - it then releases the old buffer.
- **Failure:** an allocation failure keeps the old buffer, prints `GROWTH FAILED` and stops further attempts. No false success.
- **Current capacity:** the replay's vertex buffer view and every pointer into `vp_vb` now use the current capacity.
- **Unchanged:** guest commands, shaders, display-buffer selection, draw order, depth and stencil, synchronization and the present gate. Nothing is presented or drawn by the fix.
- **Limit:** the frame that first overflows still loses its tail. Recovering it would need a mid-frame flush. The following frames fit.

**Reason accounting:**
- each early return above calls `da_fail(DA_R_…)` (first one wins), and the wrappers reset it per callback;
- `[draw_acct]` adds:
  - `reasons=<name>:<n>/display:<n>,…`, `truncated=`, `truncated_verts=`, `vb_grows=`;
  - one line for the first drop of each reason;
  - up to 8 display-drop lines, each with `reason`, `prim`, `count`, `indexed`, `rt`, guest `flip`, `fp` and `vp_bytes`;
  - an `event=vertex_buffer_grow` line.
- It is still off unless `PS3_DRAW_ACCT_MS` is set.

## Fragment-program cache (no defect shown)

- **Pipeline key:** `vp_get_fp_pso` keys on `rsx_fp_code_hash` of the program **code** (constants excluded), plus VS, blend, render-target format, mask, cull and cube state. It does not key on the address. Changed code yields a new hash and a new pipeline.
- **Inline constants:** the patched constants are re-read from guest memory for every draw at record time (`vp_record_cb` → `rsx_fp_extract_consts` → `fp_k[]`).
- **Patch ordering:** the NV3062/NV308A patches write guest memory in FIFO order, so each draw sees the constants current at its position.

No change made.

## 2×AA surfaces

Not involved in the rejection; the drops happen before any target is consulted. The 2×AA layout (`0x3148`, pitch 10240, stored at 1280×720) is still unmodelled. It is a separate open item, with no correction in this milestone.

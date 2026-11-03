# T96: First race-frame vertex allocation and presentation fix

- **Worktree:** `ps3recomp-t96`, branch `agent/t96-race-frame-fix`.
- **Base:** T95 `0834eae`. That contains T87B `07db971`, T91 `00bf2c4`, T92 as T94's cherry-pick `8ea1437`, and the T95 tests.
- **Commits: `c7e84e3`, plus `bd09877`** (T97 review fix: `d3d12_present`'s flip display check). Not merged or pushed.
- **Scope:** offline only, with no game build and no launch. **Nothing here is verified at runtime.**

## 1. Defects corrected

| # | Defect (source) | Status before | Correction |
|---|---|---|---|
| 1 | Strip/fan reservation ignored restarts (`ps3_prim_stream_max_tris`). T94 batch: 768 reserved for 309 written | VERIFIED (T95, T94) | Exact count, `ps3_prim_stream_count_tris` |
| 2 | Draws past a full parity half were dropped (`vertex_buffer_full`): real writes reached 393,216 by draw 967 of about 2000 | VERIFIED (T94) | Early replay, then continue in the other half |
| 3 | Records past `MAX_DRAWS` (2048) were dropped (`batch_full`). VP draws also uploaded before checking for a record slot | VERIFIED (T95 source) | The same early replay; room is checked before the upload |
| 4 | `vp_vb_grow` at `render_frame` entry copied the frame's used bytes out of write-combined memory (96 MiB, about 2.5 s in T87B) | VERIFIED (T91) | Frame-end growth is now the default: 0 bytes copied, old buffer retired |
| 5 | T95 fixture had 52 restarts against the record's 51 (found by T97) | VERIFIED | Fixed; the batch writes **309**, not 306 |

## 2. Code changes (`c7e84e3`, 10 files, +726/−44)

- **`include/ps3emu/prim_stream.h`:**
  - `ps3_prim_stream_count_tris(s, count, restart, value, fetch, ctx)` replays the stream's "fewer than two vertices" state and the restart rule, without changing the stream.
  - `ps3_prim_tris_to_verts(tris, &ok)` refuses anything above 32 bits.
- **`include/ps3emu/vp_flush.h` (new):**
  - `vpf_decide` returns FITS, FLUSH or REFUSE, with 64-bit `used + want` and `want + carry`.
  - `vpf_state` tracks the draws already replayed this frame, whether any was a display draw, and whether to keep the targets.
- **`libs/video/rsx_d3d12_backend.c`:**
  - **Exact reservation:** `vp_strip_verts` and `vp_draw_want` give the exact reservation. Both strip uploads use it.
  - **`vp_make_room`:** every VP draw path calls it before taking its record offset (draw_arrays quads, list/strip/fan, and indexed).
    - It flushes when the draw doesn't fit the half or the record array.
    - A `TRIANGLES` batch that would have merged into the previous record moves that record's partial triangle (≤2 vertices, ≤512 B) into the new half, so the list stays in phase.
  - **`vp_flush`:** runs `render_frame()` with `s_present_this_frame = 0`, the existing offscreen-replay mode. The replay flips parity as usual.
  - **`render_frame` changes for an early replay:**
    - the following replay skips the initial backbuffer and shared-DSV clear (`keep_targets`);
    - an early replay neither closes the `vpvb` budget frame nor grows the buffer;
    - `vpf_boundary` resets the flush state only on a real replay.
  - **Present decisions:** all three count the draws already replayed early: the ticker flip `has_display`, the `d3d12_present` `flip_has_display` (added in `bd09877`; T97 found it missing) and the display-clear `have_display_draws` / `ps3_pg_display_clear`.
  - **Clear records:** a clear record past `MAX_DRAWS` replays early instead of being dropped.
  - **Refused draws:** a draw larger than a whole half is REFUSED, with a bounded `[VPVB] draw REFUSED` line, and then reported by the existing `vertex_buffer_full` path. It can't happen for batches of ≤256 indices (762 ≤ 393,216).
  - **`vp_vb_grow`:**
    - rejects a request that is not larger than the current capacity or exceeds the ceiling;
    - copies 0 bytes at the frame end;
    - `VPVB_GROW_AT_FRAME_END=0` restores the entry-time copy, of used bytes only;
    - allocation failure behaves as before: the old buffer is kept and growth stops.
- **Tests:** `test_vp_flush.c` and `.py` are new. `test_geom_expand` and the pins in `test_draw_rejection`, `test_present_gate` and `test_rf_phase` move to the new intended behaviour.

**Unchanged:**
- geometry, winding, degenerates and draw order;
- PPU/SPU code, physics and AI;
- the 1,048,576 ceiling;
- the legacy (non-VP) path, where `batch_full` still drops with a log.

## 3. Vertex demand and copy bytes

| Quantity | Before | After |
|---|---|---|
| T94 batch reservation | 768 | **309** (= written) |
| Random restart streams (400) | bound/exact = 2.32 | want = written = reference |
| T94 frame at the overflow point | `frame_want` 590,220 for about 394,650 needed | equal to the vertices written (HYPOTHESIS for the whole frame: about 525k) |
| Draws lost on the modelled race frame | 1,868 of 2,600 draw calls | 0 (3 early replays) |
| Growth copy | up to 96 MiB per growth (entry time) | 0 B (frame end); with early replays, growth is no longer triggered |
| Extra cost per early replay | — | one submit plus `wait_for_gpu` (render_frame already serialises every replay) |

## 4. Resource-lifetime guarantees

- **Parity halves:** every replay, early or not, begins with `wait_for_gpu()`, and only then reuses a half.
  - Uploads after replay N go to the other half, which the GPU is not reading.
  - The model checks that no write lands in the in-flight half.
- **Draw slots:** per-draw constant and descriptor slots are indexed by record slot and parity, so they follow the same rule.
- **Retired buffer:** a buffer replaced by growth is retired (`rfp_vb_retire_put`) and released after the next drain.
- **Partial triangle:** the copied-forward partial triangle is read from the half just submitted, which the GPU only reads.

## 5. Regression evidence (logs in `logs/`)

| Test | Result |
|---|---|
| `test_geom_expand` (T95, updated) | 0 failures. Includes exact want = writes = reference on 400 random restart streams, the T94 fixture (51 restarts, idx 4594..4797, old 768, exact 309, writes 309), and the overflow check on `0x55555556` triangles |
| `test_vp_flush` (new) | 0 failures |
| T92 `test_vbo_diag` | 44/44 |
| T88 `test_vb_overflow` | 28/28 |
| Renderer suite (40 tests, including `test_rf_phase`, `test_present_gate`, `test_draw_rejection`, `test_prim_stream`) | 31 PASS / 9 SKIP (POSIX-only, as in T94) / 0 FAIL (`suite_t96.txt`) |
| TU compile, `rsx_d3d12_backend.c` and `cellGcmSys.c`, T94 clang-cl flags | rc=0. No new warning kinds; only a few more `-Wunsafe-buffer-usage` / `-Wdeclaration-after-statement` warnings, of kinds already present (`logs/tu/`) |
| `audit_public.py --staged` | the 25 pre-existing BLOCKs, none in T96 files (`audit.log`) |

`test_vp_flush` covers:
- decision boundaries (exactly full, one over, whole half, too big, carry, records full, merging, 32-bit extremes);
- presentation state across early replays;
- a T94-shaped race frame (1.39M vertices, 4,084 draw calls, more than 2048 records), where every triangle comes back once and in order;
- a list continued across a replay;
- record-only overflow;
- a refused draw with its neighbours kept;
- four growth steps up to the ceiling;
- allocation failure;
- zero copy at the frame end.

Independence:
- The geometry reference is a closed-form per-segment count, separate from `prim_stream.h`.
- The flush model checks triangles read back out of the halves against the guest's own submitted list, not against a recomputed count.
- `vpf_decide` is shared between the model and the backend. Source pins tie the backend to it, but its outcomes are not checked against an independent count.

## 6. Expected impact on the first race frame (HYPOTHESIS until a runtime test)

- **Draws and presentation:** with early replays, no VP draw of the frame should be dropped. Frame 2133 would replay about twice before its flip and then present.
- **Stall:** the 96 MiB entry copy can no longer occur by default. That copy was the `render_frame` stall T91 identified.
- **Remaining cost:** the CPU expansion and 256 B per vertex remain, so a race frame is still about 525k × 256 B ≈ 128 MiB of uploads.

## 7. Remaining limitations and risks

- **Not runtime-verified:** no build or launch was authorised.
- **Clears inside a continued frame:**
  - the continuation replay keeps the backbuffer and the shared depth buffer;
  - other per-replay work (texture staging, RT pool transitions, RSXI and diagnostic frame counters, `frame_count`) runs once per early replay, as it already does for offscreen replays;
  - diagnostics that count frames (RSXI, `[vbo-full]`, `[rf-phase]`) will see early replays as extra frames.
- **Legacy path:** non-VP draws and the legacy `vb_offset` buffer still drop at their limits, with a log.
- **Steady state:** early replays leave `frame_short` at 0, so the buffer never grows, and each heavy frame pays about one or two extra GPU syncs. Growing on early replays would trade that for up to 2 × 256 MiB of upload heap. I left it out (smallest change).
- **Structural fix not attempted:** an indexed D3D12 path would remove the 1.5–3× expansion. It is out of scope.

## 8. Integration

1. `git cherry-pick c7e84e3 bd09877` onto a tree containing T91 `00bf2c4`, the T92/T94 diagnostics (`8ea1437`) and the T95 tests (`f4befa9`, `0834eae`). The commit edits those tests.
2. Run `tools/test_geom_expand.py`, `tools/test_vp_flush.py`, T88/T92 (`t96/tools/run_t96_tests.cmd`) and the suite (`t96/tools/run_suite_t96.cmd <tree>`).
3. The runtime check needs a separate authorisation: one build and one launch with the T94 environment (`RF_PHASE_MS=200 RSX_VBO_DIAG=1`; `VPVB_GROW_AT_FRAME_END` is no longer needed) and no milestone target that ends the run early. Expect:
   - `[VPVB] early replay #1..` lines around frame 2133;
   - no `vertex_buffer_full` or `batch_full`;
   - `[rf-phase]` for the frame;
   - a Present.

## 9. T97 independent review (motorstorm01-8d)

- Strict T97 reference against T96: 15,429 checks, 0 failed. No blocker and no high-severity issue.
- LOW: `d3d12_present` ignored `flushed_display`. **Fixed in `bd09877`**, with a pin. Suite re-run: 31 PASS / 9 SKIP / 0 FAIL; both TUs rc=0.
- MEDIUM, accepted as a limitation (section 7): the buffer never grows on early replays, so heavy frames pay extra drains. The cost is unmeasured.
- LOW, accepted (section 7): `frame=` counters count replays, and legacy draws past `MAX_DRAWS` still drop.

## 10. Incident

My first TU compile rewrote its output path wrongly and overwrote `generated/analysis/t94/logs/tu/*` with a T96 compile. I regenerated those files with T94's own `t94/tools/tu_t94.cmd` against the unchanged `ps3recomp-t94` (`8ea1437`): rc=0, and no T96 paths remain. The `.obj` bytes may differ from the originals. T94's owner (motorstorm01-8d) has been told.

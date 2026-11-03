# T97: independent race-frame renderer validation (2026-10-27)

**Status: T96 `c7e84e3` READY for one bounded runtime verification. No BLOCKER and no HIGH.** Offline only: no build, no launch, nothing merged or pushed.

## Ownership
- **T97:** motorstorm01-8d.
  - Worktree `ps3recomp-t97`, branch `agent/t97-renderer-validation`, from T94 `8ea1437`.
  - Commit `9ff0a4c` (test only).
- **T96:** motorstorm01-21, `ps3recomp-t96` / `agent/t96-race-frame-fix` (from T95 `0834eae`). Not touched by T97.

## Independent test (`tests/test_t97_vp_expand_ref.c`)
- **Runner:** `t97/tools/run_t97_tests.cmd [<tree>] [-DT97_EXPECT_EXACT]`.
- **How it works:**
  - The reference splits the whole BEGIN/END stream at restart indices.
  - It writes each segment's triangles directly: strip even `(i,i+1,i+2)`, odd `(i,i+2,i+1)`; fan `(0,i+1,i+2)`.
  - Indices come from its own big-endian u16/u32 decode. No `ps3_prim_stream_*` call is used.
- **Production model:** `upload_strip_vp_indexed()` per batch, with the reservation pluggable through `T97_RESERVE`.

| Area | Result |
|---|---|
| Strip and fan, u16 and u32, 1000 indices across 256 seams | order and winding identical to the reference; reservation exact without restart |
| 400 random restart-heavy streams (u16/u32, strip/fan, 256 or random batch sizes, restart density 1/2..1/10) | the triangle list matches the reference in order: no duplicates, no omissions, seams continuous |
| Restart rules: off; u16 with value > 0xFFFF (off); u32 full compare; all-restart; count < 3; restart on both sides of a seam | PASS, no underflow |
| Winding: planar zig-zag strip | all 62 triangles share triangle 0's facing |
| **Baseline log** | **PASS, 440/440** (`logs/t97_ps3recomp-t97.txt`) |
| `-DT97_EXPECT_EXACT` on the baseline | FAIL 401/841. This is expected: it is the restart over-reservation T96 fixes |

## Findings on the baseline (`8ea1437`)

| Class | Finding |
|---|---|
| MEDIUM (VERIFIED) | **Strip/fan reservation ignores restarts.** Random restart streams reserve 1.86× what they write. On the T94 batch: reserves 768, writes ≥ 309. The growth decision is sized on reservations: 1700 T94-like draws (525,300 written) grow to the 1,048,576 ceiling instead of 720,896. |
| LOW (VERIFIED) | **The T95 fixture has 52 restarts in batch 1; the record has 51.** Any layout matching the record writes **≥ 309** vertices: 3·(205 − 2·51), since each restart-bounded segment loses at most 2 indices. It does not write 306. |
| none (VERIFIED) | **Expansion correctness:** the production stream matches the independent reference exactly. Fixing only the reservation therefore changes **memory bookkeeping only**: the vertices written, the draw records and their order are unchanged, except that draws previously cut by `o + 3 > maxv` near the capacity limit now fit. |
| none (VERIFIED by code reading) | **Growth/retire lifetime with `VPVB_GROW_AT_FRAME_END=1`:** the order is drain (`wait_for_gpu`, `:6087`) → release the retired buffer (`:6091`) → … → present / `vp_vb_offset = 0` / parity flip (`:7371`) → grow and retire (`:7718`). There is always a full drain between two retires, so the one-slot holder's "hand back the first" path (`if (prev) Release`) is never reached. `render_frame` has no early return between entry and the grow. |
| LOW | **One-slot retire holder:** it is safe only because of that ordering. A second grow site without a drain would release a buffer the GPU may still read. Keep it a single site, or assert `prev == NULL`. |
| MEDIUM (memory) | **Peak upload memory at the 393,216 → 1,048,576 grow:** 192 MiB retired + 512 MiB new = 704 MiB until the next drain. With exact reservation the same frame needs a 720,896 cap = 352 MiB new (544 MiB peak). |

## Stress (budget model, `vp_vb_budget.h`)
| Demand (expanded vertices) | Frame 1 kept / grow to | Frame 2 |
|---|---|---|
| 400,000 | 393,216 / 524,288 | fits |
| 525,000 | 393,216 / 720,896 | fits |
| 786,433 | 393,216 / 1,048,576 | fits |
| 1,000,000 | 393,216 / 1,048,576 | fits |
| 1,100,000 | 393,216 / 1,048,576 | 51,968 short, no further growth (at the ceiling) |

- Repeated overflow within one frame: capacity is unchanged until frame end (VERIFIED).
- Allocation failure: the old buffer is kept, the ceiling drops to the current capacity and nothing is retried (VERIFIED).
- No FPS claim is made.

## T96 `c7e84e3` (`agent/t96-race-frame-fix`, read-only)
- **Reservation (VERIFIED):** `run_t97_tests.cmd ps3recomp-t96 -DT97_T96` (strict) gives **PASS, 15,429 checks, 0 failed** (`logs/t97_ps3recomp-t96-DT97_T96.txt`).
  - Covered: u16/u32, restarts, both seams, 400 random streams, the T94 layout (exact want 309).
  - `ps3_prim_stream_count_tris` equals the triangles `push` returns, and leaves the stream unchanged.
- **T96's own `test_vp_flush` re-run here:** 0 failures (`logs/t96_test_vp_flush.txt`). The T96 worktree is clean after the run.
- **Growth copy (VERIFIED by reading):** at frame end it copies 0 bytes. With `VPVB_GROW_AT_FRAME_END=0` it copies only the used bytes. A `new_cap` that does not grow, or exceeds the ceiling, is ignored with a log line.
- **Early replay lifetime (VERIFIED by reading):**
  - every `render_frame` drains the GPU at entry;
  - after an early replay submits half P and flips, records go to half 1−P, whose last reader was the previous replay, already drained;
  - growth and retire are skipped while `in_flush`;
  - the carried partial triangle is at most 2 vertices (`tail` holds 2×256 B);
  - draw order is kept on the one queue.

| Class | Finding |
|---|---|
| MEDIUM (VERIFIED by reading; cost is a HYPOTHESIS) | **Growth is effectively dead for VP overflow.** After an early replay `frame_short` stays 0, so `vpvb_next_cap` never grows (T96 tests this deliberately). Race frames stay at a 393,216 cap and pay at least one extra drain and submit per frame. This is correct but the cost is unmeasured; no FPS claim is made. |
| LOW, **FIXED in `bd09877`** (VERIFIED by reading the 1-line diff) | **`d3d12_present` (`:7868`) ignored `flushed_display`.** `d3d12_clear` (`:7955`) and `backend_present` (`:9853`) were patched to check it. If the records left after an early replay are all offscreen, the flip does not replay or present, and `keep_targets` carries into the next guest frame. |
| LOW | **Diagnostics now count replays, not guest frames.** `frame_count++` (`:7735`), `[rf-phase]`, the RSXI `mindraws` trigger and VBO_DIAG `frame=` all run per early replay. After the first early replay, `frame=` values cannot be compared with T94's logs. |
| LOW | **The records-full early replay covers only VP draws and clears.** Non-VP (legacy) draws at `MAX_DRAWS` still drop through `batch_room`. |
| LOW (carried over) | **One-slot retire holder:** still safe only while there is a single grow site that runs after a drain. |
| INFO | **Default changed:** `VPVB_GROW_AT_FRAME_END` is now on by default; `=0` restores the entry-time copy. **Scope:** T96 also adds early replay, which goes beyond the reservation fix. |

## Readiness
- **Integration:** cherry-pick `c7e84e3` + `bd09877`. `bd09877` changes no header, so the strict T97 result still applies. T96 accepted the remaining MEDIUM and LOWs as limitations (`t96/RACE_FRAME_RENDERER_FIX.md`).
- **Offline: PASS.** No BLOCKER, so no repro was needed. Findings were sent to motorstorm01-21.
- **Runtime: not verified** (no launch was authorized).
- **Proposed check:** one bounded launch of a T96 build.
  - Environment: same as T94 (`RF_PHASE_MS=200 RSX_VBO_DIAG=1 VP_NOFIXPROJ=1`, RSXI/`TEX_SAVE`/`RSX_RT_READBACK` off, 205/210 s caps), with a target milestone that cannot be reached.
  - Pass if: there are `[VPVB] early replay` lines; there is no `dropped_draw reason=vertex_buffer_full` and no `REFUSED`; the race frame's `[rf-phase]` total is far below T87B's ~4 s; and Presents continue (`[rsx-hb]`).

## Incident
- T96 overwrote `t94/logs/tu/*` by mistake.
- They regenerated it with `tu_t94.cmd` against the unchanged `8ea1437`: rc=0 for both TUs. The logs are valid; the obj bytes may differ from the originals.

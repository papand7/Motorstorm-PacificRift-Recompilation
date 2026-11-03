# T88: RSX vertex-buffer overflow (offline, 2026-10-27)

- **Worktree:** `ps3recomp-t88`, branch `agent/t88-vb-overflow`, from the T86 integration `1163f34` (= T84E `2dcf255` + T86 `1691914`).
- **Changes:** no source changes, no build, no launch, nothing merged or pushed.
- **Inputs:** the T84E run `generated/runs/20261027-064349-t84e-gcm-offset-fix` and the T86I run `generated/runs/20261027-072822-t86i-pb-sync`. The T86I run is the same build plus counters, so it reproduces the overflow independently.

## 1. Verdict

- **VERIFIED:** the overflow is the D3D12 backend's **per-frame VP vertex budget**: `vp_reserve` → `vpvb_reserve`.
  - The budget starts at `MAX_VERTICES` = 393216 expanded vertices × 256 B per frame-parity half.
  - It only grows at the end of a frame.
  - It is a host limit. The RSX has none: it reads vertex arrays from guest memory as each draw executes.
- **VERIFIED:** neither dropped draw has a corrupted count, stride or format.
  - A draw word can ask for at most 256 indices: `DRAW_INDEX_ARRAY`'s count field is 8 bits, count−1.
  - So one draw needs at most 768 expanded vertices.
  - Filling the buffer therefore takes at least 512 such draws in one host frame.
  - Integer overflow is excluded (tests §5).
- **PARTIAL:** the walker executed draws until the frame's demand reached 393216. One `DRAW_INDEX_ARRAY` header can carry up to 2047 batches. 512 continued 256-index batches, about 2 KB of commands, fill the buffer. A real race frame does that easily (T85: about 1900 renderable batches per race frame).
- **BLOCKED offline:** whether that geometry is the game's real data or the walker decoding the wrong words. No slot contents, per-draw log or RSXI capture exist for that frame:
  - only the first drop per reason is logged;
  - truncation counts live only in the 5 s summary, which never printed again;
  - the RSXI capture was never taken.
- **Contribution to the T87 stall:** the overflow is **not a cause**. `vp_reserve` and `da_fail` contain no waits, and after the buffer fills each further draw is cheaper (no vertex reads). It is evidence about the stalled frame, though (§4).

## 2. Exact path

1. `cellGcmSys.c` `gcm_rsx_process_fifo_unlocked`:
   - for a method header (`type 0/2`, count `(w>>18)&0x7FF` ≤ 2047), it runs the inner loop over the data words, then `rsx_process_method`;
   - the outer word loop, with its `GCM_WORD_STATS` check, only resumes after the whole header.
2. `rsx_commands.c:892` `NV4097_DRAW_INDEX_ARRAY`: first = `[23:0]`, count = `[31:24]+1` (≤ 256), then `draw_indexed`. `DRAW_ARRAYS` (`:840`) uses the same packing.
3. `rsx_d3d12_backend.c`:
   - `d3d12_draw_indexed` → `_body` → `upload_strip_vp_indexed` (`:8550`);
   - `ps3_prim_stream_max_tris(count)·3` gives 762 for a fresh 256-index strip and 768 for a continued one (strips continue across batches inside one BEGIN/END);
   - then `vp_reserve(want)`.
4. `vp_reserve` (`:7984`) → `vpvb_reserve(&s_vpvb, vp_vb_offset/256, want)` (`vp_vb_budget.h`). It returns all of the request, part of it, or nothing. When it returns nothing: `da_fail(DA_R_VERTEX_BUFFER_FULL)`, the draw is not recorded, and `da_callback_ex` prints `[draw_acct] event=dropped_draw|dropped_display_draw reason=vertex_buffer_full` (draw_acct.h:216).
5. The offset resets only in `render_frame` (`:7268`, on present) and at a clear boundary (`:7847`). Growth (`vpvb_end_frame`, `:6001`) also happens only there, up to `VP_VB_MAX_VERTICES` = 1048576.

## 3. Evidence (logs)

| run | drop 1 | drop 2 | CALLs emitted before the drop |
|---|---|---|---|
| T84E (`stderr.log:52279/52281`) | `dropped_draw prim=6 count=256 indexed=1 rt=0x07B78D80 flip=5748 fp=0x07B56E81` | `dropped_display_draw prim=6 count=4 indexed=0 rt=0x00394000 fp=0x02193941` | 39 (147.26–147.59 s) |
| T86I (`stderr.log:60038/60041`) | `dropped_draw prim=6 count=256 indexed=1 rt=0x07B78D80 flip=4721 fp=0x07B58001` | `dropped_display_draw prim=6 count=4 indexed=0 rt=0x00010000 fp=0x02193941` | 39 (155.71–156.00 s); the drop is at PT ≈ 156.17 s |

- **Same pattern in both runs:**
  - 39 CALLs, i.e. two push-buffer frames, had been emitted;
  - a full 256-index strip batch is dropped on the scene RT `0x07B78D80`, which is in the T72 `RSXI_RTS` set;
  - then a 4-index fullscreen strip is dropped with the display FP `0x02193941`, after a `CLEAR_SURFACE`.
- **Both drops are well-formed:** prim 6 is TRIANGLE_STRIP, 256 is a full libgcm batch, and 4 is a quad strip. Their only cause is that the frame's budget was already used up.
- **Before the CALLs:** frames had `last_draws=3` (the loading screen). The draw_acct summary shows `truncated=0 vb_grows=0 reasons=none`. So the whole 393216 vertices were consumed inside the first push-buffer frame.

## 4. Relation to the stall (T84E / T86I / T87)

- **Overflow as a cause:** none. The drops are counters and one `fprintf`; nothing blocks.
- **Correction to T86 §9:** that section said the walker "processed no word after ≈155.9 s". That holds only for the outer word loop. In T86I, draw callbacks still executed at PT ≈ 156.17 s, more than 5 s after the last `[words]` window (≈150.9 s), yet no window printed.
  - So the walker was inside one method header's data loop, or inside a callback it calls, and never got back to the outer loop.
  - That is consistent with a very large header, up to 2047 draw batches (T84E hypothesis 2, "slow, not stuck"), or with a block inside the backend.
  - **Not decided offline.**
- **Note for T87:**
  - a stall dump keyed on the outer loop's `get` would show only the header's offset;
  - log `s_state.fifo_cmd_off` (already set per header, `cellGcmSys.c:2230`) and the index into its data, for example from a timer;
  - also log the backend's per-frame `frame_want`.

## 5. Reproduction tests

`t88/tests/test_vb_overflow.c` with `t88/tools/run_t88_tests.cmd` (clang, `-Wall -Wextra -Werror`, the worktree's real headers). Result: **PASS, 28 checks** (`t88/logs/test_vb_overflow.txt`).
1. **Decode bounds:** count is 1..256 per data word; a header holds at most 2047 data words.
2. **Per-draw demand:** strip and fan, fresh and continued, give 762 and 768; the worst case over all counts and continuation states is 768; a 4-index strip wants 6.
3. **Reproduction:** one BEGIN/END of continued 256-index batches at cap 393216.
   - 512 batches fit in full, batch 513 gets the last 6 vertices, and **batch 514 is the first `vertex_buffer_full` drop**.
   - A later 4-index display draw gets 0. This is the observed pair, with no corrupted parameters.
   - It needs about 2 KB of commands, far less than the walker had already executed.
   - Next capacity: 589824.
   - With fresh strips instead: 516 full, 1 partial (24 vertices), first drop at 518.
4. **Ceiling:** one maximal header of 2047 batches wants 1,572,090 vertices. That is more than `VP_VB_MAX_VERTICES` (1048576), so growth alone can never hold it and such a frame drops draws every time.
5. **Integers:** `frame_want` is 64-bit (4 × 0xFFFFFFFF does not wrap); `room` is 0 when used > cap; the ceiling fits in the u32 `vp_vb_offset` (2^28); exact fit; one short gives a partial of 1; a frame that fits exactly does not grow.

## 6. Proposed minimal correction (not implemented: no speculative fix)

1. **Diagnose first.** Add a disabled-by-default one-shot line at a frame's first `vertex_buffer_full`. It should print:
   - `fifo_cmd_off` (the header), its method and count, and the data index;
   - `frame_want`, `draw_count`, and the CALL return slot.
   
   Together with the T87 stall dump, this decides whether the geometry is real (one large `DRAW_INDEX_ARRAY` header inside a push-buffer slot) or a misdecode (a header at an unexpected offset, for example a chunk tail).
2. **Then, only if the geometry is real,** make the host budget match RSX semantics, which have no per-frame cap:
   - chain extra upload chunks mid-frame when the current half is full, with each record carrying its buffer;
   - or raise the starting capacity and the ceiling.
   
   Never clamp a count or silently drop geometry. A frame demanding more than 1048576 vertices would still drop draws, so the ceiling needs the chained design.
3. **Adjacent limit:** `MAX_DRAWS` = 2048 records per frame (`batch_full`). A race frame (T85: about 1900 batches) is close to it, so check it in the same run.

## 7. T87 run follow-up (2026-10-27, read-only)

- Run: `generated/runs/20261027-080253-t87-rsx-stall` (motorstorm01-3c's single launch; nothing launched from T88).
- **VERIFIED:** the race push-buffer frames were never reached (0 CALLs before the 205 s cap), and `stderr.log` contains 0 `vertex_buffer_full` lines.
  - Its two stall snapshots are from the loading phase: `draw_count` 23/2048, `frame_want` 138.
  - So they say nothing about the overflow.
- The §1 BLOCKED item (real geometry vs misdecode) stays open. Settling it needs a run that reaches the race push-buffer frames and still has the T87 stall dump enabled.

## 8. T87B run follow-up (read-only)

- Run: `generated/runs/20261027-084130-t87b-race-stall`.
- **VERIFIED:** the same drop pair appears a third time, at flip 4038:
  - a 256-index strip on `rt=0x07B78D80`;
  - then the 4-index display quad (`fp=0x02193941`).
- **The stall snapshot does not decide §1.**
  - It was taken inside `render_frame` (atlas-upload `memcpy`, `rsx_d3d12_backend.c:6109-6112`), after the per-frame reset.
  - So `frame_want=0` and `vp_vb_offset` equals the parity-1 base (393216 × 256).
  - `draw_count` was 974/2048.
- Real geometry versus misdecode stays BLOCKED. It still needs the one-shot line at the first `vertex_buffer_full` (§6.1).

**Correction to §8 (T92):**
- `vp_vb_offset=100663296` is relative to the frame-parity half, and equals 393216 × 256. So at the T87B snapshot the half was **full**, not reset.
- The snapshot was inside `vp_vb_grow` (`frame_want=0` with the old cap).
- The grow to 1048576 implies a frame demand of ≥ 786,433 expanded vertices.
- See `t92/FIRST_VERTEX_OVERFLOW_CAPTURE.md` §5.

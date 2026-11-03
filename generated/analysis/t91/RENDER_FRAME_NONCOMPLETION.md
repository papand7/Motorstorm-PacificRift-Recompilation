# T91: first race frame, D3D12 `render_frame()` noncompletion (2026-10-27)

**Status:** root cause VERIFIED for the sampled stall. It is a slow copy, not a
deadlock. The remaining render-frame time is PARTIAL. Offline only: no build, no
launch.

- **Worktree:** `ps3recomp-t91`, branch `agent/t91-render-frame-stall`, based on
  `07db971` (T87B). Not merged or pushed.
- **Commits:**
  - `12fb461`: instrumentation, `patches/0001-…`;
  - `00bf2c4`: separate correction, off by default, `patches/0002-…`.
- **Evidence:** the T87B run `generated/runs/20261027-084130-t87b-race-stall` and
  the exe `b026075c038b3c499ce5ea6d19972688940913ba3267970b9d8a8ffebfbb5ac3`.

## 1. The sampled copy is not the B8 atlas upload (VERIFIED; corrects T87B)

The watchdog frame `exe+0x1757d043` returns from `memcpy` at `0x15757d03e`. The
call is set up as follows:
- size `r8` = a 32-bit global, with the call skipped when it is 0;
- destination = the `Map` result + `parity * new_cap << 8`;
- source = a 64-bit global + `parity * old_cap << 8`;
- just before it: `CreateCommittedResource` (device vtbl +0xd8) and then `Map`
  (+0x40).

That is exactly `vp_vb_grow()` (`libs/video/rsx_d3d12_backend.c:5974`):

```c
memcpy(nm + parity*new_cap*256, vp_vb_mapped + parity*old_cap*256, vp_vb_offset);
```

The atlas loop's source stride is `w`, not a multiple of 256, so it cannot be this
code. Its caller is `render_frame()` (`:6027-6030`), right after `wait_for_gpu()`.

## 2. Timeline (T87B stderr; PT clock, µs)
| t (s) | line | event |
|---|---|---|
| ≈203.12 | 73141 | `render_frame()` entered (op=render-frame, 1063 ms old at the snapshot); first race frame, 974 draws |
| 204.18 | 73137 | stall snapshot: `vp_vb_offset=100663296` (96 MiB = the full 393216-vertex half), `vb_cap=393216` |
| 205.24 | 73399 | watchdog: stack in `memcpy` ← `vp_vb_grow` ← `render_frame` |
| 205.62 | 73497 | `[VPVB] per-frame vertex buffer grown: 393216 -> 1048576 verts (512 MB, x2 parity)`. **The copy completed.** |
| 205.6+ | 73498- | `[RSXI] triggered at frame 4062`, 3 depth surfaces, 4 new FP pipelines (cube/shadow) compiled |
| 207.36 | | guest `0x72E1E0` returns after 4.0 s, then `GcKernel::Present() Timeout!`. The runner stops on that line; no `[rsx-hb]` after 201.75 s |

So `render_frame()` was still running when the run stopped, at least 4.2 s after
entry. Before the grow finished: about 2.5 s (from ≤203.12 to 205.62 s). After it:
at least 1.7 s.

## 3. Phase 1: B8 upload path (`render_frame` `:6068-6152`, `d3d12_bind_texture` `:9073`)

**Inputs at the bind:**
- **Producer:** every bind whose base format is B8 (`0x81`), on any unit, sets:
  - `tex_w`/`tex_h` = the 16-bit `image_rect` halves;
  - `tex_src_offset = cellGcmResolveLocated(loc==1, offset)`;
  - `tex_dirty = 1`.
- **Source:** `vm_base + tex_src_offset`, guest memory owned by the game. It
  ignores `TEX_RESOLVE_AUTO`/`TEX_PROBE` and `control3` (pitch).

**Upload sizes:**
- **Destination:** a new UPLOAD buffer of `pitch*h` bytes, where
  `pitch = (w+255)&~255`. It is mapped, and `h` rows of `w` bytes are copied in.
- **Integer handling:** offsets use `u64`. The `u32` pitch cannot wrap for 16-bit `w`.
- **Size limit:** a D3D12 TEXTURE2D is at most 16384×16384, so the largest
  copy that can run is 256 MiB.

**Classification:**

| Candidate | Result |
|---|---|
| Oversized B8 copy | not observed. The race B8 dimensions are still unlogged (`atlas uploaded` printed only for 640x360 ×3) |
| Invalid source range | HYPOTHESIS only (offset + 256 MiB past 4 GiB). No evidence |
| Row-pitch or allocation mismatch | none: destination pitch and size agree. A pitched (`control3 ≠ w`) B8 source would be read with the wrong stride. That is a rendering defect, not a stall |
| Integer overflow | none found |
| Repeated uploads | VERIFIED. Every B8 bind sets `tex_dirty`, so every frame with a B8 bind recreates two committed resources and copies `w*h` bytes. That is cheap at 640x360 and not implicated in T87B |
| Is it the atlas? | it is "whatever B8 texture was bound last". It is not specific to the font atlas |

## 4. Phase 2: `render_frame()` lifecycle (`:6009-7676`): what can block or scale

Each phase, and whether it was implicated in T87B:

1. **`wait_for_gpu()`:** a full queue drain, bounded to 3×2 s.
   - Not implicated: the snapshot op was render-frame, not gpu-wait, and the fence
     was complete (8192/8192).
2. **`vp_vb_grow()`:**
   - `CreateCommittedResource` of up to 512 MB, then `Map`;
   - then a **CPU read of `vp_vb_offset` bytes (≤ 256 MiB) from the old UPLOAD
     mapping**. UPLOAD heaps are write-combined, so reading them is uncached.
   - **The sampled stall.**
3. **`compile_vp()`, readback buffer, allocator/list reset.**
4. **B8 upload (§3).**
5. **Draw replay:**
   - 974 records;
   - per-draw PSO compiles for new FPs/VPs, which this frame needed: 4 new
     cube/shadow FPs;
   - per-draw constant and SRV setup.
6. **Barriers, `Close`, `ExecuteCommandLists`.**
7. **`rsxi_frame_finish()`:** when an RSXI capture is armed, it does its own GPU
   wait plus readbacks and file writes.
   - **Armed on this exact frame** (`--capture-rsx`, `RSXI_MINDRAWS=200`;
     frame `f004062`, manifest `status: capturing`).
8. **`Present` (vsync), `move_to_next_frame()`:** a fence wait, bounded to 2 s.
9. **Tail:** heartbeat and title.

## 5. Phase 3: diagnosis
| Candidate | Class | Evidence |
|---|---|---|
| CPU read of a write-combined UPLOAD mapping in `vp_vb_grow` (96 MiB) | **VERIFIED** as the sampled operation and as ≈2.5 s of the frame | disassembly match (§1); grow log at 205.62 s; `vp_vb_offset=100663296` |
| Deadlock / GPU synchronization wait | **VERIFIED not** during the grow | op was render-frame, not gpu-wait or fence-wait; fence 8192/8192; the grow completed |
| Unexpected draw workload | PARTIAL | 974 draws and a 96 MiB vertex expansion, which overflowed 393216 vertices (`vertex_buffer_full` at flip 4038). That is the trigger for the grow |
| RSXI capture of this frame (diagnostic overhead) | HYPOTHESIS for part of the ≥1.7 s after the grow | triggered right after the grow; the capture never finished |
| New FP/VP pipeline compiles in the replay | HYPOTHESIS for part of the ≥1.7 s | 4 FP pipelines compiled after the grow |
| Oversized B8 copy / invalid range / integer overflow | not supported | §3 |
| CPU memory pressure | HYPOTHESIS, minor | 512 MB new and 192 MB old upload heaps briefly coexist |

**Why it looks like a hang:** the RSX FIFO walker runs on the same thread, so while
`render_frame()` runs:
- GET stays at `0x12068` and ref stays at `0xFC7`;
- the guest's `0x72E1E0` waits 4 s, then the game's own Present watchdog fires,
  and that line stops the run.

The frame was progressing slowly. It was not deadlocked.

## 6. Phase 4: instrumentation (`12fb461`, off by default)
- **`include/ps3emu/rf_phase.h`** (header-only):
  - 11 named phases;
  - per-phase time, phase in progress, last completed phase, slowest phase;
  - B8 geometry (`pitch`, `upload_bytes`, `copy_bytes`, guest `[src_off, src_end)`,
    `src_in_vm`, `d3d12_ok`), all in 64-bit arithmetic;
  - growth copy bytes;
  - a one-slot retire holder used by the correction.
- **Backend**, enabled by `RF_PHASE_MS=<ms>`:
  - `rfp_at()` marks around drain, grow, compile/reset, atlas, record, submit,
    capture, present and next-frame. Off, each mark is one branch.
  - One `[rf-phase] frame= total_ms= slowest= draws= vb_cap= vb_grow=a->b
    grow_copy_bytes= | phase=ms …` line per frame slower than `<ms>`, plus an
    `[rf-phase]   atlas …` line when a B8 upload ran. At most `RF_PHASE_MAX`
    lines (default 8).
  - The `GCM_STALL_MS` snapshot's backend line adds `rf_phase= rf_phase_ms=
    rf_last_done= rf_frame=`. This names the phase in progress from the monitor
    thread, read-only.
- **No pointer is dereferenced to report:** addresses and offsets are only stored
  and printed. No per-draw logging.

## 7. Correction (`00bf2c4`, separate, off by default: `VPVB_GROW_AT_FRAME_END=1`)

**Defect (VERIFIED from code and the T87B timing):**
- the grow runs before the replay, so it must preserve this frame's bytes;
- it does that by reading them back out of write-combined memory.

**Fix:**
- take the same `vpvb_end_frame()` capacity decision at the end of
  `render_frame()`, after `ExecuteCommandLists`, Present, `move_to_next_frame()`
  and the per-frame `vp_vb_offset = 0` reset. Nothing then needs copying;
- the GPU may still read the replaced buffer, so it is retired, not released;
- the retired buffer is released after the next `render_frame()`'s existing
  `wait_for_gpu()` drain.

**What it does not change:**
- no new wait, no size cap and no skipped draws;
- the capacity sequence and ceiling are the same;
- the overflowing frame's dropped draws are not recovered, as before;
- with the flag off, the original entry-time grow runs unchanged.

**Not verified at runtime.** It is not enabled by default.

## 8. Tests (offline)

**Commands:**
- `GCM_TEST_CLANG=<build clang> py -3 tools/test_rf_phase.py`;
- the suite: `generated\analysis\t91\tools\run_suite_t91.cmd ps3recomp-t91`.

**What they cover:**
- texture-size arithmetic, row pitch (1/256/257/65535/2³²−1), 64-bit sizes;
- the D3D12 16384 limit and zero dimensions;
- valid and invalid guest ranges (end exactly at 4 GiB / 1 KiB past);
- phase accounting, including a backwards clock;
- growth copy bytes (96 MiB at entry vs 0 at end);
- entry-vs-end capacity equivalence over 6 frames;
- retire lifetime (hold, release after drain, release once, double retire);
- source pins: gating, mark order, no pointer reads, unchanged copies, no new GPU
  wait.

**Results:**

| Tree state | Result | Log |
|---|---|---|
| Instrumentation only | `test_rf_phase` 0 failures; suite 28 PASS / 9 SKIP / 0 FAIL, the same as T87B | `logs/suite_instr.txt` |
| With the correction | suite 29 PASS / 9 SKIP / 0 FAIL (`test_rf_phase` now runs its correction checks); TU `rsx_d3d12_backend.c` exit 0 in both states | `logs/suite_fix.txt`, `tu_instr/`, `tu_fix/` |

**Audit:** the same 25 pre-existing BLOCKs, none in the changed files.

## 9. Recommended runtime capture (one build, one launch, when authorized)
- **Build:** T91 `00bf2c4`. The same runner as T87B, plus:
  - `RF_PHASE_MS=200 RF_PHASE_MAX=8`;
  - `VPVB_GROW_AT_FRAME_END=1`;
  - **RSXI frame capture off** (no `--capture-rsx`), so the diagnostic does not
    cost the first race frame time.
- **Expect:**
  - `grow_copy_bytes=0` and a millisecond-scale `vb-grow` on the first race frame;
  - `[rf-phase]` naming whatever else is slow (record/PSO compiles);
  - presents continuing past the race's first frame.
- **If the remaining frame time still exceeds 4 s:** the `[rf-phase]` line and
  `rf_phase=` in the stall snapshot will name the phase.

## 10. Companion: T92 (RSX_VBO_DIAG)

T92 `0882c81` (`agent/t92-first-vb-overflow`) adds `RSX_VBO_DIAG=<n>` (off by default): one `[vbo-full]` record at a frame's first `vertex_buffer_full`/`batch_full`, printed before either grow path. `git merge-tree` of T91 `00bf2c4` with T92 `0882c81`: clean (VERIFIED). For the recommended single capture, build the merge and add `RSX_VBO_DIAG=1` to `RF_PHASE_MS=200 VPVB_GROW_AT_FRAME_END=1` (RSXI capture off). Report: `generated/analysis/t92/FIRST_VERTEX_OVERFLOW_CAPTURE.md`.

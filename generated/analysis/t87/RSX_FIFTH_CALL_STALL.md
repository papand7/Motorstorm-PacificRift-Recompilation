# T87: RSX stall capture (one build, one launch)

## Result

**BLOCKED.** The one launch did not reach the race's push-buffer frames, so the
fifth-CALL stall was not captured.

- The intro-skip press was delivered, but the game did not leave the intro.
- The full Bink intro played (frames 256–3840, 124 s).
- Race entry started at 176 s and the world finished loading at 197 s.
- The 205 s session cap hit before the first push-buffer CALL.
  - T84E needed 91 s from LOAD RACE START to its stall.
- No retry, per the brief.

None of the Phase 5 questions about the fifth CALL can be answered from this run.

## Diagnostic (VERIFIED offline)

- Worktree `ps3recomp-t87`, branch `agent/t87-rsx-stall-capture`.
- Commit `d04a614b5b045249ee912215f66362f4409ea011` on `1163f34` (T86I).
- Patch: `patches/0001-RSX-stall-snapshot-GCM_STALL_MS-and-per-site-PT-limi.patch`.

### `GCM_STALL_MS=<ms>`

Off by default. `include/ps3emu/gcm_stall_watch.h` and `cellGcmSys.c`.

A monitor thread polls every 100 ms. It never takes the FIFO lock, never writes
guest memory and never moves GET.

When there is pending work (`get!=put` or an open CALL) and no word has been
decoded for `<ms>`, it prints one bounded `[stall]` snapshot per episode, at
most `GCM_STALL_MAX` (3) in total. The snapshot contains:

- GET and PUT, and where GET points;
- `ctrl` put/get/ref, as values;
- walker pass state: `in-pass` / `passes` / `no-pass`;
- the last command (offset, header, method, count, data index, data);
- 4 words before GET and 16 at GET, read with bounds checks;
- the CALL target head;
- the last 12 CALL/RET events;
- semaphore state;
- SPU job started/finished/in-flight counts;
- backend state (`draw_count`, VB offset/cap, `frame_want`).

An idle reader (`get==put`, no CALL) is never reported.

### PT tracer changes

- Three-level reads `[[[rN+a]+b]+c]`.
- Per-site `limit@ADDR=N`, which overrides `sample` at that site.
- The config now reads ref as `[[[r2+0x5AB8]+0]+8]` and put as
  `[[[r2+0x5B30]+0]+0]`. Verified in this run: `[[r2+0x5B30]+0]=0x20002000`
  (the control register), and the value at 0x7367E4 equals the new PUT.

### Tests

- `tools/test_gcm_stall_watch.py` plus a C harness. They cover:
  - safe word reads;
  - CALL/RET tracking;
  - ring vs CALL-target classification;
  - stall with pending work;
  - no false stall when idle;
  - reference value;
  - disabled behaviour.
- `test_ppu_trace` gains three-level reads and `limit@`.
- Suite: T87 28 PASS / 9 SKIP / 0 FAIL. Base T86I: 27 / 9 / 0, plus 1 absent (the new test).
- Audit: the same 25 pre-existing BLOCKs, none in changed files.

## Build and launch (VERIFIED)

- **Build:** one isolated build of `build/motorstorm-t87-stall` from `PS3RECOMP_DIR=ps3recomp-t87`. rc=0, 0 FAILED.
- **Exe:** pinned at `t87/exe/MotorStormPacificRiftRecomp.exe`.
  - SHA-256 `46a29a9dd153ac753af57bcc5a9867c14d3e08e0b1de7a8c94213a18454895a1`.
- **Registrations:** identical to T86I apart from the new test source and the internal
  `cellGcm_stall_set_backend_info`. The game never imports it, the same as the
  existing `cellGcm_*` helpers.
- **Existing pins:** 15 existing exe pins unchanged before and after the launch
  (`logs/existing_pins_{before,after,postlaunch}.sha256`).
- **Launch:** one launch, `generated/runs/20261027-080253-t87-rsx-stall`.
  - Env: `VP_NOFIXPROJ=1`, `GCM_WORD_STATS=5`, `GCM_STALL_MS=1000`, `GCM_STALL_MAX=3`.
  - Limits: 205 s session, 210 s host.
  - Termination: the session cap.

## Runtime evidence

| | T84E | T86I | T87 |
|---|---|---|---|
| intro (Bink frames) | 256–768 | 256–768 | 256–**3840** |
| first menu press | 34.6 s | — | 154.3 s |
| LOAD RACE START | 56.0 s | — | 175.7 s |
| world loaded | 76.6 s | — | 196.9 s |
| `50D868` / CALLs | 158 / 5 | 158 / 5 | **0 / 0** |
| `vertex_buffer_full` drop | yes | yes | none |

The race loader's timing is unchanged: START to world-loaded took 20.6 s in T84E
and 21.2 s in T87. So tracing did not slow that phase.

### Intro not skipped (VERIFIED)

- `[pad-trigger]` pressed CROSS 1500 ms after the `gui_intro_eu.bik` open. It was
  read 15 times and released, the same as in T84E/T86I.
- In T84E/T86I, `last_draws` goes 21 → 42 right after the press.
- In T87 it stayed at 23, and the present thread stopped at that moment (below).

### Two snapshots, both `no-pass` at the same ring point (VERIFIED)

- **#1, about 37.1 s:**
  - The game thread enters the ref throttle `0x72E1E0` at t=37.067 s with
    ref=0x3ED and target 0x3EE.
  - It stays there 3.143 s (exit `dur_us=3143139` at 40.21 s).
  - Snapshot: `get=0x00010068 put=0x00011068`, `ctrl ref=0x3ED`.
  - Walker: `in_pass=0`, `pass_seq` frozen.
  - The last command is `0x1FD8` count 1 at `0x10060`. GET holds the JUMP
    `0x20014180`.
  - No semaphore held; SPU jobs 0/0.
  - The `[rsx-hb]` heartbeat gap is 36.73 → 39.97 s (3 frames in 3.2 s).
- **#2, about 50 s:** the same `get=0x10068 put=0x11068`, `ref == host_last_ref`
  (0x4F1), `no-pass`. Heartbeat gap 1.36 s.

So:

- The guest is waiting on ctrl->ref.
- The pending ring segment `0x10068..0x11068` is complete and readable.
- No walker pass runs, because the present thread, which runs the walker, is
  blocked outside the walker.
- This is not a semaphore, an SPU job or a bad command word.
- After the gap, one `[words]` window shows `hdr=220093`, about 7× the usual,
  with segment end JUMPs at `0x1B138` (normally `0x14AF0`).

### Diagnostic shortcomings (VERIFIED)

- `at=other-buffer` is wrong here. The ring bounds came out as `[0,0x10000)`, but
  the title's ring is the four 4 KiB-stride segments at `0x10000..0x14000` (plus
  the `0x2xxxxx` mirrors).
- `flips=0` because the counter only counts `GCM_FLIP_MARKER` words.

## HYPOTHESES (not demonstrated)

1. **The 3.2 s present-thread stall caused the missed intro skip.** The present
   thread blocked exactly when the press arrived, and the intro then played to
   the end. The cause of the block is not captured: the snapshot only records
   walker state, not what the present thread is waiting on.
2. **The present stall is a pre-race form of the T84E/T86I stall.** In both the
   guest spins on ref while the walker gets no pass.

No synchronization defect is claimed: no ordering violation was observed.

## Recommended next step (minimal, needs a new authorization)

- **Fix the two diagnostic shortcomings first:**
  - Take the ring bounds from the observed segment JUMP pattern, or from
    `cellGcmInit` IO/size.
  - Add the present thread's own state to the snapshot: its last call site and
    timestamp in `rsx_d3d12_backend.c`, e.g. fence wait, `Present`, or the
    frame-want gate.
- **Then one launch with an intro-skip check:**
  - It should abort if `last_draws` does not change within 5 s of the press, so
    the 205 s budget is not spent on the intro.
  - Or add `PS3_DEV_SKIP_INTRO_DELAY_MS` re-press support.
- No code correction is proposed until the present-thread block is identified.

---

## T87B: first race-frame RSX stall (2026-10-27)

**Status: VERIFIED.** The first race frame was reached and captured. The stall is
on the host present thread, in the backend replay of that frame. It is not in the
RSX command stream.

### Build and run
- **Source:** worktree `ps3recomp-t87b`, branch `agent/t87b-race-frame-stall`,
  commit `07db971` on `d04a614`. Not merged or pushed. Patch in `t87/t87b/patches/`.
- **Instrumentation:** disabled by default and gated on `GCM_STALL_MS`:
  - `GCM_STALL_RING`, `GCM_STALL_INTRO`;
  - present-thread operation marks;
  - inner data-word and callback counters, plus the slowest callback;
  - nested CALL count;
  - fence values.
- **Offline:** suite 28 PASS / 9 SKIP / 0 FAIL, the same as T87. The C harness has
  0 failures.
- **Build:** one full build, rc=0, 0 `FAILED:`.
  - Exe SHA-256 `b026075c038b3c499ce5ea6d19972688940913ba3267970b9d8a8ffebfbb5ac3`,
    pinned at `t87/t87b/exe/`.
  - The 16 existing pins are unchanged after the build and after the launch
    (`t87/t87b/logs/existing_pins_after_*.txt`).
- **Launch:** one launch, `generated/runs/20261027-084130-t87b-race-stall`.
  - Limits: 205 s session cap, 210 s host cap.
  - Settings: `VP_NOFIXPROJ=1`, `GCM_WORD_STATS=5`, the original race-entry
    controller, the private HDD snapshot.
  - `TEX_SAVE` and `RSX_RT_READBACK` were off.
  - It ended on the game's `Gc ERROR: GcKernel::Present() Timeout!` and the session cap.

### Intro skip (Phase 2): VERIFIED
- `[pad-trigger] press 0x4000` fired once (stderr line 26210).
- `[intro-skip] OK frame with 42 draws (>= 40) 1937 ms after the press`.
- There was no re-press.

### Evidence at the stall (stderr lines 73137-73160 and 73399-73405)
| Item | Value |
|---|---|
| ring / GET / PUT | ring `[0x10000,0x14000)`, GET `0x12068` (`at=ring`), PUT `0x13068`. Later the guest moved PUT to `0x10068` (PT at 207.56 s) while GET stayed at `0x12068` |
| reference | ctrl->ref = `0xFC7` (host_last_ref `0xFC7`). The guest is in `0x72E1E0` waiting for `0xFC9` (`[[r2+0x5AB0]+0x98]`) |
| last command decoded | header `0x00041FD8` at `0x12060` (method `0x1FD8`, count 1, data `0x1` at `0x12064`). The word at GET is `0x20014180` (JUMP to the shared block) |
| walker | `in_pass=0`, `in_dispatch=0`, `open_cb_ms=0`, last pass 1391 ms earlier. Inner counters stopped (9,764,296 data words and callbacks). Slowest callback: 32 ms (method `0x1824`) |
| CALLs | 6 CALL/RET pairs to SPU-built chunks `0x01D34000`-`0x01D48000`, all returned. `call_depth=0`, `call_nested=0`. Up to 197.7 s `[words]` shows `call=0`, so this is the first race frame |
| present thread | tid 11300, op=`render-frame` for 1063 ms. 4062 frames, last frame 3 draws |
| watchdog | `[fc-watchdog] no progress for 2016 ms in stage=beat`, one report per stall, never cleared. No `[rsx-hb]` after 201.75 s, so the present thread made no progress for ≥ 5.8 s until the end |
| host stack | `VCRUNTIME140+0x1c63d` (memcpy) ← exe `+0x1757d043` ← `+0x1757cc9e` (`render_frame()` call at `present_guest_frame`, `rsx_d3d12_backend.c:9609`) |
| memcpy site | Disassembly at `0x15757d03e` matches the B8 font-atlas upload: `ID3D12Resource::Map` (vtbl +0x40) then the row copy `memcpy(mapped + y*pitch, src + y*w, w)` (`rsx_d3d12_backend.c:6109-6112`) |
| backend | `draw_count=974/2048`; `vp_vb_offset=100663296` > `vb_cap`, `vertex_buffer_full` drops at flip 4038; `fence_done=8192 = fence_want` |
| semaphores / SPU | `sema held=0`. Renderable frame-end spin `0x50C818` returned (37 ms) at 207.56 s, so the producer finished the next frame |

### Phase 5 classification
1. **Incomplete SPU command data:** VERIFIED not the cause. All 6 race CALLs
   returned, and the walker reached the end-of-frame `0x1FD8` word.
2. **Incorrect method decoding:** no evidence. The walker ended the segment
   normally. Drops are backend-capacity (`vertex_buffer_full`), not decoding.
3. **Expensive per-method callback:** VERIFIED not the cause. The worst was
   32 ms, and none was open.
4. **Missing semaphore or fence completion:** VERIFIED not the cause. The fence
   is complete and no semaphore is held.
5. **Premature buffer reuse:** VERIFIED not the cause. The guest correctly
   throttles on ref (`0xFC7` vs `0xFC9`).
6. **Present-thread synchronization:** **FIRST VERIFIED FAILURE.** `render_frame()`
   for the first race frame never returns (≥ 5.8 s). The walker runs on the same
   thread, so it cannot reach GET `0x12068`, ref stays at `0xFC7`, the guest
   blocks in `0x72E1E0`, and the game's 4 s Present watchdog fires. GET is
   stationary because the walker is not running; it is not a stalled method loop.

### Unresolved (HYPOTHESIS)
- **Whether the atlas memcpy is where it is stuck, or only where the one stack
  sample landed.** That depends on the bound B8 texture's `tex_w`/`tex_h`/
  `tex_src_offset` at the race bind. "atlas uploaded" was printed only for
  640x360, and the race dimensions were not logged.
  - Leading idea: a race B8 texture with large dimensions or an uncommitted source
    range, so the copy is very long or slow to page in.
- Whether the 96 MiB `vp_vb_offset` overflow (974 draws) makes the replay
  expensive too.

### Recommended minimal correction (not implemented)
- In `render_frame`, bound the legacy B8 atlas upload (`rsx_d3d12_backend.c:6071-6112`):
  - upload only when the bind is the cellFont atlas (the expected dimensions),
    or cap `w*h`;
  - don't re-upload every frame a large race B8 texture is bound.
- Before applying it, the next run needs `tex_w`/`tex_h`/`tex_src_offset` and a
  render-frame sub-stage in the stall snapshot to confirm it.
- No change to game logic, physics or AI. No global GPU waits.

**T91 correction (2026-10-27):** the sampled `memcpy` is `vp_vb_grow()`, not the B8 atlas upload. It copies 96 MiB out of a write-combined UPLOAD mapping, and that grow finished at 205.62 s. See `generated/analysis/t91/RENDER_FRAME_NONCOMPLETION.md`.

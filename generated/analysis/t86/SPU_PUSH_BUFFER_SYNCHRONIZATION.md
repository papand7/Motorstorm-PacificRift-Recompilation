# T86: SPU push-buffer synchronization and lifetime audit (offline, 2026-10-27)

Owner: session motorstorm01-21. Worktree `ps3recomp-t86`, branch `agent/t86-pb-sync`, based on `9eae569` (the T84D tree). Nothing was merged or pushed.
Out of scope: the T84E offset-table fix (session motorstorm01-20). T86 changes no offset-table code, builds no game, and launches nothing.

Static method: retail ELF, using `t84/tools/ppcdis84.py` plus the new `t86/tools/wdis.py` (word-by-word, because capstone stops at the first undecodable word), `nid.py` (import NIDs) and `find_put.py`. Also used: `t82/renderablejob.dis`, a source audit of `ps3recomp-t86`, and the existing T85 run log (`generated/runs/20261027-005915-t85-f1-sema`, `[words]` lines).

## 1. Verdict

- **VERIFIED (static): by design, the original game never lets the RSX execute a push-buffer CALL before its SPU job has finished.**
  - The CALL is written into the frame's command buffer early (`0x50E0FC`).
  - That buffer only becomes reachable when PUT moves.
  - PUT has exactly two writers: init (`0x736CE8`) and the flip path (`0x7367E0`).
  - The flip path runs only after the frame-end spin (`0x50C818`), which waits until every job has signalled completion.
- **Intended overlap (VERIFIED):** the RSX runs frame N while the SPUs build frame N+1, into the other parity pool and the other frame buffer.
  - Reuse two frames later is guarded on the PPU by a spin on `ctrl->ref` at `0x72E1E0`.
  - The value it waits for is the SET_REFERENCE that sits after frame N's buffer in the stream.
- **VERIFIED (source): the native runtime keeps every edge of that contract.**
  - The walker never reads past `put`.
  - An SPU DMA PUT is a synchronous copy, and the job waits for its tag before it signals.
  - The completion atomic commits under a lock-line release.
  - PPU `sync` lowers to a seq_cst fence before the PUT store.
  - The walker load-acquires `put`.
  - `ref` is published only after the walker has executed the SET_REFERENCE, never earlier.
- **No synchronization or lifetime defect is proven.** The 17–20 jobs still pending at `0x50C818` are the designed wait, not a race. So no correction is proposed.
- **Open (HYPOTHESIS):**
  - mid-frame exposure through a command-buffer overflow callback (C2);
  - the stale-tail effect of a 0xFFFFFFFF overflow JUMP (C6);
  - the exact depth of the ref throttle (C3, PARTIAL).
  - None of these can be observed until the T84E fix lets the CALLs through. §6 gives the bounded probe.

## 2. Original PS3 contract (one race frame)

| # | Step | Guest site / offsets | Mechanism | Status |
|---|---|---|---|---|
| 1 | PPU prepares the job | `0x50D868`: slot = atomic ++`[rs+0x24E8]`; EA = `[rs+0x24F0+4*([rs+0x454]&1)]` + slot<<14; job block `[rs+0x2460]`+job·0x1F0 (+0xC0 slot, +0x1E4 → `rs+0x2560`) | normal stores | VERIFIED (T85 §2) |
| 2 | RET pre-store | `0x50D914`: word 0 of the slot = `0x00020000` | an unfilled slot is a valid empty sub-buffer | VERIFIED |
| 3 | Submit to SPURS | job list `[rs+0x2464][job]`, vt+0xC alloc / +0x14 submit, module "renderablejob" | SPURS job queue | VERIFIED |
| 4 | CALL emitted at once | `0x50E0C4..E8`: IO = `[[0x1367100+0x34]+(EA>>20)*2]`; `>0xFF` → `0x50E5DC` (CALL 0xFFFFFFFF). Otherwise `0x50E0FC` → `0x757028`→`0x735BB0` writes `off\|2` at `[0x1367060+8]` | plain store into the frame command buffer (context `0x1367060`, stored at `[0x12C5CAC+4]` by `0x511B5C`) | VERIFIED |
| 5 | SPU DMA input | renderablejob GETs and GETL at `0x10CDC`; inputs: block, `rs+0x460` IO table snapshot, entry list | MFC GET + tag wait | VERIFIED (T85 agent B) |
| 6 | SPU generates and writes | chunk in LS; overflow at `0x40D0` (atomic slot ++, JUMP `0x20000000\|off`, PUT 0x20); end `0xE7B0`: RET at `0xE818`, **final PUT `0xE8A4`, then tag wait `0xE8C4..CC` (WrTagMask, WrTagUpdate=1, RdTagStat)** | data lands before the job continues | VERIFIED |
| 7 | Completion | `0x12180`: GETLLAR/PUTLLC atomic ++ at EA `desc+0x1E4` = `rs+0x2560`, after step 6's tag wait | lock-line atomic | VERIFIED |
| 8 | PPU waits | `0x5226A8` → `0x5226E4 bl 0x50C818`: spin until `[rs+0x2560]==[rs+0x44C]`, then reset `0x2560/0x44C/0x24E8`, `0x454++` (parity), `0x450++` | PPU spin | VERIFIED |
| 9 | Throttle | flip path `0x7576A8`→`0x72E518` → `0x72E5BC bl 0x72E1E0`: spin while `ref − [st+0x98] < 0` (`[[libgcm r2+0x5AB8]+8]` = ctrl->ref), `sys_timer_usleep(30)` per loop, gives up after 4× the timebase frequency (≈4 s) | PPU ← RSX reference | VERIFIED code; depth PARTIAL (C3) |
| 10 | Expose to the RSX | `0x72E648 bl 0x736770`: `0x736550` writes the ring-slot JUMP → frame buffer (`0x735B50`), the frame-buffer-end JUMP → next ring slot, and SET_REFERENCE(n) (`0x7358F0`); `0x736618` writes the flip commands; **`0x7367D4 sync`; `0x7367E0 stw` PUT** | sync + PUT | VERIFIED |
| 11 | GPU executes | ring slot k → JUMP → frame buffer (CALLs → chunks → RET) → JUMP → slot k+1: SET_REFERENCE(n), flip | in-order FIFO | VERIFIED (static); layout confirmed by T85 `[words]` |
| 12 | Recycle | pool parity and frame buffer are 2-deep (`0x14180`/`0x214180`); ring slots 4-deep (`0x10000..0x13FFF`, `(idx+1)&3` at `0x7365A8`) | reuse in frame N+2 after the step-9 throttle | VERIFIED layout; guard depth PARTIAL |

Other facts:
- **PUT writers.** A raw scan of the whole text finds 5 `sync` and 77 `lwsync`. The only `sync`→PUT stores are `0x7367E0` and `0x736CE8`. Every branch to `0x736770` comes from `0x72E648`, inside the flip function. Every flip-stub call in `0x5226A8` (`0x5227D8`, `0x52283C`, `0x522988`) comes after `0x5226E4`. VERIFIED.
- **Flip status.** `cellGcmGetFlipStatus` (E315A0B2) is called only from libgcm init (`0x736870`). `cellGcmResetFlipStatus` has no direct caller. The throttle is the reference value, not the flip status. VERIFIED.
- **Context and ring.** The HLE `_cellGcmInitBody` (`0x7256D8`→`0xCC0A9C`, out pointer `0x135BED0`) builds a 64 KiB ring with the HLE overflow callback. The game draws through its own context at `0x1367060`. Which callback that context uses was not traced (C2).
- **T85 `[words]`:**
  - PUT moves between `0x10068`/`0x11068`/`0x12068`/`0x13068`, one ring slot per frame.
  - The JUMPs go ring → `0x14180`/`0x214180` → back to a ring slot.
  - A frame buffer holds about 0x5D540 B (about 382 KB).

**Does the game intend GPU/SPU overlap?** Only across frames, not within one. The RSX may not see frame N's CALLs before all of frame N's jobs have finished (steps 8→10). It does work on frame N while frame N+1 is generated.

## 3. Native runtime comparison (`ps3recomp-t86`)

| Edge | PS3 | Native | Status |
|---|---|---|---|
| SPU PUT → data visible | MFC PUT, then tag wait | `spu_dma.h:687-716`: `memcpy` into `vm_base+ea` at submit time. The tag wait is trivially satisfied | VERIFIED, stronger than PS3 |
| Data → completion atomic | tag wait, then PUTLLC | PUTLLC commits under `spu_lockline_lock` (acquire) / unlock (release) (`spu_coherency.c:56`) | VERIFIED |
| Completion → PPU spin | lwz loop | lifted load loop. T85: every wait ends (p90 40 ms), no lost increments | VERIFIED (runtime, T85) |
| PPU `sync` → PUT | sync | `PPU_FENCE(seq_cst)` (`tools/ppu_lifter.py:2734`) | VERIFIED |
| PUT → walker | RSX reads PUT | `cellGcmSys.c`: one `put` read per pass, then `atomic_thread_fence(acquire)`, walk `while (get != put)` (budget 0x100000 words) | VERIFIED |
| CALL/RET | hardware | CALL `(w&3)==2`, single return slot. RET only when `w==0x00020000`. Targets read live with `vm_read32(gcm_io2ea())` | VERIFIED. Nesting is not used: chunks chain with JUMP |
| SET_REFERENCE → ref | RSX writes ref after earlier commands | `gcm_ref_push_at` when executed (`:2502`), published one per tick or read (`gcm_ref_publish_one`) | VERIFIED: never early, possibly late (safe direction) |
| Flip completion | RSX executes the flip | DONE only after the walker reaches the flip word (`gcm_flip_executed_take`) | VERIFIED. Not used as the game's guard |
| Pool snapshot `rs+0x460` | copy of the IO table | `0x50B430 bl 0x756518` (memcpy 0x2000 from `[0x1367100+0x34]`) runs **after** both pool maps (`0x50B3E0`, `0x50B408`) | VERIFIED. Correct once T84E keeps the guest table live |
| D3D12 lifetime | n/a | the walker decodes chunk words on the CPU as it goes and keeps no pointer into the chunk afterwards | PARTIAL: vertex and index data deferral was not audited (not push-buffer memory) |

## 4. Candidate races

| # | Producer → consumer | Required order | Current implementation | Potential failure | Observable | Smallest experiment | Status |
|---|---|---|---|---|---|---|---|
| C1 | renderablejob → walker CALL | chunk complete before the CALL is reachable | PUT only at the flip, after the `0x50C818` spin. The host keeps every edge (§3) | an empty CALL (pre-stored RET) drops the draws | `call_empty>0` with the frame's `0x50D868` count > 0 | `GCM_WORD_STATS=5` on the T84E build + `1691914` | **Ruled out on the normal path** (VERIFIED static). The model's negative control shows what a violation would look like |
| C2 | overflow callback → walker | no mid-frame exposure | the HLE callback `cellGcm_fifo_recycle` writes JUMP and then `put=begin` mid-frame (`:2766-2771`). Whether context `0x1367060` uses it is not traced. A frame is about 382 KB, so the 2 MB frame buffer should not overflow | if it happens: the CALLs before `current` run early → empty | `[REC>]` lines (`GCM_RECDBG=1`) or a `[CTX]` callback = `GCM_FIFO_CALLBACK_SENTINEL_EA` (`GCM_CTXDBG=1`) during the race | add `GCM_CTXDBG=1` to the bounded run | HYPOTHESIS (low) |
| C3 | walker → PPU throttle → frame N+2 reuse | the walker is done with frame N before frame N+2's chunks and buffer are written | `0x72E1E0` waits for `ref ≥ [st+0x98]`. Host ref is published only after it executes | reuse with 1-deep instead of 2-deep protection if `[st+0x98]` is the current frame's value (that would deadlock until the 4 s timeout, so it is unlikely) | PT `72E1E0`: ref vs target, how often it waits, timeouts | PT config `t86/pb_sync_t86.cfg` | PARTIAL (code VERIFIED, `+0x98` bookkeeping not traced) |
| C4 | SPU atomic slot ++ (`0x130A8`, PPU `[rs+0x24E8]`) | unique chunk indices | lock-line atomics; the T85 slot count equals the job count | overlapping chunks | duplicate JUMP or CALL targets in one frame | PT `50D868` slot sequence | HYPOTHESIS. Not observed (T85), and no overflow happens in the race |
| C5 | `0x50C818` reset / parity toggle | after the last job's counter increment | the spin sees equality with acquire-equivalent semantics | none found | — | — | VERIFIED no issue |
| C6 | SPU overflow JUMP into a chained chunk | snapshot table valid | `rs+0x460` is copied after the maps (§3). Before T84E it is stale: 0xFFFFFFFF JUMP | the walker skips 0xFFFFFFFF and runs into the stale tail of the chunk (an old JUMP or garbage) | `ffff>0` inside CALL targets, `resync` lines | the same run (only reached with an output > 16 KiB) | HYPOTHESIS. Moot in the race (no overflow chunks, T85) |
| C7 | walker resync heuristics | — | a resync rescues the skipped SET_REFERENCEs (`:1641-1683`), and `gcm_spu_block_for_put` may land at an SPU block | ref advances for commands that were skipped. Harmless for reuse (nothing is read) | `FIFO resync` lines | the same run | HYPOTHESIS (only on error paths) |
| C8 | `GCM_CALL_TRACE` | — | the `@flip` gate counts only `0xFEAD01xx` markers. MotorStorm's flip goes through the `0xFEAD` / direct path | no `[call]` lines | — | use `GCM_WORD_STATS` | VERIFIED (memory note), so the instrumentation does not depend on it |

## 5. Offline tests

**Synthetic protocol model:** `t86/tests/test_pb_sync_model.c`, built by `t86/tools/run_t86_tests.cmd` (clang 23.1.3 + MSVC, Windows).
- Producers, PPU and walker are real threads.
- Guest memory is relaxed atomics, so the only ordering comes from the protocol's release/acquire edges.
- All waits are spin + yield on atomics. There are no sleeps.
- The walker uses the decode rules of `cellGcmSys.c`.
- Log: `t86/logs/test_pb_sync_model.txt`. 5/5 earlier runs PASS. The overwritten negative case is bounded by the host-style pass budget.

| Scenario | Result |
|---|---|
| contract, 1/2/4/6 workers, 21 jobs × 300 frames | calls = rets = 6300; empty, stale, torn, nested, stray RET, lost all 0; refs 300 |
| stale offset table (CALL = 0xFFFFFFFF) | calls 0, rets 0, draws 0, skipped 1050 (= jobs × frames), as in T84D/T85 |
| overflow chains (JUMP inside a CALL, 600–2000 draws) | 480/480, 669 overflow chunks, no torn or stale |
| 16-byte reserve boundary: 681 draws / 682 draws | 0 overflow / exactly 80 overflow chunks (one per job), all intact |
| NEG: CALLs exposed before completion | empty = 420/420 (the detector works) |
| NEG: recycling without the ref guard (walker held inside frame 10) | stale + torn > 0 (the detector works) |
| recycling with the ref guard | the guard blocks while the walker is held, frame 12's jobs start only after release, no stale or torn |

Framework gates for commit `1691914`:

| Gate | Result |
|---|---|
| TU `cellGcmSys.c` with the T64C flags (`t84/tools/compile_tu.cmd`) | exit 0. Compared with `9eae569`: only line shifts plus one `-Wdeclaration-after-statement` (`t86/logs/tu/`) |
| suite, 30 tests (`run_suite_t84d.cmd ps3recomp-t86`) + 12 PPU/SPU tests | 0 FAIL. The verdicts match T84D's `suite_summary_t84d.txt` test for test, and `test_d3d12_depth_state` passes (`t86/logs/suite_t86*.txt`) |
| `test_gcm_sync_trace` | PASS |
| `audit_public.py --staged` | the same 25 baseline BLOCK items, none in `cellGcmSys.c` (`t86/logs/audit_t86.txt`) |

## 6. Instrumentation (disabled by default) and proposed runtime probe

**Commit `1691914`** (`ps3recomp-t86`, +14/−6, `libs/video/cellGcmSys.c`). Patch: `t86/patches/0001-GCM_WORD_STATS-count-empty-target-CALLs-and-0xFFFFFF.patch`, sha256 `6a541e3d90cb314d3d8475866f9ac59ea91a55e6dd463de9456dbc708fa9f4be`.
- This is `GCM_WORD_STATS` only. When it is unset, nothing runs.
- It appends ` call_empty=N ffff=N` to each `[words]` line. That is the premature/empty CALL count and the unmapped-CALL signature.
- The existing `call=`/`ret=` parsers (`t84e_check.py`) are unaffected.
- The extra cost is one `vm_read32` per CALL while stats are on.

**`t86/pb_sync_t86.cfg`** (PT, read only), containing the T72 race-entry sites and these records:

| Site | Records | Answers |
|---|---|---|
| `50D868` | slot, job, frame `+0x450`, parity, done, count `ctx+0x10` | submission order and the buffer generation (frame, slot) |
| `757028` | `r4`, `lr` (`50E100` normal / `50E5F0` unmapped) | normal vs unmapped CALL branch, the CALL target |
| `50C818` | jobs vs done | SPU completion relative to the end of the frame |
| `72E1E0` | ctrl->ref vs `[st+0x98]` | throttle depth, waits and timeouts (C3, buffer reuse) |
| `736770` | put/get/ref before the PUT store | exposure time relative to the walker |

The PT site at `72E1E0` and `736770` needs those addresses to be recognised as function entries. That has not been verified: PARTIAL.

**Proposed bounded run** (not run, needs authorization). It needs one build that combines the T84E fix with `1691914`, and none exists yet. Use the T84D/T84E harness and environment: `VP_NOFIXPROJ=1`, a fresh private HDD, the race-entry controller, a 205 s session and 210 s host timeout, no driving, `TEX_SAVE` off. Add `GCM_WORD_STATS=5 GCM_CTXDBG=1 PS3_TRACE_FILE=t86/pb_sync_t86.cfg`.

Pass criteria:
- `call>0`, `ret≈call`, `call_empty≈0`, `ffff=0` in race windows;
- no `[CTX]` change to the HLE sentinel callback;
- the `72E1E0` ref never more than 1 frame behind its target, and no 4 s timeout.

A nonzero `call_empty` with `0x50D868` counts > 0 points to C2. Otherwise it points to renderablejob producing RET-only output (type 32/64 with a zero count, T85 F4).

## 7. Correction

None proposed. No synchronization, visibility or lifetime defect was proven. The original contract is honoured by the runtime, and the pending jobs at the frame end are the game's designed wait. A global GPU wait would add nothing. The next step is the probe in §6, after T84E.

## 8. T86 integration: T84E + T86 for runtime validation (2026-10-27; built once, not launched)

- **Worktree** `ps3recomp-t86i`, branch `agent/t86-int-t84e`. It is T84E `2dcf255` plus T86 `1691914`, cherry-picked cleanly as **`1163f34518ddae5d15c9677ca68088767817c50d`**.
  - Ancestry: `9eae569` → `2dcf255` → `1163f34`.
  - The diff from `9eae569` touches only `libs/video/cellGcmSys.c`, `tests/test_gcm_offset_table_live.c` and `tools/test_gcm_offset_table_live.py`.
  - Not merged or pushed. The T84E and T86 worktrees are untouched.
- **What `1691914` is:** instrumentation only. It adds two `GCM_WORD_STATS` counters: `call_empty`, a CALL whose target word 0 is still RET when taken, and `ffff`.
  - With the variable unset, nothing changes.
  - With it set, the cost is one `gcm_io2ea` and one `vm_read32` per CALL word, roughly 2000 per frame.
  - It never writes guest or walker state.
- **Offline gates:**

| gate | result |
|---|---|
| renderer suite (`int/logs/suite_t86i.txt`) | 29 tests, verdicts identical to T84E |
| GCM mapping tests (`int/logs/extra_tests.txt`) | `test_gcm_offset_table_live` PASS (the 54-check regression, 0 failures). `io_alloc`, `map_flags`, `io_mappings` and `mmapper_hle_heap` are SKIP (POSIX), the same as the baseline |
| other suites | `test_gcm_sync_trace` PASS, `test_d3d12_depth_state` PASS |
| T86 model (`int/logs/test_pb_sync_model.txt`) | PASS |
| registrations against the T84E build | `ppu_hle_nids.cpp` identical (2442 lines). `hle_nid_sources.txt` and `CMakeCache.txt` identical apart from paths |
| camera | `rsx_d3d12_backend.c` and `include/` are unchanged from T84E. `test_vp_fallback` and `test_vp_branch_base` PASS |
| audit `--tree` | the same 25 baseline BLOCK items |

- **Build** `build/motorstorm-t86i`, T64C configuration (`int/configure_t86i.cmd`, `int/build_t86i.cmd`): rc=0, 0 FAILED, 279/280 steps (same as T84E).
- **Pin:** `t86/int/exe/MotorStormPacificRiftRecomp.exe`, sha256 **`0f6b5cdae9ae1465d9a6692607f27f9ce2a1870b18bc314abee950612cdae6ac`**.
  - The earlier pins are unchanged (`int/logs/existing_pins_{before,after}.sha256`).
- **Prepared run:** `py -3 generated/analysis/t86/int/run_t86i.py launch`. It is the T84E harness with:
  - `VP_NOFIXPROJ=1`, `GCM_WORD_STATS=5`, `GCM_CTXDBG=1`;
  - `PS3_TRACE_FILE=t86/pb_sync_t86.cfg` (with the race-entry controller sites);
  - a fresh private HDD;
  - a 205 s session limit and 210 s host timeout;
  - no driving and no `TEX_SAVE`.
  
  `prepare` and `dryrun` passed. Nothing was launched.
- **Reading the run:**
  - `call_empty>0` means C1, the walker ran ahead of the SPU.
  - In PT `736770`, a PUT store before the frame's `50C818` spin finishes, or a callback in `[CTX]`, means C2.
  - In PT `72E1E0`, a ref below target, or a timeout, points to C3.
  - `ffff>0` means C6.
- **Limitation:**
  - T84E's run stalled with the walker inside slot 5 (`get=0x01D12660`). `[words]` only prints while words are being walked, so if the walker is stuck on one word, the stalled window may never print.
  - Dumping the walker's word at the stall needs one more build, which is not authorized.

## 9. T86I runtime result (the one authorized launch, 2026-10-27)

Run `generated/runs/20261027-072822-t86i-pb-sync`; runtime directory `t86/int/runtime-20261027-072822/` (76 CELLMARK frames, plus `frame_075_thumb.png`); logs `t86/int/logs/{launch_t86i.txt, check_t86i.txt, run_summary_t86i.md}`.
- **Preconditions:**
  - no other session or launcher was running;
  - the exe sha256 was `0f6b5cdae9ae1465d9a6692607f27f9ce2a1870b18bc314abee950612cdae6ac` (verified before the run and again after it);
  - HEAD was `1163f34` (`2dcf255` + `1691914`);
  - the prepared private HDD and the race-entry controller were used;
  - `VP_NOFIXPROJ=1`, `GCM_WORD_STATS=5` and `GCM_CTXDBG=1` were set; `RSX_RT_READBACK` and `TEX_SAVE` were off.
- **Outcome:** launched once and not restarted. The run ended at **160.6 s**, exit 2, `stop_line` **`Gc ERROR: GcKernel::Present() Timeout!`**, inside the 205/210 s limits. GcKernel reported:
  - `Last Reference Passed: 4722`;
  - `Gpu Get` offset `0x00011068`;
  - last kick `0x11414180..0x114716e4`.
- **Earlier pins:** unchanged (`int/logs/existing_pins_postlaunch.sha256`).

**VERIFIED (runtime)**

| # | question | result |
|---|---|---|
| 1 | normal CALL branch | **yes**. All 79 `SetCallCommand` calls came from `lr 0050E100` (T84D: 0 of 1925) |
| 2 | unmapped branch gone | **yes**. 0 calls from `0x50E5EC` (T84D: 1925) |
| 3 | FIFO CALL count > 0 | **not observed**. All 30 `[words]` windows show `call=0`. No window was printed after the CALLs began (see 5) |
| 4 | targets mapped | **yes**. All 79 lie inside `0x01A00000` / `0x01D00000` (+0x300000) at a 16 KiB stride. The pools alternate per frame |
| 5 | walker advances | **no**. The last `[words]` window was printed at about 150.9 s. A window prints on the first word walked at least 5 s after the previous one, so **the walker processed no FIFO word after about 155.9 s**. The first CALL was emitted at 155.706 s. No present follows: the last `[rsx-hb]` is at 154.6 s |
| 6 | terrain, vehicles, scenery | **not determined**. Race loading had not finished: the last marker is `0x8C848`, and `0x8C2A0` (PostLevelLoad) and the RSXI capture were never reached. The last frame is the "Festival – Race / LOADING" controls screen |
| 7 | T86 detection | `call_empty=0` and `ffff=0` in all 30 windows, but none of those windows covers the push-buffer frames, so **C1 (empty CALL) is undetermined**, not excluded. `[CTX]` shows one context with `callback=0F800010` (the HLE sentinel). **C2 (mid-frame recycle) is not excluded**: the HLE callback is installed |
| 8 | new failures | `fifo_unmapped_io`, resync, SEMA give-up, SPU, DMA, RSX, NOSYS and fatal are all 0 (as in T84D and T84E). The new failure is the RSX stall and the present timeout, as in T84E |

Push-buffer frames, from PT `0x50D868` (all 79 records, `slot == job` in every row, so chunk indices are unique; this matches T85):

| frame `[rs+0x454]` | batches | time | CALL targets |
|---|---|---|---|
| 0x1270 | 19 | 155.706–155.771 s | `01A00000..01A48000` |
| 0x1271 | 20 | 155.930–156.004 s | `01D00000..01D4C000` |
| 0x1272 | 20 | 156.273–156.339 s | `01A00000..01A4C000` |
| 0x1273 | 20 | 160.467–160.535 s | `01D00000..` |

- Frame 0x1272 rewrote frame 0x1270's slots about 0.5 s after 0x1270, even though no frame had been presented since ≤ 155.6 s.
- Before frame 0x1273, thread 28 sat **4.1 s in the ref throttle** (PT `ev=stall` at 159.64 s, `recent=…0072E1E0…`). That is the game's own about-4 s throttle timeout, and GcKernel's present timeout follows.

**Instrumentation gaps**
- `pb_sync_t86.cfg` used `sample=251`, so `0x50C818`, `0x72E1E0` and `0x736770` were logged only once per 251 calls. The last record of each is at about 149.2 s, before any push-buffer frame, so these sites recorded nothing during the push-buffer frames.
- `[[r2+0x5AB8]+8]` reads a constant `0x11210000`, an address rather than `ctrl->ref`. The ref field is one dereference deeper. The target `[[r2+0x5AB0]+0x98]` does count frames (`0x11A4` at frame about 4516).
- So the PPU-side PUT/ref timing during those four frames is **not observed**.

**Last confirmed command**
- The last FIFO evidence is the 150.9 s window: `get=0x00011068`, `put=0x00012068`, last jumps `20214180@00011068`. That is the ring slot that jumps to the frame buffer at IO `0x214180`.
- GcKernel's `Gpu Get 0x00011068` agrees.
- Which word the walker stopped on is **not observed**. In T84E it was inside slot 5, at `0x01D12660`.

**Comparison**
- **T84D:** 1925 unmapped CALLs, no stall, no draws from the push buffers.
- **T84E:** 79 normal CALLs; the walker entered 4 targets and stalled in the 5th; Present timeout at 152 s.
- **T86I:** the same 79 normal CALLs and the same stall-then-timeout pattern at 160.6 s. This time no window was caught inside a target.
- So the stall reproduces, VERIFIED across 2 runs.

**Hypotheses (unresolved)**
- **H1 (C1):** the walker reaches a slot before renderablejob finishes it. This is consistent with T84E's mid-slot get, and `done` was ≤ 1 at every batch entry, so the jobs had not finished when the PPU issued the CALLs. Not proven.
- **H2 (C2):** the HLE recycle callback publishes `put=begin` mid-frame and exposes CALLs early. The callback is installed; whether it fires in these frames is not traced.
- **H3:** the slot holds an NV406E/NV4097 acquire on a label that nothing releases. The walker is stuck and no window prints.
- **H4 (C3):** frame 0x1272 rewrites 0x1270's slots while the walker is still inside them. VERIFIED that the rewrite was issued while presents had stopped. Whether the walker was in 0x1270 at that moment is not observed. This is most likely a consequence of the stall, not its cause.

**Next recommended action (needs authorization: one source change, one build, one launch)**
- Add a disabled-by-default walker stall dump. When `get` has not moved for 1 s, print once:
  - `get`, `put` and the current word;
  - the 16 words at `get`;
  - the CALL return slot;
  - `[rs+0x2560]` against `[rs+0x44C]`.
- Fix `pb_sync_t86.cfg`: drop `sample` for the five sync sites and read ref as `[[[r2+0x5AB8]]+8]`, after verifying the field statically.
- That one run decides between H1, H2 and H3. Do not add a global GPU wait.

**Correction (T88, 2026-10-27):** row 5 above, "the walker processed no FIFO word after about 155.9 s", holds only for the walker's outer word loop. A `vertex_buffer_full` draw callback still ran at PT ≈ 156.17 s, so the walker was inside one method header's data loop, or a backend callback, at that time. See `t88/RSX_VERTEX_BUFFER_OVERFLOW.md` §4.

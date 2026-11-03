# T85 — RSX push-buffer pipeline (offline, static)

Scope: SPU-generated push buffers from populated scene lists to the host FIFO walker. Renderer-site
attribution (`0x481B00` callers, view → list) is T84D's work and is not repeated here.
Method: retail-ELF disassembly (`t84/tools/ppcdis84.py`, `t85/tools/dscan.py`, `t85/tools/blscan.py`),
SPU static analysis (`t85/agentB/renderablejob.md`), and a source audit of the runtime walker
(`t85/agentA/fifo_walker_audit.md`). Nothing was built, launched or changed.

## 1. Pipeline

```
 PPU renderer (0x481B00 family, T84D)            ctx: +4 list EA, +8, +0xC list bytes,
   └─ vtable 0x0108C060 → ExecutePushBuffer 0x50D868 (r3=rs RenderSystemATG, r4=ctx)  +0x10 count, +0x24 view
        1  slot = atomic++ [rs+0x24E8]
        2  pb   = [rs+0x24F0 + 4*([rs+0x454]&1)] + slot<<14      16 KiB chunk, frame-parity pool
        3  pb[0] = 0x00020000 (RETURN)                 @0x50D914  pre-fill
        4  job block 0x1F0 B at [rs+0x2460] + [rs+0x44C]*0x1F0  (layout §2)
        5  job list [rs+0x2464][rs+0x44C]: 4 DMA inputs, kick (vt+8, vt+0xC, vt+0x14)
             in1 block 0x1F0 | in2 rs+0x460 IO-offset table snapshot 0x2000
             in3 [ctx+4] entry list ([ctx+0xC]+15)&~15 | in4 [rs+0x2474], [rs+0x2468]*0x60
        6  off = IO table [[0x01367100]+0x34] halfword[pb>>20] (>0xFF → 0xFFFFFFFF)
        7  CALL off|2 into the main FIFO NOW   0x757028 → 0x735BB0 (ctx 0x01367060 {beg,end,cur,cb})
        8  [rs+0x44C]++ ; 0x4F8950([rs+0x24]) ; 0x521628(rs+0x10) state-cache reset
                │
 SPU renderablejob (module desc 0x0108C420, job lists "Renderable")
        a  type = desc+0x1EE halfword ∈ {0,32,64}, else stopd 0x1216C
        b  opcode interpreter 0xE970 (table 0xE9AC) → shader/state/texture headers,
           DRAW_INDEX_ARRAY 0xCA10 / draw-arrays 0xCE10, GCM-style ctx at LS 0x17800+20
        c  overflow cb 0x40D0: idx = GETLLAR/PUTLLC atomic++ EA [LS 0x13710] (= rs+0x24E8),
           EA = [0x13730] + idx<<14, off via snapshot table [0x13760], emit JUMP 0x20000000|off,
           PUT chunk, atomic add (0x4000-size) at EA [0x13770]
        d  end: RETURN 0x00020000 (0xE818), PUT last chunk (0xE8A4), atomic++ EA desc+0x1E4 (= rs+0x2560) @0x12180
                │
 PPU frame end 0x5226A8
        └─ 0x5226E4 → 0x50C818: spin while [rs+0x2560] != [rs+0x44C]
             then zero 0x2560/0x44C/0x24E8/0x2570, 0x454++ (parity), 0x450++, 0x24EC = slots<<14
        └─ report 0x7576D8 (GET_REPORT), flip 0x7576A8, optional label-0x48 path 0x522950
                │
 Host walker gcm_rsx_process_fifo_unlocked (libs/video/cellGcmSys.c:1843), frame_clock thread
        reads put once per pass, every word live via vm_read32(gcm_io2ea(get));
        CALL → single return slot; RET 0x00020000 → back; JUMP old form only
        → rsx_commands / D3D12 backend → vertex program constants → (8654a4d) projection fallback
```

All PPU and SPU steps are VERIFIED from disassembly. The walker steps are VERIFIED from source
(agent A, `cellGcmSys.c` line numbers in its report).

## 2. Job block (0x1F0 B, VERIFIED)

| off | content | off | content |
|---|---|---|---|
| 0x00–0xBF | three matrices: `[rs+0x10]+0x30`, `rs+0x1F0`, `[rs+0x10]+0x70` | 0x198 | slot allocator EA `rs+0x24E8` |
| 0xC0 | slot | 0x19C/0x1A0 | pool base |
| 0xC4 | `[ctx+8]` (type 32 draw count = >>5) | 0x1A4–0x1AC | floats |
| 0xC8 | `[ctx+0xC]` list bytes | 0x1B0–0x1D8 | further ctx fields |
| 0xCC | `[ctx+4]` list EA | 0x1DC/0x1DE | halfwords |
| 0xD0 | `[ctx+0x10]` entries (type 64 count) | 0x1E0 | 64-bit flags |
| 0xD4–0xE4 | `rs+0x2494/0x2484/0x24A4/0x24B4/0x24E4` | 0x1E4 | completion counter EA `rs+0x2560` |
| 0xE8–0x194 | 4 × 0x2C records from `[obj+0x88]+0x20..0x48` | 0x1E8 | `rs+0x2570` |

Pools: `0x50B390` allocates two pools of `[rs+0x440]` MB (`[rs+0x43C]` when r4==1), 1 MB aligned
(`0x756948`), mapped through `0x757288` = cellGcmMapMainMemory (NID 0xA114EC67, VERIFIED). Old
logs show two 3 MB maps at IO 0x46F00000/0x47300000. `0x756518` copies the IO table into
`rs+0x460` at allocation time.

## 3. Ordering contract (VERIFIED guest, VERIFIED host difference)

The guest puts the CALL into the main FIFO **before** the SPU has written the chunk. The only thing
that protects it is the frame-end spin in `0x50C818`, which precedes flip. No ACQUIRE that waits on
`rs+0x2560` is emitted in `0x50D868` (VERIFIED). On PS3, then, correctness depends on the RSX
not reaching the CALL before the job's RETURN overwrites `pb[0]`. That holds because the RSX is
behind and the PUT is published late.

The host walker drains on a timer (vblank, then about every 4 ms), walks to the current `put`,
reads CALL targets live, and passes ACQUIRE without waiting by default. A CALL whose target
still holds the pre-filled RETURN returns immediately and logs nothing (agent A §2–3).

## 4. Failure boundaries

| # | Boundary | Guest site / offsets | Status | Distinguishing observable |
|---|---|---|---|---|
| F0 | Not in this pipeline. The D3D12 projection fallback in c529ab0 replaces c0–c15 when c0.x ∉ (0,8). The race has c0.x = −1.24474, so the main pass is drawn through a substitute camera and back-face culled, while the front-culled reflection survives. Fixed by **8654a4d**, which is **not** an ancestor of c529ab0 (T64C exe). | host `rsx_d3d12_backend.c`, `vp_fallback.h` | **REJECTED as cause of the missing near geometry**: T71/T72/T84C and the T85 run all used `VP_NOFIXPROJ=1` (§6) | Main-pass draws are **present** in RSXI/FIFO, with nonzero index counts, but 0 samples pass. `VP_NOFIXPROJ=1` on the T64C exe restores them. |
| F1 | Empty CALL: the walker reaches a CALL before renderablejob overwrites `pb[0]`. | `0x50D914` pre-fill, `0x735BB0` CALL, `rs+0x2560` vs `rs+0x44C` | HYPOTHESIS (possible in both guest and host code; not observed) | `GCM_CALL_TRACE` "empty" CALLs for main-pass targets; draws **absent** from RSXI. The empty fraction grows with interpreted SPU time (T64C has WWS AOT off). |
| **F2** | IO translation: a stale guest offset table gives a CALL or JUMP to 0xFFFFFFFF. | PPU `[[0x01367100]+0x34]`; SPU snapshot `rs+0x460` (in2), `[0x13760]` | **VERIFIED (runtime + code), see §6.** The PPU emits `0xFFFFFFFF` instead of a CALL | "FIFO CALL to unmapped IO" or "resync (unmapped-CALL)" lines; walker resyncs. These are always logged (first 8). |
| F3 | Interpreted SPU atomics (GETLLAR/PUTLLC with the `brsl r2` link idiom, as in T82) corrupt the slot index, so chunks overlap. | renderablejob 0x40D0 path, EA `rs+0x24E8` | HYPOTHESIS | Two jobs write the same chunk: JUMP targets repeat within a frame; `[rs+0x24E8]` at frame end ≠ jobs + overflow chunks. |
| F4 | A job emits RETURN only: `stopd`, or a zero count for its type. | `desc+0x1EE` type; `[desc+0xC4]>>5`; `[desc+0xD0]`; `stopd` 0x1216C | HYPOTHESIS | SPU stop logs; CALL trace "empty" with the counter still incremented (no `stopd` → completion runs). |
| F5 | Buffer reuse: a parity flip after the wait overwrites a chunk the walker has not yet consumed. | `[rs+0x454]&1`, `0x50C818` | HYPOTHESIS; needs the walker to lag more than one frame | Non-empty CALLs whose draws belong to the previous frame (RSXI `cmd_offset` duplicates across flips). |
| F6 | More `0x50D868` calls per frame than job lists `[rs+0x438]`. | `[rs+0x2464][rs+0x44C]`, block array `0x438*0x1F0` | HYPOTHESIS, not checked (21 calls per frame seen in T84C) | Read `[rs+0x438]`; an overrun would show as wrong block contents, not as a hang. |
| F7 | Walker CALL/RET model: single return slot, no nesting; a stray RET goes to IO 0 without a log. | `cellGcmSys.c:2141/2151` | HYPOTHESIS: renderablejob chains chunks with JUMP, not nested CALL (agent B), so this is low risk | `GCM_CALL_TRACE` with a target whose `words` exceed its chunk chain; `get` reaching 0 after RET. |

Agent B found no view mask in renderablejob. Main pass and reflection pass go through the same
`0x50D868` path and are told apart only by `ctx+0x24` and the matrices in the block. Nothing in the
push-buffer path itself favours the reflection pass. Superseded by §6: no push-buffer CALL reaches the walker in either pass.

## 5. Smallest useful runtime experiment (not run; needs authorization)

One bounded race run with the existing **T64C exe**, comparing two environments, A/B:

1. `VP_NOFIXPROJ=1` (F0). If the main pass appears, F0 is confirmed and F1–F7 can be dropped.
2. Only if 1 stays black: `GCM_SEMA_ACQUIRE=1 GCM_SEMA_ACQUIRE_MS=50 GCM_WORD_STATS=5`, plus a PT
   probe at `0x50C818` entry that records `[rs+0x2560]` and `[rs+0x44C]`. Lag between the CALL and
   completion, together with RET-heavy word stats, indicates F1.

If an e32bcc5 build becomes available, `GCM_CALL_TRACE=2000@<flip>` together with RSXI
`cmd_offset`/`call_ret` separates F0 (draws present, culled) from F1/F4 (CALLs empty) in one run.

## 6. Runtime result (T85 run, 2026-10-27)

Run: `generated/runs/20261027-005915-t85-f1-sema`. One bounded launch of the T64C exe (`162afb4a…`, sha
checked) using `t85/run/run_t85.py` (T84C harness plus `GCM_SEMA_ACQUIRE=1`, `GCM_SEMA_ACQUIRE_MS=50`,
`GCM_WORD_STATS=5`; PT `t85/run/f1_trace_t85.cfg`; `VP_NOFIXPROJ=1` kept). The harness stopped and killed the
game at 172 s (LoadRace checkpoint), and the RSXI capture completed. No source change, build or commit.

**Step 1 (`VP_NOFIXPROJ=1`) was already answered before this run.** T71 Run A, T72 and T84C used the same exe with
`VP_NOFIXPROJ=1`. The camera was correct and the reflection was correct, but the main pass lacked near
geometry (T84 §1). F0 therefore does not explain the missing draws, so the run went straight to step 2.

| observable | value | label |
|---|---|---|
| walker `[words]` over the whole run (34 × 5 s windows) | **`call=0 ret=0` in every window**; hdr 130–160 k, jump 44–50 | VERIFIED |
| `0x50D868` calls in the race | 19–21 per frame (`[rs+0x44C]` at the wait), 75 frames traced | VERIFIED |
| `[rs+0x24E8]` (slots) at the wait | equal to the job count, so there are no overflow chunks and no JUMP chaining | VERIFIED |
| jobs still pending at `0x50C818` entry | 17–20 of 19–21; wait p50 36 ms, p90 40 ms, max 47.5 ms | VERIFIED |
| `FIFO resync` / unmapped-CALL logs | 0 | VERIFIED |
| `[SEMA]` | 1 ACQUIRE (label 0x480) gave up after 50 ms; no others | VERIFIED |
| pool maps | EA 0x17000000 → IO 0x01A00000 and EA 0x17400000 → IO 0x01D00000 (3 MB each) | VERIFIED |

**Mechanism (F2):**
1. The game calls `cellGcmGetOffsetTable` once, inside libgcm init (`0x7368D8` → import stub `0xCC0AFC`).
   It stores the ioAddress table pointer at `0x01367100+0x34` (`0x7368E8`).
2. The host fills that guest table only inside `cellGcmGetOffsetTable` (`gcm_publish_offset_tables`,
   c529ab0 `cellGcmSys.c:3042/3056`; still the case at `e32bcc5` :3118/3132). `cellGcmMapMainMemory`
   (:3215/3270) updates only the host arrays.
3. The pools are mapped later, at renderer construction (`0x50B390` → `0x757288`). Their guest entries
   `ioAddress[0x170..0x176]` therefore keep reading 0xFFFF.
4. `0x50D868` at `0x50E0E0`: `lhz` of that entry, then `cmplwi 0xFF` → `bgt 0x50E5DC` → `li r23,-1` →
   `0x757028`/`0x735BB0` writes `0xFFFFFFFF | 2` = **`0xFFFFFFFF`** where the CALL should be.
5. The walker counts `0xFFFFFFFF` as a header (it is neither JUMP, CALL nor RET), decodes it as type 7, and
   skips 4 bytes without logging. Every `renderablejob` push buffer is therefore dropped in **both** passes,
   silently.
6. `0x756518` copies the same stale table into `rs+0x460`, so the SPU's own snapshot (JUMP chaining) is
   stale too. That path is not reached here, because there are no overflow chunks.

Label: **VERIFIED** (code path plus runtime `call=0`). The one link not measured directly is the guest
halfword at `inject+0x3000+0x170*2` = 0xFFFF; it follows from items 1–3.

Consequences and open points:
- F1 (empty CALL) cannot occur, because no CALL is ever emitted. The SPU jobs do finish late (§6 table), and
  that would matter only once CALLs exist. **Not excluded for a fixed build** (see the user's caveat).
- Draws that do reach the RSX (backdrop terrain, foliage, the 180 reflection objects) come from paths other
  than `0x50D868`. HYPOTHESIS: PPU-built command streams; not attributed here (T84D's area).
- F3/F5/F7 are moot until CALLs flow. F6 is unchecked.

**Smallest fix (not done; needs authorization):** have `cellGcmMapMainMemory`/`MapEaIoAddress`/unmap
republish the guest offset tables (`gcm_publish_offset_tables()` after `populate_offset_table`/
`clear_offset_table`), with a framework test. Verify with a run: `[words] call>0`, `ret>0`, and
near-ground and object draws in the main pass. Then retest F1 timing with `GCM_CALL_TRACE`, because the
jobs are still pending at frame end.

## 7. Cross-check with T84D (documented findings only, 2026-10-27)

T84D ran separately (`generated/runs/20261027-010225-t84d-pb-trace`, exe `fb90538d…`, PT enter records on `0x50D868`/`0x757028`; see `t84/BLACK_RACE_RENDERING.md` §11.7). Its results agree with §6 and close the one link §6 left unmeasured:

| observable | T84D value | label |
|---|---|---|
| `0x757028` calls from `0x50D868` | 1925 of 1925 entered with `lr=0x0050E5F0` (the `0x50E5EC` unmapped branch) and `r4=0xFFFFFFFF`; 0 via `0x50E0FC` | VERIFIED |
| views/kinds affected | all: view 0 kinds 0/1/2/4 (13 323 entries), views 1–3 kind 5 (25 756 entries) | VERIFIED |
| `[call]`/`[call-late]` lines | 0, so the empty-vs-late-written question (F1) has no data in either run | VERIFIED |

The pool-slot lookup at `0x50E0E0` therefore returns > 0xFF for every slot (VERIFIED from the branch that was taken), which is the stale guest offset table of §6, items 1–4.

The F0 row stays as written: every run in §6 and in T84D used `VP_NOFIXPROJ=1`. F0 can only affect draws that do reach the backend, and no `renderablejob` draw does.

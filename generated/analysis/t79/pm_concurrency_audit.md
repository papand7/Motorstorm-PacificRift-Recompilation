# WWS job policy module (PM): multi-SPU concurrency audit

Date: 2026-10-26. Offline, read-only static audit. Nothing was built or launched.

## Inputs

- `generated/spu_raw/wws_job_pm.bin`: 11520 bytes, LS base 0xA00, entry 0xA00.
  sha256 `145395f1434fbdbb7a9596795bf0cc439b691e25d624cee9d87c1de6aeddfd0d`, which matches `wws_job_pm.json`.
- Disassembly command, with output kept in a temp file outside the project:
  `python -I ps3recomp-t79/tools/spu_disasm.py generated/spu_raw/wws_job_pm.bin --base 0xa00`.
  I cross-checked it against `generated/spu_raw/wws_job_pm/spu_recomp.c`, whose channel sequences match.
- Host code read for context: `ps3recomp-t79/runtime/spu/spurs_policy.c`, `runtime/spu/spu_channels.c` (PM intercepts at 2627/2640 and PUTLLC at 768) and `libs/spurs/cellSpurs.c` (scheduler at 1845-1890).

Layout: data and tables occupy 0xB00-0x15FF. Code runs from 0x1600 to 0x36AC, plus the interrupt and register-save stubs at 0xA00-0xAEC.

Labels follow AGENTS.md. **VERIFIED** means read directly from the instruction stream. **PARTIAL** means the instruction stream was read but field meanings are inferred. **HYPOTHESIS** means an interpretation or a runtime effect that has not been observed.

---

## 0. Key LS variables (from the code)

| LS | Meaning | Evidence |
|---|---|---|
| 0x080..0x0FF | 128-byte buffer for the job-list header lock line (GETLLAR/PUTLLC) | 0x2418, 0x25D0, 0x33EC |
| 0x100..0x17F | Kernel `tempArea`, used as the lock-line buffer for SPURS instance line 0 (EA = spurs+0x00) | 0x3598, 0x3628 |
| 0x1330 | spuNum (copy of 0x1C8) | 0x2C30 calls 0x3520 (`lqa 0x1C0; rotqbyi 8`), then 0x2C34 |
| 0x1400 | wklCurrentId (copy of 0x1DC) | 0x2C40 calls 0x3530 (`lqa 0x1D0; rotqbyi 12`), then 0x2C44 |
| 0x13F0 | Job-list header EA (r4 word1) | 0x2BF4/0x2C04 |
| 0x14E0 at entry | r4 word0 = audit EA (0 means audit off) | 0x2BFC, 0x2C38 |
| 0x14A0 / 0x14B0 | Job-descriptor line cache key (line EA) / cached header qword0 | 0x25C0/0x25C4. 0x14A0 is cleared at entry 0x2C0C |
| 0x0D00 | Cached 128-byte job-descriptor line | 0x2440, 0x25A4 |
| 0x14C0 / 0x14D0 | Barrier dependency-counter qword / EA of the barrier already passed | 0x2534-0x2580 |
| 0x1410 / 0x1420 / 0x1430 | Claimed job index / job entry / header buffer index | 0x3028-0x3030, 0x3058-0x3060 |
| 0x14F0 | Old wklReadyCount1[wid], saved by the idle exchange | 0x3048 |
| 0x1440/0x1460/0x1480 | Three 32-byte pipeline job records (load/run/store) | 0x3114, 0x33E8 |
| 0x12A0..0x1300 | loadJobState, nextLoad, load, run and store job numbers | as documented in spurs_policy.c |
| 0x1530 | Decrementer deadline for the next selectWorkload poll | 0x2D4C-0x2D88 |
| 0x1510 | 2-element MFC list `{0x80000000,0},{0,0}` (stall-and-notify, size 0) | data |
| LS 0x0 | Interrupt vector, written as `bra 0xA2C` (0x2C10/0x2C24), with a handler at 0xA34 that ends in `iret` at 0xAEC | |

Job-list header line, as used by the PM. The EA must be 128-byte aligned because it is used unmasked as the GETLLAR EA and line offsets are taken from 0. Status: **PARTIAL**; the field names are my inference.

- +0x08 (u32): current buffer index `b` (0..3). The type-4 entry rewrites it.
- +0x0C (u32): counter or generation word. Type 4 decrements it. A change invalidates the PM's job-line cache.
- +0x30 + 4*b (u32): EA of the job array for buffer b. Entries are 8 bytes; the entry EA is `array + 8*index`.
- +0x40 + 16*b (qword Q_b):
  - h0: high-water mark, set to max(h0, idx+1).
  - h1: next job index (the claim cursor).
  - h2..h7: per-SPU "minActive" job index for spuNum 0..5. 0xFFFF means idle.

---

## 1. Every MFC command site

`wait` means a blocking tag-status wait follows (WrTagUpdate = 2, ALL). `poll` means the non-blocking tag check in routine 0x2330 (WrTagUpdate = 0, which returns `stat == mask`).

| LS (Cmd write) | Cmd | EA target | Size | Tag | Followed by | Status |
|---|---|---|---|---|---|---|
| 0x16D8 | 0x20 PUT | Kernel trace buffer (0x210 counters / 0x1C0); packet built at LS r3 | 16 | r4 | none | VERIFIED. Only reachable via wrapper 0x34F8, which has no direct caller in the PM, and gated on tempArea byte 0x175 == 1 |
| 0x207C | 0x40 GET | Job input-DMA-list EA, read into an LS buffer | r3 | r13+2 | 0x2084-0x208C GETLB in the same tag | PARTIAL (pipeline tag) |
| 0x208C | 0x45 GETLB | DMA list in LS (EAL = LS addr r6), loaded into a job buffer | (list) | same | barrier orders it after the 0x207C GET | VERIFIED |
| 0x20C4 (loop) | 0x40 GET | Job input buffer EA, chunks of at most 16 KB | ≤0x4000 | r13+2 | none. Completion is polled later in 0x2E58 | VERIFIED |
| 0x2514 | 0xB4 PUTLLC | **Job-list header line** (job claim) | 128 | n/a | RdAtomicStat; retries on failure for type 1 | VERIFIED |
| 0x243C | 0xD0 GETLLAR | Job-list header line | 128 | n/a | RdAtomicStat | VERIFIED |
| 0x2558 | 0x40 GET | Barrier DependencyCounter qword (EA = job word1 & ~15) into LS 0x14C0 | 16 | 8 | wait (mask 0x100) | VERIFIED (read-only) |
| 0x25B4 | 0x40 GET | Job-descriptor line (`array + 8*idx`) & ~127, into LS 0xD00 | 128 | 8 | wait (mask 0x100) | VERIFIED (read-only) |
| 0x25FC | 0xD0 GETLLAR | DependencyCounter line (EA & ~127) | 128 | n/a | RdAtomicStat | VERIFIED |
| 0x2638 | 0xB4 PUTLLC | DependencyCounter line (u16 count −1) | 128 | n/a | retries on failure (0x2644) | VERIFIED |
| 0x2708 | 0x20 PUT | Audit ring: per-SPU audit buffer, 128-byte block | 128 | 7 | none (drained at 0x285C) | VERIFIED. Audit only |
| 0x276C | 0x40 GET | Audit header (EA = r4 word0) into LS 0xB00 | 256 | 7 | wait (mask 0x80) | VERIFIED. Only when the audit EA is non-zero (0x2744 biz) |
| 0x27FC | 0x20 PUT | Audit header slot EA + 0x40 + 16*(spuNum + hdr[0x20]) = 0xFFFFFFFF.. | 16 | 7 | none | VERIFIED. Audit only |
| 0x28A0 | 0x20 PUT | Same per-SPU audit slot (0xDE0) = entry count | 16 | 8 | wait (mask 0x100) | VERIFIED. Audit only |
| 0x28C0 | 0xC0 (MFC barrier) | n/a | n/a | r3 | none | VERIFIED but unreachable (no reference to 0x28B8) |
| 0x28E8 | 0x45 GETLB | List at LS 0x1510 (one stall-and-notify element, size 0), LSA 0 | 16 (list) | r3 ∈ {0, 3, 5} | Raises a list-stall event once all earlier DMAs in that tag are done (barrier) | VERIFIED. No guest memory touched |
| 0x2A8C (loop) | 0x20 PUT | Job output buffer EA (descriptor word1 & ~15), chunks of at most 16 KB | ≤0x4000 | r7 (5, or r13+4) | none here. Completion is polled (0x2E58) or notified (GETLB tag 5) | VERIFIED |
| 0x3128 | 0x40 GET | Job load-command list (EA = job word1, size = (word0>>16)&0x1FF) into LS 0xC00 | ≤511 | 0 (preferred word of fsmbi 0xF0) | GETLB notify on tag 0 (0x312C) | VERIFIED |
| 0x3450 | 0xD0 GETLLAR | Job-list header line (record word0 & ~127) | 128 | n/a | RdAtomicStat | VERIFIED |
| 0x3484 | 0xB4 PUTLLC | Job-list header line (this SPU's minActive slot) | 128 | n/a | retries on failure (0x3490 back to 0x343C, which re-issues GETLLAR) | VERIFIED |
| 0x35D4 | 0xD0 GETLLAR | **SPURS instance line 0** (EAH:EAL = LS 0x1C0 u64), into LS 0x100 | 128 | 0 | RdAtomicStat, dsync | VERIFIED |
| 0x3614 | 0xB4 PUTLLC | SPURS line 0: compare-and-swap of `wklReadyCount1[wid]` | 128 | 0 | retries on failure (0x361C) | VERIFIED |
| 0x3664 | 0xD0 GETLLAR | SPURS line 0, into LS 0x100 | 128 | 0 | RdAtomicStat, dsync | VERIFIED |
| 0x369C | 0xB4 PUTLLC | SPURS line 0: exchange of `wklReadyCount1[r3]` | 128 | 0 | retries on failure (0x36A4) | VERIFIED |

There is no PUTLLUC, PUTQLLUC, GETF/PUTF, mailbox or interrupt-mailbox write anywhere in the PM. Other channels used:

- SPU_WrEventMask = 2 (list-stall event) at 0x2C28; 0 at 0x2D38.
- RdEventStat/WrEventAck at 0x2364/0x236C, and RdListStallStat/WrListStallAck at 0x237C/0x239C, all inside the event routine 0x2360.
- SPU_RdDec at 0x16B0, 0x2674 and 0x2D54.

Status: VERIFIED.

---

## 2. Job acquisition (routine 0x2418; called from 0x3024 and 0x3054)

Inputs are r3 = header EA (LS 0x13F0) and r4 = spuNum (LS 0x1330).

1. 0x242C: GETLLAR the header into LS 0x80. It reads b = +0x08 and Q = LS[0xC0 + 16b], then computes `idx = Q.h1` and `entryEA = word(+0x30 + 4b) + 8*idx` (0x2450-0x24AC).
2. If header word3 differs from the cached 0x14B0, or the entry line differs from 0x14A0, it GETs the 128-byte descriptor line into 0xD00 (0x25A4-0x25C8, tag 8, waited). Otherwise it uses the cached copy.
3. It builds the new Q: `h1 = idx+1`, `h0 = max(h0, idx+1)` (0x24A4-0x24D8). The entry type is the low halfword of entry word0:
   - **0, no job**: clears 0x14A0/0x14D0 and returns with r3 halfword 0. No PUTLLC is issued (0x24F4, then 0x257C).
   - **1, job**: also sets this SPU's minActive slot, `Q.h[spuNum+2] = min(old, idx)` (0x24A8-0x24B0, 0x2504). Then it issues the PUTLLC (0x2514). On failure (stat bit 0) it goes back to GETLLAR (0x2524). On success it clears 0x14D0 and returns the entry in r3, idx in r4 and b in r5.
   - **2, general barrier** (word1 = DependencyCounter EA): GETs the counter (0x2558). If the u16 is non-zero, it returns "no job" without a PUTLLC (0x2578-0x2584). If it is zero, it PUTLLCs the h1 increment to consume the barrier.
   - **3, NOP**: PUTLLC to consume the slot.
   - **4, buffer switch**: also sets header +0x08 = word1 and +0x0C −= 1 in the same line (0x2588-0x25A0), then PUTLLC.

   For types 2, 3 and 4, 0x251C loops back to GETLLAR whether or not the PUTLLC succeeded. The routine only returns once it has a type-1 job or nothing.
4. **Uniqueness**: the claim is the h1 increment, done read-modify-write under one reservation, and a type-1 job is only returned after a successful PUTLLC. Two SPUs that read the same h1 cannot both succeed if PUTLLC fails on any intervening change to the line; the loser re-reads and takes idx+1. **VERIFIED**: each claim is unique, so there is no duplicate execution.
5. **Job availability** comes only from the entry type being non-zero. No numJobs bound is checked; the PPU must terminate the list with a zero entry or redirect it with a type-4 entry. **VERIFIED.**
6. **Exhaustion and idle protocol** (0x3018-0x3074):
   - First claim fails: it sets 0x1530 = 0, then calls `old = xchg(wklReadyCount1[wid], 0)` (0x3044, which runs 0x3628). That is a GETLLAR/PUTLLC on SPURS line 0, byte `wid`, with retry. It saves `old` in 0x14F0.
   - It claims again (0x3054).
     - Still nothing: it returns to the main loop, which drains store jobs (0x2CE0-0x2D10), waits on tag 5, ends the audit (0x2808), clears the event mask and LS[0] (0x2D38), and calls **exitToKernel** (0x3540: `lqa $2,0x1E0; bisl $0,$2`).
     - A job appeared: `cas(wklReadyCount1[wid], expect 0, set old)` (0x3074, which runs 0x3598). It only writes if the byte is still 0.

   This is the standard "advertise idle, re-check, undo" pattern that avoids a lost wakeup with several SPUs. There is no write to wklSignal, wklState or contention, but the PUTLLC writes back the entire line 0 (0x00-0x7F, which includes CURCONT at 0x20 and SIGNAL1 at 0x70). **VERIFIED.**

---

## 3. Use of spuNum

- **Job-list header**: `Q_b.h[spuNum+2]` is set at claim (0x2418: `a r54,r4,r4; chd r64,r54+4`) and recomputed at completion (0x3424-0x3474: `a r10,r10,r10; chd r21,r10+4`). The insert offset is `(2*spuNum+4) & 15`. **spuNum 6 or 7 would wrap onto h0/h1 and corrupt the claim cursor.** spuNum must be in 0..5 and **unique among concurrent runners of one list**. If two runners shared a spuNum, each would overwrite the other's minActive; the claim cursor would still be safe, but the PPU's view of the list ending or the barriers would be wrong. **VERIFIED** (index math). The effect on the PPU side is HYPOTHESIS, based on the WWS symbol names `CheckJobList`, `IsListFinished` and `CalculateJobListMarker`.
- **Audit**: per-SPU slot EA + 0x40 + 16*(spuNum + hdr+0x20) and per-SPU ring EA + 0x100 + hdr[0x30]*(…), written with plain PUTs (0x2720-0x2800, 0x2808-0x28AC). This needs unique spuNum. It is inactive because the host passes r4 word0 = 0. **VERIFIED.**
- **Job API block**: 0x1330 (spuNum) is the r3 argument passed to every job (0x3200). Jobs may index per-SPU scratch with it. That is job code, outside this audit (HYPOTHESIS).
- The PM never reads 0x1CC (dmaTagId); it uses fixed tags 0, 2-5, 7 and 8.

---

## 4. Completion signalling (0x32D4, store stage; also reached from the event routine 0x23F8)

1. For each buffer of the store job, 0x2E58 **polls** the buffer's DMA tag (0x2E7C, which runs 0x2330 non-blocking). If any tag is not complete, 0x32D4 returns 0 and is retried later (0x33E0, then 0x34E4). Nothing is published until the job's output PUTs (0x2A8C) report complete. **VERIFIED.**
2. It marks the record free and sets storeJobNum = −1 (0x3408). Then it recomputes this SPU's minActive as the min of the job indices still held in the other pipeline records for the same list/buffer, or 0xFFFF. It writes that to `Q_b.h[spuNum+2]` with GETLLAR (0x3450) and PUTLLC (0x3484), retrying on failure. **VERIFIED** (atomic).
3. For each of up to 4 DependencyCounter EAs in the record (count = word3, EAs in the second qword; 0x3498-0x34DC), it calls 0x25D0: GETLLAR the counter line, decrement the u16, PUTLLC, retry on failure. If the old value was 1, so the count reaches 0, it calls 0x3628 with r3 = byte at counter+2 (wid) and r4 = byte at counter+3. That is an atomic exchange `wklReadyCount1[wid'] = value`, which wakes the dependent workload. **VERIFIED.**

No completion path uses a plain PUT to shared counters, an event flag, a mailbox or an interrupt mailbox. Every shared update goes through lock lines. **VERIFIED.**

---

## 5. SPURS-instance atomics and kernel calls

- **0x3628** (`xchg8`): GETLLAR spurs+0 into LS 0x100 (0x3664), replace the byte at `r3 & 15`, PUTLLC (0x369C), retry. It returns the old byte. It uses only the first qword, so **wid must be below 16**. It is called from 0x3044 (idle, value 0) and 0x2650 (dependency kick). **VERIFIED.**
- **0x3598** (`cas8`): the same, but it only writes when `byte == r4` (0x35F0-0x35F4). It is called from 0x3074 (undo idle). **VERIFIED.**
- **selectWorkload**: called only at 0x3570, from 0x3558, from 0x2D48 (poll throttle: at most once per 0x3000 decrementer ticks, deadline in 0x1530), from 0x1A60. 0x1A60 is the "load next job" path of job-API entry 0x17F0, at table slot 0x1374. It is called with **r3 = 1**. The PM then compares the **returned preferred word with wklCurrentId (LS 0x1DC)** at 0x3578-0x358C:
  - Equal means keep running: 0x2D48 returns 1, and 0x1A68 branches to claim the next job.
  - Not equal means yield: `0x12C0 |= 0xFFFFFFF0` (0x1A6C-0x1A74), so no further job is pre-loaded, the pipeline drains, and the PM calls exitToKernel.

  **VERIFIED.** The host HLE (`spu_channels.c:2640-2654`) returns **r3 = 0**. That reads as "continue" only for wid 0. **For any wid ≠ 0 the PM treats every poll as "yield to workload 0".** This does not affect correctness, because no claimed job is abandoned, but it limits each pass to the jobs already claimed. HYPOTHESIS: this explains the documented "claims ONE ticket then yields" behaviour on wid ≠ 0.
- **exitToKernel**: 0x3550 only (from 0x2D44). The PM never returns through the entry r0. **VERIFIED.**

---

## 6. State that would break with several runners

- **Non-atomic read-modify-write of shared guest memory: none found.** Shared writes are all lock-line PUTLLC (header line, counter lines, SPURS line 0). Plain PUTs go only to the claimed job's own output buffers and to per-SPU audit/trace areas. Plain GETs read immutable job descriptors, load-command lists and barrier counters (read-only). **VERIFIED** for the sites in section 1.
- **Per-lane caches** are safe across runners. Other SPUs never write job entries, only the header line. The descriptor-line cache (0xD00, keyed by 0x14A0 plus header word3 in 0x14B0) is dropped whenever an empty or blocked entry is seen (0x257C) and at every entry (0x2C0C). The barrier-passed cache 0x14D0 is per lane and cleared after each claimed job. **VERIFIED.**
- **No "only runner" assumption** appears in the PM. Pipeline state (0x12A0-0x1300, 0x1270/0x1280/0x1290 masks, records) is lane-local LS. The PM exits only after the store stage drains (0x2CE0-0x2D10), so a lane never leaves claimed jobs behind. **PARTIAL:** I traced the main loop at 0x2C48-0x2D38 and the run step at 0x31A8 (bisl 0x3210, return 0x3214), but did not exhaustively prove every job-API path.
- **Whole-line write-back of SPURS line 0**: every xchg/cas rewrites bytes 0x00-0x7F from the snapshot. Any agent (PPU or host kernel) writing readyCount, CURCONT (0x20), wklFlag (0x60) or SIGNAL1 (0x70) without invalidating the reservation would have that write silently reverted. More lanes means more such windows. The host scheduler writes these under `spu_lockline_lock` plus `ef_line_end` (cellSpurs.c:1869-1885), which is consistent; other writers are unaudited. **VERIFIED** (PM side).
- **Host kernel decrements readyCount on every dispatch** (cellSpurs.c:1873). The real kernel instead compares contention with readyCount, and this PM treats readyCount as the number of SPUs requested (xchg to 0 / restore). With the idle protocol this does not create a lost wakeup: a kick after the PM's re-check leaves readyCount non-zero, and a kick before the re-check is caught by the re-check. It can under-dispatch lanes, though. HYPOTHESIS, not observed.

---

## 7. Verdict

**The protocol is designed for, and safe under, several SPUs running one job list concurrently. VERIFIED** for the claim, the minActive and dependency-counter updates, and the idle/kick handshake. All three are lock-line read-modify-writes with PUTLLC retry. The multi-SPU-specific mechanisms (per-SPU minActive slots, idle xchg/cas on readyCount) exist only to support concurrent runners.

### Host requirements

1. **PUTLLC must fail on any intervening write to the 128-byte line since this SPU's GETLLAR.** That covers other lanes' PUTLLC, PPU stores and stwcx, host-kernel and HLE writes (readyCount, CURCONT, SIGNAL1), and DMA PUTs. The current host compares the line contents under a global lock shared with PPU stores, which is sufficient for this PM: the claim cursor h1 only grows, and the byte exchange is ABA-benign. That holds only if *every* writer of the job-list header line and SPURS line 0 takes `spu_lockline_lock` (or invalidates reservations). This is not audited for the PPU job-list code (`MultiThreadSafeJobList::AddJob*`).
2. **Unique spuNum in 0..5 per concurrent runner of the same list** (lanes 0..4 are fine). Never 6 or 7.
3. **wid below 16**, because 0x3598/0x3628 only touch bytes 0x00-0x0F.
4. **Tag-completion semantics**: a tag reported complete (0x2330 poll / 0x2340 wait) means the PUT data is visible to the PPU and other SPUs before the following PUTLLC. GETLB (0x208C, 0x28E8) must honour intra-tag barrier ordering: the list must be fetched before the list transfer, and stall-and-notify must fire only after earlier same-tag DMAs. 128-byte GETs must not tear aligned 8-byte job entries.
5. **List-stall-and-notify events and interrupts per lane**: event mask 2, vector at LS 0 (`bra 0xA2C`), handler 0xA34..0xAEC with `iret`, a self-generated register-save stub at 0x3FEC0, and RdListStallStat/Ack.
6. **Independent LS per lane.** The PM re-initialises its list attachment at each entry (0x2BF0-0x2C44, clearing the 0x14A0 cache). Lane-local LS persistence is therefore not needed for correctness across lanes, only between one lane's own quanta. Persistent and fresh contexts both work if the PM is entered at 0xA00 with an empty pipeline.
7. **selectWorkload must return the selected wid in the preferred word of r3**: wklCurrentId (LS 0x1DC) for "keep running". The current HLE returns 0, which makes every wid ≠ 0 yield at each 0x17F0 poll. That costs performance, not correctness.
8. The scheduler should keep re-dispatching a workload while `wklReadyCount1[wid] != 0`. The PM itself sets it to 0 when idle and other PMs set it non-zero on dependency completion, so dispatch must follow SPU PUTLLC writes to that byte as well as PPU kicks.

### Not verified / open

- PPU-side `MultiThreadSafeJobList` writes to the header line. I did not inspect them. Requirement 1 depends on them going through PPU reservations or HLE that shares the lock-line lock. BLOCKED for this audit (out of scope, offline).
- The exact field meanings of h0, header word3 and the type values are inferred (PARTIAL).
- Runtime behaviour with 5 lanes has not been observed. Nothing here is evidence of compatibility.

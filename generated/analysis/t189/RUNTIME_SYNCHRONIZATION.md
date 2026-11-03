# T189 Workstream 3: SPU synchronization and scheduling review

**No runtime synchronization code was changed in T189.** T187 owns the MFC/lock-line fast path (`PS3_SPU_MFC_FAST`, branch `agent/t187-spu-mfc-fast`, `34954d66`). Its in-game A/B against T184 arm P is awaiting approval. Changing the same locks here would confound that experiment. This review ranks what remains after T187, with evidence.

Labels: VERIFIED (code or measurement), HYPOTHESIS, ESTIMATE.

## 1. State after T187 (VERIFIED, T187 report)

- `spu_lockline_lock()` is still one global TTAS lock by default.
- With `PS3_SPU_MFC_FAST=1`:
  - SPU single-line transactions use 16 stripes;
  - every other caller takes an exclusive lock that drains all stripes;
  - `mfc_for()` uses a per-thread engine cache.
  - Offline: 7× on uncontended lines and 27× on MFC channel writes, with 5 threads.
- Not addressed:
  - same-line spinners (one line, no stripe benefit);
  - the higher cost of exclusive acquisitions (PPU coherent stores to reserved lines, DMA PUTs to marked lines, cellSpurs).

## 2. Remaining serialization and waiting, ranked

| # | Item | Evidence | Generic fix (proposal) | Risk | Depends on |
|---|---|---|---|---|---|
| 1 | **Same-line ticket-lock spinning** (in MotorStorm, the Havok solver's ticket lock; any title's SPU spinlock) | T186 §6: GETLLAR/PUTLLC loops on one line, each iteration taking the global or stripe lock and doing a 128-byte compare | **Reservation wait instead of spin.** When an SPU's GETLLAR returns a line equal to its last snapshot and it then waits on `SPU_RdEventStat` for LR, or loops back to GETLLAR within N instructions, park it on a per-line futex/WaitOnAddress until a store notifies the line. `spu_coh_notify_write` already identifies the line | medium: must keep the LR event semantics and must never miss a wake. A bounded park timeout is the safety net | T187 striping (the notify hook) |
| 2 | **Exclusive-lock cost under T187** | T187 design: an exclusive acquire scans 16 stripes | Measure `[spu-mfc-fast] excl=/excl_spin=` in T187's A/B first. If high, add a reader/writer split so PPU coherent stores only take the stripe of their own line (they are single-line too) | medium | T187 A/B results |
| 3 | **SPU task creation** | memory: about 297 µs per `cellSpursCreateTask` on the frame thread, 5.9 ms per race frame, one host thread per task run | `PS3_SPU_TASK_POOL=1` (T183/T184 arm P) reuses threads. Remaining cost: the `CreateTask` path itself. Next: measure the split between creation and the first dispatch in arm P | low | none |
| 4 | **Repeat-DMA backoff** `Sleep(1)` after 256 identical (ea, lsa) transfers (`spu_dma.h`) | T187 tests had to vary LSA to avoid it | Make the backoff a spin-then-yield (`SwitchToThread`) with the same trigger, opt-in, and log hits. A 1 ms sleep is about 15 % of a 30 fps frame budget for any job that legitimately re-DMAs | low–medium: the guard exists for runaway loops | none |
| 5 | **Atomic polling of SPURS state by PPU wait loops** | T186: post-Havok PPU time includes guest wait loops that sleep | These are guest loops: unchangeable. The runtime can make their host syscalls (`sys_timer_usleep`, lwcond) wake on the producing event. `PS3_LWCOND_WAKE` and `PS3_USLEEP_SPIN` exist; extend to the event the loop actually polls only with evidence of which one | medium | profile |
| 6 | **`CreateTask` stdout line** (`libs/spurs/cellSpurs.c:1135`, unconditional `printf`, not gated by `PS3_SPU_TASK_QUIET`) | about 290 lines/s in a race | Gate it behind the existing quiet switch. Measured value: negligible (µs per line against 297 µs per call), so **not done**: the change would alter what T187's arm P prints for no measurable gain | none | — |

## 3. Coherence boundaries that new PPU work must respect (VERIFIED)

The T152 inline stores ported in T189 keep the reservation path exact:
- `vm_st_page[p]` is cleared for good by `spu_coh_reserve` **before** it marks a line in page `p`, and the gate fill holds the lock-line lock. Every store to a page with an SPU-reserved line therefore still goes through `vm_write*`, which takes the lock-line lock and raises LR.
- `test_vm_page_gates` (300,000 random ops, inline vs out of line, twin reservations) passes on T189.
- Interplay with T187: `PS3_SPU_MFC_FAST` changes how `spu_lockline_lock` is implemented, not who calls it. The inline-store path never takes it; the out-of-line path calls it unchanged. The two are independent switches. A combined offline test is a T190 item, because T187's code is not on this branch.

## 4. Proposed order

1. Read T187's A/B, if approved and run: excl counters, and frame-time change.
2. #1 (reservation park) as an opt-in runtime switch, with an LR-event torture test (the T187 `test_spu_mfc_fast` stress plus a parked-waiter variant) and a negative control (park disabled).
3. #4 and #3 measurements in the same in-game run as the PPU arms (`NEXT_ARCHITECTURE_STEPS.md`).

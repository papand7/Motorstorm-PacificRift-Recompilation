# T79: SPURS scheduling and PPU waits (A1′)

This was offline only. There were no launches and no builds beyond compiling two translation units. The T70D pin `2709eafd…2cec` is unchanged.

- **Inputs:**
  - A1′ run `generated/runs/20261026-172957-t70-ab-a`: `ftrace.txt`, `stderr.log`, `stdout.log`, `performance.json`.
  - Race window 145.95–196.00 s, 262 frames.
  - Retail lift in `generated/ppu`, `EBOOT.elf`.
  - Runtime source `ps3recomp-t70` at `bdf8224`.
- **New code:** worktree `ps3recomp-t79`, branch `agent/t79-spurs-sched`, commits `01d9205` (T79) and `d248709` (T79B), local only (patches `patches/0001-…`, `0002-…`).
- **T79B (five-lane safety audit, contention-5 readiness):** see §11. Verdict: ready for an authorized build and A/B; one host defect was found and fixed.
- **T79C (candidate build and pin):** see §12. The exe `5a1b49c38eb71ee8e61dd8aaa9ecfb022e60d4a64d1597fc089e37307fb51d0e` is pinned in `ab/exe-t79/`; C1/C5 can proceed once authorized.
- **T79D (C1 baseline, one session):** see §13. 5.21 fps, p50 192.0 ms, PPU wait 132.4 ms/frame, guest 5 → applied 1, 0 errors; C5 is safe to launch with the §13.5 checks.
- **T79E (C5 five-lane run, one session):** see §14. guest 5 → applied 5, peak 5 simultaneous jobs per Wws_Job workload; 8.93 fps (+71 % vs C1), p50 112.3 ms (−41.5 %), PPU wait 75.5 ms/frame (−43 %); fixed-cadence job counts per flip equal C1's; 0 errors. Each job takes ~2.1× longer than in C1 (host contention, HYPOTHESIS).

## Answer

**The runtime concentrates SPU execution because it serialises every Wws_Job workload.**

- The game asks for `maxContention = 5`, but the HLE binding of `_cellSpursWorkloadAttributeInitialize` cannot see that argument and stores 1.
  - maxContention is the ninth argument and sits on the guest stack.
  - The binding stores 1 at `cellSpurs.c:1589` ("9th arg is beyond the 8-GPR adapter").
- With one admission per workload, each Wws job list runs one job at a time.
- The coordinator always hands work to the lowest-numbered free lane, so that lane is almost always lane 0.
- **Lane-0 concentration is a symptom.** The cause is the forced contention of 1.

**This materially causes the PPU wait (VERIFIED by timing):**
- 104 of the 131 ms/frame of main-thread wait overlap one serial WWS job: `pvsjob` 54 ms, `vehiclephysics` 41 ms.
- Main wakes about 0.7 ms after the last job of each batch.
- The frame flip follows the end of `renderablejob` by 10 µs.
- The serial WWS chain is about 153 ms of each ~189 ms frame.

The earlier claim that "the game sets maxContention = 1" (T31 §1, T69) is **wrong**. It read back the value the runtime itself had stored.

## 1. Original SPURS configuration (retail code)

| Item | Value | Label | Evidence |
|---|---|---|---|
| Instance | "MotorStorm2" at `0x1003F180`, nSpus 5, spuPriority 100, exitIfNoWork 0 | VERIFIED | `func_00436680`, `ppu_recomp_001.cpp:596256-596271` → `func_00436338` (`_cellSpursAttributeInitialize`, `InitializeWithAttribute`). The game also creates "Multistream" (nSpus 1) with a taskset only. |
| Workloads | wid 0 Wws_Job "no name", 1 EvoDefault, 2 EvoHigh, 3 LibMP3 JobList; one PM (`0x00FFCC80`, 11 520 B) | VERIFIED | `stdout.log` AddWorkloadWA |
| Instance of wid 3 | MotorStorm2, not Multistream | VERIFIED | `0x4369A8` passes `[struct+0]`; all `[spurs-busy] wid=3` lines are on `0x1003F180` |
| **maxContention** | **5** for wids 0–3 | VERIFIED | The struct `{CellSpurs*, 5}` is written at `596261`. The JobHandlerWWSJOB constructor (`func_004B33E8`) gets `r5 = [struct+4]`, stores it at `[this+4]`, and reloads it as r6 for `func_00726428`. That function stores r6 at **SP+0x70** (`ppu_recomp_003.cpp:258837`, `258899`) before calling `_cellSpursWorkloadAttributeInitialize`. No call to `cellSpursSetMaxContention` is imported. See `maxcont_static.md`. |
| minContention | 1 | VERIFIED | `r10 = 1` |
| Priorities | wid 0/1: 8 on all 8 SPUs; wid 2 (EvoHigh): 7 (higher); wid 3: from table | VERIFIED | raw attr dumps |
| Affinity | none (all lanes nonzero priority) | VERIFIED | priority bytes |
| Job-queue ownership | Each Wws_Job workload owns one job list (`data` = list EA). With contention > 1 the original PM is designed to let several SPUs pull from the same list (WWS job manager). Barriers and dependencies inside the lists are **unknown**. | PARTIAL | |

## 2. Host scheduler (`libs/spurs/cellSpurs.c`)

- **Threads:** one coordinator plus one persistent worker per configured lane.
  - MotorStorm2 has 5 lanes, host tids 20188/11936/12516/17112/21204. Multistream has 1.
- **Coordinator pass** (`spurs_kernel_thread`):
  - The coordinator waits on a shared condition variable with a 1 ms timeout (~2 600 passes/s).
  - It then walks lanes **sn = 0..n-1 in order**. For each free lane it scans workloads round-robin from a global cursor.
  - It admits the first workload that meets all of these:
    - enabled and in state 2;
    - nonzero priority on that lane;
    - `active[wid] < maxContention`;
    - kicked (ready count or signal bit), or due an idle-backoff speculative run.
  - Admission consumes one ready unit under the lock-line lock and publishes `wklCurrentContention`.
- **Worker:** each worker runs `spu_run_policy_module` outside the lock. It decrements `active[wid]` only on a real PM return, then calls `WakeAllConditionVariable`.
- **What is original and what is host-introduced:**

| Behaviour | Classification |
|---|---|
| Per-workload admission limit | original semantics, but the **value is host-introduced** (1 instead of 5) |
| Lowest-free-lane placement | host choice; guest-invisible apart from LS 0x1C8 lane id. Real SPURS lets each SPU pick independently. |
| 1 ms coordinator polling and re-admission after every PM return | host (the real kernel re-selects on the SPU itself) |
| Priority 0 excludes a lane | original |

## 3. A1′ worker utilisation

**Busy ms/s by lane and workload** (51 `[spurs-busy]` windows after settle):

| lane | wid 0 | wid 1 | wid 2 | wid 3 | total |
|---|---|---|---|---|---|
| 0 | 28.6 | **518.7** | **211.4** | 0.3 | **759** |
| 1 | 1.2 | 31.8 | 19.5 | 1.1 | 54 |
| 2 | 1.2 | 1.2 | 0.3 | 0.8 | 3 |
| 3 | 2.1 | 42.3 | 17.2 | 0.0 | 62 |
| 4 | – | – | – | – | 0 |

**Job concurrency over the window** (kind 26 spans):
- No WWS job running: 19.2 %.
- Exactly one: **77.0 %**.
- Two: 3.8 %.
- wid 1 and wid 2 overlap only 2.8 % of the time.

**Interpretation (VERIFIED):**
- At most one job per workload can run.
- The game kicks the EvoDefault and EvoHigh batches mostly one after the other, so in practice one job runs at a time.
- Lane 0 is checked first and is almost always free, so it gets that job.
- The other lanes are idle because nothing is eligible for them, not because they are being starved. Low use on lanes 1–4 is correct given contention 1, and wrong only because contention should be 5.

## 4. PPU main-thread wait attribution (131.2 ms/frame)

| Wait (lr) | ms/frame | What it is | Label |
|---|---|---|---|
| `0x94CCA8` usleep | **116.7** | `func_0094CC80` (vtable method) acquires spinlock `obj+0xC` (`func_004B63F0`: lwarx/stwcx, spin 125, then `usleep`) and then `obj+8`. This is a wait-for-event: the lock is released when a job batch completes. | VERIFIED (code) |
| ↳ while one WWS job runs | **104.4** | 54.1 pvsjob, 40.6 vehiclephysics, 2.7 screenrushjob, … | VERIFIED |
| ↳ no job running | 12.4 | job-to-job gaps and wake latency | VERIFIED |
| `0xA49AD4`, `0xA48364`, `0xA48B4C` usleep | 8.3 | `cellSyncMutexTryLock` + usleep loops early in the frame | VERIFIED (code); owner unknown |
| `0xA49E3C`, `0xA48ED4` syscall 130 | 6.1 | `sys_event_queue_receive`, same module; no WWS job running | VERIFIED; cause HYPOTHESIS (Havok / hkSpuUtil SPU path) |

**Causality (VERIFIED by timing):**
- There are 3.0 long (> 5 ms) `0x94CCA8` waits per frame, totalling 112 ms/frame: 2 vehiclephysics batches and 1 pvsjob batch.
- Main wakes 0.70 ms (median; p90 1.03 ms) after the last job of the batch ends.
- That workload's next job starts 1.7 ms later.

**Not yet proven (HYPOTHESIS):**
- What releases `obj+0xC`: SPU DMA, or a PPU thread. `JobBatchHandler` (tid 12) sleeps 99 % of the time and is not the waker (median lag 155 ms).
- The dev build names `JobBatchInternal::Wait/SignalCompletion`, which fits the code but is not matched.

All of the main wait comes from blocking syscalls and usleeps (kinds 1 and 2), and each one is identified above. None is a direct MFC, mailbox or GPU wait. The renderer's own sync (D3D12) is not instrumented in this trace.

## 5. Hot-job critical path

**Per frame (A1′ interpreter):**

| Module | ms/frame |
|---|---|
| pvsjob | 54.2 |
| vehiclephysics | 42.0 |
| renderablejob | 39.6 |
| trailsupdate | 9.1 |
| screenrush | 3.6 |
| spuconstraints | 3.0 |
| octreequery | 2.9 |

- **Timing:**
  - Union of SPU busy time: 152.8 ms/frame (median); the frame median is 188.8 ms.
  - Job-to-job gaps under 2 ms: 198/frame, median 37 µs, **10.3 ms/frame** in total.
- **Chain:**
  - The main thread waits on two vehiclephysics batches (~43 ms).
  - It then waits on the pvsjob batch (~59 ms).
  - It then runs about 58 ms of its own work, while renderablejob (~42 ms) runs and gates the flip (+0.01 ms).
- **Theoretical bounds:** not measurements. They assume the job lists can be split perfectly.

| Case | WWS chain/frame | Bound on frame |
|---|---|---|
| A1′ | ~153 ms | 188.8 ms (measured) |
| AOT only (synthetic 2.6×–8.3×, T70 `bench_spu_reloc_job`) | 59–18 ms | ≥ ~95–75 ms |
| Contention 5, interpreter, perfectly parallel lists | ~31 ms + gaps | ≥ ~75–85 ms |
| Both | < 15 ms | main-thread bound: ~58 ms own work + ~15 ms other waits ≈ 70+ ms |

- **Caveat:** the parallel case holds only if pvsjob (112 jobs/frame) and vehiclephysics (31/frame) have no internal barriers. Unknown. The A1′ serial order cannot reveal this.

## 6. Verified bottlenecks

1. **Host-forced `maxContention = 1`** (game requests 5) serialises every Wws job list. VERIFIED (code, trace).
2. **The serial WWS chain is the frame's critical path:** it overlaps 104 ms/frame of main wait and gates the flip. VERIFIED.
3. **Interpreted job bodies:** about 10 ns per SPU instruction. VERIFIED (T70). Addressed by B1/AOT.
4. **Host dispatch gaps:** about 10 ms/frame between consecutive jobs, plus about 0.7 ms wake latency per batch. VERIFIED, minor.
5. Lane-0 concentration: a consequence of 1, not a separate bottleneck. VERIFIED.

## 7. Proposed fidelity-preserving corrections

| # | Change | Status | Semantics |
|---|---|---|---|
| 1 | Pass the guest's ninth argument through (`01d9205`, opt-in `PS3_SPURS_GUEST_MAXCONT=1`; default unchanged, logs `guest=… applied=…`) | implemented and tested offline; **needs a build and an authorized A/B** | restores the original value; admission rules unchanged. Risk: WWS PM multi-SPU correctness depends on atomic DMA (getllar/putllc) and lock-line fidelity, never exercised with contention > 1 in this game. |
| 2 | Re-pick on the lane when a PM run returns and its workload is still kicked (T69 #2) | proposal | the real kernel re-selects on the SPU; reduces the 10 ms/frame of gaps |
| 3 | Per-slot condition variables instead of a shared `WakeAll`, and drop the 1 ms timed poll when every lane is busy | proposal, CPU only | none |
| 4 | WWS job AOT (T70 B1) | ready | byte-identical offline; separate authorization |

**Rejected:**
- Distributing jobs beyond the requested contention.
- Changing lane placement order (guest-invisible; no gain).
- Altering ready-count or usleep semantics.

## 8. Offline tests

All tests ran on this host through `tools/run_t79_test.cmd` (vcvars + LLVM clang + T17 shim). Logs are in `logs/`.

| Test | Result |
|---|---|
| **New** `tools/test_spurs_wkl_maxcont.py`, default mode | PASS. Attr bytes identical to the 8-arg binding except +0x24 (= 1); 5 lanes → peak 1. |
| **New**, guest mode | PASS. Stores 5. 5 lanes → peak 5, lanes 0x1F. Priority 0 on lane 2 → 4 lanes, 0x1B. One-lane instance → 1. Two instances → 3 + 2 independently. Wakeups do not over-admit. BUSY finalize while admitted. LS isolation per lane. Guest stack untouched. |
| **New**, mutation check | FAIL as expected: the guest value is ignored → "ctx path stores 1" plus admission timeout. |
| `tests/test_spurs_scheduler.c` (POSIX fixture, built via private `run_posix_fixture.py` + `pthread_min.h`) | 8/8 PASS (instances, lanes, contention 2, zero priority, round-robin, reinit/shutdown, LS/TLS) |
| `test_spu_jobspan_path`, `test_spu_jobspan`, `test_spu_reloc_job` | PASS |
| Compile-only (`compile_tus_t79.cmd`, exact `build.ninja` commands redirected to `ps3recomp-t79`): `cellSpurs.c`, `ppu_sysprx.cpp` | exit 0. New lines carry only the file's existing `-Weverything` classes. |
| `test_spurs_queue_size`, `test_spurs_taskset_size`, `test_spurs_task_exit_code_initialize`, `test_lfqueue_push_recipient`, `test_spu_context_registries`, `test_spu_machine_status` | **SKIP on Windows** (POSIX-only fixtures; not run) |
| `audit_public.py --staged` | the 25 baseline BLOCK items, none new |

DMA ordering, MFC tags, events and mailboxes are untouched by the change, which only stores one attribute word. No dedicated new tests were added for them.

## 9. Remaining unknowns

- Whether the pvsjob and vehiclephysics lists contain barriers that limit parallelism at contention 5.
- Whether the WWS PM and our DMA atomics are correct with several lanes on one list (first exercise in this game).
- What releases `obj+0xC` (the class behind `0x94CC80`).
- The owner of the `cellSyncMutex` and event-queue waits (~14 ms/frame).
- Interaction with T70F's job-loss accounting: kind 26 `who` is always 0, so lanes are not distinguishable in spans.

## 10. Recommended runtime measurements (each needs separate authorization; §11.6 gives the exact plan)

1. **Rebuild with `01d9205`, then run A1″:** A1′ plus `PS3_SPURS_GUEST_MAXCONT=1`, AOT off, the same harness and gates.
   - Confirm 4× `maxContention guest=5 applied=5`.
   - Compare fps, main wait, lane busy, job concurrency and the flip-gate lag.
   - Watch correctness: Havok 5.00 steps/frame, no fatal/MISMATCH, visuals.
2. **Then the 2×2:** contention {1, 5} × AOT {off, on}. B1 is the AOT-on, contention-1 cell.
3. **Optional instrumentation:**
   - A write-watch on the `obj+0xC` lock word (existing `g_ww_lo/hi` path) to name its releaser.
   - Lane id in kind 26 `who`, which is T70F's file: coordinate first.

Analysis tools (read-only): `tools/t79_timeline.py <run> [--frames N] [--flipgate] [--causal]` (output `timeline_a1prime.txt`) and `tools/branch_xref.py`.

## 11. T79B: five-lane concurrency safety audit

This was offline only: no game build, no launch, no merge or push. The T70D pin (`2709eafd0e57c620…`) is unchanged. The T70 harness and the T70F/T75/T77/T78 files were not modified.

### 11.1 Original WWS policy module (`wws_job_pm.bin`, sha256 matches `wws_job_pm.json`)

Full report: `pm_concurrency_audit.md` (disassembly with `tools/spu_disasm.py`, cross-checked against `spu_recomp.c`).

**The PM is designed for several SPUs on one job list (VERIFIED).** Every shared update is a GETLLAR/PUTLLC read-modify-write with retry. No plain store or plain DMA PUT updates shared state.

| Function | LS | Shared state | Mechanism |
|---|---|---|---|
| Job claim | 0x2418 (GETLLAR 0x243C, PUTLLC 0x2514, retry 0x2524) | job-list header line: cursor `h1` | atomic increment, so each job is claimed once |
| Exhaustion | 0x3044 → 0x3628 (GETLLAR 0x3664, PUTLLC 0x369C) | SPURS line 0 (0x00–0x7F) | swaps `wklReadyCount1[wid]` to 0, claims again, and restores the old value only if the byte is still 0 (0x3598, PUTLLC 0x3614) |
| Per-SPU slot | spuNum 0x1C8 → 0x1330 | `Q.h[spuNum+2]` (minimum active job) | atomic, needs a unique spuNum ≤ 5 |
| Completion | 0x32D4 (tag poll 0x2E58); 0x25D0 (GETLLAR 0x25FC, PUTLLC 0x2638, retry) | dependency counters; reaching 0 sets the dependent wid's readyCount through 0x3628 | atomic |
| Job data and output | plain GET 0x25B4 / 0x2558 / 0x3128 / 0x207C; GETLB 0x208C / 0x28E8; PUT 0x2A8C | the job's own buffers only | tag-waited before completion |

Not used: wklSignal, workload state, contention, mailboxes, event flags. Audit buffers are off (r4 word 0 = 0). The LS caches are lane-local and re-validated at every entry (0x2BF0–0x2C44).

**Requirements on the host:**

| # | Requirement | Host status |
|---|---|---|
| R1 | PUTLLC fails after any write to the reserved line, from a peer, the PPU, the kernel or an HLE | VERIFIED. All atomics run under one lock-line lock. Peer PUTLLC, PUTLLUC, DMA PUT and PPU coherent stores clear peer reservations (`spu_coh_notify_write`), and the value compare is a second check. **Defect:** `cellSpursAddWorkload` stored the min/max contention bytes in line 0 without the lock; **fixed in `d248709`.** All other line-0 writers (coordinator, worker exit, `vm_write8` APIs) already lock and notify. |
| R2 | Unique spuNum ≤ 5 per concurrent runner | VERIFIED. lane = spuNum, one PM per lane, nSpus ≤ 6 |
| R3 | wid < 16 | VERIFIED |
| R4 | A completed tag means the data is visible | VERIFIED. DMA is synchronous and each context has its own MFC engine. This is stricter than hardware, so reordering cannot be observed here. |
| R5 | Independent LS per lane | VERIFIED. Contexts are keyed by (instance, wid, lane), and the PM re-initialises at every entry. |
| R6 | selectWorkload returns the selected wid | **Gap.** The HLE returns 0 (`spu_channels.c:2652`), so every wid ≠ 0 yields at each poll (PM 0x3584). This costs throughput, not correctness, and is the same in both arms. Not changed here, because it would move the A1′ baseline; it belongs in a separate later arm. |
| R7 | Dispatch treats readyCount as "SPUs wanted" | **Gap, PARTIAL.** The host consumes one unit per dispatch; hardware keeps readyCount. The game's `ReadyCountStore(wid 1, 5)` still starts 5 lanes, and re-admission continues through idle polling. No wakeup is lost; at worst fewer lanes start. |

### 11.2 Host SPURS concurrency (`cellSpurs.c`, `spurs_policy.c`, `spu_channels.c`, `spu_coherency.c`, `spu_dma.h`)

- **Correct as written for more than one runner per workload (VERIFIED by reading the code and by tests):**
  - Admission runs under the instance lock and the registry lock.
  - `active[wid]` is compared with the instance maxContention byte, together with the priority-zero lane mask.
  - Instances are isolated by EA.
  - Workers sleep on the condition variable; on exit, `active` is decremented and CURCONT is written under the lock-line lock.
  - Finalize and RemoveWorkload return BUSY while a lane is active.
  - The function and job-module registries are filled before any SPU thread exists.
  - The diagnostic counters (`g_spu_putllc_count`, the interpreter step globals) race, but they are diagnostic only.
- **Pre-existing fidelity gaps; none is a correctness defect for the A/B:**
  - Priority values are ignored; selection is round-robin.
  - `cellSpursShutdownWorkload` and `cellSpursWaitForWorkloadShutdown` are no-ops, so a later RemoveWorkload can return BUSY while lanes are active. These calls were not seen in recent runs (race window). The risk is at exit or track change and grows with 5 lanes.
  - R6 and R7 above.
- **Fixed in `d248709`:**
  - The unlocked line-0 stores (R1).
  - maxContention is now capped at `CELL_SPURS_MAX_SPU`; above 255 it used to wrap to 0, which is never admitted.
  - The ninth-argument handler reads SP+112 only from backed guest memory; otherwise it keeps 1.
- **Performance risks to measure (not correctness):**
  - One global lock-line spinlock serialises all atomics and PPU coherent stores.
  - Up to 5 more busy host threads (12 logical CPUs).
  - PM churn from R6.

### 11.3 Ninth argument (VERIFIED)

- **Call sites 0x726504 and 0x7265F8:** `std` of a zero-extended (`rldicl`) value at SP+0x70, i.e. a big-endian doubleword in the ELFv1 parameter save area.
- **Stub `func_00CC079C`:** goes straight to `ps3_hle_call(0xEFEB2679)` and leaves r1 unchanged.
- **Handler:** takes the low word of `vm_read64(SP+112)`.
- **Dispatch:** the ctx table is checked before the generic table, and only this NID was added. There are 93 static registrations against a cap of 256. No other import's binding changes.

### 11.4 Tests (all via `tools/run_t79_test.cmd`; logs in `logs/t79b_*`)

| Test | Result |
|---|---|
| `test_spurs_wkl_maxcont`, default and guest (extended) | PASS. Values 1–5 → peak 1–5 on lanes 0x1…0x1F in guest mode, always 1 in default mode. Unaligned SP (0x7008) reads SP+112. An unbacked or wrapping slot keeps 1. 0 / 9 / 256 → instance byte 1 / 8 / 8. Priority-0 lane, one-lane instance, two instances, BUSY finalize and LS isolation: as before. |
| **New** `test_spurs_wws_concurrency`, default and guest (3 of 3 runs PASS) | Five lanes claim from one job list through the real coordinator and the real MFC channel path. 900 jobs each ran exactly once. Every result was visible before its completion bit (observer, 10⁶–10⁹ checks). PUTLLC retries under peer and PPU writes: 70–586. Per-lane rows add up. The line-0 readyCount swap races the host kernel without loss. maxContention 1 and 5 leave **byte-identical** guest state. Workload switching (3 rounds × 2 workloads on one PM image) shares lanes and never crosses contexts. Two instances (5 + 2 lanes) show no cross-talk. Shutdown with every lane mid-job returns BUSY with CURCONT = 5, then loses no completion. Priority change under load: lanes 3/4 ran 56 times before and 0 times after, while lanes 0–2 kept running. |
| Mutation: PUTLLC ignores the reservation | Detected: default mode fails ("no PUTLLC failed"), guest mode never completes. A value-compare-only mutation was masked by reservation invalidation, which shows the two checks are redundant. |
| `test_spurs_scheduler` (8/8), `test_spu_jobspan` (11), `test_spu_lifter_reloc` (13) | PASS |
| Exact-flag compile of `cellSpurs.c` and `ppu_sysprx.cpp` | exit 0; only the file's existing warning classes |
| `audit_public.py --staged` | the 25 baseline items, none new |

**Limits:**
- The claim PM is manufactured. It reproduces the PM's atomic shapes (claim, completion, readyCount swap). It does not reproduce its pipeline, GETLB stall-and-notify interrupts, dependency counters or job code.
- Synchronous host DMA cannot show MFC reordering.
- The PPU-side job-list producer (`MultiThreadSafeJobList::AddJob*`) was not audited (BLOCKED).

### 11.5 Integration needed before the authorized run

1. One game build from `ps3recomp-t79` @ `d248709`, with the T70D build configuration (same CMake options, AOT linked but off, no rendering changes). This needs separate authorization.
2. `t79/ab/run_t79_ab.py prepare <exe>`: one pinned exe for both arms.
3. Nothing else. R6 (the selectWorkload return value) and R7 (readyCount semantics) stay out of this A/B and become later, separately measured changes.

### 11.6 Exact runtime A/B plan (AOT off; not performed)

- **Harness:** `t79/ab/run_t79_ab.py`, a wrapper around the unchanged T70 harness. Both arms were dry-run and nothing was launched.
- **Kept from A1′:**
  - a fresh, verified hdd0/hdd1 copy per run;
  - the T64C menu route, and no input in the race (no driving);
  - the race-entry-armed ftrace (`329D90:8EE8C:3`) and `PS3_FTRACE_SPUJOB=3214:1320`;
  - `SPURS_BUSY_MS=1000` and the 1 s RSX heartbeat;
  - the 205 s session stop, `--timeout 210` and `--stop-on-fatal`;
  - no TEX_SAVE and no RSX readback (A1′ had neither).
- **The only difference between arms:** **C1** is the arm-A environment; **C5** is C1 plus `PS3_SPURS_GUEST_MAXCONT=1`. Run names stay `t70-ab-c1/c5`, because the T70 `main` builds them.
- **Order:** C1, C5, C1, C5, C1, C5 (3 runs per arm, interleaved against host drift). An `INVALID` run (slow-start mode, race entry after 172 s) is repeated, not used. Each launch needs its own authorization.

| Quantity | Source | Gate / C5 expectation |
|---|---|---|
| Applied contention | stdout `maxContention guest=5 applied=…`, `AddWorkloadWA … maxC=` | C1: 4 × applied=1, maxC=1. C5: 4 × applied=5, maxC=5. Anything else makes the run invalid. |
| Active workers per workload | `[spurs-busy]` per lane and wid | C5: wid 1/2 busy on more than one lane |
| Simultaneous WWS jobs | `t79_timeline.py --causal` (span overlap, since kind-26 `who` is 0) | share of time with ≥ 2 jobs ≫ 3.8 % |
| Duplicate or missing completions | jobs per frame by name (`--frames`); `[pm-end]`; job-span lost count, excluding the workload-3 false spans (pending T70F) | per-frame counts by name equal C1 (± jitter); 0 `[pm-end]` |
| DMA and MFC errors | stderr `[spu-atomic] … uncommitted`, `[spu-spin]`, `[mfc`, `MISMATCH`, fatal | no new classes compared with C1 |
| PPU main-thread wait | `--causal` (usleep lr 0x94CCA8, syncmutex, event-queue receive) | report ms/frame; the 104 ms WWS-overlap share should fall |
| Frame time | `ab_report.py` frame_ms mean, p50, p95, p99 | report only; claim nothing beyond the measured runs |
| Havok steps per frame | `ab_report.py` | 5.00 ± 0.05 in both arms |
| RSX draws | `ab_report.py` race heartbeats (≥ 90 % > 200) | equal to C1 |
| Race stability | controller stop reason; no fatal or leftover process; window ≥ 20 s | all six runs |

- **Accepting C5:** it is accepted only if every gate holds in all three C5 runs.
- **Stopping:** any difference in duplicate, missing or DMA-class results stops the series for analysis.
- **AOT:** the 2×2 with AOT on comes afterwards, under its own authorization.

### 11.7 Readiness

**Contention 5 is ready for an authorized build and launch (PARTIAL, to be VERIFIED at runtime):**
- The original PM is multi-SPU by design.
- The host meets the PM's atomic, spuNum, LS and DMA requirements.
- The one correctness defect found (unlocked line-0 stores) is fixed.
- 2 new and 3 existing test suites pass.

**Remaining risks:**
- The real PM pipeline has never run on five lanes here (stall-and-notify interrupts, dependency counters).
- The PPU-side producer is unaudited.
- The shutdown APIs are no-ops, which matters outside the race window.
- R6 and R7 throughput gaps.
- Contention on the lock-line spinlock.

## 12. T79C: candidate build and pin (no launch)

### 12.1 Build

- **Source:** `ps3recomp-t79`, branch `agent/t79-spurs-sched`, HEAD `d24870981e82d75b610bed105a1d10740830aded` (`d248709` on top of `01d9205` on top of `bdf8224`). The worktree was clean before and after the build.
- **Configure:** `build/configure_t79.cmd` writes the new private directory `build/motorstorm-t79-aot`. It is the T70D recipe (`t70/tools/configure_aot.cmd`) with only `PS3RECOMP_DIR` and the build directory changed:
  - source `port-t70`, Ninja, Release, clang-cl from `build/llvm/clang+llvm-23.1.3`;
  - `MSPR_WWS_AOT=ON` (the AOT code is linked and stays off unless `PS3_SPU_WWS_AOT=1`);
  - `PORT_SPU_AVX2=OFF`;
  - `RECOMP_DIR=generated/ppu-hooked-staging`.
- **Scope:** no T75 or T77 changes are in it.
- **Build:** `build/build_t79.cmd`, full build of 312 steps, exit 0, 0 errors. Logs: `logs/t79c_configure.log`, `logs/t79c_build.log`.
- **Existing trees:** the T70D and T70G build trees and exes are untouched (`2709eafd0e57c620…`, `ae7ed7becf06f18b…`, same as their pins).
- **Compiler flags:** all 308 objects have the same rule, FLAGS, DEFINES and INCLUDES as `motorstorm-t70-aot` once tree names are normalised (`logs/t79c_flag_compare.txt`).

| | |
|---|---|
| **Executable SHA-256** | **`5a1b49c38eb71ee8e61dd8aaa9ecfb022e60d4a64d1597fc089e37307fb51d0e`** (404,268,544 bytes) |
| **Pin** | `t79/ab/exe-t79/MotorStormPacificRiftRecomp.exe` + `t79/ab/exe_pin_t79.json` (made by `run_t79_ab.py prepare`; copy hash equals source hash); `CMakeCache.build.txt` beside it |

**Linked-code checks:**
- **Ninth-argument handler:** the `maxContention guest=%u applied=%u` and `(stack slot unreadable)` strings are in the exe, and so is the `_cellSpursWorkloadAttributeInitialize` ctx registration name. `prepare` refuses an exe without them.
- **Lock-line correction:** it is in the same TU and commit as the `stack slot unreadable` string. The exe was built from the clean `d248709` tree with identical flags. This is inferred from the commit; the code itself was not disassembled.
- **Default off:** `PS3_SPURS_GUEST_MAXCONT` is read once, and only the value `1` enables it (`spurs_guest_maxcont_enabled`). Unset, the handler stores 1. The default-mode runs of both fixtures (peak 1 on 5 lanes; attribute +0x24 = 1) prove that contention 1 remains the default.

### 12.2 Offline tests on this host

| Test | Result |
|---|---|
| `test_spurs_wkl_maxcont` (both modes) | PASS |
| `test_spurs_wws_concurrency` (both modes, 3 runs) | PASS 3/3. Covers five-lane claims, completion ordering, guest-state equivalence between contention 1 and 5, switching, instances, shutdown and priority. |
| `test_spurs_scheduler` (private POSIX runner) | 8/8 PASS |
| `test_spu_jobspan` | 11 PASS |
| `test_spu_lifter_reloc` (WWS relocation) | 13 PASS |
| Flag comparison | identical (above) |
| `audit_public.py --staged` | the 25 baseline items |
| **SKIP on Windows** (POSIX-only; they do not link with the private shims) | `test_spurs_queue_size`, `test_spurs_taskset_size`, `test_spurs_task_exit_code_initialize`, `test_lfqueue_push_recipient`, `test_spu_context_registries`, `test_spu_machine_status` |

### 12.3 selectWorkload (PM disassembly 0x1A60–0x1A74, 0x2D48–0x2D94, 0x3558–0x3590)

- **Mechanism (VERIFIED):**
  - The PM polls only on its "load next job" path (0x1A60).
  - Polls are throttled to at most one per 0x3000 decrementer ticks (about 154 µs at 79.8 MHz; deadline in LS 0x1530).
  - The kernel's preferred-word result is compared with wklCurrentId (0x1DC) at 0x3584. 0x2D48 returns 1 when the result is equal (or when the poll is throttled), and 0x1A68 then claims the next job. A different result returns 0, and 0x1A6C sets 0x12C0 |= ~0xF: no further pre-load, drain, exitToKernel.
  - The HLE returns 0. So:
    - wids 1, 2 and 3 yield at the first job load at least 154 µs after the previous poll. Interpreted jobs last milliseconds, so in practice they yield after every job.
    - wid 0 never yields.
- **Effect on the job lists: none beyond timing (VERIFIED).**
  - A yield touches no shared state. The readyCount swap happens only on a failed claim, and the minimum-active slot goes to 0xFFFF only once the pipeline has drained.
  - Claims still follow the list cursor, and barriers and dependency counters still order jobs.
  - The fixture's guest-state equivalence holds independently of lane timing.
- **What does change:**
  - **Run boundaries:** one PM run per job, which loses the load/run pipeline overlap. This is consistent with the 198 gaps of about 37 µs per frame (§3); the link is a HYPOTHESIS.
  - **Ordering between workloads:** which workload runs next on a lane is decided by the host's round-robin, not by the kernel.
  - **wid 0 is sticky:** at contention 5 a busy wid 0 could hold lanes that the real kernel would hand over at a poll. In A1′ wid 0 is almost idle. Effect on game timing: HYPOTHESIS.
- **Minimum correction (proposal, not implemented):**
  - Return wklCurrentId when the current workload is still eligible on this lane: runnable, enabled, lane priority ≠ 0, active ≤ maxContention.
  - Return another wid only when the kernel's selection would pick it: the highest priority weight among kicked, eligible workloads in the same instance, with the current workload kept on ties.
  - This needs the weight rule for the priority bytes (values 7 and 8 here), which is not yet verified from a reference, plus tests: stays, yields to a higher-priority kicked workload, and priority 0 or state ≠ runnable yields.
  - Until then it would be speculative, and it would move the C1 baseline, so it stays out of C1/C5. Both arms share the same behaviour.

### 12.4 readyCount (coordinator `cellSpurs.c` ~1873; PM 0x3044/0x3628/0x3598)

The host consumes one readyCount unit per dispatch, but a kick also resets `idle[wid]` to 0. While idle is 0, every free lane in the same pass admits the workload even when it is not kicked. Unkicked workloads back off to every 2/4/8/16 passes (about 1 ms each) only after runs that never polled.

| Question | Finding | Label |
|---|---|---|
| Starve eligible workers? | No lost wakeup. Any nonzero readyCount or signal is a kick, and a polling (yielding) run keeps idle at 0, so the workload is re-admitted on the next pass. After an empty run the backoff can delay an **unkicked** list by up to about 16 ms. This matters only if the PPU adds jobs without a readyCount or signal kick, and the PPU producer is unaudited. | PARTIAL |
| Prevent all five lanes from becoming active? | No. In the same pass, the lanes after the kicked one admit through idle = 0 up to maxContention. The host **over**-admits compared with hardware (which runs at most about readyCount SPUs). The extra runs are legal for the protocol (claims are atomic) and exit through the exhaustion path. | VERIFIED (code, fixture: `ReadyCountStore(5)` → peak 5) |
| Change completion ordering? | Only the interleaving across lanes, which is nondeterministic on hardware too. Order within a list is enforced by the PM (cursor, barrier entries, dependency counters), not by readyCount. | VERIFIED (PM), fixture equivalence |
| Premature exhaustion? | No. The PM decides exhaustion from the job entries (type 0 or a blocked barrier), never from readyCount. | VERIFIED |
| Interfere with the PM's atomic reset? | No lost update. The host decrement runs under the lock-line lock and invalidates the PM's reservation, so its PUTLLC retries. The host decrements only when the count is > 0, so it cannot underflow. If the PM's swap (→ 0) and conditional restore (only if still 0) interleave with host consumption, the value is already ≤ hardware's. A PPU kick between swap and restore is kept. | VERIFIED (code; fixture line-0 swap test) |

- **Conclusion:** readyCount consumption changes how many lanes start (more than hardware, not fewer) and the re-admission latency. It does not change correctness or guest-visible job results.
- **Changes:** none (no change without a justified correction and tests).

### 12.5 Remaining runtime risks

- The real PM pipeline on five lanes (stall-and-notify GETLB interrupts, dependency counters) has not run yet.
- The PPU-side producer is unaudited (kick path, R7 latency).
- The selectWorkload yield after every job means up to 5× exit/re-entry churn on the coordinator and the lock-line spinlock.
- Over-admission compared with hardware and round-robin fairness could take lanes from the LibMP3 workload (wid 3); watch audio and `[spurs-busy]` wid 3.
- The shutdown APIs are no-ops (outside the race window).

### 12.6 Can C1/C5 proceed?

**Yes, technically ready (PARTIAL; to be verified at runtime):**
- The candidate is built, pinned (`5a1b49c3…`), and identical to T70D in flags and configuration apart from the T79 commits.
- Every applicable offline test passes.
- The selectWorkload and readyCount deviations are the same in both arms, and neither alters job results, so the A/B isolates contention.

**How to run:** follow §11.6 unchanged (`run_t79_ab.py launch C1|C5`, 205 s cap, `--timeout 210`, fresh HDD, no driving, no TEX_SAVE). Each launch needs separate authorization.

**Later work:** the selectWorkload correction (§12.3) is a later, separately authorized arm, after C1/C5.

## 13. T79D: C1 contention-1 baseline, one session

### 13.1 Run identity

- **Exe:** `ab/exe-t79/`, sha256 `5a1b49c3…1d0e` (source `d248709`).
  - Checked before launch and unchanged after.
  - The `dryrun C1` argv equals A1″'s: AOT unset, `PS3_SPURS_GUEST_MAXCONT` unset, no TEX_SAVE, no RSX_RT_READBACK, no other flags.
  - The shell had no stray `PS3_*`/`RSX_*` variables.
- **Command:** `py -3 -I generated/analysis/t79/ab/run_t79_ab.py launch C1`, one launch.
- **Directories:**
  - Fresh HDD in `ab/runtime-20261026-202537-C1`.
  - Run dir `generated/runs/20261026-202537-t70-ab-c1` (`ftrace.txt` sha256 `79026805…a8c9`).
- **Logs** (in `logs/`):
  - `t79d_c1_launch.log`;
  - `t79d_c1_report.txt` (`ab_report.py`, unchanged);
  - `t79d_c1_identity.txt` (`t70f/identity.py`);
  - `t79d_c1_overlap.txt` and `t79d_a1pp_overlap.txt` (new read-only `tools/t79_overlap.py`).
- **Session end:**
  - The controller stopped the session on "ftrace written" at 197.9 s, under the 205 s cap.
  - The hard deadline did not fire and no process was left over.
  - The reported `exited_error (exit code 1)` is the controller's taskkill, as in A1′ and A1″.

### 13.2 Measurements (VERIFIED unless marked)

| # | Metric | C1 (`5a1b49c3`, T70D tracer) | A1″ (`ae7ed7be`, T70G tracer) |
|---|---|---|---|
| 1 | Race entry (`329D90` from `8EE8C`, once, after LoadRace) | **140.81 s**; window 143.8–196.0 s (52.2 s), 249 530 spans, 0 dropped | 144.43 s; 48.6 s |
| 2 | Frames / fps | **271 / 5.21** (heartbeat 5.19) | 244 / 5.04 |
| 2 | Frame ms mean / p50 / p95 / p99 | **191.9 / 192.0 / 202.1 / 208.8** | 198.5 / 197.6 / 209.3 / 227.3 |
| 3 | PPU main wait | **132.4 ms/frame** | 135.4 |
| 4 | SPU lanes sn0–3 (host cores) | **0.76 / 0.07 / 0.02 / 0.07** | 0.77 / 0.08 / 0.02 / 0.08 |
| 4 | SPURS `1003F180` busy, wid 0/1/2/3 | **3.3 / 57.8 / 26.2 / 0.2 %** | 3.4 / 59.6 / 25.4 / 0.2 % |
| 5 | maxContention, guest requested / applied | **5 / 1** on 3 Wws_Job workloads; **1 / 1** on the fourth (stdout `[cellSpurs] … maxContention guest=… applied=…`) | 1 applied (no T79 code) |
| 6 | Peak simultaneous workers per wid (job spans) | **1 / 1 / 1** for wid 0/1/2; across workloads ≤ 2 lanes, 4.1 % of the time | 1 / 1 / 1; ≤ 2, 4.3 % |
| 7 | WWS job completions (manifest ids) | **52 007**; per wid 94 / 769 / 217 jobs/s | 50 695; 91 / 743 / 210 jobs/s |
| 8 | Scheduler stalls / DMA errors | **0 / 0** (16 `[mfc-list] STALL` + 16 `[spu-int] TAKEN`, the PM's list-stall path; A1″ had the same lines); fc-watchdog never reported; 0 NOSYS | same |
| 9 | Havok | **5.02 steps/frame** (26.1/s) | 5.00 |
| 10 | RSX draws per frame | **45/45 window heartbeats > 200**; 263–267 draws, mean 265 | 44/44 > 200 |
| 11 | Fatal / assert / abort / MISMATCH | **0 / 0 / 0 / 0**; 0 `[spu-reloc]`, 0 AOT records | 0 |
| – | Coordinator passes | 2 610/s | 2 588/s |

- **Item 6 method:** the span lane field is `ctx->spu_id`, which is 0 on every SPURS lane. `spu_jobspan` keeps one open span per host thread, so the overlap tool counts how many spans are open at once.
  - Only the `job` class counts as workers.
  - The PM-class pseudo-spans reach 2 in wid 2, but they are not jobs.
- **Per-module runs:** the per-module table in `t79d_c1_report.txt` matches A1″ module for module, and the per-frame cadence is the same:
  - trailsupdate, groundrushjob, groundrushvisibilityjob, generatefogtable: 272 each, one per flip;
  - spuxform: 544, two per flip;
  - pvsjob: 30 464, 112.0 per flip;
  - vehiclephysics: 8 695, 32.0 per flip;
  - renderablejob: 5 676, 20.9 per flip (A1″: 20.9).
  - This is a count check, not a per-instance identity check (PARTIAL evidence of no duplicate or missing jobs).

### 13.3 Tracer limitation (as briefed)

- This exe has the T70D opener, not T70G's, so the job-span numbers show the A1′ pattern:
  - 52 007 PM-id `C40F75E2` LOST spans (reason 2) at LS 0x2C90;
  - 4 352 PM-attributed completions;
  - 917 unrecorded returns.
- Qualified LOST is 0 %.
- **Gate FAIL:** "returns attributed ≤ 1 %" fails at 9.2 % (A1′: 9.29 %). This is the known tracer defect, not a runtime fault.
  - Every other `ab_report.py` gate PASSes.
  - `VALID False` comes from that one gate only.
- **Not job counts:** none of the PM-class figures above (LOST, PM completions, unattributed) is a WWS job count.
- **wid 0 timing:** its PM-attributed completions are mislabelled `spuconstraints` runs in the per-module table, so wid 0 per-module timing is unreliable. The identity coverage is otherwise 14 manifest ids, the same set as A1″.

### 13.4 Differences from the historical baseline (not a controlled A/B: different exe and tracer)

- **Faster:** C1 is about 3 % faster than A1″ (5.21 vs 5.04 fps, p50 192.0 vs 197.6 ms) and about 1 % slower than A1′ (5.26).
  - This is within the spread across sessions so far.
  - At contention 1, the T79 code adds only the handler and the lock-line change. HYPOTHESIS: neither costs measurable time.
- **Earlier race entry:** 140.8 s vs 144.4 s, and the window is 3.6 s longer.
- **Unchanged:** workload shares, lane concentration on sn0, jobs/s and Havok cadence are all unchanged within about 4 %.
- **Contention-1 default confirmed at runtime:** the game requests 5 and gets 1 when the knob is unset.

### 13.5 Is C5 safe to launch?

**Yes (PARTIAL).** C1 is a usable same-exe baseline for C5:
- 0 errors;
- every gate that is independent of the tracer passes;
- contention 1 is verified at runtime;
- the per-frame job cadence matches A1″.

Required C5 checks, using the same pin and harness:
- **Contention:** stdout must show `guest=5 applied=5` on the three Wws_Job workloads.
- **Duplicate or missing jobs (independent of the tracer):**
  - per-flip run counts of the fixed-cadence modules must equal C1's: trailsupdate, groundrush ×2 and generatefogtable 1/flip, spuxform 2, pvsjob 112, vehiclephysics 32;
  - the set of 14 manifest ids must be the same;
  - Havok must stay at 5.00 ± 0.05 steps/frame;
  - draws must stay > 200 per heartbeat;
  - 0 fatal, assert or MISMATCH lines.
- **Workers:** `t79_overlap.py`, job class, must show more than 1 simultaneous worker per wid (that proves contention 5 took effect).
- **Audio and stalls:**
  - wid 3 busy and audio continuity must hold (LibMP3);
  - no new `[mfc-list] STALL` lines beyond 16;
  - no fc-watchdog reports.
- **Interpretation:** compare C5 only with C1. The PM-class figures stay uninterpretable on this exe.

C5 needs its own authorization. No C5 was launched.

## 14. T79E: C5 five-lane run, one session

### 14.1 Run identity

- **Exe:** `ab/exe-t79/`, sha256 `5a1b49c3…1d0e` (source `d248709`), checked before launch and unchanged after.
- **Command:** `py -3 -I generated/analysis/t79/ab/run_t79_ab.py launch C5`, one launch. The `dryrun C5` argv (`logs/t79e_c5_dryrun.log`) is C1's plus `PS3_SPURS_GUEST_MAXCONT=1` only: AOT unset, no TEX_SAVE, no RSX_RT_READBACK, same controller and trace configuration; no stray `PS3_*`/`RSX_*` variables in the shell.
- **Directories:** fresh HDD `ab/runtime-20261026-203524-C5`; run `generated/runs/20261026-203525-t70-ab-c5` (`ftrace.txt` sha256 `47689c16…72b2`).
- **Session end:** controller stop on "ftrace written", under the 205 s cap; no hard-deadline kill, no leftover process (`exited_error` is the controller's taskkill, as in C1).
- **Logs** (`logs/`): `t79e_c5_launch.log`, `t79e_c5_report.txt` (`ab_report.py`, unchanged), `t79e_c5_identity.txt` (`t70f/identity.py`), `t79e_c5_overlap.txt` (`tools/t79_overlap.py`), `t79e_compare.txt` (new read-only `tools/t79e_compare.py`, C1 vs C5).

### 14.2 Correctness (VERIFIED unless marked)

| # | Check | C5 | C1 |
|---|---|---|---|
| 1 | maxContention (stdout) | **guest=5 applied=5** on the three Wws_Job workloads (`0x0FEFF378` ×2, `0x0FEFF858`); LibMP3 guest=1 applied=1 | guest=5 applied=1 |
| 2 | Peak simultaneous job-class spans (`t79_overlap.py`) | **5 / 5 / 5** for wid 0/1/2; wid 1 has 5 jobs open 31.7 % of the window; any wid, 5 lanes busy 51.9 % | 1 / 1 / 1 |
| 3 | Job identities | the same **14 manifest modules** (kind-28 module ids); no new or unknown ids | 14 |
| 4 | Runs per flip, fixed-cadence modules | trailsupdate, groundrush ×2, generatefogtable 1.00; spuxform 2.01; spuconstraints 16.04; pvsjob 112.31; vehiclephysics 32.04; occjob 4.01; screenrushjob 3.01; octreequery 8.02 | 1.00; 2.01; 16.06; 112.41; 32.08; 4.01; 3.01; 8.03 |
| 4 | Runs per flip, scene-dependent modules | renderablejob 20.73, ProcessEmitters 2.39, BasicParticleFiller 2.78 | 20.94, 2.66, 2.73 |
| 5 | Duplicate or missing jobs | **none detected (PARTIAL)**: fixed-cadence counts agree within 0.1 %; the three scene-dependent modules differ by −10 to +2 %, consistent with a different race segment (window 155–196 s vs 143.8–196 s). A per-instance identity check is impossible on this tracer. | – |
| 6 | Havok | **5.01 steps/frame** (44.7/s) | 5.02 |
| 7 | RSX draws | **39/39** window heartbeats > 200 | 45/45 |
| 8 | DMA atomics, stalls, deadlocks | 0 DMA-error, NOSYS or deadlock lines; `[mfc-list] STALL` 16 and `[spu-int] TAKEN` 16 (= C1, the PM list-stall path); fc-watchdog prints only its start line; the race ran to the trace end at a steady 112 ms/frame (p99 118 ms) | same |
| 9 | Fatal / assert / abort / MISMATCH | **0 / 0 / 0 / 0** | 0 |
| 10 | Audio (wid 3, LibMP3, maxContention 1) | runs in **every** SPURS_BUSY second (193/193, min 70/s); race rate ~95/s vs C1 ~165/s. That is a poll rate, not decoded audio; HYPOTHESIS: fewer idle coordinator passes reach it. No cellAudio errors (C1 had 4 `GetBuffer`/`GetCurrentPadding` pacing failures). | 193/193, min 64/s |

**Gates (`ab_report.py`, unchanged):** every gate passes except "WWS job returns attributed ≤ 1 %", the known T70D-tracer gate that C1 also fails. `VALID False` comes from that single gate, as in C1. It is 22.3 % here (C1 9.2 %): unrecorded returns rose 917 → 16 480; PM-class completions 4 030.

**Instrumentation limitation (as briefed):**
- The PM pseudo-starts (LOST 71 652 vs 71 647 job completions, the same 1:1 pattern as C1) and the unrecorded returns are tracer artifacts, not missing jobs. Why unrecorded returns grow with five lanes is a HYPOTHESIS (old opener with concurrent lanes).
- Job counts above come from kind-28 module records, which include the PM-attributed spuconstraints runs (C1: 4 352, all PM-labelled; C5: 1 826 job + 4 030 PM = 5 856 = 16.04/flip).
- Correctness therefore rests on per-flip count equivalence, not on per-job identity: **PARTIAL**.

### 14.3 Performance, C1 → C5 (same exe; VERIFIED)

| Metric | C1 | C5 | Change |
|---|---|---|---|
| Race entry / window | 140.81 s / 52.2 s | 152.02 s / 41.0 s | +11.2 s (below the 172 s gate) |
| Frames | 271 | 365 | |
| Race fps | 5.21 | **8.93** | +3.72 (+71.4 %) |
| Frame ms mean / p50 / p95 / p99 | 191.9 / 192.0 / 202.1 / 208.8 | **112.1 / 112.3 / 116.1 / 118.2** | −41.6 / −41.5 / −42.6 / −43.4 % |
| PPU main wait ms/frame | 132.4 | **75.5** | −56.9 (−43.0 %) |
| SPU lanes sn0… (host cores) | 0.76 / 0.07 / 0.02 / 0.07 (Σ 0.92) | 0.63 / 0.61 / 0.63 / 0.62 / 0.62 (Σ 3.11) | ×3.4 |
| SPURS busy wid 0/1/2/3 (lanes) | 0.033 / 0.578 / 0.262 / 0.002 | 0.107 / 2.105 / 0.846 / 0.001 | |
| WWS wall time (union of open spans) ms/frame | 156.1 | **77.5** | −50.4 % |
| WWS lane time (Σ job durations) ms/frame | 162.7 | 336.5 | +106.8 % |
| Per-module median duration, C5/C1 | – | 1.57–2.69× (pvsjob 2.20, vehiclephysics 1.82, renderablejob 2.12) | each job slower |
| Interpreter ns/insn (pvsjob) | 9.14 | 22.56 | ×2.5; instructions per run unchanged (51.1 k vs 50.3 k) |
| Any-wid union idle gaps: n / median / p95 µs | 97 179 / 0.4 / 46.3 | 2 902 / 1 183 / 25 290 | |
| wid 1 union idle gaps: n / median µs | 40 123 / 37.5 (≈ per-job dispatch gap) | 1 186 / 25 122 (between bursts) | |
| Coordinator passes/s | 2 610 | 4 065 | +56 % |

- **Dispatch gaps:** span field 1 is 0 on every lane, so per-lane gaps cannot be measured on this trace; union-of-spans gaps stand in. In C1 wid 1 runs back to back with ~38 µs gaps; in C5 its jobs overlap, so the union idles only between frame bursts.
- **Scaling:** five lanes halve WWS wall time per frame, not ÷5, because each job takes ~2.1× longer. Lane CPU rises ×3.4 for a 1.71× frame rate. Cause of the per-instruction slowdown on this 12-logical-CPU host is a **HYPOTHESIS**: SMT sharing or memory bandwidth among five interpreter threads plus the PPU and RSX threads, or shared interpreter/tracer state (the job-span tracer writes on every job step). Not measured.

### 14.4 Remaining scheduling defects

1. **Per-job slowdown under concurrency** (median 1.6–2.7×, ns/insn ×2.5): the dominant loss; cause unmeasured.
2. **PPU still waits 75.5 of 112 ms per frame (67 %).** WWS union busy (77.5 ms/frame) is still on the critical path; wid 1 (pvsjob, renderablejob) is 58.5 ms/frame of it.
3. **Tracer:** the T79 exe carries the T70D opener, so the attribution gate fails (22 %) and per-lane gaps are unmeasurable; a clean VALID needs the T70G tracer.
4. **Slower load to race** (+11 s; intro opened at 35 s vs 24 s). One sample; may be variance.
5. One C1/C5 pair; run-to-run variance unmeasured.

### 14.5 Recommendation: SPURS concurrency with AOT

- C5 (+71 %, interpreted) and B1 (+125 %, AOT at contention 1, different exe) shorten the same WWS critical path in different ways: AOT makes jobs ~4× shorter, contention 5 overlaps them. The gains will not multiply. B1's WWS time is 50 ms/frame on one lane, so five lanes can remove at most ~40 ms more, and the per-job contention penalty may eat part of that.
- Next steps (each needs authorization):
  1. Offline microbench of per-instruction cost with 1 vs 5 interpreter and AOT threads, tracer on and off, to locate defect 1.
  2. Rebase the two T79 commits (`01d9205`, `d248709`) onto the T70G tree (`88feeb5`, corrected opener) and build one exe.
  3. Same-exe runs on it: D1 (AOT, contention 1) and D5 (AOT, contention 5), with the unchanged gates.
- Keep contention 1 as the default until D5 passes those gates on the corrected tracer.

No further launches, builds, merges or pushes were made after C5.

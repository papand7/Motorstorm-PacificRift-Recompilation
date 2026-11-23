# NATIVE_SPU_INTERACTION: does Fix 2 explain why the earlier natives did not move the race? (Task 4)

Private, offline.

## 1. Which jobs the interpreter fallback touched (VERIFIED, `[wws-stats]` Kksr48/52 vs 50/54; R1 AOT profile)

| native (spunat2/spunat3/spuopt) | function-level speedup | job's interpreted steps/job, Fix 2 off → on | does Fix 2 change the native's reach? |
|---|---|---|---|
| groundrush 0x40D8, groundrushsquashjob 1296695313 | 4.5–4.6x (gen/hand, `spunat2/logs/results.json`) | 0 → 0 | **No.** The job was never interpreted (720–771 µs/job, 11 jobs/frame, 7.9–8.5 SPU-ms/frame in all arms) |
| vehiclephysics 0x7370 / 0x5B00 / 0x7200, 1296695298 | 2.70x / 1.79x / 1.80x (`spunat3/logs/gates_final.txt`) | 0 → 0 | **No** (185–231 µs/job in all arms) |
| Havok HK2 collide 491898574 | ~1.44x replayed compute; 1.05–1.13x whole task (criticalpath60) | no AOT misses at all (R1) | **No** |
| renderablejob 0x6870 / 0x8140 (0x12E40 is the job entry), 1296695296 | 1.66x / 1.93x (64 FNREC snapshots each) | 79k → 30 | **Yes.** Before Fix 2, ~62–64 % of renderable time was interpretation: 1299 → 536 µs/job. A native hooks the head of a lifted function, which an interpreted stretch never calls. So any call made after the 0xDFA0 miss reached no native. Fix 2 puts every call back on lifted code |

**The interpreter does not explain the missing race gain for groundrush, vehiclephysics or Havok.** Their jobs had zero interpreted instructions before and after Fix 2. The criticalpath60 explanations stand:
- vehiclephysics natives act on ≤ ~0.9 ms of SPU execution per blocking batch, behind ~0.7 ms of JobBatchHandler hop latency;
- HK2's in-race run is 6.5x its replay (3.26 ms on-CPU vs 0.42–0.50 ms), so replayed compute is a minority;
- groundrushsquash has no measured place on the main thread's path (BLOCKED, see below).

## 2. Is a native now more valuable with Fix 2?

Only the renderable natives can be, and their size is BLOCKED:
- Per call, the snapshots give 141 → 85 ns (0x6870) and 493 → 256 ns (0x8140) (`spunat3/logs/gates_final.txt`).
- The saving per job = calls per job × 56 ns (0x6870) or 237 ns (0x8140).
- Calls per job are not recorded anywhere. The FNREC files sample every 499th call, but D:'s 2 s mtime resolution makes their timestamps unusable for rates (checked).
- Because renderable is now ~536–572 µs/job of lifted code, even a 2x native would have to cover > ~10 % of the job to save > 1 SPU-ms/frame (MODELLED bound). That is the share needed before it could plausibly matter.
- **Evidence needed:** a per-function call count or sample for renderable functions in a Fix-2-on race, or an offline whole-job replay. Neither harness exists. FNREC snapshots are function-level, and `fnx` refuses channel ops, so a job-entry snapshot (0x12E40) cannot be replayed through the DMA.

## 3. Same-state comparisons asked for in the brief, and the limits of the recordings

- **Whole-job, interpreter and native time with Fix 2 on vs off:**
  - Whole-job time is available from race `[wws-stats]` (table above).
  - Interpreter time is available from R1 only (Fix 2 off).
  - Native function time comes from snapshot replays, which do not depend on Fix 2: a snapshot enters a lifted function directly, with no reloc slot, so the switch is inert. VERIFIED by code: the probe returns 0 with no resident slot.
- **Transition counts:** R1 only. A Fix 2 on profile is BLOCKED (race needed).
- **DMA, channel and synchronisation overhead per job:** not recorded for Wws jobs. `PS3_SPU_TASK_STATS` covers SPURS tasks (Havok) only.
- **Total job completion latency on the critical path:** the only critical-path trace (Kksr36 PT plus ftrace) predates Fix 2 and covers the race intro.

**Do not combine the function-level speedups into a race gain.** The race model does not give FPS (see REJOIN_OPPORTUNITIES).

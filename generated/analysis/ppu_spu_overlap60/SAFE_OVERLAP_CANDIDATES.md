# SAFE_OVERLAP_CANDIDATES
Result: no candidate established. Status BLOCKED.

- Only 5.92 ms/frame of compute is SPU-idle, and 3.30 ms of waiting is SPU-idle (hand-off latency). Moving work across a wait needs proof it is independent of SPU-written memory and guest-visible ordering.
- No read/write-set data exists for main-loop functions (t132b call graph has structure and timing only).
- Instrumentation needed:
  1. per-function guest read/write address sets per frame (page granular first), from the existing fast-mem store path and a load hook in a profiling build;
  2. per-kick SPU job DMA input/output ranges (MFC log);
  3. an offline tool: candidate = PPU code between wait N and kick N+1 (or after a kick) whose write set is disjoint from the job's read/write set and whose read set is disjoint from the job's writes, plus no shared atomics/semaphores.
- Not implemented: any reordering or earlier submission (restriction 8).

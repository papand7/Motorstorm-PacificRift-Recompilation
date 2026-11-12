# PPU translation rework: scope (2026-11-11)

Goal: a large, general speed-up of lifted PPU code (MotorStorm 1.03 now, other ps3recomp titles later),
not another few-percent tweak. Framework work in `ps3recomp-vkgame` (lifter + runtime headers), with
focused tests, per AGENTS.md.

## Baseline (VERIFIED unless marked)

- The race frame is set by the guest main thread: 35-37 ms a frame on 1.03 (Kk269/Kk270 timeline),
  100 % busy; the RSX draw thread (about 24 ms) and SPU threads run beside it.
- Main-thread self time, Kk267: `vm_write32` 7.5 %, `vm_write64` 6.4 %, trace hooks about 5-7 % while a
  trace file is set, indirect-call dispatch 2.5 %, VMX helpers about 4 %; the rest is spread over
  thousands of lifted functions (no single hot spot).
- Already tried, no gain: register promotion (`--promote-regs`, T189 0.96-1.03x), `-march=x86-64-v3`
  (0.96-0.98x), inline guest stores (Kk31, Kk271), hot-code link order (+1.4 %). PGO: about -12 %
  main-thread cycles (PARTIAL, 1.02).
- HYPOTHESIS: since inlining stores removed the call but not the time, the cost is in what the code does
  (memory latency, CR/flag bookkeeping, branch mispredicts, indirect dispatch), not in call overhead.
  Not measured yet.

## Phase 0: measure where the cycles go (no code change to the game)

1. Hardware counters on the main thread over a race (WPR/xperf PMU sampling; needs an elevated
   prompt once): IPC, L1/L2/L3 misses, branch mispredicts, per hot lifted function.
2. A per-construct census of the lifted 1.03 code: share of instructions that are guest loads/stores,
   CR updates (`ctx->cr` read-modify-write per compare), `ctx->gpr` spills around calls, indirect calls,
   `DRAIN_TRAMPOLINE` after each call, FP/VMX helpers.
3. The T189 bench (real lifted functions + real runtime) as the A/B harness for every prototype below,
   plus in-game `[main-cyc]` Mcycles/flip.

Decision rule: a direction goes to Phase 1 only if Phase 0 shows its construct costs >= 10 % of the
main thread.

## Candidate directions (each a prototype on the T189 bench first)

| Direction | Idea | Expected if Phase 0 points there |
|---|---|---|
| A. Flag elimination | Compute CR fields only where a later branch/mfcr reads them (dead-flag analysis per function), instead of a read-modify-write of `ctx->cr` per compare | high if CR bookkeeping is large |
| B. Context out of memory | Keep `ctx` fields in SSA values across a whole function and spill only at calls/exits, with no aliasing between `ctx` and guest memory (separate address spaces) | high if loads/stores of `ctx` dominate; register promotion alone did not do this |
| C. Fast memory | Guest RAM reserved as one host range; loads/stores as one `bswap` + access, no gate; MMIO/coherence pages handled by guard pages + an exception handler; write tracking (textures, SPU lines) by page protection | medium; inline stores showed the call is not the cost |
| D. Direct calls | Resolve indirect calls through vtables/OPDs to direct calls with a guard, and drop the per-call trampoline check where the callee cannot yield | medium |
| E. LLVM IR backend | Emit LLVM IR instead of C, with TBAA/`noalias` so guest memory, `ctx` and stack never alias; enables A, B and D cleanly | the long-term vehicle for A/B/D; weeks |
| F. Build | ThinLTO across lifted chunks; trace-free lift for play builds | 5-10 % (UNTESTED) |

## Order of work

1. Phase 0 (counters + census), about 1-2 days.
2. The construct Phase 0 ranks first, as a lifter option (default off) with lifter tests and a T189 A/B.
3. If two or more directions qualify, move the lifter to E so they share one backend.
4. Every step is checked in game: same race result (lap time, positions) as the serial reference build,
   and `[main-cyc]` against the baseline exe.

## Not in scope

- Changing game behaviour or timing (no frame interpolation, no skipped game work).
- SPU translation (separate lifter; SPU threads are not the frame limit).

## 2026-11-12: restrict ctx, and where the frame goes now

- `ppu_context* __restrict ctx` on every lifted function (T189 bench, `t189/tools/real_restrict.py`, TU 003 seed 1,
  21 real functions, differential check passed): 0.992x, and the same code: 25764 vs 25766 x64 instructions,
  4082 vs 4083 ctx accesses. VERIFIED: guest-memory aliasing is not what keeps registers in memory (as register
  promotion, T189, found no gain either).
- Census of the 1.03 lifted tree (static): 25.2 M statements; CR writes 10.4 %, CR reads 8.2 %, 1.54 ctx->gpr
  references per statement, 6.7 M guest loads, 2.2 M stores.
- Kk2948 profile (all opt-ins): the main thread runs 31 % of the time and waits the rest (usleep polls of SPU work,
  event waits); Kk2949 (`PS3_USLEEP_SPIN=2` with MAIN_ONLY) 17 % -> 12 % late steps; Kk2950 (`--chain-chunks` for
  SPU images cbf1/0e1933) 12 % -> 9.9 %, SPU-thread busy samples -31 %. The frame is now set by SPU work, not PPU.

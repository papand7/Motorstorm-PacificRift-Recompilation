# PPU_DEPENDENCIES: visibility and Havok waits, reordering, PPU codegen (Tasks 3, 4, 6)

Private, offline. Labels VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## 1. Task 3: the "visibility semaphore 0xA4C590" is two different waits

**0xA4C590 is not visibility (VERIFIED).** It is an event-queue-backed semaphore wait (syscall 130). Static callers (`t132b/tools/up.py A4C590`):
- Havok job queue: 0xA48A18 (lr 0xA48E10/0xA48ED0) and 0xA499F8 (lr 0xA49E38) under `hkpMultiThreadedSimulation::stepDeltaTime` (0xB943E8/0xB95B10);
- 0x187118 (lr 0x18715C/0x187180), called from 0x174880/0x174970 in `World::Update`;
- 0x309428 (lr 0x3094E8/0x30950C), called by ms2Physics slot 0x24;
- 0x30B710 (lr 0x30B85C), the Havok step itself.

Who releases it: no `A4C7B8` post on the waited objects (e.g. 0x12F17F30) appears in the PT log. The waits end while Havok SPU tasks are still running (decomp: last SPU item end -> wait exit 0.01 ms/frame), so the semaphore is released by the Havok SPU tasks' events. **PARTIAL:** the event path itself (SPU event port -> queue) was not traced. It is 3.44 ms/frame uninstrumented (m2) and ~2.6 ms/frame by sc-wait in Kksr43.

What must finish first: the Havok job that the main thread (also a Havok worker) depends on, inside the HK1 -> HK2 -> HKd waves. Dependency: it is the physics step itself, input to vehicle physics, camera, visibility and render. A faster producer helps only through the HK2/HK1 task time (SPU_JOB_ANALYSIS section 2); the main thread already does its own Havok jobs while it waits. Recoverable share: ≤ the HK2 wave reduction. Not "all 3.5 ms".

**The real visibility wait is `Vis::Wait` 0x45CAA8 -> `PVSComputerImpl::WaitForCompletion` 0x5F74B0**, reached from `RenderableProxy` vslot 0xC 0x482680 (6 calls per invocation). The wait goes through `JobBatchInternal::Wait` (lr 0x5F7588, 96 calls/frame): 3.23 ms/frame uninstrumented (m2 inclusive). VERIFIED.
- Producer: PVS Wws jobs kicked by `KickVisibility` 0x331240 (step 17, after World::Update). In the intro trace that is job 602e92cb, 112 jobs, 11.2 SPU-ms, span 17.9-20.9 ms. The identity comes from timing only: PARTIAL.
- Release: `SetCondition(true)` by the JobBatchHandler (tid 12) after the batch's last job: up to one ~0.56 ms poll later. VERIFIED for all JobBatch gates.
- Does the producer compute or wait? It computes: jobs run 3.7 lanes wide on average and the kick -> first job is ~20 us. But its submission and completion each pass through the ~0.56 ms handler poll (PARTIAL for submission).
- Indirect dependencies: the PVS input is the camera, which follows the vehicles. So visibility depends on Havok and vehicle physics through World::Update ordering. HYPOTHESIS (strong): t84/t132b show the camera matrices are copied at kick time.
- Overlap already present: between the kick (17.9) and the first wait (20.1) the main thread runs ~2.2 ms (instrumented) of audio, online, particles and view setup. Uninstrumented that gap is shorter, which is why the wait grows to 3.2 ms.
- Shortening it:
  - (a) faster PVS jobs: not measured; 100 us/job, AOT, 0 interpreted steps;
  - (b) handler latency on submission and completion: C1, ~0.2-0.35 ms of this wait, MODELLED;
  - (c) moving more independent PPU work into the gap: not proven safe (section 2).
  - Not all 3.2 ms is recoverable: the ~3 ms SPU span is the dependency.

## 2. Task 4: can main-thread PPU work run while SPU jobs run?

**Answer: not with current evidence (BLOCKED for any concrete exact candidate).**

What is known:
- The main thread does ~9.2 ms of guest compute spread over ~420 functions. The largest exclusive function outside the spin is `func_00BFFCA8` at 0.53 ms (m2). The top 60 exclusive functions cover ~3.9 ms. VERIFIED.
- Frame order is strictly sequential on one thread (t132b). The sim tick (World::Update) must precede the visibility kick and the render. VERIFIED.
- Blocks that look independent and sit next to waits, all small: audio 0x7C9F70 0.40 ms, GUI 0x810D8 0.14 ms, particles begin/end, online pumps. Sum ≤ ~1 ms. HYPOTHESIS: independent.
- Reordering them changes the order of guest memory writes relative to SPU DMA reads/writes, allocator state (per-frame linear allocator 0x457B88), lwmutex ownership and HLE calls (audio talks to libaudio/SPURS). Exactness would need read/write sets.

Practical approach for an exact, trace-based dependency analysis (HYPOTHESIS: feasible; nothing was built):
1. **Per-region memory sets.** The runtime already has `ppu_trace_mem` kinds PPU_READ / PPU_WRITE / ATOMIC / HLE_WRITE / SPU_PUT / SPU_GET (`ppu_trace.h`). Turning on reads forces out-of-line loads (`ppu_trace_wants_reads`), which costs a lot, so record **one region pair at a time**: the candidate block B and the wait window W it would move into. Record:
   - every guest address B reads and writes (lines);
   - every SPU DMA GET/PUT and PPU write during W, from other threads included;
   - every HLE/syscall B makes;
   - lwmutex/lwcond ownership changes.
2. **Independence test.** No line written by B is read or written by W's SPU jobs or other threads. No line read by B is written during W. B makes no syscall/HLE with ordering effects (event, mutex, file, audio, SPURS). B reads no time base. B allocates nothing from shared allocators. Atomics and reservations appear only on lines W never touches.
3. **Over many frames.** Repeat across ≥1,000 race frames, including heavy scenes. Any violation rejects B.
4. **Validation if accepted.** Run a bit-exact A/B over the same recorded inputs. The PPU has no replay of real inputs today ("PPU has no recorded real inputs", perfbench README), so a race-level determinism check (pad file + identical frame hashes) would be needed. That does not exist: BLOCKED.

Expected ceiling even if every candidate passed: ≤ ~1 ms/frame. Interrupts and timers: the guest's own usleep timing and SPU interrupt timing would shift but remain legal schedules. Externally visible ordering (audio and GPU command order) must not change, which rules out moving anything that writes command buffers or audio queues.

## 3. Task 6: why the 1.6x PPU codegen gain did not show

| Question | Finding | Label |
|---|---|---|
| Do the optimised functions run in the race? | yes, but the 101 benchmarked functions cover **6.9 %** of main-thread samples (`ppucc/RESULTS.md`) | VERIFIED |
| Expected race effect | 30.6 ms x 6.9 % x (1 - 1/1.45) = **0.65 ms/frame**, below the ±1.5 ms noise | MODELLED |
| Whole-program build (fast-mem frame + vmx-locals auto + PGO + ThinLTO, exe 8ae3e635) | raced once (Kksr31): 32.8 fps, 110.8 Mcyc/flip, vs baseline 68cdc70d 33.1-35.0 fps, 101-107 Mcyc/flip. No measurable gain, single run | VERIFIED (single run) |
| Where does main-thread time really go? | compute 9.16, runtime 2.23 (PT hooks 1.11 harness-only, HLE 0.43, syscall 0.17, indirect calls 0.14, VMX out-of-line 0.15), spin 4.13, waits 14.9 ms/frame | VERIFIED |
| Is `[main-cyc]` a good metric? | no: with `PS3_USLEEP_SPIN=2` the main thread spin-waits on-CPU, so cycles/flip include ~13 ms of waiting | VERIFIED |
| Code layout / i-cache | hot-code order: no gain (PERF_60FPS.md, Kk53/Kk54) | VERIFIED (earlier) |
| PGO | quiet A/B Kk81-84: -1.7 % cycles, inside the spread | VERIFIED (earlier) |
| Register state / CR / memory helpers | gains concentrate in vector bodies (2-9x); scalar bodies 1.0-1.6x (ppucc). The main thread is mostly scalar and spread thin | VERIFIED (synthetic) |

**Conclusion:** even a perfect 2x on all lifted main-thread compute would remove ~4.6 ms. That is the largest PPU lever, and it only matters if the SPU-side waits shrink too, because the main thread then reaches the same waits sooner and waits longer. Removing the PT harness hooks (1.1 ms) is the only verified main-thread CPU item of meaningful size, and it is a measurement artifact, not a production gain.

# CURRENT_CRITICAL_PATH: the race frame after Fix 2, corrected lift and chained Havok

Private, offline (2026-11-19). No race was run for this document; it reuses existing logs.
Labels: VERIFIED (measured or read), PARTIAL, HYPOTHESIS, BLOCKED, MODELLED.

## 1. Evidence available, and its limits

| Source | Fix 2 | Covers | Limits |
|---|---|---|---|
| Kksr61/63/64 (candidate 33253d9d), Kksr50/54 (cp60 C2), Kksr57/59 (1ad0a8dd on). `[sc-wait]`, `[hle-wait]`, `[spu-task-stats]`, `[vk-stats]`, `[frame-hist]`, `cpu.jsonl` (`out/metrics_ksr47_67.*`) | on | per-thread syscall wait totals per second, Havok per-run cost, GPU time | `PS3_SPU_TASK_STATS=1000` on: Havok runs are inflated by ~1.2 ms (HK2) and ~0.4 ms (HK1). No guest-function attribution. No Present-spin measure |
| Kksr23 `[m2]` main-thread sampler (criticalpath60) | **off** | main-thread self, runtime and wait split by guest function | pre-Fix-2; PT hooks were on (1.1 ms/frame harness); 30.6 ms frame |
| Kksr36 ftrace + PT (criticalpath60) | off | job spans, handler hops, intro frames | heavy PT logging, intro only |
| `D:\cp60_runs\r1_cpath.txt` (Kksr47) | off | critical-path stream | Fix 2 off |
| spu_rejoin60 R1 counts | off/on (model) | interpreter/rejoin transitions | renderable only |

No Fix-2-on run has a main-thread sampler or a job-level trace (BLOCKED). The breakdown below therefore uses uninstrumented syscall totals for the waits, plus the pre-Fix-2 sampler for what lies between them.

## 2. Frame budget with Fix 2 (candidate, Kksr61/63/64; `PS3_SPU_TASK_STATS` on)

Mean frame 25.0 / 26.3 / 27.8 ms (40.0 / 38.0 / 36.0 fps). The rows are mutually exclusive main-thread states.

| Main-thread state | ms/frame | Evidence | Label |
|---|---:|---|---|
| JobBatch waits: guest `usleep(250)` yield-spin in the light-mutex wait (`0x4B63F0` under `0x94CC80` / `0x4AACA0`) | **8.6 / 10.0 / 9.6** | `[sc-wait]` tid 1 sc141 | VERIFIED |
| Havok/physics semaphore `0xA4C590` (event-queue receive, sc130) | **2.9 / 2.8 / 2.9** | `[sc-wait]` tid 1 sc130 | VERIFIED (stats-inflated) |
| HLE waits (lwmutex/lwcond/cellFs/GCM imports) | 0.15 | `[hle-wait]` tid 1 | VERIFIED |
| Everything else: lifted guest compute, runtime under the guest, the Present spin `0x50C818` (a guest load loop, invisible to sc-wait), the GcKernel ref poll `0x72E1E0` | **~13.3-15.0** | frame − the rows above | VERIFIED as a remainder |
| of which guest compute (pre-Fix-2 m2) | ~9.2 | criticalpath60 §2 | PARTIAL (old build, same PPU lift) |
| of which runtime (HLE dispatch, syscalls, icall, VMX, stores; PT hooks excluded) | ~1.1 | criticalpath60 §2 | PARTIAL |
| of which Present spin + GcKernel poll + fios | ~3-4.5 | remainder | HYPOTHESIS (pre-Fix-2 it was 4.13 + 0.31 + 0.45; renderable SPU time fell from 27-30 to 10-13 SPU-ms/frame with Fix 2, so the spin should be shorter) |

So the main thread waits on SPU work for **~11.5-12.9 ms/frame** (JobBatch + Havok), plus an unmeasured Present-spin share. This matches the brief's "~12 ms". The rest, ~13-15 ms, is PPU work plus the Present spin.

GPU (VERIFIED, `[vk-stats]`, last ~45 s of each run):
- 13.7-14.3 ms of GPU time per frame at `RSX_RES_SCALE=1.5` + FSR + texture pack;
- record 1.7-1.9 ms and submit 0.13 ms per frame on the RSX/backend thread;
- GPU utilisation 56-57 %;
- the backend's present/fence wait is 3.8-4.7 ms/frame.

The GPU is not the limiter at 38 fps. At 60 fps it would be at ~85 % of a 16.7 ms frame (MODELLED), so it becomes a co-limiter near the target with these settings.

## 3. Frame structure (guest order VERIFIED in criticalpath60; the timings there are pre-Fix-2)

```
Present(N-1) 0x5226A8 -> GcKernel ref poll 0x72E1E0 -> spin 0x50C818 until N-1's renderable jobs are done
World::Update 0x216008
  ms2Physics::Update -> Havok step 0x30B710 -> stepDeltaTime: HK1 x~4.6 -> HK2 x~4.6 -> HKd x~9.1 task runs per frame
      main thread = Havok PPU worker, alternating PPU solver work and 0xA4C590 waits
  vehicle physics: 2 JobBatches of vehiclephysics Wws jobs, waits at lr 0x413784
  0x187118: 0xA4C590 waits (HKc x~4.6 + 1ef1f4c9 jobs)
visibility kick 0x331240 -> PVS JobBatches (112 jobs/frame)
occluder batches (4 waits, lr 0x5F5EFC), audio, GUI
per view: RenderableProxy 0x482680 -> Vis::Wait 0x45CAA8 -> 0x5F74B0 (96 x 0x4AACA0)
          ExecutePushBuffer 0x50D868 -> renderablejob Wws jobs
EndFrame -> Present
```

Havok runs per frame (VERIFIED, `[spu-task-stats]` runs / frames): HK1 4.4-4.8, HK2 4.4-4.8, HKd 8.7-9.5, HKc 4.4-4.8, i.e. one 4-5-wide wave of each per frame.

## 4. The dependency chain that sets frame completion

1. **Sim phase**: Havok waves (main waits 2.8-2.9 ms), then the vehicle-physics batches, then the 0x187118 waves.
   - The main thread waits for SPU work it has just kicked. The SPU side is under-occupied: in the Kksr36 intro, 0.9 Wws jobs + 1.3 Havok tasks run on average in SIM.
   - So this chain is **latency-bound**: job duration plus hand-off hops, not lane throughput. VERIFIED pre-Fix-2; assumed to still hold (HYPOTHESIS).
2. **Visibility**: 112 PVS jobs, ~10.7 SPU-ms/frame (spu_rejoin60, Fix 2 on). Their span was ~3 ms on ~3.7 lanes. The main waits in Vis::Wait (3.2 ms pre-Fix-2). This is **throughput-bound on 5 lanes** while it runs.
3. **Emit**: renderable jobs (10-13 SPU-ms/frame with Fix 2) overlap ExecutePushBuffer. The **next** frame's Present spin waits for their tail.
4. **GPU**: 14 ms/frame, overlapped (Vulkan lazy sync, mailbox present).

Which waits remain the longest chain (with Fix 2):
- JobBatch waits, 8.6-10 ms total. Its split by site (vehicle physics vs Vis vs occluders vs small batches) is **BLOCKED**: there is no Fix-2-on trace. Pre-Fix-2 split: vehicle physics 3.30, Vis 3.23, occluders 0.76, small batches ~3.0 ms.
- Havok, 2.8-2.9 ms.
- The Present spin, unmeasured.

There is no double counting: these are disjoint main-thread intervals. Overlapping SPU work is not added on top.

## 5. Which earlier conclusions still hold

| Earlier conclusion | Source | Status now |
|---|---|---|
| Main ~9.2 ms guest compute + ~1.1 ms runtime | criticalpath60 | still the best estimate (the PPU lift is unchanged). PARTIAL |
| PT route hooks cost 1.1 ms/frame in Kksr runs | criticalpath60 §0.1 | **Corrected**: true for Kksr23 only. Kksr43-67 logs show `PS3_TRACE_FILE ... cannot-read`; `configure()` returns before setting a hook mask, so these runs had no hooks. VERIFIED |
| Present spin 4.13 ms | criticalpath60 (pre-Fix-2) | no longer valid; Fix 2 cut renderable SPU time by more than half. Size BLOCKED |
| renderable is the only interpreted job; Fix 2 removes the run-to-end amplification | spu_rejoin60 | still valid. The candidate adds the source-level fix (corrected lift) and C-A. Transition overhead was ≤ 0.6 SPU-ms/frame before them |
| Havok HK2 3.3 ms/run in race vs 0.42-0.50 ms replayed: "unexplained ~1.5 ms" | criticalpath60, spu_rejoin60 | **largely explained** (§6). MODELLED |
| JobBatchHandler hop latency 1-3 ms (Fix 1) | criticalpath60 | **weakened**. Race: with Fix 2 on, Fix 1 did not reduce the main JobBatch wait (C12 9.17/8.41 vs C2 8.36/9.29 ms/frame) although handler polls rose 1,800 → 4,770/s. Without Fix 2 it cut 2.0 ms/frame. PARTIAL (n=2) |
| Slow mode = host contention | slowmode | still valid; it decided Kksr60-67 (BUILD_AB_PLAN §0) |

## 6. Havok in race, re-derived (MODELLED from VERIFIED parts)

| HK2 per run (ms) | baseline-type lift (plain) | candidate (chain-chunks) |
|---|---:|---|
| in race with stats on (VERIFIED) | 3.35-3.64 | 2.91-3.00 |
| stats cost (~5,000 DMA + ~630 atomics × ~0.21 µs) | −1.1-1.2 | −1.1-1.2 |
| **in race, stats off (MODELLED)** | **~2.2-2.4** | **~1.75-1.85** |
| replay, lifted compute only, best of 40, mean recording (VERIFIED; `out/hk2_replay_phase4.txt`) | ~0.59 | ~0.48-0.54 |
| replay normalised to a mean race run (recordings carry ~0.46 of the mean DMA count; ASSUMPTION: work scales with DMA) | ~1.3 | ~1.1 |
| MFC emulation without stats, 5 threads (VERIFIED microbench, 131-167 ns/DMA) | ~0.7-0.8 | ~0.7-0.8 |
| remainder: contention, cache | ~0.2-0.3 | ~0.0-0.1 |

HK1 is analogous: stats on 1.55-1.59 (candidate) vs 1.65-1.74 ms; stats off ~1.15 vs ~1.3 ms (MODELLED).

The earlier "6.5x in-race vs replay" gap is therefore mostly the stats instrumentation plus MFC emulation. Little is left unexplained.

## 7. UPDATE 2026-11-19 (after Test A Kksr68-75 and Test B Kksr76)

### 7.1 Test A result (VERIFIED; `out/testA.json`, `out/metrics_ksr68_76.txt`)
- All 8 runs valid. A = 714690f6 (Kksr68/71/73/74); B = 33253d9d (Kksr69/70/72/75). Stats off.
- fps: A median 39.96 (SD 1.18) vs B 39.67 (SD 0.95). Median difference −0.29 fps, one-sided p = 0.70, noise floor 2.35 fps. **No detectable difference.**
- Frame time medians: p50 26.1 vs 25.8 ms, p90 32.3 vs 31.9 ms, p99 42.6 vs 41.5 ms. draw-fps 36.9 vs 36.7.
- Host: GPU 48 % in both arms, 4.0 / 4.2 game cores, 1.5 / 1.6 non-game cores. sim-pace lost time is equal (363 vs 362 ms/s).

### 7.2 Frame budget, stats off (Test A medians: A / B)

| Main-thread state | ms/frame | Label |
|---|---:|---|
| frame | 25.0 / 25.2 | VERIFIED |
| JobBatch waits (sc141) | 9.1 / 8.8 | VERIFIED |
| Havok semaphore (sc130) | **2.17 / 1.90**; every B run is below every A run (1.82-1.95 vs 2.15-2.26) | VERIFIED |
| Present spin `0x50C818` | ~1.5 (Test B sampler: 4.6 % of main-thread samples × 32.2 ms; profiled) | PARTIAL |
| everything else (guest compute + runtime + PT lean hooks + GcKernel poll) | ~12.5 | remainder |

Findings:
- **Stats cost confirmed**: the Havok wait fell from 3.4-3.6 (stats on, Kksr50-59) to 2.15-2.26 ms/frame (stats off, same lift type). VERIFIED across batches.
- The candidate's chained Havok cuts the Havok wait by **−0.27 ms/frame**. The frame does not move. The Havok wave is not the binding constraint (§4 hypothesis now supported).
- **PT route hooks were ACTIVE in all Test A/B runs.** Every log has `[PT] t=0 ev=config mask=03 fn=18 ... hooks=1 lean=1`, the config was readable this time, no `[PT] off` was logged, and no `trace_off_ksr7x` file exists. So per-call lean hooks ran on every PPU thread for the whole race in both arms. BUILD_AB_PLAN §3's "no-op" statement held for Kksr43-67 only.
  - The harness cost on the main thread is ≤ ~1.1 ms/frame (Kksr23 non-lean measurement; MODELLED).
  - It was equal in both arms, so the verdict stands. Production frames are faster by up to that amount.
- Race entry moved from 53-58 s to 102-104 s after boot in this batch (Kksr68 63 s). HYPOTHESIS: PT logging during the menu (16k `[PT]` lines up to ~104 s). Not investigated further.

### 7.3 Test B (Kksr76, 31.0 fps, profiled; timings relative)
- **The critical-path trace missed the race.** The window was `80:15` (80-95 s after the first hook). Race entry was at 103.8 s. The file holds 31,342 spans (0 dropped): menu/loading only, with **1** Havok task span. The per-site wait split and the Havok wave analysis are **still BLOCKED**. Plan error (I assumed entry at 53-66 s). Fix: NEXT_PROFILE_PLAN, Rerun section.
- Main-thread sampler, race window (2,047 samples, t ≥ 114 s):
  - `func_0050C818` (Present spin) 4.6 % → **~1.5 ms/frame**, down from 4.0 ms in Kksr47 (Fix 2 off; 11.1 % of 36.3 ms) and 4.13 ms in Kksr23. VERIFIED relative; the absolute value is profiled.
  - **Sampler artifact, not SPU work on the PPU.** The buckets `spu_2061190609_LS_27D10` 31.7 %, `spu_1297305682_LS_02FC0` 4.9 %, `spu_1296695321_LS_16268` 4.7 % and `_0FF28` 2.3 % come from `samp_lookup()` (`ppu_loader.cpp:448-487`), which attributes by extent [entry, next entry). Runtime code linked after a lifted SPU body is credited to that body. The 31.7 % bucket (10.2 ms/frame) equals the main thread's sc141 usleep-spin time (10.08 ms/frame). In Kksr47 it is 23.7 % × 36.3 ms = 8.6 ms against 9.84 ms of usleep. So it is the `sys_timer` usleep spin (HYPOTHESIS, strongly supported; no PDB available to symbolize).
  - Guest compute is spread thin (top lifted PPU function ≤ 2.1 %, `func_000106A0`). No single hot PPU function.
- Wws jobs in race (`out/wws_window_ksr76.txt`, from `spu_rejoin60/tools/wws_window.py`; job times inflated ~15-20 % by profiling):

| module | jobs/frame | µs/job | interpreted steps/job | SPU-ms/frame |
|---|---:|---:|---:|---:|
| renderablejob | 24.6 | 539 | **0.0** | 13.2 |
| pvsjob | 108.5 | 118 | 0 | 12.8 |
| groundrushsquashjob | 9.7 | 928 | 0 | 9.0 |
| vehiclephysics | 31.0 | 266 | 0 | 8.2 |
| vehicledeformation | 2.4 | 1329 | 0 | 3.1 |
| screenrushjob | 2.9 | 1032 | 0 | 3.0 |
| others (19 modules) | | | spuconstraints 1.6 | 7.8 |
| total | | | | 57.2 (on 5 lanes) |

- **Interpreter residue: gone.** renderable went 32.9 → 0 steps/job (VERIFIED). Its µs/job is unchanged (538 vs 536 in Kksr50), so the corrected lift + C-A save no measurable job time, consistent with Test A.

## 8. UPDATE 2026-11-19: Fix-2-on driving critical path (Kksr77 trace)

Source: Kksr77, exe 33253d9d.
- Route hooks off (`PS3_TRACE_FILE=`), stats off, Fix 2 and drain resume on.
- `PS3_CRITICAL_PATH_TRACE=125:20` (race entry at 103.0 s, so the window is race +22..42 s), 1,644,919 spans, 0 dropped.
- 41.16 fps, p50 25.65 ms: the profiling overhead is negligible (Test A ~40 fps).
- Tool: `tools/cp77.py`, output `out/cp77.json`.

Releaser attribution and the per-wait split are PARTIAL (timing inference). Totals are VERIFIED.

### 8.1 Frame budget (825 frames, 24.23 ms)

| Main-thread state | ms/frame | Label |
|---|---:|---|
| JobBatch waits (usleep at lr 0x94CCA8 in 0x94CC80) | **7.65** | VERIFIED |
| Havok/physics semaphore 0xA4C590 (sc 0x82; lr a49e3c 1.55, a48ed4 0.26, 0x187118 0.28) | **2.10** | VERIFIED |
| GcKernel GPU reference poll (usleep lr 0x72E5C0) | **1.00** | VERIFIED |
| Havok worker usleep polls (lr a49ad4/a48b4c/a48364) | 0.43 | VERIFIED |
| Present spin 0x50C818 (estimate from renderable completion vs the end of the GcKernel poll) | ~0 | PARTIAL |
| main-thread compute (guest + runtime), remainder | **~13.0** | VERIFIED as a remainder |

### 8.2 Per-site split (one row per releaser)

The releaser is the SPU item whose end is the latest one inside the wait. Columns:
- kick = wait start → first job of that batch;
- exec = job execution span;
- tail = last job end → main wake (handler poll + SetCondition + wake; the handler's polls are merged in the trace and cannot be split).

| Wait / releaser | waits/frame | ms/frame | kick µs | exec µs | tail µs | lanes busy |
|---|---:|---:|---:|---:|---:|---:|
| JobBatch / **vehiclephysics** (2 × 16 jobs) | 0.98 | **2.91** | 292 | 797 + 629 (two batches) | 489, plus an **871 µs gap between the batches** | 2.0 |
| JobBatch / **renderablejob** | 0.97 | **1.85** | **1,458** (pvsjob holds 2.76 lanes and screenrush 0.82 during it) | 445 | 31 | 3.8 |
| Havok sem a49e3c / none ended inside the wait (signalled mid-task by Havok SPU events) | 12.0 | 1.43 | – | – | – | 0.0 |
| JobBatch / groundrushjob | 0.17 | 0.59 | 3,062 (lanes full) | 341 | 38 | 4.1 |
| JobBatch / none | 0.95 | 0.46 | – | – | – | 0.1 |
| JobBatch / generatefogtable (occluders) | 0.59 | 0.44 | 324 | 89 | 343 | 0.8 |
| JobBatch / pvsjob (Vis) | 0.21 | 0.39 | 64 | 1,680 | 76 | 3.7 |
| JobBatch / trailsupdate, groundrushsquash, screenrush, ProcessEmitters, octreequery, LibMP3, occjob | – | 0.86 | mostly hop-dominated | | | |
| Havok sem a48ed4 / HK1, 0x187118 / spuconstraints + HKc + groundrushsquash | – | 0.67 | 0 | 40-70 | 0-40 | – |

SPU work per frame: HK2 9.9, pvs 8.9, renderable 7.1, groundrushsquash 6.9, HK1 6.4, vehiclephysics 5.5, HKc 3.9, screenrush 2.4 ms. The Wws lanes are busy 1.54 of 5 on average.

### 8.3 Longest dependency chain per frame (PARTIAL)

The chain runs: main compute (~13 ms), then the vehicle-physics wait (3.0 ms), then the renderable wait (1.9 ms), then the Havok semaphore waits (2.1 ms), then the GPU reference poll (1.0 ms), then small batches (~1.8 ms).

- **Of the vehicle wait's 3.08 ms, 1.65 ms is hand-off latency** (kick 0.29 + gap between batches 0.87 + tail 0.49) and 1.43 ms is execution.
- The renderable wait is lane contention behind the visibility (PVS) jobs.
- The Havok wave is no longer a long wait: 12 short waits per frame of ~120 µs.
- The Present spin has effectively disappeared with Fix 2.

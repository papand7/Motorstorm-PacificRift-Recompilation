# CRITICAL_PATH: where a ~30 ms race frame goes (MotorStorm PR 1.00, Vulkan)

Private analysis, offline only. No game launch, no build, no production change. Date 2026-11-17.
Labels: VERIFIED (measured or read in code), PARTIAL, HYPOTHESIS, BLOCKED.
Tools and outputs: `generated/analysis/criticalpath60/tools/*.py`, `.../out/*.txt`. Scratch (large, private): `D:/cp60_*`.

## 0. Evidence used and its limits (read this first)

| Source | What it gives | Distortion | Label |
|---|---|---|---|
| Kksr23 `[m2]` main-thread sampler (`generated/runs/20261117-004031-vk-Kksr23`, aggregate `waits/m2_race200.txt`, 7 windows t>=110 s) | main-thread self / runtime / wait split by guest function, inclusive per function | ~1 % sampler overhead (hold 17-27 us per 2 ms). PT route hooks active all race (see 0.1). **ms/frame values assume 32.7 fps**; the real Kksr23 race rate is 34.2 fps (29.2 ms), so scale by ~0.956 | VERIFIED |
| Kksr36 PT log (`runs/20261117-071427-vk-Kksr36/stderr.log`, 1.54 M `[PT]` lines, PT 114-204 s) | per-call enter/exit of the wait primitives on all threads; who signals each gate | **heavy**: each hooked call writes log lines; Kksr36 races at 14.2 fps (other runs of the same exe 33-35 fps). Steady (<50 ms) frames are ~31 ms but their main-thread CPU is inflated by ~7 ms and the waits shrink by the same amount | VERIFIED (structure), timings distorted |
| Kksr36 ftrace `waits/cpath_waits.txt` (125-135 s, 315,789 spans) | SPU job spans (kind 26/27/28/29), Havok task spans (34/38/39), lane picks (24/25), main syscalls/usleeps | covers race load + **race intro** (load returned at PT 128.5 s; intro lasts ~25 s), not driving. 89 steady frames 128.55-135 s | VERIFIED |
| PT<->ftrace clock | `ftrace_us = PT_us - 20263.5`, fitted on 353 matched cv-wait ends, p10-p90 residual 2.4 us (`out/` via joint.py) | none | VERIFIED |
| Kksr43 `[sc-wait]`, `[spu-task-stats]`, `[main-cyc]` (`runs/20261117-193837-vk-Kksr43`, 35.0 fps, same exe 68cdc70d as Kksr36) | uninstrumented syscall wait per thread, Havok task costs, main-thread cycles | route PT hooks on | VERIFIED |
| Run-to-run: same exe/env 68cdc70d: Kksr24 33.1, Kksr26 34.0, Kksr34 34.5, Kksr35 34.6, Kksr43 35.0 fps; but Kksr44 11.6, Kksr45 15.5, Kksr46 24.7 (host disturbed) | `out/run_fps.txt` | Disturbed runs exist inside "the same" config: preflight must reject them | VERIFIED |

### 0.1 Measurement artifact found: route trace hooks stay on for the whole race (VERIFIED)
- Every Kksr run sets `PS3_TRACE_FILE=nav_sites.cfg` (the controller needs route sites) and `PS3_TRACE_OFF_FILE=...trace_off_<tag>`, but no Kksr log contains `[PT] off:` (checked Kksr23/35/36/43) -> the off file was never created, `g_ppu_trace_mask` stays non-zero, and every lifted guest call and return goes through `ppu_trace_enter/ret` (`ps3recomp-vkgame/runtime/ppu/ppu_trace.cpp:924-950`: a shared racy counter `++n` on every call by every PPU thread, then a site hash lookup).
- Cost on the main thread: `ppu_trace_enter` 0.58 + `ppu_trace_ret` 0.53 = **1.11 ms/frame** (m2 host leaf rva resolution, `ppumain/results/host_rva_resolved.txt`).
- Production (`port-vkgame/main.cpp` defaults, launcher) sets no `PS3_TRACE_FILE`, so the lifted hook is one load + untaken branch (`generated/ppu-v100-twin/ppu_recomp.h:78`). All "30.6 ms" figures therefore include ~1.1 ms of harness-only main-thread CPU.

## 1. Frame structure (one main-thread iteration; guest code order VERIFIED in `t132b/main_loop_callgraph.md`)

```
Present(N-1) end: 0x5226A8 -> GcKernel ref poll 0x72E1E0 (GPU frame N-2) -> spin 0x50C818 until all renderable jobs of N-1 report done
BeginFrame, input, particles
World::Update 0x216008
  ms2Physics::Update 0x8CF1C0 -> Havok step 0x30B710 -> hkpMultiThreadedSimulation::stepDeltaTime 0xB943E8/0xB95B10
      Havok SPU task waves (hkSpuUtil tasks, own host threads, kind 38/39): HK1 0x145c1b7b (solve) x5 -> HK2 0x1d51c6ce (collide) x5 -> HKd 0x1266e45a x5
      main thread = Havok worker; waits on the Havok semaphore 0xA4C590 (event-queue receive) lr 0xA49E3C / 0xA48ED4
  vehicle physics: 2 JobBatches of 16-23 vehiclephysics Wws jobs (2e29dde); main waits 0x4AACA0 lr 0x413784 (fn 0x413390) right after Start
  other world: 0x174880/0x174970 -> 0x187118 waits 0xA4C590 lr 0x18715C/0x187180 (job 1ef1f4c9 + HKc 0x18345147 waves)
visibility kick 0x331240 -> PVS JobBatches (job 602e92cb, 112 jobs/frame)
occluder batches (0x5F58F0 region, 4 waits/frame lr 0x5F5EFC), audio 0x7C9F70, GUI
per-view render: RenderableProxy 0x482680 -> Vis::Wait 0x45CAA8 -> PVSComputerImpl::WaitForCompletion 0x5F74B0 (96 x 0x4AACA0 lr 0x5F7588)
                 ExecutePushBuffer 0x50D868 (21-48/frame) -> renderablejob Wws jobs (2b93b080)
EndFrame 0x346A40 -> Present (next iteration's first item)
```

Wait primitives (VERIFIED by disassembly, `generated/analysis/dis.py`):
- `JobBatchInternal::Wait` 0x4AACA0 -> `ConditionVariableLightImpl::Wait` 0x94CC80 -> light mutex 0x4B63F0: `lwarx/stwcx.`, then 125 x 8 polling loads, then `sys_timer_usleep(250)` (0x4B64AC), retry. The port runs the main thread's usleep as a 250 us yield-spin (`PS3_USLEEP_SPIN=2` + `MAIN_ONLY`, `sys_timer.c:316-332`), so these waits are on-CPU.
- `SetCondition(true)` for every JobBatch gate is called by guest tid 12 **JobBatchHandler** (15,613 starts = 15,613 handler signals in the window; VERIFIED). Its loop 0x4AF670: 0x4AC940, 0x4AE908, `usleep(200)` (0x4AF6C8), repeat. Dev symbols name the two halves `JobManagerBase::HandleBatchCompletions` / `HandleBatchSubmissions` (sizes match approximately; which retail function is which: PARTIAL).
- 0xA4C590 = event-queue-backed semaphore (syscall 130). Callers: Havok job queue (0xA48A18/0xA499F8 under stepDeltaTime), 0x187118 (World::Update), 0x309428/0x30B710 (ms2Physics). **It is not the visibility wait** (the brief's label): `func_00482680` 3.45 ms (next to A4C590 3.52 ms in the m2 list) is RenderableProxy -> Vis::Wait, which waits through 0x4AACA0 (VERIFIED by static call graph, `t132b/tools/up.py`, `tree2.py`).

## 2. Uninstrumented time budget (ms/frame; m2 Kksr23 at its 30.58 ms normalisation, cross-checked with Kksr43 sc-wait)

No double counting: the six rows are mutually exclusive main-thread states.

| State | ms/frame | Evidence | Label |
|---|---:|---|---|
| Lifted guest compute (ppu_self minus the 0x50C818 spin) | 9.16 | m2 cat ppu_self 13.29 - func_0050C818 self 4.13 | VERIFIED |
| Runtime under guest | 2.23 | m2; of which PT hooks 1.11 (harness only), HLE dispatch 0.43, lv2_syscall 0.17, indirect call 0.14, out-of-line VMX 0.15, vm_write32 0.10, spu_coh_notify/lockline 0.15 | VERIFIED |
| Present spin 0x50C818 (waiting for renderable jobs, counted as self by the sampler) | 4.13 | m2 self of the spin loop `while ([r3+0x2560] != [r3+0x44C])` | VERIFIED |
| JobBatch waits (0x4B63F0 spin+usleep under 0x94CC80/0x4AACA0) | 10.32 | m2 waitin; Kksr43 sc-wait usleep 265 ms/s = 7.6 ms/frame at 35 fps (the remainder is the lock's polling loads) | VERIFIED |
| Havok/physics semaphore 0xA4C590 | 3.44 | m2 waitin; Kksr43 sc130 ~92 ms/s = 2.6 ms/frame | VERIFIED |
| Other waits: fios 0x66BB38 0.45, GcKernel ref poll 0x72E1E0 0.31, misc 0.4 | ~1.2 | m2 | VERIFIED |
| Total | 30.5 | | |

So the main thread computes ~9.2 ms (guest) + ~1.1 ms (runtime, production) per frame and waits ~19 ms (JobBatch 10.3 + Havok 3.4 + renderable spin 4.1 + 1.2). `[main-cyc]` 98-117 Mcycles/flip (Kksr23-43) is mostly these spin-waits, so it no longer measures compute (VERIFIED: `out/maincyc.txt`; the ppucc whole-program build 8ae3e635 raced in Kksr31: 110.8 Mcyc/flip, 30.7 flips/s, no gain).

JobBatch wait split by caller (m2 inclusive of the calling function; each includes a little CPU):

| Caller (wait site lr) | ms/frame | Producer |
|---|---:|---|
| 0x413390 vehicle physics (0x413784), 2 waits | 3.30 | vehiclephysics Wws jobs |
| 0x45CAA8 Vis::Wait -> 0x5F74B0 (0x5F7588), 96 calls, few block | 3.23 | PVS jobs 602e92cb (identification by timing: PARTIAL) |
| 0x5F5E98 occluders (0x5F5EFC), 4 waits | 0.76 | jobs 14bb29c0/b0d7bd05/fe986f37 |
| 0x3AD890 (0x3AD910) / 0x63E6B0 (0x63E714) / 0x44B520 (0x44B55C) / 0x49DAF0 (0x49DCF8) / 0x4659B0 (0x4659E4) | 0.61 / 0.60 / 0.49 / 0.25 / 0.22 | various small batches |
| remainder (0x4CB8AC, 0x3A3EC8, 0x4924A4, 0x49EB20, ...) | ~0.85 | |

The brief's "Present/render-job spin ~0.2 ms" comes from the ftrace, which only records syscalls; the spin is a guest loop and is invisible there. The sampler shows 4.13 ms/frame. **Correction: VERIFIED.**

## 3. Chronological timeline (Kksr36 race-intro steady frames, joint PT+ftrace, median of 89 frames)

Offsets from the main thread's Present entry. Main-thread durations here are inflated by PT logging (section 0); SPU spans are not (SPU threads carry no PT hooks except tid 12's SetCondition calls). Source `out/phases_ksr36.txt`, `out/decomp_ksr36.txt`, `out/lanes_ksr36.txt`, `out/joint_sample.txt`.

| ms (p50) | Main thread | SPU side | Evidence |
|---|---|---|---|
| 0.0-0.05 | Present; spin already satisfied in the median intro frame (mean 1.58) | renderable tail of N-1 | phases |
| 0.70 | Havok step: main submits HK1 x5 directly (kind 38 by main host thread, pickup ~7 us) | HK1 1.2-2.1 ms, HK2 x5 1.7-2.6 ms, HKd x5 0.1-0.4 ms | batch.py, joint |
| ~1-6 | main alternates Havok PPU work and 0xA4C590 waits (1.84+0.28 ms/frame), each ended mid-task by a Havok SPU event, not by task end (last-end->exit 0.01 ms/frame) | 1.26 HK tasks and 0.91 Wws jobs running on average during the whole SIM phase | decomp, lanes |
| 7.05-10.78 | two vehicle-physics JobBatch waits (1.52-1.77 ms each) | 16-23 jobs/batch, 0.21 ms each, ~4 lanes | batch_hops |
| ~12.7-13.9 | 0x187118 waits | HKc waves x2, 1ef1f4c9 jobs | joint |
| 17.9 | visibility kick | PVS 602e92cb: 112 jobs, 11.2 SPU-ms, span 17.9-20.9 | phases |
| 20.1-25.0 | Vis waits (in this instrumented run mostly already satisfied) | | phases |
| 20.2-26.4 | ExecutePushBuffer x21 (mean 40) | renderable jobs 20.0-27.3, 14.6 SPU-ms (mean 33); lanes saturated (>=5 jobs) 48 % of the EMIT phase, 3.57 jobs on average | lanes |
| 28.45 | next Present | | |

Phase SPU occupancy (VERIFIED, `out/lanes_ksr36.txt`):

| Phase | ms (mean) | Wws jobs running | Havok tasks running | >=5 jobs | main waiting |
|---|---:|---:|---:|---:|---:|
| Present+spin | 1.58 | 1.21 | 0.00 | 15 % | 44 % |
| SIM (to first EPB) | 19.97 | 0.91 | 1.26 | 8 % | 35 % |
| EMIT (EPB span) | 7.56 | 3.57 | 0.00 | 48 % | 41 % |
| TAIL | 2.10 | 2.30 | 0.00 | 35 % | 2 % |

## 4. Anatomy of a blocking JobBatch wait (VERIFIED hop timings, Kksr36, `out/batch_hops_ksr36.txt`)

| Site | n | Start->kick | kick->1st job | job exec span | last job->SetCondition (tid 12) | SetCondition->wake | wait total |
|---|---:|---:|---:|---:|---:|---:|---:|
| vehicle physics 0x413784 | 178 | 332 (p10 85, p90 590) | 22 | 929 | 210 (p10 18, p90 428) | 149 (p90 251) | 1582 us |
| occluders 0x5F5EFC | 85 | 179 | 17 | 330 | 302 | 143 | 904 us |
| 0x49DCF8 | 42 | 237 (started 775 us before the wait) | -18 | 2598 | 182 | 144 | 2335 us |

- JobBatchHandler poll period in the uninstrumented race: tid 12 makes 1,748-1,803 `usleep(200)` calls per second and is asleep 959-975 ms/s (Kksr23, Kksr43 `[sc-wait]`) -> **~0.56 ms per poll, of which ~0.54 ms is the 200 us sleep** (the port sleeps non-main threads on the 0.5 ms host timer: `sys_timer.c:147-156, 323-325`). VERIFIED. The handler's completion signals cluster at 550/1100/1650 us spacings (`out/kick_source_ksr36.txt`).
- Kick -> first job is ~20 us: SPURS admission is not the problem (agrees with the brief). VERIFIED.
- For vehicle physics, 0.69 ms of the 1.6 ms Start->wake is handler + wake latency, about as much as the SPU execution (0.93 ms). HYPOTHESIS (PARTIAL evidence): the handler also performs the submission; the uniform 0-600 us Start->kick spread fits a ~550 us poller, but some kicks follow a main-thread Start within 10 us, so not every submission waits for it.

## 5. Is the ~19 ms of blocking unavoidable?

| Part | ms/frame (uninstr.) | Nature | Recoverable exactly? |
|---|---:|---|---|
| SPU execution the main thread genuinely waits for (vehicle physics ~1.9, PVS ~3 span, Havok waves, occluders, renderable tail) | ~12-14 | true guest dependency: the main thread waits for work it just kicked; SPUs idle ~60 % in SIM | only by making that SPU work faster (section 6 of SPU_JOB_ANALYSIS) |
| JobBatchHandler hop latency (submission + completion), ~0.56 ms poll vs ~0.22 ms on a PS3 | 1.0-3.0 (MODELLED) | port artifact of usleep(200) granularity | yes, timing fidelity (OPTIMIZATION_CANDIDATES C1) |
| Main-thread wake quantum (guest usleep(250) spin; SetCondition->wake 143-149 us mean) | ~0.7-1.5 | guest semantics (PS3 behaves the same) | not without returning from usleep early: not exact |
| Renderable-job interpreter share inside the Present spin | part of 4.1 | port artifact (AOT fallback) | yes (C2), size BLOCKED until AOT profile |
| GPU frame N-2 ref poll | 0.31 | GPU pacing | out of scope |

Overlap: in SIM the main thread waits 35 % of the time while SPUs average ~2.2 busy of 5 lanes + task threads, so the waits are dependency waits, not capacity waits. Independent PPU work that could fill them is not proven (PPU_DEPENDENCIES.md). In EMIT the lanes are saturated half the time: there SPU throughput (renderable) is the limit.

## 6. Missing evidence (BLOCKED until a run)
- Per-site JobBatch waits and handler latency in **driving** frames without PT logging (only m2 inclusive aggregates exist).
- Where renderablejob runs interpreted (image/pc) - `PS3_SPU_AOT_PROF` has never been enabled in a race.
- Driving-phase SPU timeline (the ftrace covers the intro only).
- Per-run in-race breakdown of Havok tasks (channel waits vs compute); recordings do not carry their in-race duration.

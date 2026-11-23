# NEXT_PROFILE_PLAN: Test B, one lightweight profiling race (separate authorization; never chained after Test A)

Private. Prepared offline; nothing launched. Labels VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## Purpose

Measure the longest dependency chain of a **driving** frame on the fastest verified build, with Fix 2 on and low overhead. Specifically:

1. The **per-site split** of the 8.6-10 ms/frame JobBatch wait (vehicle physics, Vis/PVS, occluders, small batches), identified by which Wws module's last job ends just before each wait ends.
2. The **Havok waves**:
   - the run spans of HK1/HK2/HKd/HKc (kinds 34/38/39: submit, pickup, entry→return);
   - wave width, the slowest run, and imbalance;
   - how much of the `0xA4C590` wait each wave explains.
3. The **Present spin** `0x50C818` share and the remaining guest compute, from the main-thread sampler. This is the one main-thread number that has had no Fix-2-on measurement.
4. **Lane occupancy** per phase (SIM / VIS / EMIT): are the PVS and renderable phases throughput-bound on the 5 lanes?
5. **Interpreter residue**: renderable interpreted steps per job (`PS3_SPU_WWS_STATS`). Expected ~0 with the corrected lift + C-A.
6. **Vulkan / GPU**: record and submit time on the backend thread and GPU waits (`[vk-stats]`, `[vk-waits]`, already logged), to confirm the GPU is not on the chain.

## Build and gates

- Exe: the faster build from Test A. If Test A shows no detectable difference, use the **candidate 33253d9d**: same speed, and it has the corrected lift.
- Preflight: `tools/host_preflight.py` must PASS, and the same quality gate applies (BUILD_AB_PLAN §6).
- Fix 1 (`PS3_USLEEP_SPIN_LR`) is **not set**.
- One run. Tag: the next free tag after the last Test A tag (for example `Kksr76` if Test A used Kksr68-75 with no replacements). The user appends it to ORDER.

## Configuration (all switches VERIFIED present in the 33253d9d binary)

```
mkdir D:\rt60_runs   (already created, empty)
py -3 generated\analysis\roadto60_next\tools\host_preflight.py --exe "build\motorstorm-vkgame-100-next\MotorStormPacificRiftRecomp.exe=33253d9d"
py -3 generated\analysis\spuopt\tools\run_ab.py ksr76 build\motorstorm-vkgame-100-next\MotorStormPacificRiftRecomp.exe 60 "PS3_SPU_TASK_STATS=0;PS3_SPU_INTERP_REJOIN_RELOC=1;PS3_SPU_DRAIN_RESUME_RELOC=1;PS3_CRITICAL_PATH_TRACE=80:15:D:/rt60_runs/ksr76_cpath.txt;PS3_FTRACE_SPUJOB=3214:1320;PS3_SAMPLE=2;PS3_SAMPLE_MAIN=1;PS3_SAMPLE_TOP=40;PS3_SPU_WWS_STATS=1000:3214:1320"
py -3 generated\analysis\roadto60_next\tools\race_metrics.py ksr76
```

| Switch | What it records | Overhead | Why it is chosen |
|---|---|---|---|
| `PS3_CRITICAL_PATH_TRACE=80:15:<D: path>` | streamed spans (Vyukov queue, writer thread): syscalls / usleep merges per thread (kinds 1/2), SPU channel waits (3), SPU busy (4), SPURS picks / PM runs (24/25), Havok task submit / run / entry (34/38/39), host-thread CPU every 250 ms (32) | an rdtsc + queue push per span ≥ 20 µs; drops are counted, never block | streaming survives the controller's forced stop. 80-95 s after the first hook ≈ race entry (53-66 s) + 14..42 s, i.e. while driving with the throttle held |
| `PS3_FTRACE_SPUJOB=3214:1320` | Wws job spans (26) with module hash (28), AOT answer (29), interpreted steps (27), lost jobs (30) | one hook per job | identifies vehiclephysics / pvs / occluder / renderable jobs and the releaser of each wait |
| `PS3_SAMPLE=2`, `PS3_SAMPLE_MAIN=1`, `PS3_SAMPLE_TOP=40` | main-thread guest-function self samples every 2 ms (stack-guest attribution) | ~1 % (criticalpath60: 17-27 µs hold per 2 ms) | the Present spin and guest compute are guest loops, invisible to the trace |
| `PS3_SPU_WWS_STATS=1000:3214:1320` | per-module job counts and interpreted steps each second | counters per job | interpreter residue check |
| `PS3_SPU_TASK_STATS=0` | off | — | it costs ~1.2 ms per HK2 run. Havok run spans come from kinds 34/39 instead |
| not used | `PS3_SPU_AOT_PROF` (per-miss logging), PT/route hooks, `PS3_SPU_TASK_STATS`, `SPU_IRQTRACE`, screenshots | | heavy, or not needed |

The precise m2 sampler (`PS3_SAMPLE_MAIN=2`, `PS3_SAMPLE_M2_TOP`) is **not** in the candidate. Its runtime has only the basic sampler (VERIFIED: no `SAMPLE_M2` string; `ppu_loader.cpp:763` treats any value as 1). The only exe with m2 is `build/motorstorm-vkgame-100-ppusamp` (896db12c): old Wws lift, no drain resume, not the fastest build. Do not use it for Test B.

## Overhead control

- Compare Test B's fps and per-frame waits with Test A's same-build median.
- If fps is more than 10 % lower, or any wait row changes by more than 1 ms/frame, the trace is distorted. Report its timings as relative only, as criticalpath60 did for Kksr36.
- `[ftrace]` dropped spans must be 0. The header line `# ps3_ftrace ... dropped=` is checked.
- Expected trace size: ~0.5-1 M spans for 15 s (Kksr36: 316k spans in 10 s with PT on) ≈ 50-100 MB on D:.

## Analysis (offline, after the run)

The criticalpath60 tools (`criticalpath60/tools/phases.py`, `lanes.py`, `batch_hops.py`, `decomp.py`, `joint.py`) and `waits/crit.py` read this span format. The Fix-2-off reference is `D:\cp60_runs\r1_cpath.txt` (Kksr47, same span format; it had stats on and the m2 sampler).

1. Frames: Present (kind 10) to Present on the main thread. Keep steady driving frames under 50 ms.
2. For each main-thread wait span (usleep merges at the light-mutex `usleep` site, event-queue sc130): find the releaser, i.e. the last Wws job (module hash) or Havok run that ended before the wait ended. Sum per (wait kind, releasing module). This yields the per-site split without PT hooks.
3. For each releaser, split the wait into: kick → first job; job execution span; last job end → handler `SetCondition` (tid 12 syscalls); then → main wake. These are the batch_hops columns.
4. Havok:
   - per wave: width, max / median run, pickup latency (kind 38 → 39);
   - main PPU solver work between waits;
   - wave critical path versus the `0xA4C590` wait.
5. Lanes: jobs running per phase. Is PVS throughput-bound, and renderable in EMIT?
6. Sampler: self ms/frame of `0x50C818` (Present spin), `0x72E1E0`, and the top guest functions. Scale by fps.

Output: `CRITICAL_PATH_FIX2.md` with:
- a chain table (ms/frame, no double counting: disjoint main-thread intervals; SPU spans shown only as releasers);
- a ranked list of releasers by exclusive main-thread wait;
- a refresh of OPTIMIZATION_CANDIDATES.

## What it does NOT answer

- Whether a change makes the build faster. Only Test A/F-style ABBA comparisons can show that.
- Per-function cost inside a Wws job. That needs a whole-Wws-job replay harness, which does not exist (BLOCKED).

## Rerun (after Kksr76): the first attempt missed the race

- Kksr76's trace covered 80-95 s after boot. Race entry was at 103.8 s (Test A entries: 63-104 s). Only menu spans were captured (31,342 spans, 1 Havok task).
- The sampler and `PS3_SPU_WWS_STATS` results were usable (CURRENT_CRITICAL_PATH §7.3).
- Rerun with the same env, except:
  - `PS3_CRITICAL_PATH_TRACE=125:20:D:/rt60_runs/<tag>_cpath.txt`. This covers entry + 21..41 s for an entry at 104 s, and stays inside the race window for any entry between ~50 and 105 s. Check the entry time of the preceding Test A runs first.
  - Drop `PS3_SAMPLE*`: already measured. Its extent attribution also absorbs runtime code into SPU bodies.
- Validity checks on the trace file:
  - `spans` above ~300k;
  - kind 34 Havok spans ≈ 4.6 × 3 × frames;
  - kind 26 job spans present.
- The `PS3_TRACE_FILE` route hooks are active in this runner (Test A/B). Either set `PS3_TRACE_FILE=` (empty) for profiling runs, or start `trace_off_at_race.py <tag> generated\analysis\vksync\ab2\trace_off_<tag> 2` alongside, and confirm `[PT] off` appears in stderr.

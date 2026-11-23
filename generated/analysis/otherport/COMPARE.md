# The other Pacific Rift port compared with ours: what to build in our own code (2026-11-23)

Read-only study. Nothing was built, run or uploaded, and none of their scripts were executed. Per the user ("don't fork,
make it our own"), that repository is **a study source only**. Every recommendation below is something we would write
ourselves, in our style, in `port-vkgame/`, `ps3recomp-vkgame/` or `launcher/`. The few places where copying a small
piece might be worth it are marked **[MIT copy?]** so the user can decide.

Labels: VERIFIED (read in their code or docs, or in ours), MEASURED-THEIRS (their own numbers, on their hardware, not
reproduced by us), HYPOTHESIS, BLOCKED.

## 0. Sources and provenance

- Clones, outside our tree and treated as untrusted data (read only):
  - `D:\research\mspr-other\fork` = SirTobyGirl/motorstorm-pacific-rift-pc, branch `linux-fork`, HEAD
    `6cc421d55bde1222d097da729ec9c415fbfead35` (2026-11-18).
  - `D:\research\mspr-other\orig` = millennium-h4x0r/motorstorm-pacific-rift-pc, HEAD
    `b89c73ea73c29caa6508265f6c74962f998deb66`.
  - The fork is a superset of the original. Its port code adds anisotropic filtering, distance detail, the interpolation
    presenter and tools.
  - `work/patches/ps3recomp.patch` sha256 `5a769a33…4089`, 142 files, applied to ps3recomp v0.18.0 `4e8f3ca8`.
- Their game is **BCES-00129 01.00**; ours is BCUS98155 01.00. The PPU addresses they patch are the same as the ones in
  our 1.00 analysis (VERIFIED for `0x004AF6D0`/`func_004AF670`, `func_0094CC80`/`func_004B63F0`, `func_0050C818`,
  `func_004C3778`, `func_0042E3F0`, `0x00435D18` area, `func_00360DD4`). So the 1.00 PPU code layout matches across
  regions: VERIFIED for these sites, HYPOTHESIS for the rest. Each hook still has to check the bytes it expects, as our
  `mspr_patch_init` already does.
- Their hardware: Ryzen 7 5800X (8 cores / 16 threads) + RX 9070 XT, Linux/RADV. The original author also used a
  5950X + RTX 3090. Ours (criticalpath60) is a 6-core / 12-thread host. A large part of the gap is hardware.
- Licence: MIT. ps3recomp is MIT too, so their toolkit patch is MIT-on-MIT. Copying any code needs their copyright
  notice and licence text in `THIRD_PARTY_LICENSES.md`. Nothing in their port is Sony firmware. As AGENTS.md requires,
  any idea we take must also stay clear of firmware-derived code (none of the ideas below touch firmware).

## 1. Ranked summary (expected benefit for our user: fps first, then shadows, then brightness)

| # | What we would build (our code) | Their evidence | Expected for us | Risk | Effort |
|---|---|---|---|---|---|
| 1 | **Exact SPU float under MXCSR RZ/FTZ/DAZ** (`ps3recomp-vkgame/runtime/spu/spu_helpers.h` + the SPU thread entry/exit) | -19 % job CPU, +6-15 % race fps (MEASURED-THEIRS), bit-identical over 447 M lanes | HYPOTHESIS: 8-15 % less SPU CPU (we already have the AVX2 widen-to-double path they started from), so roughly 1-2 ms less JobBatch/Havok wait per frame | Medium: MXCSR must be restored around every host callout from SPU threads | Medium |
| 2 | **Fixed-step frame rates instead of variable dt at 60**: the game's own `SetInterval` n=1/n=2 plus a 30-Hz cadence for the chase-camera springs (`func_0037FB68`) | Clean 60 at the right speed; variable "catch-up" steps made the car lurch and threw riders off (MEASURED-THEIRS) | Removes a likely source of our 60-fps vehicle/camera artefacts. It adds no fps. | Low/medium | Small/medium |
| 3 | **JobBatchHandler poll cap** (`usleep(200)` at lr `0x004AF6D0` capped at ~50 us) in `ps3recomp-vkgame/runtime/syscalls/sys_timer.c` | 51 → 59 fps, about +15 %, once job lists ran wide (MEASURED-THEIRS) | HYPOTHESIS: 0.5-2 ms/frame. Our exact-200-us version (Fix 1) was inconclusive. | Low (timing only; costs a core on Windows) | Small |
| 4 | **6th host SPURS lane for the 5-SPU instance** (`ps3recomp-vkgame/libs/spurs/cellSpurs.c`) | With the contention raise: 42.7 → 51.4 fps, main job wait 9.1 → 6.0 ms (MEASURED-THEIRS, 8-core CPU) | HYPOTHESIS: small or negative on a 6-core host; worth one A/B | Medium (hardware deviation) | Small |
| 5 | Camera shake: replay the RNG draws per 30-Hz tick, and default the shake off or low | Player preference + stable 60 | Some of it is already in ours (MSPR_CAM_*) | Low | Small |
| 6 | Exposure: nothing new. Their design is the same as our bounded ring (lag 1, then wait). | VERIFIED | none (confirms our fix) | - | - |
| 7 | Shadows: nothing on cascade refits; only a shadow-distance multiplier (we have `MSPR_SHADOW_FADE`) | VERIFIED | none directly. Item 2 may reduce visible stepping (HYPOTHESIS). | - | - |
| 8 | LOD/distance: the same hook point as ours (`func_00360DD4`). Ours already limits it by group. | VERIFIED | none. Their "maximum" preset would show our Ultra vehicle bug. | - | - |
| 9 | Optional: exact host fast path for one 48 KB LS-copy job loop (`spu_fastpaths.c`) | opt-in, unmeasured | ~0.3 ms/frame at most (HYPOTHESIS) | Low (exact, hash-gated) | Small |

**Do not adopt:** their ps3recomp v0.18 base (see §8), ThinLTO, `-march=x86-64-v3` on the PPU (both no gain for them,
and our own bench found none), SPU `-O3` (no gain), and a main-thread spin in the job-lock wait (worse for them).

## 2. Frame rate: why their main thread is "fast"

### 2.1 What their frame looks like (MEASURED-THEIRS)

| | 30 fps, 720p | 60 fps, 1440p |
|---|---|---|
| fps (10 s race window) | 29.9 (p90 = median 33.4 ms) | 58.8 (median 16.7, p90 18.2 ms) |
| main thread CPU/frame | 12.7 ms | 11.8 ms |
| main thread waiting (60 fps trace) | - | ~6.2 ms, of which 4.0 ms in `func_0094CC80` (job-object lock) |
| engine ceiling with the vblank clock out of the way | - | ~63 fps |

Ours (criticalpath60 and roadto60_next, VERIFIED from our logs): a frame of 25-28 ms. Guest compute is ~9.2 ms, almost
the same as theirs (~9 ms "running"). The difference is the **waiting**: JobBatch 8.6-10.0 ms, Havok semaphore
`0xA4C590` ~2.9 ms, and the Present spin `0x50C818` ~3-4.5 ms. SPU work costs us ~85 thread-ms per frame on 6
cores. **Their PPU codegen is not the reason.** Their notes say ThinLTO, `-march=x86-64-v3` and SPU `-O3` gave nothing,
and PGO was impossible for them. We already ship PGO + ThinLTO + inline VMX/stores. Their lead comes from cheaper and
wider SPU execution, a shorter job hand-off, and an 8-16-core CPU.

### 2.2 Their speed defaults (all in `work/port/main.cpp` main(), set unless the user set them) and where we stand

| Their switch | What it does | Ours |
|---|---|---|
| `SPU_FLOAT_RZ=1` | SPU fa/fm/fma as native SSE under MXCSR RZ+FTZ+DAZ plus a range check, instead of exact widen-to-double | **Missing.** We have the AVX2 widen-to-double path (`spu_helpers.h` `spu__x8_*`) → item 1 |
| `SPURS_MAXCONT_MIN=6` | raises the three WWS job lists' maxContention from 1 | **Covered differently**: our T79/T106 reads the real 9th argument (guest passes 5) and stores it (`cellSpurs_hle_workload_attr_init`, `PS3_SPURS_GUEST_MAXCONT=1`). Their "1" is most likely the same 8-argument binding bug we fixed (HYPOTHESIS). |
| `SPURS_HOST_SPUS=6` | 6 policy-module lanes for the guest's 5-SPU instance; the guest still sees 5 | **Missing** → item 4 |
| `PS3_USLEEP_CAP=4af6d0:50` | JobBatchHandler poll 200 → 50 us | Partly: `PS3_USLEEP_SPIN_LR=4AF6D0` (exact 200 us, opt-in, inconclusive) → item 3 |
| `PS3_USLEEP_SPIN_MAX=20` | `usleep(≤20)` yields to the deadline (Linux nanosleep ≈55 us) | Covered: `PS3_USLEEP_SPIN=2` + `_MAIN_ONLY=1` spins the main thread's short sleeps |
| `SPU_MFC_LOOKUP_CACHE=1` | memo of the SPU context→MFC lookup | Covered: `PS3_SPU_MFC_FAST=1` |
| `SPU_ASYNC_POOL=1` | persistent thread pool for SPURS tasks | Covered: `PS3_SPU_TASK_POOL=1` |
| `PS3RECOMP_ENG_GPUFETCH=1` | raw guest vertex bytes decoded in the VS | Covered: `RSX_VTX_GPU=1`, `RSX_VP_FAST_FETCH=1` |
| `VK_ASYNC_RECORD=1` (60 fps) | Vulkan recording on its own thread | Covered: our backend thread (record 1.7-1.9 ms/frame) |
| `--const-bi` SPU lift | constant indirect branches → direct calls (+1.6 fps for them) | Similar: `--chain-indirect`/`--chain-chunks` on the hot images. Low value. |
| `-msse4.1`, `x86-64-v3` on SPU code, LS pshufb | vector shufb/fa, one pshufb per LS quadword | Covered: `PORT_SPU_AVX2=ON`; `spu_context.h` SSSE3 path |
| `GCM_SEMA_ACQUIRE=1` | flips gated by the game's own vblank-handler label | Different: our `PS3_SIM_PACE` host pacer (see §3) |
| vblank on its own thread | the beat never waits for a FIFO drain | Covered: `frame_beat.h` / `vblank_clock.h` |

### 2.3 Item 1: exact SPU single precision under MXCSR (build ourselves)

- **Their mechanism (VERIFIED in `ps3recomp.patch`, `runtime/spu/spu_helpers.h`):** on SPU-thread entry,
  `spu_float_mode_enter` sets MXCSR to FZ | RC=toward zero | all masked | DAZ (`0xFFC0` pattern) and a thread-local
  flag `g_spu_float_rz`. `spu_float_mode_leave` restores both.
  - The SPU single-precision helpers test the flag. They do not use `stmxcsr`, which costs ~4 ns per op.
  - Under the flag they use plain `_mm_add_ps`/`_mm_mul_ps` (FMA likewise), then a range check: a result whose
    magnitude reaches FLT_MAX, or a non-finite input, falls back to the exact lane function. SPU extended range has no
    Inf/NaN.
  - Their test `test_spu_float_rz_mode.c` checks bit-identity against the exact forms over 447 M lanes.
- **Why it is exact:** SPU single precision truncates (rounds toward zero) and flushes denormals on input and output.
  That is exactly MXCSR RZ+FTZ+DAZ. Only overflow (SPU saturates to ±max instead of Inf) and the extended-range rule
  differ, and the range check routes those to the exact code.
- **What we would write:**
  - `ps3recomp-vkgame/runtime/spu/spu_helpers.h`: an RZ variant of `spu__x8_fa/fs/fm/fma/fms/fnms`, chosen by a
    thread-local flag, falling back per lane to our existing `spu__fma_any`.
  - Thread entry/exit in `spu_workload.c` / the SPURS PM lane loop / `spu_task_pool.h`: enter/leave around guest SPU
    execution.
  - **Leave the mode around every host callout from an SPU thread**: HLE, logging, `memcpy` is fine but libm is not,
    Vulkan never runs there. A debug assert that MXCSR is the default whenever a non-SPU function returns is useful.
  - Tests: an exhaustive-ish random and edge-case comparator in the same form as our existing `tests/` (exact vs RZ, all
    six ops, denormal/overflow/zero-sign cases), plus an offline replay of one recorded WWS job byte-for-byte.
  - Env `PS3_SPU_FLOAT_RZ`, default off until a race A/B.
- **Expected:** they measured -19 % job CPU on lanes already using the AVX2 widened path, the same starting point as
  ours. Our SPU work is ~85 thread-ms/frame and the main thread waits ~12 ms on it. HYPOTHESIS: 1-2 ms/frame of wait,
  and more in heavy crash/physics frames, where our dips are.
- **Licence:** reimplement from the idea (the IEEE argument above is public knowledge). [MIT copy?] Their 30-line MXCSR
  bracket is small enough to copy, but writing our own is easy and avoids attribution.

### 2.4 Item 3: JobBatchHandler poll cap

- **Theirs (VERIFIED, `sys_timer.c` in their patch):** `PS3_USLEEP_CAP="<lr>:<us>,…"` caps a `usleep` from a listed
  return address. Default `4af6d0:50`. They state: neutral while job lists ran serially; **+15 % (51 → 59 fps)** once
  lists ran 6-wide. They also tried and rejected: a main-thread spin at lr `0x0094CCA8` (main CPU 11.7 → 15 ms, no fps),
  wake-on-completion, and pass-wake.
- **Ours:** `PS3_USLEEP_SPIN_LR=4AF6D0` honours the 200 us exactly (~218 us per poll vs ~550 us). Races: -2.0 ms
  JobBatch wait with Fix 2 off; inconclusive with Fix 2 on (n=2, roadto60_next/OPTIMIZATION_CANDIDATES.md).
- **Build:** add `PS3_USLEEP_CAP` beside `PS3_USLEEP_SPIN_LR` in `ps3recomp-vkgame/runtime/syscalls/sys_timer.c`. On
  Windows a sub-0.5-ms sleep has to be the yield-spin tail anyway, so cap and spin combine: cap 4AF6D0 to 50 us and spin
  it.
  - This is a deliberate timing deviation: the guest asked for ≥200 us. It is a pure poll period with no semantic
    effect (RESEARCH.md: the loop checks `obj+0x4064` and services batches). Document it as such.
  - Test: extend `tests/test_usleep_spin_lr_win32.c` (capped lr ≈ cap, other lr unchanged).
- **A/B:** A = current defaults; B = `PS3_USLEEP_SPIN_LR=4AF6D0`; C = B + cap 50. Quiet PC, 2+2 races. Watch tid-12
  `[sc-wait]` polls/s and main sc141 ms/frame.
- **Risk:** one more busy core on a 6-core host shared with 5 SPU lanes. Their gain appeared only when SPU lanes had
  spare host cores.

### 2.5 Item 4: a 6th host lane (experiment only)

- **Theirs (VERIFIED):** `spurs_host_lanes(nspus)` gives 6 PM worker lanes to an instance created with ≥5 SPUs; the
  guest still sees 5 (GetInfo).
  - 6 is the ceiling because the WWS policy module keeps a halfword per SPU at byte `4 + 2*spuNum` of a quadword (job
    claim `chd` at LS `0x2418`), so spuNum 6 would overwrite the list's counters.
  - The extra lane takes the workload priority of lane `sn % nspus`.
  - Reporting 6 to the game did not change Havok's split (5 tasks per phase).
- **Ours:** `si->nspus` lanes, 5 for "MotorStorm2". Admission loop at `cellSpurs.c` ~2084 (`for sn < si->nspus`).
- **Build:** `PS3_SPURS_HOST_LANES` (off by default). Separate `nlanes` from `nspus` in our `SpursInstance`. Extra lanes
  copy the priority row of `sn % nspus`. Keep everything guest-visible at 5. Add to `test_spurs_wws_concurrency.c` a
  6-lane case whose output must equal the single-lane reference (our T81 bench already showed per-job cost flat to 6
  lanes).
- **Expected:** our render phase saturates the 5 lanes 48 % of the time (criticalpath60). The simulation phase is
  dependency-bound, not capacity-bound. On a 6-core / 12-thread CPU, HYPOTHESIS: 0 to +1.5 ms. One A/B decides; drop it
  if neutral.
- **Risk:** a deviation from hardware. A job pair relying on implicit 5-wide order would show as rare physics glitches.
  Their 2 × 9-minute soak was clean (MEASURED-THEIRS).

### 2.6 Smaller frame-rate ideas

- **SPU fast path for an LS word-copy loop** (their `work/port/spu_fastpaths.c`): jobmod `e8d07656` `func_4310` copies
  48 KB of local store, 8 words per iteration, ~300-390 us per call, a dozen calls per job. The job runs alone while
  main waits.
  - Their fast path takes over when the pointers are aligned, inside LS and non-overlapping, and the code bytes hash
    matches. It memcpy's n-1 iterations, advances r22/r23, and lets the lifted loop run the last iteration, so every
    register ends exactly as before.
  - Opt-in (`SPU_FAST_COPY=1`) and unmeasured. This fits our "native reimplementation, opt-in, exact, diff-tested" rule.
  - First check that the same module appears in our WWS AOT set (our names differ). HYPOTHESIS ≤0.3 ms/frame.
- **Main-thread lock wait `0x94CCA8` `usleep(250)`:** our main thread yield-spins it (`PS3_USLEEP_SPIN=2` main-only).
  They found spinning there burns CPU without gain on Linux.
  - Worth one A/B arm on our 6-core host: `PS3_USLEEP_SPIN_LR` cannot express "never spin this lr", so add a
    `PS3_USLEEP_NOSPIN_LR=94CCA8` exclusion.
  - HYPOTHESIS: frees a core for the SPU lanes. It may also lengthen main's wake-up by ~0.3 ms per wait. Measure only.
- **Benchmark hygiene** (their BASELINE.md lesson): frame dumps every 10 frames made a fake 169-ms judder at 1440p. Our
  arms with `RSX_SHOTS`/pass dumps should not be used for fps (our runners mostly separate these already).

## 3. 60 fps: their timestep vs our vfps + sim-pace

### 3.1 Theirs (VERIFIED, `work/port/port_patches.cpp`, `work/tools/patch_lift.py`, NOTES.md)

- `func_00435D18` is the frame timer's `SetInterval(timer, n)`. It stores n (vblanks per frame) at `timer+0x18` and the
  fixed step `n·1e6/60` us. The vblank handler (`func_00522448`) copies the same field as the flip threshold at
  `0x011478BC`.
  - Hook at entry: `r4 == 2 → 1` (`port_timer_interval`), so the step is 1/60 s and a flip is allowed every vblank.
  - Flips are gated by the real label: `GCM_SEMA_ACQUIRE=1` (ACQUIRE blocks, 250 ms bound) on a 59.94-Hz vblank thread.
  - Measured: the game clock gains exactly 1/60 per flip.
- `func_008CF1C0` receives the per-frame step in f1 and passes it to the game clock (`func_0031BA20`) and the world
  update. The game itself scales it, e.g. 1/20 in crash slow motion.
  - Their `port_frame_dt` could multiply f1 by the vblanks the last frame took ("catch-up").
  - **They turned that off by default.** The made-up step lands one frame late: the long frame moves 0.69×, the next
    1.36-1.46×, the car lurches, and Havok alternated 1/60 and 1/30 steps, throwing riders off.
  - With every step 1/60 the shaking is gone, and the cost is slow motion while below 60.
- Chase camera springs: `func_0037FB68(camera r3, vehicle r4)` steps `CHASE_SHAKE_*` springs (per-step acceleration and
  damping at camera `+0x230..+0x280`) once per call and never reads dt. At 60 it shook twice as hard.
  - `port_shake_skip` runs it once per two vblanks per camera.
  - With shake off it zeroes `+0x230`/`+0x260` xyz.
- `camerasystem::Shake` (`func_0042E3F0`, RNG `func_00439820` → `func_00439678`, TEA state at `*(TOC+0x7448)`): within a
  30-Hz tick, later updates replay the draws recorded at the tick's first update, recomputed from the saved RNG state on
  a scratch copy below r1, so the game's RNG sequence is untouched. Shake off: each draw returns `c/2`
  (`c = *(TOC+0x7010)`), i.e. zero offset, after running the real draw.
- Adaptive 60/30 (rolled back): when 3 of the last 30 frames missed a vblank, set `timer+0x18` back to 2 (an even
  30 with a 1/30 step), and back to 1 after a hold.
  - Rolled back because after a drop the race ran at double speed. They suspect `port_frame_dt` doubled the step on top
    of the game's own two-vblank handling (not investigated).
  - Their 0.7 switches/s vs ~8 frame-length changes/s before is MEASURED-THEIRS.

### 3.2 Ours (VERIFIED, `port-vkgame/main.cpp`)

- `MSPR_PATCH` defaults to `drs,vfps,audiothread`. `vfps` = `0x00435F9C lwz r6 → li r6,1`: speed by elapsed time, a
  variable world dt every frame. `60fps` = `0x00435D1C stw → nop` (inside `SetInterval`; HYPOTHESIS: same effect as
  their n=1).
- `PS3_SIM_PACE=1`, `PS3_SIM_PACE_HZ=30|45|60`: a host pacer in the guest flip (`gcm_sim_pace_after_flip`), not the
  vblank label.
- Camera: `MSPR_CAM` sets the camera rate to 1/world-dt; `MSPR_CAM_MODE=1` holds and smooths the Shake offset at 30 Hz.
  **`func_0037FB68` (chase springs) is untouched** (VERIFIED: no reference in our tools or docs).

### 3.3 What we would build

1. **Chase-spring cadence (small, independent; do first).** A hook at `func_0037FB68` entry (our
   `cam_patch_lifted.py` style, asking `mspr_*` in main.cpp): step the springs only when ≥1/30 s of *world* time has
   passed for this camera (accumulate our `s_mspr_wdt`), else return. Shake-off variant: zero `+0x230`/`+0x260`.
   - Applies under vfps (any rate > 30) and the 60 lock.
   - Expected: less over-shaking at 45/60 over rough ground (their symptom matched "shook at the same moments as
     rumble").
   - Confirm the offsets on our build by reading the buggy00 values (2 2 1 / 7 20 5), as they did.
2. **A "Fixed 60" frame-rate choice:** `60fps` patch + `PS3_SIM_PACE_HZ=60`, without vfps.
   - Every world step is the game's own 1/60. Havok, camera and shadow-refit logic see the cadence they would on a
     60-Hz-stepped build.
   - Our vfps arms showed the camera-rate mismatch (25 vs 30) and the vehicle step pattern. Fixed steps remove the
     class of problems that variable dt creates. HYPOTHESIS for our remaining 60-fps vehicle/camera/shadow artefacts.
   - Cost: slow motion when the PC misses 60. That is why fps (items 1, 3, 4) comes first.
   - Our Kveh60f arms already used "60fps lock = dt 1/60". The user has not judged it at a real held 60.
3. **Adaptive fixed step (our design, avoiding their bug):** switch the game's own `timer+0x18` between 1 and 2 with
   hysteresis (their thresholds are a starting point), and pace at 60 or 30 to match.
   - **Never also scale dt**: no vfps, no f1 multiply. The world always steps 1/60 or 1/30, both native.
   - Record the timer address from `SetInterval`'s r3 (hook at `func_00435D18` entry) and write the field at a frame
     boundary (after the flip).
   - Tests: a unit test of the hysteresis state machine, plus `MSPR_DT_LOG` race checks that world time equals wall time
     across switches (their double-speed failure is the thing to assert against).
   - This would give a 60-when-possible game without vfps's variable dt. HYPOTHESIS; needs our own A/B, and the user's
     eye check for the switch moments.
4. Keep `vfps` for 45 Hz and other non-divisor rates, where no native fixed step exists.

## 4. Shadows

- **Theirs:** nothing on cascade refit/stability (VERIFIED: no shadow code in their port or patch beyond the distance
  multiplier `PS3RECOMP_SHADOW_DIST` → `shadowFadeDistModifier`, and render scale applying to depth targets).
  - The "good shadows" our user saw are the game's own cascades at a steady frame cadence and a 2× render scale.
- **Ours:** the cadence analysis (GLITCHES.md, shadowlag) shows the game refits the cascades every 1-8 frames. That is
  the game's own logic, and it would be the same on their build.
  - What may differ is the *visibility* of the stepping. Under vfps the world dt and camera move per frame vary, so the
    refit trigger (HYPOTHESIS: a camera-motion/time threshold) fires at irregular wall times. Fixed steps (§3.3) make
    the refit pattern regular.
  - HYPOTHESIS, cheap to test: the existing shadowlag cadence tool on a `60fps`-lock capture vs a vfps capture.
- No change to our RSX_SHADOW_TILES plan follows from their code. The world-tile design is ahead of anything there.

## 5. Brightness / exposure

- **Theirs (VERIFIED, `rsx_draw_engine.c` in their patch, `eng_small_targets_to_guest`):** at each present, colour
  targets of ≤`PS3RECOMP_ENG_SMALL_WRITEBACK` pixels (default 1024) written this frame are copied to guest memory.
  - Async path: copies are recorded at present and stored at the **next** present. A ticket not ready then is kept one
    more frame, then waited for.
  - Sync fallback: one flush, then copies.
  - They argue a frame of lag matches the PS3, which reads frame N's luminance while building N+1.
  - Same mechanism as our `func_004C3778` analysis (16×16 FP16 at `0x07EBA600`, G channel).
  - Their open issue: the first race's loading screen "whites out over time".
- **Ours:** the bounded ring `RSX_RT_READBACK_ASYNC=1` with `RSX_RT_READBACK_MAX_LAG=1`, plus NaN/zero rejection, is the
  same design with extra guards. **Nothing to adopt.** Their design independently supports "lag ≤ 1, then wait" as
  correct.
  - Their selection rule (*written this frame* and *small*) is simpler than ours. If our selection heuristic ever misses
    the exposure target, theirs is a reasonable fallback rule.

## 6. Render distance / LOD

- **Theirs (VERIFIED):** `port_vq_float` after the four float stores in `func_00360DD4`/`func_00360DD8`: lodBias `+off`,
  cullThreshold and shadowCullThreshold `×scale`, shadowFadeDistModifier `×scale`, **for every group and tier**.
  - Presets: enhanced = -1 / ×0.5 / shadow ×1.5; maximum = -2 / ×0.3 / ×2.
  - Cost at 30 fps (MEASURED-THEIRS): draws ×2-3, 24.2 fps for "maximum" without async recording; LOD offset alone free.
  - Baked `.spvs` visibility does not stop small objects.
- **Ours:** `mspr_dist_f` (`MSPR_LOD_BIAS`, `MSPR_CULL_SCALE`, `MSPR_SHADOW_FADE`, `MSPR_SHADOW_RANGE`) with
  `MSPR_DIST_GROUPS` (default object, dyn, world) after the Ultra "vehicles through terrain / white far objects" report.
  - Their "maximum" (all groups, ×0.3) is the configuration that showed the bug for us.
  - **Nothing to adopt.** One idea: a milder named preset (their "enhanced": -1, ×0.5, shadow ×1.5) might be a safer
    launcher "High" than our Ultra (-2, ×0.25).
- Anisotropic filtering: theirs honours `TEXTURE_CONTROL0` max_aniso plus a user minimum (+101 % far-ground
  sharpness, 2.4 % GPU). Ours already does (`rsx_vulkan_backend.c` ~6900).

## 7. Other things they fixed that we already have (VERIFIED by reading ours)

- RSX fragment R/H register aliasing (velocity buffer noise): ours `rsx_fp_decompiler.c` `fp_alias_slots`.
- GCM offset table kept in step on map/unmap: ours `cellGcmSys.c` (set/clear_offset_table).
- The dynamic-resolution corner sampling (`eng_surface_corner`): we turn the game's DRS off (`drs` patch), so not needed.
- Shader disk cache: ours `PS3RECOMP_SPIRV_CACHE=auto` + parallel replay. Their `__GL_SHADER_DISK_CACHE_SIZE` is a
  Linux-NVIDIA setting and does not apply.
- Decals and black boxes, far white objects, foliage "low fps": nothing in their code. Our decal-edge fix
  (`RSX_DECAL_EDGE`) and the fardist group change are ours alone.
- Frame interpolation (`PS3RECOMP_INTERP`, their own GPU Lucas-Kanade presenter, experimental, never judged by eye): we
  plan FSR 3.1 FG instead (docs/FRAMEGEN_PLAN.md), which has real motion vectors from our TSR path. Not worth adopting.
- Pad pressure fix (Apocalypse lesson: force 255 only when pressure is 0). Worth checking our `cellPad.c`
  (HYPOTHESIS: may still force <255 → full throttle on a part-pulled trigger). Not checked in this study.

## 8. Upgrading our ps3recomp pin toward v0.18.0?

- **No, not for these problems.** Their speed and correctness work is almost all in their own 1.5 MB patch, not in
  v0.18: x86 SPU_FLOAT_RZ (v0.18 has an arm64-only FPCR form), host lanes, usleep caps, the GCM/exposure fixes and the
  whole Vulkan engine work. Their APOCA_LESSONS.md, read against v0.18, lists items still missing upstream (Taskset2,
  MLAA save size, pad pressure, `CELL_VDEC_ERROR_FATAL`).
- Our `ps3recomp-vkgame` carries a large body of local, tested changes (LFQueue, WWS AOT, relocatable rejoin, our Vulkan
  renderer, D3D12). A rebase would be a large deliberate project with no identified gain for fps, shadows or exposure.
- Per AGENTS.md, keep `0fe7dbf5`. Port individual ideas, with tests, as listed above.

## 9. Proposed next steps (in order, each opt-in, each with its own tests and a bounded A/B)

1. `func_0037FB68` chase-spring cadence hook (`port-vkgame/main.cpp` + a lifted-patch tool beside
   `cam_patch_lifted.py`). Eye check at 45/60.
2. `PS3_USLEEP_CAP` in `sys_timer.c` + test; A/B A / SPIN_LR / SPIN_LR+cap50.
3. `PS3_SPU_FLOAT_RZ` in `spu_helpers.h` + lane enter/leave + an exactness test; offline WWS job replay; race A/B.
4. `PS3_SPURS_HOST_LANES=6` experiment in `cellSpurs.c` + concurrency test; one A/B on the user's CPU.
5. "Fixed 60" launcher choice (`60fps` patch, no vfps, pace 60); then the adaptive 1↔2 interval if 60 holds most of the
   time.
6. Optional: the LS-copy fast path, once the module is identified in our AOT set.

## 10. Commands used (read only)

```
gh repo clone SirTobyGirl/motorstorm-pacific-rift-pc D:/research/mspr-other/fork -- --depth 50
gh repo clone millennium-h4x0r/motorstorm-pacific-rift-pc D:/research/mspr-other/orig -- --depth 50
diff -rq orig/work fork/work
sha256sum fork/work/patches/ps3recomp.patch
```

Files read there: README.md, CREDITS.md, LICENSE, docs/{NOTES,UNCAPPED,BASELINE,RENDER_DISTANCE,APOCA_LESSONS,
CONTINUE,ROADMAP,FORK_CHANGES,TESTED_ON}.md, work/port/{main.cpp,port_patches.cpp,spu_fastpaths.c,CMakeLists.txt,
config.toml}, work/tools/{patch_lift.py,lift_spu.py}, and the cellSpurs, sys_timer, spu_helpers and rsx_draw_engine
hunks of work/patches/ps3recomp.patch.

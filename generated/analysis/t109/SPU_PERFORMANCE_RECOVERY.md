# T109: SPU performance recovery and optimization (2026-10-27, offline)

- **Worktree:** `ps3recomp-t109`, branch `agent/t109-spu-optimization`.
- **Base:** T106 `8f41c5c`, which contains T104 `d7fc0a9` and T102 `1e5d534`.
- **Commits:** 10 new commits, tip **`4a1ee48`**.
- **Not done:** no build, no launch, no merge, no push.
- **Ownership:**
  - `ListAgents` shows the peers motorstorm01-21 and motorstorm01-8d, both busy; there is no T108/T109 session.
  - Read only: T108 (`ps3recomp-t108`, `df00fa9`), T104 and T106 (reports, worktrees, patches).
  - The trial replay ran in a new scratch worktree (`scratch/t109/onto_t108`).

## Results

1. **Historical fixes are complete (VERIFIED):** every T79/T81/T82 SPU commit missing from the race lineage is now on the branch.
   - Already present before T109: the maxContention, five-lane and TLS fixes (T104/T106).
   - Added by T109: the relocatable WWS-job AOT chain (8 commits, applied cleanly onto `8f41c5c`).
2. **The AOT is build-ready, with no re-lift needed (VERIFIED offline):**
   - the 31 lifted modules plus registration compile against T109;
   - their disassembly is **32/32 identical** to T106's trial objects, which T106 matched to the run-validated T81C/T82B objects;
   - the missing `MSPR_WWS_AOT` CMake block is prepared as a patch.
3. **New concurrency finding: the SPURS admission rule differs from the real kernel (VERIFIED by code).**
   - Our coordinator **consumes** one `readyCount` unit per admission and **polls un-kicked workloads**. The SPURS1 kernel (RPCS3 `spursKernel1SelectWorkload`) does neither.
   - With five lanes, a workload kicked once gets one lane; the others only arrive by 1–16 ms polling.
   - This is the leading **HYPOTHESIS** for why T79E saw each job run ×2.1 slower and why five lanes may not pay off.
   - Added as an opt-in A/B arm (`PS3_SPURS_READY_LEVEL=1`). The default is byte-identical.
4. **PRE is still unexplained, so an opt-in syscall-time accumulator was added (`PS3_SC_WAIT_MS`).** It records per guest thread and per syscall without a line per call, so one run can show how much of tid 1's 114 ms PRE is sleeping.
5. **SPU job overhead is not the next big gain (VERIFIED microbenchmark).** Each async task dispatch costs about 0.1 ms on the caller (the 128 KB image hash dominates), about 2.7 ms per frame, or 1.2 %.
6. **No FPS figure exists.** Every gain claim is from older runs; one A/B decides (§7).

## 1. Historical commit inventory (`git merge-base --is-ancestor`, `git cherry -v 8f41c5c <branch>`)

| Original | Purpose | On the race lineage | T109 |
|---|---|---|---|
| `76d5ca1`, `6817933` | `SPURS_BUSY_MS` lane accounting; PM poll log throttle | patch-identical as `5fcb348`, `3bbeb5a` (T104) | present |
| `6c6f679` (≡ `01d9205`) | read maxContention from SP+112; `PS3_SPURS_GUEST_MAXCONT=1` applies it | `33df4f7` (T104). The original is not an ancestor; the patch is identical | present |
| `5b3b6bf` (≡ `d248709`) | five-lane safety: contention bytes under the lock-line lock, cap at 8 | `d7fc0a9` (T104) | present |
| `a80b794` | per-worker TLS for interpreter and diagnostic state | `a9679cc` (T106, one resolved conflict), plus `6be362a` | present |
| — | T106 four-race fix (`event_status` atomics, cross-image report, GCM block ring, event-flag directory) | `8f41c5c` | present |
| `ad69e8e` | microstep link writes the preferred word only (ISA) | missing | **`ff640c8`** |
| `54c06d2` | job spans `PS3_FTRACE_SPUJOB` (a dependency of `d1b4119`) | missing | **`efa22b4`** |
| `d1b4119` | relocatable WWS job AOT: `--reloc` lifter, dispatch-time rebase, fail-closed | missing | **`35b76b8`** |
| `8de3590` | AOT tests (selection, fallback, hardening) | missing | **`a31bd09`** |
| `0ab0d16` (≡ `0b0b89b`) | lifter: a switch entered by a conditional branch | missing | **`fb72655`** |
| `478aea3`, `bdf8224`, `88feeb5` | job-span corrections and `PS3_FTRACE_ARM`. This is the tracer every earlier AOT A/B used | missing | **`aa18dd1`, `cfaa50e`, `dc0af2d`** |
| T89B MFC fast path | uncommitted patches in `t89b-worktree`, unmeasured | not a commit | deferred |

- **Source of the 8 commits:** T106's `aot_feasibility/patches/0001–0008`, applied with `git am -3`. The only conflict there (in `spu_interp.c`) was already resolved, and it applied cleanly onto `8f41c5c`.
- **Superseded or duplicated:** none. Nothing unrelated was picked.

## 2. Five-lane correctness

T106 already covered the audit (four races fixed; `test_spurs_wws_stress`, 1.07 M jobs exactly once). It is not repeated here. New in T109:

| Item | Finding | Class |
|---|---|---|
| Admission: readyCount | `spurs_kernel_thread` decrements `wklReadyCount1[wid]` on every admission. Real SPURS1 treats it as a **level**: a workload is eligible while `readyCount != 0 && min(rc,8) + min(idleSpuCount,8) > contention`, or while it is signalled. The kernel never writes readyCount; the policy module maintains it with its own atomics, and the WWS PM's PUTLLC swaps that line | VERIFIED (code vs RPCS3) |
| Admission: un-kicked polling | A workload with readyCount 0 and no signal still runs, every 2^idle passes (1–16 ms). Real SPURS never runs it. With 5 lanes these runs waste host time (T106 item 2) | VERIFIED (code) |
| Consequence | A single kick (readyCount 1) gets one lane. Lanes 2–5 come only through polling, after a 1–16 ms delay. That could cancel most of the 5-lane gain | HYPOTHESIS (unmeasured) |
| wklFlag receiver | Modelled in neither rule | VERIFIED gap; impact unknown |

- **Change `df863f4`:**
  - `libs/spurs/spurs_admit.h` holds both rules as one pure function.
  - `cellSpurs.c` routes admission through it, and only the legacy rule decrements.
  - `PS3_SPURS_READY_LEVEL=1` selects the level rule.
- **Tests:**
  - `test_spurs_admit`: **9,123,840 cases, 0 failures.** Legacy equals the old inline expression exactly; level equals the RPCS3 rule; plus behavioural cases.
  - Existing fixtures under the level rule:
    - `test_spurs_wws_concurrency`: PASS, both modes.
    - `test_spurs_wws_stress`: PASS, 3 seeds × 40 rounds, both modes.
    - `test_spurs_wkl_maxcont`: **times out, as expected.** Its PM never sets readyCount and relies on un-kicked polling, which real SPURS would not run either (`logs/level__*.log`).
- **Runtime risk:** if MotorStorm's job manager also depends on polling, or on wklFlag, the level arm stalls. The A/B validity gates catch that (§7).

## 3. SPU job overhead (Phase 3)

**Per async task dispatch** (`cellSpursCreateTask` → `spu_workload_dispatch_async`, about 28 per frame; T98: 10,454 dispatches, 4 images). Measured with `tools/bench_task_dispatch.c` (`logs/bench_task_dispatch.txt`):

| Step on the calling PPU thread | Cost |
|---|---|
| FNV-1a fingerprint of the whole image (byte-wise) | 24 µs / 32 KB, **97 µs / 128 KB**, 386 µs / 512 KB |
| unconditional `dispatch HIT (async)` stderr line | 1.8 µs (redirected) |
| `CreateThread`, 256 MB reservation, detached | 8.3 µs |

- **Total:** about 0.1 ms per dispatch, about **2.7 ms per frame (1.2 %)** at 128 KB images. The image sizes in the race are not logged (HYPOTHESIS: 32–512 KB).
- **Possible fix, not implemented:** cache the fingerprint per (EA, size) with a write-generation check. The gain is small, and correctness depends on detecting self-modified images.
- **WWS job path:** job time is the dominant SPU cost, not dispatch (older lineage: 169 → 50 ms/frame with AOT).
- **No change needed:**
  - worker wakeup: condvar plus a 1 ms coordinator poll; a kick bypasses backoff;
  - MFC translation: inline;
  - completion signalling: PUT → counter, ordered (T106).

## 4. Relocatable SPU AOT readiness (Phase 4)

| Question | Answer | Class |
|---|---|---|
| Re-lift needed | **No.** `generated/spu_raw/wws_reloc_t81c` (31 modules) still matches the EBOOT (T106 `verify_wws_reloc` PASS) | VERIFIED |
| Compiles against the current runtime | `tools/aot_compile_check.cmd` with `TREE=ps3recomp-t109`: **35/35** (31 modules + register + 3 runtime TUs) | VERIFIED |
| Same code as the run-validated lift | `llvm-objdump -d` against T106 trial objects: **32/32 identical** (`logs/aot_disasm_vs_t106.txt`) | VERIFIED |
| Relocation / entry mapping | `spu_wws_register_pm(pm, 0x1320, 0x3214)`; the base comes from LS 0x1320; entry = base + header[0x10]; keys carry `SPU_RELOC_KEY_BIT`; unknown words hand off to the interpreter | VERIFIED (code, tests) |
| Offline tests | `test_spu_reloc_job`, `test_spu_lifter_reloc`, `test_spu_jobspan(_path)`, `test_spu_switch_linkret`: PASS | VERIFIED |
| Build integration | `port/CMakeLists.txt` lacks `MSPR_WWS_AOT`. The patch is `port/port_wws_aot.patch` (+20/−0, verbatim from `port-t70`, `tools/make_port_aot_patch.py`). Candidate file: `port/CMakeLists.txt` here. **`port/` itself is not modified** | PREPARED |
| Default behaviour | the option is OFF; even when built, nothing registers unless `PS3_SPU_WWS_AOT=1` | VERIFIED (code) |
| Expected gain | older lineage: WWS 169 → 50 ms/frame, 5.0 → 11.3 fps; renderablejob 22.5 → 8.3 ms/frame | VERIFIED there; HYPOTHESIS here |
| Risks | only base `0x4000` validated in game; non-DMA writes caught only with `_VERIFY=1`; **AOT + 5 lanes never run** | — |

## 5. Untraced PPU time (Phase 5)

- **What T106 already established:**
  - tid 1 is off-CPU for at least 68 % of PRE;
  - Havok tasks finish at 19 ms, then comes a 67 ms gap while the WWS workloads run on one lane;
  - the wait primitive is `func_004B63F0` (spin + `sys_timer_usleep(250)`).
- **What was missing:** a cheap way to measure the sleep without per-call records.
- **Change `4a1ee48`:** `include/ps3emu/sc_wait_acct.h`, hooked into the lv2 syscall guard in `ppu_loader.cpp`.
  - Output: `PS3_SC_WAIT_MS=<ms>` prints one line per thread per window, `[sc-wait] window_ms= tid= total_ms= sc141=ms/calls sc107=…`.
  - When unset: one cached getenv per syscall, and no clock read.
  - Test: `test_sc_wait_acct` (sums, overflow to `dropped`; 8 writers against a draining reporter conserve every call and every ns; exactly one window claim among 32 racers), PASS ×3.
- **Reading it per frame:** `tid=1 sc141 ms per window / guest frames per window` = sleep per frame. Compare with PRE (114 ms) and SPIN (40 ms; a pure busy loop, so not a syscall).
- **Not covered:** HLE-level waits that block without an lv2 syscall (sysPrxForUser lwmutex/lwcond fast paths). The race wait loop uses syscall 141, so it is covered.

## 6. Offline validation

- **Suite on `ps3recomp-t109`** (`tools/run_suite_t109.cmd`, `logs/suite_t109_final.txt`): **25 PASS, 8 SKIP (POSIX-only fixtures, as in T106), 0 FAIL.**
  - `test_spu_ls_alias` reports PASS but skipped internally.
  - Coverage:
    - the AOT set;
    - SPURS concurrency/stress/maxcont;
    - MFC resume, chain chunks, program pipeline, PPU trace;
    - renderer tests (vp_expand, vp_flush, rsx_frame_perf, rf_phase, geom_expand, prim_stream, draw_rejection, present_gate).
- **Admission modes:** legacy 4/4; level 2/3, with the `wkl_maxcont` timeout expected (§2).
- **TU compile** (`tools/tu_t109.cmd`, T96I exact flags): rc=0 for all 9 TUs:
  - `cellSpurs.c`, `spu_channels.c`, `spu_coherency.c`, `spu_drain.c`, `spu_interp.c`;
  - `cellGcmSys.c`, `lv2_register.c`;
  - `ppu_loader.cpp`, `ppu_trace.cpp`.
- **Warning classes:** no new classes against T106 on the shared TUs. The new lines in `ppu_loader.cpp` warn only in classes that file already has.
- **Public audit `--staged`:** no T109 file flagged. The 25 BLOCK items are files already in the tree.

## 7. Runtime A/B plan (one exe; not run)

1. **Build** once from the T108 replay (§8) or from `4a1ee48`:
   - configured like `build/motorstorm-t96i`, into `build/motorstorm-t109`, **AOT OFF**;
   - pin the SHA-256 of the exe.
2. **Runner:** T106 §5, unchanged:
   - `t106/run_t106.py` pattern;
   - a fresh private HDD copy for each arm;
   - the same race-entry sequence and inputs;
   - no target;
   - a 300 s cap.
3. **Identical environment in both arms:**
   - T106's set: `PS3_TRACE_FILE=…/t106/ab_fps_t106.cfg`, `SPURS_BUSY_MS=1000`, `RSX_FRAME_PERF=12,10`, `RF_PHASE_MS=200`, `PS3_PRESENT_DIAG_MS=5000`, `CELLMARK_DUMP_PRESENT_ONLY=1` …, `PS3_FC_WATCHDOG_MS=2000`;
   - **plus `PS3_SC_WAIT_MS=1000`**;
   - no `RSXI_*`, `TEX_SAVE` or `PS3_FTRACE`.
4. **Arms:**
   - **A:** default (maxContention 1, legacy admission).
   - **B:** A + `PS3_SPURS_GUEST_MAXCONT=1`.
   - Order A, B, then a second pair B, A for variance.
   - **Optional C**, only after B is valid: B + `PS3_SPURS_READY_LEVEL=1`.
5. **Validity gates:**
   - 4× `maxContention guest=5 applied=1|5`;
   - race entry reached;
   - jobs issued per frame `[rs+0x44C]` equal across arms;
   - no new `[fc-watchdog]`, `[spu-depth]`, `NOSYS`, LFQueue or VPVB errors;
   - for C: no workload left with `runs=0` in `[spurs-busy]`.
6. **Window:** race entry + 10 s to race entry + 80 s.
7. **Measures and their sources:**
   - **Elapsed (wall) time, the decision metric:**
     - guest fps (`0x72E1E0` / 70 s);
     - frame interval p10/p50/p90/p99;
     - PRE/EMIT/SPIN medians (`t104/tools/frame_phases.py`);
     - jobs done at spin entry.
   - **Aggregate CPU time, never added to elapsed time:**
     - `[spurs-busy]` busy_ms per lane, with runs and polled (lane occupancy = busy/window);
     - tid-1 CPU/wall from `performance.json` (PPU active against blocked);
     - `[sc-wait] tid=1 sc141` ms per frame (PPU sleep);
     - `[rsx-frame-perf]` / `[rf-phase]` (renderer).
   - **Separating the two:** B wins only if the **wall** frame interval drops. A drop in busy_ms or CPU time with an unchanged interval is a CPU saving, not a speed-up.
   - **Progress:** guest frames and the runner's race markers; presented dumps of the same content class.
8. **After that:**
   - if B > A, a separate AOT A/B (`PS3_SPU_WWS_AOT=1`, `_BASES=4000`, `_VERIFY=1`), then AOT + B;
   - if B ≈ A, run C to test the admission hypothesis (§2).

## 8. Integration relative to T108

- **T108 (`df00fa9`)** is T105 plus replays, including T107's `ec5cdb3`. It contains none of the T104/T106/T109 SPU commits.
- **A direct merge conflicts** in `rsx_d3d12_backend.c`. The cause is T104's T102 pick versus T105's re-pick, the same thing T106 found.
- **Integrate by replay.** Trial: `git cherry-pick -x 1e5d534..4a1ee48` (18 commits) onto `df00fa9` gives detached **`90951b9`** in `scratch/t109/onto_t108`.
  - **No conflicts.** No commit touches `rsx_d3d12_backend.c`.
  - Its suite: **25 PASS / 8 SKIP / 0 FAIL** (`logs/suite_onto_t108.txt`).
- **Order:** T108 first, then this replay, then (with build authorization) `port_wws_aot.patch`.
- **Shared file:** `cellGcmSys.c` (T106 block lock). It auto-merges.

## Remaining bottlenecks (ranked, all unmeasured on this lineage)

1. **WWS job execution on one lane:** EMIT + SPIN about 110 ms/frame. The targets are B, then AOT.
2. **The PRE gap (about 67 ms):** probably tid 1 waiting on SPU results. `PS3_SC_WAIT_MS` measures it.
3. **Admission polling latency with 5 lanes:** arm C.
4. **Task dispatch:** about 2.7 ms/frame. Low priority.

## Commits (`agent/t109-spu-optimization`)

| Hash | Content |
|---|---|
| `ff640c8`, `efa22b4`, `35b76b8`, `a31bd09`, `fb72655`, `aa18dd1`, `cfaa50e`, `dc0af2d` | the AOT chain (originals `ad69e8e`, `54c06d2`, `d1b4119`, `8de3590`, `0ab0d16`, `478aea3`, `bdf8224`, `88feeb5`) |
| `df863f4` | opt-in readyCount-level admission and `test_spurs_admit` |
| `4a1ee48` | `PS3_SC_WAIT_MS` and `test_sc_wait_acct` |

**Analysis files (`generated/analysis/t109/`):**
- `tools/run_suite_t109.*`, `run_spurs_modes.cmd`, `make_tu.py` → `tu_t109.cmd`, `aot_compile_check.cmd`, `make_port_aot_patch.py`, `bench_task_dispatch.c`;
- `port/`;
- `logs/`.

# T104: Race frame critical path

- **Worktree:** `ps3recomp-t104`, branch `agent/t104-frame-critical-path`, based on T102 `1e5d534`, which includes T99 `db2aa90` and T96 `bd09877` (T96 is tree-equal to T96I `95a906d`).
- **Commits:** `5fcb348`, `3bbeb5a`, `33df4f7`, `d7fc0a9`. These are `git cherry-pick -x` of `76d5ca1`, `6817933`, `6c6f679` and `5b3b6bf`.
- **Not done:** no merge, no push, no build, no launch.
- **Ownership:** peers are motorstorm01-8d (T101) and Motorstorm05 (T103). No other T104 or synchronization owner exists; `agent/sync-correctness-audit` is old and has no live session. T100 and T103 were not touched.

## 1. Frame dependency graph (T98 run `20261027-111836-t98-visible-race`)

**Source:** PT trace sites on the guest frame thread (tid 1):
- `72E1E0`: ref throttle;
- `50D868` / `757028`: ExecutePushBuffer / CALL emit;
- `50C818`: frame-end spin on SPU jobs (`[rs+0x44C]` issued against `[rs+0x2560]` done);
- `736770`: PUT flush.

The analyzer is `tools/frame_phases.py`; its output is `logs/frame_phases_t98.txt`. It covers 354 race frames between 206 s and 299 s.

```
guest frame thread (PPU, tid 1) ─ serial ─────────────────────────────────────────────────────────────────►
 [ref throttle 0.0 ms] → [PRE 116 ms: untraced PPU work] → [EMIT 72 ms: 21 ExecutePushBuffer → 21 SPU jobs]
                      → [2.7 ms] → [SPIN 40 ms: wait until all 21 SPU jobs are done] → PUT flush → next frame
                                          │ jobs issued                       ▲ completion counter
                                          ▼                                   │
SPURS Wws_Job workloads (SPU, lifted) ── maxContention forced to 1 = one lane per workload ──┘
                                          │ push buffers in guest memory
                                          ▼
frame clock thread: FIFO drain → VP expansion → D3D12 record/submit/present  (consumes asynchronously;
                    the guest never waits for it: ref wait = 0.0 ms in p10/p50/p90)
```

| Phase per guest frame | median | mean | share | Status |
|---|---|---|---|---|
| Frame interval | 228.2 ms | 231.7 ms | 100% | VERIFIED |
| RSX ref-counter wait (`72E1E0`) | 0.0 | 0.0 | **0%** | VERIFIED |
| PRE: throttle exit → first ExecutePushBuffer | 113.6 | 116.5 | 50.3% | VERIFIED duration. Content unknown: PPU compute and/or waits under 250 ms on other workloads (physics/pvs WWS) |
| EMIT: 21 ExecutePushBuffer calls, about 3–8 ms apart | 69.8 | 71.5 | 30.8% | VERIFIED |
| SPIN: frame-end wait for SPU jobs (21 issued, **2–3 done at entry**) | 40.0 | 40.0 | 17.3% | VERIFIED |

**Conclusions:**
- **VERIFIED:** the renderer (T99/T102 territory) is **not** on the guest's critical path. The game never waits for the RSX ref counter, so T102's savings cannot raise guest fps directly.
- **VERIFIED (code + T79):** `_cellSpursWorkloadAttributeInitialize` receives maxContention as its 9th argument, on the stack. The 8-GPR binding in this lineage never reads it and stores 1. MotorStorm requests **5** for all four Wws_Job workloads (T79 §2, static proof).
- **HYPOTHESIS, strongly supported:** the forced single lane makes push-buffer jobs complete one at a time. 21 jobs over EMIT + SPIN (about 112 ms) is about 5.3 ms each, and only 2–3 are done 72 ms after the first was issued.
- **Earlier runtime evidence (T79E, older pre-geometry lineage, one session):**
  - contention 5 against contention 1: 8.93 fps (+71%), p50 112.3 ms (−41.5%), PPU wait −43%;
  - job counts per flip unchanged, 0 errors;
  - each job about 2.1× longer under host contention.
- **VERIFIED (git):** the race lineage (T84 → T96I → T98) forked at `c529ab0`, **before** the T79/T81/T82 SPU work. 13 commits are missing, including the maxContention pass-through, the five-lane safety fix, relocatable WWS job AOT (`d1b4119`; T82B: renderablejob 22.5 → 8.3 ms/frame) and per-worker diagnostic TLS (`a80b794`).

**Other stages checked:**

| Stage | Finding | Status |
|---|---|---|
| Frame pacing | `timeBeginPeriod(1)` set (`port/main.cpp:420`). The frame clock is a 59.94 Hz deadline poll with `Sleep(4)`. The guest is not paced by vblank waits in the race (ref wait 0, and no syscall ≥ 250 ms on tid 1) | VERIFIED |
| Host CPU | 2.8 cores busy. Busiest threads at 75%, 70% and 33%; none saturated | VERIFIED |
| SPURS task dispatch | about 108 async dispatches/s (about 28 per frame), each a new host thread (256 MB reserve) plus a fresh 256 KB LS and an ELF load. They run concurrently, and the cost is on the order of 0.1–0.3 ms each | VERIFIED count, HYPOTHESIS cost |
| `LBP_SPU_SERIAL` / `LBP_PERSIST_LS` | both off by default, so no global SPU serialization | VERIFIED |
| PM poll logging | 842 `[spurs-pm] poll` stderr lines/s in this lineage (the counter restarts every PM run). Throttled by cherry-picked `5fcb348` | VERIFIED |

## 2. Implemented (cherry-picks, unchanged code)

| Commit | Content | Default behaviour |
|---|---|---|
| `5fcb348` (`76d5ca1`) | `SPURS_BUSY_MS=<ms>`: per-workload, per-lane policy-module busy time and lane thread ids; PM poll log throttled | unchanged except much less stderr |
| `3bbeb5a` (`6817933`) | `SPURS_BUSY_MS` per instance and lane | off unless set |
| `33df4f7` (`6c6f679`) | Reads maxContention from SP+112 and logs `guest=… applied=…`. **`PS3_SPURS_GUEST_MAXCONT=1` applies the guest's value**; unset stores 1 as before | unchanged |
| `d7fc0a9` (`5b3b6bf`) | Five-lane safety: `cellSpursAddWorkload` contention bytes written under the lock-line lock; maxContention capped at `CELL_SPURS_MAX_SPU` | correctness fix, scheduling unchanged |

**Why the default stays at 1:**
- The race-geometry lineage has never run with contention 5.
- Keeping the switch opt-in gives a **single-executable A/B**.
- Making the guest value the default is a one-line follow-up once the A/B passes.

**What these changes do not touch:**
- No guest wait was removed or shortened.
- Admission still requires `active < maxContention`.
- The guest's own requested value is what gets restored.

## 3. Offline results

| Test | Result |
|---|---|
| `test_spurs_wkl_maxcont` (default + guest: 1–5 → peak 1–5 lanes, unaligned SP, unbacked slot, 0/9/256 clamps, priority-0 lane, two instances, BUSY finalize, LS isolation) | PASS |
| `test_spurs_wws_concurrency` (5 lanes on one list through the real coordinator and MFC atomics: 900 jobs each exactly once, results visible before completion bits, PUTLLC retries under peer/PPU writes, readyCount races, shutdown mid-job, priority change, two instances; **1 and 5 leave byte-identical guest state**) | PASS, **6 of 6 runs** (`logs/wws_concurrency_repeats.txt`) |
| SPU/MFC regressions (`test_mfc_resume_elements`, `spu_chain_chunks`, `spu_program_pipeline`, `spu_ls_alias`, `ppu_trace`) plus the renderer set (`vp_expand`, `rsx_frame_perf`, `vp_flush`, `rf_phase`, `geom_expand`, `prim_stream`, `draw_rejection`, `present_gate`) | **15 PASS / 8 SKIP (POSIX-only fixtures) / 0 FAIL** (`logs/suite_t104.txt`) |
| Exact T96I build lines (`build/motorstorm-t96i` ninja) for `cellSpurs.c`, `ppu_sysprx.cpp`, `spu_channels.c` and `rsx_d3d12_backend.c` | all rc=0. Warnings on changed lines are only kinds already present in the file (`logs/tu/`, `tools/tu_t104.cmd`) |
| `audit_public.py --tree` | same BLOCK set as T102. One untracked `__pycache__` from the test run was removed |

## 4. Estimated benefit (UNVERIFIED)

- If push-buffer jobs run on up to 5 lanes, EMIT + SPIN (about 112 ms) could shrink to roughly 40–60 ms, allowing for T79E's ×2.1 per-job slowdown under contention.
- PRE may also shrink if it waits on the other Wws_Job workloads (pvs, vehicle physics).
- Rough range: from 231 ms to **about 150–180 ms per frame (about 5.5–6.5 fps)**.
- This is not a measured result. T79E's +71% came from a different lineage and scene.

## 5. Remaining hypotheses and next steps

1. **Contents of PRE (50% of the frame):** PPU compute or untraced waits. The A/B below lowers `sc_min_us` to see waits of 1 ms or more on tid 1.
2. **Relocatable WWS job AOT** (`d1b4119`, plus `0ab0d16` and `a80b794`): it needs the lifter rerun (`tools/lift_wws_reloc.py`) and a full build, which this task is not authorized to do. It is the next integration step after the A/B.
3. **T89B MFC fast path:** uncommitted patches in `Motorstorm01/t89b-worktree`. Still unmeasured in-game.
4. **Per-dispatch thread creation for SPURS tasks:** a worker pool would be a moderate change with its own lifetime risks. Measure first (`SPURS_BUSY_MS`, thread counts).

## 6. A/B procedure (one build, two launches; needs authorization)

1. **Build:**
   - Build `agent/t104-frame-critical-path` (`d7fc0a9`) once, the same way as T96I (`build/motorstorm-t96i` configuration), into a new build directory.
   - Do not reuse T98's exe or run directory.
2. **Runner:** `generated/analysis/t98/run_t98.py`, copied to t104, with the same race-entry sequence, intro-skip check, 300 s hard cap and no target.
3. **Environment common to both arms:**
   - `PS3_TRACE_FILE=generated/analysis/t98/pb_stall_t98.cfg`, the same PT sites; a copy with `sc_min_us=1000` is optional for PRE;
   - `SPURS_BUSY_MS=1000`;
   - `RSX_FRAME_PERF=12,10`;
   - `RF_PHASE_MS=200`;
   - frame dumps exactly as in T98.
4. **The two arms:**
   - **A:** the common environment.
   - **B:** A plus `PS3_SPURS_GUEST_MAXCONT=1`.
   - Run order: A then B, on the same machine with nothing else running.
5. **Validity gates:**
   - stdout shows 4× `maxContention guest=5 applied=1` (A) or `applied=5` (B);
   - race entry is reached;
   - no `[VPVB] draw REFUSED`;
   - no crash or watchdog report.
6. **Compare:**
   - guest fps (`0x72E1E0` entries per second, 206–298 s);
   - `frame_phases.py` p10/p50/p90 of T, PRE, EMIT and SPIN;
   - `done` at spin entry;
   - per-lane busy (`SPURS_BUSY_MS`);
   - per-thread CPU (`performance.json` samples);
   - `[rsx-frame-perf]` lines;
   - job counts per frame (they must match between arms);
   - SPU/sync errors (`NOSYS`, `REFUSED`, LFQueue);
   - visual: the race frame dumps must be identical in content class (T100 owns the black-display question).
7. **Decision rule:** if B is faster with equal per-frame job counts and no new errors, make the guest value the default. Then integrate `d1b4119` (relocatable AOT) in a separate task.

## 7. Integration dependencies

- **T100 (black race display):** independent; touches the display chain only. T104 adds SPURS/SPU changes plus T102's renderer changes. Merge order: T100, then T104 (rebase, then rerun `run_suite_t104`).
- **T102:** included (`1e5d534` is T104's base).
- **T103:** independent. It touches `create_window` and RSXI texture records, and possibly `vp_root_sig` later; no overlap with T104's SPURS files.
- **T79/T81/T82/T89 lineage:** T104 brings over only the maxContention, lock and busy-accounting commits. The other 9 missing commits remain (§5.2).

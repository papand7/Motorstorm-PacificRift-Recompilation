# T106: SPU parallelism and critical path (2026-10-27, offline)

**Result:**
- The five-lane path (`PS3_SPURS_GUEST_MAXCONT=1`) is ready for a runtime A/B after two steps:
  - the missing per-worker TLS fix from T81 (`a80b794`);
  - four race fixes found by an audit of shared SPU state.
- All of this is covered by new offline stress and regression tests.
- **No FPS gain is measured.** Nothing was built, launched, merged or pushed.

**Commits.** `ps3recomp-t106`, branch `agent/t106-spu-performance`, on T104 `d7fc0a9`:

| Commit | Content |
|---|---|
| `a9679cc` | cherry-pick of `a80b794`: per-worker TLS for interpreter and diagnostic state |
| `6be362a` | `test_spu_diag_tls` made standalone (the original needed the AOT fixture) |
| `5e5666d` | `test_spurs_wws_stress` (new) |
| `8f41c5c` | four race fixes + `test_spu_event_lr_race` |

- **Also:** branch `agent/t106-spu-on-t105` = `092ab23`. These are the same 8 SPU commits (`5fcb348`…`8f41c5c`) replayed onto T105 `36d0fb7`, conflict-free (worktree `scratch/t106/onto_t105`).

## 0. Ownership
- **Peers:**
  - motorstorm01-21 (busy);
  - Motorstorm05 (T103, idle).
- **Ownership:** no other T106. The T103 and T105 worktrees were not modified; T105 was only read and test-merged with `git merge-tree`.

## 1. Missing T79/T81/T82 commits (`git cherry d7fc0a9 <branch>` against t79, t81, t81c, t82, t89, t89b; fork point `c529ab0`)

| Commit | Content | Class | T106 decision |
|---|---|---|---|
| `76d5ca1`, `6817933`, `6c6f679`, `5b3b6bf` | busy accounting, maxContention pass-through, five-lane lock | perf / logging / concurrency | already in T104 as `5fcb348`/`3bbeb5a`/`33df4f7`/`d7fc0a9` (patch-identical; `01d9205`/`d248709` on t79 are the same patches) |
| **`a80b794`** | thread-local `g_spu_interp_*`, call-trace ring, `spu_depth_guard` state; atomic one-shot report | **concurrency safety** (needed for 5 lanes of one PM) | **applied** (`a9679cc`; one conflict, resolved without T81's job-span counter) |
| `ad69e8e` | microstep link writes preferred word only (ISA) | correctness (interpreter r126 words 1–3) | not applied here. It is the first patch of the AOT series (§4); its only test comes with `d1b4119` |
| `54c06d2`, `478aea3`, `88feeb5` | PS3_FTRACE_SPUJOB job spans | logging (`54c06d2` is a build dependency of `d1b4119`) | with the AOT series |
| `bdf8224` | PS3_FTRACE_ARM | logging | with the AOT series (optional) |
| `d1b4119`, `8de3590` | relocatable WWS job AOT + tests | performance (opt-in) | §4, needs build authorization |
| `0ab0d16` ≡ `0b0b89b` | lifter: switch entered by a conditional branch | correctness of the AOT lift | with the AOT series |
| T89B MFC fast path | uncommitted patches in `t89b-worktree` | performance | not touched (unmeasured, not a commit) |

**maxContention dependencies:**
- `6c6f679` needs `5b3b6bf` (the lock) and `a80b794` (shared diagnostic state, now applied). It does not need the AOT chain.
- `spurs_guest_maxcont_enabled` and the attribute read stand alone.

## 2. Five-lane correctness

**Review sources:**
- the scheduler code: coordinator and worker lifecycle in `cellSpurs.c:1770-1963`;
- a read-only audit of all mutable shared SPU state.

**The audit's findings:**

| # | Finding | Status | Action |
|---|---|---|---|
| 1 | The owning lane's `event_status` read-modify-writes (tag update `spu_channels.c:952`, SN `spu_dma.h:815`, LR poll `:1070`) take no lock, while peers raise LR under the lock-line lock. A lost LR after `resv_valid=0` cannot be re-raised | **PARTIAL**: real data race by construction. Not reproduced: 0 losses in 3×10⁶ rounds unfixed (`logs/lr_race_unfixed.txt`); the window is one x86 `or [mem]` | fixed: all writers atomic (`8f41c5c`), regression test added |
| 3 | `spu_report_cross_image`: two lanes pass `n_seen<64` and write `seen[64]` (out-of-bounds write) | VERIFIED by code | fixed (CAS slot claim) |
| 4 | `cellGcmSys.c` SPU pushbuffer block ring, fed by every SPU PUT (`g_spu_put_hook`) and read on FIFO resync: unlocked | VERIFIED by code | fixed (SRW lock) |
| 5 | event-flag sync slots: `ef_sync_get` from concurrent lanes can initialize one slot twice. Re-Initialize can delete a CS while the PUTLLC commit hook enters it | VERIFIED by code | fixed (directory lock, never taken under a slot lock) |
| 2 | **Admission semantics:** an un-kicked workload with `idle==0` is admitted on every free lane, and `readyCount` is decremented per admission (real SPURS does not decrement). With 5 lanes, contention stays near 5, polling PM runs burn host CPU, and Finalize/RemoveWorkload mostly return BUSY | VERIFIED by code; impact HYPOTHESIS. It may explain T79E's ×2.1 per-job slowdown | **not changed** (scheduling). Measure in the A/B (`SPURS_BUSY_MS` `polled=`); resolve before making 5 the default |

- **Diagnostic-only races (left as they are):** `g_spu_putllc_count`/`_sync_hit`, `g_spurs_job_last_ea`, the `PS3_LOG_FIRST` counters.
- **Verified safe:**
  - the function and overlay registries (constructor-filled);
  - per-(ea, wid, lane) PM contexts;
  - MFC slots;
  - reservation bitmap and holders under the lock-line lock;
  - PUT → completion ordering;
  - the scheduler under `si->lock`;
  - stop/Finalize joins.
- **No lost wakeup:** the coordinator polls every 1 ms, `api_unlock` wakes it, and a kick bypasses idle backoff.

**Tests** (logs in `logs/`):

| Test | Result |
|---|---|
| `test_spurs_wws_stress`, **12 seeds × default and guest × 60 rounds** | **PASS 24/24 runs, 1,440 churn rounds, 1,067,086 jobs exactly once**, 717,023 PUTLLC retries (races exercised) (`stress_12x60.txt`) |
| (same) per-run content | Lifecycle churn (Initialize 1–5 SPUs); peak ≤ min(lanes, SPUs) and `wklCurrentContention` 0 after Finalize. 1 vs 5 lanes **byte-identical** on seeded lists. Saturation (255 ready units, 1 job/run): peak = cap. **9,280 live-list extensions, none lost** (worst kick→done 17 ms at default timer resolution). Recovery: unlifted PM never admitted; double Init/Finalize refused; re-Init at the same EA; second instance |
| Mutation checks | admission cap `>=`→`>`: caught in both modes. PUTLLC without the reservation check: caught (guest mode times out). PUTLLC without the compare only: **not caught**, because LR notification already clears `resv_valid` |
| `test_spurs_wws_concurrency` ×20 repeats | **20/20 PASS**, default and guest each time (`logs/wws_conc_*.txt`; T104 had 6/6) |
| `test_spu_diag_tls` | PASS ×3 (five lanes; does not compile against the pre-fix tree) |
| `test_spu_event_lr_race` | PASS, 200,000 kills with 0 losses (non-discriminating; see item 1) |
| Suite on `ps3recomp-t106` | 19 PASS / 9 SKIP (POSIX-only) / 0 FAIL (`suite_t106.txt`). `test_spu_program_pipeline` first failed on an `SRWLOCK` in its `spu_channels.c` excerpt; fixed (lock-free) |
| SPU set on `agent/t106-spu-on-t105` | 11/11 PASS (`suite_onto_t105.txt`) |
| Changed-file compiles with T96I's exact flags (cellSpurs, spu_channels, spu_coherency, cellGcmSys, spu_drain, spu_interp, lv2_register) | all rc=0. Only header warnings that already existed (`logs/tu/`, `tools/tu_t106.cmd`) |
| `audit_public.py --tree` (changed files) | passed |

**Residual risk:**
- The stress uses a manufactured PM, not MotorStorm's Wws PM or jobs.
- Rare interleavings inside lifted game SPU code cannot be excluded offline. The A/B must check job counts and errors.

## 3. PPU cost in PRE (`ppu/PRE_PHASE_ANALYSIS.md`)
- **Frame ID** is the index of the tid-1 `0x72E1E0` entry. The race window is IDs 1046–1446.
- **T98 cannot see waits (VERIFIED):**
  - `sc_min_us=250000` gives 0 syscalls on tid 1;
  - `hle=` covered only save-data and LFQueue functions.
- **tid 1 is off-CPU for at least 68% of PRE (PARTIAL, strong):**
  - tid 1 CPU is 0.329 of wall time (76 ms per 231 ms frame);
  - SPIN is a pure busy loop (40 ms, VERIFIED from the lifted code);
  - that leaves at most 36 ms CPU for PRE + EMIT (187 ms wall).
- **Ruled out:**
  - PPU compute as the main content;
  - memory translation (inline; VERIFIED);
  - CPU saturation (2.8 of 12 CPUs; HYPOTHESIS: no ready-time data).
- **Structure (VERIFIED order):**
  - Havok solver/collide/raycast tasks run 0–19 ms;
  - then a gap with no Havok (median 67 ms) while the SPURS job workloads keep running on one lane each;
  - then animation tasks, and EMIT about 29 ms later;
  - PRE's frame-to-frame variance sits in the gap (r = 0.48).
- **Wait primitive (VERIFIED in code):** `func_004B63F0` spins, then `sys_timer_usleep(250)`, and is used by the game's condvar `Wait` `0x94CC80` (returns at `0x94CCA8`).
- **Working model (HYPOTHESIS):** PRE is about 70–90 ms of tid 1 sleeping on SPU-produced results. If so, more lanes also shorten PRE.
- **Instrumentation (configuration, no source change):**
  - `ppu/pre_split_t106.cfg`: return sites of the race main loop `func_00082688`, `sc_min_us=200`, `hle_min_us=200`, the condvar wait sites;
  - `ppu/pre_split.py` splits PRE per frame; it reproduces T104's median of 113.6 ms on the T98 log.
- **Source proposals, not implemented:**
  - a `cpu=1` thread-cycle stamp;
  - per-thread wait accumulators;
  - tid-1 host thread id logging;
  - Havok busy records.
- **T98's cfg was heavy (PARTIAL):** `bb=` + `stall=` hooked every branch target (about 28M hooks/s on tid 1). T98 frame times may be inflated, so the A/B below does **not** use that cfg.

## 4. Relocatable SPU-job AOT (`AOT_FEASIBILITY.md`, patches in `aot_feasibility/patches/0001–0008`)
- **Applies (VERIFIED):**
  - order: `ad69e8e`, `54c06d2`, `d1b4119`, `8de3590`, `0ab0d16` (plus optional `478aea3`, `bdf8224`, `88feeb5`);
  - one trivial conflict in `spu_interp.c`;
  - the series also applies to `6be362a`, so a rebase onto `8f41c5c` is expected to be trivial (not yet done).
- **No re-lift (VERIFIED):**
  - `generated/spu_raw/wws_reloc_t81c` (31 modules: renderablejob, pvsjob, vehiclephysics, …) is byte-identical to the run-validated t82 lift and comes from the same EBOOT;
  - the lifter blob is unchanged;
  - 35/35 lifted files compile against the trial tree with T96I flags (32/35 fail on unmodified t106).
- **Build:** `port/CMakeLists.txt` lacks the 20-line `MSPR_WWS_AOT` block from `port-t70` (lines 203–222). Use a private `port-t106` copy with the T81C configure line.
- **Risks:**
  - only `PS3_SPU_WWS_AOT_BASES=4000` was validated in-game (non-zero deltas are synthetic only);
  - writes that don't come from DMA are caught only with `_VERIFY=1` (about 0.5 ms/frame);
  - AOT together with contention 5 has never run.
- **Savings (older lineage, VERIFIED there):**
  - T70: WWS job time 169 → 50 ms/frame, 5.0 → 11.3 fps;
  - T82B: renderablejob 22.5 → 8.3 ms/frame, p50 −10 to −14%.
- **Plan (each step needs authorization):**
  1. commit the series on T106;
  2. offline suite;
  3. `port-t106` + configure;
  4. one build;
  5. A/B with AOT off/on (`_VERIFY=1`, `_BASES=4000`);
  6. only then AOT + contention 5.

## 5. Runtime A/B (two launches of one exe; needs build + launch authorization)
1. **Build** once, from `agent/t106-spu-on-t105` (`092ab23`; it has the T105 renderer stack and T100's `CELLMARK_DUMP_PRESENT_ONLY`):
   - configuration as `build/motorstorm-t96i`, into a new `build/motorstorm-t106`;
   - pin the SHA-256 of the exe;
   - WWS AOT off.
2. **Runner:** copy `t98/run_t98.py` (or `t105/run_t105.py`) to `t106/run_t106.py`. Keep:
   - the exe pin;
   - a **fresh private HDD copy for each arm** from `generated/hdd0`/`hdd1` (`copy_tree_verified`);
   - the same race-entry sequence and `PS3_DEV_SKIP_INTRO` check (`last_draws` 21 → 42);
   - no target;
   - a 300 s cap.
3. **Environment, identical in both arms:**
   - the runner's base set;
   - `PS3_TRACE_FILE=generated/analysis/t106/ab_fps_t106.cfg` (only `72E1E0`/`50D868`/`50C818`/`736770`; no `bb`/`stall`/`ret`);
   - `SPURS_BUSY_MS=1000`, `RSX_FRAME_PERF=12,10`, `RF_PHASE_MS=200`;
   - `PS3_PRESENT_DIAG_MS=5000 PS3_PRESENT_DIAG_MAX=64`;
   - `CELLMARK_DUMP=6 CELLMARK_DUMP_EVERY=200 CELLMARK_DUMP_MINDRAWS=200 CELLMARK_DUMP_PRESENT_ONLY=1`;
   - `PS3_FC_WATCHDOG_MS=2000`;
   - **no** `RSXI_*`, `RSX_RT_READBACK`, `TEX_SAVE`, `PS3_FTRACE`.
4. **The two arms:**
   - **A:** the environment above.
   - **B:** A plus `PS3_SPURS_GUEST_MAXCONT=1`.
   - Order A then B, same machine, nothing else running.
   - Optional second pair (B then A) to bound run-to-run variance.
5. **Validity gates:**
   - stdout shows 4× `maxContention guest=5 applied=1` (A) or `applied=5` (B);
   - race entry is reached;
   - no `[VPVB] draw REFUSED`, `[fc-watchdog]`, `[spu-depth]`, crash, `NOSYS` or LFQueue error that is new against the other arm.
6. **Race window:** **race entry + 10 s through race entry + 80 s**. Race entry is the first `0x72E1E0` with ≥ 200 draws, i.e. the first race frame. Loading and startup are excluded, and both windows have equal length whatever the entry time.
7. **Measurements:**
   - **guest fps:** `0x72E1E0` entries / 70 s;
   - **frame intervals:** p10/p50/p90/p99, plus PRE/EMIT/SPIN medians (`t104/tools/frame_phases.py`);
   - **jobs:** issued per frame `[rs+0x44C]`, and done at spin entry `[rs+0x2560]`. **Issued per frame must match between arms**;
   - **lane occupancy:** `[spurs-busy]` `busy_ms/window_ms` per sn and wid, with `runs` and `polled`. Polled runs in B measure the §2 item 2 cost;
   - **PPU:** tid 1 CPU/wall from `performance.json`, giving active against blocked;
   - **renderer:** `[rsx-frame-perf]`, `[rf-phase]`, `[present_diag]` ok/replays;
   - **progress:** guest frames in the window and the runner's race markers;
   - **presented dumps:** same content class in both arms.
8. **Decision:**
   - If B has higher fps with equal jobs per frame and no new errors: next comes the §2 item 2 review, then default = guest value, then the §4 AOT A/B.
   - If B is not faster: the PRE split run (`ppu/pre_split_t106.cfg`, separate launch) decides where the time goes.

## 6. Integration relative to T105 (`agent/t105-renderer-integration`, `36d0fb7`)
- T105 does not contain T104. A direct merge of T106 conflicts in `rsx_d3d12_backend.c`, because T105 re-picked T99/T102 as `470785e`/`4d7e84c`, which are not patch-identical.
- **Integrate by replaying T106's 8 SPU commits onto T105.** Done as `agent/t106-spu-on-t105` (`092ab23`): no conflicts, and the SPU/SPURS/renderer subset passes.
- **Shared file `cellGcmSys.c`:** T105 adds 8 lines and T106 adds the SPU block lock. They auto-merge.
- **Order:** T105 first, then the T106 SPU series, then (after authorization) the AOT series and the `port-t106` CMake block.

## Remaining uncertainties
- No in-game measurement of any T106 change.
- The admission/readyCount semantics with 5 lanes (§2 item 2).
- The contents of the PRE gap, which are indirect only.
- AOT under contention 5.

# T193 in-game dispatch profiling protocol (prepared, NOT executed; needs separate explicit authorization)

Purpose: measure whether MotorStorm's SPU indirect branches are mostly eligible for the T192 fast path, and whether dispatch is a meaningful share of SPU time, **before** spending launches on a P/C/P/C timing A/B. It is a counting experiment; it yields no FPS or frame-time claim.

## Build (one new executable; T190's is not touched)

- Code: the T190 game tree (inline stores compiled in, as built by T190) + the T193 runtime (`72e1001d`), compiled with `-DSPU_IB_FAST_STATS`. No relift, no lifted-code change. Use the T183 `build_tNNN.cmd` recipe into a new directory (`build/motorstorm-t193c`), about 11 minutes with 6 jobs. Record the SHA-256; compare it with T190's `9e77bd4b...f8453` to prove they differ and T190's file is unchanged.
- `build/motorstorm-t190`, `generated/analysis/t190/ab/run_t190.py` and its environment stay untouched; the profiling runner is a copy (`generated/analysis/t193/ab/run_t193c.py`) that only adds the environment below and a different output directory.

## Conditions

Local Windows console session (not RDP), Godot and other GPU/CPU workloads closed, the T190 preflight (session type, idle GPU, free disk, warm shader cache from the established race configuration: `RSX_SHADER_CACHE=3` with the cache populated by a previous run). Same race and track as T184/T190, race + 75 s, then the runner stops the process (forced termination is expected and supported).

## Runs (at most 3 launches)

| Run | Environment on top of T184 arm P | Purpose |
|---|---|---|
| C1 | `PS3_SPU_IB_FAST=1 PS3_SPU_IB_STATS_INTERVAL_MS=1000 PS3_SPU_IB_STATS_FILE=<run dir>/ibstats.txt PS3_SPU_IB_STATS_OBS=64` | main counting run, low observation cost |
| C2 | as C1 with `PS3_SPU_IB_STATS_OBS=1` | exact overlapping observations (state composition); only if C1 passes its sanity checks |
| C0 | as C1 with `PS3_SPU_IB_FAST_RELOC=0` | optional: share served by the T192 relocatable extension vs T191 |

Do not combine with `PS3_SPU_MFC_FAST`, `PS3_VM_STORE_INLINE`, or the T190 arms. Keep `[spu-task-stats]` / `[rsx-frame-perf]` on as in T184 so phases can be joined by `mono_ns` / log order.

## Analysis (`generated/analysis/t193/tools/analyze_ibstats.py`, to be written with the run; it reuses the checker of `tools/test_spu_ib_telemetry.py`)

1. Integrity: every complete line passes the invariants (seq contiguous, sums, deltas); count `consistent=0` lines; ignore a trailing partial line.
2. Phases: split the interval lines into loading (before the race-start marker in the log) and racing (the T190 measurement window).
3. Per phase, from the `dlt.*` sums:
   - eligible share `E = (hit + fill) / branches`; relocatable share `s_hit_reloc / hit`;
   - refusal mix: `d_policy`, `d_irq`, `d_task`, `d_unresolved`, other, each / branches;
   - miss composition: `p_conflict` (cache too small?), `p_epoch` (registrations during the race?);
   - branch rate `R = dlt.branches / dt_ms` per second, and per live thread (`thr_live`).
4. Dispatch share of SPU time, an upper-bound estimate: `R x c_resolver / SPU_busy`, with `c_resolver` from the offline benchmark for the observed mix (about 6-15 ns per branch on this machine, `PERFORMANCE_RESULTS.md` of T192/T193) and `SPU_busy` the summed SPU host-thread CPU per second from `[spu-task-stats]` / `cpu.jsonl`. And the best-case saving `S = R x E x (c_resolver - c_fast)` in ms per second (about 1-5 ns per eligible branch). Both are estimates and are labelled HYPOTHESIS in the report; the stats build itself adds about 1-3 ns per branch, which inflates measured SPU time slightly.

## Decision rule for the subsequent P/C/P/C timing A/B

Proceed to a timing A/B (normal build, no stats; arms P and C = P + `PS3_SPU_IB_FAST=1`, order P C P C, T190 window and `analyze_t190.py`) only if **all** hold in the racing phase of C1:

1. integrity: >= 95 % of lines consistent and no invariant failure;
2. `E >= 0.30` (at least 30 % of counted branches served by the fast path);
3. the best-case saving `S >= 1 %` of the frame budget per second of racing (>= 10 ms of host CPU per second of SPU work summed over threads), so that a 2-pair A/B can resolve it above the P1-P2 drift seen in T184/T190;
4. `p_conflict / branches < 0.10` (otherwise first enlarge or re-hash the cache offline, then re-count).

If 2 fails because `d_policy` dominates, the next work is the policy-mode audit (T192 `NEXT_STEPS.md` item 2), not an A/B. If 3 fails, stop: dispatch is not where SPU time goes. Hit rate alone never justifies an FPS claim; only the timing A/B can show a frame-time change, and only beyond the drift.

## What this protocol cannot show

Effects on frames; GPU or PPU-bound phases; dispatches outside `spu_indirect_branch`. Counts are of the host runtime, not of guest instructions.

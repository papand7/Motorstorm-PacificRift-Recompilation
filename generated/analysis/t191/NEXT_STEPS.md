# T191 next steps

## Commits (local only; nothing pushed or merged)

| What | Branch / worktree | Commit |
|---|---|---|
| Code, tests, benchmark | `agent/t191-spu-fast-dispatch` / `ps3recomp-t191` (from T189 `a26240c5`) | `32203ae6` |
| Reports | `agent/t191-spu-fast-dispatch-report` / `root-t191` (from T190 `92705aa`) | the commit that adds this directory (`git log -1 -- generated/analysis/t191`) |

Public audit: run on the exact staged blobs of the four code files (a staging tree built from `git show :path`): passed. `audit_public.py --staged` on the whole ps3recomp index reports 25 items, all in tracked test fixtures and scratch files that this change does not touch (for example `runtime/spu/tests/out_workload/spu_recomp.h`, `scratch/ppu_conformance.cpp`). The two tracked scratch files the test suite rewrites (`scratch/ppu_conformance.cpp`, `scratch/ppu_conformance_run.bat`) were restored before the commit. Reports: `--staged --private-reports`.

## Status against the brief

| Criterion | Result |
|---|---|
| Correct, generic, opt-in fast path | delivered: `PS3_SPU_IB_FAST=1` |
| Verified preservation of required semantics | differential vs the resolver on the whole context: 4,148 + 4,156 directed checks, 640,008 seeded random checks, 4 threads, stack reset; ASan and UBSan clean |
| Reliable invalidation or safe fallback | ownership is never cached (it is the key); registry epoch; everything unstable is refused to the resolver. Registry removal does not exist and would need an epoch bump (`CACHE_COHERENCE.md`) |
| Reproducible offline performance | `PERFORMANCE_RESULTS.md`: hit 0.71x stable, 0.74x overlay swap, 0.92x 200 targets; miss+fill 0.69x |
| No regressions to the default resolver | none measurable (+-5-9 % layout noise, both signs) |
| Plan for in-game A/B | below |

**Honest summary:** the fast path is correct as tested and faster on the branches it accepts, and **slower on the ones it refuses** (relocatable slots +27 %, policy mode +9 % with the switch on). Whether it helps MotorStorm is unknown, and Wws jobs run from relocatable slots, which is exactly the refused kind.

## 1. Before any game launch (offline, no authorization needed)

| # | Task | Why |
|---|---|---|
| 1 | **Cache the relocatable-slot owner**: key `(pc, owner, link_base-relative key)`, apply `reloc_delta` on a hit (the one state write). Extend the differential (slot-load / slot-evict sequences from `test_spu_reloc_job`) and add the negative controls "delta not applied" and "slot evict not seen" | removes the +27 % penalty and makes the fast path cover Wws-style jobs |
| 2 | Run the existing SPU tests with `PS3_SPU_IB_FAST=1` (`test_spu_reloc_job`, `test_spurs_*`, `test_spu_jobspan_path`) | the switch-on behaviour under the real policy/job drivers; none of those ran with it |
| 3 | Per-reason fallback counters under `-DSPU_IB_FAST_STATS` (policy mode, task region, slot, tracing, miss), printed by an existing stats interval | tells the in-game run how much of the traffic the cache can serve before spending a launch |
| 4 | Cache the policy-mode ordinary branch only if the counters show policy mode is the bulk. It needs an audit of steps 3-6 of `DISPATCH_ARCHITECTURE_AUDIT.md` first; do not do it speculatively | those are the services where a wrong cache would hide a state transition |

## 2. Proposed in-game A/B (needs separate explicit authorization; not run)

Same shape as T190, so the two results are comparable:
- one executable from the T190 build (inline stores compiled in) plus this library change, built with `-DSPU_IB_FAST_STATS` for the counters; no relift;
- arms P (control: T184 arm P environment) and C (P + `PS3_SPU_IB_FAST=1`), order P C P C, console session, Godot and the other workloads closed, race + 75 s, the T190 measurement window and `analyze_t190.py`;
- decision inputs: the fallback counters first (if the accepted share of dispatches is small, stop); then frame time, post-Havok and Wws spin phases, `[spu-task-stats]`;
- accept only if frame time improves by more than the P1-P2 drift in both pairs, the switch-on log line is present, and there are no new anomalies. Do not combine with T187's `PS3_SPU_MFC_FAST` or T189's `PS3_VM_STORE_INLINE` in the same arms.

T190's inline-store A/B is still waiting on a console session; this one should follow it, not run in parallel.

## 3. The milestone order after T191

1. Finish item 1 above (relocatable owner), then the in-game A/B.
2. **SPU register promotion**, on a new SPU differential test (T188's PPU test framework is the model). Do not start before the dispatch result, so the two effects stay separable.
3. **Atomic-wait improvements**: parking same-line reservation spinners until a store wakes them (T189 `RUNTIME_SYNCHRONIZATION.md`), as an opt-in switch with an LR-event torture test.
4. Exact floating-point fast path and cheaper SPU group exits (T189 `SPU_CODEGEN_AUDIT.md`).

## 4. Not done in T191 (by the brief)

No register promotion, no floating-point work, no scheduling change. `spu_indirect_branch_mt` was left as it is. The harness and the benchmark are the only large additions.

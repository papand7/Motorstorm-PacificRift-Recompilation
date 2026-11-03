# T192 next steps

## Commits (local only; nothing pushed or merged)

| What | Branch / worktree | Commit |
|---|---|---|
| Code, tests, benchmark | `agent/t192-spu-reloc-dispatch` / `ps3recomp-t192` (from T191 `32203ae6`) | `cc386f42` |
| Reports | `agent/t192-spu-reloc-dispatch-report` / `root-t192` (from T191 reports `982fbfe`) | the commit that adds this directory (`git log -1 -- generated/analysis/t192`) |

Public audit: run on the exact staged blobs of the four code files (a staging tree built from `git show :path`, then `audit_public.py --tree`): passed. The two tracked scratch files the tests rewrite (`scratch/ppu_conformance.cpp`, `scratch/ppu_conformance_run.bat`) were restored before the commit. Reports: `--staged --private-reports`.

## Status against the brief

| Criterion | Result |
|---|---|
| 1. Reliable per-reason fallback instrumentation | delivered (`-DSPU_IB_FAST_STATS`): exclusive primary reasons, probe classes, overlapping observations; invariants asserted; overhead measured. One gap: output only at normal process exit (below) |
| 2. Verified cache-coherence and ownership model for relocatable code | `RELOCATABLE_SEMANTICS.md`, `CACHE_INVALIDATION.md`: ownership is never cached (it is the key); the delta is recomputed; equivalence with the resolver rests on the slot fields, which are written only by the context's own thread |
| 3. Working generic optimization for eligible relocatable branches | delivered: 0.84-0.89x of the resolver (T191 was 1.05-1.28x) |
| 4. Reproducible offline performance evidence | `PERFORMANCE_RESULTS.md`, 7 rounds, 3 runtimes interleaved |
| 5. No correctness regression | 1,280,056 random + 8,429 directed checks, 17/17 negative controls, ASan/UBSan clean; suite 164/43/1 with the switch off |
| 6. No performance regression in the default path | none measurable (A/Z within noise, no value above +1.2 %) |
| 7. Controlled in-game A/B proposal | below |

**Honest summary.** The extension removes T191's penalty on relocatable slots and makes them a gain in the synthetic benchmark. It does not change what is slower: policy-mode branches still pay about 0.4 ns (+7 %), and plain cache hits are about 0.2 ns slower than in T191. Whether MotorStorm's dispatch traffic is mostly eligible is still **unknown**; in a Wws race much of it may be in policy mode, which is exactly what the cache refuses. The counters exist to answer that before any timing claim.

## 1. Offline, before any game launch (no authorization needed)

| # | Task | Why |
|---|---|---|
| 1 | **Interval and signal-safe reporting** for the stats build (`PS3_SPU_IB_FAST_REPORT_S=N`, a line from the 4096-branch flush point; flush from the host-thread exit path) | today the counts are printed at `atexit` only; a game stopped by a kill prints nothing |
| 2 | **Policy-mode ordinary branch**: audit steps 3-6 of T191 `DISPATCH_ARCHITECTURE_AUDIT.md` (kernel services, WWS stats, job enter) and decide whether the dispatches inside a policy module that are not services can be served | the only large eligible-but-refused class left; do not start before item 3 shows it is the bulk |
| 3 | Run the stats build on the lifted SPU programs available offline (the existing runtime tests that drive real policy modules) and record the reason histogram | a first, game-free estimate of the eligible share |
| 4 | Share the trace-state load between the resolver and `try` (+0.1 ns) | needs `test_spu_jobspan` updated, since it pins the resolver's first lines |
| 5 | An optional LS write watch on slot spans (store hook) | the only thing that would let either dispatcher notice guest writes that bypass `spu_overlay_note_get`; costly, benefits the resolver as well |

## 2. Proposed in-game A/B (needs separate explicit authorization; not run; follows T190's inline-store A/B, which is still waiting on a console session)

- **Executable.** The T190 build (`build/motorstorm-t190`, SHA-256 `9e77bd4b...f8453`, unchanged) cannot carry this change: the dispatch lives in the runtime. Build one new executable from the T190 code tree plus the T192 runtime change, with `-DSPU_IB_FAST_STATS`, no relift. Record both SHAs. The stats build costs +2 ns per hit; so the counting arm is separate from the timing arms.
- **Arms** (P/C/P/C like T190): P = T184 arm P environment (switch unset), C = P + `PS3_SPU_IB_FAST=1`. Optional third pair C0 = C + `PS3_SPU_IB_FAST_RELOC=0` (T191 behaviour) to isolate the extension. Timing arms use a build **without** `-DSPU_IB_FAST_STATS`.
- **Step 0 (counting launch, once).** One stats-build run of arm C, race + 75 s: read the `[spu-ib-fast-stats]` line. Gate: if `hit / branches` is below 30 %, or `d_policy` is the bulk, stop: the cache cannot help this workload until item 2 above is done. Also check `p_conflict` (512 entries per thread may be too few) and `d_unresolved` (should be rare).
- **Conditions.** Console session, Godot and other workloads closed, GPU quiet; the T190 preflight; same race, same measurement window, `analyze_t190.py`; at most four timed launches; abort on a preflight failure.
- **Accept** only if frame time improves by more than the P1-P2 drift in both pairs, the switch-on log line is present, and no new anomalies appear (`[spu-*]` warnings, task-pool or SPURS errors). **Do not** combine with T187 `PS3_SPU_MFC_FAST`, T189 `PS3_VM_STORE_INLINE` or the T190 arms in the same pair.
- No FPS claim is made from the offline numbers.

## 3. Not done in T192 (by the brief)

No SPU register promotion, floating-point work, scheduling or policy-mode caching; `spu_indirect_branch_mt` untouched; no game launched; T190's prepared executable and A/B environment untouched.

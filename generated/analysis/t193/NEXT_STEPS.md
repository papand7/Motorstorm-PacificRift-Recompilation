# T193 next steps

## Commits (local only; nothing pushed or merged)

| What | Branch / worktree | Commit |
|---|---|---|
| Code, tests, benchmark | `agent/t193-spu-dispatch-telemetry` / `ps3recomp-t193` (from T192 `cc386f42`) | `72e1001d` |
| Reports | `agent/t193-spu-dispatch-telemetry-report` / `root-t193` (from T192 reports `fa01e0a`) | the commit adding this directory |

Public audit: exact staged code blobs copied to a staging tree, `audit_public.py --tree`: passed; reports `--staged --private-reports`: passed. The tracked scratch files the suite rewrites were restored before committing. T190's executable, runner and configuration were not touched; no game launched.

## Status against the success criteria

| # | Criterion | Result |
|---|---|---|
| 1 | counters collectable during bounded execution | interval lines (`PS3_SPU_IB_STATS_INTERVAL_MS`), checkpoints, exit line |
| 2 | completed intervals survive forced termination | verified 3/3 (TerminateProcess); a line in flight at the kill is not claimed |
| 3 | totals internally consistent | identities on every line; 203/203 consistent snapshots under 16 writers; exact totals over 80 exited threads; 2^64 wrap |
| 4 | lifecycle and concurrency safe | FLS / pthread-key exit flush; no shared plain data; ASan/UBSan clean; exit-during-reporting crash found and fixed |
| 5 | overhead measured and acceptably low | disabled: none; enabled: +1-3 ns per branch (about half with `PS3_SPU_IB_STATS_OBS=64`); reporting: none measurable |
| 6 | dispatch semantics unchanged | stats and normal builds both pass the full differential; 17/17 dispatch controls; suite unchanged |
| 7 | profiling protocol ready | `GAME_PROFILING_PROTOCOL.md` (needs separate authorization) |

**Honest summary.** T193 makes the counters trustworthy in a game-like process. In particular, T192's counts were unreliable for short-lived threads: a thread with fewer than 4096 branches was never counted, and this runtime runs one host thread per SPURS task. It does not tell us yet whether MotorStorm's dispatch is eligible or significant; only the counting run can.

## 1. Next (needs authorization)

The counting run of `GAME_PROFILING_PROTOCOL.md` (one build, at most 3 launches, local console, after T190's A/B or on its own day), then the decision rule there.

## 2. Offline, optional

| # | Task | Why |
|---|---|---|
| 1 | `analyze_ibstats.py` (phase split, E, S, refusal mix), tested on the harness's line files | ready before the launch |
| 2 | Investigate the `fill`-pattern observation cost (`PERFORMANCE_RESULTS.md`) | understand, even if synthetic |
| 3 | A count-only mode with the fast path off (`PS3_SPU_IB_FAST` value that counts but always uses the resolver) | branch rate of the control arm P without changing its dispatch; needs its own differential |
| 4 | Run the POSIX path (pthread key) | only Windows was run |
| 5 | Policy-mode audit (T192 item 2) | only if the counting run shows `d_policy` dominating |

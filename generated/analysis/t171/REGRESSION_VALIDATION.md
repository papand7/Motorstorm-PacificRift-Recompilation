# T171: regression validation

Tree: ps3recomp-t171, tracked sources as committed in `b282e26`. Logs are private under `generated/analysis/t171/logs/`.

| Check | Result |
|---|---|
| Full suite | PASS 122, FAIL 3, SKIP 43, TIMEOUT 0 |
| T169 baseline at `542420e` | PASS 122, FAIL 2, SKIP 43 |
| `test_t171_track` (new) | PASS, 19 checks, debug layer on |
| `test_shader_window` (pins moved to default-on) | PASS |
| `test_t169_visual`, `test_t169_rt_reinterp`, `test_t169_profile` | PASS |
| WARP list via `warp_t169.py` (T145 35/35, T144 191, T141 41, T137 49+27, T133 35, T110 88, others) | failed 0 |
| Game build, `build/motorstorm-t171` | rc 0 |

## Failures

- **Inherited, also in the baseline:** `test_rt_pool_srv_layout`, `test_vpc_watch`.
- **Not in the baseline:** `test_spurs_event_sched`, kick arm: `Finalize took 92.4 ms (waited for a timed pass?)`. Three standalone reruns on the same tree each passed with 0 failures. It is a timing check in SPURS code that T171 does not touch, so it is classed as flaky under suite load. It was not rerun under load at `542420e`.

## Debug layer and game

The authorized A/B ran with the debug layer on: 0 compile or PSO failures in both arms and no watchdog. The message set is the same apart from foreign test processes during arm B (see `PERFORMANCE_IMPACT.md`).

## Audit

- The root repo's commit hook audits report commits.
- ps3recomp has no hook or audit script of its own. Running root's `tools/audit_public.py --staged` from that tree printed 25 BLOCKs and a failed status. None is on the five committed files; they are other paths such as `runtime/spu/tests/out_*/spu_recomp.*` and `scratch/ppu_conformance.cpp`. The commit was made in the same command, so it did not wait on this result. `--staged` audits the whole index: all 25 paths exist at `542420e`, so none is new. Each needs its own review before any public release.

## Working-tree note

`scratch/ppu_conformance.cpp` and `scratch/ppu_conformance_run.bat` show as modified in the T171 worktree. `tools/test_ppu_lift.py` rewrites them during the suite. They are not committed and were left alone.

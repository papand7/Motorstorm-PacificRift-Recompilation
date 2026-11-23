# RACE_VALIDATION_PLAN (Task 10). NOT EXECUTED: every launch needs explicit authorization

All runs go through `generated/analysis/vksync/ab2/run_vk.py`, which was not invoked and not modified here:
- strict `ORDER` tags: the next tags after `Kksr59` must be appended to `ORDER` and `K_BY_TAG` in the existing style;
- preflight: an active `>console`/`>rdp-tcp#` session, free RAM/VRAM, no `FORBIDDEN` variables.

## Preflight per run (operator)

1. **Quiet PC:** `\Processor(_Total)\% Processor Time` < 10 % for 30 s with no game running, and no builds or other agents active. Kksr44-46 and Kksr58 (27.6 fps on a known-good config) show what disturbed runs look like.
2. **Exe pins:**
   - main `build/motorstorm-vkgame-100-next` 714690f6…
   - candidate `build/motorstorm-vkgame-100-rj60` 8b6d0d4a…
   - Copy each to its own pinned path, as earlier arms were.
3. **Disk:** C: ≥ 8 GB free; traces go to D:.
4. **Environment:** the Kksr50 environment, with the route trace off file written at race entry (`[PT] off:` must appear).
5. **Reject a run if** fps < 25 or `[frame-hist]` p50 is disturbed. Do not average a rejected run in.

## Arms (one exe per comparison; within-exe switch arms)

| arm | exe | env on top of the Kksr50 env | purpose |
|---|---|---|---|
| A: Fix 2 on | rj60 | `PS3_SPU_INTERP_REJOIN_RELOC=1` (default) | baseline |
| B: Fix 2 off | rj60 | `PS3_SPU_INTERP_REJOIN_RELOC=0` | re-confirm the Fix 2 size on this exe |
| C: Fix 2 + C-A | rj60 | `PS3_SPU_DRAIN_RESUME_RELOC=1` | strongest new exact change (expected ≤ 0.1 ms: a null-result check, plus the missing Fix-2-on transition profile) |
| D: Fix 2 + previous natives | **not proposed.** The offline results do not justify it: groundrush/vp/Havok natives are unaffected by Fix 2, and the renderable natives' call counts are BLOCKED | – |
| F: Fix 2 + Fix 1 | rj60 | `PS3_USLEEP_SPIN_LR=4AF6D0` | Fix 1 separately (its 2+2 A/B was inconclusive) |
| A-main | 100-next | none | ties rj60 arm A to the shipped exe (PGO mismatch check) |

**Order:**
- A, B, C, F, A, C, B, F, A, C, F, B (12 races; three of each), plus one A-main at the start and one at the end.
- If authorization is limited, run the minimum A, C, A, C, F, F (6).
- Alternate arms so host drift spreads evenly.

**Diagnostics.** Arms A and C must also log:
- `PS3_SPU_AOT_PROF=5`: Fix 2 on transition counts (missing evidence). In C, `restart` should drop to ~0 at relocatable sites and `resume` should rise by the same amount.
- `PS3_SPU_WWS_STATS=1000:3214:1320` and `PS3_SPU_TASK_STATS=1000`, both already in the env.
- These are cumulative and low-overhead, but put them in every arm for a like-for-like cost.
- One extra run of A with `PS3_SAMPLE=2 PS3_SAMPLE_MAIN=2 PS3_SAMPLE_M2_TOP=150` measures the Present spin 0x50C818 share with Fix 2 (missing evidence).

## Metrics and decision

- **Primary:** `[rsx-hb]` fps over race entry + 10 s .. end (`spuopt/tools/ab_metrics.py`).
- **Frame-time distribution:** `[frame-hist]` p50/p90/p99 per run.
- **Report:** per-arm median and range over 3 runs, never a single-run average.
- **Secondary:**
  - renderable µs/job and interpreted steps/job (`tools/wws_window.py ksrNN`);
  - main-thread usleep and event-queue ms per frame;
  - HK2 ms/run;
  - for C: AOT-prof restarts and resumes (`tools/aotprof_rates.py <log> <t0> <t1>`).
- **Keep C-A** if it is exact in-game (no new `[spu]` halts, BRANCH-TO-0, or `[spu-depth]`) and the transition counts move as predicted. An fps change is **not expected** to be resolvable: anything inside the A-arm range counts as "no measurable effect".
- **Keep Fix 1** only if all three F runs beat all three A runs and the mean gain is > 3 %.
- **Separately (build, no race needed first):** switch the 1.00 recipe's `MSPR_WWS_AOT_DIR` to `wws_reloc_t81c` (C-L) and verify in one race that the renderable switch restarts (0xAA10, 0xA944) disappear from the AOT profile.

# SPU_TRANSITION_PROFILE: interpreter fallback, rejoin and unwind overhead per job type

Private, offline. All race numbers come from existing recordings; no new race was run.

## 1. Instrumentation (Task 2)

The required counters **already exist** in the runtime. All are opt-in and off by default, use no high-frequency stdout, and do not alter guest execution:

| need | existing switch | where |
|---|---|---|
| interpreter entries, guest instructions and host ns per (reason, image, pc) | `PS3_SPU_AOT_PROF=<s>` reason `miss` | `spu_channels.c:2875-2980`, notes at 4223-4228 |
| successful rejoins | reason `rejoin` | `spu_channels.c:3354-3355` |
| drain resumes / unwinds (restart) / iret unwinds | reasons `resume`, `restart`, `irq-restart` | `spu_drain.c:304, 495, 500` |
| per job: count, ns, interpreted steps, AOT/interp answer | `PS3_SPU_WWS_STATS=1000:3214:1320` | `spu_channels.c:1296-1470` |
| Havok tasks: on-CPU, MFC counts and ns | `PS3_SPU_TASK_STATS=1000` | `spu_channels.c:1474-1572` |
| per-job spans with interpreted steps (kind 27) | `PS3_FTRACE_SPUJOB=3214:1320` | `spu_channels.c:1238-1290` |

Implementation detail of the AOT profile: a fixed 1024-entry table with atomic updates, keyed by reason/image/pc, summarised every N seconds.

- **The one gap** was that a resume inside a relocatable slot was impossible, so "resume" was always 0. The new opt-in `PS3_SPU_DRAIN_RESUME_RELOC=1` (REJOIN_OPPORTUNITIES C-A) reports its resumes through the existing `resume` reason. No new counter was needed.
- **Missing (BLOCKED, needs a race):** the AOT profile with Fix 2 **on**. All AOT-prof data is from R1 (Fix 2 off).
- **Per-step host time in dispatch helpers:** only through the main-thread sampler, which does not cover SPU threads in these runs.

## 2. Measured transitions, R1 driving window (Fix 2 off; `out/aotprof_r1_rates.txt`, 50 s, 27.6 fps)

| reason | per s | per frame | host time |
|---|---:|---:|---:|
| miss | 42,745 | 1,547 | 643 ms/s (628 ms/s at the single site 0xDFA0) |
| rejoin | 13,125 | 475 | – |
| resume | 0 | 0 | – |
| restart | 6,567 | 238 | not timed (longjmp + re-dispatch) |
| irq-restart | 6,218 | 225 | not timed |

By job type (sites in the top-24 table, which covers > 99.9 % of interpreted steps):

| job (image) | transitions per frame | interpreted steps/event | ns/event | SPU-ms/frame |
|---|---|---:|---:|---:|
| renderablejob 1296695296 | restart 0xAA10 9.14, 0xA944 4.66, job exit 0x12EEC 5.14; misses 0xDFA0 9.13, 0xAFBC 9.14, 0x12DC8 13.8, 0x12760/0x12A60/0xACF4/0xECA4/0x10390 4.66 each | 166k at 0xDFA0; 139 at 0x12A60; 0 elsewhere | 2.49 ms at 0xDFA0; 30–112 ns elsewhere | 22.7 (Fix 2 off) |
| pvsjob 1296695309 | job-exit restart 0x653C 108/frame (one per job); miss 0x4070 108 | 0 | 66 | 0.007 measured miss time (+ restarts) |
| vehiclephysics 1296695298 | job-exit restart 0xBE8C 30.8/frame (one per job) | 0 | – | restarts only |
| spuconstraints / BasicParticleFiller / octreequery / ProcessEmitters | job-exit restarts 15.4 / 12.3 / 7.7 / 14.2 per frame | 0 | – | restarts only |
| Wws PM 1297305682 (all jobs) | miss 0x3FEC0 922/frame (interrupt save/restore shim at the top of LS, never lifted: microstep); miss 0xA2C 461 (interrupt vector target, 2 steps then rejoin 0xA60); irq-restart 0x2D20 225 | 0–2 | 349 / 401 | **0.32 + 0.18 = 0.50** |
| Havok HK1/HK2 (341580667 / 491898574), SPURS tasks | none in the table | 0 | – | 0 |

- **Fix 2 on (Kksr50/54 `[wws-stats]`):** renderable 30 interpreted steps/job. ~0.5 µs per job at ~15 ns/step, so ~0.01 SPU-ms/frame. The restarts and microstep misses remain (see §3).
- **Repeated transitions at identical addresses:** every site above repeats once per job or once per interrupt, and the same pcs recur every frame.
- **Failed rejoins:** a miss with steps > 0 that ran to the job's end. This happened only at 0xDFA0 (Fix 2 off).
- **Unresolved targets (BRANCH-TO-0):** none in R1.

## 3. Cost of the residual transitions (offline measurement, `OFFLINE_RESULTS.md`)

- Synthetic module N reproduces the renderable chain at 4 bases: 6 switch unwinds plus 1 job-exit unwind per job.
- With Fix 2 on, median 2.3 µs/job (resume off) vs 0.7 µs/job (resume on), over 2,000 resident runs. That is **~0.23 µs per unwind chain** (unwind + 2 misses + ~16 interpreted instructions). VERIFIED on the synthetic module.
- Scaled to R1's 238 restarts/frame: **~0.05–0.1 SPU-ms/frame** spread over 5 lanes. MODELLED: in-game per-event costs may differ, for example in cache behaviour.

**Conclusion:** after Fix 2, the transition and interpreter overhead is ≤ ~0.6 SPU-ms/frame in total: ~0.5 from the PM interrupt shims plus ~0.1 from unwinds. It is spread over all lanes. No interpreter-fallback path anywhere near 1.5 ms/frame remains. VERIFIED for the steps; the per-event host time is MODELLED.

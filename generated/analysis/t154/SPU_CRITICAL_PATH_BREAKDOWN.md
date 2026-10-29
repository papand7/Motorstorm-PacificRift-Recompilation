# T154: SPU, Havok and the frame's critical path after the Wws AOT

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. Data: the four authorised runs of `WWS_AOT_GAME_PERFORMANCE.md` (exe `e8386a74…`), split by content phase (light = race frames 40–499, about 2,000 draws; heavy = 600 and later, about 6,900 draws). No new launch and no new switch was tested in game.

## 1. What limits the frame now

| Scene | B (no AOT) | BA (AOT) | Limiting stage with AOT |
|---|---|---|---|
| light (race start) | 92 ms per frame, PPU frame thread waiting on Wws jobs (spin 14.6 ms) and on Havok (17.9 ms) | **47 ms per frame (21 FPS)**; Wws spin 1.8 ms, RSX idle 21.5 ms per frame | **PPU main thread:** about 28 ms of its own work plus the **Havok wait of 17.5 ms** (37 % of the frame) |
| heavy (from race frame ≈ 560) | 281 ms per frame | 281 ms per frame (3.5 FPS) | **RSX thread texture recording:** 186–194 ms of a 255–263 ms drain, idle about 4 ms (VERIFIED) |

- **Light-scene split (PARTIAL).** The PPU remainder (frame − Havok − spin − ref ≈ 27.6 ms) is PPU execution plus untraced short waits. The critical-path trace (host s 175–240) missed BA's light phase, which ends at about 170 s, so it is not split further.
- **Busy-spin vs real work.** The AOT did not merely remove a busy-wait. The work the spin waited for finished sooner: Wws job time 239 → 50 ms per frame. The main thread then found the next dependency, Havok, which did not move (17.9 → 17.5 ms).

## 2. Wws jobs (per-module counters, `PS3_SPU_WWS_STATS`)

Light scene, per frame (mean of 2 runs; all jobs AOT in BA):

| Module | jobs per frame | B ms per frame (µs per job) | BA ms per frame (µs per job) | speed-up |
|---|---|---|---|---|
| pvsjob | 112 | 75.2 (670) | 11.9 (107) | 6.3× |
| renderablejob | 20.6 | 68.4 (3,315) | 22.2 (1,076) | 3.1× |
| vehiclephysics | 32 | 59.2 (1,846) | 11.7 (365) | 5.1× |
| trailsupdate | 1 | 13.2 (13,137) | 0.6 (602) | 22× |
| screenrushjob / spuconstraints / others | about 40 | about 15 | about 3 | |
| **all** | **206** | **239 (1,159)** | **50 (242)** | **4.8×** |

- In the heavy scene renderablejob dominates: 76 jobs per frame, 381 → 132 ms per frame (5,021 → 1,739 µs per job). All modules together: 615 → 167 ms per frame.
- **Cause of the old cost:** instruction execution in the interpreter (VERIFIED). B interprets 17 M instructions per frame in the light scene and 40.5 M in the heavy one; BA interprets under 0.0005 M.
- **Not the cause:**
  - interpreter fallback (no refusals);
  - scheduling: kick → admit p50 23 µs, p95 1,024 → 256 µs; completion → next pass p50 4–6 µs;
  - DMA validation: per-install body hashes are included in the BA times above.
- **Notification to the PPU (§8D):** the spin left in the light scene is 1.8 ms, and the SPURS handoffs are in microseconds. Host notification latency is not material (VERIFIED).
- **AOT coverage:** complete for the 15 modules the race runs (100 % of jobs, all at base 0x4000). `spuconstraints` and `spuxform` keep a few interpreted hand-off instructions (under 500 per frame in total). No missing job module is worth lifting.
- **Remaining Wws cost:** renderablejob at 1.07 ms (light) / 1.74 ms (heavy) per job is now the largest Wws item. It is off the critical path in the light scene (spin 1.8 ms); in the heavy scene the RSX dominates.

## 3. Havok dependency chain (critical-path trace kind 34, `tools/havok_waves_t154.py`)

Per simulation frame the Havok taskset `0x16209480` runs these waves (medians, Br1 / BAr1):

| Wave | task image | tasks | task ms | wave span ms | start spread ms | gap to next wave |
|---|---|---|---|---|---|---|
| 1 | `0x145c1b7b` | 5 | 8.29 / 7.86 | 9.47 / 8.99 | 1.16 / 1.09 | −0.84 / −0.86 ms (wave 2 starts as wave-1 tasks finish) |
| 2 | `0x1d51c6ce` | 5 | 8.73 / 8.54 | 9.06 / 8.82 | 0.96 / 0.97 | +0.51 / +0.46 ms |
| 3 | `0x1266e45a` | 5 | 0.26 / 0.21 | 1.43 / 1.39 | 1.24 / 1.21 | then the PPU continues |
| 4 | `0x18345147` | 10 | 0.52 / 0.47 | 3.75 / 3.59 | 3.52 / 3.38 | later in the frame |

- **Waves 1–3 ≈ 19 ms; the PPU's Havok wait is 17.5 ms (VERIFIED).** The wait is this chain, and it is the same in both arms and both scenes.
- **The host does not serialise it (VERIFIED):** the five tasks of a wave run in parallel on five host threads, and each wave hands off in under 1 ms.
- **The chain is task execution:** two waves of 8–8.7 ms per task. The images already run lifted code: `[spu_workload] dispatch HIT (async)` for `0x145c1b7b` and the others.
- **Host costs visible inside it:** about 1 ms of start spread per wave, because every task run spawns its own host thread (`spawning thread`). That is about 2–3 ms of the 19 ms chain (HYPOTHESIS for the saving).
- **Physics is untouched:** no physics computation, step count or task was changed, skipped or approximated.

## 4. Remaining bottlenecks, ranked by frame-time impact

1. **Heavy scene, RSX texture recording in mid-frame flushes (VERIFIED as the bound; cause HYPOTHESIS).**
   - Heavy frames run 4 RSX passes, 3 of them early flushes (`flush_ms` 204 inside the drain). Texture recording costs 194 ms for 67,090 binds, i.e. **2.9 µs per bind**, against 1.1 ms for 14,127 binds (0.08 µs) in the light scene.
   - A 37× per-bind cost suggests the per-`render_frame` caches (SRV reuse, bind dedup, snapshot handles) are rebuilt at every early flush.
   - Fixing it would raise the heavy scene from 3.5 FPS toward the light-scene rate. It is the largest item in the game now.
2. **Light scene, PPU main thread.** About 28 ms of own work per frame plus the 17.5 ms Havok wait.
   - Havok options, both opt-in and exact:
     - a persistent per-lane worker for SPU task runs instead of a host thread per task, saving about 1 ms of start spread per wave (HYPOTHESIS);
     - faster lifted code for the two 8.5 ms task images, e.g. T136's `--chain-chunks` (direct trampolines 1,282 → 217 on the solver, offline-verified, game gain unmeasured; HYPOTHESIS).
   - The PPU's own 28 ms is not split yet. That needs the T149 trace window moved into the light scene.
3. **renderablejob** (1.1–1.7 ms per job): off the critical path in the light scene; matters only once the heavy scene's RSX bound is gone.

## 5. Recommended next task

1. **Heavy-scene texture recording (offline first).**
   - Capture one heavy frame with RSXI. This needs a launch, so it needs authorisation.
   - Profile `rf` / `record` / `tex` per pass in the backend harness.
   - Make the SRV/bind/snapshot caches survive early flushes within a guest frame. It must be opt-in, with GPU-harness byte comparison and the D3D12 debug layer.
2. **Phase-aware measurement.**
   - Report FPS per race-frame segment (`tools/phase_match_t154.py`), not per host-time window; the race-start content is identical per guest frame.
   - Put `PS3_CRITICAL_PATH_TRACE`'s window at race entry + 5 to + 25 s for the light scene.
3. **Havok chain (light scene).**
   - Measure the thread-spawn share with a persistent task-thread pool offline (`test_spurs_*`, Havok-style 5-task waves).
   - Then evaluate `--chain-chunks` on the two 8.5 ms images with the per-function differential.

# T158: race A/B, C0 (standard SPU lift) vs C1 (`--chain-chunks` on the Havok images)

2026-10-29. Two authorised launches (one per exe, of the three allowed), run one after the other, no retries. No merge or push. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## 1. Result

| | C0 | C1 | C1 vs C0 |
|---|---|---|---|
| **Light-scene race FPS** (race frames 40–499, 460 frames each) | **21.39** | **22.70** | **+6.1 %** |
| mean frame time | 46.7 ms | 44.1 ms | −5.6 % |
| median (p50) | 46.1 ms | 43.5 ms | −5.6 % |
| p95 | 51.9 ms | 49.4 ms | −4.8 % |
| p99 | 62.2 ms | 56.3 ms | −9.5 % |
| PPU Havok wait `0x30B710` per frame | 17.50 ms | 16.62 ms | −5.0 % |
| Havok chain (wave-1 start → wave-3 end, median) | 18.84 ms | 17.88 ms | −5.1 % |

- **PARTIAL.** These are measured game numbers, but from one launch per arm.
  - The T154 A-to-A spread on the same route and environment was 20.99 vs 21.20 FPS (1.0 %). The +6.1 % gain is about six times that.
  - There was no same-session A-to-A pair: the three-launch grant was used as one launch per built exe, and C2 was not built.
- The **heavy scene was not measured.** C1 booted 19 s more slowly (§5), so within the 195 s cap it ended at race frame 551, before the heavy scene, which starts at 600.
- **The offline estimate did not carry over.** The offline harness predicted about −5 ms of solver/collide execution per physics frame. In game, the solver did not change and collide gained 11 % (§3).

## 2. Configuration

| Item | C0 (A) | C1 (B) |
|---|---|---|
| Exe | `build/motorstorm-t156` → `ab/exe_a` | `build/motorstorm-t158-c1` → `ab/exe_b` |
| SHA-256 | `04e64386829877c79fa86d6b0a4127cae6147deb8d360500fa324d41e2b68e3f` | `2a0403201a3571d708e2be33338571f5bf3f965b4261b07baa3106e5eb851f08` |
| ps3recomp | `756c1e1` (T156) | `756c1e1` (`7a88b53` on `agent/t158-spu-aot-codegen` adds only a test) |
| SPU lifter | defaults | `PS3RECOMP_SPU_LIFTER_IMAGE_ARGS=<4 Havok images>=--chain-chunks` (`SPU_AOT_OPTIMIZATION.md` §2) |
| Compiler / flags | same toolchain and recipe (`build_t156.cmd` / `build_t158.cmd`): clang, Release, SSE4.1, `PORT_SPU_AVX2=OFF`, `MSPR_WWS_AOT=ON`, T81C reloc lift, staging PPU lift | identical |
| Run (`generated/runs/`) | `20261029-195530-t158-ab-C0r1` | `20261029-195848-t158-ab-C1r1` |

- **Candidate selection.** C1 was chosen; C2 (`--chain-hoist`) was not built.
  - C2 passed correctness (0 mismatches), but its offline gain was 0.9–1.7 %, within noise.
  - Per the brief, a synthetic edge alone does not justify selecting it.
  - C0 is kept as the baseline.
- **Runner.** `ab/run_t158ab.py` (from T156), sequenced by `ab/seq_t158.sh`.
  - Fresh hash-manifested HDD copies per launch (`hdd_C0r1.json`, `hdd_C1r1.json`), deleted after the run.
  - The T154/T156 route: intro skip, one Cross, no manual driving; same event and vehicle.
- **Environment.** Identical in both arms: the T156 arm S environment (T153 COMMON + PERF + T150 + `PS3_SPU_WWS_STATS` + `PS3_SPU_WWS_AOT=1` + `PS3_CRITICAL_PATH_TRACE=150:22`).
  - The worker pool is off.
  - RSX switches are unchanged.
  - There is no switch that disables chaining.
  - The established 12 presenting frame dumps stay on in both arms as correctness evidence. No RSXI capture.
- **Time limits.** Changed for T158 only:
  - controller hard cap at 200 s from wrapper start;
  - `fast_startup --timeout 195` plus its 15 s grace, giving a 210 s host hard deadline.
  - Both runs ended by the 195 s wall-clock timeout (`termination: timeout`) with no leftover process.

## 3. SPU timing (critical-path trace, kind 39 task entry runs, medians)

| Havok image | C0 ms per task | C1 ms per task | change | sum over 5 tasks per wave, C0 → C1 |
|---|---|---|---|---|
| w1 solver | 7.81 | 7.88 | +0.9 % | 39.6 → 39.5 ms |
| w2 collide | 8.44 | 7.52 | **−10.8 %** | 42.0 → 37.7 ms |
| w3 raycast | 0.189 | 0.179 | −5.3 % | 1.82 → 1.65 ms |
| w4 animation | 0.422 | 0.361 | −14.5 % | 4.93 → 4.40 ms |
| all Havok per chain | | | −5.8 % | 88.4 → 83.3 ms |

Task dispatch from the PPU fell from 16.4 to 13.7 µs (solver) and from 31.9 to 29.8 µs (collide); task prologues were unchanged.

**Trace windows.**
- The fixed trace window (host 150–172 s) was race +7.5 to +29.5 s for C0 but only race +0 to +9.5 s for C1. So C1 has 165 chains and C0 has 429.
- Per-image medians in 4 s bins are flat across the race in both runs (`ab/havok_bins_*.txt`; C0 collide 8.33–8.53 ms, solver 7.70–7.87 ms with one 8.23 ms bin). So the window difference does not explain the result.

**Wws jobs** (`[wws-stats]`, light window; the code is byte-identical in both arms):

| | C0 | C1 | change |
|---|---|---|---|
| job ms per frame | 49.9 | 43.7 | −12.4 % |
| renderablejob | 22.8 | 18.4 | −19 % |
| vehiclephysics | 11.6 | 10.4 | −11 % |
| pvsjob | 11.5 | 11.1 | −3 % |
| jobs per frame | 206.6 | 205.7 | same |

- Wws spin `0x50C818`: 1.95 → 1.02 ms per frame.
- Because the Wws code is identical, the Wws change is either less host contention (less Havok CPU time) or run-to-run noise. A single pair cannot tell which. This is the main reason the FPS result is PARTIAL.

## 4. Other measurements (light window)

| Metric | C0 | C1 |
|---|---|---|
| process CPU (cores busy, `performance.json`) | 4.58 | 4.60 |
| RSX drain thread CPU (cores) | 0.45 | 0.50 (more frames per second) |
| main PPU thread CPU (cores) | 0.51 | 0.49 |
| SPURS 0x1003F180 busy workers (`[spurs-busy]`) | 1.28 | 1.18 |
| RSX per frame: drain / expand / record / other (median ms) | 15.6 / 13.0 / 4.9 / 21.1 | 14.8 / 12.2 / 4.7 / 20.9 |
| RSX rf (median) | 9.2 ms | 8.3 ms |
| GPU execution | not measurable: `wait_ms` is 0.0 and there are no GPU timestamps | — |

## 5. Loading vs race

- **Race entry** (controller) was 145.5 s for C0 and 165.5 s for C1.
- **The 19 s difference arose during boot, before any Havok task runs.**
  - First GUI page: 8.8 s vs 16.4 s.
  - Intro skip: 27.4 s vs 46.3 s.
- **Menu press to race loaded:** 108.9 s (C0) vs 110.0 s (C1), +1 %. Treated as host start-up variance. It is not counted as a C1 effect, and loading is not compared further.
- **All race metrics above are by race-frame index** (race frame 0 = first frame with ≥ 200 draws), never by host time.

## 6. Correctness

- **Same scene at the same race frame.** Draw calls were 1802 at frame 0, 2065 at frame 300 and 2456 at frame 460 in both runs; the median over the window was 2004 in both.
- **Per-frame differences** over 551 common race frames:
  - draw_calls differ in 6 frames, verts in 68, upload in 1;
  - T154 A-to-A on the same route: 338 / 444 / 148 over 757 frames;
  - so C1 matches C0 more closely than two C0-equivalent runs matched each other.
- **Error and stall lines** are identical in both runs:
  - `[stall]` 50, `GCM_STALL` 3 (all loading-time snapshots), `[fc-watchdog]` 26, `[spu]` 25, `[spu-smc]` 8;
  - no crash and no new error.
- **12 frame dumps per run** were written. Eyeballing them for graphical differences is still pending; the draw-count match is the automated check.
- **Audio.** C0 logged 4 `GetBuffer`/`GetCurrentPadding` failures. The host's default audio device changed between the runs (different WASAPI endpoint IDs), so this is a host change, not a game difference.
- **Gameplay.** The route needs no driving input. Same race progression; no physics, timestep or guest-code change (the SPU instructions executed are the same).

## 7. Did the optimisation help?

1. **SPU execution: yes for collide, raycast and animation (−5 to −15 %); no for the solver (+0.9 %).** Total Havok task time is −5.8 %, far below the offline −33 %.
   - The solver result shows that the in-game solver task is not bound by drain hops or lifted-code speed. The offline harness cannot see what bounds it: its DMA, atomics and in-task synchronisation.
2. **PPU waiting: yes, slightly.** The Havok wait fell 0.9 ms per frame (−5 %) and the Wws spin 0.9 ms.
3. **Race FPS: +6.1 % in the light scene (PARTIAL, one pair).** Part of this may be host variance (the identical Wws code also ran 12 % faster).
4. **Critical path: unchanged.** The frame is still about 44 ms, with about 17 ms in the PPU Havok wait.
   - The Havok chain is 17.9 ms: the solver wave is 9.0 ms (unchanged) and collide 7.9 ms.
   - The heavy scene stays RSX-bound (T157's area) and was not reached.
5. **Regressions:** none observed (§6).

## 8. Remaining bottleneck and recommended T159

**Primary target: the in-game Havok solver wave**, a verified bottleneck that sits outside code generation.
- It is half of the 17.9 ms Havok chain that the PPU waits on every light-scene frame, and the Havok wait is the largest single PPU wait (38 % of the frame).
- Removing 99 % of its drain hops left its time unchanged (7.81 → 7.88 ms per task).
- So its time is not in the code that chaining or register caching would speed up.

**Why not SPU register caching next.**
- The solver did not respond to a large code-generation change.
- The only Havok tasks that did respond (collide, animation) gained 11–15 %. A register cache on top would at best cut a few more percent of the collide wave.

**T159 scope** (measure first, no speculative change):
1. One diagnostic run of C1 with `PS3_SPU_TASK_STATS` (the T156 arm D counters) to split solver task time into lifted execution, DMA wait (`mfc` tag status), atomic/reservation retries and in-task waits. In the same run, read the five solver tasks' end spread (0.77 ms here).
2. Then fix the dominant mechanism in the runtime (for example the DMA tag-wait or atomic path), keeping exact semantics and the T158 differential plus suite gates.
3. Keep C1 as the base. Repeat this A/B with an A-to-A pair to settle the Wws-variance question.

## 9. Evidence (private)

- `ab/`: `launch_C0r1.txt`, `launch_C1r1.txt`, `seq_t158.log`, `runtime-*/` (controller log, `cpath.txt`, frame dumps), `race_ab.json`, `race_util.json`, `phase_sites.json`, `havok_timeline.json`, `havok_bins_*.txt`.
- Run dirs: `generated/runs/20261029-195530-t158-ab-C0r1`, `generated/runs/20261029-195848-t158-ab-C1r1`.
- Tools (tracked):
  - `tools/race_ab_t158.py`: race-frame-indexed FPS, p50 / p95 / p99 and per-frame draw comparison;
  - `tools/race_util_t158.py`: CPU and SPURS busy over the light window;
  - `tools/havok_entry_bins_t158.py`;
  - `tools/phase_sites_t158.py`: the T154 phase_sites with the heavy window skipped when a run lacks it.

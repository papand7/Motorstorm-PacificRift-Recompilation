# T154: Wws job AOT in the game (integration, offline validation, authorised A/B)

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. Four authorised launches (B, BA, B, BA), no others. Nothing was pushed or merged, and no other agent's worktree was modified.

## 0. Result

- **The Wws job AOT doubles the frame rate of the race-start scene, and it is correct as far as tested (VERIFIED):**
  - phase-matched over race frames 40–499 (about 2,000 draws per frame), FPS goes from **10.67 / 11.02 to 20.98 / 21.18** (+94 %);
  - Wws job time per frame falls 239 → 50 ms, the spin at `0x50C818` 14.6 → 1.8 ms, and there are no refusals, mismatches or lost jobs.
- **The whole-window FPS (the T153 method) falls 7.17 → 6.64. That number is a measurement artefact, not a regression (VERIFIED):**
  - the race-start content is deterministic per guest frame (§6). About 520 race frames into the race, the scene changes to a heavy one: about 6,900 draws and 4 RSX passes per frame.
  - BA reaches that frame twice as fast, so its fixed host-time window (race entry + 10 s to + 88 s) holds mostly heavy frames, and B's mostly light ones.
- **In the heavy scene both arms run at about 3.5 FPS:** B 3.46 / 3.67, BA 3.53 / 3.59, an inconclusive difference.
  - The RSX thread is saturated there: drain 255–263 ms, texture recording 180–194 ms per frame, idle about 4 ms.
  - AOT still cuts the Wws spin 82 → 24 ms there, but the PPU then waits for the RSX instead (ref throttle 108 → 209 ms).
- **Every T153 FPS figure is the same phase mix.** T153 arms all rendered about 660 race frames, so their relative comparison stands, but no T153 number is a per-scene rate.

## 1. Baseline and integration

| Item | Value |
|---|---|
| ps3recomp baseline | T153 integration checkpoint `2a764e1` (`integration/t153-continuous-performance`) |
| T154 worktree | `ps3recomp-t154-wws-aot`, branch `agent/t154-wws-aot-critical-path`: `2a764e1` → **`e8e972a`** (`PS3_SPU_WWS_STATS`) |
| Wws AOT runtime | already in `2a764e1` (T106/T109 chain `d884519`…`894bb09`: dispatch-time rebase, `spu_reloc.h`, fail-closed refusals) |
| port | `port-t154` = `port-t153` + the 20-line `MSPR_WWS_AOT` block, byte-identical to root `9cd7ef2` (T152), `port-t70` and `port-t106aot`; no other difference |
| lift | `generated/spu_raw/wws_reloc_t81c` (31 modules, link base 0x4000), read-only, not re-lifted. `wws_reloc_register.c` `d347d562…082a`, manifest `a084eee5…d298` (same as T106) |
| lift vs game | `t70/tools/verify_wws_reloc.py` against `EBOOT.elf` `bbb7fe25…b287`: 31/31 PASS (`logs/verify_wws_reloc_t81c.log`) |
| build | `tools/build_t154.cmd` (the T153 `int` recipe + `-DMSPR_WWS_AOT=ON -DMSPR_WWS_AOT_DIR=…wws_reloc_t81c`); configure prints `Wws job AOT: 31 module(s)`; 312/312, rc 0 (`logs/build_t154.txt`) |
| exe | `build/motorstorm-t154`, 411,166,208 B (+8.6 MB over T153 for the 31 modules), sha256 **`e8386a7485399d9acdc6a7061c591f08a50b28c4bf4feaf924a44284f869751a`**, pinned as `ab/exe_w`. It was used by both arms and not rebuilt during testing |
| exe inspection | `tools/inspect_t154_exe.py`: 31/31 signatures and body hashes in the image, `.CRT$XCU` constructor, 31/31 register functions resolved, `PS3_SPU_WWS_AOT` exactly `1` gate, `PS3_SPU_WWS_STATS` strings present. RESULT PASS |

**New diagnostic (`e8e972a`): `PS3_SPU_WWS_STATS=<ms>:<ret LS>:<code-base LS>`** (MotorStorm `1000:3214:1320`).
- It opens and closes a job exactly where `PS3_FTRACE_SPUJOB` does, but without the ftrace recorder.
- Per module (FNV of the 16 identifier bytes) it counts:
  - jobs, host ns and max ns;
  - interpreted instructions;
  - the `spu_wws_job_enter` answer (RESIDENT/INSTALLED = AOT, each refusal by code);
  - lost jobs and runs at another base.
- Unset, the cost is one predicted-false load per policy-mode indirect branch. It reads and writes nothing guest-visible.
- Both arms ran with it on (+0.11–0.13 µs per job, §3).

## 2. Offline correctness (all before any launch)

| Test | Result |
|---|---|
| `tests/test_spu_reloc_job.py`: lifted == interpreted at 4 bases (guest output, LS, stack, 128 GPRs), residency, two-module selection, 9 fail-closed states state-identical to no AOT, base allow-list, VERIFY, env read once, constructor gate, random-state differential; **+6 new**: stats on leaves both paths byte-identical to stats off, every job counted once with the right answer and step count, malformed value fails closed, unset silent | **91 PASS, 0 failures** |
| **Real-module differential** (`tools/fuzz_retail_t154.py`, the T70 method on the linked lift): 145 runnable functions in all 31 modules, interpreter vs relocatable lift through the real dispatcher, all GPRs and all 256 KB of LS compared | **0 mismatches**: 0x4000 5,068 trials, 0x15C00 5,025, 0x9400 5,062 |
| `test_spu_switch_linkret`, `test_spu_jobspan_path` | 0 failures |
| full suite `tools/run_all_t154.cmd --jobs 6` (SPU instruction, DMA/MFC, LS, reservation/atomic, SPURS queue/admit/kick, Wws concurrency + 3-seed stress, scheduler, renderer) | 136 PASS / 43 SKIP / 3 FAIL. The two known T146 failures (`test_rt_pool_srv_layout`, `test_vpc_watch`) plus `test_d3d12_shader_cache`, which **passes rerun alone** (load flake, a renderer test the change does not touch). Equivalent to T153's 137/43/2 on `2a764e1` |

- **Not covered offline:** whole retail jobs with real inputs. Those need live guest DMA state, so their equivalence rests on the per-function differential and on the game evidence in §6 (PARTIAL).
- **LS and DMA semantics:** a DMA GET over a resident module drops its slot, and the module is re-hashed before reuse. In game, 95 % of entries were re-validated installs (§4).

## 3. Offline performance (synthetic; no game claim follows from it)

`tests/bench_spu_reloc_job.py 2000` (best of 5 × 2000 resident jobs, one core, near-idle host):

| Job | interpreter | AOT | speed-up |
|---|---|---|---|
| int | 231.9 µs | 29.0 µs | 8.0× |
| int + PIC switch | 350.6 µs | 46.7 µs | 7.5× |
| float + switch | 361.3 µs | 73.9 µs | 4.9× |

- AVX2 for the lifted modules alone adds nothing (73.2 / 46.8 / 28.2 µs).
- A fresh-load validation hash of 0xF6D0 bytes costs 8.0 µs.
- `PS3_SPU_WWS_STATS` overhead: +0.11–0.13 µs per job in both paths (`logs/wstat_overhead.txt`).
- Dispatch latency, memory bandwidth and host CPU in a synthetic setting were not measured separately. The game counters in §5 measure them directly.

## 4. AOT coverage and fallback in game (VERIFIED, BA runs)

- **Entries:** 1,808 / 1,852 INSTALLED and 93 / 95 RESIDENT per second. UNKNOWN, MISMATCH, NO_SLOT, DISABLED, BAD_BASE and BASE_REFUSED are all 0, and so are lost jobs.
- **Coverage:** all 15 modules the race runs are AOT for 100 % of their jobs, all at base 0x4000 (0 off-base runs). The other 16 lifted modules never ran in this window.
- **Interpreted instructions inside jobs:** 22.2 / 22.6 M per frame in B, versus under 0.0005 M per frame in BA.
  - The remainder is a few instructions in 69 % of `spuconstraints` jobs and in 3 `spuxform` jobs, i.e. lifter hand-off words. They are negligible.
- **Arm B on the same exe:** 0 entries of any kind, because nothing is registered. That confirms the switch is the only difference.

## 5. Game A/B

**Setup.** Exe `e8386a74…` for both arms. The environment is T153 arm B (`COMMON` + `PERF` + `PS3_TEX_SNAPSHOT_WWATCH=1` + `PS3_CRITICAL_PATH_TRACE=175:65`) + `PS3_SPU_WWS_STATS=1000:3214:1320`. BA adds only `PS3_SPU_WWS_AOT=1`; no `_BASES` or `_VERIFY` was set.
- Same route, controller, race and stop (race entry + 90 s) as T153, with fresh hash-manifested HDD copies per launch.
- Order: Br1 13:05, BAr1 13:09, Br2 13:13, BAr2 13:17. No builds or tests ran alongside.
- One process from another project (SSX Tricky, running since 27 Oct and therefore also during T153) used about 0.4 core. It was left alone.
- Runner: `ab/run_t154ab.py` (from `tools/make_runner_t154.py`); logs are private (`generated/runs/20261029-13*-t154-ab-*`, `ab/runtime-*`).
- All 4 runs are valid: rc 0, race reached (entry 145.5–149.8 s), trace window covers the race, no fatal errors, NOSYS or torn snapshots.

### 5a. T153 method (race entry + 10 s to + 88 s, host time; phase-mixed, see §0)

| Run | FPS | frame p50 / p95 / p99 ms | race entry s | race frames to stop | Wws spin | ref throttle | Havok wait | SPU PM CPU ms/frame | busy lanes | RSX drain / idle ms |
|---|---|---|---|---|---|---|---|---|---|---|
| Br1 | 7.10 | 96.2 / 298.6 / 371.5 | 149.8 | 662 | 30.95 | 31.3 | 18.3 | 390 | 2.57 | 21.6 / 64.4 |
| BAr1 | 6.66 | 50.9 / 304.2 / 317.8 | 147.6 | 757 | 11.18 | 89.9 | 17.7 | 186 | 0.66 | 246.6 / 4.6 |
| Br2 | 7.23 | 92.3 / 284.8 / 315.5 | 147.0 | 674 | 30.14 | 32.0 | 17.7 | 390 | 2.52 | 19.5 / 62.6 |
| BAr2 | 6.63 | 50.2 / 298.1 / 308.6 | 145.5 | 761 | 11.30 | 90.2 | 17.5 | 186 | 0.67 | 245.1 / 4.6 |
| **mean B / BA** | **7.17 / 6.64** | | 148.4 / 146.5 | 668 / 759 | 30.5 / 11.2 | 31.7 / 90.1 | 18.0 / 17.6 | 390 / 186 | | |

- The B runs reproduce T153 arm B (7.27 FPS, spin 30.7 ms).
- The BA frame p50 halves (94 → 51 ms) while the p95 stays at about 300 ms: that is the two-scene mix.
- GPU fence wait is 0 in all runs.
- SPURS kick → admit latency: p50 23 µs in both arms, p95 1,024 → 256 µs. Completion → next pass: p50 5–6 → 4 µs.

### 5b. Phase-matched (same race-frame indices; `tools/phase_match_t154.py`, `tools/phase_sites_t154.py`)

| | Br1 | BAr1 | Br2 | BAr2 | mean B → BA |
|---|---|---|---|---|---|
| **light, race frames 40–499**: FPS | 10.67 | 20.98 | 11.02 | 21.18 | **10.85 → 21.08 (+94 %)** |
| host s for those 460 frames | 43.1 | 21.9 | 41.7 | 21.7 | 42.4 → 21.8 |
| Wws spin `0x50C818` ms (460 calls each) | 14.86 | 1.82 | 14.25 | 1.84 | 14.6 → 1.8 |
| Havok wait `0x30B710` ms | 18.16 | 17.64 | 17.72 | 17.42 | 17.9 → 17.5 |
| ref throttle ms | 0.17 | 0.44 | 0.09 | 0.45 | ≈ 0 |
| Wws job ms per frame / µs per job | 243 / 1,180 | 50 / 242 | 236 / 1,138 | 50 / 243 | −79 % |
| RSX drain / idle ms (median) | 17.1 / 66.3 | 16.0 / 21.5 | 16.4 / 63.8 | 15.7 / 21.4 | RSX not limiting |
| **heavy, race frames 600–660**: FPS | 3.46 | 3.53 | 3.67 | 3.59 | 3.57 → 3.56 (inconclusive) |
| Wws spin / ref throttle ms | 84.6 / 113.0 | 24.0 / 211.0 | 80.0 / 103.9 | 24.1 / 207.2 | spin −70 %, the wait moves to the RSX |
| RSX drain / tex record / idle ms | 263 / 194 / 4.3 | 263 / 194 / 4.2 | 254 / 186 / 4.3 | 260 / 192 / 4.4 | RSX-bound in both |

- The two runs of each arm agree within 3 %, and the light-phase gain is 30 times that spread, so it is VERIFIED.
- The heavy-phase segment is short: 61 frames, about 17 s, the only span every run covers. Its difference is within run-to-run variation.

**Loading:** race entry 148.4 → 146.5 s (−1.9 s). That is within the 145–150 s T153 spread, so it is inconclusive.

## 6. Visual and simulation correctness

- **Guest workload is identical per frame (VERIFIED):**
  - draw-call and vertex counts per race frame match between Br1 and BAr1 on 656 of 661 frames;
  - the two B runs match on only 641, so the AOT arm is as close to B as B is to itself;
  - the scene change (about 2,000 → 6,900 draws) happens at the same race frame (about 520–560) in all four runs.
- **The simulation is locked to frames:** the race-start sequence advances per guest frame, not per host second (about 520 frames take 48 s in B and 25 s in BA). So the AOT changes how fast frames arrive, not what a frame computes. Nothing in the original 30 Hz frame logic, Havok or vehicle physics was changed.
- **Frame dumps** (`ab/vis/sheet.png`, frames 0, 3, 6, 9 and 11 of each run): the same race-start flyover in every run, including the pre-existing overexposure; no missing geometry, texture corruption or render-target differences.
  - The dumps cover only the first race frames. Vehicle movement, collisions and the heavy scene were not visible. The controller gives no input, so race progression beyond the start sequence is unverified.
  - Full physics equivalence is **not** claimed (PARTIAL).
- **No crash, hang, stall or validation error in any run.**

## 7. Integration-ready

| Commit / item | Switch | Default | Evidence | Reversion |
|---|---|---|---|---|
| root `9cd7ef2` (T152) = `port-t154` block | CMake `-DMSPR_WWS_AOT=ON` + `MSPR_WWS_AOT_DIR=generated/spu_raw/wws_reloc_t81c` | OFF | §1, §2 | configure without it |
| (runtime already in `2a764e1`) | `PS3_SPU_WWS_AOT=1` | off (nothing registers) | §2, §4, §5 | unset |
| ps3recomp `e8e972a` | `PS3_SPU_WWS_STATS=1000:3214:1320` | off | 91 PASS, overhead §3 | unset; `git revert e8e972a` |

- **Recommendation:** make `PS3_SPU_WWS_AOT=1` (with an `MSPR_WWS_AOT=ON` exe) part of the performance preset (T153 arm B + AOT). It is the fastest configuration measured, with no correctness regression observed.
- Defaults were not changed here. Promoting it to a default is a separate decision.
- `PS3_SPU_WWS_AOT_BASES=4000` is harmless (every run was at 0x4000). `_VERIFY=1` was not needed in these runs; it is a safety net, not an optimization.
- The next limits are in `SPU_CRITICAL_PATH_BREAKDOWN.md`.

# T70: WWS AOT integration and race performance readiness

2026-10-26. No merge, no push. T70B added the one authorized isolated build (section 0). A1 was one authorized AOT-off session (section 0b). T70C (offline) fixed job-span completion and the race window (section 0c). T70E ran the one authorized A1′ session (section 0e). T70F reclassified its job spans offline (section 0f). T70G corrected the job-span opener offline (section 0g). T70H built and pinned it (section 0h). T70I ran the one authorized A1″ session, which is VALID (section 0i). T70J ran the one authorized B1 session, which is VALID: race fps 5.04 → 11.32 (section 0j).

- **Not touched:** `ps3recomp-t62`, `ps3recomp-t60`, the shared `port/CMakeLists.txt` (sha256 still `b27b99b1…ce9a`) and T71's work.
- **New, private:**
  - worktree `ps3recomp-t70` (branch `agent/t70-wws-aot-race`);
  - `generated/spu_raw/wws_reloc`;
  - `port-t70/` (copy of `port/`);
  - `build/motorstorm-t70-aot/` (built in T70B);
  - `generated/analysis/t70/`.

## 0. T70B build, VERIFIED (offline)

| Item | Result |
|---|---|
| Source | `ps3recomp-t70` `agent/t70-wws-aot-race` @ **`6817933d7b4c05da3d81b6f2bc479115dc28da7e`**: base `c529ab0` (T61 font fix) + T59 `ad69e8e` `54c06d2` `d1b4119` `8de3590` + T69 `76d5ca1` `6817933`; worktree clean before and after |
| Other inputs | `port-t70/CMakeLists.txt` `279698ce…76be`; `wws_reloc_register.c` `d347d562…082a`; manifest `a084eee5…d298` (unchanged); `generated/ppu-hooked-staging` (79 TUs, as T64C); shared `port/CMakeLists.txt` still `b27b99b1…ce9a` |
| Commands | `cmd /c generated\analysis\t70\tools\configure_aot.cmd` (exit 0, "Wws job AOT: 31 module(s)"), then `tools\build_aot.cmd` = vcvars + `cmake --build build\motorstorm-t70-aot --parallel 2` (exit 0, 312 steps, 0 errors). Logs `logs/t70b_configure.log`, `logs/t70b_build.log` |
| Flags | `ninja_diff.py` re-run: **PASS** (276 common entries identical to T64C, +32 AOT TUs, one flag set) |
| Executable | `build/motorstorm-t70-aot/MotorStormPacificRiftRecomp.exe`, 404,260,864 bytes, sha256 **`4a07bfc97470981642c5334ca07f8ef135fbb209d69690d934079c94279af672`** (T64C exe: 397,556,736 bytes) |
| Linkage / registration | `tools/inspect_aot_exe.py` **PASS** (`logs/t70b_inspect_exe.log`): all 31 module signatures and body hashes from `wws_reloc_register.c` are in the exe image; the register object carries a `.CRT$XCU` static-init entry, defines `wws_reloc_register_all` and references 31 `wr_ms_*_spu_recomp_register`, all 31 defined by the module objects |
| Off by default | Constructor registers only for `PS3_SPU_WWS_AOT` exactly `1` (source gate + test 85/85 "constructor registers only when PS3_SPU_WWS_AOT=1"); without it the PM path is the interpreter, as on T64C. `SPURS_BUSY_MS` defaults to 0; `PS3_FTRACE*` only by env. VERIFY and interpreter fallback untouched |
| Re-run tests | `test_spu_reloc_job` **85/0** (`tools/run_reloc_test.cmd`: vcvars + T17 cc shim + stub `m.lib`), `test_spu_lifter_reloc` 13/0, `test_spu_jobspan` 8/0, `verify_wws_reloc.py` 31/31 PASS |
| A/B harness | `prepare` guards (AOT strings, CMake cache) accept this exe (checked without pinning); `dryrun A` / `dryrun B` exit 0. Nothing pinned, nothing launched (`logs/t70b_ab_guard.log`) |

Not proven offline: that the CRT runs the constructor in the linked exe. Arm B's `[spu-reloc] … resident re-hash on` line is the runtime proof (an `ab_report.py` gate).

## 0b. A1 baseline run (AOT off), PARTIAL: not a valid B1 baseline

One authorized session. Exe pinned to `ab/exe/` (pin = build = **`4a07bfc97470981642c5334ca07f8ef135fbb209d69690d934079c94279af672`**). Run dir **`generated/runs/20261026-155601-t70-ab-a`**; runtime dir `ab/runtime-20261026-155600-A` (fresh verified hdd0/hdd1 copies). Stopped by the controller at 205.1 s; no leftover process. The runner's `exited_error (exit code 1)` is the hard kill, not a game error. Extraction: `ab/a1_extract.py` → `logs/t70_a1_extract.txt`; `ab_report.py` refuses the run (`logs/t70_a1_report.txt`).

| Objective | Result |
|---|---|
| Start + navigation | VERIFIED. 7-step route, presses at 88–~110 s, no manual input |
| AOT off | VERIFIED. env has no `PS3_SPU_WWS_AOT*`; 0 `[spu-reloc]` lines; 0 kind-28/29 records |
| LoadRace | VERIFIED. `0x89230` `how=ret` at 196.87 s after 87.9 s (T64C ≈ 89 s), `PostLevelLoad` marker 191.96 s, `0x329D90` from lr `0x8EE8C` 197.48–197.58 s, `0x8EA00` `how=ret`, `depth_surface_created` 197.59 s |
| Pre-race sequence | VERIFIED as reached: first heartbeat with > 200 draws at 197.8 s (263–265 draws/frame, as T64C's 256+) |
| Race FPS | **5.15 fps**, but over only 2.3 s (201.0–203.3 s, after the 3 s skip); per-second frame means 193/195 ms. Not a valid measurement |
| Frame-time percentiles | **Not available for the race**: the ftrace window (150–198 s) closed 0.2 s after race entry. In-window (loading screen) flips: n = 1500, mean 31.6, p50 31.2, p95 33.3, p99 34.9 ms |
| Havok | 60 simulate dispatches over 12 race frames = **5.00 per frame** (25.8/s), as on T64C; 190 for the whole run |
| Crashes / errors | none: no fatal, assert, unhandled, Present timeout or watchdog report |

**Why the race came late (VERIFIED; not caused by T70).** The intro Bink opens either at 35.5 s (T64, T64C) or at 78.4 s (T64B and A1; both show 1 heartbeat frame at first draw vs 5–6). Intro to race entry takes 119.2 s in both modes. A1 drew the slow mode: race entry at 197.6 s instead of 154.8 s, which leaves 7.5 s of race inside the 205 s cap. Cause unknown (HYPOTHESIS: a startup wait before the intro).

**SPU job instrumentation (VERIFIED limitation).** `PS3_FTRACE_SPUJOB` opened jobs (52 `[spujob]` lines, the log keeps the first 64) but **wrote 0 kind-26/27/28/29 records**. `spu_jobspan_return` runs only from `spu_drain_call` when the drain reaches the PM return LS (`spu_drain.c` 444/479). In the game no job close matched, so per-job time, module identity records and the **AOT result mix (kind 29, which B depends on)** are lost. HYPOTHESIS: in the game the job's `bi $0` back to LS `0x3214` returns inside the interpreter or the `_mt` dispatch, never at a drain return. `test_spu_jobspan` (8/8) drives the state machine directly, so it did not catch this.

**Module identities and load addresses (PARTIAL).** The `[spujob]` lines matched to retail modules by the 64-byte entry FNV (30 distinct ids for the 31 modules). Lane 0 only (log cap), all at **base 0x04000**:

| wid | Module | Entry LS | First seen |
|---|---|---|---|
| 3 | LibMP3 stereo job | 0x16040 | 80 s |
| 1 | octreequery | 0x04FA0 | 192.9 s |
| 2 | vehiclephysics | 0x0BDE0 | 197.8 s |
| 0 | spuconstraints | 0x05210 | 197.8 s |
| 1 | groundrushvisibilityjob, pvsjob, renderablejob, ProcessEmittersModule | 0x04B20, 0x06490, 0x12E40, 0x0C110 | 197.8 s |
| 2 | occjob, screenrushjob | 0x0A410, 0x06640 | 197.8 s |

All 10 are in the AOT manifest. 0x4000 is a tested base (synthetic and retail). Lanes 1–3 bases are not recorded.

**SPURS worker attribution (VERIFIED).** `[thread-role]`: MotorStorm2 SPURS `0x1003F180` PM lanes sn0 = TID 12444, sn1 = 20568, sn2 = 12100, sn3 = 10968, sn4 = 13680, kernel 19772; second SPURS `0x10EFA300` sn0 = 4984, kernel 20552. In the race window (200.8–205 s, about 4 s):
- **sn0 (TID 12444) is the hot lane: 0.77 cores**, wid 1 busy 0.51 (672 runs/s), wid 2 busy 0.22, wid 0 0.03.
- sn1–sn3 use 0.03–0.07 cores each (busy ≤ 0.04 per wid).
- Other top threads (no role line: PPU/RSX/host): TID 20752 0.33 cores, 20660 0.13, 3040 0.12.
- Before the race the load was spread across lanes (each lane about 0.15 busy on one wid).

This matches T69's EvoDefault (wid 1) suspicion and adds that it runs on a single lane. Over 4 s it's a HYPOTHESIS for the race as a whole.

**Verdict on A1:** valid for the AOT-off gate, LoadRace, Havok 5.00 per frame, lane → TID mapping and the lane-0 base 0x4000. **Not a valid B1 baseline:** no race frame-time percentiles, a race window < 20 s, and no job or AOT-result spans. A B1 run under the same harness would also lose the kind-29 mix. Before B1:
1. **Job-span close** (source change, needs authorization): make the jobspan close fire on the game's return path (find the path where `pc == 0x3214` is reached; add a test that runs a PM-style `bisl` → job → `bi $0` through the interpreter and `_mt` dispatch).
2. **Race window independent of the bimodal start:** e.g. arm the ftrace on race entry (the controller already sees `0x329D90` from lr `0x8EE8C`) instead of a fixed 150 s, and abandon a run whose intro opens after ~40 s (it cannot reach 20 s of race before 205 s).
3. Repeat A (A1′) under the fixed harness, then B1.

## 0c. T70C: job-span close and race-entry window, VERIFIED offline

Offline only: no launch, no game build, no merge or push. Commits on `agent/t70-wws-aot-race` (worktree clean after): **`478aea3`** (job spans) and **`bdf8224`** (ftrace arm), on top of `6817933`. Patches `patches/0007`, `0008`. Public audit `--staged` before each commit: the same 25 pre-existing items as the base (`logs/t70c_audit_c1.log`, `c2.log`), none from these files.

**Root cause (VERIFIED: code path plus offline reproduction, consistent with A1).**
1. The PM enters a job with `bisle $r0,$r5` at LS 0x3210. Lifted, that is `spu_indirect_branch` + `spu_drain_call(ctx, 0x3214)`.
2. The retail job modules call PM services through a function table: about 10 `lqx; rotqby; bisl $r0,$rX` sites in each of the 31 modules (`tools/t70c_callsites.py`, `t70c_bisl.py`).
3. The interpreter stops at the service's lifted entry, and the service host-returns to the job's next word. That word has no lifted code, so `spu_drain_call` calls `spu_restart_dispatch`, which longjmps to the driver. The drain that opened the job, and its close hook, are gone.
4. The job's final `bi $r0` then reaches 0x3214 as the driver's trampoline: `spu_indirect_branch` with `pc == 0x3214`, which only the drain ever checked. So the job stayed open forever.
5. Because the state is per host thread while PM contexts are per (wid, lane), each `[spujob]` "reopen" in A1 was a different wid's context overwriting the stale one. That is why A1 shows 52 opens (1 before the race, 51 in the last 2 s) and 0 records. A1's mid-job re-entries (`[spu-smc]` at 0x051A8 and 0x15D20, steps 0–4) are the driver resuming the job after the unwind.

**Fix (`478aea3`; execution unchanged, all behind `PS3_FTRACE_SPUJOB`):**
- `spu_indirect_branch` closes the open job when `pc` is its return. The drain closes stay.
- A job that never gets there gets **no** completion record. It gets **kind 30 `PS3_FT_SPU_JOB_LOST`** (b = entry | reason << 24) when another lane's job opens on the thread (reason 1), or when its lane's `spu_run_with_halt` ends with it open (reason 2).

**Regression (`logs/t70c_*`):**

| Test | Result |
|---|---|
| `tests/test_spu_jobspan_path.py` (new; the real SPU runtime, a PM-style `bisl` → interpreted job → lifted PM service → `bi $r0`; repeated on one lane, halted mid-job, a second lane) | **0 failures** after the fix (28 checks traced, 12 untraced). On the unfixed runtime: **10 failures**, the A1 symptom exactly (`t70c_path_prefix.log`). The PM continuation is reached through the driver, proving the restart path |
| Guest state (LS, GPRs, pc, int enable, host depth) | identical with tracing on and off, **and** identical to the unfixed runtime (6 scenarios) |
| `tools/test_spu_jobspan.py` | 26 + 1 + 2 checks, 0 failures (new: LOST reasons 1/2, close-at-dispatch and run-end wiring) |
| `tests/test_spu_reloc_job.py` | 85/0, after both commits |
| `tools/test_ppu_trace.py` | all pass, plus the new `PS3_FTRACE_ARM` arm / never / late modes |
| Compile, project LLVM 23.1.3 clang-cl, exact `build.ninja` command lines, objects to `c2_objs/` (`tools/compile_tus.py`) | all 9 TUs that include `ps3_ftrace.h` compile: `spu_channels`, `spu_drain`, `ppu_trace`, `ppu_loader`, `sys_ppu_thread`, `sys_timer`, `cellSpurs`, `cellGcmSys`, `rsx_d3d12_backend`. The 16 warnings on added lines are the build's existing `-Weverything` style categories (`logs/t70c_new_warnings.log`) |

**Race-entry window (`bdf8224` runtime, plus the private harness):**
- **Runtime:** `PS3_FTRACE_ARM=<fn>:<lr>[:<settle>]` keeps no span until the PT tracer's `fn=` hook sees `<fn>` entered from `<lr>`. Spans are then kept from `<settle>` after that entry until PS3_FTRACE's start + seconds, which stays the hard end and the dump point.
  - The event itself is a kind-31 record; the header adds `armed_us` (−1 = never) and `arm=`.
  - Never armed, or armed too late for the settle, the window is **empty** rather than wrong.
  - The hook runs before PT sampling, at configured sites only.
- **Trigger:** `0x329D90` (loading screen stop) entered from `0x8EE8C` (race loader). In all 5 traced runs it fires exactly once, after LoadRace's `how=ret`.
- **`run_t70_ab.py`** (pre-T70C copies in `logs/*.pre-t70c`):
  - `PS3_FTRACE=120:76`, `PS3_FTRACE_ARM=329D90:8EE8C:3`: the earliest start is 120 s, the hard end and dump 196 s, the settle 3 s.
  - The controller ends the session 1 s after `[ftrace] wrote`.
  - If not armed by **172 s**, the session ends as INVALID (no 20 s window possible).
  - 205 s stop, 210 s runner cap unchanged.
  - Offline controller simulation (`tools/t70c_controller_sim.py`, `finish()` stubbed): fast start stops at 197.4 s, slow start at 172.0 s INVALID, armed-but-unwritten at 205 s.
- **Fast vs slow startup:**
  - Fast start (race entry ≈ 154.8 s, as T64C) gives a 157.8–196 s window of about 38 s.
  - Slow start (race entry ≈ 197.5 s, as A1) never arms and is rejected at 172 s. No loading frame can enter: the window starts after the post-LoadRace event plus the settle.
- **`ab_report.py`** cuts the window from the trace header (ftrace clock), and the stderr streams by their order around the `[ftrace] armed` / `[ftrace] wrote` lines.
  - **ERROR** (not a short measurement) for: no header, a pre-T70C fixed-window trace (A1 is now refused this way), never armed, or armed without a completed dump.
  - **Gates:** armed once by the race-entry call after a LoadRace `how=ret`; window ≥ 20 s; 0 dropped spans; ≥ 90 % of window heartbeats > 200 draws; flips and job spans present; LOST ≤ 1 %; the A/B gates; 5.00 ± 0.05 Havok steps per frame.
  - The self-test passes and rejects all 7 negative cases (never armed, dump missing, fixed window, late entry, loading-like draws, LOST jobs, no LoadRace return).

**Limits (HYPOTHESIS until A1′).**
- The real LOST rate (a job that yields to the kernel mid-body would show up as reason 2) and the real job-record volume are unknown. The estimate is ~10k spans/s at most, against a 4M-span cap.
- Arming relies on the PT `fn=` hook for `0x329D90`, which `ab/t70_ab_trace.cfg` keeps.
- Slow starts are rejected, not measured: within the 205 s cap they cannot be.
- The pinned T70B exe (`4a07bfc9…`) does **not** contain these commits. A1′ needs a rebuild and a new pin (`prepare` refuses a second exe in `ab/exe/`: use a new pin directory or retire the old one).

**Readiness for a new A1 (A1′):** ready offline once rebuilt. Sequence, each step separately authorized:
1. Build `agent/t70-wws-aot-race` @ `bdf8224`.
2. Pin the new exe.
3. Run A1′. Valid only if every gate passes; a slow start ends at 172 s as INVALID and needs another authorized launch.
4. Run B1.

## 0d. T70D: corrected build and pin, VERIFIED offline

No launch, no merge or push. Worktree clean before and after.

| Item | Result |
|---|---|
| Source | `ps3recomp-t70` `agent/t70-wws-aot-race` @ **`bdf8224533531294e4571da00d4ced69e3be7535`** (= T70B `6817933` + `478aea3` job spans + `bdf8224` ftrace arm); the other inputs are unchanged from T70B |
| Configure | `tools/configure_aot.cmd` exit 0, "Wws job AOT: 31 module(s), PS3_SPU_WWS_AOT=1 to enable" (`logs/t70d_configure.log`) |
| Build | `tools/build_aot.cmd` exit 0, 36 incremental steps, link OK, 0 errors (`logs/t70d_build.log`) |
| Flags | `ninja_diff.py` **PASS** (`logs/t70d_ninja_diff.log`) |
| Executable | 404,267,520 bytes, sha256 **`2709eafd0e57c620bd86eb4f5d580f9315032e5fc0b88562b29663f3d2002cec`** |
| Registration | `inspect_aot_exe.py` **PASS**: 31/31 signatures and body hashes in the image; `.CRT$XCU` ctor present; 31/31 register functions defined (`logs/t70d_inspect_exe.log`) |
| Defaults | AOT only for `PS3_SPU_WWS_AOT` exactly `1`; `SPURS_BUSY_MS` 0; job spans only with `PS3_FTRACE` + `PS3_FTRACE_SPUJOB`; arm only with `PS3_FTRACE_ARM` (source gates and tests) |
| Race-entry tracing present | the exe contains `PS3_FTRACE_ARM`, `[ftrace] armed at`, `armed_us=` and `[spujob] lane` (`logs/t70d_strings.log`) |
| Pin | new directory **`ab/exe-t70d/`** + `ab/exe_pin_t70d.json` (pin = build = `2709eafd…2cec`). The A1 pin `ab/exe/` + `exe_pin.json` (`4a07bfc9…f672`) was checked before and after: unchanged (`logs/t70d_pin.log`) |
| Harness | `run_t70_ab.py` points to `exe-t70d` (pre-T70D copy `logs/run_t70_ab.py.pre-t70d`); `prepare` now also requires the arm strings. `dryrun A` / `dryrun B` exit 0 against the new pin: `PS3_FTRACE=120:76`, `PS3_FTRACE_ARM=329D90:8EE8C:3`, `PS3_FTRACE_SPUJOB=3214:1320`; B adds `PS3_SPU_WWS_AOT=1` + `VERIFY`; runner `--timeout 210`, controller stop 205 s |

**Offline regression (`logs/t70d_*`):**

| Requirement | Test | Result |
|---|---|---|
| Original T70 AOT tests | `test_spu_reloc_job`; `test_spu_lifter_reloc`; `verify_wws_reloc.py` | 85/0; 13/0; 31/31 PASS |
| Completion at the real PM return path | `test_spu_jobspan_path` (PM service callout → driver path) | 0 failures |
| Incomplete jobs → explicit LOST | `test_spu_jobspan_path` (halted) + `test_spu_jobspan` (reasons 1/2) | pass; 26+1+2 checks |
| Guest-state equivalence | `test_spu_jobspan_path`: tracing on = off (6 scenarios) | pass |
| Recording only after the race-entry trigger | `test_ppu_trace` arm / never / late | pass |
| Trace finishes before the cap; slow start rejected | `t70c_controller_sim.py`: fast start stops at 197.4 s, slow start INVALID at 172 s, unwritten stops at 205 s | 3/3 |
| Report rejects missing, incomplete or insufficient measurements | `ab_report.py --selftest` | ok, 7/7 rejections |

**Remaining risks (HYPOTHESIS until A1′):**
- The real LOST rate and the job-record volume (≤ ~10k spans/s estimated, against a 4M cap).
- A slow startup ends the session at 172 s as INVALID and needs another authorized launch.
- Arming needs the PT `fn=` hook on `0x329D90`, which `ab/t70_ab_trace.cfg` keeps.
- Job-span tracing adds the same per-job overhead in both arms.

## 0e. T70E: A1′ corrected baseline (AOT off), one session: INVALID on the LOST gate, every other gate PASS

**Run identity:**
- Exe `ab/exe-t70d/` sha256 `2709eafd…2cec` (= pin, bdf8224); no rebuild.
- Command: `py -3 generated/analysis/t70/ab/run_t70_ab.py launch A`. Argv identical to `dryrun A`: AOT unset, `PS3_FTRACE=120:76`, `PS3_FTRACE_ARM=329D90:8EE8C:3`, `PS3_FTRACE_SPUJOB=3214:1320`, `SPURS_BUSY_MS=1000`.
- Fresh verified hdd0/hdd1 in `ab/runtime-20261026-172956-A`. No driving, no TEX_SAVE, no renderer or T75/T77 changes.
- Run dir `generated/runs/20261026-172957-t70-ab-a`.
- Logs: `logs/a1prime_launch.log`, `logs/a1prime_report.txt` (`ab_report.py`), `logs/a1prime_lost.txt`.

**Session:**
- **Startup and race entry:** fast startup (intro 25.4 s). Race entry detected, armed by `329D90` from `8EE8C` at **142.95 s**, once, after LoadRace.
- **Trace:** window 145.95–196.00 s (**50.0 s**), 240 944 spans, **0 dropped**.
- **End:** the controller ended the session on "ftrace written" at 197.6 s; no leftover process.
- **Exit code:** the runner's `exited_error (exit code 1)` is the controller's taskkill, as in A1, not a game error.
- **Errors:** 0 fatal, assert, abort, MISMATCH or `[spu-reloc]` lines.

**Measurements (VERIFIED, `ab_report.py`):**

| Metric | A1′ |
|---|---|
| Race frames / fps | 262 / 5.26 (heartbeat 5.25) |
| Frame ms | mean 190.4, p50 188.8, p95 203.9, p99 214.0 |
| Native RSX draws | 44/44 window heartbeats > 200 draws |
| Havok | 26.3 steps/s = **5.00 steps/frame** |
| PPU main wait | 131.2 ms/frame |
| Completed job spans | 54 434 (wid 0: 95/s, 29.9 busy ms/s, median 191 µs; wid 1: 774/s, 575.0 ms/s, 416 µs; wid 2: 219/s, 241.4 ms/s, 1337 µs) |
| LOST spans | reason 1: 0; **reason 2: 50 225** |
| SPURS `1003F180` workload busy | wid 0 3.3 %, wid 1 59.6 %, wid 2 24.8 %, wid 3 0.2 % |
| SPURS lanes (host cores) | sn0 0.78, sn1 0.06, sn2 0.02, sn3 0.07 |
| Coordinator passes | 2593/s |
| Top modules (share of wid time) | pvsjob 49.4 %, renderablejob 35.9 % (wid 1); vehiclephysics 91.0 % (wid 2); spuconstraints 53 % / spuxform 47 % (wid 0). All bases 0x4000; interpreter about 7.6–15 ns/insn |

**Gates (corrected T70D, `ab_report.py`):**
- PASS:
  - armed once by race entry after LoadRace;
  - window ≥ 20 s;
  - 0 dropped spans;
  - ≥ 90 % race heartbeats (no loading contamination);
  - flips and job spans recorded;
  - `SPURS_BUSY_MS` lines present;
  - A: no AOT activity;
  - 5.00 Havok steps per frame.
- **FAIL:** LOST ≤ 1 % (50 225 LOST vs 54 434 completed). **`VALID False`.**

**What the LOST records are (VERIFIED as data; the cause is a HYPOTHESIS):**
- All 50 225 have one identity: lane 0, entry **LS 0x02C90**, id `C40F75E2`, mean 7.1 µs, reason 2 (the run ended with the span open).
- The `[spujob]` log names it **wid 3**, the 0.2 %-busy workload. It is not a WWS job module: the entry is below the 0x4000 module base, and no job record carries that id.
- No completed WWS job is missing from the module table.
- HYPOTHESIS: the span opener (`spu_jobspan_branch`, any indirect branch with `$r0` = 0x3214 in policy mode) also fires inside wid 3's non-JobChain code, which then ends its run without returning to 0x3214.
- **Corrected by T70F (section 0f):** 0x2C90 is WWS job PM code, not wid 3. The `[spujob]` wid byte (LS 0x1DF at open) does not identify the code. 4 208 completed records do carry that id, and genuine job returns are partly unaccounted; the "no job record" and "none missing" statements above are wrong.
- **Effect on the comparison:** the false opens would occur equally in B1, so the A/B comparison is unaffected. But the LOST gate as written cannot pass with this runtime.

**Verdict on A1′:**
- Valid on race entry, trace completion, window length, no loading contamination, Havok rate, no runtime failure and AOT-off.
- **Formally INVALID** by the LOST gate.
- **B1 is not ready** until this is decided. Options, each offline:
  - (a) restrict the span opener to JobChain workloads (needs a rebuild, a new pin and a repeat of A1′);
  - (b) amend the gate to count LOST only for job-module entries (≥ 0x4000), re-scoring A1′ with no new launch.

  Either needs authorization. No B1 launched.

## 0f. T70F: A1′ job-span accounting, reclassified offline

**Scope:** offline only; nothing was built or launched. The A1′ run directory, `logs/a1prime_report.txt` and the raw counts are unchanged (`ftrace.txt` sha256 `23ca6b2f…`). The runtime tracing is unchanged.

**Tools:**
- `t70f/lost_census.py` → `t70f/lost_census_a1prime.txt`.
- `t70f/identity.py` → `t70f/identity_a1prime.txt`.
- `ab/ab_report.py`, now sha256 `00adc250…`; the pre-T70F copy is `logs/ab_report.py.pre-t70f` (`1b0d6da8…`).
- Re-score: `logs/a1prime_report_t70f.txt`. Self-test log: `logs/t70f_ab_selftest.log`.

**Cause of the 50 225 LOST spans (VERIFIED):**
1. **Census.** All 50 225 have one identity: lane 0, entry LS 0x02C90, id `C40F75E2`, reason 2, 4.0–196.8 µs (p50 6.1, p99 15.6). Each opens at most 12.4 µs (p50 0.2 µs) after a completed job's end, after every wid (wid 1: 38 207, wid 2: 10 670, wid 0: 468) or after a previous LOST (880).
2. **Identity.** `C40F75E2` is the FNV-1a of the 64 bytes at LS 0x2C90 of the **WWS job policy module itself** (`spu_raw/wws_job_pm.bin`, base 0xA00, offset 0x2290). It matches no entry of the 31-module manifest (`identity.py`). Every other id in the window is a manifest job entry, 14 distinct; 0 are unknown.
3. **Code path.** The PM calls a job at 0x31A8: it saves its return 0x2C90 (from `brsl` at 0x2C88) at LS 0x1500, then `bisl $r0` → job, with link 0x3214. The job returns with `bi $r0` to 0x3214. Then 0x3214 runs `lqd $r5,0x1500; bi $r5` → 0x2C90 while **`$r0` still holds 0x3214**. `spu_jobspan_branch` opens a span at any indirect branch in policy mode with `$r0` = the return address and pc ≠ it, so it opens a "job" at 0x2C90.
4. **Why it never completes.** From 0x2C90 the PM continues to the next job (wid 0) or exits its run. It never branches to 0x3214 again by itself, so the span ends at run end (LOST reason 2), or a later job's return closes it.

**Side effect on genuine jobs (VERIFIED from the code and the record sequence):** while the false span is open, `s->ctx == ctx` suppresses the next real job's open on that lane.
- **4 208 completed records carry the PM id** (all wid 0). These are genuine job returns: link 0x3214 is set only by the `bisl` at 0x3210 (lifted PM). But their start, id and steps include the PM tail, and their kind-28 module is whatever was resident at the false open (manifest 27 ×3 945, 28 ×262, none ×1). **The A1′ wid-0 per-module rows (spuconstraints 4 208 runs, spuxform 526) are therefore unreliable.**
- **937 job returns are unrecorded:** 880 + 57 PM-id records follow a LOST directly, so the lane reached 0x3214 with no span open. This is consistent with a suppressed job crossing a run boundary (PARTIAL: inferred from the sequence; no direct record).
- **Genuine incomplete WWS jobs:** 0 LOST records carry a job identity.
  - Not provable: that no PM-tail LOST record hides the start of a suppressed job. 39 of them are over 30 µs; the 880 LOST→LOST pairs imply that 880 of them did.

**Classification criteria** (in `ab_report.py`; by code identity, not address):

| Class | Rule | LOST gate | Attribution gate |
|---|---|---|---|
| `job` | id = FNV-1a(64 B) at the entry of one of the 31 manifest modules (bytes from `retail_jobs.json` + decrypted EBOOT) | counts | — |
| `pm` | id = FNV-1a(64 B) at any word of the WWS job PM image (2 357 ids; any id also in `job` is removed from `pm`) | **excluded** | its completions count as unattributed |
| `unknown` | anything else, or every span if an input file is missing | counts | its completions count as unattributed |
| unrecorded return | a `pm` record whose previous record on the lane is a LOST | — | counts |

The rules are identical for arms A and B: ids hash the LS code bytes, and AOT does not change them. A job loaded at a base that changes its entry bytes becomes `unknown`, never `pm`, so it is not excluded. Raw counts stay in `spu_jobs_lost` and `job_spans.raw_*`.

**A1′ re-scored** (window 145.95–196.00 s):

| | Count | Rate |
|---|---|---|
| Raw LOST (all classes) | 50 225 vs 54 433 completed | **47.99 %** (reported, no longer gated) |
| Qualified LOST (`job` + `unknown`) | 0 | **0.00 %** of 55 370 genuine returns |
| Completions: `job` / `pm` / `unknown` | 50 225 / 4 208 / 0 | |
| Unrecorded returns | 937 | |
| Unattributed (`pm` completions + unrecorded) | 5 145 | **9.29 %** |

**Gates (corrected):**
- PASS:
  - race-entry arm;
  - window ≥ 20 s;
  - 0 dropped spans;
  - race heartbeats;
  - flips and spans;
  - **WWS job LOST ≤ 1 % (0.00 %)**;
  - SPURS busy;
  - A: no AOT;
  - Havok 5.00.
- **FAIL:** WWS job returns attributed (9.29 % > 1 %). **`VALID False`.**

**Validation:**
- `ab_report.py --selftest`: ok. The 7 original cases pass, plus 6 new ones:
  - genuine incomplete jobs → reject;
  - unknown-identity LOST → reject;
  - `pm`-identity completions → reject;
  - unrecorded returns → reject;
  - PM post-return spans alone → accept in arm B and in arm A, with raw counters preserved (`reason2` and `raw_lost` = 190, `raw_loss_frac` 0.5, qualified 0);
  - unrecorded-return count, 4 consecutive → 3.
- `t37/job_report.py --selftest`: ok.

**Verdict:**
- The 50 225 LOST spans are **conclusively non-job**: PM post-return dispatch, opened by the tracer, excluded from the LOST gate. The qualified job loss is 0.
- **A1′ stays formally INVALID.** The same tracer defect suppresses real job opens: 4 208 wid-0 jobs lose their identity and 937 returns go unrecorded (9.3 %). Per-module job timing, which B1 is meant to compare, is therefore not trustworthy for wid 0. Missing evidence: direct records of the suppressed jobs.
- Frame time, Havok, draws and SPURS busy are unaffected by span accounting and remain a usable reference.
- **B1 is not ready.** It would carry the same defect.
- **Fix, recommended and not done (a runtime change):** the opener must not treat the PM's own branch at the return address as a job entry, for example by not opening on the indirect branch that dispatches from the job return block. That needs a code change and test, a rebuild, a new pin and a repeat of A1′, each separately authorized.

## 0g. T70G: job-span start detection corrected (offline)

**Scope:** offline only. No game build or launch, no merge or push.
- Isolated worktree `ps3recomp-t70g`, branch `agent/t70g-jobspan-start`, commit **`88feeb5`** on `bdf8224`. Patch `patches/0009-t70g-jobspan-dispatch-entry.patch` (sha256 `87510f8b…`).
- Untouched: `ps3recomp-t70` (still `bdf8224`, clean) and both pinned exes (`4a07bfc9…`, `2709eafd…`).
- Logs and tools in `t70g/`.

**Dispatch and start conditions (VERIFIED from the lifted PM `spu_raw/wws_job_pm/spu_recomp.c` and the EBOOT):**

| # | Event | PM control flow | `$r0` at the branch | Target |
|---|---|---|---|---|
| 2 | **PM dispatches a job** | 0x2C88 `brsl` → 0x31A8: stores its return 0x2C90 at LS 0x1500, `base = [0x1320]`, `off = lqd [base+0x10]`, `bisle $r0, base+off` at 0x3210 | 0x3214 (set by this `bisl`) | **base + [base+0x10]** |
| 1 | PM returns from a job | job `bi $r0` → 0x3214 (closes the span), then 0x3214 `lqd $r5,0x1500; bi $r5` | 0x3214 (stale) | 0x2C90, PM code |
| 3 | PM calls a helper | 18 other `bi`/`bisl` sites (switch tables, 0x3540/0x3558 `bisl` with links 0x3554/0x3574) | ≠ 0x3214, or a target that is not the entry | PM code |
| 4 | Job calls back into the PM | the job's `bisl $r0,$rX` through the PM service table | the job's own link | PM service |
| 5 | Job resumes after a PM call | host return to the job's next word, or the driver's restart dispatch | restored job link | inside the job (span already open: no reopen) |
| 6 | Workload switch | `exitToKernel` / `selectWorkload` HLE addresses; the run ends | — | — |
| 7 | Interruption | the run ends with the job open (`spu_run_with_halt` → LOST reason 2), or another lane's job opens on the thread (reason 1) | — | — |

- 0x3214 is set as a link only by the `bisl` at 0x3210; it is the only `spu_link(0x3214)` in the PM.
- All 31 manifest modules keep their entry offset at header +0x10 (31/31 against `retail_jobs.json`).

**Correction (`runtime/spu/spu_jobspan.h`):**
- A span now opens only if `$r0` = the job return **and** pc = `spu_jobspan_dispatch_entry(ls, cb)`, the PM's own computation (`base = word[cb]`, `+ word[(base+0x10) & ~0xF]`).
- This is not a module whitelist or an address threshold. Without a configured code base nothing opens; MotorStorm's knob is `3214:1320`.
- Unchanged: completion at 0x3214 (drain and driver paths), LOST reasons 1 and 2, per-thread/per-lane state, module and AOT records, the knob gate (off = one load), and every SPU execution path.
- Knob documentation updated in `ps3_ftrace.h`.

**Regression tests:**
- **Path test (real SPU runtime).** The six T70C scenarios plus six new ones that mirror the lifted PM's return block and dispatch: `pm-tail`, `seq3`, `seq3-co`, `seq-halt`, `lane-b`, `lifted` (a job entry with lifted code, the AOT-style dispatch).
  - **Before the fix: 10 failures**, reproducing A1′ exactly: LOST at `0x02C90` after the last job; jobs 2+ recorded at entry 0x2C90; the halted job lost under the PM identity (`t70g/base_path_newtests.log`).
  - **After: 0 failures.** Each job gets one record at its own entry, steps and module. No LOST record without an interruption. The halted job is one LOST record with its own entry.
- **Unit test (`tools/test_spu_jobspan.py`).** Added: the PM return branch (pc 0x2C90, `$r0` 0x3214), off-entry branches (0x4400, 0x4104) and a knob without a code base. 30 + 1 + 2 + 2 checks, 0 failures.
- **Guest-state equivalence:** LS, GPRs, pc, interrupt enable and host depth are identical with tracing on and off in all **12** scenarios.

**Offline validation** (MSVC + LLVM 23.1.3 environment, `t70g/run_test.cmd`):

| Test | Result |
|---|---|
| `tools/test_spu_jobspan.py` | 0 failures |
| `tests/test_spu_jobspan_path.py` | 0 failures, 12/12 states identical |
| `tests/test_spu_reloc_job.py` (WWS relocation/AOT) | 85 PASS / 0 FAIL |
| `tools/test_spu_lifter_reloc.py` | 0 failures |
| `tools/test_ppu_trace.py` (PT tracer and arm) | PASS |
| `ab/ab_report.py --selftest` (T70F classes) | ok |
| clang-cl, exact `build.ninja` commands re-pointed to the tree (`t70g/compile_tu.py`): `spu_channels.c`, `spu_drain.c` | base and T70G compile, exit 0. Warnings identical except 2 new `-Wdeclaration-after-statement` in `spu_jobspan.h`, a class the file already has (`t70g/warn_diff_*.txt`) |
| Public audit `--staged` | the same 25 pre-existing items as T70C, byte-identical (`t70g/audit_staged.log`) |
| A1′ offline replay of the new condition (`t70g/a1prime_entry_check.py`) | all **50 224** genuine job starts satisfy `entry = base + [base+0x10]`; none of the 4 208 PM-id starts does; 0x2C90 is no module's dispatch entry |

**Remaining attribution risks:**
- **HYPOTHESIS:** the 937 unrecorded returns of A1′ were suppressed-open jobs crossing a run boundary. With the fix their opens are no longer suppressed, but a job that spans runs still gets a LOST record (reason 2) at the first run's end. Its resumed return then closes nothing. The next A1′ will show whether such crossings occur and how often.
- A PM that keeps its code base elsewhere, or a module without the +0x10 entry field, opens no spans: under-counting, never false spans. `ab_report.py` still classifies by identity.
- The opener reads LS at dispatch. AOT does not change LS, so arms A and B see the same condition.

**Next build (prepared, not run; each step separately authorized):**
1. `t70g/configure_aot_t70g.cmd`: the T70 configure with `-DPS3RECOMP_DIR=ps3recomp-t70g` into a **new** `build\motorstorm-t70g-aot`, so the T70D build tree is untouched.
2. `t70g/build_aot_t70g.cmd`.
3. Pin it in a new `ab/exe-t70g/` + `exe_pin_t70g.json`. This needs `run_t70_ab.py`'s `EXE`/`PIN` pointed there; `prepare` refuses existing pins.
4. Repeat A1′, then B1.

**Readiness:** the fix is ready for a separately authorized rebuild. A1′ must be repeated on the new exe before B1.

## 0h. T70H: corrected tracer built and pinned, VERIFIED offline

One authorized isolated build. Nothing was launched, merged or pushed. `ps3recomp-t70g` and `ps3recomp-t70` were clean before and after. The build wrote only to `build/motorstorm-t70g-aot` (plus untracked `__pycache__` in `ps3recomp-t70g`). Logs are in `t70h/`.

| Item | Result |
|---|---|
| Source | `ps3recomp-t70g` `agent/t70g-jobspan-start` @ **`88feeb524a98603946323843d3adc33749e28cbc`** (parent `bdf8224`). It differs from T70D's source only in the 6 T70G files. The T70G scripts equal T70D's `tools/configure_aot.cmd` and `build_aot.cmd` apart from the paths |
| Configure | `t70g/configure_aot_t70g.cmd` exit 0, "Wws job AOT: 31 module(s), PS3_SPU_WWS_AOT=1 to enable". Cache: `PS3RECOMP_DIR=…\ps3recomp-t70g`, `MSPR_WWS_AOT=ON`, `PORT_SPU_AVX2=OFF`, source `port-t70` (`configure.log`) |
| Build | `t70g/build_aot_t70g.cmd` exit 0: full build of 312 steps, link OK, 0 `error:` lines (`build.log`) |
| Flags | `t70h/ninja_diff_t70g.py` **PASS**: 308/308 objects equal T70D's in rule, source, DEFINES, FLAGS and INCLUDES once the ps3recomp-t70g → ps3recomp-t70 paths are mapped. No object is only in one build (`ninja_diff.log`) |
| Executable | 404,267,520 bytes, sha256 **`ae7ed7becf06f18b47d4e9bb003783cae32eb65f1e6f80621b39bf68e383a55e`** |
| Registration | `tools/inspect_aot_exe.py` **PASS**: 31/31 signatures and body hashes in the image; `.CRT$XCU` constructor present; 31/31 register functions defined (`inspect_exe.log`). `verify_wws_reloc.py`: 31/31 PASS (`verify_wws_reloc.log`) |
| New opener compiled in | Disassembled against T70D: `spu_jobspan_begin` is the only changed function in `spu_channels.c.obj` (285 → 315 instructions). The added code loads the be32 at `(base + 0x10) & 0x3FFF0` and adds it to the base. `spu_drain.c.obj` is unchanged, as expected, since it only calls `spu_jobspan_end`. The 50-byte sequence occurs **once** in the new exe and **0** times in the T70D or A1 exes (`find_opener_bytes.py`, `opener_in_exe.log`, `jobspan_begin_t70{d,g}.txt`) |
| Defaults | AOT runs only with `PS3_SPU_WWS_AOT` exactly `1` (inspection source gate + reloc test "constructor registers only when PS3_SPU_WWS_AOT=1"). Job spans need `PS3_FTRACE` + `PS3_FTRACE_SPUJOB` with a code base (`--off`, `--off-knob`, `--no-cb` tests). The arm needs `PS3_FTRACE_ARM` |
| Race-entry trace | The exe contains `PS3_FTRACE_ARM`, `[ftrace] armed at`, `armed_us=`, `[spujob] lane`, `PS3_FTRACE_SPUJOB`, `PS3_SPU_WWS_AOT` and `[spu-reloc]` (`strings.log`). `test_ppu_trace`: arm, never and late all PASS |
| Pin | new **`ab/exe-t70g/`** + `ab/exe_pin_t70g.json` (pin = build = `ae7ed7be…a55e`). `ab/exe/` (`4a07bfc9…f672`), `ab/exe-t70d/` (`2709eafd…2cec`) and both pin JSONs were byte-identical before and after (`pin.log`) |
| Harness | `run_t70_ab.py` now points to `exe-t70g` / `exe_pin_t70g.json`, and `prepare` requires `PS3RECOMP_DIR` = `ps3recomp-t70g` in the cache (pre-T70H copy in `logs/run_t70_ab.py.pre-t70h`). `dryrun A` / `dryrun B` exit 0 on the pinned exe: `PS3_FTRACE=120:76`, `PS3_FTRACE_ARM=329D90:8EE8C:3`, `PS3_FTRACE_SPUJOB=3214:1320`. Arm B adds `PS3_SPU_WWS_AOT=1` + `VERIFY`, arm A has no AOT variables; the runner uses `--timeout 210` and the controller stops at 205 s |

**Offline regression on `88feeb5` (`t70h/`):**

| Test | Result |
|---|---|
| `tools/test_spu_jobspan.py` (incl. `--no-cb`) | 0 failures |
| `tests/test_spu_jobspan_path.py` | 0 failures; tracing on = off in **12/12** scenarios |
| `tests/test_spu_reloc_job.py` | 85 PASS / 0 FAIL |
| `tools/test_spu_lifter_reloc.py` | 0 failures |
| `tools/test_ppu_trace.py` | PASS |
| `ab/ab_report.py --selftest` | ok |
| `tools/t70c_controller_sim.py` against the updated harness | 3/3 PASS (fast start ends at 197.4 s; slow start INVALID at 172 s; armed but never written ends at 205 s) |
| Public audit `--staged` (in `ps3recomp-t70g`) | 25 items, byte-identical to the T70G baseline (`--tree` adds only the 2 untracked `__pycache__` directories) |

**Remaining risks:**
- **HYPOTHESIS:** jobs that cross a run boundary still get LOST reason 2 (section 0g). A1″ will show how often.
- Not proven offline: that the CRT runs the AOT constructor in the linked exe (arm B's `[spu-reloc] … resident re-hash on` gate), and that the new opener fires in the game (A1″'s job counts and `ab_report.py` identity classes).
- The build reused shared inputs (`generated/ppu-hooked-staging`, `port/spu`, `generated/spu_raw/wws_reloc`). They were not modified, and the flag comparison shows the same objects. Other sessions' concurrent work (`t79/`) is outside this build.

**Readiness:** the exe and harness are ready for A1″ (AOT off) on `exe-t70g`. It needs separate authorization; B1 follows only after A1″ passes.

## 0i. T70I: A1″ corrected baseline (AOT off), one session: VALID, all gates PASS

**Run identity:**
- Exe `ab/exe-t70g/`, sha256 `ae7ed7be…a55e`, checked before launch, recorded in `inputs.json` and unchanged after.
- Command: `py -3 generated/analysis/t70/ab/run_t70_ab.py launch A`, one launch. Argv is the same as `dryrun A`:
  - AOT unset;
  - `PS3_FTRACE=120:76`, `PS3_FTRACE_ARM=329D90:8EE8C:3`, `PS3_FTRACE_SPUJOB=3214:1320`;
  - `SPURS_BUSY_MS=1000`.
- The exe has no SPURS max-contention knob (no T79 code), so contention stays 1.
- Fresh verified hdd0/hdd1 in `ab/runtime-20261026-191650-A`. No driving, no TEX_SAVE, no T75/T77 changes, no other flags.
- Run dir `generated/runs/20261026-191651-t70-ab-a` (`ftrace.txt` sha256 `7da096a3…ec67`).
- Logs: `logs/a1pp_launch.log`, `logs/a1pp_report.txt` (`ab_report.py`, T70F rules unchanged), `logs/a1pp_identity.txt` (`t70f/identity.py`).

**Session:**
- Fast startup: intro at 24 s.
- Race entry armed by `329D90` from `8EE8C` at **144.43 s**, once, after LoadRace.
- Window 147.43–196.00 s (**48.6 s**), 178 523 spans, **0 dropped**.
- The controller ended the session on "ftrace written". No leftover process.
- `exited_error (exit code 1)` is the controller's taskkill, as in A1 and A1′.
- 0 fatal, assert, abort or MISMATCH lines, and 0 `[spu-reloc]` lines.

**Gates (`ab_report.py`, unchanged since T70F):** all PASS, **`VALID True`**:
- armed once by race entry after LoadRace;
- window ≥ 20 s;
- 0 dropped spans;
- 44/44 window heartbeats > 200 draws (no loading contamination);
- flips and job spans recorded;
- **qualified LOST ≤ 1 %**;
- **unattributed returns ≤ 1 %**;
- `SPURS_BUSY_MS` lines present;
- A: no AOT activity;
- **5.00 Havok steps/frame**.

**Job accounting (VERIFIED):**

| | A1′ (T70D tracer) | **A1″ (T70G tracer)** |
|---|---|---|
| Raw completed / raw LOST | 54 434 / 50 225 (48.0 %) | **50 695 / 0 (0 %)** |
| PM-id (`C40F75E2`, LS 0x2C90) starts / completions | 54 433 / 4 208 | **0 / 0** |
| Qualified LOST | 0 % | **0 %** (reason 1: 0, reason 2: 0) |
| Unattributed (pm/unknown completions + unrecorded returns) | 9.29 % | **0 %** (0 + 0) |
| Unknown identities | 0 | **0** |

- **Identity coverage:** all completions carry 14 distinct ids, and each one is a manifest job entry at base 0x4000 + its header entry offset. Every kind-28 module id is in the 31-module manifest. The other 17 manifest modules did not run in this race window.
- The T70G hypothesis (937 unrecorded returns = jobs crossing a run boundary) does not show up here: 0 reason-2 LOST.

**Per-module WWS timing (interpreter, all at base 0x4000):**

| wid | module | runs | total ms | med ms | p95 ms | max ms | share of wid | ns/insn |
|---|---|---|---|---|---|---|---|---|
| 0 | spuconstraints | 3 920 | 795.4 | 0.186 | 0.431 | 0.572 | 53.3 % | 10.45 |
| 0 | spuxform | 489 (+1) | 696.0 | 1.290 | 2.047 | 2.855 | 46.6 % | 10.69 |
| 1 | pvsjob | 27 361 | 13 581.3 | 0.302 | 1.131 | 2.554 | 48.7 % | 9.65 |
| 1 | renderablejob | 5 108 | 10 092.1 | 1.825 | 5.027 | 12.629 | 36.2 % | 10.04 |
| 1 | trailsupdate | 244 | 2 421.6 | 9.488 | 13.376 | 15.332 | 8.7 % | 8.32 |
| 1 | octreequery | 1 957 | 742.0 | 0.092 | 1.656 | 2.644 | 2.7 % | 9.50 |
| 1 | groundrushjob | 245 | 518.7 | 2.104 | 2.872 | 4.266 | 1.9 % | 8.46 |
| 1 | ProcessEmittersModule | 670 | 314.0 | 0.350 | 1.146 | 2.289 | 1.1 % | 11.61 |
| 1 | groundrushvisibilityjob | 245 | 144.5 | 0.447 | 1.042 | 1.085 | 0.5 % | 12.01 |
| 1 | generatefogtable | 244 | 60.5 | 0.228 | 0.404 | 0.465 | 0.2 % | 11.03 |
| 2 | vehiclephysics | 7 840 | 10 724.7 | 1.375 | 1.954 | 3.321 | 89.5 % | 11.58 |
| 2 | screenrushjob | 732 | 1 083.3 | 1.276 | 3.011 | 3.123 | 9.0 % | 10.80 |
| 2 | BasicParticleFillerModule | 664 | 95.7 | 0.057 | 0.436 | 0.877 | 0.8 % | 13.40 |
| 2 | occjob | 976 | 72.9 | 0.068 | 0.131 | 0.170 | 0.6 % | 18.13 |

**Frame-performance baseline (VERIFIED):**

| Metric | A1′ | **A1″** |
|---|---|---|
| Race frames / fps | 262 / 5.26 | **244 / 5.04** (heartbeat 5.04) |
| Frame ms mean / p50 / p95 / p99 | 190.4 / 188.8 / 203.9 / 214.0 | **198.5 / 197.6 / 209.3 / 227.3** |
| Havok | 5.00 steps/frame | **5.00** (25.2 steps/s) |
| RSX draws | 44/44 heartbeats > 200 | **44/44 > 200** |
| PPU main wait | 131.2 ms/frame | **135.4 ms/frame** |
| SPURS `1003F180` busy wid 0/1/2/3 | 3.3 / 59.6 / 24.8 / 0.2 % | **3.4 / 59.6 / 25.4 / 0.2 %** |
| Job rate / busy per wid 0/1/2 | 95, 774, 219 /s | **91, 743, 210 /s; 30.8, 573.9, 246.6 busy ms/s; median 200, 433, 1352 µs** |
| SPU lanes (host cores) sn0–3 | 0.78 / 0.06 / 0.02 / 0.07 | **0.77 / 0.08 / 0.02 / 0.08** |
| Coordinator passes | 2 593/s | **2 588/s** |

- About 4 % slower than A1′ on a different exe. This is within the spread seen so far (two sessions). The workload shares match closely. B1 must run on the same `exe-t70g` pin, and should be compared with A1″ only.

**Remaining instrumentation defects:**
- **VERIFIED, cosmetic:** one completion (spuxform, id `6B385E11`) ends at 196.000 s, the hard end of the trace. Its steps and module records fell outside the window, so the per-module table shows it as an unnamed `job id 6B385E11`, 1 run, base 0x0. It changes no gate.
- Lane load still sits on sn0 (0.77 cores). That is a scheduling observation, not a tracer defect; T79 is out of scope here.

**Verdict on A1″:** VALID baseline. It meets every acceptance gate under unchanged T70F rules. **B1 is ready**, using the same pin `exe-t70g` and `run_t70_ab.py launch B`, and it needs separate authorization. No B1 was launched.

## 0j. T70J: B1 (WWS AOT on), one session: VALID, all gates PASS; race fps 5.04 → 11.32

**Run identity:**
- Exe `ab/exe-t70g/` `ae7ed7be…a55e`, checked before launch, recorded in `inputs.json` and unchanged after.
- Command: `py -3 generated/analysis/t70/ab/run_t70_ab.py launch B 4000`, one launch. The base comes from A1″'s kind-28 records, every job at 0x4000, as in the section 7 procedure.
- Argv is A1″'s plus `PS3_SPU_WWS_AOT=1`, `PS3_SPU_WWS_AOT_VERIFY=1` and `PS3_SPU_WWS_AOT_BASES=4000` (`logs/b1_dryrun.log`).
- Contention 1 (no knob in this exe). No RSX_RT_READBACK, TEX_SAVE, driving or other flags. Fresh verified HDD in `ab/runtime-20261026-194909-B`.
- Run dir `generated/runs/20261026-194910-t70-ab-b` (`ftrace.txt` `04339200…ee5f`).
- Logs: `logs/b1_launch.log`, `logs/b1_report.txt`, `logs/b1_identity.txt`, `t70j/compare.txt` (`t70j/compare.py`).

**Session:**
- Intro at 24 s.
- Race entry armed at **140.96 s**, once, after LoadRace.
- Window 143.96–196.00 s (**52.0 s**), 544 716 spans, **0 dropped**.
- The controller ended the session on "ftrace written"; no leftover process. Exit code 1 is the controller's kill.

**Gates (`ab_report.py`, unchanged):** all PASS, **`VALID True`**:
- race-entry arm;
- window ≥ 20 s;
- 0 dropped;
- 49/49 heartbeats > 200 draws (stable race rendering, no loading contamination);
- flips and jobs recorded;
- qualified LOST 0 %;
- unattributed 0 %;
- `SPURS_BUSY_MS` present;
- **B: AOT registered with VERIFY**;
- **B: no MISMATCH**;
- **Havok 5.00 steps/frame**.

**Correctness (VERIFIED):**
- **Registration and activation:** `[spu-reloc] 1 allowed base(s), resident re-hash on` (the constructor ran in the linked exe, which T70H could not prove offline). There are 64 `lane 0 job at LS 0x04000 … : AOT` lines; the logging is capped.
- **AOT executions:** 126 361 kind-29 records, **116 937 INSTALLED + 9 424 RESIDENT**. `aot_ran_frac` is 1.0, so **no job-level fallback to the interpreter**.
  - Per module, every completion of every module ran AOT. For example, pvsjob 65 917, vehiclephysics 18 833, renderablejob 16 157, spuconstraints 9 408 (588 installed + 8 820 resident).
- **Mismatches and exceptions:** 0 MISMATCH, 0 `body differs`, 0 fatal, assert or abort.
  - The only matching lines are 16 `[mfc-list] STALL` and 16 `[spu-int] TAKEN` from the job PM's list-DMA stall-notify path, plus the 4 `SetExceptionEventHandler` registrations. A1″ has the same lines, so these are guest behaviour, not a scheduler stall.
- **Identities:** 126 362 completions carry **15** ids, all manifest job entries at 0x4000 + header offset. The 15th, ParticleSortModule, is new at 79 runs. 0 PM-id, 0 unknown. Raw and qualified LOST 0, unattributed 0.
- **Cosmetic (as in A1″):**
  - one vehiclephysics completion at the 196.000 s hard end has no module record, so it shows as `job id 02E29DDE`, base 0x0;
  - single runs listed under another wid come from the `[spujob]` wid byte, which is not an identity (T70F).
- **Residual interpretation inside AOT jobs:** renderablejob still runs **680 M interpreted instructions**, about 42 k per run against about 197 k per run in A1″, so roughly a fifth of its code. This is consistent with its 61 lift hand-off words; other modules interpret ≤ 15 instructions per run. *HYPOTHESIS* on the cause.

**A1″ vs B1 (same exe, one session each; measured):**

| Metric | A1″ | B1 | Δ | % |
|---|---|---|---|---|
| Race fps | 5.04 | **11.32** | +6.28 | **+124.6 %** |
| Frame ms mean | 198.5 | 88.3 | −110.2 | −55.5 % |
| Frame ms p50 | 197.6 | **82.1** | −115.5 | **−58.5 %** |
| Frame ms p95 | 209.3 | 132.0 | −77.3 | −36.9 % |
| Frame ms p99 | 227.3 | 138.4 | −88.9 | −39.1 % |
| PPU main wait ms/frame | 135.4 | **47.9** | −87.5 | **−64.6 %** |
| Havok steps/frame | 5.00 | 5.00 | 0 | 0 |
| Draws (heartbeats > 200) | 44/44 | 49/49 | | |
| WWS job time per race second | 851 ms | 567 ms | −284 | −33 % |
| WWS job time per frame (sum of modules) | 169.4 ms | **50.2 ms** | −119.2 | **−70.4 %** |
| Lane-0 job-busy (share of window) | 85.1 % | 56.8 % | −28.3 pt | |
| Dispatch gap lane 0, median / p95 | 40.3 / 73.8 µs | 37.2 / 64.6 µs | −3.1 / −9.2 µs | −8 / −12 % |
| SPU lanes sn0/1/2/3, host cores | 0.77/0.08/0.02/0.08 | 0.59/0.06/0.04/0.07 | sn0 −0.18 | −23 % |
| SPURS `1003F180` busy wid 0/1/2/3 | 3.4/59.6/25.4/0.2 % | 2.2/48.8/11.7/0.4 % | | |
| Jobs per second (all wids) | 1 043 | 2 429 | | +133 % (tracks fps) |
| Coordinator passes per second | 2 588 | 4 837 | | +87 % |

**Per-module (median ms; ms per frame):**

| Module | A1″ med | B1 med | **speedup** | A1″ p95/max | B1 p95/max | A1″ ms/frame | B1 ms/frame | Δ |
|---|---|---|---|---|---|---|---|---|
| pvsjob | 0.302 | 0.078 | **3.9×** | 1.131/2.554 | 0.309/1.645 | 55.66 | 15.12 | −72.8 % |
| vehiclephysics | 1.375 | 0.250 | **5.5×** | 1.954/3.321 | 0.391/0.752 | 43.95 | 8.26 | −81.2 % |
| renderablejob | 1.825 | 0.420 | **4.3×** | 5.027/12.629 | 2.979/6.365 | 41.36 | 22.49 | −45.6 % (runs/frame 20.9 → 27.5) |
| trailsupdate | 9.488 | 0.704 | **13.5×** | 13.38/15.33 | 0.885/1.004 | 9.92 | 0.72 | −92.7 % |
| screenrushjob | 1.276 | 0.095 | **13.4×** | 3.011/3.123 | 0.147/0.269 | 4.44 | 0.30 | −93.2 % |
| spuconstraints | 0.186 | 0.045 | 4.1× | 0.431/0.572 | 0.079/0.255 | 3.26 | 0.75 | −76.9 % |
| octreequery | 0.092 | 0.024 | 3.8× | 1.656/2.644 | 0.212/0.386 | 3.04 | 0.45 | −85.3 % |
| spuxform | 1.290 | 0.261 | 4.9× | 2.047/2.855 | 0.400/0.535 | 2.85 | 0.55 | −80.8 % |
| groundrushjob | 2.104 | 0.467 | 4.5× | 2.872/4.266 | 0.563/1.023 | 2.13 | 0.65 | −69.5 % |
| ProcessEmittersModule | 0.350 | 0.072 | 4.9× | 1.146/2.289 | 0.317/0.509 | 1.29 | 0.31 | −76.1 % |
| groundrushvisibilityjob | 0.447 | 0.138 | 3.2× | 1.042/1.085 | 0.468/0.628 | 0.59 | 0.19 | −68.6 % |
| BasicParticleFillerModule | 0.057 | 0.028 | 2.0× | 0.436/0.877 | 0.185/0.402 | 0.39 | 0.16 | −60.2 % |
| occjob | 0.068 | 0.025 | 2.7× | 0.131/0.170 | 0.047/0.311 | 0.30 | 0.12 | −60.0 % |
| generatefogtable | 0.228 | 0.093 | 2.5× | 0.404/0.465 | 0.129/0.151 | 0.25 | 0.10 | −60.1 % |
| ParticleSortModule | — | 0.014 | n/a | — | 0.018/0.045 | 0 | 0.00 | new |

**Measured vs synthetic:**
- The measured in-game median speedups are 2.0–13.5× per module.
- The game result is +125 % fps and −58 % p50 frame time, from **one A/B pair**.
- The synthetic `bench_spu_reloc_job.py` figures (2.6× / 7.4× / 8.3×, section 3) are microbenchmarks and are not the source of any figure above.
- Per-run variance is untested. A1′ against A1″ differed by about 4 % (different exes), well below this effect.

**AOT module coverage:**
- 15 of 31 manifest modules ran in the race, and all 15 ran AOT on every job.
- The other 16 did not run in this window, so they are untested in-game (they are covered offline by the T70 differential, section 3).

**Remaining bottlenecks:**
1. **Single SPU lane.** All 126 362 jobs ran on lane 0 (contention 1). Lane 0 is still 56.8 % job-busy, and the PPU still waits 47.9 ms of the 88 ms frame. The other three lanes are idle for WWS.
2. **renderablejob:** 22.5 ms/frame, 45 % of WWS time, about a fifth of it still interpreted inside AOT jobs, and p95 2.98 ms.
3. pvsjob: 15.1 ms/frame at 112 runs/frame. That is dispatch volume; per job it is already 0.078 ms.
4. Dispatch gaps of about 37 µs median × 2 429 jobs/s ≈ 9 % of lane-0 time.

**Verdict on B1:** VALID, with no correctness failure. WWS AOT more than doubles race fps (5.04 → 11.32), with Havok unchanged at 5.00 steps/frame.

**Recommended next experiment (each needs its own authorization):**
1. Offline first: find which renderablejob paths still drop to the interpreter (hand-off words and their call sites), and whether the lift can cover them.
2. Then one replication pair, A2/B2 on the same pin, to bound run-to-run variance.
3. After that, the T79 max-contention change on top of AOT. It is the largest remaining lever (one lane carries all WWS work), but it must be a separate, isolated experiment against B1.

## Verdict

**Built (T70B); A1 ran but is not a valid baseline (section 0b). T70C fixed the job-span close and replaced the fixed window with a race-entry-armed one, offline (section 0c). T70D rebuilt and pinned the corrected exe `2709eafd…2cec` in `ab/exe-t70d/` (section 0d). A1′ ran (section 0e). T70F (section 0f) proved its 50 225 LOST spans are the PM's own post-return dispatch (LS 0x2C90), not jobs: qualified job loss 0 %. But the same tracer defect leaves 9.3 % of job returns unattributed, so A1′ stays formally invalid and T70G fixed the opener offline (`88feeb5`, section 0g). T70H built and pinned it as `ae7ed7be…a55e` in `ab/exe-t70g/` (section 0h). A1″ on that exe is VALID with every gate passing: 0 % qualified LOST, 0 % unattributed and 0 PM-id starts (section 0i). B1 (section 0j) is VALID on every gate with 0 MISMATCH: race fps 5.04 → 11.32 (+125 %), p50 frame 197.6 → 82.1 ms and PPU wait 135.4 → 47.9 ms/frame, from one A/B pair.**
- Every offline blocker from T60/T69 is resolved.
- Still unknown, and only a runtime run can settle them:
  - the load addresses the race actually uses;
  - which modules the race runs;
  - whether in-race writes trip VERIFY;
  - any FPS effect.

## 1. Relocation artifacts: `generated/spu_raw/wws_reloc`, VERIFIED

| Step | Result |
|---|---|
| Source | `generated/decrypted/EBOOT.elf`, sha256 `bbb7fe25…b287` |
| Re-extraction | `t37/retail_jobs.py --extract` → 31/31 images, byte-identical to `generated/analysis/t37/modules`; names 31/31 from the game's own name tables (`logs/retail_jobs_reextract.log`) |
| LibMP3 code ends | `modules.json` `text_end` 0x16740 / 0xEBF8 equal the `.text` ends of the two embedded SPU ELFs (re-read from the EBOOT) |
| Lift | `ps3recomp-t70/tools/lift_wws_reloc.py … --names modules.json --ctor` → 31/31 registered, 5,667 functions, 68 hand-off words (renderablejob 61 and vehiclephysics 7, all in rodata tails). Output is byte-identical to T37's lift for all 31 TUs and the manifest. `wws_reloc_register.c` differs only by the opt-in constructor (`logs/lift_wws_reloc.log`). |
| Independent check | `tools/verify_wws_reloc.py`, **PASS 31/31** (`logs/verify_wws_reloc.log`) |
| Hashes | register.c `d347d562…082a`, manifest `a084eee5…d298` |

**What `verify_wws_reloc.py` checks for each registration:**
- the module bytes are the EBOOT bytes at the retail image offset;
- the sha256 matches;
- magic, identifier and entry bytes match, and entry offset = header +0x10;
- link base = header +0x28 = 0x4000;
- the body hash, re-implemented independently from `spu_reloc.h`, is correct;
- image IDs are unique, and the manifest agrees;
- the PM registration is image 1297305682, `0x1320`, `0x3214`.

**Trap found and avoided.** Passing `names.json` instead of `modules.json` drops the LibMP3 `text_end`s. That lifts their data as code: 959/700 functions and 308/181 hand-offs instead of 840/665. The registration is unchanged, but the TUs differ from T37's lift.

**Exact procedure:** `tools/gen_wws_reloc.sh`. It refuses to overwrite an existing lift.

## 2. Clean integration: `agent/t70-wws-aot-race` in `ps3recomp-t70`

Base: `c529ab0`, the T62/T64C exe line, which contains the T61 font fix. Built from it: `build/motorstorm-t62-font-c529ab0`, exe `162afb4a…`.

| # | Commit | Content |
|---|---|---|
| 1 | `ad69e8e` | cherry-pick -x `fca46a8` (link-register fix) |
| 2 | `54c06d2` | cherry-pick -x `0974281` (job spans) |
| 3 | `d1b4119` | cherry-pick -x `6b0d3dc` (WWS AOT runtime and hardening) |
| 4 | `8de3590` | cherry-pick -x `121686d` (tests) |
| 5 | `76d5ca1` | T69 instrumentation (`SPURS_BUSY_MS`, poll-log throttle), kept separate |
| 6 | `6817933` | instrumentation fix: per-instance, per-lane accounting (§4) |

- **Same content as T59.** Commits 1–4 have the same diff as `af37553..121686d`; only hunk offsets differ (VERIFIED by diffing the two patches).
- **Not included:**
  - the 6 T24 SPU commits `c0ed872…af37553` (not in the T64C exe);
  - T68/T71 renderer changes.
- **Patches:** `patches/0001–0006`.
- **Default behaviour:** AOT stays off by default. The constructor registers only when `PS3_SPU_WWS_AOT` is exactly `1`; `PS3_SPU_WWS_AOT_VERIFY=1` enables the re-hash.

**Build configuration, VERIFIED by configure only.**
- `tools/configure_aot.cmd` uses the same environment as `build_port.cmd` and the T62 cache values, without the generator steps that rewrite shared `generated/` outputs.
- Patched port copy: `port-t70/CMakeLists.txt` = `port/` + the T54 patch (sha256 `279698ce…76be`, the same as T60's).
- CMake prints `Wws job AOT: 31 module(s)`.
- `tools/ninja_diff.py` (PASS) compares against the T64C build:
  - all 276 common compile entries have identical DEFINES/FLAGS/INCLUDES, after mapping t62 → t70 and port → port-t70;
  - the only additions are the **32 AOT TUs**, all with the lifted-SPU flags (`-DSPU_USE_DISPATCH_MT -fwrapv -O2 -msse4.1`, no AVX2).
- No build input (`ppu-hooked-staging`, `spu_raw/wws_job_pm`, `overlays`, `ppu`, `decrypted`, `port`) has changed since the T64C exe was linked.

**`SPU_USE_DISPATCH_MT`, checked rather than assumed.** The game compiles lifted SPU code with this flag and the AOT tests don't. It has no effect here: the reloc lift emits 0 `SPU_IB_DISPATCH` sites; all 334 indirect branches call the full resolver, where the AOT hook lives. A negative control (define set, MT source not linked) still links, which confirms the flag is unused by these TUs.

## 3. Offline tests (logs in `logs/`)

| Test | Base `c529ab0` | Branch HEAD `6817933` |
|---|---|---|
| `tests/test_spu_reloc_job.py`: equivalence at 4 bases, relocation, residency, DMA replace, 18 fallback states, allowlist, VERIFY/non-DMA write, R1/R2, constructor | n/a | **85 PASS / 0 FAIL** |
| `tools/test_spu_lifter_reloc.py` | n/a | 13 / 0 |
| `tools/test_spu_jobspan.py` | n/a | 8 / 0 |
| Retail differential (`tools/fuzz_retail_t70.py`): 145 functions in 31 modules, interpreted vs AOT, all GPRs and LS | n/a | **0 mismatches** at 0x4000 (5,068 trials), 0x15C00 (5,025), 0x9400 (5,062) |
| T24 suite `spu_all.sh` (15 tests) | 10 rc=0, 5 BUILDFAIL | **identical**: 10 rc=0, the same 5 BUILDFAIL |
| clang-cl compile-only, T62 flags (`tools/compile_check.py`): 31 lifted + register + 4 changed runtime TUs | — | 36/36 OK |
| Public audit `--staged` | 25 items | 25 items, byte-identical output |
| Synthetic benchmark (`bench_spu_reloc_job.py`) | — | AOT 2.6× (float+switch), 7.4× (int+switch), 8.3× (int). **Not a game claim.** |

**The 5 BUILDFAILs are expected.** Those test files (`putllc_ppu_cas`, `getllar_backoff`, `park_wake_race`, `interp_receive_event_stop`, `ef_dma_wake`) were added by the 6 T24 commits, which are not on the T64C line.

**Audit process deviation.** Commit 5's audit ran just after the commit; its output equals the base.

## 4. Instrumentation (`SPURS_BUSY_MS=<ms>`)

**Defect found and fixed (commit 6).** The T69 version had two problems:
- one global per-wid table for all SPURS instances, so Multistream's wid 0 merged into MotorStorm2's;
- it printed only for `s_inst[0]`.

**Now:** counters live in each lane's slot, and each instance's coordinator prints:
```
[spurs-busy] spurs=0x… sn=N hosttid=T wid=W window_ms=… runs=… polled=… busy_ms=… pass=…
```
The `hosttid` joins directly to `performance.json`'s per-TID CPU. That join is the missing 19848 → lane → wid mapping.

| Requirement | Evidence |
|---|---|
| No guest state change | reads and writes only host fields (`slot->busy_*`, `host_tid`), no `vm_base` or ctx access (code review) |
| No scheduling change | timing wraps `spu_run_policy_module`; nothing feeds admission. `test_spurs_scheduler` gives 8/8 PASS with the instrumentation off and on, with identical PASS lines. |
| Overhead | off: one cached `getenv` per run. On: 2 `timespec_get` per PM run (about 1k/s) plus ≤ nspus × active wids lines per window, printed under the coordinator lock once per window. The poll-log throttle removes about 960 unbuffered lines/s. |
| Interpreter and AOT | measures the whole PM run either way; the AOT runs inside it |
| Disable | unset `SPURS_BUSY_MS` (default) |

**Limit.** A run is counted in the window in which it ends; use 1000 ms windows.

## 5. Runtime identity risks (HYPOTHESIS until A runs)

1. **Load bases.** The PM picks the code base from a slot allocator. Equivalence is proven at 0x4000/0x8C00/0x15C00/0x30000 (synthetic) and 0x4000/0x9400/0x15C00 (retail functions). Any other base is still correct by construction (`ila` immediates kept), but untested.
2. **In-race bytes ≠ retail bytes.** If the game patches a module after the DMA, or the DMA does not start at the header, the result is MISMATCH/UNKNOWN: the job is interpreted, which is safe but gives no gain.
3. **Writes into a resident span.**
   - Without VERIFY, a non-DMA write leaves the job RESIDENT.
   - With VERIFY, the span is re-hashed at each entry, so a write into in-span data also reads as MISMATCH. That is a fallback, not a wrong result.
   - A write **while a job runs** is not caught.
4. **Job modules outside the EBOOT** (data-file blobs) show up as UNKNOWN and stay interpreted.
5. **Whole-job equivalence on real inputs** is untested. Only leaf functions (145) and synthetic jobs are covered.

## 6. AOT coverage

- **Static coverage, VERIFIED:** all 31 retail WWS modules, 5,667 functions. That includes everything T33/T37 named for the race: vehiclephysics, renderablejob, spuconstraints, spuxform, groundrush ×3, occjob, pvsjob, squishandordervisjob, octreequery, vehicledeformation, screenrush, trailsupdate, the particles and LibMP3.
- **Not WWS:** Havok (already lifted) is outside this AOT.
- **Runtime coverage is unknown.** Run A's kind-28 identities against the manifest, and run B's kind-29 result mix, give it exactly.

## 7. A/B procedure (each run needs its own authorization)

1. **Build: done in T70B** (`configure_aot.cmd`, then `build_aot.cmd`; exe sha256 `4a07bfc9…f672`).

**Recommended first validation (T70B), one authorization per run:**
1. `prepare` the T70B exe once; check the pin equals `4a07bfc9…f672`.
2. **A1** (AOT off). Accept only if gate A holds (0 kind-29, 0 `[spu-reloc]`), race entry ≈ 155 s, and ≥ 20 s of race in the ftrace window. From its kind-28 records take the code bases and module identities; check every identity is in the manifest.
3. **B1** with `PS3_SPU_WWS_AOT_BASES=<A1 bases>`. Check the `[spu-reloc] … resident re-hash on` line, the kind-29 mix (mostly RESIDENT/INSTALLED), 0 MISMATCH and 5.00 ± 0.05 Havok steps per frame. **Stop at the first MISMATCH, crash or Havok-rate change** and investigate offline before any further run.
4. Only then alternate to A2, B2, A3, B3 and report with `ab_report.py`. Claim an FPS effect only from the paired race windows, never from the synthetic bench.
2. **Pin the exe:** `run_t70_ab.py prepare build/motorstorm-t70-aot/MotorStormPacificRiftRecomp.exe`.
   - It requires the AOT strings in the exe, and in the CMake cache `MSPR_WWS_AOT=ON`, `ps3recomp-t70` and `PORT_SPU_AVX2=OFF`.
   - Verified offline: it refuses the T64C exe.
3. **Run:** `run_t70_ab.py launch A`, then `launch B <bases from A>`. Do at least 3 of each, alternating A and B.
4. **Report:** `ab_report.py <runs…>`.

**Identical in both arms:**
- the one pinned exe;
- a fresh verified copy of `generated/hdd0`/`hdd1` per run;
- the T64C automated route (CROSS whenever a screen settles, stop pressing at the race loader; Kanaloa Bay, ATV), and no input in the race;
- the navigation-only PT trace `ab/t70_ab_trace.cfg` (hot IO/LFQ hooks, HLE hooks, `sc=all`, stall and 58 markers removed);
- no RSXI, `TEX_SNAPSHOT`, `CELLMARK`, `LFQ_TRACE` or `FSTRACE`;
- `SPURS_BUSY_MS=1000`, `RSX_HEARTBEAT_MS=1000`;
- `PS3_FTRACE=120:76:{run_dir}/ftrace.txt`, `PS3_FTRACE_ARM=329D90:8EE8C:3` and `PS3_FTRACE_SPUJOB=3214:1320` (T70C; A1 used the fixed `150:48`).

**Arm B only:** `PS3_SPU_WWS_AOT=1`, `PS3_SPU_WWS_AOT_VERIFY=1`, `PS3_SPU_WWS_AOT_BASES=<A's bases>`.

**Automatic triggers within the 210 s cap:**
- The ftrace window opens 3 s after the race-entry call and dumps itself at 196 s (T70C; section 0c).
- `spurs-busy` and the heartbeat stream continuously.
- The controller stops the game 1 s after the dump, at 172 s as INVALID if race entry has not come, else at 205 s; the runner cap is 210 s.
- The target (`garage_capture_complete`) can't fire without RSXI, so the runner never stops early.

**Measurements (`ab_report.py`, self-test OK; smoke test on T64C: 5.01 fps, 5.00 Havok steps per frame):**

| # | Measurement | Source |
|---|---|---|
| 1 | FPS | heartbeat frames/s, race window |
| 2 | Frame time: mean, p50, p95, p99 | ftrace kind 9 flip intervals |
| 3 | Per-queue busy | `[spurs-busy]` per (SPURS, lane, wid), lane TID joined to `performance.json` cores |
| 4 | SPU job time | kind 26 per wid; per module via `t37/job_report.py` |
| 5 | AOT hit/fallback | kind 29 result mix |
| 6 | PPU main wait | kinds 1+2 of PPU thread 1, ms/frame |
| 7 | Pickup latency | **not instrumented on this line**; runs/s and coordinator passes/s as a proxy |
| 8 | Simulation | Havok simulate steps/s and per frame |
| 9 | Verification failures | kind-29 MISMATCH + `[spu-reloc] … body differs` |

**Validity gates.**
- **A:** 0 kind-29 records and 0 `[spu-reloc]` lines.
- **B:** a `… resident re-hash on` registration line and 0 MISMATCH; stop and investigate on any MISMATCH.
- **Both:** a window of at least 20 s, ftrace and busy data present, and 5.00 ± 0.05 Havok steps per frame.
- The smoke test correctly rejects T64C as an A/B run (no ftrace or busy data).

## 8. Remaining blockers

| Blocker | Status |
|---|---|
| `generated/spu_raw/wws_reloc` missing | **resolved**, verified against the EBOOT |
| AOT not on the T62/T64C line | **resolved**, isolated branch, tests green, configure matches T64C |
| Build flags unverified | **resolved**, `ninja_diff` PASS |
| Thread → wid mapping | **instrumented**; needs run A |
| Race load bases and module set | **PARTIAL** (A1: lane 0, 10 modules, all base 0x4000; other lanes not logged) |
| Job spans (kinds 26–29) never close in the game | **resolved offline** (`478aea3`, real-path regression test; section 0c); runtime confirmation needs A1′ |
| Bimodal startup (+43 s) pushes race past the ftrace window | **resolved offline** (`bdf8224` + harness: race-entry arm, slow starts rejected at 172 s; section 0c) |
| Rebuild + new pin with the T70C commits | **done** (T70D: `2709eafd…2cec`, `ab/exe-t70d/`) |
| In-race overwrite behaviour under VERIFY | **BLOCKED** (needs run B) |
| Scheduler pickup latency | **not measurable on this line**: the T25 kinds 24/25 live on the unmerged perf line |
| Game build | **done** (T70B, section 0) |
| A/B runs, merge into the T24/primary line, shared `port/` patch | **need authorization** |

## 9. Artifacts (`generated/analysis/t70/`)

- `tools/`: `gen_wws_reloc.sh`, `verify_wws_reloc.py`, `fuzz_retail_t70.py`, `compile_check.py`, `configure_aot.cmd`, `ninja_diff.py`; T70B: `build_aot.cmd`, `inspect_aot_exe.py`, `run_reloc_test.cmd`
- T70C `tools/`: `run_t70c_test.cmd`, `compile_tus.py`/`.cmd`, `t70c_new_warnings.py`, `t70c_callsites.py`, `t70c_bisl.py`, `t70c_controller_sim.py`; `c2_objs/` (scratch objects)
- `ab/`: `run_t70_ab.py`, `ab_report.py` (both T70C), `t70_ab_trace.cfg`, `a1_extract.py`
- `patches/0001–0008`, `logs/`, `modules_reextract/`
- `generated/spu_raw/wws_reloc`, `port-t70/`, `build/motorstorm-t70-aot` (configured, not built)

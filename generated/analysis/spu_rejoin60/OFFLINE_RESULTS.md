# OFFLINE_RESULTS (Tasks 8, 9)

Private. No game launch, no race, no commit. Shared trees were not modified.

## 1. What was built

- **Runtime copy:** `ps3recomp-rj60`. A file copy of `ps3recomp-vkgame` (dc3a2ba6 plus its uncommitted changes, i.e. the runtime of the main exe 714690f6, Fix 2 included). Full diff: `out/rj60_runtime.diff`.
  - `runtime/spu/spu_drain.c`: `PS3_SPU_DRAIN_RESUME_RELOC=1`. Only exactly "1" enables it; it is read once. In `spu_drain_call`'s resume probe, a pc inside a resident relocatable slot resumes when the slot lookup finds a lifted entry. With the switch off, the code is unchanged.
  - `runtime/spu/spu_channels.c`: new `spu_reloc_slot_probe()`, read-only, with the same slot rule as `spu_indirect_branch`. Fix 2's code is untouched.
  - `tests/test_spu_reloc_job.c`: new `rep` command (repeated resident jobs, timing, AOT profile dump). The PM's return stand-in halts instead of aborting when a job reaches it at host depth 0.
  - New `tests/test_spu_drain_resume_reloc.py`. Copied from ps3recomp-cp60: `tests/test_spu_interp_rejoin_reloc.py` and the `rejoin` command.
- **Candidate exe:** `build/motorstorm-vkgame-100-rj60/MotorStormPacificRiftRecomp.exe`, SHA-256 `8b6d0d4ae677ec1124e39cbbc3a0d50ddcd8ae83b8f54990d4923a59bb12f0a1` (`out/rj60_exe.sha256`).
  - Recipe `tools/build_rj60.cmd`: `build_cp60.cmd` with PR = ps3recomp-rj60, a new build dir, LTO cache `D:\lto-cache-100-rj60`, `-j3`. Same PGO profile `build/pgo103/ms103.profdata`, same Wws AOT dir `generated/spu_raw/wws_reloc` as the main exe.
  - 319/319 steps, rc 0. Both switch names are present in the binary.
  - It differs from the main exe only in runtime source, but the PGO profile may not match the changed runtime functions. **Compare arms on this one exe** (switch off vs on).
- **Test runner:** `tools/run_test.cmd` (MSVC + LLVM 23.1.3 + T17 cc shim, as `t70/tools/run_reloc_test.cmd`).

## 2. Correctness (VERIFIED)

| suite | result | file |
|---|---|---|
| `tests/test_spu_drain_resume_reloc.py --runs 2000` (new) | **157 PASS, 0 FAIL** | `out/test_drain_resume_reloc.txt` |
| `tests/test_spu_reloc_job.py` (existing T37–T154 suite) | 91 PASS, 0 FAIL | `out/regress_reloc_job_default.txt` |
| same, run with `PS3_SPU_DRAIN_RESUME_RELOC=1` exported | 91 PASS. **The suite strips `PS3_*` from its child environment, so this is effectively a second default-off run, not a resume-on run.** Resume-on coverage of modules A/B is in the new test | `out/regress_reloc_job_resume_on.txt` |
| `tests/test_spu_interp_rejoin_reloc.py` (Fix 2) | 48 PASS, 0 FAIL | `out/regress_interp_rejoin.txt` |

What the new test proves:
- **Module N** (synthetic, no game bytes) reproduces both unwind shapes seen in the race:
  - a switch `bi $r2` lifted as `SPU_RET_REG` inside nested call brackets (asserted: exactly one `SPU_RET_REG(ctx, 2)` in N's lift, as renderable 0xA650);
  - a job-exit return to `entry` tail.
  - The mid-function return points start with `ori`, so a miss goes to the interpreter, as at 0xDFA0.
- **Bases** 0x4000, 0x8C00, 0x15C00, 0x30000, which covers the relocation offset (reloc_delta) applied after the resume.
- **Combinations:** Fix 2 off/on × resume off/on. In every case the guest output (DMA'd to main memory), the LS window, the stack and all 128 GPRs are byte-identical to the pure-interpreter run.
- **Resume on:** 0 restarts, 0 misses, 0 interpreted instructions, 7 resumes per job.
- **Resume off:** restarts present (1 per job with Fix 2 off, which then interprets to the end; 6 per job with Fix 2 on).
- **Modules A/B** (no unwind shapes): unchanged by the switch, with 0 resumes and 0 restarts.
- **Repeated cycles:** 2,000 resident re-runs per configuration, the same job each time. The slot stays resident and the state is identical.

Not covered (PARTIAL):
- **Concurrency:** contexts are per-thread and the probe reads only the context plus the startup-built registry. The existing `test_spurs_wws_concurrency` / `stress` suites were not rerun with the switch.
- **SMC or non-DMA LS writes into a resident span:** C-A adds no new trust. A DMA GET into a slot clears it before any probe; a non-DMA write is caught only with `PS3_SPU_WWS_AOT_VERIFY=1`, as before.
- **Randomized differential:** the existing reloc fuzz (600 trials × 2 bases, inside `test_spu_reloc_job.py`) passes; it does not exercise unwinds.

## 3. Performance (synthetic module N, host ns per job, median of 2,000 resident runs; timer 100 ns)

| Fix 2 | resume | interpreted/job | misses/job | restarts/job | resumes/job | median ns/job |
|---|---|---:|---:|---:|---:|---:|
| off | off | 154 | 1 | 1 | 0 | 1700 |
| off | on | 0 | 0 | 0 | 7 | 700 |
| on | off | 96 | 6 | 6 | 0 | 2300 |
| on | on | 0 | 0 | 0 | 7 | 700 |

All four bases give the same numbers ±100 ns.

- Measured: with Fix 2 on, resume saves 1.6 µs per job for 6 switch chains plus 1 exit chain, i.e. **~0.23 µs per unwind chain**.
- Side observation: on this synthetic job, Fix 2 alone is slower than no fix, because the short interpreted tail is cheaper than six unwind-and-miss chains. In the game the interpreted tail was 166k instructions, so Fix 2 wins by orders of magnitude.
- Modelled race effect: 238 restarts/frame (R1) × ~0.23–0.4 µs ≈ **0.05–0.1 SPU-ms/frame**, plus ~30 renderable interpreted instructions/job × 20 jobs × ~15 ns ≈ 0.01 ms. Spread over 5 lanes; critical-path reduction ≤ ~0.05 ms/frame. Interpreter instructions avoided: ~30 per renderable job (~600/frame). Transitions avoided: ~238 unwinds plus ~50–60 misses per frame.
- **Below the ~1.5 ms bar by ~15x.** No candidate in this study is modelled above 1.5 ms.

## 4. perfbench (Task 9): not applicable to C-A (VERIFIED by code, not by a run)

- **`spu` suite:** Havok TASKREC replay (Kksr2 / Kksr38). These are SPURS tasks with no Wws relocatable slots, so `spu_reloc_slot_probe` returns 0 at its first test.
- **`snap` suite (`D:/ms_fnrec3|5|6`):** enters lifted functions directly with no resident slot, so the same holds.
- In both suites C-A cannot change a single executed instruction or timing, beyond one predicted branch on the resume path.
- Building rj60 variants of the replay exes would only re-measure the baseline, so it was not done.
- **The perfbench race model (`race_model.py`) is not FPS** and was not used: C-A's modelled saving is far below the model's validation error (−1.6 %).
- **A whole-Wws-job replay harness does not exist.** FNREC is function-level and `fnx` refuses channel ops. This is the main recording limitation for every Wws question here.

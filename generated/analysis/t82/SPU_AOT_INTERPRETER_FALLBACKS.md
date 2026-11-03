# T82: SPU AOT interpreter fallbacks (renderablejob)

2026-10-26. Offline only: no game build, no launch, no merge, no push. T81's worktree, every exe pin and every shared generated input are untouched.

## Identity

| | |
|---|---|
| Base source | `88feeb5` (`ps3recomp-t70g`): the B1 exe `exe-t70g` (`ae7ed7be…a55e`) |
| T82 worktree | `ps3recomp-t82`, branch `agent/t82-aot-fallbacks`, commit **`0b0b89b`** (local) |
| Patch | `patches/0001-SPU-lifter-a-switch-entered-by-a-conditional-branch-.patch` |
| Runtime data used | B1 `generated/runs/20261026-194910-t70-ab-b`, A1″ `generated/runs/20261026-191651-t70-ab-a` (ftrace kinds 26/27/28/29, stderr) |
| Lifts | `lift_t70g/` = baseline lifter, byte-identical to the B1 lift (`t37/lift` = `spu_raw/wws_reloc`) for all 31 TUs; `lift_t82/` = patched lifter |
| Tools | `tools/` (`switch_sites.py`, `exit_census.py`, `interp_dist.py`, `interp_bursts.py`, `interp_corr.py`, `pm_linkret_diff.py`, `crt_entry_experiment.py`, `compile_tu_src.py`, `run_regress.sh`, `run_posix_fixture.py`) |
| Logs | `logs/` |

## Answer

**renderablejob runs in the interpreter because of one mis-lifted switch, not because of its 61 hand-off words.** (VERIFIED mechanism. **T82B (§10) VERIFIED at run time that it accounts for all of it:** renderablejob interpreted 0 instructions in 12,750 runs, against 42.1 k per run in B1.)

1. **The bad lift.** The `bi $r2` at LS 0xA650 dispatches a 12-entry jump table (table at 0xA654, loaded by `lqx`/`rotqby $r2` at 0xA1DC–0xA1E0 and bounds-checked by `brz $r80, 0xA650` at 0xA1E4). The lifter emitted it as `SPU_RET_REG(ctx, 2)`, a host *return* through r2.
   - Cause: `compute_link_returns()` treats r2 as a link register, because of the module's `brsl $r2, .+4` PIC idiom.
   - It then checked only `br`/`bra` predecessors for a computed write. The `brz` predecessor that loads r2 was invisible to it.
2. **What that does at run time.** The host return lands in the enclosing drain with pc = case address.
   - The drain's resume lookup is not reloc-aware, so it calls `spu_restart_dispatch`, which unwinds every host frame of the job.
   - From then on every `bi $r0` dispatches to an unregistered mid-function return address. That goes to the microstep and then the interpreter.
   - The interpreter can never rejoin relocatable lifted code: `spu_lifted_lookup` is the plain image lookup, not the reloc-slot lookup the dispatcher uses.
   - So **the rest of the job runs interpreted**, except for PM services, until it returns to the PM's 0x3214.
   - Guest state stays correct, which is why B1 showed 0 MISMATCH.
3. **The fix (lifter only, `0b0b89b`).** Conditional predecessors now count as well. For them, the nearest writer of rN decides:
   - an immediate load or register copy means a planted link, so the branch stays a return;
   - anything else means a computed target, so it becomes a dispatch.
4. **Effect of the fix:**
   - Re-lifting the 31 modules changes **one line in one TU**: renderablejob 0xA650 becomes `ctx->pc = r2; spu_indirect_branch`. All 12 case targets are registered entries.
   - The manifest, registration TU, header and function list are unchanged.
   - The PM's 14 link returns classify exactly as before.
5. **Evidence it is significant (VERIFIED from B1, offline).**
   - renderablejob's per-run interpreted counts are **identical across all 589 frames per burst position**, for example `4473 120910 13738 4444 164060 159199 23942 4444 183008 157461 18899 0 0 0 0 139 139 139 139 0 0`.
   - That is data-dependent and deterministic, which rules out interrupts, races and DMA timing.
   - Big positions interpret about 62 % of their fully interpreted (A1″) count, consistent with "everything after the switch".
   - The other 30 modules interpret 0 instructions, apart from the 2-instruction interrupt prologue in spuconstraints and spuxform.
   - 0xA650 is the only non-r0 link return in all 31 lifts.

## 1. Fallback-site classification

How compiled code can end up in the interpreter (runtime: `runtime/spu/spu_channels.c` `spu_indirect_branch` → `spu_smc_microstep` → `spu_interp_run_until`; `spu_drain.c` `spu_drain_call`). Static counts are over the 31 lifted WWS modules (`logs/exit_census.md`).

| # | Class | Static sites (31 modules) | Interpreter transition? | renderablejob, measured | Status |
|---|---|---|---|---|---|
| 1 | Unsupported or undecodable instruction (`.word` hand-off) | 68 (renderablejob 61, vehiclephysics 7); 0 unknown mnemonics | Only if executed | All 61 are rodata strings at 0x13360–0x135FC ("State", "Assignm…"), never executed | VERIFIED |
| 2 | Indirect branches through `spu_indirect_branch` | 809 `bie`/`bid` fences, 23 computed `bi`, 334 `bisl`, 0 `iret` | Only on a lookup miss | All renderablejob targets registered: 93 jump-table entries, the `ila` and PIC fence targets, the PM API table (0x2F10 / 0x17C8 / 0x17F0 / 0x1AE8), the ctor/dtor list (0xF660 / 0xF670) and the 0x13680 handler table (11 entries + a 0xFFFFFFFF sentinel). No unregistered code pointer in the image (`switch_sites.py`) | VERIFIED |
| 2a | Computed `bi $rN` mis-lifted as a host return (`SPU_RET_REG`) | **1** (renderablejob 0xA650) → 0 after T82 | Unwind, then remainder interpreted | The B1 hotspot | VERIFIED mechanism, fixed |
| 3 | Dynamic code | PM interrupt path: vector 0xA2C is not a lifted entry; save/restore stubs are generated at 0x3FEC0 | Per interrupt: microstep plus a few interpreted instructions | spuconstraints and spuxform show exactly 2 per run (0xA68 stqx, 0xA6C brnz, then rejoin at 0xA60). HYPOTHESIS: renderablejob's constant 139 is the switch taken late, not interrupts | PARTIAL |
| 4 | Calls outside the module | PM services via the API table at LS 0x1330+48…76, all lifted PM entries (PM lift: 239 entries) | Only at unregistered PM addresses (the 0xA2C vector) | none | VERIFIED |
| 5 | Runtime services | `selectWorkload`/exit HLE at reserved LS, taskset syscall 0xA70 | No (handled in the dispatcher) | none | VERIFIED |
| 6 | DMA and channel operations | Lifted inline (`spu_rdch`/`spu_wrch`); blocking reads park the host thread on a CV | No | none | VERIFIED |
| 7 | Unresolved control-flow targets | 0 unresolved-branch hand-offs. **Runtime amplifiers:** (a) the interpreter cannot rejoin reloc code; (b) drain resume is not reloc-aware, so it calls `spu_restart_dispatch`; (c) at host depth 0, `bi $r0` dispatches to mid-function return addresses, which are never registered | Yes, after any miss or unwind | Turns one bad return into "rest of job interpreted" | VERIFIED (code + synthetic) |
| 8 | Verification and instrumentation | `PS3_SPU_WWS_AOT_VERIFY` hash at entry; job-span tracer | MISMATCH means the whole job is interpreted (B1: 0) | none | VERIFIED |
| 9 | Other: CRT manual-link entry | All 31 modules: `ila $r0, post; a $r0,$r0,$r126; brz $r81, body` | Not interpreted; **one `spu_restart_dispatch` per job**. The job then reaches 0x3214 via the dispatcher at host depth 0 | Synthetic: 0 interpreted, 1 restart at `post`, state == interpreter (`logs/crt_entry_experiment.log`). Effect on the PM after it: not measured | VERIFIED mechanism / HYPOTHESIS cost |

Static versus measured: the census counts *sites*; the only *measured* runtime transitions come from B1's kind-27 counts (interpreted instructions per job) and the 8 logged `[spu-smc] microstep … pc=0x00A68` lines (interrupt prologue). B1 has 0 `drain-resume` lines (logged first 8), so every drain mismatch in B1 was a silent restart.

## 2. renderablejob control flow

- **Module:** `ms_10aa3f4480ef_eEE40` (manifest entry 22): link base 0x4000, image 0xF6D0, bss 0x153E0, entry 0x12E40, 1,018 lifted functions.
- **The only reachable exit site.** Guest code 0xA1CC–0xA1E8, in lifted chunk `…spu_func_0000A120` (0xA120–0xA1E8), part of the guest function at 0x9E20 (called from 0xACC0 and 0xE574):
  - `shli $r85,$r9,2; ila $r88,0xA654; clgti $r80,$r9,11; a; lqx $r83,$r88,$r85; rotqby $r2,$r83,$r84; brz $r80,0xA650`;
  - then `…spu_func_0000A650` = `bi $r2` (source line 7645).
  - Cases (12): 0xAA64, 0xAA38, 0xAA10, 0xA1E8, 0xA9E4, 0xA9BC, 0xA994, 0xA96C, 0xA944, 0xA91C, 0xA8F4, 0xA8CC, all registered lifted entries.
- **Reachable, frequent, required?**
  - Reachable on every renderable whose index path reaches the switch (`brhnz $r67,0xA60C` not taken). Frequent: in B1's common 21-run burst, 11 of the 21 positions interpret ≥ 4 k instructions every frame.
  - Not required for correctness: a dispatch to registered entries is what the hardware does.
  - The lifter handles it directly once classified as a dispatch.
- **Mapping kept:** every lifted function is still named and registered by its link-base LS address (`wr_ms_10aa3f4480ef_eEE40_spu_func_<LS>`). Only the body of `…_0000A650` changed.
- **Other exits in renderablejob:** none reachable. The 195 fences and 9 table switches dispatch natively. The 13 indirect calls go to lifted PM services or registered module functions. The object callbacks at 0x13154/0x13194 (`[r3+12]`) are runtime data and unverifiable offline, but no kind-27 evidence points at them.

## 3. Verified versus hypothetical hotspots

| Finding | Status |
|---|---|
| Interpretation is deterministic per renderablejob burst position, identical in all 589 B1 bursts (`logs/` via `interp_bursts.py`) | VERIFIED |
| Only renderablejob interprets; others 0 (spuconstraints/spuxform 2 = interrupt prologue) | VERIFIED |
| 0xA650 mis-lift causes unwind + remainder-interpreted | VERIFIED (code, and synthetic reproduction: 336 of 403 instructions interpreted after the first switch) |
| 0xA650 accounts for (nearly) all 680 M interpreted instructions | **VERIFIED (T82B, §10)**: with only this change, renderablejob interprets 0 |
| renderablejob's 139 / 4.4 k classes are the same switch taken late in the job | HYPOTHESIS |
| One `spu_restart_dispatch` per job from the CRT entry (all modules) | VERIFIED mechanism (synthetic); in-game PM cost after it unmeasured |

## 4. Synthetic transition costs

These are host-specific microbenchmarks from `tests/bench_spu_switch_linkret.py` (`logs/bench_spu_switch_linkret.log`): best of 5 × 2,000 resident runs at base 0x4000. They do not represent game FPS.

| Quantity | Cost |
|---|---|
| Native loop iteration (switch, 3 calls) | 36 ns |
| Same iteration interpreted (39 SPU instructions) | 251 ns: **+5.5 ns per interpreted instruction, ×7.0** |
| Native indirect dispatch (`bid`/`bie` fence via `spu_indirect_branch`) | 7.7 ns each |
| Host-frame unwind + re-dispatch (`spu_restart_dispatch`) | ≈ 0.5 µs once per job (loops = 64); not separable at loops = 8 (noise) |
| Whole synthetic job, 9 iterations | native 2.8–3.0 µs; old lift (1 unwind + 336 interpreted) 4.1–4.4 µs; interpreter 5.0–5.2 µs |

## 5. Safe optimisation implemented

- **`tools/spu_lifter.py` `compute_link_returns()`:** conditional-branch predecessors are now included. For them, a nearest writer that is `il`/`ilh`/`ilhu`/`ila`/`iohl` or `ai`/`ori … 0` stays a link (`_is_link_value`); otherwise the branch is a computed target. Unconditional predecessors behave as before.
- **Direction of risk:** turning a mis-detected return into a dispatch is semantically safe. A drain catches a dispatch to its own return pc; elsewhere the dispatcher resolves or interprets. Only the reverse is harmful, and it is what was fixed.
- **Re-lift (`logs/lift_t82.log`):** 31/31 modules. One line changes in renderablejob; 30 TUs and the manifest are byte-identical.
- **Build check:** the patched TU compiled with the B1 build's exact `build.ninja` command (clang-cl, LLVM 23.1.3, `/O2 -msse4.1 -DSPU_USE_DISPATCH_MT`). It produces the same warning count as the B1 source, and its object differs from the B1-source object in **exactly one function** (`…spu_func_0000A650`, 20 → 16 instructions; 1,033 others identical).
- **Runtime instrumentation (`PS3_SPU_AOT_PROF=<s>`, off by default):** see §9.
- **Not changed** (each is a separately justified future change): the interpreter's rejoin lookup, the drain resume rule, the per-job CRT restart and the PM interrupt prologue.
  - Reloc-aware rejoin alone would convert interpretation into unwind cascades. A rejoined callee runs as a trampoline, so its return host-returns to an unregistered mid-function pc.
  - It needs the drain to continue in place for reloc slots too, which changes host-frame structure on every job and needs its own tests and run.

## 6. Interpreter/AOT parity

**`tests/test_spu_switch_linkret.py`** (new, synthetic module, real SPU runtime; `logs/test_spu_switch_linkret.log`): 22/22 PASS.
- Classifier: switch → dispatch; conditional manual-link `ila` → return; saved-link copy → return; plain helper return → return; `br`-computed → dispatch (unchanged).
- At bases 0x4000 / 0x8C00 / 0x15C00 / 0x30000: AOT interprets 0 instructions, returns through its drain (no unwind), and guest output, LS window, stack window and all 128 GPRs are byte-identical to the interpreted run.
- A resident re-run stays 0-interpreted with the same output.
- With `--old-tree ps3recomp-t70g`, the old lift reproduces the defect: `SPU_RET_REG`, unwound, 336 interpreted, state still == interpreter.

**Regression suite** (`logs/regress_t82.txt`, run under the build's MSVC + LLVM environment):

| Test | Result |
|---|---|
| `test_spu_reloc_job` (WWS relocation/AOT: lifted == interpreted at 4 bases, residency, 9 fail-closed states vs no-AOT, random-state differential, hardening) | PASS, 0 failures |
| `test_spu_lifter_reloc` | PASS |
| `test_spu_jobspan`, `test_spu_jobspan_path` | PASS |
| `test_spurs_scheduler` (private POSIX runner `tools/run_posix_fixture.py`) | 8/8 PASS (baseline also 8/8) |
| `test_spu_chain_chunks`, `test_spu_ls_inline`, `test_spu_program_pipeline`, `test_spu_disasm_ri10`, `test_mfc_resume_elements`, `test_lifter_dedupe`, `test_lifter_header_name` | PASS |
| `audit_public.py --staged` | the 25 baseline items, none in T82 files |

| Not run here | Reason |
|---|---|
| `test_spu_fnms_zero_extended` | FAIL at link (`duplicate symbol: GetFileAttributesA`); identical on the pristine `88feeb5` tree, so pre-existing on Windows |
| `test_spu_context_registries`, `test_spu_interpreter_handoff`, `test_spu_interpreter_ilh`, `test_spu_ls_alias`, `test_spu_machine_status`, `test_spu_sdcrz`, `test_spu_smc_lqa_stqa`, `test_spu_taskset_elf_flags`, `test_spurs_queue_size`, `test_spurs_task_exit_code_initialize`, `test_spurs_taskset_size`, `test_spinlock_word_width` | SKIP: POSIX-only fixtures |
| `lift_selftest`, `spu_lift_selftest` | SKIP: PS3 SDK compilers |
| `spu_disasm_audit` | needs private images, not run |

**Runtime TUs.** `spu_channels.c` and `spu_drain.c` compiled with the B1 build commands against the T82 tree: exit 0. New warnings are only in classes the files already carry (`getenv` deprecation, declaration-after-statement, unsafe-buffer-usage).

## 7. Remaining unsupported operations and transitions

- The interpreter cannot rejoin relocatable lifted code (`spu_lifted_lookup` ignores reloc slots). Any future miss inside a job still interprets until a PM entry or the drain's return pc.
- The drain resume is not reloc-aware. Every job's CRT manual-link entry ends in `spu_restart_dispatch`, and the PM then runs at host depth 0, where its own `bi $r0` returns dispatch to return addresses (PM cost unmeasured).
- Mid-function return addresses are never registered entries, which matters only after an unwind.
- The PM interrupt vector 0xA2C is not a lifted entry, and the 0x3FEC0 save/restore stubs are runtime-generated: each interrupt is microstep plus a few interpreted instructions. This is dynamic code, so it stays interpreted.
- 809 interrupt-window fences pay a full dispatcher pass each (about 7.7 ns synthetic); renderablejob has 195 sites.
- The PM's own lift (not re-lifted in T82) has 14 `SPU_RET_REG` sites; the patched analysis leaves all 14 as returns (`pm_linkret_diff.py`).

## 8. Estimated improvement (HYPOTHESIS until measured)

- **Basis:** B1 renderablejob ran 16,157 times and interpreted 680.3 M instructions, 42.1 k per run. At 27.5 runs per frame that is about 1.16 M interpreted instructions per frame.
- **Interpreted time:** at A1″'s interpreted rate for renderablejob (10.04 ns/insn) that is about **11.6 ms/frame** of renderablejob's 22.5 ms/frame.
- **Native time:** running those instructions natively at 4.3–5.5× (4.3× is renderablejob's own B1 speedup, itself still partly interpreted, so conservative; 5.5× is vehiclephysics, fully native) costs about 2.1–2.7 ms. Saving: about **9 ms/frame of SPU job time** (renderablejob ≈ 22.5 → 13.5 ms/frame; WWS sum ≈ 50 → 41 ms/frame).
- **Cross-check:** consistent with the synthetic ×7 interpreted/native ratio.
- **No FPS claim:** whether this shortens the PPU's 47.9 ms/frame wait depends on renderablejob being on the frame's critical path. Not established.

## 9. Recommended runtime validation

This needs separate authorization for one isolated build and one B-arm session.

1. **Lift:** run the T82 lifter, same command as T70 (`lift_wws_reloc.py --modules generated/analysis/t37/modules --pm-image 1297305682 --codebase-word 0x1320 --job-return 0x3214 --names …/modules.json --ctor`), into a *new* private lift directory, and point a *new* build directory at it. Do not overwrite `generated/spu_raw/wws_reloc` or any pin. Expect exactly the one-line renderablejob diff (`lift_t82/` here).
2. **Build:** runtime `0b0b89b`, with the B1 configuration otherwise unchanged.
3. **Run:** one B-arm session on the B1 harness (`run_t70_ab.py launch B 4000` semantics: AOT on, VERIFY on, base 0x4000, 205 s / 210 s, fresh HDD, no driving).
   - Keep counters off for the performance numbers.
   - If a diagnostic is wanted, run a separate session with `PS3_SPU_AOT_PROF=10` (one bounded summary per 10 s: at most 26 lines).
4. **Pass criteria:**
   - renderablejob kind-27 interpreted instructions ≈ 0 per run (B1: 42.1 k);
   - 0 MISMATCH and 0 AOT fallbacks;
   - per-module job counts per frame, Havok 5.00 steps/frame and draws > 200 as in B1.
5. **Compare** renderablejob ms/frame, WWS ms/frame, PPU wait and fps against B1 on the same harness.
6. **With counters on, expect:**
   - no `restart` keyed to renderablejob case addresses;
   - the remaining `restart` count ≈ jobs (the CRT entry, §7), which sizes the next candidate fix;
   - the PM `miss` sites show what the depth-0 PM continuation costs.

The counters are thread-safe for five-lane execution: one fixed 1,024-entry table, CAS-claimed keys, atomic adds, no allocation, no per-event logging. They are tested with 8 threads × 200 k notes, 0 lost.

## 10. T82B: runtime validation (one build, one launch)

2026-10-26. Files: `t82b/` (scripts, logs, report). No source change in T82B, no merge, no push, no commit. Earlier pins (`exe-t70g`, `exe-t79`, …) were re-hashed afterwards and are unchanged. `generated/spu_raw/wws_reloc` is untouched.

### Identity

| | |
|---|---|
| Source | `ps3recomp-t82` `0b0b89b` (= B1 source `88feeb5` + T82 lifter fix + off-by-default counters). No T79/T81/T83 change |
| Lift | **new** `generated/spu_raw/wws_reloc_t82` (`t82b/gen_wws_reloc_t82.sh`). `verify_wws_reloc.py` RESULT PASS against the EBOOT; per-file hashes in `t82b/wws_reloc_t82.sha256` |
| Build dir | **new** `build/motorstorm-t82b-aot` (`t82b/configure_t82b.cmd`, `build_t82b.cmd`). B1's recipe with only the tree and the lift dir re-pointed. `ninja_cmp_b1.py`: all 309 compile/link entries identical to B1 after that mapping |
| Exe | **`94e7e3c39b1544d449fbd4bd0a21d0169a48bffccaf54b8a04fbf39f77cf6d98`** |
| Pin | **new** `t82b/ab/exe-t82b/` + `t82b/ab/exe_pin_t82b.json` |
| Run | `generated/runs/20261026-222323-t70-ab-t82b` (`t82b/ab/run_t82b_ab.py launch T82B`) |

### Phases 1–4 (all PASS)

- **Source and lift.** The new lift is byte-identical to `lift_t82/`. Against B1's lift, one line differs: renderablejob 0xA650 changes from `SPU_RET_REG(ctx, 2)` to `ctx->pc = r2; spu_indirect_branch`. The other 30 modules and the manifest are identical.
  - All 12 case targets are registered (`t82b/switch_sites_t82b.txt`).
  - The census has 0 `SPU_RET_REG` sites left (`exit_census_b1_vs_t82b.md`).
  - The policy module's 14 link returns are unchanged (`pm_linkret_diff.txt`).
  - The VERIFY path is unchanged.
- **Build.** One build, exit 0, 0 FAILED.
- **Objects.** Comparing B1 and T82B objects function by function (`obj_func_diff.py`, 31 module objects plus the registration object): the only difference is `…10aa3f4480ef_eEE40_spu_func_0000A650` (20 → 16 instructions). That function is identical to the offline T82 compile.
- **Exe.** `inspect_aot_exe.py` RESULT PASS: all 31 signatures and body hashes are present, the constructor is wired, and the gates are off by default.
- **Tests.** `t82b/regress.txt` matches T82 §6:
  - PASS: reloc_job, switch_linkret, lifter_reloc, jobspan, jobspan_path, chain_chunks, ls_inline, program_pipeline, disasm_ri10, mfc_resume, lifter_dedupe, lifter_header_name;
  - SPURS scheduler 8/8 (`sched_t82b.log`);
  - same pre-existing fnms link failure and the same POSIX/SDK skips as before.
- **Launch configuration.** The dry-run environment equals B1's `runner_argv.json` except for run-directory paths:
  - `PS3_SPU_WWS_AOT=1`, `PS3_SPU_WWS_AOT_VERIFY=1`, bases 4000;
  - `PS3_SPURS_GUEST_MAXCONT` and `PS3_SPU_AOT_PROF` unset;
  - no TEX_SAVE or readback, no driving, fresh HDD, 205 s / 210 s.

### Phase 6: correctness gates (`t82b/t82b_report.txt`; all PASS, VALID)

| Gate | B1 | T82B |
|---|---|---|
| Race entry (armed once after LoadRace) | 141.0 s | 151.4 s (gate ≤ 172 s) |
| Race window | 52.0 s | 41.6 s |
| Dropped / lost / unattributed spans | 0 / 0 / 0 | 0 / 0 / 0 |
| AOT VERIFY mismatches | 0 | 0 |
| Fatal / assert / abort / exception lines in stderr | 0 | 0 |
| Session end | controller stop after the trace was written (exit as B1) | same |
| Module identities | 15 entry ids, 15 module ids, all from the manifest | the same 15 + 15 (`t82b_identity.txt`) |
| Havok steps per frame | 5.00 | 5.00 |
| Heartbeats with draws > 200 | 49/49 | 40/40 |

**Per-frame job counts.** pvsjob, spuconstraints, vehiclephysics, octreequery and occjob per frame match B1 to within 0.5 %. renderablejob per frame is lower (23.6 vs 27.5), and so are a few particle jobs. **Investigated** (`t82b/burst_timeline.txt`): this is window composition, not changed behaviour.
- Both runs show the same burst classes per frame: 21 or 20 renderablejob runs on the grid, then 76 once the race starts, about 35–40 s after entry.
- Because T82B entered the race 10 s later, its window holds 27 frames of the heavy class versus B1's 71.
- VERIFIED: the class lengths are identical. B1 is 20×209 / 21×307 / 76×71; T82B is 20×209 / 21×304 / 76×27.

### Phase 7: performance, B1 vs T82B

Whole window, as reported (mixes the classes above, so it favours T82B):

| | B1 | T82B |
|---|---|---|
| Race fps | 11.32 | 13.03 |
| Frame p50 / p95 / p99 (ms) | 82.1 / 132.0 / 138.4 | 73.7 / 111.4 / 115.3 |
| PPU main-thread wait (ms/frame) | 47.9 | 49.5 |
| WWS job time (ms/frame, all wids) | 50.1 | 36.5 |
| renderablejob (ms/frame) | 22.5 | 8.3 |
| renderablejob mean per run | 0.819 ms | 0.352 ms |
| **Interpreted instructions per renderablejob run** | **42,105** | **0** (12,750 runs) |
| Interpreted instructions, all modules | 680,298,004 | 17,376 |

**Like-for-like, by frame class** (`t82b/phase_matched.py`; a frame runs from one renderablejob burst start to the next):

| Class | Frame-interval p50 (ms) B1 → T82B | renderablejob ms/frame | WWS ms/frame |
|---|---|---|---|
| 20 runs (grid) | 82.3 → 74.4 (−9.6 %) | 18.7 → 7.2 | 44.8 → 34.8 |
| 21 runs (grid) | 81.2 → 72.8 (−10.3 %) | 17.2 → 6.6 | 43.8 → 34.3 |
| 76 runs (race started) | 131.5 → 113.4 (−13.8 %) | 55.5 → 33.3 | 92.1 → 71.5 |

- **Interpreter fallback reduction (VERIFIED, kind-27 counts):** renderablejob fell from 42.1 k interpreted instructions per run to **0**, in every run and every class. All-module interpreted instructions fell 680.3 M → 17.4 k (−99.997 %).
- **§8 estimate check:** predicted about −9 ms/frame of renderablejob time on the B1 mix; measured −10.5 to −11.5 ms/frame on the grid classes and −22 ms/frame on the race class. renderablejob's native cost per run is 315–440 µs.
- **Frame time:** about 8–9 ms/frame shorter on the grid classes (≈ 10 %) and about 18 ms in the race class.
- **PPU wait did not fall** (47.9 → 49.5 ms/frame, different class mix). HYPOTHESIS: the PPU's wait is bounded by something other than renderablejob, such as wid 2/vehiclephysics or the GPU. Not investigated here.
- **Not measured:** native/interpreter transitions and stack unwinds. The counters stayed off for the performance run, as required; the kind-27 counts above are the transition evidence.

### Remaining interpreter transitions (VERIFIED, unchanged from B1)

- spuconstraints: 1.875 interpreted instructions per run; spuxform: 1 per run. This is the policy module's interrupt prologue (§1 row 3), with the same 8 logged `microstep` lines in both runs.
- Not measured, but not interpreted: the per-job CRT `spu_restart_dispatch` (§1 row 9).

### Recommendation for T81 integration

- **Integrate the T82 lifter change first and on its own.** It is one lifter rule that changes one line of lifted output and needs no runtime change. It is orthogonal to T81's concurrency work.
- The off-by-default counters (`PS3_SPU_AOT_PROF`) are optional. They carry no measured overhead, but they are not needed by the fix.
- **Rebase T81's measurements on T82B,** not B1. renderablejob is no longer the dominant WWS cost; pvsjob (≈ 15 ms/frame) and vehiclephysics (≈ 8.8 ms/frame) now are. Any T81 speedup claimed against B1 would include the T82 gain.
- **Use a matched-class comparison** (`phase_matched.py`) or equal race-entry times in A/B work. A 10 s difference in race entry changes the per-frame job mix.

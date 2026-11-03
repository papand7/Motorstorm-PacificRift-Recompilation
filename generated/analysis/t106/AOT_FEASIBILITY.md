# T106: WWS relocatable-job AOT on the race lineage — feasibility (offline)

2026-10-27. Offline only. No game build, no game launch, no lifter run over game binaries, no merge, no push, no commit to any named branch. `ps3recomp-t106` was not modified. Private outputs live under `generated/analysis/t106/aot_feasibility/`.

Labels: **VERIFIED** (checked here, or by a cited run with its log), **PARTIAL**, **HYPOTHESIS**, **BLOCKED**.

## 0. Verdict

- **Feasible and cheap (VERIFIED offline).** The missing chain is 8 commits. They cherry-pick onto `a9679cc` with **one trivial conflict**: `spu_interp.c`, two lines plus one added line, resolved with the exact text of the `0ab0d16` tree. The resolved series also applies cleanly to the newer t106 tip `6be362a`.
  - After the chain, the SPU runtime, lifter and reloc/switch tests equal `0ab0d16`, except for the race lineage's own `spurs_job.c` job counters and its `ppu_trace.cpp` changes.
- **No re-lift is needed (VERIFIED).**
  - The trial tree's `tools/spu_lifter.py` is the same git blob (`6616441…`) as `0ab0d16` and `0b0b89b`. That lifter produced `generated/spu_raw/wws_reloc_t81c`.
  - Its 31 module images still match the current decrypted EBOOT (`verify_wws_reloc.py` RESULT PASS).
  - All 31 lifted TUs and the registration TU compile against the trial tree with the race build's exact flags. Their disassembly is **identical, 31/31**, to the T81C build objects. T81C found those identical to the run-validated T82B objects.
- **The build integration is missing on the race side.** `port/CMakeLists.txt`, which race builds such as `build/motorstorm-t96i` configure from, has no `MSPR_WWS_AOT` block. Only `port-t70/` has it, as a 20-line block.
- **Expected gain (VERIFIED on the older lineage; HYPOTHESIS for t106).** These figures come from earlier runs, not from the race lineage:
  - B1 against A1″: WWS job time 169.4 → 50.2 ms/frame, race fps 5.04 → 11.32.
  - T82B: renderablejob 22.5 → 8.3 ms/frame, WWS 50.1 → 36.5 ms/frame, frame p50 −9.6 % to −13.8 % (phase-matched).
  - Whether the same gain shows up on the t104/t106 renderer is unmeasured.

## 1. What the commits do

### ad69e8e — SPU microstep link fix (runtime, 4 lines)
- `spu_smc_microstep` (`spu_channels.c`) wrote the link for `brsl`/`brasl`/`bisl`/`bisled` into all four words (`spu_splat_u32`).
- The ISA, the interpreter and the lifter write only the preferred word and zero the rest (`spu_link`). Now the microstep does too.
- Why it matters: every Wws job enters through the microstep and finds its own base with `brsl $r126,.+4`. Before the fix, interpreted and lifted jobs differed in words 1–3 of r126 and of every register derived from it.
- `test_spu_reloc_job` depends on this fix: 16 byte-for-byte checks fail without it. There is no standalone test in this commit.

### 54c06d2 — job spans (dependency of d1b4119)
- Adds `PS3_FTRACE_SPUJOB=<ret LS>`: ftrace kinds 26/27, `runtime/spu/spu_jobspan.h`, and a per-thread `t_spu_interp_steps_total`.
- d1b4119 builds directly on it: it extends `spu_jobspan.h` and `test_spu_jobspan.c`, adds kinds 28/29, and its AOT hook writes `t_spujob.has_aot/aot_res/aot_img`.
- **Dependency answer:** d1b4119 needs ad69e8e and 54c06d2. It does **not** need 478aea3, bdf8224 or 88feeb5. Those three are later tracer corrections: close the span at the return's dispatch and record jobs that never return; `PS3_FTRACE_ARM`; open the span only at the PM's dispatched entry. They are optional, but they are the tracer every A/B measurement (A1″, B1, T82B) used.

### d1b4119 — WWS relocatable job AOT
- **The problem.** MotorStorm's Wws_Job policy module (PM image `0x4D535052` = 1297305682) DMAs job modules to a base it picks at run time. The base word is at LS `0x1320`. It enters each job with `bisl $r0`, r0 = `0x3214`, at `base + header[0x10]`.
- **Lifting: `tools/spu_lifter.py --reloc`.**
  - Each module is lifted once, at its link base (header +0x28, `0x4000` for all 31).
  - Every PC the guest can observe is emitted as `SPU_RA(addr)` = `(addr + ctx->reloc_delta) & 0x3FFFF`. That covers link values, drain return points, `ctx->pc` on tails and handoffs, and `lqr`/`stqr` addresses.
  - Functions register under `SPU_RELOC_KEY_BIT` (`0x80000000`), so an ordinary absolute lookup can never hit them.
  - Images containing `bra`/`brasl`/`lqa`/`stqa` are refused. `--reloc` with `--chain-chunks` is refused.
  - Any word the lifter cannot translate becomes a hand-off: publish the rebased pc, return to the dispatcher, and the interpreter continues from there. The manifest lists these as `interpreter_handoffs`.
  - Immediates (`ila` and friends) stay absolute, as on hardware. So a module the game loads somewhere other than 0x4000 is still exact; the lift does not need to know the base.
- **`tools/lift_wws_reloc.py`.** For each `*.bin` it:
  - checks the header (magic `0xC0DEC0DE` at +0x20, entry at +0x10, link base at +0x28);
  - wraps the image as an SPU ELF and runs the lifter with `--reloc --auto-functions`, seeding the entries `lift_jobmods` proves exist;
  - writes `<out>/<module>/spu_recomp.{c,h}`, `wws_reloc_manifest.json` and `wws_reloc_register.c`. The registration TU calls `spu_wws_register_pm(pm, 0x1320, 0x3214)`, then `spu_reloc_register_module(sig16, entry16, link_base, entry_off, span, body_hash, image_id)` for each module.
  - With `--ctor` it adds a constructor that registers only when `PS3_SPU_WWS_AOT=1` exactly.
- **`runtime/spu/spu_reloc.h`.** API, result enum and `spu_reloc_body_hash`, a word-wise 64-bit non-cryptographic hash that the Python side mirrors. The result codes are:

  | Code | Meaning |
  |---|---|
  | 0 | NOT_JOB |
  | 1 | RESIDENT |
  | 2 | INSTALLED |
  | 3 | UNKNOWN |
  | 4 | MISMATCH |
  | 5 | NO_SLOT |
  | 6 | DISABLED |
  | 7 | BAD_BASE |
  | 8 | BASE_REFUSED |

- **Dispatch-time rebase (`spu_channels.c`).** `spu_indirect_branch` calls `spu_wws_job_enter` for policy-mode branches, and only when a PM is registered; otherwise the cost is one predicted-false branch. It accepts a job only when all of these hold:
  - the image is the registered PM, r0 is the registered return point, and pc is not the return point;
  - the code-base word is 16-byte aligned and inside LS;
  - `pc == base + header[0x10]`;
  - the 16 identifier bytes match a registered module, and so do the entry offset and the 16 entry bytes;
  - the full-span hash matches. The hash is checked on first use at a base and after any DMA GET that overlaps the module.

  It then installs the module in a `resident_code[]` slot with `link_base` set. The new field `link_base` is added to `spu_context.h`, along with `ctx->reloc_delta`.
  - Lookups for that slot use `(pc - lsa + link_base) | SPU_RELOC_KEY_BIT` and set `ctx->reloc_delta = lsa - link_base`.
  - `spu_overlay_note_get` drops a relocatable slot on any overlapping GET.
- **Switches.** All are read once, by the first `spu_wws_register_pm`, i.e. in the constructor before any SPU thread exists:

  | Switch | Effect |
  |---|---|
  | `PS3_SPU_WWS_AOT=1` | Enables the generated constructor. Unset means nothing is registered. `=0` gives DISABLED. |
  | `PS3_SPU_WWS_AOT_BASES=<hex,…>` | At most 16 bases. Any other base gives BASE_REFUSED and is interpreted. More than 16 entries, or text with no hex base, warns and fails closed. |
  | `PS3_SPU_WWS_AOT_VERIFY=1` | Re-hashes the span at every resident entry, which catches non-DMA writes. |
  | `PS3_FTRACE_SPUJOB=3214:1320` | Adds kinds 28/29 (module id and base, AOT result). |

  CMake capability is the `MSPR_WWS_AOT=ON` option, which is in `port-t70` only (§4).
- **Fail-closed behaviour.** Every refusal leaves the job to the interpreter, unchanged:
  - unknown module, mismatch, no free slot, bad base, refused base, disabled, or a different PM;
  - `8de3590` tests each of these as byte-identical to a build with no AOT: all guest memory, LS, GPRs, and channel/MFC state.

### 8de3590 — tests
`tests/test_spu_reloc_job.{c,py}` now has 85 checks, all on synthetic modules with no game bytes:
- lifted equals interpreted at bases 0x4000, 0x8C00, 0x15C00 and 0x30000;
- residency, and selection between two resident modules;
- the 9 fail-closed states;
- the constructor gate and the hardening switches.

### 0ab0d16 (= 0b0b89b) — conditional-branch switch classification
- **The fix.** `compute_link_returns()` now counts conditional-branch predecessors. If the nearest writer of rN is `il`/`ilh`/`ilhu`/`ila`/`iohl`, or `ai`/`ori … 0`, it stays a link return; any other writer means a computed dispatch.
- **Effect on the lift.** It fixes renderablejob's `bi $r2` at LS 0xA650 (jump table at 0xA654), which had been lifted as `SPU_RET_REG`. The lifted output changes by **one line, in renderablejob only**. That difference is between `wws_reloc` and `wws_reloc_t81c`/`_t82`.
- **Also added:**
  - `PS3_SPU_AOT_PROF=<s>`, off by default: miss/rejoin/resume/restart counters in a fixed atomic table, with hooks in `spu_drain.c`;
  - `tests/test_spu_switch_linkret.{c,py}` (26 checks) and `tests/bench_spu_switch_linkret.py`.

## 2. Does it apply to t106? (VERIFIED)

Trial worktree: `scratch/t106/aot_trial`, created with `git -C ps3recomp worktree add --detach … a9679cc`. Commits were made with a throwaway identity on detached HEAD only. Logs: `aot_feasibility/logs/cp_*.log`.

| # | Picked | Trial sha | Result |
|---|---|---|---|
| 1 | ad69e8e | 3836eb3 | clean |
| 2 | 54c06d2 | 7e907b4 | **conflict** in `runtime/spu/spu_interp.c` (see below) |
| 3 | d1b4119 | 293a740 | clean |
| 4 | 8de3590 | b122c05 | clean |
| 5 | 0ab0d16 | dac697f | clean (**minimal tip**) |
| 6 | 478aea3 | c6bdd1d | clean (optional tracer) |
| 7 | bdf8224 | d444808 | clean (optional, `PS3_FTRACE_ARM`; merges with the race lineage's `ppu_trace.cpp` work) |
| 8 | 88feeb5 | 8babd2a | clean (**full tip**) |

- **The conflict, and how it was resolved.**
  - Cause: t106 (a80b794's equivalent) made `g_spu_interp_last_pc`/`g_spu_interp_steps` `SPU_THREAD_LOCAL`, while 54c06d2 adds `__thread uint64_t t_spu_interp_steps_total` beside the old non-TLS declarations.
  - Resolution: keep `SPU_THREAD_LOCAL` and add the new line. This is identical to `0ab0d16:runtime/spu/spu_interp.c`. Difficulty: trivial.
- **Tree check.** `git diff 0ab0d16 <minimal tip>` over the lifter, `lift_wws_reloc.py`, `spu_reloc.h` and the reloc/switch tests is **empty**. In `runtime/spu` it differs only by:
  - the race lineage's `spurs_job.c` job counters;
  - the three optional tracer commits, which are absent at the minimal tip.

  At the full tip only `spurs_job.c` and `ppu_trace.cpp` differ, and both are race-lineage additions.
- **Overlap with the race lineage.** Its SPU changes since the fork at `c529ab0` are:
  - `spu_channels.c`: the PM poll-log throttle (independent of this series);
  - `spu_drain.c`/`spu_interp.c`/`spu_interp.h`: TLS diagnostics;
  - `spurs_job.c` counters;
  - `cellSpurs` maxContention/five-lane changes (independent of this series).
- **Patch series.** `aot_feasibility/patches/0001…0008-*.patch`, exported with `git format-patch a9679cc..8babd2a`. Patch 0002 carries the resolution. SHA-256:
  - 0001 `6bf1d803…50d2`
  - 0002 `6483e3b0…2953`
  - 0003 `918c0f9d…bd20`
  - 0004 `b21f2f3a…10aa`
  - 0005 `7059ab37…6e12`
  - 0006 `f19743e9…0656`
  - 0007 `06eab436…9582`
  - 0008 `b52f5a07…181e`
- **Newer t106 tip.** During this study `ps3recomp-t106` moved to `6be362a` ("test_spu_diag_tls: standalone fixture", which touches only `tests/test_spu_diag_tls.c` and `tools/test_spu_diag_tls.py`). It also has an uncommitted one-line edit in `spu_channels.c`, in `spu_mfc_atomic` at about line 766, which is not in any patch hunk. That edit is not mine and was left alone.
  - A second throwaway worktree at `6be362a` took all 8 resolved commits with no conflict.
- **State.** Both trial worktrees (`aot_trial`, `aot_trial2`) were removed with `git worktree remove --force` and pruned. `scratch/t106/` is empty. The trial commits now exist only as dangling objects and as the exported patches. No named branch was touched.

## 3. Generated-code compatibility

- **Lifted outputs.** All are private:
  - `generated/spu_raw/wws_reloc` (original T37/T70 lift, B1);
  - `generated/spu_raw/wws_reloc_t82` (T82B, run-validated) and `generated/spu_raw/wws_reloc_t81c`. These two are byte-identical (95/95 files);
  - analysis copies: `generated/analysis/t37/lift`, `t81/t81c/lanes_*/lift`, `t82/lift_t70g`, `t82/lift_t82`;
  - scratch copies under `scratch/t37`, `scratch/t54` and `scratch/t60`.
  - The manifest is identical in all three spu_raw lifts (`a084eee5…d298`), and so is `wws_reloc_register.c` (`d347d562…082a`). Only renderablejob `spu_recomp.c` differs between `wws_reloc` and `_t81c`.
- **Module set.** 31 of 31 registered, all with link base 0x4000; image ids start at `0x4D4A0000`. The file name is `ms_<sha256 prefix>_e<entry>`:
  - renderablejob `ms_10aa3f4480ef_eEE40`: 63,184 B, hash `BA6FE5DE13B13916`, 1,018 functions, 61 `.word` hand-offs, all of them rodata strings that never execute;
  - vehiclephysics `ms_1ec6c9bb0a22_e7DE0`: 7 `.word` hand-offs;
  - pvsjob `ms_87a63dd45e5d_e2490`;
  - occjob, octreequery, spuconstraints, spuxform, groundrush/screenrush/squash/visibility jobs, step1/step2module, trailsupdate, vehicledeformation, spupathfinding, generatefogtable;
  - the particle modules: Particle/Orientated*Filler, Process/Cull Emitters/Effectors, ParticleSort;
  - LibMP3 surround and stereo jobs.

  The full table is in `wws_reloc_t81c/wws_reloc_manifest.json`.
- **Job images are the same for both lineages (VERIFIED).** Both lineages build from the same `generated/decrypted/EBOOT.elf` (SHA-256 `bbb7fe25…b287`; `PORT_SPU_INPUTS` is identical in the t96i and t81c caches). `verify_wws_reloc.py`, which is read-only (it compares hashes and bytes and does not lift), passes all 31 against that EBOOT (`logs/verify_wws_reloc_t81c.log`). The Wws PM lift `generated/spu_raw/wws_job_pm` and `port/wws_job_pm_register.c` (image `0x4D535052`) are shared by both lineages.
- **Re-lift not required (VERIFIED).**
  1. The lifter is identical to the one that produced `_t81c`, which already includes the 0ab0d16 change.
  2. The lifted C uses `ctx->reloc_delta`, `SPU_RELOC_KEY_BIT`, `spu_link`, `spu_drain_call`, `spu_img_restore`, `spu_indirect_branch(_mt)`, `SPU_IB_DISPATCH`, `spu_ls_read128/write128`, `spu_rdch/wrch`, `spu_stop`/`spu_halt` and the `spu_helpers.h` ops. The registration TU uses `spu_reloc.h`, `spu_begin_image` and `spu_wws_register_pm`.
  3. **Against unmodified t106:** 32 of 35 TUs fail. Each lifted TU fails with `no member named 'reloc_delta' in 'struct spu_context'`, and the registration TU fails with `'spu_reloc.h' file not found` (`obj/t106_unmodified/*.log`). The 3 TUs that compile are the runtime files.
  4. **Against the trial tree:** 35 of 35 compile, both at the minimal and the full tip (`obj/trial`, `obj/full`). Flags are copied from `build/motorstorm-t96i/build.ninja` (lifted TUs: `/O2 /Ob2 /std:c17 -fwrapv -msse4.1 -DSPU_USE_DISPATCH_MT`; runtime: `-ffp-contract=off`). The `spu_context.h`/`spu_helpers.h`/`spu_interp.h` layout equals `0ab0d16`.
  5. The 31 trial module objects are disassembly-identical to `build/motorstorm-t81c-aot`'s objects (`llvm-objdump -d`, 31/31).
- An optional re-lift into a new directory would prove determinism. It needs authorization (it runs the lifter over game-derived binaries) and is not required.

## 4. Build-system changes needed

- **Race builds.** `build/motorstorm-t96i` was configured from `port/` with `PS3RECOMP_DIR=ps3recomp-t96i`, `RECOMP_DIR=generated/ppu-hooked-staging`, `SPU_DIR=port/spu` and `PORT_SPU_AVX2=OFF`. `port/CMakeLists.txt` lacks the block below. `port-t70/CMakeLists.txt` differs from `port/` **only** by this block (lines 203–222, verified with `diff`):
  ```
  option(MSPR_WWS_AOT ... OFF)
  set(MSPR_WWS_AOT_DIR ".../generated/spu_raw/wws_reloc" CACHE PATH ...)
  if(MSPR_WWS_AOT)  -> FATAL_ERROR without ${PS3RECOMP_DIR}/runtime/spu/spu_reloc.h or ${MSPR_WWS_AOT_DIR}/wws_reloc_register.c
     glob ${MSPR_WWS_AOT_DIR}/*/spu_recomp.c, append them + wws_reloc_register.c to SPU_SOURCES
  ```
  The lifted TUs then get the existing SPU-TU include and flag scoping (`-fwrapv -msse4.1 -DSPU_USE_DISPATCH_MT`).
- **Options.** Either add the block to `port/` (OFF by default, so existing configurations are unaffected) or use a new private `port-t106/` copy. The copy follows the T70/T81 pattern and leaves the shared `port/` untouched; it is the safer choice while other agents build from `port/`.
- **How T81/T82 did it.** `generated/analysis/t81/t81c/configure_t81c.cmd` runs:
  ```
  cmake -S port-t70 -B build\motorstorm-t81c-aot -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl -DPS3RECOMP_DIR=…\ps3recomp-t81c -DRECOMP_DIR=…\generated\ppu-hooked-staging -DSPU_DIR=…\port\spu -DPORT_SPU_INPUTS=…\generated\decrypted\EBOOT.elf -DPORT_ENABLE_SPU=ON -DPORT_HLE_NIDS_GENERATE=ON -DPORT_SPU_AVX2=OFF -DMSPR_WWS_AOT=ON -DMSPR_WWS_AOT_DIR=…\generated\spu_raw\wws_reloc_t81c
  ```
  - Result: 312/312 objects; `inspect_t81c_exe.py` passed 31/31 signatures and hashes, the constructor in `.CRT$XCU`, and default-off gates.
  - For t106, use the same command with `-S port-t106` (or `port`), `PS3RECOMP_DIR=<integrated t106>`, a new `-B build\motorstorm-t106-aot`, and `MSPR_WWS_AOT_DIR=generated\spu_raw\wws_reloc_t81c`, read-only.
- **Expected `build.ninja` difference** against a plain t106 build with the same tree: the 32 extra TUs and the link line only. Check it with an adapted `t81c/ninja_cmp_b1.py`.

## 5. Correctness risks

| Risk | Assessment |
|---|---|
| Relocation correctness | VERIFIED synthetic: lifted equals interpreted at 4 bases (85 checks). In game: every A/B run used `BASES=4000`, which is also the link base, so `reloc_delta` was 0 in every validated run. Non-zero deltas are validated only synthetically. The modules form some absolute addresses with `ila` (computed `bi`, switch-table bases) and keep absolute pointers in data. Those are exact *only if* the game itself only runs them at 0x4000, as the hardware would. Keep `PS3_SPU_WWS_AOT_BASES=4000` (PARTIAL for other bases). |
| Self-modifying code / DMA overlays | Any overlapping DMA GET drops the slot and forces a full re-hash. SPU stores, GETLLAR or PPU writes into a resident span are caught only with `VERIFY=1`, at the next entry. A write *during* a running job is never caught (documented). All validated runs used `VERIFY=1`, with 0 MISMATCH in B1/T82B. Cost: per T89, one re-hash per job is about 0.52 ms/frame of synthetic CPU work (renderablejob 8.8 µs per hash). |
| 5-lane concurrency | Registration tables and switches are written only in the constructor, before SPU threads exist. Per-thread state: `t_reloc_last`, round-robin `rr` (`SPU_THREAD_LOCAL`) and `t_spujob`. Slots are per `spu_context`. The `AOT_PROF` table uses atomics. A benign race: `PS3_LOG_FIRST` static counters (log only). Synthetic results: 5 lanes × 200 jobs, AOT outputs equal the reference with 0 lost spans (T81/T81C bench); `test_spurs_wws_concurrency` passes on the trial tree. **In game, AOT plus guest contention 5 (arm D) has never been launched** (T81C: 0 launches). HYPOTHESIS: safe. |
| Fallback | Fail-closed to the interpreter, tested in 9 states. The interpreter cannot rejoin relocatable code, so a miss inside a job runs interpreted until the PM or drain boundary (performance only, not correctness). Each job also takes one `spu_restart_dispatch` at its CRT manual-link entry (VERIFIED mechanism; cost unmeasured). |
| Race-lineage interaction | The race lineage changes renderer/GCM code, `spurs_job.c` counters and the PM poll log. None of these touch the reloc path. The renderablejob output feeds the RSX FIFO that the race renderer consumes. AOT output has been byte-identical in parity tests, but the race renderer has never been run with AOT (HYPOTHESIS: neutral). |

**Measured savings, all from the older lineage (`88feeb5`/`0b0b89b`, renderer before T84–T104):**
- **T70 B1 vs A1″** (`generated/analysis/t70/WWS_AOT_RACE_READINESS.md` §0j):
  - WWS job time 169.4 → 50.2 ms/frame (−70 %);
  - race fps 5.04 → 11.32;
  - p50 frame time 197.6 → 82.1 ms;
  - PPU wait 135.4 → 47.9 ms/frame;
  - per-module median speedups 2.0–13.5× (pvsjob 3.9×, vehiclephysics 5.5×, renderablejob 4.3×).
- **T82B vs B1** (`generated/analysis/t82/SPU_AOT_INTERPRETER_FALLBACKS.md` §10):
  - renderablejob 22.5 → 8.3 ms/frame, 0 interpreted instructions in 12,750 runs;
  - interpreted instructions, all modules: 680.3 M → 17.4 k;
  - WWS 50.1 → 36.5 ms/frame;
  - phase-matched frame p50 −9.6 % (grid), −10.3 % (grid), −13.8 % (race);
  - PPU wait did not fall (47.9 → 49.5 ms/frame).
- **T81B (synthetic):** five-lane AOT job 282.6 → 162.5 µs after the diagnostic-TLS fix, which t106 already has.

For t106 (HYPOTHESIS): WWS CPU time per frame should fall by roughly the same 70–78 %. Frame-time gain depends on whether WWS is on the race lineage's critical path, which T104's frame-critical-path report should tell. It must be measured with a matched-phase A/B.

## 6. Offline-testable pieces (run in the trial worktree)

Environment: `aot_feasibility/tools/run_trial.cmd`. It sets up the same environment as `t104/tools/run_suite_t104.cmd`: vcvars64, `build\llvm` clang 23.1.3 on PATH, `CC=scratch\t17\cc_shim.cmd`, `LIB=scratch\t17\lib`. The tests use synthetic modules only; none touch game data.

**Minimal tip `dac697f`** (logs `logs/min_*.log`):

| Test | Result |
|---|---|
| `tests/test_spu_reloc_job.py` | PASS 85, 0 failures |
| `tests/test_spu_switch_linkret.py` | PASS 26, 0 failures |
| `tools/test_spu_lifter_reloc.py` | PASS 13 |
| `tools/test_spu_jobspan.py` | PASS 8 |
| `tools/test_spu_diag_tls.py` | PASS 3 |

**Race-lineage regressions on the minimal tip** (logs `logs/reg_*.log`):
- PASS: `test_spurs_wkl_maxcont` (default + guest), `test_spurs_wws_concurrency` (default + guest), `test_mfc_resume_elements`, `test_spu_chain_chunks`, `test_spu_program_pipeline`, `test_ppu_trace`, `test_lifter_dedupe`, `test_lifter_header_name`, `test_spu_ls_inline`, `test_spu_disasm_ri10`;
- PASS, renderer: `test_vp_expand`, `test_rsx_frame_perf`, `test_vp_flush`, `test_rf_phase`, `test_geom_expand`, `test_draw_rejection`, `test_present_gate`, `test_gcm_stall_watch`;
- `test_spurs_scheduler`: SKIP (POSIX fixture; the earlier private runner `t82/tools/run_posix_fixture.py` was not used).

**Full tip `8babd2a`** (logs `logs/full_*.log`):

| Test | Result |
|---|---|
| reloc_job | 85 PASS |
| switch_linkret | 26 PASS |
| lifter_reloc | 13 PASS |
| jobspan | 12 PASS |
| jobspan_path | 63 PASS |
| ppu_trace | 6 PASS |
| diag_tls | 3 PASS |
| wws_concurrency | PASS |
| wkl_maxcont | PASS |
| gcm_stall_watch | 46 PASS |

Not run: `test_spu_fnms_zero_extended` (known Windows link failure), the SDK selftests (BLOCKED: no PS3 SDK), `spu_disasm_audit` (needs private images), and the timing-only benches.

**Pieces that could be integrated alone:**
- **ad69e8e alone.** A 4-line ISA-correctness fix to the interpreter-side microstep, which affects every lineage. Its regression coverage is in `test_spu_reloc_job` (the next commits), so on its own it has no test. It could get a focused microstep link test. Safe, but low value alone.
- **ad69e8e + 54c06d2 + 478aea3 + bdf8224 + 88feeb5** (tracer only, off by default; jobspan 12 and jobspan_path 63 pass). This adds the measurement instrument without any AOT.
- **The full AOT** (patches 0001–0005) is off twice by default: no registration without `PS3_SPU_WWS_AOT=1`, and with `MSPR_WWS_AOT=OFF` no lifted code is linked. All of its tests pass offline. It is the natural unit.

## 7. Integration plan

1. **(Needs authorization: commit to `agent/t106-spu-performance`; the t106 owner must first commit or park the uncommitted `spu_channels.c` edit.)**
   - Apply: `git -C ps3recomp-t106 am --3way generated/analysis/t106/aot_feasibility/patches/000{1..5}-*.patch`. Add 0006–0008 to keep the tracer comparable with B1/T82B; this is recommended.
   - Before each commit: `python tools/audit_public.py --staged`.
2. **Offline gate (no authorization needed).** Run each `<script>` through `run_trial.cmd` with `TREE=ps3recomp-t106` (or `generated/analysis/t106/tools/run_one.cmd`). Scripts: the reloc_job, switch_linkret, lifter_reloc, jobspan, jobspan_path, diag_tls, wws_concurrency, wkl_maxcont, ppu_trace and renderer tests from §6. Then `TREE=ps3recomp-t106 TAG=t106int aot_feasibility/tools/compile_check.cmd`, which expects 35/35.
3. **Build recipe (no authorization needed; private).** Copy `port/` to `port-t106/` and add the `MSPR_WWS_AOT` block from `port-t70/CMakeLists.txt` lines 203–222. Write `configure_t106_aot.cmd` from the T81C script (§4), pointing it at `ps3recomp-t106` and `generated\spu_raw\wws_reloc_t81c` (read-only). Do not re-lift.
4. **(Needs authorization: one full build.)** Configure `build\motorstorm-t106-aot`, then `cmake --build … --parallel 2`. Then:
   - `ninja_cmp` against a plain t106 build: only the +32 TUs may differ;
   - `inspect_t81c_exe.py` adapted: 31/31 signatures and hashes, constructor present, gates off;
   - pin the exe.
5. **(Needs authorization: two launches.)** A/B on the same exe:
   - A: no `PS3_SPU_WWS_AOT`;
   - B: `PS3_SPU_WWS_AOT=1 PS3_SPU_WWS_AOT_VERIFY=1 PS3_SPU_WWS_AOT_BASES=4000`, plus `PS3_FTRACE_SPUJOB=3214:1320`;
   - fresh HDD, bounded session, no input.

   Gates: 0 MISMATCH, kind-29 RESIDENT/INSTALLED only, Havok 5.00 steps/frame, draws as in A, renderablejob interpreted ≈ 0. Compare phase-matched (`t82/t82b/phase_matched.py`).
6. Only after B passes, consider arm D (with `PS3_SPURS_GUEST_MAXCONT=1`), which has never been run in game. It is a separate authorization.

## Files

- Report: `generated/analysis/t106/AOT_FEASIBILITY.md`
- Patches: `generated/analysis/t106/aot_feasibility/patches/0001…0008-*.patch`
- Tools: `generated/analysis/t106/aot_feasibility/tools/run_trial.cmd`, `compile_check.cmd`
- Logs: `generated/analysis/t106/aot_feasibility/logs/` (`cp_*`, `min_*`, `reg_*`, `full_*`, `verify_wws_reloc_t81c.log`)
- Objects (private): `generated/analysis/t106/aot_feasibility/obj/{trial,full,t106_unmodified}/`

# T54: WWS job AOT integration readiness

Offline only. Nothing was launched, and no game or port build was made. Nothing was merged or pushed. Neither shared runtime files nor `port/` were modified (`port/CMakeLists.txt` sha256 `b27b99b1…ce9a` is unchanged).

| Item | Location |
|---|---|
| Branch | `agent/t54-wws-aot-integration` @ `b036875` (worktree `ps3recomp-t54`), local only. Parents: T37 `bb072a3`, then `ad8c7f8`. |
| Commit content | Tests and `tools/lift_wws_reloc.py` only; no runtime files. |
| CMake patch (not applied) | `port_cmake_wws_aot.patch` (sha256 `31cee2d6…99d7`) |
| T24 runtime proposal (not applied) | `t24_proposal_wws_aot_hardening.patch` (sha256 `892af82a…ecc4`) |
| Logs | `logs/` |

## 1. Review of T37 `ad8c7f8` and `bb072a3`

| Finding | Label |
|---|---|
| `ad8c7f8` is a correct fix. `spu_smc_microstep` copied the brsl/bisl link into all four words; the ISA puts it in the preferred word and zeroes the rest. T24's current `af37553` still has the bug (`spu_channels.c:2330`, `:2358`). Every interpreted Wws job enters through this path. | VERIFIED |
| Both commits merge cleanly onto T24 `af37553` with no conflicts (merge-tree, then a real merge in a throwaway worktree). | VERIFIED |
| On that merged tree, `test_spu_reloc_job`, `test_spu_lifter_reloc` and `test_spu_jobspan` all pass. T24's own 15-test SPU suite (`spu_all.sh`: PUTLLC/GETLLAR, park/wake, stop 0x110, SPURS scheduler, EF DMA wake, LFQueue, coherency) also passes. | VERIFIED |
| T24's newer work (word-wise PUTLLC, GETLLAR back-off, PUT commit hook, stop 0x110) does not touch the AOT dispatch, `note_get` or the job-span code. | VERIFIED (source diff) |
| With nothing registered (`s_wws_pm_n == 0`), the added cost in `spu_indirect_branch` is one predicted-false branch. The `note_get` change only takes effect when a slot has `link_base` set. | VERIFIED (source) |
| `spu_context` gains `link_base` (in `resident_code[4]`) and `reloc_delta`. Because the layout changes, every runtime and SPU object must be rebuilt. | VERIFIED |
| `SPU_RELOC_NOT_JOB` and `BAD_BASE` refusals are not logged and do not update `spu_wws_last_result()`. A job refused because of its base therefore shows no kind-29 record. | VERIFIED; fixed in the proposal |

## 2. Dispatch safety conditions (the module identity check)

Facts about the 31 retail modules, from the T37 manifest:

| Fact | Label |
|---|---|
| 31 distinct 16-byte identifiers and 31 distinct body hashes. | VERIFIED |
| All 31 have the same `entry16` (a shared prologue), so it does not tell modules apart. | VERIFIED |
| Spans run from 0xA20 to 0x19A10 bytes. | VERIFIED |
| Link base is 0x4000 for all. | VERIFIED |
| Image ids are 0x4D4A0000+i, distinct from the PM's id (0x4D535052). | VERIFIED |
| 68 undecoded `.word` hand-offs, in 2 modules, go to the interpreter. | VERIFIED |

A lift runs only when **all** of these hold at the `bisl` job entry (`spu_wws_job_enter`):

1. The context is in policy mode, `image_id` is the registered PM (0x4D535052), and `r0` is the registered return point (0x3214).
2. The code-base word (LS 0x1320) holds `base`, which is 16-byte aligned with `base + 0x30 ≤ LS`. Also `pc == base + be32(base+0x10)`, so the word agrees with the entry actually taken.
3. `PS3_SPU_WWS_AOT` is not `0`. In the proposal, `base` must also be listed in `PS3_SPU_WWS_AOT_BASES` when that is set.
4. The 16 identifier bytes at `base` match a registered module.
5. On first use at that base, or after any overlapping GET: `entry_off`, `base + span ≤ LS`, `entry16`, and the **full-span 64-bit hash** must all match. When the slot is already resident, the identifier, the image id of the slot and `entry16` must match; in the proposal, `PS3_SPU_WWS_AOT_VERIFY=1` re-hashes the full span here too.
6. A code slot is free, or one is held by another relocatable lift. Absolute overlays are never evicted unless the new module overwrites them.

The identifier alone is not sufficient, because the entry bytes are generic; what discriminates is the identifier plus the full-span hash. The hash is non-cryptographic: it guards against a wrong or partly loaded body, not against an adversary.

## 3. Fail-closed fallback (design and evidence)

Every refusal returns before any guest-visible mutation. The existing code-slot lookup then misses, and the job runs through `spu_smc_microstep` → `spu_interp_run_until`, exactly as it does today.

The new `state` test compares each refusal against a build with **no AOT registered**. It runs one job per process at bases 0x4000 and 0x8C00, and compares 1,312,876 bytes per run byte for byte: all guest memory, the 256 KB LS, 128 GPRs, pc/status/stop/srr0/events, MFC registers and tag status, list-stall state, and all mailboxes and signal channels.

| Condition | Decision | Interpreted | State == no-AOT |
|---|---|---|---|
| Unknown identifier | UNKNOWN (3) | yes | VERIFIED |
| Known identifier, different body (unverified relocation or patched body) | MISMATCH (4) | yes | VERIFIED |
| No free slot (4 absolute overlays resident, left untouched) | NO_SLOT (5) | yes | VERIFIED |
| `PS3_SPU_WWS_AOT=0` | DISABLED (6) | yes | VERIFIED |
| Misaligned code base (`base\|4`) | BAD_BASE (7) | yes | VERIFIED |
| Code base past the end of LS | BAD_BASE (7) | yes | VERIFIED |
| In-range code base that disagrees with the entry | NOT_JOB | yes | VERIFIED |
| Another PM image | NOT_JOB | yes | VERIFIED |
| Base not on the allowlist (proposal) | BASE_REFUSED (8) | yes | VERIFIED (patched tree) |
| Accepted (control) | INSTALLED (2) | 0 instructions | VERIFIED: the lift equals no-AOT too |

**Overlays.** Any DMA GET that overlaps a relocatable slot drops it; this is VERIFIED by the scenario test. Every GET, including list elements, reaches `note_get` through `mfc_do_transfer` (source). Code DMA'd outside a module's span has no slot, so it is interpreted.

**Effect on SPURS scheduling and job completion.** This is VERIFIED for the synthetic jobs:

- The fallback leaves identical channel, MFC and completion-PUT state.
- The AOT path is identical as well; only timing differs.
- The job-level hook touches no SPURS or kernel state, only the `resident_code` table and the per-thread trace fields.
- There is no preemption inside a job on either path. The PM regains control at 0x3214 in both cases.

## 4. Relocation limitations

- **ila absolutes (VERIFIED).** The modules build 0x4000-based addresses with `ila`. The lift keeps them unchanged, so it is exactly as faithful as the interpreter at any base. Equivalence has been shown at 0x4000, 0x8C00, 0x9400, 0x15C00, 0x2F000 and 0x30000. Whether the game ever runs a module away from 0x4000 is unknown (HYPOTHESIS); the trace in §8 answers it. If the PM patches relocations into a module, the hash fails and the job is interpreted.
- **Writes into a resident span that are not DMA GETs (VERIFIED gap).** Examples are SPU `stq*` into the span, GETLLAR into LS, and PPU LS writes. These do not drop the slot, so the next entry stays resident. The proposal adds `PS3_SPU_WWS_AOT_VERIFY=1`, which re-hashes on every entry; the test shows it catches this case. The cost is at most 0x19A10/8 ≈ 13k hash steps per entry, so use it for the first A/B only.
- **Code overwritten while it runs (HYPOTHESIS, low risk).** A lifted function keeps running its old code until the next dispatch.
- **Undecoded words.** The 68 `.word` sites in 2 modules hand off to the interpreter if they are reached.

## 5. Tests (all offline)

| Test | Tree | Result |
|---|---|---|
| `tests/test_spu_reloc_job.py`, extended (select, state ×22, ctor opt-in, plus the T37 checks) | T54 `b036875` | 0 failures (`logs/reloc_job.log`) |
| Same, plus `test_spu_lifter_reloc` and `test_spu_jobspan` | merge of T24 `af37553` + T54 | 0 failures (`logs/merged_*.log`) |
| T24 SPU suite (15 tests) | same merge | all rc=0 (`logs/t24suite/`) |
| Proposal: allowlist (0x4000 AOT, 0x8C00 refused == no-AOT) and non-DMA write (default stays resident; VERIFY refuses) | T54 + proposal patch | 0 failures (`logs/prop_reloc_job.log`) |

New checks:

- **select:** two modules are resident at once (0x8C00 and 0x15C00). Over two rounds, each job runs its own lift with its own delta (0x4C00 and 0x11C00).
- **ctor opt-in:** the generated constructor registers nothing unless `PS3_SPU_WWS_AOT=1`.

Toolchain: `scratch/t54/test_in.cmd` (t15 env, t17 shim). `python ../tools/audit_public.py --staged` shows only the 25 pre-existing items; none are T54 files.

## 6. CMake integration (`port_cmake_wws_aot.patch`, +19 lines, dry run OK)

- `option(MSPR_WWS_AOT … OFF)`. When ON, it globs `generated/spu_raw/wws_reloc/*/spu_recomp.c` and adds `wws_reloc_register.c` to `SPU_SOURCES`. Those sources inherit the existing SPU flags.
- Configure stops with an error when ON if the runtime lacks `spu_reloc.h` or the lift is missing.
- Enabling AOT takes two opt-ins: the CMake option, then `PS3_SPU_WWS_AOT=1` at run time.
- AVX2 stays separate: the lift follows `PORT_SPU_AVX2`, which stays OFF.
- Prerequisite: re-lift privately with `python tools/lift_wws_reloc.py --modules generated/analysis/t37/modules --out generated/spu_raw/wws_reloc --pm-image 0x4D535052 --codebase-word 0x1320 --job-return 0x3214 --ctor`. The T37 output in `generated/analysis/t37/lift` has no constructor.

## 7. Performance measurement plan (needs authorization)

- **Build.** One build with `MSPR_WWS_AOT=ON` and the default `PORT_SPU_AVX2=OFF`. The AVX2 build is a separate, later arm.
- **Arms.**
  - A: `PS3_SPU_WWS_AOT` unset (interpreter).
  - B: `PS3_SPU_WWS_AOT=1`, `PS3_SPU_WWS_AOT_BASES=<trace result>`, `PS3_SPU_WWS_AOT_VERIFY=1`.
  - C (optional): B without VERIFY.
- **Runs.** Three alternating runs per arm, each with a private hdd1 snapshot (`scratch/t25/t25_launch.py`).
- **Environment.** Every `vm_inline_ok` trigger must be unset (`RSX_RTVIS`, `PPU_*WATCH`, …); setting any of them, even empty, disables inline loads.
- **Windows.** Use a per-run garage window, never one fixed time window.
- **Metrics.**
  - Per module (`generated/analysis/t37/job_report.py`): kind 26 span, kind 27 interpreted instructions (B should be ~0), kind 29 decision counts.
  - wid 1 and wid 2 busy time, measured from PICK (kind 24).
  - Main's gate waits (`t33/gate_link.py`; baseline ~37 ms/frame wid 1, ~8 ms/frame wid 2).
  - Frame time.
- **Correctness gate for B.** No MISMATCH or NO_SLOT storms, the same frontend progression, and no new assertions.
- **Expected effect (HYPOTHESIS).** Integer/shuffle jobs gain up to ~30× per T33, float-heavy jobs ~2×, and synthetic jobs gained 2.7–9.6×. The frame effect is bounded by how much of the wid 1/2 gate waits is job execution.

## 8. Exact configuration for the authorized load-address trace

This is a record-only trace with no AOT, run on a build containing `bb072a3` (any `MSPR_WWS_AOT` setting, with `PS3_SPU_WWS_AOT` **unset**). Launch it the way `scratch/t25/run_t25_ab.ps1` arm A does, through `scratch/t25/t25_launch.py --hdd1 <fresh private snapshot>`. Use T25's base environment, with these changes:

```
PS3_FTRACE=30:120:{run_dir}\ftrace.txt
PS3_FTRACE_SPUJOB=3214:1320
PS3_FTRACE_SPURS=1
PS3_FTRACE_SYNC=1
PS3_FTRACE_CAP=8388608
(unset) PS3_SPU_WWS_AOT, PS3_USLEEP_SPIN, RSX_RTVIS, PPU_RWATCH, PPU_FORCE_READ_ADDR,
        YDKJ_RWATCH, PPU_RVAL, PPU_RVAL64, PPU_HOTMAP, PPU_HOTREAD, PPU_SPINBT, PS3_TRACE
```

- Optionally, after the garage, send CROSS, UP, CROSS to reach `mainmenu`. Race modules such as vehiclephysics (entry `+0x7DE0`) need a later race leg.
- **Analysis.** Run `python generated/analysis/t37/job_report.py <run dir> --modules generated/analysis/t37/retail_jobs.json`.
  - Kind 28: `a` is the FNV-1a of the identifier; the base is `b & 0x3FFFF`.
  - Result: the set of bases per module. If it is {0x4000} for all modules, use `PS3_SPU_WWS_AOT_BASES=4000`; otherwise list the observed bases.

## 9. Required T24 approvals

1. Take `ad8c7f8` (the link-word fix). T24's `af37553` has the same bug.
2. The runtime parts of `bb072a3`:
   - the hook in `spu_indirect_branch` before the code-slot lookup;
   - the `note_get` invalidation;
   - the `spu_context` layout change (full rebuild);
   - the `spu_jobspan.h` and `ps3_ftrace.h` kinds 28 and 29.
3. `t24_proposal_wws_aot_hardening.patch`: the base allowlist, `VERIFY` mode, and logged base refusals (+48 runtime lines, with tests). It applies cleanly to the T24+T54 merge.
4. Agreement on who integrates into `port/` (the CMake patch) and owns the private re-lift.

## 10. Overlap with T51 DMA instrumentation

Source: `Motorstorm01/t36-worktree/generated/analysis/t51/PHYSICS_TRACE_INTEGRATION.md`.

- **The same job sites.** T51's SPU entry and return hooks sit on the job span that kinds 26–29 already use (`spu_jobspan.h` begin/end, PM 0x3214). T51's "B from LS1320, entry B+7DE0" is exactly kind 28's base, and `+0x7DE0` is the T37 module `vehiclephysics` (image 0x4D4A0002, span 0x8240). T51 should take module identity and base from kind 28 rather than adding a second LS read.
- **DMA.** T51's PUT, publication and tag hooks are in `spu_dma.h` (`mfc_submit`, `mfc_do_transfer`, tag completion). The AOT touches only the GET path (`note_get`), and T24 added the PUT commit hook there. There is no functional conflict, but both edit `mfc_do_transfer`. T51 observers should be added after the existing hooks, without reordering them. Lifted jobs issue DMA through the same `wrch` → MFC path, so DMA records are identical under AOT and under the interpreter.
- **Conflict.** T51's per-instruction "arithmetic" hook after `B+0x220C` cannot fire in lifted code. T51 physics traces must run with `PS3_SPU_WWS_AOT` unset, or else with a hook inside the lift (not proposed).

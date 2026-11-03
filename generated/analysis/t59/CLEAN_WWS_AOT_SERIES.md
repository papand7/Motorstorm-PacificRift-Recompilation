# T59: Clean WWS AOT series on agent/t24-spu

**Status: VERIFIED (offline).** There are four linear commits on `agent/t59-wws-aot-clean`, in the private worktree `ps3recomp-t59`, based directly on `agent/t24-spu` @ `af375538e9b4738bb40919380d1ca5d87a8190b3`.

`agent/t24-spu`, the shared worktrees and `port/` are unchanged. Nothing was built or launched, and nothing was merged or pushed.

## 1. Commits

| # | Hash | Subject | Source |
|---|---|---|---|
| 1 | `fca46a8727c128231cd2f162a1f8bbfe95eac319` | SPU microstep: brsl/brasl/bisl/bisled links as the ISA writes them | T37 `ad8c7f8` (cherry-pick -x, unchanged) |
| 2 | `0974281b2a0a9a9f37fdb0429bd5ce83b93669d5` | SPU job spans: PS3_FTRACE_SPUJOB per-job ftrace records (kinds 26/27) | T33 `0568549`, SPU parts only |
| 3 | `6b0d3dce1cd35305e11bd07f8d29b885f6ba8952` | WWS relocatable job AOT: dispatch-time rebase, lifter --reloc, opt-in hardening | T37 `bb072a3` + the `b036875` constructor gate + the T54 hardening with T58 R1/R2 |
| 4 | `121686d5103fa8101c4deb5977c3a56bbe677354` | WWS AOT tests: selection, fail-closed fallback states, hardening switches | T54 `b036875` tests + proposal tests + new R1/R2 tests |

## 2. Dependency graph

```
af37553 (agent/t24-spu)
  └─ fca46a8  [1] link fix ............ independent; can land alone
       └─ 0974281  [2] job spans ...... needs only af37553's ps3_ftrace.h
            └─ 6b0d3dc  [3] AOT ........ needs [2] (spu_jobspan.h, t_spujob, kinds 26/27); its equivalence tests need [1]
                 └─ 121686d  [4] tests . needs [3]
```

- `git rev-list af37553..121686d` returns exactly these 4 commits, each with one parent (no merges).
- The 10 T25/T17 commits are not in the series: `9069985`, `d6d4576`, `3b38721`, `991337d`, `3e4696d`, `1595ee4`, `3d19969`, `fab7b2c`, `aec8c95` and `eea8f42`.

**What changed during the rebase:**
- **`ps3_ftrace.h`.** It gains only `PS3_FT_SPU_JOB` 26, `_STEPS` 27, `_MOD` 28 and `_AOT` 29, the `spujob`/`spujob_cb` fields with their parse, and `ps3_ft_spujob_ret`/`_cb`.
  - Numbers 15–25 (the perf line's D3D12/SPURS kinds) are left unused. The numbering is kept so that traces and `ftrace_report.py` agree on both branches.
  - Not taken: `sync`, `ureg`, `spurs`, `ps3_ft_usleep_reg`, and the GPU_WAIT comment.
- **Benchmarks.** T33's `tests/bench_spu_helper_ops.c` and `bench_spu_interp_step.{c,py}` are left out (perf only). T37's `tests/bench_spu_reloc_job.py` is kept, because it benchmarks this AOT and imports only `test_spu_reloc_job`.
- **One test message.** `tools/test_spu_jobspan.py` no longer says "after SPURS_PM (25)".

## 3. Changed files (`af37553..121686d`)

| File | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| `runtime/spu/spu_channels.c` | +4/−4 | +29 | +218/−2 | |
| `runtime/spu/spu_drain.c` | | +3 | | |
| `runtime/spu/spu_interp.c` | | +6/−3 (per-thread step total) | | |
| `runtime/spu/spu_jobspan.h` | | new, 63 | +31 | |
| `runtime/spu/spu_context.h` | | | +7 (`link_base`, `reloc_delta`) | |
| `runtime/spu/spu_reloc.h` | | | new, 99 | |
| `include/ps3emu/ps3_ftrace.h` | | +16 | +16/−1 | |
| `tools/spu_lifter.py` | | | +74/−12 (`--reloc`) | |
| `tools/lift_wws_reloc.py` | | | new, 201 | |
| `tools/test_spu_lifter_reloc.py` | | | new, 87 | |
| `tools/test_spu_jobspan.py` | | new, 74 | +1/−1 | |
| `tests/test_spu_jobspan.c` | | new, 116 | +16/−5 | |
| `tests/test_spu_reloc_job.{c,py}` | | | new, 403 + 349 | +221/−5, +134/−1 |
| `tests/bench_spu_reloc_job.py` | | | new, 63 | |

VERIFIED by `git diff --name-only af37553 HEAD`: no file under `libs/`, `runtime/ppu/`, `port/` or any video/D3D12/RSX path. The only file outside `runtime/spu`, `tools` and `tests` is `include/ps3emu/ps3_ftrace.h`, which is header-only and needed for kinds 26–29.

**Hardening in commit 3 (T58 R1/R2):**
- **R1.** `PS3_SPU_WWS_AOT`, `PS3_SPU_WWS_AOT_BASES` and `PS3_SPU_WWS_AOT_VERIFY` are read only in `spu_reloc_read_env()`. That function is called once, by the first `spu_wws_register_pm` (the generated constructor, before any SPU thread starts). SPU threads only read the resulting statics. The lazy `s_off`, `s_verify` and `s_b` reads are gone.
- **R2.** More than 16 bases: the warning "more than 16 bases; ignoring '…' (those bases are interpreted)". Trailing text: the warning "ignoring '…'". No hex base at all: every base is refused, with a warning. All three cases fail closed.
- **Unchanged.** The opt-in non-DMA recheck (VERIFY), `BASE_REFUSED 8`, and dropping a resident slot at a refused base.
- **Content check.** Compared with the T58-reviewed tree (`scratch/t58/prop`), `spu_context.h`, `spu_jobspan.h`, `spu_drain.c`, `spu_interp.c`, `spu_lifter.py`, `lift_wws_reloc.py` and the lifter/jobspan tests are identical. `spu_channels.c` and `spu_reloc.h` differ only in the R1/R2 hunks.

## 4. Offline tests (logs: `logs/`)

| Test | Tree | Result |
|---|---|---|
| T24 `spu_all.sh`, 15 SPU/SPURS tests | commit 1 (`fca46a8`) | VERIFIED: 15/15 rc=0 (`logs/suite_c1/`) |
| T24 `spu_all.sh`, 15 SPU/SPURS tests | HEAD (`121686d`) | VERIFIED: 15/15 rc=0 (`logs/suite_head/`) |
| `tools/test_spu_jobspan.py` | commit 2 / HEAD | 0 failures / 7 PASS, 0 FAIL |
| `tests/test_spu_reloc_job.py` (T37 equivalence) | commit 3 | 0 failures |
| `tools/test_spu_lifter_reloc.py`, `tools/test_spu_jobspan.py` | commit 3 | 0 failures each |
| `tests/test_spu_reloc_job.py` | HEAD | **85 PASS, 0 FAIL, 0 skipped** |
| `tools/test_spu_lifter_reloc.py` | HEAD | 12 PASS, 0 FAIL |
| Negative control: HEAD with commit 1 reverted | `scratch/t59/w_nolink` | 12 FAIL, as expected; every failure is a lifted-vs-interpreted comparison |

The 85 checks at HEAD cover:
- **T37 equivalence.** For two modules at 4 bases (0x4000, 0x8C00, 0x15C00, 0x30000), lifted equals interpreted, byte for byte: guest output, LS, stack and 128 GPRs. Fuzzing: 2×600 trials, 0 mismatches.
- **Relocation and residency.** Relocation is exact, residency and DMA replacement work, and selection works with two modules resident at once.
- **All 18 fallback cases.** Disabled, unknown, mismatch, no slot, misaligned, outside LS, elsewhere, other PM, and the accepted AOT run, each at 0x4000 and 0x8C00. Each is byte-identical to its no-AOT baseline (1,312,876 bytes).
- **Allowlist.** 0x8C00 is refused; with 17 bases the 17th is refused and a warning is printed; the text `zz` refuses everything, with a warning.
- **Non-DMA write.** Stays RESIDENT by default; MISMATCH and interpreted under VERIFY.
- **R1.** A static check that only `spu_reloc_read_env` calls `getenv` for the three switches, plus a run that changes the switches after registration: the job still installs (2) and VERIFY stays off (1).
- **Constructor.** It registers nothing unless `PS3_SPU_WWS_AOT=1`.

**Disabled by default (VERIFIED):**
- No CMake or `port/` change.
- No runtime code calls `wws_reloc_register_all`.
- The generated constructor checks for exactly `1`.
- With nothing registered, `spu_indirect_branch` skips the hook (`s_wws_pm_n == 0`).
- The interpreter's only change is the per-thread step counter from commit 2. The fallback states show that interpreted jobs are byte-identical with and without the AOT code, and T24's suite passes unchanged.

## 5. Public audit (`python ../tools/audit_public.py --staged`, motorstorm `tools/audit_public.py`)

| Index | Exit | Items |
|---|---|---|
| base `af37553` | 1 | 25 |
| commit 1 (`fca46a8`, audited afterwards) | 1 | 25 (identical output to base) |
| commit 2 | 1 | 25 (identical output to base) |
| commit 3 (staged) | 1 | 25 (identical) |
| commit 4 (staged) | 1 | 25 (identical) |

- The exit status is 1 at every point, including the base. The 25 BLOCK items are pre-existing (for example `runtime/spu/tests/out_workload/spu_recomp.c` and `scratch/ppu_conformance.cpp`), and the series adds none.
- **Process deviation:** commit 2 was audited just after it was committed, not before. Its output is identical to the base. Commits 3 and 4 were audited before they were committed.
- Commit 1 is an unchanged cherry-pick of a commit already audited in T37. It was also audited afterwards: output identical to the base.

## 6. T24 handoff (the T24 owner runs these; nothing here does)

```sh
cd /c/Users/Julie/Desktop/motorstorm/ps3recomp-t24-spu        # agent/t24-spu
git log -1 --format=%H                                       # must be af37553...; otherwise rebase the series first
git merge --ff-only agent/t59-wws-aot-clean                  # or: git cherry-pick af37553..121686d
# Re-verify on the result (offline):
TAG=t24 R=$(pwd) sh ../scratch/t59/suite/spu_all.sh          # 15/15
cmd //c "..\\scratch\\t54\\test_in.cmd" "%CD%" tests\\test_spu_reloc_job.py   # 0 failure(s); also tools\\test_spu_lifter_reloc.py, tools\\test_spu_jobspan.py
python ../tools/audit_public.py --staged                     # same 25 pre-existing items
```

- Commit 1 may be taken alone (`git cherry-pick fca46a8`).
- **CMake (T24-owned, separate step):**
  - When: only after the series is on the branch that `PS3RECOMP_DIR` points to.
  - Command: `patch --binary -p1 < generated/analysis/t54/port_cmake_wws_aot.patch` from the motorstorm root (CRLF, sha256 `31cee2d6…99d7`).
  - `MSPR_WWS_AOT` and `PORT_SPU_AVX2` stay OFF.
- Runtime activation stays `PS3_SPU_WWS_AOT=1`, with `PS3_SPU_WWS_AOT_VERIFY=1` and `PS3_SPU_WWS_AOT_BASES=<traced bases>`, as in T58 §9. Each run needs separate authorization.

## 7. Remaining integration risks

- **The perf line merges later.** When the T25/T17 line merges with this branch, `ps3_ftrace.h` will conflict. The resolution is mechanical: keep both enums (15–25 from perf, 26–29 from here), both struct field sets, and both parse blocks.
- **`agent/t24-spu` may move past `af37553`.** Then fast-forward is impossible. Cherry-pick the series; `spu_channels.c` is the likely conflict point.
- **A write into a resident span while a job is running** is not caught, even with VERIFY (HYPOTHESIS: the game doesn't do this). Keep VERIFY=1 until a trace settles it.
- **Game-level SPURS equivalence with AOT on** is unverified (only synthetic jobs were tested). It needs the authorized trace and A/B run from T58 §9.
- **T55 physics hooks** must land as a separate series after commit 3, and physics captures run with AOT off (no kind-29 records).
- **Excluded benchmarks.** The T33 microbenchmarks are not on this branch. Any later perf work that uses them must bring them in separately.

## 8. Private artifacts

- Worktrees: `ps3recomp-t59` (`agent/t59-wws-aot-clean`), plus scratch worktrees `scratch/t59/w_c1` (commit 1) and `scratch/t59/w_nolink` (negative control). Remove them with `git worktree remove` when no longer needed.
- Scripts: `scratch/t59/edit.py`, `c2_*.py`, `c3_*.py`, `c4_*.py`, and `suite/`.
- Excluded T33 benchmark files: `scratch/t59/excluded/`.

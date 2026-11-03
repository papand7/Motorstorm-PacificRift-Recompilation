# T58: T24 SPU runtime integration review of T37/T54 WWS AOT

Reviewer role: T24 SPU runtime owner. Base: `agent/t24-spu` @ `af375538e9b4738bb40919380d1ca5d87a8190b3`, untouched.
Reviewed: `ad8c7f8`, `bb072a3` (T37); `b036875` (T54); `generated/analysis/t54/WWS_AOT_INTEGRATION_READINESS.md`; `t24_proposal_wws_aot_hardening.patch` (sha256 `892af82a…ecc4`); `port_cmake_wws_aot.patch` (sha256 `31cee2d6…99d7`); T55 `RUNTIME_HOOK_PROPOSAL.md` / `PHYSICS_TRACE_IMPLEMENTATION.md`.
Scope: offline unit and synthetic tests only. Nothing was built or launched for MotorStorm, and nothing was merged, pushed or applied to a shared worktree.

## 1. Decisions

| Change | Decision | Condition |
|---|---|---|
| `ad8c7f8` link-register fix | **APPROVED** | Cherry-pick it alone onto `af37553`; it applies cleanly. |
| `bb072a3` runtime parts (`spu_reloc.h`, dispatcher, `link_base`/`reloc_delta`, `note_get` clear, kinds 28/29) | **APPROVED in content, REJECTED as submitted** | Blocker B1: it cannot land on `af37553` without 10 unrelated commits. T37 must resubmit a rebased series. |
| `bb072a3` tools (`spu_lifter.py --reloc`, `lift_wws_reloc.py`) and tests | **APPROVED** | Lands in the same rebased series. |
| `b036875` fallback tests and opt-in constructor | **APPROVED** | Lands in the same series. |
| T54 hardening proposal (`PS3_SPU_WWS_AOT_BASES`, `PS3_SPU_WWS_AOT_VERIFY`, `BASE_REFUSED 8`) | **APPROVED with two changes** | R1 and R2 in §4. Regenerate it against the rebased series; its hunk offsets refer to the T54 tree. |
| `port_cmake_wws_aot.patch` (`MSPR_WWS_AOT`, OFF) | **APPROVED; ownership assigned to the T24 runtime owner** | Apply only after the runtime series is on the branch that `PS3RECOMP_DIR` points to. |
| T51/T55 physics hooks | **Separation APPROVED; hook code not yet submitted** | See §6. |

## 2. Blocking defects

- **B1 (BLOCKING, VERIFIED): dependency chain.**
  - Merging `b036875` into `af37553` brings in 14 commits: T33 `0568549`, `ad8c7f8`, `bb072a3`, `b036875`, and 10 unrelated T25/T17 commits. Those 10 cover D3D12, texture snapshots, PPU inline-load logging and SPURS ftrace: `9069985`, `d6d4576`, `3b38721`, `991337d`, `3e4696d`, `1595ee4`, `3d19969`, `fab7b2c`, `aec8c95` and `eea8f42`.
  - A minimal cherry-pick fails. `0568549` conflicts in `include/ps3emu/ps3_ftrace.h`, and the ftrace.h chain (`9069985 → d6d4576 → 3b38721 → 991337d`) itself conflicts in `rsx_d3d12_backend.c`/`tex_snapshot.h`.
  - Fix (T37 owner): rebase onto `af37553` as four commits:
    1. `ad8c7f8`;
    2. the T33 jobspan, plus only the `ps3_ftrace.h` hunks for kinds 26–29 and `spujob`/`spujob_cb`;
    3. the reloc runtime, lifter and tools;
    4. the T54 tests.
  - The renderer/PPU commits need their own owners' approval and must not ride along.
- **None found in the dispatch logic itself.** The residual risks are listed in §4.

## 3. Evidence (all offline; logs in `generated/analysis/t58/logs/`)

| Tree (private scratch worktree) | Contents | Result |
|---|---|---|
| `cp` | `af37553` + `ad8c7f8` only | T24 `spu_all.sh`: **15/15 pass** (VERIFIED) |
| `merged` (`c51f009`) | `af37553` merged with `b036875` | `test_spu_reloc_job.py` 70 PASS / 0 FAIL; `test_spu_lifter_reloc.py` 12/0; `test_spu_jobspan.py` 7/0; T24 suite: see §3a |
| `prop` | `merged` + T54 proposal (regenerated with `patch_prop.py`; identical to the T54 patch except hunk offsets) | reloc 78/0, lifter 12/0, jobspan 7/0; T24 suite: see §3a |
| `nolink` | `merged` with `ad8c7f8` reverted | reloc **10 FAIL** ("lifted == interpreted, byte for byte" at every base), as expected |

- **Link fix (objective 1): VERIFIED.**
  - `spu_link()` exists in T24's `spu_helpers.h:195`, and `af37553` still has `spu_splat_u32(pc + 4)` at `spu_channels.c:2330` and `:2358`.
  - With the fix, T24's own suite is unchanged (15/15). Without it, interpreted jobs differ from lifted ones (the negative control above).
- **Fallback (objective 2): VERIFIED on synthetic jobs.** 18 fallback states, at bases 0x4000 and 0x8C00, are byte-identical to the matching no-AOT baseline. Each comparison covers 1,312,876 bytes: guest memory, LS, 128 GPRs, channels, MFC, stall mask and drain/IRQ PCs. The cases are:
  - disabled, unknown identifier, body mismatch, no slot;
  - misaligned, outside-LS and wrong-entry base;
  - other PM;
  - the accepted AOT run itself.
  - The proposal adds the refused base (state equals noreg) and the non-DMA case.
- **Identity check, as reviewed (`spu_channels.c:2206` on the merge):**
  1. PM image id and `r0 == 0x3214`, with `pc != r0`.
  2. The code-base word at LS 0x1320 is 16-aligned and inside LS.
  3. `pc == base + hdr[0x10]`.
  4. The 16 identifier bytes match.
  5. `entry_off`, `entry16` and the span fit.
  6. The full-span 64-bit hash matches on first use, or after any overlapping GET.
  - `entry16` is the same in all 31 retail modules. Identity rests on (4) and (6).
- **Slot hygiene: VERIFIED by reading.** Only two sites write `resident_code` (`note_get` install and `spu_wws_job_enter`). Both set `link_base`, and contexts are `calloc`/`memset`. `SPU_CHAIN_IND_OK` excludes `policy_mode` and any resident slot, so lifted chaining cannot bypass job entry.

### 3a. T24 suite on `merged` and `prop`

VERIFIED: **15/15 pass on both** (rc=0), the same as on `cp`. Coverage: PUTLLC/PPU CAS 13, GETLLAR backoff 26, park/wake race, stop 0x110, SPURS scheduler, EF DMA wake, queue size, lock-line peer 51, MFC slots 558, MFC shared lookup 634, taskset wake 9, signalled 2, taskset bits 6, coherency 195, LFQueue recipient. Logs: `scratch/t58/suite/logs/{cp,merged,prop}/`.

## 4. Non-DMA overwrite gap (objective 3)

- **VERIFIED limitation.** A resident slot is dropped only by an overlapping DMA GET (`note_get`, `spu_channels.c:2063`). An SPU store, GETLLAR, or a PPU/HLE write into a resident span leaves it RESIDENT, so stale lifted code would run. The `nondma` test shows this: the default stays RESIDENT (result 1).
- **Proposal: VERIFIED.** With `PS3_SPU_WWS_AOT_VERIFY=1`, the span is re-hashed at every resident entry, and the same write gives MISMATCH (4) and runs in the interpreter. With `PS3_SPU_WWS_AOT_BASES=4000`, base 0x8C00 is refused and interpreted, and its state equals noreg.
- **Not covered, even with VERIFY:** a write into the span while a job is running. VERIFY checks only at entry. Whether the game does this is a HYPOTHESIS (unlikely: the modules contain no self-modifying store pattern). Only a trace can settle it.
- **Required changes before the proposal lands:**
  - **R1.** Parse `PS3_SPU_WWS_AOT_BASES` and `PS3_SPU_WWS_AOT_VERIFY` once in `spu_wws_register_pm`, which runs in the constructor before any SPU thread starts. The current lazy parse on SPU threads writes `s_b[]` without synchronization, a benign but formal data race.
  - **R2.** Warn when the list is truncated at 16 entries. An unparsable list already refuses all bases (fail-closed; keep that).
- **Policy:** keep VERIFY=1 for every authorized AOT run until a trace shows no non-DMA writes into resident spans. The default stays unprotected, which is acceptable only because AOT is off by default.

## 5. SPURS scheduling and completion (objective 4)

**Integration is safe with AOT off. Safe with AOT on is VERIFIED for synthetic jobs only; for the game it remains a HYPOTHESIS until the A/B in §8.**

- The dispatcher only decides which body executes inside the existing `spu_indirect_branch` (`:2668`, before the slot lookup at `:2832`).
- The PM, the return to 0x3214, `wrch`/MFC/tag/channel paths, workload pick and kick are unchanged. Lifted jobs issue DMA through the same MFC code.
- Every refusal returns to the existing interpreter path with no state written beyond dropping the slot. This is shown byte-identical, including channels and MFC.
- Unregistered (`MSPR_WWS_AOT=OFF`, or `PS3_SPU_WWS_AOT` not equal to `1`): `s_wws_pm_n == 0`, so the hook costs one predicted-false branch, no kind-29 records and no `[spu-reloc]` lines.
- Neither `PS3_SPU_WWS_AOT*` nor `PS3_FTRACE_SPUJOB` is in the `vm_inline_ok` trigger list (`ppu_loader.cpp:1612`), so an A/B run measures the real fast path.

## 6. T51/T55 physics hooks (objective 5)

**Confirmed: they can integrate separately with AOT disabled.**

- **No file overlap with the dispatch logic.** The proposed hooks sit in `spu_dma.h` (`mfc_submit`, `mfc_run_list`, `mfc_do_transfer`, tag channels) and `spu_jobspan.h`, not in `spu_wws_job_enter`. The shared edit point is `mfc_do_transfer`: append observers after the existing `note_get` and PUT hooks, never reorder them, and leave `g_spu_put_hook(EA,size)` untouched.
- **AOT must be off for physics captures.** The B+0x220C original-PC observer cannot fire inside lifted code. Validity criterion: zero kind-29 records and zero `[spu-reloc]` lines in the capture. Kind 28 (module/base) stays available and is the identity source; T51/T55 must not add a second LS 0x1320 read.
- **Order:** T55 asks T37 to extend the jobspan and AOT notes with invocation IDs. Land that as a separate commit after the AOT series. Do not fold it into the reloc commits.
- **Owner approvals still pending (T24):** DMA rc/stall handling, engine/context lifetime, selected-range writer coverage and the completion acquire contract. These cover the hook code itself, which has not been submitted, so there is nothing to approve yet.

## 7. CMake (objectives 6–7)

- **Reviewed:** the patch adds `option(MSPR_WWS_AOT … OFF)` and a configurable `MSPR_WWS_AOT_DIR` (default `generated/spu_raw/wws_reloc`, private).
  - Configure fails if `spu_reloc.h` or `wws_reloc_register.c` is missing.
  - The sources are appended to `SPU_SOURCES` before `set_source_files_properties`, so they get `runtime/spu` includes, `SPU_USE_DISPATCH_MT`, `-O2 -msse4.1`, and AVX2 only through the existing `PORT_SPU_AVX2` (OFF).
  - They link directly into `add_executable`, so the constructor is not dropped by a static library.
  - Dry run from the repository root: `patch --binary --dry-run -p1 < generated/analysis/t54/port_cmake_wws_aot.patch` → `checking file port/CMakeLists.txt`, clean. `port/CMakeLists.txt` is unchanged (sha256 `b27b99b1…ce9a`).
- **Runtime gate:** the generated constructor registers only when `PS3_SPU_WWS_AOT` is exactly `1`. Tested: "generated constructor registers only when PS3_SPU_WWS_AOT=1".
- **Owner: T24 runtime owner.** Apply it in a commit separate from the runtime series, only once `PS3RECOMP_DIR`'s branch carries `spu_reloc.h`. Keep CRLF and apply with `--binary`.

## 8. Integration order

1. T24: cherry-pick `ad8c7f8` onto `agent/t24-spu` (independent, approved).
2. T37: resubmit the rebased series (B1, steps 2–4), then rerun the T24 suite and the three T37/T54 tests on it.
3. T54/T24: regenerate the hardening proposal on that series with R1/R2, and add the `refused`/`nondma`/allowlist tests.
4. T24: apply the CMake patch (OFF).
5. **Separate authorization:** trace run. Lift outputs and binaries stay private under `generated/`/`build/`.
6. **Separate authorization:** AOT A/B.
7. T55 hooks, as a separate series with AOT off. T37's invocation-ID extension comes after step 3.

## 9. Minimum future validation (each run needs explicit authorization)

- **Offline, before any build:** on the rebased tree, the T24 `spu_all.sh` suite (15/15), `tests/test_spu_reloc_job.py` (0 FAIL, including the fallback, allowlist and non-DMA cases), `tools/test_spu_lifter_reloc.py` and `tools/test_spu_jobspan.py`. Also the `nolink` negative control: the fix reverted must fail.
- **Trace run (AOT compiled, not active):**
  - Config: `MSPR_WWS_AOT=ON`, `PORT_SPU_AVX2=OFF`, `PS3_SPU_WWS_AOT` unset, `PS3_FTRACE=<private path>`, `PS3_FTRACE_SPUJOB=3214:1320`. No `vm_inline_ok` trigger may be set (`RSX_RTVIS`, `PPU_*WATCH`, …), and the startup log must show `[vm] inline guest loads on`.
  - Run boot → garage.
  - Pass if: zero kind-29 records, and the kind-28 bases/identifiers match the manifest. Collect the set of bases.
- **AOT run:** the same, plus `PS3_SPU_WWS_AOT=1`, `PS3_SPU_WWS_AOT_VERIFY=1` and `PS3_SPU_WWS_AOT_BASES=<bases from the trace>`.
  - Pass if: kind-29 results are only 1, 2 or 8. Any 4 is investigated before going further.
  - Pass if: the garage is reached with the same screen sequence as the trace run, and the SPU job-completion counts per module agree.
- **A/B:** compare per-run garage windows (not one fixed time window), using job busy time from kind 26 spans. No performance claim is made until then.

## 10. Status

- VERIFIED: link fix compatible; fallback byte-identical (synthetic); proposal works as designed; CMake patch clean and OFF.
- BLOCKED: B1 (rebased series from T37); trace and A/B authorization.
- HYPOTHESIS: no in-job non-DMA code writes in the game; game-level SPURS equivalence with AOT on.

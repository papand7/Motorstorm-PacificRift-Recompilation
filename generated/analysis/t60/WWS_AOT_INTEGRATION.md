# T60: WWS AOT integration into the T24 SPU runtime (private)

Date: 2026-10-26. Nothing was launched, built (game), merged into `agent/t24-spu`, or pushed. Shared `port/CMakeLists.txt` is unchanged (sha256 `b27b99b1…ce9a`); `agent/t24-spu` is still `af37553`, clean.

## 1. Integration

| Item | Value |
|---|---|
| Worktree | `ps3recomp-t60`, branch `agent/t60-wws-aot-int` |
| Method | `git worktree add -b agent/t60-wws-aot-int … af37553`; `git merge --ff-only agent/t59-wws-aot-clean` |
| HEAD | `121686d5103fa8101c4deb5977c3a56bbe677354` (no merge commit) |

Ancestry, VERIFIED (`git log --format='%H %P' af37553..HEAD`), one parent each:

```
af37553 ─ fca46a8 link-register fix
        ─ 0974281 SPU job spans (ftrace kinds 26/27)
        ─ 6b0d3dc WWS AOT dispatch, lifter --reloc, hardening (kinds 28/29)
        ─ 121686d identity / relocation / fallback / hardening tests
```

Scope, VERIFIED: 15 files changed, +2218/−21. They are `include/ps3emu/ps3_ftrace.h`, 6 files in `runtime/spu/`, 4 in `tests/` and 4 in `tools/`. Nothing in D3D12, the renderer, RSX, `runtime/ppu`, `libs/` or `port/`. `spu_dma.h` is untouched.

CMake (port is not under git, so it was patched as a private copy):
- `generated/analysis/t60/port/CMakeLists.txt` (sha256 `279698ce…76be`) = shared `port/CMakeLists.txt` + `generated/analysis/t54/port_cmake_wws_aot.patch` (sha256 `31cee2d6…99d7`), applied with `patch --binary -p1`. The diff is `port_CMakeLists.applied.diff`.
- 19 non-blank lines + 1 blank line inserted after line 202.
- CRLF is preserved, VERIFIED: 343 → 363 lines, all CRLF, 0 bare LF.

## 2. CMake configuration

Default build (unchanged behaviour):
```
cmake -S port -B build/<dir> -DPS3RECOMP_DIR=<ps3recomp-t60>      # MSPR_WWS_AOT=OFF, PORT_SPU_AVX2=OFF
```
AOT-capable build (future, authorized only):
```
python tools/lift_wws_reloc.py --modules generated/analysis/t37/modules \
    --out generated/spu_raw/wws_reloc --pm-image 1297305682 \
    --codebase-word 0x1320 --job-return 0x3214 --ctor        # run in ps3recomp-t60; private output
cmake -S port -B build/<dir> -DPS3RECOMP_DIR=<ps3recomp-t60> \
    -DMSPR_WWS_AOT=ON -DPORT_SPU_AVX2=OFF \
    -DMSPR_WWS_AOT_DIR=<repo>/generated/spu_raw/wws_reloc
```
- Compiled in, the AOT still does nothing at run time unless `PS3_SPU_WWS_AOT=1` (exactly `1`).
- `generated/spu_raw/wws_reloc` does not exist yet, so an ON configure stops with FATAL_ERROR until the lift is run.

Isolated configure check of the inserted block (`logs/cmake/`, a `LANGUAGES NONE` project; not a game configure), VERIFIED:

| Case | Result |
|---|---|
| default | rc 0, `MSPR_WWS_AOT=OFF`, SPU_SOURCES unchanged (1) |
| ON, lift directory missing | rc 1, `Missing …; run tools/lift_wws_reloc.py --ctor` |
| ON, runtime `af37553` (no `spu_reloc.h`) | rc 1, `MSPR_WWS_AOT needs a runtime with spu_reloc.h` |
| ON, `ps3recomp-t60` + 2 stub modules | rc 0, `Wws job AOT: 2 module(s)`, SPU_SOURCES 1 → 4 |

AVX2: `option(PORT_SPU_AVX2 … OFF)` is unchanged; the AOT sources get `-mavx2` only through that option.

## 3. Tests (offline, in `ps3recomp-t60`; logs in `logs/`)

| Test | Result |
|---|---|
| T24 `spu_all.sh`, 15 SPU/SPURS tests | VERIFIED 15/15 rc=0 (`suite_t60.log`, `suite/`) |
| `tests/test_spu_reloc_job.py` | VERIFIED 85 PASS / 0 FAIL, including 18/18 fallback cases |
| `tools/test_spu_lifter_reloc.py` | VERIFIED 12 / 0 |
| `tools/test_spu_jobspan.py` | VERIFIED 7 / 0 |
| `nolink` negative control | Not rerun. HEAD is the same commit as T59's, where it gave 12 FAIL as expected. |

- **Disabled AOT = original interpreter (VERIFIED).**
  - All 18 fallback states are byte-identical to the no-AOT baseline (1,312,876 bytes each).
  - The constructor registers only when `PS3_SPU_WWS_AOT=1`. With nothing registered, the hook is skipped (`s_wws_pm_n == 0`).
  - The only change to `spu_interp.c` is the per-thread step counter `t_spu_interp_steps_total` (3 `+=` at existing returns), which does not change control flow.
  - The T24 suite passes unchanged.
- **Non-DMA overwrite recheck available (VERIFIED).**
  - Default: the job stays RESIDENT (result 1), a documented limitation.
  - `PS3_SPU_WWS_AOT_VERIFY=1`: the span is re-hashed, the job gets MISMATCH (4) and runs in the interpreter.
  - Switches changed after registration are ignored (R1).
  - The 16-base truncation warning and the `zz` fail-closed case pass (R2).

## 4. Audit vs `af37553`

| Target | Exit | Items |
|---|---|---|
| base `af37553` (`--staged`, T59 log) | 1 | 25 |
| `ps3recomp-t60` index @ `121686d` (`--staged`) | 1 | 25, byte-identical to base (`cmp`) |
| `--tree` of the patched `port/CMakeLists.txt` copy | 0 | passed |

The series adds no audit items; the 25 are pre-existing.

## 5. T55 proposal review (not integrated)

`Motorstorm01/t55-worktree/generated/analysis/t55/RUNTIME_HOOK_PROPOSAL.md` (sha256 `1979485c…c3b5`):
- **Compatible.** Its hook sites (`mfc_submit`, `mfc_run_list`, `mfc_do_transfer` and the tag channels) lie in `spu_dma.h`, which this series does not touch. It keeps kinds 26–29, and `PS3_PHYSICS_TRACE` is kept out of the `vm_inline_ok` triggers.
- **Must re-anchor.** It was written against `bb072a3`; it needs re-anchoring on `121686d`.
- **Conflict with this change, deferred.** It asks for an original-PC observer "on both interpreter and existing AOT paths". Lifted Wws jobs cannot fire the B+0x220C observer, so physics captures must run with AOT off. Validity check for such a capture: 0 kind-29 records and 0 `[spu-reloc]` lines.
- **Order.** The invocation-ID extension to jobspan/AOT notes comes as a separate commit after this series. The T24 approvals it lists are still pending, and no hook code has been submitted.

## 6. Remaining runtime risks (HYPOTHESIS until traced)

1. Equivalence is proven only on synthetic jobs. Whether game modules behave the same is untested.
2. A write into a resident span while a job is running is not caught, even with VERIFY.
3. Non-DMA writes into resident spans are undetected unless `PS3_SPU_WWS_AOT_VERIFY=1`.
4. The set of game load addresses is unknown. Modules that form link-base addresses with `ila` rely on the interpreter-identical semantics; at a new base they are correct but untested.
5. The lifter's hand-off sites run in the interpreter; their performance cost is unmeasured.
6. Merging the perf line will conflict in `ps3_ftrace.h` (kinds 15–25), and that conflict needs a manual merge.
7. No performance claim can be made yet.

## 7. Load-address trace configuration (AOT compiled, inactive)

- Build: the AOT-capable configuration from §2.
- Environment:
  ```
  PS3_FTRACE=<private path under generated/>
  PS3_FTRACE_SPUJOB=3214:1320
  PS3_SPU_WWS_AOT          unset
  ```
- None of the `vm_inline_ok` triggers may be set, not even to empty or 0 (`RSX_RTVIS`, `PPU_*WATCH`, …). The startup log must show `[vm] inline guest loads on`.
- Use a private HDD root.
- Run boot → garage.
- Read the kind-28 records. `a` = FNV-1a of the 16 identifier bytes. `b & 0x3FFFF` = code base, and `b >> 18` = size/16.
- Pass if: 0 kind-29 records, 0 `[spu-reloc]` lines, and every kind-28 identifier is in `wws_reloc_manifest.json`. Output: the set of code bases.

## 8. Minimal future A/B (each run needs authorization)

1. **A** = the §7 run.
2. **B** = the same build and inputs, plus:
   ```
   PS3_SPU_WWS_AOT=1
   PS3_SPU_WWS_AOT_VERIFY=1
   PS3_SPU_WWS_AOT_BASES=<bases from A>
   ```
3. Gate B on its kind-29 results: only 1, 2 or 8 are allowed. Stop on any 4 (MISMATCH).
4. Gate on the run as a whole:
   - The same screen sequence to the garage as A.
   - The same number of job completions per module (kind 26 counts per kind-28 identifier).
5. Compare busy time from the kind-26 spans, within per-run garage windows (not a fixed wall-clock window). Use at least 3 runs per arm.
6. Drop VERIFY only after a trace shows no non-DMA writes into resident spans.

## 9. Status

- VERIFIED: ancestry; scope; ff integration; CMake patch applied privately with CRLF and OFF defaults; offline tests; disabled-path identity; VERIFY recheck; audit identical to base.
- BLOCKED (authorization): applying the patch to shared `port/`, merging into `agent/t24-spu`, the lift into `generated/spu_raw/wws_reloc`, the AOT build, the trace run and the A/B.
- T24 handoff:
  1. On `agent/t24-spu`, run `git merge --ff-only agent/t60-wws-aot-int` (= `121686d`).
  2. In `port/`, run `patch --binary -p1 < generated/analysis/t54/port_cmake_wws_aot.patch`. The expected result is sha256 `279698ce…76be`.

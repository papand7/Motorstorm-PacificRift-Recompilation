# T173 regression validation (offline)

**Result: every offline check passed; nothing was run in the game.** Revisions: ps3recomp baseline `fda8c9b`, fix `b6f53f8`. Host: Windows 11, MSVC 18 (cl for the conformance driver), clang-cl 23.1.3 (project build compiler), Python 3.14.

## New regression test: `tools/test_ppu_jump_spill.py`

Part 1 decodes hand-assembled words (round-tripped through `ppu_disasm` first). Part 2 lifts a 29-entry model function with `PPULifter`, compiles it with the project's conformance driver (`cl`), and runs it.

| check | T173 lifter | T170 lifter (same test file) |
|---|---|---|
| spilled base resolves to 29 entries / 23 distinct blocks | ok | **FAIL (no table)** |
| ... also without function entries | ok | **FAIL** |
| direct TOC form with `add rB,x,rB; mtctr rB` | ok | **FAIL** (old lifter missed this form too) |
| refused: second store to the slot; store between loop head and reload; store later in the function; stored value not a TOC load; `ld` reload of a `stw`-stored slot; reload from a slot never stored; no store at all; frame resized between store and reload | ok (8 of 8 left unresolved) | ok (unresolved either way) |
| spilled base whose TOC slot points at no table: dropped, no wrong dispatcher | ok | ok |
| a later store is not visible without function entries (documented limit) | ok | FAIL (nothing resolves) |
| lifted `bctr` is a computed `switch`, one arm per distinct target, `default:` keeps `ps3_indirect_call` | ok | not reached (the test stops when nothing resolves) |
| **executed**: all 29 selectors give the right block result (`r3`), `ctr`, `r9 = selector*4`, no indirect call | ok | not reached |
| **executed**: LR keeps the `mtlr r6` value (LR as scratch) for every selector | ok | not reached |
| **executed**: invalid selectors 29, 30, 63, 127, 128, 200, 255 take the bounds exit, no dispatch, `ctr` untouched | ok | not reached |
| **executed**: a corrupted table entry (target not a case label) reaches `ps3_indirect_call` once with `ctr` equal to the computed target, no case runs | ok | not reached |

The model uses a generic synthetic layout (its own addresses, selector map and numbers), keeping game data out of the public repo. It has the real function's prologue `stdu`, and models its out-of-range selector as an exit instead of the original's spin (faithful spin is in the root-cause risks).

## Existing lifter and PPU tool tests, T170 tree vs T173 tree

`tools/run_lifter_tests_t173.py` ran all 21 existing `test_ppu*.py` and `test_lifter*.py` files in both trees (the new test is the 22nd, absent from the T170 tree). **All 21 exit 0 in both**, including `test_ppu_jumptables.py` (all vectors), `test_ppu_lift.py` (the conformance driver, compiled with cl and run), `test_ppu_branches.py`, `test_ppu_lifter_chunks.py`, `test_ppu_cs_*`, `test_ppu_fallthrough.py`, `test_ppu_trace.py`. No test skipped for a missing compiler. Full output: `generated/t173/lifter_tests.json` (private).

Not run: `lift_selftest.py` (needs the PPU gcc, absent here), the ps3recomp CMake/ctest suite and the SPU lifter tests (the fix touches only `discover_jump_tables`), and any game launch.

## Whole-binary relift (the generated-code comparison)

Command as `docs/BUILD.md`, `--jobs 6 --trace-hooks`, into private scratch trees, deleted after comparing.

| comparison | result |
|---|---|
| T170-lifter relift vs `generated/ppu-hooked-staging` | 56 files identical; 22 differ from lifter drift (raw-store coherence macros, `VM_RAW_ST`, header). **Chunks 006 and 026 identical.** |
| T170-lifter relift vs T173-lifter relift | **77 files identical, 2 differ (006, 026)**; dispatchers 790 -> 791, case targets 6,456 -> 6,479 |
| each differing file | 1 line replaced, 22 label lines added, 0 other changes (`git diff --numstat`: 23 added, 1 removed) |
| T173 relift repeated with the audit switch on | all 79 files byte-identical, so the output is deterministic and the audit switch changes nothing |
| T173 relift repeated after a small refactor | chunks 006 and 026 SHA-256 equal to the verified ones |
| lifted switch vs table decoded from the ELF (`verify_arms_t173.py`) | 23 arms = 23 targets; one label per arm in both functions; default and `mtctr` unchanged |
| unresolved `bctr` after the fix | 386, all function-descriptor tail calls (root cause, section 6) |

## Compile checks of the changed chunks

With the build's compiler and flags (`tu_check_t173.cmd`, as `build.ninja`: clang-cl `/O2 /Ob2 -std:c++20 -fno-strict-aliasing -fwrapv /bigobj`, the build's include set, the old staging's header):

| chunk | `/Zs` | `-c` to an object |
|---|---|---|
| `ppu_recomp_026.cpp` | rc 0 | rc 0, 21.7 MB, 105 s |
| `ppu_recomp_006.cpp` | rc 0 | rc 0, 4.2 MB, 19 s |

A computed `goto` into labels past local variables would have been a hard C++ error; there was none. The objects were deleted. **The full executable was not built.**

## Audit

`audit_public.py --staged`, run in `ps3recomp-t173` with `b6f53f8` staged: 25 BLOCK items, all in committed ps3recomp fixtures (`runtime/spu/tests/out_*/spu_recomp.*`, `scratch/ppu_conformance.cpp`, and similar). The same 25 appear when run in `ps3recomp-t170`, so they pre-date T173. **Neither changed file is flagged**; the test has no game data (synthetic addresses and values). The report branch is a separate repository, audited by its own commit hook.

## Not covered

- The lifted code in the executable: only the two changed chunks were compiled; link and run were not.
- Any other game or title lifted with this lifter.
- Behaviour of the 22 never-executed case blocks.

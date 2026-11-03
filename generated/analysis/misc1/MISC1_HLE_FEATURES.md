# misc1: small HLE gaps on the game's own import list

Worktree `ps3recomp-misc1`, branch `agent/misc-hle-features`, base T108 `6b1a7e4`. Nothing built, launched, merged or pushed.

Source of the gaps: `t30/loader/hle/imports_classified.tsv` (386 imports) and the T98 run log
(`runs/20261027-111836-t98-visible-race/stderr.log`; its only `[hle] unresolved NID` is `0x7A0A83C4`).

| commit | import(s) | before | now | label |
|---|---|---|---|---|
| `b6467d1` | `cellFontInitLibraryFreeTypeWithRevision` 0x7A0A83C4, `cellFontEndLibrary` 0x40D40544 | unresolved: CELL_OK, `*lib` = stack garbage (caller `0x584284` stores it at `[base+0x400A8]`, passes it to every `cellFontOpenFontFile`) | zeroed guest block written to `*lib`; EndLibrary checks it | VERIFIED offline; runtime effect on menu text HYPOTHESIS (OpenFontFile ignores the handle) |
| `c9abc88` | `cellSaveDataListAutoSave` 0x4DD03A4E | unresolved: CELL_OK, no callback, nothing written | `savedata_fixed(1, …)` + nine-arg ctx handler, registered by `gen_hle_nids.py` | VERIFIED offline; not yet reached at runtime (no run has got past the race) |
| `b3f9812` | `cellFsUnlink` 0x7F4677A8, `cellFsRmdir` 0x2796FDF3 | CELL_OK stubs | real delete + cellFs errors under `PS3_HDD0_ROOT`/`PS3_HDD1_ROOT` only; disc/firmware/unrooted/`..` paths unchanged (CELL_OK, nothing removed) | VERIFIED offline |

## Review round 1: deletion containment (`7b6f9f0`)

- **Problem:** the `b3f9812` guard checked guest text only. VERIFIED by running the new test against `b3f9812`: it fails 12 checks, and that run did delete an external sentinel through a junction inside the hdd1 root. It also removed root aliases (`/dev_hdd1`, `/dev_hdd1/`, `/dev_hdd1/cache/..`).
- **Fix:** `7b6f9f0`.
  - Guest strings must fit their buffer and host paths must not be cut, otherwise ENAMETOOLONG.
  - The parent is resolved on the host (`realpath` / `GetFinalPathNameByHandleA`) and must be the resolved root or inside it.
  - The final name may not be empty, `.` or `..`, and may not itself be a link.
  - The delete uses the resolved path; a refused delete returns EACCES.
  - `fs_hdd_root()` is now shared by translation and validation.
- **Tests:** `test_ppu_fs_delete.py` passes 35/35, with `CXX` set to the bundled clang++.
  - The file-symlink case SKIPs because this account lacks the symlink privilege; the junction cases cover the escape.
  - `test_ppu_fs_imports.py` still passes.
- **Build and audit:** `ppu_fs.cpp` compiles with the exact T96I flags (rc=0) with the same warning kinds as T108. The staged audit shows the same 25 pre-existing items, none in these files.
- **Residual risk (HYPOTHESIS: low):** a host process could swap a directory for a link between the check and the delete. The guest has no call that creates links.
- **On Windows:** narrow-path APIs fail beyond MAX_PATH, so the truncation cases were already partly blocked there. The old code still failed them with ENOENT instead of a clean refusal.

## Review round 2: Windows dot/space final names (`5b30c3a`)

- **Problem:** VERIFIED. Only the parent was resolved, and Win32 trims trailing dots and spaces from the final name. Against `7b6f9f0`, `rmdir "/dev_hdd1/. "` returned OK and removed the empty configured root, and `rmdir "/dev_hdd1/e/.. "` removed `e`. 16 checks fail in the new `dots` run.
- **Fix:** two layers, each tested alone.
  - On Windows, a final name ending in `.` or space, or containing `:` (stream syntax), is refused with EACCES.
  - On all hosts, an existing target is resolved in full and must be strictly below the resolved root and equal to the named path (`parent/name`, case-insensitive on Windows); otherwise EACCES. The link rejection is unchanged.
  - With the name check compiled out (temp copy), the second layer alone still passes all checks. With only the strict-descendant part, `e/...` still removed `e` inside the root, which is why the equality is required.
- **Tests:** `test_ppu_fs_delete.py` now also runs `test_fs_delete dots` in a fresh process (the roots are read once per process). It uses an empty root, an external `sentinel.bin` and an empty external directory.
  - Cases: `. `, `.. `, `...`, `....`, `. .`, `..  `, the same with a trailing `/`, `oempty/..`, `x/../...`, plus `e/.. `, `e/...`, `e/. ` below the root. Ordinary unlink and rmdir still work.
  - Results: main 33 PASS, 1 SKIP (file symlink); dots 17 PASS. `test_ppu_fs_imports.py` passes. No temp directories are left behind.
- **Build and audit:** the three TUs compile with the T96I flags (rc=0), and `ppu_fs.cpp` has the same warning kinds as the base. The staged audit (`logs/audit_r2.log`) shows the same 25 pre-existing items as round 1, none in these files.
- **Limit:** names ending in `.` or space can't be deleted on Windows. The guest can't create them there either, because the host trims them on create.

Checks (clang 23.1.3 from `build/llvm`, `CXX`/`CC` set to it):
- `test_font_init_library.c`, the 4 other font C tests, `test_font_hle_nids.py`: pass.
- `test_savedata_list_autosave.c`: pass. `test_savedata_list_nids.py`: 8/8, and 3 fail on T108.
- `test_ppu_fs_delete.py`: 16/16, and 7 fail when built against T108's `ppu_fs.cpp`.
- No regressions: `test_ppu_fs_imports.py`, `test_savedata_user_autosave.py`, `test_hle_registration_dependencies.py`, `test_hle_float_args.py`.
- The generated NID table differs from T108's only by the new registrations (`gen/`).
- `cellFont.c`, `cellSaveData.c` and `ppu_fs.cpp` compile with the exact T96I flags (`tools/make_tu.py`, `tu_new.cmd`/`tu_base.cmd`, rc=0). No new warning kinds (`logs/tu_*`).
- `audit_public.py --staged`: the same 25 pre-existing items as T108, none in these files.
- `libs/system/tests/test_savedata_fixed.c` / `test_savedata_io.c` are POSIX-only (`mkdtemp`) and don't build with clang-msvc. This predates misc1.

Not done (larger, or risky): `cellSaveDataDelete2` (UI-driven), `sys_lwcond_signal` (OK stub, polling wait; a concurrency change), `cellFsMkdir` returning EEXIST (boot-path behaviour), sceNp/cellSearch (offline).

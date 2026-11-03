# T148 — historical feature recovery and miscellaneous integration

Worktree `ps3recomp-t148-misc-integration`, branch `integration/t148-misc-features`, base T146 `80fe5de`.
No game launch and no live networking. "Runtime-unverified" means the feature is in the built exe but
no game run has tested it. Per-feature classification: `FEATURE_COVERAGE_MATRIX.md`.

## 1. Branch inventory

- 115 worktrees and 128 branches scanned. 69 branches have commits whose patch-id is missing from
  the base (`logs/branches_missing.txt`). Content presence was checked per commit with
  `git apply --check` (reverse succeeds = present, forward succeeds = missing, neither = conflict).
- Commits that were on no branch (in detached worktrees) are now on non-destructive refs:

  | Branch | Commit |
  |---|---|
  | `recover/t24-ppu` | `3e9bb93` |
  | `recover/t109-onto-t108` | `90951b9` |
  | `recover/t58-cp` | `7d69e45` |
  | `recover/t58-merged` | `c51f009` |
  | `recover/t58-nolink` | `1e21eb4` |
  | `recover/t59-w-nolink` | `e6c90a9` |

- Commits still on no branch, but reachable through a tag or the stash:
  - `e9f6a6e` (Twisted Metal)
  - `f0a8216` (GT5P)
  - `e8c795f` and `bf5f54b` (SPURS)
- Most of the 69 branches are other titles (Twisted Metal, GT5P, inFAMOUS), copies of commits that
  are already present, or T146/T147 scope (SPU, SPURS, renderer).

## 2. Integrated commits (VERIFIED by build and tests)

| T148 commit | Feature | Source |
|---|---|---|
| `b21c73c` | cellFont InitLibraryFreeTypeWithRevision / EndLibrary | misc-hle `b6467d1` |
| `f86ec3b` | cellSaveDataListAutoSave | misc-hle `c9abc88` |
| `232c1dd` `b7dad18` `fe28979` | cellFsUnlink / Rmdir really delete, only under writable roots, contained by the resolved host path, Windows dot/space names refused | misc-hle `b3f9812` `7b6f9f0` `5b30c3a` |
| `084bba9` | real `sys_lwcond` waiter queue | T24 `2a8522b` |
| `e69bafe` | lwcond queue is opt-in, `PS3_LWCOND_QUEUE=1` (new) | — |
| `3eccd28` | savedata: a NULL buffer with zero size is an empty file operation | T24 `316747e` |
| `a86a08a` `3be1431` `36a39df` `e6fcc15` `e22ec5a` `2b32fa6` | sceNp RequestTicket2/GetTicket with deferred GOT_TICKET; offline RPCN foundation, local Schannel transport with mock server, interoperability preparation | networking-audit `3a926a5` `f578741` `fd1b52c` `a4945a9` `539450d` `13a4e02` |
| `eb82b5b` `17c004c` `08bb9df` | RSXI replay inventory, lossless blobs, capture contract | t32/t53 `3316d53` `dc1780f` `a311ab9` |
| `850708a` `c41741f` `fe9e1bd` `cfbfbb9` `54d8df2` | `tools/msre` RE workbench | `954d19d` `0d1e152` `a840dce` `65ea4b0` `f9f33d1` |
| `2a5ab0a` `50e8af8` | upstream source compare; PRX import boundary test | t27 `92cdae7` `65b20e8` |
| `dfa311a` `695aaeb` | PS3 API coverage audit, plus a path fix for nested worktrees (new) | ps3-api-audit `6bae99b` |
| `f9bac03` | SPU pipeline keeps the mtimes of byte-identical regenerated files | t24-build `2778d7e` |
| `373040c` | msmods offline graphics mod framework | T111 `d2a65f9` |

All new HLE entry points are imported by the game (NIDs resolved against
`generated/analysis/EBOOT.imports.json`). No stubs were removed.

## 3. Superseded or already present

- **Superseded:**
  - T24 precise usleep, by T121 `PS3_USLEEP_SPIN=2`.
  - t25 `PS3_FTRACE_SPURS`, by T134 `PS3_FT_SPURS_PICK`/`PM`.
- **Already present in the base:**
  - garage-input-audit cellPad work (packet lengths, sensor refusal, analog triggers);
  - T118 audio;
  - `PS3_FTRACE_SPUJOB` and `PS3_FTRACE_ARM`;
  - the boot and frontend progression fixes.

## 4. Conflicts and decisions

- The NP and RPCN cherry-picks applied cleanly (3-way).
- sys_lwcond: T24 made the queue the default. Rules forbid unverified default changes, so `e69bafe`
  keeps the old poll model as the default and puts the queue behind `PS3_LWCOND_QUEUE=1`. A test pin
  checks this.
- `test_ps3_api_audit` assumed the old sibling layout. `695aaeb` resolves the game root through
  `MSPR_GAME_ROOT`, then the parent tree.
- `1a415e6` (cmake: suppress warnings on SPU sources) conflicts with the current
  `cmake/PS3RecompSPU.cmake`. It has low value and was not ported.

## 5. Tests

- **Focused tests, all PASS:**
  - ppu_fs_delete, savedata_list_nids, savedata_empty_write, font_hle_nids;
  - lwcond_wait (including the opt-in pin), lwcond_layout;
  - np_ticket, np_rpcn;
  - rsxi ×3, msre ×4;
  - upstream_source_compare, ppu_import_boundaries, ps3_api_audit;
  - spu_program_pipeline (1 skip);
  - msmods 57/57 (`tools/test_msmods.cmd` builds the native shader_tool).
- **Full suite** (`logs/suite_t148.txt`): PASS 144, SKIP 43, FAIL 5. T146 was PASS 126, SKIP 43,
  FAIL 8.
  - `test_rpcn_check`, `test_rpcn_transport`: **BLOCKED**. The Python `cryptography` package is
    missing; it was not installed.
  - `test_rt_pool_srv_layout`, `test_vpc_watch`: they also fail on T146. T148 does not touch
    `libs/video`.
  - `test_d3d12_shader_cache`: failed once in the parallel suite. Run alone it passed 3 out of 3
    times (`logs/shader_cache_rerun{1,2,3}.txt`), and it passes on T146. T148 has no `libs/video`
    diff, so this is a load-sensitive WARP test (PARTIAL), not a regression.
  - Six of T146's failures pass here (fp_span, present_progress, c_fp_span, c_t133_image_quality,
    cpath_trace, spurs_event_sched). They are timing- or load-dependent.
- The suite rewrites `scratch/ppu_conformance*` with local paths. These files are left uncommitted.

## 6. Build

- `generated/analysis/t148/tools/build_t148.cmd` builds `build/motorstorm-t148/MotorStormPacificRiftRecomp.exe`
  from `2b32fa6`. Every later commit only changes tools, docs or tests.
- rc=0, 279 steps, 383.9 MB, SHA-256 `8f9a8c29989e6db967ae84aeae37fa1a3c71d548d7dfe939c9b7e255a590a87b`.
- The exe contains `PS3_LWCOND_QUEUE`, `sceNpManagerRequestTicket2`, `cellSaveDataListAutoSave`,
  `cellFontEndLibrary` and `cellFontInitLibraryFreeTypeWithRevision`. Not launched.

## 7. Missing or blocked

- **Not implemented:**
  - sceNp Matching2 / lobby (the game imports `sceNpMatching2Init2` and 25 sceNp2 functions);
  - the early-boot workaround review (proving a removal safe needs game runs).
- **BLOCKED:**
  - RPCN mock tests: they need `cryptography`.
  - Live RPCN interoperability: needs authorisation, which is suspended.
  - WWS AOT exe variant: needs `port-t106aot` (T146).
- **Runtime-unverified:** every integrated HLE change (savedata, fs, font, NP ticket, lwcond opt-in).

## 8. Handoffs

**T146** (performance, SPU/SPURS; their worktree was not modified):

| Commit(s) | Content |
|---|---|
| `73d6041` | HLE dispatch cache |
| `9da3454` | PPU_THREAD_LOCAL constinit; needs a re-lift |
| `e92508f` | lifter switch base; needs a re-lift and PPU conformance |
| `23ae052` `69ed8fe` `f04abfb` `24e67f0` `75f2b18` `3493cb6` `11c76d8` | t28 SPU/SPURS correctness; two conflict |
| `bf5f54b` `e8c795f` | SPURS ShutdownJobChain, job index in data2; stash/tag only |
| `7ce5c57` | SPU_JOBCAP |
| `9069985` `eea8f42` `aec8c95` `fab7b2c` `d6d4576` `3d19969` `3b38721` `1595ee4` `3e4696d` | renderer/PPU perf; conflicts with newer code |
| `b00e999` | T144 `PS3_SPURS_LANE_HANDOFF`; opt-in, net synthetic regression |

**T147** (rendering, at `d76e08e`):

| Commit(s) | Content |
|---|---|
| `8f7ac89` | VPC trace |
| `d4c0f78` `0cb58e9` `b76b9c7` | D3D12 vtable-path visuals; the base already has later depth/stencil/sampler work |

## 9. Prioritised next steps

1. An authorised bounded boot-to-race run of the T148 exe with defaults, to check that the savedata,
   fs and font changes don't regress startup or saving.
2. A run with `PS3_LWCOND_QUEUE=1`, with frame-phase comparison (`t134/tools/phases_all.py`), before
   any default change.
3. Install `cryptography` in a dev venv to unblock the RPCN mock tests (offline).
4. T146 to triage the t28 SPU/SPURS correctness commits and `73d6041`.
5. Matching2 offline stubs that report "no network", if the game's online menu needs them.
6. Merge order: T146 → T148 (independent files, no overlap seen) → T147.

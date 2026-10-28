# ps3recomp upstream integration

## v0.15.0 -> v0.17.0 (2026-10-22)

| | |
|---|---|
| Previous base | `0fe7dbf5` (v0.15.0) plus uncommitted local changes |
| Local baseline | branch `motorstorm/v0.15-local`, commit `f373398`, tag `ms-baseline-v0.15-local` |
| Upstream | v0.17.0 = `a6d76c8` = `master` on 2026-10-22 (newest tag and branch head) |
| Integration branch | `motorstorm/v0.17-integration`, worktree `ps3recomp-int/` |
| Rollback | `git -C ps3recomp switch motorstorm/v0.15-local`, or check out the baseline tag; `generated/upstream/local-v0.15-baseline.diff` and `local-v0.15-untracked.tar` hold the pre-commit tree |

`ps3recomp/` itself is untouched (another workflow builds `build/motorstorm` from it).
The integrated runtime builds into `build/motorstorm-int` (`generated/upstream/build_int.cmd`).
`scratch/ppu_conformance.cpp` stays uncommitted in the baseline: the public audit blocks it.

### Commits

| Commit | Content |
|---|---|
| `f373398` | Local fork on v0.15.0 (SPURS/LFQueue, FIOS, Bink, cellFont, D3D12 texture-source order, PPU trace, RSX inspector, startup runner, usleep timer) |
| `02646b7` | Merge of v0.17.0; 8 conflicting files resolved by hand |
| `b15310d` | Local regression fixtures follow v0.17.0 |
| `b5e2831` | SSSE3 SPU byte rotates/shifts and generate-controls; one LS diagnostic gate |
| `ab989d3` | SSE4.1 `shufb` in host byte order (~10% throughput in `shufb_tp.c`; three mutants caught) |

### HLE NID table

The lift's `ppu_hle_nids.cpp` is byte-identical to v0.15.0's `gen_hle_nids.py --all` output. Against v0.17.0 it fails to link: #400 replaced the invented cellFiber API with the SDK's (`cellFiberPpuWakeup` and 10 others removed, 12 added), and v0.17.0 adds `cellSpursQueueSize`, `cellVdec*Ex` and avconf entries. The port option `PORT_HLE_NIDS_GENERATE=ON` (default OFF) regenerates the table from `PS3RECOMP_DIR`; the integration build uses it. The decrypted EBOOT contains no `cellFiber` module string and none of the removed NIDs (VERIFIED by byte search), so the change does not alter MotorStorm imports.

### Conflicts

| File | Resolution |
|---|---|
| `runtime/spu/spu_channels.c` | Both: local `SPU_STALL_MS` reporter and upstream `SPU_PCSAMPLE` |
| `runtime/spu/spu_workload.c` | Local timestamped trace caps; the `WAIT_SIGNAL` counter made unsigned as upstream |
| `runtime/ppu/ppu_loader.cpp` | Both includes (`ppu_trace.h`, `ps3_ftrace.h`) |
| `runtime/ppu/ppu_sysprx.cpp` | Both: local f1 HLE adapters (cellFont, `cellMsgDialogClose`, `cellVoiceSetVolume`) and upstream `avconf_register_ctx` |
| `libs/spurs/cellSpurs.c` | Local `spurs-ef-watch`; upstream `PS3_LOG_FIRST` cap |
| `libs/video/rsx_d3d12_backend.c` | Upstream FP export-bit code (the same fix as ours, plus `RSX_FP_CTRL_AUTO`); local `RSX_PSO_WATCH_FP` |
| `libs/video/rsx_texture_layout.c` | Local `0x9F` -> G8B8 lanes kept; upstream X16 (`0x94`) -> B8 adopted |
| `libs/video/tests/test_texture_layout.c` | Both test sets |

### Classification of relevant upstream changes (80 merges)

Already present: the D3D12 FP export-control fix (#396's D3D12 side matched our local change); #291 SPURS scheduler test (in v0.15.0).

Integrated (merged, active in the D3D12/Windows build):

- SPU: #369 AVX2 single-precision fast path (active only with `-DPORT_SPU_AVX2=ON`, see below), #370 SSE2 float compares, #383 DMA identical-transfer halt uses wall time, #340 / #388 atomic SPURS signalled bit and taskset bitsets, #411 `cellSpursQueueSize`, #366 job frame placement.
- RSX/GCM: #361 vertex-program cache keyed on the program, #392 FP pipeline cache keyed on the code hash, #332 Y16_X16/HILO8 crossbar, #384 X16 presentation, #408 31-bit texture offsets, #390 wrapped ring cannot overwrite unread commands, #343 queued flip waits for its label, #354 late flip completion, #401 / #410 GCM get/IO mapping, #347 / #358 / #334 NV3089 fixes, #393 depth/stencil-only clears, #391 strip parity, #389 initguid.
- PPU/runtime: #353 GCM callbacks at `sys_timer_usleep`/`sleep` (in the syscall dispatcher, independent of our high-resolution wait), #409 thread slots, #296 allocation domains, #349 `CELL_FS_O_*` values, #376 AIO reads, #350 `/dev_hdd1`, #326 spinlock width.
- Diagnostics: #339 `PS3_FTRACE`, #397 `PS3_HLE_TOP`, #394 `SPU_INTERP_STATS`, #398 `FP_DUMP`, #399 log caps.

Adapted: #332 does not cover `0x9F` (Y16_X16_FLOAT); the local G8B8 lane mapping for it stays. Whether `0x9F` also needs the 16-bit-block crossbar is unverified (HYPOTHESIS), and it is not shown to affect the garage white-out.

Merged but inactive for this port: #367, #348, #375, #357 (the shared draw engine; the D3D12 backend does not use it), #346 (SPIR-V cache), Vulkan/Metal changes (#330, #351, #352, #355, #356, #373, #374, #378).

Deferred: #387 PPU lifter jump-table bounds -- takes effect only after re-lifting PPU, which is not done (`generated/ppu` belongs to another workflow; the trace build lifts into `generated/ppu-hooked-staging`). SPU code is regenerated at configure time by the upstream lifter.

Not relevant: title-specific bring-up (#381, #344), cellVdec MPEG-2 (#379, #380), cellPad rumble (#372), cellFiber (#400), docs.

### Local generic changes on top of v0.17.0

| Change | Evidence |
|---|---|
| x86 SSSE3 forms of the nine quadword byte rotates/shifts (upstream had NEON only; x86 used a 16-byte scalar loop) | `test_spu_int_neon` now runs on x86, bit-identical to `_ref` over 200k random cases; two mutants caught |
| SSE generate-controls cbd/chd/cwd/cdd (scalar forms caused a failed store forward per call) | all positions -64..63 against `_ref`; mutant caught |
| One LS diagnostic gate in `spu_ls_read128`/`spu_ls_write128`; image-2 WWS probes opt-in (`SPU_WWS_PROBE=1`) | WWS probes never fired in MotorStorm logs |
| `sys_timer_usleep` per-thread high-resolution waitable timer | `tools/test_timer_usleep.py` |

Lifted-style microbenchmark (`generated/upstream/bench/ls_bench.c`, 7 LS accesses + 11 ops, same checksum): v0.15-local 34-37 ns/iteration, integration 10.0-10.4 ns. This is a synthetic kernel, not a decode measurement.

`PORT_SPU_AVX2` (port CMake option, default OFF): builds the lifted SPU sources with `-mavx2` so #369's path is used. `fp_bench.c`: 15.2 -> 7.4 ns per fa/fs/fm, same result. `main.cpp` refuses to start without AVX2 when it is on.

### Regression results (integration tree, Windows, clang 23)

- Python suite (`tools/test_*.py`): 83 run; 4 failures fixed (`test_hle_float_args` KNOWN list, `test_mfc_resume_elements` and `test_lfqueue_push_recipient` stubs, `test_ppu_trace` was a concurrent-compile flake and passes alone). About 40 skip as POSIX-only.
- C, built by hand: `test_lfqueue_push_recipient`, `test_texture_layout`, `test_fp_decompiler` (76/76), `test_spu_helpers` (70/70), `test_spu_shufb`, `test_spu_int_neon` (x86), `test_spu_float_neon` (AVX2), `test_spurs_taskset_bits_atomic` (6/6) and `test_spurs_signalled_atomic` (2/2) through a Win32 pthread shim, `test_timer_usleep`.
- NOT TESTED on Windows: `test_gcm_flip_status`, `test_gcm_flip_stream`, `test_rsx_draw_engine`, `test_spu_fnms_zero_extended` (need the POSIX toolchain).

### Integrated build (2026-10-22)

`generated/upstream/build_int.cmd` (`-DPORT_SPU_AVX2=ON -DPORT_HLE_NIDS_GENERATE=ON`) links `build/motorstorm-int/MotorStormPacificRiftRecomp.exe` (401 MB) and `MotorStorm.map`. Two port fixes were needed: the generated table replaces the lift's copy in the source list (otherwise `ppu_hle_register_all` is defined twice), and the AVX2 start-up check uses `IsProcessorFeaturePresent` on Windows (`__builtin_cpu_supports` needs compiler-rt's `__cpu_model`, which clang-cl does not link). Runtime behaviour: NOT TESTED.

### First integrated probe (2026-10-22, run `20261022-085456-int`) and fixes

The probe stopped on no progress before the intro (baseline: intro opened at 28 s). Peak ACPI 354 K. Evidence and fixes:

- **VERIFIED, earliest divergence:** `/dev_hdd1` creates now succeed. v0.15's `ppu_fs.cpp` defined `CELL_FS_O_CREAT` as `0x0200` (the real value is `0x40`, octal 0100); #349 fixed it. The FIOS cache open (`/dev_hdd1/cache/BLES00000/fios/cache.idx`) and the game's font copies (`/dev_hdd1/{kab_plain,framdcn}.ttf`, byte-identical to the disc fonts) now succeed. Without `PS3_HDD1_ROOT` they were written into `original/game/` (moved out: `generated/upstream/hdd1_written/`; `original/game/cache/BLES00000/fios/` is also run output).
- **VERIFIED:** the game then calls `cellFontOpenFontFile("/dev_hdd1/<font>.ttf")`, and cellFont failed: `cellfs_translate_path` had no `/dev_hdd1` mapping. The baseline opened the `/dev_bdvd` path because the copy had failed.
- **STRONGLY SUPPORTED:** the stall is the documented failed-`framdcn.ttf` path (STATUS: glyph packing on an unwritten glyph image). Draws stop at 19.2 s, right after the failed open; no sampler data.
- **VERIFIED:** 16 `identical transfers ... halting the SPU` lines on all four `Wws_Job` lanes (image 1297305682, pc `0x025A4`, idle job-list polling). Cause: per-thread counters (`a6d231b`) plus #383's 30 s rule. Not the stall's trigger (first halt after the stall) but fatal for any later job.

Fixes (`3805b00` in `ps3recomp-int`; port and tools outside it):

| Change | Test |
|---|---|
| `spu_dma_repeat.h`: back off past the limit (yield 2 ms, then `Sleep(1)`), report once per episode, halt only with `SPU_DMA_REPEAT_HALT=1` | `test_spu_dma_repeat.c`: 60 s simulated idle never halts; 64 jobs to 4 idle workers all processed once; halt mode strands 0/64; 2 mutants caught |
| `cellFs.c`: `/dev_hdd1/` -> `PS3_HDD1_ROOT` | `test_cellfs_hdd1.c` (mutant caught) |
| `port/main.cpp` `isolate_hdd1`: default `PS3_HDD1_ROOT` = `<exe dir>/hdd1`, created at start | exe string check |
| `tools/fast_startup.py`: `PS3_HDD1_ROOT=generated/hdd1` (starts empty, as a first boot; `cellSysCacheMount` creates `cache/<id>`) | - |
| `port/port_cpu.h`: AVX2 = CPUID.7 EBX5 + CPUID.1 ECX27/28 + XCR0 bits 1-2, XGETBV only after OSXSAVE | `port/tests/test_port_cpu.c` (8 cases, 2 mutants) |

Back-off cost (test, Windows, `timeBeginPeriod(1)`): an idle worker picks up new work in ~1.0-1.1 ms on average (max ~2-2.5 ms), with or without the 2 ms yield phase; work arriving within 2 ms of the previous transfer is picked up after a yield. Effect on game frame rate: NOT TESTED. Bink's taskset waits on signals, not DMA polling.

Python suite 82/82 pass after the fixes. Rebuilt exe 09:28. Not yet run.

### Second integrated probe (2026-10-22, run `20261022-101338-int2`)

- VERIFIED: fonts copied to `generated/hdd1` (byte-identical) and opened by cellFont with no failure; drawing continued past 19.2 s; intro opened at 29 s; garage file requested at 190 s (runner exit 0, no abort). No SPU halts; 4 `Wws_Job` lanes reported "polling or wedged; still running" once each and idled at 2-3% CPU.
- VERIFIED: Bink decode 20.13 frames/s (blocks 18.92-21.59) vs 10.49 baseline (+92%); 1.85 cores vs 1.82; ~0.092 vs ~0.174 CPU-s per frame (-47%). GPU avg 14% (max 24%); ACPI max 353 K; CPU perf >= 108%.
- Hotspots (decode thread, 96% CPU): `spu_task_launch_check` 10.1%, Bink SPU funcs `127F8` 8.8%, `105F0` 6.7%, `CF80` 6.3%, `102F4` 4.9%; `spu_check_stack_reset` 3.2%.
- NOT TESTED: frame-by-frame video correctness (fast profile takes no captures).

### Drain-hop fast path (offline, commit `02f396e`)

- `spu_task_launch_check` + `spu_check_stack_reset` were 13.3% of the decode thread; the port registers no stack-reset entry, so this was call overhead on every trampoline hop.
- Inline common case (`spu_task_step`, `spu_lockstep_step` in `spu_context.h`); full check unchanged for LS 0, flow tracing, stack-reset entries and step diagnostics.
- VERIFIED (microbenchmark `generated/profile/bench/drain_hop_bench.c` against the built runtime lib, 3 runs): hook cost 7.4-7.8 -> 3.2-3.5 ns/hop; drain step 9.6-10.0 -> 5.4-5.7 ns/hop.
- Tests: new `test_spu_task_step` 11/11 (2 mutants caught); 7 CI SPU suites in WSL pass; `tools/test_*.py` 82/82. Exe rebuilt 10:39.
- HYPOTHESIS: about 5-8% more decode throughput. NOT TESTED in game.

## Third integrated probe: drain-hop fast path measured (2026-10-22, run `20261022-110809-int3`)

Exe sha256 `9f4e9e34...cb15d` (10:39 build, ps3recomp-int `02f396e`). One bounded intro-only run, fast profile, cold FIOS cache (the int2 cache moved to `generated/upstream/hdd1_written/int2/`), fonts already in `generated/hdd1`. Logs: `generated/profile/probe_int3_{run.log,thermal.csv,sample.log,sample.json}`.

| metric | int2 baseline | int3 | change |
|---|---:|---:|---:|
| Bink decode, frames 256-3072 | 20.13 fps | **22.05 fps** | +9.5 % |
| per-256-frame block | 18.92-21.59 | 20.90-23.04 | |
| intro opened -> garage request | 160.75 s | 146.94 s | -8.6 % |
| intro-stage CPU | 295.95 s | 259.56 s | |
| avg cores (whole run) | 1.85 | 1.82 | |
| CPU-s per decoded frame (stage CPU / (fps x stage s)) | 0.092 | 0.080 | -13 % |
| GPU 3D avg / max | 13.9 / 23.9 % | 14.6 / 26.7 % | |
| ACPI max | 353 K | 350 K | |

Decode-thread shares (20 s sampling, 200 Hz): `spu_task_launch_check` 10.1 % -> 0, `spu_check_stack_reset` 3.2 % -> 0, `yz_lockstep_tick` 2.6 % -> 0, `spu_drain_call` 2.5 % -> 10.2 % (hooks now inline there). Drain overhead total 18.4 % -> 10.2 %. New top five: `spu_drain_call` 10.2 %, SPU `127F8` 9.1 %, SPU `CF80` 7.6 %, an unresolved system-DLL address `0x7FFD449115D3` 6.8 %, SPU `105F0` 6.7 % (`102F4` 4.9 %).

Correctness: VERIFIED fonts open from `/dev_hdd1` (no "Cannot open"); garage request reached naturally (runner exit 0); same four `[spu-dma] ... still running` notices as int2, no halts; error/fail lines identical to int2 after normalising numbers. Video frames were not captured (NOT TESTED for image correctness in this run) to keep the measurement clean.

New baseline: **22.05 fps, 0.080 CPU-s/frame**.

## Chained SPU direct transfers (offline, ps3recomp-int `a049a8f`, 2026-10-22)

Rollback point: tag `rollback/pre-spu-direct-branch` = `02f396e`; its exe is kept at `build/motorstorm-int-stepfast/` (sha256 `9f4e9e34...cb15d`). Build without chaining: configure with `-DPS3RECOMP_SPU_LIFTER_ARGS=` (the value is cached), or run with `SPU_NO_CHAIN=1`.

### Dispatch model before the change (VERIFIED from source)

1. Dispatch: `find_spu_functions` cuts at every branch target, so each lifted function is a basic block. A direct branch to another block sets `ctx->pc` and `g_spu_trampoline_fn` and returns; `SPU_DRAIN`/`spu_drain_call` calls the next block. Calls (`brsl`) nest a host call bracketed by `host_depth` and `spu_drain_call(return_pc)`; `bi $r0` is `SPU_RET`; indirect branches go through `spu_indirect_branch` (lookup by image).
2. Guest PC: written only at transfers (`ctx->pc = target`), never per instruction.
3. Instruction accounting/budget: none per instruction. `ctx->steps` counts hops (only used to tell a job's first entry at LS 0 from a later return there). There was no execution budget; loops within one block were already plain `goto`s.
4. DMA/sync: synchronous inside `spu_wrch`/`spu_rdch`; nothing is serviced at hops.
5. Interrupts/stop: a pending `(event_status & event_mask)` with `int_enable` is taken at the next hop (`spu_take_interrupt`, srr0 = hop pc); `stop` sets status and returns; LS 0 transfers end SPURS jobs in `spu_task_launch_check`.
6. Diagnostics at hops: lockstep tick, full task check (stack-reset entries, LS-0 end, `SPU_EXITTRACE`/`SPU_STEPTRACE`/`SPU_JOBDRAIN`), policy flow trace, `SPU_PCHIST`, `SPU_TAILRET`, `g_spu_recent`/`g_spu_pch` post-mortem rings, `drain_ret_pc` reset.
7. Required at every boundary: pc publication, step count, interrupt check, the diagnostics above when enabled.
8. Deferrable: the post-mortem rings (diagnostic only); returning to the drain loop itself (nothing else runs there).

### Change

`--chain-chunks` lifts contiguous chunks as one static function with per-chunk entry stubs; direct transfers between its chunks are `SPU_CHAIN` (pc + step + jump) with fallback to the original hop whenever any item in 6 is active or an interrupt is pending; backward transfers spend a 256-per-invocation budget; LS 0 never chains. Bink: 47 groups, direct trampoline sites 1300 -> 127.

### Offline results

- Tests: `test_spu_chain.c` 122/122 (+119/119 diag) under gcc and clang; 10/10 deliberate mutants caught (interrupt guard, budget, step count, pc store, flow guard, lockstep guard, stack-reset clear, diagnostic arming, lifter back-edge classification, fall-through target). `test_spu_chain_chunks.py` 6/6; Python suite 84/84; extracted CI SPU suites ALL-OK; task-step 9+2.
- Microbenchmark (`generated/profile/bench/chainbench`, clang-cl /O2 -mavx2 like the port, pinned core, 3 runs x 21 reps, medians): direct transfer 5.2 -> 1.1 ns; Bink `127F8` loop, skip path 17.8-20.3 -> 3.9-4.8 ns/iteration, full body 33.6-35.7 -> 24.7-27.4 ns/iteration; budget cost within noise. Registers and step counts identical in every case.
- `127F8`: VERIFIED `1288C` is `ai $r13,$r13,1` (loop counter), its own chunk because 127F8 branches to it; `12890` is `clgt`+`brnz 127F8`. Per iteration: 3 dispatcher returns/indirect calls -> 0 (1 per 256 iterations); group 362 x86 instructions vs 305 across three functions; no new spills (4 stack references, prologue only); the back edge is a native `jmp`. Bitstream bit 1 leaves through the `12BA0` jump table (`bi $r4`), which remains an indirect hop.
- `CF80` (651 insns, 1 branch): 33% loads, 29% shuffles, 22% stores -- LS access bound, chaining does not help it. `105F0` (174)/`102F4` (183): straight-line integer/multiply/shuffle; 2 branches each.
- AVX2: VERIFIED in the chained `127F8` group the compiler emits VEX 128-bit ops and some 256-bit `ymm` merges (`vpblendd`, `vinserti128`) from `-mavx2`; no evidence that the AVX2 single-precision helpers matter here (these functions are integer).
- Unknown hotspot: VERIFIED `0x7FFD449115D3` = `ucrtbase.dll+0x315D3`, the environment-string scan of the CRT getenv (same boot, system DLL bases unchanged); caller `mfc_for`'s per-access `getenv("SPU_PCSAMPLE")`. Fixed (read once).
- Exe: `build/motorstorm-int/MotorStormPacificRiftRecomp.exe` sha256 `5cefe19a...e8f2`, 12:02, chained lift of all 26 images.
- In-game effect: NOT TESTED. HYPOTHESIS: drain overhead (10.2%) and getenv (6.8%) mostly removed, plus faster `127F8`-type loops -> roughly 15-25% more decode throughput (22 -> ~25-27 fps), not enough alone for 29.97.

## Fourth integrated probe: chained transfers (`a049a8f`, int4)

Exe sha256 `5cefe19a...e8f2` (12:02). Same method as int3: one bounded intro-only run, fast profile, cold FIOS cache (int3's moved to `generated/upstream/hdd1_written/int3/`), fonts in `generated/hdd1`, no `SPU_*` variables, same thermal guard and 20 s/200 Hz sampler 30 s after the intro opened. Run `generated/runs/20261022-124002-int4`; logs `generated/profile/probe_int4_*`.

| metric | int3 | int4 | change |
|---|---:|---:|---:|
| Bink decode, frames 256-3072 | 22.05 fps | **27.12 fps** | +5.07 (+23.0 %) |
| per-256-frame block | 20.9-23.0 | 20.7-30.0 | |
| intro opened -> garage request | 146.94 s | 120.17 s | -26.77 s (-18.2 %) |
| intro-stage CPU | 259.56 s | 197.12 s | -24.1 % |
| avg cores (whole run) | 1.82 | 1.60 | -0.22 (-12 %) |
| CPU-s per decoded frame | 0.080 | 0.060 | -0.020 (-25 %) |
| GPU 3D avg, all guard rows (int3 method) / game present / max | 14.6 / 16.6 / 26.7 % | 14.1 / 17.3 / 26.0 % | |
| ACPI max | 350 K (77 C) | 351 K (78 C) | +1 K |

29.97 fps needs a further +10.5 % (2.85 fps).

Correctness: VERIFIED fonts open from `/dev_hdd1`; intro `.bik` opens; all 3072 counted frames decoded, the slow third block (20.7) matches int3's (20.9) so it is content, not a stall; normalised error/notice classes identical to int3 (same four `[spu-dma] ... still running`, no halts, no assertions); garage request reached naturally (exit 0); no guard kill. Chaining has no runtime log, so fallback/budget behaviour is not directly observed (PARTIAL): the decode profile is consistent with chaining active. Visual output not captured: NOT TESTED.

Decode thread (97 % CPU): groups replace per-chunk symbols, so shares are per group. `grp_122E8` (contains `127F8`) 17.0 %, `grp_10200` (`102F4`+`105F0`) 13.0 %, `grp_12BB4` 10.2 %, `grp_F530` 7.6 %, `grp_12108` 7.0 %, `grp_CB40` (contains `CF80`) 6.7 %. Dispatch: `spu_indirect_branch` 2.5 % + `spu_lookup` 1.5 % + `spu_drain_call` 1.4 % = 5.4 % (int3: 13.6 %). The ucrtbase getenv hotspot is gone from the decode thread (0.1 % on another thread).
New hotspot, VERIFIED: `spu_ls_write128` 5.4 % + `spu_ls_read128` 4.2 % as out-of-line calls. The chained build's map has 36 out-of-line copies of these `static inline` helpers (int3: 8, read only): clang stops inlining them into the larger group functions.

New baseline: **27.12 fps, 0.060 CPU-s/frame** (`a049a8f`).

## LS accessor inlining (offline, ps3recomp-int `b1aa857`, 2026-10-22)

Tested baseline tagged `baseline/int4-chain-27fps` (= `a049a8f`); its exe is kept at `build/motorstorm-int-chain-int4/` (sha256 `5cefe19a...e8f2`).

- VERIFIED cause of int4's new 9.6 %: in the Bink image compiled exactly as the port does (clang-cl /O2 -mavx2, `generated/profile/bench/lsbench/cc.cmd`), groups make 860 `spu_ls_read128` and 443 `spu_ls_write128` out-of-line calls (`grp_CB40` 250+166, `grp_8708` 403+178). Each call spills the u128 (Windows x64 passes it by reference), pushes 3-4 registers, and the write checks a `/GS` cookie, around one `vmovdqu`+`vpshufb`+`vmovdqu`.
- Change: both accessors `always_inline` (`SPU_LS_INLINE` in `spu_context.h`); diagnostic paths stay `noinline, cold`. Out-of-line calls 1303 -> 0; Bink object +4.9 %.
- Microbenchmark (`lsbench/bench.c`, pinned core, 3 runs x 21 reps x 20000 calls, medians; same result-state checksum `34B32D26`, pc 0x8850): `CF80` chunk 1249.2 / 1276.3 / 1545.9 -> 642.5 / 644.3 / 645.5 ns per call (-49 %).
- Remaining per-access cost (VERIFIED from disassembly): because LS stores go through `uint8_t*`, the compiler reloads `ctx->ls`, `g_spu_ls_diag` and the address register after every store (about 9 instructions per access). Removing that needs the lifter to keep the LS base and gate in locals (HYPOTHESIS: a further gain in `CF80`-type code; not attempted).
- Tests: `tools/test_spu_ls_inline.py` 2/2 (gcc, clang in WSL; skipped on Windows); old header caught under gcc (Linux clang inlines either way). Chain 122/122 + 119/119 (gcc, clang), CI SPU suites ALL-OK, task-step 9+2, Python 85/85.
- Exe: `build/motorstorm-int/MotorStormPacificRiftRecomp.exe` 13:01, sha256 `c09662be...46ac`; map has no out-of-line LS accessor; keeps the DMA, `/dev_hdd1`, chaining and AVX2 settings.
- In-game effect: NOT TESTED. HYPOTHESIS: most of the 9.6 % recovered, ~+8-10 % decode throughput (27.1 -> ~29-30 fps).

## Fifth integrated probe: LS accessors inlined (`b1aa857`, int5)

Exe sha256 `c09662be...46ac` (13:01). One bounded intro-only run, fast profile. Preflight: `original/game/` held no FIOS cache or font copies; an empty `game/BLES00000/USRDIR` tree (18 Oct, cellGame's `/dev_hdd0/game` content root) was moved to `generated/upstream/vfs_written_20261018/`; `PS3_HDD1_ROOT` = `generated/hdd1` (`tools/fast_startup.py`), emptied first (int4's cache and fonts -> `generated/upstream/hdd1_written/int4/`), so this run also re-copied the fonts. Idle ACPI 352 K after the rebuild; launched after it settled to 345-346 K. Run `generated/runs/20261022-130726-int5`; logs `generated/profile/probe_int5_*`.

| metric | int4 | int5 | change |
|---|---:|---:|---:|
| Bink decode, frames 256-3072 | 27.12 fps | 27.54 fps | +0.42 (+1.5 %) |
| per-256-frame block | 20.7-30.0 | 24.9-30.5 | |
| intro opened -> garage request | 120.17 s | 118.58 s | -1.3 % |
| intro-stage CPU | 197.12 s | 201.81 s | +2.4 % |
| avg cores (whole run) | 1.60 | 1.65 | |
| CPU-s per decoded frame | 0.060 | 0.062 | +3 % |
| GPU 3D avg all rows / game present / max | 14.1 / 17.3 / 26.0 % | 14.0 / 17.3 / 26.4 % | |
| ACPI max | 351 K | 352 K | |

Correctness: VERIFIED fonts copied into the empty HDD1 root (byte-identical to earlier copies) and opened by `cellFontOpenFontFile`; intro opened and decoded through frame 3072; error/notice classes identical to int4 (four `[spu-dma] ... still running`, no halts); garage request reached naturally; no guard kill. Visual output NOT TESTED. The run recreated the empty `original/game/game/BLES00000/USRDIR` (cellGame content root, `libs/system/cellGame.c`); moved to `generated/upstream/vfs_written_int5/`.

Profile (decode thread 97 %): `spu_ls_read128/write128` 9.6 % -> 0; `grp_122E8` 17.8 %, `grp_10200` 17.8 %, `grp_12BB4` 11.8 %, `grp_F530` 8.7 %, `grp_CB40` 7.8 %; dispatch 5.0 %.

VERIFIED: the inlining removed the call overhead but gained only ~1.5 % in game (within block-to-block spread), far below the microbenchmark's 2x on `CF80` and the predicted +8-10 %. The isolated benchmark ran one chunk hot in cache; in game the time moved into the groups. Not a regression; keep. New measured baseline: **27.54 fps, 0.062 CPU-s/frame**.

## Intro presentation: decoded vs shown frames (offline, 2026-10-22)

The user sees the intro at about 8 fps. The 27.54 fps above is the Bink **decode** rate (SPU task wakes of taskset `0x0135D080`, one per frame: 3160 wakes for the file's 3159 frames in the diagnostic run). It is not a display rate.

Pipeline: PPU `BinkMoviePlayer` sets event flag `0x01366700` -> Bink SPU task (image `456415131`, one task, one SPU) decodes a frame into guest memory -> PPU draws it (YUV planes as textures, 23 draws a frame) and queues a flip (`_cellGcmSetFlipCommand`) -> RSX FIFO drain reaches the flip -> D3D12 replays the draws, `Present(1, 0)` (vsync, at most one flip per 60 Hz tick) -> guest flip completion on the next tick.

Evidence from existing logs (VERIFIED unless marked):

| run | decode fps | median guest flips/s during the intro | flips per decoded frame | Bink audio port 1 `PortStop` calls |
|---|---|---|---|---|
| baseline-diag | 5.9 | 3.8 | 0.64 | 462 |
| int2 | 20.1 | 6.1 | 0.30 | 65 |
| int3 | 22.05 | 6.1 | 0.28 | 48 |
| int4 | 27.12 | 7.2 | 0.26 | 14 |
| int5 | 27.54 | 7.1 | 0.26 | 12 |

- Guest flips are 60/s on the loading screen before the intro and 16-33/s after it, so the host present path is not capped near 8.
- In int5, the intro (3159 frames, 30000/1001 fps, 105.4 s of media) took about 115 s from open to the last decode: playback is paced by the decoder, not by a clock.
- The decode thread is 97 % busy, and the render thread (`ppu_gcm_pump`) is about 84 % waiting. The decoder is never idle waiting for the PPU to ask for the next frame.
- Bink stops and restarts its audio port (port 1) repeatedly. This is how it resyncs when video lags audio. The count falls as decode speeds up.
- Guest clocks: all 1312 lifted `mftb` sites call `ppu_timebase_now()` (QPC scaled to 79.8 MHz), and `sys_time_get_system_time` and `get_current_time` come from QPC. No conversion error was found by reading the code.
- `cellGcmSetWaitFlip` is not imported, so its 64 x `Sleep(1)` bound is not involved.

SUPPORTED HYPOTHESIS (rank 1): the decoder is below real time (27.5 < 29.97), so Bink is permanently behind its clock and skips **displaying** most frames. It must still decode every frame, so skipping does not help it catch up. The result is about one displayed frame per 3.5-4 decoded, the user's ~8 fps. The ratio is nearly constant from 20 to 27.5 fps and changes only in the far-behind regime. If correct, the visible rate will jump toward 29.97 only once decode sustains real time with margin; today's slowest 256-frame blocks run at 24.9 fps, so the slowest blocks need about +22 %, and the average needs about +9 %.

Rank 2, NOT TESTED: the D3D12 texture cache re-uploads a held texture only when a sparse checksum changes (1024 words, 0.4 % of a 720p luma plane). A video frame that changes only between sample points would show the previous frame. `PS3_VIDEO_STATS` counts this as `stale`.

Rank 3, NOT TESTED: per-frame present/fence waits. `PS3_VIDEO_STATS` and the new D3D12 `PS3_FTRACE` spans measure them.

Instrumentation (ps3recomp-int `f764b84`, local): `PS3_VIDEO_STATS=1` reports decoded/s, new video textures consumed/s, presents/s, video presents new/dup, stale binds, decoder wakes per new present ("advance"), flips/s, vblank/s, bind-to-present latency, `Present()`/fence ms and requested usleep ms/s every 2 s. A per-present CSV goes to `PS3_VIDEO_STATS_TIMELINE`. D3D12 `Present()`/fence spans are added to `PS3_FTRACE`. Disabled cost is 0.3 ns per hook (load and branch); enabled, about 0.1 ms per frame (720p luma hash). Exe `build/motorstorm-int` sha256 `bdd9c098836706403d986421ab1aa1d7b48b97d0c1e526addc43c036b0ad92ce`; the int5 exe is preserved in `build/motorstorm-int-lsinline-int5/` (`c09662be...`).

Prepared probe (needs approval): `generated/profile/probe_vstat.sh`.

### `/dev_hdd0` isolation

`tools/fast_startup.py` sets `PS3_HDD0_ROOT=generated/hdd0`. sys_fs, `ppu_fs` and cellGame already honour it; cellFs's default table now does too (ps3recomp-int, with test). Guest `/dev_hdd0/game/BLES00000/USRDIR` therefore lands in `generated/hdd0/game/...`, not `original/game/game/...`. VERIFIED by the test; not yet verified in a game run.

### Post-intro loading

- Last verified state with the current build (int5): at 145.7 s, the garage's loose-file probes (`worlds/track_garage_*.rpk`, `data/track_garage/*`) miss as expected, because the data is in `ms2.psarc` and member opens are not logged. `AsyncRenderThread` has been created, and the loading screen presents at 33 fps with 3 draws.
- No run of a build with the HDD1/font fix has gone further. The diagnostic run that did (`20261021-220103-baseline-diag`, 773 s) predates the fix: its fonts failed to open, and presents stopped altogether 25 s after the garage request.
- Whether the current build loads the garage is NOT TESTED.

## Diagnostic probe `20261022-142003-vstat` (exe `bdd9c098`, `f764b84`)

Bounded intro-only run: it reached the garage request naturally at 141.5 s. ACPI max 353 K, GPU 3D 14.5 % average and 25.8 % peak, 1.71 cores. Both fonts were copied into an empty HDD1 cache and opened. Error/notice classes are identical to int5 (four `[spu-dma] ... still running`, no halts or assertions).

| | int5 | vstat |
|---|---|---|
| Bink decode, frames 256-3072 | 27.54 fps (blocks 24.9-30.5) | 28.79 fps (blocks 27.1-30.2) |
| intro opened -> garage request | 118.58 s | 113.84 s |
| average cores | 1.65 | 1.71 |
| new video frames presented, whole intro | (not measured) | 1320 of 3160 decoded, 11.75 /s |
| steady lagging phase | ~7 flips/s | 6.3-8.0 /s, exactly 4.00 decoded per presented |

Per-present CSV over 1545 intro presents:
- decoded-frame advance between consecutive presents: 1 in 692 presents, 4 in 588, 0 in 218, 2 or 3 in 45, and 8 once;
- stale binds: 0;
- presents equal guest flips;
- `Present()` 1.1-1.5 ms average, frame fence 0.01-0.04 ms, bind-to-present 1.5-2 ms;
- cellAudio mixed 187.4-187.8 blocks/s against 187.5 real time;
- Bink audio port stopped 6 times.

Timeline excerpt (seconds after the first stats window):
- in sync: 40.325 s decoded 469 -> 40.358 s 470 -> 40.392 s 471 -> ... (+1 every 33 ms, a flip each);
- lagging: 50.309 s 756 -> 50.452 s 760 -> 50.597 s 764 -> 50.740 s 768 (+4 every 143 ms, a flip each, all new and none stale).

Findings:
- **H1, VERIFIED (mechanism) / SUPPORTED (cause).** The 27 -> 7 loss happens in the guest before submission. The game requests one flip per four decoded frames, and every requested flip reaches the screen with new content. It alternates between in-sync stretches (advance 1.0, 30 presents/s, whenever decode holds about 30 fps) and lagging stretches pinned at exactly 4. This is a capped catch-up skip by the original player. The trigger, falling behind its clock, matches decode dropping below 29.97.
- **H2, RULED OUT:** 0 stale binds measured with a full hash.
- **H3, RULED OUT:** Present and fence waits are about 1 ms and 0.02 ms, and every flip was presented.
- **H4, RULED OUT for the clock rate:** the audio mixer runs at real time (+0.05 %).
- Guest vblank: not measured. The hook sat in `cellGcm_request_tick`, but the port ticker calls `cellGcmTickVBlank`; fixed in `1966458`. Flips reached 60/s on the loading screen.
- `PS3_FTRACE` output was lost (the probe script passed an MSYS path; fixed). `PS3_POLLTOP` printed empty tables.
- Instrumentation overhead: decode was 28.79 fps against int5's 27.54, so it did not slow the decoder. The difference is within run-to-run spread.
- `/dev_hdd0`: cellGame's content root was `generated/hdd0/game`. `cellGameContentPermit` still also created `original/game/game/BLES00000/USRDIR` (empty), which was moved to `generated/upstream/vfs_written_vstat/`. Fixed in `1966458` with a test; the exe is now `e6683cfa...`.

Next (smallest evidence-based step): decode throughput. Display collapses to 1/4 whenever decode drops below real time, and returns to 1:1 whenever it holds about 30 fps. The slowest 256-frame blocks (27.1 fps here) need about +11 % to sustain 29.97 with no margin. Identify which decode groups dominate the slow blocks (I-frame-heavy scenes?) and optimise those. Do not change the player's timing.

## Bink decode cost and frame-skip rule (offline, ps3recomp-int `29df355`, 2026-10-22)

Exe `0194b89e147698d16d1af068d3643fb4c9d45d85b5fa802c83f291443efc6e78`. The previous exe `e6683cfa...` (`1966458`) and its map are preserved in `build/motorstorm-int-1966458/`. Rebuild log: `generated/profile/rebuild_lsfwd.log`, exit 0. Not run.

- **Skip rule, VERIFIED in code** (details in `docs/RESEARCH.md`):
  - the clock is system time (`RADTimerRead`); audio is not used;
  - a frame is skipped when it is more than 2000*Div/Rate (~66 ms) late;
  - at most 3 consecutive skips, which gives the fixed 4:1;
  - 1:1 resumes once lateness drops below the threshold;
  - above 725 ms late, a sound pause/resume resync resets the epoch.
  
  Nothing was patched. The `usleep(10)` poll costs ~0.27 ms per frame (measured).
- **Changes:**
  - x86 SSE4.1/AVX2 SPU multiply/extend/shift helpers (bit-identical);
  - restrict LS pointer and hoisted diag gate in lifted chunk groups. On the Bink image this cuts `ctx->ls` reloads 5133 -> 68 and stores -14.7 %.
- **Whole-group benchmarks** (identical state hashes, real bitstream):

  | Stage | before (ns) | after (ns) | change |
  |---|---|---|---|
  | coefficient decode, per call | 5154-5721 | 4670-4737 | ~-12 % |
  | IDCT `101F8`, per block | 1441-1495 | 1204-1286 | ~-15 % |
  | IDCT `F530`, per block | 1306-1407 | 1021-1034 | ~-24 % |

  The FPS effect is not measured; it is a HYPOTHESIS of +6-9 % decode.
- **Diagnostics fixed, with tests:** vblank counted exactly once; per-row timeline flush; POLLTOP has no empty reports.
- **Filesystem:** bare `/dev_hdd0` and `/dev_hdd1` now map to their roots in `ppu_fs` and `sys_fs`. A new test checks that all translators agree.
- **Tests:**
  - tools suite (Windows): 86/86;
  - tools suite (WSL Ubuntu): 83/86; the 3 failures are the known pre-existing ones (`test_loaded_image_memory`, `test_sail_boot_callback`, `test_sysmodule_unload_module_ex`);
  - SPU chain tests: 132/132 (129 in diag mode) on gcc and clang;
  - video_stats: 21 checks;
  - polltop: 30/30;
  - vblank and mount-agreement tests pass.
  - Audit: only the 25 pre-existing blocks; none involve staged files.

## Diagnostic probe `20261022-180551-lsfwd` (exe `0194b89e`, `29df355`)

One bounded intro-only run, the same script, limits and cold `generated/hdd0`/`hdd1` as `vstat` (`generated/profile/probe_lsfwd.sh`, which refuses any other exe hash). It reached the garage request naturally at 137.5 s and stopped there. ACPI peak 351 K (78 °C), GPU 3D 19.0 % average and 26.2 % peak, 1.92 cores. Afterwards no game, guard or sampler process remained. `original/` was identical before and after (file stats, mtimes, EBOOT sha256, no `original/game/game`). HDD writes went to `generated/hdd0` and `generated/hdd1`. Error/notice classes are unchanged: four `[spu-dma] ... still running`, no halts.

| | vstat (`bdd9c098`) | lsfwd (`0194b89e`) |
|---|---|---|
| Bink decode, frames 256-3072 | 28.79 fps (blocks 27.13-30.23) | 30.01 fps (blocks 29.26-30.97) |
| intro opened -> garage request | 113.84 s | 109.91 s |
| process start -> garage request | 141.5 s | 137.5 s |
| new video frames presented, whole intro | 1319 of 3160 (41.7 %) | 1953 of 3160 (61.8 %) |
| presents with advance 1 / 4 | 692 / 588 | 1530 / 382 |
| 2 s windows in 4:1 skip mode | 29 of 54 | 17 of 52 |
| mean unique visible / flips per s (intro windows) | 11.9 / 13.8 | 18.5 / 21.6 |
| Bink audio port stops (resyncs) | 6 | 0 (one close at the end) |
| max lateness proxy (29.97 clock - decoded) | 122 frames | 15 frames |
| `Present()` mean / max ms | 1.65 / 90.7 | 2.04 / 14.7 |
| fence mean ms, stale binds | 0.018, 0 | 0.013, 0 |
| vblank/s | 0 (not counted) | 62.5 |
| process CPU-s per decoded frame (intro stage) | 0.064 | 0.071 |
| Bink SPU thread (sampler, 20 s) | 96 % of a core | 95 % of a core |

- Instrumentation, VERIFIED in production:
  - `PS3_FTRACE` wrote a valid file at the Windows path: 27 threads, 5357 spans, 0 bad, none after 70 s;
  - the timeline CSV has 3498 rows;
  - POLLTOP printed 13 reports with 0 empty (previously 26 reports, 10 of them empty);
  - vblank is counted once per ticker beat.
- **VERIFIED:** the vblank cadence is 62.5 Hz, not 59.94 Hz. `port/main.cpp` steps the ticker by 16 ms of `GetTickCount64`. Bink's skip clock is system time, so this does not drive frame selection. It is a fidelity deviation for anything the game paces on vblank. Not changed.
- **VERIFIED (mechanism):** display is still bimodal: either 1:1 (~30/s) or the player's capped 4:1 (~7.5/s). The ftrace window (60-70 s, a skip stretch) shows:
  - the main thread sleeps 88 % of the time in `DoFrameAsyncWait`'s poll (`lr 0xC704EC`, in `0xC70318`);
  - flip intervals have a median of 129 ms, which is four decoded frames.
  
  4:1 starts whenever lateness passes 66 ms (2 frames). It pays back at only (decode - 29.97) frames/s, so with decode at 30.0 one slow stretch (intro 24-32 s, the content-heavy region slow in every run) costs ~10-20 s of 4:1.
- **INCONCLUSIVE (attribution):** the decode change, +1.22 fps (+4.2 %), equals the int5 -> vstat difference (+1.25 fps), which had no SPU code change. One run each cannot separate it from run-to-run spread. It is below the +6-9 % predicted from the group benchmarks.
  - The slowest block is +2.1 fps.
  - The per-frame cost of the decoder thread fell ~5 % (sampler: 0.96 core / 28.79 vs 0.95 / 30.01).
  
  The display gains are real as measured, but they follow from where decode sits relative to 29.97, so they inherit the same uncertainty.
- **INCONCLUSIVE:** process CPU per decoded frame rose 10 %. The guest flipped 57 % more often (more frames rendered and presented), which is the likeliest cause; it was not isolated. The decoder thread's own cost did not rise.
- Next, ranked:
  1. Decode headroom. The SPU thread is saturated at one core, and 30.0 has no margin over 29.97. The slow content stretch needs roughly +10 % to stay 1:1. Hot groups: `122E8`/`12BB4` (coefficient symbol handlers, 33 %), `10200`/`F530` (IDCT, 21 %). Lever: the register-file/drain-hop cost (RESEARCH.md hypothesis).
  2. Vblank cadence 62.5 -> 59.94 Hz, for fidelity, not intro speed.
  3. Nothing on the present path: Present ~2 ms, fence ~0.01 ms, every flip presented.

Hardening after the probe (not run in game): `SPU_LS_GROUP_ENTRY` now also stores `ls` into `ctx->ls`, which makes the restrict contract ISO-valid for DMA helpers and inlined lifted functions. The probed exe passed the alias test (9/9) under production clang-cl, and its group `0x3478` disassembly reloads LS after the DMA-GET call. Its correctness rested on clang treating the asm escape as publishing `ls`, which ISO does not guarantee. The no-publish mutant miscompiles 3 cases. The exe `0194b89e` and its map are preserved in `build/motorstorm-int-29df355/`.

Rebuilt with the hardening (ps3recomp-int `9b0c120`, local; log `generated/profile/rebuild_lshard.log`, exit 0): exe `27a79e7b826c64dcb668e4379f3ccd0ed61387b486e5e4b3b3ab73ab739c1ab0`. It has not been run in game.
- All 46 emitted Bink group symbols begin with `movq %r8, 0x40800(%rcx)` (`ctx->ls = ls`). Disassembly: `generated/profile/lsalias/grp3478_27a79e7b.s`.
- Tests:
  - `test_spu_ls_alias.py` (WSL): gcc and clang 9/9; clang mutant caught (3 cases);
  - chain tests 132/129 on gcc and clang; `test_spu_chain_chunks.py` OK;
  - Windows tools suite 87/87;
  - CI runs the alias test (`linux.yml`).

## Video artifacts, FPS counter, audio and vblank (offline, 2026-10-22)

Nothing was run in game. Evidence came from existing logs and captures, source code, and private offline comparisons (`generated/profile/vartifact/`).

### Title-bar FPS (VERIFIED, code)
- **Where:** `render_frame()` in `libs/video/rsx_d3d12_backend.c`, at the end of each call. It runs on the present thread (the port's `frame_clock`), not a guest thread.
- **What it counted (exe `0194b89e`/`27a79e7b`):** every `render_frame()` call, including offscreen-only batches that call no `Present()`. In the intro, presents equal guest flips (vstat), so in practice it showed guest flips per second. Repeated frames are included.
- **How:** count divided by elapsed time over a window of at least 1000 ms of `GetTickCount64` (15.6 ms granularity), reset each window. No rolling average. One counter covers video, UI and 3D. It is not tied to vblank, but presents happen inside the tick loop.
- **Below 10:** in the player's 4:1 stretches the guest flips 7.2–8.0 times per second (vstat `flips`), so the counter reads ~7.5. Decode stays at ~30.
- **Change:** it now counts `Present()` calls over a QPC window. `PS3_VIDEO_STATS` reports decode/s (`decoded`), unique video frames/s (`new`), presents/s, flips/s, repeats (`dup`), vblank/s and now `torn`.

### Video artifacts
- **VERIFIED (independent decode):** FFmpeg's `binkvideo` decodes the intro (BIKi 1280×720, 3159 frames, 29.97 fps). The 11 intro frames in the presented captures `generated/frames/video-luma-20261021-1/` (Oct 21 build) match it:
  - global correlation 0.995–1.000;
  - 16×16 block RMS about 1 level outside highlights.

  So the decoded pixels are correct, and that run had no block-level decode corruption.
- **VERIFIED (mixed generations):** capture 47 shows frame 447 for y < 160 and frame 445 below, a hard cut on a macroblock-row boundary. Frames 445 and 447 share a Bink buffer. The decoder had written the first 10 macroblock rows of 447 into 445's buffer before the backend read that texture. This is the "portions delayed / updating wrongly" look. Captures 38–40 show smaller top-strip mismatches; 42–45 differ only in clipped sky. That run dumped frames synchronously (perturbed timing), on an older build.
- **SUPPORTED (current build):** in the `lsfwd` ftrace window (60–70 s, a 4:1 stretch), each frame was presented 6.8 ms after its flip request (median; max 10.0). The decoder could start reusing that buffer at the earliest 26.3 ms after the flip, so 0 of 78 presents raced. The hazard exists but did not occur in that window. Whether it occurs elsewhere in today's build is INCONCLUSIVE until a probe with the new `torn` counter.
- **Defect fixed (VERIFIED, code):** the texture cache computed its re-upload checksum after the copy. A torn upload was therefore cached under the finished frame's checksum and shown until the bytes changed again, which is two frames later in a double buffer. It now checksums before the copy.
- **Not the cause (VERIFIED):** Bink makes no cellGcm calls, and the player loop (`0x5C65D8`–`0x5C668C`) has no RSX fence before `DoFrameAsync`. Buffer safety comes from the game's frame pacing. Separately, the ticker calls `cellGcmTickFlip` before it presents the frame, so the guest sees the flip complete microseconds before the textures are read. Not changed.
- **Decoder differential (VERIFIED):** coefficient decode (`0x120A8` → `122E8`/`12BB4`) and IDCT `0x101F8` on the real bitstream at frames 0/900/2000/3100 are identical (per-call registers, coefficients, whole LS) across:
  - the 1966458-era object;
  - the `29df355` object (probed exe);
  - the `9b0c120` production object (hardened).

  The F530 check is weak: its hash does not vary with input.
- **YUV planes:** Y 1280×720 (921,600 B) and chroma 640×360 (230,400 B), uploaded as R8. Each plane is a separate cache entry keyed by guest offset. The stale metric covered luma only; `torn` covers both.

### Frame skipping
Unchanged, VERIFIED (RESEARCH.md). Skip when more than 66 ms late against `sys_time_get_system_time`, at most 3 in a row (hence 4:1). Resync above 725 ms. The runtime adds about 0.27 ms of usleep latency per frame. No runtime timing violation was found.

### VBlank (VERIFIED, fixed)
`cellVideoOut` reports 59.94 Hz; the frame clocks ticked every 16 ms (62.5 Hz).
- **Fix:** `include/ps3emu/vblank_clock.h` (deadline t0 + n·1001000/60 µs, no drift, same burst/resync). It is used by `port/main.cpp`, the project template and `boot_main.cpp`.
- **Test:** `tests/test_vblank_clock.c`.
- `port/main.cpp` is not under version control; the original is preserved in `generated/profile/vblank/port_main.cpp.orig`.

### Audio
- **Libraries the game imports (VERIFIED):**
  - cellAudio: 11 NIDs. 10 are implemented; `0x4109D08C` (likely `cellAudioSetPortLevel`) is missing but was not called before the garage request.
  - cellVoice: 13 NIDs (voice chat).
  - No libmixer, libsnd3, cellAdec or ATRAC.
- **Game audio (SUPPORTED, thread names):** Sony MultiStream ("Multistream PPU Update Thread") mixes on SPU into port 0 (8ch, 16 blocks). The game's `avStream` threads stream files; `avStream::StreamCodecMP3::ProcessThread` decodes MP3 on the PPU (likely the music).
- **Intro audio (VERIFIED):** Bink audio (DCT, 48 kHz; the file has 28 audio tracks) runs on the "Bink Audio Thread". It goes to port 1 (2ch, 16 blocks). Its clock is system time, not audio. Resync stops and restarts port 1.
- **Runtime mixer (VERIFIED, code + test):**
  - pacing: one 256-sample block per port per 5.33 ms, paced by WASAPI padding;
  - input: big-endian float;
  - 8ch is downmixed to stereo with fixed gains, an approximation, not the firmware matrix;
  - port level is ignored (always 1.0);
  - mixes are summed and hard-clipped;
  - each block is cleared after consumption;
  - the read index is published modulo nBlock;
  - timestamps are tag × 5.33 ms from init.
- **Measured:**
  - `lsfwd`: 187.6 blocks/s against 187.5 (+0.05 %), 0 % silent, 0 dropped, 0 Bink resyncs;
  - vstat run: 6 resyncs.

  Whether the audible output is correct is NOT TESTED.
- **Missing or partial for gameplay:**
  - `cellAudioSetPortLevel`;
  - the firmware 7.1 → 2 downmix;
  - multichannel host output (stereo only);
  - `cellAudioAddData` family (not imported);
  - cellVoice: stub level, not reviewed.

  Engine, positional and menu audio go through MultiStream on SPU, which is untested beyond port 0 receiving data.
- **New:** `PS3_AUDIO_STATS=1` (`[astat]` every 5 s) reports per-port blocks/filled/empty/Start/Stop, drift against 48 kHz, latency, drops and mixer CPU. Tests: `tests/test_audio_stats.c` and `libs/audio/tests/test_audio_mix.c` (in CI).

- Rebuild after the A/V diagnostics commit `b4d532c` (ps3recomp-int): exe `bba5c2a904bd8d6fea64618ff7decb65565fb8fdd0b4cd63bc486d28e0b607fd`, preserved in `build/motorstorm-int-b4d532c/`. Not yet run in game.

### A/V probe `av` (exe bba5c2a9, 2026-10-22 19:15) — invalid as a baseline comparison

One bounded run (`generated/profile/probe_av.sh`, run `generated/runs/20261022-191521-av`). Preflight error: `generated/hdd1` was not emptied, so the run started with the lsfwd run's warm FIOS cache (cache.dat 505 MB, cache.idx 1 MB). The game then reopened `fios/cache.idx`/`cache.dat` about 4,000 times, never drew, never opened the intro, used under 1 % CPU, and hit the 210 s timeout (runner exit 2). ACPI peak 352 K; no guard kill; no processes left; `original/` identical before and after. The warm cache was moved to `generated/upstream/hdd1_written/av_warm/`.
- VERIFIED: vblank median 60.00/s (p10 59.54, p90 60.07; 80 five-second windows) versus a 62.51 mean before the fix.
- VERIFIED: the title bar counted Present() at 59.86–60.18 (one 56.2) with 0 draws, because the ticker path keeps presenting.
- SUPPORTED HYPOTHESIS: `cellSysCacheClear` (`libs/system/cellSysutil.c`) only unmounts and does not delete the cache contents as the PS3 does, so a cache left by a run stopped at the garage request survives into the next boot. Not fixed.
- NOT TESTED: every intro, audio, torn-frame and decode question.

### Cold-cache A/V run `av2` (exe bba5c2a9, 2026-10-22 19:28)

One bounded run, `generated/runs/20261022-192859-av2` (`probe_av.sh av2`). Preflight passed: full exe hash, `original/` snapshot, `hdd1` holding only the two fonts, `hdd0` empty, no processes, and no WAV. Runner exit 0 (`milestone_reached`). Duration 145 s; ACPI peak 355 K; no guard trip. Afterwards `original/` was identical (`probe_av/original_before2.json` vs `original_after2.json`). The new cache was moved to `generated/upstream/hdd1_written/av2_cold/` (`av_warm` untouched), and no processes remained.

Compared with lsfwd (exe 0194b89e); intro means are over the windows where decoding was active:

| metric | lsfwd | av2 |
|---|---|---|
| intro opened / garage request | 27 s / 137.5 s | 27 s / 145 s |
| Bink decode, frames 256–3072 | 30.01/s (blocks 29.26–30.97) | 27.66/s (blocks 25.60–30.01) |
| vstat decoded/s | 29.13 | 27.32 |
| unique displayed (`new`)/s | 18.11 | 9.41 |
| flips/s = presents/s | 21.77 | 10.96 |
| windows with advance ≥ 3.5 (about one in four shown) | 18/53 | 36/56 |
| torn uploads per window (mean, max) | not measured (counter added in b4d532c) | 1.18, 11 (17/56 windows) |
| stale | 0 | 0.02 (max 1) |
| vblank/s | 62.51 | 59.95 (59.46–60.37) |
| Bink audio port Start/Stop | 1/1 | 11/11 |

- VERIFIED: with a cold cache, the intro opens and plays through to the garage request.
- VERIFIED: vblank now runs at about 59.94 Hz.
- VERIFIED: compared with lsfwd, unique displayed FPS halved, decode is about 8 % slower, and the game shows one decoded frame in four for most of the intro. The title bar read 6–7 FPS for most of the intro.
- VERIFIED: torn texture uploads occur (the guest rewrote the texture bytes while the backend was copying them) in 17 of 56 windows. The lsfwd exe had no torn counter, so this is not a regression comparison.
- VERIFIED: audio.
  - `cellAudio` Init.
  - Port 0 is 8ch × 16 blocks and is never fed (100 % silent).
  - Bink port 1 is 2ch × 16 blocks.
  - The mixer ran at 187.5 blocks/s (drift within ±5 ms) with 0 dropped frames.
  - Port 1 had 10 extra Stop/Start pairs; each window containing one has about 145 empty blocks (about 0.77 s with no Bink audio).
  - Whether the audible output is correct is NOT TESTED.
- HYPOTHESIS: the extra Stop/Start pairs and the one-in-four skipping share a cause, such as Bink pausing audio when it falls behind. Candidate differences from lsfwd:
  - the 59.94 Hz vblank (versus 62.5);
  - the extra stats overhead;
  - run-to-run variance (only one run each).
  
  None of these is isolated.
- FIOS cache, from offline reading of the logs and code:
  - VERIFIED: `cellSysCacheClear` only clears `s_cache_mounted`/`s_cache_path` and deletes no files.
  - VERIFIED: `cellSysCacheMount` always returns 0 (`CELL_SYSCACHE_RET_OK_CLEARED`), even when a cache with that id already exists.
  - VERIFIED: the game calls Mount and then Clear before FIOS opens the files.
  - Documented semantics (SDK/RPCS3 behaviour from memory, not checked against a primary source this session): Clear deletes the cache directory's contents; Mount returns `RET_OK_RELAYED` (1) when the cache is kept.
  - VERIFIED: the `cache.idx` from this cold run, killed at the garage request, also has an all-zero first 512 bytes (only 10,955 bytes are nonzero).
  - VERIFIED: in the cold run the first index read is 64 KiB → 3584 bytes, and it is followed by no reopen loop. In the warm run it is a 512-byte read of a zero header, followed by a reopen about every 50–100 ms.
  - SUPPORTED HYPOTHESIS: the loop is FIOS rejecting a stale index that a killed run left without a valid header. On a PS3, Clear would have removed it, so the cause is the missing deletion in Clear, not a metadata or format incompatibility.
  - NOT TESTED: open flags (not logged); whether a cleanly shut-down run writes a valid header.
  - Not fixed.

## Offline investigation after `av2`: texture race, display regression, audio restarts, FIOS cache (2026-10-22)

The game was not run. Commit `d51122c` (ps3recomp-int). The rebuilt exe `4d6fe7607f47ea79d023268a84f555f063451280b334ede5917c9cd8f019ba6b` is preserved with its map in `build/motorstorm-int-d51122c/`; the `bba5c2a9` exe stays in `build/motorstorm-int-b4d532c/`. `port/main.cpp` received the same beat change; its prior copy is `generated/profile/vblank/port_main.cpp.pre_beat`.

### A. Torn texture uploads
- **What `torn` measures (VERIFIED, code):** `vp_upload_tex_slot` (`libs/video/rsx_d3d12_backend.c`) hashes the guest plane (≥64 KB) before `rsx_texture_decode` copies it to the D3D12 upload heap, and again after the copy and the command recording. A mismatch proves that a guest writer modified those bytes during the CPU staging copy. It does not show which bytes the copy captured. The GPU reads only the upload heap, never guest memory, so GPU reads cannot race.
- **Path (VERIFIED, code):**
  1. The Bink SPU task DMA-writes the Y and chroma planes into guest memory.
  2. The PPU records the draws (texture offsets only) in the FIFO and queues the flip.
  3. The FIFO drain on the frame-clock thread reaches the flip marker (`s_flip_pending`, `s_fifo_flips_reached`).
  4. The frame clock presents: `render_frame` → `vp_upload_tex_slot` copies each plane separately, Y then chroma.
  5. Completion reaches the guest when a guest thread runs `ppu_gcm_pump` (flip status DONE, vblank handler).
- **Defect (VERIFIED, code):** the vblank beat ran `cellGcmTickVBlank`, `cellGcmTickFlip`, and only then the present. A guest pump between those steps saw the flip complete while the textures were still being copied. On the RSX a completed flip means the draws have already sampled them. Because the planes are copied one after another, a decode starting mid-sequence can give Y and chroma from different frames.
- **Evidence (VERIFIED, `av2` log):** torn uploads appeared in 17 of the 23 intro windows that contain 1:1 display and in 0 of the 33 pure 4:1 windows.
- **SUPPORTED HYPOTHESIS:** in 1:1 the player waits for the flip and then decodes into the buffer just shown. Which guest wait releases it (flip status or vblank handler) is not traced.
- **Fix:** `include/ps3emu/frame_beat.h` orders each beat present → vblank → flip done → drain. It is used by the template, `boot_main.cpp` and `port/main.cpp`; it adds no locks or sleeps. `tests/test_frame_beat.c` shows the old order tearing at every one of twelve guest phases and the new order never tearing. The fix is NOT TESTED in game.

### B. Displayed-FPS regression (30.01 → 27.66 decode; 18.1 → 9.4 unique)
- **VERIFIED (code, RESEARCH.md):** Bink's clock is `sys_time` (QPC), not vblank. It skips frames once lateness exceeds 66 ms, at most 3 in a row, and resyncs above 725 ms. The 59.94 Hz vblank change therefore cannot alter skip decisions directly.
- **VERIFIED (arithmetic):** the decode rate sets the displayed rate.
  - At 27.66 decoded/s against 29.97 the player falls behind by ~77 ms each second, so it mostly runs at 4:1 and resyncs about every 9–10 s. About 10 resyncs are expected over the intro; 10 extra port-1 Stop/Start pairs were observed.
  - At 30.01 lateness never reaches 725 ms (lsfwd: 0 resyncs).
  - An 8 % decode loss therefore halves the unique frame rate.
- **VERIFIED (offline benchmark, real intro bitstream, interleaved ×3):**
  - `9b0c120`, the only SPU change between the two exes, is not slower: coefficient decode 4681–4769 vs 4685–4707 ns/call; IDCT 101F8 +2.6 %, F530 −2 %.
  - State hashes are identical (`generated/profile/bench/lsfwd/hard_vs_news.txt`).
- **VERIFIED (thread samples):** the decode thread was 95 % busy in both runs, so decode is CPU-bound and not waiting on the PPU or vblank.
- **Diagnostic overhead:** the extra `torn` hashes run on the present thread, and `PS3_AUDIO_STATS` on the mixer thread. Neither touches the decode thread. Not measured separately.
- **INCONCLUSIVE:** why the host decoded 8 % slower.
  - Mean `cpu_perf_pct` over the intro was 125.6 vs 127.9, with dips to 109 that coincide with the slowest decode blocks (r = 0.35).
  - Background load at launch was 12 % CPU and 15.7 % GPU.
  - lsfwd's 30.01 may be the high end of run-to-run spread (int5: 27.54).
  - One run of each is not enough to separate these.

### C. Audio restarts
- **VERIFIED (code, RESEARCH.md):** above 725 ms lateness, `NextFrame` calls sound pause `0xC6CC40` with argument 0 (→ `cellAudioPortStop`), waits for the IO buffer, resets the epoch and resumes (→ `PortStart`). Each Stop/Start pair is a native Bink resync, caused by the decode deficit in B.
- **Correlation:** in `av2` the pairs fall in alternate 5 s `[astat]` windows (period ~10 s). Each such window has 109–153 empty port-1 blocks (~0.6–0.8 s of silence) while the mixer stays at 187.5 blocks/s with 0 drops.
- **No state-machine defect found:** Start/Stop only set or clear `running`, and a stopped port is neither mixed nor advanced (already covered by `test_audio_mix.c`). No new test.
- **NOT TESTED:** whether a PS3 shows the same gap length; audible correctness.

### D. FIOS cache semantics
- **Reference:** RPCS3 `Emu/Cell/Modules/cellSysCache.cpp` and `cellSysutil.h` (master), read 2026-10-22. This is an HLE reference, not firmware or the SDK, so the semantics are VERIFIED against RPCS3 only.
  - Clear removes the cache directory's contents, keeps the directory, stays mounted, and returns `RET_OK_CLEARED` (0), or `ERROR_NOTMOUNTED` (0x8002BC04).
  - Mount returns `RET_OK_RELAYED` (1) for the cache id already in use and otherwise clears and returns CLEARED. It returns `ERROR_PARAM` (0x8002BC03) for a bad name.
  - A cache still carrying RPCS3's in-progress marker (an interrupted run) is cleared at the next mount. By default (`retain_caches` off) the cache is deleted at shutdown.
  - RPCS3 returns `/dev_hdd1` as the cache path; this runtime returns `/dev_hdd1/cache/<id>`. Not changed.
  - RPCS3's `CellSysCacheParam.getCachePath` is 1055 bytes; the comment here says 136. Harmless, since the path written is short.
- **Fix:** `cellSysCacheClear` and `cellSysCacheMount` follow RPCS3, apart from the retain mode below.
  - Deletion happens only under an explicit `PS3_HDD1_ROOT`, only inside `<root>/cache/<id>` (the id must be one plain path component), never through a symlink or junction, and never in a cache directory that is itself a link.
  - Fonts in the hdd1 root and `original/` are out of reach.
  - Cross-boot retention is not implemented, so every boot is cold, as in the successful `av2` run.
  - `tests/test_syscache_host.c` (44 checks; Linux gcc/clang, Windows with a junction) covers killed-run recovery, fonts and link targets left intact, and id validation.
- **SUPPORTED HYPOTHESIS:** the ~4,000 reopens came from FIOS rejecting the stale index (zero 512-byte header) that the killed run left, which Clear would have removed on a PS3. FIOS's own validation code is not traced, and the zero header is not taken as the format.

### Tests (offline)
- `test_frame_beat` 26/26 and `test_syscache_host` 44/44 on gcc, clang and Windows clang-cl.
- video_stats 24, vblank_clock 17, audio_stats 22, audio_mix 4160 on gcc and clang.
- Tools suite: Windows 87/87; WSL 84/87, where the 3 failures are the known pre-existing ones.
- The template, `port/main.cpp` and `boot_main.cpp` syntax-check clean with clang-cl.
- Audit: only the 25 pre-existing blocks, none involving staged files.

### Is another controlled run justified?
Yes, one, to test the two fixes. Success criteria:
- with a cold cache, `torn` = 0 in 1:1 windows;
- after a second boot over the leftover cache, no reopen loop.

Decode throughput, and therefore the 4:1 display, is unchanged by these fixes. Unique displayed FPS will only rise if decode stays at or above 29.97 frames/s.


## Validation run `beat` (exe `4d6fe760`, commit `d51122c`), 2026-10-22

This was one authorized cold-cache run: `hdd1` held only the two fonts, `hdd0` was empty and there was no `cache/` directory.
- Run directory: `generated/runs/20261022-202127-beat/`.
- Probe outputs: `generated/profile/probe_beat_*`.
- Stopped at the target `garage_resources_requested` at 02:34; the runner exited 0.
- Total runtime about 157 s, below the 210 s limit.
- Thermal zone: 348 K at the start, **peak 352 K** (limit 363 K). No guard trip.
- `original/` is unchanged (`original_before3.json` = `original_after3.json`, eboot `218cd8aa…`).
- No processes were left running afterwards.

| Item | lsfwd | av2 | **beat** |
|---|---|---|---|
| Bink decode (frames/s) | 30.01 | 27.66 | **26.27** |
| Per-256-frame blocks (frames/s) | 29.26–30.97 | 25.60–30.01 | **23.14–29.00** |
| Intro windows (pure 4:1 / mixed) | 53 (18 at 4:1) | 56 (33/23) | **59 (32/27)** |
| Unique frames/s | 18.1 | 9.4 | **8.1** |
| Flips/s | 21.8 | 11.0 | **9.9** |
| Torn: total | not measured | 66 | **44** |
| Torn: mixed windows with any | — | 17 of 23 | **19 of 27** |
| Torn: pure 4:1 windows | — | 0 | **0** |
| Vblank (Hz) | 62.51 | 59.95 | 59.95 |
| Port-1 Stop/Start pairs | 1/1 | 11/11 | **19/20** |
| Garage request | 137.5 s | 145 s | 154 s |
| Peak temperature | 351 K | 355 K | 352 K |

### A. Torn frames: NOT fixed (VERIFIED)
- There were 44 torn uploads, all in 1:1 (mixed) windows, and 0 in pure 4:1 windows. The prediction that the frame-beat reorder would bring `torn` to 0 is falsified.
- Flip ordering is correct (VERIFIED, from ftrace over 60–70 s):
  - There were 83 flip requests and 83 presents, in strict request→present alternation, with no flip lost or doubled.
  - Request→present latency: median 8.0 ms, p90 10.5 ms, max 12.6 ms, so every present lands within one vblank.
  - No `[SEMA-REL]` label release outside offset 0x400 was logged.
- The guest therefore overwrites the buffer while the backend copies it, even though the completion of that flip is no longer visible to the guest yet.
- SUPPORTED HYPOTHESIS: Bink's buffer reuse is not gated by the flip completion that `frame_beat.h` reorders. The backend reads the textures at present, up to about 12 ms after the draw was queued, whereas the RSX samples during the draw. That window is open only when decode keeps pace (1:1).
- The `frame_beat.h` change is harmless and keeps the order correct, but it did not address the tearing.

### B. Decoder throughput
- Overall 26.27 frames/s; per-window mean 26.2 (SD 2.45).
- CPU telemetry during the intro: perf 119.9 % (min 103 %); system CPU 26 %.
- Correlations with per-window decode: r = 0.37 with `cpu_perf_pct`, r = −0.14 with `sys_cpu_pct`. The time mapping was approximate: thermal samples every ~6 s, offset about 2.3 s.
- The three runs give 30.01, 27.66 and 26.27 frames/s. Their block ranges overlap, and lsfwd also had higher perf (127.9 %).
- INCONCLUSIVE: a host-frequency or load effect is weakly supported, and a decoder regression is neither shown nor excluded.

### C. Audio (VERIFIED)
- One `cellAudioInit`, two `PortOpen` calls.
- Port 1 had 19 Stop and 20 Start calls. These are Bink resyncs (a frame more than 725 ms late), up from 11 in av2 and 1 in lsfwd.
- The mixer drift stayed within ±0.8 ms per window and nothing was dropped.
- Over the three runs, resyncs rise as decode falls (1 → 11 → 19 for 30.0 → 27.7 → 26.3 frames/s). This SUPPORTS the conclusion that the audio gaps follow decoder throughput and are not a mixer fault.

### D. FIOS cache
- Mount: id `BLES00000`, logged as cleared. Then `SysCacheClear`, logged as cleared.
- `cache.idx` and `cache.dat` were each opened once. There was no reopen loop.
- The intro opened at 00:29; the garage request came at 02:34.
- Resulting cache: `cache.dat` 548,405,760 bytes; `cache.idx` 1,043,456 bytes, first 512 bytes zero.
- It is kept in place in `generated/hdd1/cache/BLES00000/fios/`, with a copy in `generated/upstream/hdd1_written/beat_cold/`.
- A warm-cache boot over this state is NOT TESTED and needs separate authorization.


## Texture lifetime and Bink throughput (offline, after `beat`), 2026-10-22

No game launch. ps3recomp-int commit `6e4d780`. Exe `build/motorstorm-int/MotorStormPacificRiftRecomp.exe` = `1b7cb3cf894bffaae54c830c2bc51da52adae04f82fdff704820395a0bfefeed`, copied to `build/motorstorm-int-texsnap/`. The `beat` exe is kept in `build/motorstorm-int-d51122c/`.

### A. Texture ownership

**VERIFIED (code, `ps3recomp-int`):**

1. **Draw recording.** Draws are recorded during the FIFO drain. Each record keeps texture offsets only (`rsx_d3d12_backend.c`: `d3d12_draw_arrays` and the indexed paths, then `vp_record_cb`).
2. **Texture reads.** Guest texture bytes are read later, at `render_frame` → `vp_upload_tex_slot`, when the frame is presented.
3. **Signals the drain publishes.** The drain runs on the frame-clock thread (`port/main.cpp` `frame_clock`: every beat, and again after each `Sleep(4)` pass). Before that present, it publishes:
   - `get`;
   - NV406E semaphore releases (`cellGcmSys.c`, ~2069);
   - back-end and texture-read label releases (`rsx_commands.c` `0x1D70`/`0x1D74`);
   - SET_REFERENCE;
   - the flip-marker count (`s_fifo_flips_reached`).
4. **Measured gap.** From `beat` ftrace (60–70 s), flip request → present: median 8.0 ms, maximum 12.6 ms. All 83 flips were presented once, in order.

**VERIFIED (static scan of the game's EBOOT, `generated/analysis/scan_gcm_sema.py`):**

- The game builds back-end label commands (`0x1D6C`/`0x1D70`) only through libgcm helpers `0x735A50`/`0x735AD0` (stubs `0x754E78`/`0x754E88`). Their only callers are two transfer routines, `0x346AD8` and `0x350658`, using labels `0x49`/`0x4A`.
- There is no texture-read release (`0x1D74`) anywhere.
- The Bink library (`0xC5D000`–`0xC74000`) builds no RSX commands.

**SUPPORTED HYPOTHESIS:**

- Nothing in the movie path holds a Bink YUV buffer beyond its draw. The guest reuses the buffer once the RSX is past that draw, so the correct ownership boundary is draw consumption, not flip completion.
- Torn uploads appear only in 1:1 windows: 0 of 32 pure 4:1 windows, against 19 of 27 mixed windows. In those windows a frame is redrawn and the next decode starts right after; in 4:1 the wait for the in-flight decode (~37 ms) hides the gap.

**NOT VERIFIED:**

- The exact guest event Bink or the movie player waits on before `DoFrameAsync` reuses a buffer.
- Whether a direct `get`/REF poll is involved.

### B. Correction (commit `6e4d780`)

- **Mechanism:** `include/ps3emu/tex_snapshot.h`. At record time, before the drain processes any later command, `vp_record_tex_snap` copies each eligible bound texture. The present uploads that copy (`s_tex_src_override` in `vp_upload_tex_slot`).
- **Storage:**
  - Four generations per guest offset, so two frames recorded before one present keep their own bytes.
  - Unchanged bytes cost one hash and no copy.
  - A copy that is recycled before its present falls back to guest memory and is counted as `evicted`.
- **Scope:** `PS3_TEX_SNAPSHOT=1` (the default) covers linear B8/G8B8 textures of 64 KB and up. `2` covers every 2D texture of that size; `0` gives the old behaviour.
- **Unchanged:**
  - RSX command order;
  - the vblank clock;
  - flip/present order (`frame_beat.h`);
  - guest timing (no waits added).
- **Metric:** for captured textures, `torn` now counts guest writes during the record-time copy, i.e. writes that race the RSX's own read.
- **Test:** `tests/test_tex_snapshot.c`, 39 checks.
  - It models a guest that, once the drain publishes the command after the draw, reuses the buffer and writes in chunks interleaved with the present's copy.
  - With the old present-time read, the model tears. With the capture it does not, at any of nine guest phases.
  - It also covers dedupe, generations, eviction and key recycling.
  - Passes on gcc, clang and clang-cl.
  - This is a model; it does not prove the game is correct.

**Remaining gap:** guest `put` → drain, up to one frame-clock pass. A guest that reuses a buffer before the drain has consumed the draw would still race. The RSX would usually have consumed the draw by then.

### C. Decoder throughput (lsfwd 30.01 → av2 27.66 → beat 26.27 frames/s)

| Run | Exe | Commit | Bink SPU code vs previous run | Cache | Diagnostics |
|---|---|---|---|---|---|
| lsfwd | `0194b89e` | `29df355` | — | cold | FTRACE, POLLTOP, VIDEO_STATS |
| av2 | `bba5c2a9` | `b4d532c` | 17 of 47 functions differ, +272 bytes (from `9b0c120`) | cold | + AUDIO_STATS, torn hashing |
| beat | `4d6fe760` | `d51122c` | identical (all 10,864 SPU function sizes match av2) | cold | same as av2 |

- **VERIFIED: host drift on identical code.** The Bink kernel bench (`b_hard`/`b_news`, intro bitstream) was rerun interleaved at 22:27 (`generated/profile/bench/lsfwd/hard_vs_news_rerun.txt`).
  - Coefficient decode: 5,270–5,364 ns/call, against 4,685–4,770 ns for the same binaries in `hard_vs_news.txt` (written 19:52). That is +12.5 % on identical code.
  - A/B difference: < 0.5 %.
  - At the rerun: CPU performance counter 123.7 %, system CPU 21.5 %.

Ranked explanations:

1. **Host-state variability (frequency, power or thermal state, background load).** SUPPORTED.
   - av2 → beat (−5 %) has identical SPU code.
   - The same bench drifts 12.5 % within hours.
   - Earlier probe runs today ranged 27.12–28.79.
   - Smallest test: interleave the kernel bench while logging `% Processor Performance`, temperature and the top CPU processes.
2. **Thread scheduling/contention with the present thread.** Possible.
   - `torn` hashing (b4d532c) adds about 0.1 ms per video present on the frame-clock thread, not on the decoder thread.
   - Smallest test: the kernel bench with one concurrent hashing thread, then with two.
3. **`9b0c120` SPU change.** Unlikely: the isolated bench shows no difference, and av2 → beat drops further with no SPU change.
   - Smallest test: already done (A/B within noise).
4. **Logging overhead.** Unlikely: 4,157 / 4,204 / 4,407 log lines per run, and AUDIO_STATS prints one line every 2 s.
   - Smallest test: the bench with and without `PS3_AUDIO_STATS`/`PS3_VIDEO_STATS` set (hooks only).
5. **Different workload.** Ruled out as stated: the same intro, cold cache in all three, the same EBOOT hash.
6. **Compiler/code generation.** Ruled out for av2 → beat (identical SPU function sizes, same clang 23.1.3). For lsfwd → av2 it is covered by item 3.

**INCONCLUSIVE:** single-run averages cannot separate a code effect smaller than about 10 % from host drift. Any comparison needs interleaved A/B runs under logged host state.

### D. Regression checks

- WSL tools: 84/87 (the 3 known pre-existing failures).
- Windows tools: 87/87.
- C tests:
  - video_stats 24;
  - vblank 17;
  - audio_stats 22;
  - audio_mix 4,160;
  - frame_beat 26;
  - syscache 44;
  - tex_snapshot 39.
- Audit: no blocks on staged files.
- Not run: the game.

### E. Is a run justified?

Yes, one bounded cold-cache run with the `1b7cb3cf` exe, same probe and limits. Success criteria:
- `torn` = 0 in 1:1 windows;
- the flip/present order and the 59.95 Hz vblank unchanged.

Decode throughput will only be comparable if host state is logged and the run is read against variance, not against a single average.


## Validation run `texsnap` (exe `1b7cb3cf`, commit `6e4d780`), 2026-10-22

This was one authorized cold-cache run: `hdd1` held only the two fonts, `hdd0` was empty and there was no `cache/` directory.
- The `beat` state was moved, not deleted, to `generated/upstream/hdd1_written/beat_live/` and `generated/upstream/hdd0_written/beat/`.
- The run used `PS3_TEX_SNAPSHOT=1` and the same probe as `beat` (`generated/profile/probe_texsnap.sh`).
- One addition: `texsnap_sampler.py`, which reads the `s_texsnap` counters read-only via ReadProcessMemory. The exe does not log them. The map RVA is `0x19934950`; offsets come from `scratch/texsnap_off.c`.
- Run directory: `generated/runs/20261022-224618-texsnap/`.
- Stopped at the target `garage_resources_requested` at 02:24 (wall 144.5 s, below the 210 s limit); the runner exited 0.
- Peak thermal zone 349 K (range 346–349 K); no guard trip.
- `original/` is unchanged (`probe_texsnap/original_before.json` = `original_after.json`).
- No processes were left running afterwards.

| Item | lsfwd | av2 | beat | **texsnap** |
|---|---|---|---|---|
| Bink decode, runner (frames/s) | 30.01 | 27.66 | 26.27 | **28.42** |
| Per-256-frame blocks (frames/s) | 29.26–30.97 | 25.60–30.01 | 23.14–29.00 | **26.34–29.95** |
| Intro windows (pure 4:1 / mixed)* | 53 | 56 | 59 (31/28) | **55 (36/19)** |
| Window decode: pure 4:1 / mixed* | — | 28.17 / 26.11 | 27.22 / 24.22 | **28.67 / 26.54** |
| Unique frames/s (window mean) | 18.1 | 9.4 | 8.1 | **10.7** |
| Flips/s | 21.8 | 11.0 | 9.9 | **12.6** |
| Torn uploads (all windows) | not measured | 66 | 44 | **0** |
| Vblank (Hz) | 62.51 | 59.95 | 59.95 | **59.96** |
| Port-1 Stop/Start pairs | 1/1 | 11/11 | 19/20 | **8/8** |
| Mean CPU perf / system CPU (%) | 127.9 / — | — | 118.0 / 27.7 | **126.6 / 28.1** |
| Peak temperature | 351 K | 355 K | 352 K | **349 K** |

\* `generated/profile/vstat_windows.py`; pure 4:1 means `advance` = 4.00 exactly. It reproduces beat's 59 windows and 44 torn uploads, but counts 31/28 against the earlier 32/27.

### A. Texture snapshot (VERIFIED runtime counters, end of run)

| Counter | Value |
|---|---|
| Captures (copies) | 3,609 |
| Unchanged-hash reuses | 501 |
| Fallbacks to guest memory (`evicted`) | 0 |
| Torn captures (guest writes during the capture copy) | 0 |
| Allocation failures | 0 |
| Keys / generations live | 7 / 25 |
| Largest capture | 2,097,152 B |

- **Guest writes during capture:** 0.
- **Guest writes during fallback uploads:** none possible, since there were no fallbacks. The vstat `torn` count for the whole run was 0, including all 19 mixed windows.
- **Generation exhaustion:** 0.
- **Mixed planes and visible corruption:** NOT VERIFIED. No frames were captured or inspected; the hash counters cannot show artifacts.
- A zero `torn` count is necessary but not sufficient for artifact-free playback.
- Cost: mean `present_ms` over the intro was 1.82 against 1.79 in beat. Record-time hash and copy time is not measured separately (it runs in the drain).

### B. Throughput
- Decode was 28.42 frames/s against 26.27 in beat, with no change to decoder code.
- Host state was better than in beat: CPU perf mean 126.6 % against 118.0 %.
- The run therefore does not show any snapshot cost to decode. It also does not show a snapshot gain: the difference is within the host-drift range (VERIFIED +12.5 % on identical bench code).
- The higher unique frames/s and flips/s follow from the faster decode (36 of 55 windows were 4:1).

### C. Timing and audio
- Vblank 59.96 Hz.
- ftrace 60–70 s:
  - 81 flip requests and 80 presents; request→present median 7.6 ms, maximum 12.0 ms.
  - **One request (buffer 1, at 60.863 s) had no present of its own.** The next present came at 61.020 s, after the following request (buffer 0, at 61.014 s).
  - No present was duplicated. Whether the buffer-1 flip was coalesced or reached late is INCONCLUSIVE; beat had 83/83.
- Audio:
  - one `cellAudioInit`, two `PortOpen` calls;
  - port 1: 8 Stop / 8 Start resyncs, against 19/20 in beat;
  - mixer drift −1.1 to +5.1 ms per window, total +4.3 ms, 0 dropped.

### D. FIOS
- SysCache Mount and Clear were both logged as cleared.
- `cache.idx` and `cache.dat` were each opened once; there was no reopen loop.
- The intro opened at 00:28; the garage request came at 02:24.
- Resulting `cache.dat` is 478 MB, against 548 MB at beat's later stop.
- It is kept in place, with a copy in `generated/upstream/hdd1_written/texsnap_cold/`.


## Bink playback scheduler, frame pacing and SPU helpers (offline, after `texsnap`), 2026-10-22

No game launch. Details:
- `docs/BINK_PLAYBACK_SCHEDULER.md` (native logic);
- `docs/BINK_FRAME_PACING_ANALYSIS.md` (timeline);
- `docs/BINK_PERFORMANCE_BACKLOG.md` (ranked work);
- tool `tools/analyze_bink_pacing.py`, test `tools/test_analyze_bink_pacing.py` (14 checks).

**Native frame skipping (VERIFIED NATIVE).**
- `BinkShouldSkip` (`0xC6F088`) skips a frame when lateness exceeds `+0x2C8` (66 ms, i.e. two frames at 29.97 fps), at most 3 in a row (`+0x340`, `cmplwi 2`). That gives a fixed 4:1.
- Lateness = (`RADTimerRead` − epoch) − (frames since epoch × 33.37 ms). The audio position is not involved.
- Above 725 ms, `BinkNextFrame` (`0xC6ED28`) resyncs:
  1. sound pause (`0xC6CC40`, port 1 `PortStop`);
  2. wait for the IO buffer to be 29/32 full;
  3. clear the epoch;
  4. resume (`PortStart`).
- Skipped frames are fully decoded. Skipping never catches up; only decode faster than 29.97 fps, or a resync, ends 4:1.

**Why 28.42 decoded fps shows about 10.5 unique fps (VERIFIED RUNTIME, all four runs).**
- Replaying the rule over the per-present timelines:
  - agrees with the observed 1:1/4:1 mode for 88–96 % of presents;
  - infers exactly as many resyncs as there are audio Stop/Start pairs (texsnap 7, beat 18, av2 10, lsfwd 0).
- Correction: texsnap had 7 resyncs, not 8. Its eighth `PortStop` precedes `PortClose` at the movie's end.
- Catch-up exits happen only in stretches decoding at 30.0–31.5 fps.
- The bottleneck is SPU decode throughput:
  - the Bink SPU thread is 96.6 % busy;
  - all host waiting together is at most about 3.4 % of a frame;
  - present and flip run on another thread while decode N+1 is in flight.

**Missing flip (SUPPORTED HYPOTHESIS).**
- MotorStorm flips through `_cellGcmSetFlipCommand`, but every traced request took the direct fallback (`in_fifo` = 0).
- `frame_clock` presents a pending flip before draining. If the frame's onscreen draws are not drained yet, the D3D12 present skips `Present()` (`has_display` = 0), yet still consumes the flip.
- Observed once in 81 flips (present 1431 covers flips 1393→1395, `new` = 1).
- This is a host ordering defect, not legitimate coalescing. It is too rare to affect pacing. Fix and diagnostics are in the backlog.

**SPU helper change (ps3recomp-int `0eae6a4`).**
- x86 SSE2 forms for 19 plain word ops that were per-lane C loops. Clang had split some of them into scalar halves, written to the register file as 4- or 8-byte stores and re-read as 16-byte loads.
- Partial stores in the five hot Bink groups: 333 → 147.
- Interleaved bench, 8 rounds, real drain, intro bitstream, identical state hashes:
  - coefficient decode −8.1 % (8/8 rounds);
  - IDCT −15.6 % (8/8) and −11.1 % (7/8).
- Estimated frame decode time −6 % or more (SUPPORTED HYPOTHESIS; the in-game effect is not measured).
- Tests (tools 87/87 Windows, 84/87 WSL with the 3 known failures): `test_spu_int_neon.c` (19 ops, now including `shli`/`rotmi`, plain x86-64 too) on gcc, clang and clang-cl, at baseline/SSE4.1/AVX2; `test_spu_helpers.c` 70/70.
- A gcc `-O0` link failure of `test_spu_helpers.c` (`spu_ls_watch_slow`) predates this change.
- Exe: `build/motorstorm-int/MotorStormPacificRiftRecomp.exe` = `dbcec5d6ca2792c5a2cb205c4823de54e4c39d5a0340876309e914a9a708c609`. The texsnap exe is kept in `build/motorstorm-int-texsnap/`.

**Direct-dispatch experiment (not adopted).**
- The coefficient `bi $r4` at LS `0x122D0` reaches 4 targets, 112 times per call.
- Guarded direct transfers gave coef −3.5 %, about 1.3 % of a frame. That is below the risk of bypassing the resolver's ownership rules.

**Is a run justified?** Yes, one bounded cold-cache run of the new exe with the texsnap probe (timeline, ftrace, sampler, thermal guard).
- Read it with `tools/analyze_bink_pacing.py`: decode per stretch, resyncs, catch-ups. Do not read it from the averages.
- Expected (SUPPORTED HYPOTHESIS): average decode about 30–31 fps under texsnap-like host state, with fewer resyncs and more catch-ups (lsfwd-like), but still some 4:1. Full 1:1 needs the register-caching work.

### Validation run `sse2` (exe `dbcec5d6`, commit `0eae6a4`)

One bounded cold-cache run on 2026-10-23, same probe as texsnap: run dir `generated/runs/20261023-062815-sse2`, outputs in `generated/profile/probe_sse2_*`. It stopped at `garage_resources_requested` (2:18), runner exit 0, wall time 138.2 s, no process left. `original/` is unchanged (71 files, eboot `218cd8aa…`). FIOS opened `cache.idx`/`cache.dat` once each. The cache was copied to `generated/upstream/hdd1_written/sse2_cold/`.

**Guard disclosure.** Preflight found the thermal guard's rapid-rise check had never fired: PowerShell unwrapped the one-element history to a scalar. It was fixed (explicit array, 12 s time window) and tested with a dummy process before this run. **texsnap and earlier runs had no working rapid-rise protection**; only the absolute limit was active.

| run | decoded fps (frames 256–3072) | unique fps | 4:1 s | resyncs | lateness max |
|---|---|---|---|---|---|
| lsfwd | 30.01 | 18.1 | – | – | – |
| av2 | 27.66 | 9.4 | – | – | – |
| beat | 26.27 | 8.1 | – | – | – |
| texsnap | 28.42 (intro 27.27) | 10.4 | 89.6 | 7 | ~794 ms |
| **sse2** | **29.97** (intro 28.63; blocks 29.68–30.17) | **27.11** | **6.7** | **0** | 434 ms |

- **Decode.** Over 51 complete 2 s windows: mean 29.97, min 28.69, max 31.31; 25 of 51 windows were ≥ 29.97, none below 28. Once it stops running late, decode is paced by the Bink clock, so 29.97 is a ceiling: headroom above it cannot be measured from fps.
- **Pacing (analyze_bink_pacing).** One skip stretch (25.7–32.4 s, entered at 54 ms lateness, recovered by catch-up); 0 resyncs. The rest is normal cadence: 1:1 for 50.6 s plus the 2-VBlank 30-on-60 pattern ("other") for 52.9 s. Advance histogram: 0:1349, 1:1578, 2:8, 3:1, 4:52. The skip rule agrees on 99.4 % of presents.
- **Snapshot.** 8964 captures, 518 reuses; 0 torn, 0 failed, 0 evicted (premature recycling); 7 keys and 25 generations, at most 2 MB.
- **Audio.** No resync Stop/Start pairs, only the end-of-movie PortStop(1). 0 dropped; total drift +5.1 ms.
- **VBlank and flips.** VBlank 59.94 Hz. 6113 flips and 6153 presents over 137.7 s. In the ftrace window, 390 flip requests produced 390 presents (latency median 7.9 ms, max 15.5 ms).
- **Host.** CPU perf 113–130 % (mean 121 %); system CPU 16–35 % (mean 26 %). Peak 344 K (texsnap: 349 K); the guard never tripped. Bink SPU thread 94 % busy (texsnap 96.6 %). Hottest groups: `000122E8` 16 %, `00010200` 13 %, `00012BB4` 11 %.

**Assessment.** VERIFIED: the run went from repeated 4:1 with 7 resyncs to almost all 1:1 (unique fps 10.4 → 27.1). SUPPORTED HYPOTHESIS: the SSE2 helpers are the cause. Their offline gain (coef −8 %, IDCT −11…−16 %) is enough to cross the ~29.97 threshold from texsnap's 28.4. However, a single run sits inside the ±12.5 % host drift (host perf mean was 121 % here), so this is not proven causally. The margin is thin: the SPU thread is still 94 % busy, one 4:1 stretch remains, and the slowest windows are at 28.7.

**Next.** Backlog #3 (remaining partial `ctx->gpr` stores in the hot groups `000122E8`/`00010200`/`00012BB4`) is the cheap continuation of the same mechanism. #2 (register caching) is the larger step needed for real headroom. Re-measure with a bench first; then, only if authorized, run a paired runtime test to separate the gain from host drift.

**User visual confirmation (2026-10-23).** Most of the intro plays smoothly with no artifacts. Occasional skipping is still visible, sometimes dropping to 30 fps or below. This matches the one remaining 4:1 stretch and the slowest windows (about 28.7 fps). VERIFIED (user): no visual artifacts; residual skipping confirmed.

## Backlog #3: partial / redundant SPU register stores (offline), 2026-10-23

No game launch, no code change, nothing committed. Tools (private): `generated/profile/bench/ps3/dis_stores.py` (store histogram from the disassembly) and `dflow.py` (liveness over the lifted C groups); full disassembly of the SSE2 bench object in `generated/profile/bench/ps3/sse_all.dis`.

**VERIFIED (static).**
- **Partial stores into `ctx->gpr`.** The three hottest groups (`122E8`, `12BB4`, `10200`) and `F530` / `12108` have **0**. The pre-SSE2 build had 120 `movl` in `122E8` + `12BB4` alone. The remaining narrow stores in those groups go to context fields above the register file (`0x40800+`: ls pointer, pc), once per entry or exit.
- Elsewhere: `CB40` 16 `movw` (two `shlhi` sites to r95 that clang scalarised), `8708` 16 `movb` (one `ceqbi` to r79), and 2–4 `vpmaskmovd` per group. The earlier "147 remaining" figure counted with a different (unrecorded) criterion and does not reproduce; this count supersedes it.
- **Redundant full stores.** Data-flow over the lifted C finds **0 dead register definitions** in all eight hot groups, both as compiled and if chain exits wrote back lazily. Every store is either read later or live at a guest-visible exit. Asm stores ≈ lifted definitions (`12BB4` 236 / 238, `122E8` 462 / 471).

**Not done, and why.**
- No variant exists to benchmark: the three target groups have nothing left to remove.
- An SSE2 `shlhi` / `ceqbi` would touch three sites in groups the bench does not cover (`CB40`, `8708`), with an estimated ≤ 0.3 % of frame decode. That is below the bench's resolution, so it cannot show a reproducible benefit, and it was not implemented.
- No tests were run because nothing changed.

**Conclusion.** #3 cannot provide the 5–10 % target. The register-file cost that remains is that registers live in memory (15–20 % of hot-group instructions are `ctx->gpr` loads/stores), which is #2. The plan with validation gates is in `docs/BINK_PERFORMANCE_BACKLOG.md`, "Plan for #2". Its first gate is a bench-only prototype (no lifter change) that must show ≥ 8 % on both the coef and IDCT kernels before any lifter work.

## Backlog #2, Gate 1: bench-only SPU register caching (offline), 2026-10-23

**Result: FAILED the gate (coef regresses). Gate 2 not recommended. No game launch, no lifter/runtime change, nothing committed.**

**Prototype (private, `generated/profile/bench/ibr/`).** `regcache.py` rewrites the bench copy of the five groups (`F530`, `10200`, `12108`, `122E8`, `12BB4`) so SPU registers are `u128 rN` locals:
- On every exit (SPU_CHAIN not-OK, SPU_CHAIN_BACK budget, cross-group branch, indirect branch, SPU_RET, stop), the prototype first writes back each register that may have been defined since entry (forward may-def).
- The LS diagnostic gate (`_spu_lsd != 0`) runs the unmodified group, so the diag paths see an exact `ctx->gpr`.
- Three load strategies were tried:
  - `rca`: load all registers at entry;
  - `rcl`: per-entry liveness loads, with may-def unioned over entries;
  - `rcc`: the body cloned per entry, so the load and write-back sets are exact for that entry.
- `rci` caches only the two IDCT groups.
- `bench.c` gained `BENCH_CHAIN=0|1`, which forces chaining before every call.

**Correctness (VERIFIED).** Every variant reproduces `trace=B44D3D70 ls=A664900C`, IDCT `B61EC94F` / `93B5C2E7`, and identical step counts (1422385 / 4353 / 3219) in all of these modes:
- default;
- chaining forced off (every chain edge takes its write-back exit);
- chaining forced on;
- `SPU_CHAIN_BUDGET=2` (budget exhaustion).

The trace hashes the full 128-register file, the coefficient output and pc after each of the 1800 calls, then all of LS.

**Performance (`ab_rc.txt`, 8 interleaved rounds, peak 338 K, one distinct state).** Improvement vs. SSE2; positive means faster.

| Variant | coef | IDCT 101F8 | IDCT F530 |
|---|---|---|---|
| `rcl` | −63.1 % median (sd 1.5), 0/8 faster | +12.9 % (sd 1.3), 8/8 | +14.5 % (sd 5.7), 8/8 |
| `rcc` (exact per entry) | −56.6 % (sd 2.4), 0/8 | +12.9 % (sd 2.5), 8/8 | +13.6 % (sd 3.6), 8/8 |
| `rci` (IDCT only) | −0.9 % (sd 0.7), 1/8 | +10.4 % (sd 2.5), 8/8 | +13.8 % (sd 2.6), 8/8 |

Per-round values, medians and CVs: `ab_stats.py ab_rc.txt`. Baseline medians: coef 5012 ns/call, 101F8 1296 ns/block, F530 1157 ns/block.

**Code metrics (`objmetrics.py`, static, hot and cold paths together).**

| Group | Variant | Instructions | `gpr` ld / st | Spill st / ld | Frame |
|---|---|---:|---:|---:|---:|
| `10200` | sse | 3341 | 449 / 409 | 87 / 78 | 0x158 |
| `10200` | rcl | 4221 | 596 / 848 | 605 / 654 | 0x698 |
| `12BB4` | sse | 1973 | 202 / 261 | 20 / 9 | 0xB8 |
| `12BB4` | rcl | 5024 | 871 / 1162 | 741 / 712 | 0x568 |
| `12BB4` | rcc | 16573 | 694 / 5552 | 1376 / 3689 | 0x5F8 |
| `122E8` | sse | 5574 | 602 / 559 | 70 / 26 | 0xC0 |
| `122E8` | rcl | 19620 | 3978 / 5164 | 2926 / 3149 | 0x788 |
| `122E8` | rcc | 94362 | 3803 / 36255 | 6523 / 23053 | 0x7E8 |

Write-back per exit averages 37–71 registers; entry loads average 23–53 registers (`rcc`–`rcl`).

**Why coef loses (VERIFIED by the metrics; mechanism SUPPORTED).**
- The coefficient handlers are short straight-line runs between group entries and exits. Each register is defined about once per path, and a decode call enters and leaves groups many times (about 790 steps per call).
- Caching therefore cannot remove stores there: every definition still has to be written back at the exit. It does add spill traffic: 69–79 live `u128` values against 16 XMM registers, with frames of 0x568–0x7E8 bytes. A write-back from a spill slot costs a load plus a store, where the original had one store.
- The IDCT groups loop internally with redefinitions, so there the saved stores outweigh the spills.

**Whole-frame estimate** (shares from the texsnap profile: coef groups 35.9 %, IDCT groups 22.5 %):
- full caching (`rcc`): about −18 % of frame decode, a regression;
- IDCT-only (`rci`): about +2.5 % (+0.3 to +0.4 from IDCT minus about 0.3 from coef × share). That is below the 5–10 % target and was measured on the bench only.

**Conclusion.** Register caching as a group-wide transformation is not justified. A selective variant (caching only loop bodies, or only groups whose may-def write-back is much smaller than their executed definitions) could keep about +2.5 %. That is within reach of other backlog items, and it would need its own heuristic in the lifter. Not pursued without review.

## Open intro-completion blocker: no audible audio output (added 2026-10-23)

**Status: UNRESOLVED, BLOCKER for calling the intro complete.**
- The user reports the intro plays without audible sound.
- What the logs show (VERIFIED): `cellAudio` init, Bink audio port 1 Start/Stop, `[astat]` block counts at about 187.5 blocks/s, and 0 audio resyncs in `sse2`.
- What they do not show: that PCM reaches the Windows audio device. Block counters measure the guest ring and the WASAPI pacing loop, not the samples written to the endpoint, their level, or whether the endpoint renders them.
- Not yet checked:
  - non-silent sample content (peak/RMS) at the point the mixer hands buffers to WASAPI;
  - which endpoint and format were opened, and whether the stream was started;
  - `GetCurrentPadding`/`ReleaseBuffer` results and any silent-flag use;
  - session volume/mute;
  - big-endian float conversion and port level (always 1.0).
- Next step (offline first): a host-side test that renders a known tone through the runtime mixer to the default device, plus a `PS3_AUDIO_STATS` extension that logs per-5 s peak/RMS of what is actually submitted. No game launch needed for the first part.


## SPU cross-group dispatch (2026-10-23, ps3recomp-int `6637de6`)

- ps3recomp-int: `spu_lifter.py --chain-indirect --image-id N` (group-local dispatch of computed `bi` over the group's own chunk starts, guarded by `SPU_CHAIN_IND_OK`) and `--join-groups`. Per-image lifter args are passed through `PS3RECOMP_SPU_LIFTER_IMAGE_ARGS`.
- The default output is byte-identical (all 26 images compared). The kill switch is `SPU_NO_CHAIN_IND=1`. Local dispatch is off under resolver diagnostics and after any taskset task registration.
- Bink bench: coef −13.7 % (8/8 rounds), IDCT not slower, hashes identical in every mode.
- Tests:
  - `test_spu_chain.c`: third lift, dispatch and joined-return fixtures, guard unit tests; 353 checks; 9 mutants caught;
  - `test_spu_chain_chunks.py`: 10 tests;
  - tools suites: Windows 87/87, WSL 84/87 (the known 3).
- Whole-frame estimate 3–5.5 % (ESTIMATED). No game run yet. Details: `SPU_DISPATCH_OPTIMIZATION.md`.

### Validation run `ind` (exe `453e2a16`, commit `6637de6`, 2026-10-23)

**Gate before launch.** Offline coverage of all six local-dispatch sites (`generated/profile/bench/ibr/`, `sitecov.py`, `sitecov_main.c`, `mut_sitecov.cmd`):
- static checks 6/6 sites, 0 failed;
- harness 38 891 checks passed, 0 failed (544 landings, 7207 fallbacks), covering every guard condition and the budget boundary (budget 2 lands, budget 1 falls back);
- all 6 mutants caught;
- bench real execution: identical state hashes. Sites 3 and 4 ran 202 128 and 17 344 hits, and their 316 and 28 fallbacks were all budget exhaustion. Sites 0, 1, 2 and 5 were not executed by the bench and are covered only by the static checks and the harness.

**Run.** One authorized cold-cache run with the same probe as `sse2`:
- run dir `generated/runs/20261023-084212-ind`, outputs `generated/profile/probe_ind_*`;
- exe sha256 `453e2a16…dffc65`, checked against the preserved `build/motorstorm-int-6637de6/` before launch;
- stopped at `garage_resources_requested` (2:18), runner exit 0, wall 139.0 s, no game, guard or sampler process left;
- `original/` unchanged (82 entries, eboot `218cd8aa…`, `probe_ind/original_{before,after}.json`);
- FIOS opened `cache.idx` and `cache.dat` once each;
- cache preserved in `generated/upstream/hdd1_written/ind_cold/` and `hdd0_written/ind/`.

All values below are MEASURED unless marked.

| run | decoded fps (frames 256–3072) | unique fps | 4:1 s | resyncs | lateness max |
|---|---|---|---|---|---|
| sse2 | 29.97 (intro 28.63; blocks 29.68–30.17) | 27.11 | 6.7 | 0 | 434 ms |
| **ind** | **29.90** (intro 28.62; blocks 29.20–30.40) | **27.02** | **6.0** | **0** | 429 ms |

- **Decode.** 52 complete 2 s windows: mean 29.98, min 28.05, max 31.88. 23 of 52 windows were ≥ 29.97 (sse2: 25 of 51) and 3 were below 29 (sse2: 4). The slowest were 28.05, 28.66, 28.95 and 29.04.
- **Pacing.**
  - Two skip stretches: 45.6–47.2 s (entered at 51 ms lateness) and 100.3–103.6 s (72 ms), both recovered by catch-up. sse2 had one, lasting 6.7 s.
  - 0 resyncs.
  - Modes: 1:1 53.0 s, other 51.2 s.
  - Advance histogram: 0:1254, 1:1657, 2:13, 3:5, 4:50 (sse2: 0:1349, 1:1578, 2:8, 3:1, 4:52).
  - The skip rule agrees on 98.7 % of presents.
- **Snapshot.** 8937 captures, 502 reuses; 0 torn, 0 failed, 0 evicted; 7 keys and 25 generations, at most 2 MB. The vstat torn count was 0.
- **Audio.** One PortStart(1) and only the end-of-movie PortStop(1), so no resync pairs. 0 dropped; drift −0.7…+4.7 ms. This shows port activity only, not audible audio.
- **VBlank and flips.**
  - VBlank 59.95 Hz.
  - ftrace: 460 flip requests and 459 presents (latency median 7.4 ms, max 12.9 ms).
  - One request at 67.856 s had no present of its own; the next present came 41 ms later. This is the same class as the open "possible missing present" item.
- **Host.**
  - CPU perf 95–134 %, mean 108 % (sse2: 121 %); system CPU mean 36 % (sse2: 26 %).
  - Peak 353 K (idle about 348 K); the guard never tripped.
  - The Bink SPU thread was 95 % busy.
  - The fused `00012108` group took 35.3 %. In sse2, `12108`, `122E8` and `12BB4` together took 32.1 %. The share is not comparable across different host clocks.

**Assessment.**
- VERIFIED in game: no regression in correctness, with 0 torn, 0 resyncs and the same pacing class as sse2.
- NOT MEASURABLE: the expected gain (ESTIMATED 3–5.5 % of frame decode) is below the run-to-run noise.
  - Host perf was about 11 % lower than in sse2.
  - Decode is capped by the Bink clock at 29.97.
  - Decoded and unique fps match sse2 within 0.3 %.
- A paired or interleaved comparison (sse2 vs ind under one host state) would be needed to resolve it. That was not authorized and was not run.
- Visual artifacts: pending user confirmation.

## Intro audio: root cause and fix, offline (2026-10-23, ps3recomp-int `8b62438`)

**Status: the silent-intro blocker stays OPEN until the user hears the intro.**

- **Root cause (VERIFIED).** No Windows audio device was ever opened.
  - `tools/motorstorm_milestones.json` set `FIRST_FRAME_AUDIO=silent` for every runner launch (all 20 manifests), so `cellAudioInit` took the clock-paced null sink.
  - Guest audio did run through the mixer: Bink port 1 (2 ch, 16 blocks) was 100 % filled, and mixed blocks were non-silent through the intro.
  - Zero resyncs were therefore never evidence of output.
- **Second defect (VERIFIED from the game binary).** `cellAudioOutGetDeviceInfo` wrote its modes at +6 + 4k, but the game reads them at +8 + 8k. The game found no mode, printed "CAN'T FIND A SUPPORTED AUDIO RESOLUTION" and skipped `cellAudioOutConfigure`.
- **Changes.**
  - Runner: `FIRST_FRAME_AUDIO=native`.
  - `8b62438`: avconf layout fix; `PS3_AUDIO_STATS` port, mix and device levels and device state; WASAPI `Start`/`GetBuffer`/`ReleaseBuffer` checks.
- **Tests.**
  - New avconf test, which fails on the old code.
  - Stats test: 32 checks. Mixer test: 4166 checks.
  - Host WASAPI tone test: PASS, 29 184 frames accepted at −34.4 dBFS, 0 errors.
  - `tools/test_*.py`: Windows 87/87, WSL 84/87 (the known 3).
- Details: `PS3_AUDIO_PIPELINE.md`, `PS3_AUDIO_FAILURE_ANALYSIS.md`, `PS3_AUDIO_IMPLEMENTATION.md` (including the validation plan).
- **NOT TESTED in game:** guest PCM level, device submission, audibility, and the effect of a valid audio-out mode (`cellAudioOutConfigure` plus the game's 1 s wait).
- Exe: `build/motorstorm-int` rebuilt from `8b62438`, sha256 `611ad702…969ba8` (copy in `build/motorstorm-int-8b62438/`); Bink lift unchanged. Not launched.

### Audio validation run `20261023-100017-audio` (exe 611ad702…969ba8, ps3recomp-int 8b62438, FIRST_FRAME_AUDIO=native)
- VERIFIED: intro soundtrack audible (user). WASAPI shared 48 kHz 2 ch f32 on the default endpoint; dev frames ≈48 000/s, err=0, drift < 20 ms, 0 dropped. No avconf banner; `AudioOutConfigure` ok; Bink now opens an **8 ch** port 1. p1 rms −14.9…−20 dBFS, nonfinite=0; device rms = mix rms. 8→2 downmix clips (up to 450 samples/window, 10 windows).
- REGRESSION (cause unknown): video stopped at decoded frame 2255 (~104 s; `ind` reached 3160), presents stopped, 26 guest `GcKernel::Present() Timeout` (last RSX reference 2526), p1 fill fell to ~2 % with no PortStop. Garage not requested; runner timeout at 210 s. Peak 355 K. `sse2`/`ind`: 0 timeouts.
- Warm caches moved to `generated/upstream/hdd1_written/pre_audio_warm/`, `hdd0_written/pre_audio/`.

## Menu milestone, offline (2026-10-23) — no launch

**Earliest blocker (native audio): OPEN, cause unknown.**
- Run `20261023-100017-audio` stopped at the **210 s timeout**.
- Bink video froze at **frame 2255 of ~3160**.
- The guest logged **26 `GcKernel::Present() Timeout!` GPU-watchdog errors**: RSX GET stuck at `0x11068`, last reference 2526.
- The garage was never requested.
- This is the earliest observed blocker with native audio. Silent-audio runs (`sse2`/`ind`) had 0 timeouts and reached the garage request.
- Native audio stays on. A silent run would be a diagnostic only, not a workaround.

**Deferred, not part of this milestone:** intro performance work, namely:
- decode at ~1/4 speed;
- lower FPS and stutter;
- 8→2 downmix clipping (up to 450 samples per window).

Audio and video implementations are unchanged.

**Changes:**
- **Runner** (ps3recomp-int, see `docs/STARTUP_RUNNER.md`):
  - `fd_event` milestones;
  - `extended` milestones needing `--allow-extended`;
  - `--stop-after-next`, `--stop-on-fatal`;
  - per-milestone `since_prev_s`/fd/caller/result.
- **`tools/fast_startup.py`:**
  - the default target is now the garage request, with a 210 s cap;
  - targets past the garage need `--allow-extended`;
  - imports the runner from `ps3recomp-int`.
- **`tools/psarc_read_map.py`:** maps `[fsread]` offsets to PSARC members (read-only).
- **Thermal guard v2** (fail-closed) passes 10 offline cases. Idle sensor 347–349 K.

**Proposed** (not installed, needs approval): `generated/profile/motorstorm_milestones.proposed.json`.

**Docs:**
- `POST_INTRO_TRANSITION.md`: guest handler addresses.
- `GARAGE_LOADING_PROGRESS.md`
- `MENU_INITIALIZATION.md`
- `MENU_MILESTONE_PLAN.md`: proposed runs; none executed.

## Optional thermal monitor, mandatory run safeguards, frame-clock watchdog (offline, 2026-10-23)

- **Decision:** software thermal monitoring is optional and off by default.
  - `fast_startup.py --thermal-guard` enables guard v3 through `tools/thermal_supervisor.py`.
  - Without the flag nothing is imported or polled, and a missing ACPI sensor cannot block
    a run.
  - Ordinary thermal protection is left to the hardware, firmware and Windows. ACPI TZ01
    is not identified as a CPU or GPU sensor.
  - See `docs/THERMAL_GUARD_RUNTIME_VALIDATION.md`.
- **Mandatory regardless of the monitor:**
  - 210 s cap;
  - hard deadline at timeout + 15 s, which kills the tree;
  - stop at the first `GcKernel::Present() Timeout` (the GPU watchdog);
  - process-tree kill;
  - default garage-request stop, with `--allow-extended` opt-in;
  - `--retries` / `--retry-before` refused;
  - no evidence deleted.
- **ps3recomp-int runner changes:**
  - `--stop-on-line REGEX`: a config-independent stop, reason `stop_line`.
  - On Windows the stop kills the tree with `taskkill /PID /T /F` (`terminate()` orphaned
    children).
  - Tests: `test_startup_runner.py` 22/22.
- **Proposed config validation** (`generated/profile/validate_proposed_config.py`, all 21
  saved runs replayed):
  - the stop line fires only in `20261023-100017-audio`;
  - no fatal or stop-line match in the other 20;
  - the default target is reached in the 14 runs that requested the garage.

  `intro_video_closed` / `garage_archive_read` never fire without
  `FS_CALLER` / `PS3_FSLOG_READS` logs. The live config is unchanged and the proposed one
  still needs approval. It is not needed for the next run.
- **Frame-clock watchdog** (`PS3_FC_WATCHDOG_MS`, off by default) is built in. The exe is
  `f25903bca47a32a13820d42f5f1dcab70fccf712e4c8ff8b7ab977ff390f7cb8`
  (`build/motorstorm-int-fcw-f25903bc/`). The previous `611ad702…` is kept.
- **Synchronization review:** no verified defect. The four unlogged blocking candidates are
  listed in `docs/NATIVE_AUDIO_STARTUP_REGRESSION.md`. The next run is in
  `docs/NEXT_SAFE_RUNTIME_EXPERIMENT.md` (not run).
- **Tests:**
  - Windows `ps3recomp-int/tools/test_*.py`: 87/87.
  - Private: `test_fast_startup_safety` 19/19, `test_thermal_supervisor` 11/11, PSARC 5/5,
    frontend 8/8, audit 5/5, overlays 1/1.
  - Thermal guard v2 script: ALL PASS.
  - Frame-clock watchdog: PASS.
  - WASAPI output (Windows): PASS.
  - WSL tools: 84/87. The 3 failures are the known inherited ones.
  - WSL C suites: all PASS, including audio mix, audio stats, audio ring and frame beat.
- **No MotorStorm launch.**

## Garage resource loading, offline (2026-10-23, ps3recomp-int `2f6c7cf`)

No launch. Details are in these docs:
- `GARAGE_RESOURCE_LOADING_ANALYSIS.md`
- `PSARC_GARAGE_RESOURCE_MAP.md`
- `FIOS_CACHE_BEHAVIOR.md`
- `GARAGE_RUNTIME_DIAGNOSTICS.md`
- `NEXT_GARAGE_VALIDATION_RUN.md`

### Findings

- **VERIFIED:** the first garage request (`track_garage_ain_objects.rpk`, `cellFsOpen` → ENOENT)
  is a loose-file probe for a file that exists neither on the disc tree nor in `MS2.PSARC`. The
  same is true of `_cps`/`_gan_objects`, `track_garage.{jump,bin,spvs,gvl}`, `default.gags` and
  `default.race`.
- **VERIFIED:** before that probe the game had already sought to:
  - `/gui/loadscreen-garage.gui` (right after the intro closed);
  - `guiloading.rpk`;
  - `/worlds/track_garage.rpk`;
  - the garage sky package.

  After it, the game went on to `screenrush.xml`, `post.rpk` and audio members. Every seek lands on
  a member start from the archive TOC.
- **VERIFIED (offline):** every listed garage member decompresses to its TOC size. The name MD5s
  match.
- **VERIFIED:** the cache shrink (480 → 30 MB) is the cold-cache-per-boot behaviour introduced in
  `d51122c`, not a fault.
- **Defect (diagnostic only, fixed):** `[fsread] pos` came from `ftell`, which is 32-bit on
  Windows, so it read -1 past 2 GiB. Mutation-checked: the new check fails on the old code.

### Changes

- **`ppu_fs.cpp`:**
  - 64-bit `[fsread]` position plus `t_ms`;
  - 64-bit `PS3_FSLOG_EOF` limit;
  - `open FAIL` adds errno and, with `FS_CALLER`, the caller.
- **`startup_runner`:** `span_read` milestones.
- **Private:**
  - `motorstorm_milestones.garage.proposed.json` (not live);
  - `generated/analysis/garage_seek_map.py` and `psarc_member_verify.py`.

### Tests

| Suite | Result |
|---|---|
| `test_fs_large_file` | Windows clang++, WSL gcc and clang: PASS |
| `test_startup_runner` | 25/25 |
| ps3recomp-int tools | Windows 87/87; WSL 84/87 (the same 3 known failures) |
| Private: `fast_startup` safety, PSARC read map, frontend, audit, thermal, Bink pacing, overlays | PASS |
| `pad_trigger` | 6941 checks plus getdata: PASS |
| Audit | the 25 inherited blocks only, none in the staged files |

### Build and next run

The exe is `8bc4932e9a9e87c9ae2a6c8e795d2d19b6133b1361b9dc2211f541ed217c044f`, in
`build/motorstorm-int-garage-8bc4932e/`. Not run. The next run (`NEXT_GARAGE_VALIDATION_RUN.md`)
needs authorization.

## 2026-10-23: RSX/shader diagnostics for the garage render stage (ps3recomp-int `dadfcaa`)

No MotorStorm launch.
Docs:
- `GARAGE_RENDERING_PIPELINE.md`
- `WHITE_TO_BLACK_INVESTIGATION.md`
- `RSX_FRAME_CAPTURE_PLAN.md`
- `FRONTEND_RENDER_MILESTONES.md`
- `NEXT_GARAGE_RENDER_VALIDATION.md`

### Findings (offline)

- **VERIFIED (source):** `[CUBE] fp=` is printed while the HLSL is patched, before `D3DCompile`. The old milestone `garage_rendering_started` named a translation attempt. It is replaced in the proposed v3 config.
- **VERIFIED (logs):** no decompile, compile or PSO failure in the 2026-10-21 run or the garage-read run.
- **VERIFIED (frames 24–30 of `menu-long-20261021`):** the white-out is one scalar gain per frame, equal in R, G and B (×2.72 / 2.72 / 2.73, then ×1.63 / 1.62 / 1.63), converging. Black stays black. Frames 31–34 are exactly 0.
  - Eliminated for the ramp: gamma, channel/format mismatch, RT garbage, sampling.
  - Leading (open): exposure feedback.
- **VERIFIED:** the game issues ZPASS `GET_REPORT`s into main memory from boot. The walker always answers `0xFFFF`. This is a new candidate feedback source.

### Changes (`dadfcaa`)

- `RSX_SHADER_TRACE` (bounded, off by default):
  - `translated`, `translate_fail`;
  - `compile_fail`;
  - `pso_fail`, `pso_ready`;
  - `bound`, `fallback`.
- `RSXI_MAX_MB`: a total snapshot cap.
- A failed `Present` is logged.
- `RSX_REPORT_TRACE`.
- Private: `generated/profile/motorstorm_milestones.render.proposed.json` (not live) and `test_render_milestones.py`.

### Tests

| Suite | Result |
|---|---|
| ps3recomp-int tools, Windows | 89/89 |
| ps3recomp-int tools, WSL | 86/89 (the same 3 known failures) |
| New: `test_d3d12_shader_trace` | 17 checks, WSL with C harness; Windows source checks, harness SKIP with no `cc` |
| New: `test_gcm_report_trace` | on/off PASS; mutation (no dedupe) fails |
| `test_d3d12_rsxi_hooks` | PASS |
| Private | `fast_startup` safety, PSARC map, frontend, audit, thermal, Bink pacing, overlays: PASS |
| `render_milestones` | 14/14 |
| `pad_trigger` / getdata | ok |
| `fs_large_file` | PASS |
| Audit | the 25 inherited blocks only, none in the staged files |

### Build

The exe is `8baed0493510ded2a04988dacb9df3a59b577d4d609d2e118ca1963f66dde9e4`, in
`build/motorstorm-int-render-8baed049/`. Not run. The next run (`NEXT_GARAGE_RENDER_VALIDATION.md`)
needs authorization.

## Blend state, presentation stall and frame gain (ps3recomp-int `c874771`, 2026-10-23)

Offline, from the garage-render run `20261023-150148`. MotorStorm was not launched.

### Changes

- **Fix:** D3D12 `vp_get_vs` sets `rsx_vp_set_branch_base` to the program's start slot before decompiling. Branching vertex programs at non-zero slots took wrong targets. `tools/test_vp_branch_base.py` fails on `dadfcaa`.
- **`PS3_PRESENT_PROGRESS_MS`** (header-only `include/ps3emu/present_progress.h`, off by default, bounded). Hooks:
  - `cellGcmSys.c`: flips, drain `get` progress, the poll;
  - `rsx_d3d12_backend.c`: replay, Present, four present-gate reasons, batch fill;
  - `ppu_fs.cpp`: reads;
  - `spu_workload.c`: dispatches.
- **RSXI:** per-draw `vp_consts` (`RSXI_VP_CONSTS`, default 32), and `vshader` events with `shaders/vp_<hash>.hlsl`. Vertex ucode is kept only while `RSXI` is set. `rsx_inspect.py` accepts `vshader`.
- **`tools/rsxi_frame_gain.py`**: tells a scalar gain from blend accumulation. Test: `test_rsxi_frame_gain.py`.
- **`tools/test_d3d12_blend_state.py`**: blend decoding and translation.

### Findings (details in the docs listed)

- `0x0122418B` is the D3D12 key: colour `SRC_ALPHA`/`INV_SRC_ALPHA`/`ADD`, alpha `INV_DEST_ALPHA`/`ONE`/`ADD`. The translation matches RSX; no defect. Gap: `SET_BLEND_COLOR` is not implemented. (`RSX_BLEND_STATE_INVESTIGATION.md`)
- The brightening is a pre-store gain, linear in frames (×1.104, ×1.208), not accumulation. The varying input must come from the vertex stage. (`LOADING_SCREEN_FRAME_ACCUMULATION.md`)
- Presents stop when `AsyncRenderThread` exits (45.8 s). The drain still decodes commands, and replays stop. The clear-driven present policy in `rsx_d3d12_backend_present` / `d3d12_clear` can swallow flips; not proven, so not changed. (`PRESENTATION_STALL_ANALYSIS.md`)
- The PSARC walk is FIOS cache population. `garage_sky_read_complete` was completed by the walk. (`FIOS_SEQUENTIAL_READ_ANALYSIS.md`)

### Tests

| Suite | Result |
|---|---|
| ps3recomp-int tools, Windows | 93/93 (C harnesses SKIP with no `cc`) |
| ps3recomp-int tools, WSL | 90/93 (the 3 known: `test_loaded_image_memory`, `test_sail_boot_callback`, `test_sysmodule_unload_module_ex`) |
| New | `test_present_progress` (20 harness + 14 source), `test_d3d12_blend_state` (12 harness + 5 source and build), `test_vp_branch_base` (6), `test_rsxi_frame_gain` (8) |
| Private | `fast_startup` safety, frontend, PSARC map, audit, thermal, Bink pacing, overlays, `render_milestones` 14/14: PASS. The 4 LFQueue validators need log arguments, as before. |
| Audit | the 25 inherited blocks only, none in the staged files |

### Build

The exe is `be870473cc6070510838e0c6bfe11ad4fa1405555c33137c7a4fd2cbbe2749d9`, in
`build/motorstorm-int-present-be870473/`. Not run. The next run (`NEXT_RENDER_DIAGNOSTIC_RUN.md`) needs authorization.

## ps3recomp-int `25cbff4`: presentation gate (2026-10-23)

Upstream candidates (title-agnostic):

- **`include/ps3emu/present_gate.h`** (new, header-only):
  - the D3D12 flip/clear frame-boundary policy, moved out of `rsx_d3d12_backend.c`;
  - new rule: after `PG_CLEAR_LAPSE_FLIPS` (2) flips with no display colour clear, the ticker presents at the flip again; a display colour clear re-arms clear mode.
  - Fixes titles whose renderer stops colour-clearing the display after the first clear-boundary present; previously they were never presented again.
- **`rsx_d3d12_backend.c`:**
  - `batch_room()` at all 6 record sites;
  - batch-full drops are counted and reported (`[d3d12] batch full`, powers of two);
  - `MAX_DRAWS` is unchanged.
- **`present_progress.h`:** new `flip_presents=` and `dropped=` fields.
- **`rsx_commands.c`:** `RSX_VPC_WATCH=<slot>` / `RSX_VPC_WATCH_MAX`, off by default.
- **Tests:**
  - `tools/test_present_gate.py` with `libs/video/tests/test_present_gate.c` (the policy against synthetic RSX sequences, old against new);
  - `tools/test_vpc_watch.py`;
  - `test_present_progress` updated.

**Upstream risk:** a title that colour-clears its display less often than every second flip, and whose drain runs past flips, gets ticker presents between its clears. Run each port's own visual check before merging.

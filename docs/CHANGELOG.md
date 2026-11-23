# Changelog

## 2026-11-23 launcher 0.2.0 (alpha release)

- Launcher version 0.2.0 (`launcher/electron/package.json`; the earlier README said 0.1.0). Portable `MotorStormPacificRift.exe`.
- Install needs only the disc's decrypted 1.00 `EBOOT.elf`; the 1.03 build is gone.
- Source snapshot (`source_bundles.js`): ps3recomp-vkgame's working tree (tracked plus untracked, non-ignored files) instead of `git archive HEAD`, so uncommitted runtime changes ship; `--runtime-head` keeps the old behaviour. New folders: `tools/` (`build_spu_overlay.py` for the overlays step) and `cockpit-tool/` (`tools/cockpit`: the cockpit camera tool and `cockpit_positions.default.json`, camera offsets only). `npm run dist` and `npm run bundles` pass `--with-pcmenu`, so the PC Settings page tool ships.
- Lift (`launcher/pipeline/lift_motorstorm.py`): the 1.00 lift now also applies the hook patches the port's features call (`PATCHES_100`: task slice, camera rate and shake, distances/LOD, Cheats, the in-game PC Settings pages, cockpit tuning). Before, launcher builds had none of them.
- Cockpit step: bakes the shipped positions, with the player's own `play\cockpit_positions.json` (F2) on top; that file is only read, never overwritten.
- Defaults: frame rate 30 FPS (above 30 experimental); upscaler FSR 1 in the exe as in the launcher (`pc_settings.h` was FSR 3.1).
- Settings: Lighting (Original/Enhanced), level of detail, PBR materials, button prompts, racing wheel rows, Cheats tab (unlock vehicles, unlock Free Play tracks). Ray-traced shadows are not offered.
- Known issues: 60 FPS camera and shadow artefacts; the garage vehicle-edit screen may be blank; Festival and Time Trial lists are not unlocked by the cheat; exposure spikes.

## 2026-10-22 ps3recomp v0.17.0 integration and SPU helper speedups

- ps3recomp: v0.17.0 (`a6d76c8`) merged into the local fork on branch `motorstorm/v0.17-integration` (worktree `ps3recomp-int/`); the v0.15 fork is preserved as `motorstorm/v0.15-local` / tag `ms-baseline-v0.15-local`. Record: `docs/UPSTREAM_INTEGRATION.md`.
- SPU: SSSE3 quadword byte rotates/shifts and generate-controls; one LS diagnostic gate. Lifted-style microbenchmark 36 -> 10 ns per iteration. Decode-rate effect not yet measured in-game.
- Build: `PORT_SPU_AVX2` (default OFF) compiles the lifted SPU sources with `-mavx2` for upstream's AVX2 float path (#369); fa/fs/fm 15.2 -> 7.4 ns. The exe then checks for AVX2 at startup.
- Runner: `tools/fast_startup.py` appends the Bink decode rate (from the every-256-wakes line) to each run's summary; `fast_startup.py rate <run>` reports it for an existing run.
- Measured (probe `20261022-075236-usleep-hrtimer`, v0.15 fork + high-resolution usleep): 10.49 decoded frames/s; 1.82 host cores during the intro (4.1-4.2 before the timer change).

## 2026-10-22 profiling and post-FX texture format

- Runtime: `sys_timer_usleep` sleeps on a high-resolution timer instead of yield-spinning (the two guest `usleep(200)` pollers held ~2 host cores). Not yet measured in-game.
- Milestones: counter `bink_task_wakes_x256` for fast-profile decode rate.

- Build: translated SPU sources compile with `-msse4.1` when the compiler supports it, so `spu_shufb` uses the SSE4.1 path (21% of the decode thread's samples; 2x faster in a microbenchmark).
- D3D12: Y16_X16_FLOAT (`0x9F`) textures bind, upload and sample as `R16G16_FLOAT`; refused formats are logged once.
- Profiling: `thread_sampler.py` caller attribution for samples in system DLLs.

## 2026-10-21 Bink intro rendering

- D3D12: the exact offscreen render-target match now precedes the display-sized frame-copy fallback, and that fallback only accepts 32-bit colour textures. The original Bink intro renders with motion and colour. Added `tools/test_d3d12_texture_source_order.py`.
- Diagnostics: `DRAWUNITS=N` (`DRAWUNITS_AFTER_MS`) logs each draw's fragment program, target and texture units. The `[SCREENTEX]` binding log now includes the texture address and format.

## 2026-10-21 Bink/FIOS streaming

- Fixed the false NOSYS in `_cellSpursLFQueuePushBody` when another taskset of the same SPURS has the recipient task enabled. Added a regression test.
- The original startup splash screens now render; the Bink intro streams and decodes on the SPU.
- Diagnostics (all off by default):
  - `SPU_STALL_MS` reports stalled SPU contexts with their LS call chain and wait object;
  - `SPU_WS_TRACE=N` and `SPURS_LFQ_TRACE=N` raise the log budgets and add timestamps;
  - `SPU_LFQ_ATOM_EA` accepts up to four lines, with `SPU_LFQ_ATOM_MAX`;
  - PushBody NOSYS paths now log their reason.
- `probe_first_frame.ps1` keeps caller-supplied `SPURS_LFQ_TRACE` and `SPU_LFQ_ATOM_EA` values.

## 2026-10-21 font atlas and GUI intro

- Fixed the cellFont renderer ABI:
  - Create takes `(library, config, renderer*)`.
  - Bind and Destroy take the renderer object's address.
  - Destroy unbinds its fonts.
- With the original disc fonts, the glyph atlas now completes, and the frontend reaches `gui_intro_eu.bik`.
- Font opens use the TTC face index `subNum` and reject non-font data with `OPEN_FAILED`.
- Added f1 handlers for `cellMsgDialogClose` and `cellVoiceSetVolume`, plus the `test_hle_float_args.py` guard.
- `tools/probe_first_frame.ps1` reports process CPU and peak memory at timeout.
- Extracted the remaining 58 disc files (GUI fonts and videos) privately; see BUILD.md.

## 2026-10-21 glyph-atlas stall diagnosis

- Traced the second `func_001E8058` call into `func_005867A8` and its glyph path. After the font open fails, cellFont bind and render return `INVALID_PARAMETER`, three unregistered cellFont NIDs return the default 0, and original atlas packer `func_00584C20` does not return. This is diagnostic only. No runtime behavior or generated code was changed; the probed chunks were restored and rebuilt.

## 2026-10-21 frontend handoff tracing

- Extended the existing reversible private-AOT tracer to correlate multiple original functions in one probe, trace several return sites and labels, and sample hot loops at power-of-two visits. The existing log summarizer can focus on a guest function. Fixed the tracer's CLI help formatting. Six focused tool tests pass.
- Traced the original return chain after `SetExitOnline` into `func_001E8058` and its caller `func_001F5658`. An earlier `func_005867A8` invocation completes a 2,097,152-iteration bitset scan; a later `func_001E8058` invocation has not returned in a bounded probe. This is diagnostic work only; no guest state, compatibility API result, or original code was changed.

## 2026-10-21 frontend diagnostics

- Added opt-in `PS3_CALLTRACE_TOS` and `PS3_CALLTRACE_LR_LO`/`PS3_CALLTRACE_LR_HI` filters to the existing indirect-call trace. They restrict log output and do not alter original call dispatch.
- Mapped the original loading command wrappers and traced `PopulateLoadingScreen` through its scheduled callback and preload status write. Temporary markers in private generated AOT code were removed before the clean native rebuild. No compatibility return value or frontend state was changed.
- Traced the live original dispatcher through its state-`0x10` predicate: original code changes the watched byte from 0 to 1, the predicate succeeds, and `SetExitOnline` executes next. This corrects the earlier hypothesis that the predicate itself was permanently blocking. The next title/menu trigger remains unmapped; no gameplay or compatibility shortcut was added.

## 2026-10-20 focused loading diagnostics

- Added bounded, opt-in `PS3_HLE_AFTER_NID` tracing for later imports from the same PPU thread. `PPU_RWATCH_AFTER_HLE=1` arms an existing read watch only at that import, avoiding early allocations that reuse the watched address. `PS3_HLE_CENSUS=1` samples live PPU threads at 5 and 15 seconds. These diagnostics change no guest return values or state. Private AOT-only save-task probes established the original success path and were removed after the experiment.
- Mapped the `+0x4064` loop and direct writers: zero keeps the original `JobBatchHandler` working; nonzero exits it. Confirmed the save-task state write and the lack of a normal guest-memory read during a bounded post-save watch. No speculative compatibility change was made.

## 2026-10-20 loading-screen pipeline and network state

- Corrected `cellFontOpenFontFile` from a four-argument declaration to the documented five-argument guest ABI. Added opt-in `CELL_FONT_TRACE` and a focused ABI regression. The original calls now reach an actual missing-file result instead of failing on the wrong argument. No font asset or success result is synthesized.

- Extended D3D12 draw texture snapshots, SRV descriptors, root signature, samplers, and render-target transitions from four to the RSX's 16 texture units. Added opt-in PSO/debug-layer and per-draw texture diagnostics; proprietary shader captures remain private. FP `0x02193941` now creates successfully.
- Corrected initialized offline `cellNetCtlGetState` to return success with `Disconnected`, and added a focused lifecycle regression. Original-game network polling no longer repeats a false uninitialized error; a title/menu is still unverified.
- Extended the bounded startup probe limit to 600 seconds for loading-state diagnosis. Read-only event-queue, syscall, guest poll, and guest-memory watches identified active queue delivery and a persistent original worker wait flag; no synchronization behavior was changed. No original game code or assets changed.

## 2026-10-20 first original image

- Corrected D3D12 fragment decompilation to use the recorded RSX export-width bit already stored in the draw and PSO key. The observed half-export shader now returns its final `h0` color instead of an `r0` coordinate intermediate. Added bounded draw-state and vertex diagnostics and updated the opt-in fragment-output diagnostic for MRT shaders; normal rendering has no output override.
- Draw-gated original-game captures produced four consecutive animated loading-icon frames at 1280×720; the user confirmed the icon matches the game. The earlier black captures came from presents without draws. The native build and focused regressions passed; title/menu rendering remains unverified.

## 2026-10-20 event ownership validation

- Added a filtered SPURS event wait diagnostic and used a bounded atomic trace to confirm that original SPU image `283218738` writes event bit `0x0001` at guest flag `0x0140F000` through `GETLLAR`/`PUTLLC`. The PPU wait repeatedly completes. This is a diagnostic change; no event is fabricated.
- Confirmed original RSX draw submissions and repeated guest GCM flip requests after the AOT overlay entries were extended. The initial captured presents were uniformly dark; later draw-gated captures corrected this interpretation.
- Captured black backbuffers and an upstream offscreen snapshot without draw gating. Targeted texture sampling found one empty and one populated on-screen source; this led to the fragment export-mode investigation above.

## 2026-10-20

- Added complete-body fingerprints for locally generated SPU overlays, explicit unknown-body failure, and bounded diagnostics for resident transitions, AOT entries and code-loading DMA tags.
- Added an evidence-gated local overlay discovery tool that matches observed branch targets and LS bytes to private DMA captures, extends existing AOT lifts, and reuses unchanged outputs.
- Lifted additional observed entries in the first MotorStorm overlay (`0x35F18`, `0x35F10`, `0x36B40`) and second (`0x36390`, `0x36E70`) without changing original game code. The latest probe submitted original RSX draw commands; SPU completion, event delivery and frame presentation remain unverified.
- Changed the host SPU run log so an unlifted-branch halt is not called a completed guest job. Added an opt-in per-address SPURS event wait trace.
- Expanded the SPU dispatch regression and added an overlay-discovery regression. No proprietary captures or generated code were added to public source.

## 2026-10-19

- Traced image `283218738`'s indirect branch to a DMA-loaded LS code slot. Added opt-in private capture of distinct DMA body versions and a local-only AOT build script for the two populated versions; zero-filled initial transfers are excluded.
- Added content-at-offset SPU overlay registration and a regression proving late population, correct AOT dispatch and overwrite invalidation (99 checks passed). Linked both locally generated overlays and seeded observed indirect entries. Native runs passed the original LS `0x38790` miss but have not yet completed the whole job or event wait.

- Extended the independently authored direction-3 LFQueue producer to reference-captured repeated submissions, original SPU interim/final waiter registrations, and the observed publication phase wrap. Added a pre-mutation owner-tag check for the generic waiter path. Unverified/full/concurrent states still fail explicitly.
- Updated capture-based planner and native startup regressions. Two bounded Windows probes passed the former Edge Zlib assertion, transferred repeated work items through the original SPU, completed PPU events, read further archive data and reached an unlifted SPU branch at LS `0x38790`. No original frame was presented.
- Rebuilt the native target and passed LFQueue, initializer, silent-audio and public-source audit checks. Private reference captures and native logs remain in ignored build/generated directories.

- Implemented the reference-captured direction-3 LFQueue PushBody first-waiter and uncontended no-waiter producer paths, using guest ring bytes, shared lock-line serialization, and taskset signaling. Unsupported states remain explicit failures before guest mutation.
- Added capture-checked producer and native startup regressions. The original SPU resumed and fetched the work item; startup progressed to an edgezlib queue assertion. No original frame or menu appeared.
- Added a repeatable, bounded import-call inventory and opt-in `FIRST_FRAME` audio policy. The Windows silent output path preserves the real guest mixer, 48 kHz pacing, read cursor and completion events; normal mode is unchanged. Added policy and native silent-audio regressions.
- Rebuilt and compared six-second default/FIRST_FRAME probes. Optional audio initialization was not reached; both remained blocked at explicit LFQueue PushBody unsupported, without an original flip or frame. No network, trophy, input or save-data behavior was changed.

- Added a read-only, bounded `SPURS_SCHED_TRACE` of native taskset bitsets and the full SPURS pointer. Rebuilt and ran a six-second native First Frame probe; PushBody remains explicit unsupported.
- Added an isolated original-firmware direct task-signal control and capture regression. It confirms a successful signal-word transition without task resumption, independent of LFQueue publication. Repeated matched no-push/push captures under RPCS3's static SPU interpreter; no native queue or scheduler behavior was changed.

- Captured original firmware notification arguments in a private post-load RPCS3 reference run: one recipient, task 0, callback success, and a taskset signal-bit transition. The isolated SPU remains blocked, so no native PushBody behavior was changed. Removed the earlier zero-recipient inference from the active findings.

- Added a private SPU wait-object diagnostic based on the original task's observed `queue + 5` value. Matched no-push and firmware-push captures confirm that this correction alone does not deliver the item to the SPU task. Kept native PushBody unsupported.
- Added a bounded First Frame development probe that keeps original PPU/SPU, filesystem and graphics paths active, selects offline network state, and offers an explicit audio-unavailable diagnostic. Its five-second startup trace still stops at PushBody.

- Added isolated SPURS task LS-pattern and blocked-wait controls, reference-log regressions, and a capture-checked pure initial-push planner. A genuine firmware push to a manually registered blocked SPU waiter published the item but did not notify that task; the missing registration step is under investigation.
- Kept native PushBody explicitly unsupported with no guest-state mutation for the game's waiter path. Rebuilt the native executable and repeated the bounded startup and direction-3 initializer regressions. Private debugger captures and generated outputs remain ignored.

## Public distribution policy

- Added private-input and generated-output ignore rules, staged-blob and release-tree audit tooling, a pre-commit hook, distribution rules, and third-party license inventory. Game and firmware code stays in local user-generated artifacts; public compatibility APIs must be independent implementations.
- Five audit regression tests passed. A source-only staging tree including the ps3recomp source and license passed the release audit; excluded upstream generated test fixtures and packaging media. No public release was made.

## 2026-10-17

- Extracted and SHA-256 hashed original `PARAM.SFO` and retail `EBOOT.BIN` from the supplied ISO; recorded complete ISO hash and directory inventory.
- Pinned a full ps3recomp source checkout to the supplied v0.15.0 package's commit.
- Ran the framework ELF parser, PPU loader, PPU lifter, SPU image scan, and fSELF rebuilder against the supplied input. Recorded actual zero-function and retail-encryption blockers.
- Added a guarded reproducible translation/build script, Windows build scripts, and milestone-specific evidence documentation.
- Accepted the user's decrypted ELF as a hashed, separate input; recovered original PPU OPD functions and imports.
- Generated 78 PPU C++ chunks and lifted all 26 embedded SPU images using the pinned ps3recomp source.
- Installed a verified portable Clang 23.1.3 toolchain under `build/` and compiled the framework runtime library.
- Updated the build scripts to use the local toolchain and include the generated SPU workload registry.
- Compiled all generated PPU code. Fixed the first link failure by adding Windows SDK `dxguid.lib` to the game target.
- Switched the native build to the framework's `PORT_SPU_INPUTS` path so SPU programs are generated inside the build tree and compiled into the target.
- Linked the first SPU-inclusive Windows executable and executed original startup code.
- Extracted and hashed the original multi-extent `MS2.PSARC` after startup identified it as missing.
- Identified, extracted and statically lifted the raw Wws_Job SPURS policy module dispatched during startup; added exact fingerprint registration to the game target.
- Verified Wws_Job resolves and executes in the rebuilt native target. Captured the remaining startup task/event signal wait without introducing a fake wakeup.

## 2026-10-18

- Built the official ps3dev PPU/SPU toolchains and PSL1GHT locally in Ubuntu WSL. Added reproducible local build, bounded RPCS3 probe, independently authored LFQueue fixture, and reference-log regression tools. No PS3 fixture binary or firmware output is part of public source.
- Executed genuine firmware PushBody for empty, multi-entry and wraparound cases; captured successful PPU waiter delivery and a partial consumer-word commit transition with an SPU-registered field. Proved a minimal SPURS SPU task executes by DMA-writing a PPU marker and exits cleanly through the task syscall. A no-push control caught the experimental second SPU wait returning task `STAT` with no taskset waiting bit, even with context-save storage; no SPU notification claim or native PushBody implementation was made.

- Located the user-installed firmware `libsre.sprx`, verified its hash and exact `cellSpurs` export for PushBody, and captured a decrypted PRX through a bounded local RPCS3 PPU-debug diagnostic. Restored RPCS3 configuration after the run and kept all firmware images and disassembly in ignored paths.
- Added `tools/inspect_local_spurs_firmware.py` to produce a private metadata-only inventory with validated export-to-ELF address mapping. Confirmed the original direction-3 function calls atomic reservation, ring copy, commit, and notification helpers. Deferred guest-state changes until their packed transitions and waiter signal behavior are verified by a focused original-code call.

- Registered `_cellSpursLFQueuePushBody` with guest pointer/queue validation and an explicit unsupported result for a valid direction-3 push. This removes the previous false-success unresolved import without fabricating a queue entry or signal. Restored bounded queue snapshots in the resolved handler so the initializer regression remains usable.
- Regenerated the HLE NID table, rebuilt and linked the Windows target, and ran an eight-second startup probe. The NID resolved; task 0 and the separate PPU event flag remained blocked. Added an explicit-failure integration gate and a bounded startup probe script. Updated the build script to regenerate NID bindings before building.
- The corrected direction-3 initializer integration regression passed against the final trace. Added a focused incremental Windows build script. Audited a fresh source-only staging tree and confirmed the nested toolkit Git index has no staged files. Documented unresolved legal and anti-circumvention review before any public release.

- Added opt-in `SPURS_LFQ_TRACE` diagnostics for unresolved `_cellSpursLFQueuePushBody`, bounded to eight calls and dumping PPU arguments, queue metadata, and item bytes.
- Rebuilt and linked the native game target; three bounded startup probes verified the missing producer call and unchanged wait state. No synchronization behavior was altered.

- Corrected `_cellSpursLFQueueInitialize` to write the complete guest direction-3 empty state, including zeroed control words, tagged buffer pointer, direction, sentinels, and bounds/alignment validation. The original lifted SPU now follows its ANY2ANY branch and registers a waiter at queue offset `+0x04`.
- Added opt-in `SPU_LFQ_ATOM_EA` tracing for bounded SPU `GETLLAR/PUTLLC` queue snapshots and `tools/test_spurs_lfqueue_init.py` integration regression. Rebuilt and linked Windows x64, then repeated a bounded native startup probe. PushBody remains unresolved; no item publication or signal was added.

## 2026-10-18

- Added a private, ignored RPCS3 GDB breakpoint harness for the original PushBody call and bounded local reference boot. It identified an earlier reproducible null-read freeze at guest `0x00531338`; no firmware code or raw trace was added to public source.
- Repeated the native startup probe and explicit-unsupported LFQueue regression. No public runtime behavior changed because a successful firmware producer transition has not been observed.
- Confirmed the existing direction-3 initializer with its targeted atomic trace and regression test.

- Analyzed private original firmware reservation, commit and notification helpers alongside the original SPU consumer. Documented a partial guest queue field map and the remaining producer state transition in `docs/RESEARCH.md`. No public compatibility behavior changed.
- Diagnosed the saved RPCS3 fault as reported at a NOP return site, leaving the actual null-reading instruction unresolved. Confirmed the native and reference ELF hashes match and no 1.03 update was used.
- Checked isolated PS3 fixture prerequisites: no local PPU/SPU compiler, no PowerPC target in bundled LLVM, and no ps3dev/PSL1GHT installation in WSL.

# Reproducible local workflow

## Runtime tracing without per-probe rebuilds

One-time hooked lift and build, in their own private trees (`generated/ppu` and `build/motorstorm` are not touched):

    py -3 ps3recomp/tools/ppu_lifter.py generated/decrypted/EBOOT.elf --functions generated/analysis/EBOOT.functions.json --hle-stubs generated/analysis/EBOOT.imports.json --output generated/ppu-hooked-staging --jobs 4 --trace-hooks
    py -3 tools/compare_hooked_lift.py generated/ppu-hooked-staging
    cmd /c tools\build_trace_port.cmd

`compare_hooked_lift.py` must report every lifted file equal to `generated/ppu` once hooks are removed; otherwise the lifter or its inputs changed and the hooked tree is not the same translation. Then each probe is configuration only:

    py -3 tools/trace_runtime.py "fn=001E8058,00584C20;regs=r3,r4,r1;stall=5000;profile=10;hle=all;hle_min_us=100000" --seconds 90 --name <name>

It runs `probe_first_frame.ps1 -Exe build/motorstorm-trace/...`, writes `generated/logs/<name>-trace.log`, and summarizes it with `tools/summarize_probe.py`. Keys and event fields: `ps3recomp/docs/TRACING.md`. Without the hooked executable, `--exe build/motorstorm/MotorStormPacificRiftRecomp.exe` still traces imports, syscalls, callbacks and memory watches; guest-hook keys are refused with `ev=config-error`. `tools/trace_frontend.py` remains the fallback for a point the hooks do not expose: one instruction inside straight-line code.

## Focused loading-screen checks

For a repeatable private AOT trace, run `py -3 tools/trace_frontend.py 0x0059F2F8 --after-call 0x0059F978 --seconds 30 --name frontend-check`. The tool inserts bounded entry and selected return-site logging, builds, runs the original game, summarizes the probe, restores the original generated source, and rebuilds the ordinary executable. `--also 0x0059DC60%r6+4` traces another function in the same probe; append `@0x0059F978` to trace a call return. `--include-returns` also records returns from the primary function. `--exit-label` selects a guest label; without a selected point the tool logs all generated returns. `--after-call '0x001E82B8,0x001E82C4'` traces several call returns. `--labels '0x0058716C' --sample-power2` samples a hot guest label at powers of two after the initial limit. `--entry-only --lr-filter 0x001E82B8` keeps large trampolines bounded to the intended caller. Quote comma-separated lists in PowerShell. `--watch-reg r3+4` reads a 32-bit guest field at entry only when that pointer is known valid. Logs and source backups remain under ignored `generated/logs/`. Run `py -3 tools/summarize_probe.py <probe-name> --focus 00782E68` for a compact handoff timeline. Run `py -3 -m unittest discover -s tools -p test_frontend_tools.py` for the tool tests.

For a bounded frontend dispatch trace, set `PS3_CALLTRACE=1`, `PS3_CALLTRACE_LR_LO=0059D000`, and `PS3_CALLTRACE_LR_HI=0059F000` before `tools/probe_first_frame.ps1`. To trace only selected indirect targets, set `PS3_CALLTRACE_TOS` to up to 16 comma-separated hexadecimal guest addresses. These filters do not change guest calls. Store logs under ignored `generated/logs/`; original game inputs and generated AOT source remain private.

To trace the original save-data task without logging every thread, set `PS3_HLE_AFTER_NID=21425307` before a bounded `tools/probe_first_frame.ps1` run. `PS3_HLE_CENSUS=1` adds two live PPU thread/CPU snapshots, approximately 5 and 15 seconds after that import. `PPU_RWATCH=<guest-hex>,<length>` with `PPU_RWATCH_AFTER_HLE=1` starts the existing read watch at that import, avoiding false attribution when boot allocations reuse the address. Confirm the watched object's address in the same run; all resulting logs belong under ignored `generated/logs/`. These settings only report state and are not loading fixes.

For the font ABI regression, run `wsl --cd '<absolute path to ps3recomp>' -- bash -lc 'clang -std=gnu17 -ffunction-sections -fdata-sections -I include libs/font/tests/test_font_open_file_abi.c -Wl,--gc-sections -o /tmp/test_font_open_file_abi && /tmp/test_font_open_file_abi'`. `CELL_FONT_TRACE=1` logs the five raw guest arguments and early return reason during a bounded native probe. The private `generated/analysis/inspect_psarc_fonts.py` experiment reads the user-supplied PSARC manifest; do not copy its private output to public release artifacts. A correct font ABI does not supply missing original TTF assets.

`tools/probe_first_frame.ps1` accepts up to 600 seconds. For a bounded original-game probe, run `./tools/probe_first_frame.ps1 -Seconds 60 -Name loading-check -FirstFrame -AudioPolicy silent` after `cmd /c tools\build_incremental.cmd`. Keep logs and captured shaders under ignored `generated/`. To inspect only the failing fragment PSO, set `RSX_PSO_WATCH_FP=0x02193941` and `RSX_PSO_CAPTURE_DIR=generated/analysis/<local-name>` before the probe; set `D3D12_DBG=1` for D3D12 information-queue errors. The original `0x02193941` PSO now builds. Run `wsl --cd '<absolute path to ps3recomp>' -- bash -lc 'clang -std=gnu17 -ffunction-sections -fdata-sections -I include -I libs/system libs/network/tests/test_netctl_offline_state.c -Wl,--gc-sections -o /tmp/test_netctl_offline_state && /tmp/test_netctl_offline_state'` for the offline network regression. Captured game images and bytecode are private and must not be staged.

## Verify first original loading image

Build with `cmd /c tools\build_incremental.cmd`. In PowerShell, create a private capture directory and select only draw-bearing presents:

```powershell
$frameDir = 'generated/frames/first-original-frame'
New-Item -ItemType Directory -Force -Path $frameDir | Out-Null
$env:CELLMARK_DUMP = '4'
$env:CELLMARK_DUMP_SKIP = '10'
$env:CELLMARK_DUMP_MINDRAWS = '20'
$env:CELLMARK_DUMP_DIR = (Resolve-Path $frameDir).Path
./tools/probe_first_frame.ps1 -Seconds 35 -Name first-original-frame -FirstFrame -AudioPolicy silent
```

Inspect `generated/frames/first-original-frame/frame_*.bmp` for the small centered original loading emblem. Capturing arbitrary guest flips may produce black images because some presents have no draws. All BMPs and logs remain private. For the focused shader test, build `ps3recomp/libs/video/tests/test_fp_decompiler.c` per its header and run it; the current run passed 49 checks. No title screen or menu has been verified.

## Optional locally generated SPU code overlays

For subsequent unknown SPU code, run a bounded local probe with `SPU_DUMP_OVL=generated/overlays/<name>/versions,<LS-base>`, `SPU_DUMP_OVL_VERSIONS=1`, `SPU_OVERLAY_TRACE=1`, `SPU_OVERLAY_TRACE_IMAGE=<image-id>`, and `SPU_OVERLAY_DMA_LSA=<LS-base>`. Then run `py -3 tools/discover_spu_overlays.py --log generated/logs/<probe>-stderr.log --captures generated/overlays/<name>/versions --out generated/overlays/discovered --build`. Discovery requires a real branch miss and a byte-for-byte match at that LS entry before lifting; it merges new entries into an existing private lift of the same body and skips unchanged translations. `port/CMakeLists.txt` includes newly discovered private lifts on the next CMake build. Keep all capture, plan, generated source and executable output under ignored `generated/` and `build/`; never publish them.

After a native build, create private `generated/overlays/spu38790/versions/`, then run a bounded probe with `SPU_DUMP_OVL=generated/overlays/spu38790/versions,0x35F00` and `SPU_DUMP_OVL_VERSIONS=1` in the probe process environment. This records distinct 12 KiB GET bodies loaded into LS `0x35F00`; it does not change guest execution. These binaries and all lifted outputs are ignored and must remain local. `tools/build_port.cmd` calls `tools/build_spu_overlay.py` for the two observed populated SHA-256 versions, then CMake links the resulting private AOT sources if present. A fresh checkout without those local captures still builds without the overlays and reports an unlifted branch when the game reaches them. The script rejects unsupported SPU instructions. Do not publish the generated `overlay.elf`, C, register file, objects or linked executable.

For the SPU runtime regression, the build command is documented at the top of `ps3recomp/runtime/spu/tests/test_spu_lifted_start.c`; link `-lm` on Linux and run the resulting binary. The late-populated overlay case rejects zero, partial, modified and unknown DMA bodies while preserving the legacy continuation-DMA path. Run `py -3 tools/test_discover_spu_overlays.py` for the discovery gate. See `docs/STATUS.md` for the incomplete job/event milestone.

## Current Edge Zlib regression probe

From the project root, rebuild with `cmd /c tools\build_incremental.cmd`, then run `powershell -NoProfile -ExecutionPolicy Bypass -File tools/probe_first_frame.ps1 -Seconds 10 -Name edgezlib-check -FirstFrame -AudioPolicy silent -AtomEa 0x40494E00`. The probe stops the child after the bound and writes private stdout/stderr to `generated/logs/edgezlib-check-*.log`. Run `py -3 tools/test_spurs_lfqueue_push_native.py generated/logs/edgezlib-check-stderr.log generated/logs/edgezlib-check-stdout.log` to check repeated original SPU queue work and absence of the former line-420 assertion. `-AtomEa` filters diagnostics to the observed queue; it is not a runtime queue address. The next observed boundary is an unlifted SPU branch to LS `0x38790` and a separate event wait, with no verified original frame.

For the pure LFQueue planner regression, compile `tools/test_lfq_producer.c` with `cc -std=c11 -Wall -Wextra -Werror -o /tmp/test_lfq_producer tools/test_lfq_producer.c` in WSL and run `/tmp/test_lfq_producer`. The preserved initializer capture is checked with `py -3 tools/test_spurs_lfqueue_init.py generated/logs/startup-lfq-init-final-stderr.log`. Run `cmd /c tools\test_first_frame_silent_runtime.cmd` for the audio integration regression and `py -3 tools/test_audit_public.py` for the public-source audit tests. Release staging must pass `py -3 tools/audit_public.py --tree <release-staging>`.

## FIRST_FRAME development mode

After the normal local build, run `powershell -NoProfile -ExecutionPolicy Bypass -File tools/probe_first_frame.ps1 -FirstFrame -AudioPolicy silent -Seconds 6 -Name first-frame-check`. This selects `FIRST_FRAME=1` and `FIRST_FRAME_AUDIO=silent` only for the bounded child process; `native` and `unavailable` are separate audio choices. The probe keeps the existing offline network setting and original PPU/SPU, filesystem and RSX paths. Default execution is unchanged. On Windows, silent audio initialization runs the guest mixer and its completion events without opening WASAPI. The optional mode logs its use when `cellAudioInit` is actually called.

For an import inventory, set `PS3_HLE_TRACE=3000` around a bounded probe and run `py -3 tools/report_startup_apis.py generated/logs/<name>-stderr.log generated/analysis/EBOOT.imports.json generated/ppu/ppu_hle_nids.cpp`. These inputs and logs remain private. Run `cmd /c tools\\test_first_frame_silent_runtime.cmd` for the native audio cursor/event regression.

All inputs and generated outputs in this workflow remain local. Do not upload the ISO, decrypted ELF, game assets, firmware modules (including `libsre.sprx`), lifted code, or linked executable. See `docs/DISTRIBUTION.md`.

Prerequisites on this Windows host: Node.js, Python 3, CMake, Ninja, and the Visual Studio 2026 x64 build environment. `tools/resolve_env.cmd` locates `vcvars64.bat` via `vswhere` and Python via `C:\Program Files\PyManager\python.exe` or `py -3`; preset `VCVARS` or `PYTHON` to override. A SHA-256-verified Clang 23.1.3 toolchain is available under `build/llvm/` and the build scripts add it to PATH. The supplied binary package is `../ps3recomp-v0.15.0-win-x64`; the local `ps3recomp/` source checkout is pinned to commit `0fe7dbf5db9a467aca268865fb26170ea113c541`.

From the workspace root in PowerShell:

```powershell
node tools/inspect_iso.js '..\MotorStorm - Pacific Rift (USA) (En,Fr,Es).iso' original/game
& 'C:\Program Files\PyManager\python.exe' ps3recomp/tools/unfself.py original/game/PS3_GAME/USRDIR/EBOOT.BIN --info
```

The `unfself.py` output confirms this is retail SELF. The user supplied a decrypted `original/game/PS3_GAME/USRDIR/EBOOT.elf`; a byte-identical copy is at `generated/decrypted/EBOOT.elf` with SHA-256 `bbb7fe2545e54847483439f59cda54e907db23a111d7afe9a1b655624886b287`. The framework's `unfself.py` does not decrypt retail SELF. Do not rename the SELF to `.elf` or lift it directly.

Extract the original multi-extent archive required at startup:

```powershell
node tools/extract_iso_asset.js original/game/manifest.json /PS3_GAME/USRDIR/MS2.PSARC original/game/PS3_GAME/USRDIR/MS2.PSARC
```

The extractor refuses to overwrite an existing destination. The verified output is 4,811,608,561 bytes with SHA-256 `5c76379cbc13c5cf305120640bf0367cce8ebedcd31af61d8c46e73f5df397ec`.

The game's GUI fonts (`PS3_GAME/USRDIR/GUI/FONTS/*.TTF`), GUI videos and the other loose files must also be extracted from the ISO with the same tool, one manifest path at a time. The game opens `/dev_bdvd/PS3_GAME/USRDIR/gui/fonts/{framdcn,kab_plain}.ttf` at frontend start. Do not copy them to `/dev_hdd1`: the game probes that location as its own cache. The 2026-10-21 extraction (58 files; `PS3UPDAT.PUP` skipped) is logged with SHA-256 in `generated/logs/extract-remaining-disc-20261021.log`.

For a complete fresh translation and native build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/recompile.ps1
```

The script validates ELF64 big-endian PowerPC magic, hashes the input, runs the real ps3recomp PPU loader and lifter, generates HLE NID bindings, discovers embedded SPU images, copies the framework's port template to `port/`, then configures and builds with Ninja. `tools/build_port.cmd` lifts the separately identified raw Wws_Job policy module and CMake lifts the 26 embedded SPU ELF images. Logs and generated outputs live under `generated/`; native binaries live under `build/`. SPU lifting fails on unsupported candidates instead of silently substituting behavior.

For the runtime library alone, run `tools\build_runtime.cmd` from a Command Prompt. It successfully produced `build/runtime-clang/ps3recomp_runtime.lib` with Clang 23.1.3. The separate game target is built by `tools\build_port.cmd` using the generated PPU and SPU trees.

The intentional rejection test is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/recompile.ps1 -Elf original/game/PS3_GAME/USRDIR/EBOOT.BIN
```

It must exit 1 with `SELF is rejected`. The native build with 26 embedded SPU images and the raw Wws_Job policy module linked and ran original startup. Set `PS3_VFS_ROOT` to the absolute `original/game` path before launching `build/motorstorm/MotorStormPacificRiftRecomp.exe generated/decrypted/EBOOT.elf`. The current startup trace reaches PSARC reads and SPURS task dispatch, then waits on a task/event signal. See `docs/STATUS.md` and `generated/logs/startup-with-wws-*.log`.

The framework's `tools/test_unfself.py` passed its fSELF round-trip, retail rejection, and symbol recovery checks; see `generated/logs/unfself-test.json`.

For an existing configured native target after a runtime edit, run `tools\build_incremental.cmd`. A full `tools\build_port.cmd` now regenerates the HLE NID table before building, so newly implemented imports are bound. To capture an eight-second local startup trace:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/probe_startup.ps1 -Seconds 8 -Name startup-lfq-check -AtomEa 0x40494E00
python tools/test_spurs_lfqueue_init.py generated/logs/startup-lfq-check-stderr.log
python tools/test_spurs_lfqueue_push_pending.py generated/logs/startup-lfq-check-stderr.log
```

`-AtomEa` is a diagnostic filter for the observed queue and may change between runs. The probe writes local logs under `generated/logs/` and stops the process after the bound. The current PushBody handler reports an explicit unsupported result; passing these tests does **not** establish a functioning queue push.

For a bounded First Frame development run with original PPU/SPU and graphics paths, use `powershell -NoProfile -ExecutionPolicy Bypass -File tools/probe_first_frame.ps1 -Seconds 8 -Name first-frame-check`. This profile uses local game data and offline network state. Add `-SilentAudio` only to test the existing audio-unavailable path; it returns an error to the game rather than pretending audio initialized. `-AtomEa` is an optional diagnostic filter. The script restores inherited environment variables after its run. A timeout or D3D12 initialization is not evidence of a rendered game frame.

For local firmware research after installing user-supplied firmware in RPCS3, enable RPCS3's `PPU Debug` only for a bounded diagnostic run that loads `libsre.sprx`, then restore the prior setting. RPCS3 writes a decrypted PRX under its local `ppu_progs/` directory. Keep that directory private. Once its loader log and dump exist, record the module/export mapping without copying firmware code into source:

```powershell
python tools/inspect_local_spurs_firmware.py build/rpcs3
```

The inventory is written to ignored `generated/firmware_analysis/libsre-inventory.json`. It hashes the retail SELF, decrypted PRX, and x64 cache objects and checks that the export descriptor maps to the dumped ELF entry. The command does not implement PushBody or prove a successful queue operation.

### Isolated LFQueue firmware reference test prerequisite

The upstream [ps3dev toolchain](https://github.com/ps3dev/ps3toolchain) provides the local Ubuntu WSL route for independently authored PS3 reference fixtures. Keep executable outputs and captures under ignored `build/` or `generated/`. The previously included `spurs_test.self` is not a PushBody oracle because it does not import the target NID.

### 2026-10-18 reference environment update

Ubuntu WSL now has a local ps3dev installation under `/home/papand7/ps3ref/install`. The ps3toolchain source is pinned to `de85d7d5d11dc0a99d823ece3d440eea46c34d0f`; PSL1GHT source is pinned to `f649a08fd536a9e27c08c7db2d93a2d7ee4c3bbe`. `tools/ps3ref_wsl_build.sh` builds the required ps3toolchain stages and logs them under `/home/papand7/ps3ref/logs/`. The locally created PSL1GHT archive hash is `05ebe71fcc0eb9779af06e443a146d5ecc953f6d06a96c3cfa8251dc42880e98`. PPU GCC 13.2.0 and SPU GCC 9.5.0 are installed; GDB and extra libraries were not needed.

The original [PSL1GHT SPURS sample](https://github.com/ps3dev/PSL1GHT) built with `tools/ps3ref_wsl_sample.sh /home/papand7/ps3ref/test/spurs`, produced a SELF accepted by RPCS3, and printed `Finalize spurs` in the private warm-run log. The independently authored fixture source is `tools/ps3ref_lfq_probe.c` plus `tools/ps3ref_spu_task.c`. Its private WSL test directory contains the copied PSL1GHT sample Makefile and `spu_bin.h` resource; firmware initializes the taskset and LFQueue rather than the probe fabricating them. Compile the SPU task at LS `0x3A00` with `spu-gcc -O2 -Wl,-Ttext-segment=0x3a00 -Wl,--local-store=0x3a00:0x3ffff`, then build the PPU fixture with `tools/ps3ref_wsl_sample.sh /home/papand7/ps3ref/test/lfq`. Use `TEST_SPU_TASK` or `TEST_PPU_WAITER` on the copied private source to select the diagnostic variant. `TEST_SPU_CONTEXT` plus `TEST_SPU_LS_PATTERN` makes the experimental second wait persist; `TEST_SPU_HOLD_NO_PUSH` exits before producer publication after confirming a held wait, while `TEST_SPU_WAIT_FOR_BLOCK` and `TEST_SPU_NOTIFY_ONLY` capture one original push after the waiting bit appears. `TEST_SPU_QUEUE_ATTACH` and `TEST_TAGGED_SPURS_OWNER` select the attachment and owner variants. These variants still do not perform full SPU consumer registration.

Run a bounded fixture locally with `powershell -NoProfile -ExecutionPolicy Bypass -File tools/probe_ps3ref.ps1 -Self build/ps3ref/lfq.self -Seconds 20 -Name lfq-check`. The script refuses to attach to an existing RPCS3 process, launches its own hidden process, stops it after the bound, and copies logs to ignored `build/ps3ref/`. Run `python tools/test_ps3ref_lfq.py no-waiter build/ps3ref/lfq-pop-wrap-rpcs3.log`, `python tools/test_ps3ref_lfq.py ppu-waiter build/ps3ref/lfq-ppu-waiter-attached-rpcs3.log`, `python tools/test_ps3ref_lfq.py spu-task build/ps3ref/lfq-spu-dma-exit-rpcs3.log`, and `python tools/test_ps3ref_lfq.py spu-wait-control build/ps3ref/lfq-spu-wait-codes-rpcs3.log` against the captured logs. The last mode proves the current experimental SPU wait returns during a no-push control with task `STAT` while the taskset waiting bitset stays zero; it must not be used as notification evidence. On this Windows installation the working Python path was `C:\Program Files\PyManager\python.exe` when `python` was not on PATH.

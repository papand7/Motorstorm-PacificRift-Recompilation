# Architecture

The overview diagram is in the [README](../README.md#architecture). This page names the components and where they
live. Findings about the game itself (guest addresses, frame phases, SPU workloads) are in
[RESEARCH.md](RESEARCH.md) and [STATUS.md](STATUS.md).

## Repositories

| Repository | Workspace path | Contents |
|---|---|---|
| Project (this repository) | workspace root | `AGENTS.md`, `docs/`, `tools/`, `port/`, reviewed `generated/analysis/<task>/` reports |
| ps3recomp fork | `ps3recomp/` (main checkout) and `ps3recomp-<task>/` worktrees | recompiler (`tools/`), runtime (`runtime/`), HLE libraries (`libs/`), tests |

The ps3recomp checkout is its own Git repository with the MotorStorm branches; it is not a subdirectory of this
repository's history. Its `origin` remote is the **public** upstream, so MotorStorm branches must never be pushed
there (see [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md)).

## Build-time pipeline

| Stage | Tool | Output (Git-ignored) |
|---|---|---|
| Disc extraction | `tools/inspect_iso.js`, `tools/extract_iso_asset.js` | `original/game/` |
| Executable check | `ps3recomp/tools/unfself.py --info` (rejects retail SELF) | — |
| PPU analysis + lift | `ps3recomp/tools/ppu_loader.py`, `ppu_lifter.py` | `generated/ppu/` (C++) |
| HLE import table | `ps3recomp/tools/gen_hle_nids.py` | `generated/ppu/ppu_hle_nids.cpp` |
| SPU lift | CMake `PORT_SPU_INPUTS` scan of embedded SPU ELFs; `tools/build_wws_pm.py`, `tools/build_spu_overlay.py` | build tree, `port/spu/`, `generated/overlays/` |
| Native build | `port/CMakeLists.txt` + clang-cl + Ninja | `build/motorstorm*/MotorStormPacificRiftRecomp.exe` |

## Run-time components (ps3recomp)

| Component | Source | Role |
|---|---|---|
| Guest memory | `runtime/memory/` | One 4 GiB reservation shared by PPU code, SPU DMA and RSX. |
| PPU threads | `runtime/syscalls/sys_ppu_thread.c`, `runtime/ppu/` | Each guest thread is a host thread running lifted code. |
| LV2 syscalls and sync | `runtime/syscalls/`, `libs/sync/` | Event flags, queues, mutexes, semaphores, timers. |
| SPURS | `libs/spurs/cellSpurs.c`, `runtime/spu/spurs_*.c` | Kernel, workload admission, task sets, job chains, LFQueues on host lanes. |
| SPU execution | `runtime/spu/` | AOT-lifted SPU programs; `spu_interp.c` fallback for unlifted code; DMA, channels, mailboxes. |
| Graphics | `libs/video/cellGcmSys.c`, `rsx_commands.c`, `rsx_d3d12_backend.c` | Command-buffer drain thread, RSX method decoder, guest VP/FP to HLSL, D3D12 render targets and present. |
| Audio | `libs/audio/cellAudio.c` | Guest mixer ports to WASAPI (gameplay on MultiStream port 0, Bink on port 1). |
| Input | `libs/input/cellPad.c` | XInput, keyboard fallback, scripted pads. |
| File system | `libs/filesystem/cellFs.c` | Guest paths resolved under `PS3_VFS_ROOT`; PSARC archives are read by the game itself. |
| Diagnostics | `include/ps3emu/ps3_ftrace.h`, `runtime/diag/` | Timeline tracing (`PS3_FTRACE`, `PS3_CRITICAL_PATH_TRACE`), frame-perf and RSXI captures. |

## Synchronisation

The game's own primitives carry every PPU/SPU/RSX hand-off: SPURS event flags and LFQueues between PPU and SPU,
GCM labels, reference values and flips between PPU and RSX. The runtime does not add waits the console would not
have, and removing one requires evidence that guest synchronisation stays correct.

## Port project

`port/` is the per-title CMake project: `main.cpp` boots the runtime and enters the lifted ELF, `stubs.cpp` holds
title-specific HLE bridges, `frame_clock_watchdog.h` and `port_cpu.h` are host helpers with tests in `port/tests/`.

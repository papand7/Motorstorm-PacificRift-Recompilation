# Building

This is the short path from a clean checkout to a running native build. Every command below is taken from the
scripts in `tools/`; the long-form log of each step, with verified hashes and probe recipes, is in
[BUILD.md](BUILD.md). No game data is provided by this repository.

## 1. Host requirements

| Component | Notes |
|---|---|
| Windows 11 x64 | The only tested host. Other Windows versions: **not verified**. |
| Visual Studio 2026, x64 C++ workload | Supplies `vcvars64.bat`, the linker and the Windows SDK. `tools/resolve_env.cmd` finds it with `vswhere`; preset `VCVARS` to override. |
| Clang 23.1.3 (`clang-cl`) | Required by ps3recomp. The scripts prefer `build\llvm\clang+llvm-23.1.3-x86_64-pc-windows-msvc\bin` if present, otherwise `clang-cl` on `PATH`. |
| CMake + Ninja | Ninja generator, Release configuration. |
| Python 3 | `tools/resolve_env.cmd` uses `C:\Program Files\PyManager\python.exe` or `py -3`; preset `PYTHON` to override. ps3recomp's Python requirements: `ps3recomp/requirements.txt`. |
| Node.js | ISO inspection and extraction (`tools/inspect_iso.js`, `tools/extract_iso_asset.js`). |
| Direct3D 12 GPU | Any D3D12 adapter; `CELLMARK_IGPU=1` selects an integrated GPU on hybrid systems. |

## 2. Framework checkout

The recompiler and runtime live in `ps3recomp/` at the workspace root, a separate Git repository (see
[ARCHITECTURE.md](ARCHITECTURE.md#repositories)). Its base is commit `0fe7dbf5db9a467aca268865fb26170ea113c541`
(v0.15.0); MotorStorm work is on its `motorstorm/*` and `agent/*` branches. Agents build from their own worktree
(`ps3recomp-<task>/`) by passing it as `PS3RECOMP_DIR`.

## 3. Your game data (local only)

Place your own disc image outside the repository, then extract and verify it as described in
[BUILD.md](BUILD.md):

| Input | Location (Git-ignored) |
|---|---|
| Extracted disc tree | `original/game/` (`node tools/inspect_iso.js <iso> original/game`, then `tools/extract_iso_asset.js` per file) |
| Decrypted executable | `generated/decrypted/EBOOT.elf` — a verified standalone ELF; the retail SELF is rejected. This repository provides no decryption tooling or keys. |
| Lifted PPU source | `generated/ppu/` (written by `ppu_lifter.py`) |
| SPU overlays (optional) | `generated/overlays/` (see BUILD.md, "Optional locally generated SPU code overlays") |

## 4. Build

From the workspace root:

```powershell
# full translation + build (lifts, generates HLE NIDs, configures and builds)
powershell -NoProfile -ExecutionPolicy Bypass -File tools/recompile.ps1

# configure + build build\motorstorm from an existing lift
cmd /c tools\build_port.cmd

# rebuild an already configured build\motorstorm after a source change
cmd /c tools\build_incremental.cmd

# runtime library only
cmd /c tools\build_runtime.cmd
```

`build_port.cmd` configures `port/` with `-DPS3RECOMP_DIR=ps3recomp -DRECOMP_DIR=generated\ppu
-DPORT_SPU_INPUTS=generated\decrypted\EBOOT.elf` and builds with Ninja.

## 5. Run

```powershell
$env:PS3_VFS_ROOT = (Resolve-Path original/game).Path
build\motorstorm\MotorStormPacificRiftRecomp.exe generated\decrypted\EBOOT.elf
```

For bounded, logged runs use `tools/probe_first_frame.ps1` (see [DEVELOPMENT.md](DEVELOPMENT.md)). Logs, frame
captures and HDD images land in Git-ignored `generated/`.

## Known gaps

- A clean-machine build from an empty workspace has **not been re-verified** since the early milestones; report
  any missing step.
- No CI job builds the game: that needs the private inputs. CI checks only the audit, documentation and synthetic
  tool tests ([.github/workflows/ci.yml](../.github/workflows/ci.yml)).

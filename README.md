# MotorStorm: Pacific Rift, PC

A native PC port of **MotorStorm: Pacific Rift** (PlayStation 3, 2008), built by recompiling the game's own code ahead
of time, with an upscaling pipeline and PC settings. For **Windows x64**. **Status: ALPHA.**

> [!WARNING]
> **ALPHA.** The port has not yet been run end to end: the title screen, menus and a full race are not verified
> yet. Expect crashes, graphical faults and missing features. Report what you see with the launcher's log.

> [!NOTE]
> **No game files are included.** The launcher runs only with your own copy of the game: your own disc image or
> disc folder, the 1.03 update, and your own decrypted program files (`EBOOT.elf`) for 1.00 and 1.03. The launcher
> never ships or decrypts game data.

## What it is

The PS3 game's PowerPC and Cell SPU code is translated ahead of time into C++ and built into a native Windows
program. The PS3 system calls the game makes are provided by an independently written compatibility layer, and the
RSX graphics commands are drawn with Direct3D 12 or Vulkan. The game's logic, physics and AI are the original code,
not approximations.

<table>
<tr><th>Original</th><th>Ultra</th></tr>
<tr><td>TODO: original screenshot (none found)</td><td>TODO: Ultra screenshot (none found)</td></tr>
</table>

*TODO: captions for the screenshots once they are chosen.*

## What you need

- Windows 10 or 11, 64-bit, with a graphics card and driver that support Vulkan.
- Your own copy of the game (the US disc, BCUS98155): an `.iso` image, or a folder with `PS3_GAME` in it.
- The 1.03 update package's folder, with its `USRDIR\ms2patch.psarc`.
- Your own decrypted `EBOOT.elf` for version 1.00 (from the disc) and for version 1.03 (from the update), made from
  your own console. The launcher checks each file by its SHA-256 and refuses anything that does not match.
- Free disk space for the tools, the build and the game files, and an internet connection for the first install.
  The launcher downloads its tools from their publishers, checks each download's SHA-256, and asks you to accept
  Microsoft's terms before it installs the Visual C++ and Windows SDK libraries.

## Install

1. Download `MotorStormPacificRift.zip` from the [latest release](https://github.com/papand7/motorstorm-pacific-rift-native/releases/latest)
   and unzip it to a folder of your own.
2. Run `MotorStormPacificRift.exe`.
3. Choose your disc, the 1.03 update folder and the two `EBOOT.elf` files, and press **Install**. The launcher builds
   the game on your PC. It writes everything under a `MotorStorm\` folder beside the exe.
4. Press **Play** when the install is done.

> [!IMPORTANT]
> **The installer cannot finish in this 0.1.0 alpha build.** It builds the game from a source snapshot that the
> launcher does not include yet, because that snapshot still holds upstream runtime key tables that must be removed
> first. Until the next release, the launcher opens and shows its pages, and Install stops with a message that the
> launcher carries no game source.

The launcher keeps a `launcher.log` with every command it ran and its output. Include it when you report a problem.

## Settings

The launcher's **Settings** page and the game's own **PC Settings** pages write to the same file, `play\settings.ini`.

| Setting | Choices |
|---|---|
| Display | Window or full screen |
| Resolution, dynamic resolution, frame rate, vsync | As the port supports them |
| Upscaling | **FSR 1** or **FSR 3.1** (AMD FidelityFX), with FSR 3.1 as the default; FSR 3.1 needs AMD's two DLLs beside the exe, otherwise FSR 1 runs |
| HDR | Off or On |
| Textures | **HD texture pack**: your own game's textures, upscaled on your PC, used when the pack is present |
| Ray-traced sun shadows | Off or On, where the graphics card supports ray queries and DXC is installed |
| Motion blur, anisotropic filtering | As the port supports them |
| Keyboard bindings | All 13 actions, rebindable from the keyboard |

Every choice that needs a missing part (no DXC, no FSR 3.1 DLLs, no HD pack, no ray-tracing GPU) shows the reason
on its page.

## Features

- **Native PC port:** the game's own code, compiled for Windows x64 ahead of time.
- **Upscaling:** FSR 1 and FSR 3.1 (AMD FidelityFX).
- **HD texture pack:** your game's textures upscaled on your PC, applied when the pack is in place.
- **PC Settings pages:** graphics, upscaling and keyboard settings in the game's own menus, generated from your
  copy's data on your PC.
- **Keyboard rebinding:** all 13 actions can be rebound.
- **Ray-traced sun shadows** where the graphics card and the installed tools support them.

## Not in this release

- **Multiplayer:** no online or LAN play.
- **Gamepad rebinding:** not in the alpha. Key bindings are keyboard-only.
- **Ray-traced lighting, reflections and ambient occlusion:** only ray-traced sun shadows are offered.
- **Verified gameplay:** the port has not been run end to end yet (see the status above).

## Building

The launcher is an Electron app in `launcher/electron/`. Its own unit tests run with `node test_settings.js`. The
portable exe is built with `npm run dist:public` (a build without the game source snapshot). Developers who need
the snapshot read [docs/LAUNCHER.md](docs/LAUNCHER.md).

## Status

| Part | State |
|---|---|
| Launcher window and settings | Alpha: unit-tested settings file; the window opens |
| Install from your own files | Not complete in this release (no source snapshot yet) |
| Game in the port | Not verified end to end: title screen, menus and races are not confirmed |
| Upscaling, HD textures, PC Settings pages, keyboard rebinding | Implemented; not yet verified in a running game |

Detailed records are in [docs/STATUS.md](docs/STATUS.md) and [docs/LAUNCHER.md](docs/LAUNCHER.md).

## Credits

- **ps3recomp** by sp00nznet, the static recompilation framework this port is built on (MIT). Pinned to the v0.15.0
  revision.
- **AMD FidelityFX** (FSR 1 and FSR 3.1), redistributed by the launcher's tool step with AMD's licence.
- **DXC** (Microsoft), the shader compiler used for ray-traced shadows.
- **Electron**, **Clang/LLVM**, **CMake**, **Ninja**, **Python** and the Vulkan SDK components, each downloaded by the
  launcher from its publisher.

Third-party components and their licences: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## License

The launcher's package is marked MIT (`launcher/electron/package.json`). No root `LICENSE` file has been added to this
repository yet; the owner must confirm the project's licence before a public release. This project contains none of
MotorStorm's code or files: MotorStorm is the property of its owners, and this port is not affiliated with Sony
Interactive Entertainment or Evolution Studios.
